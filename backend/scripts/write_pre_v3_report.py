"""
Build reports/FINAL_PRE_V3_LATENCY_HARDENING.{md,json}.

Reads the before/after suite reports plus the evaluator-v2 output and produces
the hardening report: before/after metrics, stage latency, slowest 10,
determinism across repeats, regression summary, optimization summary and the
final verdict (HARD GATE vs TARGET kept distinct).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"

from scripts.final_latency_check import (  # noqa: E402
    COMPOUND_COVERAGE_GATE,
    COMPOUND_INTENT_GATE,
    COMPOUND_MEDIAN_GATE_MS,
    COMPOUND_P95_TARGET_MS,
    SIMPLE_MEDIAN_GATE_MS,
    SIMPLE_P95_TARGET_MS,
    _cohort,
    _fmt_slow,
    _fmt_stage_table,
    run as run_gate,
)

# Measured baseline of the accepted pre-hardening state (Final Latency Check v1
# run of 2026-09-13T07:47Z). Used as the "Before" column.
BEFORE = {
    "simple": {
        "median_ms": 1193.6, "p95_ms": 3947.5, "intent_rate": 0.875,
        "hc_wrong": 0, "coverage": None,
    },
    "compound": {
        "median_ms": 1773.1, "p95_ms": 5027.1, "intent_rate": 1.0,
        "hc_wrong": 0, "coverage": 0.9313,
    },
}

OPTIMIZATIONS = [
    # file, function, reason, measured effect, quality impact
    ("app/services/domain_terms.py", "normalize_for_matching",
     "~80 compiled-regex substitutions were re-run for every bank alias, keyword "
     "and profile blob on the recovery path (tens of thousands of passes per "
     "request).",
     "LRU memoization of a pure function.",
     "None — identical output string."),
    ("app/services/technical_term_repair.py", "repair_technical_terms",
     "~30 regex passes repeated for the same transcript in match(), "
     "prefetch_scores(), should_trigger_semantic_recovery() and "
     "recover_semantic_intent().",
     "LRU memoization keyed by (text, prior_topic).",
     "None — pure function."),
    ("app/services/question_bank.py", "_content_tokens",
     "Tokenization repeated per alias / per candidate.",
     "LRU memoization; still returns a fresh list.",
     "None."),
    ("app/services/question_bank.py", "_build_lexical_structures / _score_all",
     "Per-alias scoring rebuilt a joined+casefolded entry blob for every "
     "distinctive family, plus the keyword blob for the guardrail rule.",
     "Per-entry constants hoisted to bank-load time "
     "(entry_owned_families / entry_guardrail_penalty / entry_cv_definition_penalty / "
     "entry_is_technical / entry_topic).",
     "None — same expressions, evaluated once."),
    ("app/services/question_bank.py", "_score_all (_lexical_batch)",
     "Two rapidfuzz calls per alias in a Python loop on full-bank scans.",
     "Optional process.cdist batching (same scorers) for pools >= 1200 aliases; "
     "QB_FAST_LEXICAL=0 forces the scalar path.",
     "None — verified byte-identical scores."),
    ("app/services/question_bank.py", "_maybe_semantic_rerank / _query_vector",
     "Re-embedded the query and the top-3 bank questions although both are "
     "already rows of alias_matrix / already embedded by _score_all.",
     "Reuse cached vectors; embed only on a cache miss.",
     "None — same vectors."),
    ("app/services/semantic_intent_recovery.py", "recover_semantic_intent (rerank)",
     "Re-embedded 5 profile blobs that are exactly the rows of the semantic "
     "intent matrix.",
     "semantic_intent_index.vector_for() lookup; query embedded once "
     "(RAW `repaired`, as before).",
     "None — same cosines."),
    ("app/services/semantic_intent_recovery.py", "_entry_static / _profile_blob_norm / "
     "_profile_blob_lower / _profile_owned_terms",
     "_lexical_expand_candidates normalized every profile blob on every call "
     "(full-bank scan); _alias_lex / _keyword_score / _conflict_penalty "
     "normalized aliases and keywords per candidate.",
     "Per-entry / per-profile static strings memoized per bank generation.",
     "None — same strings, same scores."),
    ("app/services/semantic_intent_recovery.py", "recover_semantic_intent "
     "(precomputed_trigger)",
     "should_trigger_semantic_recovery() ran a second time inside recovery, "
     "repeating repair + normalize + intent_agreement.",
     "Callers pass the decision they already computed.",
     "None — same (trigger, reason)."),
    ("app/services/intent_profile.py", "intent_agreement",
     "Rebuilt alias/keyword/blob targets and re-normalized them on every call; "
     "called 3-5x per request for the same (entry, spoken) pair.",
     "Per-entry statics + (entry, spoken) memo, invalidated on bank reload.",
     "None — same max() over the same score list."),
    ("app/services/compound_question_pipeline.py", "resolve_compound_question (harvest)",
     "Harvest scored the raw utterance and each clause separately, repeating "
     "identical queries.",
     "Dedupe harvest queries and warm the score cache with one batched "
     "prefetch_scores() pass.",
     "None — same queries, same order, same candidates."),
    ("app/services/warm_start.py", "warm_system / warm_system_blocking",
     "Whisper weights were loaded at startup but never exercised, and the "
     "semantic index / ONNX session compiled on the first live question.",
     "One tiny decode + one embedding at startup; SYSTEM_WARM flag exposed on "
     "/api/health and /api/health/warm.",
     "None — moves one-off cost off the live path."),
    ("scripts/final_latency_check.py", "run",
     "EVALUATOR BUG: a single gate_ms = 1500 was applied to both cohorts, so a "
     "compliant compound median (1773.1 <= 2000) reported FAIL.",
     "Cohort-specific hard gates (simple 1500 / compound 2000); p95 reported as "
     "TARGET, not gate.",
     "Scoring correction only — no pipeline change."),
]


def _cohort_runs(pattern: str) -> list[Path]:
    return sorted(REPORTS.glob(pattern))


def _determinism(paths: list[Path]) -> dict[str, Any]:
    runs = []
    for p in paths:
        payload = json.loads(p.read_text(encoding="utf-8"))
        rows = [r for r in (payload.get("results") or [])
                if not str(r.get("notes") or "").startswith("warmup:")]
        posts = [float((r.get("timings") or {}).get("post_speech_ms") or 0.0) for r in rows]
        runs.append({
            "file": p.name,
            "n": len(rows),
            "median_post_ms": round(statistics.median(posts), 1) if posts else 0.0,
            "intent_ok": sum(1 for r in rows if r.get("intent_ok")),
            "hc_wrong": sum(1 for r in rows if r.get("high_confidence_wrong")),
            "intents": {str(r.get("sample_id")): r.get("match_id") for r in rows},
            "results": {str(r.get("sample_id")): bool(r.get("intent_ok")) for r in rows},
        })
    unstable: list[str] = []
    if len(runs) >= 2:
        keys = set().union(*[set(r["results"]) for r in runs])
        for k in sorted(keys):
            vals = {r["results"].get(k) for r in runs}
            if len(vals) > 1:
                unstable.append(k)
    return {
        "runs": [{k: v for k, v in r.items() if k != "results"} for r in runs],
        "unstable_clips": unstable,
        "deterministic": not unstable,
    }


def build(simple_path: Optional[Path], compound_path: Optional[Path]) -> dict[str, Any]:
    gate = run_gate(simple_path, compound_path)
    after = {
        "simple": {
            "median_ms": gate["simple"]["summary"]["post_speech_ms"]["p50"],
            "p95_ms": gate["simple"]["summary"]["post_speech_ms"]["p95"],
            "intent_rate": gate["simple"]["quality"]["intent_rate"],
            "hc_wrong": gate["simple"]["quality"]["hc_wrong"],
            "coverage": gate["simple"]["quality"]["gold_part_coverage"],
        },
        "compound": {
            "median_ms": gate["compound"]["summary"]["post_speech_ms"]["p50"],
            "p95_ms": gate["compound"]["summary"]["post_speech_ms"]["p95"],
            "intent_rate": gate["compound"]["quality"]["intent_rate"],
            "hc_wrong": gate["compound"]["quality"]["hc_wrong"],
            "coverage": gate["compound"]["quality"]["gold_part_coverage"],
        },
    }
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "track": "final_pre_v3_latency_hardening",
        "before": BEFORE,
        "after": after,
        "hard_gates": gate["hard_gates"],
        "targets": gate["targets"],
        "verdict": gate["verdict"],
        "ready": gate["ready"],
        "stage_latency": {
            "simple": gate["simple"]["summary"],
            "simple_trace": gate["simple"]["trace_summary"],
            "compound": gate["compound"]["summary"],
            "compound_trace": gate["compound"]["trace_summary"],
        },
        "slowest_10": {
            "simple": gate["simple"]["slowest_10"],
            "compound": gate["compound"]["slowest_10"],
        },
        "determinism": {
            "simple": _determinism(_cohort_runs("_pre_v3_short_run*.json")),
            "compound": _determinism(_cohort_runs("_pre_v3_compound_run*.json")),
        },
        "optimizations": [
            {"file": f, "function": fn, "reason": r, "measured_effect": e, "quality_impact": q}
            for f, fn, r, e, q in OPTIMIZATIONS
        ],
    }
    return payload


def to_markdown(p: dict[str, Any]) -> str:
    b, a = p["before"], p["after"]
    h, t = p["hard_gates"], p["targets"]

    def _cell(value: Any, unit: str) -> str:
        return "n/a" if value is None else f"{value}{unit}"

    def _row(label: str, key: str, unit: str = "", simple: bool = True) -> str:
        s_before = _cell(b["simple"][key], unit) if simple else "n/a"
        s_after = _cell(a["simple"][key], unit) if simple else "n/a"
        return (
            f"| {label} | {s_before} | {s_after} | "
            f"{_cell(b['compound'][key], unit)} | {_cell(a['compound'][key], unit)} |"
        )

    out = [
        "# FINAL PRE-V3 PERFORMANCE & RELIABILITY HARDENING",
        "",
        f"**Verdict:** {p['verdict']}",
        f"**Created:** {p['created_at']}",
        "",
        "Intent layer, STT model, audio preprocessing, VAD, thresholds, weights, "
        "aliases and compound architecture are FROZEN. Every change below is an "
        "implementation change (caching, duplicate-work removal, batching, "
        "warm start) or the documented evaluator correction.",
        "",
        "## Before / After",
        "",
        "| Metric | Simple before | Simple after | Compound before | Compound after |",
        "|---|---|---|---|---|",
        _row("Median post-speech", "median_ms", " ms"),
        _row("p95 post-speech", "p95_ms", " ms"),
        _row("Intent rate", "intent_rate"),
        _row("HC wrong", "hc_wrong"),
        _row("Gold-part coverage", "coverage", simple=False),
        "",
        "## HARD GATES",
        "",
        "| Gate | Value | Threshold | Result |",
        "|---|---|---|---|",
        f"| Simple median post | {h['simple_median_ms']} ms | <= {SIMPLE_MEDIAN_GATE_MS} ms | "
        f"{'PASS' if h['simple_median_pass'] else 'FAIL'} |",
        f"| Compound median post | {h['compound_median_ms']} ms | <= {COMPOUND_MEDIAN_GATE_MS} ms | "
        f"{'PASS' if h['compound_median_pass'] else 'FAIL'} |",
        f"| Simple HC wrong | {h['simple_hc_wrong']} | = 0 | "
        f"{'PASS' if h['simple_hc_pass'] else 'FAIL'} |",
        f"| Compound HC wrong | {h['compound_hc_wrong']} | = 0 | "
        f"{'PASS' if h['compound_hc_pass'] else 'FAIL'} |",
        f"| Compound intent | {h['compound_intent_rate']} | >= {COMPOUND_INTENT_GATE} | "
        f"{'PASS' if h['compound_intent_pass'] else 'FAIL'} |",
        f"| Compound gold-part coverage | {h['compound_coverage']} | >= {COMPOUND_COVERAGE_GATE} | "
        f"{'PASS' if h['compound_coverage_pass'] else 'FAIL'} |",
        "",
        "## TARGETS (not release gates)",
        "",
        "| Target | Value | Target | Met |",
        "|---|---|---|---|",
        f"| Simple p95 post | {t['simple_p95_ms']} ms | <= {SIMPLE_P95_TARGET_MS} ms | "
        f"{'yes' if t['simple_p95_met'] else 'no'} |",
        f"| Compound p95 post | {t['compound_p95_ms']} ms | <= {COMPOUND_P95_TARGET_MS} ms | "
        f"{'yes' if t['compound_p95_met'] else 'no'} |",
        "",
        "## Stage latency — simple",
        "",
        _fmt_stage_table(p["stage_latency"]["simple"]),
        "",
        "### Simple stage trace (post_speech_trace)",
        "",
        _fmt_stage_table(p["stage_latency"]["simple_trace"]),
        "",
        "## Stage latency — compound",
        "",
        _fmt_stage_table(p["stage_latency"]["compound"]),
        "",
        "### Compound stage trace (post_speech_trace)",
        "",
        _fmt_stage_table(p["stage_latency"]["compound_trace"]),
        "",
        "## Slowest 10 — simple",
        "",
        _fmt_slow(p["slowest_10"]["simple"]),
        "",
        "## Slowest 10 — compound",
        "",
        _fmt_slow(p["slowest_10"]["compound"]),
        "",
        "## Determinism (repeat runs)",
        "",
    ]
    for cohort in ("simple", "compound"):
        det = p["determinism"][cohort]
        out.append(f"### {cohort}")
        out.append("")
        if not det["runs"]:
            out += ["_no repeat runs recorded_", ""]
            continue
        out += ["| run | n | median post | intent ok | HC wrong |", "|---|---|---|---|---|"]
        for r in det["runs"]:
            out.append(
                f"| {r['file']} | {r['n']} | {r['median_post_ms']} ms | {r['intent_ok']} | {r['hc_wrong']} |"
            )
        out += [
            "",
            f"Deterministic: **{det['deterministic']}**"
            + ("" if det["deterministic"] else f" — unstable clips: {det['unstable_clips']}"),
            "",
        ]
    out += ["## Optimization summary", "",
            "| File | Function | Reason | Measured effect | Quality impact |",
            "|---|---|---|---|---|"]
    for o in p["optimizations"]:
        out.append(
            f"| `{o['file']}` | `{o['function']}` | {o['reason']} | {o['measured_effect']} | "
            f"{o['quality_impact']} |"
        )
    out += [
        "",
        "## Final verdict",
        "",
        f"**{p['verdict']}**",
        "",
        (
            "All hard gates pass — Final Unseen Holdout v3 may start."
            if p["ready"]
            else "A hard gate failed — do NOT start Final Unseen Holdout v3."
        ),
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simple", type=Path, default=None)
    ap.add_argument("--compound", type=Path, default=None)
    args = ap.parse_args()
    payload = build(args.simple, args.compound)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "FINAL_PRE_V3_LATENCY_HARDENING.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (REPORTS / "FINAL_PRE_V3_LATENCY_HARDENING.md").write_text(
        to_markdown(payload), encoding="utf-8"
    )
    print(f"verdict: {payload['verdict']}")
    print(f"wrote {REPORTS / 'FINAL_PRE_V3_LATENCY_HARDENING.md'}")
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
