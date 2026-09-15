"""Evaluate stress-test interview audio clips via Whisper + question bank."""

from __future__ import annotations

import json
import time
import wave
from dataclasses import asdict, dataclass
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


@dataclass
class ClipEvalResult:
    sample_id: Optional[int]
    file: str
    question_id: Optional[int]
    speaker: Optional[str]
    condition: Optional[str]
    expected_question: str
    spoken_wording: str
    transcript: str
    stt_ms: float
    match_id: Optional[str]
    match_question: Optional[str]
    match_score: float
    match_mode: Optional[str]
    question_similarity: float
    pass_match: bool
    grade: str
    answer_en: Optional[str]
    followup_en: Optional[str]
    expected_answer: Optional[str]
    notes: str


def stress_root() -> Path:
    return STRESS_ROOT


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
    return np.ascontiguousarray(audio, dtype=np.float32), (sample_rate)


def _best_question_similarity(expected: str, match: Any) -> float:
    if not expected or match is None:
        return 0.0
    candidates = [match.entry.question, *(match.entry.aliases or [])]
    scores = [fuzz.token_set_ratio(expected, c) / 100.0 for c in candidates if c]
    return max(scores) if scores else 0.0


def _grade(pass_match: bool, match_score: float, question_similarity: float) -> str:
    if pass_match and question_similarity >= 0.85 and match_score >= 0.55:
        return "A"
    if pass_match and question_similarity >= 0.70:
        return "B"
    if match_score >= 0.45 and question_similarity >= 0.55:
        return "C"
    if match_score > 0:
        return "D"
    return "F"


def _notes(pass_match: bool, transcript: str, expected: str) -> str:
    if not transcript.strip():
        return "Empty transcript — Whisper heard no usable speech."
    if pass_match:
        return "Matched the expected interview question well enough for coaching."
    if fuzz.token_set_ratio(transcript, expected) >= 70:
        return "Transcript looks close, but question-bank match missed or was weak."
    return "Hard clip or mismatch — check noise/distance and aliases."


async def evaluate_wav_path(
    path: Path,
    *,
    meta: Optional[dict[str, Any]] = None,
) -> ClipEvalResult:
    expected = (meta or {}).get("main_question") or (meta or {}).get("spoken_wording") or ""
    spoken = (meta or {}).get("spoken_wording") or expected

    audio, sample_rate = load_wav_mono(path)
    started = time.perf_counter()
    transcript = await transcribe_whisper_async(audio, sample_rate)
    stt_ms = (time.perf_counter() - started) * 1000.0

    match = question_bank.match(transcript) if transcript.strip() else None
    similarity = _best_question_similarity(expected, match) if match else 0.0
    # Also accept high similarity between transcript and expected question text.
    transcript_sim = fuzz.token_set_ratio(transcript, expected) / 100.0 if expected else 0.0
    effective_sim = max(similarity, transcript_sim * 0.95)
    pass_match = bool(match) and effective_sim >= 0.70 and float(match.score) >= 0.40
    grade = _grade(pass_match, float(match.score) if match else 0.0, effective_sim)

    try:
        file_label = str(path.resolve().relative_to(STRESS_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        file_label = path.name

    return ClipEvalResult(
        sample_id=(meta or {}).get("sample_id"),
        file=file_label,
        question_id=(meta or {}).get("question_id"),
        speaker=(meta or {}).get("requested_region_profile"),
        condition=(meta or {}).get("condition"),
        expected_question=expected,
        spoken_wording=spoken,
        transcript=transcript,
        stt_ms=round(stt_ms, 1),
        match_id=match.entry.id if match else None,
        match_question=match.entry.question if match else None,
        match_score=round(float(match.score), 3) if match else 0.0,
        match_mode=match.mode if match else None,
        question_similarity=round(effective_sim, 3),
        pass_match=pass_match,
        grade=grade,
        answer_en=match.entry.answer_en if match else None,
        followup_en=match.entry.followup_en if match else None,
        expected_answer=(meta or {}).get("expected_answer"),
        notes=_notes(pass_match, transcript, expected),
    )


def find_meta_for_file(relative_file: str, metadata: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    target = relative_file.replace("\\", "/").lstrip("/")
    if target.startswith("stress-pilot/"):
        target = target[len("stress-pilot/") :]
    for row in metadata:
        if str(row.get("file", "")).replace("\\", "/") == target:
            return row
    # Also allow bare filename match
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
    limit: int = 30,
) -> list[dict[str, Any]]:
    rows = metadata
    if question_id is not None:
        rows = [r for r in rows if int(r.get("question_id", -1)) == (question_id)]
    if speaker and speaker != "all":
        rows = [r for r in rows if str(r.get("requested_region_profile")) == speaker]
    if condition and condition != "all":
        rows = [r for r in rows if str(r.get("condition")) == condition]
    return rows[: max(1, min(limit, 180))]


def summarize(results: list[ClipEvalResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.pass_match)
    by_condition: dict[str, dict[str, int]] = {}
    by_speaker: dict[str, dict[str, int]] = {}
    by_grade: dict[str, int] = {}
    for r in results:
        by_grade[r.grade] = by_grade.get(r.grade, 0) + 1
        cond = r.condition or "unknown"
        sp = r.speaker or "unknown"
        by_condition.setdefault(cond, {"total": 0, "pass": 0})
        by_condition[cond]["total"] += 1
        by_condition[cond]["pass"] += int(r.pass_match)
        by_speaker.setdefault(sp, {"total": 0, "pass": 0})
        by_speaker[sp]["total"] += 1
        by_speaker[sp]["pass"] += int(r.pass_match)

    def rate(block: dict[str, dict[str, int]]) -> dict[str, Any]:
        out = {}
        for key, val in block.items():
            t = val["total"]
            p = val["pass"]
            out[key] = {
                "total": t,
                "pass": p,
                "pass_rate": round((p / t) if t else 0.0, 3),
            }
        return out

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round((passed / total) if total else 0.0, 3),
        "avg_stt_ms": round(sum(r.stt_ms for r in results) / total, 1) if total else 0.0,
        "avg_match_score": round(sum(r.match_score for r in results) / total, 3) if total else 0.0,
        "by_grade": by_grade,
        "by_condition": rate(by_condition),
        "by_speaker": rate(by_speaker),
    }


def save_report(results: list[ClipEvalResult], summary: dict[str, Any], filters: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"stress_audio_report_{stamp}.json"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filters": filters,
        "summary": summary,
        "results": [asdict(r) for r in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
