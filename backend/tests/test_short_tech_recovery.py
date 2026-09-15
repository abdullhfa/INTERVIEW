"""Unit tests for SHORT_TECH_RECOVERY."""

from __future__ import annotations

from app.services.question_bank import question_bank
from app.services.short_tech_recovery import recover_tech_terms
from app.services.technical_term_repair import clear_repair_cache, repair_technical_terms


def setup_function(_fn=None):
    clear_repair_cache()


def test_am_bedding_recovers_to_embeddings():
    rec = recover_tech_terms("Why am bedding?")
    assert rec.recovered_terms
    assert "embedding" in rec.normalized_transcript.lower()
    m = question_bank.match("Why am bedding?")
    assert m is not None
    assert "embedding" in m.entry.id or "embedding" in m.entry.question.lower()


def test_whyland_draft_recovers_langgraph():
    rec = recover_tech_terms("Whyland draft here.")
    assert "langgraph" in rec.normalized_transcript.lower()
    m = question_bank.match("Whyland draft here.")
    assert m is not None
    assert "langgraph" in m.entry.id.lower()


def test_london_does_not_become_langchain():
    rec = recover_tech_terms(
        "What did London give you that you would otherwise need to build yourself?"
    )
    assert "langchain" not in rec.normalized_transcript.lower()


def test_unrecoverable_garbage_unchanged():
    raw = "What in a me, amet, amma, am."
    rec = recover_tech_terms(raw)
    assert rec.recovered_terms == []
    assert rec.normalized_transcript == raw


def test_clean_short_unchanged():
    raw = "Why embeddings?"
    rec = recover_tech_terms(raw)
    assert rec.recovered_terms == []
    assert repair_technical_terms(raw) == raw


def test_zundra_ambiguous_no_forced_chroma():
    """Zundra must not be force-mapped to Chroma (ambiguous vs LangGraph)."""
    rec = recover_tech_terms("When will you use Zundra?")
    assert "chroma" not in rec.normalized_transcript.lower()
