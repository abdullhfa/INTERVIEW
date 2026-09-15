"""
Clean A/B Audio→STT benchmark (no intent/matcher changes).

Compares preprocess variants on the same WAV files:
  raw | preroll_pad | normalize | denoise | combo
  + vad_crop / vad_crop_preroll (onset-loss simulation)

Does not touch question-bank aliases or the confidence gate.
"""

from __future__ import annotations

import html
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from rapidfuzz import fuzz

from app.audio.utterance_preprocess import apply_preprocess
from app.audio.whisper_stt import transcribe_whisper, warm_whisper_model
from app.services.interview_audio_runner import load_wav_mono
from app.services.stt_confidence import edge_word_diagnostics, needs_accurate_second_pass

STRESS_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "stress-pilot"
)
REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"

# Primary A/B variants requested for Clean diagnosis.
PRIMARY_VARIANTS = ("raw", "preroll_pad", "normalize", "denoise", "combo")
# Extra onset diagnostics (not used to pick the live default).
ONSET_VARIANTS = ("vad_crop", "vad_crop_preroll")
DEFAULT_VARIANTS = PRIMARY_VARIANTS + ONSET_VARIANTS

TECH_TERMS = (
    "rag", "agentic", "langchain", "langgraph", "guardrails",
    "embeddings", "chromadb", "n8n", "llm", "retrieval",
)


@dataclass
class VariantResult:
    variant: str
    transcript: str
    score: float
    stt_ms: float
    first_word_missing: bool
    last_word_missing: bool
    hallucinated_tech_term: bool
    accurate_pass: bool = False


@dataclass
class ClipABResult:
    sample_id: Optional[int]
    file: str
    question_id: Optional[int]
    speaker: Optional[str]
    condition: str
    expected: str
    speech_duration_ms: float
    variants: dict[str, VariantResult] = field(default_factory=dict)
    best_variant: str = ""
    best_score: float = 0.0
    combo_hurts: bool = False
    raw_beats_combo: bool = False


def _score(transcript: str, expected: str) -> float:
    a = (transcript or "").strip()
    b = (expected or "").strip()
    if not a or not b:
        return 0.0
    return round(fuzz.token_set_ratio(a, b) / 100.0, 4)


def _hallucinated_tech(transcript: str, expected: str) -> bool:
    """True if a known tech term appears in transcript but not in expected."""
    t = (transcript or "").casefold()
    e = (expected or "").casefold()
    for term in TECH_TERMS:
        if term in t and term not in e:
            # Allow common substrings only when clearly present as a word-ish token.
            if term == "rag" and "rag" not in e and "retrieval" not in e:
                return True
            if term != "rag":
                return True
    return False


def load_clean_rows(metadata: list[dict[str, Any]], *, limit: Optional[int] = None) -> list[dict[str, Any]]:
    rows = [r for r in metadata if str(r.get("condition")) == "clean"]
    rows.sort(key=lambda r: (int(r.get("question_id") or 0), str(r.get("requested_region_profile")), str(r.get("file"))))
    if limit is not None:
        return rows[:limit]
    return rows


def run_clip_ab(
    meta: dict[str, Any],
    *,
    variants: tuple[str, ...] = DEFAULT_VARIANTS,
    also_accurate_on_short: bool = True,
) -> ClipABResult:
    path = STRESS_ROOT / str(meta["file"])
    expected = str(meta.get("spoken_wording") or meta.get("main_question") or "")
    audio, sr = load_wav_mono(path)
    if sr != 16000 and len(audio):
        # Simple downsample if needed
        ratio = sr / 16000
        if ratio > 1:
            audio = audio[:: int(ratio)]
            sr = 16000
    duration_ms = (len(audio) / float(sr)) * 1000.0 if len(audio) else 0.0

    out = ClipABResult(
        sample_id=meta.get("sample_id"),
        file=str(meta.get("file")),
        question_id=meta.get("question_id"),
        speaker=meta.get("requested_region_profile"),
        condition=str(meta.get("condition")),
        expected=expected,
        speech_duration_ms=round(duration_ms, 1),
    )

    for name in variants:
        processed = apply_preprocess(audio, name, sample_rate=sr)
        t0 = time.perf_counter()
        text = transcribe_whisper(processed, sr, accurate=False)
        stt_ms = (time.perf_counter() - t0) * 1000
        # Specialized accurate second-pass for short transcripts only.
        if also_accurate_on_short and needs_accurate_second_pass(text):
            t1 = time.perf_counter()
            text2 = transcribe_whisper(processed, sr, accurate=True)
            stt_ms += (time.perf_counter() - t1) * 1000
            if _score(text2, expected) >= _score(text, expected):
                text = text2
                accurate_used = True
            else:
                accurate_used = False
        else:
            accurate_used = False
        edge = edge_word_diagnostics(expected, text)
        score = _score(text, expected)
        out.variants[name] = VariantResult(
            variant=name,
            transcript=text,
            score=score,
            stt_ms=round(stt_ms, 1),
            first_word_missing=(edge["first_word_missing"]),
            last_word_missing=(edge["last_word_missing"]),
            hallucinated_tech_term=_hallucinated_tech(text, expected),
            accurate_pass=accurate_used,
        )

    ranked = sorted(out.variants.values(), key=lambda v: (-v.score, v.stt_ms))
    best = ranked[0]
    out.best_variant = best.variant
    out.best_score = best.score
    raw = out.variants.get("raw")
    combo = out.variants.get("combo")
    if raw and combo:
        out.raw_beats_combo = raw.score > combo.score + 0.02
        out.combo_hurts = out.raw_beats_combo and combo.score < 0.85
    return out


