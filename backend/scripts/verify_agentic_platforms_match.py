"""Verify agentic platforms entry matches correctly."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.question_bank import question_bank


def main() -> int:
    question_bank.load(force=True)
    print("entries", len(question_bank.entries), flush=True)
    print("warming...", flush=True)
    question_bank.warm()
    checks = [
        (
            "PLATFORMS",
            "What platforms can you use to build agentic AI workflows?",
            "tech.agentic_platforms",
        ),
        (
            "PLATFORMS2",
            "Which frameworks can you use for agentic AI workflows?",
            "tech.agentic_platforms",
        ),
        (
            "DIFF",
            "What is the difference between an AI Agent, Agentic Workflow, Multi-Agent System, and Agent Orchestrator?",
            "hard.agent_terms_difference",
        ),
        ("AGENTIC_WHAT", "What is agentic AI?", "tech.agentic_what"),
    ]
    ok = True
    for label, q, expect in checks:
        m = question_bank.match(q)
        mid = m.entry.id if m else None
        mode = m.mode if m else None
        score = round(m.score, 3) if m else None
        good = mid == expect
        ok = ok and (good)
        status = "OK" if good else "FAIL"
        print(f"{label}: {mid}/{mode}/{score} expect={expect} {status}", flush=True)
        if mid == "tech.agentic_platforms" and m:
            print("  ans:", m.entry.answer_en[:100], "...", flush=True)
    print("GATE", "PASS" if ok else "FAIL", flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
