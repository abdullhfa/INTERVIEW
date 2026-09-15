
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

import numpy as np

from app.config import settings
from app.services.domain_terms import (
    WHISPER_DOMAIN_PROMPT,
    WHISPER_TECH_SECOND_PASS_PROMPT,
    canonicalize_display,
)

logger = logging.getLogger(__name__)

_model: Any = None
_model_lock = threading.Lock()
_warm_lock = asyncio.Lock()
_whisper_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper-stt")

_active: dict[str, Any] = {"model": None, "device": None, "compute_type": None}
_last_decode: dict[str, Any] = {}
_decode_log: list[dict[str, Any]] = []


def active_stt_info() -> dict[str, Any]:
    return dict(_active)


def last_decode_info() -> dict[str, Any]:
    return dict(_last_decode)


def clear_decode_log() -> None:
    _decode_log.clear()


def pop_decode_log() -> list[dict[str, Any]]:
    out = list(_decode_log)
    _decode_log.clear()
    return out


def _record_decode(info: dict[str, Any]) -> None:
    global _last_decode
    _last_decode = dict(info)
    _decode_log.append(dict(info))
    if len(_decode_log) > 500:
        del _decode_log[:-250]

_INTERVIEW_PROMPT = WHISPER_DOMAIN_PROMPT

_CUDA_DLL_PACKAGES = ("cublas", "cudnn", "cuda_nvrtc", "cuda_runtime")
_cuda_dlls_ready = False


def _ensure_cuda_dlls() -> None:
    """Make the pip-installed NVIDIA CUDA runtime DLLs visible to ctranslate2 (Windows)."""
    global _cuda_dlls_ready
    if _cuda_dlls_ready or not sys.platform.startswith("win"):
        _cuda_dlls_ready = True
        return
    added: list[str] = []
    for base in {Path(p) for p in sys.path if p and Path(p).name == "site-packages"}:
        nvidia_dir = base / "nvidia"
        if not nvidia_dir.is_dir():
            continue
        for pkg in _CUDA_DLL_PACKAGES:
            bin_dir = nvidia_dir / pkg / "bin"
            if bin_dir.is_dir():
                added.append(str(bin_dir))
                try:
                    os.add_dll_directory(str(bin_dir))
                except (AttributeError, OSError):
                    pass
    if added:
        os.environ["PATH"] = os.pathsep.join(added + [os.environ.get("PATH", "")])
        logger.info("CUDA DLL directories registered: %s", ", ".join(Path(p).parent.name for p in added))
    _cuda_dlls_ready = True


def _cuda_available() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception as exc:  # pragma: no cover - depends on machine
        logger.info("CUDA probe failed: %s", exc)
        return False


_WATER_PREFIX = re.compile(
    r"^(water|watt|watch)\s+(?:are\s+)?(.+)$",
    re.IGNORECASE,
)
_WATER_SKIP = {
    "bottle", "bottles", "cycle", "plant", "plants", "pipe", "pipes",
    "damage", "leak", "leaks", "supply",
}


