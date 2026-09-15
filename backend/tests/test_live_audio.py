import unittest
from typing import Any
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.models.candidate import AnswerLanguageMode, AnswerLengthMode
from app.services.live_audio import LiveAudioOrchestrator
from app.services.transcript_aggregator import TranscriptAggregator


class LiveAudioLatencyRegressionTests(unittest.IsolatedAsyncioTestCase):
    def _await_args(self, mock: Any):
        self.assertIsNotNone(mock.await_args)
        await_args = mock.await_args
        assert await_args is not None
        return await_args

    async def test_live_coaching_starts_loopback_without_microphone_worker(self):
        orchestrator = LiveAudioOrchestrator(
            websocket=Mock(),
            session_id="loopback-session",
        )
        orchestrator.router.initialize = Mock()
        orchestrator.router.set_callbacks = Mock()
        orchestrator._send_ws = AsyncMock()

        with patch("app.services.live_audio.capture_manager") as capture:
            capture.start_capture = AsyncMock()
            capture.stop_capture = AsyncMock()
            capture.active_loopback_name = "Speakers [Loopback]"
            capture.active_output_name = "Speakers"
            await orchestrator.start()
            try:
                start_args = self._await_args(capture.start_capture)
                self.assertIsNone(start_args.kwargs["on_mic_audio"])
                self.assertEqual(len(orchestrator._tasks), 2)
                orchestrator.router.initialize.assert_called_once_with(
                    enable_candidate=False
                )
                send_args = self._await_args(orchestrator._send_ws)
                self.assertEqual(send_args.args[0]["type"], "AUDIO_CAPTURE_READY")
            finally:
                await orchestrator.stop()

    async def test_first_loopback_frame_announces_active_stream(self):
        import asyncio
        import numpy as np

        orchestrator = LiveAudioOrchestrator(Mock(), "audio-active-session")
        orchestrator._loop = asyncio.get_running_loop()
        orchestrator.router.process_interviewer_audio = Mock(return_value=None)
        orchestrator._send_ws = AsyncMock()

        # Keepalive-level silence must NOT count as meeting audio.
        orchestrator._loopback_audio_wrapper(np.zeros(512, dtype=np.float32))
        await asyncio.sleep(0.01)
        self.assertFalse(orchestrator._stream_active_notified)

        # Real speech-level amplitude should announce the stream.
        speech = np.full(512, 0.05, dtype=np.float32)
        orchestrator._loopback_audio_wrapper(speech)
        await asyncio.sleep(0.01)

        self.assertTrue(orchestrator._stream_active_notified)
        self.assertEqual(orchestrator._audio_frames_received, 2)
        event_types = [
            call.args[0]["type"] for call in orchestrator._send_ws.await_args_list
        ]
        self.assertIn("AUDIO_STREAM_ACTIVE", event_types)

    async def test_watchdog_reports_missing_system_audio_frames(self):
        import asyncio
        import time

        orchestrator = LiveAudioOrchestrator(Mock(), "audio-stalled-session")
        orchestrator.is_running = True
        orchestrator._capture_started_at = time.time() - 6
        orchestrator._send_ws = AsyncMock()

        with patch(
            "app.services.live_audio.capture_manager.is_loopback_stream_active",
            return_value=False,
        ):
            task = asyncio.create_task(orchestrator._pipeline_watchdog())
            await asyncio.sleep(0.15)
            orchestrator.is_running = False
            await task

        stalled_calls = [
            call.args[0]
            for call in orchestrator._send_ws.await_args_list
            if call.args[0]["type"] == "AUDIO_CAPTURE_STALLED"
        ]
        self.assertEqual(len(stalled_calls), 1)
        self.assertIn("تعذر التقاط صوت النظام", stalled_calls[0]["message"])

    async def test_watchdog_skips_stall_when_loopback_stream_is_active(self):
        import asyncio
        import time

        orchestrator = LiveAudioOrchestrator(Mock(), "audio-healthy-session")
        orchestrator.is_running = True
        orchestrator._capture_started_at = time.time() - 6
        orchestrator._send_ws = AsyncMock()

        with patch(
            "app.services.live_audio.capture_manager.is_loopback_stream_active",
            return_value=True,
        ):
            task = asyncio.create_task(orchestrator._pipeline_watchdog())
            await asyncio.sleep(0.15)
            orchestrator.is_running = False
            await task

        stalled_calls = [
            call.args[0]
            for call in orchestrator._send_ws.await_args_list
            if call.args[0]["type"] == "AUDIO_CAPTURE_STALLED"
        ]
        self.assertEqual(len(stalled_calls), 0)

    def test_realtime_queue_drops_stale_audio_when_full(self):
        import asyncio
        queue = asyncio.Queue(maxsize=2)
        LiveAudioOrchestrator._enqueue_latest(queue, ("old-1", 1))
        LiveAudioOrchestrator._enqueue_latest(queue, ("old-2", 2))
        LiveAudioOrchestrator._enqueue_latest(queue, ("latest", 3))

        self.assertEqual(queue.get_nowait(), ("old-2", 2))
        self.assertEqual(queue.get_nowait(), ("latest", 3))

    async def test_answer_is_sent_before_post_display_persistence(self):
        orchestrator = LiveAudioOrchestrator.__new__(LiveAudioOrchestrator)
        orchestrator.session_id = "session-1"
        orchestrator.suppress_answer = False
        orchestrator.current_question_id = None
        orchestrator.length_mode = AnswerLengthMode.QUICK
        orchestrator.language_mode = AnswerLanguageMode.ALWAYS_ENGLISH
        orchestrator.aggregator = TranscriptAggregator()
        # __new__ skips __init__; attrs used by _handle_utterance / history.
        orchestrator._last_turns = []
        orchestrator._last_interviewer_audio_levels = {}
        orchestrator.current_utterance_id = ""
        orchestrator._pending_interviewer = []
        events = []

        async def send(payload):
            events.append(payload["type"])

        async def record(_session_id, _generated):
            events.append("record_answer")

        orchestrator._send_ws = send
        session = SimpleNamespace(candidate_id="candidate-1", conversation_history=[])
        classification = SimpleNamespace(model_dump=lambda: {})
        generated = SimpleNamespace(
            question="question",
            answer_en="answer",
            answer_ar=None,
            validation=SimpleNamespace(is_valid=True),
            model_dump=lambda: {"answer_en": "answer"},
        )

        classifier = SimpleNamespace(
            classify=AsyncMock(return_value=classification),
            determine_action=Mock(return_value=SimpleNamespace(value="SHOW_ANSWER")),
        )
        generator = SimpleNamespace(generate=AsyncMock(return_value=generated))
        manager = SimpleNamespace(
            get_session=Mock(return_value=session),
            update_metrics=Mock(),
            publish_live_answer=AsyncMock(side_effect=lambda *_args: events.append("publish_answer")),
            record_answer=AsyncMock(side_effect=record),
            clear_live_question=AsyncMock(),
        )
        profiles = SimpleNamespace(get_profile=Mock(return_value=SimpleNamespace(id="candidate-1")))

        with (
            patch("app.services.live_audio.question_classifier", classifier),
            patch("app.services.live_audio.answer_generator", generator),
            patch("app.services.live_audio.session_manager", manager),
            patch("app.services.live_audio.candidate_profile_service", profiles),
        ):
            await orchestrator._handle_utterance("question", transcription_ms=12.5)

        self.assertLess(events.index("publish_answer"), events.index("ANSWER_READY"))
        self.assertLess(events.index("ANSWER_READY"), events.index("record_answer"))
        generate_args = self._await_args(generator.generate)
        self.assertEqual(generate_args.kwargs["length_mode"], AnswerLengthMode.QUICK)
        self.assertEqual(
            generate_args.kwargs["language_mode"],
            AnswerLanguageMode.ALWAYS_ENGLISH,
        )
        self.assertIsNotNone(manager.update_metrics.call_args)
        metrics = manager.update_metrics.call_args.args[1]
        self.assertEqual(metrics.transcription_ms, 12.5)
        self.assertGreater(metrics.total_latency_ms, 0)


if __name__ == "__main__":
    unittest.main()
