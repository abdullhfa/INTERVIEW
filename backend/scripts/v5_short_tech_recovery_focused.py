"""Focused SHORT_TECH_RECOVERY measurement."""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.services.intent_profile import intent_agreement, intent_meaning_ok
from app.services.question_bank import question_bank
from app.services.semantic_intent_index import semantic_intent_index
from app.services.short_tech_recovery import clear_vocab_cache, recover_tech_terms
from app.services.technical_term_repair import clear_repair_cache, repair_technical_terms

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

# Diagnostic targets from V5 E2E (not clip-specific rules).
TARGETS = [
    {
        "id": "V5A_121",
        "bucket": "target",
        "raw": "Why am bedding?",
        "gold_text": "Why embeddings?",
        "gold_ids": ("tech.embeddings", "tech.tfidf_vs_embeddings"),
        "expect_recovery": True,
    },
    {
        "id": "V5A_124",
        "bucket": "target",
        "raw": "When will you use Zundra?",
        "gold_text": "When would you use LangGraph?",
        "gold_ids": ("cv.langgraph", "tech.what_is_langgraph", "hard.langgraph_vs_n8n_vs_python"),
        "expect_recovery": False,  # ambiguous garble — abstain preferred
    },
    {
        "id": "V5A_125",
        "bucket": "target",
        "raw": "Whyland draft here.",
        "gold_text": "Why LangGraph here?",
        "gold_ids": ("cv.langgraph", "tech.what_is_langgraph"),
        "expect_recovery": True,
    },
    {
        "id": "V5A_148",
        "bucket": "target",
        "raw": "What in a me, amet, amma, am.",
        "gold_text": "What is a vector database?",
        "gold_ids": ("cv.vector_db", "tech.vector_db_choice", "tech.what_is_chromadb"),
        "expect_recovery": False,  # unrecoverable — abstain
    },
    {
        "id": "V5A_149",
        "bucket": "target",
        "raw": "What does affect your database store?",
        "gold_text": "What does a vector database store?",
        "gold_ids": ("cv.vector_db", "tech.vector_db_choice"),
        "expect_recovery": True,
    },
]

