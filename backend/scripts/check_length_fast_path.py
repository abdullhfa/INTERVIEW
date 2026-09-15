"""Offline fast-path check for short/medium/very_long gold transcripts."""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.services.compound_question_detector import detect_question_complexity
from app.services.compound_question_pipeline import resolve_compound_question
from app.services.question_bank import question_bank

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT.parent
    / "frontend"
    / "public"
    / "voice-drill"
    / "stress-holdout-v2"
    / "manifest.json"
)


def main() -> None:
    question_bank.load()
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for cat in ("short", "medium", "very_long"):
        rows = [x for x in raw if str(x.get("category", "")).lower() == cat]
        print(f"==== {cat} ({len(rows)})")
        det_ms: list[float] = []
        single = 0
        decomp = 0
        for x in rows:
            t = str(x.get("transcript") or "")
            t0 = time.perf_counter()
            d = detect_question_complexity(t)
            det_ms.append((time.perf_counter() - t0) * 1000)
            m = question_bank.match(t)
            strong = bool(m and m.mode == "strong")
            used = False
            if d.question_type != "single" and not strong:
                r = resolve_compound_question(t, detection=d)
                used = (r.used_compound_path)
            if d.question_type == "single":
                single += 1
            if used:
                decomp += 1
            preview = t[:70].replace("\n", " ")
            print(
                f"  type={d.question_type:9} strong={strong} "
                f"used_compound={used} det_ms={det_ms[-1]:.3f} | {preview}"
            )
        med = sorted(det_ms)[len(det_ms) // 2] if det_ms else 0.0
        print(
            f"  single={single}/{len(rows)} unnecessary_decomp={decomp} "
            f"median_det_ms={med:.3f}"
        )


if __name__ == "__main__":
    main()
