"""
AI Interview Coach - Consistency Checker

Maintains the Interview Facts Ledger and checks new answers
against the CV, profile, and all previous session answers.
"""

from __future__ import annotations
import logging
from typing import Optional

from app.models.session import InterviewFactEntry
from app.models.candidate import CandidateProfile
from app.services.gemini_gateway import gemini
from pydantic import BaseModel

class ConsistencyResult(BaseModel):
    is_consistent: bool
    warnings: list[str]

class FactExtractionResult(BaseModel):
    facts: list[str]

logger = logging.getLogger(__name__)


class ConsistencyChecker:
    """Ensures answer consistency throughout an interview session."""

    def add_fact(
        self,
        facts_ledger: list[InterviewFactEntry],
        fact: str,
        question_context: Optional[str] = None,
    ) -> list[InterviewFactEntry]:
        """Add a stated fact to the session ledger."""
        entry = InterviewFactEntry(
            fact=fact,
            question_context=question_context,
        )
        facts_ledger.append(entry)
        return facts_ledger

    async def check_consistency(
        self,
        new_answer: str,
        facts_ledger: list[InterviewFactEntry],
        profile: CandidateProfile,
    ) -> list[str]:
        """
        Check a new answer for semantic contradictions against:
        1. The Interview Facts Ledger (previous session answers)
        2. The candidate profile/CV
        
        Uses Gemini for semantic contradiction detection.
        Returns a list of contradiction warnings.
        """
        if not facts_ledger and not profile.employment_history:
            return []
            
        warnings = []
        
        # Build ledger context
        ledger_text = "\n".join(
            f"- In context of '{e.question_context}': {e.fact}"
            for e in facts_ledger[-10:]  # Only check recent ledger facts to save tokens
        ) if facts_ledger else "No previous facts."
        
        # Build profile context
        profile_text = "\n".join(
            f"- Worked at {emp.company} as {emp.title} ({emp.start_date} to {emp.end_date})"
            for emp in profile.employment_history
        ) if profile.employment_history else "No employment history."
        
        prompt = f"""You are a strict consistency checker. Detect if the candidate's new answer contradicts their CV or previously stated facts.

CV Information:
{profile_text}

Previously Stated Facts:
{ledger_text}

New Answer:
"{new_answer}"

Return is_consistent=false ONLY if there is a clear, semantic contradiction (e.g. said they had 5 years experience previously, now says 10; or said they never used Python, now says they built an app in it).
Provide the warnings describing the exact contradiction.
"""
        try:
            result = await gemini.classify(
                prompt,
                ConsistencyResult,
                system_instruction="You are an expert fact-checker looking for interview consistency issues."
            )
            if not result.is_consistent:
                warnings.extend(result.warnings)
                logger.warning(f"Consistency issues detected: {len(warnings)} warnings")
        except Exception as e:
            logger.error(f"Semantic consistency check failed: {e}")

        return warnings

    def _detect_contradiction(self, new_text: str, previous_fact: str) -> bool:
        # Deprecated: Handled semantically by check_consistency
        return False

    def _check_profile_consistency(
        self, answer: str, profile: CandidateProfile
    ) -> list[str]:
        # Deprecated: Handled semantically by check_consistency
        return []

    async def extract_facts_from_answer(self, answer: str) -> list[str]:
        """
        Extract factual claims from an answer for ledger storage using Gemini.
        """
        if not answer.strip() or len(answer) < 15:
            return []
            
        prompt = f"""Extract all concrete factual claims made in this text regarding experience, skills, roles, projects, or achievements.
Return a list of strings, each being a clear fact. If none, return empty.
Text: "{answer}"
"""
        try:
            result = await gemini.classify(
                prompt,
                FactExtractionResult,
                system_instruction="You extract facts."
            )
            return result.facts
        except Exception as e:
            logger.error(f"Fact extraction failed: {e}")
            return []


# Singleton instance
consistency_checker = ConsistencyChecker()