def repair_live_transcript(text: str) -> str:
    """Fix common live-STT confusions without changing real words."""
    from app.services.technical_term_repair import repair_technical_terms

    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return ""
    match = _WATER_PREFIX.match(cleaned)
    if match:
        rest = match.group(2).strip()
        first = rest.split()[0].casefold() if rest else ""
        if rest and first not in _WATER_SKIP:
            repaired = f"what are {rest}"
            logger.info("STT repair: %r -> %r", cleaned, repaired)
            cleaned = repaired
    raw_stt = cleaned
    tech = repair_technical_terms(cleaned)
    if tech != cleaned:
        logger.info("STT technical repair: %r -> %r", cleaned, tech)
        cleaned = tech
    try:
        from app.services.tech_acronym_recovery import last_acronym_recovery

        acr = last_acronym_recovery()
        if acr is not None and (acr.replacements or acr.abstained):
            logger.info(
                "STT acronym path raw=%r recovered=%r matched_intent=%s",
                acr.raw_transcript or raw_stt,
                acr.recovered_transcript,
                acr.matched_intent or "-",
            )
    except Exception:
        pass
    try:
        from app.services.interview_phrase_recovery import last_phrase_recovery

        phr = last_phrase_recovery()
        if phr is not None and (phr.applied or phr.abstained):
            logger.info(
                "STT phrase path raw=%r recovered=%r type=%s matched_intent=%s",
                phr.raw_transcript or raw_stt,
                phr.recovered_transcript,
                phr.recovery_type or "-",
                phr.matched_intent or "-",
            )
    except Exception:
        pass
    try:
        from app.services.bank_guided_understanding import (
            apply_bank_guided_transcript,
            last_understanding,
        )

        # Bank-primary rewrite from the original STT hypothesis.
        guided = apply_bank_guided_transcript(raw_stt)
        if guided != cleaned:
            logger.info("STT bank-guided display: %r -> %r", cleaned, guided)
            cleaned = guided
        und = last_understanding()
        if und is not None:
            logger.info(
                "STT bank-guided raw=%r recovered=%r canonical=%r intent=%s conf=%.3f amb=%s",
                und.raw_transcript,
                und.recovered_transcript,
                und.canonical_question,
                und.intent_id or "-",
                und.confidence,
                und.ambiguous,
            )
    except Exception:
        pass
    repaired = canonicalize_display(cleaned)
    if repaired != cleaned:
        logger.info("STT domain repair: %r -> %r", cleaned, repaired)
    return repaired


def _build_model(model_size: str, device: str, compute_type: str) -> Any:
    from faster_whisper import WhisperModel

    started = time.perf_counter()
    try:
        # Prefer the local cache so a slow/blocked network never delays startup.
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=4,
            num_workers=1,
            local_files_only=True,
        )
    except Exception as cache_exc:
        logger.info("Whisper %s not cached locally (%s); downloading", model_size, cache_exc)
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=4,
            num_workers=1,
        )
    # A real decode proves the CUDA kernels/DLLs work (construction alone does not).
    silence = np.zeros(16000, dtype=np.float32)
    segments, _info = model.transcribe(silence, language="en", beam_size=1, vad_filter=False, without_timestamps=True)
    for _ in segments:
        pass
    logger.info(
        "Whisper STT ready (model=%s device=%s compute=%s load=%.1fs)",
        model_size, device, compute_type, time.perf_counter() - started,
    )
    return model


def _resolve_plan() -> list[tuple[str, str, str]]:
    """Ordered (model, device, compute_type) attempts."""
    device = (settings.whisper_device or "auto").lower()
    compute = (settings.whisper_compute_type or "auto").lower()
    primary = settings.whisper_model_size
    fallback = settings.whisper_fallback_model_size or "base"

    def _compute_for(dev: str) -> str:
        if compute != "auto":
            return compute
        return "int8_float16" if dev == "cuda" else "int8"

    plan: list[tuple[str, str, str]] = []
    if device in ("auto", "cuda"):
        _ensure_cuda_dlls()
        if _cuda_available():
            plan.append((primary, "cuda", _compute_for("cuda")))
        elif device == "cuda":
            logger.warning("whisper_device=cuda requested but no CUDA device is visible; using CPU")
    cpu_model = primary if device == "cpu" else fallback
    plan.append((cpu_model, "cpu", _compute_for("cpu")))
    if cpu_model != fallback:
        plan.append((fallback, "cpu", "int8"))
    return plan


def _load_model() -> Any:
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        last_exc: Optional[Exception] = None
        for model_size, device, compute_type in _resolve_plan():
            try:
                _model = _build_model(model_size, device, compute_type)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Whisper load failed (model=%s device=%s compute=%s): %s",
                    model_size, device, compute_type, exc,
                )
                continue
            _active.update({"model": model_size, "device": device, "compute_type": compute_type})
            return _model
        raise RuntimeError(f"Whisper STT could not be loaded: {last_exc}")


