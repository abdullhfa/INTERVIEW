"""Unit tests for INTERVIEW_PHRASE_RECOVERY."""

from __future__ import annotations

from app.services.interview_phrase_recovery import (
    clear_phrase_cache,
    recover_interview_phrases,
)
from app.services.question_bank import question_bank
from app.services.technical_term_repair import clear_repair_cache, repair_technical_terms


def setup_function(_fn=None):
    clear_repair_cache()
    clear_phrase_cache()
    question_bank.load(force=True)


def test_and_you_plan_recovers_explain_project():
    rec = recover_interview_phrases("and you plan your project")
    assert rec.applied
    assert rec.recovered_transcript == "Explain your project"
    assert rec.recovery_type == "interview_phrase"
    assert "plan your project" not in rec.recovered_transcript.lower() or "explain" in rec.recovered_transcript.lower()
    m = question_bank.match("and you plan your project")
    assert m is not None
    assert m.entry.id == "cv.projects_overview"


def test_how_do_you_plan_not_rewritten_to_explain():
    raw = "How do you plan your project?"
    rec = recover_interview_phrases(raw)
    assert not rec.applied
    assert "explain" not in rec.recovered_transcript.lower()
    assert repair_technical_terms(raw).lower().startswith("how do you plan")


def test_tell_me_a_boat_yourself():
    rec = recover_interview_phrases("tell me a boat yourself")
    assert rec.applied
    assert rec.recovered_transcript == "Tell me about yourself"
    m = question_bank.match("tell me a boat yourself")
    assert m is not None
    assert m.entry.id == "intro.tell_me_about_yourself"


def test_clean_explain_unchanged():
    raw = "Explain your project"
    rec = recover_interview_phrases(raw)
    assert not rec.applied
    assert repair_technical_terms(raw) == raw


def test_raw_preserved_in_result():
    raw = "and you plan your project"
    rec = recover_interview_phrases(raw)
    assert rec.raw_transcript == raw
    assert rec.recovered_transcript != raw
