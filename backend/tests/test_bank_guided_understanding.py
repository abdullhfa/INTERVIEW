"""Unit tests for bank-guided understanding."""

from __future__ import annotations

from app.services.bank_guided_understanding import (
    clear_bank_guided_cache,
    understand_interview_question,
)
from app.services.question_bank import question_bank
from app.services.technical_term_repair import clear_repair_cache


def setup_function(_fn=None):
    clear_repair_cache()
    clear_bank_guided_cache()
    question_bank.load(force=True)


def test_lalam_to_llm_bank_primary():
    u = understand_interview_question("What is the Lalam?")
    assert u.intent_id == "tech.what_is_llm"
    assert not u.ambiguous
    m = question_bank.match("What is the Lalam?")
    assert m is not None
    assert m.entry.id == "tech.what_is_llm"


def test_and_you_plan_to_project():
    u = understand_interview_question("and you plan your project")
    assert u.intent_id == "cv.projects_overview"
    assert "project" in u.canonical_question.lower()


def test_how_plan_not_project_overview():
    u = understand_interview_question("How do you plan your project?")
    assert u.intent_id != "cv.projects_overview"
    m = question_bank.match("How do you plan your project?")
    assert m is None or m.entry.id != "cv.projects_overview"


def test_dual_transcript_retained():
    raw = "and you plan your project"
    u = understand_interview_question(raw)
    assert u.raw_transcript == raw
    assert u.recovered_transcript
    assert u.canonical_question
