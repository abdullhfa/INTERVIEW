#!/usr/bin/env python3
"""V5 150 Voice Stress — REAL end-to-end loopback validation.

Path (not offline WAV→Whisper injection):
  play WAV on speakers → WASAPI loopback → VAD → STT → repair → intent → answer

Writes / updates:
  reports/V5_150_VOICE_STRESS_E2E_REPORT.{json,html}  (from loopback runner)
  reports/V5_150_VOICE_STRESS_E2E_VERDICT.{md,json}

Requires unmuted default playback + working WASAPI loopback device.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _group(results: list[dict[str, Any]], key: str) -> dict[str, Any]:
    bags: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        bags[str(r.get(key) or "unknown")].append(r)
    out = {}
    for g, rs in sorted(bags.items()):
        n = len(rs)
        out[g] = {
            "n": n,
            "pass": sum(1 for r in rs if r.get("result") == "PASS"),
            "pass_rate": round(sum(1 for r in rs if r.get("result") == "PASS") / max(n, 1), 4),
            "stt_ok": sum(1 for r in rs if r.get("stt_ok")),
            "intent_ok": sum(1 for r in rs if r.get("intent_ok")),
            "hc_wrong": sum(1 for r in rs if r.get("high_confidence_wrong")),
            "median_total_ms": _median(
                [float((r.get("timings") or {}).get("total_ms") or 0) for r in rs]
            ),
            "median_post_speech_ms": _median(
                [float((r.get("timings") or {}).get("post_speech_ms") or 0) for r in rs]
            ),
        }
    return out


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    m = len(ys) // 2
    return float(ys[m]) if len(ys) % 2 else (ys[m - 1] + ys[m]) / 2.0


def _decide(summary: dict[str, Any]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    n = int(summary.get("n") or 0)
    if n < 150:
        blockers.append(f"incomplete run n={n} < 150")
    hc = int(summary.get("hc_wrong") or 0)
    if hc > 0:
        blockers.append(f"confident_wrong={hc}")
    # Audio-path collapse: too many AUDIO timeouts means loopback not working
    audio_fail = int(summary.get("audio_fail") or 0)
    if n and audio_fail / n > 0.20:
        blockers.append(f"audio_capture_fail_rate={audio_fail/n:.3f} > 0.20 (loopback/speakers?)")
    pass_rate = float(summary.get("pass_rate") or 0.0)
    if pass_rate < 0.65:
        blockers.append(f"pass_rate={pass_rate:.3f} < 0.65")
    intent_rate = float(summary.get("intent_rate") or 0.0)
    if intent_rate < 0.55:
        blockers.append(f"intent_rate={intent_rate:.3f} < 0.55")
    for accent, g in (summary.get("by_accent") or {}).items():
        if g["n"] >= 10 and g["pass_rate"] < 0.50:
            blockers.append(f"accent {accent} collapsed pass_rate={g['pass_rate']:.3f}")
    verdict = "PASS_150_VOICE_STRESS_E2E" if not blockers else "FAIL_150_VOICE_STRESS_E2E"
    return verdict, blockers


async def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    limit = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        limit = int(sys.argv[1])

    print("=== V5 150 VOICE STRESS — REAL E2E LOOPBACK ===", flush=True)
    print("Path: play → WASAPI loopback → VAD → STT → intent → answer", flush=True)
    if limit:
        print(f"(limited to first {limit} clips)", flush=True)

    from app.services.interview_e2e_loopback import run_e2e_suite

    payload = await run_e2e_suite(suite="v5_150_voice", limit=limit)
    results = [r for r in (payload.get("results") or []) if not str(r.get("notes") or "").startswith("warmup:")]
    # results may already be dicts from asdict
    if results and hasattr(results[0], "__dataclass_fields__"):
        from dataclasses import asdict

        results = [asdict(r) for r in results]

    n = len(results)
    hc_wrong = sum(1 for r in results if r.get("high_confidence_wrong"))
    audio_fail = sum(1 for r in results if r.get("failure_stage") == "AUDIO")
    stt_ok_n = sum(1 for r in results if r.get("stt_ok"))
    intent_ok_n = sum(1 for r in results if r.get("intent_ok"))
    pass_n = sum(1 for r in results if r.get("result") == "PASS")

    # Derive accent/speed/distance/noise from condition "speed|distance|noise|style"
    enriched = []
    for r in results:
        cond = str(r.get("condition") or "")
        parts = cond.split("|")
        speed = parts[0] if len(parts) > 0 else ""
        distance = parts[1] if len(parts) > 1 else ""
        noise = parts[2] if len(parts) > 2 else ""
        style = parts[3] if len(parts) > 3 else ""
        er = dict(r)
        er["accent"] = r.get("speaker") or ""
        er["speed"] = speed
        er["distance"] = distance
        er["noise"] = noise
        er["style"] = style
        enriched.append(er)

    summary = {
        "n": n,
        "pass": pass_n,
        "pass_rate": round(pass_n / max(n, 1), 4),
        "stt_ok": stt_ok_n,
        "stt_rate": round(stt_ok_n / max(n, 1), 4),
        "intent_ok": intent_ok_n,
        "intent_rate": round(intent_ok_n / max(n, 1), 4),
        "hc_wrong": hc_wrong,
        "audio_fail": audio_fail,
        "median_total_ms": _median(
            [float((r.get("timings") or {}).get("total_ms") or 0) for r in results]
        ),
        "median_post_speech_ms": _median(
            [float((r.get("timings") or {}).get("post_speech_ms") or 0) for r in results]
        ),
        "by_accent": _group(enriched, "accent"),
        "by_speed": _group(enriched, "speed"),
        "by_distance": _group(enriched, "distance"),
        "by_noise": _group(enriched, "noise"),
        "by_style": _group(enriched, "style"),
        "measurement_mode": "e2e_windows_loopback",
        "path": "WAV → speakers → WASAPI loopback → VAD → STT → understanding → answer",
    }
    verdict, blockers = _decide(summary)
    summary["verdict"] = verdict
    summary["blockers"] = blockers

    out = {
        "created_at": _now(),
        "track": "v5_150_voice_stress_e2e",
        "note": (
            "Synthetic accent proxies. This run uses the REAL audio capture path. "
            "Offline WAV→Whisper harness numbers are NOT valid for this gate."
        ),
        "loopback_payload_summary": payload.get("summary"),
        "summary": summary,
        "results": enriched,
        "report_json": payload.get("json_path") or payload.get("report_json"),
        "report_html": payload.get("html_path") or payload.get("report_html"),
    }
    json_path = REPORTS / "V5_150_VOICE_STRESS_E2E_VERDICT.json"
    json_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    fails = [r for r in enriched if r.get("result") != "PASS"][:30]
    hc = [r for r in enriched if r.get("high_confidence_wrong")][:20]
    md = [
        verdict,
        "",
        "# V5 150 Voice Stress — End-to-End Loopback Verdict",
        "",
        f"Created: `{out['created_at']}`",
        "",
        f"Path: `{summary['path']}`",
        "",
        "## Summary",
        "",
        f"- n={summary['n']}",
        f"- pass_rate=**{summary['pass_rate']}**",
        f"- stt_rate=**{summary['stt_rate']}**",
        f"- intent_rate=**{summary['intent_rate']}**",
        f"- confident_wrong=**{summary['hc_wrong']}**",
        f"- audio_fail=**{summary['audio_fail']}**",
        f"- median_total_ms=**{summary['median_total_ms']:.1f}**",
        f"- median_post_speech_ms=**{summary['median_post_speech_ms']:.1f}**",
        "",
        "## Accent / speed / distance / noise",
        "",
        "### Accent",
        "```json",
        json.dumps(summary["by_accent"], indent=2),
        "```",
        "",
        "### Speed",
        "```json",
        json.dumps(summary["by_speed"], indent=2),
        "```",
        "",
        "### Distance",
        "```json",
        json.dumps(summary["by_distance"], indent=2),
        "```",
        "",
        "### Noise",
        "```json",
        json.dumps(summary["by_noise"], indent=2),
        "```",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        md += [f"- {b}" for b in blockers]
    else:
        md.append("- none")
    md += ["", "## Confident wrong", ""]
    if not hc:
        md.append("- none")
    else:
        for r in hc:
            md.append(
                f"- `{r.get('sample_id')}` match={r.get('match_id')} "
                f"tx={r.get('transcript')!r}"
            )
    md += ["", "## Failures (up to 30)", ""]
    if not fails:
        md.append("- none")
    else:
        for r in fails:
            md.append(
                f"- `{r.get('sample_id')}` stage={r.get('failure_stage')} "
                f"detail={r.get('failure_detail')} tx={r.get('transcript')!r}"
            )
    md += [
        "",
        "## Prior offline harness",
        "",
        "Previous `PASS_150_VOICE_STRESS` / 0.90 metrics are **invalidated** for E2E claims "
        "(see `V5_150_VOICE_STRESS_RESULTS.md` marked `NOT_VALIDATED_END_TO_END`).",
        "",
    ]
    md_path = REPORTS / "V5_150_VOICE_STRESS_E2E_VERDICT.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    print("=== E2E VERDICT ===", flush=True)
    print(verdict, flush=True)
    print(
        f"pass={summary['pass_rate']} stt={summary['stt_rate']} "
        f"intent={summary['intent_rate']} hc={summary['hc_wrong']} "
        f"audio_fail={summary['audio_fail']}",
        flush=True,
    )
    print(f"wrote {md_path}", flush=True)
    print(f"wrote {json_path}", flush=True)
    return 0 if verdict == "PASS_150_VOICE_STRESS_E2E" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
