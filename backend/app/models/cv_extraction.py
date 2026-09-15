"""
Simplified CV extraction schemas for Gemini constrained decoding.

The full CandidateProfile model is too complex for Gemini's response_schema
("constraint that has too many states"). These draft models strip enums,
numeric bounds, UUIDs, datetimes, and interview preferences so extraction
succeeds; we then map into CandidateProfile locally.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.models.candidate import (
    CandidateProfile,
    PersonalProfile,
    ProfessionalSummary,
    Employment,
    Project,
    Education,
    Certification,
    Skill,
    VerifiedFact,
    CareerTransition,
    FactSource,
)


class DraftPersonal(BaseModel):
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


class DraftSummary(BaseModel):
    summary: Optional[str] = None
    years_of_experience: Optional[int] = None
    current_role: Optional[str] = None
    specializations: list[str] = Field(default_factory=list)

    @field_validator("years_of_experience", mode="before")
    @classmethod
    def _coerce_years_of_experience(cls, value: object) -> Optional[int]:
        """Accept ints and common CV phrases like 'since 2010' / '15 years'."""
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if 0 <= value <= 60 else None
        if isinstance(value, float):
            years = int(value)
            return years if 0 <= years <= 60 else None

        text = str(value).strip().lower()
        # Prefer an explicit year count when no calendar year is present.
        if not re.search(r"(19|20)\d{2}", text):
            count = re.search(r"(\d{1,2})\s*(?:\+)?\s*(?:years?|yrs?|عام|سنوات|سنة)?", text)
            if count:
                years = int(count.group(1))
                return years if 0 <= years <= 60 else None

        year_match = re.search(r"(19|20)\d{2}", text)
        if year_match:
            start = int(year_match.group(0))
            now = datetime.now(timezone.utc).year
            if 1970 <= start <= now:
                return max(1, now - start)
        return None


class DraftEmployment(BaseModel):
    company: str = ""
    title: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    location: Optional[str] = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    reason_for_leaving: Optional[str] = None

    @field_validator("company", "title", mode="before")
    @classmethod
    def _coerce_required_strings(cls, value: object) -> str:
        return str(value).strip() if value is not None else ""


class DraftProject(BaseModel):
    name: str = ""
    description: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    duration: Optional[str] = None
    team_size: Optional[int] = None

    @field_validator("name", mode="before")
    @classmethod
    def _coerce_name(cls, value: object) -> str:
        return str(value).strip() if value is not None else ""

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

    @field_validator(
        "technologies", "outcomes", "challenges", mode="before"
    )
    @classmethod
    def _coerce_str_lists(cls, value: object) -> list:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []


class DraftEducation(BaseModel):
    institution: str = ""
    degree: Optional[str] = None
    field: Optional[str] = None
    graduation_date: Optional[str] = None
    gpa: Optional[str] = None
    honors: list[str] = Field(default_factory=list)


class DraftCertification(BaseModel):
    name: str = ""
    issuer: Optional[str] = None
    obtained_date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None


class DraftSkill(BaseModel):
    name: str = ""
    category: Optional[str] = None
    proficiency: Optional[str] = None
    years_used: Optional[int] = None
    evidence: list[str] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def _coerce_name(cls, value: object) -> str:
        return str(value).strip() if value is not None else ""


class DraftAchievement(BaseModel):
    fact: str = ""
    source_section: Optional[str] = None


class DraftTransition(BaseModel):
    from_role: str = ""
    to_role: str = ""
    reason: Optional[str] = None
    year: Optional[str] = None


class CVExtractionDraft(BaseModel):
    """Minimal schema Gemini can serve for CV extraction."""

    personal_profile: DraftPersonal = Field(default_factory=DraftPersonal)
    professional_summary: DraftSummary = Field(default_factory=DraftSummary)
    education: list[DraftEducation] = Field(default_factory=list)
    certifications: list[DraftCertification] = Field(default_factory=list)
    employment_history: list[DraftEmployment] = Field(default_factory=list)
    projects: list[DraftProject] = Field(default_factory=list)
    technical_skills: list[DraftSkill] = Field(default_factory=list)
    management_skills: list[DraftSkill] = Field(default_factory=list)
    soft_skills: list[DraftSkill] = Field(default_factory=list)
    achievements: list[DraftAchievement] = Field(default_factory=list)
    career_transitions: list[DraftTransition] = Field(default_factory=list)
    topics_to_avoid: list[str] = Field(default_factory=list)


class CVFastExtractionDraft(BaseModel):
    """Small schema for the first fast CV pass (~20-30s)."""

    personal_profile: DraftPersonal = Field(default_factory=DraftPersonal)
    professional_summary: DraftSummary = Field(default_factory=DraftSummary)
    employment_history: list[DraftEmployment] = Field(default_factory=list)
    education: list[DraftEducation] = Field(default_factory=list)
    technical_skills: list[DraftSkill] = Field(default_factory=list)
    certifications: list[DraftCertification] = Field(default_factory=list)


def draft_to_candidate_profile(draft: CVExtractionDraft) -> CandidateProfile:
    """Map a simplified extraction draft into the full CandidateProfile model."""

    def to_skill(item: DraftSkill) -> Skill:
        return Skill(
            name=item.name.strip() or "Unknown",
            category=item.category,
            proficiency=item.proficiency,
            years_used=item.years_used,
            evidence=list(item.evidence or []),
            source=FactSource.CV,
            confidence=1.0,
        )

    employment = [
        Employment(
            company=(e.company or "").strip() or "Unknown",
            title=(e.title or "").strip() or "Unknown",
            start_date=e.start_date,
            end_date=e.end_date,
            is_current=e.is_current,
            location=e.location,
            responsibilities=list(e.responsibilities or []),
            achievements=list(e.achievements or []),
            technologies=list(e.technologies or []),
            reason_for_leaving=e.reason_for_leaving,
            source=FactSource.CV,
            confidence=1.0,
        )
        for e in draft.employment_history
        if (e.company or e.title)
    ]

    projects = [
        Project(
            name=(p.name or "").strip() or "Untitled project",
            description=p.description,
            role=p.role,
            company=p.company,
            technologies=list(p.technologies or []),
            outcomes=list(p.outcomes or []),
            challenges=list(p.challenges or []),
            duration=p.duration,
            team_size=p.team_size,
            source=FactSource.CV,
            confidence=1.0,
        )
        for p in draft.projects
        if (p.name or p.description)
    ]

    education = [
        Education(
            institution=(ed.institution or "").strip() or "Unknown",
            degree=ed.degree,
            field=ed.field,
            graduation_date=ed.graduation_date,
            gpa=ed.gpa,
            honors=list(ed.honors or []),
            source=FactSource.CV,
            confidence=1.0,
        )
        for ed in draft.education
        if ed.institution
    ]

    certifications = [
        Certification(
            name=(c.name or "").strip() or "Unknown",
            issuer=c.issuer,
            obtained_date=c.obtained_date,
            expiry_date=c.expiry_date,
            credential_id=c.credential_id,
            source=FactSource.CV,
            confidence=1.0,
        )
        for c in draft.certifications
        if c.name
    ]

    achievements = [
        VerifiedFact(
            fact=a.fact.strip(),
            source=FactSource.CV,
            source_section=a.source_section,
            confidence=1.0,
        )
        for a in draft.achievements
        if a.fact and a.fact.strip()
    ]

    transitions = [
        CareerTransition(
            from_role=(t.from_role or "").strip() or "Unknown",
            to_role=(t.to_role or "").strip() or "Unknown",
            reason=t.reason,
            year=t.year,
            source=FactSource.CV,
        )
        for t in draft.career_transitions
        if t.from_role or t.to_role
    ]

    personal = draft.personal_profile or DraftPersonal()
    summary = draft.professional_summary or DraftSummary()

    return CandidateProfile(
        personal_profile=PersonalProfile(
            full_name=personal.full_name,
            email=personal.email,
            phone=personal.phone,
            location=personal.location,
            nationality=personal.nationality,
            linkedin=personal.linkedin,
            github=personal.github,
            portfolio=personal.portfolio,
            languages=list(personal.languages or []),
            personal_summary=personal.personal_summary,
        ),
        professional_summary=ProfessionalSummary(
            summary=summary.summary,
            years_of_experience=summary.years_of_experience,
            current_role=summary.current_role,
            specializations=list(summary.specializations or []),
        ),
        education=education,
        certifications=certifications,
        employment_history=employment,
        projects=projects,
        technical_skills=[to_skill(s) for s in draft.technical_skills if s.name],
        management_skills=[to_skill(s) for s in draft.management_skills if s.name],
        soft_skills=[to_skill(s) for s in draft.soft_skills if s.name],
        achievements=achievements,
        career_transitions=transitions,
        topics_to_avoid=list(draft.topics_to_avoid or []),
    )
