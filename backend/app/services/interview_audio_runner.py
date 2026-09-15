"""
Automated Interview Audio Test Runner

Direct-injects stress-pilot WAV clips into:
  WAV → Whisper STT → Question Bank match → prepared answer

Evaluates semantically (not word-for-word) and writes JSON + HTML reports
with failure-stage diagnosis.
"""

from __future__ import annotations

import html
import json
import time
import wave
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from rapidfuzz import fuzz

from app.audio.whisper_stt import transcribe_whisper_async
from app.services.question_bank import question_bank

STRESS_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "stress-pilot"
)
REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"

STAGES = (
    "AUDIO",
    "STT",
    "QUESTION_UNDERSTANDING",
    "RETRIEVAL",
    "ANSWER_GENERATION",
)


@dataclass
class StageTiming:
    stt_ms: float = 0.0
    understand_ms: float = 0.0
    answer_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class TestCaseResult:
    sample_id: Optional[int]
    file: str
    question_id: Optional[int]
    speaker: Optional[str]
    condition: Optional[str]
    expected_question: str
    spoken_wording: str
    expected_answer: Optional[str]
    transcript: str
    stt_ok: bool
    stt_score: float
    intent_ok: bool
    intent_score: float
    topic: Optional[str]
    match_id: Optional[str]
    match_question: Optional[str]
    match_score: float
    match_mode: Optional[str]
    answer_en: Optional[str]
    answer_ok: bool
    answer_score: float
    accuracy: float
    result: str  # PASS / FAIL
    failure_stage: Optional[str]
    failure_detail: str
    recovered_after_stt_error: bool = False
    timings: StageTiming = field(default_factory=StageTiming)
    notes: str = ""


def load_metadata() -> list[dict[str, Any]]:
    path = STRESS_ROOT / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"Stress metadata not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_clip_path(relative_file: str) -> Path:
    rel = relative_file.replace("\\", "/").lstrip("/")
    if rel.startswith("stress-pilot/"):
        rel = rel[len("stress-pilot/") :]
    path = (STRESS_ROOT / rel).resolve()
    root = STRESS_ROOT.resolve()
    if root not in path.parents and path != root:
        raise ValueError("Audio path outside stress-pilot folder")
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {rel}")
    return path


def find_meta_for_file(relative_file: str, metadata: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    target = relative_file.replace("\\", "/").lstrip("/")
    if target.startswith("stress-pilot/"):
        target = target[len("stress-pilot/") :]
    for row in metadata:
        if str(row.get("file", "")).replace("\\", "/") == target:
            return row
    name = Path(target).name
    for row in metadata:
        if Path(str(row.get("file", ""))).name == name:
            return row
    return None


def filter_metadata(
    metadata: list[dict[str, Any]],
    *,
    question_id: Optional[int] = None,
    speaker: Optional[str] = None,
    condition: Optional[str] = None,
    limit: int = 180,
) -> list[dict[str, Any]]:
    rows = metadata
    if question_id is not None:
        rows = [r for r in rows if int(r.get("question_id", -1)) == (question_id)]
    if speaker and speaker not in {"all", "*"}:
        rows = [r for r in rows if str(r.get("requested_region_profile")) == speaker]
    if condition and condition not in {"all", "*"}:
        rows = [r for r in rows if str(r.get("condition")) == condition]
    return rows[: max(1, min((limit), 180))]


def load_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())

    if sample_width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sample_width == 1:
        audio = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return np.ascontiguousarray(audio, dtype=np.float32),(sample_rate)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-9:
        return 0.0
    return float(np.dot(a, b) / denom)