def summarize_ab(results: list[ClipABResult], variants: tuple[str, ...]) -> dict[str, Any]:
    total = len(results)
    by_variant: dict[str, Any] = {}
    for name in variants:
        scores = [r.variants[name].score for r in results if name in r.variants]
        ok = sum(1 for s in scores if s >= 0.72)
        first_miss = sum(1 for r in results if name in r.variants and r.variants[name].first_word_missing)
        last_miss = sum(1 for r in results if name in r.variants and r.variants[name].last_word_missing)
        hallu = sum(1 for r in results if name in r.variants and r.variants[name].hallucinated_tech_term)
        avg_ms = round(sum(r.variants[name].stt_ms for r in results if name in r.variants) / max(1, len(scores)), 1)
        by_variant[name] = {
            "n": len(scores),
            "stt_ok_rate": round(ok / max(1, len(scores)), 3),
            "mean_score": round(sum(scores) / max(1, len(scores)), 3),
            "median_score": round(sorted(scores)[len(scores) // 2], 3) if scores else 0.0,
            "first_word_missing_rate": round(first_miss / max(1, len(scores)), 3),
            "last_word_missing_rate": round(last_miss / max(1, len(scores)), 3),
            "tech_hallucination_rate": round(hallu / max(1, len(scores)), 3),
            "avg_stt_ms": avg_ms,
        }

    wins = Counter(r.best_variant for r in results)
    combo_hurt = sum(1 for r in results if r.combo_hurts)
    raw_beats = sum(1 for r in results if r.raw_beats_combo)

    # Pairwise: does combo beat raw?
    better_default = "combo"
    if "raw" in by_variant and "combo" in by_variant:
        if by_variant["raw"]["stt_ok_rate"] > by_variant["combo"]["stt_ok_rate"] + 0.03:
            better_default = "raw"
        elif by_variant["normalize"]["stt_ok_rate"] >= max(
            by_variant["combo"]["stt_ok_rate"], by_variant["raw"]["stt_ok_rate"]
        ):
            better_default = "normalize"
        elif by_variant["denoise"]["stt_ok_rate"] > by_variant["combo"]["stt_ok_rate"] + 0.03:
            better_default = "denoise"

    # Failures where raw beats combo (actionable)
    hurt_examples = []
    for r in results:
        if not r.combo_hurts:
            continue
        hurt_examples.append({
            "file": r.file,
            "expected": r.expected,
            "raw": r.variants["raw"].transcript if "raw" in r.variants else "",
            "combo": r.variants["combo"].transcript if "combo" in r.variants else "",
            "raw_score": r.variants["raw"].score if "raw" in r.variants else 0,
            "combo_score": r.variants["combo"].score if "combo" in r.variants else 0,
            "best": r.best_variant,
        })

    return {
        "total_clips": total,
        "by_variant": by_variant,
        "best_variant_wins": dict(wins),
        "combo_hurts_count": combo_hurt,
        "raw_beats_combo_count": raw_beats,
        "recommended_live_preprocess": better_default,
        "combo_hurt_examples": hurt_examples[:20],
        "targets": {"clean_stt_ok": 0.90},
    }


def write_ab_reports(results: list[ClipABResult], summary: dict[str, Any], filters: dict[str, Any]) -> dict[str, str]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "clean_stt_ab_benchmark",
        "filters": filters,
        "summary": summary,
        "results": [
            {
                **{k: getattr(r, k) for k in (
                    "sample_id", "file", "question_id", "speaker", "condition",
                    "expected", "speech_duration_ms", "best_variant", "best_score",
                    "combo_hurts", "raw_beats_combo",
                )},
                "variants": {k: asdict(v) for k, v in r.variants.items()},
            }
            for r in results
        ],
    }
    stem = "CLEAN_STT_AB_REPORT"
    json_path = REPORTS_DIR / f"{stem}_{stamp}.json"
    latest = REPORTS_DIR / f"{stem}.json"
    html_path = REPORTS_DIR / f"{stem}.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    def esc(x: Any) -> str:
        return html.escape("" if x is None else str(x))

    cards = []
    for name, block in summary.get("by_variant", {}).items():
        cards.append(
            f"<div class='card'><span>{esc(name)}</span>"
            f"<b>{block.get('stt_ok_rate', 0):.0%}</b>"
            f"<small>mean {block.get('mean_score')} · 1st-miss {block.get('first_word_missing_rate')}</small></div>"
        )

    rows = []
    for r in sorted(results, key=lambda x: (x.combo_hurts, -x.best_score)):
        raw_t = r.variants.get("raw")
        combo_t = r.variants.get("combo")
        rows.append(
            "<tr class='{cls}'><td>{qid}</td><td>{sp}</td><td>{exp}</td>"
            "<td>{raw}</td><td>{combo}</td><td>{best}</td><td>{hurt}</td></tr>".format(
                cls="hurt" if r.combo_hurts else "ok",
                qid=esc(r.question_id),
                sp=esc(r.speaker),
                exp=esc(r.expected),
                raw=esc(f"{raw_t.score:.2f} · {raw_t.transcript}" if raw_t else "—"),
                combo=esc(f"{combo_t.score:.2f} · {combo_t.transcript}" if combo_t else "—"),
                best=esc(f"{r.best_variant} ({r.best_score:.2f})"),
                hurt=esc("YES" if r.combo_hurts else "—"),
            )
        )

    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Clean STT A/B Report</title>
<style>
body{{font-family:Segoe UI,Tahoma,sans-serif;margin:24px;background:#0f1419;color:#e8eef5}}
.card{{display:inline-block;background:#1a222d;border:1px solid #2a3544;border-radius:12px;padding:12px;margin:6px;min-width:130px;vertical-align:top}}
.card b{{display:block;font-size:1.3rem}}
.card small{{color:#8b9aab}}
table{{width:100%;border-collapse:collapse;background:#1a222d;margin-top:16px}}
th,td{{border-bottom:1px solid #2a3544;padding:8px;font-size:.82rem;text-align:left;vertical-align:top}}
tr.hurt td{{background:rgba(240,113,120,.10)}}
.meta{{color:#8b9aab}}
</style></head><body>
<h1>Clean STT A/B Benchmark</h1>
<p class="meta">Direct WAV → preprocess → Whisper (no matcher). Generated {esc(payload['created_at'])}</p>
<p class="meta">Recommended live preprocess: <b>{esc(summary.get('recommended_live_preprocess'))}</b>
 · combo hurts: {summary.get('combo_hurts_count')} · raw beats combo: {summary.get('raw_beats_combo_count')}</p>
<div>{''.join(cards)}</div>
<p><b>Best-variant wins:</b> {esc(json.dumps(summary.get('best_variant_wins')))}</p>
<table><thead><tr>
<th>Q</th><th>Speaker</th><th>Expected</th><th>RAW</th><th>COMBO</th><th>Best</th><th>Combo hurts</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
</body></html>"""
    html_path.write_text(body, encoding="utf-8")
    desktop = Path.home() / "OneDrive" / "Desktop"
    try:
        if desktop.is_dir():
            (desktop / f"{stem}.html").write_text(body, encoding="utf-8")
    except OSError:
        pass
    return {"report_json": str(json_path), "report_html": str(html_path)}


async def run_clean_stt_ab(
    *,
    limit: Optional[int] = None,
    variants: tuple[str, ...] = DEFAULT_VARIANTS,
) -> dict[str, Any]:
    await warm_whisper_model()
    metadata = json.loads((STRESS_ROOT / "metadata.json").read_text(encoding="utf-8"))
    rows = load_clean_rows(metadata, limit=limit)
    results: list[ClipABResult] = []
    print(f"=== Clean STT A/B · {len(rows)} clips · variants={list(variants)} ===", flush=True)
    for i, row in enumerate(rows, start=1):
        result = run_clip_ab(row, variants=variants)
        results.append(result)
        print(
            f"[{i}/{len(rows)}] Q{result.question_id} {result.speaker} "
            f"best={result.best_variant}:{result.best_score:.2f} "
            f"combo_hurts={result.combo_hurts} "
            f"raw={result.variants.get('raw').score if 'raw' in result.variants else '-'} "
            f"combo={result.variants.get('combo').score if 'combo' in result.variants else '-'}",
            flush=True,
        )
    summary = summarize_ab(results, variants)
    filters = {"condition": "clean", "limit": limit, "variants": list(variants)}
    paths = write_ab_reports(results, summary, filters)
    return {"summary": summary, "results": results, **paths, "filters": filters}
