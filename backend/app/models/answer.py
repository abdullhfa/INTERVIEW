"""
AI Interview Coach - Answer Generation Models

Models for answer generation, validation, confidence, and review.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from app.models.candidate import AnswerLengthMode


class AnswerStrategy(str, Enum):
    """Strategy for generating the answer."""

    PERSONAL_NARRATIVE = "PERSONAL_NARRATIVE"  # "Tell me about yourself"
    CV_EVIDENCE = "CV_EVIDENCE"  # "What did you do at company X?"
    TECHNICAL_CONCISE = "TECHNICAL_CONCISE"  # "What is RAG?"
    TECHNICAL_DETAILED = "TECHNICAL_DETAILED"  # "Explain RAG architecture"
    BEHAVIORAL_STAR = "BEHAVIORAL_STAR"  # "Tell me about a time..."
    PROJECT_WALKTHROUGH = "PROJECT_WALKTHROUGH"  # "Describe your project"
    LEADERSHIP_EXAMPLE = "LEADERSHIP_EXAMPLE"  # "Describe your leadership"
    PROBLEM_SOLVING = "PROBLEM_SOLVING"  # Scenario questions
    CAREER_EXPLANATION = "CAREER_EXPLANATION"  # "Why did you leave?"
    COMPANY_FIT = "COMPANY_FIT"  # "Why this company?"
    FOLLOW_UP_EXPANSION = "FOLLOW_UP_EXPANSION"  # Follow-up to previous answer
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"  # Not enough info to answer


# ── Confidence ──────────────────────────────────────────────────


class ConfidenceScores(BaseModel):
    """Confidence metrics for a generated answer."""

    question_confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="How well the question was understood"
    )
    context_confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Quality of retrieved candidate context"
    )
    answer_confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Overall answer quality confidence"
    )
    technical_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Technical accuracy confidence (for technical Qs)",
    )


# ── Validation ──────────────────────────────────────────────────


class ValidationResult(BaseModel):
    """Result of answer validation checks."""

    is_valid: bool = True
    hallucination_detected: bool = False
    hallucinated_claims: list[str] = Field(default_factory=list)
    consistency_warning: bool = False
    contradictions: list[str] = Field(default_factory=list)
    technical_errors: list[str] = Field(default_factory=list)
    missing_context: bool = False
    missing_context_details: Optional[str] = None


# ── Generated Answer ────────────────────────────────────────────


class EvidenceSource(BaseModel):
    """A source from the candidate KB used to support the answer."""

    fact: str
    source_type: str  # CV, MANUAL_ENTRY, etc.
    source_section: Optional[str] = None
    relevance: float = Field(ge=0.0, le=1.0)


class GeneratedAnswer(BaseModel):
    """A complete answer package ready for display."""

    question_id: str = Field(default="")
    question: str
    normalized_question: str
    answer_en: str
    answer_ar: Optional[str] = None
    strategy: AnswerStrategy
    length_mode: AnswerLengthMode
    confidence: ConfidenceScores
    validation: ValidationResult
    candidate_evidence: list[EvidenceSource] = Field(default_factory=list)
    conversation_context: list[str] = Field(
        default_factory=list, description="Previous Q&A that influenced this answer"
    )
    action: str = "SHOW_ANSWER"  # SHOW_ANSWER, LISTEN, INSUFFICIENT_CONTEXT
    internal_reasoning: Optional[str] = None  # Debug only

    @property
    def is_safe_to_display(self) -> bool:
        """Answer passes all validation checks."""
        return (
            self.validation.is_valid
            and not self.validation.hallucination_detected
            and not self.validation.consistency_warning
            and self.confidence.answer_confidence >= 0.5
        )


# ── Answer Review (Mock Interview) ─────────────────────────────


class AnswerReviewScores(BaseModel):
    """Scoring dimensions for candidate answer review."""

    correctness: float = Field(0, ge=0, le=100)
    relevance: float = Field(0, ge=0, le=100)
    completeness: float = Field(0, ge=0, le=100)
    confidence_displayed: float = Field(0, ge=0, le=100)
    clarity: float = Field(0, ge=0, le=100)
    naturalness: float = Field(0, ge=0, le=100)
    conciseness: float = Field(0, ge=0, le=100)
    technical_accuracy: float = Field(0, ge=0, le=100)
    cv_consistency: float = Field(0, ge=0, le=100)
    answer_consistency: float = Field(0, ge=0, le=100)
    star_structure: Optional[float] = Field(None, ge=0, le=100)

    @property
    def overall_score(self) -> float:
        scores = [
            self.correctness,
            self.relevance,
            self.completeness,
            self.confidence_displayed,
            self.clarity,
            self.naturalness,
            self.conciseness,
            self.technical_accuracy,
            self.cv_consistency,
            self.answer_consistency,
        ]
        if self.star_structure is not None:
            scores.append(self.star_structure)
        return sum(scores) / len(scores)


class AnswerReview(BaseModel):
    """Complete review of a candidate's answer."""

    question: str
    candidate_answer: str
    scores: AnswerReviewScores
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    filler_words_detected: list[str] = Field(default_factory=list)
    repeated_words: list[str] = Field(default_factory=list)
    estimated_duration_seconds: Optional[float] = None
    suggested_better_answer: Optional[str] = None
    suggested_better_answer_ar: Optional[str] = None
    improvement_tips: list[str] = Field(default_factory=list)
