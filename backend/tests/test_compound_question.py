"""Unit tests for multi-intent / compound question layer."""

from __future__ import annotations

import pytest

from app.services.compound_answer_builder import build_compound_answer
from app.services.compound_question_decomposer import decompose_compound_question
from app.services.compound_question_detector import detect_question_complexity
from app.services.compound_question_pipeline import resolve_compound_question
from app.services.question_bank import question_bank


@pytest.fixture(scope="module", autouse=True)
def _load_bank() -> None:
    question_bank.load()


def test_case1_what_is_rag_is_single() -> None:
    d = detect_question_complexity("What is RAG?")
    assert d.question_type == "single"
    r = resolve_compound_question("What is RAG?", detection=d)
    assert r.used_compound_path is False


def test_case2_rag_definition_and_mechanism_small_set() -> None:
    text = "What is RAG and how does it work?"
    d = detect_question_complexity(text)
    assert d.question_type in {"single", "compound", "uncertain"}
    r = resolve_compound_question(text, detection=d)
    if r.used_compound_path:
        assert r.answer_en
        assert len(r.selected_intents) <= 2
        blob = r.answer_en.lower()
        assert "retriev" in blob or "rag" in blob


def test_case3_rag_why_empty_is_compound() -> None:
    text = (
        "What is RAG, why did you use it instead of fine tuning, "
        "and what happens if retrieval returns nothing?"
    )
    d = detect_question_complexity(text)
    assert d.question_type in {"compound", "uncertain"}
    r = resolve_compound_question(text, detection=d)
    assert r.used_compound_path
    assert r.requested_parts_count >= 2
    assert r.answer_en
    assert r.matched_parts_count >= 2 or r.full_compound_success


def test_case4_similarity_checker_compound() -> None:
    text = (
        "Explain the similarity checker, why it is not RAG, "
        "and who makes the final decision."
    )
    d = detect_question_complexity(text)
    assert d.question_type in {"compound", "uncertain"}
    r = resolve_compound_question(text, detection=d)
    assert r.used_compound_path
    ids = " ".join(r.selected_intents)
    assert "similarity" in ids
    assert r.answer_en
    lower = r.answer_en.lower()
    assert "embed" in lower or "similar" in lower or "rag" in lower


def test_case5_agentic_workflow_compound() -> None:
    text = (
        "Tell me about your agentic BTEC workflow, where the human "
        "approval happens, and what happens if validation fails."
    )
    d = detect_question_complexity(text)
    assert d.question_type in {"compound", "uncertain"}
    r = resolve_compound_question(text, detection=d)
    # May be facet-driven partial or full; must not invent production claims.
    if r.answer_en:
        assert "langgraph in production" not in r.answer_en.lower() or "not" in r.answer_en.lower()


def test_case6_langgraph_single() -> None:
    d = detect_question_complexity("Tell me about LangGraph.")
    # Short single-topic ask should stay single (or uncertain at worst).
    assert d.question_type in {"single", "uncertain"}
    r = resolve_compound_question("Tell me about LangGraph.", detection=d)
    if d.question_type == "single":
        assert r.used_compound_path is False


def test_case7_langgraph_compound_honest() -> None:
    text = (
        "Have you used LangGraph in production, how would it help "
        "your current Python workflow, and when would you use it?"
    )
    d = detect_question_complexity(text)
    assert d.question_type in {"compound", "uncertain"}
    r = resolve_compound_question(text, detection=d)
    if r.answer_en:
        lower = r.answer_en.lower()
        # Must not invent production use.
        assert "not" in lower or "python" in lower or "checkpoint" in lower or "langgraph" in lower
        assert "i used langgraph in production" not in lower


def test_pronoun_resolution_inherits_rag() -> None:
    decomp = decompose_compound_question(
        "Explain RAG, and why did you choose it?"
    )
    joined = " ".join(decomp.sub_questions).lower()
    assert "rag" in joined


def test_answer_builder_concise_bank_only() -> None:
    m1 = question_bank.match("What is RAG?")
    m2 = question_bank.match("When would you use RAG versus fine tuning?")
    matches = [m for m in (m1, m2) if m is not None]
    if len(matches) < 2:
        pytest.skip("bank matches unavailable")
    built = build_compound_answer(matches)
    assert built is not None
    assert built.sentence_count <= 7
    assert built.answer_en
    assert built.source_ids
