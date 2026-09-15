"""
AI Interview Coach - Speaker Router

Routes audio from Channel A (interviewer) and Channel B (candidate)
to appropriate processing pipelines. Prevents answer generation
while the candidate is speaking.

Interviewer utterance audio sent to STT is always:
  pre-roll + detected speech + post-roll
VAD only decides when speech starts/ends — it does not crop the onset.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

import numpy as np

from app.audio.vad_engine import VADEngine, SpeechState, VADResult
from app.config import settings

logger = logging.getLogger(__name__)


class ActiveSpeaker(str, Enum):
    NONE = "NONE"
    INTERVIEWER = "INTERVIEWER"
    CANDIDATE = "CANDIDATE"
    BOTH = "BOTH"  # Overlap detected


class SpeakerEvent(str, Enum):
    INTERVIEWER_STARTED = "INTERVIEWER_STARTED"
    INTERVIEWER_STOPPED = "INTERVIEWER_STOPPED"
    CANDIDATE_STARTED = "CANDIDATE_STARTED"
    CANDIDATE_STOPPED = "CANDIDATE_STOPPED"


@dataclass
class OnsetDiagnostics:
    """Timing breadcrumbs for capture → VAD → buffer → STT diagnosis."""
    pre_roll_ms: int = 0
    post_roll_ms: int = 0
    capture_start_t: Optional[float] = None
    vad_speech_start_t: Optional[float] = None
    actual_buffer_start_t: Optional[float] = None
    first_non_silent_offset_ms: float = 0.0
    stt_start_t: Optional[float] = None
    pre_roll_samples_used: int = 0

    def as_dict(self) -> dict:
        def rel_ms(t: Optional[float]) -> Optional[float]:
            if t is None or self.capture_start_t is None:
                return None
            return round((t - self.capture_start_t) * 1000.0, 1)

        return {
            "pre_roll_ms": self.pre_roll_ms,
            "post_roll_ms": self.post_roll_ms,
            "pre_roll_samples_used": self.pre_roll_samples_used,
            "capture_start_t": self.capture_start_t,
            "vad_speech_start_ms": rel_ms(self.vad_speech_start_t),
            "actual_buffer_start_ms": rel_ms(self.actual_buffer_start_t),
            "first_non_silent_offset_ms": round(self.first_non_silent_offset_ms, 1),
            "stt_start_ms": rel_ms(self.stt_start_t),
            "capture_to_vad_ms": rel_ms(self.vad_speech_start_t),
            "vad_to_buffer_lead_ms": (
                round(
                    (self.vad_speech_start_t - self.actual_buffer_start_t) * 1000.0,
                    1,
                )
                if self.vad_speech_start_t is not None and self.actual_buffer_start_t is not None
                else None
            ),
        }


def _first_nonsilent_offset_ms(
    audio: np.ndarray,
    *,
    sample_rate: int = 16000,
    thresh: float = 0.012,
) -> float:
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    if x.size == 0:
        return 0.0
    # 10ms frames
    frame = max(1, int(sample_rate * 0.01))
    for i in range(0, len(x), frame):
        chunk = x[i : i + frame]
        if float(np.sqrt(np.mean(np.square(chunk)))) >= thresh:
            return (i / float(sample_rate)) * 1000.0
    return (len(x) / float(sample_rate)) * 1000.0


class SpeakerRouter:
    """
    Routes audio from two independent channels to their respective pipelines.
    Does NOT rely on diarization — uses hardware-level channel separation.
    """

    def __init__(self, *, pre_roll_ms: Optional[int] = None, post_roll_ms: Optional[int] = None):
        self._interviewer_vad = VADEngine()
        self._candidate_vad = VADEngine()
        self._active_speaker = ActiveSpeaker.NONE

        self._interviewer_buffer: list[np.ndarray] = []
        self._candidate_buffer: list[np.ndarray] = []

        self._sample_rate = int(getattr(settings, "audio_sample_rate", 16000))
        self._pre_roll_ms = int(
            pre_roll_ms
            if pre_roll_ms is not None
            else getattr(settings, "vad_pre_roll_ms", 800)
        )
        self._post_roll_ms = int(
            post_roll_ms
            if post_roll_ms is not None
            else getattr(settings, "vad_post_roll_ms", 250)
        )
        self._interviewer_pre_roll: deque[np.ndarray] = deque()
        self._interviewer_pre_roll_samples = 0
        self._pre_roll_max_samples = int(self._sample_rate * (self._pre_roll_ms / 1000.0))
        self._post_roll_samples = int(self._sample_rate * (self._post_roll_ms / 1000.0))
        self._post_roll_remaining = 0
        self._post_roll_active = False
        self._utterance_active = False
        # Long-utterance continuation: keep segments when max-duration fires.
        self._pending_segments: list[np.ndarray] = []
        self._awaiting_continuation = False
        self._continuation_deadline: Optional[float] = None
        self._continuation_gap_s = 1.8
        self._max_segments = 3
        self.last_segment_count = 1
        self.last_truncated_by_max = False
        self._utterance_was_truncated = False

        self._onset = OnsetDiagnostics(
            pre_roll_ms=self._pre_roll_ms,
            post_roll_ms=self._post_roll_ms,
        )
        self._last_onset: Optional[OnsetDiagnostics] = None

        self._on_speaker_event: Optional[Callable] = None
        self._on_interviewer_utterance: Optional[Callable] = None
        self._on_candidate_utterance: Optional[Callable] = None

    def initialize(self, *, enable_candidate: bool = True):
        """Initialize VAD engines."""
        interviewer_silence = getattr(
            settings, "vad_interviewer_min_silence_ms", 900
        )
        # Fast speech_start confirm (~1–2 frames). Onset audio comes from pre-roll.
        min_speech = int(getattr(settings, "vad_min_speech_ms", 64))
        self._interviewer_vad = VADEngine(
            min_silence_ms=interviewer_silence,
            min_speech_ms=min_speech,
        )
        self._interviewer_vad.initialize()
        if enable_candidate:
            self._candidate_vad.initialize()
        self._sample_rate = int(getattr(settings, "audio_sample_rate", 16000))
        self._pre_roll_max_samples = int(self._sample_rate * (self._pre_roll_ms / 1000.0))
        self._post_roll_samples = int(self._sample_rate * (self._post_roll_ms / 1000.0))
        logger.info(
            "Speaker router initialized (candidate_channel=%s interviewer_silence_ms=%s "
            "min_speech_ms=%s pre_roll_ms=%s post_roll_ms=%s)",
            "enabled" if enable_candidate else "disabled",
            interviewer_silence,
            min_speech,
            self._pre_roll_ms,
            self._post_roll_ms,
        )

    def set_pre_roll_ms(self, pre_roll_ms: int) -> None:
        """Update circular pre-roll length (used by onset A/B)."""
        self._pre_roll_ms = max(0, (pre_roll_ms))
        self._pre_roll_max_samples = int(self._sample_rate * (self._pre_roll_ms / 1000.0))
        self._onset.pre_roll_ms = self._pre_roll_ms
        # Trim existing buffer if needed.
        while (
            self._interviewer_pre_roll
            and self._interviewer_pre_roll_samples > self._pre_roll_max_samples
        ):
            dropped = self._interviewer_pre_roll.popleft()
            self._interviewer_pre_roll_samples -= len(dropped)

    def set_callbacks(
        self,
        on_speaker_event: Optional[Callable] = None,
        on_interviewer_utterance: Optional[Callable] = None,
        on_candidate_utterance: Optional[Callable] = None,
    ):
        """Set event callbacks."""
        self._on_speaker_event = on_speaker_event
        self._on_interviewer_utterance = on_interviewer_utterance
        self._on_candidate_utterance = on_candidate_utterance

    def mark_capture_start(self) -> None:
        """Call when a new E2E clip / turn begins."""
        self._onset = OnsetDiagnostics(
            pre_roll_ms=self._pre_roll_ms,
            post_roll_ms=self._post_roll_ms,
            capture_start_t=time.perf_counter(),
        )

    def mark_stt_start(self) -> OnsetDiagnostics:
        if self._last_onset is not None:
            self._last_onset.stt_start_t = time.perf_counter()
            return self._last_onset
        self._onset.stt_start_t = time.perf_counter()
        return self._onset

    @property
    def last_onset(self) -> Optional[OnsetDiagnostics]:
        return self._last_onset

    def _push_pre_roll(self, audio_chunk: np.ndarray) -> None:
        self._interviewer_pre_roll.append(np.asarray(audio_chunk, dtype=np.float32))
        self._interviewer_pre_roll_samples += len(audio_chunk)
        while (
            self._interviewer_pre_roll
            and self._interviewer_pre_roll_samples > self._pre_roll_max_samples
        ):
            dropped = self._interviewer_pre_roll.popleft()
            self._interviewer_pre_roll_samples -= len(dropped)

    def _consume_pre_roll(self) -> list[np.ndarray]:
        chunks = list(self._interviewer_pre_roll)
        samples = self._interviewer_pre_roll_samples
        self._interviewer_pre_roll.clear()
        self._interviewer_pre_roll_samples = 0
        self._onset.pre_roll_samples_used = (samples)
        # Buffer starts ~pre_roll_ms before VAD speech_start.
        if self._onset.vad_speech_start_t is not None:
            self._onset.actual_buffer_start_t = (
                self._onset.vad_speech_start_t - (samples / float(self._sample_rate))
            )
        return chunks

    def _flush_interviewer(self, duration_ms: float) -> None:
        segments = list(self._pending_segments)
        if self._interviewer_buffer:
            segments.append(np.concatenate(self._interviewer_buffer))
        self._pending_segments = []
        self._awaiting_continuation = False
        self._continuation_deadline = None
        self.last_segment_count = max(1, len(segments))
        # Sticky for E2E/observability: did this utterance include a max-duration cut?
        self.last_truncated_by_max = self._utterance_was_truncated
        if segments and self._on_interviewer_utterance:
            full_audio = np.concatenate(segments) if len(segments) > 1 else segments[0]
            # duration from merged audio
            merged_ms = (len(full_audio) / float(self._sample_rate)) * 1000.0
            use_ms = max(float(duration_ms), merged_ms)
            if len(full_audio) > 0 and use_ms >= 300:
                self._onset.first_non_silent_offset_ms = _first_nonsilent_offset_ms(
                    full_audio, sample_rate=self._sample_rate
                )
                self._last_onset = self._onset
                logger.info(
                    "UTTERANCE_FLUSH (Interviewer) duration=%.1fms segments=%s "
                    "pre_roll=%sms post_roll=%sms first_nonsilent=%.0fms truncated=%s",
                    use_ms,
                    self.last_segment_count,
                    self._pre_roll_ms,
                    self._post_roll_ms,
                    self._onset.first_non_silent_offset_ms,
                    self.last_truncated_by_max,
                )
                self._on_interviewer_utterance(full_audio, use_ms)
            else:
                logger.debug("Ignored short interviewer utterance (%.1fms)", use_ms)
        self._interviewer_buffer = []
        self._post_roll_active = False
        self._post_roll_remaining = 0
        self._utterance_active = False
        self._utterance_was_truncated = False
        self._interviewer_pre_roll.clear()
        self._interviewer_pre_roll_samples = 0
        self._update_speaker(ActiveSpeaker.NONE, SpeakerEvent.INTERVIEWER_STOPPED)

    def _stash_truncated_segment(self) -> None:
        """Keep audio after max-duration cut; wait briefly for continuation."""
        if self._interviewer_buffer:
            seg = np.concatenate(self._interviewer_buffer)
            if len(seg) > 0:
                self._pending_segments.append(seg)
        self._interviewer_buffer = []
        self._post_roll_active = False
        self._post_roll_remaining = 0
        self._utterance_active = False
        self._awaiting_continuation = True
        self._continuation_deadline = time.perf_counter() + self._continuation_gap_s
        self.last_truncated_by_max = True
        self._utterance_was_truncated = True
        logger.info(
            "UTTERANCE_SEGMENT_STASH pending=%s awaiting_continuation=%.1fs",
            len(self._pending_segments),
            self._continuation_gap_s,
        )

    def process_interviewer_audio(self, audio_chunk: np.ndarray) -> VADResult:
        """Process a chunk of interviewer (loopback) audio."""
        chunk = np.asarray(audio_chunk, dtype=np.float32)

        # Continuation timeout: deliver stashed segments if speech did not resume.
        if (
            self._awaiting_continuation
            and self._continuation_deadline is not None
            and time.perf_counter() >= self._continuation_deadline
            and not self._utterance_active
        ):
            logger.info("UTTERANCE_CONTINUATION_TIMEOUT flushing %s segments", len(self._pending_segments))
            self._flush_interviewer(
                (sum(len(s) for s in self._pending_segments) / float(self._sample_rate)) * 1000.0
            )

        result = self._interviewer_vad.process_chunk(chunk)

        # Finish post-roll collection after VAD end-of-speech.
        if self._post_roll_active:
            self._interviewer_buffer.append(chunk)
            self._post_roll_remaining -= len(chunk)
            if self._post_roll_remaining <= 0:
                # duration ≈ buffered audio without relying on VAD clock alone
                duration_ms = (sum(len(c) for c in self._interviewer_buffer) / self._sample_rate) * 1000.0
                if getattr(result, "truncated_by_max", False) or self.last_truncated_by_max:
                    # Should not normally hit post-roll on truncate; stash instead.
                    self._stash_truncated_segment()
                else:
                    self._flush_interviewer(duration_ms)
            return result

        if result.state == SpeechState.SPEECH_DETECTED:
            logger.info("UTTERANCE_START (Interviewer)")
            self._onset.vad_speech_start_t = time.perf_counter()
            if self._onset.capture_start_t is None:
                self._onset.capture_start_t = self._onset.vad_speech_start_t
            self._update_speaker(ActiveSpeaker.INTERVIEWER, SpeakerEvent.INTERVIEWER_STARTED)
            # Resuming after max-duration segment: keep pending, start next buffer.
            if self._awaiting_continuation:
                self._awaiting_continuation = False
                self._continuation_deadline = None
                self._interviewer_buffer = self._consume_pre_roll()
                self._interviewer_buffer.append(chunk)
            else:
                self._interviewer_buffer = self._consume_pre_roll()
                self._interviewer_buffer.append(chunk)
            self._utterance_active = True
            self._post_roll_active = False

        elif result.state == SpeechState.SPEECH_CONTINUING:
            if self._utterance_active:
                self._interviewer_buffer.append(chunk)
            else:
                # Unconfirmed / brief energy: keep in pre-roll only.
                self._push_pre_roll(chunk)

        elif result.state == SpeechState.UTTERANCE_FINALIZED:
            if self._utterance_active:
                self._interviewer_buffer.append(chunk)
                truncated = bool(getattr(result, "truncated_by_max", False))
                if truncated and len(self._pending_segments) + 1 < self._max_segments:
                    # Soft boundary: stash and listen for continuation (do not drop tail).
                    self._stash_truncated_segment()
                elif self._post_roll_samples > 0 and not truncated:
                    self._post_roll_active = True
                    self._post_roll_remaining = self._post_roll_samples
                else:
                    self._flush_interviewer(float(result.duration_ms))
            else:
                self._push_pre_roll(chunk)

        elif result.state == SpeechState.SILENCE:
            # Always refresh circular pre-roll while idle.
            # Do NOT start the utterance buffer from VAD confirmation frames —
            # those frames already live in the pre-roll and would duplicate.
            self._push_pre_roll(chunk)
            if result.is_speech:
                # Confirmation window: keep rolling into pre-roll only.
                pass

        return result

    def process_candidate_audio(self, audio_chunk: np.ndarray) -> VADResult:
        """Process a chunk of candidate (microphone) audio."""
        result = self._candidate_vad.process_chunk(audio_chunk)

        if result.state == SpeechState.SPEECH_DETECTED:
            self._update_speaker(ActiveSpeaker.CANDIDATE, SpeakerEvent.CANDIDATE_STARTED)
            self._candidate_buffer.append(audio_chunk)

        elif result.state == SpeechState.SPEECH_CONTINUING:
            self._candidate_buffer.append(audio_chunk)

        elif result.state == SpeechState.UTTERANCE_FINALIZED:
            self._candidate_buffer.append(audio_chunk)
            if self._candidate_buffer and self._on_candidate_utterance:
                full_audio = np.concatenate(self._candidate_buffer)
                if len(full_audio) > 0 and result.duration_ms >= 300:
                    self._on_candidate_utterance(full_audio, result.duration_ms)
                else:
                    logger.debug("Ignored short candidate utterance (%.1fms)", result.duration_ms)
            self._candidate_buffer = []
            self._update_speaker(ActiveSpeaker.NONE, SpeakerEvent.CANDIDATE_STOPPED)

        elif result.state == SpeechState.SILENCE:
            if result.is_speech:
                self._candidate_buffer.append(audio_chunk)
            elif not self._candidate_vad.is_speaking:
                self._candidate_buffer = []

        return result

    def _update_speaker(self, speaker: ActiveSpeaker, event: SpeakerEvent):
        """Update the active speaker state and emit events."""
        old = self._active_speaker

        if event == SpeakerEvent.INTERVIEWER_STARTED:
            if self._active_speaker == ActiveSpeaker.CANDIDATE:
                self._active_speaker = ActiveSpeaker.BOTH
            else:
                self._active_speaker = ActiveSpeaker.INTERVIEWER

        elif event == SpeakerEvent.INTERVIEWER_STOPPED:
            if self._active_speaker == ActiveSpeaker.BOTH:
                self._active_speaker = ActiveSpeaker.CANDIDATE
            else:
                self._active_speaker = ActiveSpeaker.NONE

        elif event == SpeakerEvent.CANDIDATE_STARTED:
            if self._active_speaker == ActiveSpeaker.INTERVIEWER:
                self._active_speaker = ActiveSpeaker.BOTH
            else:
                self._active_speaker = ActiveSpeaker.CANDIDATE

        elif event == SpeakerEvent.CANDIDATE_STOPPED:
            if self._active_speaker == ActiveSpeaker.BOTH:
                self._active_speaker = ActiveSpeaker.INTERVIEWER
            else:
                self._active_speaker = ActiveSpeaker.NONE

        if old != self._active_speaker:
            logger.debug("Speaker: %s → %s (%s)", old, self._active_speaker, event)

        if self._on_speaker_event:
            self._on_speaker_event(event, self._active_speaker)

    def reset(self):
        """Reset all state."""
        self._interviewer_vad.reset()
        self._candidate_vad.reset()
        self._active_speaker = ActiveSpeaker.NONE
        self._interviewer_buffer = []
        self._candidate_buffer = []
        self._interviewer_pre_roll.clear()
        self._interviewer_pre_roll_samples = 0
        self._post_roll_active = False
        self._post_roll_remaining = 0
        self._utterance_active = False
        self._onset = OnsetDiagnostics(
            pre_roll_ms=self._pre_roll_ms,
            post_roll_ms=self._post_roll_ms,
        )

    def force_flush_interviewer(self):
        """Force flush the accumulated interviewer audio."""
        if self._interviewer_buffer and self._on_interviewer_utterance:
            full_audio = np.concatenate(self._interviewer_buffer)
            duration_ms = (len(full_audio) / self._sample_rate) * 1000
            if len(full_audio) > 0:
                logger.warning("UTTERANCE_FLUSH (Interviewer Forced) duration=%.1fms", duration_ms)
                self._on_interviewer_utterance(full_audio, duration_ms)
        self._interviewer_buffer = []
        self._post_roll_active = False
        self._post_roll_remaining = 0
        self._utterance_active = False
        self._interviewer_vad.reset()
        self._update_speaker(ActiveSpeaker.NONE, SpeakerEvent.INTERVIEWER_STOPPED)

    @property
    def active_speaker(self) -> ActiveSpeaker:
        return self._active_speaker

    @property
    def is_candidate_speaking(self) -> bool:
        return self._active_speaker in (ActiveSpeaker.CANDIDATE, ActiveSpeaker.BOTH)

    @property
    def is_interviewer_speaking(self) -> bool:
        return self._active_speaker in (ActiveSpeaker.INTERVIEWER, ActiveSpeaker.BOTH)

    @property
    def pre_roll_ms(self) -> int:
        return self._pre_roll_ms
