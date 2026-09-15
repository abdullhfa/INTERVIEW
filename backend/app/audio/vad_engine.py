"""
AI Interview Coach - VAD Engine

Silero VAD wrapper for real-time voice activity detection.
CPU-efficient, runs on ONNX Runtime. Supports adaptive end-of-turn detection.
"""

from __future__ import annotations
import logging
import time
import numpy as np
from typing import Optional, Callable
from enum import Enum
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)


class SpeechState(str, Enum):
    SILENCE = "SILENCE"
    SPEECH_DETECTED = "SPEECH_DETECTED"
    SPEECH_CONTINUING = "SPEECH_CONTINUING"
    UTTERANCE_FINALIZED = "UTTERANCE_FINALIZED"


@dataclass
class VADResult:
    """Result of VAD processing for a single audio chunk."""
    state: SpeechState
    probability: float
    is_speech: bool
    duration_ms: float = 0  # Duration of current speech/silence segment
    truncated_by_max: bool = False  # True when max-utterance duration forced end


class VADEngine:
    """
    Silero VAD wrapper with adaptive end-of-turn detection.

    Short pause inside sentence: continue listening.
    Clear end of speech: finalize utterance.
    """

    def __init__(
        self,
        threshold: Optional[float] = None,
        min_speech_ms: Optional[int] = None,
        min_silence_ms: Optional[int] = None,
        sample_rate: Optional[int] = None,
    ):
        self._threshold = threshold if threshold is not None else getattr(settings, 'vad_threshold', 0.5)
        self._min_speech_ms = (
            min_speech_ms
            if min_speech_ms is not None
            else getattr(settings, "vad_min_speech_ms", 250)
        )
        self._min_silence_ms = (
            min_silence_ms
            if min_silence_ms is not None
            else getattr(settings, "vad_min_silence_ms", 600)
        )
        self._sample_rate = sample_rate if sample_rate is not None else getattr(settings, 'audio_sample_rate', 16000)
        self._max_speech_ms = 30000  # Per-segment cap; router may continue/merge
        self._segment_index = 0

        self._model = None
        self._is_speaking = False
        self._speech_start_time: Optional[float] = None
        self._silence_start_time: Optional[float] = None
        self._speech_duration_ms: float = 0
        self._silence_duration_ms: float = 0

    def initialize(self):
        """Load the Silero VAD model."""
        try:
            from silero_vad import load_silero_vad
            self._model = load_silero_vad(onnx=True)
            logger.info("Silero VAD initialized (ONNX)")
        except ImportError:
            logger.warning("silero_vad not available, using threshold-based VAD")
            self._model = None

    def reset(self):
        """Reset VAD state between sessions or speakers."""
        self._is_speaking = False
        self._speech_start_time = None
        self._silence_start_time = None
        self._speech_duration_ms = 0
        self._silence_duration_ms = 0
        if hasattr(self, "_noise_floor"):
            delattr(self, "_noise_floor")

        if self._model is not None:
            try:
                self._model.reset_states()
            except Exception:
                pass

    def process_chunk(self, audio_chunk: np.ndarray) -> VADResult:
        """
        Process a single audio chunk and return VAD result.

        Args:
            audio_chunk: numpy array of float32 audio samples, 16kHz mono

        Returns:
            VADResult with speech state and probability
        """
        import torch

        current_time = time.time()

        # Get speech probability
        if self._model is not None:
            try:
                tensor = torch.from_numpy(audio_chunk).float()
                probability = self._model(tensor, self._sample_rate).item()
            except Exception as e:
                logger.error(f"VAD inference error: {e}")
                probability = self._energy_based_vad(audio_chunk)
        else:
            probability = self._energy_based_vad(audio_chunk)

        rms = float(np.sqrt(np.mean(audio_chunk**2))) if len(audio_chunk) > 0 else 0.0

        is_speech = probability >= self._threshold

        # Avoid spamming VAD_CONTINUE in debug, keep basic diagnostics
        if not self._is_speaking:
            logger.debug(
                f"[VAD DIAGNOSTICS] "
                f"rms={rms:.4f} "
                f"vad_score={probability:.4f} "
                f"is_speech={is_speech} "
                f"state=SILENCE"
            )

        # State machine logic
        if is_speech:
            if not self._is_speaking:
                # Potential speech start
                if self._speech_start_time is None:
                    self._speech_start_time = current_time

                elapsed = (current_time - self._speech_start_time) * 1000

                if elapsed >= self._min_speech_ms:
                    # Confirmed speech start
                    self._is_speaking = True
                    self._silence_start_time = None
                    self._silence_duration_ms = 0
                    logger.info(f"VAD_START detected (rms={rms:.4f}, prob={probability:.4f})")
                    return VADResult(
                        state=SpeechState.SPEECH_DETECTED,
                        probability=probability,
                        is_speech=True,
                        duration_ms=elapsed,
                    )
                else:
                    # Speech is present but not confirmed yet. Expose that fact
                    # so the router can retain the confirmation-window audio.
                    return VADResult(
                        state=SpeechState.SILENCE,
                        probability=probability,
                        is_speech=True,
                    )
            else:
                # Continuing speech
                self._silence_start_time = None
                self._silence_duration_ms = 0
                speech_started = self._speech_start_time
                if speech_started is None:
                    speech_started = current_time
                    self._speech_start_time = speech_started
                duration = (current_time - speech_started) * 1000

                # Enforce per-segment max duration (router may continue + merge).
                if duration >= self._max_speech_ms:
                    logger.warning(f"VAD_END forced by MAX_UTTERANCE_DURATION ({duration:.1f}ms)")
                    speech_duration = duration
                    self._is_speaking = False
                    self._speech_start_time = None
                    self._silence_start_time = None
                    self._segment_index += 1
                    return VADResult(
                        state=SpeechState.UTTERANCE_FINALIZED,
                        probability=probability,
                        is_speech=False,
                        duration_ms=speech_duration,
                        truncated_by_max=True,
                    )

                return VADResult(
                    state=SpeechState.SPEECH_CONTINUING,
                    probability=probability,
                    is_speech=True,
                    duration_ms=duration,
                )
        else:
            # Silence
            self._speech_start_time = None if not self._is_speaking else self._speech_start_time

            if self._is_speaking:
                # Was speaking, now silence
                if self._silence_start_time is None:
                    self._silence_start_time = current_time

                silence_ms = (current_time - self._silence_start_time) * 1000

                if silence_ms >= self._min_silence_ms:
                    # Confirmed end of speech
                    speech_duration = (
                        (self._silence_start_time - self._speech_start_time) * 1000
                        if self._speech_start_time
                        else 0
                    )
                    logger.info(f"VAD_END detected after {speech_duration:.1f}ms speech and {silence_ms:.1f}ms silence")
                    self._is_speaking = False
                    self._speech_start_time = None
                    self._silence_start_time = None
                    return VADResult(
                        state=SpeechState.UTTERANCE_FINALIZED,
                        probability=probability,
                        is_speech=False,
                        duration_ms=speech_duration,
                    )
                else:
                    # Brief pause — keep listening
                    return VADResult(
                        state=SpeechState.SPEECH_CONTINUING,
                        probability=probability,
                        is_speech=True,
                        duration_ms=silence_ms,
                    )
            else:
                # Pure silence
                if not self._is_speaking:
                    self._speech_start_time = None
                return VADResult(
                    state=SpeechState.SILENCE,
                    probability=probability,
                    is_speech=False,
                )

    def _energy_based_vad(self, audio_chunk: np.ndarray) -> float:
        """Fallback energy-based VAD with adaptive noise floor."""
        if len(audio_chunk) == 0:
            return 0.0
            
        # Add epsilon to prevent division by zero and handle very low amplitudes
        eps = 1e-6
        energy = float(np.sqrt(np.mean(audio_chunk ** 2))) + eps
        
        if not hasattr(self, "_noise_floor"):
            # Initialize to a very low value so the first loud chunk is recognized as speech
            self._noise_floor = eps
            
        # Update noise floor (slowly upwards, fast downwards)
        if energy < self._noise_floor:
            # Drop noise floor relatively quickly if energy drops
            self._noise_floor = energy * 0.2 + self._noise_floor * 0.8
        else:
            # Raise noise floor very slowly so speech doesn't immediately raise it
            self._noise_floor = self._noise_floor * 0.995 + energy * 0.005
            
        self._noise_floor = max(eps, self._noise_floor)
        
        snr = energy / self._noise_floor
        
        # Mapping SNR to probability [0..1]
        # Adjusted scaling to be more sensitive to lower amplitudes
        score = (snr - 1.5) / 2.0
        return float(np.clip(score, 0.0, 1.0))

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
