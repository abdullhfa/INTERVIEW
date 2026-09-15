import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import speech_recognition as sr

from app.config import settings
from app.audio.stt_engine import stt_engine
from app.audio.whisper_stt import repair_live_transcript


def _fake_gemini() -> SimpleNamespace:
    generate = Mock()
    generate_async = AsyncMock()
    return SimpleNamespace(
        models=SimpleNamespace(generate_content=generate),
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_async)),
    )


class STTEngineLatencyRegressionTests(unittest.TestCase):
    def test_candidate_audio_skips_gemini_fallback(self):
        audio = np.zeros(1600, dtype=np.float32)
        fake = _fake_gemini()

        with (
            patch.object(stt_engine, "_gemini", fake),
            patch.object(
                stt_engine.recognizer,
                "recognize_google",
                side_effect=sr.UnknownValueError(),
            ),
        ):
            result = stt_engine.transcribe(
                audio,
                allow_gemini_fallback=False,
            )

        self.assertEqual(result, "")
        fake.models.generate_content.assert_not_called()
        self.assertEqual(
            stt_engine.recognizer.operation_timeout,
            settings.google_stt_timeout_seconds,
        )


class STTEngineRealtimeRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_realtime_transcription_uses_cancellable_fast_model(self):
        """Whisper is the live primary STT; Gemini is only an optional fallback."""
        audio = np.ones(1600, dtype=np.float32) * 0.02

        with patch.object(
            stt_engine,
            "_transcribe_whisper",
            new=AsyncMock(return_value="What is artificial intelligence?"),
        ) as whisper:
            result = await stt_engine.transcribe_realtime(audio, timeout_seconds=1)

        self.assertEqual(result, "What is artificial intelligence?")
        whisper.assert_awaited_once()

    async def test_realtime_gemini_fallback_after_whisper_miss(self):
        """After Whisper miss, Google miss → optional Gemini realtime path."""
        audio = np.ones(1600, dtype=np.float32) * 0.02
        with (
            patch.object(
                stt_engine,
                "_transcribe_whisper",
                new=AsyncMock(return_value=""),
            ),
            patch(
                "app.audio.stt_engine.settings.google_stt_fallback_enabled",
                True,
            ),
            patch.object(
                stt_engine,
                "_transcribe_google_sequential",
                new=AsyncMock(return_value=""),
            ),
            patch.object(
                stt_engine,
                "_gemini_realtime",
                new=AsyncMock(return_value="What is artificial intelligence?"),
            ) as gemini,
            patch.object(stt_engine, "_gemini", object()),
        ):
            result = await stt_engine.transcribe_realtime(audio, timeout_seconds=1)

        self.assertEqual(result, "What is artificial intelligence?")
        gemini.assert_awaited_once()

    async def test_realtime_transcription_skips_near_silence(self):
        fake = _fake_gemini()
        with (
            patch.object(stt_engine, "_gemini", fake),
            patch.object(
                stt_engine,
                "_transcribe_whisper",
                new=AsyncMock(),
            ) as whisper,
        ):
            result = await stt_engine.transcribe_realtime(np.zeros(1600, dtype=np.float32))

        self.assertEqual(result, "")
        whisper.assert_not_awaited()
        fake.aio.models.generate_content.assert_not_awaited()


class LiveTranscriptRepairTests(unittest.TestCase):
    def test_repairs_water_transformers(self):
        self.assertEqual(
            repair_live_transcript("water transformers"),
            "what are transformers",
        )

    def test_leaves_real_water_phrase_alone(self):
        self.assertEqual(repair_live_transcript("water cycle"), "water cycle")

    def test_leaves_normal_question_alone(self):
        self.assertEqual(
            repair_live_transcript("What are transformers?"),
            "What are transformers?",
        )


if __name__ == "__main__":
    unittest.main()
