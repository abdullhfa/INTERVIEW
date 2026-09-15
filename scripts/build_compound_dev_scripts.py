"""Build compound-dev pack — 40 NEW compound cases for Track B (not Holdout).

Does not copy final-unseen-holdout texts. Audio via synthesize_compound_dev.py.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "frontend" / "public" / "voice-drill" / "compound-dev"

# Gold IDs may list siblings that the bank returns for the same part (eval labels only).
CASES: list[dict] = [
    {
        "t": "Define RAG briefly, and say why you prefer it over baking yearly rules into weights.",
        "ids": ["tech.rag_what", "tech.rag_vs_finetuning", "tech.rag_build"],
        "parts": ["RAG definition", "Why RAG vs fine-tune"],
    },
    {
        "t": "What are embeddings and cosine similarity, and why is the similarity checker not called RAG?",
        "ids": ["tech.cosine_semantic_search", "tech.embeddings", "proj.similarity.is_rag", "proj.similarity.stack"],
        "parts": ["Embeddings/cosine", "Not RAG"],
    },
    {
        "t": "Explain guardrails, then point to where a human must approve before saving a generated item.",
        "ids": [
            "tech.guardrails_what",
            "hard.hitl_where",
            "hard.agent_terms_difference",
        ],
        "parts": ["Guardrails", "HITL gate"],
    },
    {
        "t": "Give a short agentic AI definition, then when plain RAG without tools is enough.",
        "ids": ["tech.agentic_what", "hard.why_agent_not_rag", "tech.rag_vs_finetuning"],
        "parts": ["Agentic def", "When RAG enough"],
    },
    {
        "t": "What is LangGraph, and would you pick it, n8n, or plain Python for approval gates?",
        "ids": ["tech.what_is_langgraph", "cv.langgraph", "hard.langgraph_vs_n8n_vs_python"],
        "parts": ["LangGraph", "Orchestrator choice"],
    },
    {
        "t": "Define precision and recall, and which mattered more for early-warning students.",
        "ids": ["tech.precision_recall", "proj.early_warning.metric", "proj.early_warning.describe"],
        "parts": ["Precision/recall", "Early-warning metric"],
    },
    {
        "t": "What is hallucination, and how do you reduce it without treating temperature as a truth switch?",
        "ids": ["tech.hallucination_what", "tech.hallucination_prevent", "cv.hallucination_in_projects"],
        "parts": ["Hallucination def", "Prevention"],
    },
    {
        "t": "On empty retrieval, what should happen, and how do you block invented finance numbers?",
        "ids": ["hard.empty_retrieval", "tech.no_wrong_info_finance", "tech.rag_prevent_invented_numbers"],
        "parts": ["Empty retrieval", "No invented numbers"],
    },
    {
        "t": "Describe metadata filtering and how it supports isolation between school tenants.",
        "ids": ["tech.metadata_filtering", "hard.tenant_isolation", "tech.vector_db_choice"],
        "parts": ["Metadata filter", "Tenant isolation"],
    },
    {
        "t": "What is chunk size with overlap, and what breaks if you stuff twenty chunks into one prompt?",
        "ids": ["tech.chunk_size", "hard.context_stuffing"],
        "parts": ["Chunk size", "Context stuffing"],
    },
    {
        "t": "How do you write a solid prompt, and how do you stop retrieved PDFs from becoming instructions?",
        "ids": ["tech.prompt_engineering", "hard.injection_in_pdf"],
        "parts": ["Prompt craft", "Injection control"],
    },
    {
        "t": "What is WER, and how else do you judge transcription quality for this coach?",
        "ids": ["tech.wer", "tech.transcription_quality"],
        "parts": ["WER", "Transcription quality"],
    },
    {
        "t": "Have you used Pydantic, and where does schema validation sit relative to teacher approval?",
        "ids": ["cv.pydantic", "hard.teacher_rejects"],
        "parts": ["Pydantic", "Teacher approval"],
    },
    {
        "t": "What is LoRA at a high level, and why is it not your default for yearly regulation updates?",
        "ids": ["tech.lora", "tech.rag_vs_finetuning", "hard.not_finetune_first"],
        "parts": ["LoRA", "Not default for regs"],
    },
    {
        "t": "Separate indexing from retrieval, then say what you check when answers are wrong but hits look populated.",
        "ids": [
            "tech.rag_two_phases",
            "tech.rag_debugging",
            "hard.which_rag_layer_failed",
            "hard.rag_debug_steps",
        ],
        "parts": ["Two phases", "Debug wrong answers"],
    },
    {
        "t": "What is a vector store for, and why did you pick Chroma in practice?",
        "ids": ["tech.vector_db_choice", "cv.chromadb", "cv.vector_db"],
        "parts": ["Vector store role", "Chroma"],
    },
    {
        "t": "How do you redact PII in logs, and why does that matter near student cases?",
        "ids": ["tech.pii_redaction", "hard.tenant_isolation", "cv.student_pii"],
        "parts": ["PII redaction", "Student safety"],
    },
    {
        "t": "When should an agent stop calling tools, and how do you avoid double side effects after resume?",
        "ids": ["hard.agent_stop_tools", "hard.interrupt_side_effects"],
        "parts": ["Stop tools", "No double side effects"],
    },
    {
        "t": "Explain temperature in generation, and why zero is safer for factual ministry answers.",
        "ids": ["tech.temperature", "tech.hallucination_prevent"],
        "parts": ["Temperature", "Safer factual"],
    },
    {
        "t": "What is HITL, and what must never be saved after a teacher rejects a draft?",
        "ids": ["hard.hitl_where", "hard.teacher_rejects", "hard.agent_terms_difference"],
        "parts": ["HITL", "Reject path"],
    },
    {
        "t": "Is plain Python still agentic without LangGraph, and what graph feature would you still want later?",
        "ids": [
            "hard.plain_python_still_agentic",
            "tech.what_is_langgraph",
            "cv.langgraph",
            "hard.langgraph_vs_n8n_vs_python",
        ],
        "parts": ["Plain Python agentic", "LangGraph later"],
    },
    {
        "t": "How do you debug which RAG layer failed, and when do you abstain instead of regenerating?",
        "ids": [
            "hard.which_rag_layer_failed",
            "hard.empty_retrieval",
            "tech.rag_debugging",
            "hard.rag_debug_steps",
        ],
        "parts": ["Which layer", "Abstain"],
    },
    {
        "t": "Can you stream a government answer before validation, and what is the safer order?",
        "ids": ["hard.streaming_vs_validate", "tech.hallucination_prevent"],
        "parts": ["Streaming vs validate", "Safety order"],
    },
    {
        "t": "What role does the similarity tool play for teachers, and why is it decision support not auto-grading?",
        "ids": [
            "proj.similarity.role",
            "hard.hitl_where",
            "proj.similarity.is_rag",
            "proj.similarity.describe",
        ],
        "parts": ["Similarity role", "Not auto-grader"],
    },
    {
        "t": "Walk indexing versus query-time retrieval, then name one faithfulness check after generation.",
        "ids": ["tech.rag_two_phases", "tech.hallucination_prevent"],
        "parts": ["Index vs query", "Faithfulness"],
    },
    {
        "t": "Define embeddings simply, and say what cosine similarity gives you in search.",
        "ids": ["tech.embeddings", "tech.cosine_semantic_search"],
        "parts": ["Embeddings", "Cosine"],
    },
    {
        "t": "Why not fine-tune first for changing PDFs, and what do you re-index instead?",
        "ids": ["hard.not_finetune_first", "tech.rag_vs_finetuning", "cv.fine_tuning"],
        "parts": ["Not fine-tune first", "Re-index"],
    },
    {
        "t": "How do you keep campus A from reading campus B via search, and where do filters apply?",
        "ids": [
            "hard.tenant_isolation",
            "tech.metadata_filtering",
            "tech.rag_access_control",
            "tech.vector_db_choice",
        ],
        "parts": ["Isolation", "Filter placement"],
    },
    {
        "t": "What is prompt engineering here, and how does structured output with Pydantic help?",
        "ids": [
            "tech.prompt_engineering",
            "cv.pydantic",
            "tech.structured_output",
            "hard.teacher_rejects",
        ],
        "parts": ["Prompting", "Structured output"],
    },
    {
        "t": "Explain RAG build briefly, then how two-phase retrieve-then-generate stays grounded.",
        "ids": ["tech.rag_build", "tech.rag_two_phases", "tech.rag_what"],
        "parts": ["RAG build", "Two phases"],
    },
    {
        "t": "What happens on weak top-k, and how do you prevent inventing citation numbers?",
        "ids": ["hard.empty_retrieval", "tech.rag_prevent_invented_numbers", "tech.no_wrong_info_finance"],
        "parts": ["Weak/empty top-k", "No invented numbers"],
    },
    {
        "t": "Define agentic workflows, then how you interrupt before an email send.",
        "ids": ["tech.agentic_what", "hard.interrupt_side_effects", "hard.hitl_where"],
        "parts": ["Agentic", "Interrupt before send"],
    },
    {
        "t": "What is Chroma used for, and how does metadata filtering sit on top of it?",
        "ids": ["cv.chromadb", "tech.metadata_filtering", "tech.vector_db_choice", "tech.what_is_chromadb"],
        "parts": ["Chroma", "Metadata"],
    },
    {
        "t": "How do LangChain helpers differ from LangGraph control flow, and when is each enough?",
        "ids": [
            "tech.langgraph_vs_langchain",
            "tech.what_is_langgraph",
            "cv.langgraph",
            "hard.langgraph_vs_n8n_vs_python",
        ],
        "parts": ["LangChain vs Graph", "When enough"],
    },
    {
        "t": "What is good enough to launch for teachers, and which metric would you refuse to vanity-chase?",
        "ids": ["tech.good_enough_to_launch", "tech.evaluate_classification"],
        "parts": ["Launch bar", "No vanity metric"],
    },
    {
        "t": "Explain access control for retrieval, and how tenant isolation depends on it.",
        "ids": [
            "tech.rag_access_control",
            "hard.tenant_isolation",
            "hard.secure_rag",
            "tech.vector_db_choice",
        ],
        "parts": ["Access control", "Tenants"],
    },
    {
        "t": "What is question generation in the BTEC path, and where does teacher reject stop persistence?",
        "ids": ["moe.question_generation", "hard.teacher_rejects", "hard.hitl_where"],
        "parts": ["QG path", "Reject"],
    },
    {
        "t": "How do you judge transcription quality, and what is WER useful for versus not?",
        "ids": ["tech.transcription_quality", "tech.wer"],
        "parts": ["Quality bar", "WER limits"],
    },
    {
        "t": "Define hallucination, empty-retrieval abstain, and one post-generation number check — in that order.",
        "ids": ["tech.hallucination_what", "hard.empty_retrieval", "tech.rag_prevent_invented_numbers", "tech.hallucination_prevent"],
        "parts": ["Hallucination", "Abstain", "Number check"],
    },
    {
        "t": "What is RAG, why use it for question generation, what if retrieval fails, and how do you validate JSON output?",
        "ids": ["tech.rag_what", "tech.rag_vs_finetuning", "hard.empty_retrieval", "cv.pydantic", "tech.rag_build"],
        "parts": ["RAG", "Why RAG", "Empty retrieval", "Validate JSON"],
    },
]


def _resolve_ids(raw_ids: list[str]) -> list[str]:
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
    accents = ["indian", "jordanian", "egyptian", "emirati"]
    conditions = ["clean", "office", "clean", "office"]
    warm = [
        {
            "id": "cdev_warm_01",
            "question_type": "compound",
            "condition": "clean",
            "accent": "indian",
            "transcript": "What is an embedding, and what is cosine similarity used for?",
            "expected_intent_ids": _resolve_ids(["tech.embeddings", "tech.cosine_semantic_search"]),
            "requested_parts": ["Embeddings", "Cosine"],
            "file": "audio/cdev_warm_01.wav",
            "warmup": True,
            "pack": "compound-dev",
            "eval_only": True,
        }
    ]
    for i, case in enumerate(CASES, start=1):
        sid = f"cdev_{i:03d}"
        rows.append(
            {
                "id": sid,
                "question_type": "compound",
                "condition": conditions[(i - 1) % len(conditions)],
                "accent": accents[(i - 1) % len(accents)],
                "transcript": case["t"],
                "expected_intent_ids": _resolve_ids(list(case["ids"])),
                "requested_parts": list(case["parts"]),
                "file": f"audio/{sid}.wav",
                "warmup": False,
                "pack": "compound-dev",
                "eval_only": True,
            }
        )
    assert len(rows) == 40
    return warm + rows


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "audio").mkdir(parents=True, exist_ok=True)
    rows = build()
    scored = [r for r in rows if not r.get("warmup")]
    (PACK / "scripts.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (PACK / "manifest.json").write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {
        "name": "compound-dev",
        "track": "B",
        "scored_cases": 40,
        "warmup_cases": 1,
        "not_final_holdout": True,
        "audio_status": "pending_synthesis",
    }
    (PACK / "pack_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (PACK / "README.md").write_text(
        "# Compound Dev (Track B)\n\nNot Final Holdout. New compound wording only.\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows ({len(scored)} scored) -> {PACK}")


if __name__ == "__main__":
    main()
