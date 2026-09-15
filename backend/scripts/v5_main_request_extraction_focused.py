"""Focused MAIN_REQUEST_EXTRACTION measurement (no full 150 E2E).

Runs target V5 failures + synthetic long/indirect variations + non-regression
shorts/compounds/telegraphic. Writes reports/V5_MAIN_REQUEST_EXTRACTION.{md,json}.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.services.intent_profile import intent_agreement, intent_meaning_ok
from app.services.main_request_extraction import (
    extract_main_request,
    match_with_main_request,
)
from app.services.question_bank import question_bank
from app.services.semantic_intent_index import semantic_intent_index

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

# Target V5 E2E understanding failures (canonical expected text from manifest).
TARGET_CASES = [
    {
        "id": "V5A_091",
        "bucket": "target",
        "full": (
            "Imagine your RAG system retrieves a document that looks semantically close "
            "but actually contains outdated policy information, and the language model "
            "starts answering from it. Walk me through how you would detect the issue, "
            "where you would fix it, and how you would prevent the same failure from "
            "reaching users again."
        ),
        "gold_family": ("tech.hallucination_prevent", "hard.wrong_chunk", "tech.no_wrong_info_finance"),
    },
    {
        "id": "V5A_100",
        "bucket": "target",
        "full": (
            "During a live interview a person asks a very indirect question with several "
            "details, but the real request is only about how you evaluated your model. "
            "How should your assistant identify the main intent without getting distracted "
            "by every word in the sentence?"
        ),
        "gold_family": ("gen.ambiguity",),
    },
    {
        "id": "V5A_102",
        "bucket": "target",
        "full": (
            "If a question contains background information, an example, and a final request "
            "that is phrased indirectly, how will you design the understanding layer so it "
            "responds to the intended question rather than matching the loudest keyword?"
        ),
        "gold_family": ("gen.ambiguity",),
    },
    {
        "id": "V5A_112",
        "bucket": "target",
        "full": (
            "Your assistant understands the interview question correctly, but the answer "
            "arrives several seconds after the interviewer finishes speaking. Walk me through "
            "how you would measure the delay and decide whether the bottleneck is speech "
            "recognition, retrieval, model inference, or the user interface."
        ),
        "gold_family": ("tech.latency_p95", "hard.production_monitoring"),
    },
]

# Same patterns, different wording (do not copy target sentences).
SYNTHETIC_CASES = [
    {
        "id": "SYN_01_bg_end_ask",
        "bucket": "synthetic",
        "full": (
            "Suppose the vector index returns a near-neighbor policy page that is actually "
            "an expired revision, and the model happily quotes it. How would you catch that "
            "failure, where would you patch the pipeline, and how would you stop it shipping "
            "to end users again?"
        ),
        "gold_family": ("tech.hallucination_prevent", "hard.wrong_chunk", "tech.no_wrong_info_finance"),
    },
    {
        "id": "SYN_02_scenario_final",
        "bucket": "synthetic",
        "full": (
            "Given that a ministry chatbot pulled stale regulation text that still ranked "
            "high on similarity, walk me through how you would detect the stale retrieval "
            "and prevent recurrence."
        ),
        "gold_family": ("tech.hallucination_prevent", "hard.wrong_chunk", "tech.no_wrong_info_finance"),
    },
    {
        "id": "SYN_03_long_story_one_ask",
        "bucket": "synthetic",
        "full": (
            "In a live coaching session the interviewer rambles about accents, room noise, "
            "and model cards, but the only thing they actually want is how the assistant "
            "finds the intended question. How should the understanding layer ignore the "
            "loud details and lock onto that ask?"
        ),
        "gold_family": ("gen.ambiguity",),
    },
    {
        "id": "SYN_04_details_one_intent",
        "bucket": "synthetic",
        "full": (
            "If someone buries examples, project names, and side notes before asking "
            "indirectly for the real need, how do you make sure matching follows the "
            "intended question instead of the noisiest keyword?"
        ),
        "gold_family": ("gen.ambiguity",),
    },
    {
        "id": "SYN_05_latency_story",
        "bucket": "synthetic",
        "full": (
            "Let's say the spoken question is understood correctly, yet the grounded answer "
            "shows up a few seconds late. How would you measure that delay and decide if the "
            "bottleneck is speech recognition, retrieval, model inference, or the UI?"
        ),
        "gold_family": ("tech.latency_p95", "hard.production_monitoring"),
    },
    {
        "id": "SYN_06_outdated_first_change",
        "bucket": "synthetic",
        "full": (
            "If I handed you a ministry RAG stack where retrieved content is outdated, "
            "what would you change first to stop the model answering from it?"
        ),
        "gold_family": ("hard.wrong_chunk", "tech.hallucination_prevent", "tech.no_wrong_info_finance"),
    },
    {
        "id": "SYN_07_too_long_where_start",
        "bucket": "synthetic",
        "full": (
            "Suppose your AI gives the right answer but it takes too long. Where would you "
            "start looking to diagnose the latency?"
        ),
        "gold_family": ("tech.latency_p95", "hard.production_monitoring"),
    },
    {
        "id": "SYN_08_retrieval_failure_story",
        "bucket": "synthetic",
        "full": (
            "Tell me about a time retrieval gave you the wrong information and what you "
            "did about it."
        ),
        "gold_family": ("hard.wrong_chunk", "tech.hallucination_prevent", "cv.hallucination_in_projects"),
    },
    {
        "id": "SYN_09_two_real_intents",
        "bucket": "synthetic",
        "full": (
            "Imagine answers are correct but slow, and separately users still get outdated "
            "retrieved policies. Walk me through how you would measure the latency bottleneck "
            "and how you would prevent outdated retrieval from reaching users."
        ),
        "gold_family": ("tech.latency_p95", "tech.hallucination_prevent", "hard.wrong_chunk"),
    },
    {
        "id": "SYN_10_indirect_eval_distraction",
        "bucket": "synthetic",
        "full": (
            "During an interview someone mentions kiosk audio, fan noise, and evaluation "
            "spreadsheets, yet the real ask is how the assistant identifies main intent. "
            "How should it avoid latching onto every side detail?"
        ),
        "gold_family": ("gen.ambiguity",),
    },
]

# Must not change behavior for these passing styles.
REGRESSION_CASES = [
    {"id": "REG_direct", "bucket": "regression", "full": "What is RAG?", "gold_family": ("tech.rag_what",)},
    {
        "id": "REG_short",
        "bucket": "regression",
        "full": "What is hallucination?",
        "gold_family": ("tech.hallucination_what",),
    },
    {
        "id": "REG_compound",
        "bucket": "regression",
        "full": "What is RAG, why did you use it, and how did you implement it?",
        "gold_family": ("cv.rag_experience", "tech.rag_what"),
    },
    {
        "id": "REG_telegraphic",
        "bucket": "regression",
        "full": "vector store?",
        "gold_family": ("cv.vector_db", "tech.vector_store"),
    },
    {
        "id": "REG_simple_indirect",
        "bucket": "regression",
        "full": "How do you handle ambiguous requirements?",
        "gold_family": ("gen.ambiguity",),
    },
]


def _eval(case: dict) -> dict:
    q = case["full"]
    t0 = time.perf_counter()
    old = question_bank.match(q)
    old_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    new, ext, meta = match_with_main_request(q)
    new_ms = (time.perf_counter() - t1) * 1000

    def _ok(match) -> tuple[bool, float]:
        if match is None:
            return False, 0.0
        profile = semantic_intent_index.get(match.entry.id)
        agr = intent_agreement(match.entry, q, profile=profile)
        ok, agr2 = intent_meaning_ok(
            match.entry, q, match_score=float(match.score), profile=profile, agreement=agr
        )
        gold = case.get("gold_family") or ()
        if gold and match.entry.id in gold:
            return True, agr2
        return (ok), agr2

    old_ok, old_agr = _ok(old)
    new_ok, new_agr = _ok(new)
    # For target/synthetic with gold_family, require family hit when present.
    gold = tuple(case.get("gold_family") or ())
    if gold:
        old_ok = bool(old and old.entry.id in gold and old_ok)
        new_ok = bool(new and new.entry.id in gold and new_ok)

    hc_old = bool(old and old.mode == "strong" and not old_ok and float(old.score) >= 0.70)
    hc_new = bool(new and new.mode == "strong" and not new_ok and float(new.score) >= 0.70)

    return {
        "id": case["id"],
        "bucket": case["bucket"],
        "full_transcript": q,
        "main_request": ext.main_request,
        "secondary_requests": list(ext.secondary_requests),
        "confidence": ext.confidence,
        "extraction_applied": ext.applied,
        "override": meta.get("override"),
        "old_intent": None if old is None else old.entry.id,
        "new_intent": None if new is None else new.entry.id,
        "gold_intent": list(gold),
        "old_correct": old_ok,
        "new_correct": new_ok,
        "old_agreement": round(old_agr, 3),
        "new_agreement": round(new_agr, 3),
        "old_mode": None if old is None else old.mode,
        "new_mode": None if new is None else new.mode,
        "HC_status_old": hc_old,
        "HC_status_new": hc_new,
        "latency_before_ms": round(old_ms, 2),
        "latency_after_ms": round(new_ms, 2),
        "latency_delta_ms": round(new_ms - old_ms, 2),
    }


def main() -> int:
    question_bank.load()
    semantic_intent_index.ensure_loaded()

    rows = [_eval(c) for c in TARGET_CASES + SYNTHETIC_CASES + REGRESSION_CASES]

    targets = [r for r in rows if r["bucket"] == "target"]
    regs = [r for r in rows if r["bucket"] == "regression"]
    synth = [r for r in rows if r["bucket"] == "synthetic"]

    recovered = sum(1 for r in targets if (not r["old_correct"]) and r["new_correct"])
    target_still_fail = [r["id"] for r in targets if not r["new_correct"]]
    target_pass_after = sum(1 for r in targets if r["new_correct"])

    broken = [r["id"] for r in regs if r["old_correct"] and not r["new_correct"]]
    hc_wrong = sum(1 for r in rows if r["HC_status_new"])

    def _acc(subset):
        n = len(subset) or 1
        return {
            "before": round(sum(1 for r in subset if r["old_correct"]) / n, 3),
            "after": round(sum(1 for r in subset if r["new_correct"]) / n, 3),
        }

    lat_before = sum(r["latency_before_ms"] for r in rows) / max(len(rows), 1)
    lat_after = sum(r["latency_after_ms"] for r in rows) / max(len(rows), 1)
    lat_delta = lat_after - lat_before

    # Success gate from user request.
    gate_ok = (
        recovered > 0
        and len(broken) == 0
        and hc_wrong == 0
        and lat_delta < 250.0  # small impact budget for focused offline match
        and target_pass_after >= 3  # prefer most of 091/100/102/112
    )
    verdict = "MAIN_REQUEST_EXTRACTION_PASS" if gate_ok else "MAIN_REQUEST_EXTRACTION_NO_IMPLEMENT"

    summary = {
        "verdict": verdict,
        "target_cases_recovered": recovered,
        "target_pass_after": target_pass_after,
        "target_still_fail": target_still_fail,
        "passing_cases_broken": len(broken),
        "broken_ids": broken,
        "HC_wrong": hc_wrong,
        "intent_accuracy_before": _acc(targets + synth + regs),
        "intent_accuracy_after_targets": _acc(targets),
        "intent_accuracy_after_synthetic": _acc(synth),
        "intent_accuracy_after_regression": _acc(regs),
        "latency_before_ms_avg": round(lat_before, 2),
        "latency_after_ms_avg": round(lat_after, 2),
        "latency_delta_ms_avg": round(lat_delta, 2),
        "results": rows,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "V5_MAIN_REQUEST_EXTRACTION.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# V5 MAIN_REQUEST_EXTRACTION",
        "",
        f"**Verdict:** `{verdict}`",
        "",
        "## Gate",
        f"- target_cases_recovered: **{recovered}**",
        f"- target_pass_after: **{target_pass_after}/4** ({', '.join(t['id'] for t in targets)})",
        f"- target_still_fail: {target_still_fail or '[]'}",
        f"- passing_cases_broken: **{len(broken)}** {broken or ''}",
        f"- HC_wrong: **{hc_wrong}**",
        f"- latency_before_ms_avg: {lat_before:.1f}",
        f"- latency_after_ms_avg: {lat_after:.1f}",
        f"- latency_delta_ms_avg: {lat_delta:.1f}",
        "",
        "## Target cases",
    ]
    for r in targets:
        lines.append(
            f"- `{r['id']}` old=`{r['old_intent']}`({r['old_correct']}) → "
            f"new=`{r['new_intent']}`({r['new_correct']}) override={r['override']} "
            f"main=`{(r['main_request'] or '')[:80]}`"
        )
    lines.extend(["", "## Synthetic", ""])
    for r in synth:
        lines.append(
            f"- `{r['id']}` old={r['old_correct']} new={r['new_correct']} "
            f"`{r['old_intent']}`→`{r['new_intent']}`"
        )
    lines.extend(["", "## Regression (must not break)", ""])
    for r in regs:
        lines.append(
            f"- `{r['id']}` old={r['old_correct']} new={r['new_correct']} "
            f"`{r['old_intent']}`→`{r['new_intent']}`"
        )
    (REPORTS / "V5_MAIN_REQUEST_EXTRACTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(verdict)
    print(json.dumps({k: summary[k] for k in summary if k != "results"}, indent=2))
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
