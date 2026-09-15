"""
Final Latency Check (A+B+C) — EVALUATOR.

SCORING CORRECTION (not performance tuning)
-------------------------------------------
The previous ad-hoc check stored a single `gate_ms = 1500.0` and applied it to
BOTH cohorts (see reports/FINAL_LATENCY_CHECK.json, key `gate.gate_ms`). The
documented, frozen release gates are cohort-specific:

    simple_median_gate_ms   = 1500     (short_length)
    compound_median_gate_ms = 2000     (compound_dev)

Applying the simple gate to compound made a compliant compound median
(1773.1 ms <= 2000) report FAIL. That is an evaluator bug, and this script
fixes only that: it reads the documented gates, reports each cohort against its
own threshold, and labels p95 as TARGET (diagnostic), not HARD GATE.

Nothing about the pipeline, thresholds, weights or aliases is touched here.

Usage:
    python scripts/final_latency_check.py
    python scripts/final_latency_check.py --simple reports/LENGTH_SHORT_REGRESSION_REPORT.json \
                                          --compound reports/COMPOUND_DEV_REPORT.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# ── Documented frozen gates ────────────────────────────────────────────────
SIMPLE_MEDIAN_GATE_MS = 1500.0      # HARD GATE
COMPOUND_MEDIAN_GATE_MS = 2000.0    # HARD GATE
SIMPLE_P95_TARGET_MS = 2000.0       # TARGET (diagnostic)
COMPOUND_P95_TARGET_MS = 3000.0     # TARGET (diagnostic)

# Quality gates that ride along with the latency check (observe + enforce HC).
COMPOUND_INTENT_GATE = 0.95         # HARD GATE
COMPOUND_COVERAGE_GATE = 0.90       # HARD GATE
HC_WRONG_GATE = 0                   # HARD GATE (both cohorts)

_STAGES = (
    "vad_ms",
    "whisper_ms",
    "match_ms",
    "semantic_ms",
    "rerank_ms",
    "compound_detect_ms",
    "decomposition_ms",
    "matching_ms",
    "merge_ms",
    "compound_ms",
    "answer_ms",
    "intent_ms",
    "post_speech_ms",
)

_TRACE_STAGES = (
    "whisper_pass1_ms",
    "whisper_pass2_ms",
    "technical_repair_ms",
    "routing_ms",
    "base_match_ms",
    "lexical_match_ms",
    "semantic_embedding_ms",
    "semantic_search_ms",
    "semantic_rerank_ms",
    "semantic_total_ms",
    "compound_detect_ms",
    "decomposition_ms",
    "subquestion_match_ms",
    "subquestion_semantic_ms",
    "harvest_ms",
    "dedupe_ms",
    "answer_lookup_ms",
    "answer_merge_ms",
    "final_validation_ms",
    "other_ms",
    "unattributed_ms",
)


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return round(ordered[idx], 1)


def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p95": 0.0, "mean": 0.0, "max": 0.0}
    return {
        "p50": _pct(values, 0.5),
        "p95": _pct(values, 0.95),
        "mean": round(sum(values) / len(values), 1),
        "max": round(max(values), 1),
    }


def _scored_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("results") or []
    return [r for r in rows if not str(r.get("notes") or "").startswith("warmup:")] or rows


def _cohort(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = _scored_rows(payload)
    filters = payload.get("filters") or {}
    warm = filters.get("warm") or {}
    # A run whose warm-up had not finished scored some clips with the alias
    # matrix absent (strong->weak demotion) and some with it present: two
    # different systems in one report. Never gate on that.
    per_clip_warm = [
        bool((r.get("post_speech_trace") or {}).get("alias_matrix_ready"))
        for r in rows
        if (r.get("post_speech_trace") or {}).get("alias_matrix_ready") is not None
    ]
    warm_mixed = bool(per_clip_warm) and len(set(per_clip_warm)) > 1
    if "gate_valid" not in filters:
        # Report predates the warm-state instrumentation: we cannot prove the
        # run was warm, so it cannot be used as a gate. Re-run the suite.
        gate_valid = False
        gate_valid_reason = "warm state not recorded — re-run with the instrumented harness"
    elif warm_mixed:
        gate_valid = False
        gate_valid_reason = "warm-up finished mid-run: clips scored with and without the alias matrix"
    elif not filters.get("gate_valid"):
        gate_valid = False
        gate_valid_reason = "warm-up did not complete before the first clip"
    else:
        gate_valid = True
        gate_valid_reason = "warm before first clip; alias matrix present for every scored clip"
    summary: dict[str, Any] = {"n": len(rows)}
    for stage in _STAGES:
        summary[stage] = _stats([float((r.get("timings") or {}).get(stage) or 0.0) for r in rows])
    trace_summary: dict[str, Any] = {}
    for stage in _TRACE_STAGES:
        vals = [
            float((r.get("post_speech_trace") or {}).get(stage) or 0.0)
            for r in rows
            if (r.get("post_speech_trace") or {}).get(stage) is not None
        ]
        if vals:
            trace_summary[stage] = _stats(vals)

    intent_ok = sum(1 for r in rows if r.get("intent_ok"))
    hc = sum(1 for r in rows if r.get("high_confidence_wrong"))
    coverage_rows = [r for r in rows if r.get("gold_part_coverage") is not None]
    coverage = (
        round(sum(float(r.get("gold_part_coverage") or 0.0) for r in coverage_rows) / len(coverage_rows), 4)
        if coverage_rows
        else None
    )
    whisper_calls = [
        int((r.get("post_speech_trace") or {}).get("whisper_call_count") or 0) for r in rows
    ]
    slowest = sorted(
        rows, key=lambda r: float((r.get("timings") or {}).get("post_speech_ms") or 0.0), reverse=True
    )[:10]
    return {
        "label": label,
        "source": str(path),
        "suite": payload.get("suite"),
        "created_at": payload.get("created_at"),
        "gate_valid": gate_valid,
        "gate_valid_reason": gate_valid_reason,
        "warm": {
            **warm,
            "per_clip_alias_matrix_ready": f"{sum(per_clip_warm)}/{len(per_clip_warm)}"
            if per_clip_warm
            else "not recorded",
            "warm_mixed_within_run": warm_mixed,
        },
        "embed_stats": filters.get("embed_stats"),
        "rerank_stats": filters.get("rerank_stats"),
        "summary": summary,
        "trace_summary": trace_summary,
        "quality": {
            "n": len(rows),
            "intent_ok": intent_ok,
            "intent_rate": round(intent_ok / len(rows), 4) if rows else 0.0,
            "hc_wrong": hc,
            "gold_part_coverage": coverage,
            "whisper_calls_median": _pct([float(x) for x in whisper_calls], 0.5),
            "whisper_calls_max": max(whisper_calls) if whisper_calls else 0,
        },
        "slowest_10": [_slow_row(r) for r in slowest],
    }


def _slow_row(r: dict[str, Any]) -> dict[str, Any]:
    t = r.get("timings") or {}
    pt = r.get("post_speech_trace") or {}
    return {
        "clip": r.get("sample_id"),
        "file": r.get("file"),
        "question_type": r.get("question_type_label") or r.get("question_type"),
        "transcript": str(r.get("transcript") or "")[:90],
        "post_ms": round(float(t.get("post_speech_ms") or 0.0), 1),
        "whisper_ms": round(float(t.get("whisper_ms") or 0.0), 1),
        "whisper_calls": pt.get("whisper_call_count"),
        "lexical_ms": pt.get("lexical_match_ms"),
        "semantic_ms": round(float(t.get("semantic_ms") or 0.0), 1),
        "rerank_ms": pt.get("semantic_rerank_ms", pt.get("reranker_ms")),
        "subquestion_count": pt.get("subquestion_count"),
        "harvest_ms": pt.get("harvest_ms"),
        "harvest_ran": pt.get("harvest_ran"),
        "fast_path": pt.get("fast_path"),
        "semantic_reason": (r.get("semantic_recovery") or {}).get("reason"),
        "slow_reason": _slow_reason(r),
        "intent_ok": r.get("intent_ok"),
        "hc_wrong": r.get("high_confidence_wrong"),
    }


def _slow_reason(r: dict[str, Any]) -> str:
    pt = r.get("post_speech_trace") or {}
    t = r.get("timings") or {}
    reasons: list[str] = []
    if int(pt.get("whisper_call_count") or 1) > 1:
        reasons.append(f"stt_pass2:{pt.get('second_pass_trigger_reason')}")
    if float(t.get("semantic_ms") or 0.0) >= 200:
        reasons.append(f"semantic:{(r.get('semantic_recovery') or {}).get('reason')}")
    if float(pt.get("lexical_match_ms") or 0.0) >= 200:
        reasons.append("compound_lexical")
    if float(pt.get("harvest_ms") or 0.0) >= 200:
        reasons.append("harvest")
    if float(pt.get("semantic_parts_ms") or 0.0) >= 200:
        reasons.append("semantic_parts")
    if float(pt.get("semantic_rerank_ms") or pt.get("reranker_ms") or 0.0) >= 200:
        reasons.append("reranker")
    return ", ".join(reasons) or "whisper_only"


def run(simple_path: Optional[Path], compound_path: Optional[Path]) -> dict[str, Any]:
    simple_path = simple_path or (REPORTS_DIR / "LENGTH_SHORT_REGRESSION_REPORT.json")
    compound_path = compound_path or (REPORTS_DIR / "COMPOUND_DEV_REPORT.json")
    simple = _cohort(simple_path, "simple")
    compound = _cohort(compound_path, "compound")

    s_med = simple["summary"]["post_speech_ms"]["p50"]
    c_med = compound["summary"]["post_speech_ms"]["p50"]
    s_p95 = simple["summary"]["post_speech_ms"]["p95"]
    c_p95 = compound["summary"]["post_speech_ms"]["p95"]

    hard: dict[str, Any] = {
        "simple_median_ms": s_med,
        "simple_median_gate_ms": SIMPLE_MEDIAN_GATE_MS,
        "simple_median_pass": s_med <= SIMPLE_MEDIAN_GATE_MS,
        "compound_median_ms": c_med,
        "compound_median_gate_ms": COMPOUND_MEDIAN_GATE_MS,
        "compound_median_pass": c_med <= COMPOUND_MEDIAN_GATE_MS,
        "simple_hc_wrong": simple["quality"]["hc_wrong"],
        "simple_hc_pass": simple["quality"]["hc_wrong"] <= HC_WRONG_GATE,
        "compound_hc_wrong": compound["quality"]["hc_wrong"],
        "compound_hc_pass": compound["quality"]["hc_wrong"] <= HC_WRONG_GATE,
        "compound_intent_rate": compound["quality"]["intent_rate"],
        "compound_intent_pass": compound["quality"]["intent_rate"] >= COMPOUND_INTENT_GATE,
        "compound_coverage": compound["quality"]["gold_part_coverage"],
        "compound_coverage_pass": (
            compound["quality"]["gold_part_coverage"] is None
            or compound["quality"]["gold_part_coverage"] >= COMPOUND_COVERAGE_GATE
        ),
    }
    targets = {
        "simple_p95_ms": s_p95,
        "simple_p95_target_ms": SIMPLE_P95_TARGET_MS,
        "simple_p95_met": s_p95 <= SIMPLE_P95_TARGET_MS,
        "compound_p95_ms": c_p95,
        "compound_p95_target_ms": COMPOUND_P95_TARGET_MS,
        "compound_p95_met": c_p95 <= COMPOUND_P95_TARGET_MS,
        "simple_intent_rate": simple["quality"]["intent_rate"],
    }
    hard["simple_run_gate_valid"] = simple["gate_valid"]
    hard["simple_run_gate_valid_pass"] = simple["gate_valid"]
    hard["compound_run_gate_valid"] = compound["gate_valid"]
    hard["compound_run_gate_valid_pass"] = compound["gate_valid"]
    ready = all(v for k, v in hard.items() if k.endswith("_pass"))
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "track": "final_latency_check",
        "evaluator_version": 2,
        "evaluator_note": (
            "v2 scoring correction: cohort-specific median gates "
            "(simple<=1500, compound<=2000). v1 applied gate_ms=1500 to both "
            "cohorts, which is not the documented frozen criterion. p95 is a "
            "TARGET, never a hard gate."
        ),
        "a_b_c_frozen": True,
        "hard_gates": hard,
        "targets": targets,
        "verdict": "LATENCY_READY_FOR_V3" if ready else "NOT_READY_FOR_V3",
        "ready": ready,
        "simple": simple,
        "compound": compound,
    }
    return payload


def _fmt_stage_table(summary: dict[str, Any]) -> str:
    lines = ["| Stage | p50 ms | p95 ms | mean | max |", "|---|---|---|---|---|"]
    for stage, stats in summary.items():
        if stage == "n" or not isinstance(stats, dict):
            continue
        lines.append(
            f"| {stage} | {stats['p50']} | {stats['p95']} | {stats['mean']} | {stats['max']} |"
        )
    return "\n".join(lines)


def _fmt_slow(rows: list[dict[str, Any]]) -> str:
    head = (
        "| clip | type | post | whisper | calls | lexical | semantic | rerank | parts | harvest | reason |"
    )
    lines = [head, "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            "| {clip} | {question_type} | {post_ms} | {whisper_ms} | {whisper_calls} | "
            "{lexical_ms} | {semantic_ms} | {rerank_ms} | {subquestion_count} | {harvest_ms} | "
            "{slow_reason} |".format(**{k: ("" if v is None else v) for k, v in r.items()})
        )
    return "\n".join(lines)


def to_markdown(p: dict[str, Any]) -> str:
    h, t = p["hard_gates"], p["targets"]
    out = [
        "# Final Latency Check (A+B+C) — evaluator v2",
        "",
        f"**Verdict:** {p['verdict']}",
        f"**Created:** {p['created_at']}",
        "",
        "> Scoring correction: v1 applied a single `gate_ms = 1500` to both cohorts.",
        "> The documented frozen gates are cohort-specific "
        "(`simple_median_gate_ms = 1500`, `compound_median_gate_ms = 2000`).",
        "> p95 values are TARGETS, not hard gates.",
        "",
        "## HARD GATES",
        "",
        "| Gate | Value | Threshold | Result |",
        "|---|---|---|---|",
        f"| Simple median post | {h['simple_median_ms']} ms | <= {h['simple_median_gate_ms']} ms | "
        f"{'PASS' if h['simple_median_pass'] else 'FAIL'} |",
        f"| Compound median post | {h['compound_median_ms']} ms | <= {h['compound_median_gate_ms']} ms | "
        f"{'PASS' if h['compound_median_pass'] else 'FAIL'} |",
        f"| Simple HC wrong | {h['simple_hc_wrong']} | = 0 | "
        f"{'PASS' if h['simple_hc_pass'] else 'FAIL'} |",
        f"| Compound HC wrong | {h['compound_hc_wrong']} | = 0 | "
        f"{'PASS' if h['compound_hc_pass'] else 'FAIL'} |",
        f"| Compound intent | {h['compound_intent_rate']} | >= {COMPOUND_INTENT_GATE} | "
        f"{'PASS' if h['compound_intent_pass'] else 'FAIL'} |",
        f"| Compound gold-part coverage | {h['compound_coverage']} | >= {COMPOUND_COVERAGE_GATE} | "
        f"{'PASS' if h['compound_coverage_pass'] else 'FAIL'} |",
        f"| Simple run warm-valid | {h['simple_run_gate_valid']} ({p['simple']['gate_valid_reason']}) | must be True | "
        f"{'PASS' if h['simple_run_gate_valid_pass'] else 'FAIL'} |",
        f"| Compound run warm-valid | {h['compound_run_gate_valid']} ({p['compound']['gate_valid_reason']}) | must be True | "
        f"{'PASS' if h['compound_run_gate_valid_pass'] else 'FAIL'} |",
        "",
        "> A run is warm-valid only when warm-up finished before the first clip and every"
        " scored clip saw the alias matrix. A mixed run measured two different systems.",
        "",
        "## TARGETS (diagnostic only)",
        "",
        "| Target | Value | Target | Met |",
        "|---|---|---|---|",
        f"| Simple p95 post | {t['simple_p95_ms']} ms | <= {t['simple_p95_target_ms']} ms | "
        f"{'yes' if t['simple_p95_met'] else 'no'} |",
        f"| Compound p95 post | {t['compound_p95_ms']} ms | <= {t['compound_p95_target_ms']} ms | "
        f"{'yes' if t['compound_p95_met'] else 'no'} |",
        f"| Simple intent rate | {t['simple_intent_rate']} | observe | — |",
        "",
    ]
    for cohort in ("simple", "compound"):
        c = p[cohort]
        out += [
            f"## {cohort.title()} — {c['suite']} (n={c['summary']['n']})",
            "",
            f"Source: `{c['source']}`",
            "",
            _fmt_stage_table(c["summary"]),
            "",
            "### Slowest 10",
            "",
            _fmt_slow(c["slowest_10"]),
            "",
        ]
    out += [
        "## Next",
        "",
        (
            "- **LATENCY_READY_FOR_V3** — proceed to Final Unseen Holdout v3."
            if p["ready"]
            else "- **NOT_READY_FOR_V3** — do not start Holdout v3; fix the failing hard gate first."
        ),
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simple", type=Path, default=None)
    ap.add_argument("--compound", type=Path, default=None)
    ap.add_argument("--stem", default="FINAL_LATENCY_CHECK")
    args = ap.parse_args()

    payload = run(args.simple, args.compound)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"{args.stem}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (REPORTS_DIR / f"{args.stem}.md").write_text(to_markdown(payload), encoding="utf-8")
    print(to_markdown(payload))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
