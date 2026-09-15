"""Unit tests for TECH_ACRONYM_RECOVERY."""

from __future__ import annotations

from app.services.question_bank import question_bank
from app.services.tech_acronym_recovery import (
    clear_acronym_vocab_cache,
    recover_acronyms,
)
from app.services.technical_term_repair import clear_repair_cache, repair_technical_terms


def setup_function(_fn=None):
    clear_repair_cache()
    clear_acronym_vocab_cache()
    question_bank.load(force=True)


def test_lalam_recovers_to_llm_not_llama():
    rec = recover_acronyms("What is the Lalam?")
    assert "LLM" in rec.recovered_transcript
    assert "llama" not in rec.recovered_transcript.lower()
    assert any(r[1] == "LLM" for r in rec.replacements)
    m = question_bank.match("What is the Lalam?")
    assert m is not None
    assert m.entry.id == "tech.what_is_llm"


def test_el_el_em_to_llm():
    rec = recover_acronyms("What is el el em?")
    assert "LLM" in rec.recovered_transcript
    m = question_bank.match("What is el el em?")
    assert m is not None
    assert "llm" in m.entry.id.lower() or "llm" in m.entry.question.lower()


def test_clean_llm_unchanged():
    raw = "What is LLM?"
    rec = recover_acronyms(raw)
    assert rec.replacements == []
    assert repair_technical_terms(raw) == raw
    m = question_bank.match(raw)
    assert m is not None
    assert m.entry.id == "tech.what_is_llm"


def test_are_a_g_to_rag():
    rec = recover_acronyms("What is are a g?")
    assert "RAG" in rec.recovered_transcript


def test_en_eight_en_to_n8n():
    rec = recover_acronyms("When would you use en eight en?")
    assert "n8n" in rec.recovered_transcript.lower()


def test_london_not_forced_to_acronym():
    raw = "What did London give you that you would otherwise need to build yourself?"
    rec = recover_acronyms(raw)
    assert rec.replacements == []
    assert "LLM" not in rec.recovered_transcript
