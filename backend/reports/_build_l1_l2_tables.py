"""Build L1/L2 root-cause tables from v3 report (read-only)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rep = json.loads((ROOT / "FINAL_UNSEEN_HOLDOUT_V3_REPORT.json").read_text(encoding="utf-8"))
rows = [r for r in rep["results"] if not str(r.get("notes") or "").startswith("warmup:")]

# Keyword hints that a human would expect for each gold family (analysis only).
KEYWORD_HINTS: dict[str, list[str]] = {
    "tech.hallucination_what": ["makes things up", "hallucinat", "invent"],
    "tech.reindex_embedding_change": ["swapped", "re-index", "reindex", "embedding", "answers changed"],
    "hard.cost_spike": ["invoice", "tripled", "cost", "bill", "finance"],
    "hard.wrong_chunk": ["wrong paragraph", "right document", "chunk"],
    "hard.citation_lie": ["where the sentence came from", "citation", "source"],
    "tech.faithfulness_check": ["where the sentence came from", "faithful", "ground"],
    "tech.i_dont_know_too_often": ["cannot help", "i don't know", "ignoring"],
    "tech.rag_access_control": ["procurement", "human resources", "read a file", "access"],
    "hard.agent_loop": ["round in circles", "loop", "gave up"],
    "hard.timeout_vs_steps": ["four minutes", "timeout", "steps"],
    "tech.good_enough_to_launch": ["pilot", "actually good", "launch", "evaluate"],
    "hard.evaluate_rag": ["whether it is actually good", "evaluate", "pilot"],
    "tech.temperature": ["different answers", "same afternoon", "temperature"],
    "hard.prompt_versioning": ["same thing", "different answers", "version"],
    "tech.audio_retention": ["recordings", "leaving the building", "lawyers"],
    "tech.external_api_risks": ["leaving the building", "external", "cloud"],
    "gen.motivation": ["hired you", "interesting problems", "motivation"],
}


def gold_rank(sem: dict, gold_ids: list[str]) -> tuple[str, str]:
    """Where gold appears in semantic/hybrid lists."""
    tops = sem.get("semantic_top5") or []
    hybs = sem.get("hybrid_top5") or []
    sem_pos = next((i + 1 for i, x in enumerate(tops) if x.get("id") in gold_ids), None)
    hyb_pos = next((i + 1 for i, x in enumerate(hybs) if x.get("id") in gold_ids), None)
    hyb = next((x for x in hybs if x.get("id") in gold_ids), None)
    return (
        f"sem#{sem_pos}" if sem_pos else "sem:absent",
        f"hyb#{hyb_pos} final={hyb.get('final')} lex={hyb.get('lex')} sem={hyb.get('sem')}"
        if hyb
        else "hyb:absent",
    )


def present_hints(text: str, gold_ids: list[str]) -> list[str]:
    low = (text or "").casefold()
    hits = []
    for gid in gold_ids:
        for h in KEYWORD_HINTS.get(gid, []):
            if h.casefold() in low:
                hits.append(f"{gid}:{h}")
    return hits


print("===== L1 TABLE =====")
ind_fails = [
    r
    for r in rows
    if (r.get("question_type_label") or "") == "indirect_paraphrase" and not r.get("intent_ok")
]
for r in ind_fails:
    gold = list(r.get("expected_intent_ids") or [])
    sem = r.get("semantic_recovery") or {}
    hyb0 = (sem.get("hybrid_top5") or [{}])[0]
    text = r.get("raw_transcript") or r.get("transcript") or ""
    sem_r, hyb_r = gold_rank(sem, gold)
    hints = present_hints(text, gold)
    print(
        json.dumps(
            {
                "id": r.get("sample_id"),
                "cond": r.get("condition"),
                "accent": r.get("accent_label"),
                "question": (r.get("expected_question") or "")[:100],
                "transcript": text[:110],
                "gold": gold,
                "lex_match_id": r.get("match_id"),
                "lex_mode": r.get("match_mode"),
                "lex_score": r.get("match_score"),
                "intent_score": r.get("intent_score"),
                "sem_reason": sem.get("reason"),
                "abstain": sem.get("abstain_reason"),
                "agreement": sem.get("agreement"),
                "margin": sem.get("margin"),
                "hyb_top1": {
                    "id": hyb0.get("id"),
                    "final": hyb0.get("final"),
                    "lex": hyb0.get("lex"),
                    "sem": hyb0.get("sem"),
                },
                "gold_in_lists": f"{sem_r}; {hyb_r}",
                "surface_cues_present": hints,
            },
            ensure_ascii=False,
        )
    )

print("\n===== L2 TABLE =====")
for r in [x for x in rows if (x.get("question_type_label") or "") == "compound"]:
    tr = r.get("compound_trace") or {}
    cands = tr.get("candidate_intents") or []
    locus = []
    subs = tr.get("sub_questions") or r.get("compound_sub_questions") or []
    # Segmentation: if requested_parts from gold vs detected
    req = r.get("requested_parts_count")
    det = r.get("detected_parts_count")
    matched = r.get("matched_parts_count")
    if det is not None and req is not None and det < req:
        locus.append("segmentation_underdetect")
    dropped = tr.get("dropped_intents") or []
    for d in dropped:
        reason = d.get("reason") or ""
        if reason in {"low_score", "weak", "abstain"}:
            locus.append(f"matching:{reason}")
        elif "dup" in reason:
            locus.append("dedupe")
        else:
            locus.append(f"matching:{reason or 'drop'}")
    if r.get("duplicate_parts"):
        locus.append("dedupe")
    # merge: detected and candidates accepted partially but coverage low with answered < matched
    if matched and r.get("answered_parts_count") is not None:
        if r.get("answered_parts_count") < matched:
            locus.append("merge_or_answer_short")
    if tr.get("failure_code") == "ANSWER_TOO_SHORT":
        locus.append("answer_too_short")
    # classify trailing
    missed = r.get("missed_parts") or []
    trailing = []
    for m in missed:
        ml = m.casefold()
        if ml.startswith("when ") or "when would" in ml:
            trailing.append("when-clause")
        elif ml.startswith("what do you") or "what do you do" in ml:
            trailing.append("what-do-you-do")
        elif "which" in ml and ("pick" in ml or "choose" in ml or "use" in ml):
            trailing.append("which-pick")
        elif ml.startswith("say ") or ml.startswith("and say") or ml.startswith("tell me"):
            trailing.append("say/tell-followon")
        elif ml.startswith("how "):
            trailing.append("how-followon")
        else:
            trailing.append("other-followon")

    print(
        json.dumps(
            {
                "id": r.get("sample_id"),
                "cov": r.get("gold_part_coverage"),
                "gold_req": req,
                "detected": det,
                "matched": matched,
                "answered": r.get("answered_parts_count"),
                "subs": subs,
                "candidates": [
                    {
                        "q": c.get("sub_question"),
                        "id": c.get("intent_id"),
                        "score": c.get("score"),
                        "mode": c.get("mode"),
                        "accepted": c.get("accepted"),
                        "drop": c.get("drop_reason"),
                        "sem_trig": c.get("semantic_triggered"),
                    }
                    for c in cands
                ],
                "missed": missed,
                "trailing_pattern": trailing,
                "locus": sorted(set(locus)) or ["coverage_mismatch_check"],
                "fail_code": tr.get("failure_code") or r.get("compound_failure_code"),
                "notes": tr.get("decomposition_notes"),
                "dup": r.get("duplicate_parts"),
                "transcript": (r.get("raw_transcript") or "")[:100],
            },
            ensure_ascii=False,
        )
    )
