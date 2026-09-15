"""
E2E Windows Loopback Test Runner

Real path (no direct WAV→STT injection):
  play WAV on default speakers
  → WASAPI loopback capture
  → VAD
  → Whisper STT
  → technical repair (existing live path)
  → intent match
  → bank answer

Stage timings:
  audio_detected → speech_final → stt_final → intent_ready → answer_ready
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import threading
import time
import wave
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from rapidfuzz import fuzz

from app.audio.capture_manager import capture_manager
from app.audio.speaker_router import SpeakerRouter
from app.audio.whisper_stt import (
    active_stt_info,
    clear_decode_log,
    last_decode_info,
    pop_decode_log,
    transcribe_whisper_async,
    warm_whisper_model,
)
from app.services.question_bank import question_bank

logger = logging.getLogger(__name__)

STRESS_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "stress-pilot"
)
HOLDOUT_V2_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "stress-holdout-v2"
)
LONG_ACCENT_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "long-sentence-accent-pack"
)
V5_150_VOICE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "v5-150-voice-stress"
    / "V5_150_Voice_Stress_Test"
)
FINAL_UNSEEN_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "final-unseen-holdout"
)
FINAL_UNSEEN_ROOT_V2 = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "final-unseen-holdout-v2"
)
FINAL_UNSEEN_ROOT_V3 = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "final-unseen-holdout-v3"
)
FINAL_UNSEEN_ROOT_V4 = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "final-unseen-holdout-v4"
)
COMPOUND_DEV_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "compound-dev"
)
GENERALIZATION_DEV_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "voice-drill"
    / "generalization-dev"
)
REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"

# Hard questions from the prior stress analysis.
HARD_QUESTION_IDS = {156, 173, 178, 212, 275}


# Latency-cut: simple questions never pay a third Whisper call.
MAX_STT_PASSES_SIMPLE = 2


def _is_simple_stt_clip(meta: dict[str, Any]) -> bool:
    """True when this clip should use the simple STT budget (not labeled compound)."""
    return str(meta.get("question_type_label") or "") != "compound"


@dataclass
class StageTimings:
    audio_detected_ms: float = 0.0
    speech_final_ms: float = 0.0
    stt_ms: float = 0.0
    intent_ms: float = 0.0
    answer_ms: float = 0.0
    total_ms: float = 0.0
    vad_ms: float = 0.0  # speech_final - audio_detected
    post_speech_ms: float = 0.0  # STT + intent + answer (interview-relevant)
    # Honest stage breakdown (evaluator audit / post-speech latency audit).
    whisper_ms: float = 0.0
    match_ms: float = 0.0
    semantic_ms: float = 0.0
    compound_ms: float = 0.0
    compound_detect_ms: float = 0.0
    decomposition_ms: float = 0.0
    matching_ms: float = 0.0
    rerank_ms: float = 0.0
    merge_ms: float = 0.0
    # Latency-cut: per-pass STT + stage split (sums still in whisper_ms / semantic_ms).
    whisper_pass_1_ms: float = 0.0
    whisper_pass_2_ms: float = 0.0
    number_of_stt_passes: int = 0
    technical_repair_ms: float = 0.0
    base_match_ms: float = 0.0
    semantic_embedding_ms: float = 0.0
    semantic_search_ms: float = 0.0
    semantic_recovery_used: bool = False


@dataclass
class E2EResult:
    sample_id: Optional[int]
    file: str
    question_id: Optional[int]
    speaker: Optional[str]
    condition: Optional[str]
    expected_question: str
    transcript: str
    stt_ok: bool
    stt_score: float
    intent_ok: bool
    intent_score: float
    match_id: Optional[str]
    match_question: Optional[str]
    match_score: float
    answer_en: Optional[str]
    answer_ok: bool
    recovered_after_stt_error: bool
    result: str
    failure_stage: Optional[str]
    failure_detail: str
    high_confidence_wrong: bool
    timings: StageTimings = field(default_factory=StageTimings)
    notes: str = "e2e_loopback"
    first_word_missing: bool = False
    last_word_missing: bool = False
    speech_duration_ms: float = 0.0
    pre_roll_used: bool = True
    raw_transcript: Optional[str] = None
    processed_transcript: Optional[str] = None
    better_audio_source: Optional[str] = None
    onset: dict[str, Any] = field(default_factory=dict)
    audio_levels: dict[str, float] = field(default_factory=dict)
    fail_bucket: Optional[str] = None
    failure_position: Optional[str] = None
    # Compound / multi-intent observability (optional; single-intent path leaves defaults).
    question_type: Optional[str] = None
    compound_detected: bool = False
    compound_confidence: float = 0.0
    requested_parts_count: int = 0
    matched_parts_count: int = 0
    unsupported_parts_count: int = 0
    intent_coverage_rate: float = 0.0
    full_compound_success: bool = False
    partial_compound_success: bool = False
    answer_order_correct: bool = True
    compound_sub_questions: list[str] = field(default_factory=list)
    compound_selected_intents: list[str] = field(default_factory=list)
    compound_trace: dict[str, Any] = field(default_factory=dict)
    semantic_recovery: dict[str, Any] = field(default_factory=dict)
    segment_count: int = 1
    truncated_by_max: bool = False
    merged_transcript: bool = False
    # Final Unseen Holdout labeling (optional).
    question_type_label: Optional[str] = None
    expected_intent_ids: list[str] = field(default_factory=list)
    accent_label: Optional[str] = None
    holdout_gold_hit: Optional[bool] = None
    match_mode: Optional[str] = None
    gold_id_mismatch: bool = False
    gold_part_coverage: float = 0.0
    detected_parts_count: int = 0
    answered_parts_count: int = 0
    missed_parts: list[str] = field(default_factory=list)
    duplicate_parts: list[str] = field(default_factory=list)
    compound_failure_code: Optional[str] = None
    final_coverage: float = 0.0
    post_speech_trace: dict[str, Any] = field(default_factory=dict)


def load_metadata() -> list[dict[str, Any]]:
    path = STRESS_ROOT / "metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))


def select_stress_clips(metadata: list[dict[str, Any]], limit: int = 54) -> list[dict[str, Any]]:
    """Hard-question stress set (previous E2E focus)."""
    hard = [r for r in metadata if int(r.get("question_id", -1)) in HARD_QUESTION_IDS]
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: dict[str, Any]) -> None:
        key = str(row.get("file"))
        if key in seen:
            return
        seen.add(key)
        selected.append(row)

    for qid in sorted(HARD_QUESTION_IDS):
        for cond in ("clean", "office_noise", "fast", "poor_call", "far"):
            for row in hard:
                if int(row["question_id"]) == qid and row.get("requested_region_profile") == "jordanian" and row.get("condition") == cond:
                    add(row)
                    break
        for sp in ("indian", "kuwaiti"):
            for cond in ("clean", "far", "combined"):
                for row in hard:
                    if int(row["question_id"]) == qid and row.get("requested_region_profile") == sp and row.get("condition") == cond:
                        add(row)
                        break
        for row in hard:
            if int(row["question_id"]) == qid and row.get("requested_region_profile") == "jordanian" and row.get("condition") == "combined":
                add(row)
                break

    if len(selected) < limit:
        for row in hard:
            if row.get("condition") == "office_noise" and row.get("requested_region_profile") in {"indian", "kuwaiti"}:
                add(row)
            if len(selected) >= limit:
                break
    return selected[:limit]


def select_realistic_clips(metadata: list[dict[str, Any]], limit: int = 100) -> list[dict[str, Any]]:
    """
    Representative interview mix (~100) from the 180 stress-pilot pool:
      ~60 normal/medium (clean/office/fast/poor — prefer non-hard)
      ~20 short technical (hard Qs on clean/office)
      ~20 difficult (far/combined/poor)
    """
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: dict[str, Any]) -> bool:
        key = str(row.get("file"))
        if key in seen:
            return False
        seen.add(key)
        selected.append(row)
        return True

    def is_hard(row: dict[str, Any]) -> bool:
        return int(row.get("question_id", -1)) in HARD_QUESTION_IDS

    normal_conds = {"clean", "office_noise", "fast", "poor_call"}
    easy = [r for r in metadata if r.get("condition") in normal_conds]
    easy_nonhard = sorted(
        [r for r in easy if not is_hard(r)],
        key=lambda r: (
            0 if r.get("condition") in {"clean", "office_noise"} else 1,
            str(r.get("file")),
        ),
    )
    easy_hard_clean = [r for r in easy if is_hard(r) and r.get("condition") == "clean"]
    easy_hard_rest = [r for r in easy if is_hard(r) and r.get("condition") != "clean"]

    # ~60 normal/medium
    for bucket in (easy_nonhard, easy_hard_clean, easy_hard_rest):
        for row in bucket:
            if len(selected) >= 60:
                break
            add(row)
        if len(selected) >= 60:
            break

    # ~20 short technical
    short_n = 0
    for row in metadata:
        if short_n >= 20:
            break
        if is_hard(row) and row.get("condition") in {"clean", "office_noise"}:
            if add(row):
                short_n += 1

    # ~20 difficult — prefer far, then combined, then poor_call
    hard_n = 0
    difficult = sorted(
        [r for r in metadata if r.get("condition") in {"far", "combined", "poor_call"}],
        key=lambda r: (
            {"far": 0, "combined": 1, "poor_call": 2}.get(str(r.get("condition")), 9),
            0 if is_hard(r) else 1,
            str(r.get("file")),
        ),
    )
    for row in difficult:
        if hard_n >= 20:
            break
        if add(row):
            hard_n += 1

    # Fill remainder toward limit with leftover clean/office
    if len(selected) < limit:
        for row in metadata:
            if len(selected) >= limit:
                break
            if row.get("condition") in {"clean", "office_noise"}:
                add(row)

    return selected[:limit]


def select_realistic_holdout_clips(
    metadata: list[dict[str, Any]], limit: int = 80
) -> list[dict[str, Any]]:
    """
    Disjoint holdout from the primary Realistic 100.
    Never overlaps the development/regression set — final readiness gate only.
    """
    primary_files = {str(r.get("file")) for r in select_realistic_clips(metadata, limit=100)}
    rows = [r for r in metadata if str(r.get("file")) not in primary_files]
    # Prefer balanced coverage: combined/far/poor first (harder), then fast, then clean/office.
    order = {"combined": 0, "far": 1, "poor_call": 2, "fast": 3, "office_noise": 4, "clean": 5}
    rows.sort(
        key=lambda r: (
            order.get(str(r.get("condition")), 9),
            int(r.get("question_id") or 0),
            str(r.get("requested_region_profile") or ""),
            str(r.get("file") or ""),
        )
    )
    return rows[:limit]


# Map external holdout-v2 pack categories → interview readiness conditions.
# combined is intentionally excluded from readiness.
_HOLDOUT_V2_CATEGORY_MAP: dict[str, str] = {
    "far": "far",
    "noise": "office_noise",
    "fast": "fast",
    "interrupted": "poor_call",
    "slow": "clean",
    "short": "clean",
    "medium": "clean",
    "long": "clean",
    "very_long": "clean",
}


def load_holdout_v2_pack() -> list[dict[str, Any]]:
    """Load never-seen pack from interview_audio_stress_test_pilot.zip extract."""
    manifest_path = HOLDOUT_V2_ROOT / "manifest.json"
    if not manifest_path.is_file():
        return []
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for i, item in enumerate(raw, start=1):
        cat = str(item.get("category") or "").strip().lower()
        condition = _HOLDOUT_V2_CATEGORY_MAP.get(cat)
        if not condition:
            continue
        transcript = str(item.get("transcript") or "").strip()
        rows.append(
            {
                "sample_id": 10_000 + i,
                "question_id": None,
                "main_question": transcript,
                "spoken_wording": transcript,
                "speaker_profile": "holdout_v2_synthetic",
                "requested_region_profile": "holdout_v2",
                "condition": condition,
                "file": str(item.get("file") or ""),
                "audio_root": str(HOLDOUT_V2_ROOT),
                "pack": "stress-holdout-v2",
                "source_category": cat,
            }
        )
    return rows


def select_realistic_holdout_v2(
    metadata: list[dict[str, Any]],
    *,
    per_condition: int = 20,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Balanced unseen readiness set: clean / office / fast / poor / far.
    Sources: unused stress-pilot (non-combined) + holdout-v2 zip pack.
    Combined is excluded from Overall Readiness.
    """
    primary_files = {str(r.get("file")) for r in select_realistic_clips(metadata, limit=100)}
    readiness_conds = ("clean", "office_noise", "fast", "poor_call", "far")

    unused_pilot: list[dict[str, Any]] = []
    for r in metadata:
        if str(r.get("file")) in primary_files:
            continue
        if str(r.get("condition")) not in readiness_conds:
            continue
        row = dict(r)
        row.setdefault("audio_root", str(STRESS_ROOT))
        row["pack"] = "stress-pilot-unused"
        unused_pilot.append(row)

    pack_rows = load_holdout_v2_pack()
    pool = unused_pilot + pack_rows

    by_cond: dict[str, list[dict[str, Any]]] = {c: [] for c in readiness_conds}
    for r in pool:
        c = str(r.get("condition"))
        if c in by_cond:
            by_cond[c].append(r)

    for c in readiness_conds:
        by_cond[c].sort(
            key=lambda r: (
                0 if r.get("pack") == "stress-pilot-unused" else 1,
                str(r.get("source_category") or ""),
                int(r.get("question_id") or 0) if r.get("question_id") is not None else 10**9,
                str(r.get("file") or ""),
            )
        )

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in readiness_conds:
        n = 0
        for row in by_cond[c]:
            if n >= per_condition:
                break
            key = f"{row.get('audio_root')}|{row.get('file')}"
            if key in seen:
                continue
            seen.add(key)
            selected.append(row)
            n += 1

    # If under target total, fill remaining slots from leftover clean/fast/poor/far
    # (still never combined), preserving deterministic order.
    target_total = limit if limit is not None else per_condition * len(readiness_conds)
    if len(selected) < target_total:
        leftovers: list[dict[str, Any]] = []
        for c in readiness_conds:
            for row in by_cond[c]:
                key = f"{row.get('audio_root')}|{row.get('file')}"
                if key not in seen:
                    leftovers.append(row)
        leftovers.sort(
            key=lambda r: (
                readiness_conds.index(str(r.get("condition"))),
                str(r.get("file") or ""),
            )
        )
        for row in leftovers:
            if len(selected) >= target_total:
                break
            key = f"{row.get('audio_root')}|{row.get('file')}"
            if key in seen:
                continue
            seen.add(key)
            selected.append(row)

    return selected[:target_total]


def select_extreme_combined_clips(
    metadata: list[dict[str, Any]], limit: int = 30
) -> list[dict[str, Any]]:
    """Combined-only extreme stress — NOT part of Overall Readiness Score."""
    rows = [
        {**r, "audio_root": r.get("audio_root") or str(STRESS_ROOT), "pack": "extreme-combined"}
        for r in metadata
        if str(r.get("condition")) == "combined"
    ]
    rows.sort(
        key=lambda r: (
            int(r.get("question_id") or 0),
            str(r.get("requested_region_profile") or ""),
            str(r.get("file") or ""),
        )
    )
    return rows[:limit]