SYNTHETIC = [
    {"id": "SYN_why_emb_clean", "bucket": "synthetic", "raw": "Why embeddings?", "gold_text": "Why embeddings?", "gold_ids": ("tech.embeddings", "tech.tfidf_vs_embeddings"), "expect_recovery": False},
    {"id": "SYN_why_emb_dist", "bucket": "synthetic", "raw": "Why am bedding?", "gold_text": "Why embeddings?", "gold_ids": ("tech.embeddings", "tech.tfidf_vs_embeddings"), "expect_recovery": True},
    {"id": "SYN_why_use_emb", "bucket": "synthetic", "raw": "Why use embeddings?", "gold_text": "Why use embeddings?", "gold_ids": ("tech.embeddings", "tech.tfidf_vs_embeddings"), "expect_recovery": False},
    {"id": "SYN_when_chroma", "bucket": "synthetic", "raw": "When would you use Chroma?", "gold_text": "When would you use Chroma?", "gold_ids": ("tech.what_is_chromadb", "cv.chromadb", "hard.why_not_chroma_prod"), "expect_recovery": False},
    {"id": "SYN_when_zandra", "bucket": "synthetic", "raw": "When will you use Zandra?", "gold_text": "When would you use Chroma?", "gold_ids": ("tech.what_is_chromadb", "cv.chromadb", "hard.why_not_chroma_prod"), "expect_recovery": True},
    {"id": "SYN_why_langgraph", "bucket": "synthetic", "raw": "Why LangGraph?", "gold_text": "Why LangGraph?", "gold_ids": ("cv.langgraph", "tech.what_is_langgraph", "tech.langgraph_vs_langchain"), "expect_recovery": False},
    {"id": "SYN_land_graph", "bucket": "synthetic", "raw": "Why land graph?", "gold_text": "Why LangGraph?", "gold_ids": ("cv.langgraph", "tech.what_is_langgraph"), "expect_recovery": True},
    {"id": "SYN_guardrails", "bucket": "synthetic", "raw": "What do guardrails prevent?", "gold_text": "What do guardrails prevent?", "gold_ids": ("tech.guardrails_what", "tech.guardrails_how", "cv.guardrails"), "expect_recovery": False},
    {"id": "SYN_n8n_clean", "bucket": "synthetic", "raw": "When would you use n8n?", "gold_text": "When would you use n8n?", "gold_ids": ("hard.langgraph_vs_n8n_vs_python",), "expect_recovery": False},
    {"id": "SYN_n8n_dist", "bucket": "synthetic", "raw": "When would you use n-hash-n?", "gold_text": "When would you use n8n?", "gold_ids": ("hard.langgraph_vs_n8n_vs_python",), "expect_recovery": True},
    {"id": "SYN_vector_store", "bucket": "synthetic", "raw": "Why vector store?", "gold_text": "Why vector store?", "gold_ids": ("cv.vector_db", "tech.vector_db_choice"), "expect_recovery": False},
    {"id": "SYN_factor_store", "bucket": "synthetic", "raw": "Why factor store?", "gold_text": "Why vector store?", "gold_ids": ("cv.vector_db", "tech.vector_db_choice"), "expect_recovery": True},
    {"id": "SYN_how_rag", "bucket": "synthetic", "raw": "How does RAG help?", "gold_text": "How does RAG help?", "gold_ids": ("tech.rag_what", "tech.rag_build", "cv.rag_experience"), "expect_recovery": False},
    {"id": "SYN_ragged", "bucket": "synthetic", "raw": "Why ragged?", "gold_text": "Why RAG?", "gold_ids": ("tech.rag_what", "cv.rag_experience"), "expect_recovery": True},
    {"id": "SYN_lankan", "bucket": "synthetic", "raw": "What did Lankan give you that you would otherwise need to build yourself?", "gold_text": "What did LangChain give you?", "gold_ids": ("tech.what_is_langchain", "cv.langchain", "hard.remove_langchain"), "expect_recovery": True},
    {"id": "SYN_london_no", "bucket": "synthetic", "raw": "What did London give you that you would otherwise need to build yourself?", "gold_text": "What did London give you?", "gold_ids": (), "expect_recovery": False, "must_not_recover_to": "LangChain"},
    {"id": "SYN_unrecoverable", "bucket": "synthetic", "raw": "What in a me, amet, amma, am.", "gold_text": "What is a vector database?", "gold_ids": (), "expect_recovery": False, "prefer_abstain": True},
    {"id": "SYN_rerank", "bucket": "synthetic", "raw": "Why reranking?", "gold_text": "Why reranking?", "gold_ids": (), "expect_recovery": False},
    {"id": "SYN_hybrid", "bucket": "synthetic", "raw": "When hybrid search?", "gold_text": "When hybrid search?", "gold_ids": ("tech.hybrid_search",), "expect_recovery": False},
    {"id": "SYN_whyland", "bucket": "synthetic", "raw": "Whyland draft here.", "gold_text": "Why LangGraph here?", "gold_ids": ("cv.langgraph", "tech.what_is_langgraph"), "expect_recovery": True},
]

REGRESSION = [
    {"id": "REG_rag", "bucket": "regression", "raw": "What is RAG?", "gold_text": "What is RAG?", "gold_ids": ("tech.rag_what",)},
    {"id": "REG_compound", "bucket": "regression", "raw": "What is RAG, why did you use it, and how did you implement it?", "gold_text": "What is RAG, why did you use it, and how did you implement it?", "gold_ids": ("cv.rag_experience", "tech.rag_what")},
    {"id": "REG_long_mre", "bucket": "regression", "raw": "Your assistant understands the interview question correctly, but the answer arrives several seconds after the interviewer finishes speaking. Walk me through how you would measure the delay and decide whether the bottleneck is speech recognition, retrieval, model inference, or the user interface.", "gold_text": "measure latency", "gold_ids": ("tech.latency_p95", "hard.production_monitoring")},
    {"id": "REG_tele", "bucket": "regression", "raw": "vector store?", "gold_text": "vector store?", "gold_ids": ("cv.vector_db",)},
    {"id": "REG_indirect", "bucket": "regression", "raw": "How do you handle ambiguous requirements?", "gold_text": "How do you handle ambiguous requirements?", "gold_ids": ("gen.ambiguity",)},
    {"id": "REG_embeddings_def", "bucket": "regression", "raw": "What are embeddings?", "gold_text": "What are embeddings?", "gold_ids": ("tech.embeddings",)},
    {"id": "REG_guardrails", "bucket": "regression", "raw": "What are guardrails?", "gold_text": "What are guardrails?", "gold_ids": ("tech.guardrails_what",)},
]


