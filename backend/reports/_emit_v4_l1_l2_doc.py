"""Emit V4_PRE_CODE_L1_L2_ROOT_CAUSES.md from v3 report (analysis only)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rep = json.loads((ROOT / "FINAL_UNSEEN_HOLDOUT_V3_REPORT.json").read_text(encoding="utf-8"))
rows = [r for r in rep["results"] if not str(r.get("notes") or "").startswith("warmup:")]

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


def present_hints(text: str, gold_ids: list[str]) -> list[str]:
    low = (text or "").casefold()
    hits = []
    for gid in gold_ids:
        for h in KEYWORD_HINTS.get(gid, []):
            if h.casefold() in low:
                hits.append(f"{gid}:{h}")
    return hits


def gold_list_status(sem: dict, gold_ids: list[str]) -> str:
    tops = sem.get("semantic_top5") or []
    hybs = sem.get("hybrid_top5") or []
    sem_pos = next((i + 1 for i, x in enumerate(tops) if x.get("id") in gold_ids), None)
    hyb_pos = next((i + 1 for i, x in enumerate(hybs) if x.get("id") in gold_ids), None)
    hyb = next((x for x in hybs if x.get("id") in gold_ids), None)
    sem_s = f"sem#{sem_pos}" if sem_pos else "sem:absent"
    if hyb:
        hyb_s = f"hyb#{hyb_pos} final={hyb.get('final')}"
    else:
        hyb_s = "hyb:absent"
    return f"{sem_s}; {hyb_s}"


ind_fails = [
    r
    for r in rows
    if (r.get("question_type_label") or "") == "indirect_paraphrase" and not r.get("intent_ok")
]
l1: list[dict] = []
for r in ind_fails:
    gold = list(r.get("expected_intent_ids") or [])
    sem = r.get("semantic_recovery") or {}
    hyb0 = (sem.get("hybrid_top5") or [{}])[0]
    text = r.get("raw_transcript") or r.get("transcript") or ""
    l1.append(
        {
            "id": r.get("sample_id"),
            "question": r.get("expected_question") or "",
            "transcript": text,
            "gold": gold,
            "lex_match_id": r.get("match_id"),
            "lex_mode": r.get("match_mode"),
            "lex_score": r.get("match_score"),
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
            "gold_in_lists": gold_list_status(sem, gold),
            "surface_cues_present": present_hints(text, gold),
            "sem_top3": [x.get("id") for x in (sem.get("semantic_top5") or [])[:3]],
            "hyb_top3": [x.get("id") for x in (sem.get("hybrid_top5") or [])[:3]],
        }
    )

pat = Counter()
for r in l1:
    if r.get("sem_reason") == "abstain_low_confidence":
        pat["abstain_low_confidence"] += 1
    g = r.get("gold_in_lists") or ""
    if "hyb:absent" in g and "sem:absent" in g:
        pat["gold_absent_both_lists"] += 1
    elif "hyb:absent" in g and "sem#" in g:
        pat["gold_in_sem_not_hybrid"] += 1
    if "hyb#" in g:
        pat["gold_in_hybrid_still_abstain"] += 1
    if r.get("surface_cues_present"):
        pat["surface_cues_present"] += 1
    if not r.get("lex_mode"):
        pat["lex_none"] += 1
    elif r.get("lex_mode") == "weak":
        pat["lex_weak"] += 1
    top = float((r.get("hyb_top1") or {}).get("final") or 0)
    if top < 0.5:
        pat["hyb_top1_final_lt_0.5"] += 1
    else:
        pat["hyb_top1_final_ge_0.5"] += 1
    if float(r.get("agreement") or 0) >= 0.75:
        pat["agreement_ge_0.75"] += 1

comp = [r for r in rows if (r.get("question_type_label") or "") == "compound"]
l2: list[dict] = []
locus_c = Counter()
trail_c = Counter()
seg_ok_match_fail = 0

for r in comp:
    tr = r.get("compound_trace") or {}
    cands = tr.get("candidate_intents") or []
    req = r.get("requested_parts_count")
    det = r.get("detected_parts_count")
    matched = r.get("matched_parts_count")
    answered = r.get("answered_parts_count")
    locus: list[str] = []
    if det is not None and req is not None and det < req:
        locus.append("segmentation_underdetect")
    for d in tr.get("dropped_intents") or []:
        reason = d.get("reason") or "drop"
        if "dup" in reason:
            locus.append("dedupe")
        else:
            locus.append(f"matching:{reason}")
    for c in cands:
        if c.get("accepted") is False:
            dr = c.get("drop_reason") or "drop"
            if "dup" in dr:
                locus.append("dedupe")
            else:
                locus.append(f"matching:{dr}")
    if r.get("duplicate_parts"):
        locus.append("dedupe")
    if answered is not None and matched is not None and answered < matched:
        locus.append("merge_or_answer_short")
    if tr.get("failure_code") == "ANSWER_TOO_SHORT":
        locus.append("answer_too_short")
    # gold-intent mismatch despite full part counts
    if (
        det
        and req
        and matched
        and det >= req
        and matched >= req
        and float(r.get("gold_part_coverage") or 0) < 0.999
    ):
        locus.append("wrong_intent_on_accepted_parts")

    missed = list(r.get("missed_parts") or [])
    trailing: list[str] = []
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

    if det is not None and req is not None and matched is not None and det >= req and matched < req:
        seg_ok_match_fail += 1

    for x in locus:
        locus_c[x] += 1
    for x in trailing:
        trail_c[x] += 1

    l2.append(
        {
            "id": r.get("sample_id"),
            "cov": r.get("gold_part_coverage"),
            "gold_req": req,
            "detected": det,
            "matched": matched,
            "answered": answered,
            "candidates": [
                {
                    "q": c.get("sub_question"),
                    "id": c.get("intent_id"),
                    "score": c.get("score"),
                    "accepted": c.get("accepted"),
                    "drop": c.get("drop_reason"),
                }
                for c in cands
            ],
            "missed": missed,
            "trailing_pattern": trailing,
            "locus": sorted(set(locus)) or ["ok_or_unclassified"],
            "fail_code": tr.get("failure_code") or r.get("compound_failure_code"),
            "question": r.get("expected_question") or "",
        }
    )

trig = sum(1 for r in rows if (r.get("semantic_recovery") or {}).get("triggered"))
app = sum(1 for r in rows if (r.get("semantic_recovery") or {}).get("applied"))
mean_cov = sum(float(r.get("gold_part_coverage") or 0) for r in comp) / max(1, len(comp))

lines: list[str] = []
A = lines.append
A("# v4 pre-code analysis — L1 & L2 root causes")
A("")
A("Source: official VALID `FINAL_UNSEEN_HOLDOUT_V3_*`. **Analysis only — no code changes.**")
A("Immutable: **HC=0**, **meaning_lost=0**.")
A("")
A(f"Suite design signal (all scored clips): semantic recovery **triggered {trig} / applied {app}**.")
A("")
A("---")
A("")
A("## L1 — indirect_paraphrase failures (12/15)")
A("")
A("### Per-case table")
A("")
A("| id | gold | lex (id/mode/score) | hyb top1 | gold in lists | abstain detail | surface cues that should help |")
A("|---|---|---|---|---|---|---|")
for r in l1:
    gold = ", ".join(f"`{g}`" for g in r["gold"])
    lex = f"`{r.get('lex_match_id') or '∅'}` / {r.get('lex_mode') or 'none'} / {r.get('lex_score')}"
    hyb = r["hyb_top1"]
    hyb_s = f"`{hyb.get('id')}` @ {hyb.get('final')} (lex={hyb.get('lex')}, sem={hyb.get('sem')})"
    cues = ", ".join(r["surface_cues_present"]) if r["surface_cues_present"] else "—"
    A(
        f"| `{r['id']}` | {gold} | {lex} | {hyb_s} | {r['gold_in_lists']} | "
        f"{r.get('sem_reason')}: {r.get('abstain')} | {cues} |"
    )

A("")
A("### Readable case notes")
A("")
for r in l1:
    A(f"- **`{r['id']}`** → gold {', '.join(f'`{g}`' for g in r['gold'])}")
    A(f"  - Original: {r['question']}")
    A(f"  - ASR: {r['transcript']}")
    A(
        f"  - Lexical: `{r.get('lex_match_id')}` ({r.get('lex_mode')}, score={r.get('lex_score')}); "
        f"hyb#1=`{r['hyb_top1'].get('id')}` final={r['hyb_top1'].get('final')}; "
        f"agree={round(float(r.get('agreement') or 0), 3)}; lists: {r['gold_in_lists']}"
    )
    A(f"  - sem top3: {r['sem_top3']}")
    A(f"  - hyb top3: {r['hyb_top3']}")

A("")
A("### L1 pattern counts (n=12)")
A("")
for k, v in sorted(pat.items()):
    A(f"- **{k}:** {v}/12")

A("")
A("### Root causes L1 (shared patterns only)")
A("")
A("1. **Weak / empty lexical coverage on scenario paraphrases**  ")
A("   Bank aliases expect definitional phrasing; holdout uses workplace stories. Lexical is `none` or `weak` on a wrong neighbor.")
A("")
A("2. **Surface cues present, but lexical never elevates them**  ")
A(f"   **{pat['surface_cues_present']}/12** transcripts already contain human-obvious symptom phrases, yet lex is weak/∅. "
  f"Only **{pat['gold_absent_both_lists']}/12** miss gold in *both* recovery lists — so pure “never retrieves” is minority; the bigger split is demotion / non-apply.")
A("")
A("3. **Hybrid demotion when semantic already finds gold**  ")
A(f"   **{pat['gold_in_sem_not_hybrid']}/12**: gold is in semantic top-k but **not** in hybrid top-k (e.g. `hard.cost_spike` as sem#1 → hyb prefers `hard.least_privilege_example`). Ranking/mix, not only retrieval.")
A("")
A("4. **Gold in hybrid still abstains (apply gate)**  ")
A(f"   **{pat['gold_in_hybrid_still_abstain']}/12** have gold somewhere in hybrid top-5 but still `abstain_low_confidence` — final score / agreement path never **applies**. Thresholding *and* wrong top1 both matter.")
A("")
A("5. **Recovery is paid abstain, not a paraphrase bridge**  ")
A(f"   All 12 fail via `abstain_low_confidence`; **{pat['hyb_top1_final_lt_0.5']}/12** have hyb top1 final &lt;0.5. "
  "High agreement (≥0.75) often means agreement with the *current wrong weak match*, not that recovery found gold. Aligns with suite **triggered ≫ applied**.")

A("")
A("### L1 design read on `triggered / applied = 0`")
A("")
A("| Hypothesis | Supported by L1? |")
A("|---|---|")
A(f"| Semantic retrieval alone is weak (gold absent both lists) | Partial — **{pat['gold_absent_both_lists']}/12** |")
A(f"| Hybrid demotes a usable semantic hit | **Yes** — **{pat['gold_in_sem_not_hybrid']}/12** |")
A(f"| Threshold / apply blocks usable hybrid hits | **Yes** — **{pat['gold_in_hybrid_still_abstain']}/12**; hyb top1 final &lt;0.5 in **{pat['hyb_top1_final_lt_0.5']}/12** |")
A("| Recovery over-triggers on hopeless weak lexical | **Yes** — every miss paid recovery then abstained |")
A("| Latency-only explanation | **No** — design: call without apply |")

A("")
A("---")
A("")
A("## L2 — compound (15 clips; intent_ok 15/15; mean gold-part coverage ≈ "
  + f"{mean_cov:.3f})")
A("")
A("Note: coverage is **gold-intent** coverage, not merely part count. Clips can show "
  "`matched == requested` yet cov &lt; 1.0 when accepted intents are the wrong family.")
A("")
A("### Per-question part table")
A("")
A("| id | cov | req/det/matched/answered | missed part(s) | trailing pattern | locus | dropped / weak candidates |")
A("|---|---|---|---|---|---|---|")
for r in sorted(l2, key=lambda x: float(x.get("cov") or 0)):
    drops = []
    for c in r["candidates"]:
        if c.get("accepted") is False:
            q = (c.get("q") or "")[:42]
            drops.append(f"{q}→`{c.get('id')}` ({c.get('drop')}/{c.get('score')})")
    A(
        f"| `{r['id']}` | {r.get('cov')} | {r.get('gold_req')}/{r.get('detected')}/"
        f"{r.get('matched')}/{r.get('answered')} | "
        f"{'; '.join(r.get('missed') or []) or '—'} | "
        f"{', '.join(r.get('trailing_pattern') or []) or '—'} | "
        f"{', '.join(r.get('locus') or [])} | {'; '.join(drops) or '—'} |"
    )

A("")
A("### Locus / trailing tallies")
A("")
A(f"- Cases with det≥req but matched&lt;req (**seg OK, match fail**): **{seg_ok_match_fail}**")
A(f"- Trailing patterns among missed: `{dict(trail_c)}`")
A("- Locus counts (clips can contribute multiple tags):")
for k, v in sorted(locus_c.items(), key=lambda kv: -kv[1]):
    A(f"  - `{k}`: {v}")

A("")
A("### Root causes L2")
A("")
A("1. **Trailing / dependent-clause loss after a strong first part**  ")
A("   Patterns: `when would you…`, `what do you do…`, `which would you pick…`, `say what you do…`. "
  "Part1 often matches strongly (`reranking`, `overfitting`, `vector_db`); part2 drops as "
  "`low_score` / `no_match` / `below_answer_threshold`, frequently collapsing to `gen.anything_else` / `gen.strengths`.")
A("")
A("2. **Pronoun / ellipsis matching failure (not segmentation)**  ")
A("   Segmentation usually finds the right part count (`detected ≈ requested`). Failure is **matching** "
  "on under-specified follow-ons (`adding one`, `fit inside one`, `pick for us`).")
A("")
A("3. **Wrong-intent acceptance lowers gold coverage even when all parts “match”**  ")
A("   Several clips have full req/det/matched/answered but cov 0.33–0.67 — accepted intents are adjacent/wrong. "
  "That is a **matching quality** issue, not merge.")
A("")
A("4. **Dedupe / merge are secondary**  ")
A("   Duplicates rare. `ANSWER_TOO_SHORT` appears after partial select, not as the primary drop mechanism.")
A("")
A("5. **STT garble amplifies worst case**  ")
A("   Lowest cov (0.0) coincides with damaged transcript (`stairs` / draft libraries); still, clean "
  "trailing-clause misses dominate the mean.")

A("")
A("---")
A("")
A("## Fixed protection rules")
A("")
A("- **HC wrong = 0** — hard gate, no exceptions for coverage.")
A("- **meaning_lost = 0** — hard gate.")
A("- Do **not** force-apply hybrid top1 solely to raise intent rate.")
A("- Do **not** retune on v3 clips; v4 requires a **new** unseen pack + one-shot path.")

A("")
A("## Hypotheses only (no implementation)")
A("")
A("### H-L1")
A("1. Improve recovery **candidate generation** for symptom/scenario language (without global strong-threshold cuts).")
A("2. Inspect **hybrid demotion** of correct semantic hits (act/dist/exist / neighbor bias on `hard.*`).")
A("3. Tighten **when** recovery triggers *or* enable conservative **apply** when gold-like symptom cues + margin allow — measured offline.")
A("4. Limited explicit symptom→intent patterns as A/B hypotheses (e.g. *makes things up* → hallucination) on held-out paraphrases.")

A("")
A("### H-L2")
A("1. Carry **head noun / prior-part topic** into trailing-clause matching.")
A("2. Dependent WH-clause acceptance when part1 is strong same-topic (margin-aware), without accepting unrelated intents.")
A("3. Revisit second-part `low_score` / `below_answer_threshold` floors separately from first-part floors.")
A("4. Latency: expect partial win from fewer useless outer recoveries (L1) before Whisper micro-opts.")

A("")
A("## Success criteria for v4")
A("")
A("| Gate | Target |")
A("|---|---|")
A("| Indirect / overall intent | ≥ **0.92** |")
A("| Compound gold-part coverage | ≥ **0.90** |")
A("| HC wrong | **0** |")
A("| meaning_lost | **0** |")
A("| Latency | re-measure after L1/L2; expect partial drop if recovery applies or triggers less |")
A("")
A("## Bottom line")
A("")
A("L1 is a **paraphrase→candidate→apply** failure chain (not STT). L2 is mostly **trailing-clause matching** "
  "(not segmentation). The `triggered 86 / applied 0` signal is the design key for v4: recovery currently "
  "buys abstain safety, not generalization.")
A("")

out = ROOT / "V4_PRE_CODE_L1_L2_ROOT_CAUSES.md"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", out)
print("L1", len(l1), "L2", len(l2))
print("pats", dict(pat))
print("locus", dict(locus_c))
print("trailing", dict(trail_c))
print("seg_ok_match_fail", seg_ok_match_fail)
