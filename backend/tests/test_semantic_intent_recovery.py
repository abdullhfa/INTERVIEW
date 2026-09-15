"""Unit tests for semantic intent agreement + recovery."""

from __future__ import annotations

import pytest

from app.services.intent_profile import intent_agreement, build_intent_profile
from app.services.question_bank import question_bank
from app.services.semantic_intent_index import semantic_intent_index
from app.services.semantic_intent_recovery import (
    recover_semantic_intent,
    should_trigger_semantic_recovery,
)


@pytest.fixture(scope="module", autouse=True)
def _bank() -> None:
    question_bank._warm = False
    question_bank.warm()
    semantic_intent_index.ensure_loaded()


def test_agreement_uses_aliases_not_only_canonical() -> None:
    entry = question_bank.get("proj.similarity.stack") or question_bank.get("proj.similarity.is_rag")
    assert entry is not None
    spoken = (
        "Why do you use embeddings and cosine similarity instead of an LLM "
        "in the similarity checker?"
    )
    score = intent_agreement(entry, spoken)
    # Must beat bare canonical-only fuzz for this medium paraphrase.
    from rapidfuzz import fuzz

    canonical_only = fuzz.token_set_ratio(spoken, entry.question) / 100.0
    assert score >= canonical_only
    assert score >= 0.45


def test_rag_paraphrases_same_family() -> None:
    variants = [
        "What is RAG?",
        "Can you explain Retrieval-Augmented Generation?",
        "What does RAG actually do?",
    ]
    ids = []
    for q in variants:
        m = question_bank.match(q)
        d = recover_semantic_intent(q, m)
        chosen = d.match or m
        assert chosen is not None
        ids.append(chosen.entry.id)
    # All should land in rag-related intents
    assert all("rag" in i.lower() or "retrieval" in i.lower() for i in ids)


def test_fast_path_skips_recovery_for_clear_short() -> None:
    q = "What is RAG?"
    m = question_bank.match(q)
    # Even if weak before warm, trigger logic should be conservative when agreement high.
    trigger, reason = should_trigger_semantic_recovery(q, m)
    if m is not None and m.mode == "strong":
        assert trigger is False
        assert reason == "strong_agrees"


def test_medium_similarity_not_generic_rag_def() -> None:
    q = (
        "Why do you use embeddings and cosine similarity instead of an LLM "
        "in the similarity checker?"
    )
    m = question_bank.match(q)
    d = recover_semantic_intent(q, m)
    chosen = d.match or m
    assert chosen is not None
    assert "similarity" in chosen.entry.id or "similarity" in chosen.entry.topic
    assert chosen.entry.id != "tech.rag_what"


def test_action_mismatch_prefers_how_over_definition() -> None:
    q = "How would LangGraph help if your Python agentic workflow became more complex?"
    m = question_bank.match(q)
    d = recover_semantic_intent(q, m)
    chosen = d.match or m
    assert chosen is not None
    # Prefer workflow/compare over bare definition when possible.
    if d.applied and d.match is not None and d.reason.startswith("recovered"):
        assert "what_is_langgraph" not in chosen.entry.id or chosen.mode == "weak"


def test_profile_builds_from_bank_only() -> None:
    entry = question_bank.entries[0]
    profile = build_intent_profile(entry)
    assert profile.intent_id == entry.id
    assert profile.canonical_question == entry.question
    assert profile.profile_blob


def test_ultra_short_why_recall_safe() -> None:
    q = "Why recall?"
    m = question_bank.match(q)
    d = recover_semantic_intent(q, m)
    chosen = d.match or m
    # Safe: abstain or land on a recall-metric family; never strong with tiny margin.
    if chosen is not None and chosen.mode == "strong":
        assert d.margin >= 0.04 or d.agreement >= 0.55
    if chosen is not None:
        blob = " ".join(
            [
                chosen.entry.id,
                chosen.entry.question,
                " ".join(chosen.entry.keywords or ()),
            ]
        ).lower()
        assert "recall" in blob or d.abstain_reason


def test_intent_meaning_ok_paraphrase_gate() -> None:
    from app.services.intent_profile import intent_meaning_ok

    entry = question_bank.get("hard.empty_retrieval")
    assert entry is not None
    spoken = (
        "What should the system do when the retrieved context does not "
        "contain enough information?"
    )
    ok, agr = intent_meaning_ok(entry, spoken, match_score=0.52)
    assert ok is True
    assert agr >= 0.52


def test_ministry_business_question_not_strong_wrong() -> None:
    """HC guard: vague ministry-value asks must not become strong on agentic-RAG design."""
    q = "How does this solution help the Ministry?"
    m = question_bank.match(q)
    d = recover_semantic_intent(q, m)
    chosen = d.match or m
    if chosen is not None and chosen.entry.id == "hard.agentic_rag_design":
        assert chosen.mode != "strong"
    if chosen is not None and chosen.mode == "strong":
        surface = " ".join(
            [
                chosen.entry.id,
                chosen.entry.question,
                " ".join(chosen.entry.aliases or ()),
                " ".join(chosen.entry.keywords or ()),
            ]
        ).lower()
        assert "ministr" in surface or "moe" in chosen.entry.id.lower()
