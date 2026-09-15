import asyncio

import pytest

from app.models.question import QuestionAction, UtteranceType
from app.services.question_classifier import is_non_question_monologue, question_classifier

TTS_ADVERT = (
    "kindly enter your text here to convert it to natural Indian English speech. Our advanced "
    "artificial intelligence technology will transform your text into authentic Indian pronunciation "
    "with clear, articulate delivery. Please paste your text in the box below and click the large "
    "button to proceed. You will receive a high-quality MP3 audio file that you can download and "
    "utilize as per your requirement. Experience the distinctive clarity and warmth of Indian English."
)
HISTORY = [
    {"role": "interviewer", "text": "Did you use LLMs in Kuwait?"},
    {"role": "suggested_answer", "text": "No. The Kuwait work was classical ML and NLP."},
]


@pytest.mark.parametrize(
    "text",
    [
        TTS_ADVERT,
        "Welcome to our channel. Today we are going to look at the new features of this product and it is really great.",
        "This meeting is being recorded. All participants are muted on entry and it will start shortly.",
        "The weather today is sunny with a light breeze and temperatures around thirty degrees in the afternoon.",
    ],
)
def test_non_question_monologue_is_ignored(text):
    assert is_non_question_monologue(text)
    classification = asyncio.run(
        question_classifier.classify(text, conversation_history=HISTORY, prefer_speed=True)
    )
    assert classification.type == UtteranceType.STATEMENT
    assert not classification.is_follow_up
    assert question_classifier.determine_action(classification) == QuestionAction.LISTEN


@pytest.mark.parametrize(
    "text",
    [
        "How long did you work in Kuwait?",
        "Okay so, walk me through the BTEC similarity project you built at the ministry.",
        "I want you to tell us about a time you disagreed with your manager and how you handled it.",
        "Let's talk about RAG. In your projects at the ministry, chunking and retrieval were built by you.",
        "And what did you do about it after that",
        "We are a government financial entity with strict data rules. Tell me how you would deploy an LLM here.",
        "Explain the difference between LoRA and full fine tuning.",
        "Your experience with Whisper on the kiosk project, the accuracy problems and how they were solved.",
        "حدثني عن خبرتك في مشروع الوزارة وكيف تعاملت مع البيانات",
    ],
)
def test_real_interviewer_questions_still_answered(text):
    assert not is_non_question_monologue(text)
    classification = asyncio.run(
        question_classifier.classify(text, conversation_history=HISTORY, prefer_speed=True)
    )
    assert question_classifier.determine_action(classification) == QuestionAction.SHOW_ANSWER


@pytest.mark.parametrize(
    "text",
    [
        "Okay thanks, that makes sense.",
        "mm hmm yeah",
        "Okay thanks.",
        "Got it.",
    ],
)
def test_soft_acknowledgments_are_not_answered(text):
    from app.services.question_classifier import is_greeting_or_filler

    assert is_greeting_or_filler(text)
    classification = asyncio.run(
        question_classifier.classify(text, conversation_history=HISTORY, prefer_speed=True)
    )
    assert classification.type == UtteranceType.STATEMENT
    assert question_classifier.determine_action(classification) == QuestionAction.LISTEN


def test_short_why_how_are_follow_ups_with_history():
    for text in ("Why?", "How?"):
        classification = asyncio.run(
            question_classifier.classify(text, conversation_history=HISTORY, prefer_speed=True)
        )
        assert classification.type == UtteranceType.FOLLOW_UP
        assert classification.is_follow_up
        assert question_classifier.determine_action(classification) == QuestionAction.SHOW_ANSWER
