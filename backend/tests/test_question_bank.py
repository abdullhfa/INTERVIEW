import pytest

from app.services.domain_terms import canonicalize_display, normalize_for_matching
from app.services.question_bank import detect_intent, question_bank


@pytest.fixture(scope="module", autouse=True)
def _warm_bank():
    # Warm once per module: loads the three JSON banks and embeds every alias.
    # Force a real matrix even if an earlier test marked the bank "warm" after a
    # failed/partial embed (alias_matrix=None) — otherwise strong matches demote
    # and how/definition splits flake under the full suite.
    question_bank._warm = False
    question_bank.warm()
    assert question_bank._index.alias_matrix is not None, (
        "question bank semantic matrix failed to warm; bank tests require MiniLM"
    )


def _strong(text: str, expected_prefix: str, **kwargs) -> None:
    match = question_bank.match(text, **kwargs)
    assert match is not None, f"no match for {text!r}"
    assert match.entry.id.startswith(expected_prefix), (
        f"{text!r} -> {match.entry.id} (expected {expected_prefix}*), score={match.score:.2f}"
    )
    assert match.is_strong, f"{text!r} matched {match.entry.id} but only {match.mode} ({match.score:.2f})"


def test_bank_files_loaded():
    ids = {e.id for e in question_bank.entries}
    assert len(ids) >= 270
    assert {e.bank for e in question_bank.entries} == {"cv", "general", "technical", "scenario"}
    assert "hard.agentic_rag_design" in ids
    assert "intro.tell_me_about_yourself" in ids


def test_exact_and_paraphrased_intro():
    _strong("Tell me about yourself.", "intro.tell_me_about_yourself")
    _strong("So, to start, could you please introduce yourself briefly?", "intro.tell_me_about_yourself")
    _strong(
        "Okay so, uh, give me little bit background about you, your journey till now.",
        "intro.tell_me_about_yourself",
    )


def test_asr_noise_on_domain_terms():
    # Accented / mis-transcribed brand names still resolve.
    _strong("Tell me about the bee tech assignment similarity project you did in the ministry.", "proj.similarity")
    _strong("Have you used lang chain in production?", "cv.langchain")
    _strong("Have you worked with wisper before?", "cv.whisper_experience")
    _strong("What is m c p?", "tech.mcp")


def test_indirect_long_questions():
    _strong("You mentioned a similarity checker for assignments, how did that work actually?", "proj.similarity")
    _strong("How did you predict students who are at risk of failing?", "proj.early_warning")
    _strong(
        "You have been a project manager for a long time, why do you think you are a senior AI engineer?",
        "cv.senior_justification",
    )
    _strong(
        "Hmm, if we give you a project with unclear requirements, how would you approach it?",
        "gen.ambiguity",
    )


def test_technical_bank():
    _strong("Can you explain what is retrieval augmented generation?", "tech.rag_what")
    _strong("What is the difference between lang chain and lang graph?", "tech.langgraph_vs_langchain")
    _strong("How do you handle imbalanced data?", "tech.imbalanced")


