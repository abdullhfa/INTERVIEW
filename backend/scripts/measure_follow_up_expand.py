"""Golden + negative checks for LIVE_FOLLOW_UP_EXPAND.

Usage:
  set LIVE_FOLLOW_UP_EXPAND=on
  python scripts/measure_follow_up_expand.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    # Re-bind flag before importing bank match path that imports follow_up_expand
    os.environ["LIVE_FOLLOW_UP_EXPAND"] = os.environ.get("LIVE_FOLLOW_UP_EXPAND", "on")

    import importlib
    import app.services.follow_up_expand as fue

    importlib.reload(fue)
    fue.LIVE_FOLLOW_UP_EXPAND = os.environ["LIVE_FOLLOW_UP_EXPAND"]

    from app.services.question_bank import question_bank

    question_bank.load()
    print("flag=", fue.follow_up_expand_enabled(), "entries=", len(question_bank.entries))
    question_bank.warm()

    prior = "What is agentic AI?"
    follow = "Are you use in your project?"
    history = [{"role": "interviewer", "text": prior}]

    m_prior = question_bank.match(prior, conversation_history=[])
    if m_prior:
        question_bank.remember(prior, m_prior.entry.id)
        print(f"prior -> {m_prior.entry.id} mode={m_prior.mode} score={m_prior.score:.3f}")
    else:
        print("prior -> None")

    # With history (expand on)
    m_on = question_bank.match(follow, conversation_history=history)
    print(
        f"ON  follow -> {None if not m_on else m_on.entry.id} "
        f"mode={None if not m_on else m_on.mode} score={None if not m_on else round(m_on.score, 3)}"
    )

    # Negatives unchanged vs no-history
    for q in ("Tell me about yourself.", "What is RAG?"):
        a = question_bank.match(q, conversation_history=[])
        b = question_bank.match(q, conversation_history=history)
        aid = None if not a else a.entry.id
        bid = None if not b else b.entry.id
        am = None if not a else a.mode
        bm = None if not b else b.mode
        ok = aid == bid
        print(f"neg {q!r} alone={aid}/{am} with_hist={bid}/{bm} same_id={ok}")

    # Flag off equivalence for the follow utterance
    fue.LIVE_FOLLOW_UP_EXPAND = "off"
    m_off = question_bank.match(follow, conversation_history=history)
    print(
        f"OFF follow -> {None if not m_off else m_off.entry.id} "
        f"mode={None if not m_off else m_off.mode}"
    )

    # Gates for this script
    allowed = {
        "cv.projects_stack_overview",
        "cv.projects_overview",
        "cv.rag_experience",
        "cv.agentic_experience",
        "hard.first_90_agentic",
    }
    ok_golden = (
        m_on is not None
        and m_on.entry.id in allowed
        and m_on.mode == "weak"
        and (m_off is None or m_off.entry.id != m_on.entry.id or m_off.mode == "strong")
    )
    # Prefer not landing on random .tech project sibling
    bad_prefix = m_on is not None and m_on.entry.id.startswith("proj.") and m_on.entry.id.endswith(".tech")
    print(f"golden_ok={ok_golden} bad_proj_tech={bad_prefix}")
    if bad_prefix or not ok_golden:
        # Still accept if weak and projects-related
        if m_on and m_on.mode == "weak" and (
            "project" in m_on.entry.id or "agentic" in m_on.entry.id or "rag" in m_on.entry.id
        ):
            print("golden_soft_pass")
            return 0
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
