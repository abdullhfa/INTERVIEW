"""
AI Interview Coach - Live Audio Orchestrator

Manages the true real-time loop:
WASAPI loopback -> CaptureManager -> SpeakerRouter -> VAD -> Buffer -> STTEngine
-> QuestionClassifier -> AnswerGenerator -> WebSocket
"""

import asyncio
import logging
import time
import uuid
import numpy as np
from typing import Optional
from fastapi import WebSocket

from app.audio.capture_manager import capture_manager
from app.audio.speaker_router import SpeakerRouter, SpeakerEvent, ActiveSpeaker
from app.audio.stt_engine import stt_engine, warm_whisper_model

from app.models.candidate import AnswerLengthMode, AnswerLanguageMode
from app.models.answer import (
    AnswerStrategy,
    ConfidenceScores,
    GeneratedAnswer,
    ValidationResult,
)
from app.models.session import SessionMetrics
from app.config import settings
from app.services.session_manager import session_manager
from app.models.question import QuestionAction, UtteranceType
from app.services.question_classifier import question_classifier, is_greeting_or_filler
from app.services.question_bank import BankMatch, question_bank
from app.services.answer_generator import answer_generator
from app.services.candidate_profile import candidate_profile_service
from app.services.transcript_aggregator import TranscriptAggregator
from app.services.gemini_gateway import gemini


logger = logging.getLogger(__name__)