def transcribe_whisper(
    audio: np.ndarray,
    sample_rate: int = 16000,
    *,
    beam_size: Optional[int] = None,
    initial_prompt: Optional[str] = None,
    accurate: bool = False,
    apply_repair: bool = True,
) -> str:
    """Transcribe mono float32 audio in-process.

    accurate=True: slower second-pass decode (larger beam + tech prompt).
    Use only for short/weak utterances so live latency stays low.
    """
    if len(audio) == 0:
        return ""

    audio = np.asarray(audio, dtype=np.float32)
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    audio = np.clip(audio, -1.0, 1.0)

    if sample_rate != 16000:
        ratio = sample_rate / 16000
        if ratio > 1:
            audio = audio[:: int(ratio)]

    model = _load_model()
    # Interview questions are English-only; force `en` on every pass (esp. second-pass).
    language = (settings.whisper_language or "").strip() or "en"
    if language.lower() in {"auto", "none"}:
        language = "en"
    default_beam = max(1, (settings.whisper_beam_size or 1))
    if accurate:
        # Limited second pass (Latency-cut): same beam family as first, single temperature.
        # Multi-temp + wider beam was ~2× wall-clock for marginal STT fixes.
        beam = max(1, (beam_size or default_beam))
        beam = min(beam, max(default_beam, 4))
        prompt = initial_prompt if initial_prompt is not None else WHISPER_TECH_SECOND_PASS_PROMPT
        patience = 1.0
        temperatures: Any = 0.0
        pass_name = "accurate"
    else:
        beam = max(1, (beam_size or default_beam))
        prompt = initial_prompt if initial_prompt is not None else _INTERVIEW_PROMPT
        patience = 1.0
        temperatures = 0.0
        pass_name = "first"
    # best_of=beam forces a costly multi-candidate search; keep best_of=1 for live latency.
    best_of = 1
    started = time.perf_counter()
    # Live audio is already VAD-segmented; skipping Whisper VAD saves ~0.5-1.5s.
    segments, _info = model.transcribe(
        audio,
        language=language,
        beam_size=beam,
        best_of=best_of,
        patience=patience,
        temperature=temperatures,
        vad_filter=False,
        condition_on_previous_text=False,
        without_timestamps=True,
        initial_prompt=prompt,
        # Hallucination guards for short, noisy accented clips.
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.6,
    )
    text = " ".join(part.text.strip() for part in segments if part.text.strip())
    repaired = repair_live_transcript(text) if apply_repair else " ".join(text.split())
    whisper_ms = (time.perf_counter() - started) * 1000
    audio_sec = float(len(audio) / 16000.0)
    _record_decode(
        {
            "pass": pass_name,
            "accurate": (accurate),
            "beam": beam,
            "best_of": best_of,
            "audio_sec": round(audio_sec, 3),
            "whisper_ms": round(whisper_ms, 1),
            "rtf": round(whisper_ms / 1000.0 / audio_sec, 3) if audio_sec > 0 else None,
            "device": _active.get("device"),
            "model": _active.get("model"),
            "compute_type": _active.get("compute_type"),
        }
    )
    logger.debug(
        "Whisper %.0fms accurate=%s beam=%s best_of=%s (%.1fs audio) -> %r",
        whisper_ms,
        accurate,
        beam,
        best_of,
        audio_sec,
        repaired,
    )
    return repaired


async def transcribe_whisper_async(
    audio: np.ndarray,
    sample_rate: int = 16000,
    *,
    beam_size: Optional[int] = None,
    initial_prompt: Optional[str] = None,
    accurate: bool = False,
    apply_repair: bool = True,
) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _whisper_executor,
        lambda: transcribe_whisper(
            audio,
            sample_rate,
            beam_size=beam_size,
            initial_prompt=initial_prompt,
            accurate=accurate,
            apply_repair=apply_repair,
        ),
    )


async def warm_whisper_model() -> None:
    """Load Whisper weights during startup so live STT is fast."""
    if not settings.whisper_stt_enabled:
        return

    async with _warm_lock:
        if _model is not None:
            return
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(_whisper_executor, _load_model)
        except Exception as exc:
            logger.warning("Whisper warm-up skipped: %s", exc)
