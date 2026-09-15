"""
AI Interview Coach - Question Classification Models

Models for question detection, classification, and prediction.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class UtteranceType(str, Enum):
    """Classification of an interviewer utterance."""

    QUESTION = "QUESTION"
    STATEMENT = "STATEMENT"
    FOLLOW_UP = "FOLLOW_UP"
    UNCERTAIN = "UNCERTAIN"


class QuestionCategory(str, Enum):
    """Interview question categories."""

    INTRODUCTION = "INTRODUCTION"
    CV_DEEP_DIVE = "CV_DEEP_DIVE"
    TECHNICAL = "TECHNICAL"
    ARCHITECTURE = "ARCHITECTURE"
    AI_ML = "AI_ML"
    SOFTWARE_ENGINEERING = "SOFTWARE_ENGINEERING"
    PROGRAMMING = "PROGRAMMING"
    MANAGEMENT = "MANAGEMENT"
    PROJECT_MANAGEMENT = "PROJECT_MANAGEMENT"
    LEADERSHIP = "LEADERSHIP"
    BEHAVIORAL = "BEHAVIORAL"
    STAR = "STAR"
    PROBLEM_SOLVING = "PROBLEM_SOLVING"
    SITUATIONAL = "SITUATIONAL"
    COMMUNICATION = "COMMUNICATION"
    CONFLICT_MANAGEMENT = "CONFLICT_MANAGEMENT"
    CAREER_MOTIVATION = "CAREER_MOTIVATION"
    COMPANY_FIT = "COMPANY_FIT"
    SALARY_HR = "SALARY_HR"
    FOLLOW_UP = "FOLLOW_UP"
    UNEXPECTED = "UNEXPECTED"


class UtteranceClassification(BaseModel):
    """Result of classifying an interviewer utterance."""

    type: UtteranceType
    confidence: float = Field(ge=0.0, le=1.0)
    normalized_question: Optional[str] = None
    category: Optional[QuestionCategory] = None
    requires_candidate_context: bool = False
    is_follow_up: bool = False
    follow_up_context: Optional[str] = None
    raw_utterance: str = ""
    latency_ms: Optional[float] = None


class QuestionAction(str, Enum):
    """What action the system should take after classification."""

    SHOW_ANSWER = "SHOW_ANSWER"
    LISTEN = "LISTEN"
    WAIT_FOR_COMPLETION = "WAIT_FOR_COMPLETION"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"

