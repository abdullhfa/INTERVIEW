"""Tests for LLMGateway (DeepSeek) — updated for the post-Gemini HTTP client."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.config import settings
from app.models.candidate import CandidateProfile, ProfileExtractionResult
from app.services.candidate_profile import candidate_profile_service
from app.services.gemini_gateway import LLMGateway

# Historical test class name; the runtime class is LLMGateway.
GeminiGateway = LLMGateway


def _ok_extraction(name: str = "John Doe") -> ProfileExtractionResult:
    return ProfileExtractionResult(
        extracted_profile=CandidateProfile(personal_profile={"full_name": name}),
        raw_text=f"{name}, software engineer",
        extraction_status="complete",
    )


class GeminiGatewayTimeoutRegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        candidate_profile_service.clear_extraction_cache()

    async def test_timeout_error_contains_actionable_duration(self):
        gateway = GeminiGateway.__new__(GeminiGateway)
        gateway._api_key = "test-key"
        gateway._base_url = "https://example.test"
        gateway._client_lock = __import__("asyncio").Lock()

        slow_post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        gateway._client = SimpleNamespace(post=slow_post, is_closed=False)

        with self.assertRaisesRegex(
            TimeoutError, r"DeepSeek request timed out after 0\.01 seconds"
        ):
            await gateway._chat_completion(
                {"model": "test-model", "messages": [{"role": "user", "content": "x"}]},
                timeout_seconds=0.01,
            )

        slow_post.assert_awaited_once()

    async def test_text_generation_retries_truncated_provider_response(self):
        gateway = GeminiGateway.__new__(GeminiGateway)
        gateway._api_key = "test-key"
        gateway._base_url = "https://example.test"
        gateway._reasoning_model = "test-model"
        gateway._fast_model = "test-model"
        gateway._client_lock = __import__("asyncio").Lock()

        short = ("Hi.", "length")
        complete = ("A complete answer that is long enough to keep.", "stop")
        with patch.object(
            gateway,
            "_chat_completion",
            new=AsyncMock(side_effect=[short, complete]),
        ) as chat:
            result = await gateway.generate_text("question", max_output_tokens=100)

        self.assertEqual(result, complete[0])
        self.assertEqual(chat.await_count, 2)
        second_payload = chat.await_args_list[1].args[0]
        self.assertEqual(second_payload["max_tokens"], 200)

    async def test_cv_extraction_uses_fast_cv_model_and_timeout(self):
        mocked_full = AsyncMock(return_value=_ok_extraction())

        with patch.object(candidate_profile_service, "_extract_full", mocked_full):
            await candidate_profile_service.extract_from_document(
                "John Doe, software engineer", "resume.txt"
            )

        mocked_full.assert_awaited_once()
        self.assertEqual(settings.gemini_cv_model, settings.deepseek_model)

    async def test_repeated_cv_text_uses_extraction_cache(self):
        mocked_full = AsyncMock(return_value=_ok_extraction())

        with patch.object(candidate_profile_service, "_extract_full", mocked_full):
            first = await candidate_profile_service.extract_from_document(
                "John Doe, software engineer", "resume.pdf"
            )
            second = await candidate_profile_service.extract_from_document(
                "John Doe, software engineer", "resume.pdf"
            )

        mocked_full.assert_awaited_once()
        self.assertEqual(
            first.extracted_profile.personal_profile.full_name,
            second.extracted_profile.personal_profile.full_name,
        )

    async def test_empty_fast_extraction_falls_back_to_reasoning_model(self):
        with patch.object(
            candidate_profile_service,
            "_extract_full",
            new=AsyncMock(side_effect=ValueError("full failed")),
        ), patch.object(
            candidate_profile_service,
            "_extract_fast",
            new=AsyncMock(return_value=_ok_extraction()),
        ) as fast:
            result = await candidate_profile_service.extract_from_document(
                "John Doe, software engineer", "resume.pdf"
            )

        fast.assert_awaited_once()
        self.assertEqual(result.extracted_profile.personal_profile.full_name, "John Doe")


if __name__ == "__main__":
    unittest.main()