def select_long_sentence_accent_clips(limit: int = 40) -> list[dict[str, Any]]:
    """
    Long-sentence accent pack only (length factor, clean condition).
    Profiles: indian / jordanian / egyptian / emirati synthetic — 10 each.
    """
    manifest_path = LONG_ACCENT_ROOT / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Long accent pack missing: {manifest_path}")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    accent_order = {
        "indian_synthetic": 0,
        "jordanian_synthetic": 1,
        "egyptian_synthetic": 2,
        "emirati_synthetic": 3,
    }
    rows: list[dict[str, Any]] = []
    for i, item in enumerate(raw, start=1):
        profile = str(item.get("profile") or "").strip()
        accent = profile.replace("_synthetic", "") if profile.endswith("_synthetic") else profile
        transcript = str(item.get("transcript") or "").strip()
        rows.append(
            {
                "sample_id": 20_000 + i,
                "question_id": None,
                "main_question": transcript,
                "spoken_wording": transcript,
                "speaker_profile": profile,
                "requested_region_profile": accent,
                "condition": "long",
                "file": str(item.get("file") or ""),
                "audio_root": str(LONG_ACCENT_ROOT),
                "pack": "long-sentence-accent",
                "declared_duration_sec": float(item.get("duration_sec") or 0.0),
            }
        )
    rows.sort(
        key=lambda r: (
            accent_order.get(str(r.get("speaker_profile")), 9),
            str(r.get("file") or ""),
        )
    )
    return rows[:limit]


def select_v5_150_voice_clips(limit: Optional[int] = None) -> list[dict[str, Any]]:
    """
    V5 150 Voice Stress pack — REAL loopback path only.
    WAV → speakers → WASAPI loopback → VAD → STT → intent → answer.
    """
    manifest_path = V5_150_VOICE_ROOT / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"V5 150 voice pack missing: {manifest_path}")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in raw:
        rel = str(item.get("file") or "").replace("\\", "/")
        wav = V5_150_VOICE_ROOT / rel
        if not wav.is_file():
            missing.append(rel)
            continue
        expected = str(
            item.get("expected_question") or item.get("tts_input_text") or ""
        ).strip()
        accent = str(item.get("accent_target") or "").strip().lower()
        speed = str(item.get("speed") or "").strip().lower()
        distance = str(item.get("distance") or "").strip().lower()
        noise = str(item.get("noise") or "").strip().lower()
        style = str(item.get("question_style") or "").strip().lower()
        condition = f"{speed}|{distance}|{noise}|{style}"
        rows.append(
            {
                "sample_id": item.get("sample_id"),
                "question_id": item.get("intent_id"),
                "main_question": expected,
                "spoken_wording": expected,
                "intent_key": item.get("intent_key"),
                "question_style": style,
                "requested_region_profile": accent,
                "condition": condition,
                "speed": speed,
                "distance": distance,
                "noise": noise,
                "file": rel,
                "audio_root": str(V5_150_VOICE_ROOT),
                "pack": "v5-150-voice-stress",
                "declared_duration_sec": float(item.get("duration_sec") or 0.0),
                "accent_note": item.get("accent_note"),
            }
        )
    if missing:
        raise FileNotFoundError(
            f"V5 150 pack incomplete: {len(missing)} WAVs missing. "
            f"Example: {missing[0]}"
        )
    if limit is not None:
        return rows[: max(0, limit)]
    return rows


