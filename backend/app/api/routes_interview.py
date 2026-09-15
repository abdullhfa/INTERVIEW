"""
AI Interview Coach - Interview Session API Routes

Manages interview session lifecycle and answer generation.
"""

from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.models.session import SessionMode, InterviewSession
from app.models.candidate import AnswerLengthMode, AnswerLanguageMode
from app.models.question import UtteranceClassification
from app.models.answer import GeneratedAnswer
from app.services.session_manager import session_manager
from app.services.question_classifier import question_classifier
from app.services.answer_generator import answer_generator
from app.services.candidate_profile import candidate_profile_service

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateSessionRequest(BaseModel):
    candidate_id: str
    mode: SessionMode = SessionMode.COACHING
    target_role_id: Optional[str] = None
    meeting_platform: Optional[str] = None


class ProcessUtteranceRequest(BaseModel):
    session_id: str
    utterance: str
    length_mode: AnswerLengthMode = AnswerLengthMode.STANDARD
    language_mode: AnswerLanguageMode = AnswerLanguageMode.ANSWER_IN_QUESTION_LANGUAGE


class ProcessUtteranceResponse(BaseModel):
    classification: UtteranceClassification
    answer: Optional[GeneratedAnswer] = None
    action: str  # SHOW_ANSWER, LISTEN, INSUFFICIENT_CONTEXT


@router.post("/sessions", response_model=InterviewSession)
async def create_session(request: CreateSessionRequest):
    """Create a new interview session."""
    profile = candidate_profile_service.get_profile(request.candidate_id)
    if not profile:
        raise HTTPException(404, "Candidate profile not found")

    session = session_manager.create_session(
        candidate_id=request.candidate_id,
        mode=request.mode,
        target_role_id=request.target_role_id,
        meeting_platform=request.meeting_platform,
    )
    return session


@router.get("/sessions/{session_id}", response_model=InterviewSession)
async def get_session(session_id: str):
    """Get session state."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.post("/sessions/{session_id}/end", response_model=InterviewSession)
async def end_session(session_id: str):
    """End an interview session."""
    try:
        return session_manager.end_session(session_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/test-question", response_model=ProcessUtteranceResponse)
@router.post("/process-utterance", response_model=ProcessUtteranceResponse)
async def process_utterance(request: ProcessUtteranceRequest):
    """
    Process an interviewer utterance through the full pipeline:
    classify → retrieve context → generate answer → validate.

    This is the main endpoint for non-WebSocket usage.
    """
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    profile = candidate_profile_service.get_profile(session.candidate_id)
    if not profile:
        raise HTTPException(404, "Candidate profile not found")

    history = session_manager.effective_conversation_history(session)

    # Step 1: Classify the utterance
    classification = await question_classifier.classify(
        request.utterance,
        conversation_history=history,
    )

    # Step 2: Determine action
    action = question_classifier.determine_action(classification)

    # Step 3: Generate answer if it's a question
    generated_answer = None
    if action.value == "SHOW_ANSWER":
        generated_answer = await answer_generator.generate(
            classification=classification,
            profile=profile,
            conversation_history=history,
            target_role_id=getattr(session, "target_role_id", None),
            length_mode=request.length_mode,
            language_mode=request.language_mode,
        )

        # Step 5: Record in session state
        await session_manager.record_answer(session.id, generated_answer)

    return ProcessUtteranceResponse(
        classification=classification,
        answer=generated_answer,
        action=action.value,
    )
