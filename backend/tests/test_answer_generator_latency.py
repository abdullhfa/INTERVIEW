import unittest
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.models.candidate import CandidateProfile, AnswerLanguageMode, AnswerLengthMode
from app.models.question import (
    QuestionCategory,
    UtteranceClassification,
    UtteranceType,
)
from app.services.answer_generator import answer_generator
from app.services.answer_generator import BilingualAnswerText


class AnswerGeneratorLatencyRegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        answer_generator.clear_specialist_cache()
        # These tests assert LLM call shape; disable the prepared bank short-circuit.
        bank_patch = patch.object(settings, "question_bank_enabled", False)
        bank_patch.start()
        self.addCleanup(bank_patch.stop)

    async def test_general_quick_answer_avoids_retrieval_and_second_model_call(self):
        classification = UtteranceClassification(
            type=UtteranceType.QUESTION,
            confidence=0.95,
            normalized_question="What is AI?",
            raw_utterance="What is AI?",
            category=QuestionCategory.AI_ML,
            requires_candidate_context=False,
        )

        with (
            patch(
                "app.services.answer_generator.context_retriever.retrieve",
                new=AsyncMock(),
            ) as retrieve,
            patch(
                "app.services.answer_generator.gemini.generate_text",
                new=AsyncMock(return_value="AI is the simulation of human intelligence."),
            ) as generate,
            patch(
                "app.services.answer_generator.answer_validator.validate",
                new=AsyncMock(),
            ) as validate,
        ):
            result = await answer_generator.generate(
                classification,
                CandidateProfile(),
                [],
                length_mode=AnswerLengthMode.QUICK,
            )

        retrieve.assert_not_awaited()
        validate.assert_not_awaited()
        self.assertTrue(result.validation.is_valid)
        self.assertEqual(generate.await_args.kwargs["model"], settings.gemini_answer_model)
        self.assertEqual(generate.await_args.kwargs["max_output_tokens"], 384)
        self.assertIsNone(generate.await_args.kwargs["thinking_budget"])

    async def test_repeated_specialist_question_uses_bounded_answer_cache(self):
        classification = UtteranceClassification(
            type=UtteranceType.QUESTION,
            confidence=0.95,
            normalized_question="What is machine learning?",
            raw_utterance="What is machine learning?",
            category=QuestionCategory.AI_ML,
            requires_candidate_context=False,
        )

        with patch(
            "app.services.answer_generator.gemini.generate_text",
            new=AsyncMock(return_value="Machine learning helps computers learn from data."),
        ) as generate:
            first = await answer_generator.generate(
                classification,
                CandidateProfile(),
                [],
                question_id="first",
                length_mode=AnswerLengthMode.QUICK,
            )
            second = await answer_generator.generate(
                classification,
                CandidateProfile(),
                [],
                question_id="second",
                length_mode=AnswerLengthMode.QUICK,
            )

        generate.assert_awaited_once()
        self.assertEqual(first.answer_en, second.answer_en)
        self.assertEqual(second.question_id, "second")

    async def test_bilingual_answer_uses_one_structured_call_and_populates_both_fields(self):
        classification = UtteranceClassification(
            type=UtteranceType.QUESTION,
            confidence=0.95,
            normalized_question="What is AI?",
            raw_utterance="What is AI?",
            category=QuestionCategory.AI_ML,
            requires_candidate_context=False,
        )
        bilingual = BilingualAnswerText(
            answer_en="AI helps computers do tasks that need human thinking.",
            answer_ar="يساعد الذكاء الاصطناعي الحاسوب على تنفيذ مهام تحتاج إلى تفكير بشري.",
        )

        with (
            patch(
                "app.services.answer_generator.gemini.generate_structured",
                new=AsyncMock(return_value=bilingual),
            ) as generate_structured,
            patch(
                "app.services.answer_generator.gemini.generate_text",
                new=AsyncMock(),
            ) as generate_text,
        ):
            result = await answer_generator.generate(
                classification,
                CandidateProfile(),
                [],
                length_mode=AnswerLengthMode.QUICK,
                language_mode=AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH,
            )

        generate_structured.assert_awaited_once()
        generate_text.assert_not_awaited()
        self.assertEqual(result.answer_en, bilingual.answer_en)
        self.assertEqual(result.answer_ar, bilingual.answer_ar)
        self.assertEqual(
            generate_structured.await_args.args[1],
            BilingualAnswerText,
        )
        self.assertEqual(
            generate_structured.await_args.kwargs["max_output_tokens"],
            768,
        )
