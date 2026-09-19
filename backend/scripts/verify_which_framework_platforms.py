"""Verify platforms routes to which_framework; agent_terms still self-matches."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.question_bank import question_bank


def main() -> int:
    question_bank.load(force=True)
    print("entries", len(question_bank.entries), flush=True)
    assert "tech.agentic_platforms" not in {e.id for e in question_bank.entries}
    print("warming...", flush=True)
    question_bank.warm()

    checks = [
        (
            "PLATFORMS",
            "What platforms can you use to build agentic AI workflows?",
            "tech.which_framework",
        ),
        (
            "WHICH_FW",
            "Which framework do you use, and why?",
            "tech.which_framework",
        ),
        (
            "DIFF",
            "What is the difference between an AI Agent, Agentic Workflow, Multi-Agent System, and Agent Orchestrator?",
            "hard.agent_terms_difference",
        ),
        (
            "ORCH",
            "What is an orchestrator in AI systems?",
            "tech.orchestrator_ai_systems",
        ),
        (
            "AGENT_ORCH",
            "What is an agent orchestrator?",
            "tech.agent_orchestrator",
        ),
    ]
    ok = True
    for label, q, expect in checks:
        m = question_bank.match(q)
        mid = m.entry.id if m else None
        mode = m.mode if m else None
        score = round(m.score, 3) if m else None
        good = mid == expect
        ok = ok and (good)
        print(
            f"{label}: {mid}/{mode}/{score} expect={expect} {'OK' if good else 'FAIL'}",
            flush=True,
        )

    # self-match remaining aliases on agent_terms
    e = next(x for x in question_bank.entries if x.id == "hard.agent_terms_difference")
    for a in [e.question, *e.aliases]:
        m = question_bank.match(a)
        mid = m.entry.id if m else None
        good = mid == e.id
        ok = ok and (good)
        if not good:
            print(f"SELF_FAIL agent_terms: {a!r} -> {mid}", flush=True)

    e2 = next(x for x in question_bank.entries if x.id == "tech.which_framework")
    for a in [e2.question, *e2.aliases]:
        m = question_bank.match(a)
        mid = m.entry.id if m else None
        good = mid == e2.id
        ok = ok and (good)
        if not good:
            print(f"SELF_FAIL which_framework: {a!r} -> {mid}", flush=True)

    print("GATE", "PASS" if ok else "FAIL", flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
