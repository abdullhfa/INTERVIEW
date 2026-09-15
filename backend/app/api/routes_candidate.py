"""
AI Interview Coach - Candidate API Routes

Handles CV upload, profile extraction, verification, and target role management.
"""

from __future__ import annotations
import asyncio
import logging
import time
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional

from app.models.candidate import (
    CandidateProfile,
    ProfileExtractionResult,
    TargetRole,
    TargetRoleRequest,
    ExpectedQuestionsRequest,
)
from app.services.document_parser import document_parser
from app.services.candidate_profile import candidate_profile_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload-cv", response_model=ProfileExtractionResult)
async def upload_cv(file: UploadFile = File(...)):
    """
    Upload a CV document (PDF, DOCX, TXT, MD).
    Returns extracted profile for user review — NOT yet verified.
    """
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(400, "Empty file")

    parse_start = time.perf_counter()
    try:
        loop = asyncio.get_running_loop()
        parsed = await loop.run_in_executor(
            None, document_parser.parse, contents, file.filename
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Document parse failed for %s", file.filename)
        raise HTTPException(400, f"تعذر قراءة الملف: {e}") from e
    parse_ms = (time.perf_counter() - parse_start) * 1000

    if not parsed.raw_text.strip():
        raise HTTPException(400, "No text could be extracted from the document")

    extract_start = time.perf_counter()
    try:
        result = await candidate_profile_service.extract_from_document(
            parsed.raw_text, file.filename
        )
    except ValueError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        logger.exception("CV extraction failed for %s", file.filename)
        raise HTTPException(
            500,
            f"تعذر تحليل السيرة الذاتية: {e}",
        ) from e
    extract_ms = (time.perf_counter() - extract_start) * 1000
    logger.info(
        "CV_UPLOAD_DONE filename=%s parse_ms=%.0f extract_ms=%.0f chars=%s",
        file.filename,
        parse_ms,
        extract_ms,
        len(parsed.raw_text),
    )

    # Add document parser warnings
    result.warnings.extend(parsed.warnings)

    return result


@router.get("/cv-enrichment/{job_id}")
async def get_cv_enrichment(job_id: str):
    """Poll background full CV extraction after the fast essentials pass."""
    status = await candidate_profile_service.get_enrichment_status(job_id)
    if status is None:
        raise HTTPException(404, "Enrichment job not found")
    return status


@router.post("/verify-profile", response_model=CandidateProfile)
async def verify_profile(profile: CandidateProfile):
    """
    Submit a user-reviewed and corrected profile for verification.
    Only after this step does data enter VERIFIED_PROFILE_DATA.
    """
    verified = await candidate_profile_service.verify_and_store(profile)
    return verified


@router.get("/profiles", response_model=list[CandidateProfile])
async def list_profiles():
    """List all stored candidate profiles."""
    return candidate_profile_service.list_profiles()


@router.get("/profiles/{profile_id}", response_model=CandidateProfile)
async def get_profile(profile_id: str):
    """Get a specific candidate profile."""
    profile = candidate_profile_service.get_profile(profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile


@router.post("/profiles/{profile_id}/target-role", response_model=CandidateProfile)
async def add_target_role(profile_id: str, request: TargetRoleRequest):
    """Save the selected field and precise specialization for specialist answers."""
    target_role = TargetRole(
        field=request.field.strip(),
        specialization=request.specialization.strip(),
    )

    try:
        profile = await candidate_profile_service.add_target_role(
            profile_id, target_role
        )
        return profile
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/profiles/{profile_id}/expected-questions", response_model=CandidateProfile)
async def save_expected_questions(profile_id: str, request: ExpectedQuestionsRequest):
    """Save optional expected interview questions and prepared answers."""
    try:
        return await candidate_profile_service.set_expected_questions(
            profile_id, request.items
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/upload-job-description")
async def upload_job_description(
    profile_id: str = Form(...),
    file: UploadFile = File(None),
    text: str = Form(None),
):
    """Upload or paste a job description."""
    if not file and not text:
        raise HTTPException(400, "Provide either a file or text")

    if file:
        contents = await file.read()
        parsed = document_parser.parse(contents, file.filename or "job-description.txt")
        jd_text = parsed.raw_text
    else:
        jd_text = text

    target_role = TargetRole(job_description=jd_text)

    try:
        profile = await candidate_profile_service.add_target_role(
            profile_id, target_role
        )
        return {"status": "success", "profile_id": profile.id}
    except ValueError as e:
        raise HTTPException(404, str(e))
