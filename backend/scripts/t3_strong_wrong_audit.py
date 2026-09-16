"""Warm T3 audit: list strong+wrong self-matches for a question bank dir.

Usage:
  python scripts/t3_strong_wrong_audit.py
  python scripts/t3_strong_wrong_audit.py --data-dir app/data/question_bank_V6_backup
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.question_bank import QuestionBank


def audit(data_dir: Path) -> int:
    qb = QuestionBank(data_dir=data_dir)
    qb.load(force=True)
    print(f"data_dir={data_dir}", flush=True)
    print(f"entries={len(qb.entries)}", flush=True)
    t0 = time.perf_counter()
    qb.warm()
    print(f"warm_s={time.perf_counter() - t0:.1f}", flush=True)

    rows: list[dict] = []
    q_ok = q_bad = a_ok = a_bad = alias_total = 0
    for e in qb.entries:
        m = qb.match(e.question)
        mid = getattr(getattr(m, "entry", None), "id", None) if m else None
        mode = getattr(m, "mode", None) if m else None
        if m and m.entry and m.entry.id == e.id:
            q_ok += 1
        else:
            q_bad += 1
        if m and mode == "strong" and mid and mid != e.id:
            rows.append(
                {
                    "own_id": e.id,
                    "own_q": e.question,
                    "kind": "question",
                    "text": e.question,
                    "matched_id": mid,
                    "matched_q": m.entry.question,
                    "score": getattr(m, "score", None),
                    "confidence": getattr(m, "confidence", None),
                }
            )
        for a in e.aliases or ():
            alias_total += 1
            m = qb.match(a)
            mid = getattr(getattr(m, "entry", None), "id", None) if m else None
            mode = getattr(m, "mode", None) if m else None
            if mid == e.id:
                a_ok += 1
            else:
                a_bad += 1
            if m and mode == "strong" and mid and mid != e.id:
                rows.append(
                    {
                        "own_id": e.id,
                        "own_q": e.question,
                        "kind": "alias",
                        "text": a,
                        "matched_id": mid,
                        "matched_q": m.entry.question,
                        "score": getattr(m, "score", None),
                        "confidence": getattr(m, "confidence", None),
                    }
                )

    print(f"questions {q_ok}/{len(qb.entries)} bad={q_bad}", flush=True)
    print(f"aliases {a_ok}/{alias_total} bad={a_bad}", flush=True)
    print(f"strong_and_wrong={len(rows)}", flush=True)
    print("---TABLE---", flush=True)
    print(
        "own_id | own_question | kind | text_matched | wrong_id | wrong_question | score",
        flush=True,
    )
    for r in rows:
        text = (r["text"] or "").replace("\n", " ").strip()
        own_q = (r["own_q"] or "").replace("\n", " ").strip()
        mq = (r["matched_q"] or "").replace("\n", " ").strip()
        print(
            f"{r['own_id']} | {own_q} | {r['kind']} | {text} | "
            f"{r['matched_id']} | {mq} | score={r['score']}",
            flush=True,
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "app" / "data" / "question_bank",
    )
    args = ap.parse_args()
    return audit(args.data_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
