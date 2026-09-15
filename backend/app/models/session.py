"""
AI Interview Coach - Session & State Machine Models

Defines the deterministic interview session state machine.
State transitions are explicit — not LLM-driven.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field
from app.models.answer import GeneratedAnswer


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionState(str, Enum):
    """Interview session states — deterministic state machine."""

    IDLE = "IDLE"
    LISTENING = "LISTENING"
    INTERVIEWER_SPEAKING = "INTERVIEWER_SPEAKING"
    CANDIDATE_SPEAKING = "CANDIDATE_SPEAKING"
    QUESTION_DETECTED = "QUESTION_DETECTED"
    QUESTION_FINALIZING = "QUESTION_FINALIZING"
    CONTEXT_RETRIEVAL = "CONTEXT_RETRIEVAL"
    ANSWER_GENERATING = "ANSWER_GENERATING"
    ANSWER_READY = "ANSWER_READY"
    WAITING_FOR_CANDIDATE = "WAITING_FOR_CANDIDATE"
    CANDIDATE_ANSWERING = "CANDIDATE_ANSWERING"
    ANSWER_REVIEW = "ANSWER_REVIEW"
    PAUSED = "PAUSED"
    ERROR_RECOVERY = "ERROR_RECOVERY"


class SessionMode(str, Enum):
    """Interview session modes."""

    COACHING = "COACHING"  # Real-time coaching during interview
    PRACTICE = "PRACTICE"  # Mock interview with AI interviewer
    PREPARATION = "PREPARATION"  # Pre-interview study/review


class SessionEvent(str, Enum):
    """Events that can trigger state transitions."""

    START_SESSION = "START_SESSION"
    INTERVIEWER_VAD_ACTIVE = "INTERVIEWER_VAD_ACTIVE"
    INTERVIEWER_SILENCE = "INTERVIEWER_SILENCE"
    BRIEF_PAUSE_RESUME = "BRIEF_PAUSE_RESUME"
    CANDIDATE_VAD_ACTIVE = "CANDIDATE_VAD_ACTIVE"
    CANDIDATE_SILENCE = "CANDIDATE_SILENCE"
    IS_QUESTION = "IS_QUESTION"
    IS_STATEMENT = "IS_STATEMENT"
    CLASSIFY_COMPLETE = "CLASSIFY_COMPLETE"
    CONTEXT_READY = "CONTEXT_READY"
    ANSWER_VALIDATED = "ANSWER_VALIDATED"
    VALIDATION_FAILED_RETRY = "VALIDATION_FAILED_RETRY"
    ANSWER_DISPLAYED = "ANSWER_DISPLAYED"
    REVIEW_COMPLETE = "REVIEW_COMPLETE"
    PAUSE_REQUESTED = "PAUSE_REQUESTED"
    RESUME_REQUESTED = "RESUME_REQUESTED"
    END_SESSION = "END_SESSION"
    ERROR_OCCURRED = "ERROR_OCCURRED"
    ERROR_RESOLVED = "ERROR_RESOLVED"


# ── Valid State Transitions ─────────────────────────────────────

VALID_TRANSITIONS: dict[SessionState, dict[SessionEvent, SessionState]] = {
    SessionState.IDLE: {
        SessionEvent.START_SESSION: SessionState.LISTENING,
    },
    SessionState.LISTENING: {
        SessionEvent.INTERVIEWER_VAD_ACTIVE: SessionState.INTERVIEWER_SPEAKING,
        SessionEvent.CANDIDATE_VAD_ACTIVE: SessionState.CANDIDATE_SPEAKING,
        SessionEvent.PAUSE_REQUESTED: SessionState.PAUSED,
        SessionEvent.END_SESSION: SessionState.IDLE,
        SessionEvent.ERROR_OCCURRED: SessionState.ERROR_RECOVERY,
    },
    SessionState.INTERVIEWER_SPEAKING: {
        SessionEvent.INTERVIEWER_SILENCE: SessionState.QUESTION_FINALIZING,
        SessionEvent.BRIEF_PAUSE_RESUME: SessionState.INTERVIEWER_SPEAKING,
        SessionEvent.ERROR_OCCURRED: SessionState.ERROR_RECOVERY,
    },
    SessionState.QUESTION_FINALIZING: {
        SessionEvent.IS_QUESTION: SessionState.QUESTION_DETECTED,
        SessionEvent.IS_STATEMENT: SessionState.LISTENING,
        SessionEvent.INTERVIEWER_VAD_ACTIVE: SessionState.INTERVIEWER_SPEAKING,
    },
    SessionState.QUESTION_DETECTED: {
        SessionEvent.CLASSIFY_COMPLETE: SessionState.CONTEXT_RETRIEVAL,
    },
    SessionState.CONTEXT_RETRIEVAL: {
        SessionEvent.CONTEXT_READY: SessionState.ANSWER_GENERATING,
        SessionEvent.ERROR_OCCURRED: SessionState.ERROR_RECOVERY,
    },
    SessionState.ANSWER_GENERATING: {
        SessionEvent.ANSWER_VALIDATED: SessionState.ANSWER_READY,
        SessionEvent.VALIDATION_FAILED_RETRY: SessionState.ANSWER_GENERATING,
        SessionEvent.CANDIDATE_VAD_ACTIVE: SessionState.CANDIDATE_SPEAKING,
        SessionEvent.ERROR_OCCURRED: SessionState.ERROR_RECOVERY,
    },
    SessionState.ANSWER_READY: {
        SessionEvent.ANSWER_DISPLAYED: SessionState.WAITING_FOR_CANDIDATE,
        SessionEvent.END_SESSION: SessionState.IDLE,
    },
    SessionState.WAITING_FOR_CANDIDATE: {
        SessionEvent.CANDIDATE_VAD_ACTIVE: SessionState.CANDIDATE_ANSWERING,
        SessionEvent.INTERVIEWER_VAD_ACTIVE: SessionState.INTERVIEWER_SPEAKING,
        SessionEvent.END_SESSION: SessionState.IDLE,
    },
    SessionState.CANDIDATE_SPEAKING: {
        SessionEvent.CANDIDATE_SILENCE: SessionState.LISTENING,
        SessionEvent.ERROR_OCCURRED: SessionState.ERROR_RECOVERY,
    },
    SessionState.CANDIDATE_ANSWERING: {
        SessionEvent.CANDIDATE_SILENCE: SessionState.ANSWER_REVIEW,
        SessionEvent.ERROR_OCCURRED: SessionState.ERROR_RECOVERY,
    },
    SessionState.ANSWER_REVIEW: {
        SessionEvent.REVIEW_COMPLETE: SessionState.LISTENING,
    },
    SessionState.PAUSED: {
        SessionEvent.RESUME_REQUESTED: SessionState.LISTENING,
        SessionEvent.END_SESSION: SessionState.IDLE,
    },
    SessionState.ERROR_RECOVERY: {
        SessionEvent.ERROR_RESOLVED: SessionState.LISTENING,
        SessionEvent.END_SESSION: SessionState.IDLE,
    },
}


# ── Session Data ────────────────────────────────────────────────


class InterviewFactEntry(BaseModel):
    """An entry in the Interview Facts Ledger for consistency tracking."""

    fact: str
    stated_at: datetime = Field(default_factory=_utc_now)
    question_context: Optional[str] = None
    source: str = "session_answer"


class SessionMetrics(BaseModel):
    """Latency and performance metrics for a session."""

    audio_capture_ms: float = 0
    speech_detection_ms: float = 0
    transcription_ms: float = 0
    question_classification_ms: float = 0
    context_retrieval_ms: float = 0
    answer_generation_ms: float = 0
    answer_validation_ms: float = 0
    rendering_ms: float = 0
    total_latency_ms: float = 0


class InterviewSession(BaseModel):
    """Active interview session state."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    candidate_id: str
    target_role_id: Optional[str] = None
    meeting_platform: Optional[str] = None  # Zoom, Teams, Meet, etc.
    mode: SessionMode = SessionMode.COACHING
    state: SessionState = SessionState.IDLE
    facts_ledger: list[InterviewFactEntry] = Field(default_factory=list)
    conversation_history: list[dict] = Field(default_factory=list)
    current_question: Optional[str] = None
    current_answer: Optional[GeneratedAnswer] = None
    questions_asked: int = 0
    latest_metrics: SessionMetrics = Field(default_factory=SessionMetrics)
    last_completed_question: Optional[str] = None
    last_completed_answer: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utc_now)