def select_final_unseen_holdout_clips(
    *,
    include_warmup: bool = True,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Final Unseen Holdout — EVAL ONLY. Requires synthesized WAVs under pack/audio/.
    Raises if scored audio is incomplete so we never silently score a partial pack.
    """
    scripts_path = FINAL_UNSEEN_ROOT / "scripts.json"
    if not scripts_path.is_file():
        raise FileNotFoundError(
            f"Final Unseen Holdout scripts missing: {scripts_path}. "
            "Run scripts/build_final_unseen_holdout_scripts.py first."
        )
    raw = json.loads(scripts_path.read_text(encoding="utf-8"))
    warm = [r for r in raw if r.get("warmup")]
    scored = [r for r in raw if not r.get("warmup")]
    if limit is not None:
        scored = scored[: max(0, (limit))]

    def _to_clip(item: dict[str, Any]) -> dict[str, Any]:
        rel = str(item.get("file") or "")
        wav = FINAL_UNSEEN_ROOT / rel
        return {
            "sample_id": item.get("id"),
            "question_id": item.get("id"),
            "main_question": item.get("transcript"),
            "spoken_wording": item.get("transcript"),
            "expected_intent_ids": list(item.get("expected_intent_ids") or []),
            "question_type_label": item.get("question_type"),
            "context_prior": item.get("context_prior"),
            "speaker_profile": f"{item.get('accent')}_synthetic",
            "requested_region_profile": item.get("accent"),
            "condition": item.get("condition"),
            "file": rel,
            "audio_root": str(FINAL_UNSEEN_ROOT),
            "pack": "final-unseen-holdout",
            "warmup": bool(item.get("warmup")),
            "eval_only": True,
            "wav_path": str(wav),
        }

    missing = [str(FINAL_UNSEEN_ROOT / r["file"]) for r in scored if not (FINAL_UNSEEN_ROOT / r["file"]).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Final Unseen Holdout audio incomplete ({len(missing)}/{len(scored)} missing). "
            f"Example: {missing[0]}. Synthesize WAVs before running --suite final_unseen_holdout."
        )

    out: list[dict[str, Any]] = []
    if include_warmup:
        out.extend(_to_clip(r) for r in warm)
    out.extend(_to_clip(r) for r in scored)
    return out


def select_final_unseen_holdout_v2_clips(
    *,
    include_warmup: bool = True,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Final Unseen Holdout v2 — EVAL ONLY (replaces voided v1).
    Requires synthesized WAVs under pack/audio/.
    """
    scripts_path = FINAL_UNSEEN_ROOT_V2 / "scripts.json"
    if not scripts_path.is_file():
        raise FileNotFoundError(
            f"Final Unseen Holdout v2 scripts missing: {scripts_path}. "
            "Run scripts/build_final_unseen_holdout_v2_scripts.py first."
        )
    raw = json.loads(scripts_path.read_text(encoding="utf-8"))
    warm = [r for r in raw if r.get("warmup")]
    scored = [r for r in raw if not r.get("warmup")]
    if limit is not None:
        scored = scored[: max(0, (limit))]

    def _to_clip(item: dict[str, Any]) -> dict[str, Any]:
        rel = str(item.get("file") or "")
        wav = FINAL_UNSEEN_ROOT_V2 / rel
        return {
            "sample_id": item.get("id"),
            "question_id": item.get("id"),
            "main_question": item.get("transcript"),
            "spoken_wording": item.get("transcript"),
            "expected_intent_ids": list(item.get("expected_intent_ids") or []),
            "question_type_label": item.get("question_type"),
            "context_prior": item.get("context_prior"),
            "speaker_profile": f"{item.get('accent')}_synthetic",
            "requested_region_profile": item.get("accent"),
            "condition": item.get("condition"),
            "file": rel,
            "audio_root": str(FINAL_UNSEEN_ROOT_V2),
            "pack": "final-unseen-holdout-v2",
            "warmup": bool(item.get("warmup")),
            "eval_only": True,
            "wav_path": str(wav),
        }

    missing = [
        str(FINAL_UNSEEN_ROOT_V2 / r["file"])
        for r in scored
        if not (FINAL_UNSEEN_ROOT_V2 / r["file"]).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"Final Unseen Holdout v2 audio incomplete ({len(missing)}/{len(scored)} missing). "
            f"Example: {missing[0]}. Synthesize WAVs before running --suite final_unseen_holdout_v2."
        )

    out: list[dict[str, Any]] = []
    if include_warmup:
        out.extend(_to_clip(r) for r in warm)
    out.extend(_to_clip(r) for r in scored)
    return out


def _load_final_unseen_gold(root: Path) -> dict[str, list[str]]:
    gold_path = root / "gold.json"
    if not gold_path.is_file():
        raise FileNotFoundError(
            f"Final Unseen Holdout gold missing: {gold_path}. "
            "Run the pack build script first."
        )
    payload = json.loads(gold_path.read_text(encoding="utf-8"))
    raw = payload.get("expected_intent_ids") or {}
    return {str(k): list(v or []) for k, v in raw.items()}


def select_final_unseen_holdout_v3_clips(
    *,
    include_warmup: bool = True,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Final Unseen Holdout v3 — EVAL ONLY.
    Gold is loaded from gold.json (scripts.json has no expected ids).
    """
    scripts_path = FINAL_UNSEEN_ROOT_V3 / "scripts.json"
    if not scripts_path.is_file():
        raise FileNotFoundError(
            f"Final Unseen Holdout v3 scripts missing: {scripts_path}. "
            "Run scripts/build_final_unseen_holdout_v3_scripts.py first."
        )
    gold_by_id = _load_final_unseen_gold(FINAL_UNSEEN_ROOT_V3)
    raw = json.loads(scripts_path.read_text(encoding="utf-8"))
    warm = [r for r in raw if r.get("warmup")]
    scored = [r for r in raw if not r.get("warmup")]
    if limit is not None:
        scored = scored[: max(0, (limit))]

    def _to_clip(item: dict[str, Any]) -> dict[str, Any]:
        clip_id = str(item.get("id") or "")
        rel = str(item.get("file") or "")
        wav = FINAL_UNSEEN_ROOT_V3 / rel
        return {
            "sample_id": clip_id,
            "question_id": clip_id,
            "main_question": item.get("transcript"),
            "spoken_wording": item.get("transcript"),
            "expected_intent_ids": list(gold_by_id.get(clip_id) or []),
            "question_type_label": item.get("question_type"),
            "context_prior": item.get("context_prior"),
            "speaker_profile": f"{item.get('accent')}_synthetic",
            "requested_region_profile": item.get("accent"),
            "condition": item.get("condition"),
            "file": rel,
            "audio_root": str(FINAL_UNSEEN_ROOT_V3),
            "pack": "final-unseen-holdout-v3",
            "warmup": bool(item.get("warmup")),
            "eval_only": True,
            "wav_path": str(wav),
        }

    missing = [
        str(FINAL_UNSEEN_ROOT_V3 / r["file"])
        for r in scored
        if not (FINAL_UNSEEN_ROOT_V3 / r["file"]).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"Final Unseen Holdout v3 audio incomplete ({len(missing)}/{len(scored)} missing). "
            f"Example: {missing[0]}. Synthesize WAVs before running --suite final_unseen_holdout_v3."
        )

    out: list[dict[str, Any]] = []
    if include_warmup:
        out.extend(_to_clip(r) for r in warm)
    out.extend(_to_clip(r) for r in scored)
    return out


def select_final_unseen_holdout_v4_clips(
    *,
    include_warmup: bool = True,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Final Unseen Holdout v4 — EVAL ONLY.
    Gold is loaded from gold.json (scripts.json has no expected ids).
    """
    scripts_path = FINAL_UNSEEN_ROOT_V4 / "scripts.json"
    if not scripts_path.is_file():
        raise FileNotFoundError(
            f"Final Unseen Holdout v4 scripts missing: {scripts_path}. "
            "Run scripts/build_final_unseen_holdout_v4_scripts.py first."
        )
    gold_by_id = _load_final_unseen_gold(FINAL_UNSEEN_ROOT_V4)
    raw = json.loads(scripts_path.read_text(encoding="utf-8"))
    warm = [r for r in raw if r.get("warmup")]
    scored = [r for r in raw if not r.get("warmup")]
    if limit is not None:
        scored = scored[: max(0, (limit))]

    def _to_clip(item: dict[str, Any]) -> dict[str, Any]:
        clip_id = str(item.get("id") or "")
        rel = str(item.get("file") or "")
        wav = FINAL_UNSEEN_ROOT_V4 / rel
        return {
            "sample_id": clip_id,
            "question_id": clip_id,
            "main_question": item.get("transcript"),
            "spoken_wording": item.get("transcript"),
            "expected_intent_ids": list(gold_by_id.get(clip_id) or []),
            "question_type_label": item.get("question_type"),
            "context_prior": item.get("context_prior"),
            "speaker_profile": f"{item.get('accent')}_synthetic",
            "requested_region_profile": item.get("accent"),
            "condition": item.get("condition"),
            "file": rel,
            "audio_root": str(FINAL_UNSEEN_ROOT_V4),
            "pack": "final-unseen-holdout-v4",
            "warmup": bool(item.get("warmup")),
            "eval_only": True,
            "wav_path": str(wav),
        }

    missing = [
        str(FINAL_UNSEEN_ROOT_V4 / r["file"])
        for r in scored
        if not (FINAL_UNSEEN_ROOT_V4 / r["file"]).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"Final Unseen Holdout v4 audio incomplete ({len(missing)}/{len(scored)} missing). "
            f"Example: {missing[0]}. Synthesize WAVs before running --suite final_unseen_holdout_v4."
        )

    out: list[dict[str, Any]] = []
    if include_warmup:
        out.extend(_to_clip(r) for r in warm)
    out.extend(_to_clip(r) for r in scored)
    return out


def select_compound_dev_clips(
    *,
    include_warmup: bool = True,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Track B compound-dev pack — not Final Holdout."""
    scripts_path = COMPOUND_DEV_ROOT / "scripts.json"
    if not scripts_path.is_file():
        raise FileNotFoundError(
            f"compound-dev scripts missing: {scripts_path}. "
            "Run scripts/build_compound_dev_scripts.py first."
        )
    raw = json.loads(scripts_path.read_text(encoding="utf-8"))
    warm = [r for r in raw if r.get("warmup")]
    scored = [r for r in raw if not r.get("warmup")]
    if limit is not None:
        scored = scored[: max(0, (limit))]

    def _to_clip(item: dict[str, Any]) -> dict[str, Any]:
        rel = str(item.get("file") or "")
        wav = COMPOUND_DEV_ROOT / rel
        return {
            "sample_id": item.get("id"),
            "question_id": item.get("id"),
            "main_question": item.get("transcript"),
            "spoken_wording": item.get("transcript"),
            "expected_intent_ids": list(item.get("expected_intent_ids") or []),
            "question_type_label": item.get("question_type") or "compound",
            "requested_parts": list(item.get("requested_parts") or []),
            "speaker_profile": f"{item.get('accent')}_synthetic",
            "requested_region_profile": item.get("accent"),
            "condition": item.get("condition"),
            "file": rel,
            "audio_root": str(COMPOUND_DEV_ROOT),
            "pack": "compound-dev",
            "warmup": bool(item.get("warmup")),
            "eval_only": True,
            "wav_path": str(wav),
        }

    missing = [
        str(COMPOUND_DEV_ROOT / r["file"])
        for r in scored
        if not (COMPOUND_DEV_ROOT / r["file"]).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"compound-dev audio incomplete ({len(missing)}/{len(scored)} missing). "
            f"Example: {missing[0]}. Run scripts/synthesize_compound_dev.py"
        )

    out: list[dict[str, Any]] = []
    if include_warmup:
        out.extend(_to_clip(r) for r in warm)
    out.extend(_to_clip(r) for r in scored)
    return out


def select_generalization_dev_clips(
    *,
    include_warmup: bool = True,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Track C generalization-dev pack — not Final Holdout, not compound-dev."""
    scripts_path = GENERALIZATION_DEV_ROOT / "scripts.json"
    if not scripts_path.is_file():
        raise FileNotFoundError(
            f"generalization-dev scripts missing: {scripts_path}. "
            "Run scripts/build_generalization_dev_scripts.py first."
        )
    raw = json.loads(scripts_path.read_text(encoding="utf-8"))
    warm = [r for r in raw if r.get("warmup")]
    scored = [r for r in raw if not r.get("warmup")]
    if limit is not None:
        scored = scored[: max(0, (limit))]

    def _to_clip(item: dict[str, Any]) -> dict[str, Any]:
        rel = str(item.get("file") or "")
        wav = GENERALIZATION_DEV_ROOT / rel
        return {
            "sample_id": item.get("id"),
            "question_id": item.get("id"),
            "main_question": item.get("transcript"),
            "spoken_wording": item.get("transcript"),
            "expected_intent_ids": list(item.get("expected_intent_ids") or []),
            "question_type_label": item.get("question_type"),
            "context_prior": item.get("context_prior"),
            "speaker_profile": f"{item.get('accent')}_synthetic",
            "requested_region_profile": item.get("accent"),
            "condition": item.get("condition"),
            "file": rel,
            "audio_root": str(GENERALIZATION_DEV_ROOT),
            "pack": "generalization-dev",
            "warmup": bool(item.get("warmup")),
            "eval_only": True,
            "wav_path": str(wav),
        }

    missing = [
        str(GENERALIZATION_DEV_ROOT / r["file"])
        for r in scored
        if not (GENERALIZATION_DEV_ROOT / r["file"]).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"generalization-dev audio incomplete ({len(missing)}/{len(scored)} missing). "
            f"Example: {missing[0]}. Run scripts/synthesize_generalization_dev.py"
        )

    out: list[dict[str, Any]] = []
    if include_warmup:
        out.extend(_to_clip(r) for r in warm)
    out.extend(_to_clip(r) for r in scored)
    return out


def select_length_category_clips(category: str, limit: Optional[int] = None) -> list[dict[str, Any]]:
    """
    Length-factor clips from stress-holdout-v2:
      short | medium | very_long  (also accepts long)
    Clean condition; used for post-compound regression.
    """
    cat = (category or "").strip().lower()
    if cat not in {"short", "medium", "long", "very_long"}:
        raise ValueError(f"Unknown length category: {category}")
    pack = load_holdout_v2_pack()
    rows = [
        {
            **r,
            "condition": cat,
            "requested_region_profile": cat,
            "speaker_profile": f"holdout_v2_{cat}",
        }
        for r in pack
        if str(r.get("source_category") or "").lower() == cat
    ]
    rows.sort(key=lambda r: str(r.get("file") or ""))
    if limit is None:
        return rows
    return rows[:limit]


def select_clean_clips(metadata: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    """All clean-condition clips (or up to limit) for Clean E2E gate."""
    rows = [r for r in metadata if str(r.get("condition")) == "clean"]
    rows.sort(
        key=lambda r: (
            int(r.get("question_id") or 0),
            str(r.get("requested_region_profile") or ""),
            str(r.get("file") or ""),
        )
    )
    return rows[:limit]


def select_office_poor_clips(metadata: list[dict[str, Any]], limit: int = 60) -> list[dict[str, Any]]:
    """
    Medium-noise gate: office_noise + poor_call only.
    Same frozen Clean audio config — no VAD/pre-roll/matcher changes.
    """
    rows = [
        r for r in metadata
        if str(r.get("condition")) in {"office_noise", "poor_call"}
    ]
    rows.sort(
        key=lambda r: (
            0 if r.get("condition") == "office_noise" else 1,
            int(r.get("question_id") or 0),
            str(r.get("requested_region_profile") or ""),
            str(r.get("file") or ""),
        )
    )
    return rows[:limit]


def select_poor_clips(metadata: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    """Poor Call only — recovery gate. Clean/Office stay frozen."""
    rows = [r for r in metadata if str(r.get("condition")) == "poor_call"]
    rows.sort(
        key=lambda r: (
            int(r.get("question_id") or 0),
            str(r.get("requested_region_profile") or ""),
            str(r.get("file") or ""),
        )
    )
    return rows[:limit]


def select_far_clips(metadata: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    """
    Far-only diagnostic / gate suite.
    Independent of Clean/Office/Poor freezes — no matcher/alias/Whisper changes.
    """
    rows = [r for r in metadata if str(r.get("condition")) == "far"]
    rows.sort(
        key=lambda r: (
            int(r.get("question_id") or 0),
            str(r.get("requested_region_profile") or ""),
            str(r.get("file") or ""),
        )
    )
    return rows[:limit]


def classify_far_acoustic_causes(result: "E2EResult") -> list[str]:
    """
    Hypothesis tags for Far failures (diagnostic only).
    Uses existing level/onset/fail_bucket fields — does not change the pipeline.
    """
    if result.intent_ok:
        return []
    levels = result.audio_levels or {}
    rms = float(levels.get("rms_before") or 0.0)
    bw = float(levels.get("bandwidth_hz_est") or 0.0)
    hf = float(levels.get("high_freq_energy_ratio") or 1.0)
    snr = float(levels.get("snr_db_est") or 99.0)
    causes: list[str] = []
    if rms < 0.02:
        causes.append("low_rms")
    if (bw > 0 and bw < 2500.0) or hf < 0.03:
        causes.append("narrowband")
    if result.first_word_missing or bool((result.onset or {}).get("first_word_at_risk")):
        causes.append("onset")
    # Distance/reverb proxy: usable level + not narrowband, but STT meaning gone.
    if (
        result.fail_bucket == "stt_wrong_meaning_lost"
        and rms >= 0.02
        and not ((bw > 0 and bw < 2500.0) or hf < 0.03)
    ):
        causes.append("reverb_or_distance")
    if result.fail_bucket == "stt_wrong_intent_recoverable":
        causes.append("stt_recoverable")
    if result.fail_bucket == "intent_only":
        causes.append("intent_only")
    if result.fail_bucket == "stt_wrong_meaning_lost":
        causes.append("meaning_lost")
    if snr < 6.0 and rms >= 0.02:
        causes.append("low_snr")
    return causes or ["unknown"]


# Back-compat name
select_e2e_clips = select_stress_clips


def _play_wav_blocking(path: Path) -> None:
    """Play WAV on the default Windows output device (heard by WASAPI loopback)."""
    import winsound

    winsound.PlaySound(str(path), winsound.SND_FILENAME)


def _semantic(a: str, b: str) -> float:
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(a, b) / 100.0


class LoopbackE2ESession:
    """One long-lived capture session reused across clips."""

    def __init__(
        self,
        *,
        pre_roll_ms: Optional[int] = None,
        post_roll_ms: Optional[int] = None,
        enable_realistic_recovery: bool = False,
    ) -> None:
        self._router = SpeakerRouter(pre_roll_ms=pre_roll_ms, post_roll_ms=post_roll_ms)
        self._utterance_event = asyncio.Event()
        self._utterance_audio: Optional[np.ndarray] = None
        self._t_audio_detected: Optional[float] = None
        self._t_speech_final: Optional[float] = None
        self._t0: float = 0.0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._started = False
        # Only for realistic / holdout suites — never on Clean/Office/Poor/Far gates.
        self._enable_realistic_recovery = (enable_realistic_recovery)

    async def start(self) -> None:
        if self._started:
            return
        self._loop = asyncio.get_running_loop()
        self._router.initialize(enable_candidate=False)

        def on_event(event, speaker):  # noqa: ANN001
            from app.audio.speaker_router import SpeakerEvent

            if event == SpeakerEvent.INTERVIEWER_STARTED and self._t_audio_detected is None:
                self._t_audio_detected = time.perf_counter()

        def on_utterance(audio: np.ndarray, duration_ms: float) -> None:
            self._utterance_audio = np.asarray(audio, dtype=np.float32)
            self._t_speech_final = time.perf_counter()
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._utterance_event.set)

        self._router.set_callbacks(
            on_speaker_event=on_event,
            on_interviewer_utterance=on_utterance,
            on_candidate_utterance=None,
        )

        def on_loopback(chunk: np.ndarray) -> None:
            result = self._router.process_interviewer_audio(chunk)
            # Detect start from VAD state as backup.
            from app.audio.vad_engine import SpeechState

            if result.state == SpeechState.SPEECH_DETECTED and self._t_audio_detected is None:
                self._t_audio_detected = time.perf_counter()

        capture_manager.configure(mic_device_index=None, loopback_device_index=None)
        await capture_manager.start_capture(
            on_mic_audio=None,
            on_loopback_audio=on_loopback,
            owner_id="e2e-loopback-runner",
        )
        self._started = True
        logger.info(
            "E2E loopback started (loopback=%s output=%s)",
            capture_manager.active_loopback_name,
            capture_manager.active_output_name,
        )

    async def stop(self) -> None:
        if not self._started:
            return
        await capture_manager.stop_capture(owner_id="e2e-loopback-runner")
        self._started = False

    def _reset_turn(self) -> None:
        self._utterance_event.clear()
        self._utterance_audio = None
        self._t_audio_detected = None
        self._t_speech_final = None
        self._router.reset()
        self._router.mark_capture_start()

    async def run_clip(self, meta: dict[str, Any], *, timeout_s: float = 25.0) -> E2EResult:
        root = Path(str(meta["audio_root"])) if meta.get("audio_root") else STRESS_ROOT
        path = root / str(meta["file"])
        expected = str(meta.get("main_question") or meta.get("spoken_wording") or "")
        spoken = str(meta.get("spoken_wording") or expected)

        # Settle after previous clip.
        await asyncio.sleep(0.35)
        self._reset_turn()
        self._t0 = time.perf_counter()

        play_err: list[str] = []

        def _play() -> None:
            try:
                _play_wav_blocking(path)
            except Exception as exc:  # pragma: no cover
                play_err.append(str(exc))

        player = threading.Thread(target=_play, daemon=True)
        player.start()

        try:
            await asyncio.wait_for(self._utterance_event.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            player.join(timeout=2)
            return E2EResult(
                sample_id=meta.get("sample_id"),
                file=str(meta.get("file")),
                question_id=meta.get("question_id"),
                speaker=meta.get("requested_region_profile"),
                condition=meta.get("condition"),
                expected_question=expected,
                transcript="",
                stt_ok=False,
                stt_score=0.0,
                intent_ok=False,
                intent_score=0.0,
                match_id=None,
                match_question=None,
                match_score=0.0,
                answer_en=None,
                answer_ok=False,
                recovered_after_stt_error=False,
                result="FAIL",
                failure_stage="AUDIO",
                failure_detail="Timeout waiting for loopback VAD utterance. Check speakers/loopback device.",
                high_confidence_wrong=False,
                timings=StageTimings(total_ms=round((time.perf_counter() - self._t0) * 1000, 1)),
                notes="; ".join(play_err) or "e2e_loopback_timeout",
            )

        player.join(timeout=5)
        audio = self._utterance_audio
        if audio is None or len(audio) == 0:
            return E2EResult(
                sample_id=meta.get("sample_id"),
                file=str(meta.get("file")),
                question_id=meta.get("question_id"),
                speaker=meta.get("requested_region_profile"),
                condition=meta.get("condition"),
                expected_question=expected,
                transcript="",
                stt_ok=False,
                stt_score=0.0,
                intent_ok=False,
                intent_score=0.0,
                match_id=None,
                match_question=None,
                match_score=0.0,
                answer_en=None,
                answer_ok=False,
                recovered_after_stt_error=False,
                result="FAIL",
                failure_stage="AUDIO",
                failure_detail="Empty utterance after VAD finalize.",
                high_confidence_wrong=False,
                timings=StageTimings(total_ms=round((time.perf_counter() - self._t0) * 1000, 1)),
            )

        t_audio = self._t_audio_detected or self._t0
        t_final = self._t_speech_final or time.perf_counter()
        audio_detected_ms = (t_audio - self._t0) * 1000
        speech_final_ms = (t_final - self._t0) * 1000
        vad_ms = max(0.0, (t_final - t_audio) * 1000)

        self._router.mark_stt_start()
        from app.audio.utterance_preprocess import estimate_audio_levels, preprocess_utterance
        from app.services.stt_confidence import (
            assess_match_risk,
            apply_strong_abstain,
            classify_fail_bucket,
            classify_failure_position,
            edge_word_diagnostics,
            simple_need_second_pass,
            compound_need_second_pass,
            transcript_looks_weak,
            MAX_STT_PASSES_SIMPLE,
            MAX_STT_PASSES_COMPOUND,
        )

        raw_audio = np.asarray(audio, dtype=np.float32)
        speech_duration_ms = (len(raw_audio) / 16000.0) * 1000.0
        prepared = preprocess_utterance(raw_audio, sample_rate=16000, boost=1.0)
        audio_levels = estimate_audio_levels(raw_audio, prepared, sample_rate=16000)

        # Honest stage timers: Whisper-only STT; match/recovery/semantic/compound → intent.
        whisper_ms = 0.0
        match_ms = 0.0
        semantic_ms = 0.0
        compound_ms = 0.0
        compound_detect_ms = 0.0
        rerank_ms = 0.0
        whisper_pass_1_ms = 0.0
        whisper_pass_2_ms = 0.0
        whisper_pass_3_ms = 0.0
        number_of_stt_passes = 0
        technical_repair_ms = 0.0
        base_match_ms = 0.0
        semantic_embedding_ms = 0.0
        semantic_search_ms = 0.0
        semantic_recovery_used = False
        need_second_reason = ""
        first_pass_text = ""
        first_pass_intent: Optional[str] = None
        first_pass_confidence = 0.0
        strong_agrees_flag = False
        simple_stt = _is_simple_stt_clip(meta)
        labeled_compound = str(meta.get("question_type_label") or "") == "compound"
        realistic_ms = 0.0
        recovery_ms = 0.0
        routing_ms = 0.0
        answer_lookup_ms = 0.0
        max_stt_passes = MAX_STT_PASSES_SIMPLE if simple_stt else MAX_STT_PASSES_COMPOUND

        clear_decode_log()
        t_w0 = time.perf_counter()
        transcript = await transcribe_whisper_async(prepared, 16000)
        wall_p1 = (time.perf_counter() - t_w0) * 1000
        d1 = last_decode_info()
        whisper_pass_1_ms = float(d1.get("whisper_ms") or wall_p1)
        whisper_ms += wall_p1
        number_of_stt_passes = 1
        processed_transcript = transcript
        raw_transcript: Optional[str] = None
        first_pass_text = transcript or ""

        # Track C follow_up: seed bank recent-match cache from context_prior, then pass history.
        conversation_history: Optional[list[dict[str, Any]]] = None
        prior = str(meta.get("context_prior") or "").strip()
        qtype_label = str(meta.get("question_type_label") or "")
        if prior and qtype_label in {"follow_up", "follow_up_contextual"}:
            question_bank.match(prior)
            conversation_history = [{"role": "interviewer", "text": prior}]

        t_m0 = time.perf_counter()
        mre_meta: dict[str, Any] = {}
        if transcript.strip():
            from app.services.main_request_extraction import match_with_main_request

            match, _mre_ext, mre_meta = match_with_main_request(
                transcript, conversation_history=conversation_history
            )
        else:
            match = None
        base_match_ms += (time.perf_counter() - t_m0) * 1000
        first_pass_intent = match.entry.id if match is not None else None
        first_pass_confidence = float(match.score) if match is not None else 0.0
        risk = assess_match_risk(transcript, match)
        # Reporting only — do NOT feed gold spoken edges into second-pass gate.
        edge0 = edge_word_diagnostics(spoken, transcript)

        if simple_stt:
            need_second, need_second_reason, strong_agrees_flag = simple_need_second_pass(
                transcript, match, risk=risk
            )
        else:
            # Compound: STT retry only for broken audio — not weak whole-utterance intent.
            need_second, need_second_reason, strong_agrees_flag = compound_need_second_pass(
                transcript, match, risk=risk
            )
        match_ms += base_match_ms

        # When MAIN_REQUEST_EXTRACTION overrode keyword distraction, keep that lock —
        # realistic/semantic recovery must not re-introduce background keywords.
        _extraction = mre_meta.get("extraction")
        _extraction_dict = _extraction if isinstance(_extraction, dict) else {}
        mre_locked = bool(mre_meta.get("override")) and float(
            _extraction_dict.get("confidence") or 0.0
        ) >= 0.72
        if mre_locked:
            strong_agrees_flag = True

        better_source = "processed"
        if need_second and number_of_stt_passes < max_stt_passes:
            # One accurate decode on prepared audio (hard cap 2 for simple + compound).
            t_w0 = time.perf_counter()
            cand_proc = await transcribe_whisper_async(prepared, 16000, accurate=True)
            wall_p2 = (time.perf_counter() - t_w0) * 1000
            d2 = last_decode_info()
            whisper_pass_2_ms = float(d2.get("whisper_ms") or wall_p2)
            whisper_ms += wall_p2
            number_of_stt_passes += 1
            processed_transcript = cand_proc or processed_transcript
            t_m0 = time.perf_counter()
            best = cand_proc or transcript
            from app.services.main_request_extraction import match_with_main_request

            if (best or "").strip():
                best_match, _, _ = match_with_main_request(
                    best, conversation_history=conversation_history
                )
            else:
                best_match = match
            best_score = float(best_match.score) if best_match else 0.0
            better_source = "processed"
            elapsed_m = (time.perf_counter() - t_m0) * 1000
            base_match_ms += elapsed_m
            match_ms += elapsed_m
            # Never a third Whisper pass (MAX_STT_PASSES_* = 2). Pick better of pass1/pass2.
            raw_transcript = None
            for cand, source in ((transcript, "processed"), (cand_proc, "processed")):
                if not cand:
                    continue
                m, _, _ = match_with_main_request(
                    cand, conversation_history=conversation_history
                )
                s = float(m.score) if m else 0.0
                fixes = transcript_looks_weak(best or "") and not transcript_looks_weak(cand)
                if (not best) or s > best_score + 0.03 or fixes:
                    best, best_match, best_score = cand, m, s
                    better_source = source
            transcript = best
            match = best_match
            risk = assess_match_risk(transcript, match)
            # Re-evaluate MAIN_REQUEST on the final transcript (may differ after STT pass 2).
            if (transcript or "").strip():
                rematch, _rext, rmeta = match_with_main_request(
                    transcript, conversation_history=conversation_history
                )
                match = rematch
                mre_meta = rmeta
                _rext_obj = rmeta.get("extraction")
                _rext_dict = _rext_obj if isinstance(_rext_obj, dict) else {}
                mre_locked = bool(rmeta.get("override")) and float(
                    _rext_dict.get("confidence") or 0.0
                ) >= 0.72
                if mre_locked:
                    strong_agrees_flag = True
                risk = assess_match_risk(transcript, match)
        elif need_second:
            need_second_reason = f"capped:{need_second_reason or 'stt'}"

        t_m0 = time.perf_counter()
        match = apply_strong_abstain(match, risk)
        recovery_note = "mre_locked" if mre_locked else ""
        cond = str(meta.get("condition") or "")
        # Suite packs may label "poor"; recovery modules expect "poor_call".
        cond_recovery = "poor_call" if cond in {"poor", "poor_call"} else cond
        # Simple fast path: strong lexical agree → skip realistic/semantic heavy work.
        # Labeled compound: whole-utterance semantic is duplicate work — compound path owns intent.
        skip_heavy_recovery = (strong_agrees_flag) or (labeled_compound) or mre_locked
        if mre_locked and not recovery_note:
            recovery_note = "mre_locked"
        if labeled_compound:
            recovery_note = "fast_path:labeled_compound"
        if (not skip_heavy_recovery) and transcript.strip() and match is not None:
            from app.services.semantic_intent_recovery import should_trigger_semantic_recovery

            _trig, _treason = should_trigger_semantic_recovery(transcript, match)
            if (not _trig) and _treason == "strong_agrees":
                skip_heavy_recovery = True
                strong_agrees_flag = True
        # Latency-cut simple: high lexical score already chose an intent — do not pay
        # thin_margin semantic/rerank tax (Intent thresholds unchanged).
        if (
            simple_stt
            and (not skip_heavy_recovery)
            and match is not None
            and float(getattr(match, "score", 0.0) or 0.0) >= 0.90
            and not transcript_looks_weak(transcript)
        ):
            skip_heavy_recovery = True
            recovery_note = (
                f"{recovery_note}; fast_path:high_lexical"
                if recovery_note
                else "fast_path:high_lexical"
            )
        if cond_recovery == "poor_call":
            from app.services.poor_call_recovery import recover_poor_match

            decision = recover_poor_match(
                transcript,
                match,
                condition="poor_call",
                audio_levels=audio_levels,
                conversation_history=conversation_history,
            )
            if decision.applied:
                match = decision.match
                recovery_note = f"poor_recovery:{decision.reason}:margin={decision.margin:.3f}"
                skip_heavy_recovery = False
        elif cond_recovery == "far":
            from app.services.far_call_recovery import recover_far_match

            decision = recover_far_match(
                transcript,
                match,
                condition="far",
                audio_levels=audio_levels,
                conversation_history=conversation_history,
            )
            if decision.applied:
                match = decision.match
                recovery_note = f"far_recovery:{decision.reason}:margin={decision.margin:.3f}"
                skip_heavy_recovery = False
        # Realistic recovery: low-confidence only. Skip on strong_agrees / labeled compound.
        t_r0 = time.perf_counter()
        if self._enable_realistic_recovery and not skip_heavy_recovery:
            from app.services.realistic_recovery import recover_realistic_match

            decision = recover_realistic_match(
                transcript,
                match,
                conversation_history=conversation_history,
            )
            if decision.applied:
                match = decision.match
                tag = f"realistic_recovery:{decision.reason}:margin={decision.margin:.3f}"
                recovery_note = f"{recovery_note}; {tag}" if recovery_note else tag
        elif skip_heavy_recovery and self._enable_realistic_recovery and not labeled_compound:
            recovery_note = (
                f"{recovery_note}; fast_path:strong_agrees"
                if recovery_note
                else "fast_path:strong_agrees"
            )
        realistic_ms = (time.perf_counter() - t_r0) * 1000
        recovery_ms = (time.perf_counter() - t_m0) * 1000
        match_ms += recovery_ms

        # Semantic paraphrase / short / weak recovery — skip when strong_agrees.
        semantic_trace: dict[str, Any] = {}
        if (
            transcript.strip()
            and not skip_heavy_recovery
            and (
                self._enable_realistic_recovery
                or cond in {"short", "medium", "long", "very_long"}
            )
        ):
            from app.services.semantic_intent_recovery import recover_semantic_intent

            t_s0 = time.perf_counter()
            sem = recover_semantic_intent(
                transcript,
                match,
                conversation_history=conversation_history,
            )
            semantic_ms = (time.perf_counter() - t_s0) * 1000
            rerank_ms = float(getattr(sem, "rerank_ms", 0.0) or 0.0)
            semantic_embedding_ms = float(getattr(sem, "embedding_ms", 0.0) or 0.0)
            semantic_search_ms = float(getattr(sem, "search_ms", 0.0) or 0.0)
            semantic_recovery_used = (sem.triggered)
            semantic_trace = {
                "triggered": sem.triggered,
                "reason": sem.reason,
                "agreement": sem.agreement,
                "margin": sem.margin,
                "reranker_used": sem.reranker_used,
                "semantic_top5": sem.semantic_top5,
                "hybrid_top5": sem.hybrid_top5,
                "abstain_reason": sem.abstain_reason,
                "latency_ms": sem.latency_ms,
                "rerank_ms": round(rerank_ms, 1),
                "embedding_ms": round(semantic_embedding_ms, 1),
                "search_ms": round(semantic_search_ms, 1),
            }
            if sem.applied:
                match = sem.match
                tag = f"semantic_recovery:{sem.reason}:agree={sem.agreement:.3f}"
                recovery_note = f"{recovery_note}; {tag}" if recovery_note else tag
        elif skip_heavy_recovery:
            semantic_trace = {
                "triggered": False,
                "reason": "strong_agrees_fast_path",
                "agreement": 0.0,
                "margin": 0.0,
                "reranker_used": False,
                "latency_ms": 0.0,
                "rerank_ms": 0.0,
            }
        edge = edge_word_diagnostics(spoken, transcript)
        onset = (self._router.last_onset.as_dict() if self._router.last_onset else {})
        stt_ms = whisper_ms
        stt_score = max(_semantic(transcript, spoken), _semantic(transcript, expected))
        stt_ok = stt_score >= 0.72 and bool(transcript.strip())

        t_i0 = time.perf_counter()
        from app.services.compound_question_detector import detect_question_complexity
        from app.services.compound_question_pipeline import resolve_compound_question

        compound = None
        t_det0 = time.perf_counter()
        detection = detect_question_complexity(transcript) if transcript.strip() else None
        compound_detect_ms = (time.perf_counter() - t_det0) * 1000
        # Track B: labeled compound packs must enter the multi-intent path even if
        # detection is shy or a single strong match exists.
        # Latency-cut: single detection → detector only (no resolve) unless labeled compound.
        if transcript.strip() and (
            labeled_compound
            or (detection is not None and detection.question_type != "single")
        ):
            from app.services.compound_question_detector import ComplexityDetection

            force_det = detection
            if labeled_compound and (
                detection is None or detection.question_type == "single"
            ):
                force_det = ComplexityDetection(
                    "compound",
                    0.9,
                    max(2, int(getattr(detection, "request_count_estimate", 1) or 1)),
                    ("labeled_compound_pack",),
                )
            compound = resolve_compound_question(
                transcript,
                conversation_history=conversation_history,
                detection=force_det,
            )
        compound_ms = (time.perf_counter() - t_i0) * 1000
        intent_ms = match_ms + semantic_ms + compound_ms
        ct_timings = (compound.timings if compound is not None else {}) or {}
        decomposition_ms = float(ct_timings.get("decomposition_ms") or 0.0)
        matching_ms = float(ct_timings.get("matching_ms") or 0.0)
        merge_ms = float(ct_timings.get("answer_merge_ms") or 0.0)
        lexical_match_ms = float(ct_timings.get("lexical_match_ms") or 0.0)
        batch_embed_ms = float(ct_timings.get("batch_embed_ms") or 0.0)
        semantic_parts_ms = float(ct_timings.get("semantic_parts_ms") or 0.0)
        harvest_ms = float(ct_timings.get("harvest_ms") or 0.0)
        decode_passes = pop_decode_log()
        stt_info = active_stt_info()

        t_a0 = time.perf_counter()
        intent_score = 0.0
        match_id = None
        match_question = None
        match_score = 0.0
        match_mode = None
        answer_en = None
        from app.services.intent_profile import intent_agreement, intent_meaning_ok
        from app.services.semantic_intent_index import semantic_intent_index

        compound_ok = bool(
            compound
            and compound.used_compound_path
            and compound.answer_en
            and (
                labeled_compound
                or compound.full_compound_success
                or compound.intent_coverage_rate >= 0.67
                or (
                    compound.matched_parts_count >= 2
                    and compound.intent_coverage_rate >= 0.5
                )
            )
        )
        if compound_ok and compound is not None:
            answer_en = compound.answer_en
            match_id = ",".join(compound.selected_intents[:6]) or None
            match_question = " | ".join(compound.sub_questions[:4])
            match_score = max(
                (float(m.score) for m in compound.selected_matches),
                default=0.0,
            )
            match_mode = "strong"
            # Intent score for compound: mean of selected match scores (not short-Q vs long spoken).
            intent_score = match_score
            intent_ok = True
            answer_ok = True
        elif match is not None:
            match_id = match.entry.id
            match_question = match.entry.question
            match_score = float(match.score)
            match_mode = match.mode
            answer_en = match.entry.answer_en if match.mode == "strong" else None
            profile = semantic_intent_index.get(match.entry.id)
            intent_score = max(
                intent_agreement(match.entry, expected, profile=profile),
                intent_agreement(match.entry, spoken, profile=profile),
                intent_agreement(match.entry, transcript, profile=profile),
            )
            # HC protection: strong + very low agreement → demote for scoring/answer.
            if match.mode == "strong" and intent_score < 0.55:
                match_mode = "weak"
                answer_en = None
            meaning_ok, intent_score = intent_meaning_ok(
                match.entry,
                spoken or transcript or expected,
                match_score=match_score,
                profile=profile,
                agreement=intent_score,
            )
            intent_ok = bool(match) and meaning_ok
            answer_ok = bool(answer_en) and intent_ok and match_mode == "strong"
        else:
            intent_ok = False
            answer_ok = False

        # Holdout / compound-dev / generalization-dev: gold IDs authoritative when present.
        gold_ids = [str(x) for x in (meta.get("expected_intent_ids") or []) if x]
        selected_ids: list[str] = []
        if compound_ok and compound is not None:
            # Prefer answered source IDs for gold-part coverage (spoken fragments).
            selected_ids = list(compound.answer_sources or compound.selected_intents or [])
            if not selected_ids:
                selected_ids = list(compound.selected_intents or [])
        elif match is not None:
            selected_ids = [match.entry.id]
        gold_hit: Optional[bool] = None
        gold_id_mismatch = False
        gold_part_coverage = 0.0
        final_coverage = 0.0
        if gold_ids:
            overlap = set(selected_ids) & set(gold_ids)
            gold_hit = bool(overlap)
            gold_id_mismatch = not gold_hit
            # Denominator = human requested parts when labeled (Track B), else |gold|.
            part_labels = list(meta.get("requested_parts") or [])
            denom = float(len(part_labels) or len(gold_ids))
            gold_part_coverage = min(1.0, len(overlap) / denom) if denom else 0.0
            final_coverage = gold_part_coverage
            # Gold hit OR meaning_ok still passes intent; gold miss alone is not HC.
            intent_ok = (gold_hit or intent_ok)
        elif compound is not None and compound.used_compound_path:
            gold_part_coverage = float(compound.intent_coverage_rate or 0.0)
            final_coverage = float(getattr(compound, "final_coverage", 0.0) or gold_part_coverage)
        detected_parts_count = int(getattr(compound, "detected_parts_count", 0) or 0) if compound else 0
        answered_parts_count = int(getattr(compound, "answered_parts_count", 0) or 0) if compound else 0
        missed_parts = list(getattr(compound, "missed_parts", None) or []) if compound else []
        duplicate_parts = list(getattr(compound, "duplicate_parts", None) or []) if compound else []
        compound_failure_code = getattr(compound, "failure_code", None) if compound else None
        result_pass = intent_ok
        answer_ms = (time.perf_counter() - t_a0) * 1000
        answer_lookup_ms = answer_ms

        recovered = (not stt_ok) and intent_ok
        # HC wrong = strong confidence + wrong semantic/intent outcome (not gold-ID sibling mismatch).
        high_conf_wrong = (match_mode == "strong") and (not intent_ok) and match_score >= 0.70
        # Compound path: never mark HC-wrong when coverage gate already passed.
        if compound_ok:
            high_conf_wrong = False
        fail_bucket = classify_fail_bucket(
            stt_ok=stt_ok,
            intent_ok=intent_ok,
            stt_score=stt_score,
            transcript=transcript,
            expected=spoken,
        )
        failure_position = classify_failure_position(
            spoken,
            transcript,
            intent_ok=intent_ok,
            first_word_missing=(edge["first_word_missing"]),
            last_word_missing=(edge["last_word_missing"]),
        )

        if not transcript.strip():
            stage, detail = "STT", "Empty transcript after loopback capture."
        elif not intent_ok and not stt_ok:
            stage, detail = "STT", f"Poor loopback transcription ({fail_bucket})."
        elif not intent_ok:
            stage, detail = "QUESTION_UNDERSTANDING", f"Transcript usable but wrong intent ({fail_bucket})."
        elif not answer_ok:
            stage, detail = "ANSWER_GENERATION", "Intent ok but no bank answer."
        else:
            stage, detail = None, (
                "RECOVERED_AFTER_STT_ERROR" if recovered else ""
            )

        compound_note = ""
        if compound and compound.used_compound_path:
            compound_note = (
                f"compound:cov={compound.intent_coverage_rate}:"
                f"parts={compound.matched_parts_count}/{compound.requested_parts_count}"
            )
        elif detection is not None and detection.question_type != "single":
            compound_note = f"compound_skipped:{detection.question_type}"

        total_ms = (time.perf_counter() - self._t0) * 1000
        return E2EResult(
            sample_id=meta.get("sample_id"),
            file=str(meta.get("file")),
            question_id=meta.get("question_id"),
            speaker=meta.get("requested_region_profile"),
            condition=meta.get("condition"),
            expected_question=expected,
            transcript=transcript,
            stt_ok=stt_ok,
            stt_score=round(stt_score, 3),
            intent_ok=intent_ok,
            intent_score=round(intent_score, 3),
            match_id=match_id,
            match_question=match_question,
            match_score=round(match_score, 3),
            answer_en=answer_en,
            answer_ok=answer_ok,
            recovered_after_stt_error=recovered,
            result="PASS" if result_pass else "FAIL",
            failure_stage=stage if not result_pass else None,
            failure_detail=detail,
            high_confidence_wrong=high_conf_wrong,
            timings=StageTimings(
                audio_detected_ms=round(audio_detected_ms, 1),
                speech_final_ms=round(speech_final_ms, 1),
                stt_ms=round(stt_ms, 1),
                intent_ms=round(intent_ms, 1),
                answer_ms=round(answer_ms, 1),
                total_ms=round(total_ms, 1),
                vad_ms=round(vad_ms, 1),
                post_speech_ms=round(stt_ms + intent_ms + answer_ms, 1),
                whisper_ms=round(whisper_ms, 1),
                match_ms=round(match_ms, 1),
                semantic_ms=round(semantic_ms, 1),
                compound_ms=round(compound_ms, 1),
                compound_detect_ms=round(compound_detect_ms, 1),
                decomposition_ms=round(decomposition_ms, 1),
                matching_ms=round(matching_ms, 1),
                rerank_ms=round(rerank_ms, 1),
                merge_ms=round(merge_ms, 1),
                whisper_pass_1_ms=round(whisper_pass_1_ms, 1),
                whisper_pass_2_ms=round(whisper_pass_2_ms, 1),
                number_of_stt_passes=(number_of_stt_passes),
                technical_repair_ms=round(technical_repair_ms, 1),
                base_match_ms=round(base_match_ms, 1),
                semantic_embedding_ms=round(semantic_embedding_ms, 1),
                semantic_search_ms=round(semantic_search_ms, 1),
                semantic_recovery_used=(semantic_recovery_used),
            ),
            first_word_missing=(edge["first_word_missing"]),
            last_word_missing=(edge["last_word_missing"]),
            speech_duration_ms=round(speech_duration_ms, 1),
            pre_roll_used=True,
            raw_transcript=raw_transcript,
            processed_transcript=processed_transcript,
            better_audio_source=better_source,
            onset=onset,
            audio_levels=audio_levels,
            fail_bucket=fail_bucket,
            failure_position=failure_position,
            notes=("; ".join(x for x in ("e2e_loopback", recovery_note, compound_note) if x)),
            question_type=(detection.question_type if detection else None),
            compound_detected=bool(
                detection and detection.question_type == "compound"
            ),
            compound_confidence=float(detection.confidence) if detection else 0.0,
            requested_parts_count=(compound.requested_parts_count) if compound else 0,
            matched_parts_count=(compound.matched_parts_count) if compound else 0,
            unsupported_parts_count=(compound.unsupported_parts_count) if compound else 0,
            intent_coverage_rate=float(compound.intent_coverage_rate) if compound else 0.0,
            full_compound_success=(compound.full_compound_success) if compound else False,
            partial_compound_success=(compound.partial_compound_match) if compound else False,
            answer_order_correct=(compound.answer_order_correct) if compound else True,
            compound_sub_questions=list(compound.sub_questions) if compound else [],
            compound_selected_intents=list(compound.selected_intents) if compound else [],
            compound_trace=compound.to_trace() if compound else {},
            semantic_recovery=semantic_trace,
            segment_count=int(getattr(self._router, "last_segment_count", 1) or 1),
            truncated_by_max=bool(getattr(self._router, "last_truncated_by_max", False)),
            merged_transcript=int(getattr(self._router, "last_segment_count", 1) or 1) > 1,
            question_type_label=meta.get("question_type_label"),
            expected_intent_ids=list(meta.get("expected_intent_ids") or []),
            accent_label=meta.get("requested_region_profile"),
            holdout_gold_hit=gold_hit,
            match_mode=match_mode,
            gold_id_mismatch=gold_id_mismatch,
            gold_part_coverage=round(gold_part_coverage, 4),
            detected_parts_count=detected_parts_count,
            answered_parts_count=answered_parts_count,
            missed_parts=missed_parts,
            duplicate_parts=duplicate_parts,
            compound_failure_code=compound_failure_code,
            final_coverage=round(final_coverage, 4),
            post_speech_trace={
                "whisper_call_count": (number_of_stt_passes),
                "whisper_pass1_ms": round(whisper_pass_1_ms, 1),
                "whisper_pass2_ms": round(whisper_pass_2_ms, 1),
                "whisper_pass3_ms": round(whisper_pass_3_ms, 1) if whisper_pass_3_ms else None,
                "whisper_pass_1_ms": round(whisper_pass_1_ms, 1),
                "whisper_pass_2_ms": round(whisper_pass_2_ms, 1),
                "whisper_pass_3_ms": round(whisper_pass_3_ms, 1) if whisper_pass_3_ms else None,
                "number_of_stt_passes": (number_of_stt_passes),
                "second_pass_trigger_reason": need_second_reason or None,
                "need_second": (need_second),
                "first_pass_text": (first_pass_text or "")[:240],
                "first_pass_intent": first_pass_intent,
                "first_pass_confidence": round(first_pass_confidence, 4),
                "strong_agrees": (strong_agrees_flag),
                "final_text": (transcript or "")[:240],
                "total_whisper_ms": round(whisper_ms, 1),
                "match_ms": round(match_ms, 1),
                "base_match_ms": round(base_match_ms, 1),
                "realistic_ms": round(realistic_ms, 1),
                "recovery_ms": round(recovery_ms, 1),
                "outer_semantic_ms": round(semantic_ms, 1),
                "semantic_ms": round(semantic_ms, 1),
                "compound_ms": round(compound_ms, 1),
                "intent_ms": round(intent_ms, 1),
                "total_post_ms": round(stt_ms + intent_ms + answer_ms, 1),
                "TOTAL_POST_MS": round(stt_ms + intent_ms + answer_ms, 1),
                "traced_stages_ms": round(
                    whisper_ms
                    + match_ms
                    + semantic_ms
                    + compound_ms
                    + answer_ms,
                    1,
                ),
                "unattributed_ms": round(
                    (stt_ms + intent_ms + answer_ms)
                    - (whisper_ms + match_ms + semantic_ms + compound_ms + answer_ms),
                    1,
                ),
                "attribution_note": (
                    "post = whisper + match_ms + outer_semantic + compound_ms + answer; "
                    "compound_ms includes detect/decomp/subq_match/merge; "
                    "do not sum medians across stages"
                ),
                "simple_stt_budget": (simple_stt),
                "max_stt_passes_simple": MAX_STT_PASSES_SIMPLE,
                "max_stt_passes_compound": MAX_STT_PASSES_COMPOUND,
                "max_stt_passes": int(max_stt_passes),
                "stt_device": stt_info.get("device"),
                "stt_model": stt_info.get("model"),
                "stt_compute_type": stt_info.get("compute_type"),
                "decode_passes": decode_passes,
                "technical_repair_ms": round(technical_repair_ms, 1),
                "routing_ms": round(routing_ms, 1),
                "semantic_embedding_ms": round(semantic_embedding_ms, 1),
                "semantic_search_ms": round(semantic_search_ms, 1),
                "reranker_ms": round(rerank_ms, 1),
                "semantic_recovery_used": (semantic_recovery_used),
                "fast_path": (skip_heavy_recovery),
                "labeled_compound_fast_path": (labeled_compound and skip_heavy_recovery),
                "compound_detect_ms": round(compound_detect_ms, 1),
                "decomposition_ms": round(decomposition_ms, 1),
                "subquestion_match_ms": round(matching_ms, 1),
                "lexical_match_ms": round(lexical_match_ms, 1),
                "batch_embed_ms": round(batch_embed_ms, 1),
                "semantic_parts_ms": round(semantic_parts_ms, 1),
                "harvest_ms": round(harvest_ms, 1),
                "merge_ms": round(merge_ms, 1),
                "answer_ms": round(answer_ms, 1),
                "answer_lookup_ms": round(answer_lookup_ms, 1),
                "edge_report_only": {
                    "first_word_missing": bool(edge0.get("first_word_missing")),
                    "last_word_missing": bool(edge0.get("last_word_missing")),
                },
                "alias_matrix_ready": bool(
                    getattr(getattr(question_bank, "_index", None), "alias_matrix", None)
                    is not None
                ),
                "system_warm": bool(
                    __import__(
                        "app.services.warm_start", fromlist=["is_system_warm"]
                    ).is_system_warm()
                ),
            },
        )


def summarize(results: list[E2EResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.result == "PASS")
    intent_ok = sum(1 for r in results if r.intent_ok)
    stt_ok = sum(1 for r in results if r.stt_ok)
    recovered = sum(1 for r in results if r.recovered_after_stt_error)
    hc_wrong = sum(1 for r in results if r.high_confidence_wrong)
    first_miss = sum(1 for r in results if r.first_word_missing)
    last_miss = sum(1 for r in results if r.last_word_missing)
    raw_better = sum(1 for r in results if r.better_audio_source == "raw")
    multi_segment = sum(1 for r in results if int(getattr(r, "segment_count", 1) or 1) > 1)
    truncated_max = sum(1 for r in results if getattr(r, "truncated_by_max", False))
    fail_buckets: dict[str, int] = {}
    acoustic_causes: dict[str, int] = {}
    for r in results:
        if r.fail_bucket:
            fail_buckets[r.fail_bucket] = fail_buckets.get(r.fail_bucket, 0) + 1
        for cause in classify_far_acoustic_causes(r):
            acoustic_causes[cause] = acoustic_causes.get(cause, 0) + 1
    totals = sorted(r.timings.total_ms for r in results)
    post = sorted(r.timings.post_speech_ms for r in results)
    stts = [r.timings.stt_ms for r in results]
    vads = [r.timings.vad_ms for r in results]
    intents = [r.timings.intent_ms for r in results]
    answers = [r.timings.answer_ms for r in results]

    def pct(vals: list[float], p: float) -> float:
        if not vals:
            return 0.0
        idx = min(len(vals) - 1, max(0, (round((len(vals) - 1) * p))))
        return round(sorted(vals)[idx], 1)

    by_condition: dict[str, dict[str, int]] = {}
    by_speaker: dict[str, dict[str, int]] = {}
    stages: dict[str, int] = {}
    for r in results:
        c = r.condition or "?"
        s = r.speaker or "?"
        by_condition.setdefault(c, {"total": 0, "pass": 0, "intent": 0})
        by_condition[c]["total"] += 1
        by_condition[c]["pass"] += int(r.result == "PASS")
        by_condition[c]["intent"] += int(r.intent_ok)
        by_speaker.setdefault(s, {"total": 0, "pass": 0, "intent": 0})
        by_speaker[s]["total"] += 1
        by_speaker[s]["pass"] += int(r.result == "PASS")
        by_speaker[s]["intent"] += int(r.intent_ok)
        if r.failure_stage:
            stages[r.failure_stage] = stages.get(r.failure_stage, 0) + 1

    rms_before = [float((r.audio_levels or {}).get("rms_before") or 0.0) for r in results]
    rms_after = [float((r.audio_levels or {}).get("rms_after") or 0.0) for r in results]
    snr = [float((r.audio_levels or {}).get("snr_db_est") or 0.0) for r in results]
    fails = [r for r in results if r.result != "PASS"]
    fail_low_rms = sum(
        1 for r in fails
        if float((r.audio_levels or {}).get("rms_before") or 0.0) < 0.02
    )
    fail_ok_rms_low_snr = sum(
        1 for r in fails
        if float((r.audio_levels or {}).get("rms_before") or 0.0) >= 0.02
        and float((r.audio_levels or {}).get("snr_db_est") or 99.0) < 6.0
    )

    def rate(block: dict[str, dict[str, int]]) -> dict[str, Any]:
        out = {}
        for k, v in block.items():
            t = v["total"]
            out[k] = {
                "total": t,
                "pass": v["pass"],
                "intent": v["intent"],
                "pass_rate": round(v["pass"] / t, 3) if t else 0.0,
                "intent_rate": round(v["intent"] / t, 3) if t else 0.0,
            }
        return out

    def avg(vals: list[float]) -> float:
        return round(sum(vals) / len(vals), 5) if vals else 0.0

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "stt_success": f"{stt_ok}/{total}",
        "intent_success": f"{intent_ok}/{total}",
        "intent_success_rate": round(intent_ok / total, 3) if total else 0.0,
        "recovered_after_stt_error": recovered,
        "intent_recovery_rate": round(recovered / max(1, total - stt_ok), 3),
        "high_confidence_wrong": hc_wrong,
        "first_word_missing": first_miss,
        "last_word_missing": last_miss,
        "multi_segment_utterances": multi_segment,
        "truncated_by_max": truncated_max,
        "raw_better_than_processed": raw_better,
        "fail_buckets": fail_buckets,
        "acoustic_causes": acoustic_causes,
        "audio_levels": {
            "avg_rms_before": avg(rms_before),
            "avg_rms_after": avg(rms_after),
            "avg_snr_db_est": round(sum(snr) / len(snr), 2) if snr else 0.0,
            "avg_bandwidth_hz_est": avg(
                [float((r.audio_levels or {}).get("bandwidth_hz_est") or 0.0) for r in results]
            ),
            "avg_high_freq_energy_ratio": avg(
                [float((r.audio_levels or {}).get("high_freq_energy_ratio") or 0.0) for r in results]
            ),
            "fail_low_rms_count": fail_low_rms,
            "fail_ok_rms_low_snr_count": fail_ok_rms_low_snr,
            "fail_narrowband_count": sum(
                1
                for r in fails
                if (
                    float((r.audio_levels or {}).get("bandwidth_hz_est") or 0.0) > 0
                    and float((r.audio_levels or {}).get("bandwidth_hz_est") or 0.0) < 2500.0
                )
                or float((r.audio_levels or {}).get("high_freq_energy_ratio") or 1.0) < 0.03
            ),
            "fail_onset_count": sum(1 for r in fails if r.first_word_missing),
        },
        "latency": {
            "median_total_ms": pct(totals, 0.5),
            "p95_total_ms": pct(totals, 0.95),
            "avg_total_ms": round(sum(totals) / total, 1) if total else 0.0,
            "median_post_speech_ms": pct(post, 0.5),
            "p95_post_speech_ms": pct(post, 0.95),
            "avg_post_speech_ms": round(sum(post) / total, 1) if total else 0.0,
            "avg_vad_ms": round(sum(vads) / total, 1) if total else 0.0,
            "avg_stt_ms": round(sum(stts) / total, 1) if total else 0.0,
            "avg_intent_ms": round(sum(intents) / total, 1) if total else 0.0,
            "avg_answer_ms": round(sum(answers) / total, 1) if total else 0.0,
        },
        "by_condition": rate(by_condition),
        "by_speaker": rate(by_speaker),
        "failure_stages": stages,
        "compound": {
            "compound_detected": sum(1 for r in results if r.compound_detected),
            "compound_path_used": sum(
                1 for r in results if r.matched_parts_count > 0 and r.question_type in {"compound", "uncertain"}
            ),
            "full_compound_success": sum(1 for r in results if r.full_compound_success),
            "partial_compound_success": sum(1 for r in results if r.partial_compound_success),
            "avg_intent_coverage_rate": round(
                sum(r.intent_coverage_rate for r in results if r.requested_parts_count > 0)
                / max(1, sum(1 for r in results if r.requested_parts_count > 0)),
                3,
            ),
            "answer_order_correct": sum(1 for r in results if r.answer_order_correct),
            "final_answer_ok": sum(1 for r in results if r.answer_ok),
            "requested_parts_total": sum(r.requested_parts_count for r in results),
            "matched_parts_total": sum(r.matched_parts_count for r in results),
            "unsupported_parts_total": sum(r.unsupported_parts_count for r in results),
        },
        "targets": {
            "clean_intent": 0.95,
            "office_intent": 0.90,
            "poor_call_intent": 0.85,
            "far_intent": 0.85,
            "combined_pass": 0.60,
            "median_post_speech_ms": 1500,
            "p95_post_speech_ms": 2500,
            "high_confidence_wrong": 0,
        },
    }


def summarize_by_accent(results: list[E2EResult]) -> list[dict[str, Any]]:
    """Accent table for long/short length A/B reports."""
    groups: dict[str, list[E2EResult]] = {}
    for r in results:
        accent = (r.speaker or "?")
        groups.setdefault(accent, []).append(r)

    def pct(vals: list[float], p: float) -> float:
        if not vals:
            return 0.0
        idx = min(len(vals) - 1, max(0, round((len(vals) - 1) * p)))
        return round(sorted(vals)[idx], 1)

    rows: list[dict[str, Any]] = []
    for accent in sorted(groups.keys()):
        rs = groups[accent]
        n = len(rs)
        stt_n = sum(1 for r in rs if r.stt_ok)
        intent_n = sum(1 for r in rs if r.intent_ok)
        meaning_lost = sum(1 for r in rs if r.fail_bucket == "stt_wrong_meaning_lost")
        hc = sum(1 for r in rs if r.high_confidence_wrong)
        durs = [float(r.speech_duration_ms or 0.0) for r in rs]
        posts = [float(r.timings.post_speech_ms or 0.0) for r in rs]
        pos_counts: dict[str, int] = {}
        for r in rs:
            if r.intent_ok:
                continue
            pos = r.failure_position or "unknown"
            pos_counts[pos] = pos_counts.get(pos, 0) + 1
        # Dominant failure position among fails (or none).
        if pos_counts:
            dominant = max(pos_counts.items(), key=lambda kv: kv[1])[0]
        else:
            dominant = "none"
        rows.append(
            {
                "accent": accent,
                "n": n,
                "stt": f"{stt_n}/{n}",
                "stt_rate": round(stt_n / n, 3) if n else 0.0,
                "intent": f"{intent_n}/{n}",
                "intent_rate": round(intent_n / n, 3) if n else 0.0,
                "meaning_lost": meaning_lost,
                "hc_wrong": hc,
                "duration_median_ms": pct(durs, 0.5),
                "latency_median_ms": pct(posts, 0.5),
                "failure_position": dominant,
                "failure_positions": pos_counts,
            }
        )
    return rows


def write_final_unseen_holdout_report(
    results: list[E2EResult],
    summary: dict[str, Any],
    filters: dict[str, Any],
    *,
    suite: str = "final_unseen_holdout",
    stem: str = "FINAL_UNSEEN_HOLDOUT_REPORT",
) -> dict[str, Any]:
    """Adoption-gate report: overall → type → condition → accent → FAIL detail."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    scored = [r for r in results if not (r.notes or "").startswith("warmup:")]
    # Prefer results already filtered by caller; keep all if none tagged.
    if not scored:
        scored = list(results)

    total = len(scored)
    intent_n = sum(1 for r in scored if r.intent_ok)
    hc = sum(1 for r in scored if r.high_confidence_wrong)
    meaning_lost = sum(1 for r in scored if r.fail_bucket == "stt_wrong_meaning_lost")
    posts = sorted(float(r.timings.post_speech_ms or 0.0) for r in scored)
    median_post = posts[len(posts) // 2] if posts else 0.0
    whis = sorted(float(r.timings.whisper_ms or 0.0) for r in scored)
    sems = sorted(float(r.timings.semantic_ms or 0.0) for r in scored)
    intent_lat = sorted(float(r.timings.intent_ms or 0.0) for r in scored)

    def _med(vals: list[float]) -> float:
        return vals[len(vals) // 2] if vals else 0.0

    compound_rows = [r for r in scored if (r.question_type_label or "") == "compound"]
    if compound_rows:
        # Gate metric: gold part coverage (parts hit), NOT whether router used compound_path.
        cov = sum(float(r.gold_part_coverage or 0.0) for r in compound_rows) / len(compound_rows)
        path_used = sum(
            1
            for r in compound_rows
            if bool((r.compound_trace or {}).get("used_compound_path"))
            or float(r.intent_coverage_rate or 0.0) > 0.0
        ) / len(compound_rows)
    else:
        cov = 0.0
        path_used = 0.0
    gold_mismatch_n = sum(1 for r in scored if r.gold_id_mismatch)
    simple = [
        r
        for r in scored
        if (r.question_type_label or "") in {"ultra_short", "short"}
    ]
    compound_on_simple = sum(
        1
        for r in simple
        if r.compound_detected
        and (
            bool((r.compound_trace or {}).get("used_compound_path"))
            or (r.matched_parts_count or 0) >= 2
        )
    )
    last_miss_vl = sum(
        1
        for r in scored
        if (r.question_type_label or "") == "very_long" and r.last_word_missing
    )
    vl_n = sum(1 for r in scored if (r.question_type_label or "") == "very_long")

    gate = {
        "intent_rate": round(intent_n / total, 4) if total else 0.0,
        "intent_pass": (intent_n / total >= 0.92) if total else False,
        "hc_wrong": hc,
        "hc_pass": hc == 0,
        "gold_id_mismatch": gold_mismatch_n,
        "meaning_lost_rate": round(meaning_lost / total, 4) if total else 0.0,
        "meaning_lost_pass": (meaning_lost / total <= 0.01) if total else False,
        "median_post_speech_ms": round(median_post, 1),
        "median_post_speech_pass": median_post <= 1500.0,
        "latency_breakdown_median_ms": {
            "whisper": round(_med(whis), 1),
            "intent_total": round(_med(intent_lat), 1),
            "semantic": round(_med(sems), 1),
            "post_speech": round(median_post, 1),
        },
        "compound_coverage": round(cov, 4),
        "compound_coverage_pass": (cov >= 0.90) if compound_rows else True,
        "compound_path_used_rate": round(path_used, 4),
        "compound_path_used_diagnostic_only": True,
        "simple_unnecessary_compound": compound_on_simple,
        "simple_fast_path_pass": compound_on_simple == 0,
        "very_long_last_word_missing": f"{last_miss_vl}/{vl_n}",
        "very_long_last_word_missing_diagnostic_only": True,
    }
    gate["ready"] = all(
        [
            gate["intent_pass"],
            gate["hc_pass"],
            gate["meaning_lost_pass"],
            gate["median_post_speech_pass"],
            gate["compound_coverage_pass"],
            gate["simple_fast_path_pass"],
        ]
    )

    def _bucket(key_fn):
        groups: dict[str, list[E2EResult]] = {}
        for r in scored:
            groups.setdefault(key_fn(r), []).append(r)
        out = {}
        for k, rs in sorted(groups.items()):
            n = len(rs)
            out[k] = {
                "total": n,
                "intent": sum(1 for r in rs if r.intent_ok),
                "intent_rate": round(sum(1 for r in rs if r.intent_ok) / n, 3) if n else 0.0,
                "hc_wrong": sum(1 for r in rs if r.high_confidence_wrong),
                "meaning_lost": sum(1 for r in rs if r.fail_bucket == "stt_wrong_meaning_lost"),
            }
        return out

    by_type = _bucket(lambda r: r.question_type_label or "?")
    by_condition = _bucket(lambda r: r.condition or "?")
    by_accent = _bucket(lambda r: r.accent_label or r.speaker or "?")

    fails = []
    for r in scored:
        if r.intent_ok and r.result == "PASS":
            continue
        selected = r.match_id
        if r.compound_selected_intents:
            selected = ",".join(r.compound_selected_intents)
        elif not selected and r.semantic_recovery.get("abstain_reason"):
            selected = f"abstain:{r.semantic_recovery.get('abstain_reason')}"
        fails.append(
            {
                "id": r.sample_id or r.question_id,
                "question_type": r.question_type_label,
                "condition": r.condition,
                "accent": r.accent_label or r.speaker,
                "transcript": r.transcript,
                "expected_intent": list(r.expected_intent_ids or []),
                "selected_or_abstain": selected,
                "failure_stage": r.failure_stage,
                "fail_bucket": r.fail_bucket,
                "last_word_missing": r.last_word_missing,
                "gold_hit": r.holdout_gold_hit,
            }
        )

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "suite": suite,
        "eval_only": True,
        "frozen_intent_layer": True,
        "filters": filters,
        "summary": summary,
        "adoption_gate": gate,
        "by_question_type": by_type,
        "by_condition": by_condition,
        "by_accent": by_accent,
        "fails": fails,
        "results": [asdict(r) for r in scored],
        "protocol": "FINAL_UNSEEN_HOLDOUT_PROTOCOL.md",
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORTS_DIR / f"{stem}_{stamp}.json"
    latest = REPORTS_DIR / f"{stem}.json"
    html_path = REPORTS_DIR / f"{stem}.html"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")

    def _tbl(title: str, block: dict[str, Any]) -> str:
        rows = "".join(
            f"<tr><td>{html.escape(k)}</td><td>{v['intent']}/{v['total']}</td>"
            f"<td>{v['intent_rate']:.0%}</td><td>{v['hc_wrong']}</td><td>{v['meaning_lost']}</td></tr>"
            for k, v in block.items()
        )
        return (
            f"<h2>{html.escape(title)}</h2><table><tr><th>Key</th><th>Intent</th>"
            f"<th>Rate</th><th>HC</th><th>meaning_lost</th></tr>{rows}</table>"
        )

    ready_cls = "ok" if gate["ready"] else "bad"

    def _fail_expected(f: dict[str, Any]) -> str:
        expected = f.get("expected_intent")
        if isinstance(expected, list):
            return ",".join(str(x) for x in expected)
        return ""

    fail_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(f.get('id')))}</td>"
        f"<td>{html.escape(str(f.get('question_type')))}</td>"
        f"<td>{html.escape(str(f.get('condition')))}</td>"
        f"<td>{html.escape(str(f.get('accent')))}</td>"
        f"<td>{html.escape(str(f.get('transcript') or '')[:160])}</td>"
        f"<td>{html.escape(_fail_expected(f))}</td>"
        f"<td>{html.escape(str(f.get('selected_or_abstain')))}</td>"
        f"<td>{html.escape(str(f.get('failure_stage')))}</td>"
        "</tr>"
        for f in fails
    )
    body = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Final Unseen Holdout</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:2rem;background:#0f1419;color:#e7ecf1}}
table{{border-collapse:collapse;width:100%;margin:.8rem 0 1.4rem}}
th,td{{border:1px solid #2a3540;padding:.45rem .55rem;text-align:left;font-size:.92rem}}
th{{background:#1a2330}}.ok{{color:#7ddea0}}.bad{{color:#f07178}}.warn{{color:#f0b27a}}
</style></head><body>
<h1>Final Unseen Holdout — <span class="{ready_cls}">{"READY" if gate["ready"] else "NOT READY"}</span></h1>
<p>Eval-only · frozen intent layer · do not tune on this pack.</p>
<ul>
<li>Intent: <strong>{intent_n}/{total}</strong> ({gate["intent_rate"]:.1%}) — gate ≥92% — {"PASS" if gate["intent_pass"] else "FAIL"}</li>
<li>HC wrong: <strong>{hc}</strong> — gate 0 — {"PASS" if gate["hc_pass"] else "FAIL"}</li>
<li>gold_id_mismatch (obs): <strong>{gate.get("gold_id_mismatch", 0)}</strong> — not HC</li>
<li>meaning_lost: <strong>{meaning_lost}/{total}</strong> ({gate["meaning_lost_rate"]:.1%}) — gate ≤1% — {"PASS" if gate["meaning_lost_pass"] else "FAIL"}</li>
<li>median post-speech: <strong>{gate["median_post_speech_ms"]}ms</strong> — gate ≤1500ms — {"PASS" if gate["median_post_speech_pass"] else "FAIL"}</li>
<li>latency median breakdown: <strong>{html.escape(str(gate.get("latency_breakdown_median_ms")))}</strong></li>
<li>Compound gold-part coverage: <strong>{gate["compound_coverage"]:.1%}</strong> — gate ≥90% — {"PASS" if gate["compound_coverage_pass"] else "FAIL"}</li>
<li class="warn">compound_path_used (diagnostic): {gate.get("compound_path_used_rate", 0):.1%}</li>
<li>Simple unnecessary compound: <strong>{compound_on_simple}</strong> — {"PASS" if gate["simple_fast_path_pass"] else "FAIL"}</li>
<li class="warn">Very-long last_word_missing (diagnostic): {gate["very_long_last_word_missing"]}</li>
</ul>
{_tbl("By question type", by_type)}
{_tbl("By audio condition", by_condition)}
{_tbl("By accent", by_accent)}
<h2>FAIL detail</h2>
<table><tr><th>ID</th><th>Type</th><th>Cond</th><th>Accent</th><th>Transcript</th><th>Expected intent</th><th>Selected/abstain</th><th>Stage</th></tr>
{fail_rows or "<tr><td colspan='8'>None</td></tr>"}
</table>
</body></html>"""
    html_path.write_text(body, encoding="utf-8")
    public = (
        Path(__file__).resolve().parents[3] / "frontend" / "public" / "voice-drill"
    )
    try:
        public.mkdir(parents=True, exist_ok=True)
        (public / f"{stem}.html").write_text(body, encoding="utf-8")
    except OSError:
        pass
    return {
        "report_json": str(latest),
        "report_html": str(html_path),
        "report_html_latest": str(html_path),
        "score_name": "Final Unseen Holdout",
        "suite": suite,
        "adoption_gate": gate,
    }


def write_compound_dev_report(
    results: list[E2EResult],
    summary: dict[str, Any],
    filters: dict[str, Any],
) -> dict[str, Any]:
    """Track B gate report for compound-dev pack."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    scored = [r for r in results if not (r.notes or "").startswith("warmup:")]
    if not scored:
        scored = list(results)
    total = len(scored)
    intent_n = sum(1 for r in scored if r.intent_ok)
    hc = sum(1 for r in scored if r.high_confidence_wrong)
    cov = (
        sum(float(r.gold_part_coverage or 0.0) for r in scored) / total if total else 0.0
    )
    dup_rate = (
        sum(1 for r in scored if r.duplicate_parts) / total if total else 0.0
    )
    posts = sorted(float(r.timings.post_speech_ms or 0.0) for r in scored)
    median_post = posts[len(posts) // 2] if posts else 0.0
    codes: dict[str, int] = {}
    for r in scored:
        code = r.compound_failure_code or "NONE"
        codes[code] = codes.get(code, 0) + 1
    path_used = sum(
        1 for r in scored if bool((r.compound_trace or {}).get("used_compound_path"))
    )
    gate = {
        "intent_rate": round(intent_n / total, 4) if total else 0.0,
        "intent_pass": (intent_n / total >= 0.95) if total else False,
        "hc_wrong": hc,
        "hc_pass": hc == 0,
        "gold_part_coverage": round(cov, 4),
        "gold_part_coverage_pass": cov >= 0.90,
        "duplicate_answer_rate": round(dup_rate, 4),
        "duplicate_pass": dup_rate <= 0.05,
        "median_post_speech_ms": round(median_post, 1),
        "median_post_speech_observe_only": True,
        "compound_path_used": path_used,
        "failure_codes": codes,
    }
    gate["ready"] = all(
        [
            gate["intent_pass"],
            gate["hc_pass"],
            gate["gold_part_coverage_pass"],
            gate["duplicate_pass"],
        ]
    )
    fails = []
    for r in scored:
        if r.intent_ok and float(r.gold_part_coverage or 0) >= 0.99 and r.result == "PASS":
            continue
        fails.append(
            {
                "id": r.sample_id,
                "transcript": (r.transcript or "")[:200],
                "expected": list(r.expected_intent_ids or []),
                "selected": list(r.compound_selected_intents or ([r.match_id] if r.match_id else [])),
                "answered_sources": list((r.compound_trace or {}).get("answer_sources") or []),
                "gold_part_coverage": r.gold_part_coverage,
                "failure_code": r.compound_failure_code,
                "detected": r.detected_parts_count,
                "matched": r.matched_parts_count,
                "answered": r.answered_parts_count,
                "missed": list(r.missed_parts or []),
            }
        )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "suite": "compound_dev",
        "track": "B",
        "not_final_holdout": True,
        "filters": filters,
        "summary": summary,
        "track_b_gate": gate,
        "fails": fails,
        "results": [asdict(r) for r in scored],
    }
    stem = "COMPOUND_DEV_REPORT"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    latest = REPORTS_DIR / f"{stem}.json"
    html_path = REPORTS_DIR / f"{stem}.html"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (REPORTS_DIR / f"{stem}_{stamp}.json").write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    ready_cls = "ok" if gate["ready"] else "bad"
    body = f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Compound Dev Track B</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:2rem;background:#0f1419;color:#e7ecf1}}
.ok{{color:#7ddea0}}.bad{{color:#f07178}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #2a3540;padding:.4rem;text-align:left}}
</style></head><body>
<h1>Compound Dev (Track B) — <span class="{ready_cls}">{"PASS" if gate["ready"] else "FAIL"}</span></h1>
<ul>
<li>Intent: {intent_n}/{total} ({gate["intent_rate"]:.1%}) — gate ≥95%</li>
<li>Gold-part coverage: {gate["gold_part_coverage"]:.1%} — gate ≥90%</li>
<li>HC wrong: {hc}</li>
<li>Duplicate rate: {gate["duplicate_answer_rate"]:.1%}</li>
<li>Median post-speech (observe): {gate["median_post_speech_ms"]}ms</li>
<li>Failure codes: {html.escape(json.dumps(codes))}</li>
</ul>
</body></html>"""
    html_path.write_text(body, encoding="utf-8")
    return {
        "report_json": str(latest),
        "report_html": str(html_path),
        "report_html_latest": str(html_path),
        "score_name": "Compound Dev Track B",
        "suite": "compound_dev",
        "track_b_gate": gate,
    }


def write_generalization_dev_report(
    results: list[E2EResult],
    summary: dict[str, Any],
    filters: dict[str, Any],
) -> dict[str, Any]:
    """Track C gate report for generalization-dev pack."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    scored = [r for r in results if not (r.notes or "").startswith("warmup:")]
    if not scored:
        scored = list(results)
    total = len(scored)
    intent_n = sum(1 for r in scored if r.intent_ok)
    hc = sum(1 for r in scored if r.high_confidence_wrong)
    meaning_lost = sum(1 for r in scored if r.fail_bucket == "stt_wrong_meaning_lost")
    posts = sorted(float(r.timings.post_speech_ms or 0.0) for r in scored)
    median_post = posts[len(posts) // 2] if posts else 0.0

    major = ("medium", "ultra_short", "indirect", "follow_up")
    by_slice: dict[str, dict[str, Any]] = {}
    for key in major:
        rs = [r for r in scored if (r.question_type_label or "") == key]
        n = len(rs)
        ok = sum(1 for r in rs if r.intent_ok)
        rate = (ok / n) if n else 0.0
        by_slice[key] = {
            "n": n,
            "intent_ok": ok,
            "intent_rate": round(rate, 4),
            "intent_pass": rate >= 0.90 if n else False,
            "hc_wrong": sum(1 for r in rs if r.high_confidence_wrong),
            "meaning_lost": sum(1 for r in rs if r.fail_bucket == "stt_wrong_meaning_lost"),
        }
    hard = [r for r in scored if (r.question_type_label or "") in {"far", "poor"}]
    hard_n = len(hard)
    hard_ok = sum(1 for r in hard if r.intent_ok)
    hard_rate = (hard_ok / hard_n) if hard_n else 0.0

    gate = {
        "intent_rate": round(intent_n / total, 4) if total else 0.0,
        "intent_pass": (intent_n / total >= 0.92) if total else False,
        "hc_wrong": hc,
        "hc_pass": hc == 0,
        "meaning_lost": meaning_lost,
        "meaning_lost_pass": meaning_lost == 0,
        "by_slice": by_slice,
        "slice_pass": all(by_slice[k]["intent_pass"] for k in major if by_slice[k]["n"]),
        "far_poor_rate": round(hard_rate, 4),
        "far_poor_n": hard_n,
        "far_poor_pass_observe": hard_rate >= 0.85 if hard_n else True,
        "median_post_speech_ms": round(median_post, 1),
        "median_post_speech_observe_only": True,
    }
    gate["ready"] = all(
        [
            gate["intent_pass"],
            gate["hc_pass"],
            gate["meaning_lost_pass"],
            gate["slice_pass"],
        ]
    )
    fails = []
    for r in scored:
        if r.intent_ok and r.result == "PASS" and not r.high_confidence_wrong:
            continue
        fails.append(
            {
                "id": r.sample_id,
                "question_type": r.question_type_label,
                "condition": r.condition,
                "transcript": (r.transcript or "")[:200],
                "expected": list(r.expected_intent_ids or []),
                "selected": list(r.compound_selected_intents or ([r.match_id] if r.match_id else [])),
                "intent_ok": r.intent_ok,
                "gold_hit": r.holdout_gold_hit,
                "hc_wrong": r.high_confidence_wrong,
                "fail_bucket": r.fail_bucket,
                "failure_stage": r.failure_stage,
            }
        )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "suite": "generalization_dev",
        "track": "C",
        "not_final_holdout": True,
        "filters": filters,
        "summary": summary,
        "track_c_gate": gate,
        "fails": fails,
        "results": [asdict(r) for r in scored],
    }
    stem = "GENERALIZATION_DEV_REPORT"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    latest = REPORTS_DIR / f"{stem}.json"
    html_path = REPORTS_DIR / f"{stem}.html"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (REPORTS_DIR / f"{stem}_{stamp}.json").write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    ready_cls = "ok" if gate["ready"] else "bad"
    slice_rows = "".join(
        f"<tr><td>{k}</td><td>{v['intent_ok']}/{v['n']}</td>"
        f"<td>{v['intent_rate']:.0%}</td><td>{v['hc_wrong']}</td>"
        f"<td>{v['meaning_lost']}</td></tr>"
        for k, v in by_slice.items()
    )
    body = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Generalization Dev Track C</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:2rem;background:#0f1419;color:#e7ecf1}}
.ok{{color:#7ddea0}}.bad{{color:#f07178}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #2a3540;padding:.4rem;text-align:left}}
</style></head><body>
<h1>Generalization Dev (Track C) — <span class="{ready_cls}">{"PASS" if gate["ready"] else "FAIL"}</span></h1>
<ul>
<li>Overall Intent: {intent_n}/{total} ({gate["intent_rate"]:.1%}) — gate ≥92%</li>
<li>HC wrong: {hc}</li>
<li>meaning_lost: {meaning_lost}</li>
<li>Far+poor (observe ≥85%): {hard_ok}/{hard_n} ({gate["far_poor_rate"]:.1%})</li>
<li>Median post-speech (observe): {gate["median_post_speech_ms"]}ms</li>
</ul>
<h2>By slice (gate ≥90% each)</h2>
<table><tr><th>Slice</th><th>Intent</th><th>Rate</th><th>HC</th><th>meaning_lost</th></tr>
{slice_rows}
</table>
</body></html>"""
    html_path.write_text(body, encoding="utf-8")
    return {
        "report_json": str(latest),
        "report_html": str(html_path),
        "report_html_latest": str(html_path),
        "score_name": "Generalization Dev Track C",
        "suite": "generalization_dev",
        "track_c_gate": gate,
        "adoption_gate": gate,
    }


def write_reports(
    results: list[E2EResult],
    summary: dict[str, Any],
    filters: dict[str, Any],
    *,
    report_stem: str = "INTERVIEW_E2E_LOOPBACK_REPORT",
) -> dict[str, str]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": filters.get("mode", "e2e_windows_loopback"),
        "suite": filters.get("suite", "stress"),
        "filters": filters,
        "summary": summary,
        "results": [asdict(r) for r in results],
    }
    json_path = REPORTS_DIR / f"{report_stem}_{stamp}.json"
    latest_json = REPORTS_DIR / f"{report_stem}.json"
    html_path = REPORTS_DIR / f"{report_stem}.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    def esc(x: Any) -> str:
        return html.escape("" if x is None else str(x))

    ranked = sorted(results, key=lambda r: (-(r.result == "PASS"), -r.intent_score, r.timings.total_ms))
    rows = []
    for r in ranked:
        cls = "pass" if r.result == "PASS" else "fail"
        rows.append(
            "<tr class='{cls}'>"
            "<td>{audio}</td><td>{stt}</td><td>{intent}</td><td>{ans}</td>"
            "<td>{vad}</td><td>{sttm}</td><td>{im}</td><td>{am}</td><td>{tot}</td>"
            "<td>{rec}</td><td><b>{res}</b></td><td>{stage}</td>"
            "</tr>".format(
                cls=cls,
                audio=esc(f"Q{r.question_id} {r.speaker} {r.condition}"),
                stt=esc("OK" if r.stt_ok else f"weak {r.stt_score}"),
                intent=esc("OK" if r.intent_ok else f"wrong {r.intent_score}"),
                ans=esc("OK" if r.answer_ok else "no"),
                vad=esc(r.timings.vad_ms),
                sttm=esc(r.timings.stt_ms),
                im=esc(r.timings.intent_ms),
                am=esc(r.timings.answer_ms),
                tot=esc(r.timings.total_ms),
                rec=esc("YES" if r.recovered_after_stt_error else "—"),
                res=esc(r.result),
                stage=esc(r.failure_stage or "—"),
            )
        )

    lat = summary.get("latency", {})
    suite = str(filters.get("suite") or "stress")
    score_name = (
        "Realistic Interview Score"
        if suite == "realistic"
        else "Clean E2E Score"
        if suite == "clean"
        else "Office + Poor Call Score"
        if suite == "office_poor"
        else "Poor Call Recovery Score"
        if suite == "poor"
        else "Far Diagnostic Score"
        if suite == "far"
        else "Realistic Holdout Score"
        if suite == "realistic_holdout"
        else "Realistic Holdout V2 Score"
        if suite == "realistic_holdout_v2"
        else "Extreme Stress Combined Score"
        if suite == "extreme_combined"
        else "Long Sentence Accent Score"
        if suite == "long_accent"
        else "Short Length Regression Score"
        if suite == "short_length"
        else "Medium Length Regression Score"
        if suite == "medium_length"
        else "Very Long Length Regression Score"
        if suite == "very_long_length"
        else "Stress Test Score"
    )
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{esc(score_name)}</title>
<style>
body{{font-family:Segoe UI,Tahoma,sans-serif;margin:24px;background:#0f1419;color:#e8eef5}}
.card{{display:inline-block;background:#1a222d;border:1px solid #2a3544;border-radius:12px;padding:12px;margin:6px;min-width:140px}}
.card b{{display:block;font-size:1.25rem}}
table{{width:100%;border-collapse:collapse;background:#1a222d}}
th,td{{border-bottom:1px solid #2a3544;padding:8px;font-size:.85rem;text-align:left}}
tr.pass td{{background:rgba(61,214,140,.06)}}
tr.fail td{{background:rgba(240,113,120,.08)}}
.meta{{color:#8b9aab}}
</style></head><body>
<h1>{esc(score_name)}</h1>
<p class="meta">Suite: {esc(suite)} · Mode: play → WASAPI loopback → VAD → STT → repair → intent → answer</p>
<p class="meta">Audio path: pre-roll + light denoise + RMS normalize · STT second-pass + strong-answer abstain</p>
<p class="meta">Generated: {esc(payload['created_at'])}</p>
<div>
  <div class="card"><span>Total</span><b>{summary.get('total')}</b></div>
  <div class="card"><span>PASS</span><b>{summary.get('passed')}</b></div>
  <div class="card"><span>Intent</span><b>{esc(summary.get('intent_success'))}</b></div>
  <div class="card"><span>HC wrong</span><b>{summary.get('high_confidence_wrong')}</b></div>
  <div class="card"><span>Avg RMS before</span><b>{esc((summary.get('audio_levels') or {}).get('avg_rms_before'))}</b></div>
  <div class="card"><span>Avg SNR dB</span><b>{esc((summary.get('audio_levels') or {}).get('avg_snr_db_est'))}</b></div>
  <div class="card"><span>Median post-speech</span><b>{lat.get('median_post_speech_ms')} ms</b></div>
  <div class="card"><span>p95 post-speech</span><b>{lat.get('p95_post_speech_ms')} ms</b></div>
  <div class="card"><span>Median wall</span><b>{lat.get('median_total_ms')} ms</b></div>
  <div class="card"><span>Avg VAD</span><b>{lat.get('avg_vad_ms')} ms</b></div>
  <div class="card"><span>Avg STT</span><b>{lat.get('avg_stt_ms')} ms</b></div>
  <div class="card"><span>Avg Intent</span><b>{lat.get('avg_intent_ms')} ms</b></div>
  <div class="card"><span>Avg Answer</span><b>{lat.get('avg_answer_ms')} ms</b></div>
</div>
<p><b>By condition intent:</b> {esc(json.dumps(summary.get('by_condition')))}</p>
<p><b>Compound:</b> {esc(json.dumps(summary.get('compound')))}</p>
<p><b>Failure stages:</b> {esc(json.dumps(summary.get('failure_stages')))}</p>
<table><thead><tr>
<th>Audio</th><th>STT</th><th>Intent</th><th>Answer</th>
<th>VAD ms</th><th>STT ms</th><th>Intent ms</th><th>Answer ms</th><th>Total ms</th>
<th>Recovered</th><th>Result</th><th>Stage</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
</body></html>"""
    html_path.write_text(body, encoding="utf-8")
    public_dir = (
        Path(__file__).resolve().parents[3]
        / "frontend"
        / "public"
        / "voice-drill"
    )
    try:
        public_dir.mkdir(parents=True, exist_ok=True)
        (public_dir / f"{report_stem}.html").write_text(body, encoding="utf-8")
        # Keep legacy filename pointing at stress report when applicable.
        if report_stem.endswith("STRESS_REPORT") or report_stem == "INTERVIEW_E2E_LOOPBACK_REPORT":
            (public_dir / "INTERVIEW_E2E_LOOPBACK_REPORT.html").write_text(body, encoding="utf-8")
    except OSError:
        pass
    desktop = Path.home() / "OneDrive" / "Desktop"
    try:
        if desktop.is_dir():
            (desktop / f"{report_stem}.html").write_text(body, encoding="utf-8")
    except OSError:
        pass
    return {
        "report_json": str(json_path),
        "report_html": str(html_path),
        "report_html_latest": str(html_path),
        "score_name": score_name,
        "suite": suite,
    }


async def run_e2e_suite(
    *,
    suite: str = "stress",
    limit: Optional[int] = None,
    pre_roll_ms: Optional[int] = None,
    post_roll_ms: Optional[int] = None,
    on_scored_clip: Optional[Callable[[int, Any], None]] = None,
) -> dict[str, Any]:
    suite = (suite or "stress").strip().lower()
    if suite not in {
        "stress",
        "realistic",
        "realistic_holdout",
        "realistic_holdout_v2",
        "extreme_combined",
        "long_accent",
        "short_length",
        "medium_length",
        "very_long_length",
        "final_unseen_holdout",
        "final_unseen_holdout_v2",
        "final_unseen_holdout_v3",
        "final_unseen_holdout_v4",
        "compound_dev",
        "generalization_dev",
        "v5_150_voice",
        "clean",
        "office_poor",
        "poor",
        "far",
    }:
        raise ValueError(f"Unknown suite: {suite}")

    question_bank.load(force=True)
    await warm_whisper_model()
    logger.info("E2E active STT: %s", active_stt_info())
    print(f"Active STT: {active_stt_info()}", flush=True)

    # Full warm-up BEFORE any scored clip — required for gate_valid / latency gates.
    from app.services.question_bank import embed_stats, reset_embed_stats
    from app.services.semantic_intent_index import semantic_intent_index
    from app.services.semantic_intent_recovery import rerank_stats, reset_rerank_stats
    from app.services.warm_start import is_system_warm, system_warm_state, warm_system

    reset_embed_stats()
    reset_rerank_stats()
    warm_timeout_s = 900.0
    t_warm0 = time.perf_counter()
    warm_completed = False
    try:
        await asyncio.wait_for(warm_system(probe_audio=False), timeout=warm_timeout_s)
        warm_completed = True
        logger.info("Semantic intent warm finished before E2E clips")
    except asyncio.TimeoutError:
        logger.warning(
            "System warm still running after %.0fs; continuing — gate_valid will fail",
            warm_timeout_s,
        )
    except Exception as exc:
        logger.warning("System warm failed: %s", exc)
    warm_snap = system_warm_state()
    alias_ready = (
        getattr(getattr(question_bank, "_index", None), "alias_matrix", None) is not None
    )
    sem_ready = (semantic_intent_index.ready)
    gate_valid = bool(
        warm_completed and is_system_warm() and alias_ready and sem_ready
    )
    warm_info: dict[str, Any] = {
        "warm_completed": warm_completed,
        "warm_wall_ms": round((time.perf_counter() - t_warm0) * 1000, 1),
        "warm_timeout_s": warm_timeout_s,
        "system_warm": (is_system_warm()),
        "alias_matrix_ready": alias_ready,
        "semantic_index_ready": sem_ready,
        "steps": dict(warm_snap.get("steps") or {}),
        "errors": dict(warm_snap.get("errors") or {}),
        "gate_valid": gate_valid,
    }
    print(
        f"WARM gate_valid={gate_valid} alias={alias_ready} sem={sem_ready} "
        f"wall_ms={warm_info['warm_wall_ms']}",
        flush=True,
    )

    metadata = load_metadata()
    # Frozen system: realistic recovery on realistic* + length packs (live path).
    enable_realistic_recovery = suite in {
        "realistic",
        "realistic_holdout",
        "realistic_holdout_v2",
        "long_accent",
        "short_length",
        "medium_length",
        "very_long_length",
        "final_unseen_holdout",
        "final_unseen_holdout_v2",
        "final_unseen_holdout_v3",
        "final_unseen_holdout_v4",
        "compound_dev",
        "generalization_dev",
        "v5_150_voice",
    }
    clip_timeout_s = 25.0
    if suite == "realistic":
        clip_limit = 100 if limit is None else limit
        clips = select_realistic_clips(metadata, limit=clip_limit)
        report_stem = "INTERVIEW_E2E_REALISTIC_REPORT"
        score_label = "Realistic Interview Score"
    elif suite == "realistic_holdout":
        clip_limit = 80 if limit is None else limit
        clips = select_realistic_holdout_clips(metadata, limit=clip_limit)
        report_stem = "INTERVIEW_E2E_REALISTIC_HOLDOUT_REPORT"
        score_label = "Realistic Holdout Score"
    elif suite == "realistic_holdout_v2":
        clip_limit = 100 if limit is None else limit
        clips = select_realistic_holdout_v2(metadata, per_condition=20, limit=clip_limit)
        report_stem = "INTERVIEW_E2E_REALISTIC_HOLDOUT_V2_REPORT"
        score_label = "Realistic Holdout V2 Score"
    elif suite == "extreme_combined":
        clip_limit = 30 if limit is None else limit
        clips = select_extreme_combined_clips(metadata, limit=clip_limit)
        report_stem = "EXTREME_STRESS_COMBINED_REPORT"
        score_label = "Extreme Stress Combined Score"
    elif suite == "long_accent":
        clip_limit = 40 if limit is None else limit
        clips = select_long_sentence_accent_clips(limit=clip_limit)
        report_stem = "LONG_SENTENCE_ACCENT_REPORT"
        score_label = "Long Sentence Accent Score"
        clip_timeout_s = 45.0
    elif suite == "short_length":
        clip_limit = 8 if limit is None else limit
        clips = select_length_category_clips("short", limit=clip_limit)
        report_stem = "LENGTH_SHORT_REGRESSION_REPORT"
        score_label = "Short Length Regression Score"
        clip_timeout_s = 20.0
    elif suite == "medium_length":
        clip_limit = 8 if limit is None else limit
        clips = select_length_category_clips("medium", limit=clip_limit)
        report_stem = "LENGTH_MEDIUM_REGRESSION_REPORT"
        score_label = "Medium Length Regression Score"
        clip_timeout_s = 30.0
    elif suite == "very_long_length":
        clip_limit = 8 if limit is None else limit
        clips = select_length_category_clips("very_long", limit=clip_limit)
        report_stem = "LENGTH_VERY_LONG_REGRESSION_REPORT"
        score_label = "Very Long Length Regression Score"
        clip_timeout_s = 75.0
    elif suite == "final_unseen_holdout":
        clip_limit = 120 if limit is None else limit
        clips = select_final_unseen_holdout_clips(include_warmup=True, limit=clip_limit)
        report_stem = "FINAL_UNSEEN_HOLDOUT_REPORT"
        score_label = "Final Unseen Holdout v1 VOIDED (debug only)"
        clip_timeout_s = 75.0
    elif suite == "final_unseen_holdout_v2":
        clip_limit = 120 if limit is None else limit
        clips = select_final_unseen_holdout_v2_clips(include_warmup=True, limit=clip_limit)
        report_stem = "FINAL_UNSEEN_HOLDOUT_V2_REPORT"
        score_label = "Final Unseen Holdout v2 (EVAL ONLY)"
        clip_timeout_s = 75.0
    elif suite == "final_unseen_holdout_v3":
        clip_limit = 120 if limit is None else limit
        clips = select_final_unseen_holdout_v3_clips(include_warmup=True, limit=clip_limit)
        report_stem = "FINAL_UNSEEN_HOLDOUT_V3_REPORT"
        score_label = "Final Unseen Holdout v3 (EVAL ONLY)"
        clip_timeout_s = 75.0
    elif suite == "final_unseen_holdout_v4":
        clip_limit = 120 if limit is None else limit
        clips = select_final_unseen_holdout_v4_clips(include_warmup=True, limit=clip_limit)
        report_stem = "FINAL_UNSEEN_HOLDOUT_V4_REPORT"
        score_label = "Final Unseen Holdout v4 (EVAL ONLY)"
        clip_timeout_s = 75.0
    elif suite == "compound_dev":
        clip_limit = 40 if limit is None else limit
        clips = select_compound_dev_clips(include_warmup=True, limit=clip_limit)
        report_stem = "COMPOUND_DEV_REPORT"
        score_label = "Compound Dev Track B"
        clip_timeout_s = 45.0
    elif suite == "generalization_dev":
        clip_limit = 60 if limit is None else limit
        clips = select_generalization_dev_clips(include_warmup=True, limit=clip_limit)
        report_stem = "GENERALIZATION_DEV_REPORT"
        score_label = "Generalization Dev Track C"
        clip_timeout_s = 45.0
    elif suite == "v5_150_voice":
        clip_limit = None if limit is None else limit
        clips = select_v5_150_voice_clips(limit=clip_limit)
        report_stem = "V5_150_VOICE_STRESS_E2E_REPORT"
        score_label = "V5 150 Voice Stress E2E (loopback)"
        clip_timeout_s = 45.0
    elif suite == "clean":
        clip_limit = 30 if limit is None else limit
        clips = select_clean_clips(metadata, limit=clip_limit)
        report_stem = "INTERVIEW_E2E_CLEAN_REPORT"
        score_label = "Clean E2E Score"
    elif suite == "office_poor":
        clip_limit = 60 if limit is None else limit
        clips = select_office_poor_clips(metadata, limit=clip_limit)
        report_stem = "INTERVIEW_E2E_OFFICE_POOR_REPORT"
        score_label = "Office + Poor Call Score"
    elif suite == "poor":
        clip_limit = 30 if limit is None else limit
        clips = select_poor_clips(metadata, limit=clip_limit)
        report_stem = "INTERVIEW_E2E_POOR_CALL_REPORT"
        score_label = "Poor Call Recovery Score"
    elif suite == "far":
        clip_limit = 30 if limit is None else limit
        clips = select_far_clips(metadata, limit=clip_limit)
        report_stem = "INTERVIEW_E2E_FAR_REPORT"
        score_label = "Far Diagnostic Score"
    else:
        clip_limit = 54 if limit is None else limit
        clips = select_stress_clips(metadata, limit=clip_limit)
        report_stem = "INTERVIEW_E2E_STRESS_REPORT"
        score_label = "Stress Test Score"

    session = LoopbackE2ESession(
        pre_roll_ms=pre_roll_ms,
        post_roll_ms=post_roll_ms,
        enable_realistic_recovery=enable_realistic_recovery,
    )
    results: list[E2EResult] = []
    try:
        await session.start()
        # Warm-up silence / device settle
        await asyncio.sleep(0.8)
        print(
            f"=== Running {score_label} ({suite}) · {len(clips)} clips "
            f"· pre_roll={session._router.pre_roll_ms}ms "
            f"· realistic_recovery={enable_realistic_recovery} ===",
            flush=True,
        )
        if suite == "realistic_holdout_v2":
            from collections import Counter

            print(
                "Holdout V2 mix:",
                dict(Counter(str(r.get("condition")) for r in clips)),
                "| packs:",
                dict(Counter(str(r.get("pack")) for r in clips)),
                flush=True,
            )
        if suite == "final_unseen_holdout":
            print(
                "VOIDED v1 pack — not an official adoption gate. "
                "Use --suite final_unseen_holdout_v2.",
                flush=True,
            )
        if suite == "final_unseen_holdout_v2":
            print(
                "FINAL UNSEEN HOLDOUT V2 — eval only · frozen settings · "
                "do not open report mid-run to retune.",
                flush=True,
            )
        if suite == "final_unseen_holdout_v3":
            print(
                "FINAL UNSEEN HOLDOUT V3 — eval only · frozen settings · "
                "do not open report mid-run to retune.",
                flush=True,
            )
        if suite == "final_unseen_holdout_v4":
            print(
                "FINAL UNSEEN HOLDOUT V4 — eval only · frozen settings · "
                "do not open report mid-run to retune.",
                flush=True,
            )
        scored_n = sum(1 for c in clips if not c.get("warmup"))
        scored_i = 0
        for i, row in enumerate(clips, start=1):
            result = await session.run_clip(row, timeout_s=clip_timeout_s)
            if row.get("warmup"):
                result.notes = f"warmup:{result.notes}"
                print(
                    f"[warm-up] {result.result} {row.get('sample_id')} "
                    f"(excluded from scored metrics)",
                    flush=True,
                )
                continue
            results.append(result)
            scored_i += 1
            if on_scored_clip is not None:
                on_scored_clip(scored_i, result)
            levels = result.audio_levels or {}
            if suite in {
                "final_unseen_holdout",
                "final_unseen_holdout_v2",
                "final_unseen_holdout_v3",
                "final_unseen_holdout_v4",
            }:
                print(
                    f"[{scored_i}/{scored_n}] {result.result} "
                    f"{result.question_type_label}/{result.speaker}/{result.condition} "
                    f"intent={result.intent_ok} hc_wrong={result.high_confidence_wrong} "
                    f"gold={result.holdout_gold_hit} gold_mm={result.gold_id_mismatch} "
                    f"post={result.timings.post_speech_ms:.0f}ms "
                    f"w={result.timings.whisper_ms:.0f}/sem={result.timings.semantic_ms:.0f} "
                    f"stage={result.failure_stage or '-'}",
                    flush=True,
                )
            else:
                print(
                    f"[{i}/{len(clips)}] {result.result} Q{result.question_id} "
                    f"{result.speaker}/{result.condition} "
                    f"intent={result.intent_ok} hc_wrong={result.high_confidence_wrong} "
                    f"1st_miss={result.first_word_missing} "
                    f"pos={result.failure_position or '-'} "
                    f"rms={levels.get('rms_before')} snr={levels.get('snr_db_est')} "
                    f"src={result.better_audio_source} "
                    f"post={result.timings.post_speech_ms:.0f}ms "
                    f"stage={result.failure_stage or '-'}",
                    flush=True,
                )
    finally:
        await session.stop()

    filters = {
        "mode": "e2e_windows_loopback",
        "suite": suite,
        "score_name": score_label,
        "limit": clip_limit,
        "pre_roll_ms": session._router.pre_roll_ms,
        "post_roll_ms": getattr(session._router, "_post_roll_ms", None),
        "hard_questions": sorted(HARD_QUESTION_IDS),
        "audio_path": "pre_roll+speech+post_roll+stt_second_pass_on_doubt+strong_abstain",
        "eval_only": suite
        in {
            "final_unseen_holdout",
            "final_unseen_holdout_v2",
            "final_unseen_holdout_v3",
            "final_unseen_holdout_v4",
            "compound_dev",
            "generalization_dev",
        },
        "voided_holdout": suite == "final_unseen_holdout",
        "track_b": suite == "compound_dev",
        "track_c": suite == "generalization_dev",
        "warm": warm_info,
        "gate_valid": bool(warm_info.get("gate_valid")),
        "embed_stats": embed_stats(),
        "rerank_stats": rerank_stats(),
    }
    summary = summarize(results)
    summary["score_name"] = score_label
    summary["suite"] = suite
    summary["pre_roll_ms"] = session._router.pre_roll_ms
    if suite == "long_accent":
        summary["by_accent"] = summarize_by_accent(results)
    if suite == "final_unseen_holdout":
        paths = write_final_unseen_holdout_report(
            results,
            summary,
            filters,
            suite=suite,
            stem="FINAL_UNSEEN_HOLDOUT_REPORT",
        )
    elif suite == "final_unseen_holdout_v2":
        paths = write_final_unseen_holdout_report(
            results,
            summary,
            filters,
            suite=suite,
            stem="FINAL_UNSEEN_HOLDOUT_V2_REPORT",
        )
    elif suite == "final_unseen_holdout_v3":
        paths = write_final_unseen_holdout_report(
            results,
            summary,
            filters,
            suite=suite,
            stem="FINAL_UNSEEN_HOLDOUT_V3_REPORT",
        )
    elif suite == "final_unseen_holdout_v4":
        paths = write_final_unseen_holdout_report(
            results,
            summary,
            filters,
            suite=suite,
            stem="FINAL_UNSEEN_HOLDOUT_V4_REPORT",
        )
    elif suite == "compound_dev":
        paths = write_compound_dev_report(results, summary, filters)
    elif suite == "generalization_dev":
        paths = write_generalization_dev_report(results, summary, filters)
    else:
        paths = write_reports(results, summary, filters, report_stem=report_stem)
    return {
        "summary": summary,
        "results": [asdict(r) for r in results],
        **paths,
        "filters": filters,
        "score_name": score_label,
        "suite": suite,
    }


async def run_e2e_both(*, stress_limit: Optional[int] = None, realistic_limit: Optional[int] = None) -> dict[str, Any]:
    """Run Stress then Realistic and return both report payloads."""
    stress = await run_e2e_suite(suite="stress", limit=stress_limit)
    realistic = await run_e2e_suite(suite="realistic", limit=realistic_limit)
    return {"stress": stress, "realistic": realistic}
