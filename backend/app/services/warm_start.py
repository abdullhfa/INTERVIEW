"""
Warm-start orchestration (Phase 11).

Production interview mode must not pay model initialisation on the first real
question. This module loads and *exercises* every component once, then flips
`SYSTEM_WARM` to True. Nothing here changes any matching / intent behaviour —
it only moves one-off initialisation cost off the live path.

Steps (in order):
    1. Whisper weights
    2. question bank + alias embedding matrix (loads the embedding model)
    3. semantic intent index (profiles + profile-blob matrix)
    4. inverted lexical index (built during bank load)
    5. one tiny Whisper decode  — warms CUDA kernels / graph
    6. one semantic embedding   — warms the ONNX session
    7. audio loopback probe     — optional, reported not enforced
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_STATE: dict[str, Any] = {
    "system_warm": False,
    "started_at": None,
    "finished_at": None,
    "duration_ms": None,
    "steps": {},
    "errors": {},
}


def system_warm_state() -> dict[str, Any]:
    """Snapshot of warm-up progress. `system_warm` is the READY flag."""
    return {**_STATE, "steps": dict(_STATE["steps"]), "errors": dict(_STATE["errors"])}


def is_system_warm() -> bool:
    return bool(_STATE["system_warm"])


def _step(name: str, fn) -> None:
    started = time.perf_counter()
    try:
        fn()
        _STATE["steps"][name] = round((time.perf_counter() - started) * 1000, 1)
    except Exception as exc:  # pragma: no cover - defensive
        _STATE["steps"][name] = round((time.perf_counter() - started) * 1000, 1)
        _STATE["errors"][name] = f"{type(exc).__name__}: {exc}"
        logger.warning("Warm-start step %s failed: %s", name, exc)


def warm_system_blocking(*, probe_audio: bool = False) -> dict[str, Any]:
    """Synchronous warm-up. Safe to call twice; the second call is a no-op."""
    if _STATE["system_warm"]:
        return system_warm_state()
    _STATE["started_at"] = time.time()
    t0 = time.perf_counter()

    from app.services.question_bank import question_bank

    _step("question_bank_load", lambda: question_bank.load())
    _step("question_bank_warm", lambda: question_bank.warm())

    def _semantic_index() -> None:
        from app.services.semantic_intent_index import semantic_intent_index

        semantic_intent_index.warm()

    _step("semantic_intent_index", _semantic_index)

    def _warm_embedding() -> None:
        # One real embedding so the ONNX session is compiled before a live question.
        question_bank._embed(["warm up embedding for the interview assistant"])  # noqa: SLF001

    _step("embedding_probe", _warm_embedding)

    def _warm_decode() -> None:
        import glob
        import os
        import wave

        import numpy as np

        from app.audio.whisper_stt import transcribe_whisper

        # Near-silence trips `no_speech_threshold` and returns before the decoder
        # loop runs, so the first REAL question still paid full kernel init
        # (measured: 14.3 s cold vs 2.6 s warm on the same machine). Warm with a
        # real dev-pack clip instead — never a holdout pack, so nothing about the
        # unseen evaluation is observed here.
        repo_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        clips = sorted(
            glob.glob(
                os.path.join(
                    repo_root, "frontend", "public", "voice-drill",
                    "compound-dev", "audio", "*.wav",
                )
            )
        )
        sample = None
        if clips:
            try:
                with wave.open(clips[0], "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    rate = wf.getframerate()
                if rate == 16000:
                    sample = np.frombuffer(frames, dtype=np.int16).astype("float32") / 32768.0
            except Exception as exc:
                logger.debug("Warm-up clip unreadable (%s); using synthetic audio", exc)
        if sample is None:
            # Fallback: the previous synthetic probe. Better than skipping warm-up.
            sample = (np.random.default_rng(0).standard_normal(8000) * 1e-4).astype("float32")
        transcribe_whisper(sample, 16000)

    _step("whisper_decode_probe", _warm_decode)

    if probe_audio:
        def _probe_loopback() -> None:
            from app.audio.capture_manager import capture_manager  # noqa: F401

            # Presence check only — never opens a stream during warm-up.
            _STATE["steps"]["audio_loopback_available"] = True

        _step("audio_loopback_probe", _probe_loopback)

    _STATE["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    _STATE["finished_at"] = time.time()
    _STATE["system_warm"] = True
    logger.info(
        "SYSTEM_WARM=True in %.0f ms (steps=%s errors=%s)",
        _STATE["duration_ms"],
        _STATE["steps"],
        _STATE["errors"] or "none",
    )
    return system_warm_state()


async def warm_system(*, probe_audio: bool = False) -> dict[str, Any]:
    """Run warm-up in a worker thread so the event loop stays responsive."""
    from app.audio.whisper_stt import warm_whisper_model

    try:
        await warm_whisper_model()
    except Exception as exc:  # pragma: no cover - defensive
        _STATE["errors"]["whisper_model"] = f"{type(exc).__name__}: {exc}"
        logger.warning("Whisper warm-up failed: %s", exc)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: warm_system_blocking(probe_audio=probe_audio)
    )