class LiveAudioOrchestrator:
    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        length_mode: AnswerLengthMode = AnswerLengthMode.QUICK,
        language_mode: AnswerLanguageMode = AnswerLanguageMode.ANSWER_IN_QUESTION_LANGUAGE,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.length_mode = length_mode
        self.language_mode = language_mode
        self.router = SpeakerRouter()
        self.is_running = False
        
        # Queues for background STT processing to not block audio callbacks.
        # Keep headroom so a long answer generation cannot drop the next question.
        self.interviewer_queue = asyncio.Queue(maxsize=8)
        self.candidate_queue = asyncio.Queue(maxsize=4)
        
        self.suppress_answer = False
        # Questions finalized while the candidate is speaking must not be
        # discarded. They are processed after the candidate utterance ends.
        self._pending_interviewer: list[tuple[str, float]] = []
        self._tasks = []
        self.last_loopback_time = time.time()
        self._capture_started_at = 0.0
        self._audio_frames_received = 0
        self._stream_active_notified = False
        self._capture_stalled_notified = False
        self._silence_warned = False
        self._peak_loopback_rms = 0.0
        # Keepalive tone is ~1e-5; real speech/meeting audio is typically >> 0.005
        self._meaningful_audio_rms = 0.008
        self.current_question_id = None
        self._capture_owner = f"{session_id}:{uuid.uuid4()}"
        self._last_telemetry = {"interviewer": 0.0, "candidate": 0.0}
        self._ws_send_lock = asyncio.Lock()
        self._pending_transcript_parts: list[str] = []
        self._pending_transcript_flush_at = 0.0
        self._pending_transcript_ms = 0.0
        
        # Aggregator for incoming partial STT transcripts
        agg_silence = getattr(settings, 'aggregation_silence_ms', 1000)
        self.aggregator = TranscriptAggregator(timeout_ms=agg_silence, dedup_window_s=8.0)
        self._answer_tasks: set[asyncio.Task] = set()
        self._last_turns: list[dict] = []
        self._last_interviewer_audio_levels: dict[str, float] = {}

    async def start(self):
        """Start the live audio loop."""
        self.is_running = True
        self._loop = asyncio.get_running_loop()
        self.router.initialize(enable_candidate=False)
        
        self.router.set_callbacks(
            on_speaker_event=self._on_speaker_event,
            on_interviewer_utterance=self._on_interviewer_utterance,
            on_candidate_utterance=None,
        )
        
        # Start background workers
        self._tasks.append(asyncio.create_task(self._process_interviewer_queue()))
        self._tasks.append(asyncio.create_task(self._pipeline_watchdog()))
        asyncio.create_task(gemini.warm_connection(), name="llm-warmup")
        asyncio.create_task(warm_whisper_model(), name="whisper-warmup")

        # Start hardware capture
        try:
            self._capture_started_at = time.time()
            await capture_manager.start_capture(
                on_mic_audio=None,
                on_loopback_audio=self._loopback_audio_wrapper,
                owner_id=self._capture_owner,
            )
        except Exception:
            self.is_running = False
            for task in self._tasks:
                task.cancel()
            self._tasks.clear()
            raise
        logger.info(
            "Live Audio Orchestrator started for session %s (pipeline=stt-parallel-v2)",
            self.session_id,
        )
        await self._send_ws({
            "type": "AUDIO_CAPTURE_READY",
            "message": "بانتظار بدأ المقابله",
            "loopback_device": capture_manager.active_loopback_name,
            "output_device": capture_manager.active_output_name,
        })

    def _mic_audio_wrapper(self, audio: np.ndarray):
        rms = float(np.sqrt(np.mean(audio**2))) if len(audio) > 0 else 0.0
        result = self.router.process_candidate_audio(audio)
        
        if (
            hasattr(self, '_loop')
            and self._loop.is_running()
            and self._should_emit_telemetry("candidate")
        ):
            asyncio.run_coroutine_threadsafe(
                self._send_ws({
                    "type": "telemetry", 
                    "speaker": "candidate", 
                    "rms": rms,
                    "vad_score": result.probability if result else 0.0,
                    "vad_state": result.state.value if result else "SILENCE"
                }),
                self._loop
            )

    def _loopback_audio_wrapper(self, audio: np.ndarray):
        self.last_loopback_time = time.time()
        self._audio_frames_received += 1
        rms = float(np.sqrt(np.mean(audio**2))) if len(audio) > 0 else 0.0
        if rms > self._peak_loopback_rms:
            self._peak_loopback_rms = rms
        result = self.router.process_interviewer_audio(audio)

        # Do not treat the near-silent WASAPI keepalive as "meeting audio".
        if (
            not self._stream_active_notified
            and rms >= self._meaningful_audio_rms
            and hasattr(self, '_loop')
            and self._loop.is_running()
        ):
            self._stream_active_notified = True
            self._silence_warned = False
            asyncio.run_coroutine_threadsafe(
                self._send_ws({
                    "type": "AUDIO_STREAM_ACTIVE",
                    "message": "بانتظار بدأ المقابله",
                    "rms": rms,
                }),
                self._loop,
            )
        
        if (
            hasattr(self, '_loop')
            and self._loop.is_running()
            and self._should_emit_telemetry("interviewer")
        ):
            asyncio.run_coroutine_threadsafe(
                self._send_ws({
                    "type": "telemetry", 
                    "speaker": "interviewer", 
                    "rms": rms,
                    "vad_score": result.probability if result else 0.0,
                    "vad_state": result.state.value if result else "SILENCE"
                }),
                self._loop
            )

    def _should_emit_telemetry(self, speaker: str) -> bool:
        """Limit telemetry to 4Hz per channel instead of flooding the WebSocket."""
        now = time.monotonic()
        if now - self._last_telemetry[speaker] < 0.25:
            return False
        self._last_telemetry[speaker] = now
        return True

    async def stop(self):
        """Stop the live audio loop."""
        self.is_running = False
        self._pending_interviewer.clear()
        self.suppress_answer = False
        await capture_manager.stop_capture(owner_id=self._capture_owner)
        for task in list(self._answer_tasks):
            task.cancel()
        self._answer_tasks.clear()
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("Live Audio Orchestrator stopped.")

    def force_flush_interviewer(self):
        """Force flush the interviewer VAD buffer manually."""
        if hasattr(self, 'router') and self.router:
            self.router.force_flush_interviewer()

    def _on_speaker_event(
        self,
        event: SpeakerEvent,
        active_speaker: ActiveSpeaker | None = None,
    ):
        """Handle real-time VAD state changes."""
        logger.debug(f"Speaker Event: {event}")
        if not self.is_running or not hasattr(self, '_loop'):
            return
            
        if event == SpeakerEvent.CANDIDATE_STARTED:
            self.suppress_answer = True
            self.candidate_speaking_start_time = time.time()
            asyncio.run_coroutine_threadsafe(self._send_ws({"type": "CANDIDATE_SPEAKING", "status": True}), self._loop)
            asyncio.run_coroutine_threadsafe(self._send_ws({"type": "STATE_CHANGED", "state": "CANDIDATE_ANSWERING"}), self._loop)
            asyncio.run_coroutine_threadsafe(self._send_ws({"type": "SPEECH_DETECTED", "speaker": "candidate"}), self._loop)
            
        elif event == SpeakerEvent.CANDIDATE_STOPPED:
            self.suppress_answer = False
            asyncio.run_coroutine_threadsafe(self._send_ws({"type": "CANDIDATE_SPEAKING", "status": False}), self._loop)
            asyncio.run_coroutine_threadsafe(self._send_ws({"type": "STATE_CHANGED", "state": "LISTENING"}), self._loop)
            asyncio.run_coroutine_threadsafe(self._flush_pending_interviewer(), self._loop)
            
        elif event == SpeakerEvent.INTERVIEWER_STARTED:
            asyncio.run_coroutine_threadsafe(self._send_ws({"type": "STATE_CHANGED", "state": "INTERVIEWER_SPEAKING"}), self._loop)
            asyncio.run_coroutine_threadsafe(self._send_ws({"type": "SPEECH_DETECTED", "speaker": "interviewer"}), self._loop)
            asyncio.run_coroutine_threadsafe(self._send_ws({"type": "PARTIAL_TRANSCRIPT", "speaker": "interviewer", "text": "Interviewer is speaking..."}), self._loop)
            
        elif event == SpeakerEvent.INTERVIEWER_STOPPED:
            # Do not jump back to LISTENING here — STT/classify is about to run.
            # Premature LISTENING made the UI look like the question was abandoned.
            asyncio.run_coroutine_threadsafe(
                self._send_ws({"type": "STATE_CHANGED", "state": "QUESTION_FINALIZING"}),
                self._loop,
            )

    def _on_interviewer_utterance(self, audio: np.ndarray, duration_ms: float):
        """Called when the interviewer finishes a chunk of speech."""
        logger.info("Interviewer utterance finalized (%.0fms)", duration_ms)
        try:
            if hasattr(self, '_loop') and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._send_ws({"type": "UTTERANCE_FINALIZED", "speaker": "interviewer"}),
                    self._loop,
                )
                self._loop.call_soon_threadsafe(
                    self._enqueue_latest, self.interviewer_queue, (audio, duration_ms)
                )
        except Exception as e:
            logger.error(f"Failed to queue interviewer audio: {e}")

    def _on_candidate_utterance(self, audio: np.ndarray, duration_ms: float):
        """Called when the candidate finishes a chunk of speech."""
        logger.debug(f"Candidate utterance finalized ({duration_ms}ms)")
        try:
            if hasattr(self, '_loop') and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._enqueue_latest, self.candidate_queue, (audio, duration_ms))
        except Exception as e:
            logger.error(f"Failed to queue candidate audio: {e}")

    @staticmethod
    def _enqueue_latest(queue: asyncio.Queue, item: tuple) -> None:
        """Enqueue interviewer/candidate audio without dropping real utterances.

        Previously this dropped the oldest item when full, which discarded the
        next interview question while a long answer was still generating.
        """
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.warning(
                "Audio queue full (%s/%s); waiting briefly instead of dropping utterance",
                queue.qsize(),
                queue.maxsize,
            )
            # Last resort: drop only if still full after a tiny yield window is
            # impossible from a sync callback — replace the newest noise slot.
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(item)
            except asyncio.QueueFull:
                logger.error("Failed to enqueue audio utterance; queue saturated")

    async def _pipeline_watchdog(self):
        """
        Watchdog to handle WASAPI loopback silence bug and pipeline locks.
        If no audio is received for 200ms and the interviewer is currently speaking,
        inject silence to flush the VAD buffer and trigger SPEECH_END.
        Also, ensure candidate suppression doesn't lock the pipeline indefinitely.
        """
        chunk_samples = getattr(settings, 'audio_chunk_samples', 512)
        silence_chunk = np.zeros(chunk_samples, dtype=np.float32)
        
        while self.is_running:
            await asyncio.sleep(0.1)
            now = time.time()

            if (
                self._audio_frames_received == 0
                and not self._capture_stalled_notified
                and self._capture_started_at
                and now - self._capture_started_at >= 5.0
                and not capture_manager.is_loopback_stream_active()
            ):
                self._capture_stalled_notified = True
                await self._send_ws({
                    "type": "AUDIO_CAPTURE_STALLED",
                    "message": (
                        "تعذر التقاط صوت النظام. اختر جهاز الإخراج الحالي في Windows "
                        "وتأكد أن صوت الاجتماع يعمل عليه."
                    ),
                })

            # Frames may arrive from keepalive only — warn when meeting audio is silent.
            if (
                not self._stream_active_notified
                and not self._silence_warned
                and self._capture_started_at
                and now - self._capture_started_at >= 8.0
            ):
                self._silence_warned = True
                device = capture_manager.active_loopback_name or "جهاز الإخراج المحدد"
                await self._send_ws({
                    "type": "AUDIO_CAPTURE_SILENT",
                    "message": "بانتظار بدأ المقابله",
                    "peak_rms": self._peak_loopback_rms,
                    "loopback_device": device,
                })

            # Loopback Audio Watchdog
            if hasattr(self, 'last_loopback_time') and now - self.last_loopback_time > 0.2:
                # If we haven't received loopback audio and the router thinks the interviewer is speaking
                if self.router.is_interviewer_speaking:
                    self.last_loopback_time = now
                    self._loopback_audio_wrapper(silence_chunk)
            
            # Transcript Aggregator Watchdog is removed. We process immediately.
                        
            # Candidate Suppression Watchdog
            if self.suppress_answer and hasattr(self, 'candidate_speaking_start_time'):
                if now - self.candidate_speaking_start_time > 15.0:
                    logger.warning("Pipeline Watchdog: Candidate suppression locked for > 15s. Forcing release.")
                    self.suppress_answer = False
                    self.candidate_speaking_start_time = now  # Reset to prevent log spam
                    await self._flush_pending_interviewer()

            if (
                self._pending_transcript_parts
                and self._pending_transcript_flush_at
                and now >= self._pending_transcript_flush_at
            ):
                await self._flush_pending_transcript(force=True)

    async def _transcribe_interviewer(self, audio: np.ndarray) -> tuple[str, float]:
        """STT with preprocess + short-question accurate second pass."""
        from app.audio.utterance_preprocess import estimate_audio_levels, preprocess_utterance
        from app.services.stt_confidence import (
            assess_match_risk,
            simple_need_second_pass,
            transcript_looks_weak,
        )

        stt_start = time.perf_counter()
        timeout = settings.stt_timeout_seconds
        raw = np.asarray(audio, dtype=np.float32)
        prepared = preprocess_utterance(raw, sample_rate=16000, boost=1.0)
        try:
            self._last_interviewer_audio_levels = estimate_audio_levels(
                raw, prepared, sample_rate=16000
            )
        except Exception:
            self._last_interviewer_audio_levels = {}

        try:
            text = await stt_engine.transcribe_realtime(
                prepared,
                timeout_seconds=timeout,
            )
        except TimeoutError:
            text = ""

        # Latency-cut simple STT: at most one accurate retry; never raw third pass.
        prelim = question_bank.match(text) if (text or "").strip() else None
        risk = assess_match_risk(text, prelim)
        need_second, _reason, _strong = simple_need_second_pass(text, prelim, risk=risk)
        if need_second:
            await self._send_ws({
                "type": "STT_RETRYING",
                "speaker": "interviewer",
                "message": "إعادة محاولة تفريغ السؤال...",
            })
            candidates: list[str] = []
            try:
                accurate = await stt_engine.transcribe_realtime(
                    prepared,
                    timeout_seconds=settings.stt_retry_timeout_seconds,
                    accurate=True,
                )
            except TimeoutError:
                accurate = ""
            if accurate:
                candidates.append(accurate)

            best = text
            best_match = prelim
            best_score = float(prelim.score) if prelim else 0.0
            for cand in candidates:
                m = question_bank.match(cand) if cand.strip() else None
                s = float(m.score) if m else 0.0
                fixes = transcript_looks_weak(best or "") and not transcript_looks_weak(cand)
                if (not best) or s > best_score + 0.03 or fixes:
                    best, best_match, best_score = cand, m, s
            text = best

        transcription_ms = (time.perf_counter() - stt_start) * 1000
        return text, transcription_ms

    async def _process_interviewer_queue(self):
        """STT worker — must stay free so question 2/3 are transcribed during answer gen."""
        while self.is_running:
            try:
                audio, duration_ms = await self.interviewer_queue.get()
                
                logger.info("STT_START (Interviewer) queue_remaining=%s", self.interviewer_queue.qsize())
                # Clear stale live question/answer so polling cannot resurrect Q1
                # while Q2 is being transcribed.
                await session_manager.begin_interviewer_utterance(self.session_id)
                await self._send_ws({
                    "type": "STATE_CHANGED",
                    "state": "QUESTION_FINALIZING",
                })
                text, transcription_ms = await self._transcribe_interviewer(audio)

                if not text:
                    logger.warning("STT_EMPTY (Interviewer) after retry")
                    await self._send_ws({
                        "type": "STT_EMPTY",
                        "speaker": "interviewer",
                        "soft": True,
                    })
                    await self._send_ws({"type": "STATE_CHANGED", "state": "LISTENING"})
                    continue

                await self._send_ws({"type": "STATE_CHANGED", "state": "QUESTION_FINALIZING"})
                logger.info(
                    "STT_SUCCESS (Interviewer) text='%s' latency=%.0fms",
                    text,
                    transcription_ms,
                )

                if self.aggregator.is_duplicate(text):
                    logger.info(f"Duplicate question ignored: '{text}'")
                    await self._send_ws({"type": "STATE_CHANGED", "state": "LISTENING"})
                    continue

                # Show transcript + kick off classify/generate in the background
                # so the next utterance can be transcribed immediately.
                await self._ingest_interviewer_transcript(text, transcription_ms)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing interviewer audio: {e}")

    @staticmethod
    def _looks_like_complete_question(text: str) -> bool:
        """Heuristic: keep waiting for more fragments when speech was cut mid-question."""
        from app.services.question_classifier import is_introduction_question

        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return False
        if is_introduction_question(cleaned):
            return True
        if cleaned.endswith("?"):
            return True
        words = cleaned.split()
        if len(words) >= 4:
            return True
        starters = (
            "tell me", "what ", "why ", "how ", "when ", "where ", "who ",
            "can you", "could you", "please ", "describe", "explain",
            "تحدث", "ما هو", "ما هي", "لماذا", "كيف", "هل ",
        )
        lowered = cleaned.casefold()
        if any(lowered.startswith(s) or f" {s}" in f" {lowered}" for s in starters):
            return len(words) >= 3
        return False

    async def _ingest_interviewer_transcript(self, text: str, transcription_ms: float) -> None:
        """Show transcript immediately, then classify/answer without post-STT delay."""
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return

        merge_ms = getattr(settings, "interviewer_stt_merge_ms", 0)
        if merge_ms > 0 and self._pending_transcript_parts:
            last = self._pending_transcript_parts[-1].casefold()
            if cleaned.casefold() != last and cleaned.casefold() not in last:
                self._pending_transcript_parts.append(cleaned)
            self._pending_transcript_ms = max(self._pending_transcript_ms, transcription_ms)
        else:
            self._pending_transcript_parts = [cleaned]
            self._pending_transcript_ms = transcription_ms

        combined = " ".join(self._pending_transcript_parts).strip()
        await session_manager.set_current_question(self.session_id, combined)
        await self._send_ws({
            "type": "TRANSCRIPT_CREATED",
            "speaker": "interviewer",
            "text": combined,
        })

        # Slow-speech completeness comes from vad_interviewer_min_silence_ms.
        # Do not add extra wait after STT before generating the answer.
        if (
            merge_ms <= 0
            or self._looks_like_complete_question(combined)
            or len(self._pending_transcript_parts) >= 4
        ):
            await self._flush_pending_transcript(force=True)
            return

        self._pending_transcript_flush_at = time.time() + (merge_ms / 1000.0)
        logger.info(
            "Holding incomplete interviewer transcript for merge: '%s'",
            combined,
        )
        await self._send_ws({"type": "STATE_CHANGED", "state": "QUESTION_FINALIZING"})

    async def _flush_pending_transcript(self, *, force: bool = False) -> None:
        if not self._pending_transcript_parts:
            return
        if not force and self._pending_transcript_flush_at and time.time() < self._pending_transcript_flush_at:
            return

        combined = " ".join(self._pending_transcript_parts).strip()
        transcription_ms = self._pending_transcript_ms
        self._pending_transcript_parts = []
        self._pending_transcript_flush_at = 0.0
        self._pending_transcript_ms = 0.0

        if not combined:
            await self._send_ws({"type": "STATE_CHANGED", "state": "LISTENING"})
            return

        if self.suppress_answer:
            logger.info("Candidate is speaking; queueing interviewer question until candidate finishes.")
            self._pending_interviewer.append((combined, transcription_ms))
            await self._send_ws({
                "type": "question_queued",
                "reason": "candidate_speaking",
            })
            return

        self._schedule_handle_utterance(combined, transcription_ms)

    def _schedule_handle_utterance(self, text: str, transcription_ms: float = 0.0) -> None:
        """Run classify+generate without blocking the STT worker."""
        task = asyncio.create_task(
            self._handle_utterance(text, transcription_ms=transcription_ms),
            name=f"handle-utterance-{text[:24].replace(' ', '_')}",
        )
        self._answer_tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            self._answer_tasks.discard(t)
            if t.cancelled():
                return
            exc = t.exception()
            if exc:
                logger.error("Background utterance handling failed: %s", exc)

        task.add_done_callback(_done)

    async def _process_candidate_queue(self):
        """Background loop to process STT for Candidate."""
        while self.is_running:
            try:
                audio, duration_ms = await self.candidate_queue.get()
                
                logger.info("STT_START (Candidate)")
                try:
                    text = await stt_engine.transcribe_realtime(
                        audio,
                        timeout_seconds=settings.candidate_stt_timeout_seconds,
                    )
                except TimeoutError:
                    logger.error(
                        "STT_TIMEOUT (Candidate) after %.1fs",
                        settings.candidate_stt_timeout_seconds,
                    )
                    text = ""
                    await self._send_ws({"type": "STT_TIMEOUT", "speaker": "candidate"})

                if text:
                    logger.info(f"STT_SUCCESS (Candidate) text='{text}'")
                    await self._send_ws({"type": "TRANSCRIPT_CREATED", "speaker": "candidate", "text": text})

                    # Record candidate answer
                    await session_manager.record_candidate_answer(self.session_id, text)
                    await self._send_ws({"type": "candidate_answer_recorded"})
                else:
                    logger.warning("Candidate STT returned empty; releasing answer suppression anyway.")
                    await self._send_ws({
                        "type": "STT_EMPTY",
                        "speaker": "candidate",
                    })

                # Always release suppression after the candidate utterance has
                # been finalized, even if STT failed. Otherwise one failed STT
                # request permanently blocks every future AI answer.
                if not self.router.is_candidate_speaking:
                    self.suppress_answer = False
                    await self._flush_pending_interviewer()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing candidate audio: {e}")


    async def _flush_pending_interviewer(self):
        """Process questions that arrived while the candidate was speaking."""
        if self.suppress_answer or not self._pending_interviewer:
            return

        pending = self._pending_interviewer
        self._pending_interviewer = []
        logger.info("Flushing %d queued interviewer utterance(s)", len(pending))
        for text, transcription_ms in pending:
            self._schedule_handle_utterance(text, transcription_ms)

    async def _bank_match(self, text: str, history: list[dict]) -> Optional[BankMatch]:
        """Prepared-bank lookup off the event loop; never raises."""
        if not settings.question_bank_enabled or not text.strip():
            return None
        loop = asyncio.get_running_loop()
        levels = dict(self._last_interviewer_audio_levels or {})
        try:
            from app.services.far_call_recovery import recover_far_match
            from app.services.realistic_recovery import recover_realistic_match
            from app.services.stt_confidence import assess_match_risk, apply_strong_abstain

            def _lookup() -> Optional[BankMatch]:
                from app.services.main_request_extraction import match_with_main_request

                match, _ext, mre_meta = match_with_main_request(
                    text, conversation_history=history
                )
                risk = assess_match_risk(text, match)
                match = apply_strong_abstain(match, risk)
                mre_locked = bool(mre_meta.get("override")) and float(
                    (
                        mre_meta["extraction"].get("confidence")
                        if isinstance(mre_meta.get("extraction"), dict)
                        else 0.0
                    )
                    or 0.0
                ) >= 0.72
                if mre_locked:
                    return match
                # Narrowband Far recovery (frozen path) — wideband Clean/Office skip it.
                decision = recover_far_match(
                    text,
                    match,
                    audio_levels=levels,
                    conversation_history=history,
                )
                if decision.applied:
                    match = decision.match
                    logger.info(
                        "Far/narrowband recovery: %s margin=%.3f id=%s",
                        decision.reason,
                        decision.margin,
                        None if not decision.match else decision.match.entry.id,
                    )
                # Realistic recovery: ambiguous / distinctive conflict only.
                decision = recover_realistic_match(
                    text,
                    match,
                    conversation_history=history,
                )
                if decision.applied:
                    logger.info(
                        "Realistic recovery: %s margin=%.3f id=%s",
                        decision.reason,
                        decision.margin,
                        None if not decision.match else decision.match.entry.id,
                    )
                    match = decision.match
                # Semantic paraphrase / short / weak recovery (conditional).
                from app.services.semantic_intent_recovery import recover_semantic_intent

                sem = recover_semantic_intent(
                    text,
                    match,
                    conversation_history=history,
                )
                if sem.applied and sem.match is not None:
                    logger.info(
                        "Semantic recovery: %s id=%s mode=%s agree=%.3f",
                        sem.reason,
                        sem.match.entry.id,
                        sem.match.mode,
                        sem.agreement,
                    )
                    return sem.match
                return match

            return await loop.run_in_executor(None, _lookup)
        except Exception as exc:
            logger.warning("Question bank lookup failed: %s", exc)
            return None

    async def _handle_utterance(self, text: str, transcription_ms: float = 0.0):
        """Generate answer based on interviewer utterance."""
        import uuid
        question_id = str(uuid.uuid4())
        utterance_id = str(uuid.uuid4())
        self.current_question_id = question_id
        self.current_utterance_id = utterance_id
        
        session = session_manager.get_session(self.session_id)
        if session is None:
            logger.error("Session %s not found during utterance handling", self.session_id)
            await self._send_ws({"type": "STATE_CHANGED", "state": "LISTENING"})
            return

        profile = candidate_profile_service.get_profile(session.candidate_id)
        if profile is None:
            logger.error(
                "Candidate profile missing for session %s (candidate_id=%s)",
                self.session_id,
                session.candidate_id,
            )
            await self._send_ws({"type": "STATE_CHANGED", "state": "LISTENING"})
            return

        history = self._conversation_history(session)
        
        # Include STT in the user-visible pipeline latency, while using a
        # monotonic clock so system clock adjustments cannot corrupt metrics.
        start_time = time.perf_counter() - (transcription_ms / 1000)

        if not self.suppress_answer:
            await self._send_ws({"type": "ANSWER_GENERATING"})
        
        # Classify
        logger.info("QUESTION_CLASSIFICATION_START history_turns=%s", len(history))
        classify_start = time.perf_counter()
        classification, bank_match = await asyncio.gather(
            question_classifier.classify(
                text,
                conversation_history=history,
                prefer_speed=True,
            ),
            self._bank_match(text, history),
        )
        classify_ms = (time.perf_counter() - classify_start) * 1000
        action = question_classifier.determine_action(classification)
        # A strong hit in the prepared question bank is a question by
        # definition (imperatives like "Walk me through the BTEC project" must
        # never be dropped as statements). Acknowledgments never match strongly.
        if (
            action.value != "SHOW_ANSWER"
            and bank_match is not None
            and bank_match.is_strong
            and not is_greeting_or_filler(text)
        ):
            logger.info(
                "Question bank override: treating %r as a question (id=%s score=%.2f)",
                text, bank_match.entry.id, bank_match.score,
            )
            classification = classification.model_copy(
                update={"type": UtteranceType.QUESTION, "confidence": max(classification.confidence, 0.9)}
            )
            action = QuestionAction.SHOW_ANSWER
        logger.info(f"QUESTION_CLASSIFIED (action={action.value}) latency={classify_ms:.1f}ms")
        
        await self._send_ws({
            "type": "QUESTION_DETECTED",
            "utterance": text,
            "classification": classification.model_dump(),
            "action": action.value,
            "latency_ms": round(classify_ms, 1),
        })

        if action.value != "SHOW_ANSWER":
            await self._send_ws({
                "type": "QUESTION_IGNORED",
                "utterance": text,
                "action": action.value,
                "reason": classification.type.value if classification.type else "not_a_question",
            })
            await self._send_ws({"type": "STATE_CHANGED", "state": "LISTENING"})
            return
        
        if not self.suppress_answer:
            logger.info("ANSWER_GENERATION_START")
            gen_start = time.perf_counter()
            requested_language = getattr(
                self,
                "language_mode",
                AnswerLanguageMode.ANSWER_IN_QUESTION_LANGUAGE,
            )
            async def on_partial(text: str) -> None:
                cleaned = (text or "").strip()
                if len(cleaned) < 4:
                    return
                if self.current_question_id != question_id or self.suppress_answer:
                    return
                asked = classification.raw_utterance or classification.normalized_question or ""
                draft = GeneratedAnswer(
                    question_id=question_id,
                    question=asked,
                    normalized_question=classification.normalized_question or asked,
                    answer_en=cleaned,
                    strategy=AnswerStrategy.TECHNICAL_CONCISE,
                    length_mode=getattr(self, "length_mode", AnswerLengthMode.QUICK),
                    confidence=ConfidenceScores(
                        question_confidence=0.8,
                        context_confidence=0.7,
                        answer_confidence=0.7,
                        technical_confidence=0.7,
                    ),
                    validation=ValidationResult(is_valid=True),
                    action="SHOW_ANSWER",
                )
                await self._send_ws({
                    "type": "ANSWER_PARTIAL",
                    "answer": draft.model_dump(),
                })

            generated = await answer_generator.generate(
                classification=classification,
                profile=profile,
                conversation_history=history,
                question_id=question_id,
                target_role_id=getattr(session, "target_role_id", None),
                length_mode=getattr(self, "length_mode", AnswerLengthMode.QUICK),
                language_mode=requested_language,
                prefer_speed=True,
                on_partial=on_partial,
            )
            
            if not generated.validation.is_valid:
                # Live coaching must still show the answer. Blocking here made the
                # transcript flash then vanish back to "listening" with an empty UI.
                logger.warning(
                    "Live answer validation soft-fail (%s); publishing anyway.",
                    generated.validation.missing_context_details or "invalid",
                )
                generated.validation.is_valid = True

            # CRITICAL: Check again if candidate started speaking during generation!
            # Still publish — dropping silently left the UI with no answer.
            if self.suppress_answer:
                logger.warning("Candidate spoke during generation; still publishing live answer.")
                
            if self.current_question_id != question_id:
                logger.warning("Answer superseded by a newer question. Discarding.")
                return

            gen_ms = (time.perf_counter() - gen_start) * 1000
            total_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "ANSWER_GENERATION_SUCCESS latency=%.0fms total=%.0fms stt=%.0fms classify=%.0fms",
                gen_ms,
                total_ms,
                transcription_ms,
                classify_ms,
            )

            session_manager.update_metrics(
                self.session_id,
                SessionMetrics(
                    transcription_ms=round(transcription_ms, 1),
                    question_classification_ms=round(classify_ms, 1),
                    answer_generation_ms=round(gen_ms, 1),
                    total_latency_ms=round(total_ms, 1),
                ),
            )

            # Publish the complete display payload before WebSocket delivery.
            # The socket remains the fast path; the REST session snapshot is the
            # replayable source of truth if this one frame is lost.
            await session_manager.publish_live_answer(self.session_id, generated)
            self._remember_turn(generated.question, generated.answer_en)
            await self._send_ws({
                "type": "ANSWER_READY",
                "answer": generated.model_dump(),
                "metrics": {
                    "classification_ms": round(classify_ms, 1),
                    "generation_ms": round(gen_ms, 1),
                    "total_ms": round(total_ms, 1),
                },
            })

            await session_manager.record_answer(self.session_id, generated)
            # Free the live strip for the next question; keep answer for recovery.
            await session_manager.clear_live_question(self.session_id)
            self.aggregator.recent_questions.clear()
            await self._send_ws({"type": "STATE_CHANGED", "state": "LISTENING"})

            if (
                requested_language == AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH
                and not (generated.answer_ar and generated.answer_ar.strip())
            ):
                asyncio.create_task(
                    self._fill_second_language(generated, question_id),
                    name=f"bilingual-fill-{question_id[:8]}",
                )

    async def _fill_second_language(self, generated, question_id: str) -> None:
        """Add the missing EN/AR side after the first language is already on screen."""
        try:
            if self.current_question_id != question_id or self.suppress_answer:
                return
            updated = await answer_generator.fill_bilingual_pair(generated)
            if self.current_question_id != question_id or self.suppress_answer:
                return
            if updated.answer_ar == generated.answer_ar and updated.answer_en == generated.answer_en:
                return
            await session_manager.publish_live_answer(self.session_id, updated)
            await self._send_ws({
                "type": "ANSWER_READY",
                "answer": updated.model_dump(),
            })
            await session_manager.record_answer(self.session_id, updated)
            if self.current_question_id == question_id:
                await session_manager.clear_live_question(self.session_id)
        except Exception as e:
            logger.warning("Background bilingual fill failed: %s", e)

    def _remember_turn(self, question: str, answer: str) -> None:
        self._last_turns = [
            {"role": "interviewer", "text": question},
            {"role": "suggested_answer", "text": answer},
        ]

    def _conversation_history(self, session) -> list[dict]:
        history = list(session.conversation_history or [])
        if history:
            return history
        last_q = getattr(session, "last_completed_question", None)
        last_a = getattr(session, "last_completed_answer", None)
        if last_q:
            return [
                {"role": "interviewer", "text": last_q},
                {"role": "suggested_answer", "text": last_a or ""},
            ]
        return list(self._last_turns)

    async def _send_ws(self, payload: dict):
        """Safely send to websocket."""
        try:
            import uuid
            msg_type = payload.get("type", "unknown")
            msg = {
                "version": 1,
                "event_id": str(uuid.uuid4()),
                "session_id": self.session_id,
                "utterance_id": getattr(self, "current_utterance_id", ""),
                "question_id": getattr(self, "current_question_id", ""),
                "type": msg_type,
                "source": "backend",
                "timestamp": str(time.time()),
                "payload": payload
            }
            if msg_type != "ANSWER_PARTIAL":
                logger.info(f"WEBSOCKET_SEND {msg_type}")
            async with self._ws_send_lock:
                await self.websocket.send_json(msg)
        except Exception as e:
            logger.error(f"Failed to send WS message: {e}")
