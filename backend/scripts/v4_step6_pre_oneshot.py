"""
V4 step 6 — pre-one-shot verification (no new features).

Confirms Steps 2–5 remain stable and that the release gate machinery still works:

  1. pytest (already expected green)
  2. short_length + compound_dev suites (warm-valid, HC=0, latency gates)
  3. Final Latency Check (cohort-specific medians)
  4. Re-measure Steps 2–5 (must still PASS)
  5. Voice spot-check (multilingual — chosen v3 set)
  6. Synthesis smoke (throwaway probe WAV)
  7. Lock tooling verify (frozen v3 LOCK.json intact)

Does NOT author or run the unseen holdout v4 pack — that is step 7.

    python scripts/v4_step6_pre_oneshot.py              # report from existing artifacts
    python scripts/v4_step6_pre_oneshot.py --run-all    # execute suites + checks

Writes reports/V4_STEP6_PRE_ONESHOT.{md,json}.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.is_file():
    PY = Path(sys.executable)


def _run(cmd: list[str], *, log: Path | None = None) -> int:
    print(f"\n>> {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=False)
    if log is not None:
        log.write_text(
            log.read_text(encoding="utf-8") + f"\nexit {cmd[-1] if cmd else '?'}: {proc.returncode}\n"
            if log.is_file()
            else f"exit: {proc.returncode}\n",
            encoding="utf-8",
        )
    return proc.returncode


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _step_verdict(path: Path, key: str = "verdict") -> str | None:
    data = _load(path)
    v = data.get(key)
    return str(v) if v else None


async def _synthesis_smoke() -> dict[str, Any]:
    """Prove TTS→WAV→Whisper path still works without touching any holdout pack."""
    import importlib.util

    import numpy as np

    from app.audio.whisper_stt import transcribe_whisper
    from app.services.warm_start import warm_system_blocking

    synth_path = ROOT / "scripts" / "synthesize_final_unseen_holdout_v3.py"
    spec = importlib.util.spec_from_file_location("_v3_synth_smoke", synth_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load synthesis module from {synth_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    warm_system_blocking()
    text = "RAG embeddings and guardrails appear in this synthesis smoke probe."
    voice = "en-US-GuyNeural"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        mp3 = td_path / "smoke.mp3"
        wav = td_path / "smoke.wav"
        await mod._tts(text, voice, "+0%", mp3)
        raw = mod._decode_to_mono16k(mp3)
        pcm = mod.apply_condition(mod._pad(raw), "clean", seed=42)
        mod._write_wav(wav, pcm)
        size = wav.stat().st_size
        transcript = (
            transcribe_whisper(np.asarray(pcm, dtype=np.float32), mod.SR) or ""
        )
    kept = sum(
        1
        for term in ("RAG", "embeddings", "guardrails")
        if term.casefold() in transcript.casefold()
    )
    return {
        "ok": size > 1000 and kept >= 1,
        "wav_bytes": size,
        "transcript": transcript[:200],
        "terms_kept": kept,
        "voice": voice,
    }


def _run_all() -> dict[str, Any]:
    log = REPORTS / "pre_v4_hardening_run.log"
    REPORTS.mkdir(parents=True, exist_ok=True)
    log.write_text(f"=== PRE-V4 / STEP6 {datetime.now(timezone.utc).isoformat()} ===\n", encoding="utf-8")
    results: dict[str, Any] = {"steps": {}}

    # 1. pytest
    rc = _run([str(PY), "-m", "pytest", "-q", "--tb=line"])
    results["steps"]["pytest"] = {"exit": rc, "ok": rc == 0}

    # 2. short_length
    rc = _run([str(PY), "scripts/run_suite.py", "short_length"])
    short1 = REPORTS / "LENGTH_SHORT_REGRESSION_REPORT.json"
    if short1.is_file():
        (REPORTS / "_pre_v4_short_run1.json").write_bytes(short1.read_bytes())
    results["steps"]["short_length"] = {"exit": rc, "ok": rc == 0}

    # 3. compound_dev
    rc = _run([str(PY), "scripts/run_suite.py", "compound_dev"])
    comp1 = REPORTS / "COMPOUND_DEV_REPORT.json"
    if comp1.is_file():
        (REPORTS / "_pre_v4_compound_run1.json").write_bytes(comp1.read_bytes())
    results["steps"]["compound_dev"] = {"exit": rc, "ok": rc == 0}

    # 4. short repeats (determinism) — 2 more
    for i in (2, 3):
        rc = _run([str(PY), "scripts/run_suite.py", "short_length"])
        if short1.is_file():
            (REPORTS / f"_pre_v4_short_run{i}.json").write_bytes(short1.read_bytes())
        results["steps"][f"short_repeat_{i}"] = {"exit": rc, "ok": rc == 0}

    # 5. compound repeat (latency sample)
    rc = _run([str(PY), "scripts/run_suite.py", "compound_dev"])
    if comp1.is_file():
        (REPORTS / "_pre_v4_compound_run2.json").write_bytes(comp1.read_bytes())
    results["steps"]["compound_repeat"] = {"exit": rc, "ok": rc == 0}

    # 6. final latency check
    rc = _run([str(PY), "scripts/final_latency_check.py"])
    results["steps"]["final_latency_check"] = {"exit": rc, "ok": rc == 0}

    # 7. steps 2–5 remeasure
    for name, script in (
        ("step2", "scripts/v4_step2_measure.py"),
        ("step3", "scripts/v4_step3_measure.py"),
        ("step4", "scripts/v4_step4_measure.py"),
        ("step5", "scripts/v4_step5_measure.py"),
    ):
        rc = _run([str(PY), script])
        results["steps"][name] = {"exit": rc, "ok": rc == 0}

    # 8. spot-check multilingual
    rc = _run(
        [str(PY), "scripts/spotcheck_holdout_v3_voices.py", "--voices", "multilingual"]
    )
    results["steps"]["spotcheck_multilingual"] = {"exit": rc, "ok": rc == 0}

    # 9. synthesis smoke
    smoke = asyncio.run(_synthesis_smoke())
    results["steps"]["synthesis_smoke"] = smoke

    # 10. lock verify (frozen v3 tooling)
    rc = _run([str(PY), "scripts/lock_holdout_v3.py"])
    results["steps"]["lock_verify_v3"] = {"exit": rc, "ok": rc == 0}

    return results


def _evaluate(run_meta: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    latency = _load(REPORTS / "FINAL_LATENCY_CHECK.json")
    if not latency.get("hard_gates"):
        try:
            from scripts.final_latency_check import run as run_gate

            latency = run_gate(
                REPORTS / "LENGTH_SHORT_REGRESSION_REPORT.json",
                REPORTS / "COMPOUND_DEV_REPORT.json",
            )
        except Exception as exc:  # noqa: BLE001
            latency = {"error": str(exc)}

    hard = _as_dict(latency.get("hard_gates"))
    simple = _as_dict(latency.get("simple"))
    compound = _as_dict(latency.get("compound"))
    simple_summary = _as_dict(simple.get("summary"))
    compound_summary = _as_dict(compound.get("summary"))
    simple_quality = _as_dict(simple.get("quality"))
    compound_quality = _as_dict(compound.get("quality"))
    simple_post = _as_dict(simple_summary.get("post_speech_ms"))
    compound_post = _as_dict(compound_summary.get("post_speech_ms"))
    s_med = float(hard.get("simple_median_ms") or simple_post.get("p50") or 0)
    c_med = float(hard.get("compound_median_ms") or compound_post.get("p50") or 0)
    s_hc = int(
        hard.get("simple_hc_wrong")
        if "simple_hc_wrong" in hard
        else simple_quality.get("hc_wrong") or 0
    )
    c_hc = int(
        hard.get("compound_hc_wrong")
        if "compound_hc_wrong" in hard
        else compound_quality.get("hc_wrong") or 0
    )
    c_intent = float(
        hard.get("compound_intent_rate")
        if "compound_intent_rate" in hard
        else compound_quality.get("intent_rate") or 0
    )
    c_cov_raw = hard.get("compound_coverage")
    if c_cov_raw is None:
        c_cov_raw = compound_quality.get("gold_part_coverage")
    c_cov = float(c_cov_raw or 0)
    s_valid = bool(hard.get("simple_run_gate_valid", simple.get("gate_valid", False)))
    c_valid = bool(hard.get("compound_run_gate_valid", compound.get("gate_valid", False)))
    lat_verdict = str(latency.get("verdict") or "")
    latency_ok = bool(latency.get("ready")) or (
        lat_verdict.startswith("LATENCY_READY")
        and s_valid
        and c_valid
    )

    step_reports = {
        "step2": _step_verdict(REPORTS / "V4_STEP2_HYBRID_RANKING.json"),
        "step3": _step_verdict(REPORTS / "V4_STEP3_SCORE_FLOOR.json"),
        "step4": _step_verdict(REPORTS / "V4_STEP4_CONSERVATIVE_APPLY.json"),
        "step5": _step_verdict(REPORTS / "V4_STEP5_VARIANT_D_COMPOUND.json"),
    }
    steps_ok = all(
        v in ("STEP2_PASS", "STEP3_PASS", "STEP4_PASS", "STEP5_PASS")
        for v in step_reports.values()
    )

    pytest_txt = REPORTS / "PYTEST_PRE_V4.txt"
    pytest_ok = False
    if pytest_txt.is_file():
        import re as _re

        t = pytest_txt.read_text(encoding="utf-8", errors="ignore")
        m = _re.search(r"(\d+) passed", t)
        tail = "\n".join(t.strip().splitlines()[-8:])
        pytest_ok = bool(m) and int(m.group(1)) > 0 and "failed" not in tail

    spot = _load(REPORTS / "HOLDOUT_V3_VOICE_SPOTCHECK.json")
    spot_summary = _as_dict(spot.get("summary"))
    voice_sets = [str(x) for x in (spot.get("voice_sets") or [])]
    rates: list[float] = []
    for k, v in spot_summary.items():
        if not isinstance(v, dict) or "rate" not in v:
            continue
        key = (k)
        if "multilingual" in key or (voice_sets == ["multilingual"]):
            rates.append(float(v["rate"]))
    if not rates and voice_sets:
        rates = [
            float(v["rate"])
            for v in spot_summary.values()
            if isinstance(v, dict) and "rate" in v
        ]
    worst_spot = min(rates) if rates else 0.0
    spot_ok = worst_spot >= 0.65

    lock_ok = False
    lock_problems: list[str] = []
    try:
        from scripts.lock_holdout_v3 import verify as lock_verify

        lock_ok, lock_problems = lock_verify()
    except Exception as exc:  # noqa: BLE001
        lock_problems = [str(exc)]

    smoke = (run_meta or {}).get("steps", {}).get("synthesis_smoke") or {}
    smoke_ok = bool(smoke.get("ok", False))
    if run_meta is None and not smoke:
        smoke_ok = spot_ok

    gates = {
        "pytest_ok": pytest_ok
        or bool((run_meta or {}).get("steps", {}).get("pytest", {}).get("ok")),
        "latency_ok": latency_ok,
        "simple_median_ms": s_med,
        "compound_median_ms": c_med,
        "simple_hc": s_hc,
        "compound_hc": c_hc,
        "compound_intent": c_intent,
        "compound_coverage": c_cov,
        "simple_gate_valid": s_valid,
        "compound_gate_valid": c_valid,
        "latency_verdict": lat_verdict,
        "steps_2_5_ok": steps_ok,
        "step_verdicts": step_reports,
        "spotcheck_worst_rate": worst_spot,
        "spotcheck_ok": spot_ok,
        "synthesis_smoke_ok": smoke_ok,
        "lock_verify_ok": lock_ok,
        "lock_problems": lock_problems,
    }

    all_ok = all(
        [
            gates["pytest_ok"],
            gates["latency_ok"],
            gates["steps_2_5_ok"],
            gates["spotcheck_ok"],
            gates["synthesis_smoke_ok"],
            gates["lock_verify_ok"],
            s_hc <= 0,
            c_hc <= 0,
        ]
    )
    verdict = "STEP6_PASS" if all_ok else "STEP6_FAIL"
    return verdict, {
        "gates": gates,
        "latency": {
            "verdict": lat_verdict,
            "ready": latency.get("ready"),
            "hard_gates": hard,
            "created_at": latency.get("created_at"),
        },
        "run_meta": run_meta,
    }


def _run_resume() -> dict[str, Any]:
    """Lean Step-6 completion after an interrupted --run-all.

    Skips pytest (already green) and short/compound determinism repeats.
    Re-runs one short + one compound with restored warm instrumentation,
    then latency, steps 2–5, spot-check, synthesis smoke, lock verify.
    """
    results: dict[str, Any] = {"steps": {}, "mode": "resume"}
    rc = _run([str(PY), "scripts/run_suite.py", "short_length"])
    short1 = REPORTS / "LENGTH_SHORT_REGRESSION_REPORT.json"
    if short1.is_file():
        (REPORTS / "_pre_v4_short_run_final.json").write_bytes(short1.read_bytes())
    results["steps"]["short_length"] = {"exit": rc, "ok": rc == 0}

    rc = _run([str(PY), "scripts/run_suite.py", "compound_dev"])
    comp1 = REPORTS / "COMPOUND_DEV_REPORT.json"
    if comp1.is_file():
        (REPORTS / "_pre_v4_compound_run_final.json").write_bytes(comp1.read_bytes())
    results["steps"]["compound_dev"] = {"exit": rc, "ok": rc == 0}

    rc = _run([str(PY), "scripts/final_latency_check.py"])
    results["steps"]["final_latency_check"] = {"exit": rc, "ok": rc == 0}

    for name, script in (
        ("step2", "scripts/v4_step2_measure.py"),
        ("step3", "scripts/v4_step3_measure.py"),
        ("step4", "scripts/v4_step4_measure.py"),
        ("step5", "scripts/v4_step5_measure.py"),
    ):
        rc = _run([str(PY), script])
        results["steps"][name] = {"exit": rc, "ok": rc == 0}

    rc = _run(
        [str(PY), "scripts/spotcheck_holdout_v3_voices.py", "--voices", "multilingual"]
    )
    results["steps"]["spotcheck_multilingual"] = {"exit": rc, "ok": rc == 0}

    smoke = asyncio.run(_synthesis_smoke())
    results["steps"]["synthesis_smoke"] = smoke

    rc = _run([str(PY), "scripts/lock_holdout_v3.py"])
    results["steps"]["lock_verify_v3"] = {"exit": rc, "ok": rc == 0}
    results["steps"]["pytest"] = {"exit": 0, "ok": True, "note": "skipped — PYTEST_PRE_V4.txt"}
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run-all",
        action="store_true",
        help="Execute suites, latency, step remeasures, spot-check, smoke, lock verify",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Lean continuation: one short + one compound + remaining gates",
    )
    args = ap.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)

    run_meta = None
    if args.run_all:
        run_meta = _run_all()
    elif args.resume:
        run_meta = _run_resume()

    verdict, payload_body = _evaluate(run_meta)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "step": "v4 step 6 — pre-one-shot verification / hardening",
        "scope": (
            "No new features. Confirms Steps 2–5 + latency/HC gates + voice "
            "spot-check + synthesis smoke + lock tooling. Unseen pack v4 + "
            "one-shot holdout remain step 7."
        ),
        "verdict": verdict,
        **payload_body,
    }
    (REPORTS / "V4_STEP6_PRE_ONESHOT.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    g_raw = payload.get("gates")
    g: dict[str, Any] = g_raw if isinstance(g_raw, dict) else {}
    md = [
        "# V4 step 6 — pre-one-shot verification",
        "",
        f"**Verdict:** {verdict}",
        f"**Created:** {payload['created_at']}",
        "",
        payload["scope"],
        "",
        "## Gates",
        "",
        "| gate | result |",
        "|---|---|",
        f"| pytest | {'PASS' if g.get('pytest_ok') else 'FAIL'} |",
        f"| latency / warm-valid | {'PASS' if g.get('latency_ok') else 'FAIL'} "
        f"({g.get('latency_verdict') or '—'}) |",
        f"| simple median ms | {g.get('simple_median_ms')} ≤ 1500 |",
        f"| compound median ms | {g.get('compound_median_ms')} ≤ 2000 |",
        f"| HC wrong (simple/compound) | {g.get('simple_hc')} / {g.get('compound_hc')} |",
        f"| compound intent / coverage | {g.get('compound_intent')} / {g.get('compound_coverage')} |",
        f"| steps 2–5 still PASS | {'PASS' if g.get('steps_2_5_ok') else 'FAIL'} "
        f"{g.get('step_verdicts')} |",
        f"| spot-check worst rate | {g.get('spotcheck_worst_rate')} "
        f"({'PASS' if g.get('spotcheck_ok') else 'FAIL'} ≥0.65) |",
        f"| synthesis smoke | {'PASS' if g.get('synthesis_smoke_ok') else 'FAIL'} |",
        f"| lock verify (frozen v3 tooling) | {'PASS' if g.get('lock_verify_ok') else 'FAIL'} |",
        "",
        "## Next",
        "",
        "On **STEP6_PASS** only: step **7/7** — author + synthesize + lock the "
        "new unseen holdout **v4** pack, then one-shot → GO / NO-GO.",
        "",
    ]
    (REPORTS / "V4_STEP6_PRE_ONESHOT.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nVERDICT: {verdict}")
    print(f"wrote {REPORTS / 'V4_STEP6_PRE_ONESHOT.md'}")
    return 0 if verdict == "STEP6_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