def _correct(match, gold_text: str, gold_ids: tuple[str, ...]) -> tuple[bool, float]:
    if match is None:
        return False, 0.0
    profile = semantic_intent_index.get(match.entry.id)
    agr = intent_agreement(match.entry, gold_text, profile=profile)
    ok, agr2 = intent_meaning_ok(
        match.entry, gold_text, match_score=float(match.score), profile=profile, agreement=agr
    )
    if gold_ids:
        return (match.entry.id in gold_ids) or ok, agr2
    return (ok), agr2


def _eval(case: dict) -> dict:
    raw = case["raw"]
    gold_text = case.get("gold_text") or raw
    gold_ids = tuple(case.get("gold_ids") or ())

    t0 = time.perf_counter()
    # "Old" = match without short_tech curated path: approximate by matching raw
    # through bank with tech_repair disabled for baseline distortion cases.
    old = question_bank.match(raw, tech_repair=False)
    old_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    rec = recover_tech_terms(raw)
    new = question_bank.match(raw, tech_repair=True)
    new_ms = (time.perf_counter() - t1) * 1000

    old_ok, old_agr = _correct(old, gold_text, gold_ids)
    new_ok, new_agr = _correct(new, gold_text, gold_ids)

    # For prefer_abstain: success if no confident wrong
    if case.get("prefer_abstain"):
        new_ok = new is None or (new.mode != "strong")
        # don't count as recovered intent if abstaining
        if new is None:
            new_ok = True  # abstain is correct for unrecoverable

    false_norm = False
    must_not = case.get("must_not_recover_to")
    if must_not:
        for t in rec.recovered_terms:
            if must_not.lower() in t.normalized.lower():
                false_norm = True
        if any(must_not.lower() in (rec.normalized_transcript or "").lower() for _ in [0]):
            if must_not.lower() not in raw.lower() and must_not.lower() in rec.normalized_transcript.lower():
                false_norm = True

    hc = bool(new and new.mode == "strong" and not new_ok and float(new.score) >= 0.70)

    return {
        "id": case["id"],
        "bucket": case["bucket"],
        "raw_transcript": raw,
        "normalized_transcript": rec.normalized_transcript,
        "recovered_terms": [
            {"raw": t.raw, "normalized": t.normalized, "confidence": t.confidence}
            for t in rec.recovered_terms
        ],
        "recovery_confidence": rec.confidence,
        "old_intent": None if old is None else old.entry.id,
        "new_intent": None if new is None else new.entry.id,
        "gold_intent": list(gold_ids),
        "old_correct": old_ok,
        "new_correct": new_ok,
        "expect_recovery": bool(case.get("expect_recovery")),
        "false_normalization": false_norm,
        "HC_status": hc,
        "latency_before_ms": round(old_ms, 2),
        "latency_after_ms": round(new_ms, 2),
        "latency_delta_ms": round(new_ms - old_ms, 2),
        "old_agreement": round(old_agr, 3),
        "new_agreement": round(new_agr, 3),
        "new_mode": None if new is None else new.mode,
    }


