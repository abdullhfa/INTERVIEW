"""
Run Final Unseen Holdout v3 — ONCE.

This wrapper exists so the one-shot rule is enforced by code rather than by
memory, and so an infrastructure failure is never mistaken for a v3 result.

Consumption rule (what “uses up” the unseen pack):
  - Preflight / pre-scoring faults do NOT consume v3. They write only
    reports/V3_PRECHECK_FAILURE.json and may be fixed and retried.
  - The moment the first scored clip finishes, V3_RUN_RECORD.json is created
    with status STARTED. From that point the pack is consumed: no full rerun.
  - Completing all scored clips → VALID.
  - Crash / abort after STARTED → VOID (partial scores already observed).
    Full restart from clip 1 is forbidden. Safe resume of unscored clips is
    not implemented here; VOID means a new unseen pack (v4) is required.

Preflight (all must hold, or nothing runs; no consuming record):
  1. pack built, gold present, no gold leaked into scripts.json
  2. every WAV present
  3. LOCK.json verifies byte-for-byte
  4. reports/FINAL_LATENCY_CHECK.json says LATENCY_READY_FOR_V3 and both
     cohorts are warm-valid
  5. no consuming V3_RUN_RECORD (STARTED / VALID / VOID / legacy in-progress)

Outcome classification:
  PRECHECK_FAILED — infrastructure fault before first scored clip (lock,
                    missing WAV, cold latency gate, crash before scoring).
                    Fix and run again. Not a v3 result.
  VALID           — first scored clip started and the suite finished. Whatever
                    it scored is the v3 result, including Whisper variance.
  VOID            — scoring started then aborted / incomplete / post-score
                    warm-valid failure after partial or full observation.
                    Pack consumed; no full rerun.

    python scripts/run_holdout_v3.py
    python scripts/run_holdout_v3.py --preflight-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
PACK_ROOT = ROOT.parent / "frontend" / "public" / "voice-drill" / "final-unseen-holdout-v3"
RUN_RECORD = REPORTS / "V3_RUN_RECORD.json"
PRECHECK_FAILURE = REPORTS / "V3_PRECHECK_FAILURE.json"

# Statuses that mean the unseen pack has already been exposed / consumed.
CONSUMING_OUTCOMES = frozenset({
    "STARTED",
    "VALID",
    "VOID",
    "IN_PROGRESS",  # legacy: old wrapper wrote this before first clip
})

GATES = {
    "intent_rate": 0.92,
    "hc_wrong": 0,
    "meaning_lost_rate": 0.01,
    "compound_gold_part_coverage": 0.90,
    "simple_median_post_ms": 1500.0,
    "compound_median_post_ms": 2000.0,
}
TARGETS = {"simple_p95_post_ms": 2000.0, "compound_p95_post_ms": 3000.0}
EXPECTED_SCORED = 120


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_precheck_failure(problems: list[str], info: dict) -> None:
    _write_json(
        PRECHECK_FAILURE,
        {
            "created_at": _utc_now(),
            "pack": "final-unseen-holdout-v3",
            "outcome": "PRECHECK_FAILED",
            "problems": problems,
            "info": info,
            "note": (
                "Precheck only — V3_RUN_RECORD was not created. "
                "Fix and run again; v3 is not consumed."
            ),
        },
    )


def write_run_record(payload: dict) -> None:
    _write_json(RUN_RECORD, payload)


def _record_is_consuming(prev: dict) -> bool:
    outcome = str(prev.get("outcome") or "")
    if outcome in CONSUMING_OUTCOMES:
        return True
    # Legacy RUN_INVALID after scoring started still consumes the pack.
    if outcome == "RUN_INVALID" and prev.get("first_scored_at"):
        return True
    if outcome == "RUN_INVALID" and prev.get("scoring_started"):
        return True
    return False


def preflight() -> tuple[bool, list[str], dict]:
    problems: list[str] = []
    info: dict = {}

    scripts_path = PACK_ROOT / "scripts.json"
    gold_path = PACK_ROOT / "gold.json"
    if not scripts_path.is_file():
        problems.append("pack not built (scripts.json missing)")
        return False, problems, info
    rows = json.loads(scripts_path.read_text(encoding="utf-8"))
    info["clips"] = len(rows)
    info["scored_clips"] = sum(1 for r in rows if not r.get("warmup"))
    if not gold_path.is_file():
        problems.append("gold.json missing")
    if any("expected_intent_ids" in r for r in rows):
        problems.append("gold leaked into runtime scripts.json")

    missing = [r["file"] for r in rows if not (PACK_ROOT / r["file"]).is_file()]
    if missing:
        problems.append(f"{len(missing)} WAV(s) missing (e.g. {missing[0]})")

    from scripts.lock_holdout_v3 import verify as verify_lock  # type: ignore

    locked, lock_problems = verify_lock()
    info["locked"] = locked
    if not locked:
        problems.extend(f"lock: {p}" for p in lock_problems[:5])

    gate_path = REPORTS / "FINAL_LATENCY_CHECK.json"
    if not gate_path.is_file():
        problems.append("FINAL_LATENCY_CHECK.json missing — run the hardening suite first")
    else:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        info["latency_verdict"] = gate.get("verdict")
        info["simple_warm_valid"] = gate.get("simple", {}).get("gate_valid")
        info["compound_warm_valid"] = gate.get("compound", {}).get("gate_valid")
        if gate.get("verdict") != "LATENCY_READY_FOR_V3":
            problems.append(f"latency gate verdict is {gate.get('verdict')}")
        if not info["simple_warm_valid"]:
            problems.append("simple cohort run was not warm-valid")
        if not info["compound_warm_valid"]:
            problems.append("compound cohort run was not warm-valid")

    if RUN_RECORD.is_file():
        prev = json.loads(RUN_RECORD.read_text(encoding="utf-8"))
        info["previous_record"] = {
            "outcome": prev.get("outcome"),
            "started_at": prev.get("started_at"),
            "first_scored_at": prev.get("first_scored_at"),
        }
        if _record_is_consuming(prev):
            problems.append(
                f"v3 already consumed at {prev.get('started_at') or prev.get('first_scored_at')} "
                f"({prev.get('outcome')}). Full rerun forbidden; new unseen pack required."
            )
        else:
            # Stale non-consuming artifact (e.g. old preflight wrote RUN_INVALID).
            info["stale_nonconsuming_record"] = True

    return (not problems), problems, info


def _scored(payload: dict) -> list[dict]:
    rows = payload.get("results") or []
    return [r for r in rows if not str(r.get("notes") or "").startswith("warmup:")] or rows


def evaluate(payload: dict) -> dict:
    rows = _scored(payload)
    filters = payload.get("filters") or {}
    n = len(rows)
    warm_flags = [
        bool((r.get("post_speech_trace") or {}).get("alias_matrix_ready"))
        for r in rows
    ]
    warm_valid = bool(filters.get("gate_valid")) and all(warm_flags) and bool(warm_flags)

    intent_ok = sum(1 for r in rows if r.get("intent_ok"))
    hc = sum(1 for r in rows if r.get("high_confidence_wrong"))
    meaning_lost = sum(
        1 for r in rows if (r.get("post_speech_trace") or {}).get("meaning_lost")
        or r.get("fail_bucket") == "stt_wrong_meaning_lost"
    )
    simple = [r for r in rows if (r.get("question_type_label") or "") in
              {"ultra_short", "short", "medium", "long", "very_long",
               "indirect_paraphrase", "follow_up_contextual"}]
    compound = [r for r in rows if (r.get("question_type_label") or "") == "compound"]

    def med(vals: list[float]) -> float:
        return round(sorted(vals)[len(vals) // 2], 1) if vals else 0.0

    def p95(vals: list[float]) -> float:
        if not vals:
            return 0.0
        o = sorted(vals)
        return round(o[min(len(o) - 1, max(0, round((len(o) - 1) * 0.95)))], 1)

    def posts(rs: list[dict]) -> list[float]:
        return [float((r.get("timings") or {}).get("post_speech_ms") or 0.0) for r in rs]

    cov_rows = [r for r in compound if r.get("gold_part_coverage") is not None]
    coverage = (round(sum(float(r["gold_part_coverage"]) for r in cov_rows) / len(cov_rows), 4)
                if cov_rows else None)

    simple_p95_post_ms = p95(posts(simple))
    compound_p95_post_ms = p95(posts(compound))

    measured = {
        "n": n,
        "intent_rate": round(intent_ok / n, 4) if n else 0.0,
        "hc_wrong": hc,
        "meaning_lost_rate": round(meaning_lost / n, 4) if n else 0.0,
        "compound_gold_part_coverage": coverage,
        "simple_median_post_ms": med(posts(simple)),
        "compound_median_post_ms": med(posts(compound)),
        "simple_p95_post_ms": simple_p95_post_ms,
        "compound_p95_post_ms": compound_p95_post_ms,
        "whisper_pass_counts": {
            str(k): sum(1 for r in rows
                        if int((r.get("post_speech_trace") or {}).get("whisper_call_count") or 0) == k)
            for k in (1, 2, 3)
        },
        "transcripts_repaired": sum(
            1 for r in rows if (r.get("post_speech_trace") or {}).get("transcript_repaired")
        ),
    }
    gates = {
        "intent_rate": measured["intent_rate"] >= GATES["intent_rate"],
        "hc_wrong": measured["hc_wrong"] <= GATES["hc_wrong"],
        "meaning_lost_rate": measured["meaning_lost_rate"] <= GATES["meaning_lost_rate"],
        "compound_gold_part_coverage": (
            coverage is None or coverage >= GATES["compound_gold_part_coverage"]
        ),
        "simple_median_post_ms": measured["simple_median_post_ms"] <= GATES["simple_median_post_ms"],
        "compound_median_post_ms": (
            measured["compound_median_post_ms"] <= GATES["compound_median_post_ms"]
        ),
        "warm_valid": warm_valid,
    }
    targets_met = {
        "simple_p95_post_ms": simple_p95_post_ms <= TARGETS["simple_p95_post_ms"],
        "compound_p95_post_ms": compound_p95_post_ms <= TARGETS["compound_p95_post_ms"],
    }
    return {
        "warm_valid": warm_valid,
        "measured": measured,
        "hard_gates": gates,
        "targets_met": targets_met,
        "all_gates_pass": all(gates.values()),
        "per_clip": [
            {
                "clip": r.get("sample_id"),
                "question_type": r.get("question_type_label"),
                "condition": r.get("condition"),
                "accent": r.get("accent_label"),
                "raw_transcript": (r.get("post_speech_trace") or {}).get("raw_transcript"),
                "repaired_transcript": (r.get("post_speech_trace") or {}).get("repaired_transcript"),
                "whisper_pass_count": (r.get("post_speech_trace") or {}).get("whisper_call_count"),
                "warm_valid": (r.get("post_speech_trace") or {}).get("alias_matrix_ready"),
                "intent_ok": r.get("intent_ok"),
                "hc_wrong": r.get("high_confidence_wrong"),
                "meaning_lost": r.get("fail_bucket") == "stt_wrong_meaning_lost",
                "gold_part_coverage": r.get("gold_part_coverage"),
                "post_speech_ms": round(float((r.get("timings") or {}).get("post_speech_ms") or 0.0), 1),
            }
            for r in rows
        ],
    }


def write_verdict(outcome: str, detail: dict, problems: list[str]) -> None:
    payload = {
        "created_at": _utc_now(),
        "pack": "final-unseen-holdout-v3",
        "outcome": outcome,
        "problems": problems,
        **detail,
    }
    (REPORTS / "FINAL_UNSEEN_HOLDOUT_V3_VERDICT.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Final Unseen Holdout v3 — verdict",
        "",
        f"**Outcome:** {outcome}",
        f"**Created:** {payload['created_at']}",
        "",
    ]
    if outcome == "PRECHECK_FAILED":
        lines += [
            "This is **not** a v3 result and **does not consume** the pack.",
            "Only `V3_PRECHECK_FAILURE.json` was written. Fix and run again.",
            "",
        ] + [f"- {p}" for p in problems] + [""]
    elif outcome == "VOID":
        lines += [
            "Scoring had already started. Partial (or cold) results were observed, so",
            "the unseen pack is **consumed**. Full rerun from clip 1 is forbidden.",
            "A new unseen pack (v4) is required if you need another official gate.",
            "",
        ] + [f"- {p}" for p in problems] + [""]
        if detail.get("measured"):
            m = detail["measured"]
            lines += [
                f"- Scored clips observed: {m.get('n')}",
                "",
            ]
    else:
        m, g = detail["measured"], detail["hard_gates"]
        lines += [
            "The system was warm, the pack was locked, and the run completed. Whatever",
            "is below is the v3 result — including clips lost to Whisper variance.",
            "",
            "## Hard gates",
            "",
            "| Gate | Measured | Threshold | Result |",
            "|---|---|---|---|",
            f"| Overall intent | {m['intent_rate']} | >= {GATES['intent_rate']} | "
            f"{'PASS' if g['intent_rate'] else 'FAIL'} |",
            f"| HC wrong | {m['hc_wrong']} | = 0 | {'PASS' if g['hc_wrong'] else 'FAIL'} |",
            f"| Meaning lost | {m['meaning_lost_rate']} | <= {GATES['meaning_lost_rate']} | "
            f"{'PASS' if g['meaning_lost_rate'] else 'FAIL'} |",
            f"| Compound gold-part | {m['compound_gold_part_coverage']} | >= "
            f"{GATES['compound_gold_part_coverage']} | "
            f"{'PASS' if g['compound_gold_part_coverage'] else 'FAIL'} |",
            f"| Simple median post | {m['simple_median_post_ms']} ms | <= "
            f"{GATES['simple_median_post_ms']} ms | "
            f"{'PASS' if g['simple_median_post_ms'] else 'FAIL'} |",
            f"| Compound median post | {m['compound_median_post_ms']} ms | <= "
            f"{GATES['compound_median_post_ms']} ms | "
            f"{'PASS' if g['compound_median_post_ms'] else 'FAIL'} |",
            f"| Warm-valid run | {detail['warm_valid']} | must be True | "
            f"{'PASS' if g['warm_valid'] else 'FAIL'} |",
            "",
            "## Targets (not gates)",
            "",
            "| Target | Measured | Target | Met |",
            "|---|---|---|---|",
            f"| Simple p95 | {m['simple_p95_post_ms']} ms | <= {TARGETS['simple_p95_post_ms']} ms | "
            f"{'yes' if detail['targets_met']['simple_p95_post_ms'] else 'no'} |",
            f"| Compound p95 | {m['compound_p95_post_ms']} ms | <= "
            f"{TARGETS['compound_p95_post_ms']} ms | "
            f"{'yes' if detail['targets_met']['compound_p95_post_ms'] else 'no'} |",
            "",
            "## Observations",
            "",
            f"- Whisper pass counts: {m['whisper_pass_counts']}",
            f"- Clips whose transcript needed a term repair: {m['transcripts_repaired']}/{m['n']}",
            "- Whisper is not deterministic across runs on this machine. That variance is",
            "  part of the system under test; clips lost to it count against v3 and are",
            "  not re-run.",
            "",
            "## Per-clip",
            "",
            "| clip | type | cond | passes | intent | HC | meaning lost | post ms | raw -> repaired |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for c in detail["per_clip"]:
            raw = (c["raw_transcript"] or "")[:48]
            rep = (c["repaired_transcript"] or "")[:48]
            arrow = f"{raw}" if raw == rep else f"{raw} -> {rep}"
            lines.append(
                f"| {c['clip']} | {c['question_type']} | {c['condition']} | "
                f"{c['whisper_pass_count']} | {'Y' if c['intent_ok'] else 'N'} | "
                f"{'Y' if c['hc_wrong'] else 'N'} | {'Y' if c['meaning_lost'] else 'N'} | "
                f"{c['post_speech_ms']} | {arrow} |"
            )
        lines += [
            "",
            "## Next",
            "",
            (
                "- All gates pass → **READY FOR INTERVIEW**."
                if detail["all_gates_pass"]
                else "- A gate failed. If you fix a real bug after seeing this, v3 is VOID "
                     "and a new unseen v4 pack is required."
            ),
            "",
        ]
    (REPORTS / "FINAL_UNSEEN_HOLDOUT_V3_VERDICT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight-only", action="store_true")
    args = ap.parse_args()

    ok, problems, info = preflight()
    print("preflight:", json.dumps(info, indent=2))
    if not ok:
        print("\nPRECHECK FAILED — nothing scored; pack NOT consumed:")
        for p in problems:
            print("  -", p)
        write_precheck_failure(problems, info)
        write_verdict("PRECHECK_FAILED", {"preflight": info}, problems)
        return 1
    print("preflight OK")
    if args.preflight_only:
        return 0

    REPORTS.mkdir(parents=True, exist_ok=True)
    suite_started_at = _utc_now()
    scoring_started = False
    first_scored_at: Optional[str] = None
    first_clip_id: Optional[str] = None
    scored_seen = 0
    expected = int(info.get("scored_clips") or EXPECTED_SCORED)

    def on_scored_clip(scored_i: int, result: Any) -> None:
        nonlocal scoring_started, first_scored_at, first_clip_id, scored_seen
        scored_seen = scored_i
        if scoring_started:
            # Keep STARTED record updated with progress only (still STARTED).
            write_run_record(
                {
                    "started_at": suite_started_at,
                    "first_scored_at": first_scored_at,
                    "first_clip_id": first_clip_id,
                    "outcome": "STARTED",
                    "scoring_started": True,
                    "scored_completed": scored_i,
                    "expected_scored": expected,
                    "last_clip_id": getattr(result, "sample_id", None),
                    "updated_at": _utc_now(),
                }
            )
            return
        scoring_started = True
        first_scored_at = _utc_now()
        first_clip_id = getattr(result, "sample_id", None)
        write_run_record(
            {
                "started_at": suite_started_at,
                "first_scored_at": first_scored_at,
                "first_clip_id": first_clip_id,
                "outcome": "STARTED",
                "scoring_started": True,
                "scored_completed": scored_i,
                "expected_scored": expected,
                "updated_at": first_scored_at,
            }
        )
        print(
            f"V3_RUN_RECORD STARTED at first scored clip "
            f"({first_clip_id}); pack is now consumed.",
            flush=True,
        )

    from app.services.interview_e2e_loopback import run_e2e_suite

    try:
        payload = asyncio.run(
            run_e2e_suite(
                suite="final_unseen_holdout_v3",
                on_scored_clip=on_scored_clip,
            )
        )
    except Exception as exc:
        problems = [f"suite crashed: {type(exc).__name__}: {exc}"]
        if not scoring_started:
            write_precheck_failure(problems, {**info, "suite_started_at": suite_started_at})
            write_verdict("PRECHECK_FAILED", {"preflight": info}, problems)
            print("PRECHECK_FAILED (crash before first scored clip):", problems[0])
            return 1
        write_run_record(
            {
                "started_at": suite_started_at,
                "first_scored_at": first_scored_at,
                "first_clip_id": first_clip_id,
                "finished_at": _utc_now(),
                "outcome": "VOID",
                "scoring_started": True,
                "scored_completed": scored_seen,
                "expected_scored": expected,
                "problems": problems,
            }
        )
        write_verdict(
            "VOID",
            {
                "preflight": info,
                "measured": {"n": scored_seen},
            },
            problems + ["crash after scoring started — full rerun forbidden"],
        )
        print("VOID:", problems[0])
        return 1

    if not scoring_started:
        problems = ["suite returned without scoring any clip"]
        write_precheck_failure(problems, {**info, "suite_started_at": suite_started_at})
        write_verdict("PRECHECK_FAILED", {"preflight": info}, problems)
        print("PRECHECK_FAILED:", problems[0])
        return 1

    report_path = Path(payload.get("report_json") or (REPORTS / "FINAL_UNSEEN_HOLDOUT_V3_REPORT.json"))
    detail = evaluate(json.loads(Path(report_path).read_text(encoding="utf-8")))
    detail["preflight"] = info
    detail["report"] = str(report_path)
    n = int(detail["measured"]["n"])

    if n < expected:
        problems = [
            f"incomplete scored set: {n}/{expected} — scoring started; pack consumed"
        ]
        write_run_record(
            {
                "started_at": suite_started_at,
                "first_scored_at": first_scored_at,
                "first_clip_id": first_clip_id,
                "finished_at": _utc_now(),
                "outcome": "VOID",
                "scoring_started": True,
                "scored_completed": n,
                "expected_scored": expected,
                "report": str(report_path),
                "problems": problems,
            }
        )
        write_verdict("VOID", detail, problems)
        print("VOID:", problems[0])
        return 1

    if not detail["warm_valid"]:
        # Scores already observed → consume as VOID (not a retriable precheck).
        problems = [
            "system was not warm for every scored clip after scoring started — "
            "pack consumed (VOID); not a retriable precheck"
        ]
        write_run_record(
            {
                "started_at": suite_started_at,
                "first_scored_at": first_scored_at,
                "first_clip_id": first_clip_id,
                "finished_at": _utc_now(),
                "outcome": "VOID",
                "scoring_started": True,
                "scored_completed": n,
                "expected_scored": expected,
                "report": str(report_path),
                "problems": problems,
            }
        )
        write_verdict("VOID", detail, problems)
        print("VOID:", problems[0])
        return 1

    write_verdict("VALID", detail, [])
    write_run_record(
        {
            "started_at": suite_started_at,
            "first_scored_at": first_scored_at,
            "first_clip_id": first_clip_id,
            "finished_at": _utc_now(),
            "outcome": "VALID",
            "scoring_started": True,
            "scored_completed": n,
            "expected_scored": expected,
            "all_gates_pass": detail["all_gates_pass"],
            "report": str(report_path),
        }
    )
    print(f"\nv3 VALID — gates pass: {detail['all_gates_pass']}")
    print("read reports/FINAL_UNSEEN_HOLDOUT_V3_VERDICT.md")
    return 0 if detail["all_gates_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