@pytest.mark.parametrize(
    "text,expected",
    [
        # Each question must land on its own focused answer, never the sibling entry.
        ("What is RAG?", "tech.rag_what"),
        ("How would you build a RAG system for our documents?", "tech.rag_build"),
        ("What is data leakage?", "tech.data_leakage"),
        ("How do you prevent data leakage?", "tech.data_leakage_prevent"),
        ("What is overfitting?", "tech.overfitting"),
        ("How do you prevent overfitting?", "tech.overfitting_prevent"),
        ("What is machine learning?", "tech.what_is_ml"),
        ("What is the difference between AI, machine learning and deep learning?", "tech.ai_ml_dl_difference"),
        ("What is TF-IDF?", "tech.tfidf_what"),
        ("What is model drift?", "tech.model_drift"),
        ("How do you monitor a model in production?", "tech.model_monitoring"),
        ("What is a large language model?", "tech.what_is_llm"),
        ("How does an LLM generate text?", "tech.how_llm_works"),
        ("What are the limitations of large language models?", "tech.llm_problems"),
        ("What can LLMs be used for?", "tech.llm_uses"),
        ("What are tokens?", "tech.tokens"),
        ("What is a context window?", "tech.context_window"),
        ("What is hallucination?", "tech.hallucination_what"),
        ("How do you prevent hallucination?", "tech.hallucination_prevent"),
        ("What is the difference between zero-shot and few-shot?", "tech.zero_shot_few_shot"),
        ("What is metadata filtering?", "tech.metadata_filtering"),
        ("What is a knowledge graph?", "tech.knowledge_graph_what"),
        ("What are embeddings?", "tech.embeddings"),
        ("What is cosine similarity?", "tech.cosine_semantic_search"),
        ("What is hybrid search?", "tech.hybrid_search"),
        ("What is re-ranking?", "tech.reranking"),
        ("What is agentic AI?", "tech.agentic_what"),
        ("How would you design an agent for a financial organization?", "tech.agent_design_finance"),
        ("What is LangChain?", "tech.what_is_langchain"),
        ("What is LangGraph?", "tech.what_is_langgraph"),
        ("What is tool calling?", "tech.tool_calling"),
        ("What is chain of thought?", "tech.chain_of_thought"),
        ("What is a container and how is it different from a virtual machine?", "tech.container_vs_vm"),
        ("What are guardrails?", "tech.guardrails_what"),
        ("What is a golden dataset?", "tech.golden_dataset"),
        ("What is LLM as a judge?", "tech.llm_as_judge"),
        ("What is prompt injection?", "tech.prompt_injection_what"),
        ("What is fine-tuning?", "tech.fine_tuning_what"),
        ("What is LoRA?", "tech.lora"),
        ("What is p95 latency?", "tech.p95"),
        ("How does speech to text work?", "tech.how_stt_works"),
        ("How would you build a voice assistant?", "tech.voice_assistant_design"),
        ("Why Whisper and not a cloud speech API?", "tech.whisper_vs_cloud"),
        ("What is word error rate?", "tech.wer"),
        ("How do you evaluate a classification model?", "tech.evaluate_classification"),
        ("Did you work in Kuwait?", "cv.kuwait_did_you_work"),
        ("How long did you work in Kuwait?", "cv.kuwait_how_long"),
        ("Tell me about your time in Kuwait.", "cv.kuwait_experience"),
        ("Why did you move back to Jordan?", "cv.why_back_to_jordan"),
        ("What is PRINCE2?", "cv.prince2"),
        ("Why do you have a Cisco CCNP?", "cv.ccnp"),
        ("What is your most recent project?", "cv.projects.most_recent"),
        ("What NLP tasks have you worked on?", "cv.nlp_experience"),
    ],
)
def test_split_entries_answer_only_their_own_question(text, expected):
    match = question_bank.match(text)
    assert match is not None, f"no match for {text!r}"
    assert match.entry.id == expected, f"{text!r} -> {match.entry.id} ({match.mode} {match.score:.2f}), expected {expected}"
    assert match.is_strong, f"{text!r} -> {match.entry.id} only {match.mode} ({match.score:.2f})"


@pytest.mark.parametrize(
    "text",
    [
        "Okay. That's right.",
        "Okay, thank you.",
        "Yes, yes, I see.",
        "Great, let's move on to the next one.",
        "Can you hear me?",
        "What is the weather today in Dubai?",
        "Do you have a driving license?",
    ],
)
def test_acknowledgments_and_off_topic_never_strong(text):
    match = question_bank.match(text)
    assert match is None or not match.is_strong, f"{text!r} -> {match.entry.id} {match.mode}"


def test_follow_up_scoped_to_previous_topic():
    prev = "Tell me about the early warning system for students."
    first = question_bank.match(prev)
    assert first is not None and first.entry.topic == "project:early_warning"
    question_bank.remember(prev, first.entry.id)
    history = [{"role": "interviewer", "text": prev}, {"role": "candidate", "text": "..."}]

    scoped = question_bank.match("How did you avoid data leakage in that model?", conversation_history=history)
    assert scoped is not None and scoped.entry.id == "proj.early_warning.leakage"

    generic = question_bank.match("What was your role in it?", conversation_history=history)
    assert generic is not None and generic.entry.topic == "project:early_warning"


