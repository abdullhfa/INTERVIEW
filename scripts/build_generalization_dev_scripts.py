"""Build generalization-dev pack — Track C (NOT Holdout, NOT compound-dev).

New wording only. Audio via synthesize_generalization_dev.py.
Slices: medium | ultra_short | indirect | follow_up | far | poor
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "frontend" / "public" / "voice-drill" / "generalization-dev"

# Each case: transcript, gold ids (siblings OK), question_type, optional context_prior, condition.
# Do NOT copy final-unseen-holdout / holdout-v2 wording.
CASES: list[dict] = [
    # ---- medium paraphrases (12) ----
    {
        "t": "Walk me through RAG: how retrieval feeds the model before it writes the final reply.",
        "ids": ["tech.rag_what", "tech.rag_build", "tech.rag_two_phases", "cv.rag_experience"],
        "type": "medium",
        "condition": "clean",
    },
    {
        "t": "In the plagiarism helper, why embeddings plus cosine instead of calling a chat model?",
        "ids": ["proj.similarity.stack", "tech.cosine_semantic_search", "tech.embeddings"],
        "type": "medium",
        "condition": "office",
    },
    {
        "t": "Before a draft question is persisted, what validation happens and who can still reject it?",
        "ids": ["hard.teacher_rejects", "hard.hitl_where", "cv.pydantic"],
        "type": "medium",
        "condition": "clean",
    },
    {
        "t": "Why keep a human-in-the-loop approval gate even when the generator already sounds fluent?",
        "ids": ["hard.hitl_where", "hard.teacher_rejects"],
        "type": "medium",
        "condition": "office",
    },
    {
        "t": "How do you enforce tenant isolation so one school never reads another school's indexed chunks?",
        "ids": ["hard.tenant_isolation", "tech.metadata_filtering", "tech.rag_access_control"],
        "type": "medium",
        "condition": "clean",
    },
    {
        "t": "If top-k comes back empty, what should the product do instead of inventing figures?",
        "ids": ["hard.empty_retrieval", "tech.rag_prevent_invented_numbers", "tech.no_wrong_info_finance"],
        "type": "medium",
        "condition": "office",
    },
    {
        "t": "How do you stop prompt injection when a retrieved PDF tries to become an instruction to the model?",
        "ids": ["hard.injection_in_pdf", "tech.prompt_engineering", "tech.prompt_injection_what"],
        "type": "medium",
        "condition": "clean",
    },
    {
        "t": "When answers look wrong but the vector hits are non-empty, how do you debug which layer failed?",
        "ids": ["hard.which_rag_layer_failed", "tech.rag_debugging", "hard.rag_debug_steps"],
        "type": "medium",
        "condition": "office",
    },
    {
        "t": "Why not fine-tune every time a ministry PDF set changes for the year?",
        "ids": ["hard.not_finetune_first", "tech.rag_vs_finetuning"],
        "type": "medium",
        "condition": "clean",
    },
    {
        "t": "For early-warning students, which metric mattered more than chasing raw accuracy?",
        "ids": ["proj.early_warning.metric", "tech.precision_recall", "proj.early_warning.describe"],
        "type": "medium",
        "condition": "office",
    },
    {
        "t": "Would you orchestrate approval gates with LangGraph, n8n, or plain Python, and why?",
        "ids": ["hard.langgraph_vs_n8n_vs_python", "tech.what_is_langgraph", "cv.langgraph"],
        "type": "medium",
        "condition": "clean",
    },
    {
        "t": "How do you judge that transcription quality is good enough for this interview coach?",
        "ids": ["tech.transcription_quality", "tech.wer"],
        "type": "medium",
        "condition": "office",
    },
    # ---- ultra_short (12) ----
    {"t": "What is RAG?", "ids": ["tech.rag_what"], "type": "ultra_short", "condition": "clean"},
    {"t": "Define embeddings.", "ids": ["tech.embeddings"], "type": "ultra_short", "condition": "office"},
    {"t": "What is hallucination?", "ids": ["tech.hallucination_what"], "type": "ultra_short", "condition": "clean"},
    {"t": "Explain LoRA.", "ids": ["tech.lora"], "type": "ultra_short", "condition": "office"},
    {"t": "What is WER?", "ids": ["tech.wer"], "type": "ultra_short", "condition": "clean"},
    {"t": "What is temperature?", "ids": ["tech.temperature"], "type": "ultra_short", "condition": "office"},
    {"t": "What is Chroma?", "ids": ["cv.chromadb", "tech.what_is_chromadb", "tech.vector_db_choice"], "type": "ultra_short", "condition": "clean"},
    {"t": "What is human in the loop?", "ids": ["hard.hitl_where"], "type": "ultra_short", "condition": "office"},
    {"t": "Define guardrails.", "ids": ["tech.guardrails_what", "cv.guardrails"], "type": "ultra_short", "condition": "clean"},
    {"t": "What is LangGraph?", "ids": ["tech.what_is_langgraph", "cv.langgraph"], "type": "ultra_short", "condition": "office"},
    {"t": "What is chunking?", "ids": ["tech.chunk_size"], "type": "ultra_short", "condition": "clean"},
    {"t": "Explain Pydantic.", "ids": ["cv.pydantic"], "type": "ultra_short", "condition": "office"},
    # ---- indirect (12) ----
    {
        "t": "If yearly regulation PDFs change, why prefer RAG over fine-tuning instead of baking text into weights?",
        "ids": ["tech.rag_vs_finetuning", "hard.not_finetune_first", "tech.rag_what"],
        "type": "indirect",
        "condition": "clean",
    },
    {
        "t": "Suppose retrieval returns nothing useful — what is the safe user-facing behavior?",
        "ids": ["hard.empty_retrieval", "tech.hallucination_prevent"],
        "type": "indirect",
        "condition": "office",
    },
    {
        "t": "How would you keep school A from ever seeing school B's assignment store?",
        "ids": ["hard.tenant_isolation", "tech.rag_access_control", "tech.metadata_filtering"],
        "type": "indirect",
        "condition": "clean",
    },
    {
        "t": "When do you need an agent with tools instead of plain RAG retrieval alone?",
        "ids": ["hard.why_agent_not_rag", "tech.agentic_what"],
        "type": "indirect",
        "condition": "office",
    },
    {
        "t": "How do you prevent invented citation numbers and other hallucinations in finance answers?",
        "ids": ["tech.rag_prevent_invented_numbers", "tech.no_wrong_info_finance", "tech.hallucination_prevent"],
        "type": "indirect",
        "condition": "clean",
    },
    {
        "t": "Where should a teacher be able to stop a generated item from being saved?",
        "ids": ["hard.hitl_where", "hard.teacher_rejects"],
        "type": "indirect",
        "condition": "office",
    },
    {
        "t": "Is the assignment similarity checker meant to auto-grade, or only support a human decision?",
        "ids": [
            "proj.similarity.role",
            "proj.similarity.is_rag",
            "proj.similarity.describe",
            "hard.similarity_vs_qgen_arch",
        ],
        "type": "indirect",
        "condition": "clean",
    },
    {
        "t": "What goes wrong with context stuffing if you dump twenty retrieved chunks into one prompt?",
        "ids": ["hard.context_stuffing", "tech.chunk_size", "hard.pii_in_chunks"],
        "type": "indirect",
        "condition": "office",
    },
    {
        "t": "How do you keep personal student fields out of logs sent to the model?",
        "ids": ["tech.pii_redaction", "cv.student_pii", "hard.tenant_isolation"],
        "type": "indirect",
        "condition": "clean",
    },
    {
        "t": "In a government RAG app, should answers stream to the user before validation finishes?",
        "ids": ["hard.streaming_vs_validate", "tech.hallucination_prevent", "hard.secure_rag"],
        "type": "indirect",
        "condition": "office",
    },
    {
        "t": "What graph control would you still want after starting with plain Python agents?",
        "ids": ["hard.plain_python_still_agentic", "tech.what_is_langgraph", "cv.langgraph"],
        "type": "indirect",
        "condition": "clean",
    },
    {
        "t": "How do metadata filters sit on top of a vector collection in practice?",
        "ids": ["tech.metadata_filtering", "cv.chromadb", "tech.vector_db_choice"],
        "type": "indirect",
        "condition": "office",
    },
    # ---- follow_up (12) with context_prior ----
    {
        "t": "And why not just fine-tune on those PDFs instead?",
        "ids": ["tech.rag_vs_finetuning", "hard.not_finetune_first"],
        "type": "follow_up",
        "condition": "clean",
        "context_prior": "We use RAG so yearly regulation PDFs can be re-indexed without retraining weights.",
    },
    {
        "t": "Where does the human-in-the-loop approval step sit in that flow?",
        "ids": ["hard.hitl_where", "hard.teacher_rejects"],
        "type": "follow_up",
        "condition": "office",
        "context_prior": "The BTEC path generates a draft question from retrieved passages.",
    },
    {
        "t": "What if retrieval returns nothing useful there?",
        "ids": ["hard.empty_retrieval", "tech.rag_prevent_invented_numbers"],
        "type": "follow_up",
        "condition": "clean",
        "context_prior": "The finance assistant answers from a private document collection.",
    },
    {
        "t": "Is the similarity checker itself a RAG system?",
        "ids": ["proj.similarity.is_rag", "proj.similarity.stack"],
        "type": "follow_up",
        "condition": "office",
        "context_prior": "The assignment similarity checker embeds student work and ranks neighbors with cosine.",
    },
    {
        "t": "Which metric mattered more for those alerts?",
        "ids": ["proj.early_warning.metric", "tech.precision_recall"],
        "type": "follow_up",
        "condition": "clean",
        "context_prior": "We built an early-warning model for at-risk students.",
    },
    {
        "t": "How do you stop cross-tenant leakage in that setup?",
        "ids": ["hard.tenant_isolation", "tech.metadata_filtering", "tech.rag_access_control"],
        "type": "follow_up",
        "condition": "office",
        "context_prior": "Multiple schools share one RAG platform with separate collections.",
    },
    {
        "t": "Would you still pick LangGraph for the approval interrupts?",
        "ids": ["hard.langgraph_vs_n8n_vs_python", "tech.what_is_langgraph", "cv.langgraph"],
        "type": "follow_up",
        "condition": "clean",
        "context_prior": "Today the agentic workflow is mostly plain Python with explicit stop conditions.",
    },
    {
        "t": "How do you prevent invented numbers and hallucinations in those ministry answers?",
        "ids": ["tech.rag_prevent_invented_numbers", "tech.hallucination_prevent", "tech.no_wrong_info_finance"],
        "type": "follow_up",
        "condition": "office",
        "context_prior": "The coach answers factual ministry questions from retrieved passages.",
    },
    {
        "t": "And how do you keep PDF text from becoming instructions?",
        "ids": ["hard.injection_in_pdf", "tech.prompt_engineering"],
        "type": "follow_up",
        "condition": "clean",
        "context_prior": "Retrieval can pull long policy PDFs into the prompt.",
    },
    {
        "t": "What do you check first when hits look fine but answers are wrong?",
        "ids": ["tech.rag_debugging", "hard.which_rag_layer_failed", "hard.rag_debug_steps"],
        "type": "follow_up",
        "condition": "office",
        "context_prior": "Indexing and query-time retrieval are separate phases in our RAG build.",
    },
    {
        "t": "Where does schema validation sit relative to teacher approval?",
        "ids": ["cv.pydantic", "hard.teacher_rejects", "tech.structured_output"],
        "type": "follow_up",
        "condition": "clean",
        "context_prior": "Generated questions must be valid structured JSON before persistence.",
    },
    {
        "t": "Besides word error rate, how else do you judge transcription quality?",
        "ids": ["tech.transcription_quality", "tech.wer"],
        "type": "follow_up",
        "condition": "office",
        "context_prior": "We track word error rate for the interview coach STT path.",
    },
    # ---- far (4) + poor (4) — distinct new lines ----
    {
        "t": "Briefly, what is retrieval augmented generation used for here?",
        "ids": ["tech.rag_what", "tech.rag_build"],
        "type": "far",
        "condition": "far",
    },
    {
        "t": "Why keep a teacher approval gate before saving drafts?",
        "ids": ["hard.hitl_where", "hard.teacher_rejects"],
        "type": "far",
        "condition": "far",
    },
    {
        "t": "How do you isolate tenants when many schools share one index?",
        "ids": ["hard.tenant_isolation", "tech.metadata_filtering"],
        "type": "far",
        "condition": "far",
    },
    {
        "t": "What should happen when retrieval finds no useful chunks?",
        "ids": ["hard.empty_retrieval"],
        "type": "far",
        "condition": "far",
    },
    {
        "t": "What is cosine similarity doing in semantic search?",
        "ids": ["tech.cosine_semantic_search", "tech.embeddings"],
        "type": "poor",
        "condition": "poor",
    },
    {
        "t": "How do you reduce hallucination without treating temperature as truth?",
        "ids": ["tech.hallucination_prevent", "tech.temperature", "tech.hallucination_what"],
        "type": "poor",
        "condition": "poor",
    },
    {
        "t": "Why prefer RAG over fine-tuning for changing regulation PDFs?",
        "ids": ["tech.rag_vs_finetuning", "hard.not_finetune_first"],
        "type": "poor",
        "condition": "poor",
    },
    {
        "t": "What is metadata filtering in a vector store?",
        "ids": ["tech.metadata_filtering"],
        "type": "poor",
        "condition": "poor",
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
    accents = ["indian", "jordanian", "egyptian", "emirati"]
    warm = [
        {
            "id": "gdev_warm_01",
            "question_type": "ultra_short",
            "condition": "clean",
            "accent": "indian",
            "transcript": "What is an embedding?",
            "expected_intent_ids": _resolve_ids(["tech.embeddings"]),
            "file": "audio/gdev_warm_01.wav",
            "warmup": True,
            "pack": "generalization-dev",
            "eval_only": True,
        }
    ]
    rows: list[dict] = []
    for i, case in enumerate(CASES, start=1):
        sid = f"gdev_{i:03d}"
        row = {
            "id": sid,
            "question_type": case["type"],
            "condition": case["condition"],
            "accent": accents[(i - 1) % len(accents)],
            "transcript": case["t"],
            "expected_intent_ids": _resolve_ids(list(case["ids"])),
            "file": f"audio/{sid}.wav",
            "warmup": False,
            "pack": "generalization-dev",
            "eval_only": True,
        }
        if case.get("context_prior"):
            row["context_prior"] = case["context_prior"]
        rows.append(row)
    assert len(rows) == 56, len(rows)
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[str(r["question_type"])] = by_type.get(str(r["question_type"]), 0) + 1
    assert by_type.get("medium") == 12
    assert by_type.get("ultra_short") == 12
    assert by_type.get("indirect") == 12
    assert by_type.get("follow_up") == 12
    assert by_type.get("far") == 4
    assert by_type.get("poor") == 4
    return warm + rows


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "audio").mkdir(parents=True, exist_ok=True)
    rows = build()
    scored = [r for r in rows if not r.get("warmup")]
    (PACK / "scripts.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (PACK / "manifest.json").write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {
        "name": "generalization-dev",
        "track": "C",
        "scored_cases": len(scored),
        "warmup_cases": 1,
        "not_final_holdout": True,
        "slices": ["medium", "ultra_short", "indirect", "follow_up", "far", "poor"],
        "audio_status": "pending_synthesis",
    }
    (PACK / "pack_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (PACK / "README.md").write_text(
        "# Generalization Dev (Track C)\n\nNot Final Holdout. New wording only.\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows ({len(scored)} scored) -> {PACK}")


if __name__ == "__main__":
    main()