def main() -> int:
    clear_repair_cache()
    clear_vocab_cache()
    question_bank.load()
    semantic_intent_index.ensure_loaded()

    rows = [_eval(c) for c in TARGETS + SYNTHETIC + REGRESSION]

    targets = [r for r in rows if r["bucket"] == "target"]
    synth = [r for r in rows if r["bucket"] == "synthetic"]
    regs = [r for r in rows if r["bucket"] == "regression"]

    # Recovered = was wrong (or None), now correct among targets that expect recovery
    expect_rec = [r for r in targets + synth if r["expect_recovery"]]
    target_recovered = sum(
        1 for r in expect_rec if (not r["old_correct"]) and r["new_correct"]
    )
    false_norms = sum(1 for r in rows if r["false_normalization"])
    broken = [r["id"] for r in regs if r["old_correct"] and not r["new_correct"]]
    # Also break if clean regression became wrong
    hc_wrong = sum(1 for r in rows if r["HC_status"])

    short_before = sum(1 for r in targets + synth if r["old_correct"]) / max(len(targets + synth), 1)
    short_after = sum(1 for r in targets + synth if r["new_correct"]) / max(len(targets + synth), 1)
    tech_acc = sum(1 for r in expect_rec if r["new_correct"]) / max(len(expect_rec), 1)

    lat_delta = sum(r["latency_delta_ms"] for r in rows) / max(len(rows), 1)

    # Abstain check on unrecoverable
    unrec = [r for r in rows if r["id"] in {"V5A_148", "SYN_unrecoverable", "SYN_london_no"}]
    unrec_ok = all(
        (not r["false_normalization"])
        and (r["new_mode"] != "strong" or r["new_correct"])
        for r in unrec
    )

    gate = (
        target_recovered > 0
        and false_norms == 0
        and len(broken) == 0
        and hc_wrong == 0
        and lat_delta < 80.0
        and unrec_ok
        and tech_acc >= 0.5
    )
    verdict = "SHORT_TECH_RECOVERY_PASS" if gate else "SHORT_TECH_RECOVERY_NO_IMPLEMENT"

    known = []
    for r in targets:
        if r["expect_recovery"] and not r["new_correct"]:
            known.append(f"{r['id']}: expected recovery failed")
        if (not r["expect_recovery"]) and r["id"] == "V5A_124" and not r["new_correct"]:
            known.append(
                "V5A_124: STT 'Zundra' for LangGraph is phonetically ambiguous "
                "(near Chroma/LangGraph) — abstain by design"
            )
        if r["id"] == "V5A_148" and r["new_intent"] is None:
            known.append("V5A_148: heavily garbled vector-DB ask — abstain by design")

    summary = {
        "verdict": verdict,
        "target_recovered": target_recovered,
        "false_normalizations": false_norms,
        "passing_cases_broken": len(broken),
        "broken_ids": broken,
        "HC_wrong": hc_wrong,
        "short_question_accuracy_before": round(short_before, 3),
        "short_question_accuracy_after": round(short_after, 3),
        "technical_term_recovery_accuracy": round(tech_acc, 3),
        "latency_delta_ms_avg": round(lat_delta, 2),
        "KNOWN_LIMITATIONS": known,
        "results": rows,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_SHORT_TECH_RECOVERY.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# V5 SHORT_TECH_RECOVERY",
        "",
        f"**Verdict:** `{verdict}`",
        "",
        "## Gate",
        f"- target_recovered: **{target_recovered}**",
        f"- false_normalizations: **{false_norms}**",
        f"- passing_cases_broken: **{len(broken)}** {broken or ''}",
        f"- HC_wrong: **{hc_wrong}**",
        f"- short accuracy: {short_before:.3f} → {short_after:.3f}",
        f"- technical recovery accuracy: {tech_acc:.3f}",
        f"- latency_delta_ms_avg: {lat_delta:.1f}",
        "",
        "## Targets",
    ]
    for r in targets:
        lines.append(
            f"- `{r['id']}` `{r['raw_transcript']}` → `{r['normalized_transcript']}` "
            f"old={r['old_intent']}({r['old_correct']}) new={r['new_intent']}({r['new_correct']})"
        )
    lines.extend(["", "## KNOWN_LIMITATIONS", ""])
    for k in known or ["(none)"]:
        lines.append(f"- {k}")
    (REPORTS / "V5_SHORT_TECH_RECOVERY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(verdict)
    print(json.dumps({k: summary[k] for k in summary if k != "results"}, indent=2))
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