def test_bare_why_how_follow_ups_use_prior_topic():
    prev = "What is RAG?"
    first = question_bank.match(prev)
    assert first is not None
    question_bank.remember(prev, first.entry.id)
    history = [
        {"role": "interviewer", "text": prev},
        {"role": "suggested_answer", "text": first.entry.answer_en[:180]},
    ]
    for continuer in ("Why?", "How?"):
        m = question_bank.match(continuer, conversation_history=history)
        assert m is not None, f"{continuer!r} produced no match"
        assert m.mode == "weak"
        assert m.entry.id == first.entry.id
        from app.services.semantic_intent_recovery import recover_semantic_intent

        d = recover_semantic_intent(continuer, m, conversation_history=history)
        chosen = d.match or m
        assert chosen.entry.id == first.entry.id
        assert chosen.mode != "strong"
        blob = f"{chosen.entry.id} {chosen.entry.question} {chosen.entry.topic}".lower()
        assert "rag" in blob or "retriev" in blob


@pytest.mark.parametrize(
    "text,intent",
    [
        ("What is Whisper?", "definition"),
        ("Okay so, can you explain what is retrieval augmented generation?", "definition"),
        ("Have you used Whisper?", "experience"),
        ("How did you avoid data leakage in that model?", "experience"),
        ("How does an LLM generate text?", "how"),
        ("What are the steps to create an LLM?", "how"),
        ("How do you train an LLM?", "how"),
        ("Why LangGraph and not LangChain?", "why"),
        ("What is the difference between LangChain and LangGraph?", "compare"),
        ("Tell me about the BTEC similarity checker.", "describe"),
    ],
)
def test_intent_detection(text, intent):
    assert detect_intent(normalize_for_matching(text)) == intent


@pytest.mark.parametrize(
    "text,expected",
    [
        # Same keyword, three intents, three different answers.
        ("What is Whisper?", "tech.what_is_whisper"),
        ("Have you worked with wisper before?", "cv.whisper_experience"),
        ("How does Whisper turn audio into text?", "tech.how_stt_works"),
        ("What is RAG?", "tech.rag_what"),
        ("How does RAG work?", "tech.rag_build"),
        ("Have you used RAG in your projects?", "cv.rag_experience"),
        ("What is LangChain?", "tech.what_is_langchain"),
        ("Have you used LangChain?", "cv.langchain"),
        ("What is LangGraph?", "tech.what_is_langgraph"),
        ("Have you used LangGraph?", "cv.langgraph"),
        ("What is agentic AI?", "tech.agentic_what"),
        ("Have you used agentic AI in your projects?", "cv.agentic_experience"),
        ("What is ChromaDB?", "tech.what_is_chromadb"),
        ("Have you used ChromaDB?", "cv.chromadb"),
        ("What is n8n?", "tech.n8n_what"),
        ("Have you used n8n?", "cv.n8n"),
        ("What is an agent orchestrator?", "tech.agent_orchestrator"),
        ("What is deep learning?", "tech.what_is_dl"),
        ("What are the steps to create an LLM?", "tech.llm_create_steps"),
        ("What is an LLM?", "tech.what_is_llm"),
        ("How does an LLM work?", "tech.how_llm_works"),
        ("Does the similarity checker use an LLM?", "proj.similarity.stack"),
        ("Does the question generation use RAG?", "moe.question_generation.stack"),
        ("What is fine-tuning?", "tech.fine_tuning_what"),
        ("Have you done any fine tuning?", "cv.fine_tuning"),
    ],
)
def test_intent_separates_definition_experience_how(text, expected):
    match = question_bank.match(text)
    assert match is not None and match.entry.id == expected, (
        f"{text!r} -> {match.entry.id if match else None} ({match.mode if match else ''})"
    )
    assert match.is_strong, f"{text!r} only {match.mode} ({match.score:.2f}) runner={match.runner_up}"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("What projects do you have in Kuwait, and has any work been done on LLM for them?", "cv.kuwait_projects_and_llm"),
        ("What projects did you do in Kuwait?", "cv.kuwait_projects"),
        ("Did you use LLMs in Kuwait?", "cv.kuwait_llm"),
    ],
)
def test_personal_question_never_answered_with_definition(text, expected):
    match = question_bank.match(text)
    assert match is not None, text
    assert match.entry.id == expected, f"{text!r} -> {match.entry.id} ({match.mode}, {match.score:.2f})"
    assert match.is_strong, f"{text!r} only {match.mode} ({match.score:.2f}) runner={match.runner_up}"
    # Whatever ends up on top, a question about the candidate must never be a textbook definition.
    for cand in question_bank.search(text, limit=3):
        if cand.entry.bank == "technical":
            assert cand.score < match.score - 0.05, cand.entry.id


