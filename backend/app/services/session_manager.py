"""
AI Interview Coach - Session Manager

Manages the deterministic interview state machine.
All state transitions are explicit — never LLM-driven.
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional, Callable, Any
from datetime import datetime, timezone

from app.models.session import (
    SessionState,
    SessionEvent,
    SessionMode,
    InterviewSession,
    InterviewFactEntry,
    SessionMetrics,
    VALID_TRANSITIONS,
)
from app.models.candidate import CandidateProfile
from app.models.question import UtteranceClassification
from app.models.answer import GeneratedAnswer
from app.services.consistency_checker import consistency_checker
from app.db.repository import repository
import asyncio

logger = logging.getLogger(__name__)


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class SessionManager:
    """Manages interview sessions with deterministic state machine."""

    def __init__(self):
        self._sessions: dict[str, InterviewSession] = {}
        self._listeners: list[Callable] = []
        self._persistence_tasks: set[asyncio.Task] = set()

    def _persist_in_background(self, session: InterviewSession) -> None:
        """Track background persistence so shutdown cannot abandon DB writes."""
        task = asyncio.create_task(repository.save_session(session))
        self._persistence_tasks.add(task)
        task.add_done_callback(self._persistence_finished)

    def _persistence_finished(self, task: asyncio.Task) -> None:
        self._persistence_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception as exc:
            logger.error("Background session persistence failed: %s", exc)

    async def drain_persistence(self) -> None:
        """Wait for all pending session writes before closing the event loop."""
        if self._persistence_tasks:
            await asyncio.gather(*tuple(self._persistence_tasks), return_exceptions=True)

    # ── Session Lifecycle ───────────────────────────────────────

    def create_session(
        self,
        candidate_id: str,
        mode: SessionMode = SessionMode.COACHING,
        target_role_id: Optional[str] = None,
        meeting_platform: Optional[str] = None,
    ) -> InterviewSession:
        """Create a new interview session."""
        session = InterviewSession(
            candidate_id=candidate_id,
            target_role_id=target_role_id,
            meeting_platform=meeting_platform,
            mode=mode,
            state=SessionState.IDLE,
        )
        self._sessions[session.id] = session
        logger.info(f"Session created: {session.id} (mode={mode})")
        
        # Persist to database in background
        self._persist_in_background(session)
        
        return session

    def get_session(self, session_id: str) -> Optional[InterviewSession]:
        """Retrieve a session by ID."""
        return self._sessions.get(session_id)

    @staticmethod
    def effective_conversation_history(session: InterviewSession) -> list[dict]:
        history = list(session.conversation_history or [])
        if history:
            return history
        if session.last_completed_question:
            return [
                {"role": "interviewer", "text": session.last_completed_question},
                {"role": "suggested_answer", "text": session.last_completed_answer or ""},
            ]
        return []

    def mark_session_active(self, session_id: str) -> InterviewSession:
        """Repair lifecycle timestamps when reconnecting to an active session."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        session.ended_at = None
        if session.started_at is None:
            session.started_at = datetime.now(timezone.utc)
        self._persist_in_background(session)
        return session

    def end_session(self, session_id: str) -> InterviewSession:
        """End a session."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.state = SessionState.IDLE
        session.ended_at = datetime.now(timezone.utc)
        logger.info(f"Session ended: {session_id}")
        
        # Persist
        self._persist_in_background(session)
        
        return session

    # ── State Machine ───────────────────────────────────────────

    def transition(
        self, session_id: str, event: SessionEvent
    ) -> tuple[SessionState, SessionState]:
        """
        Attempt a state transition.
        Returns (old_state, new_state).
        Raises InvalidTransitionError if transition is not valid.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        old_state = session.state
        valid_events = VALID_TRANSITIONS.get(old_state, {})

        if event not in valid_events:
            raise InvalidTransitionError(
                f"Invalid transition: {old_state} + {event}. "
                f"Valid events from {old_state}: {list(valid_events.keys())}"
            )

        new_state = valid_events[event]
        session.state = new_state

        # Track session start
        if event == SessionEvent.START_SESSION:
            session.started_at = datetime.now(timezone.utc)
            session.ended_at = None

        logger.debug(f"State transition: {old_state} → {new_state} (event={event})")

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(session_id, old_state, new_state, event)
            except Exception as e:
                logger.error(f"Listener error: {e}")

        # Persist to database in background
        self._persist_in_background(session)

        return old_state, new_state

    def can_transition(
        self, session_id: str, event: SessionEvent
    ) -> bool:
        """Check if a transition is valid without performing it."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        valid_events = VALID_TRANSITIONS.get(session.state, {})
        return event in valid_events

    # ── Reliable Live View State ───────────────────────────────

    async def begin_interviewer_utterance(self, session_id: str) -> None:
        """Clear stale live Q/A as soon as a new utterance starts STT.

        Prevents the frontend poller from resurrecting the previous question
        while the next one is still being transcribed.
        """
        session = self._sessions.get(session_id)
        if not session:
            return
        session.current_answer = None
        session.current_question = None
        await repository.save_session(session)

    async def clear_live_question(self, session_id: str) -> None:
        """Mark the live strip idle after an answer is shown."""
        session = self._sessions.get(session_id)
        if not session:
            return
        # Keep current_answer for recovery; clear question so poll won't
        # push the UI back into "جاري التصنيف".
        session.current_question = None
        await repository.save_session(session)

    async def set_current_question(self, session_id: str, question: str) -> None:
        """Publish a transcribed question as recoverable session state."""
        session = self._sessions.get(session_id)
        if not session:
            return
        session.current_question = question
        session.current_answer = None
        await repository.save_session(session)

    async def publish_live_answer(self, session_id: str, answer: GeneratedAnswer) -> None:
        """Publish the complete answer before attempting transient WS delivery."""
        session = self._sessions.get(session_id)
        if not session:
            return
        session.current_question = answer.question
        session.current_answer = answer
        session.last_completed_question = answer.question
        session.last_completed_answer = answer.answer_en
        await repository.save_session(session)

    # ── Facts Ledger ────────────────────────────────────────────

    async def record_answer(
        self,
        session_id: str,
        answer: GeneratedAnswer,
    ):
        """Record facts from a generated answer in the session ledger."""
        session = self._sessions.get(session_id)
        if not session:
            return

        # Store Q&A immediately so the next live question can use it as context.
        # Fact extraction talks to the LLM and must not delay history.
        last_question = None
        for entry in reversed(session.conversation_history):
            if entry.get("role") == "interviewer":
                last_question = entry.get("text")
                break

        if last_question == answer.question:
            for entry in reversed(session.conversation_history):
                if entry.get("role") == "suggested_answer":
                    entry["text"] = answer.answer_en
                    break
        else:
            session.conversation_history.append({
                "role": "interviewer",
                "text": answer.question,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            session.conversation_history.append({
                "role": "suggested_answer",
                "text": answer.answer_en,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            session.questions_asked += 1

        session.last_completed_question = answer.question
        session.last_completed_answer = answer.answer_en

        await repository.save_session(session)

        async def _extract_facts_later() -> None:
            try:
                facts = await consistency_checker.extract_facts_from_answer(answer.answer_en)
                live_session = self._sessions.get(session_id)
                if not live_session:
                    return
                for fact in facts:
                    consistency_checker.add_fact(
                        live_session.facts_ledger,
                        fact=fact,
                        question_context=answer.question,
                    )
            except Exception as exc:
                logger.warning("Fact extraction skipped: %s", exc)

        asyncio.create_task(_extract_facts_later())

    async def record_candidate_answer(
        self,
        session_id: str,
        answer_text: str,
        question_context: Optional[str] = None,
    ):
        """Record the candidate's actual spoken answer."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.conversation_history.append({
            "role": "candidate",
            "text": answer_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Extract facts from candidate's answer too
        facts = await consistency_checker.extract_facts_from_answer(answer_text)
        for fact in facts:
            consistency_checker.add_fact(
                session.facts_ledger,
                fact=fact,
                question_context=question_context,
            )
            
        await repository.save_session(session)

    # ── Metrics ─────────────────────────────────────────────────

    def update_metrics(self, session_id: str, metrics: SessionMetrics):
        """Update session latency metrics."""
        session = self._sessions.get(session_id)
        if session:
            session.latest_metrics = metrics

    # ── Event Listeners ─────────────────────────────────────────

    def add_listener(self, callback: Callable):
        """Add a state transition listener."""
        self._listeners.append(callback)


# Singleton instance
session_manager = SessionManager()
