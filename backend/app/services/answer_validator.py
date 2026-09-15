"""
AI Interview Coach - Answer Validator

Post-generation validation: hallucination check, technical verification,
and fact verification against the Candidate Knowledge Base.
"""

from __future__ import annotations
import logging
from typing import Optional

from app.models.answer import ValidationResult, EvidenceSource
from app.models.candidate import CandidateProfile
from app.services.gemini_gateway import gemini

logger = logging.getLogger(__name__)

VALIDATION_SYSTEM_PROMPT = """\
You are a strict fact-checker for interview answers. Your job is to verify that
a generated answer does not contain fabricated candidate information.

RULES:
1. Any first-person claim about experience, projects, employment, education, or skills
   MUST have supporting evidence in the provided context.
2. General technical knowledge (definitions, explanations) does NOT need evidence.
3. Flag any claim that appears to be invented or inferred without evidence.
4. Check for technical errors in the answer.
5. Return structured validation results."""


class AnswerValidator:
    """Validates generated answers for hallucinations and accuracy."""

    async def validate(
        self,
        answer: str,
        question: str,
        evidence: list[EvidenceSource],
        profile: CandidateProfile,
        requires_candidate_context: bool,
    ) -> ValidationResult:
        """
        Full validation pass on a generated answer.
        Used for important questions where accuracy is critical.
        """
        result = ValidationResult()

        # Quick validation for general knowledge questions
        if not requires_candidate_context:
            result = await self._validate_technical(answer, question)
            return result

        # Full fact verification for candidate-specific answers
        evidence_text = "\n".join(
            f"- [{e.source_type}] {e.fact}" for e in evidence
        ) if evidence else "No evidence provided."

        prompt = f"""Validate this interview answer for factual accuracy.

## Question
"{question}"

## Generated Answer
"{answer}"

## Available Evidence from Candidate Profile
{evidence_text}

## Validation Task
1. Does the answer contain any first-person claims NOT supported by the evidence?
2. Are there any fabricated projects, companies, titles, or achievements?
3. Are there technical errors?
4. Is there missing critical information that the evidence supports?

Return validation results."""

        try:
            validation = await gemini.classify(
                prompt,
                ValidationResult,
                system_instruction=VALIDATION_SYSTEM_PROMPT,
            )
            return validation
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            # Fail closed: do not trust unverified info if service is down
            result.is_valid = False
            result.missing_context = True
            result.missing_context_details = "Validation service unavailable."
            return result

    async def _validate_technical(
        self, answer: str, question: str
    ) -> ValidationResult:
        """Lightweight technical accuracy check."""
        prompt = f"""Validate this technical interview answer for accuracy.
        
Question: "{question}"
Answer: "{answer}"

Rules:
1. Identify technical inaccuracies, misleading simplifications, and falsehoods.
2. Check that an explanation answers the question and describes the mechanism in a logical order.
3. Flag unsupported absolute claims such as "always", "guarantees", or a model "correctly"
   predicting every result. Probabilistic outputs must not be presented as certain.
4. For classification, distinguish output scores or probabilities from guaranteed correctness.
5. Return is_valid=false if a material technical error or misleading claim exists, otherwise true.
6. List each specific issue in technical_errors.
"""
        try:
            validation = await gemini.classify(
                prompt,
                ValidationResult,
                system_instruction="You are an expert technical interviewer verifying facts.",
            )
            return validation
        except Exception as e:
            logger.error(f"Technical validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                missing_context=True,
                missing_context_details="Technical validation unavailable."
            )


# Singleton instance
answer_validator = AnswerValidator()
