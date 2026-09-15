"""
AI Interview Coach - Analytics Generator

Aggregates session scores into a Post-Interview Scorecard
and generates an actionable Study Plan.
"""

from __future__ import annotations
import logging
from pydantic import BaseModel
from typing import Optional

from app.services.gemini_gateway import gemini
from app.services.scoring_engine import AnswerScore

logger = logging.getLogger(__name__)

class StudyPlanAction(BaseModel):
    topic: str
    weakness_identified: str
    action_item: str
    recommended_resource: str

class InterviewScorecard(BaseModel):
    overall_score: int
    technical_score: int
    communication_score: int
    behavioral_score: int
    key_strengths: list[str]
    critical_weaknesses: list[str]
    study_plan: list[StudyPlanAction]
    general_feedback: str

ANALYTICS_SYSTEM_PROMPT = """\
You are an expert career coach analyzing a candidate's mock interview performance.
You will be provided with the scores and feedback for each question they answered.

Synthesize this into an overall scorecard and an actionable study plan.
1. Calculate overall averages for Technical, Communication, and Behavioral (STAR) dimensions.
2. Identify the most critical weaknesses that need immediate attention.
3. Generate a concrete study plan with specific action items.
"""

class AnalyticsGenerator:
    """Generates post-interview analytics."""

    async def generate_scorecard(self, session_answers: list[dict], candidate_summary: str) -> InterviewScorecard:
        """Generate final scorecard and study plan from all session answers."""
        
        # Prepare context from session answers
        context_parts = [f"## Candidate Summary: {candidate_summary}"]
        
        for i, ans in enumerate(session_answers):
            context_parts.append(f"\n### Question {i+1}")
            context_parts.append(f"Q: {ans.get('question')}")
            context_parts.append(f"A: {ans.get('candidate_answer')}")
            
            # If we saved the AnswerScore dict
            score_data = ans.get('scores', {})
            context_parts.append(f"Scores: {score_data}")
            
        prompt = "\n".join(context_parts)
        
        try:
            scorecard = await gemini.generate_structured(
                prompt=prompt,
                response_schema=InterviewScorecard,
                system_instruction=ANALYTICS_SYSTEM_PROMPT,
                temperature=0.4
            )
            return scorecard
        except Exception as e:
            logger.error(f"Scorecard generation failed: {e}")
            raise

# Singleton
analytics_generator = AnalyticsGenerator()
