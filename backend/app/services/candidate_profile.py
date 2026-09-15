"""
AI Interview Coach - Candidate Profile Service

Extracts structured profiles from raw document text.
Upload returns instantly; LLM enrichment runs in the background.
"""

from __future__ import annotations

from collections import OrderedDict
from hashlib import sha256
import asyncio
import json
import logging
import re
from typing import Optional

from app.models.candidate import (
    CandidateProfile,
    PersonalProfile,
    ProfessionalSummary,
    ProfileExtractionResult,
    Project,
    FactSource,
    TargetRole,
)
from app.models.cv_extraction import (
    CVExtractionDraft,
    CVFastExtractionDraft,
    draft_to_candidate_profile,
)
from app.services.gemini_gateway import gemini, LLMGateway
from app.services.context_retriever import context_retriever
from app.db.repository import repository
from app.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """\
You are an expert CV and resume parser. Extract COMPLETE structured information
from raw document text into a normalized candidate profile.

CRITICAL RULES:
1. Extract ONLY information explicitly stated in the document.
2. NEVER invent, infer, or fabricate any information.
3. If a field is not found, leave it as null or empty.
4. Preserve exact company names, dates, and titles as written.
5. For EACH employment entry, extract responsibilities and achievements — do NOT skip bullets.
6. Detect and preserve both Arabic and English content.
7. Return every item found in the CV.
8. Extract EVERY project into `projects` with name, description, role, company,
   technologies, outcomes, and challenges when stated.
9. For AI/ML projects, preserve exact tool names as written (RAG, LLM, LangChain,
   LangGraph, embeddings, vector database, Chroma, FAISS, agents, OpenAI, Gemini, etc.).
   Do not rename or invent tools.

Output a JSON object matching the provided extraction schema."""

EXTRACTION_PROMPT_TEMPLATE = """\
Extract a COMPLETE structured candidate profile from the following document text.

## Document Text
```
{document_text}
```

Return JSON only."""

FAST_EXTRACTION_SYSTEM_PROMPT = """\
You are a fast CV parser. Extract ONLY essential profile fields.

Rules:
1. Use only facts explicitly stated in the document.
2. Never invent information.
3. Up to 6 recent jobs, 3 responsibilities each.
4. Up to 20 technical skills and 5 certifications.
5. Preserve Arabic and English text as written.

Return valid JSON only."""

FAST_EXTRACTION_PROMPT_TEMPLATE = """\
Extract essential candidate profile fields from this CV text.

## Document Text
```
{document_text}
```

Return JSON only."""

FAST_JSON_SHAPE = """{
  "personal_profile": {"full_name": null, "email": null, "phone": null, "location": null, "linkedin": null},
  "professional_summary": {"summary": null, "years_of_experience": null, "current_role": null},
  "employment_history": [{"company": "", "title": "", "start_date": null, "end_date": null, "responsibilities": []}],
  "education": [{"institution": "", "degree": null, "field": null}],
  "technical_skills": [{"name": ""}],
  "certifications": [{"name": "", "issuer": null}]
}
Notes:
- years_of_experience must be an integer count of years (e.g. 15), never a date range like "2010-present" or "since 2010".
- Fill employment_history and education whenever present in the CV."""


def _fast_cv_excerpt(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit]


def _parse_fast_draft(raw: str) -> CVFastExtractionDraft:
    text = LLMGateway._extract_json(raw.strip())
    try:
        return CVFastExtractionDraft.model_validate_json(text)
    except Exception:
        # Salvage truncated JSON from token-limit responses.
        trimmed = text.rstrip()
        for suffix in ('"}]}', '"]}', ']}', '}'):
            try:
                return CVFastExtractionDraft.model_validate_json(trimmed + suffix)
            except Exception:
                continue
        raise


