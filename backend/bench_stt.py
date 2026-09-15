"""Benchmark live STT backends with a short synthetic tone (smoke) and optional WAV path."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import numpy as np

from app.audio.stt_engine import stt_engine
from app.audio.whisper_stt import warm_whisper_model
from app.config import settings


async def bench_array(label: str, audio: np.ndarray, sample_rate: int = 16000) -> None:
    start = time.perf_counter()
    text = await stt_engine.transcribe_realtime(audio, sample_rate=sample_rate)
    elapsed = (time.perf_counter() - start) * 1000
    print(f"{label}: {elapsed:.0f}ms text={text!r}")


async def main() -> None:
    print("whisper_enabled", settings.whisper_stt_enabled)
    print("whisper_model", settings.whisper_model_size)

    warm_start = time.perf_counter()
    await warm_whisper_model()
    print(f"whisper_warm_ms={((time.perf_counter() - warm_start) * 1000):.0f}")

    wav_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if wav_path and wav_path.exists():
        import wave

        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            sample_rate = wf.getframerate()
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        await bench_array(f"file:{wav_path.name}", audio, sample_rate)
        return

    # Smoke: near-silent audio should return quickly without 18s Google hang.
    silence = np.zeros(16000 * 2, dtype=np.float32)
    await bench_array("silence_2s", silence)


if __name__ == "__main__":
    asyncio.run(main())
