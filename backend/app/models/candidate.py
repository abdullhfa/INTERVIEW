"""
AI Interview Coach - Candidate Knowledge Base Models

Every extracted fact carries a source reference and confidence score.
These models enforce that no candidate information exists without provenance.
"""

from __future__ import annotations
from datetime import date, datetime, timezone
from enum import Enum
import re
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── Source Tracking ─────────────────────────────────────────────


class FactSource(str, Enum):
    CV = "CV"
    MANUAL_ENTRY = "MANUAL_ENTRY"
    JOB_DESCRIPTION = "JOB_DESCRIPTION"
    CERTIFICATION_DOC = "CERTIFICATION_DOC"
    PROJECT_DOC = "PROJECT_DOC"
    INTERVIEW_NOTES = "INTERVIEW_NOTES"
    SESSION_ANSWER = "SESSION_ANSWER"


class VerifiedFact(BaseModel):
    """Every candidate claim must be traceable to a source."""

    fact: str
    source: FactSource
    source_section: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)


# ── Profile Components ──────────────────────────────────────────


class PersonalProfile(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    nationality: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    personal_summary: Optional[str] = None


class ProfessionalSummary(BaseModel):
    summary: Optional[str] = None
    years_of_experience: Optional[int] = None
    current_role: Optional[str] = None
    specializations: list[str] = Field(default_factory=list)

    @field_validator("years_of_experience", mode="before")
    @classmethod
    def _coerce_years(cls, value: object) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if 0 <= value <= 60 else None
        if isinstance(value, float):
            years = int(value)
            return years if 0 <= years <= 60 else None
        text = str(value).strip()
        match = re.search(r"\d{1,2}", text)
        if not match:
            return None
        years = int(match.group(0))
        return years if 0 <= years <= 60 else None


class Employment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    location: Optional[str] = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    reason_for_leaving: Optional[str] = None
    source: FactSource = FactSource.CV
    confidence: float = 1.0


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    duration: Optional[str] = None
    team_size: Optional[int] = None
    source: FactSource = FactSource.CV
    confidence: float = 1.0

    @field_validator("team_size", mode="before")
    @classmethod
    def _coerce_team_size(cls, value: object) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 0 else None
        if isinstance(value, float):
            return int(value) if value >= 0 else None
        text = str(value).strip()
        match = re.search(r"\d{1,4}", text)
        if not match:
            return None
        size = int(match.group(0))
        return size if size >= 0 else None


class Education(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    institution: str
    degree: Optional[str] = None
    field: Optional[str] = None
    graduation_date: Optional[str] = None
    gpa: Optional[str] = None
    honors: list[str] = Field(default_factory=list)
    source: FactSource = FactSource.CV
    confidence: float = 1.0


class Certification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    issuer: Optional[str] = None
    obtained_date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None
    source: FactSource = FactSource.CV
    confidence: float = 1.0


class Skill(BaseModel):
    name: str
    category: Optional[str] = None  # technical, management, soft
    proficiency: Optional[str] = None  # expert, advanced, intermediate, beginner
    years_used: Optional[int] = None
    evidence: list[str] = Field(default_factory=list)
    source: FactSource = FactSource.CV
    confidence: float = 1.0


class CareerTransition(BaseModel):
    from_role: str
    to_role: str
    reason: Optional[str] = None
    year: Optional[str] = None
    source: FactSource = FactSource.CV


# ── Target Role ─────────────────────────────────────────────────


class TargetRole(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    field: Optional[str] = None
    specialization: Optional[str] = None
    # Legacy fields remain readable so previously saved profiles still load.
    company: Optional[str] = None
    position: Optional[str] = None
    job_description: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    seniority_level: Optional[str] = None
    interview_language: Optional[str] = "en"
    department: Optional[str] = None
    industry: Optional[str] = None


# ── Interview Preferences ───────────────────────────────────────


class AnswerLengthMode(str, Enum):
    QUICK = "QUICK"  # 20-30 seconds
    STANDARD = "STANDARD"  # 45-60 seconds
    DETAILED = "DETAILED"  # 60-120 seconds


class AnswerLanguageMode(str, Enum):
    ANSWER_IN_QUESTION_LANGUAGE = "ANSWER_IN_QUESTION_LANGUAGE"
    ALWAYS_ARABIC = "ALWAYS_ARABIC"
    ALWAYS_ENGLISH = "ALWAYS_ENGLISH"
    SHOW_ARABIC_AND_ENGLISH = "SHOW_ARABIC_AND_ENGLISH"


class InterviewPreferences(BaseModel):
    answer_length: AnswerLengthMode = AnswerLengthMode.STANDARD
    answer_language: AnswerLanguageMode = (
        AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH
    )
    preferred_language: str = "en"
    show_confidence: bool = True
    show_evidence: bool = True
    enable_teleprompter: bool = False


# ── Complete Candidate Profile ──────────────────────────────────


class ExpectedQuestion(BaseModel):
    """A question the candidate expects, with the exact answer they want to use."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    prompt: str = Field(
        min_length=2,
        max_length=500,
        description="How the interviewer may ask, or a close meaning",
    )
    answer: str = Field(min_length=2, max_length=4000)


class CandidateProfile(BaseModel):
    """
    The normalized Candidate Knowledge Base.
    This is the single source of truth for all candidate information.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    personal_profile: PersonalProfile = Field(default_factory=PersonalProfile)
    professional_summary: ProfessionalSummary = Field(
        default_factory=ProfessionalSummary
    )
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    employment_history: list[Employment] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    technical_skills: list[Skill] = Field(default_factory=list)
    management_skills: list[Skill] = Field(default_factory=list)
    soft_skills: list[Skill] = Field(default_factory=list)
    achievements: list[VerifiedFact] = Field(default_factory=list)
    career_transitions: list[CareerTransition] = Field(default_factory=list)
    interview_preferences: InterviewPreferences = Field(
        default_factory=InterviewPreferences
    )
    target_roles: list[TargetRole] = Field(default_factory=list)
    expected_questions: list[ExpectedQuestion] = Field(default_factory=list)
    verified_personal_facts: list[VerifiedFact] = Field(default_factory=list)
    topics_to_avoid: list[str] = Field(default_factory=list)
    is_verified: bool = False
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


# ── API Request/Response Models ─────────────────────────────────


class ProfileExtractionResult(BaseModel):
    """Result of CV/document parsing before user verification."""

    extracted_profile: CandidateProfile
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    raw_text: Optional[str] = None
    extraction_status: str = Field(
        "complete",
        description="partial = fast essentials only; complete = full extraction",
    )
    enrichment_job_id: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    """User-corrected profile data for verification."""

    profile: CandidateProfile
    corrections_made: list[str] = Field(default_factory=list)


class TargetRoleRequest(BaseModel):
    """The selected professional field and its precise target specialization."""

    field: str = Field(min_length=2, max_length=200)
    specialization: str = Field(min_length=2, max_length=200)


class ExpectedQuestionsRequest(BaseModel):
    """Optional prepared Q&A list. Empty list clears previously saved items."""

    items: list[ExpectedQuestion] = Field(default_factory=list)
