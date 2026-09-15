"""CLI: Clean STT A/B preprocess benchmark (WAV → STT only)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on clean clips")
    parser.add_argument(
        "--variants",
        default="raw,preroll_pad,normalize,denoise,combo,vad_crop,vad_crop_preroll",
        help="Comma-separated preprocess variants",
    )
    args = parser.parse_args()
    variants = tuple(v.strip() for v in args.variants.split(",") if v.strip())

    from app.services.clean_stt_ab_benchmark import run_clean_stt_ab

    out = await run_clean_stt_ab(limit=args.limit, variants=variants)
    s = out["summary"]
    print("\n=== CLEAN STT A/B SUMMARY ===")
    print("Recommended live preprocess:", s.get("recommended_live_preprocess"))
    print("Combo hurts:", s.get("combo_hurts_count"), "| Raw beats combo:", s.get("raw_beats_combo_count"))
    print("Best-variant wins:", s.get("best_variant_wins"))
    for name, block in s.get("by_variant", {}).items():
        print(
            f"  {name:16s} stt_ok={block['stt_ok_rate']:.1%} "
            f"mean={block['mean_score']:.3f} "
            f"1st_miss={block['first_word_missing_rate']:.1%} "
            f"hallu={block['tech_hallucination_rate']:.1%} "
            f"avg_ms={block['avg_stt_ms']}"
        )
    print("HTML:", out["report_html"])


if __name__ == "__main__":
    asyncio.run(main())