def test_compound_question_without_covering_alias_is_weak():
    match = question_bank.match("How long did you work in Kuwait, and why did you move back to Jordan?")
    assert match is not None
    assert match.entry.id.startswith("cv.")
    assert not match.is_strong, f"{match.entry.id} {match.mode} {match.score:.2f}"


def test_long_question_mentioning_a_term_is_not_a_definition():
    # "llm" + "work" appear, but the alias "how does an llm work" covers little of the question.
    match = question_bank.match(
        "Okay, so in the ministry, which team did you work with, and did the LLM part of that project go to production?"
    )
    assert match is None or not (match.is_strong and match.entry.bank == "technical"), (
        f"{match.entry.id} {match.mode} {match.score:.2f}"
    )


def test_bank_answer_survives_scores_above_one():
    # Intent/topic bonuses push scores past 1.0; the GeneratedAnswer must still validate.
    from app.models.candidate import AnswerLengthMode
    from app.services.answer_generator import answer_generator

    match = question_bank.match("How long did you work in Kuwait?")
    assert match is not None and match.score > 1.0
    answer = answer_generator._answer_from_bank(
        match=match, question="How long did you work in Kuwait?", asked="How long did you work in Kuwait?",
        question_id="t", length_mode=AnswerLengthMode.STANDARD, elapsed_ms=1.0,
    )
    assert answer.answer_en.startswith("Thirteen years")
    assert answer.candidate_evidence[0].relevance <= 1.0


def test_normalization_collapses_variants():
    assert normalize_for_matching("Have you used Lang Chain?") == "have you used langchain"
    assert normalize_for_matching("tell me about b tech") == "tell me about btec"
    assert normalize_for_matching("what is m c p") == "what is mcp"
    # Ordinary words are untouched.
    assert normalize_for_matching("for a good reason") == "for a good reason"


def test_display_repair():
    assert (
        canonicalize_display("Have you used Lang Chain and Langraph in the Btech project?")
        == "Have you used LangChain and LangGraph in the BTEC project?"
    )
    assert canonicalize_display("How do you react to feedback in a project?") == (
        "How do you react to feedback in a project?"
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Design an Agentic RAG system for our organization.", "hard.agentic_rag_design"),
        ("Why do you need an agent here? Why not normal RAG?", "hard.why_agent_not_rag"),
        ("When should an agent stop using tools?", "hard.agent_stop_tools"),
        ("What if the agent chooses the wrong tool?", "hard.wrong_tool"),
        ("What if two agents disagree?", "hard.agents_disagree"),
        ("How do you prevent an agent from looping forever?", "hard.agent_loop"),
        ("How do you give an agent memory without leaking sensitive data?", "hard.agent_memory_privacy"),
        ("Would you use LangGraph, n8n, or plain Python for this workflow? Why?", "hard.langgraph_vs_n8n_vs_python"),
        ("Why ChromaDB and not Qdrant or PostgreSQL with pgvector?", "hard.why_not_chroma_prod"),
        ("How would you debug a bad RAG answer step by step?", "hard.rag_debug_steps"),
        ("How do you know whether the problem is the embedding model, retrieval, prompt, or LLM?", "hard.which_rag_layer_failed"),
        ("How would you design RAG for Arabic and English documents?", "hard.rag_arabic_english"),
        ("What changes when documents contain tables, PDFs, scanned files, or images?", "hard.rag_pdfs_tables_scans"),
        ("What happens when the user asks a question that requires information from three different documents?", "hard.three_documents"),
        ("Can an agent write directly to a database?", "hard.agent_write_db"),
        ("What is the difference between an AI Agent, Agentic Workflow, Multi-Agent System, and Agent Orchestrator?", "hard.agent_terms_difference"),
        ("Show me the architecture of one of your AI projects from user request until final response.", "hard.project_architecture_e2e"),
        ("If I remove LangChain from your system, can it still work?", "hard.remove_langchain"),
        ("If I remove the LLM from your RAG system, what parts still remain?", "hard.remove_llm_from_rag"),
        ("What would you monitor in production: latency, cost, retrieval quality, hallucination, tool errors?", "hard.production_monitoring"),
    ],
)
def test_hard_scenario_questions(text, expected):
    match = question_bank.match(text)
    assert match is not None, text
    assert match.entry.id == expected, f"{text!r} -> {match.entry.id} ({match.mode}, {match.score:.2f}) runner={match.runner_up}"
    assert match.is_strong, f"{text!r} only {match.mode} ({match.score:.2f})"