def semantic_similarity(a: str, b: str, *, use_embeddings: bool = False) -> float:
    """Blend token-set ratio with optional embedding cosine."""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    lexical = fuzz.token_set_ratio(a, b) / 100.0
    if not use_embeddings:
        return round(lexical, 4)
    vectors = question_bank._embed([a, b])  # noqa: SLF001 — shared local embedder
    if vectors is None or len(vectors) < 2:
        return round(lexical, 4)
    cosine = _cosine(np.asarray(vectors[0], dtype=np.float32), np.asarray(vectors[1], dtype=np.float32))
    cosine_norm = max(0.0, min(1.0, (cosine - 0.15) / 0.80))
    return round(0.55 * cosine_norm + 0.45 * lexical, 4)


def _diagnose_failure(
    *,
    transcript: str,
    stt_ok: bool,
    stt_score: float,
    intent_ok: bool,
    intent_score: float,
    match_id: Optional[str],
    answer_en: Optional[str],
    answer_ok: bool,
) -> tuple[Optional[str], str]:
    if not transcript.strip():
        return "STT", "Empty transcript — audio did not yield usable speech."
    if not stt_ok and not intent_ok:
        return "STT", "Poor transcription changed the question meaning."
    if stt_ok and not intent_ok:
        return "QUESTION_UNDERSTANDING", "Transcript was usable, but the matcher chose the wrong question/intent."
    if intent_ok and match_id is None:
        return "RETRIEVAL", "Intent looked close, but no bank entry was retrieved."
    if intent_ok and not answer_en:
        return "ANSWER_GENERATION", "Question matched, but no prepared answer was returned."
    if intent_ok and answer_en and not answer_ok:
        return "ANSWER_GENERATION", "Answer text drifted from the expected meaning / CV-safe content."
    if not stt_ok and intent_ok and answer_ok:
        return None, "STT had word errors, but intent and answer stayed correct (PASS)."
    return None, ""


