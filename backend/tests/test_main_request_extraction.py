"""Unit tests for MAIN_REQUEST_EXTRACTION (structure only + match gating)."""

from __future__ import annotations

from app.services.main_request_extraction import (
    extract_main_request,
    is_long_or_indirect_question,
    match_with_main_request,
)
from app.services.question_bank import question_bank


def test_short_direct_skips_override():
    q = "What is RAG?"
    assert not is_long_or_indirect_question(q)
    ex = extract_main_request(q)
    assert ex.applied is False
    m, _, meta = match_with_main_request(q)
    assert meta["override"] is False
    assert m is not None
    assert m.entry.id == question_bank.match(q).entry.id


def test_scenario_extracts_final_ask():
    q = (
        "Imagine your RAG system retrieves outdated policy information and answers from it. "
        "Walk me through how you would detect the issue, where you would fix it, and how you "
        "would prevent the same failure from reaching users again."
    )
    assert is_long_or_indirect_question(q)
    ex = extract_main_request(q)
    assert ex.applied is True
    assert "detect" in ex.main_request.lower()
    assert len(ex.secondary_requests) >= 1
    assert "outdated" in (ex.background_context + " " + ex.main_request).lower()


def test_target_latency_maps_to_latency_family():
    q = (
        "Your assistant understands the interview question correctly, but the answer arrives "
        "several seconds after the interviewer finishes speaking. Walk me through how you would "
        "measure the delay and decide whether the bottleneck is speech recognition, retrieval, "
        "model inference, or the user interface."
    )
    m, ex, meta = match_with_main_request(q)
    assert ex.applied is True
    assert meta["override"] is True
    assert m is not None
    assert m.entry.id in {"tech.latency_p95", "hard.production_monitoring"}
    assert m.mode != "strong" or m.entry.id == question_bank.match(
        "How do you measure and improve latency?"
    ).entry.id


def test_low_confidence_does_not_fabricate():
    q = "Something something maybe related somehow?"
    ex = extract_main_request(q)
    assert ex.applied is False or ex.confidence < 0.72
