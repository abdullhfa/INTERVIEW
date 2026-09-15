"""CLI: run automated interview audio stress tests (direct WAV injection)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Interview audio Test Runner")
    parser.add_argument("--question-id", type=int, default=None)
    parser.add_argument("--speaker", type=str, default=None)
    parser.add_argument("--condition", type=str, default=None)
    parser.add_argument("--limit", type=int, default=180)
    args = parser.parse_args()

    from app.services.interview_audio_runner import run_suite
    from app.services.question_bank import question_bank

    question_bank.load()
    # Skip full embedding warm-up for faster CLI starts; matcher falls back
    # to lexical scoring until the embedder is used on demand.
    question_bank.load(force=True)
    print("Starting direct-injection suite...", flush=True)

    def progress(i, total, result):
        mark = "PASS" if result.result == "PASS" else "FAIL"
        print(
            f"[{i}/{total}] {mark} Q{result.question_id} {result.speaker}/{result.condition} "
            f"acc={result.accuracy}% {result.timings.total_ms:.0f}ms "
            f"stage={result.failure_stage or '-'}",
            flush=True,
        )

    out = await run_suite(
        question_id=args.question_id,
        speaker=args.speaker,
        condition=args.condition,
        limit=args.limit,
        progress_cb=progress,
    )
    summary = out["summary"]
    print("\n=== SUMMARY ===")
    print(f"Total: {summary['total']}")
    print(f"PASS: {summary['passed']}  FAIL: {summary['failed']}")
    print(f"STT success: {summary['stt_success']}")
    print(f"Intent success: {summary['intent_success']}")
    print(f"Answer success: {summary['answer_success']}")
    print(f"Average latency: {summary['average_latency_sec']} sec")
    print(f"Main weakness: {summary['main_weakness']}")
    print(f"HTML report: {out['report_html_latest']}")
    print(f"JSON report: {out['report_json']}")


if __name__ == "__main__":
    asyncio.run(main())