class CandidateProfileService:
    """Manages candidate profile extraction, verification, and storage."""

    _EXTRACTION_CACHE_SIZE = 16
    _profiles: dict[str, CandidateProfile] = {}

    def __init__(self) -> None:
        self._extraction_cache: OrderedDict[str, ProfileExtractionResult] = OrderedDict()
        self._enrichment_jobs: dict[str, dict] = {}

    async def extract_from_document(
        self, raw_text: str, filename: str
    ) -> ProfileExtractionResult:
        """Extract a complete profile and only return after extraction finishes."""
        logger.info("Extracting profile from document: %s", filename)

        document_text = raw_text[: settings.cv_max_input_chars]
        cache_key = sha256(
            (
                "cv-extraction-v7-full\0"
                + settings.gemini_cv_model
                + "\0"
                + document_text
            ).encode("utf-8")
        ).hexdigest()
        cached = self._get_cached_extraction(cache_key)
        if cached is not None and cached.extraction_status == "complete":
            logger.info("CV_EXTRACTION_CACHE_HIT filename=%s", filename)
            return cached

        import time

        pipeline_start = time.perf_counter()
        try:
            result = await self._extract_full(document_text, filename, raw_text)
            result.extraction_status = "complete"
            result.enrichment_job_id = None
            self._cache_extraction(cache_key, result)
            logger.info(
                "CV_FULL_EXTRACTION_DONE filename=%s total_ms=%.0f",
                filename,
                (time.perf_counter() - pipeline_start) * 1000,
            )
            return result
        except Exception as full_exc:
            logger.warning(
                "Full CV extraction failed for %s; falling back to fast pass: %s",
                filename,
                full_exc,
            )

        excerpt = _fast_cv_excerpt(raw_text, settings.cv_fast_input_chars)
        try:
            result = await self._extract_fast(excerpt, filename, document_text)
            result.extraction_status = "complete"
            result.enrichment_job_id = None
            result.warnings.insert(
                0,
                "تم الاستخراج بوضع سريع بعد تعثر الاستخراج الكامل. راجع الوظائف والتعليم بعناية.",
            )
            self._cache_extraction(cache_key, result)
            logger.info(
                "CV_FAST_FALLBACK_DONE filename=%s total_ms=%.0f",
                filename,
                (time.perf_counter() - pipeline_start) * 1000,
            )
            return result
        except Exception as fast_exc:
            logger.exception("CV extraction failed for %s", filename)
            raise ValueError(
                f"تعذر استخراج السيرة الذاتية بالكامل: {fast_exc}"
            ) from fast_exc

    async def get_enrichment_status(self, job_id: str) -> Optional[dict]:
        job = self._enrichment_jobs.get(job_id)
        if not job:
            return None
        payload = {"status": job["status"], "stage": job.get("stage", "full")}
        if job.get("result") is not None:
            payload["result"] = job["result"].model_dump()
        if job.get("error"):
            payload["error"] = job["error"]
        return payload

    async def _run_enrichment_pipeline(
        self,
        job_id: str,
        document_text: str,
        filename: str,
        raw_text: str,
        cache_key: str,
    ) -> None:
        import time

        pipeline_start = time.perf_counter()
        excerpt = _fast_cv_excerpt(raw_text, settings.cv_fast_input_chars)
        try:
            fast_result = await self._extract_fast(excerpt, filename, document_text)
            fast_result.enrichment_job_id = job_id
            fast_result.extraction_status = "partial"
            fast_result.warnings.insert(
                0,
                "تم استخراج المعلومات الأساسية. جاري إكمال التفاصيل…",
            )
            self._enrichment_jobs[job_id] = {
                "status": "running",
                "stage": "full",
                "result": fast_result,
                "cache_key": cache_key,
                "filename": filename,
            }
            logger.info(
                "CV_FAST_ENRICHMENT_DONE filename=%s latency=%.0fms",
                filename,
                (time.perf_counter() - pipeline_start) * 1000,
            )
        except Exception as exc:
            logger.warning("Background fast CV extraction failed: %s", exc)

        try:
            result = await self._extract_full(document_text, filename, raw_text)
            result.extraction_status = "complete"
            result.enrichment_job_id = job_id
            self._cache_extraction(cache_key, result)
            self._enrichment_jobs[job_id] = {
                "status": "complete",
                "stage": "done",
                "result": result,
                "cache_key": cache_key,
                "filename": filename,
            }
            logger.info(
                "CV_FULL_ENRICHMENT_DONE filename=%s total_ms=%.0f job=%s",
                filename,
                (time.perf_counter() - pipeline_start) * 1000,
                job_id,
            )
        except Exception as exc:
            logger.exception("CV full enrichment failed job=%s: %s", job_id, exc)
            job = self._enrichment_jobs.get(job_id, {})
            self._enrichment_jobs[job_id] = {
                "status": "failed",
                "stage": "done",
                "result": job.get("result"),
                "cache_key": cache_key,
                "filename": filename,
                "error": str(exc),
            }

    async def _extract_fast(
        self,
        fast_text: str,
        filename: str,
        full_document_text: str,
    ) -> ProfileExtractionResult:
        prompt = (
            FAST_EXTRACTION_PROMPT_TEMPLATE.format(document_text=fast_text)
            + "\n\nReturn ONLY valid JSON matching this shape:\n"
            + FAST_JSON_SHAPE
        )
        raw = await gemini.generate_text(
            prompt=prompt,
            system_instruction=FAST_EXTRACTION_SYSTEM_PROMPT,
            model=settings.gemini_cv_model,
            temperature=0.05,
            max_output_tokens=settings.cv_fast_output_tokens,
            timeout_seconds=settings.cv_fast_timeout_seconds,
            json_mode=True,
        )
        draft = _parse_fast_draft(raw)
        full_draft = CVExtractionDraft(
            personal_profile=draft.personal_profile,
            professional_summary=draft.professional_summary,
            employment_history=draft.employment_history,
            education=draft.education,
            technical_skills=draft.technical_skills,
            certifications=draft.certifications,
        )
        profile = draft_to_candidate_profile(full_draft)
        if not self._has_minimum_profile_content(profile):
            raise ValueError("Fast CV extraction returned no usable profile data")

        profile = self._enrich_profile_after_extraction(profile)
        profile.target_roles = []
        return ProfileExtractionResult(
            extracted_profile=profile,
            warnings=self._detect_warnings(profile),
            missing_fields=self._detect_missing_fields(profile),
            contradictions=self._detect_contradictions(profile),
            raw_text=full_document_text[: settings.cv_max_input_chars],
            extraction_status="partial",
        )

    def _heuristic_extraction(
        self, raw_text: str, document_text: str
    ) -> ProfileExtractionResult:
        head = raw_text[:4000]
        lines = [line.strip() for line in head.splitlines() if line.strip()]
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", head)
        phone_match = re.search(r"(?:\+?\d[\d\s\-()]{7,}\d)", head)

        name = None
        for line in lines[:6]:
            if "@" in line or re.search(r"\d{7,}", line):
                continue
            if 2 <= len(line.split()) <= 6 and len(line) <= 80:
                name = line
                break

        profile = CandidateProfile(
            personal_profile=PersonalProfile(
                full_name=name,
                email=email_match.group(0) if email_match else None,
                phone=phone_match.group(0).strip() if phone_match else None,
            ),
            professional_summary=ProfessionalSummary(
                summary=lines[1][:400] if len(lines) > 1 else None,
            ),
        )
        profile = self._enrich_profile_after_extraction(profile)
        profile.target_roles = []
        return ProfileExtractionResult(
            extracted_profile=profile,
            warnings=["تم قراءة الملف — ستُحدَّث التفاصيل تلقائياً."],
            missing_fields=self._detect_missing_fields(profile),
            contradictions=self._detect_contradictions(profile),
            raw_text=document_text[: settings.cv_max_input_chars],
            extraction_status="partial",
        )

    async def _extract_full(
        self,
        document_text: str,
        filename: str,
        raw_text: str,
    ) -> ProfileExtractionResult:
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(document_text=document_text)
        try:
            draft = await gemini.generate_structured(
                prompt=prompt,
                response_schema=CVExtractionDraft,
                system_instruction=EXTRACTION_SYSTEM_PROMPT,
                model=settings.gemini_cv_model,
                temperature=0.1,
                timeout_seconds=settings.gemini_long_request_timeout_seconds,
                max_output_tokens=settings.cv_max_output_tokens,
            )
            profile = draft_to_candidate_profile(draft)
            if not self._has_minimum_profile_content(profile):
                raise ValueError("Full CV extraction returned no usable profile data")
        except Exception as e:
            logger.warning("Full CV extraction failed; trying plain JSON: %s", e)
            profile = await self._extract_via_plain_json(prompt)

        profile = self._enrich_profile_after_extraction(profile)
        profile.target_roles = []
        warnings = self._detect_warnings(profile)
        if len(raw_text) > settings.cv_max_input_chars:
            warnings.append(
                "Document text exceeded the extraction input limit; "
                "some trailing content may be incomplete."
            )
        return ProfileExtractionResult(
            extracted_profile=profile,
            warnings=warnings,
            missing_fields=self._detect_missing_fields(profile),
            contradictions=self._detect_contradictions(profile),
            raw_text=raw_text[: settings.cv_max_input_chars],
            extraction_status="complete",
        )

    async def _extract_via_plain_json(self, prompt: str) -> CandidateProfile:
        raw = await gemini.generate_text(
            prompt=(
                prompt
                + "\n\nReturn ONLY valid JSON matching this shape:\n"
                + json.dumps(CVExtractionDraft().model_dump(), ensure_ascii=False)
            ),
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            model=settings.gemini_cv_model,
            temperature=0.1,
            max_output_tokens=settings.cv_max_output_tokens,
            timeout_seconds=settings.gemini_long_request_timeout_seconds,
            json_mode=True,
        )
        cleaned = LLMGateway._extract_json(raw)
        draft = CVExtractionDraft.model_validate_json(cleaned)
        return draft_to_candidate_profile(draft)

    def clear_extraction_cache(self) -> None:
        self._extraction_cache.clear()
        self._enrichment_jobs.clear()

    def _get_cached_extraction(self, key: str) -> Optional[ProfileExtractionResult]:
        if key not in self._extraction_cache:
            return None
        result = self._extraction_cache.pop(key)
        self._extraction_cache[key] = result
        return result.model_copy(deep=True)

    def _cache_extraction(self, key: str, result: ProfileExtractionResult) -> None:
        self._extraction_cache[key] = result.model_copy(deep=True)
        self._extraction_cache.move_to_end(key)
        while len(self._extraction_cache) > self._EXTRACTION_CACHE_SIZE:
            self._extraction_cache.popitem(last=False)

    @staticmethod
    def _has_minimum_profile_content(profile: CandidateProfile) -> bool:
        return bool(
            profile.personal_profile.full_name
            or profile.professional_summary.summary
            or profile.employment_history
            or profile.education
            or profile.technical_skills
            or profile.certifications
        )

    async def verify_and_store(self, profile: CandidateProfile) -> CandidateProfile:
        profile.is_verified = True
        profile = self._enrich_profile_after_extraction(profile)
        try:
            await context_retriever.index_profile(profile)
        except Exception as e:
            logger.error("Profile indexing failed (continuing verify): %s", e)

        self._profiles[profile.id] = profile
        try:
            await repository.save_profile(profile)
        except Exception as e:
            logger.error("Failed to persist profile to DB: %s", e)

        logger.info("Verified and stored profile %s", profile.id)
        return profile

    @staticmethod
    def _enrich_profile_after_extraction(profile: CandidateProfile) -> CandidateProfile:
        if not profile.projects:
            derived: list[Project] = []
            for emp in profile.employment_history:
                highlights = list(emp.achievements or [])[:6]
                if not highlights and emp.responsibilities:
                    highlights = list(emp.responsibilities)[:4]
                if not highlights:
                    continue
                derived.append(
                    Project(
                        name=f"{emp.title} @ {emp.company}".strip(" @"),
                        description=(
                            f"Key work while {emp.title} at {emp.company}."
                            if emp.title and emp.company
                            else None
                        ),
                        role=emp.title,
                        company=emp.company,
                        technologies=list(emp.technologies or []),
                        outcomes=highlights,
                        source=FactSource.CV,
                        confidence=0.85,
                    )
                )
            profile.projects = derived

        if not profile.target_roles:
            suggested = CandidateProfileService._suggest_target_role(profile)
            if suggested:
                profile.target_roles.append(suggested)
        return profile

    @staticmethod
    def _suggest_target_role(profile: CandidateProfile):
        text_bits = [
            profile.professional_summary.current_role or "",
            profile.professional_summary.summary or "",
            " ".join(profile.professional_summary.specializations or []),
            " ".join(s.name for s in profile.technical_skills[:12]),
        ]
        blob = " ".join(text_bits).casefold()
        field = "Computer Engineering"
        specialization = "Software Engineering"
        matched = False
        rules = [
            (("artificial intelligence", "machine learning", "llm", "generative ai", "langchain", "الذكاء الاصطناعي"),
             "Computer Engineering", "Artificial Intelligence"),
            (("data science", "data engineer", "analytics"),
             "Computer Science", "Data Science"),
            (("cyber", "security", "أمن"),
             "Computer Engineering", "Cybersecurity"),
            (("cloud", "aws", "azure", "devops"),
             "Computer Engineering", "Cloud Computing"),
            (("network", "شبكات"),
             "Computer Engineering", "Computer Networks"),
            (("software", "backend", "frontend", "full stack", "developer"),
             "Computer Science", "Software Development"),
        ]
        for needles, f, s in rules:
            if any(n in blob for n in needles):
                field, specialization = f, s
                matched = True
                break
        if not matched and profile.professional_summary.current_role:
            specialization = profile.professional_summary.current_role.strip()[:120]
        if not any(bit.strip() for bit in text_bits):
            return None
        return TargetRole(field=field, specialization=specialization)

    def get_profile(self, profile_id: str) -> Optional[CandidateProfile]:
        return self._profiles.get(profile_id)

    def list_profiles(self) -> list[CandidateProfile]:
        return list(self._profiles.values())

    async def add_target_role(
        self, profile_id: str, target_role: TargetRole
    ) -> CandidateProfile:
        profile = self._profiles.get(profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")
        profile.target_roles.append(target_role)
        self._profiles[profile.id] = profile
        try:
            await repository.save_profile(profile)
        except Exception as e:
            logger.error("Failed to persist profile to DB: %s", e)
        return profile

    async def set_expected_questions(
        self, profile_id: str, items: list
    ) -> CandidateProfile:
        from datetime import datetime, timezone
        from app.models.candidate import ExpectedQuestion

        profile = self._profiles.get(profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")
        cleaned: list[ExpectedQuestion] = []
        for item in items:
            prompt = str(getattr(item, "prompt", "") or "").strip()
            answer = str(getattr(item, "answer", "") or "").strip()
            item_id = str(getattr(item, "id", "") or "").strip()
            if len(prompt) < 2 or len(answer) < 2:
                continue
            payload: dict = {"prompt": prompt, "answer": answer}
            if item_id:
                payload["id"] = item_id
            cleaned.append(ExpectedQuestion(**payload))
        profile.expected_questions = cleaned
        profile.updated_at = datetime.now(timezone.utc)
        self._profiles[profile.id] = profile
        try:
            await repository.save_profile(profile)
        except Exception as e:
            logger.error("Failed to persist expected questions: %s", e)
        return profile

    def _detect_warnings(self, profile: CandidateProfile) -> list[str]:
        warnings = []
        for emp in profile.employment_history:
            if emp.start_date and emp.end_date and emp.start_date == emp.end_date:
                warnings.append(
                    f"Very short employment at {emp.company}: same start and end date"
                )
        for skill in profile.technical_skills:
            if not skill.evidence and skill.confidence < 0.8:
                warnings.append(
                    f"Low-confidence skill '{skill.name}' has no supporting CV evidence"
                )
        return warnings

    def _detect_missing_fields(self, profile: CandidateProfile) -> list[str]:
        missing = []
        if not profile.personal_profile.full_name:
            missing.append("Full name")
        if not profile.personal_profile.email:
            missing.append("Email address")
        if not profile.employment_history:
            missing.append("Employment history")
        if not profile.education:
            missing.append("Education")
        if not profile.technical_skills:
            missing.append("Technical skills")
        if not profile.professional_summary.summary:
            missing.append("Professional summary")
        return missing

    def _detect_contradictions(self, profile: CandidateProfile) -> list[str]:
        contradictions = []
        sorted_history = sorted(
            [e for e in profile.employment_history if e.start_date],
            key=lambda e: e.start_date or "",
        )
        for i in range(len(sorted_history) - 1):
            current = sorted_history[i]
            next_emp = sorted_history[i + 1]
            if (
                current.end_date
                and next_emp.start_date
                and current.end_date > next_emp.start_date
                and not current.is_current
            ):
                contradictions.append(
                    f"Overlapping dates: {current.company} ends {current.end_date} "
                    f"but {next_emp.company} starts {next_emp.start_date}"
                )
        return contradictions


candidate_profile_service = CandidateProfileService()
