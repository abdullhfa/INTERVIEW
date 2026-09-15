import unittest
from unittest.mock import AsyncMock, patch

from app.models.answer import (
    AnswerStrategy,
    ConfidenceScores,
    GeneratedAnswer,
    ValidationResult,
)
from app.models.candidate import AnswerLengthMode
from app.models.session import SessionEvent, SessionState
from app.services.session_manager import SessionManager


class ReliableLiveStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_restarting_ended_session_clears_stale_end_timestamp(self):
        manager = SessionManager()
        with patch(
            "app.services.session_manager.repository.save_session",
            AsyncMock(),
        ):
            session = manager.create_session("candidate-1")
            manager.end_session(session.id)
            manager.transition(session.id, SessionEvent.START_SESSION)
            await manager.drain_persistence()

        self.assertIsNone(session.ended_at)

    async def test_reconnecting_active_session_clears_stale_end_timestamp(self):
        manager = SessionManager()
        with patch(
            "app.services.session_manager.repository.save_session",
            AsyncMock(),
        ):
            session = manager.create_session("candidate-1")
            manager.end_session(session.id)
            session.state = SessionState.LISTENING
            manager.mark_session_active(session.id)
            await manager.drain_persistence()

        self.assertIsNone(session.ended_at)

    async def test_question_and_full_answer_are_recoverable_without_websocket(self):
        manager = SessionManager()
        answer = GeneratedAnswer(
            question_id="question-1",
            question="What is AI?",
            normalized_question="What is AI?",
            answer_en="AI is the simulation of human intelligence in machines.",
            strategy=AnswerStrategy.TECHNICAL_CONCISE,
            length_mode=AnswerLengthMode.QUICK,
            confidence=ConfidenceScores(answer_confidence=0.9),
            validation=ValidationResult(is_valid=True),
        )

        with patch(
            "app.services.session_manager.repository.save_session",
            AsyncMock(),
        ):
            session = manager.create_session("candidate-1")
            await manager.set_current_question(session.id, answer.question)
            question_snapshot = manager.get_session(session.id).model_copy(deep=True)
            await manager.publish_live_answer(session.id, answer)
            answer_snapshot = manager.get_session(session.id).model_copy(deep=True)
            await manager.drain_persistence()

        self.assertEqual(question_snapshot.current_question, "What is AI?")
        self.assertIsNone(question_snapshot.current_answer)
        self.assertEqual(answer_snapshot.current_answer, answer)


if __name__ == "__main__":
    unittest.main()