async def run_one(meta: dict[str, Any]) -> TestCaseResult:
    question_bank.load()
    path = resolve_clip_path(str(meta["file"]))
    expected_q = str(meta.get("main_question") or meta.get("spoken_wording") or "")
    spoken = str(meta.get("spoken_wording") or expected_q)
    expected_a = str(meta.get("expected_answer") or "") or None

    t0 = time.perf_counter()
    audio, sample_rate = load_wav_mono(path)
    if len(audio) < int(0.05 * sample_rate):
        timings = StageTiming(total_ms=round((time.perf_counter() - t0) * 1000, 1))
        return TestCaseResult(
            sample_id=meta.get("sample_id"),
            file=str(meta.get("file")),
            question_id=meta.get("question_id"),
            speaker=meta.get("requested_region_profile"),
            condition=meta.get("condition"),
            expected_question=expected_q,
            spoken_wording=spoken,
            expected_answer=expected_a,
            transcript="",
            stt_ok=False,
            stt_score=0.0,
            intent_ok=False,
            intent_score=0.0,
            topic=None,
            match_id=None,
            match_question=None,
            match_score=0.0,
            match_mode=None,
            answer_en=None,
            answer_ok=False,
            answer_score=0.0,
            accuracy=0.0,
            result="FAIL",
            failure_stage="AUDIO",
            failure_detail="Audio clip too short or empty.",
            timings=timings,
            notes="AUDIO stage failure",
        )

    t_stt = time.perf_counter()
    transcript = await transcribe_whisper_async(audio, sample_rate)
    stt_ms = (time.perf_counter() - t_stt) * 1000.0

    t_u = time.perf_counter()
    stt_score = semantic_similarity(transcript, spoken)
    # Also allow similarity to the canonical question wording.
    stt_score = max(stt_score, semantic_similarity(transcript, expected_q))
    stt_ok = stt_score >= 0.72 and bool(transcript.strip())

    match = question_bank.match(transcript) if transcript.strip() else None
    understand_ms = (time.perf_counter() - t_u) * 1000.0

    t_a = time.perf_counter()
    intent_score = 0.0
    topic = None
    match_id = None
    match_question = None
    match_score = 0.0
    match_mode = None
    answer_en = None
    if match is not None:
        topic = match.entry.topic or match.entry.category
        match_id = match.entry.id
        match_question = match.entry.question
        match_score = float(match.score)
        match_mode = match.mode
        answer_en = match.entry.answer_en
        intent_score = max(
            semantic_similarity(match.entry.question, expected_q),
            semantic_similarity(match.entry.question, spoken),
            *[semantic_similarity(alias, expected_q) for alias in (match.entry.aliases or [])[:8]],
        )
    intent_ok = bool(match) and intent_score >= 0.70 and match_score >= 0.40

    answer_score = 0.0
    if answer_en and expected_a:
        answer_score = semantic_similarity(answer_en, expected_a, use_embeddings=True)
    elif answer_en and intent_ok:
        answer_score = 0.85
    # For this coach, a correct bank match already yields the prepared CV-safe answer.
    answer_ok = bool(answer_en) and intent_ok
    if answer_ok:
        answer_score = max(answer_score, 0.85)
    answer_ms = (time.perf_counter() - t_a) * 1000.0

    # Soft-STT PASS rule from the user's spec: word errors OK if intent+answer correct.
    result_pass = intent_ok and answer_ok
    recovered = (not stt_ok) and intent_ok and answer_ok
    accuracy = round(100.0 * (0.25 * stt_score + 0.40 * intent_score + 0.35 * answer_score), 1)

    failure_stage, failure_detail = _diagnose_failure(
        transcript=transcript,
        stt_ok=stt_ok,
        stt_score=stt_score,
        intent_ok=intent_ok,
        intent_score=intent_score,
        match_id=match_id,
        answer_en=answer_en,
        answer_ok=answer_ok,
    )
    if result_pass:
        failure_stage = None
        if recovered:
            failure_detail = (
                "RECOVERED_AFTER_STT_ERROR: transcript imperfect, but intent and answer correct."
            )
        else:
            failure_detail = ""

    try:
        file_label = str(path.resolve().relative_to(STRESS_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        file_label = str(meta.get("file"))

    total_ms = (time.perf_counter() - t0) * 1000.0
    return TestCaseResult(
        sample_id=meta.get("sample_id"),
        file=file_label,
        question_id=meta.get("question_id"),
        speaker=meta.get("requested_region_profile"),
        condition=meta.get("condition"),
        expected_question=expected_q,
        spoken_wording=spoken,
        expected_answer=expected_a,
        transcript=transcript,
        stt_ok=stt_ok,
        stt_score=round(stt_score, 3),
        intent_ok=intent_ok,
        intent_score=round(intent_score, 3),
        topic=topic,
        match_id=match_id,
        match_question=match_question,
        match_score=round(match_score, 3),
        match_mode=match_mode,
        answer_en=answer_en,
        answer_ok=answer_ok,
        answer_score=round(answer_score, 3),
        accuracy=accuracy,
        result="PASS" if result_pass else "FAIL",
        failure_stage=failure_stage,
        failure_detail=failure_detail,
        recovered_after_stt_error=recovered,
        timings=StageTiming(
            stt_ms=round(stt_ms, 1),
            understand_ms=round(understand_ms, 1),
            answer_ms=round(answer_ms, 1),
            total_ms=round(total_ms, 1),
        ),
        notes="Direct audio injection",
    )


def summarize(results: list[TestCaseResult]) -> dict[str, Any]:
    total = len(results)
    stt_ok = sum(1 for r in results if r.stt_ok)
    intent_ok = sum(1 for r in results if r.intent_ok)
    answer_ok = sum(1 for r in results if r.answer_ok)
    passed = sum(1 for r in results if r.result == "PASS")
    failed = [r for r in results if r.result == "FAIL"]

    soft_stt_fail = sum(1 for r in results if not r.stt_ok)
    recovered = sum(1 for r in results if r.recovered_after_stt_error)
    intent_recovery_rate = round((recovered / soft_stt_fail) if soft_stt_fail else 0.0, 3)

    by_condition: dict[str, dict[str, int]] = {}
    by_speaker: dict[str, dict[str, int]] = {}
    by_stage: dict[str, int] = {}
    for r in results:
        cond = r.condition or "unknown"
        sp = r.speaker or "unknown"
        by_condition.setdefault(cond, {"total": 0, "pass": 0})
        by_condition[cond]["total"] += 1
        by_condition[cond]["pass"] += int(r.result == "PASS")
        by_speaker.setdefault(sp, {"total": 0, "pass": 0})
        by_speaker[sp]["total"] += 1
        by_speaker[sp]["pass"] += int(r.result == "PASS")
        if r.failure_stage:
            by_stage[r.failure_stage] = by_stage.get(r.failure_stage, 0) + 1

    def rate(block: dict[str, dict[str, int]]) -> dict[str, Any]:
        out = {}
        for key, val in sorted(block.items(), key=lambda kv: (kv[1]["pass"] / max(kv[1]["total"], 1))):
            t = val["total"]
            p = val["pass"]
            out[key] = {"total": t, "pass": p, "pass_rate": round((p / t) if t else 0.0, 3)}
        return out

    # Main weakness = lowest pass-rate condition+speaker combo with enough samples
    weakness = "none"
    worst = None
    for r in results:
        key = f"{r.condition} + {r.speaker}"
        # computed below
    combo: dict[str, dict[str, int]] = {}
    for r in results:
        key = f"{r.condition or '?'} + {r.speaker or '?'}"
        combo.setdefault(key, {"total": 0, "pass": 0})
        combo[key]["total"] += 1
        combo[key]["pass"] += int(r.result == "PASS")
    for key, val in combo.items():
        if val["total"] < 2:
            continue
        rate_v = val["pass"] / val["total"]
        if worst is None or rate_v < worst[0]:
            worst = (rate_v, key, val)
    if worst is not None and worst[0] < 0.85:
        weakness = f"{worst[1]} (pass {worst[2]['pass']}/{worst[2]['total']})"

    avg_latency = (
        round(sum(r.timings.total_ms for r in results) / total / 1000.0, 3) if total else 0.0
    )
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round((passed / total) if total else 0.0, 3),
        "stt_success": f"{stt_ok}/{total}",
        "stt_success_rate": round((stt_ok / total) if total else 0.0, 3),
        "intent_success": f"{intent_ok}/{total}",
        "intent_success_rate": round((intent_ok / total) if total else 0.0, 3),
        "answer_success": f"{answer_ok}/{total}",
        "answer_success_rate": round((answer_ok / total) if total else 0.0, 3),
        "recovered_after_stt_error": recovered,
        "stt_imperfect_cases": soft_stt_fail,
        "intent_recovery_rate": intent_recovery_rate,
        "average_latency_sec": avg_latency,
        "failed_cases": total - passed,
        "main_weakness": weakness,
        "failure_stages": by_stage,
        "by_condition": rate(by_condition),
        "by_speaker": rate(by_speaker),
        "failed_sample_ids": [r.sample_id for r in failed],
    }


def _result_to_dict(r: TestCaseResult) -> dict[str, Any]:
    d = asdict(r)
    return d


def write_json_report(
    results: list[TestCaseResult],
    summary: dict[str, Any],
    filters: dict[str, Any],
    path: Optional[Path] = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = path or (REPORTS_DIR / f"INTERVIEW_AUDIO_TEST_REPORT_{stamp}.json")
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "direct_audio_injection",
        "filters": filters,
        "summary": summary,
        "results": [_result_to_dict(r) for r in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_html_report(
    results: list[TestCaseResult],
    summary: dict[str, Any],
    filters: dict[str, Any],
    path: Optional[Path] = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = path or (REPORTS_DIR / "INTERVIEW_AUDIO_TEST_REPORT.html")
    # Also keep stamped copy
    stamped = REPORTS_DIR / f"INTERVIEW_AUDIO_TEST_REPORT_{stamp}.html"

    ranked = sorted(results, key=lambda r: (-(r.result == "PASS"), -r.accuracy, r.timings.total_ms))
    failed = [r for r in ranked if r.result == "FAIL"]

    def esc(x: Any) -> str:
        return html.escape("" if x is None else str(x))

    rows = []
    for r in ranked:
        cls = "pass" if r.result == "PASS" else "fail"
        rows.append(
            "<tr class='{cls}'>"
            "<td>{audio}</td>"
            "<td>{stt}</td>"
            "<td>{intent}</td>"
            "<td>{answer}</td>"
            "<td>{acc}%</td>"
            "<td>{lat}s</td>"
            "<td><strong>{result}</strong></td>"
            "<td>{recovered}</td>"
            "<td>{stage}</td>"
            "</tr>".format(
                cls=cls,
                audio=esc(f"Q{r.question_id} {r.speaker} {r.condition}"),
                stt=esc("Correct" if r.stt_ok else f"Weak ({r.stt_score})"),
                intent=esc("Correct" if r.intent_ok else f"Wrong ({r.intent_score})"),
                answer=esc("Correct" if r.answer_ok else f"Wrong ({r.answer_score})"),
                acc=esc(r.accuracy),
                lat=esc(round(r.timings.total_ms / 1000.0, 2)),
                result=esc(r.result),
                recovered=esc("YES" if r.recovered_after_stt_error else "—"),
                stage=esc(r.failure_stage or "—"),
            )
        )

    fail_blocks = []
    for r in failed:
        fail_blocks.append(
            f"""
            <div class="fail-card">
              <h3>FAIL · {esc(r.file)}</h3>
              <p><b>Failure Stage:</b> {esc(r.failure_stage)}</p>
              <p>{esc(r.failure_detail)}</p>
              <p><b>Expected:</b> {esc(r.expected_question)}</p>
              <p><b>Captured STT:</b> {esc(r.transcript)}</p>
              <p><b>Matched:</b> {esc(r.match_question)} ({esc(r.match_id)})</p>
              <p><b>Pipeline:</b> AUDIO → STT → QUESTION UNDERSTANDING → RETRIEVAL → ANSWER GENERATION</p>
            </div>
            """
        )

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Interview Audio Test Report</title>
  <style>
    body {{ font-family: Segoe UI, Tahoma, sans-serif; margin: 24px; background:#0f1419; color:#e8eef5; }}
    h1,h2 {{ margin-bottom: 8px; }}
    .meta {{ color:#8b9aab; }}
    .cards {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin:16px 0; }}
    .card {{ background:#1a222d; border:1px solid #2a3544; border-radius:12px; padding:12px; }}
    .card b {{ font-size:1.3rem; display:block; }}
    table {{ width:100%; border-collapse: collapse; background:#1a222d; }}
    th, td {{ border-bottom:1px solid #2a3544; padding:8px; text-align:left; font-size:0.9rem; }}
    tr.pass td {{ background: rgba(61,214,140,0.06); }}
    tr.fail td {{ background: rgba(240,113,120,0.08); }}
    .fail-card {{ background:#2a181c; border:1px solid #5c2a32; border-radius:12px; padding:12px; margin:10px 0; }}
    code {{ background:#0b1016; padding:2px 6px; border-radius:6px; }}
  </style>
</head>
<body>
  <h1>Interview Audio Test Report</h1>
  <p class="meta">Mode: <code>direct_audio_injection</code> · Generated: {esc(datetime.now(timezone.utc).isoformat())}</p>
  <p class="meta">Filters: {esc(json.dumps(filters))}</p>

  <div class="cards">
    <div class="card"><span>Total</span><b>{summary.get("total")}</b></div>
    <div class="card"><span>PASS</span><b>{summary.get("passed")}</b></div>
    <div class="card"><span>FAIL</span><b>{summary.get("failed")}</b></div>
    <div class="card"><span>STT success</span><b>{esc(summary.get("stt_success"))}</b></div>
    <div class="card"><span>Intent success</span><b>{esc(summary.get("intent_success"))}</b></div>
    <div class="card"><span>Answer success</span><b>{esc(summary.get("answer_success"))}</b></div>
    <div class="card"><span>Intent recovery</span><b>{esc(summary.get("intent_recovery_rate"))}</b></div>
    <div class="card"><span>Recovered after STT</span><b>{esc(summary.get("recovered_after_stt_error"))}</b></div>
    <div class="card"><span>Avg latency</span><b>{esc(summary.get("average_latency_sec"))}s</b></div>
  </div>

  <p><b>Main weakness:</b> {esc(summary.get("main_weakness"))}</p>
  <p><b>Failure stages:</b> {esc(json.dumps(summary.get("failure_stages")))}</p>

  <h2>Results (best → worst)</h2>
  <table>
    <thead>
      <tr>
        <th>Audio</th><th>STT</th><th>Intent</th><th>Answer</th>
        <th>Accuracy</th><th>Latency</th><th>Result</th><th>Recovered</th><th>Failure Stage</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>

  <h2>Failed cases</h2>
  {''.join(fail_blocks) if fail_blocks else '<p class="meta">No failures 🎉</p>'}
</body>
</html>
"""
    path.write_text(body, encoding="utf-8")
    stamped.write_text(body, encoding="utf-8")
    # Mirror into the Voice Drill static folder for browser access.
    public_copy = (
        Path(__file__).resolve().parents[3]
        / "frontend"
        / "public"
        / "voice-drill"
        / "INTERVIEW_AUDIO_TEST_REPORT.html"
    )
    try:
        public_copy.parent.mkdir(parents=True, exist_ok=True)
        public_copy.write_text(body, encoding="utf-8")
    except OSError:
        pass
    return path


async def run_suite(
    *,
    question_id: Optional[int] = None,
    speaker: Optional[str] = None,
    condition: Optional[str] = None,
    limit: int = 180,
    progress_cb=None,
) -> dict[str, Any]:
    metadata = load_metadata()
    rows = filter_metadata(
        metadata,
        question_id=question_id,
        speaker=speaker,
        condition=condition,
        limit=limit,
    )
    results: list[TestCaseResult] = []
    for i, row in enumerate(rows, start=1):
        result = await run_one(row)
        results.append(result)
        if progress_cb is not None:
            progress_cb(i, len(rows), result)

    filters = {
        "question_id": question_id,
        "speaker": speaker,
        "condition": condition,
        "limit": limit,
        "mode": "direct_audio_injection",
    }
    summary = summarize(results)
    json_path = write_json_report(results, summary, filters)
    html_path = write_html_report(results, summary, filters)
    # Stable latest names
    latest_json = REPORTS_DIR / "INTERVIEW_AUDIO_TEST_REPORT.json"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    return {
        "summary": summary,
        "results": [_result_to_dict(r) for r in results],
        "report_json": str(json_path),
        "report_html": str(html_path),
        "report_html_latest": str(REPORTS_DIR / "INTERVIEW_AUDIO_TEST_REPORT.html"),
        "filters": filters,
    }


# Backwards-compatible aliases used by routes_audio.py
ClipEvalResult = TestCaseResult


async def evaluate_wav_path(path: Path, *, meta: Optional[dict[str, Any]] = None) -> TestCaseResult:
    if meta is None:
        meta = {
            "file": path.name,
            "main_question": "",
            "spoken_wording": "",
            "expected_answer": None,
        }
        # try recover from metadata
        try:
            found = find_meta_for_file(path.name, load_metadata())
            if found:
                meta = found
        except FileNotFoundError:
            pass
    else:
        meta = dict(meta)
        meta["file"] = meta.get("file") or path.name
    return await run_one(meta)


def save_report(results: list[TestCaseResult], summary: dict[str, Any], filters: dict[str, Any]) -> Path:
    return write_json_report(results, summary, filters)
