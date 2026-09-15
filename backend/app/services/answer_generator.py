"""
AI Interview Coach - Answer Generator

10-step pipeline from Section 15:
1. Normalize question → 2. Classify → 3. Determine knowledge type →
4. Retrieve context → 5. Check history → 6. Determine strategy →
7. Generate → 8. Hallucination check → 9. Contradiction check →
10. Final answer

CRITICAL: Never invent candidate experience, projects, or facts.
"""

from __future__ import annotations
from collections import OrderedDict
from datetime import datetime, timezone
import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Optional
from pydantic import BaseModel

from app.models.candidate import CandidateProfile, TargetRole, AnswerLengthMode, AnswerLanguageMode
from app.models.question import UtteranceClassification, QuestionCategory
from app.models.answer import (
    AnswerStrategy,
    GeneratedAnswer,
    ConfidenceScores,
    ValidationResult,
    EvidenceSource,
)
from app.services.gemini_gateway import gemini
from app.services.context_retriever import context_retriever
from app.services.answer_validator import answer_validator
from app.services.consistency_checker import consistency_checker
from app.services.question_classifier import (
    is_introduction_question,
    looks_like_follow_up,
    bind_follow_up_question,
)
from app.services.expected_questions import match_expected_question
from app.services.question_bank import BankMatch, question_bank
from app.config import settings

logger = logging.getLogger(__name__)


class BilingualAnswerText(BaseModel):
    """One-call bilingual answer with stable fields for the UI."""

    answer_en: str
    answer_ar: str


ANSWER_SYSTEM_PROMPT = """\
You are an expert interview coach generating answer suggestions for a candidate.

ABSOLUTE RULES:
1. NEVER invent candidate experience, employment, projects, achievements, or certifications.
2. For personal questions, use ONLY the provided candidate context.
3. For specialist questions, use accurate professional knowledge within ONLY the configured
   specialization. Never use the parent field as the answer domain. Never introduce a different
   field or claim candidate experience. If the specialization is Artificial Intelligence, stay
   strictly inside AI/ML.
4. Never say "I implemented..." or "I worked on..." unless that experience exists in the context.
5. Answers must sound like a real candidate speaking in an interview. Easy words. Short sentences.
   Easy to say out loud. For technical definitions cover three beats: what it is, why it is a
   problem, and what you do about it. Keep common English terms like overfitting.
6. Avoid robotic language, empty textbook recitation, and AI-sounding phrases such as "I am passionate about",
   "leverage", "utilize", "facilitate", "robust", "seamless", "in today's world", "furthermore",
   "moreover", "indeed", "delve", "landscape", "paradigm", "holistic", "comprehensive",
   "cutting-edge", "synergy", or "as an AI language model".
7. Avoid unnecessary introductions like "Great question!" or "That's an excellent question."
8. Never invent placeholders such as [Name], [الاسم], YOUR_NAME, <name>, or similar blanks.
   If a CV fact is missing, omit it. If the name is in the candidate context, use that exact name.
9. For STAR behavioral questions, use natural storytelling, NOT labeled sections.
10. Keep answers to the appropriate length mode.
11. Preserve commonly used English technical terms in Arabic answers (e.g., RAG, API, Docker).
12. When writing in English, use easy spoken words (CEFR A2–B1). Prefer: learn, train, data, new,
    old, well, fail, stop, check, score, noise, extra. Keep sentences under 14 words. Do not use
    contractions. Write full forms: I am, I have, I do not. Keep common English terms like
    overfitting. Never use hard words such as underlying, outliers, generalization, practitioner,
    excessively, detect, control, evaluation, regularization.
13. When writing in Arabic, use easy interview Arabic that is simple to say. Keep English terms
    such as overfitting. Do not translate them into hard Arabic like الإفراط في التعلّم. Do not use
    dialect: لما، اللي، شافها، يخليه، يشتغل. Avoid heavy words such as: يتم، يساهم، القيم الشاذة،
    التعميم، بالإضافة إلى ذلك، علاوة على ذلك.
14. Structure English answers cleanly: one idea per sentence, correct grammar and punctuation, and no
    run-on lists that sound machine-generated.
15. Give AI/ML questions extra technical care. Explain the real mechanism, use accepted terms,
    and avoid vague claims such as saying a model simply "understands" because language is complex.
16. When the question asks to explain, clarify, or expand, give a complete explanation: state the
    main idea, describe the mechanism in logical order, give a concrete example, and mention an
    important limitation or condition. Never present a probabilistic model's prediction as guaranteed
    correctness; say it produces scores, probabilities, or a likely prediction when appropriate.
17. If asked for types or categories, state the classification basis and include every standard
    category needed for a complete answer. For AI by capability, include Narrow AI, General AI,
    and Super AI; do not silently omit a category.
18. For project questions, use ONLY listed CV projects/employment. Name real projects and tech.
    If asked whether RAG/LLM/LangChain/agents were used, say yes only when evidenced in the CV.
    When explaining RAG from a project or as a definition, keep the pipeline order accurate:
    ingest → chunk → embed → vector store → retrieve → augment prompt → LLM generate.
19. Never invent that the candidate used RAG, LLM, LangChain, agents, or a vector DB unless those
    appear in the candidate context. Definitions are allowed on specialist questions; personal
    usage claims require CV evidence.
20. If asked whether a program/system at the candidate's current workplace (e.g. Ministry of
    Education) is operational or working now, answer from current CV employment/projects.
    When the CV shows a present role building or maintaining that work, say clearly that yes,
    it is working now. Never refuse this as outside Artificial Intelligence.

ANSWER LENGTH GUIDELINES:
- QUICK: 3 short easy sentences (what it is, why it is a problem, what you do)
- STANDARD: 4-6 sentences, 45-60 seconds spoken
- DETAILED: 8-12 sentences, 60-120 seconds spoken

If candidate context is INSUFFICIENT for a personal question:
- Do NOT fabricate an answer.
- Indicate that more information is needed.
- Set action to INSUFFICIENT_CONTEXT."""

# Shorter system prompt for live coaching — same hard rules, less token overhead.
# Shorter system prompt for live coaching — accurate first, still easy to say.
LIVE_ANSWER_SYSTEM_PROMPT = """\
Easy spoken interview answer. Short words. Easy to say out loud.
Be factually accurate. Answer ONLY the asked question. Do not drift.
Never invent CV facts. Stay in the specialization when it is a specialist question.
Keep English terms like overfitting, RAG, LLM, embeddings.
No contractions. No dialect Arabic.
Do NOT force a "problem / what you do" template on every question.
- Definition: what it is + why it matters + one practical note.
- Project/role: only the asked project facts from CV evidence.
- Yes/no: answer yes/no first, then one short supporting fact.
If writing Arabic: simple formal interview Arabic. Never dialect words such as
لما، اللي، ده، دي، كتير، بيفشل، بشوف، بتاع، بدري، عشان، مش."""


