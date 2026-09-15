"""
AI Interview Coach - Speech-to-Text Engine

Transcribes candidate audio to text.
Uses SpeechRecognition with Google Web Speech API for zero-config fast STT.
Optional Gemini audio fallback when GEMINI_API_KEY is configured.
"""

from __future__ import annotations
import asyncio
import logging
import io
import wave
from typing import Any

import numpy as np
import speech_recognition as sr

from app.config import settings
from app.audio.whisper_stt import transcribe_whisper_async, warm_whisper_model

logger = logging.getLogger(__name__)

try:
    from google import genai as _genai_module
    from google.genai import types as _genai_types

    _GENAI_AVAILABLE = True
except ImportError:
    _genai_module = None
    _genai_types = None
    _GENAI_AVAILABLE = False


def _recognize_google(
    recognizer: sr.Recognizer,
    audio_record: sr.AudioData,
    *,
    language: str,
) -> str:
    """SpeechRecognition exposes recognize_google at runtime; stubs omit it."""
    recognize = getattr(recognizer, "recognize_google", None)
    if recognize is None:
        raise AttributeError("recognize_google is unavailable on this Recognizer")
    return str(recognize(audio_record, language=language))


class STTEngine:
    """Speech-to-Text transcriber."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.operation_timeout = settings.google_stt_timeout_seconds
        self._gemini: Any = None
        if settings.gemini_api_key and _GENAI_AVAILABLE and _genai_module is not None:
            self._gemini = _genai_module.Client(api_key=settings.gemini_api_key)

    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
        *,
        allow_gemini_fallback: bool = True,
    ) -> str:
        if language is None:
            language = getattr(settings, "primary_language", "en-US")

        if len(audio_data) == 0:
            return ""

        self.recognizer.operation_timeout = settings.google_stt_timeout_seconds

        audio = np.asarray(audio_data, dtype=np.float32)
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
        audio = np.clip(audio, -1.0, 1.0)

        wav_bytes = self._to_wav_bytes(audio, sample_rate)

        try:
            wav_io = io.BytesIO(wav_bytes)
            with sr.AudioFile(wav_io) as source:
                audio_record = self.recognizer.record(source)

            try:
                text = _recognize_google(
                    self.recognizer,
                    audio_record,
                    language=language,
                )
            except sr.UnknownValueError:
                text = ""
            except sr.RequestError as exc:
                logger.warning("Google STT request failed: %s", exc)
                text = ""

            if text:
                logger.info("STT Google (%s): %s", language, text)
                return text.strip()

        except Exception as e:
            logger.exception("Google STT pipeline failed: %s", e)

        if not allow_gemini_fallback or not self._gemini or _genai_types is None:
            return ""

        try:
            prompt = (
                "Transcribe the speech in this audio exactly as spoken. "
                "The audio may be Arabic, English, or mixed Arabic/English. "
                "Return ONLY the transcript text, with no explanation, labels, "
                "quotes, or markdown. If there is no intelligible speech, return an empty string."
            )
            response = self._gemini.models.generate_content(
                model=settings.gemini_fast_model,
                contents=[
                    prompt,
                    _genai_types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                ],
            )
            text = (response.text or "").strip()
            if text:
                logger.info("STT Gemini fallback: %s", text)
                return text
            logger.warning("Gemini STT returned empty text")
        except Exception:
            logger.exception("Gemini STT fallback failed")

        return ""

    def _stt_language_list(self, language: str | None) -> list[str]:
        if language:
            return [language]
        raw = getattr(settings, "stt_languages", "") or getattr(
            settings, "primary_language", "en-US"
        )
        langs = [part.strip() for part in raw.split(",") if part.strip()]
        return langs or ["en-US"]

    async def _transcribe_google_lang(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str,
    ) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.transcribe(
                audio,
                sample_rate,
                language,
                allow_gemini_fallback=False,
            ),
        )

    async def _transcribe_google_sequential(
        self,
        audio: np.ndarray,
        sample_rate: int,
        languages: list[str],
        request_timeout: float,
    ) -> str:
        """Try Google languages one-by-one with a hard per-language cap."""
        if not languages:
            return ""

        per_lang = min(
            settings.google_stt_per_lang_timeout_seconds,
            max(1.0, request_timeout / len(languages)),
        )
        for lang in languages:
            try:
                text = await asyncio.wait_for(
                    self._transcribe_google_lang(audio, sample_rate, lang),
                    timeout=per_lang,
                )
            except asyncio.TimeoutError:
                logger.warning("Google STT (%s) timed out after %.1fs", lang, per_lang)
                continue
            except Exception:
                logger.exception("Google STT (%s) failed", lang)
                continue
            if text:
                logger.info("STT Google sequential (%s): %s", lang, text)
                return text
        return ""

    async def _transcribe_whisper(
        self,
        audio: np.ndarray,
        sample_rate: int,
        request_timeout: float,
        *,
        accurate: bool = False,
    ) -> str:
        if not settings.whisper_stt_enabled:
            return ""

        try:
            text = await asyncio.wait_for(
                transcribe_whisper_async(audio, sample_rate, accurate=accurate),
                timeout=min(request_timeout, settings.whisper_stt_timeout_seconds * (1.6 if accurate else 1.0)),
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Whisper STT timed out after %.1fs accurate=%s",
                min(request_timeout, settings.whisper_stt_timeout_seconds),
                accurate,
            )
            return ""
        except Exception:
            logger.exception("Whisper STT failed")
            return ""

        if text:
            logger.info("STT Whisper%s: %s", " accurate" if accurate else "", text)
        return text

    async def transcribe_realtime(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
        *,
        timeout_seconds: float | None = None,
        model: str | None = None,
        accurate: bool = False,
    ) -> str:
        """Transcribe live audio with timeout; Google first, optional Gemini fallback."""
        if len(audio_data) == 0:
            return ""

        audio = np.asarray(audio_data, dtype=np.float32)
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
        audio = np.clip(audio, -1.0, 1.0)
        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if rms < 0.0003 and peak < 0.008:
            logger.info(
                "STT skipped near-silent audio (rms=%.6f peak=%.6f)",
                rms,
                peak,
            )
            return ""

        request_timeout = timeout_seconds or settings.stt_timeout_seconds
        languages = self._stt_language_list(language)

        whisper_text = await self._transcribe_whisper(
            audio,
            sample_rate,
            request_timeout,
            accurate=accurate,
        )
        if whisper_text:
            return whisper_text

        if accurate:
            # Accurate path is Whisper-only; do not fall back to Google on second pass.
            return ""

        if not settings.google_stt_fallback_enabled:
            return ""

        google_budget = min(4.0, request_timeout)

        try:
            google_text = await self._transcribe_google_sequential(
                audio,
                sample_rate,
                languages,
                google_budget,
            )
            if google_text:
                return google_text
        except Exception:
            logger.exception("Google STT realtime failed")

        if self._gemini:
            return await self._gemini_realtime(audio, sample_rate, request_timeout, model)

        return ""

    async def _gemini_realtime(
        self,
        audio: np.ndarray,
        sample_rate: int,
        request_timeout: float,
        model: str | None,
    ) -> str:
        if not self._gemini or _genai_types is None:
            return ""

        wav_bytes = self._to_wav_bytes(audio, sample_rate)
        prompt = (
            "Transcribe only the spoken words in this interview audio. "
            "The speech may be Arabic, English, or mixed Arabic/English. "
            "Preserve English technical terms when they are spoken inside Arabic. "
            "Return only the exact transcript with no label, quotes, translation, answer, or markdown. "
            "If no clear speech is present, return exactly NO_SPEECH."
        )
        config = _genai_types.GenerateContentConfig(temperature=0, max_output_tokens=256)
        primary_model = model or settings.gemini_stt_model
        fallback_model = settings.gemini_fast_model

        models_to_try = [primary_model]
        if fallback_model and fallback_model != primary_model:
            models_to_try.append(fallback_model)

        last_timeout: Exception | None = None
        for stt_model in models_to_try:
            try:
                response = await asyncio.wait_for(
                    self._gemini.aio.models.generate_content(
                        model=stt_model,
                        contents=[
                            prompt,
                            _genai_types.Part.from_bytes(
                                data=wav_bytes,
                                mime_type="audio/wav",
                            ),
                        ],
                        config=config,
                    ),
                    timeout=request_timeout,
                )
            except asyncio.TimeoutError:
                last_timeout = TimeoutError(
                    f"Live transcription timed out after {request_timeout:g}s on {stt_model}"
                )
                logger.warning("%s", last_timeout)
                request_timeout = max(
                    request_timeout,
                    getattr(settings, "stt_retry_timeout_seconds", request_timeout),
                )
                continue
            except Exception:
                logger.exception("STT model %s failed", stt_model)
                continue

            text = (response.text or "").strip().strip('"')
            if text.casefold().replace("_", " ") in {
                "no speech",
                "no clear speech",
                "silence",
                "no_speech",
            }:
                return ""
            if text:
                logger.info("STT Gemini realtime (%s): %s", stt_model, text)
                return text
            logger.warning("STT model %s returned empty text", stt_model)

        if last_timeout:
            raise last_timeout
        return ""

    @staticmethod
    def _to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
        audio_int16 = (audio * 32767.0).astype(np.int16)
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        return wav_io.getvalue()


stt_engine = STTEngine()

__all__ = ["STTEngine", "stt_engine", "warm_whisper_model"]
