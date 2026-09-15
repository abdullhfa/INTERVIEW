"""
AI Interview Coach - Scoring Engine

Evaluates candidate answers against 12+ dimensions and generates sub-scores.
"""

from __future__ import annotations
import logging
from typing import Optional
from pydantic import BaseModel, Field

from app.services.gemini_gateway import gemini

logger = logging.getLogger(__name__)

class DimensionScore(BaseModel):
    score: int = Field(..., ge=1, le=10, description="Score from 1 to 10")
    feedback: str = Field(..., description="Specific feedback on this dimension")

class AnswerScore(BaseModel):
    technical_accuracy: DimensionScore
    communication_clarity: DimensionScore
    star_method_adherence: DimensionScore
    relevance_to_role: DimensionScore
    confidence_tone: DimensionScore
    overall_score: int = Field(..., ge=1, le=10)
    key_strengths: list[str]
    areas_for_improvement: list[str]
    suggested_better_answer: str

SCORING_SYSTEM_PROMPT = """\
You are an expert technical interviewer evaluating a candidate's answer.
Analyze the answer against the provided question and candidate profile.

Provide scores (1-10) for:
1. Technical Accuracy (Is the content correct and sound?)
2. Communication Clarity (Is the answer structured and easy to follow?)
3. STAR Method (Did they provide a Situation, Task, Action, and Result?)
4. Relevance to Role (Does it match the target job description?)
5. Confidence & Tone (Is the language professional and assertive?)

Also provide an overall score, key strengths, areas for improvement, and a suggested better answer.
Be highly critical but constructive.
"""

class ScoringEngine:
    """Evaluates candidate answers in Practice Mode."""

    async def score_answer(
        self,
        question: str,
        answer: str,
        candidate_summary: str,
        target_role: str
    ) -> AnswerScore:
        """Score a single answer."""
        
        prompt = f"""
## Question Asked
{question}

## Candidate's Answer
{answer}

## Candidate Summary
{candidate_summary}

## Target Role
{target_role}

Evaluate this answer comprehensively.
"""
        try:
            score = await gemini.generate_structured(
                prompt=prompt,
                response_schema=AnswerScore,
                system_instruction=SCORING_SYSTEM_PROMPT,
                temperature=0.3
            )
            return score
        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            raise

# Singleton
scoring_engine = ScoringEngine()
