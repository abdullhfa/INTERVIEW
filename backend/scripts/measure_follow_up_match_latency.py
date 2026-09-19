"""Microbench: question_bank.match latency OFF vs ON with history.

Isolates expand cost (second match) from STT/live noise.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run(flag: str, pairs: list[tuple[str, str]], repeats: int = 5) -> list[dict]:
    os.environ["LIVE_FOLLOW_UP_EXPAND"] = flag
    import importlib
    import app.services.follow_up_expand as fue

    importlib.reload(fue)
    fue.LIVE_FOLLOW_UP_EXPAND = flag

    from app.services.question_bank import question_bank

    question_bank.load()
    if not getattr(question_bank, "_warmed", False):
        question_bank.warm()
        question_bank._warmed = True  # type: ignore[attr-defined]

    rows: list[dict] = []
    for prior, follow in pairs:
        history = [{"role": "interviewer", "text": prior}]
        # remember prior so subject extraction can use recent entry
        m_prior = question_bank.match(prior, conversation_history=[])
        if m_prior:
            question_bank.remember(prior, m_prior.entry.id)

        # cold-ish first call discarded
        question_bank.match(follow, conversation_history=history)

        times: list[float] = []
        last = None
        for _ in range(repeats):
            t0 = time.perf_counter()
            last = question_bank.match(follow, conversation_history=history)
            times.append((time.perf_counter() - t0) * 1000)
        times_sorted = sorted(times)
        rows.append(
            {
                "flag": flag,
                "prior": prior,
                "follow": follow,
                "id": last.entry.id if last else None,
                "mode": last.mode if last else None,
                "median_ms": times_sorted[len(times_sorted) // 2],
                "mean_ms": sum(times) / len(times),
                "min_ms": min(times),
                "max_ms": max(times),
            }
        )
    return rows


def main() -> int:
    pairs = [
        ("What is agentic AI?", "Are you use in your project?"),  # expand fires
        ("What is RAG?", "Have you used it in your projects?"),  # expand may fire
        ("What is agentic AI?", "What is RAG?"),  # standalone
        ("Tell me about yourself.", "What projects have you worked on?"),  # standalone
    ]
    off = _run("off", pairs)
    on = _run("on", pairs)
    print("---OFF---")
    for r in off:
        print(
            f"{r['median_ms']:7.1f} ms median  {r['id']}/{r['mode']}  "
            f"follow={r['follow']!r}"
        )
    print("---ON---")
    for r in on:
        print(
            f"{r['median_ms']:7.1f} ms median  {r['id']}/{r['mode']}  "
            f"follow={r['follow']!r}"
        )
    print("---DELTA (ON-OFF median)---")
    for a, b in zip(off, on):
        d = b["median_ms"] - a["median_ms"]
        print(f"{d:+7.1f} ms  {a['follow']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
