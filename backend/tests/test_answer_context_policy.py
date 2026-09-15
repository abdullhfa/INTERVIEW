import unittest
from typing import Any
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.models.answer import EvidenceSource, ValidationResult
from app.models.candidate import (
    AnswerLengthMode,
    AnswerLanguageMode,
    CandidateProfile,
    Certification,
    Education,
    Employment,
    FactSource,
    PersonalProfile,
    ProfessionalSummary,
    Skill,
    TargetRole,
    VerifiedFact,
)
from app.models.question import QuestionCategory, UtteranceClassification, UtteranceType
from app.services.answer_generator import answer_generator
from app.services.question_classifier import question_classifier


class AnswerContextPolicyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        answer_generator.clear_specialist_cache()
        # These tests assert on the LLM prompt; the prepared question bank
        # would otherwise answer most of them instantly without any prompt.
        bank_patch = patch.object(settings, "question_bank_enabled", False)
        bank_patch.start()
        self.addCleanup(bank_patch.stop)

    def _profile(self) -> CandidateProfile:
        return CandidateProfile(
            personal_profile=PersonalProfile(full_name="Test Candidate"),
            professional_summary=ProfessionalSummary(
                summary="PRIVATE CV SUMMARY",
                current_role="BTEC IT Teacher",
                years_of_experience=14,
            ),
            education=[
                Education(
                    institution="Philadelphia University",
                    degree="Bachelor's degree",
                    field="Computer Engineering",
                    graduation_date="2010",
                ),
                Education(
                    institution="Jadara University Jordan",
                    degree="Higher Diploma",
                    field="Educational Administration",
                    graduation_date="2024",
                ),
            ],
            certifications=[
                Certification(
                    name="PMP Certification",
                    issuer="PMI",
                    credential_id="3424344",
                ),
                Certification(
                    name="Pearson BTEC Teacher Educator",
                    issuer="Pearson BTEC",
                ),
            ],
            employment_history=[
                Employment(
                    company="Bab Amman School",
                    title="BTEC IT Teacher",
                    is_current=True,
                    start_date="3 October 2022",
                    location="Jerash, Jordan",
                    responsibilities=["Teach Python, networking, and Security+."],
                ),
                Employment(
                    company="KNET",
                    title="Project Manager",
                    start_date="26 November 2015",
                    end_date="1 June 2021",
                    location="Kuwait",
                    responsibilities=[
                        "Supervise & maintain all VNC projects from an IT perspective such as "
                        "Kuwait Government e-stamp project, Stamp generation kiosks "
                        "(more than 400 kiosks)."
                    ],
                    technologies=["ERP System", "POS"],
                ),
            ],
            technical_skills=[
                Skill(name="Python"),
                Skill(name="Networking"),
                Skill(
                    name="CCNA R&S",
                    evidence=[
                        "I taught CCNA R&S for government employees at New Horizons in Bahrain."
                    ],
                ),
            ],
            management_skills=[Skill(name="Project Management")],
            achievements=[
                VerifiedFact(
                    fact="Delivered technical training courses in Bahrain and Kuwait",
                    source=FactSource.CV,
                    source_section="Training",
                    confidence=1.0,
                )
            ],
            target_roles=[
                TargetRole(
                    field="Computer Engineering",
                    specialization="Artificial Intelligence",
                    position="Cloud Security Engineer",
                    company="Acme",
                    seniority_level="Senior",
                    required_skills=["Zero Trust", "Azure", "SIEM"],
                    job_description="Design cloud security controls and incident response workflows.",
                )
            ],
        )

    def _await_prompt(self, generate_mock: Any) -> str:
        self.assertIsNotNone(generate_mock.await_args)
        await_args = generate_mock.await_args
        assert await_args is not None
        prompt = await_args.kwargs.get("prompt")
        self.assertIsInstance(prompt, str)
        assert isinstance(prompt, str)
        return prompt

    def _await_kwarg(self, generate_mock: Any, key: str) -> Any:
        self.assertIsNotNone(generate_mock.await_args)
        await_args = generate_mock.await_args
        assert await_args is not None
        return await_args.kwargs[key]

    async def test_personal_question_uses_verified_cv_evidence(self):
        classification = UtteranceClassification(
            type=UtteranceType.QUESTION,
            confidence=0.95,
            normalized_question="تحدث عن خبراتك السابقة",
            raw_utterance="تحدث عن خبراتك السابقة",
        )
        evidence = [
            EvidenceSource(
                fact="Worked as a security analyst",
                source_type="employment",
                source_section="Employment",
                relevance=0.9,
            )
        ]

        with (
            patch("app.services.answer_generator.context_retriever.retrieve", new=AsyncMock(return_value=evidence)) as retrieve,
            patch("app.services.answer_generator.gemini.generate_text", new=AsyncMock(return_value="Personal answer.")) as generate,
            patch("app.services.answer_generator.answer_validator.validate", new=AsyncMock(return_value=ValidationResult(is_valid=True))),
            patch("app.services.answer_generator.consistency_checker.check_consistency", new=AsyncMock(return_value=[])),
        ):
            result = await answer_generator.generate(
                classification,
                self._profile(),
                [{"role": "candidate", "text": "PRIVATE PREVIOUS CV ANSWER"}],
            )

        retrieve.assert_awaited_once()
        prompt = self._await_prompt(generate)
        self.assertIn("PRIVATE CV SUMMARY", prompt)
        self.assertIn("Worked as a security analyst", prompt)
        self.assertNotIn("Primary Field: Computer Engineering", prompt)
        self.assertNotIn("Target Specialization: Artificial Intelligence", prompt)
        self.assertTrue(
            any(item.fact == "Worked as a security analyst" for item in result.candidate_evidence)
        )
        self.assertGreaterEqual(len(result.candidate_evidence), 1)

    async def test_specialist_question_excludes_cv_and_uses_only_field_and_specialization(self):
        classification = UtteranceClassification(
            type=UtteranceType.QUESTION,
            confidence=0.95,
            normalized_question="How would you implement Zero Trust in Azure?",
            raw_utterance="How would you implement Zero Trust in Azure?",
            category=QuestionCategory.TECHNICAL,
            requires_candidate_context=True,
        )

        with (
            patch("app.services.answer_generator.context_retriever.retrieve", new=AsyncMock()) as retrieve,
            patch("app.services.answer_generator.gemini.generate_text", new=AsyncMock(return_value="Specialist answer.")) as generate,
        ):
            result = await answer_generator.generate(
                classification,
                self._profile(),
                [
                    {"role": "candidate", "text": "PRIVATE PREVIOUS CV ANSWER"},
                    {"role": "interviewer", "text": "Let us continue with Azure."},
                ],
            )

        retrieve.assert_not_awaited()
        prompt = self._await_prompt(generate)
        self.assertNotIn("PRIVATE CV SUMMARY", prompt)
        self.assertNotIn("PRIVATE PREVIOUS CV ANSWER", prompt)
        self.assertNotIn("INTERVIEWER: Let us continue with Azure.", prompt)
        self.assertIn("Primary Field: Computer Engineering", prompt)
        self.assertIn("Target Specialization: Artificial Intelligence", prompt)
        self.assertNotIn("Acme", prompt)
        self.assertNotIn("Zero Trust, Azure, SIEM", prompt)
        self.assertNotIn("Design cloud security controls", prompt)
        self.assertIn("ONLY the configured specialization", prompt)
        self.assertIn("Answer domain: Artificial Intelligence ONLY", prompt)
        self.assertIn("Answer only in Artificial Intelligence", prompt)
        self.assertNotIn("and its parent field", prompt)
        self.assertEqual(result.strategy.value, "TECHNICAL_DETAILED")
        self.assertEqual(result.candidate_evidence, [])

    async def test_ai_question_uses_deep_ai_strategy_and_prompt(self):
        classification = await question_classifier.classify(
            "Why do LLMs use deep learning?"
        )

        with patch(
            "app.services.answer_generator.gemini.generate_text",
            new=AsyncMock(return_value="LLMs learn representations from text."),
        ) as generate:
            result = await answer_generator.generate(
                classification,
                self._profile(),
                [],
            )

        prompt = self._await_prompt(generate)
        self.assertEqual(classification.category, QuestionCategory.AI_ML)
        self.assertFalse(classification.requires_candidate_context)
        self.assertEqual(result.strategy.value, "TECHNICAL_DETAILED")
        self.assertIn("This is an AI/ML interview question", prompt)
        self.assertIn("next-token prediction", prompt)
        self.assertIn("Do not imply that an LLM understands exactly like a human", prompt)

    async def test_ai_specialization_locks_live_answers_to_ai_domain(self):
        classification = UtteranceClassification(
            type=UtteranceType.QUESTION,
            confidence=0.95,
            normalized_question="What is a REST API?",
            raw_utterance="What is a REST API?",
            category=QuestionCategory.TECHNICAL,
        )
        with patch(
            "app.services.answer_generator.gemini.generate_text",
            new=AsyncMock(return_value="In AI systems an API often serves model inference."),
        ) as generate:
            result = await answer_generator.generate(
                classification,
                self._profile(),
                [],
                prefer_speed=True,
            )

        prompt = self._await_prompt(generate)
        self.assertEqual(result.strategy.value, "TECHNICAL_DETAILED")
        self.assertIn("Answer only in Artificial Intelligence", prompt)
        self.assertIn("Do not drift into cloud", prompt)

    async def test_live_definition_prompt_asks_for_interview_grade_structure(self):
        classification = UtteranceClassification(
            type=UtteranceType.QUESTION,
            confidence=0.99,
            normalized_question="What is overfitting?",
            raw_utterance="What is overfitting?",
            category=QuestionCategory.AI_ML,
        )
        with patch(
            "app.services.answer_generator.gemini.generate_text",
            new=AsyncMock(
                return_value=(
                    "Overfitting is when a model fits training noise instead of the true pattern. "
                    "It matters because validation and production performance then collapse. "
                    "I would watch the train-validation gap and use regularization or early stopping."
                )
            ),
        ) as generate:
            await answer_generator.generate(
                classification,
                self._profile(),
                [],
                prefer_speed=True,
                length_mode=AnswerLengthMode.QUICK,
            )

        prompt = self._await_prompt(generate)
        self.assertIn("Easy spoken words", prompt)
        self.assertIn("Be accurate", prompt)
        self.assertIn("Do not force a problem template", prompt)
        self.assertIn("overfitting", prompt.casefold())
        self.assertIn("Keep it short and accurate", prompt)

    async def test_self_introduction_overrides_wrong_follow_up_and_ignores_technical_history(self):
        classification = UtteranceClassification(
            type=UtteranceType.FOLLOW_UP,
            confidence=0.92,
            normalized_question="please speak for yourself",
            raw_utterance="please speak for yourself",
            category=QuestionCategory.FOLLOW_UP,
            requires_candidate_context=False,
            is_follow_up=True,
        )
        with (
            patch("app.services.answer_generator.context_retriever.retrieve", new=AsyncMock()) as retrieve,
            patch("app.services.answer_generator.gemini.generate_text", new=AsyncMock()) as generate,
            patch("app.services.answer_generator.answer_validator.validate", new=AsyncMock(return_value=ValidationResult(is_valid=True))),
        ):
            result = await answer_generator.generate(
                classification,
                self._profile(),
                [{"role": "interviewer", "text": "What is machine learning?"}],
            )

        retrieve.assert_not_awaited()
        generate.assert_not_awaited()
        self.assertIn("Test Candidate", result.answer_en)
        self.assertIn("Computer Engineering", result.answer_en)
        self.assertIn("finished in 2010", result.answer_en)
        self.assertIn("KNET", result.answer_en)
        self.assertIn("Kuwait", result.answer_en)
        self.assertIn("Project Manager", result.answer_en)
        self.assertIn("PMP Certification", result.answer_en)
        self.assertIn("CCNA R&S", result.answer_en)
        self.assertIn("Hi, my name is", result.answer_en)
        self.assertNotIn("Career history", result.answer_en)
        self.assertNotIn("My responsibilities included", result.answer_en)
        self.assertNotIn("professional experience", result.answer_en)
        self.assertNotIn("focusing on", result.answer_en)
        self.assertNotIn("machine learning", result.answer_en.casefold())
        self.assertNotIn("Artificial Intelligence", result.answer_en)
        self.assertGreaterEqual(len(result.candidate_evidence), 7)
        self.assertGreaterEqual(result.confidence.context_confidence, 0.9)
        self.assertEqual(result.strategy.value, "PERSONAL_NARRATIVE")

    async def test_bilingual_introduction_is_specific_and_deterministic(self):
        classification = UtteranceClassification(
            type=UtteranceType.QUESTION,
            confidence=0.99,
            normalized_question="I want you to talk about yourself.",
            raw_utterance="I want you to talk about yourself.",
            category=QuestionCategory.INTRODUCTION,
            requires_candidate_context=True,
        )

        with patch(
            "app.services.answer_generator.gemini.generate_structured",
            new=AsyncMock(),
        ) as generate:
            result = await answer_generator.generate(
                classification,
                self._profile(),
                [],
                language_mode=AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH,
            )

        generate.assert_not_awaited()
        self.assertIn("Bab Amman School", result.answer_en)
        self.assertIn("finished in 2010", result.answer_en)
        self.assertIn("Educational Administration", result.answer_en)
        self.assertIn("finished in 2024", result.answer_en)
        self.assertIn("KNET", result.answer_en)
        self.assertIn("Kuwait", result.answer_en)
        self.assertIn("Project Manager", result.answer_en)
        self.assertIn("about", result.answer_en)
        self.assertIn("BTEC IT Teacher and Engineer", result.answer_en)
        self.assertIn("Jerash, Jordan", result.answer_en)
        self.assertIn("PMP Certification", result.answer_en)
        self.assertIn("CCNA R&S", result.answer_en)
        self.assertIn("My work was mainly about", result.answer_en)
        self.assertIn("I also have these courses", result.answer_en)
        self.assertNotIn("Career history", result.answer_en)
        self.assertNotIn("Courses and training I delivered", result.answer_en)
        self.assertLess(len(result.answer_en.split()), 260)
        self.assertIsNotNone(result.answer_ar)
        answer_ar = result.answer_ar or ""
        self.assertIn("باب عمّان", answer_ar)
        self.assertIn("درست", answer_ar)
        self.assertIn("عام 2010", answer_ar)
        self.assertIn("في Kuwait", answer_ar)
        self.assertIn("دوراتي وشهاداتي", answer_ar)
        self.assertNotIn("المسار المهني", answer_ar)

    async def test_classifier_treats_stt_self_introduction_as_new_personal_question(self):
        with patch("app.services.question_classifier.gemini.classify", new=AsyncMock()) as classify:
            result = await question_classifier.classify(
                "please speak for yourself",
                [{"role": "interviewer", "text": "What is machine learning?"}],
            )

        classify.assert_not_awaited()
        self.assertEqual(result.type, UtteranceType.QUESTION)
        self.assertEqual(result.category, QuestionCategory.INTRODUCTION)
        self.assertTrue(result.requires_candidate_context)
        self.assertFalse(result.is_follow_up)

    async def test_classifier_handles_filler_before_question_without_model_call(self):
        with patch("app.services.question_classifier.gemini.classify", new=AsyncMock()) as classify:
            result = await question_classifier.classify(
                "Okay, so can you explain machine learning?"
            )

        classify.assert_not_awaited()
        self.assertEqual(result.type, UtteranceType.QUESTION)
        self.assertGreaterEqual(result.confidence, 0.9)

    async def test_classifier_handles_colloquial_arabic_question_without_model_call(self):
        with patch("app.services.question_classifier.gemini.classify", new=AsyncMock()) as classify:
            result = await question_classifier.classify(
                "طيب يعني إيه precision في الموديل"
            )

        classify.assert_not_awaited()
        self.assertEqual(result.type, UtteranceType.QUESTION)

    async def test_classifier_marks_example_reference_as_follow_up_without_model_call(self):
        history = [
            {
                "role": "interviewer",
                "text": "What is artificial intelligence and what are its types?",
            },
            {
                "role": "suggested_answer",
                "text": "A recommendation system suggests products a user may like.",
            },
        ]

        with patch("app.services.question_classifier.gemini.classify", new=AsyncMock()) as classify:
            result = await question_classifier.classify(
                "Can you explain the example more?",
                history,
            )

        classify.assert_not_awaited()
        self.assertEqual(result.type, UtteranceType.FOLLOW_UP)
        self.assertEqual(result.category, QuestionCategory.FOLLOW_UP)
        self.assertTrue(result.is_follow_up)
        self.assertIsNotNone(result.follow_up_context)
        self.assertIn("recommendation system", result.follow_up_context or "")

    async def test_follow_up_prompt_includes_previous_suggested_answer(self):
        classification = UtteranceClassification(
            type=UtteranceType.FOLLOW_UP,
            confidence=0.99,
            normalized_question="Can you explain the example more?",
            raw_utterance="Can you explain the example more?",
            category=QuestionCategory.FOLLOW_UP,
            is_follow_up=True,
        )
        history = [
            {
                "role": "interviewer",
                "text": "What is artificial intelligence and what are its types?",
            },
            {
                "role": "suggested_answer",
                "text": "A recommendation system suggests products a user may like.",
            },
            {"role": "candidate", "text": "PRIVATE CANDIDATE SPEECH"},
        ]

        with (
            patch(
                "app.services.answer_generator.gemini.generate_text",
                new=AsyncMock(return_value="It learns from viewed and purchased products."),
            ) as generate,
            patch(
                "app.services.answer_generator.answer_validator.validate",
                new=AsyncMock(return_value=ValidationResult(is_valid=True)),
            ),
        ):
            await answer_generator.generate(
                classification,
                self._profile(),
                history,
            )

        prompt = self._await_prompt(generate)
        self.assertIn("SUGGESTED_ANSWER: A recommendation system", prompt)
        self.assertNotIn("PRIVATE CANDIDATE SPEECH", prompt)
        self.assertIn("Resolve references", prompt)

    async def test_explanation_request_gets_fuller_answer_and_technical_validation(self):
        classification = UtteranceClassification(
            type=UtteranceType.FOLLOW_UP,
            confidence=0.99,
            normalized_question="Explain the example further.",
            raw_utterance="Explain the example further.",
            category=QuestionCategory.FOLLOW_UP,
            is_follow_up=True,
        )
        history = [
            {
                "role": "suggested_answer",
                "text": "An image classifier processes pixels through hidden layers.",
            }
        ]

        with (
            patch(
                "app.services.answer_generator.gemini.generate_text",
                new=AsyncMock(return_value="A careful technical explanation."),
            ) as generate,
            patch(
                "app.services.answer_generator.answer_validator.validate",
                new=AsyncMock(return_value=ValidationResult(is_valid=True)),
            ) as validate,
        ):
            result = await answer_generator.generate(
                classification,
                self._profile(),
                history,
                length_mode=AnswerLengthMode.QUICK,
            )

        prompt = self._await_prompt(generate)
        self.assertEqual(self._await_kwarg(generate, "max_output_tokens"), 720)
        self.assertIn("This is an EXPLANATION request", prompt)
        self.assertIn("at least 4-6 connected sentences", prompt)
        self.assertIn("scores or probabilities", prompt)
        self.assertIn("prediction that can be wrong", prompt)
        validate.assert_awaited_once()
        self.assertTrue(result.validation.is_valid)

    def test_arabic_explanation_request_is_detected(self):
        self.assertTrue(answer_generator._is_explanation_request("اشرح المثال أكثر"))
        self.assertTrue(answer_generator._is_explanation_request("وضّح آلية عمل النموذج"))
        self.assertFalse(answer_generator._is_explanation_request("ما هو التعلم العميق؟"))

    async def test_greetings_are_ignored_in_live_mode(self):
        for phrase in ("hi", "hello", "welcome", "welcome everyone", "مرحبا"):
            with self.subTest(phrase=phrase):
                result = await question_classifier.classify(phrase, prefer_speed=True)
                self.assertEqual(result.type, UtteranceType.STATEMENT)
                self.assertEqual(
                    question_classifier.determine_action(result).value,
                    "LISTEN",
                )

    async def test_misheard_two_word_topic_is_still_a_question(self):
        result = await question_classifier.classify(
            "water transformers",
            prefer_speed=True,
        )
        self.assertEqual(result.type, UtteranceType.QUESTION)
        self.assertEqual(
            question_classifier.determine_action(result).value,
            "SHOW_ANSWER",
        )

    async def test_greeting_prefix_does_not_drop_real_question(self):
        result = await question_classifier.classify(
            "hi what are transformers",
            prefer_speed=True,
        )
        self.assertEqual(result.type, UtteranceType.QUESTION)
        self.assertIn("transformers", (result.normalized_question or "").casefold())

    async def test_stages_follow_up_keeps_previous_topic(self):
        history = [
            {"role": "interviewer", "text": "What is a transformer in deep learning?"},
            {"role": "suggested_answer", "text": "A transformer uses self-attention layers."},
        ]
        result = await question_classifier.classify(
            "Explain more about the stages it goes through.",
            history,
            prefer_speed=True,
        )
        self.assertTrue(result.is_follow_up)
        self.assertIn("self-attention", result.follow_up_context or "")

    async def test_follow_up_prompt_names_previous_transformer_topic(self):
        classification = UtteranceClassification(
            type=UtteranceType.QUESTION,
            confidence=0.95,
            normalized_question="Explain more about the stages it goes through.",
            raw_utterance="Explain more about the stages it goes through.",
        )
        history = [
            {"role": "interviewer", "text": "What are transformers?"},
            {
                "role": "suggested_answer",
                "text": "A transformer is a neural network that uses self-attention.",
            },
        ]
        with (
            patch(
                "app.services.answer_generator.gemini.generate_text",
                new=AsyncMock(return_value="It starts with tokenization then self-attention layers."),
            ) as generate,
            patch(
                "app.services.answer_generator.answer_validator.validate",
                new=AsyncMock(return_value=ValidationResult(is_valid=True)),
            ),
        ):
            await answer_generator.generate(
                classification,
                self._profile(),
                history,
                prefer_speed=True,
            )

        prompt = self._await_prompt(generate)
        self.assertIn("What are transformers?", prompt)
        self.assertIn("self-attention", prompt)
        self.assertIn("follow-up", prompt.casefold())
        self.assertIn("Previous question", prompt)

    async def test_what_else_is_a_follow_up_of_previous_topic(self):
        history = [
            {"role": "interviewer", "text": "What are transformers?"},
            {"role": "suggested_answer", "text": "A transformer uses self-attention."},
        ]
        result = await question_classifier.classify(
            "What else?",
            history,
            prefer_speed=True,
        )
        self.assertTrue(result.is_follow_up)

        classification = UtteranceClassification(
            type=UtteranceType.FOLLOW_UP,
            confidence=0.99,
            normalized_question="What else?",
            raw_utterance="What else?",
            is_follow_up=True,
        )
        with patch(
            "app.services.answer_generator.gemini.generate_text",
            new=AsyncMock(return_value="Transformers also use positional encoding."),
        ) as generate:
            await answer_generator.generate(
                classification,
                self._profile(),
                history,
                prefer_speed=True,
            )
        prompt = self._await_prompt(generate)
        self.assertIn("What are transformers?", prompt)
        self.assertIn("Start with the next fact", prompt)
        self.assertNotIn("overfitting", prompt.casefold())

    def _profile_with_rag_project(self) -> CandidateProfile:
        profile = self._profile()
        from app.models.candidate import Project

        profile.projects = [
            Project(
                name="Interview Knowledge Assistant",
                description="Built a RAG assistant over internal docs with LangChain.",
                role="AI Engineer",
                company="Acme Labs",
                technologies=["RAG", "LangChain", "Chroma", "LLM", "embeddings"],
                outcomes=["Reduced support lookup time", "Grounded answers with citations"],
            )
        ]
        return profile

    async def test_arabic_project_question_uses_cv_projects_and_walkthrough(self):
        classification = await question_classifier.classify(
            "شو المشاريع اللي اشتغلتها"
        )
        self.assertTrue(classification.requires_candidate_context)

        with (
            patch(
                "app.services.answer_generator.context_retriever.retrieve",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.answer_generator.gemini.generate_text",
                new=AsyncMock(return_value="Worked on Interview Knowledge Assistant."),
            ) as generate,
            patch(
                "app.services.answer_generator.answer_validator.validate",
                new=AsyncMock(return_value=ValidationResult(is_valid=True)),
            ),
        ):
            result = await answer_generator.generate(
                classification,
                self._profile_with_rag_project(),
                [],
            )

        prompt = self._await_prompt(generate)
        self.assertEqual(result.strategy.value, "PROJECT_WALKTHROUGH")
        self.assertIn("Interview Knowledge Assistant", prompt)
        self.assertIn("Projects (use exact names", prompt)
        self.assertIn("PROJECT walkthrough", prompt)
        self.assertIn("ingest documents", prompt)
        self.assertTrue(
            any(e.source_type == "project" for e in result.candidate_evidence)
        )

    async def test_rag_usage_question_is_cv_grounded_not_generic_ai(self):
        classification = await question_classifier.classify(
            "هل استخدمت ال rag في احدى مشاريعك"
        )
        self.assertTrue(classification.requires_candidate_context)
        self.assertEqual(classification.category, QuestionCategory.CV_DEEP_DIVE)

        with (
            patch(
                "app.services.answer_generator.context_retriever.retrieve",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.answer_generator.gemini.generate_text",
                new=AsyncMock(return_value="Yes, in Interview Knowledge Assistant I used RAG."),
            ) as generate,
            patch(
                "app.services.answer_generator.answer_validator.validate",
                new=AsyncMock(return_value=ValidationResult(is_valid=True)),
            ),
        ):
            result = await answer_generator.generate(
                classification,
                self._profile_with_rag_project(),
                [],
            )

        prompt = self._await_prompt(generate)
        self.assertEqual(result.strategy.value, "PROJECT_WALKTHROUGH")
        self.assertIn("answer YES only when", prompt)
        self.assertIn("RAG", prompt)
        self.assertIn("LangChain", prompt)
        self.assertIn("vector database", prompt)
        self.assertNotIn("This is a SPECIALIST question", prompt)

    async def test_pure_rag_definition_stays_specialist_with_pipeline(self):
        classification = await question_classifier.classify("What is RAG?")
        self.assertFalse(classification.requires_candidate_context)
        self.assertEqual(classification.category, QuestionCategory.AI_ML)

        with patch(
            "app.services.answer_generator.gemini.generate_text",
            new=AsyncMock(return_value="RAG retrieves documents then generates an answer."),
        ) as generate:
            result = await answer_generator.generate(
                classification,
                self._profile_with_rag_project(),
                [],
            )

        prompt = self._await_prompt(generate)
        self.assertEqual(result.strategy.value, "TECHNICAL_DETAILED")
        self.assertIn("Retrieval-Augmented Generation", prompt)
        self.assertIn("chunking", prompt)
        self.assertIn("Do not claim personal project usage", prompt)
        self.assertNotIn("Interview Knowledge Assistant", prompt)

    async def test_ministry_operational_question_uses_cv_not_ai_refusal(self):
        profile = self._profile()
        profile.employment_history = [
            Employment(
                company="Ministry of Education | Jordan",
                title="Systems Developer & AI Engineer - BTEC",
                is_current=True,
                start_date="2023",
                location="Jordan",
                responsibilities=[
                    "Build LLM/RAG and Agentic AI solutions for student assessment support."
                ],
                technologies=["LLM", "RAG", "Agentic AI"],
            )
        ]
        classification = await question_classifier.classify(
            "Is the program currently operational at the Ministry of Education?"
        )
        self.assertTrue(classification.requires_candidate_context)

        with (
            patch(
                "app.services.answer_generator.context_retriever.retrieve",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.answer_generator.gemini.generate_text",
                new=AsyncMock(return_value="Yes, it is working now at the Ministry of Education."),
            ) as generate,
            patch(
                "app.services.answer_generator.answer_validator.validate",
                new=AsyncMock(return_value=ValidationResult(is_valid=True)),
            ),
        ):
            await answer_generator.generate(classification, profile, [], prefer_speed=True)

        prompt = self._await_prompt(generate)
        self.assertIn("Ministry of Education", prompt)
        self.assertIn("Yes, it is working now", prompt)
        self.assertIn("Do not say it is outside AI", prompt)
        self.assertNotIn("Answer only in Artificial Intelligence", prompt)

    async def test_project_role_follow_up_stays_on_project_not_career(self):
        from app.models.candidate import Project

        profile = self._profile()
        profile.employment_history = [
            Employment(
                company="Ministry of Education | Jordan",
                title="Systems Developer & AI Engineer - BTEC",
                is_current=True,
                start_date="2023",
                responsibilities=[
                    "Build LLM/RAG solutions for student assessment support.",
                    "Use embeddings for assignment similarity checking.",
                ],
                technologies=["LLM", "RAG", "embeddings"],
            ),
            Employment(
                company="Al Najat Charity",
                title="Applied AI Engineer",
                start_date="2017",
                end_date="2023",
                responsibilities=["Built Whisper kiosk voice tools."],
            ),
        ]
        profile.projects = [
            Project(
                name="BTEC Assignment Similarity Checker",
                description="Compared assignments using embeddings and similarity scores.",
                role="Systems Developer & AI Engineer",
                company="Ministry of Education",
                technologies=["Python", "NLP", "Embeddings"],
                outcomes=["Flagged high-similarity cases for review"],
            )
        ]
        history = [
            {
                "role": "interviewer",
                "text": "Tell me about the BTEC Assignment Similarity Checker project.",
            },
            {
                "role": "suggested_answer",
                "text": "I built the BTEC Assignment Similarity Checker using embeddings.",
            },
        ]
        classification = await question_classifier.classify(
            "What was your role in the project?",
            history,
            prefer_speed=True,
        )
        self.assertTrue(classification.is_follow_up)
        self.assertTrue(classification.requires_candidate_context)

        with (
            patch(
                "app.services.answer_generator.gemini.generate_text",
                new=AsyncMock(
                    return_value=(
                        "In that project my role was Systems Developer and AI Engineer. "
                        "I built the similarity checker and used embeddings."
                    )
                ),
            ) as generate,
            patch(
                "app.services.answer_generator.answer_validator.validate",
                new=AsyncMock(return_value=ValidationResult(is_valid=True)),
            ),
        ):
            result = await answer_generator.generate(
                classification,
                profile,
                history,
                prefer_speed=True,
            )

        prompt = self._await_prompt(generate)
        self.assertEqual(result.strategy.value, "PROJECT_WALKTHROUGH")
        self.assertIn("BTEC Assignment Similarity Checker", prompt)
        self.assertIn("only that project's title, role", prompt)
        self.assertIn("Do NOT list older jobs", prompt)
        self.assertNotIn("Al Najat Charity", prompt)




if __name__ == "__main__":
    unittest.main()