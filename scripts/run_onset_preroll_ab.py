"""CLI: A/B onset pre-roll on Clean E2E (400/600/800/1000ms).

Primary metric: first_word_missing (target ≤1/30).
Does not change aliases / matcher / confidence gate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pre-rolls",
        default="400,600,800,1000",
        help="Comma-separated pre-roll ms values",
    )
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--post-roll", type=int, default=250)
    args = parser.parse_args()
    values = [int(x.strip()) for x in args.pre_rolls.split(",") if x.strip()]

    from app.services.interview_e2e_loopback import REPORTS_DIR, run_e2e_suite

    rows = []
    print("Onset A/B: same 30 Clean clips, only pre_roll_ms changes.", flush=True)
    for ms in values:
        print(f"\n######## PRE-ROLL {ms} ms ########", flush=True)
        out = await run_e2e_suite(
            suite="clean",
            limit=args.limit,
            pre_roll_ms=ms,
            post_roll_ms=args.post_roll,
        )
        s = out["summary"]
        lat = s["latency"]
        row = {
            "pre_roll_ms": ms,
            "post_roll_ms": args.post_roll,
            "total": s["total"],
            "first_word_missing": s.get("first_word_missing"),
            "last_word_missing": s.get("last_word_missing"),
            "stt_success": s.get("stt_success"),
            "intent_success": s.get("intent_success"),
            "intent_success_rate": s.get("intent_success_rate"),
            "high_confidence_wrong": s.get("high_confidence_wrong"),
            "median_post_speech_ms": lat.get("median_post_speech_ms"),
            "report_html": out.get("report_html"),
        }
        rows.append(row)
        print(
            f"PRE-ROLL {ms}: 1st_miss={row['first_word_missing']}/{row['total']} "
            f"STT={row['stt_success']} Intent={row['intent_success']} "
            f"HC={row['high_confidence_wrong']} "
            f"post_med={row['median_post_speech_ms']}ms",
            flush=True,
        )

    # Pick best by first_word_missing, then intent, then latency.
    ranked = sorted(
        rows,
        key=lambda r: (
            int(r["first_word_missing"] or 99),
            -(float(r["intent_success_rate"] or 0)),
            float(r["median_post_speech_ms"] or 9e9),
        ),
    )
    best = ranked[0]
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "onset_preroll_ab",
        "rows": rows,
        "recommended_pre_roll_ms": best["pre_roll_ms"],
        "gates": {
            "first_word_missing_max": 1,
            "clean_stt_min": 0.96,
            "clean_intent_min": 0.90,
            "high_confidence_wrong": 0,
            "median_post_speech_ms_max": 1500,
        },
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "ONSET_PREROLL_AB_REPORT.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== ONSET PRE-ROLL A/B SUMMARY ===")
    for r in rows:
        print(
            f"  {r['pre_roll_ms']:4d}ms  1st_miss={r['first_word_missing']}/{r['total']}  "
            f"intent={r['intent_success_rate']:.1%}  "
            f"post_med={r['median_post_speech_ms']}ms  HC={r['high_confidence_wrong']}"
        )
    print(f"Recommended pre_roll_ms: {best['pre_roll_ms']}")
    print("JSON:", path)


if __name__ == "__main__":
    asyncio.run(main())
