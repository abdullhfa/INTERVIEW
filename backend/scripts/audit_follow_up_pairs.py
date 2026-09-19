"""Paired follow-up expand audit (history-aware).

Usage:
  set LIVE_FOLLOW_UP_EXPAND=on
  python scripts/audit_follow_up_pairs.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Pairs: (prior, follow, expected_family_substrings_or_ids, is_true_followup)
# expected: if follow-up should change intent, list acceptable id substrings / ids.
# is_true_followup=False → standalone that must NOT fire expand / change intent.
PAIRS: list[tuple[str, str, tuple[str, ...], bool]] = [
    # True follow-ups (object-less / deictic)
    ("What is agentic AI?", "Are you use in your project?", ("agentic", "projects_stack", "projects_overview", "rag_experience"), True),
    ("What is RAG?", "Have you used it in your projects?", ("rag", "projects"), True),
    ("What is Whisper?", "why did you choose that?", ("whisper",), True),
    ("What is LangGraph?", "have you used it?", ("langgraph", "langchain", "agentic", "projects"), True),
    ("What are guardrails?", "what do you use in your own system?", ("guardrail", "cv.guardrails"), True),
    ("What is an embedding?", "how do you choose one?", ("embed",), True),
    ("How would you build a RAG system?", "what about arabic documents?", ("rag", "arabic", "hard.rag"), True),
    ("Tell me about the early-warning project.", "what was your role in it?", ("early_warning", "role"), True),
    ("Tell me about the early-warning project.", "what challenges did you face?", ("early_warning", "challenge"), True),
    ("What is ChromaDB?", "would you keep it if you scaled?", ("chroma", "why_not_chroma"), True),
    ("What is fine-tuning?", "have you done that on a project?", ("fine", "lora", "projects", "experience"), True),
    ("What is a vector database?", "which one did you use?", ("vector", "chroma", "faiss", "pgvector", "projects"), True),
    # More deictic / short
    ("What is MCP?", "have you used it?", ("mcp", "projects", "experience"), True),
    ("What is LoRA?", "did you apply it?", ("lora", "fine", "projects"), True),
    ("Explain hybrid search.", "when would you use that?", ("hybrid",), True),
    # Standalone negatives (must NOT change intent vs no-history / must not false-fire usefully)
    ("What is agentic AI?", "What is RAG?", ("rag_what", "tech.rag"), False),
    ("What is agentic AI?", "Tell me about yourself.", ("tell_me_about_yourself", "intro."), False),
    ("What is RAG?", "How do you prevent overfitting?", ("overfit",), False),
    ("What is Whisper?", "What is an LLM?", ("what_is_llm", "llm_what", "tech.what_is_llm"), False),
    ("Tell me about yourself.", "What projects have you worked on?", ("projects",), False),
]


def _family_ok(entry_id: str, expected: tuple[str, ...]) -> bool:
    eid = (entry_id or "").lower()
    return any(tok.lower() in eid for tok in expected)


def main() -> int:
    os.environ["LIVE_FOLLOW_UP_EXPAND"] = os.environ.get("LIVE_FOLLOW_UP_EXPAND", "on")
    import importlib
    import app.services.follow_up_expand as fue

    importlib.reload(fue)
    fue.LIVE_FOLLOW_UP_EXPAND = os.environ["LIVE_FOLLOW_UP_EXPAND"]

    from app.services.follow_up_expand import (
        append_subject,
        follow_up_expand_enabled,
        follow_up_hint,
        subject_from_prior,
    )
    from app.services.question_bank import question_bank

    question_bank.load()
    print(f"flag={follow_up_expand_enabled()} entries={len(question_bank.entries)}")
    t0 = time.perf_counter()
    question_bank.warm()
    print(f"warm_s={time.perf_counter() - t0:.1f}")

    added = 0  # expand fired and moved to correct family
    wrong_strong = 0
    wrong_any = 0
    false_fire = 0  # standalone where expand changed intent
    missed = 0  # true follow-up where expand should help but didn't fire/change
    rows: list[str] = []

    for prior, follow, expected, is_fu in PAIRS:
        history = [{"role": "interviewer", "text": prior}]
        m_prior = question_bank.match(prior, conversation_history=[])
        if m_prior:
            question_bank.remember(prior, m_prior.entry.id)

        hint = follow_up_hint(follow, has_prior=True)
        subject = subject_from_prior(history, recent_entry=m_prior.entry if m_prior else None)
        expanded = append_subject(follow, subject) if subject else follow

        raw = question_bank.match(follow, conversation_history=history, _skip_follow_up=True)
        # Force off for baseline-without-expand under same history
        prev = fue.LIVE_FOLLOW_UP_EXPAND
        fue.LIVE_FOLLOW_UP_EXPAND = "off"
        alone = question_bank.match(follow, conversation_history=history)
        fue.LIVE_FOLLOW_UP_EXPAND = prev

        on = question_bank.match(follow, conversation_history=history)

        raw_id = None if not raw else raw.entry.id
        alone_id = None if not alone else alone.entry.id
        on_id = None if not on else on.entry.id
        on_mode = None if not on else on.mode

        fired = hint and subject and expanded != " ".join(follow.split())
        changed = on_id is not None and alone_id is not None and on_id != alone_id
        # Also count when alone was different from skip path... alone with off should == raw typically
        changed = on_id != raw_id if (on_id or raw_id) else False

        correct = on_id is not None and _family_ok(on_id, expected)
        incorrect = on_id is not None and not _family_ok(on_id, expected)

        tag = ""
        if is_fu:
            if fired and changed and correct:
                added += 1
                tag = "VALUE"
            elif fired and changed and incorrect:
                wrong_any += 1
                if on_mode == "strong":
                    wrong_strong += 1
                tag = "WRONG_STRONG" if on_mode == "strong" else "WRONG_WEAK"
            elif fired and not changed:
                # expand fired but same intent — ok if already correct
                tag = "FIRED_NOCHANGE"
                if not correct:
                    missed += 1
                    tag = "MISS"
            else:
                # did not fire
                if correct:
                    tag = "OK_NOEXPAND"
                else:
                    missed += 1
                    tag = "MISS"
        else:
            # standalone
            if fired and changed:
                false_fire += 1
                tag = "FALSE_FIRE"
            else:
                tag = "OK_STANDALONE"
                if incorrect:
                    # standalone wrong match is bank debt, not expand — note only
                    tag = "STANDALONE_BANK"

        rows.append(
            f"{tag}\tprior={prior!r}\tfollow={follow!r}\thint={hint}\tsubj={subject!r}\t"
            f"exp={expanded!r}\traw={raw_id}\ton={on_id}/{on_mode}\talone_off={alone_id}"
        )

    print("---ROWS---")
    for r in rows:
        print(r)
    print("---SUMMARY---")
    print(f"n_pairs={len(PAIRS)}")
    print(f"value_added (true FU, expand changed to correct)={added}")
    print(f"wrong_intent_any={wrong_any}")
    print(f"wrong_intent_STRONG={wrong_strong}")
    print(f"false_fire_on_standalone={false_fire}")
    print(f"missed_true_followups={missed}")
    ok = wrong_strong == 0
    print("GATE_STRONG_WRONG_FROM_EXPAND", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
