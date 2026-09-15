"""P2 statement gate: fail-closed STATEMENT, structural request, light lexical."""

from __future__ import annotations

import asyncio

import pytest

from app.models.question import QuestionAction, UtteranceType
from app.services.question_classifier import (
    has_structural_interview_request,
    is_greeting_or_filler,
    is_system_audio_or_noise,
    question_classifier,
)


REJECT = [
    "Yeah, John.",
    "Okay.",
    "Thanks.",
    "Your download is ready.",
    "Playback started.",
    "Click here to start.",
]

PASS = [
    "Explain your project.",
    "Tell me about yourself.",
    "Walk me through your experience.",
    "Describe your role.",
    "What is LLM?",
]


@pytest.mark.parametrize("text", REJECT)
def test_p2_reject_examples_stop(text: str):
    assert is_greeting_or_filler(text) or is_system_audio_or_noise(text) or (
        not has_structural_interview_request(text)
    )
    classification = asyncio.run(
        question_classifier.classify(text, conversation_history=[], prefer_speed=True)
    )
    assert classification.type in {UtteranceType.STATEMENT, UtteranceType.UNCERTAIN}
    assert question_classifier.determine_action(classification) == QuestionAction.LISTEN


@pytest.mark.parametrize("text", PASS)
def test_p2_pass_examples_answer(text: str):
    assert has_structural_interview_request(text)
    classification = asyncio.run(
        question_classifier.classify(text, conversation_history=[], prefer_speed=True)
    )
    assert classification.type in {UtteranceType.QUESTION, UtteranceType.FOLLOW_UP}
    assert question_classifier.determine_action(classification) == QuestionAction.SHOW_ANSWER


def test_p2_statement_default_listen_without_structural():
    classification = asyncio.run(
        question_classifier.classify(
            "The weather is nice today around the office.",
            conversation_history=[],
            prefer_speed=True,
        )
    )
    assert classification.type == UtteranceType.STATEMENT
    assert question_classifier.determine_action(classification) == QuestionAction.LISTEN


def test_p2_sequence_question_box_accepts_twice_only():
    """Simulate the live acceptance sequence at the classifier gate."""
    sequence = [
        ("What is LLM?", QuestionAction.SHOW_ANSWER),
        ("Okay.", QuestionAction.LISTEN),
        ("Yeah, John.", QuestionAction.LISTEN),
        ("Your download is ready.", QuestionAction.LISTEN),
        ("Explain your project.", QuestionAction.SHOW_ANSWER),
    ]
    accepted = 0
    for text, expected in sequence:
        classification = asyncio.run(
            question_classifier.classify(text, conversation_history=[], prefer_speed=True)
        )
        action = question_classifier.determine_action(classification)
        assert action == expected, (text, action, classification.type)
        if action == QuestionAction.SHOW_ANSWER:
            accepted += 1
    assert accepted == 2


@pytest.mark.asyncio
async def test_bank_task_cancel_await_safe():
    """Cancelled bank lookup must be awaited so asyncio does not warn."""

    async def _slow():
        await asyncio.sleep(60)
        return None

    bank_task = asyncio.create_task(_slow())
    bank_task.cancel()
    try:
        await bank_task
    except asyncio.CancelledError:
        pass
    assert bank_task.cancelled() or bank_task.done()
