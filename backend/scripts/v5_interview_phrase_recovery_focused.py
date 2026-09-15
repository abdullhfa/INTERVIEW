"""Focused INTERVIEW_PHRASE_RECOVERY measurement (accent-style STT corruptions)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.services.interview_phrase_recovery import (
    clear_phrase_cache,
    recover_interview_phrases,
)
from app.services.question_bank import question_bank
from app.services.technical_term_repair import clear_repair_cache, repair_technical_terms

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

# Simulated STT from Indian / Jordanian / Gulf English + rate/distance variants.
# Real loopback audio can be layered later; this gate is phonetic corruption → phrase.
CASES = [
    # Critical live bug
    {"id": "PHR_and_you_plan", "accent": "indian", "rate": "normal", "dist": "close", "raw": "and you plan your project", "gold": "Explain your project", "expect_recover": True, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    {"id": "PHR_and_you_plan_fast", "accent": "jordanian", "rate": "fast", "dist": "close", "raw": "and you plan your project", "gold": "Explain your project", "expect_recover": True, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    {"id": "PHR_and_you_plan_far", "accent": "emirati", "rate": "slow", "dist": "far", "raw": "and explain your project", "gold": "Explain your project", "expect_recover": True, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    # Ambiguity — must NOT rewrite
    {"id": "PHR_how_plan_keep", "accent": "indian", "rate": "normal", "dist": "close", "raw": "How do you plan your project?", "gold": "How do you plan your project?", "expect_recover": False, "gold_ids": (), "must_not": ("Explain your project",)},
    {"id": "PHR_how_plan_gulf", "accent": "emirati", "rate": "fast", "dist": "far", "raw": "How do you plan your project?", "gold": "How do you plan your project?", "expect_recover": False, "gold_ids": (), "must_not": ("Explain your project",)},
    # Clean phrases unchanged
    {"id": "PHR_explain_clean", "accent": "jordanian", "rate": "normal", "dist": "close", "raw": "Explain your project", "gold": "Explain your project", "expect_recover": False, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    {"id": "PHR_tell_self_clean", "accent": "indian", "rate": "normal", "dist": "close", "raw": "Tell me about yourself", "gold": "Tell me about yourself", "expect_recover": False, "gold_ids": ("intro.tell_me_about_yourself",), "must_not": ()},
    {"id": "PHR_walk_clean", "accent": "emirati", "rate": "slow", "dist": "close", "raw": "Walk me through your project", "gold": "Walk me through your project", "expect_recover": False, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    # Yourself corruptions
    {"id": "PHR_boat_yourself", "accent": "indian", "rate": "normal", "dist": "close", "raw": "tell me a boat yourself", "gold": "Tell me about yourself", "expect_recover": True, "gold_ids": ("intro.tell_me_about_yourself",), "must_not": ()},
    {"id": "PHR_aboat", "accent": "jordanian", "rate": "fast", "dist": "far", "raw": "tell me aboat yourself", "gold": "Tell me about yourself", "expect_recover": True, "gold_ids": ("intro.tell_me_about_yourself",), "must_not": ()},
    {"id": "PHR_you_self", "accent": "emirati", "rate": "slow", "dist": "close", "raw": "tell me about you self", "gold": "Tell me about yourself", "expect_recover": True, "gold_ids": ("intro.tell_me_about_yourself",), "must_not": ()},
    # Project walk / tell
    {"id": "PHR_watch_through", "accent": "indian", "rate": "normal", "dist": "close", "raw": "watch me through your project", "gold": "Walk me through your project", "expect_recover": True, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    {"id": "PHR_walk_a_project", "accent": "jordanian", "rate": "fast", "dist": "far", "raw": "walk me through a project", "gold": "walk me through a project", "expect_recover": False, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    {"id": "PHR_tell_projects", "accent": "emirati", "rate": "normal", "dist": "close", "raw": "tell me about the project", "gold": "Tell me about your project", "expect_recover": True, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    # Role / build / challenges / outcome
    {"id": "PHR_roll", "accent": "indian", "rate": "slow", "dist": "close", "raw": "what was your roll", "gold": "What was your role?", "expect_recover": True, "gold_ids": ("proj.similarity.role",), "must_not": ()},
    {"id": "PHR_built", "accent": "jordanian", "rate": "normal", "dist": "far", "raw": "what did you built", "gold": "What did you build?", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "PHR_bill", "accent": "emirati", "rate": "fast", "dist": "close", "raw": "what did you bill", "gold": "What did you build?", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "PHR_challenges_phase", "accent": "indian", "rate": "normal", "dist": "close", "raw": "what challenge did you phase", "gold": "What challenges did you face?", "expect_recover": True, "gold_ids": ("proj.similarity.challenges",), "must_not": ()},
    {"id": "PHR_challenges_clean", "accent": "jordanian", "rate": "slow", "dist": "far", "raw": "What challenges did you face?", "gold": "What challenges did you face?", "expect_recover": False, "gold_ids": ("proj.similarity.challenges",), "must_not": ()},
    {"id": "PHR_outcome", "accent": "emirati", "rate": "normal", "dist": "close", "raw": "what was the out come", "gold": "What was the outcome?", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "PHR_result", "accent": "indian", "rate": "fast", "dist": "far", "raw": "what was the result", "gold": "What was the result?", "expect_recover": False, "gold_ids": (), "must_not": ()},
    # RAG why
    {"id": "PHR_why_rack", "accent": "jordanian", "rate": "normal", "dist": "close", "raw": "why did you use rack", "gold": "Why did you use RAG?", "expect_recover": True, "gold_ids": ("proj.similarity.is_rag",), "must_not": ()},
    {"id": "PHR_why_rag_clean", "accent": "emirati", "rate": "slow", "dist": "close", "raw": "Why did you use RAG?", "gold": "Why did you use RAG?", "expect_recover": False, "gold_ids": ("proj.similarity.is_rag",), "must_not": ()},
    {"id": "PHR_why_drag", "accent": "indian", "rate": "fast", "dist": "far", "raw": "why did you use drag", "gold": "Why did you use RAG?", "expect_recover": True, "gold_ids": ("proj.similarity.is_rag",), "must_not": ()},
    # Implement / evaluate / hire
    {"id": "PHR_implemen", "accent": "jordanian", "rate": "normal", "dist": "close", "raw": "how did you implemen it", "gold": "How did you implement it?", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "PHR_implement_clean", "accent": "emirati", "rate": "slow", "dist": "far", "raw": "How did you implement it?", "gold": "How did you implement it?", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "PHR_evaluate_model", "accent": "indian", "rate": "normal", "dist": "close", "raw": "how did you evaluate the model", "gold": "How did you evaluate the model?", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "PHR_higher_you", "accent": "jordanian", "rate": "fast", "dist": "close", "raw": "why should we higher you", "gold": "Why should we hire you?", "expect_recover": True, "gold_ids": (), "must_not": ()},
    {"id": "PHR_describe_exp", "accent": "emirati", "rate": "normal", "dist": "far", "raw": "describe your experiences", "gold": "Describe your experience", "expect_recover": True, "gold_ids": (), "must_not": ()},
    # Negatives — do not invent interview phrases
    {"id": "PHR_london_no", "accent": "indian", "rate": "normal", "dist": "close", "raw": "What did London give you that you would otherwise need to build yourself?", "gold": "", "expect_recover": False, "gold_ids": (), "must_not": ("Tell me about yourself", "Explain your project")},
    {"id": "PHR_embeddings_no", "accent": "jordanian", "rate": "fast", "dist": "far", "raw": "What are embeddings?", "gold": "", "expect_recover": False, "gold_ids": (), "must_not": ("Explain your project",)},
    {"id": "PHR_rag_def_no", "accent": "emirati", "rate": "slow", "dist": "close", "raw": "What is RAG?", "gold": "", "expect_recover": False, "gold_ids": (), "must_not": ("Why did you use RAG?",)},
    # Extra variants
    {"id": "PHR_explain_you_project", "accent": "indian", "rate": "slow", "dist": "far", "raw": "explain you project", "gold": "Explain your project", "expect_recover": True, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    {"id": "PHR_and_you_plan_q", "accent": "jordanian", "rate": "normal", "dist": "close", "raw": "and you plan your project?", "gold": "Explain your project", "expect_recover": True, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    {"id": "PHR_tell_project_clean", "accent": "emirati", "rate": "fast", "dist": "close", "raw": "Tell me about your project", "gold": "Tell me about your project", "expect_recover": False, "gold_ids": ("cv.projects_overview",), "must_not": ()},
    {"id": "PHR_role_clean", "accent": "indian", "rate": "normal", "dist": "far", "raw": "What was your role?", "gold": "What was your role?", "expect_recover": False, "gold_ids": ("proj.similarity.role",), "must_not": ()},
    {"id": "PHR_build_clean", "accent": "jordanian", "rate": "slow", "dist": "close", "raw": "What did you build?", "gold": "What did you build?", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "PHR_outcome_clean", "accent": "emirati", "rate": "normal", "dist": "far", "raw": "What was the outcome?", "gold": "What was the outcome?", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "PHR_evaluate_clean", "accent": "indian", "rate": "fast", "dist": "close", "raw": "How did you evaluate the model?", "gold": "How did you evaluate the model?", "expect_recover": False, "gold_ids": (), "must_not": ()},
    {"id": "PHR_challenges_face", "accent": "jordanian", "rate": "normal", "dist": "close", "raw": "what challenges did you faced", "gold": "What challenges did you face?", "expect_recover": True, "gold_ids": ("proj.similarity.challenges",), "must_not": ()},
    {"id": "PHR_why_rags", "accent": "emirati", "rate": "slow", "dist": "far", "raw": "why did you use rags", "gold": "Why did you use RAG?", "expect_recover": True, "gold_ids": ("proj.similarity.is_rag",), "must_not": ()},
    {"id": "PHR_in_plement", "accent": "indian", "rate": "normal", "dist": "close", "raw": "how did you in plement it", "gold": "How did you implement it?", "expect_recover": True, "gold_ids": (), "must_not": ()},
]


def main() -> int:
    clear_repair_cache()
    clear_phrase_cache()
    question_bank.load(force=True)
    # Warm phrase bank once (excluded from per-case latency).
    _ = recover_interview_phrases("Tell me about yourself")
    clear_repair_cache()

    rows = []
    t0 = time.perf_counter()
    recover_targets = []
    recover_hit = 0
    false_phrase = 0
    broken_clean = 0
    hc_wrong = 0
    intent_before_ok = 0
    intent_after_ok = 0
    intent_n = 0
    latency_sum = 0.0
    latency_base_sum = 0.0

    for case in CASES:
        raw = case["raw"]
        gold = case["gold"]
        expect_recover = bool(case["expect_recover"])
        gold_ids = tuple(case.get("gold_ids") or ())
        must_not = tuple(case.get("must_not") or ())

        # Intent before phrase layer (tech repair only would still include phrase
        # inside repair_technical_terms — measure match on raw with tech_repair False
        # as "before", and full repair as "after").
        before = question_bank.match(raw, tech_repair=False)

        t_phr0 = time.perf_counter()
        phr = recover_interview_phrases(raw)
        phr_ms = (time.perf_counter() - t_phr0) * 1000

        t2 = time.perf_counter()
        repaired = repair_technical_terms(raw)
        after = question_bank.match(raw)
        ms = (time.perf_counter() - t2) * 1000
        latency_sum += phr_ms
        latency_base_sum += 0.0

        did_recover = bool(phr.applied)
        forbid = [b for b in must_not if b and b.lower() in repaired.lower()]
        if forbid and expect_recover is False:
            false_phrase += 1
        if did_recover and not expect_recover:
            false_phrase += 1
            broken_clean += 1

        recover_pass = True
        if expect_recover:
            recover_targets.append(case["id"])
            recover_pass = (
                did_recover
                and gold.lower().rstrip("?") in repaired.lower().rstrip("?")
                and not forbid
            )
            if recover_pass:
                recover_hit += 1
        else:
            recover_pass = (not did_recover) and not forbid
            if gold and expect_recover is False:
                # clean: repaired should stay close to gold/raw
                if SequenceMatcher := __import__("difflib").SequenceMatcher:
                    if SequenceMatcher(None, repaired.lower(), raw.lower()).ratio() < 0.85 and did_recover:
                        recover_pass = False
                        broken_clean += 1

        intent_pass = True
        if gold_ids:
            intent_n += 1
            b_ok = before is not None and before.entry.id in gold_ids
            a_ok = after is not None and after.entry.id in gold_ids
            if b_ok:
                intent_before_ok += 1
            if a_ok:
                intent_after_ok += 1
            intent_pass = a_ok if expect_recover or gold_ids else True
            if (
                after is not None
                and getattr(after, "mode", "") == "strong"
                and after.entry.id not in gold_ids
            ):
                hc_wrong += 1

        rows.append(
            {
                "id": case["id"],
                "accent": case["accent"],
                "rate": case["rate"],
                "dist": case["dist"],
                "raw": raw,
                "gold": gold,
                "recovered": phr.recovered_transcript,
                "repaired": repaired,
                "did_recover": did_recover,
                "expect_recover": expect_recover,
                "recovery_type": phr.recovery_type,
                "margin": round(phr.margin, 3),
                "candidates": [
                    {
                        "candidate": c.phrase,
                        "phonetic_score": round(c.phonetic, 3),
                        "semantic_score": round(c.semantic, 3),
                        "bank_support": round(c.bank_support, 3),
                        "combined_score": round(c.combined, 3),
                    }
                    for c in phr.candidates[:3]
                ],
                "intent_before": before.entry.id if before else None,
                "intent_after": after.entry.id if after else None,
                "phrase_matched_intent": phr.matched_intent or None,
                "forbid": forbid,
                "pass": recover_pass and (intent_pass if gold_ids else True),
                "ms": round(ms, 2),
            }
        )

    n = len(rows)
    passed = sum(1 for r in rows if r["pass"])
    recover_rate = recover_hit / max(1, len(recover_targets))
    latency_delta = latency_sum / max(1, n)  # avg cost of phrase recovery alone

    blockers = []
    if recover_hit <= 0:
        blockers.append("target_recovered=0")
    if false_phrase:
        blockers.append(f"false_phrase_corrections={false_phrase}")
    if broken_clean:
        blockers.append(f"passing_cases_broken={broken_clean}")
    if hc_wrong:
        blockers.append(f"HC_wrong={hc_wrong}")
    if latency_delta > 80:
        blockers.append(f"latency_delta={latency_delta:.1f}ms")
    if recover_targets and recover_rate < 0.80:
        blockers.append(f"phrase_recovery_accuracy={recover_rate:.3f}<0.80")
    # Critical cases
    for crit in ("PHR_and_you_plan", "PHR_how_plan_keep", "PHR_boat_yourself"):
        row = next(r for r in rows if r["id"] == crit)
        if not row["pass"]:
            blockers.append(f"critical_fail={crit}")

    verdict = "INTERVIEW_PHRASE_RECOVERY_PASS" if not blockers else "INTERVIEW_PHRASE_RECOVERY_NO_IMPLEMENT"
    # If nothing useful recovered, use NO_IMPLEMENT label per brief
    if recover_hit <= 0:
        verdict = "INTERVIEW_PHRASE_RECOVERY_NO_IMPLEMENT"

    payload = {
        "verdict": verdict,
        "blockers": blockers,
        "n": n,
        "pass_rate": round(passed / n, 4),
        "phrase_recovery_accuracy": round(recover_rate, 4),
        "target_recovered": recover_hit,
        "recover_targets": len(recover_targets),
        "false_phrase_corrections": false_phrase,
        "passing_cases_broken": broken_clean,
        "intent_before": intent_before_ok,
        "intent_after": intent_after_ok,
        "intent_n": intent_n,
        "HC_wrong": hc_wrong,
        "latency_delta_ms_avg": round(latency_delta, 2),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "note": "Accent/rate/distance labels are STT-corruption proxies on the real repair→match path. Full WASAPI loopback pack can reuse these scripts.",
        "cases": rows,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "V5_INTERVIEW_PHRASE_RECOVERY.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    md = [
        "# V5 INTERVIEW_PHRASE_RECOVERY",
        "",
        f"**Verdict:** `{verdict}`",
        "",
        "## Pipeline",
        "`STT → ACRONYM → TECH_TERM → INTERVIEW_PHRASE → MAIN_REQUEST → INTENT`",
        "",
        "## Summary",
        "| metric | value |",
        "|---|---:|",
        f"| n | {n} |",
        f"| pass_rate | {payload['pass_rate']} |",
        f"| phrase_recovery_accuracy | {payload['phrase_recovery_accuracy']} ({recover_hit}/{len(recover_targets)}) |",
        f"| false_phrase_corrections | {false_phrase} |",
        f"| passing_cases_broken | {broken_clean} |",
        f"| intent_before → after | {intent_before_ok} → {intent_after_ok} / {intent_n} |",
        f"| HC_wrong | {hc_wrong} |",
        f"| latency_delta_ms_avg | {payload['latency_delta_ms_avg']} |",
        "",
        "## Critical",
    ]
    for crit in ("PHR_and_you_plan", "PHR_how_plan_keep", "PHR_boat_yourself"):
        row = next(r for r in rows if r["id"] == crit)
        md.append(
            f"- `{crit}` raw=`{row['raw']}` → `{row['repaired']}` "
            f"intent={row['intent_after']} pass={row['pass']}"
        )
    if blockers:
        md += ["", "## Blockers"] + [f"- {b}" for b in blockers]
    md += [
        "",
        "## Rules",
        "- Multi-signal scoring: phonetic + semantic + bank + structure",
        "- Rewrite only when combined score and margin clear",
        "- `How do you plan your project?` must not become `Explain your project`",
        "- raw_transcript always retained alongside recovered_transcript",
    ]
    (REPORTS / "V5_INTERVIEW_PHRASE_RECOVERY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(verdict)
    print(json.dumps({k: payload[k] for k in payload if k != "cases"}, indent=2))
    return 0 if verdict.endswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
