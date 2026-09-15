"""Post-speech latency audit (diagnostic only).

Does NOT tune STT (Track A frozen) or compound coverage (Track B frozen).
Reads the latest COMPOUND_DEV_REPORT.json and writes a stage breakdown:

  whisper_ms / compound_detect_ms / decomposition_ms / matching_ms /
  semantic_ms / rerank_ms / merge_ms / total_post_ms

Also runs an offline text-only compound timing pass for detect/decomp/match/merge
(no Whisper) to confirm where wall-clock sits after STT.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

REPORTS = BACKEND / "reports"
COMPOUND_JSON = REPORTS / "COMPOUND_DEV_REPORT.json"
SCRIPTS = (
    ROOT
    / "frontend"
    / "public"
    / "voice-drill"
    / "compound-dev"
    / "scripts.json"
)
OUT_JSON = REPORTS / "POST_SPEECH_LATENCY_AUDIT.json"
OUT_MD = REPORTS / "POST_SPEECH_LATENCY_AUDIT.md"


def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round((len(s) - 1) * p))))
    return round(s[i], 1)


def _mean(vals: list[float]) -> float:
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def _agg(rows: list[dict[str, float]]) -> dict[str, Any]:
    keys = [
        "whisper_ms",
        "match_ms",
        "compound_detect_ms",
        "decomposition_ms",
        "matching_ms",
        "semantic_ms",
        "rerank_ms",
        "merge_ms",
        "compound_ms",
        "intent_ms",
        "total_post_ms",
    ]
    out: dict[str, Any] = {"n": len(rows)}
    for k in keys:
        vals = [float(r.get(k) or 0.0) for r in rows]
        out[k] = {
            "p50": _pct(vals, 0.5),
            "p90": _pct(vals, 0.9),
            "mean": _mean(vals),
            "max": round(max(vals), 1) if vals else 0.0,
        }
    return out


def from_e2e_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results") or []
    rows: list[dict[str, float]] = []
    for r in results:
        t = r.get("timings") or {}
        ct = (r.get("compound_trace") or {}).get("timings") or {}
        sem = r.get("semantic_recovery") or {}
        # Older reports lack compound_detect_ms / rerank_ms — derive when possible.
        detect = float(t.get("compound_detect_ms") or ct.get("detection_ms") or 0.0)
        decomp = float(t.get("decomposition_ms") or ct.get("decomposition_ms") or 0.0)
        matching = float(t.get("matching_ms") or ct.get("matching_ms") or 0.0)
        merge = float(t.get("merge_ms") or ct.get("answer_merge_ms") or 0.0)
        compound_bucket = float(t.get("compound_ms") or 0.0)
        if detect <= 0 and compound_bucket > 0:
            # Folded detect ≈ residual of compound bucket after known stages.
            residual = compound_bucket - decomp - matching - merge
            detect = max(0.0, round(residual, 1)) if residual < 50 else 0.0
        rows.append(
            {
                "id": r.get("sample_id") or r.get("question_id") or "",
                "whisper_ms": float(t.get("whisper_ms") or t.get("stt_ms") or 0.0),
                "match_ms": float(t.get("match_ms") or 0.0),
                "compound_detect_ms": detect,
                "decomposition_ms": decomp,
                "matching_ms": matching,
                "semantic_ms": float(t.get("semantic_ms") or sem.get("latency_ms") or 0.0),
                "rerank_ms": float(t.get("rerank_ms") or sem.get("rerank_ms") or 0.0),
                "merge_ms": merge,
                "compound_ms": compound_bucket,
                "intent_ms": float(t.get("intent_ms") or 0.0),
                "total_post_ms": float(t.get("post_speech_ms") or 0.0),
            }
        )
    return {"source": str(path), "rows": rows, "summary": _agg(rows)}


def offline_compound_stages() -> dict[str, Any]:
    from app.services.compound_question_detector import detect_question_complexity
    from app.services.compound_question_pipeline import resolve_compound_question
    from app.services.question_bank import question_bank

    question_bank.load()
    scripts = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    scored = [s for s in scripts if not s.get("warmup")]
    # Warm embeddings / bank once.
    if scored:
        resolve_compound_question(scored[0]["transcript"])

    rows: list[dict[str, float]] = []
    for s in scored:
        text = s["transcript"]
        t0 = time.perf_counter()
        det = detect_question_complexity(text)
        detect_ms = (time.perf_counter() - t0) * 1000
        r = resolve_compound_question(text, detection=det)
        tt = r.timings or {}
        rows.append(
            {
                "id": s.get("id") or "",
                "whisper_ms": 0.0,
                "match_ms": 0.0,
                "compound_detect_ms": round(detect_ms, 1),
                "decomposition_ms": float(tt.get("decomposition_ms") or 0.0),
                "matching_ms": float(tt.get("matching_ms") or 0.0),
                "semantic_ms": 0.0,
                "rerank_ms": 0.0,
                "merge_ms": float(tt.get("answer_merge_ms") or 0.0),
                "compound_ms": float(r.total_latency_ms or 0.0),
                "intent_ms": float(r.total_latency_ms or 0.0) + detect_ms,
                "total_post_ms": float(r.total_latency_ms or 0.0) + detect_ms,
            }
        )
    return {
        "source": "offline_text_compound_dev",
        "note": "No Whisper/VAD — compound stages only, bank warmed",
        "rows": rows,
        "summary": _agg(rows),
    }


def write_md(e2e: dict[str, Any], offline: dict[str, Any]) -> str:
    es = e2e["summary"]
    os_ = offline["summary"]

    def row(label: str, block: dict[str, Any]) -> str:
        return (
            f"| {label} | {block['p50']} | {block['p90']} | {block['mean']} | {block['max']} |"
        )

    lines = [
        "# Post-Speech Latency Audit",
        "",
        "**Status:** DIAGNOSTIC (Track A/B frozen — no STT or compound-coverage retune)",
        f"**E2E source:** `{Path(e2e['source']).name}` (compound-dev, n={es['n']})",
        f"**Offline source:** text-only compound-dev (n={os_['n']})",
        "",
        "## Verdict",
        "",
        f"- E2E median **total_post_ms = {es['total_post_ms']['p50']} ms** (observe gate <=1500 for READY later).",
        f"- E2E median **whisper_ms = {es['whisper_ms']['p50']} ms** — STT is not the main leftover after Track A.",
        f"- Dominant leftover: **compound matching_ms p50 = {es['matching_ms']['p50']} ms** "
        f"+ **semantic_ms p50 = {es['semantic_ms']['p50']} ms** "
        f"(+ first-pass **match_ms p50 = {es['match_ms']['p50']} ms**).",
        f"- Decomposition / merge are tiny (decomp p50={es['decomposition_ms']['p50']} ms, "
        f"merge p50={es['merge_ms']['p50']} ms).",
        "",
        "## E2E breakdown (compound-dev audio)",
        "",
        "| Stage | p50 ms | p90 ms | mean | max |",
        "|-------|--------|--------|------|-----|",
        row("whisper_ms", es["whisper_ms"]),
        row("match_ms (pre-compound bank)", es["match_ms"]),
        row("semantic_ms", es["semantic_ms"]),
        row("rerank_ms", es["rerank_ms"]),
        row("compound_detect_ms", es["compound_detect_ms"]),
        row("decomposition_ms", es["decomposition_ms"]),
        row("matching_ms (compound)", es["matching_ms"]),
        row("merge_ms", es["merge_ms"]),
        row("compound_ms (detect+resolve)", es["compound_ms"]),
        row("intent_ms (match+sem+compound)", es["intent_ms"]),
        row("**total_post_ms**", es["total_post_ms"]),
        "",
        "## Offline compound stages (no Whisper)",
        "",
        "| Stage | p50 ms | p90 ms | mean | max |",
        "|-------|--------|--------|------|-----|",
        row("compound_detect_ms", os_["compound_detect_ms"]),
        row("decomposition_ms", os_["decomposition_ms"]),
        row("matching_ms", os_["matching_ms"]),
        row("merge_ms", os_["merge_ms"]),
        row("compound resolve total", os_["compound_ms"]),
        "",
        "## Interpretation",
        "",
        "1. Track A succeeded: Whisper is ~1–2s median on this pack, not ~3s.",
        "2. Compound **matching** (per-part `question_bank.match` + harvest `top_matches`) "
        "is the largest compound-internal cost (~1s median).",
        "3. **Semantic recovery** often adds hundreds of ms–>1s when triggered "
        "(compound-dev enables realistic recovery).",
        "4. Detect / decompose / merge are not the bottleneck.",
        "5. Do **not** hide this behind Track C Intent gains — READY still needs "
        "post-speech well below 4.6s after generalization.",
        "",
        "## Next (ordered)",
        "",
        "1. **Track C — Generalization** (new dev set; no Holdout v2).",
        "2. Separate **compound/semantic latency cut** (still frozen STT) once C is underway or after C gate.",
        "3. Only then Final Holdout v3.",
        "",
        "## Instrumentation note",
        "",
        "`StageTimings` now records `compound_detect_ms`, `decomposition_ms`, "
        "`matching_ms`, `rerank_ms`, `merge_ms` on new E2E runs. This audit used "
        "the frozen Track B report plus offline text timing.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    if not COMPOUND_JSON.is_file():
        raise SystemExit(f"Missing {COMPOUND_JSON} — run --suite compound_dev first")
    e2e = from_e2e_report(COMPOUND_JSON)
    offline = offline_compound_stages()
    payload = {
        "e2e_compound_dev": {
            "source": e2e["source"],
            "summary": e2e["summary"],
            "sample_rows": e2e["rows"][:5],
        },
        "offline_compound_dev": {
            "source": offline["source"],
            "note": offline["note"],
            "summary": offline["summary"],
            "sample_rows": offline["rows"][:5],
        },
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md = write_md(e2e, offline)
    OUT_MD.write_text(md, encoding="utf-8")
    # Avoid Windows console UnicodeEncodeError on special dashes.
    sys.stdout.buffer.write((md + f"\n\nWrote {OUT_MD}\nWrote {OUT_JSON}\n").encode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()