class AnswerGenerator:
    """Generates interview answer suggestions with full validation pipeline."""

    _SPECIALIST_CACHE_SIZE = 128

    _PERSONAL_CATEGORIES = {
        QuestionCategory.INTRODUCTION,
        QuestionCategory.CV_DEEP_DIVE,
        QuestionCategory.BEHAVIORAL,
        QuestionCategory.STAR,
        QuestionCategory.CAREER_MOTIVATION,
        QuestionCategory.LEADERSHIP,
        QuestionCategory.MANAGEMENT,
        QuestionCategory.PROJECT_MANAGEMENT,
        QuestionCategory.COMMUNICATION,
        QuestionCategory.CONFLICT_MANAGEMENT,
        QuestionCategory.SALARY_HR,
    }

    _SPECIALIST_CATEGORIES = {
        QuestionCategory.TECHNICAL,
        QuestionCategory.AI_ML,
    }

    _PERSONAL_QUESTION_MARKERS = (
        "tell me about yourself", "introduce yourself", "your background",
        "speak about yourself", "speak for yourself", "talk about yourself",
        "your name", "what is your name", "what's your name", "whats your name",
        "your experience", "your previous experience", "your work experience",
        "your work history", "years of experience", "work experience",
        "your previous role", "your previous job", "your current job",
        "your current role", "where you work", "where do you work",
        "where you worked", "what you did", "what did you do", "what you do",
        "what do you do", "in the past", "your company", "your companies",
        "your employer", "your employers", "your certifications",
        "your certificates", "your courses", "your education", "your degree",
        "your projects", "your project", "projects you worked",
        "projects you have", "project you worked", "project you built",
        "tell me about a project", "walk me through a project",
        "walk me through your project", "describe your project",
        "your achievements", "your skills", "your resume",
        "your cv", "tell me about your", "walk me through your",
        "did you use", "have you used", "have you worked with",
        "did you work with", "did you apply", "have you applied",
        "تحدث عن نفسك", "حدثني عن نفسك", "تكلم عن نفسك", "احكي عن نفسك",
        "عرفني بنفسك", "عرف عن نفسك", "أخبرني عن نفسك",
        "ما اسمك", "شو اسمك", "ايش اسمك", "إيش اسمك", "اسمك",
        "خبراتك", "خبرتك", "خبرتك العملية", "خبرتك المهنية",
        "اعمالك السابقة", "أعمالك السابقة",
        "وظائفك السابقة", "عملك السابق", "عملك الحالي",
        "وين تشتغل", "أين تعمل", "وين اشتغلت", "أين عملت",
        "شو اشتغلت", "ماذا عملت", "شو بتشتغل", "ماذا تعمل",
        "في الماضي", "سيرتك", "السيرة الذاتية",
        "الدورات التي لديك", "دوراتك",
        "شهاداتك", "مؤهلاتك", "تعليمك", "دراستك",
        "مشاريعك", "المشاريع", "مشروعك", "مشاريع",
        "إنجازاتك", "انجازاتك", "مهاراتك",
        "هل استخدمت", "هل استعملت", "هل طبقت", "هل اشتغلت",
        "استخدمت", "استعملت", "طبقت",
    )

    # Strong project-interview detection (English + Arabic).
    _PROJECT_QUESTION_MARKERS = (
        "your projects", "your project", "projects you", "project you",
        "a project you", "one of your projects", "tell me about a project",
        "walk me through a project", "walk me through your project",
        "describe your project", "describe a project", "project walkthrough",
        "what projects", "which projects", "notable projects",
        "side project", "portfolio project",
        "مشاريعك", "المشاريع", "مشروعك", "مشاريع",
        "شو المشاريع", "ما المشاريع", "اي مشاريع", "أي مشاريع",
        "اشرح مشروع", "حدثني عن مشروع", "احكي عن مشروع",
        "تحدث عن مشروع", "وصف مشروع", "مشاريع اللي", "المشاريع اللي",
        "في مشاريعك", "في احد مشاريعك", "في إحدى مشاريعك",
        "في احدى مشاريعك", "من مشاريعك",
    )

    _PROJECT_ROLE_QUESTION_MARKERS = (
        "your role in", "role in the project", "what was your role",
        "what is your role in", "what were your tasks", "your tasks in",
        "your responsibilities in", "what did you do in the project",
        "what did you do on the project", "your duties in",
        "دورك", "شو دورك", "ما دورك", "ايش دورك", "إيش دورك",
        "مهامك", "مسؤولياتك", "شو عملت في المشروع", "ماذا عملت في المشروع",
        "دورك في المشروع", "في هذا المشروع",
    )

    # "Did you use RAG / LLM / LangChain in a project?" needs CV grounding.
    _CV_TECH_USAGE_VERBS = (
        "did you use", "have you used", "did you apply", "have you applied",
        "did you work with", "have you worked with", "did you implement",
        "have you implemented", "did you build", "have you built",
        "experience with", "used in your", "in your project", "in your projects",
        "هل استخدمت", "هل استعملت", "هل طبقت", "هل اشتغلت",
        "استخدمت", "استعملت", "طبقت", "في مشروع", "في مشاريع",
        "في مشاريعك", "في احد مشاريعك", "في إحدى مشاريعك",
        "في احدى مشاريعك",
    )
    _CV_TECH_USAGE_TOPICS = (
        "rag", "retrieval augmented", "retrieval-augmented",
        "llm", "llms", "large language model", "langchain", "langgraph",
        "langsmith", "agentic", "ai agent", "agents", "vector database",
        "vector db", "embedding", "embeddings", "chroma", "faiss",
        "pinecone", "weaviate", "openai", "gemini", "deepseek",
        "transformer", "fine-tuning", "fine tuning", "prompt engineering",
        "الذكاء الاصطناعي", "تعلم الآلة",
    )

    # Second-person + career topic → treat as CV/personal even if phrasing varies.
    _PERSONAL_YOU_MARKERS = (
        "you ", "your ", "you're", "youre", "yourself",
        "أنت", "انت", "عندك", "لك ", "بنفسك", "عنك",
    )
    _PERSONAL_TOPIC_MARKERS = (
        "work", "job", "role", "company", "employer", "experience", "career",
        "background", "project", "education", "degree", "course", "certificat",
        "skill", "resume", "cv", "past", "previous", "current", "employ",
        "عمل", "شغل", "وظيفة", "شركة", "خبرة", "مشروع", "مشاريع", "دراسة", "شهادة",
        "مهارة", "سيرة", "ماضي", "سابق", "حالي",
    )

    # Status of the candidate's real workplace systems / programs.
    _WORK_STATUS_MARKERS = (
        "operational", "in production", "in use", "currently running",
        "still running", "is it working", "does it work", "is the program",
        "is the system", "is the tool", "is the solution", "currently operational",
        "working now", "works now", "live in", "deployed at", "deployed in",
        "يعمل", "شغال", "شغّال", "قيد التشغيل", "مستخدم حاليا",
        "هل يعمل", "هل البرنامج", "هل النظام", "هل الأداة", "هل الحل",
        "يعمل الان", "يعمل الآن", "ما زال يعمل", "مازال يعمل",
    )
    _WORKPLACE_STATUS_MARKERS = (
        "ministry", "ministry of education", "at the ministry", "moe",
        "department of education", "at work", "at the company", "in production",
        "وزارة", "وزارة التربية", "الوزارة", "في العمل", "في الشركة",
        "في الوزارة", "لدى الوزارة",
    )

    _EXPLANATION_REQUEST_MARKERS = (
        "explain", "clarify", "expand on", "elaborate", "walk me through",
        "describe how", "break down", "in more detail", "further detail",
        "اشرح", "وضح", "وضّح", "فسر", "فسّر", "بيّن", "بين لي",
        "بالتفصيل", "بشكل أوضح", "بشكل اوضح", "اشرح أكثر", "اشرح اكثر",
    )

    def __init__(self) -> None:
        # Cache only context-free specialist answers. Personal and follow-up
        # answers must always be rebuilt from the current interview state.
        self._specialist_answer_cache: OrderedDict[
            tuple[str, ...], tuple[str, Optional[str]]
        ] = OrderedDict()
        # Live observability (read by live_audio after generate).
        self._last_bank_lookup_ms: float = 0.0
        self._last_answer_source: str = "deepseek"

    async def generate(
        self,
        classification: UtteranceClassification,
        profile: CandidateProfile,
        conversation_history: list[dict],
        *,
        question_id: str = "",
        target_role_id: Optional[str] = None,
        length_mode: AnswerLengthMode = AnswerLengthMode.STANDARD,
        language_mode: AnswerLanguageMode = AnswerLanguageMode.ANSWER_IN_QUESTION_LANGUAGE,
        prefer_speed: bool = False,
        on_partial: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> GeneratedAnswer:
        """
        Full 10-step answer generation pipeline.

        prefer_speed: live coaching path — skip extra Gemini validation /
        consistency round-trips so the answer appears as soon as generation finishes.
        """
        start_time = time.perf_counter()
        self._last_bank_lookup_ms = 0.0
        self._last_answer_source = "deepseek"
        asked = (classification.raw_utterance or classification.normalized_question or "").strip()
        question = classification.normalized_question or asked

        prepared = match_expected_question(
            question, getattr(profile, "expected_questions", None) or []
        )
        if prepared is None and asked:
            prepared = match_expected_question(
                asked, profile.expected_questions or []
            )
        if prepared is not None:
            logger.info(
                "Using prepared expected-question answer score=%.2f reason=%s",
                prepared.score,
                prepared.reason,
            )
            self._last_answer_source = "bank"
            return self._answer_from_prepared(
                question=question,
                asked=classification.raw_utterance or question,
                prepared_text=prepared.item.answer,
                question_id=question_id,
                length_mode=length_mode,
            )

        # Prepared question bank (CV / personal / senior-AI technical).
        bank_match: Optional[BankMatch] = None
        reference_answer: Optional[str] = None
        if settings.question_bank_enabled:
            bank_t0 = time.perf_counter()
            bank_match = await self._match_question_bank(asked or question, conversation_history)
            self._last_bank_lookup_ms = (time.perf_counter() - bank_t0) * 1000
            logger.info(
                "bank_lookup_ms=%.0f strong=%s",
                self._last_bank_lookup_ms,
                bool(bank_match is not None and bank_match.is_strong),
            )
        if bank_match is not None:
            question_bank.remember(asked or question, bank_match.entry.id)
            logger.info(
                "Question bank %s match id=%s score=%.2f (sem=%.2f lex=%.2f) runner_up=%s",
                bank_match.mode, bank_match.entry.id, bank_match.score,
                bank_match.semantic, bank_match.lexical, bank_match.runner_up,
            )
            reference_answer = bank_match.entry.answer_en

        # Track B: if detector says compound/uncertain, try multi-intent BEFORE
        # returning a strong single-intent bank answer (so all parts get covered).
        if settings.question_bank_enabled:
            compound_answer = await self._maybe_compound_answer(
                asked or question,
                conversation_history=conversation_history,
                question=question,
                asked=classification.raw_utterance or question,
                question_id=question_id,
                length_mode=length_mode,
                start_time=start_time,
            )
            if compound_answer is not None:
                self._last_answer_source = "bank"
                return compound_answer

        if bank_match is not None and bank_match.is_strong:
            self._last_answer_source = "bank"
            return self._answer_from_bank(
                match=bank_match,
                question=question,
                asked=classification.raw_utterance or question,
                question_id=question_id,
                length_mode=length_mode,
                elapsed_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Step 1-2: Already done by classifier (normalize + classify)

        # Step 3: Determine knowledge type
        is_introduction = is_introduction_question(question)
        # Self-introductions and CV biography questions must stay factual and stable.
        # Keep them concise and spoken — never a full CV dump — while still
        # respecting the user's length mode.
        requires_candidate_context = is_introduction or self._is_personal_question(
            question, classification
        ) or self._is_work_status_question(question, profile)
        deterministic_introduction = is_introduction or (
            requires_candidate_context
            and self._is_cv_biography_question(question)
        )
        explanation_request = self._is_explanation_request(question)
        # Live coaching: keep QUICK truly quick. Offline/high-quality path may
        # still bump explanation requests up to STANDARD depth.
        generation_length_mode = (
            AnswerLengthMode.STANDARD
            if explanation_request and length_mode == AnswerLengthMode.QUICK and not prefer_speed
            else length_mode
        )
        target_role = self._select_target_role(profile, target_role_id)
        if (
            self._is_ai_specialization(target_role)
            and not requires_candidate_context
            and not deterministic_introduction
        ):
            classification = classification.model_copy(
                update={"category": QuestionCategory.AI_ML}
            )
        is_project_question = (
            self._is_project_question(question)
            or self._is_project_role_question(question)
            or (requires_candidate_context and self._is_cv_tech_usage_question(question))
        )
        # Role-in-project follow-ups must stay on the project walkthrough path,
        # not a full career narrative.
        if (
            not is_project_question
            and requires_candidate_context
            and (
                classification.is_follow_up
                or looks_like_follow_up(asked or question, conversation_history)
            )
            and self._history_mentions_project(conversation_history)
        ):
            if self._is_project_role_question(question) or "project" in question.casefold() or "مشروع" in question:
                is_project_question = True
        strategy = self._determine_strategy(
            classification,
            requires_candidate_context,
            is_introduction=deterministic_introduction,
            is_project_question=is_project_question,
        )

        # Step 4: Retrieve relevant candidate knowledge
        evidence = []
        retrieval_start = time.perf_counter()
        if deterministic_introduction or requires_candidate_context:
            # Personal / CV questions always get full profile evidence so the
            # model cannot invent a generic career story.
            evidence = self._build_introduction_evidence(profile)
            if is_project_question and not deterministic_introduction:
                project_evidence = self._build_project_focused_evidence(
                    profile, question, conversation_history
                )
                if project_evidence:
                    evidence = project_evidence
            if not deterministic_introduction and prefer_speed:
                # Keep keyword hits as extra cues, but never as the only source.
                # For role-in-project answers, do not re-attach unrelated jobs.
                if not (
                    is_project_question
                    and self._is_project_role_question(question)
                ):
                    keyword_hits = self._build_fast_local_evidence(
                        profile, question, n_results=4
                    )
                    seen = {e.fact for e in evidence}
                    for hit in keyword_hits:
                        if hit.fact not in seen:
                            evidence.append(hit)
            elif not deterministic_introduction and not prefer_speed:
                chroma_hits = await context_retriever.retrieve(
                    query=question,
                    candidate_id=profile.id,
                    n_results=5,
                )
                if is_project_question and self._is_project_role_question(question):
                    chroma_hits = [
                        hit for hit in chroma_hits
                        if hit.source_type in {"project", "employment"}
                    ][:3]
                seen = {e.fact for e in evidence}
                for hit in chroma_hits:
                    if hit.fact not in seen:
                        evidence.append(hit)
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

        # Step 5: Previous Q&A only when this turn depends on it. Standalone
        # specialist questions must not inherit an unrelated earlier topic.
        is_follow_up = (classification.is_follow_up) or (
            not is_introduction
            and looks_like_follow_up(asked or question, conversation_history)
        )
        if is_follow_up and not classification.is_follow_up:
            classification = classification.model_copy(update={"is_follow_up": True})
        include_history = bool(conversation_history) and not deterministic_introduction and is_follow_up
        history_context = (
            self._format_history(
                conversation_history,
                include_candidate_answers=requires_candidate_context,
                include_suggested_answers=True,
                max_entries=2 if prefer_speed else 4,
            )
            if include_history
            else ""
        )
        prompt_question = question
        if is_follow_up:
            prompt_question = bind_follow_up_question(asked or question, conversation_history)
            logger.info(
                "FOLLOW_UP using previous turn in prompt (history_entries=%s)",
                len(conversation_history or []),
            )

        # Step 6: Strategy already determined above

        # Step 7: Generate answer
        prompt = self._build_prompt(
            question=prompt_question,
            classification=classification,
            profile=profile,
            evidence=evidence,
            history=history_context,
            strategy=strategy,
            length_mode=generation_length_mode,
            language_mode=language_mode,
            requires_candidate_context=requires_candidate_context,
            target_role=target_role,
            compact=prefer_speed,
            reference_answer=reference_answer,
        )

        try:
            generation_start = time.perf_counter()
            cache_key = self._specialist_cache_key(
                question=question,
                classification=classification,
                target_role=target_role,
                length_mode=generation_length_mode,
                language_mode=language_mode,
                requires_candidate_context=requires_candidate_context,
            )
            cached_answer = self._get_cached_specialist_answer(cache_key)
            cache_hit = cached_answer is not None
            answer_ar: Optional[str] = None
            # Live path: slightly tighter budgets so the first paint arrives sooner
            # without starving a complete spoken answer.
            if prefer_speed:
                max_output_tokens = {
                    AnswerLengthMode.QUICK: 180,
                    AnswerLengthMode.STANDARD: 280,
                    AnswerLengthMode.DETAILED: 400,
                }[generation_length_mode]
            else:
                max_output_tokens = {
                    AnswerLengthMode.QUICK: 384,
                    AnswerLengthMode.STANDARD: 720,
                    AnswerLengthMode.DETAILED: 1200,
                }[generation_length_mode]
            system_prompt = (
                LIVE_ANSWER_SYSTEM_PROMPT if prefer_speed else ANSWER_SYSTEM_PROMPT
            )
            gen_temperature = 0.15 if prefer_speed else 0.25
            if prefer_speed and requires_candidate_context:
                gen_temperature = 0.1
            if prefer_speed and not requires_candidate_context:
                # Specialist definitions need less randomness for accuracy.
                gen_temperature = 0.1
            if deterministic_introduction:
                introduction_en = self._build_english_introduction(
                    profile, generation_length_mode
                )
                introduction_ar = self._build_arabic_introduction(
                    profile, generation_length_mode
                )
                if language_mode == AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH:
                    answer_text = introduction_en
                    answer_ar = introduction_ar
                elif (
                    language_mode == AnswerLanguageMode.ALWAYS_ARABIC
                    or (
                        language_mode == AnswerLanguageMode.ANSWER_IN_QUESTION_LANGUAGE
                        and re.search(r"[\u0600-\u06ff]", question)
                    )
                ):
                    answer_text = introduction_ar
                else:
                    answer_text = introduction_en
                generation_ms = (time.perf_counter() - generation_start) * 1000
            elif cached_answer is not None:
                answer_text, answer_ar = cached_answer
                generation_ms = (time.perf_counter() - generation_start) * 1000
            elif language_mode == AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH:
                if prefer_speed:
                    # First paint: English only (fast). Arabic fills in background
                    # via fill_bilingual_pair after ANSWER_READY.
                    answer_text = await self._complete_answer_text(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        max_output_tokens=max_output_tokens,
                        gen_temperature=gen_temperature,
                        prefer_speed=True,
                        on_partial=on_partial,
                    )
                    answer_ar = None
                else:
                    bilingual = await gemini.generate_structured(
                        prompt,
                        BilingualAnswerText,
                        system_instruction=system_prompt,
                        model=settings.gemini_answer_model,
                        temperature=0.3,
                        max_output_tokens=max_output_tokens * 2,
                    )
                    answer_text = bilingual.answer_en.strip()
                    answer_ar = bilingual.answer_ar.strip()
                generation_ms = (time.perf_counter() - generation_start) * 1000
            else:
                answer_text = await self._complete_answer_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_output_tokens=max_output_tokens,
                    gen_temperature=gen_temperature,
                    prefer_speed=prefer_speed,
                    on_partial=on_partial,
                )
                generation_ms = (time.perf_counter() - generation_start) * 1000
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return self._error_answer(question, str(e))

        # If the model invented blank placeholders, fall back to the CV intro builder.
        if (
            not deterministic_introduction
            and requires_candidate_context
            and self._contains_cv_placeholders(answer_text, answer_ar)
        ):
            logger.warning(
                "Replacing placeholder CV answer with deterministic introduction"
            )
            introduction_en = self._build_english_introduction(
                profile, generation_length_mode
            )
            introduction_ar = self._build_arabic_introduction(
                profile, generation_length_mode
            )
            if language_mode == AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH:
                answer_text = introduction_en
                answer_ar = introduction_ar
            elif (
                language_mode == AnswerLanguageMode.ALWAYS_ARABIC
                or (
                    language_mode == AnswerLanguageMode.ANSWER_IN_QUESTION_LANGUAGE
                    and re.search(r"[\u0600-\u06ff]", question)
                )
            ):
                answer_text = introduction_ar
                answer_ar = None
            else:
                answer_text = introduction_en
                answer_ar = None

        # Step 8: Hallucination check
        validation_start = time.perf_counter()
        validation_text = (
            f"English: {answer_text}\nArabic: {answer_ar}"
            if answer_ar
            else answer_text
        )
        if deterministic_introduction or prefer_speed:
            # Live coaching: never block the UI on missing-evidence gates.
            # Mark soft warnings on the validation object instead.
            validation = ValidationResult(is_valid=True)
            if requires_candidate_context and not evidence and not deterministic_introduction:
                validation.missing_context = True
                validation.missing_context_details = "insufficient_candidate_evidence"
        else:
            validation = await self._validate_answer(
                answer=validation_text,
                question=question,
                evidence=evidence,
                profile=profile,
                requires_candidate_context=requires_candidate_context,
                force_technical_validation=explanation_request,
            )
        validation_ms = (time.perf_counter() - validation_start) * 1000

        if cache_key is not None and validation.is_valid and not cache_hit:
            self._cache_specialist_answer(cache_key, answer_text, answer_ar)

        # Step 9: Contradiction check against conversation history
        if (
            not prefer_speed
            and requires_candidate_context
            and conversation_history
        ):
            contradictions = await self._check_contradictions(
                validation_text, conversation_history, profile
            )
            if contradictions:
                validation.consistency_warning = True
                validation.contradictions = contradictions

        # Step 10: Build final answer
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "ANSWER_PIPELINE retrieval=%.1fms generation=%.1fms validation=%.1fms total=%.1fms cache_hit=%s",
            retrieval_ms,
            generation_ms,
            validation_ms,
            elapsed_ms,
            cache_hit,
        )

        # Calculate confidence
        confidence = ConfidenceScores(
            question_confidence=classification.confidence,
            context_confidence=self._calc_context_confidence(evidence, requires_candidate_context),
            answer_confidence=0.9 if validation.is_valid else 0.5,
            technical_confidence=0.85,
        )

        return GeneratedAnswer(
            question_id=question_id,
            question=classification.raw_utterance,
            normalized_question=question,
            answer_en=answer_text,
            answer_ar=answer_ar,
            strategy=strategy,
            length_mode=length_mode,
            confidence=confidence,
            validation=validation,
            candidate_evidence=evidence,
            conversation_context=[
                f"Q: {h.get('text', '')}" for h in conversation_history[-3:]
                if h.get('role') == 'interviewer'
            ],
            action="SHOW_ANSWER" if validation.is_valid else "INSUFFICIENT_CONTEXT",
        )

    def clear_specialist_cache(self) -> None:
        """Clear the bounded answer cache (mainly useful for tests)."""
        self._specialist_answer_cache.clear()

    def _specialist_cache_key(
        self,
        *,
        question: str,
        classification: UtteranceClassification,
        target_role: Optional[TargetRole],
        length_mode: AnswerLengthMode,
        language_mode: AnswerLanguageMode,
        requires_candidate_context: bool,
    ) -> Optional[tuple[str, ...]]:
        if requires_candidate_context or classification.is_follow_up:
            return None

        normalized_question = re.sub(r"\s+", " ", question.casefold()).strip(" ?!.")
        field = (target_role.field if target_role else "") or ""
        specialization = (
            (target_role.specialization or target_role.position)
            if target_role
            else ""
        ) or ""
        category = classification.category.value if classification.category else "GENERAL"
        return (
            "easy-speak-v5-accurate",
            normalized_question,
            field.casefold(),
            specialization.casefold(),
            category,
            length_mode.value,
            language_mode.value,
        )

    def _get_cached_specialist_answer(
        self,
        key: Optional[tuple[str, ...]],
    ) -> Optional[tuple[str, Optional[str]]]:
        if key is None or key not in self._specialist_answer_cache:
            return None
        answer = self._specialist_answer_cache.pop(key)
        self._specialist_answer_cache[key] = answer
        return answer

    def _cache_specialist_answer(
        self,
        key: tuple[str, ...],
        answer_en: str,
        answer_ar: Optional[str],
    ) -> None:
        self._specialist_answer_cache[key] = (answer_en, answer_ar)
        self._specialist_answer_cache.move_to_end(key)
        while len(self._specialist_answer_cache) > self._SPECIALIST_CACHE_SIZE:
            self._specialist_answer_cache.popitem(last=False)

    def _determine_strategy(
        self,
        classification: UtteranceClassification,
        requires_candidate_context: bool = False,
        *,
        is_introduction: bool = False,
        is_project_question: bool = False,
    ) -> AnswerStrategy:
        """Map question category to answer strategy."""
        if is_introduction:
            return AnswerStrategy.PERSONAL_NARRATIVE
        if is_project_question:
            return AnswerStrategy.PROJECT_WALKTHROUGH

        category = classification.category

        strategy_map = {
            QuestionCategory.INTRODUCTION: AnswerStrategy.PERSONAL_NARRATIVE,
            QuestionCategory.CV_DEEP_DIVE: AnswerStrategy.CV_EVIDENCE,
            QuestionCategory.TECHNICAL: AnswerStrategy.TECHNICAL_CONCISE,
            QuestionCategory.ARCHITECTURE: AnswerStrategy.TECHNICAL_DETAILED,
            QuestionCategory.AI_ML: AnswerStrategy.TECHNICAL_DETAILED,
            QuestionCategory.SOFTWARE_ENGINEERING: AnswerStrategy.TECHNICAL_CONCISE,
            QuestionCategory.PROGRAMMING: AnswerStrategy.TECHNICAL_CONCISE,
            QuestionCategory.MANAGEMENT: AnswerStrategy.LEADERSHIP_EXAMPLE,
            QuestionCategory.PROJECT_MANAGEMENT: AnswerStrategy.PROJECT_WALKTHROUGH,
            QuestionCategory.LEADERSHIP: AnswerStrategy.LEADERSHIP_EXAMPLE,
            QuestionCategory.BEHAVIORAL: AnswerStrategy.BEHAVIORAL_STAR,
            QuestionCategory.STAR: AnswerStrategy.BEHAVIORAL_STAR,
            QuestionCategory.PROBLEM_SOLVING: AnswerStrategy.PROBLEM_SOLVING,
            QuestionCategory.SITUATIONAL: AnswerStrategy.PROBLEM_SOLVING,
            QuestionCategory.CAREER_MOTIVATION: AnswerStrategy.CAREER_EXPLANATION,
            QuestionCategory.COMPANY_FIT: AnswerStrategy.COMPANY_FIT,
            QuestionCategory.FOLLOW_UP: AnswerStrategy.FOLLOW_UP_EXPANSION,
        }

        # Project-role follow-ups already handled via is_project_question.
        if classification.is_follow_up and not is_project_question:
            return AnswerStrategy.FOLLOW_UP_EXPANSION

        default_strategy = (
            AnswerStrategy.CV_EVIDENCE
            if requires_candidate_context
            else AnswerStrategy.TECHNICAL_CONCISE
        )
        if category is None:
            return default_strategy

        return strategy_map.get(category, default_strategy)

    async def _complete_answer_text(
        self,
        *,
        prompt: str,
        system_prompt: str,
        max_output_tokens: int,
        gen_temperature: float,
        prefer_speed: bool,
        on_partial: Optional[Callable[[str], Awaitable[None]]],
    ) -> str:
        timeout = (
            min(5.0, settings.gemini_request_timeout_seconds) if prefer_speed else None
        )
        kwargs = {
            "prompt": prompt,
            "system_instruction": system_prompt,
            "model": settings.gemini_answer_model,
            "temperature": gen_temperature,
            "max_output_tokens": max_output_tokens,
            "thinking_budget": None,
            "disable_thinking": True,
            "timeout_seconds": timeout,
            "skip_length_retry": prefer_speed,
        }
        if prefer_speed and on_partial is not None:
            accumulated = ""
            last_emit = 0
            try:
                async for chunk in gemini.generate_text_stream(**kwargs):
                    accumulated = chunk
                    stripped = accumulated.strip()
                    if len(stripped) < 4:
                        continue
                    if (
                        last_emit == 0
                        or len(stripped) - last_emit >= 8
                        or stripped[-1:] in ".!?\n؟"
                    ):
                        last_emit = len(stripped)
                        await on_partial(stripped)
                if accumulated.strip():
                    if last_emit != len(accumulated.strip()):
                        await on_partial(accumulated.strip())
                    return accumulated
            except Exception as exc:
                logger.warning("Streaming generation failed; using full response: %s", exc)
        return await gemini.generate_text(**kwargs)

    def _build_prompt(
        self,
        question: str,
        classification: UtteranceClassification,
        profile: CandidateProfile,
        evidence: list[EvidenceSource],
        history: str,
        strategy: AnswerStrategy,
        length_mode: AnswerLengthMode,
        language_mode: AnswerLanguageMode,
        requires_candidate_context: bool,
        target_role: Optional[TargetRole],
        *,
        compact: bool = False,
        reference_answer: Optional[str] = None,
    ) -> str:
        """Build the full prompt for answer generation."""
        reference_block = (
            "Prepared reference answer (verified facts from the candidate's own preparation). "
            "Use its facts and wording. Adapt it to the exact question asked. "
            "Answer ONLY what was asked: if the question has several parts, answer each part "
            "in order and nothing else; if a part is not covered by the reference or the evidence, "
            "say so plainly instead of guessing. No closing remarks or extra selling points. "
            "Do not add facts that are not in it or in the evidence.\n"
            f"{reference_answer.strip()}"
            if reference_answer and reference_answer.strip()
            else ""
        )
        # Format evidence — keep enough job facts on the live path
        evidence_text = ""
        if evidence:
            evidence_limit = 12 if (compact and requires_candidate_context) else (
                4 if compact else len(evidence)
            )
            evidence_items = []
            for e in evidence[:evidence_limit]:
                evidence_items.append(
                    f"- [{e.source_type}/{e.source_section}] {e.fact}"
                )
            evidence_text = "\n".join(evidence_items)
        elif requires_candidate_context:
            evidence_text = "No specific candidate evidence found."
        else:
            evidence_text = "Not included: this is not a personal question."

        candidate_summary = (
            self._format_candidate_summary(profile, compact=False if requires_candidate_context else compact)
            if requires_candidate_context
            else "Not included: this is not a personal question."
        )
        if (
            requires_candidate_context
            and strategy == AnswerStrategy.PROJECT_WALKTHROUGH
            and self._is_project_role_question(question)
        ):
            candidate_summary = self._format_project_role_summary(profile, evidence)
        target_role_context = (
            "Not included: this is a personal question."
            if requires_candidate_context
            else self._format_target_role(target_role)
        )
        specialization_lock = (
            self._ai_specialization_instruction()
            if (not requires_candidate_context and self._is_ai_specialization(target_role))
            else ""
        )

        if compact:
            lang_line = {
                AnswerLanguageMode.ALWAYS_ENGLISH: "Easy spoken English. Short words.",
                AnswerLanguageMode.ALWAYS_ARABIC: "Easy Arabic. Keep English terms like overfitting.",
                AnswerLanguageMode.ANSWER_IN_QUESTION_LANGUAGE: "Same language as the question. Easy words.",
                AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH: "English only. Easy spoken words.",
            }.get(language_mode, "Same language as the question. Easy words.")
            parts = [
                f"Live answer ({length_mode.value}). {lang_line}",
                f'Q: "{question}"',
            ]
            if requires_candidate_context:
                parts.append(f"Candidate:\n{candidate_summary}")
                parts.append(f"Evidence:\n{evidence_text or 'None.'}")
            else:
                parts.append(f"Specialization:\n{target_role_context}")
            if reference_block:
                parts.append(reference_block)
            if history:
                parts.append(f"Recent conversation:\n{history}")
            if classification.is_follow_up:
                parts.append(
                    "This is a FOLLOW-UP. Continue the previous topic immediately. "
                    "Start with the next fact. Never say the question is open or vague. "
                    "Never pick a new topic."
                )
            if specialization_lock:
                parts.append(specialization_lock.strip())
            if requires_candidate_context:
                parts.append(
                    "Name real companies, titles, dates, duties, and projects from Candidate/Evidence. "
                    "Never give a generic career summary."
                )
                if strategy == AnswerStrategy.PROJECT_WALKTHROUGH:
                    parts.append(self._project_answer_instruction(compact=True))
                if self._is_work_status_question(question, profile):
                    parts.append(
                        "If asked whether the program/system at the current workplace is operational: "
                        "answer Yes, it is working now / نعم يعمل الآن when current CV employment supports it. "
                        "Do not say it is outside AI."
                    )
            if not requires_candidate_context:
                parts.append(
                    "Easy spoken words. Easy to say out loud. Be accurate. "
                    "Answer only this question. Do not force a problem template. "
                    "Keep English terms. No hard words. No personal projects."
                )
                # Follow-ups must stay on the previous topic; injecting the full
                # RAG/LLM/overfitting tip sheet steers the model onto unrelated terms.
                if not classification.is_follow_up:
                    parts.append(self._rag_llm_definition_instruction(compact=True))
            parts.append(
                "Start with the answer. No filler. Keep it short and accurate."
            )
            return "\n\n".join(p for p in parts if p)

        grounding_instruction = (
            "This is a PERSONAL question. Use only the candidate summary and verified CV evidence. "
            "You MUST mention real company names, job titles, locations, projects, and what the candidate did "
            "when the question asks about work, projects, or past experience. "
            "Do not add experience, projects, courses, certifications, or achievements that are not provided. "
            "Never invent a generic career story. "
            "If asked whether a program, system, or tool at the current employer (for example the Ministry "
            "of Education) is operational or working now: answer from current employment and projects. "
            "If the CV shows a current role there building or maintaining that system, answer clearly: "
            "Yes, it is working now / نعم، يعمل الآن. Do not refuse as outside AI specialization."
            if requires_candidate_context else
            "This is a SPECIALIST question. Do not use or mention the candidate CV. "
            "Use accurate professional domain knowledge within ONLY the configured specialization. "
            "Do not treat the parent field as the answer domain. "
            "Do not infer a company, seniority, job description, skills list, or candidate experience. "
            "If the question is outside the specialization, state that briefly and answer only the part "
            "that is directly relevant to the specialization."
        )
        strategy_instruction = (
            "Write a short spoken self-introduction. Use easy words and sound like a real person talking, "
            "not like ChatGPT or a formal CV summary. Cover study place and graduation year, each job "
            "(company, country, how long, title, and what you did), then your courses. Use short clean sentences."
            if strategy == AnswerStrategy.PERSONAL_NARRATIVE
            else (
                self._project_answer_instruction(compact=False)
                if strategy == AnswerStrategy.PROJECT_WALKTHROUGH
                else ""
            )
        )
        ai_ml_instruction = (
            (
                "This is an AI/ML interview question. Start with a direct answer in easy spoken words. "
                "Then say why it matters and how it works. Keep common English terms. "
                "For LLM questions, mention layers, attention, and next-token prediction when relevant, "
                "using easy words. Do not imply that an LLM understands exactly like a human. "
                "Keep the answer natural and respect the selected answer length.\n"
                + self._rag_llm_definition_instruction(compact=False)
            )
            if (
                classification.category == QuestionCategory.AI_ML
                and not requires_candidate_context
            )
            else ""
        )
        follow_up_instruction = (
            "This is a FOLLOW-UP. Resolve references such as 'it', 'that', 'the project', "
            "'the example', or their Arabic equivalents from the most recent interviewer question and "
            "SUGGESTED_ANSWER below. Directly expand the requested point and keep the same "
            "facts. Never reply with a generic explanation of how an example could be broken down. "
            "If asked for your role or tasks in the project: answer only the role and duties for "
            "that same project. Do not switch to a full career summary or list previous jobs."
            if classification.is_follow_up
            else ""
        )
        explanation_instruction = (
            "This is an EXPLANATION request. Give a complete, interview-ready explanation even "
            "when QUICK was selected. Use at least 4-6 connected sentences. First answer the point "
            "directly, then explain the mechanism or steps in logical order, give one concrete "
            "example, and finish with a relevant limitation or condition. Define any essential "
            "technical term in plain language. Avoid unsupported absolutes such as 'always', "
            "'guarantees', or 'correctly'. For classification models, explain that the output layer "
            "produces scores or probabilities and the selected class is a prediction that can be wrong."
            if self._is_explanation_request(question)
            else ""
        )

        # Language instruction
        lang_instruction = {
            AnswerLanguageMode.ALWAYS_ENGLISH: (
                "Speak in easy English (CEFR A2–B1). Short sentences. Easy to say out loud. "
                "Prefer: learn, train, data, new, well, fail, stop, check, score. "
                "Do not use contractions. Write full forms (I am, I have, I do not). "
                "Keep common terms like overfitting. Never use hard words such as underlying, "
                "outliers, generalization, practitioner, excessively, regularization."
            ),
            AnswerLanguageMode.ALWAYS_ARABIC: (
                "Answer in easy formal interview Arabic. Keep English terms like overfitting. "
                "Never use dialect such as لما، اللي، ده، دي، كتير، بيفشل، بشوف، بتاع، بدري، عشان، مش. "
                "Prefer: عندما، هذا، كثيرًا، يفشل، أراجع، أوقف، مبكرًا."
            ),
            AnswerLanguageMode.ANSWER_IN_QUESTION_LANGUAGE: (
                "Answer in the same language as the question. Easy words. Short sentences. "
                "Easy to say out loud. Keep English terms like overfitting. No contractions in English. "
                "No dialect in Arabic (never لما، اللي، ده، كتير، بشوف، بتاع، بدري)."
            ),
            AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH: (
                "Return two versions with the same facts. English: easy spoken words (A2–B1). "
                "Arabic: easy formal interview Arabic, keep English terms, no dialect "
                "(never لما، اللي، ده، كتير، بشوف، بتاع، بدري). No extra facts in one side."
            ),
        }.get(language_mode, "Answer in the same language as the question.")

        return f"""Generate an interview answer suggestion.

## Question
"{question}"

## Question Category
{classification.category or "GENERAL"}

## Answer Strategy
{strategy.value}

## Answer Length
{length_mode.value}

## Language
{lang_instruction}

## Candidate Summary
{candidate_summary}

## Relevant Evidence from Candidate Profile
{evidence_text}

## Prepared Reference Answer
{reference_block or "None."}

## Sole Answer Specialization
{target_role_context}

## Conversation History
{history or "No previous conversation."}

## Instructions
Generate a natural, human-sounding answer that the candidate could speak aloud in an interview.
Sound like a real person talking, not like an AI template, textbook, or LinkedIn post.
Use easy words when the answer is English. Use simple spoken Arabic when the answer is Arabic.
Keep grammar and punctuation fully correct. One clear idea per sentence.
{grounding_instruction}
{specialization_lock}
{strategy_instruction}
{ai_ml_instruction}
{follow_up_instruction}
{explanation_instruction}
Match the answer length to {length_mode.value} mode."""

    def _build_fast_local_evidence(
        self,
        profile: CandidateProfile,
        question: str,
        *,
        n_results: int = 4,
    ) -> list[EvidenceSource]:
        """Keyword evidence from the in-memory profile — no Chroma round-trip."""
        tokens = {
            t for t in re.findall(r"[a-zA-Z\u0600-\u06ff0-9+]{3,}", question.casefold())
        }
        if not tokens:
            tokens = set()

        scored: list[tuple[float, EvidenceSource]] = []

        def consider(fact: str, source_type: str, section: str) -> None:
            text = (fact or "").strip()
            if not text:
                return
            lowered = text.casefold()
            overlap = sum(1 for t in tokens if t in lowered) if tokens else 0
            # Always keep a small baseline so personal answers still have context.
            score = float(overlap) + (0.15 if section in {"Summary", "Current Role"} else 0.0)
            if overlap == 0 and section not in {"Summary", "Current Role", "Recent Employment"}:
                return
            scored.append(
                (
                    score,
                    EvidenceSource(
                        fact=text[:500],
                        source_type=source_type,
                        source_section=section,
                        relevance=round(min(1.0, 0.35 + 0.15 * overlap), 3),
                    ),
                )
            )

        if profile.professional_summary.summary:
            consider(profile.professional_summary.summary, "professional_summary", "Summary")
        if profile.professional_summary.current_role:
            consider(profile.professional_summary.current_role, "professional_summary", "Current Role")

        for emp in profile.employment_history[:5]:
            consider(
                f"{emp.title} at {emp.company}. "
                + "; ".join((emp.achievements or emp.responsibilities or [])[:3]),
                "employment",
                "Recent Employment",
            )
            for tech in (emp.technologies or [])[:8]:
                consider(tech, "employment", emp.company)

        for skill in profile.technical_skills[:20]:
            consider(skill.name, "skill", skill.category or "technical")

        for project in profile.projects[:5]:
            consider(
                AnswerGenerator._format_project_fact(project),
                "project",
                "Projects",
            )
            for tech in (project.technologies or [])[:8]:
                consider(tech, "project", project.name)

        scored.sort(key=lambda item: item[0], reverse=True)
        unique: list[EvidenceSource] = []
        seen: set[str] = set()
        for _, evidence in scored:
            key = evidence.fact.casefold()[:120]
            if key in seen:
                continue
            seen.add(key)
            unique.append(evidence)
            if len(unique) >= n_results:
                break
        return unique

    def _is_explanation_request(self, question: str) -> bool:
        """Detect explicit requests for a fuller explanation in English or Arabic."""
        normalized = " ".join(question.casefold().split())
        return any(
            marker in normalized for marker in self._EXPLANATION_REQUEST_MARKERS
        )

    @staticmethod
    def _contains_cv_placeholders(*texts: Optional[str]) -> bool:
        """Detect invented blanks like [Name] / [الاسم] that must never reach the UI."""
        pattern = re.compile(
            r"\[(?:name|الاسم|full\s*name|your\s*name|candidate)\]"
            r"|<name>|YOUR_NAME|FULL_NAME",
            re.IGNORECASE,
        )
        return any(bool(text and pattern.search(text)) for text in texts)

    def _is_personal_question(
        self,
        question: str,
        classification: UtteranceClassification,
    ) -> bool:
        """Allow CV access for any question about the candidate's own background."""
        normalized = " ".join(question.casefold().split())
        if any(marker in normalized for marker in self._PERSONAL_QUESTION_MARKERS):
            return True
        if self._is_project_question(question):
            return True
        if self._is_cv_tech_usage_question(question):
            return True
        if self._looks_like_personal_cv_question(normalized):
            return True
        if classification.category in self._PERSONAL_CATEGORIES:
            return True
        # Honor the classifier flag, but never force CV into specialist topics.
        if (
            classification.requires_candidate_context
            and classification.category not in self._SPECIALIST_CATEGORIES
        ):
            return True
        return (
            classification.is_follow_up
            and classification.category == QuestionCategory.FOLLOW_UP
            and classification.requires_candidate_context
        )

    @classmethod
    def _is_work_status_question(
        cls,
        question: str,
        profile: Optional[CandidateProfile] = None,
    ) -> bool:
        """True when asking if the candidate's workplace program/system is running."""
        normalized = " ".join(question.casefold().split())
        has_status = any(marker in normalized for marker in cls._WORK_STATUS_MARKERS)
        if not has_status:
            return False
        has_place = any(marker in normalized for marker in cls._WORKPLACE_STATUS_MARKERS)
        if has_place:
            return True
        if profile is None:
            return False
        return cls._question_mentions_cv_employer(normalized, profile)

    @staticmethod
    def _question_mentions_cv_employer(
        normalized_question: str,
        profile: CandidateProfile,
    ) -> bool:
        """Match employer/company names from the CV inside the interviewer question."""
        companies: list[str] = []
        for emp in profile.employment_history:
            if emp.company:
                companies.append(emp.company)
        for project in profile.projects:
            if project.company:
                companies.append(project.company)
        for company in companies:
            cleaned = re.sub(r"[^\w\u0600-\u06ff]+", " ", company.casefold())
            tokens = [t for t in cleaned.split() if len(t) >= 4]
            # Prefer distinctive tokens: ministry, education, najat, knet, etc.
            meaningful = [
                t for t in tokens
                if t not in {
                    "company", "projects", "organization", "educational",
                    "charity", "network", "vending", "jordan", "kuwait",
                }
            ]
            check = meaningful or tokens
            if any(token in normalized_question for token in check):
                return True
            # Also try a short contiguous phrase from the company name.
            phrase = " ".join(tokens[:3])
            if len(phrase) >= 8 and phrase in normalized_question:
                return True
        return False

    @classmethod
    def _is_project_question(cls, question: str) -> bool:
        """True for interview questions that ask about the candidate's projects."""
        normalized = " ".join(question.casefold().split())
        return any(marker in normalized for marker in cls._PROJECT_QUESTION_MARKERS)

    @classmethod
    def _is_project_role_question(cls, question: str) -> bool:
        """True when asking for the candidate's role/tasks inside a project."""
        normalized = " ".join(question.casefold().split())
        return any(marker in normalized for marker in cls._PROJECT_ROLE_QUESTION_MARKERS)

    @staticmethod
    def _history_mentions_project(history: Optional[list[dict]]) -> bool:
        if not history:
            return False
        blob = " ".join(
            str(entry.get("text") or "")
            for entry in history[-6:]
            if entry.get("role") in {"interviewer", "suggested_answer", "candidate"}
        ).casefold()
        return any(
            marker in blob
            for marker in (
                "project", "rag", "llm", "langchain", "similarity", "btec",
                "مشروع", "مشاريع",
            )
        )

    @classmethod
    def _build_project_focused_evidence(
        cls,
        profile: CandidateProfile,
        question: str,
        history: Optional[list[dict]],
    ) -> list[EvidenceSource]:
        """Prefer the project discussed in history over a full career dump."""
        history_blob = " ".join(
            str(entry.get("text") or "")
            for entry in (history or [])[-8:]
            if entry.get("role") in {"interviewer", "suggested_answer", "candidate"}
        ).casefold()
        question_blob = f"{question} {history_blob}".casefold()

        scored: list[tuple[int, EvidenceSource]] = []
        for project in profile.projects:
            fact = cls._format_project_fact(project)
            score = 0
            name = (project.name or "").casefold()
            company = (project.company or "").casefold()
            if name and any(token in question_blob for token in name.split() if len(token) >= 4):
                score += 5
            if company and any(token in question_blob for token in company.split() if len(token) >= 4):
                score += 3
            for tech in project.technologies or []:
                if tech and tech.casefold() in question_blob:
                    score += 2
            if score == 0 and history_blob:
                # Soft keep recent projects when history talked about projects.
                score = 1
            if score <= 0:
                continue
            role_line = project.role or ""
            # Attach matching employment title when company aligns.
            for emp in profile.employment_history:
                emp_company = (emp.company or "").casefold()
                if company and company[:12] in emp_company:
                    role_line = role_line or emp.title
                    duties = "; ".join((emp.responsibilities or [])[:4])
                    if duties:
                        fact = f"{fact}. Employment role: {emp.title}. Duties: {duties}"
                    break
            if role_line and "Role:" not in fact:
                fact = f"Role: {role_line}. {fact}"
            scored.append(
                (
                    score,
                    EvidenceSource(
                        fact=fact,
                        source_type="project",
                        source_section=f"Project - {project.name}",
                        relevance=min(1.0, 0.7 + 0.05 * score),
                    ),
                )
            )

        if not scored:
            return []
        scored.sort(key=lambda item: item[0], reverse=True)
        focused = [item[1] for item in scored[:3]]
        # Keep matching current/recent employment only, not the whole career.
        top_fact = focused[0].fact.casefold()
        for emp in profile.employment_history:
            company = (emp.company or "").casefold()
            if company and any(tok in top_fact for tok in company.split() if len(tok) >= 4):
                details = [
                    f"Role: {emp.title}",
                    f"Company: {emp.company}",
                ]
                if emp.is_current:
                    details.append("Current role")
                if emp.responsibilities:
                    details.append("Tasks: " + "; ".join(emp.responsibilities[:5]))
                if emp.technologies:
                    details.append("Technologies: " + ", ".join(emp.technologies[:8]))
                focused.append(
                    EvidenceSource(
                        fact=". ".join(details),
                        source_type="employment",
                        source_section=f"Employment - {emp.company}",
                        relevance=0.95,
                    )
                )
                break
        return focused

    @classmethod
    def _is_cv_tech_usage_question(cls, question: str) -> bool:
        """True when asking if the candidate used a tech (RAG/LLM/...) in their work."""
        normalized = " ".join(question.casefold().split())
        has_verb = any(marker in normalized for marker in cls._CV_TECH_USAGE_VERBS)
        has_topic = any(marker in normalized for marker in cls._CV_TECH_USAGE_TOPICS)
        return has_verb and has_topic

    @staticmethod
    def _project_answer_instruction(*, compact: bool) -> str:
        """Ground project answers in CV facts with accurate RAG/LLM walkthrough rules."""
        if compact:
            return (
                "PROJECT answer from CV only. Name real projects, role, company, tech, outcomes. "
                "If asked YOUR ROLE / TASKS in the project: answer only that project's title, role, "
                "and duties from Evidence. Do NOT list older jobs or a full career story. "
                "If asked about RAG/LLM/LangChain/agents: say YES only when that tech appears in "
                "Projects/Evidence; otherwise say it is not in the listed projects. "
                "When a project used RAG, explain only evidenced steps: ingest, chunk, embed, "
                "vector store, retrieve, prompt+context, LLM answer. Do not invent tools."
            )
        return (
            "This is a PROJECT walkthrough. Use ONLY projects and employment evidence from the CV. "
            "Structure: (1) project name and goal, (2) your role, (3) tech stack that is listed, "
            "(4) what you built or delivered, (5) outcome/result if listed. "
            "If the question asks specifically for your role or tasks in the project: answer ONLY "
            "the job title/role and the concrete duties for that project from Evidence. "
            "Start with the role. Then list 2-4 tasks. Do NOT mention previous employers, "
            "older jobs, or a career timeline unless the interviewer asked for your full background. "
            "If several projects exist, cover the most relevant ones briefly, then go deeper on one. "
            "If the interviewer asks whether you used RAG, LLM, LangChain, agents, embeddings, or a "
            "vector database: answer YES only when that exact term or a clear synonym appears in the "
            "project technologies, description, outcomes, or employment technologies. "
            "If it is absent, say clearly that it is not listed in your CV projects, and do NOT invent "
            "personal usage. You may add a short accurate definition only after that honest statement. "
            "When a listed project used RAG, explain the pipeline in order with easy words: "
            "ingest documents → chunk text → create embeddings → store in a vector database → "
            "retrieve top matches for the question → put retrieved text into the prompt → "
            "LLM generates the answer → optional citation or evaluation. "
            "Mention only tools and steps supported by the CV (for example LangChain, Chroma, FAISS). "
            "When a listed project used an LLM: say what the model did in that project (chat, "
            "summarize, classify, generate), and keep next-token prediction in simple words. "
            "For agentic AI projects: explain tools/actions only if evidenced. Never invent agents."
        )

    @staticmethod
    def _rag_llm_definition_instruction(*, compact: bool) -> str:
        """Accurate specialist definitions for RAG / LLM / agent questions."""
        if compact:
            return (
                "Be accurate. Match the question. "
                "If RAG: retrieval then generation. Steps: chunk, embed, vector DB, retrieve, "
                "add context to prompt, LLM answers. "
                "If LLM: predicts next token with attention. Not human understanding. "
                "If overfitting: train data fit too well including noise; fails on new data; "
                "check train vs new scores and stop early. "
                "If LangChain/agents: chains or tool-using loops around an LLM. No personal projects."
            )
        return (
            "If asked what RAG is: Retrieval-Augmented Generation means the system first retrieves "
            "relevant documents, then the LLM generates an answer using that context. Cover the "
            "standard pipeline in order: document ingest, chunking, embeddings, vector store, "
            "similarity retrieval, prompt augmentation, LLM generation, and optional grounding/citation. "
            "Say why RAG helps: fresher or private knowledge without full model retraining, and lower "
            "hallucination risk when context is good. Mention a limitation: bad retrieval still hurts answers. "
            "If asked what an LLM is: a large neural language model that predicts the next token using "
            "transformer layers and attention; it does not understand like a human. "
            "If asked about LangChain or agentic AI: LangChain is a framework to connect prompts, "
            "retrievers, tools, and memory around an LLM; an agent decides which tool or step to call "
            "in a loop. Keep definitions accurate. Do not claim personal project usage."
        )


    @classmethod
    def _looks_like_personal_cv_question(cls, normalized: str) -> bool:
        """Catch varied phrasings: 'where you work', 'what you did in the past', etc."""
        has_you = any(marker in normalized for marker in cls._PERSONAL_YOU_MARKERS)
        has_topic = any(marker in normalized for marker in cls._PERSONAL_TOPIC_MARKERS)
        return has_you and has_topic

    @classmethod
    def _is_cv_biography_question(cls, question: str) -> bool:
        """Name/work/education biography questions use the deterministic CV builder.

        Behavioral STAR questions stay on the LLM path with CV evidence, so we
        do not treat every 'you + work' phrase as a full self-introduction.
        """
        if is_introduction_question(question):
            return True
        normalized = " ".join(question.casefold().split())
        biography_markers = (
            "where you work", "where do you work", "where you worked",
            "what you did in", "what did you do", "what do you do at",
            "your companies", "your employers", "your previous jobs",
            "walk me through your experience", "walk me through your cv",
            "walk me through your resume",
            "وين تشتغل", "أين تعمل", "وين اشتغلت", "أين عملت",
            "شو اشتغلت", "ماذا عملت", "شو بتشتغل", "ماذا تعمل",
        )
        # Avoid STAR traps like "tell me about a time you worked under pressure".
        if "a time" in normalized or "time when" in normalized or "مثال" in normalized:
            return False
        return any(marker in normalized for marker in biography_markers)

    @staticmethod
    def _select_target_role(
        profile: CandidateProfile,
        target_role_id: Optional[str],
    ) -> Optional[TargetRole]:
        if target_role_id:
            for role in profile.target_roles:
                if role.id == target_role_id:
                    return role
        return profile.target_roles[-1] if profile.target_roles else None

    @staticmethod
    def _format_target_role(role: Optional[TargetRole]) -> str:
        if not role:
            return "No field or specialization configured. Do not guess either value."

        # Position is a compatibility fallback for profiles saved before the
        # single-specialization flow was introduced. No other role data is used.
        specialization = role.specialization or role.position
        if not specialization:
            return "No field or specialization configured."
        field = role.field or "Not specified"
        lines = [
            f"Primary Field: {field}",
            f"Target Specialization: {specialization}",
        ]
        if AnswerGenerator._is_ai_specialization(role):
            lines.append(
                "Answer domain: Artificial Intelligence ONLY. "
                "Do not use the parent field as the answer domain."
            )
        return "\n".join(lines)

    @staticmethod
    def _is_ai_specialization(role: Optional[TargetRole]) -> bool:
        if role is None:
            return False
        blob = " ".join(
            part for part in (role.specialization, role.position) if part
        ).casefold()
        markers = (
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "generative ai",
            "computer vision",
            "natural language processing",
            "nlp",
            "الذكاء الاصطناعي",
            "تعلم الآلة",
            "التعلم الآلي",
        )
        return any(marker in blob for marker in markers)

    @staticmethod
    def _ai_specialization_instruction() -> str:
        return (
            "Answer only in Artificial Intelligence. Keep common English AI terms. "
            "Explain them with easy words. "
            "Do not drift into cloud, networking, cybersecurity, or general software. "
            "If this is a follow-up, continue the previous AI topic. "
            "Do not invent a new topic. Do not comment on the question.\n"
        )

    def _format_candidate_summary(self, profile: CandidateProfile, *, compact: bool = False) -> str:
        """Create a concise candidate summary for context."""
        parts = []

        if profile.personal_profile.full_name:
            parts.append(f"Name: {profile.personal_profile.full_name}")

        if profile.professional_summary.summary:
            summary = profile.professional_summary.summary
            if compact and len(summary) > 120:
                summary = summary[:117].rstrip() + "..."
            parts.append(f"Summary: {summary}")

        if profile.professional_summary.current_role:
            parts.append(f"Current Role: {profile.professional_summary.current_role}")

        if profile.professional_summary.years_of_experience:
            parts.append(
                f"Verified Experience: {profile.professional_summary.years_of_experience} years"
            )

        edu_limit = 2 if compact else 3
        if profile.education:
            education = "; ".join(
                " in ".join(part for part in (edu.degree, edu.field) if part)
                + (f" from {edu.institution}" if edu.institution else "")
                for edu in profile.education[:edu_limit]
            )
            parts.append(f"Education: {education}")

        emp_limit = 4 if compact else 6
        if profile.employment_history:
            recent = profile.employment_history[:emp_limit]
            emp_bits = []
            for e in recent:
                bit = f"{e.title} at {e.company}"
                if e.location:
                    bit += f" ({e.location})"
                if e.start_date or e.end_date or e.is_current:
                    span = " - ".join(
                        p for p in (
                            e.start_date,
                            "present" if e.is_current else e.end_date,
                        ) if p
                    )
                    if span:
                        bit += f" [{span}]"
                duties = (e.responsibilities or [])[:2]
                if duties:
                    bit += f" — did: {'; '.join(duties)}"
                emp_bits.append(bit)
            parts.append("Employment (use exact names):\n- " + "\n- ".join(emp_bits))

        skill_limit = 4 if compact else 15
        if profile.technical_skills:
            skills = ", ".join(s.name for s in profile.technical_skills[:skill_limit])
            parts.append(f"Key Skills: {skills}")

        if profile.management_skills:
            skills = ", ".join(s.name for s in profile.management_skills[:6])
            parts.append(f"Management Skills: {skills}")

        if profile.certifications:
            certifications = ", ".join(c.name for c in profile.certifications[:5])
            parts.append(f"Certifications: {certifications}")

        project_limit = 3 if compact else 8
        if profile.projects:
            project_bits = []
            for project in profile.projects[:project_limit]:
                project_bits.append(self._format_project_fact(project))
            parts.append(
                "Projects (use exact names; do not invent tech):\n- "
                + "\n- ".join(project_bits)
            )

        return "\n".join(parts) if parts else "No candidate profile available."

    @classmethod
    def _format_project_role_summary(
        cls,
        profile: CandidateProfile,
        evidence: list[EvidenceSource],
    ) -> str:
        """Slim summary for 'what was your role in the project?' answers."""
        parts: list[str] = []
        if profile.personal_profile.full_name:
            parts.append(f"Name: {profile.personal_profile.full_name}")
        project_bits = [
            e.fact for e in evidence if e.source_type in {"project", "employment"}
        ]
        if project_bits:
            parts.append(
                "Focus only on this project evidence (do not invent older jobs):\n- "
                + "\n- ".join(project_bits[:4])
            )
        elif profile.projects:
            parts.append(
                "Projects:\n- "
                + "\n- ".join(cls._format_project_fact(p) for p in profile.projects[:2])
            )
        return "\n".join(parts) if parts else "No project evidence available."

    @staticmethod
    def _format_project_fact(project) -> str:
        """Serialize one CV project for prompt/evidence grounding."""
        details = [f"Name: {project.name}"]
        if project.company:
            details.append(f"Company: {project.company}")
        if project.role:
            details.append(f"Role: {project.role}")
        if project.description:
            details.append(f"Description: {project.description}")
        if project.technologies:
            details.append("Technologies: " + ", ".join(project.technologies))
        if project.outcomes:
            details.append("Outcomes: " + "; ".join(project.outcomes))
        if project.challenges:
            details.append("Challenges: " + "; ".join(project.challenges[:3]))
        if project.duration:
            details.append(f"Duration: {project.duration}")
        return ". ".join(details)

    @staticmethod
    def _build_introduction_evidence(profile: CandidateProfile) -> list[EvidenceSource]:
        """Build complete CV evidence for deterministic self-introductions."""
        evidence: list[EvidenceSource] = []

        identity_parts = []
        if profile.personal_profile.full_name:
            identity_parts.append(f"Name: {profile.personal_profile.full_name}")
        if profile.professional_summary.current_role:
            identity_parts.append(f"Current role: {profile.professional_summary.current_role}")
        if profile.professional_summary.years_of_experience:
            identity_parts.append(
                f"Experience: {profile.professional_summary.years_of_experience} years"
            )
        if identity_parts:
            evidence.append(EvidenceSource(
                fact=". ".join(identity_parts),
                source_type="profile",
                source_section="Professional identity",
                relevance=1.0,
            ))

        for education in profile.education:
            details = [education.degree, education.field, education.institution]
            if education.graduation_date:
                details.append(f"graduated {education.graduation_date}")
            evidence.append(EvidenceSource(
                fact="; ".join(item for item in details if item),
                source_type="education",
                source_section=f"Education - {education.institution}",
                relevance=max(0.9, min(1.0, education.confidence)),
            ))

        for employment in profile.employment_history:
            details = [
                f"Role: {employment.title}",
                f"Company: {employment.company}",
            ]
            if employment.start_date:
                details.append(f"Start: {employment.start_date}")
            if employment.end_date:
                details.append(f"End: {employment.end_date}")
            elif employment.is_current:
                details.append("End: Present")
            if employment.location:
                details.append(f"Location: {employment.location}")
            if employment.responsibilities:
                details.append("Responsibilities: " + "; ".join(employment.responsibilities))
            if employment.achievements:
                details.append("Achievements: " + "; ".join(employment.achievements))
            if employment.technologies:
                details.append("Technologies: " + ", ".join(employment.technologies))
            evidence.append(EvidenceSource(
                fact=". ".join(details),
                source_type="employment",
                source_section=f"Employment - {employment.company}",
                relevance=max(0.9, min(1.0, employment.confidence)),
            ))

        if profile.certifications:
            evidence.append(EvidenceSource(
                fact="Verified certifications: " + ", ".join(
                    certification.name for certification in profile.certifications
                ),
                source_type="certification",
                source_section="Certifications",
                relevance=1.0,
            ))

        if profile.technical_skills:
            evidence.append(EvidenceSource(
                fact="Verified technical skills: " + ", ".join(
                    skill.name for skill in profile.technical_skills
                ),
                source_type="skills",
                source_section="Technical skills",
                relevance=1.0,
            ))

        for project in profile.projects:
            evidence.append(EvidenceSource(
                fact=AnswerGenerator._format_project_fact(project),
                source_type="project",
                source_section=f"Project - {project.name}",
                relevance=max(0.9, min(1.0, project.confidence)),
            ))

        return evidence

    @staticmethod
    def _use_deterministic_english_introduction(
        question: str,
        language_mode: AnswerLanguageMode,
    ) -> bool:
        if language_mode == AnswerLanguageMode.ALWAYS_ENGLISH:
            return True
        if language_mode != AnswerLanguageMode.ANSWER_IN_QUESTION_LANGUAGE:
            return False
        return re.search(r"[\u0600-\u06ff]", question) is None

    @classmethod
    def _build_english_introduction(
        cls,
        profile: CandidateProfile,
        length_mode: AnswerLengthMode,
    ) -> str:
        """
        Easy, human spoken self-introduction covering:
        study place + year, each job (company, country, tenure, title, work), and courses.
        """
        del length_mode
        sentences: list[str] = []
        name = profile.personal_profile.full_name
        years = profile.professional_summary.years_of_experience
        nationality = profile.personal_profile.nationality

        if name:
            sentences.append(f"Hi, my name is {name.title()}.")
        if nationality:
            sentences.append(f"I am {nationality}.")
        if years:
            sentences.append(f"I have worked in IT for about {years} years.")

        # If enrichment has not finished yet, use the CV summary so the intro
        # is not reduced to the candidate's name only.
        if (
            not profile.employment_history
            and not profile.education
            and profile.professional_summary.summary
        ):
            summary = profile.professional_summary.summary.strip()
            if summary:
                sentences.append(summary if summary.endswith(".") else f"{summary}.")

        for education in profile.education:
            if education.field:
                study = education.field
            elif education.degree:
                study = education.degree
            else:
                study = "my field"
            place = education.institution or "university"
            if education.graduation_date:
                sentences.append(
                    f"I studied {study} at {place} and finished in {education.graduation_date}."
                )
            else:
                sentences.append(f"I studied {study} at {place}.")

        jobs = list(reversed(profile.employment_history))
        for job in jobs:
            role = cls._simple_english_role(job.title) or "an IT specialist"
            # Keep role easy: drop heavy "and Engineer" stacking only when redundant.
            company = cls._short_company_name(job.company)
            location = job.location.strip() if job.location else ""
            tenure = cls._employment_tenure(job, arabic=False)
            focus = cls._job_focus(job, arabic=False)

            place_bits = [f"at {company}"]
            if location:
                place_bits.append(f"in {location}")
            place = " ".join(place_bits)

            if job.is_current:
                if tenure:
                    sentences.append(f"Right now I work as a {role} {place}.")
                    sentences.append(f"I have been there for {tenure}.")
                else:
                    sentences.append(f"Right now I work as a {role} {place}.")
            else:
                if tenure:
                    sentences.append(f"I worked as a {role} {place} for {tenure}.")
                else:
                    sentences.append(f"I worked as a {role} {place}.")
            if focus:
                sentences.append(f"My work was mainly about {focus}.")

        courses = cls._course_credentials(profile, arabic=False)
        if courses:
            if len(courses) == 1:
                sentences.append(f"I also have this course: {courses[0]}.")
            elif len(courses) == 2:
                sentences.append(
                    f"I also have these courses: {courses[0]} and {courses[1]}."
                )
            else:
                sentences.append(
                    "I also have these courses: "
                    + ", ".join(courses[:-1])
                    + f", and {courses[-1]}."
                )

        if not sentences:
            return "I am ready to introduce myself from my CV."
        return " ".join(sentences)

    @classmethod
    def _build_arabic_introduction(
        cls,
        profile: CandidateProfile,
        length_mode: AnswerLengthMode,
    ) -> str:
        """Arabic compact intro: study, jobs with tenure/country/nature, and courses."""
        del length_mode
        sentences: list[str] = []
        name = profile.personal_profile.full_name
        years = profile.professional_summary.years_of_experience
        nationality = profile.personal_profile.nationality

        if name:
            lead = f"أنا {name.title()}"
            if nationality:
                lead += f"، {nationality}"
            if years:
                lead += f"، ولدي نحو {years} عامًا من الخبرة المهنية"
            sentences.append(lead + ".")
        elif years:
            sentences.append(f"لدي نحو {years} عامًا من الخبرة المهنية.")

        if (
            not profile.employment_history
            and not profile.education
            and profile.professional_summary.summary
        ):
            summary = profile.professional_summary.summary.strip()
            if summary:
                sentences.append(summary if summary.endswith(".") else f"{summary}.")

        if profile.education:
            edu_bits = []
            for education in profile.education:
                degree = cls._arabic_degree(education.degree) if education.degree else "مؤهل"
                field = cls._arabic_field(education.field) if education.field else ""
                bit = f"{degree}{f' في {field}' if field else ''} من {education.institution}"
                if education.graduation_date:
                    bit += f" عام {education.graduation_date}"
                edu_bits.append(bit)
            if len(edu_bits) == 1:
                sentences.append(f"درست {edu_bits[0]}.")
            else:
                sentences.append("درست " + "، و".join(edu_bits) + ".")

        jobs = list(reversed(profile.employment_history))
        for job in jobs:
            role = cls._arabic_role(job.title) or "موظفًا"
            company = cls._arabic_company_name(job.company)
            location = job.location.strip() if job.location else ""
            tenure = cls._employment_tenure(job, arabic=True)
            focus = cls._job_focus(job, arabic=True)

            where = f" لدى {company}"
            if location:
                where += f" في {location}"
            when = f" لمدة {tenure}" if tenure else ""
            nature = f"، وطبيعة عملي كانت {focus}" if focus else ""
            if job.is_current:
                sentences.append(f"أعمل حاليًا {role}{where}{when}{nature}.")
            else:
                sentences.append(f"عملت {role}{where}{when}{nature}.")

        courses = cls._course_credentials(profile, arabic=True)
        if courses:
            if len(courses) == 1:
                sentences.append(f"ومن دوراتي وشهاداتي: {courses[0]}.")
            else:
                sentences.append(
                    "ومن دوراتي وشهاداتي: " + "، ".join(courses[:-1]) + f"، و{courses[-1]}."
                )

        if not sentences:
            return "أنا مستعد لتقديم نفسي بناءً على خلفيتي المهنية الموثقة."
        return " ".join(sentences)

    @staticmethod
    def _employment_tenure(employment, *, arabic: bool) -> str:
        """Return a short tenure phrase like 'about 5 years' when dates allow."""
        def extract_year(value: Optional[str]) -> Optional[int]:
            if not value:
                return None
            match = re.search(r"(19|20)\d{2}", value)
            return int(match.group(0)) if match else None

        start_year = extract_year(employment.start_date)
        end_year = extract_year(employment.end_date)
        if employment.is_current and start_year and not end_year:
            end_year = datetime.now(timezone.utc).year
        if start_year and end_year and end_year >= start_year:
            years = max(1, end_year - start_year)
            if arabic:
                return f"نحو {years} {'عام' if years == 1 else 'أعوام'}"
            return f"about {years} year" + ("s" if years != 1 else "")

        period = AnswerGenerator._employment_period(employment, arabic=arabic)
        if "not stated" in period.casefold() or "غير مذكور" in period:
            return ""
        return period

    @classmethod
    def _job_focus(cls, employment, *, arabic: bool) -> str:
        """One short phrase describing the nature of work at a role."""
        text = ""
        if employment.achievements:
            text = cls._clean_cv_items(employment.achievements)[0]
        elif employment.responsibilities:
            text = cls._clean_cv_items(employment.responsibilities)[0]
        elif employment.technologies:
            techs = cls._clean_cv_items(employment.technologies)[:3]
            text = cls._join_naturally(techs) if not arabic else "، ".join(techs)

        if not text:
            return ""
        text = re.sub(
            r"^(?:I\s+)?"
            r"(?:worked on|managed|manage|supervised|supervise|led|maintain|maintained|"
            r"oversee|oversaw|teach|taught|teaching)\s+"
            r"(?:&\s+maintain(?:ed)?\s+)?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = text.lstrip("& ").strip(" .;")
        if arabic:
            text = cls._arabic_scale(text)
        if len(text) > 110:
            text = text[:107].rsplit(" ", 1)[0] + "…"
        return text

    @classmethod
    def _course_credentials(cls, profile: CandidateProfile, *, arabic: bool) -> list[str]:
        """Compact list of certifications and notable courses from the CV."""
        items: list[str] = []
        seen: set[str] = set()

        def add(label: str) -> None:
            cleaned = label.strip().rstrip(".")
            if not cleaned:
                return
            key = cleaned.casefold()
            if key in seen:
                return
            seen.add(key)
            items.append(cleaned)

        for certification in profile.certifications:
            if certification.name:
                name = (
                    cls._arabic_certification(certification.name)
                    if arabic
                    else certification.name
                )
                add(name)

        course_markers = (
            "ccna", "ccnp", "security+", "pmp", "linux", "vmware", "btec",
            "fortigate", "office", "adobe",
        )
        for skill in [*profile.technical_skills, *profile.management_skills]:
            name = (skill.name or "").strip()
            if not name:
                continue
            lowered = name.casefold()
            if any(marker in lowered for marker in course_markers):
                add(name)
            for evidence in skill.evidence:
                if any(
                    marker in evidence.casefold()
                    for marker in ("taught", "course", "training", "دورة", "درّست")
                ):
                    # Prefer the skill/course name over the full evidence sentence.
                    add(name)
                    break

        for entry in cls._training_entries(profile)[:3]:
            short = entry.strip().rstrip(".")
            lowered = short.casefold()
            if (
                len(short) > 50
                or " for " in lowered
                or lowered.startswith(("i taught", "delivered", "teach", "taught"))
            ):
                continue
            add(short)

        return items[:8]

    @staticmethod
    def _clean_cv_items(items: list[str]) -> list[str]:
        """Normalize CV list punctuation without rewriting or inventing facts."""
        return [item.strip().rstrip(".;") for item in items if item and item.strip()]

    @staticmethod
    def _employment_period(employment, *, arabic: bool) -> str:
        start = employment.start_date
        end = employment.end_date
        if employment.is_current and not end:
            end = "Present"
        if employment.is_current and not start:
            return (
                "الوظيفة الحالية؛ تاريخ البدء غير مذكور في السيرة"
                if arabic else
                "Current role; start date is not stated in the CV"
            )
        if start and end:
            return f"من {start} إلى {'الآن' if arabic and end.casefold() == 'present' else end}" if arabic else f"From {start} to {end}"
        if start:
            return f"منذ {start}" if arabic else f"Since {start}"
        if end:
            return f"حتى {end}" if arabic else f"Until {end}"
        return "التاريخ غير مذكور في السيرة" if arabic else "Dates are not stated in the CV"

    @staticmethod
    def _training_entries(profile: CandidateProfile) -> list[str]:
        """Collect explicitly evidenced courses/training without treating skills as courses."""
        entries: list[str] = []
        seen: set[str] = set()
        markers = ("taught", "course", "training", "curriculum", "درّست", "دورة", "تدريب")
        for skill in [
            *profile.technical_skills,
            *profile.management_skills,
            *profile.soft_skills,
        ]:
            for evidence in skill.evidence:
                normalized = " ".join(evidence.casefold().split())
                if not any(marker in normalized for marker in markers):
                    continue
                key = re.sub(r"[^\w]+", " ", normalized).strip()
                if key in seen:
                    continue
                seen.add(key)
                entries.append(evidence.strip().rstrip(".") + ".")
        for achievement in profile.achievements:
            normalized = " ".join(achievement.fact.casefold().split())
            if not any(marker in normalized for marker in markers):
                continue
            key = re.sub(r"[^\w]+", " ", normalized).strip()
            if key in seen:
                continue
            seen.add(key)
            entries.append(achievement.fact.strip().rstrip(".") + ".")
        return entries

    @staticmethod
    def _current_employment(profile: CandidateProfile):
        for employment in profile.employment_history:
            if employment.is_current:
                return employment
        current_role = (profile.professional_summary.current_role or "").casefold()
        if current_role:
            for employment in profile.employment_history:
                title = employment.title.casefold()
                if title in current_role or current_role in title:
                    return employment
        return None

    @staticmethod
    def _simple_english_role(role: Optional[str]) -> str:
        if not role:
            return ""
        normalized = role.casefold()
        if "btec" in normalized and "teacher" in normalized:
            return "BTEC IT Teacher and Engineer"
        return role.split("(", 1)[0].strip().replace(" / ", " and ")

    @staticmethod
    def _arabic_role(role: Optional[str]) -> str:
        if not role:
            return ""
        normalized = role.casefold()
        if "btec" in normalized and "teacher" in normalized:
            return "مدرسًا لتكنولوجيا المعلومات بنظام BTEC ومهندسًا"
        if "project manager" in normalized:
            return "مدير مشاريع"
        if "it manager" in normalized:
            return "مديرًا لتكنولوجيا المعلومات"
        if "system" in normalized and "software engineer" in normalized:
            return "مهندس أنظمة وبرمجيات"
        return role.split("(", 1)[0].strip().replace(" / ", " و")

    @staticmethod
    def _arabic_company_name(value: str) -> str:
        normalized = value.casefold()
        if "bab amman" in normalized:
            return "مدرسة باب عمّان الثانوية"
        if "al najat charity" in normalized:
            return "جمعية النجاة الخيرية"
        return value

    @staticmethod
    def _join_naturally_ar(items: list[str]) -> str:
        if len(items) <= 1:
            return items[0] if items else ""
        return "، ".join(items[:-1]) + f"، و{items[-1]}"

    @staticmethod
    def _arabic_degree(value: str) -> str:
        normalized = value.casefold()
        if "bachelor" in normalized:
            return "درجة البكالوريوس"
        if "higher diploma" in normalized:
            return "الدبلوم العالي"
        return value

    @staticmethod
    def _arabic_field(value: str) -> str:
        if "computer engineering" in value.casefold():
            return "هندسة الحاسوب"
        return value

    @staticmethod
    def _arabic_certification(value: str) -> str:
        if "pmp" in value.casefold():
            return "شهادة PMP"
        return value

    @staticmethod
    def _arabic_project_name(value: str) -> str:
        normalized = value.casefold()
        if "kuwait" in normalized and "e-stamp" in normalized:
            return "مشروع الطوابع الإلكترونية للحكومة الكويتية"
        return value

    @staticmethod
    def _arabic_scale(value: str) -> str:
        translated = re.sub(r"(?i)\bmore than\b|\bover\b", "أكثر من", value)
        translated = re.sub(r"(?i)\bkiosks?\b", "كشك", translated)
        return translated

    @staticmethod
    def _join_naturally(items: list[str]) -> str:
        if len(items) <= 1:
            return items[0] if items else ""
        if len(items) == 2:
            return " and ".join(items)
        return ", ".join(items[:-1]) + f", and {items[-1]}"

    @staticmethod
    def _short_company_name(company: str) -> str:
        parenthetical = re.search(r"\(([^)]+)\)", company)
        if parenthetical:
            alias = parenthetical.group(1).strip()
            if len(alias) <= 10 and alias.upper() == alias:
                return alias
            return company.split("(", 1)[0].strip()
        return company

    @classmethod
    def _build_scaled_project_highlight(
        cls,
        profile: CandidateProfile,
        length_mode: AnswerLengthMode,
    ) -> str:
        project = cls._scaled_project_components(profile, length_mode)
        if not project:
            return ""
        company, project_name, scale, technologies = project
        technology_clause = (
            f" using {cls._join_naturally(technologies)}"
            if technologies
            else ""
        )
        return (
            f"At {company}, I worked on the {project_name}, which included "
            f"{scale}{technology_clause}."
        )

    @classmethod
    def _scaled_project_components(
        cls,
        profile: CandidateProfile,
        length_mode: AnswerLengthMode,
    ) -> Optional[tuple[str, str, str, list[str]]]:
        candidates = []
        for employment in profile.employment_history:
            for responsibility in employment.responsibilities:
                scale = re.search(
                    r"(?:more than|over|approximately|about)\s+\d+[\w\s-]{0,30}",
                    responsibility,
                    flags=re.IGNORECASE,
                )
                if not scale:
                    continue
                detail = re.split(
                    r"\bsuch as\s*:?\s*",
                    responsibility,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[-1]
                detail = re.sub(
                    r"^(?:I\s+)?(?:managed|manage|worked on|led|supervised|supervise|"
                    r"maintained|maintain)\s+(?:the\s+)?",
                    "",
                    detail,
                    flags=re.IGNORECASE,
                )
                project = re.search(
                    r"^([^,;()]{3,120}?\bproject)\b",
                    detail,
                    flags=re.IGNORECASE,
                )
                score = sum(
                    marker in responsibility.casefold()
                    for marker in ("government", "project", "kiosk", "network", "erp")
                )
                candidates.append((score, employment, project, scale.group(0).strip()))

        if not candidates:
            return None
        _, employment, project, scale = max(candidates, key=lambda item: item[0])
        project_name = project.group(1).strip() if project else "a major technology project"
        technology_limit = 2 if length_mode == AnswerLengthMode.QUICK else 3
        technologies = employment.technologies[:technology_limit]
        return (
            cls._short_company_name(employment.company),
            project_name,
            scale,
            technologies,
        )

    def _format_history(
        self,
        history: list[dict],
        *,
        include_candidate_answers: bool = True,
        include_suggested_answers: bool = False,
        max_entries: int = 6,
    ) -> str:
        """Format conversation history for context."""
        if not history:
            return ""

        recent = history[-max(1, max_entries):]
        lines = []
        for entry in recent:
            raw_role = entry.get("role", "unknown").casefold()
            if raw_role == "candidate" and not include_candidate_answers:
                continue
            if raw_role == "suggested_answer" and not include_suggested_answers:
                continue
            if raw_role not in {"interviewer", "candidate", "suggested_answer"}:
                continue
            role = raw_role.upper()
            text = entry.get("text", "")
            if len(text) > 400:
                text = text[:397].rstrip() + "..."
            lines.append(f"{role}: {text}")
        return "\n".join(lines)

    async def _validate_answer(
        self,
        answer: str,
        question: str,
        evidence: list[EvidenceSource],
        profile: CandidateProfile,
        requires_candidate_context: bool,
        force_technical_validation: bool = False,
    ) -> ValidationResult:
        """
        Validate answer for hallucinations and technical accuracy using AnswerValidator.
        """
        # Enforce fail closed if context is required but missing
        if requires_candidate_context and not evidence:
            result = ValidationResult()
            result.is_valid = False
            result.missing_context = True
            result.missing_context_details = "insufficient_candidate_evidence"
            return result

        # General-knowledge answers contain no candidate claims. The generation
        # prompt already constrains them, so a second Gemini round trip adds
        # latency without improving CV hallucination protection.
        if not requires_candidate_context and not force_technical_validation:
            return ValidationResult(is_valid=True)

        # Call the hardened external validator
        try:
            return await asyncio.wait_for(
                answer_validator.validate(answer, question, evidence, profile, requires_candidate_context),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            if force_technical_validation:
                logger.warning(
                    "Technical explanation validation timed out after 5s. "
                    "Failing closed to avoid showing an unchecked explanation."
                )
                return ValidationResult(
                    is_valid=False,
                    missing_context=True,
                    missing_context_details="Technical validation timed out.",
                )
            logger.warning("Deep validation timed out after 5s. Failing open (showing answer).")
            return ValidationResult(is_valid=True)
        except Exception as e:
            logger.error(f"Answer validation failed: {e}")
            return ValidationResult(is_valid=False, missing_context=True, missing_context_details=f"Validation error: {e}")

    async def _check_contradictions(
        self, answer: str, history: list[dict], profile: CandidateProfile
    ) -> list[str]:
        """Check for contradictions with previous answers."""
        contradictions = []

        previous_answers = [
            h.get("text", "") for h in history if h.get("role") == "candidate"
        ]
        
        if not previous_answers:
            return []

        # We use ConsistencyChecker to compare new answer directly against previous ones
        try:
            # We don't have a full ledger here, so we simulate it by parsing previous answers
            # or we just rely on check_consistency to see the previous_answers as part of profile?
            # Let's mock the ledger with the previous answers as simple facts
            from app.models.session import InterviewFactEntry
            mock_ledger = [InterviewFactEntry(fact=ans, question_context="Previous answer") for ans in previous_answers]
            
            contradictions = await consistency_checker.check_consistency(
                new_answer=answer,
                facts_ledger=mock_ledger,
                profile=profile
            )
        except Exception as e:
            logger.error(f"Contradiction check failed: {e}")

        return contradictions

    def _calc_context_confidence(
        self, evidence: list[EvidenceSource], requires_context: bool
    ) -> float:
        """Calculate confidence in the retrieved context."""
        if not requires_context:
            return 0.9  # General knowledge, high confidence

        if not evidence:
            return 0.2  # No evidence found

        avg_relevance = sum(e.relevance for e in evidence) / len(evidence)
        return min(0.95, avg_relevance + 0.3)

    def _parse_bilingual_text(self, raw: str) -> tuple[str, str]:
        """Split a plain-text ENGLISH:/ARABIC: response into two answers."""
        text = (raw or "").strip()
        if not text:
            return "", ""

        upper = text.upper()
        en_idx = upper.find("ENGLISH:")
        ar_idx = upper.find("ARABIC:")

        if en_idx >= 0 and ar_idx >= 0:
            if en_idx < ar_idx:
                answer_en = text[en_idx + len("ENGLISH:") : ar_idx].strip()
                answer_ar = text[ar_idx + len("ARABIC:") :].strip()
            else:
                answer_ar = text[ar_idx + len("ARABIC:") : en_idx].strip()
                answer_en = text[en_idx + len("ENGLISH:") :].strip()
            return answer_en, answer_ar

        # Fallback: treat whole blob as English if markers are missing.
        return text, ""

    async def fill_bilingual_pair(self, generated: GeneratedAnswer) -> GeneratedAnswer:
        """
        After a fast single-language live answer, fill the missing EN/AR side.
        Keeps the already-shown text and only translates the counterpart.
        """
        primary = (generated.answer_en or "").strip()
        if not primary:
            return generated
        if generated.answer_ar and generated.answer_ar.strip():
            return generated

        translate_tokens = 180
        translate_timeout = min(8.0, settings.gemini_request_timeout_seconds)

        primary_is_arabic = bool(re.search(r"[\u0600-\u06ff]", primary))
        if primary_is_arabic:
            prompt = (
                "Translate this interview answer into easy spoken English. "
                "Short words. Easy to say. Keep English terms. Do not add facts.\n\n"
                f"{primary}"
            )
            english = (
                await gemini.generate_text(
                    prompt=prompt,
                    system_instruction=(
                        "Translate into easy spoken English. Short sentences. No hard words."
                    ),
                    model=settings.gemini_answer_model,
                    temperature=0.2,
                    max_output_tokens=translate_tokens,
                    thinking_budget=None,
                    timeout_seconds=translate_timeout,
                )
            ).strip()
            return generated.model_copy(update={"answer_en": english, "answer_ar": primary})

        arabic = await self._translate_to_interview_arabic(
            primary,
            max_output_tokens=translate_tokens,
            timeout_seconds=translate_timeout,
        )
        return generated.model_copy(update={"answer_ar": arabic})

    async def _translate_to_interview_arabic(
        self,
        english: str,
        *,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> str:
        """Translate to easy formal interview Arabic and reject dialect output."""
        system = (
            "Translate into easy formal interview Arabic (not dialect). "
            "Keep English tech terms such as overfitting, model, training data, noise, score. "
            "Short sentences. Do not add facts. "
            "Forbidden dialect: لما، اللي، ده، دي، كتير، أوي، بيفشل، بيشوف، بشوف، بتاع، "
            "بوقف، بدري، عشان، مش، يعني ايه، كده. "
            "Prefer: عندما، الذي/التي، هذا، كثيرًا، يفشل، أراجع، الخاص بـ، أوقف، مبكرًا."
        )
        prompt = (
            "Translate this interview answer into easy formal Arabic.\n"
            "Keep English terms. No dialect. No extra facts.\n\n"
            f"{english}\n\n"
            "Good style example:\n"
            "الـ overfitting هو عندما يتعلم الـ model بيانات التدريب أكثر من اللازم، "
            "بما في ذلك الـ noise. هذه مشكلة لأن أداءه يضعف على بيانات جديدة. "
            "أراجع الـ training score مع score البيانات الجديدة، وأوقف الـ training مبكرًا."
        )
        arabic = (
            await gemini.generate_text(
                prompt=prompt,
                system_instruction=system,
                model=settings.gemini_answer_model,
                temperature=0.15,
                max_output_tokens=max_output_tokens,
                thinking_budget=None,
                timeout_seconds=timeout_seconds,
            )
        ).strip()
        if self._contains_arabic_dialect(arabic):
            retry_prompt = (
                prompt
                + "\n\nYour previous draft used dialect. Rewrite in formal interview Arabic only."
            )
            arabic = (
                await gemini.generate_text(
                    prompt=retry_prompt,
                    system_instruction=system,
                    model=settings.gemini_answer_model,
                    temperature=0.1,
                    max_output_tokens=max_output_tokens,
                    thinking_budget=None,
                    timeout_seconds=timeout_seconds,
                )
            ).strip()
        return arabic

    @staticmethod
    def _contains_arabic_dialect(text: str) -> bool:
        """Detect common dialect markers that must not appear in interview Arabic."""
        if not text:
            return False
        dialect_markers = (
            "لما ", " لما", "اللي", " ده ", "ده ", " دي ", "دي ",
            "كتير", "اوي", "أوي", "بيفشل", "بيشوف", "بشوف", "بتاع",
            "بوقف", "بدري", "عشان", " مش ", "مش ", "كده", "يعني ايه",
        )
        normalized = f" {text} "
        return any(marker in normalized for marker in dialect_markers)

    def _error_answer(self, question: str, error: str) -> GeneratedAnswer:
        """Create an error response."""
        return GeneratedAnswer(
            question=question,
            normalized_question=question,
            answer_en=f"Unable to generate answer: {error}",
            strategy=AnswerStrategy.INSUFFICIENT_CONTEXT,
            length_mode=AnswerLengthMode.STANDARD,
            confidence=ConfidenceScores(),
            validation=ValidationResult(is_valid=False),
            action="INSUFFICIENT_CONTEXT",
        )

    def _answer_from_prepared(
        self,
        *,
        question: str,
        asked: str,
        prepared_text: str,
        question_id: str,
        length_mode: AnswerLengthMode,
    ) -> GeneratedAnswer:
        text = prepared_text.strip()
        return GeneratedAnswer(
            question_id=question_id,
            question=asked,
            normalized_question=question,
            answer_en=text,
            answer_ar=None,
            strategy=AnswerStrategy.PERSONAL_NARRATIVE,
            length_mode=length_mode,
            confidence=ConfidenceScores(
                question_confidence=0.95,
                context_confidence=1.0,
                answer_confidence=0.98,
                technical_confidence=0.9,
            ),
            validation=ValidationResult(is_valid=True),
            candidate_evidence=[
                EvidenceSource(
                    fact=text[:400],
                    source_type="MANUAL_ENTRY",
                    source_section="expected_questions",
                    relevance=1.0,
                )
            ],
            action="SHOW_ANSWER",
        )

    async def _match_question_bank(
        self, text: str, conversation_history: list[dict]
    ) -> Optional[BankMatch]:
        """Run the (CPU-bound, ~50 ms) bank matcher off the event loop."""
        if not text.strip():
            return None
        loop = asyncio.get_running_loop()

        def _lookup() -> Optional[BankMatch]:
            from app.services.main_request_extraction import match_with_main_request

            match, _ext, mre_meta = match_with_main_request(
                text, conversation_history=conversation_history
            )
            mre_locked = bool(mre_meta.get("override")) and float(
                (
                    mre_meta["extraction"].get("confidence")
                    if isinstance(mre_meta.get("extraction"), dict)
                    else 0.0
                )
                or 0.0
            ) >= 0.72
            if mre_locked:
                return match
            try:
                from app.services.semantic_intent_recovery import recover_semantic_intent

                sem = recover_semantic_intent(
                    text,
                    match,
                    conversation_history=conversation_history,
                )
                if sem.applied and sem.match is not None:
                    return sem.match
            except Exception as exc:
                logger.debug("Semantic recovery skipped in answer_generator: %s", exc)
            return match

        try:
            return await loop.run_in_executor(None, _lookup)
        except Exception as exc:
            logger.warning("Question bank match failed: %s", exc)
            return None

    async def _maybe_compound_answer(
        self,
        text: str,
        *,
        conversation_history: list[dict],
        question: str,
        asked: str,
        question_id: str,
        length_mode: AnswerLengthMode,
        start_time: float,
    ) -> Optional[GeneratedAnswer]:
        """Compound / multi-intent bank merge when the single match is not strong."""
        from app.services.compound_question_detector import detect_question_complexity
        from app.services.compound_question_pipeline import resolve_compound_question

        if not (text or "").strip():
            return None
        detection = detect_question_complexity(text)
        if detection.question_type == "single":
            return None
        loop = asyncio.get_running_loop()
        try:
            resolution = await loop.run_in_executor(
                None,
                lambda: resolve_compound_question(
                    text,
                    conversation_history=conversation_history,
                    detection=detection,
                ),
            )
        except Exception as exc:
            logger.warning("Compound question resolve failed: %s", exc)
            return None
        if not resolution.used_compound_path or not resolution.answer_en:
            return None
        if resolution.selected_intents:
            question_bank.remember(text, resolution.selected_intents[0])
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return GeneratedAnswer(
            question_id=question_id,
            question=asked,
            normalized_question=question,
            answer_en=resolution.answer_en,
            answer_ar=None,
            strategy=AnswerStrategy.TECHNICAL_CONCISE,
            length_mode=length_mode,
            confidence=ConfidenceScores(
                question_confidence=min(0.97, 0.72 + 0.05 * len(resolution.selected_intents)),
                context_confidence=1.0,
                answer_confidence=0.94 if resolution.full_compound_success else 0.88,
                technical_confidence=0.93,
            ),
            validation=ValidationResult(is_valid=True),
            candidate_evidence=[
                EvidenceSource(
                    fact=f"Compound bank intents: {', '.join(resolution.selected_intents)}",
                    source_type="question_bank",
                    source_section=",".join(resolution.answer_sources[:6]),
                    relevance=round(max(0.0, min(1.0, resolution.intent_coverage_rate)), 3),
                )
            ],
            action="SHOW_ANSWER",
            internal_reasoning=(
                f"compound_question intents={resolution.selected_intents} "
                f"coverage={resolution.intent_coverage_rate} "
                f"partial={resolution.partial_compound_match} "
                f"in {elapsed_ms:.0f}ms"
            ),
        )

    def _answer_from_bank(
        self,
        *,
        match: BankMatch,
        question: str,
        asked: str,
        question_id: str,
        length_mode: AnswerLengthMode,
        elapsed_ms: float,
    ) -> GeneratedAnswer:
        entry = match.entry
        text = entry.answer_en.strip()
        strategy = (
            AnswerStrategy.TECHNICAL_CONCISE
            if entry.bank == "technical"
            else AnswerStrategy.PERSONAL_NARRATIVE
        )
        return GeneratedAnswer(
            question_id=question_id,
            question=asked,
            normalized_question=question,
            answer_en=text,
            answer_ar=entry.answer_ar,
            strategy=strategy,
            length_mode=length_mode,
            confidence=ConfidenceScores(
                question_confidence=min(0.99, 0.75 + match.score / 4),
                context_confidence=1.0,
                answer_confidence=0.97,
                technical_confidence=0.95,
            ),
            validation=ValidationResult(is_valid=True),
            candidate_evidence=[
                EvidenceSource(
                    fact=f"Bank question: {entry.question}",
                    source_type="question_bank",
                    source_section=entry.id,
                    # Intent / topic bonuses can push the score above 1.0.
                    relevance=round(max(0.0, min(1.0, match.score)), 3),
                )
            ],
            action="SHOW_ANSWER",
            internal_reasoning=(
                f"question_bank:{entry.id} score={match.score:.2f} "
                f"sem={match.semantic:.2f} lex={match.lexical:.2f} in {elapsed_ms:.0f}ms"
            ),
        )


# Singleton instance
answer_generator = AnswerGenerator()
