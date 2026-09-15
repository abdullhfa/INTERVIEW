"""Final Latency Check on current A+B+C build (measure only).

Does NOT reuse Track B's 4608ms audit as judgment.
Reads fresh E2E reports:
  - LENGTH_SHORT_REGRESSION_REPORT.json  (simple)
  - COMPOUND_DEV_REPORT.json             (compound)

Writes FINAL_LATENCY_CHECK.{md,json} with stage p50/p95/mean split by cohort.
Gate: simple median post <= 1500 AND compound median post <= 1500.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
REPORTS = BACKEND / "reports"

SIMPLE_JSON = REPORTS / "LENGTH_SHORT_REGRESSION_REPORT.json"
COMPOUND_JSON = REPORTS / "COMPOUND_DEV_REPORT.json"
OUT_JSON = REPORTS / "FINAL_LATENCY_CHECK.json"
OUT_MD = REPORTS / "FINAL_LATENCY_CHECK.md"

GATE_MS = 1500.0

STAGE_KEYS = [
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
]


def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round((len(s) - 1) * p))))
    return round(s[i], 1)


def _mean(vals: list[float]) -> float:
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def _agg(rows: list[dict[str, float]]) -> dict[str, Any]:
    out: dict[str, Any] = {"n": len(rows)}
    for k in STAGE_KEYS:
        vals = [float(r.get(k) or 0.0) for r in rows]
        out[k] = {
            "p50": _pct(vals, 0.5),
            "p95": _pct(vals, 0.95),
            "mean": _mean(vals),
            "max": round(max(vals), 1) if vals else 0.0,
        }
    return out


def _extract_rows(path: Path, *, cohort: str) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results") or []
    rows: list[dict[str, Any]] = []
    for r in results:
        if (r.get("notes") or "").startswith("warmup:"):
            continue
        t = r.get("timings") or {}
        ct = (r.get("compound_trace") or {}).get("timings") or {}
        sem = r.get("semantic_recovery") or {}
        detect = float(t.get("compound_detect_ms") or ct.get("detection_ms") or 0.0)
        decomp = float(t.get("decomposition_ms") or ct.get("decomposition_ms") or 0.0)
        matching = float(t.get("matching_ms") or ct.get("matching_ms") or 0.0)
        merge = float(t.get("merge_ms") or ct.get("answer_merge_ms") or 0.0)
        compound_bucket = float(t.get("compound_ms") or 0.0)
        whisper = float(t.get("whisper_ms") or t.get("stt_ms") or 0.0)
        match = float(t.get("match_ms") or 0.0)
        semantic = float(t.get("semantic_ms") or sem.get("latency_ms") or 0.0)
        answer = float(t.get("answer_ms") or 0.0)
        post = float(t.get("post_speech_ms") or 0.0)
        # Prefer reported post; fall back to sum of stages if missing.
        if post <= 0:
            post = whisper + match + semantic + compound_bucket + answer
        rows.append(
            {
                "id": r.get("sample_id") or r.get("question_id") or "",
                "cohort": cohort,
                "intent_ok": bool(r.get("intent_ok")),
                "hc_wrong": bool(r.get("high_confidence_wrong")),
                "vad_ms": float(t.get("vad_ms") or 0.0),
                "whisper_ms": whisper,
                "match_ms": match,
                "semantic_ms": semantic,
                "rerank_ms": float(t.get("rerank_ms") or sem.get("rerank_ms") or 0.0),
                "compound_detect_ms": detect,
                "decomposition_ms": decomp,
                "matching_ms": matching,
                "merge_ms": merge,
                "compound_ms": compound_bucket,
                "answer_ms": answer,
                "intent_ms": float(t.get("intent_ms") or 0.0),
                "post_speech_ms": post,
            }
        )
    return rows


def _quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    intent_n = sum(1 for r in rows if r.get("intent_ok"))
    hc = sum(1 for r in rows if r.get("hc_wrong"))
    return {
        "n": n,
        "intent_ok": intent_n,
        "intent_rate": round(intent_n / n, 4) if n else 0.0,
        "hc_wrong": hc,
    }


def _table(summary: dict[str, Any], keys: list[str]) -> list[str]:
    lines = [
        "| Stage | p50 ms | p95 ms | mean | max |",
        "|-------|--------|--------|------|-----|",
    ]
    for k in keys:
        s = summary.get(k) or {}
        lines.append(
            f"| {k} | {s.get('p50', 0)} | {s.get('p95', 0)} | "
            f"{s.get('mean', 0)} | {s.get('max', 0)} |"
        )
    return lines


def write_md(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    simple = payload["simple"]["summary"]
    compound = payload["compound"]["summary"]
    combined = payload["combined"]["summary"]
    qs = payload["simple"]["quality"]
    qc = payload["compound"]["quality"]
    verdict = "PASS" if gate["ready"] else "FAIL"
    stage_order = [
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
    ]
    lines = [
        "# Final Latency Check (A+B+C)",
        "",
        f"**Status:** {verdict}",
        f"**Created:** {payload.get('created_at')}",
        "**Locks:** Track A/B/C frozen — measure only; do not use Track B 4608ms as judgment.",
        "",
        "## Gate",
        "",
        "| Cohort | Median post | Gate | Result |",
        "|--------|-------------|------|--------|",
        f"| Simple (`short_length`) | {gate['simple_median_post_ms']} ms | ≤ {GATE_MS:.0f} | "
        f"{'PASS' if gate['simple_pass'] else 'FAIL'} |",
        f"| Compound (`compound_dev`) | {gate['compound_median_post_ms']} ms | ≤ {GATE_MS:.0f} | "
        f"{'PASS' if gate['compound_pass'] else 'FAIL'} |",
        f"| Combined | {gate['combined_median_post_ms']} ms | observe | — |",
        "",
        f"**READY-relevant verdict:** **{verdict}** "
        f"(both simple and compound median post must be ≤ {GATE_MS:.0f} ms).",
        "",
        "## Quality (same runs; observe only)",
        "",
        f"- Simple: Intent {qs['intent_ok']}/{qs['n']} ({qs['intent_rate']:.0%}), HC={qs['hc_wrong']}",
        f"- Compound: Intent {qc['intent_ok']}/{qc['n']} ({qc['intent_rate']:.0%}), HC={qc['hc_wrong']}",
        "",
        "## Simple — short_length",
        "",
        f"Source: `{payload['simple']['source']}` · n={simple['n']}",
        "",
        *_table(simple, stage_order),
        "",
        "## Compound — compound_dev",
        "",
        f"Source: `{payload['compound']['source']}` · n={compound['n']}",
        "",
        *_table(compound, stage_order),
        "",
        "## Combined",
        "",
        f"n={combined['n']}",
        "",
        *_table(combined, stage_order),
        "",
        "## Interpretation",
        "",
    ]
    s_post = simple["post_speech_ms"]["p50"]
    c_post = compound["post_speech_ms"]["p50"]
    lines.append(
        f"1. Simple median post = **{s_post} ms** "
        f"({'≤' if s_post <= GATE_MS else '>'} {GATE_MS:.0f})."
    )
    lines.append(
        f"2. Compound median post = **{c_post} ms** "
        f"({'≤' if c_post <= GATE_MS else '>'} {GATE_MS:.0f})."
    )
    lines.append(
        f"3. Dominant compound stages (p50): whisper={compound['whisper_ms']['p50']}, "
        f"match={compound['match_ms']['p50']}, semantic={compound['semantic_ms']['p50']}, "
        f"compound_matching={compound['matching_ms']['p50']}."
    )
    lines.append(
        f"4. Dominant simple stages (p50): whisper={simple['whisper_ms']['p50']}, "
        f"match={simple['match_ms']['p50']}, semantic={simple['semantic_ms']['p50']}."
    )
    lines.append("5. `vad_ms` is observe-only (not counted in post-speech).")
    lines.extend(
        [
            "",
            "## Next",
            "",
        ]
    )
    if gate["ready"]:
        lines.append(
            "- **PASS** → next is Final Unseen Holdout **v3** (new pack only; not v1/v2/C)."
        )
    else:
        lines.append(
            "- **FAIL** → do **not** start Holdout v3. Open a separate latency-cut track "
            "(likely compound matching + semantic; STT stays frozen), then re-run this check."
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    missing = [p for p in (SIMPLE_JSON, COMPOUND_JSON) if not p.is_file()]
    if missing:
        raise SystemExit(
            "Missing fresh E2E reports:\n  "
            + "\n  ".join(str(p) for p in missing)
            + "\nRun --suite short_length and --suite compound_dev first (venv)."
        )

    simple_rows = _extract_rows(SIMPLE_JSON, cohort="simple")
    compound_rows = _extract_rows(COMPOUND_JSON, cohort="compound")
    if not simple_rows:
        raise SystemExit(f"No scored rows in {SIMPLE_JSON}")
    if not compound_rows:
        raise SystemExit(f"No scored rows in {COMPOUND_JSON}")

    simple_summary = _agg(simple_rows)
    compound_summary = _agg(compound_rows)
    combined_rows = simple_rows + compound_rows
    combined_summary = _agg(combined_rows)

    simple_median = float(simple_summary["post_speech_ms"]["p50"])
    compound_median = float(compound_summary["post_speech_ms"]["p50"])
    combined_median = float(combined_summary["post_speech_ms"]["p50"])
    simple_pass = simple_median <= GATE_MS
    compound_pass = compound_median <= GATE_MS
    gate = {
        "gate_ms": GATE_MS,
        "simple_median_post_ms": simple_median,
        "compound_median_post_ms": compound_median,
        "combined_median_post_ms": combined_median,
        "simple_p95_post_ms": float(simple_summary["post_speech_ms"]["p95"]),
        "compound_p95_post_ms": float(compound_summary["post_speech_ms"]["p95"]),
        "simple_pass": simple_pass,
        "compound_pass": compound_pass,
        "ready": simple_pass and compound_pass,
    }

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "track": "final_latency_check",
        "a_b_c_frozen": True,
        "not_track_b_audit": True,
        "gate": gate,
        "simple": {
            "source": str(SIMPLE_JSON),
            "suite": "short_length",
            "summary": simple_summary,
            "quality": _quality(simple_rows),
            "sample_rows": simple_rows[:3],
        },
        "compound": {
            "source": str(COMPOUND_JSON),
            "suite": "compound_dev",
            "summary": compound_summary,
            "quality": _quality(compound_rows),
            "sample_rows": compound_rows[:3],
        },
        "combined": {
            "summary": combined_summary,
            "quality": _quality(combined_rows),
        },
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md = write_md(payload)
    OUT_MD.write_text(md, encoding="utf-8")
    sys.stdout.buffer.write(
        (
            md
            + f"\n\nWrote {OUT_MD}\nWrote {OUT_JSON}\n"
            f"VERDICT={'PASS' if gate['ready'] else 'FAIL'}\n"
        ).encode("utf-8", errors="replace")
    )
    if not gate["ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
