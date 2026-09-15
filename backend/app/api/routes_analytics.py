"""
AI Interview Coach - Analytics API Routes

Retrieves scorecards and study plans.
"""

from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException

from app.services.session_manager import session_manager
from app.services.analytics_generator import analytics_generator, InterviewScorecard
from app.services.candidate_profile import candidate_profile_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/sessions/{session_id}/scorecard", response_model=InterviewScorecard)
async def get_scorecard(session_id: str):
    """Generate or retrieve the scorecard for a completed session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
        
    profile = candidate_profile_service.get_profile(session.candidate_id)
    summary = profile.professional_summary.summary if profile else "Unknown Candidate"
    
    # In a real app, session answers with scores would be fetched from DB.
    # For now, we simulate fetching the answers from the session's conversation history
    # where the candidate provided an answer.
    
    answers = []
    # Simplified mock extraction
    for entry in session.conversation_history:
        if entry.get("role") == "candidate":
            answers.append({
                "question": entry.get("question_context", "Unknown Question"),
                "candidate_answer": entry.get("text", "")
            })
            
    if not answers:
        raise HTTPException(400, "No candidate answers found in this session to score.")

    try:
        scorecard = await analytics_generator.generate_scorecard(answers, summary)
        return scorecard
    except Exception as e:
        raise HTTPException(500, str(e))
