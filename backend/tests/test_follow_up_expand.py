"""Unit tests for contextual follow-up expand helpers (no embedder required)."""

from __future__ import annotations

from app.services import follow_up_expand as fue


def test_follow_up_hint_objectless_use_in_project():
    assert fue.follow_up_hint("Are you use in your project?", has_prior=True) is True
    assert fue.follow_up_hint("Are you use in your project?", has_prior=False) is False


def test_follow_up_hint_skips_when_distinctive_present():
    assert fue.follow_up_hint("Have you used agentic AI in your projects?", has_prior=True) is False
    assert fue.follow_up_hint("What is RAG?", has_prior=True) is False


def test_follow_up_hint_generic_markers():
    assert fue.follow_up_hint("what was your role in it?", has_prior=True) is True


def test_subject_from_prior_agentic_question():
    history = [{"role": "interviewer", "text": "What is agentic AI?"}]
    # normalize_for_matching drops bare "ai"; distinctive token remains "agentic".
    assert fue.subject_from_prior(history) == "agentic"


def test_append_subject_into_use_in_project():
    out = fue.append_subject("Are you use in your project?", "agentic")
    assert out.casefold() == "are you use agentic in your project?"
    assert "agentic" in out.casefold()


def test_append_subject_idempotent():
    text = "Are you use agentic in your project?"
    assert fue.append_subject(text, "agentic") == text


def test_reconcile_caps_strong_when_intent_changes():
    from app.services.question_bank import BankEntry, BankMatch

    raw_e = BankEntry(
        id="proj.early_warning.tech",
        bank="cv",
        category="x",
        topic="early",
        question="tech?",
        aliases=(),
        keywords=(),
        answer_en="a",
    )
    exp_e = BankEntry(
        id="cv.projects_stack_overview",
        bank="cv",
        category="x",
        topic="projects",
        question="stack?",
        aliases=(),
        keywords=(),
        answer_en="b",
    )
    raw = BankMatch(
        entry=raw_e, score=0.80, semantic=0.7, lexical=0.7, keyword=0.0, alias="", mode="strong"
    )
    exp = BankMatch(
        entry=exp_e, score=0.90, semantic=0.8, lexical=0.8, keyword=0.0, alias="", mode="strong"
    )
    out = fue.reconcile_raw_and_expanded(
        raw, exp, expanded_text="Are you use agentic in your project?"
    )
    assert out.entry.id == "cv.projects_stack_overview"
    assert out.mode == "weak"


def test_flag_defaults_off(monkeypatch):
    monkeypatch.setattr(fue, "LIVE_FOLLOW_UP_EXPAND", "off")
    assert fue.follow_up_expand_enabled() is False
    monkeypatch.setattr(fue, "LIVE_FOLLOW_UP_EXPAND", "on")
    assert fue.follow_up_expand_enabled() is True
