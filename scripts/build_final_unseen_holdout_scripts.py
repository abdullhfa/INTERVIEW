"""Build Final Unseen Holdout scripts.json — 120 NEW eval-only cases (text + labels).

Does NOT copy development pack transcripts. Does NOT synthesize audio.
Audio must be produced separately into audio/*.wav matching file names.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "frontend" / "public" / "voice-drill" / "final-unseen-holdout"

QUESTION_TYPES = [
    "ultra_short",
    "short",
    "medium",
    "long",
    "very_long",
    "compound",
    "indirect_paraphrase",
    "follow_up_contextual",
]
CONDITIONS = ["clean", "office", "poor", "far", "fast"]
ACCENTS = ["indian", "jordanian", "egyptian", "emirati"]

# 15 per type — brand-new phrasings for holdout (not copied from length/accent packs).
CASES: dict[str, list[dict]] = {
    "ultra_short": [
        {"t": "Why precision?", "ids": ["tech.precision_recall"]},
        {"t": "Define embeddings.", "ids": ["tech.embeddings"]},
        {"t": "What is Chroma?", "ids": ["cv.chromadb", "tech.vector_db_choice"]},
        {"t": "Why guardrails?", "ids": ["tech.guardrails_what"]},
        {"t": "Agent or RAG?", "ids": ["hard.why_agent_not_rag", "proj.similarity.is_rag"]},
        {"t": "What is WER?", "ids": ["tech.wer"]},
        {"t": "Why abstain?", "ids": ["hard.empty_retrieval", "tech.hallucination_prevent"]},
        {"t": "Define LoRA.", "ids": ["tech.lora"]},
        {"t": "What is HITL?", "ids": ["hard.hitl_where"]},
        {"t": "Why metadata?", "ids": ["tech.metadata_filtering", "hard.tenant_isolation"]},
        {"t": "What is Pydantic?", "ids": ["cv.pydantic"]},
        {"t": "Why re-rank?", "ids": ["tech.rag_two_phases", "tech.rag_debugging"]},
        {"t": "Define hallucination.", "ids": ["tech.hallucination_what"]},
        {"t": "What is tenant isolation?", "ids": ["hard.tenant_isolation"]},
        {"t": "Why temperature zero?", "ids": ["tech.temperature", "tech.hallucination_prevent"]},
    ],
    "short": [
        {"t": "What is retrieval augmented generation in one sentence?", "ids": ["tech.rag_what"]},
        {"t": "How do you define an agentic workflow briefly?", "ids": ["tech.agentic_what"]},
        {"t": "What problem does LangGraph solve for you?", "ids": ["tech.what_is_langgraph"]},
        {"t": "When do you refuse to answer from model memory?", "ids": ["hard.empty_retrieval"]},
        {"t": "What is the job of a vector store here?", "ids": ["tech.vector_db_choice", "cv.chromadb"]},
        {"t": "How do you keep personal data out of logs?", "ids": ["tech.pii_redaction"]},
        {"t": "What makes a chunk size choice good enough?", "ids": ["tech.chunk_size"]},
        {"t": "Why not trust accuracy alone on imbalanced data?", "ids": ["tech.precision_recall"]},
        {"t": "What is a faithfulness check after generation?", "ids": ["tech.hallucination_prevent"]},
        {"t": "How do you know transcription quality is usable?", "ids": ["tech.transcription_quality", "tech.wer"]},
        {"t": "What does cosine similarity tell you in search?", "ids": ["tech.cosine_semantic_search"]},
        {"t": "When is fine-tuning the wrong first move?", "ids": ["tech.rag_vs_finetuning", "hard.not_finetune_first"]},
        {"t": "What is structured output used for in your stack?", "ids": ["cv.pydantic", "tech.prompt_engineering"]},
        {"t": "How do you stop inventing financial numbers?", "ids": ["tech.no_wrong_info_finance", "tech.rag_prevent_invented_numbers"]},
        {"t": "What is the teacher approval step protecting?", "ids": ["hard.hitl_where", "hard.teacher_rejects"]},
    ],
    "medium": [
        {
            "t": "Walk me through how retrieved passages become a grounded answer before the model speaks freely.",
            "ids": ["tech.rag_two_phases", "tech.rag_build"],
        },
        {
            "t": "In the assignment checker, why prefer embedding similarity over asking an LLM to judge sameness?",
            "ids": ["proj.similarity.stack", "proj.similarity.is_rag"],
        },
        {
            "t": "How does question generation stay blocked until a human confirms the draft is safe to save?",
            "ids": ["hard.teacher_rejects", "hard.hitl_where"],
        },
        {
            "t": "If LangGraph is not in production yet, why still study it for complex ministry workflows?",
            "ids": ["hard.langgraph_vs_n8n_vs_python", "tech.what_is_langgraph"],
        },
        {
            "t": "How do school-level metadata filters prevent one campus from reading another campus files?",
            "ids": ["hard.tenant_isolation", "tech.metadata_filtering"],
        },
        {
            "t": "What should happen when top-k returns only weak or empty context for a regulation question?",
            "ids": ["hard.empty_retrieval"],
        },
        {
            "t": "Explain how RAG updates knowledge differently from changing behavior with fine-tuning.",
            "ids": ["tech.rag_vs_finetuning"],
        },
        {
            "t": "Why is human sign-off still required when the draft already looks fluent and complete?",
            "ids": ["tech.hallucination_prevent", "hard.hitl_where"],
        },
        {
            "t": "How would you debug whether the failure is embedding, retrieval, prompt, or the generator?",
            "ids": ["hard.which_rag_layer_failed", "tech.rag_debugging"],
        },
        {
            "t": "What changes in your answer strategy when the user mixes Arabic and English in one query?",
            "ids": ["hard.mixed_language_query"],
        },
        {
            "t": "How do you keep an agent from looping on tools forever without finishing the user task?",
            "ids": ["hard.agent_stop_tools"],
        },
        {
            "t": "Why can stuffing many chunks into the prompt still produce a worse answer?",
            "ids": ["hard.context_stuffing"],
        },
        {
            "t": "How do you decide the system is good enough to launch for teachers without chasing a vanity metric?",
            "ids": ["tech.good_enough_to_launch"],
        },
        {
            "t": "What is the practical difference between LangChain helpers and a LangGraph-style control flow?",
            "ids": ["tech.langgraph_vs_langchain"],
        },
        {
            "t": "How does your BTEC path validate generated JSON before anything is persisted?",
            "ids": ["hard.teacher_rejects", "cv.pydantic"],
        },
    ],
    "long": [
        {
            "t": (
                "Please explain end to end how a teacher request becomes retrieved unit content, "
                "a structured draft, validation, and only then a saved bank item, including where "
                "you refuse to invent missing learning outcomes."
            ),
            "ids": ["moe.question_generation", "hard.teacher_rejects", "tech.rag_build"],
        },
        {
            "t": (
                "Compare a pure similarity pipeline without generation against a full RAG path, "
                "and tell me which ministry tools should stay non-generative and why that boundary matters."
            ),
            "ids": ["proj.similarity.is_rag", "proj.similarity.stack"],
        },
        {
            "t": (
                "If regulations change every year, argue whether you would retrain weights, re-index "
                "documents, or do both, and what evidence you would show auditors for each choice."
            ),
            "ids": ["tech.rag_vs_finetuning"],
        },
        {
            "t": (
                "Describe how you would design access control so retrieval never surfaces another "
                "school's assignments even when embeddings are similar across tenants."
            ),
            "ids": ["hard.tenant_isolation", "tech.rag_access_control"],
        },
        {
            "t": (
                "Walk through a production incident where retrieval looked fine but answers still "
                "hallucinated numbers, and list the checks you would add after generation."
            ),
            "ids": ["tech.hallucination_prevent", "tech.rag_prevent_invented_numbers"],
        },
        {
            "t": (
                "Explain when you would pick plain Python orchestration, when n8n, and when LangGraph, "
                "using a ministry workflow that needs interrupts and retries."
            ),
            "ids": ["hard.langgraph_vs_n8n_vs_python"],
        },
        {
            "t": (
                "How do you evaluate an early-warning classifier when the positive class is rare, "
                "and which error type is more expensive for students and teachers?"
            ),
            "ids": ["proj.early_warning.metric", "tech.precision_recall"],
        },
        {
            "t": (
                "Describe a safe interrupt pattern so an agent prepares an email but never sends it "
                "twice after a human resumes the graph."
            ),
            "ids": ["hard.hitl_where", "hard.interrupt_side_effects"],
        },
        {
            "t": (
                "If a retrieved PDF tries prompt injection and asks to dump all documents, what "
                "controls keep the system from following that instruction?"
            ),
            "ids": ["hard.injection_in_pdf"],
        },
        {
            "t": (
                "How would you measure whether Whisper transcription quality is good enough for "
                "intent matching without pretending word error rate alone is the product metric?"
            ),
            "ids": ["tech.wer", "tech.transcription_quality"],
        },
        {
            "t": (
                "Tell me how chunk overlap, metadata filters, and optional reranking interact at "
                "query time, and which part you have actually shipped versus only studied."
            ),
            "ids": ["tech.rag_two_phases", "tech.chunk_size"],
        },
        {
            "t": (
                "Explain your approach to personally identifiable information in prompts and logs "
                "when teachers discuss student cases near an AI tool."
            ),
            "ids": ["tech.pii_redaction"],
        },
        {
            "t": (
                "If the teacher rejects a generated question with a short comment, what does the "
                "system do next, and what must never be saved?"
            ),
            "ids": ["hard.teacher_rejects"],
        },
        {
            "t": (
                "How do you keep streaming tokens from becoming a public answer in a government "
                "RAG app before validation and approval complete?"
            ),
            "ids": ["hard.streaming_vs_validate"],
        },
        {
            "t": (
                "Describe how you would prove to a skeptical director that the tool is decision "
                "support, not an automatic grader that marks students alone."
            ),
            "ids": ["proj.similarity.role", "hard.hitl_where"],
        },
    ],
    "very_long": [
        {
            "t": (
                "I want a complete narrative of your BTEC RAG system for interview depth: start from "
                "authorized login and unit selection, then indexing versus query-time retrieval, "
                "prompt construction, JSON validation, teacher approval, empty-retrieval abstain, "
                "and finally how you would explain a wrong answer without blaming the model alone. "
                "Please keep the order clear and name the failure points you watch in production."
            ),
            "ids": ["moe.question_generation", "tech.rag_two_phases", "hard.empty_retrieval"],
        },
        {
            "t": (
                "Compare three architectures for the same ministry need: embeddings-only similarity, "
                "classic RAG with citations, and an agent that can call tools and wait for humans. "
                "For each, say what it is good at, what it must never do, and which of your projects "
                "already matches that pattern in real use rather than in slides."
            ),
            "ids": ["proj.similarity.is_rag", "hard.why_agent_not_rag", "tech.rag_what"],
        },
        {
            "t": (
                "Imagine auditors ask why you did not fine-tune on every regulation PDF. Give a "
                "careful answer covering knowledge freshness, citation needs, cost, evaluation, "
                "and the narrow cases where fine-tuning or adapters might still help behavior "
                "without becoming the source of legal facts."
            ),
            "ids": ["tech.rag_vs_finetuning", "hard.not_finetune_first"],
        },
        {
            "t": (
                "Design a tenant-safe retrieval story for multiple schools sharing one platform: "
                "metadata design, filter placement before search, what leaks if you filter too late, "
                "how logs should look, and how you would test that school A cannot read school B "
                "even when questions are nearly identical."
            ),
            "ids": ["hard.tenant_isolation", "tech.rag_access_control"],
        },
        {
            "t": (
                "Walk through a LangGraph-style interview answer that stays honest about production "
                "experience: what graph features matter for interrupts and retries, what you have "
                "not run at scale, and how you would still defend a plain Python agentic flow that "
                "is careful with side effects and human gates."
            ),
            "ids": ["hard.langgraph_vs_n8n_vs_python", "hard.plain_python_still_agentic"],
        },
        {
            "t": (
                "Give a long debugging playbook for a RAG answer that sounds confident but is wrong: "
                "how you separate indexing bugs from retrieval bugs from prompt bugs from model bugs, "
                "which metrics you look at, and when you force abstain instead of another regenerate."
            ),
            "ids": ["tech.rag_debugging", "hard.which_rag_layer_failed", "hard.empty_retrieval"],
        },
        {
            "t": (
                "Explain a full quality bar for launching an education AI feature: offline test set "
                "discipline, confusion-aware metrics, teacher review loops, latency budgets after "
                "speech ends, and the difference between a demo that impresses a meeting and a tool "
                "teachers still open next month."
            ),
            "ids": ["tech.good_enough_to_launch", "tech.evaluate_classification"],
        },
        {
            "t": (
                "Describe how Whisper, technical term repair, intent matching, and bank answers "
                "connect in a live interview coach, including what you freeze versus what you allow "
                "to recover under poor or far audio without lowering safety on clean speech."
            ),
            "ids": ["tech.transcription_quality", "tech.wer"],
        },
        {
            "t": (
                "Narrate a compound ministry scenario where the interviewer asks for architecture, "
                "safety, and personal ownership in one breath, and show how you would answer each "
                "part in order without dropping the safety constraints or inventing CV claims."
            ),
            "ids": ["hard.hitl_where", "tech.hallucination_prevent", "gen.leadership"],
        },
        {
            "t": (
                "Provide an extended explanation of precision, recall, and operational cost in the "
                "early-warning student support setting, including why a high accuracy headline can "
                "still hide a harmful miss rate and how you would present that to non-technical staff."
            ),
            "ids": ["proj.early_warning.metric", "tech.precision_recall"],
        },
        {
            "t": (
                "Detail a safe generation contract for financial or regulatory answers: grounding, "
                "I do not know, schema checks, number-in-source rules, human approval, and what you "
                "do when retrieval is empty but the user still demands a fluent reply."
            ),
            "ids": ["tech.no_wrong_info_finance", "tech.hallucination_prevent", "hard.empty_retrieval"],
        },
        {
            "t": (
                "Give a thorough comparison of chunking strategy tradeoffs for policy documents: "
                "too small, too large, overlap, heading-aware splits, and how those choices show up "
                "later as retrieval misses or bloated prompts."
            ),
            "ids": ["tech.chunk_size", "tech.rag_build"],
        },
        {
            "t": (
                "Explain, at interview length, how you would monitor a live RAG service after launch: "
                "latency, abstain rate, teacher reject reasons, retrieval emptiness, citation failures, "
                "and when you roll back a prompt change versus a model change."
            ),
            "ids": ["tech.good_enough_to_launch", "hard.teacher_rejects"],
        },
        {
            "t": (
                "Describe an end-to-end story from microphone speech to a spoken bank answer in this "
                "coach app, naming VAD end conditions, transcription risk, semantic recovery triggers, "
                "and when the system must stay silent instead of reading the wrong prepared answer."
            ),
            "ids": ["tech.transcription_quality"],
        },
        {
            "t": (
                "Offer a long-form answer on career judgment: generative work since recent years on top "
                "of longer applied ML and payments experience, what senior means for you, and how that "
                "shows up as refusing unsafe automation rather than chasing every new framework name."
            ),
            "ids": ["gen.leadership", "gen.why_ai_field"],
        },
    ],
    "compound": [
        {
            "t": "What is RAG, and why did you choose it for question generation instead of fine-tuning the regulations into the model?",
            "ids": ["tech.rag_what", "tech.rag_vs_finetuning"],
        },
        {
            "t": "Explain embeddings and cosine similarity, then tell me why the similarity checker is not a RAG system.",
            "ids": ["tech.cosine_semantic_search", "proj.similarity.is_rag"],
        },
        {
            "t": "What are guardrails, and where exactly do you put a human in the loop before saving a generated question?",
            "ids": ["tech.guardrails_what", "hard.hitl_where"],
        },
        {
            "t": "Define agentic AI briefly, then say when a normal RAG path is enough without tools.",
            "ids": ["tech.agentic_what", "hard.why_agent_not_rag"],
        },
        {
            "t": "What is LangGraph, and would you use it, n8n, or plain Python for a workflow with approval gates?",
            "ids": ["tech.what_is_langgraph", "hard.langgraph_vs_n8n_vs_python"],
        },
        {
            "t": "Explain precision and recall, and which one mattered more in early warning and why.",
            "ids": ["tech.precision_recall", "proj.early_warning.metric"],
        },
        {
            "t": "What is hallucination, and how do you reduce it without pretending temperature alone fixes truth?",
            "ids": ["tech.hallucination_what", "tech.hallucination_prevent"],
        },
        {
            "t": "What should the system do on empty retrieval, and how do you stop invented numbers in finance-like answers?",
            "ids": ["hard.empty_retrieval", "tech.no_wrong_info_finance"],
        },
        {
            "t": "Describe metadata filtering and how it supports tenant isolation between schools.",
            "ids": ["tech.metadata_filtering", "hard.tenant_isolation"],
        },
        {
            "t": "What is chunk size and overlap, and what goes wrong if you stuff twenty chunks into one prompt?",
            "ids": ["tech.chunk_size", "hard.context_stuffing"],
        },
        {
            "t": "How do you write a good prompt, and how do you keep retrieved documents from becoming instructions?",
            "ids": ["tech.prompt_engineering"],
        },
        {
            "t": "What is WER, and how else do you judge whether transcription is good enough for this interview coach?",
            "ids": ["tech.wer", "tech.transcription_quality"],
        },
        {
            "t": "Have you used Pydantic, and where does schema validation sit relative to teacher approval?",
            "ids": ["cv.pydantic", "hard.teacher_rejects"],
        },
        {
            "t": "What is LoRA at a high level, and why is it still not your default way to update yearly regulations?",
            "ids": ["tech.lora", "tech.rag_vs_finetuning"],
        },
        {
            "t": "Explain indexing versus retrieval phases, then say what you check when answers are wrong but retrieval looks populated.",
            "ids": ["tech.rag_two_phases", "tech.rag_debugging"],
        },
    ],
    "indirect_paraphrase": [
        {
            "t": "When facts move every year, do you bake them into weights or keep them outside the model?",
            "ids": ["tech.rag_vs_finetuning"],
        },
        {
            "t": "How do you make the model stick to sources instead of finishing a fluent but unsupported sentence?",
            "ids": ["tech.hallucination_prevent"],
        },
        {
            "t": "If search returns junk, should the model still answer from what it remembers?",
            "ids": ["hard.empty_retrieval"],
        },
        {
            "t": "How do you keep campus A from quietly reading campus B materials through similarity search?",
            "ids": ["hard.tenant_isolation"],
        },
        {
            "t": "Why would a checker that only ranks similar text not deserve the RAG label?",
            "ids": ["proj.similarity.is_rag"],
        },
        {
            "t": "Where does a person have to see the draft before anything becomes official?",
            "ids": ["hard.hitl_where"],
        },
        {
            "t": "If two orchestrators and raw code are options, how do you choose for interrupt-heavy flows?",
            "ids": ["hard.langgraph_vs_n8n_vs_python"],
        },
        {
            "t": "What metric do you optimize when missing a struggling student is costlier than an extra follow-up?",
            "ids": ["proj.early_warning.metric", "tech.precision_recall"],
        },
        {
            "t": "How do you know which layer broke when the answer is wrong but the UI still looks healthy?",
            "ids": ["hard.which_rag_layer_failed"],
        },
        {
            "t": "What happens after a teacher says no to a generated item?",
            "ids": ["hard.teacher_rejects"],
        },
        {
            "t": "How do you avoid sending the same side effect twice after an approval resume?",
            "ids": ["hard.interrupt_side_effects", "hard.hitl_where"],
        },
        {
            "t": "If a document tells the model to ignore prior rules, what stops that from winning?",
            "ids": ["hard.injection_in_pdf"],
        },
        {
            "t": "Why can adding more context chunks make the answer worse rather than safer?",
            "ids": ["hard.context_stuffing"],
        },
        {
            "t": "How do you talk about senior judgment without turning it into a years contest?",
            "ids": ["gen.leadership"],
        },
        {
            "t": "What is the smallest honest description of what Whisper does versus what an agent does?",
            "ids": ["tech.wer", "tech.agentic_what"],
        },
    ],
    "follow_up_contextual": [
        {
            "t": "And why that metric instead of accuracy?",
            "ids": ["proj.early_warning.metric", "tech.precision_recall"],
            "context_prior": "We discussed early-warning classification for students who need support.",
        },
        {
            "t": "What would you change if retrieval came back empty in that same flow?",
            "ids": ["hard.empty_retrieval"],
            "context_prior": "We just walked through BTEC question generation with retrieval and validation.",
        },
        {
            "t": "Where does the human gate sit in the graph you just described?",
            "ids": ["hard.hitl_where"],
            "context_prior": "Candidate explained an agentic workflow with tools and retries.",
        },
        {
            "t": "Does that make the similarity tool a RAG system?",
            "ids": ["proj.similarity.is_rag"],
            "context_prior": "Candidate described embeddings and cosine scoring for assignment similarity.",
        },
        {
            "t": "Would fine-tuning fix the yearly regulation change problem you mentioned?",
            "ids": ["tech.rag_vs_finetuning"],
            "context_prior": "Discussion about regulations that change every year.",
        },
        {
            "t": "How do you keep school B out if embeddings still look close?",
            "ids": ["hard.tenant_isolation"],
            "context_prior": "Talking about multi-school document search.",
        },
        {
            "t": "What do you do with the reject reason after that no?",
            "ids": ["hard.teacher_rejects"],
            "context_prior": "Teacher approval path for generated questions.",
        },
        {
            "t": "Is LangGraph required for that to still be agentic?",
            "ids": ["hard.plain_python_still_agentic", "tech.what_is_langgraph"],
            "context_prior": "Candidate described a Python orchestration with tools and a human gate.",
        },
        {
            "t": "Which layer would you inspect first if citations looked right but numbers were invented?",
            "ids": ["tech.rag_debugging", "tech.rag_prevent_invented_numbers"],
            "context_prior": "Grounded generation with citation requirements.",
        },
        {
            "t": "Can you stream that to the user before approval?",
            "ids": ["hard.streaming_vs_validate"],
            "context_prior": "Government RAG drafting answers for officers.",
        },
        {
            "t": "What if the PDF itself contains an injection instruction?",
            "ids": ["hard.injection_in_pdf"],
            "context_prior": "Retrieval safety and untrusted documents.",
        },
        {
            "t": "Why not just raise temperature for more creativity there?",
            "ids": ["tech.hallucination_prevent", "tech.temperature"],
            "context_prior": "Hallucination controls on factual ministry answers.",
        },
        {
            "t": "How does metadata filtering help in that isolation story?",
            "ids": ["tech.metadata_filtering", "hard.tenant_isolation"],
            "context_prior": "Tenant isolation between schools.",
        },
        {
            "t": "What is the next step after Pydantic validation fails?",
            "ids": ["cv.pydantic", "hard.teacher_rejects"],
            "context_prior": "Structured JSON generation for exam questions.",
        },
        {
            "t": "And how would you explain that failure to a non-technical director?",
            "ids": ["gen.leadership", "gen.why_ai_field"],
            "context_prior": "A wrong answer reached a teacher review screen.",
        },
    ],
}


def _resolve_existing_ids(raw_ids: list[str]) -> list[str]:
    """Drop IDs that are not in the bank when bank is available; keep labels otherwise."""
    try:
        import sys

        sys.path.insert(0, str(ROOT / "backend"))
        from app.services.question_bank import question_bank

        question_bank.load()
        known = {e.id for e in question_bank.entries}
        kept = [i for i in raw_ids if i in known]
        return kept or raw_ids
    except Exception:
        return raw_ids


def build() -> list[dict]:
    rows: list[dict] = []
    n = 0
    for qi, qtype in enumerate(QUESTION_TYPES):
        items = CASES[qtype]
        assert len(items) == 15, qtype
        for j, item in enumerate(items):
            n += 1
            condition = CONDITIONS[(qi * 15 + j) % len(CONDITIONS)]
            accent = ACCENTS[(qi * 3 + j * 2) % len(ACCENTS)]
            sid = f"fuh_{n:03d}"
            rows.append(
                {
                    "id": sid,
                    "question_type": qtype,
                    "condition": condition,
                    "accent": accent,
                    "transcript": item["t"],
                    "expected_intent_ids": _resolve_existing_ids(list(item["ids"])),
                    "context_prior": item.get("context_prior"),
                    "file": f"audio/{sid}.wav",
                    "warmup": False,
                    "pack": "final-unseen-holdout",
                    "eval_only": True,
                }
            )
    # Two warm-up rows (not in the 120 scored set) — short clean definitions.
    warmups = [
        {
            "id": "fuh_warm_01",
            "question_type": "short",
            "condition": "clean",
            "accent": "indian",
            "transcript": "What is an embedding vector used for in search?",
            "expected_intent_ids": _resolve_existing_ids(["tech.embeddings", "tech.cosine_semantic_search"]),
            "context_prior": None,
            "file": "audio/fuh_warm_01.wav",
            "warmup": True,
            "pack": "final-unseen-holdout",
            "eval_only": True,
        },
        {
            "id": "fuh_warm_02",
            "question_type": "short",
            "condition": "clean",
            "accent": "jordanian",
            "transcript": "What is a vector database in a RAG pipeline?",
            "expected_intent_ids": _resolve_existing_ids(["tech.vector_db_choice", "cv.chromadb"]),
            "context_prior": None,
            "file": "audio/fuh_warm_02.wav",
            "warmup": True,
            "pack": "final-unseen-holdout",
            "eval_only": True,
        },
    ]
    return warmups + rows


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "audio").mkdir(parents=True, exist_ok=True)
    rows = build()
    scored = [r for r in rows if not r.get("warmup")]
    assert len(scored) == 120
    scripts_path = PACK / "scripts.json"
    manifest_path = PACK / "manifest.json"
    scripts_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    # manifest = scored only for runners that ignore warmup flag
    manifest_path.write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {
        "name": "final-unseen-holdout",
        "eval_only": True,
        "scored_cases": 120,
        "warmup_cases": 2,
        "question_types": {t: 15 for t in QUESTION_TYPES},
        "conditions": CONDITIONS,
        "accents": ACCENTS,
        "audio_status": "pending_synthesis",
        "protocol": "backend/reports/FINAL_UNSEEN_HOLDOUT_PROTOCOL.md",
    }
    (PACK / "pack_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Wrote {scripts_path} ({len(rows)} rows incl. warmup)")
    print(f"Wrote {manifest_path} ({len(scored)} scored)")
    print("Audio WAVs not generated — synthesize into audio/ before E2E run.")


if __name__ == "__main__":
    main()
