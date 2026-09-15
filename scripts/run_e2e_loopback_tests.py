"""CLI: E2E Windows loopback interview audio test.

Suites (kept separate on purpose):
  --suite clean                 Clean-only gate (FROZEN)
  --suite office_poor           Office + poor (FROZEN)
  --suite poor                  Poor Call recovery (FROZEN)
  --suite far                   Far recovery (FROZEN)
  --suite realistic             Primary realistic mix (regression)
  --suite realistic_holdout     Legacy holdout (includes combined skew)
  --suite realistic_holdout_v2  Balanced unseen readiness (no combined)
  --suite extreme_combined      Combined-only stress (NOT readiness)
  --suite stress                Hard-question stress set
  --suite very_long_length      Very-long continuation regression
  --suite final_unseen_holdout     VOIDED v1 (debug only)
  --suite final_unseen_holdout_v2  EVAL ONLY adoption gate (120; frozen NOT READY)
  --suite compound_dev             Track B compound coverage (40; not holdout)
  --suite generalization_dev       Track C generalization pack (56; not holdout)
  --suite both                  Stress then realistic
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
except ImportError:
    pass


def _print_summary(out: dict) -> None:
    s = out["summary"]
    lat = s["latency"]
    levels = s.get("audio_levels") or {}
    name = out.get("score_name") or s.get("score_name") or "E2E Score"
    suite = out.get("suite") or s.get("suite") or "?"
    print(f"\n=== {name} ({suite}) ===")
    print(f"Total: {s['total']}  PASS: {s['passed']}  FAIL: {s['failed']}")
    print(f"Intent: {s['intent_success']} ({s['intent_success_rate']})")
    print(f"STT: {s['stt_success']}")
    print(f"Recovered after STT error: {s['recovered_after_stt_error']}")
    print(f"High-confidence wrong: {s['high_confidence_wrong']}")
    print(
        f"first_word_missing={s.get('first_word_missing')} "
        f"last_word_missing={s.get('last_word_missing')} "
        f"raw_better={s.get('raw_better_than_processed')} "
        f"pre_roll_ms={s.get('pre_roll_ms') or out.get('filters', {}).get('pre_roll_ms')}"
    )
    print(
        f"Audio levels: rms_before={levels.get('avg_rms_before')} "
        f"rms_after={levels.get('avg_rms_after')} "
        f"snr_db={levels.get('avg_snr_db_est')} | "
        f"bw={levels.get('avg_bandwidth_hz_est')} "
        f"hf={levels.get('avg_high_freq_energy_ratio')} | "
        f"fail_low_rms={levels.get('fail_low_rms_count')} "
        f"fail_narrowband={levels.get('fail_narrowband_count')} "
        f"fail_onset={levels.get('fail_onset_count')}"
    )
    print(
        f"Latency post-speech median={lat.get('median_post_speech_ms')}ms "
        f"p95={lat.get('p95_post_speech_ms')}ms | "
        f"wall median={lat['median_total_ms']}ms | "
        f"avg VAD={lat['avg_vad_ms']} STT={lat['avg_stt_ms']} "
        f"Intent={lat['avg_intent_ms']} Answer={lat['avg_answer_ms']}"
    )
    print("By condition:", s["by_condition"])
    print("Fail buckets:", s.get("fail_buckets"))
    print("Acoustic causes:", s.get("acoustic_causes"))
    print("Failure stages:", s["failure_stages"])
    print("HTML:", out["report_html"])


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        choices=(
            "clean",
            "office_poor",
            "poor",
            "far",
            "stress",
            "realistic",
            "realistic_holdout",
            "realistic_holdout_v2",
            "extreme_combined",
            "long_accent",
            "short_length",
            "medium_length",
            "very_long_length",
            "final_unseen_holdout",
            "final_unseen_holdout_v2",
            "compound_dev",
            "generalization_dev",
            "both",
        ),
        default="both",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pre-roll", type=int, default=None)
    parser.add_argument("--post-roll", type=int, default=None)
    args = parser.parse_args()

    from app.services.interview_e2e_loopback import run_e2e_both, run_e2e_suite

    print("Starting E2E loopback suite (play -> loopback -> VAD -> STT -> intent)...", flush=True)
    print("Ensure default speakers are not muted and Windows default output is active.", flush=True)

    if args.suite == "both":
        both = await run_e2e_both(stress_limit=args.limit, realistic_limit=args.limit)
        _print_summary(both["stress"])
        _print_summary(both["realistic"])
    else:
        out = await run_e2e_suite(
            suite=args.suite,
            limit=args.limit,
            pre_roll_ms=args.pre_roll,
            post_roll_ms=args.post_roll,
        )
        _print_summary(out)
        if args.suite == "long_accent":
            print("\n=== LONG SENTENCE ACCENT (length factor only) ===")
            print("Accent | STT | Intent | meaning_lost | HC wrong | duration | latency | failure_position")
            for row in (out.get("summary") or {}).get("by_accent") or []:
                print(
                    f"{row['accent']:12} | {row['stt']:6} ({row['stt_rate']:.0%}) | "
                    f"{row['intent']:6} ({row['intent_rate']:.0%}) | "
                    f"{row['meaning_lost']:2} | {row['hc_wrong']:2} | "
                    f"{row['duration_median_ms']:7.0f}ms | {row['latency_median_ms']:7.0f}ms | "
                    f"{row['failure_position']} {row.get('failure_positions') or ''}"
                )
            print("Frozen system · next: Short sentences A/B")
        elif args.suite in {"short_length", "medium_length", "very_long_length"}:
            s = out.get("summary") or {}
            c = s.get("compound") or {}
            print(f"\n=== LENGTH REGRESSION ({args.suite}) ===")
            print(
                f"compound_detected={c.get('compound_detected')} "
                f"compound_path_used={c.get('compound_path_used')} "
                f"coverage={c.get('avg_intent_coverage_rate')} "
                f"final_answer_ok={c.get('final_answer_ok')}"
            )
            print(
                f"intent_ms_avg={((s.get('latency') or {}).get('avg_intent_ms'))} "
                f"post_speech_median={((s.get('latency') or {}).get('median_post_speech_ms'))}"
            )
        elif args.suite == "realistic_holdout_v2":
            print("\n=== REALISTIC HOLDOUT V2 (FINAL READINESS) ===")
            print("Overall Intent >= 90% | HC wrong = 0 | meaning_lost <= 1% | median <= 1.5s")
        elif args.suite == "extreme_combined":
            print("\n=== EXTREME STRESS COMBINED (NOT READINESS) ===")
        elif args.suite == "final_unseen_holdout":
            print("\n=== FINAL UNSEEN HOLDOUT V1 — VOIDED (not official) ===")
        elif args.suite == "final_unseen_holdout_v2":
            s = out.get("summary") or {}
            g = out.get("adoption_gate") or {}
            print("\n=== FINAL UNSEEN HOLDOUT V2 (EVAL ONLY) ===")
            print(
                f"READY={g.get('ready')} | Intent={s.get('intent_success')} | "
                f"HC={s.get('high_confidence_wrong')} | "
                f"gold_mismatch={g.get('gold_id_mismatch')} | "
                f"meaning_lost_rate={g.get('meaning_lost_rate')} | "
                f"median_post={g.get('median_post_speech_ms')}ms | "
                f"compound_cov={g.get('compound_coverage')} | "
                f"latency={g.get('latency_breakdown_median_ms')}"
            )
            print("Do not tune on this pack. Bug-fix voids this holdout sample.")
        elif args.suite == "compound_dev":
            g = out.get("track_b_gate") or {}
            print("\n=== COMPOUND DEV TRACK B ===")
            print(
                f"PASS={g.get('ready')} | Intent={g.get('intent_rate')} | "
                f"gold_part={g.get('gold_part_coverage')} | HC={g.get('hc_wrong')} | "
                f"dup={g.get('duplicate_answer_rate')} | "
                f"median_post={g.get('median_post_speech_ms')}ms | "
                f"codes={g.get('failure_codes')}"
            )
        elif args.suite == "generalization_dev":
            g = out.get("track_c_gate") or out.get("adoption_gate") or {}
            slices = g.get("by_slice") or {}
            slice_txt = ", ".join(
                f"{k}={((slices.get(k) or {}).get('intent_rate'))}" for k in slices
            )
            print("\n=== GENERALIZATION DEV TRACK C ===")
            print(
                f"PASS={g.get('ready')} | Intent={g.get('intent_rate')} | "
                f"HC={g.get('hc_wrong')} | meaning_lost={g.get('meaning_lost')} | "
                f"slices=[{slice_txt}] | "
                f"far_poor={g.get('far_poor_rate')} | "
                f"median_post={g.get('median_post_speech_ms')}ms"
            )
        elif args.suite == "realistic":
            print("\n=== REALISTIC REGRESSION (dev set) ===")


if __name__ == "__main__":
    asyncio.run(main())
