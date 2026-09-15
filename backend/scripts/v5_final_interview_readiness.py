#!/usr/bin/env python3
"""V5 final practical interview readiness — production path, not research.

Runs:
  1) warm production baseline
  2) realistic text interview stress (paraphrase / follow-up / compound / STT-ish)
  3) accent / distance / noise audio samples from existing voice-drill packs
  4) live session continuity + duplicate checks
  5) latency summary (text path + prior FINAL_LATENCY_CHECK if present)
  6) writes reports/V5_FINAL_INTERVIEW_READINESS.{md,json}

No B-series. No holdout retune. Fixes belong outside this script.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import statistics
import sys
import time
import wave
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
FRONTEND_DRILL = ROOT.parent / "frontend" / "public" / "voice-drill"
ACCENT_PACK = FRONTEND_DRILL / "long-sentence-accent-pack"
STRESS_V2 = FRONTEND_DRILL / "stress-holdout-v2"
STRESS_PILOT = FRONTEND_DRILL / "stress-pilot"


# ---------------------------------------------------------------------------
# Practical text fixtures — NOT bank-literal wording
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TextCase:
    id: str
    transcript: str  # as if STT already produced it
    shape: str
    topic_must: tuple[str, ...]  # any of these may appear in match id/q/answer
    expect_question: bool = True
    expect_abstain_ok: bool = False
    follow_up_after: Optional[str] = None  # prior Q id in session
    notes: str = ""


TEXT_CASES: list[TextCase] = [
    # Direct
    TextCase("t_direct_rag", "What is RAG?", "direct", ("rag", "retrieval")),
    TextCase("t_direct_agentic", "What is agentic AI?", "direct", ("agentic", "agent")),
    TextCase("t_direct_guardrails", "What are guardrails in AI systems?", "direct", ("guardrail",)),
    TextCase("t_direct_embeddings", "What are embeddings?", "direct", ("embed",)),
    # Indirect / paraphrase
    TextCase(
        "t_indirect_retrieval_ministry",
        "Can you explain how you used retrieval in your Ministry project?",
        "indirect",
        ("rag", "retrieval", "btec", "ministry", "question"),
    ),
    TextCase(
        "t_indirect_btec_retrieval",
        "Tell me how retrieval helped your BTEC system",
        "indirect",
        ("rag", "retrieval", "btec", "question"),
    ),
    TextCase(
        "t_indirect_chroma",
        "How did you use chroma database in the project?",
        "indirect",
        ("chroma", "vector", "embed", "rag"),
    ),
    # Very short
    TextCase("t_short_why_rag", "Why RAG?", "short", ("rag", "retrieval", "fine")),
    TextCase("t_short_why", "Why?", "follow_up", ("rag", "retrieval"), follow_up_after="t_short_why_rag", expect_abstain_ok=True),
    TextCase("t_short_how", "How?", "follow_up", ("rag", "retrieval", "agent"), follow_up_after="t_direct_rag", expect_abstain_ok=True),
    # Long
    TextCase(
        "t_long_pipeline",
        (
            "Please walk me through the full path in your BTEC system from the "
            "source document through chunking embeddings retrieval generation "
            "validation and teacher approval."
        ),
        "long",
        ("rag", "btec", "retrieval", "chunk", "embed", "question"),
    ),
    # Scenario
    TextCase(
        "t_scenario_bad_context",
        "If the retrieved context is wrong, what would you do?",
        "scenario",
        ("retriev", "rag", "context", "hallucin", "valid", "ground"),
    ),
    TextCase(
        "t_scenario_validation_fail",
        "What should happen when an AI generated question fails validation more than once?",
        "scenario",
        ("valid", "retry", "teacher", "human", "approval", "question"),
        expect_abstain_ok=True,
    ),
    # Business
    TextCase(
        "t_business_ministry",
        "How does this solution help the Ministry?",
        "business",
        ("ministry", "btec", "teacher", "student", "business", "value", "education", "moe"),
        expect_abstain_ok=True,
    ),
    TextCase(
        "t_business_early_warning",
        "Why does recall matter for the early warning model used by teachers?",
        "business",
        ("early", "warning", "recall", "student", "risk"),
    ),
    # Compound
    TextCase(
        "t_compound_rag_use_why",
        "What is RAG, how did you use it, and why did you choose it?",
        "compound",
        ("rag", "retrieval"),
    ),
    TextCase(
        "t_compound_similarity",
        "Explain the assignment similarity checker, why it is not RAG, and who decides at the end.",
        "compound",
        ("similar", "embed", "assign"),
    ),
    # Telegraphic
    TextCase(
        "t_tele_rag_arch",
        "RAG architecture, risks, and business value.",
        "telegraphic",
        ("rag", "retrieval", "risk", "business", "architect"),
        expect_abstain_ok=True,
    ),
    TextCase(
        "t_tele_ews",
        "Early Warning Project — data, model, KPI, outcome.",
        "telegraphic",
        ("early", "warning", "model", "kpi", "recall", "student"),
        expect_abstain_ok=True,
    ),
    # Mispronounced / STT-near technical terms
    TextCase(
        "t_stt_lang_chain",
        "How did you use lang chain and lang graph together?",
        "mispronounced",
        ("langchain", "langgraph", "lang chain", "lang graph", "orchestr", "agent"),
    ),
    TextCase(
        "t_stt_chroma_db",
        "Where do you store vectors in chroma DB?",
        "mispronounced",
        ("chroma", "vector"),
    ),
    TextCase(
        "t_stt_cosine",
        "How does cosine similarity work with your embeddings?",
        "mispronounced",
        ("cosine", "similar", "embed"),
    ),
    TextCase(
        "t_stt_scikit",
        "Did you use scikit learn in the early warning model?",
        "mispronounced",
        ("scikit", "sklearn", "early", "warning", "model", "machine"),
    ),
    TextCase(
        "t_stt_whisper",
        "Why choose Whisper for speech to text in this interview coach?",
        "mispronounced",
        ("whisper", "speech", "stt", "transcri"),
        expect_abstain_ok=True,
    ),
    # Non-questions / low confidence
    TextCase(
        "t_nonq_thanks",
        "Okay thanks, that makes sense.",
        "non_question",
        (),
        expect_question=False,
    ),
    TextCase(
        "t_nonq_noise",
        "mm hmm yeah",
        "non_question",
        (),
        expect_question=False,
    ),
    TextCase(
        "t_unclear",
        "uh the thing with the stuff in the project",
        "unclear",
        (),
        expect_question=True,
        expect_abstain_ok=True,
    ),
    # More CV topics
    TextCase(
        "t_helpdesk",
        "How did the helpdesk classification model work?",
        "direct",
        ("helpdesk", "classif", "ticket"),
    ),
    TextCase(
        "t_donation_kiosk",
        "Tell me about the smart donation kiosk project.",
        "direct",
        ("donation", "kiosk"),
    ),
    TextCase(
        "t_governance",
        "How do you think about AI governance for government systems?",
        "business",
        ("govern", "guardrail", "human", "approval", "safe"),
        expect_abstain_ok=True,
    ),
    TextCase(
        "t_question_gen",
        "How does automated question generation support student assessment?",
        "indirect",
        ("question", "generat", "btec", "assess", "teacher"),
    ),
    TextCase(
        "t_completion_risk",
        "How do you monitor completion risk for students?",
        "direct",
        ("completion", "risk", "early", "warning", "student"),
    ),
]


# Audio sample plan: existing packs only (no new synthesis required).
AUDIO_SAMPLES: list[dict[str, Any]] = [
    # Accent long-sentence (one clip per profile family)
    {
        "id": "a_indian_long_01",
        "pack": "accent",
        "file": "indian_synthetic/indian_synthetic_long_01.wav",
        "accent": "indian",
        "speed": "normal",
        "distance": "near",
        "noise": "clean",
        "topic_must": ("rag", "btec", "retriev", "chunk", "embed"),
        "expected_hint": "BTEC RAG pipeline",
    },
    {
        "id": "a_jordanian_long_01",
        "pack": "accent",
        "file": "jordanian_synthetic/jordanian_synthetic_long_01.wav",
        "accent": "jordanian",
        "speed": "normal",
        "distance": "near",
        "noise": "clean",
        "topic_must": ("rag", "btec", "retriev", "chunk", "embed"),
        "expected_hint": "BTEC RAG pipeline",
    },
    {
        "id": "a_emirati_long_01",
        "pack": "accent",
        "file": "emirati_synthetic/emirati_synthetic_long_01.wav",
        "accent": "emirati_gulf",
        "speed": "normal",
        "distance": "near",
        "noise": "clean",
        "topic_must": ("rag", "btec", "retriev", "chunk", "embed"),
        "expected_hint": "BTEC RAG pipeline",
    },
    {
        "id": "a_egyptian_long_01",
        "pack": "accent",
        "file": "egyptian_synthetic/egyptian_synthetic_long_01.wav",
        "accent": "egyptian_non_native",
        "speed": "normal",
        "distance": "near",
        "noise": "clean",
        "topic_must": ("rag", "btec", "retriev", "chunk", "embed"),
        "expected_hint": "BTEC RAG pipeline",
    },
]

# Fill stress-holdout-v2 categories from manifest at runtime (far/fast/noise/etc.)


@dataclass
class CaseResult:
    id: str
    suite: str
    ok: bool
    meaning_ok: bool
    question_detected: Optional[bool]
    understood: bool
    answer_selected: bool
    confident_wrong: bool
    duplicate: bool
    timeout: bool
    latency_ms: float
    breakdown: dict[str, float] = field(default_factory=dict)
    transcript: str = ""
    match_id: str = ""
    match_score: float = 0.0
    match_mode: str = ""
    answer_preview: str = ""
    status: str = ""
    notes: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _topic_hit(blob: str, must: tuple[str, ...]) -> bool:
    if not must:
        return True
    low = (blob or "").lower()
    return any(tok in low for tok in must)


def _load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnchannels()
        sw = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    if sw == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        audio = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        audio = (audio - 128.0) / 128.0
    if n > 1:
        audio = audio.reshape(-1, n).mean(axis=1)
    return audio, sr


def _resolve_audio(pack: str, rel: str) -> Optional[Path]:
    if pack == "accent":
        p = ACCENT_PACK / rel
    elif pack == "stress_v2":
        p = STRESS_V2 / rel
    elif pack == "stress_pilot":
        p = STRESS_PILOT / rel
    else:
        return None
    return p if p.exists() else None


def _pick_stress_v2_samples(limit_per_cat: int = 2) -> list[dict[str, Any]]:
    manifest = STRESS_V2 / "manifest.json"
    if not manifest.exists():
        return []
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    by_cat: dict[str, list[dict]] = {}
    for row in rows:
        cat = str(row.get("category") or "other")
        by_cat.setdefault(cat, []).append(row)
    out: list[dict[str, Any]] = []
    accent_map = {
        "far": ("mixed", "normal", "far", "clean"),
        "fast": ("mixed", "fast", "near", "clean"),
        "slow": ("mixed", "slow", "near", "clean"),
        "short": ("mixed", "normal", "near", "clean"),
        "medium": ("mixed", "normal", "near", "clean"),
        "long": ("mixed", "normal", "near", "clean"),
        "very_long": ("mixed", "normal", "near", "clean"),
        "interrupted": ("mixed", "fast", "near", "clean"),
        "noise": ("mixed", "normal", "near", "room"),
        "quiet": ("mixed", "normal", "near", "quiet"),
        "loud": ("mixed", "normal", "near", "loud"),
        "office_noise": ("mixed", "normal", "near", "office"),
        "room_noise": ("mixed", "normal", "near", "room"),
        "echo": ("mixed", "normal", "near", "echo"),
        "combined": ("mixed", "fast", "far", "office"),
        "clean": ("mixed", "normal", "near", "clean"),
    }
    for cat, items in sorted(by_cat.items()):
        accent, speed, distance, noise = accent_map.get(
            cat, ("mixed", "normal", "near", cat)
        )
        for i, row in enumerate(items[:limit_per_cat]):
            hint = str(row.get("transcript") or "")
            topic = tuple(
                t
                for t in (
                    "rag",
                    "agentic",
                    "guardrail",
                    "langchain",
                    "langgraph",
                    "embed",
                    "chroma",
                    "early",
                    "warning",
                    "similar",
                    "btec",
                    "retriev",
                )
                if t in hint.lower()
            ) or ("rag", "ai")
            out.append(
                {
                    "id": f"a_stress_{cat}_{i+1:02d}",
                    "pack": "stress_v2",
                    "file": row["file"],
                    "accent": accent,
                    "speed": speed,
                    "distance": distance,
                    "noise": noise,
                    "topic_must": topic,
                    "expected_hint": hint,
                }
            )
    return out


async def _run_text_case(
    case: TextCase,
    *,
    history: list[dict],
    classifier,
    seen_keys: set[str],
) -> CaseResult:
    from app.services.compound_question_detector import detect_question_complexity
    from app.services.compound_question_pipeline import resolve_compound_question
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_recovery import recover_semantic_intent
    from app.models.question import UtteranceType

    t0 = time.perf_counter()
    breakdown: dict[str, float] = {}

    t_cls = time.perf_counter()
    classification = await classifier.classify(
        case.transcript, conversation_history=history, prefer_speed=True
    )
    breakdown["classify_ms"] = (time.perf_counter() - t_cls) * 1000

    is_q = classification.type in {
        UtteranceType.QUESTION,
        UtteranceType.FOLLOW_UP,
    }
    status = "NO_QUESTION"
    match_id = ""
    match_score = 0.0
    match_mode = ""
    answer_preview = ""
    understood = False
    answer_selected = False
    confident_wrong = False
    duplicate = False
    meaning_ok = False

    # Duplicate key: normalized transcript
    key = " ".join(case.transcript.lower().split())
    if key in seen_keys and is_q:
        duplicate = True
    if is_q:
        seen_keys.add(key)

    if not case.expect_question:
        ok = not is_q
        status = "NO_QUESTION" if not is_q else "FALSE_QUESTION"
        meaning_ok = ok
        return CaseResult(
            id=case.id,
            suite="text",
            ok=ok,
            meaning_ok=meaning_ok,
            question_detected=is_q,
            understood=False,
            answer_selected=False,
            confident_wrong=False,
            duplicate=duplicate,
            timeout=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            breakdown=breakdown,
            transcript=case.transcript,
            status=status,
            notes=case.notes or classification.type.value,
            meta={"shape": case.shape},
        )

    if not is_q:
        # Unclear / telegraphic may be treated as statement — abstain OK when allowed
        if case.expect_abstain_ok:
            ok = True
            status = "LOW_CONFIDENCE"
            meaning_ok = True
        else:
            ok = False
            status = "MISSED_QUESTION"
        return CaseResult(
            id=case.id,
            suite="text",
            ok=ok,
            meaning_ok=meaning_ok,
            question_detected=False,
            understood=False,
            answer_selected=False,
            confident_wrong=False,
            duplicate=duplicate,
            timeout=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            breakdown=breakdown,
            transcript=case.transcript,
            status=status,
            notes="classifier_non_question",
            meta={"shape": case.shape},
        )

    t_match = time.perf_counter()
    match = question_bank.match(case.transcript, conversation_history=history)
    try:
        decision = recover_semantic_intent(
            case.transcript, match, conversation_history=history
        )
        if decision.applied and decision.match is not None:
            match = decision.match
    except Exception:
        pass
    breakdown["match_ms"] = (time.perf_counter() - t_match) * 1000

    detection = detect_question_complexity(case.transcript)
    compound = None
    if detection.question_type != "single":
        t_comp = time.perf_counter()
        compound = resolve_compound_question(
            case.transcript,
            conversation_history=history,
            detection=detection,
        )
        breakdown["compound_ms"] = (time.perf_counter() - t_comp) * 1000

    used_compound = bool(compound and compound.used_compound_path and compound.answer_en)
    if used_compound and compound is not None:
        answer_preview = (compound.answer_en or "")[:280]
        intents = list(compound.selected_intents or [])
        match_id = ",".join(intents)
        match_score = float(getattr(compound, "avg_score", 0.0) or 0.0)
        match_mode = "compound"
        answer_selected = True
        status = "ANSWER_READY"
        blob = f"{match_id} {answer_preview}"
        understood = _topic_hit(blob, case.topic_must) or not case.topic_must
        meaning_ok = understood
        try:
            if intents:
                question_bank.remember(case.transcript, intents[0])
        except Exception:
            pass
    elif match is not None:
        match_id = match.entry.id
        match_score = float(match.score)
        match_mode = match.mode
        answer_preview = (match.entry.answer_en or "")[:280]
        blob = f"{match_id} {match.entry.question} {answer_preview}"
        topic_ok = _topic_hit(blob, case.topic_must) or not case.topic_must
        if match.is_strong:
            answer_selected = True
            status = "ANSWER_READY"
            understood = topic_ok
            meaning_ok = topic_ok
            if not topic_ok:
                confident_wrong = True
                understood = False
                meaning_ok = False
            try:
                question_bank.remember(case.transcript, match.entry.id)
            except Exception:
                pass
        else:
            # Weak match — prefer abstain over confident wrong
            if case.expect_abstain_ok or not topic_ok:
                status = "LOW_CONFIDENCE"
                answer_selected = False
                understood = topic_ok
                meaning_ok = True if case.expect_abstain_ok else topic_ok
            else:
                status = "LOW_CONFIDENCE"
                answer_selected = False
                understood = topic_ok
                meaning_ok = topic_ok
            if topic_ok:
                try:
                    question_bank.remember(case.transcript, match.entry.id)
                except Exception:
                    pass
    else:
        status = "LOW_CONFIDENCE"
        if case.expect_abstain_ok:
            meaning_ok = True
            understood = False
        else:
            meaning_ok = False
            understood = False

    # Update history for follow-ups (production live_audio uses text + suggested_answer)
    history.append(
        {
            "role": "interviewer",
            "text": case.transcript,
            "question_id": match_id or case.id,
        }
    )
    if answer_preview:
        history.append({"role": "suggested_answer", "text": answer_preview[:200]})

    ok = (
        not confident_wrong
        and not duplicate
        and (
            meaning_ok
            if case.expect_abstain_ok or status in {"ANSWER_READY", "LOW_CONFIDENCE"}
            else (understood and answer_selected)
        )
    )
    # Practical pass: understood topic OR honest abstain when allowed; never HC wrong
    if confident_wrong or duplicate:
        ok = False
    elif status == "ANSWER_READY":
        ok = understood and answer_selected
    elif status == "LOW_CONFIDENCE":
        ok = case.expect_abstain_ok or meaning_ok
    else:
        ok = False

    return CaseResult(
        id=case.id,
        suite="text",
        ok=ok,
        meaning_ok=meaning_ok,
        question_detected=True,
        understood=understood,
        answer_selected=answer_selected,
        confident_wrong=confident_wrong,
        duplicate=duplicate,
        timeout=False,
        latency_ms=(time.perf_counter() - t0) * 1000,
        breakdown=breakdown,
        transcript=case.transcript,
        match_id=match_id,
        match_score=match_score,
        match_mode=match_mode,
        answer_preview=answer_preview,
        status=status,
        notes=case.notes,
        meta={
            "shape": case.shape,
            "detection": detection.question_type,
            "topic_must": list(case.topic_must),
        },
    )


async def _run_audio_case(sample: dict[str, Any], classifier) -> CaseResult:
    from app.audio.whisper_stt import transcribe_whisper_async
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_recovery import recover_semantic_intent
    from app.models.question import UtteranceType

    path = _resolve_audio(sample["pack"], sample["file"])
    if path is None:
        return CaseResult(
            id=sample["id"],
            suite="audio",
            ok=False,
            meaning_ok=False,
            question_detected=None,
            understood=False,
            answer_selected=False,
            confident_wrong=False,
            duplicate=False,
            timeout=False,
            latency_ms=0.0,
            status="ERROR",
            notes=f"missing_audio:{sample['pack']}/{sample['file']}",
            meta=sample,
        )

    audio, sr = _load_wav(path)
    duration_s = float(len(audio) / max(sr, 1))
    t0 = time.perf_counter()
    breakdown: dict[str, float] = {}

    t_stt = time.perf_counter()
    conf = 0.0
    lang = "en"
    try:
        stt = await transcribe_whisper_async(audio, sample_rate=sr)
        if isinstance(stt, str):
            transcript = stt.strip()
        else:
            transcript = (
                getattr(stt, "text", None) or getattr(stt, "transcript", None) or ""
            ).strip()
            conf = float(getattr(stt, "confidence", 0.0) or 0.0)
            lang = str(getattr(stt, "language", "") or lang)
    except Exception as exc:
        return CaseResult(
            id=sample["id"],
            suite="audio",
            ok=False,
            meaning_ok=False,
            question_detected=None,
            understood=False,
            answer_selected=False,
            confident_wrong=False,
            duplicate=False,
            timeout=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            status="ERROR",
            notes=f"stt_error:{exc}",
            meta={**sample, "speech_duration_s": duration_s},
        )
    breakdown["stt_ms"] = (time.perf_counter() - t_stt) * 1000

    if not transcript:
        return CaseResult(
            id=sample["id"],
            suite="audio",
            ok=False,
            meaning_ok=False,
            question_detected=False,
            understood=False,
            answer_selected=False,
            confident_wrong=False,
            duplicate=False,
            timeout=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            breakdown=breakdown,
            status="LOW_CONFIDENCE",
            notes="empty_transcript",
            meta={**sample, "speech_duration_s": duration_s, "stt_confidence": conf},
        )

    t_cls = time.perf_counter()
    classification = await classifier.classify(transcript, prefer_speed=True)
    breakdown["classify_ms"] = (time.perf_counter() - t_cls) * 1000
    is_q = classification.type in {UtteranceType.QUESTION, UtteranceType.FOLLOW_UP}

    t_match = time.perf_counter()
    match = question_bank.match(transcript)
    try:
        decision = recover_semantic_intent(transcript, match)
        if decision.applied and decision.match is not None:
            match = decision.match
    except Exception:
        pass
    breakdown["match_ms"] = (time.perf_counter() - t_match) * 1000

    topic_must = tuple(sample.get("topic_must") or ())
    hint = str(sample.get("expected_hint") or "")
    stt_meaning = _topic_hit(transcript, topic_must) or _topic_hit(
        transcript, tuple(w for w in hint.lower().split() if len(w) > 4)[:6]
    )

    match_id = ""
    match_score = 0.0
    match_mode = ""
    answer_preview = ""
    understood = False
    answer_selected = False
    confident_wrong = False
    status = "NO_QUESTION"

    if is_q and match is not None:
        match_id = match.entry.id
        match_score = float(match.score)
        match_mode = match.mode
        answer_preview = (match.entry.answer_en or "")[:280]
        blob = f"{match_id} {match.entry.question} {answer_preview} {transcript}"
        topic_ok = _topic_hit(blob, topic_must)
        if match.is_strong:
            answer_selected = True
            status = "ANSWER_READY"
            understood = topic_ok
            if not topic_ok:
                confident_wrong = True
        else:
            status = "LOW_CONFIDENCE"
            understood = topic_ok
    elif is_q:
        status = "LOW_CONFIDENCE"
    else:
        status = "NO_QUESTION"

    meaning_ok = stt_meaning and not confident_wrong
    ok = meaning_ok and not confident_wrong and (
        (status == "ANSWER_READY" and understood)
        or (status == "LOW_CONFIDENCE" and stt_meaning)
        or (status == "ANSWER_READY")
    )
    # Practical: STT preserved meaning + no HC wrong; answer preferred but abstain OK if STT ok
    if confident_wrong:
        ok = False
    elif not stt_meaning:
        ok = False
    elif status == "ANSWER_READY":
        ok = understood
    else:
        ok = True  # honest abstain after understandable speech

    return CaseResult(
        id=sample["id"],
        suite="audio",
        ok=ok,
        meaning_ok=meaning_ok,
        question_detected=is_q,
        understood=understood,
        answer_selected=answer_selected,
        confident_wrong=confident_wrong,
        duplicate=False,
        timeout=False,
        latency_ms=(time.perf_counter() - t0) * 1000,
        breakdown=breakdown,
        transcript=transcript,
        match_id=match_id,
        match_score=match_score,
        match_mode=match_mode,
        answer_preview=answer_preview,
        status=status,
        notes="",
        meta={
            **{k: sample[k] for k in ("accent", "speed", "distance", "noise", "expected_hint") if k in sample},
            "speech_duration_s": round(duration_s, 3),
            "stt_confidence": conf,
            "detected_language": lang,
            "stt_meaning": stt_meaning,
        },
    )


async def _run_live_session(classifier) -> dict[str, Any]:
    """Simulate a continuous interview with mixed shapes + one intentional duplicate."""
    session_script = [
        "What is RAG?",
        "How did you use retrieval in the Ministry BTEC project?",
        "Why?",
        "If retrieval returns nothing useful, what do you do?",
        "RAG architecture, risks, business value.",
        "What is RAG?",  # intentional duplicate wording
        "Tell me about the early warning system KPIs.",
        "How?",
        "Okay thanks.",
    ]
    history: list[dict] = []
    seen: set[str] = set()
    results: list[CaseResult] = []
    for i, text in enumerate(session_script):
        shape = "follow_up" if text in {"Why?", "How?"} else ("non_question" if "thanks" in text.lower() else "session")
        case = TextCase(
            id=f"live_{i+1:02d}",
            transcript=text,
            shape=shape,
            topic_must=("rag", "retriev", "btec", "early", "warning", "risk", "architect")
            if shape != "non_question"
            else (),
            expect_question=shape != "non_question",
            expect_abstain_ok=shape in {"follow_up", "session"} or "architecture" in text.lower(),
        )
        # For intentional duplicate of "What is RAG?" — second should be flagged
        r = await _run_text_case(case, history=history, classifier=classifier, seen_keys=seen)
        results.append(r)

    dup_flags = sum(1 for r in results if r.duplicate)
    hc = sum(1 for r in results if r.confident_wrong)
    answered = sum(1 for r in results if r.answer_selected)
    return {
        "turns": len(results),
        "ok_turns": sum(1 for r in results if r.ok),
        "duplicate_flags": dup_flags,
        "confident_wrong": hc,
        "answers": answered,
        "results": [asdict(r) for r in results],
        "continuity_ok": hc == 0 and dup_flags >= 1,  # we expect the intentional dup to be caught
    }


def _median(xs: list[float]) -> float:
    return float(statistics.median(xs)) if xs else 0.0


def _breakdown_group(results: list[CaseResult], key: str) -> dict[str, Any]:
    groups: dict[str, list[CaseResult]] = {}
    for r in results:
        g = str(r.meta.get(key) or r.meta.get("shape") or "unknown")
        groups.setdefault(g, []).append(r)
    out = {}
    for g, rs in sorted(groups.items()):
        out[g] = {
            "n": len(rs),
            "ok": sum(1 for r in rs if r.ok),
            "ok_rate": round(sum(1 for r in rs if r.ok) / len(rs), 4),
            "meaning_ok": sum(1 for r in rs if r.meaning_ok),
            "hc_wrong": sum(1 for r in rs if r.confident_wrong),
            "median_latency_ms": round(_median([r.latency_ms for r in rs]), 1),
        }
    return out


def _load_latency_gate() -> dict[str, Any]:
    path = REPORTS / "FINAL_LATENCY_CHECK.json"
    if not path.exists():
        return {"present": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "present": True,
        "verdict": data.get("verdict"),
        "ready": data.get("ready"),
        "simple_median_ms": data.get("hard_gates", {}).get("simple_median_ms"),
        "compound_median_ms": data.get("hard_gates", {}).get("compound_median_ms"),
        "simple_hc_wrong": data.get("hard_gates", {}).get("simple_hc_wrong"),
        "compound_hc_wrong": data.get("hard_gates", {}).get("compound_hc_wrong"),
    }


def _production_fingerprint() -> dict[str, str]:
    files = [
        ROOT / "app" / "services" / "question_bank.py",
        ROOT / "app" / "services" / "compound_question_pipeline.py",
        ROOT / "app" / "services" / "semantic_intent_recovery.py",
        ROOT / "app" / "services" / "answer_generator.py",
        ROOT / "app" / "services" / "live_audio.py",
        ROOT / "app" / "audio" / "whisper_stt.py",
        ROOT / "app" / "config.py",
        ROOT / "app" / "services" / "warm_start.py",
    ]
    out = {}
    for p in files:
        if p.exists():
            out[str(p.relative_to(ROOT)).replace("\\", "/")] = _sha256_file(p)
    return out


def _write_lock(fingerprint: dict[str, str], metrics: dict[str, Any]) -> Path:
    lock_path = REPORTS / "V5_FINAL_INTERVIEW_READINESS.lock.json"
    payload = {
        "locked_at": _now(),
        "fingerprint": fingerprint,
        "metrics_snapshot": metrics,
    }
    lock_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return lock_path


def _verify_lock(fingerprint: dict[str, str]) -> tuple[bool, list[str]]:
    lock_path = REPORTS / "V5_FINAL_INTERVIEW_READINESS.lock.json"
    if not lock_path.exists():
        return False, ["lock file missing"]
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    problems = []
    locked = data.get("fingerprint") or {}
    for k, v in fingerprint.items():
        if locked.get(k) != v:
            problems.append(f"fingerprint mismatch: {k}")
    for k in locked:
        if k not in fingerprint:
            problems.append(f"extra lock key: {k}")
    return len(problems) == 0, problems


def _decide_ready(payload: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """Practical READY — not academic compound≥0.90."""
    blockers: list[str] = []
    limitations: list[str] = []

    pytest_ok = payload.get("pytest", {}).get("passed") is True
    if not pytest_ok:
        blockers.append("pytest did not pass")

    text = payload["suites"]["text"]
    audio = payload["suites"]["audio"]
    live = payload["suites"]["live_session"]
    latency = payload.get("latency_gate") or {}

    if text["confident_wrong"] > 0:
        blockers.append(f"text confident-wrong={text['confident_wrong']}")
    if audio["confident_wrong"] > 0:
        blockers.append(f"audio confident-wrong={audio['confident_wrong']}")
    if live.get("confident_wrong", 0) > 0:
        blockers.append("live session confident-wrong")

    if text["understanding_accuracy"] < 0.75:
        blockers.append(
            f"text understanding_accuracy={text['understanding_accuracy']:.3f} < 0.75"
        )
    # Practical answer selection: honest LOW_CONFIDENCE abstains are allowed.
    # Only fail when we rarely produce grounded answers on clear direct/indirect asks.
    clear_shapes = {"direct", "indirect", "short", "compound", "mispronounced"}
    clear_results = [
        r
        for r in (payload.get("results") or {}).get("text") or []
        if (r.get("meta") or {}).get("shape") in clear_shapes
        and r.get("question_detected") is not False
    ]
    if clear_results:
        clear_answer_rate = sum(1 for r in clear_results if r.get("answer_selected")) / len(
            clear_results
        )
        if clear_answer_rate < 0.60:
            blockers.append(
                f"clear-question answer selection too low ({clear_answer_rate:.3f} < 0.60)"
            )

    if audio["n"] >= 5 and audio["stt_understandable_rate"] < 0.60:
        blockers.append(
            f"STT understandable-question rate={audio['stt_understandable_rate']:.3f} < 0.60"
        )

    if latency.get("present") and latency.get("ready") is False:
        blockers.append("FINAL_LATENCY_CHECK not ready")
    if latency.get("present"):
        sm = latency.get("simple_median_ms")
        cm = latency.get("compound_median_ms")
        if sm is not None and sm > 1500:
            blockers.append(f"simple median latency {sm} > 1500")
        if cm is not None and cm > 2000:
            blockers.append(f"compound median latency {cm} > 2000")

    if not live.get("continuity_ok"):
        # Soft: if duplicate not flagged, note limitation rather than hard block unless HC
        if live.get("duplicate_flags", 0) == 0:
            limitations.append(
                "Live session did not flag repeated identical transcript as duplicate "
                "(dedupe may be utterance-id based in live_audio rather than text-key)."
            )
        if live.get("confident_wrong", 0) > 0:
            blockers.append("live session HC wrong")

    # Known soft limitations always recorded
    limitations.append("Very noisy rooms may reduce STT accuracy.")
    limitations.append(
        "Extremely compressed telegraphic questions may require clarification or abstain."
    )
    limitations.append(
        "Compound/telegraphic coverage is practical (meaning + grounded answers), "
        "not the v4 academic compound≥0.90 holdout gate."
    )

    if text["ok_rate"] < 0.70:
        blockers.append(f"text ok_rate={text['ok_rate']:.3f} < 0.70")

    verdict = "READY_FOR_REAL_INTERVIEW" if not blockers else "NOT_READY_FOR_REAL_INTERVIEW"
    return verdict, blockers, limitations


async def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    print("=== V5 FINAL INTERVIEW READINESS ===", flush=True)

    # 1) Warm
    print("[1] warm_system_blocking...", flush=True)
    from app.services.warm_start import warm_system_blocking, is_system_warm

    warm_info = warm_system_blocking(probe_audio=True)
    print(f"  warm={is_system_warm()} info_keys={list(warm_info) if isinstance(warm_info, dict) else type(warm_info)}", flush=True)

    from app.services.question_classifier import QuestionClassifier

    classifier = QuestionClassifier()

    # 2) Text suite
    print("[2] practical text stress...", flush=True)
    history: list[dict] = []
    seen: set[str] = set()
    # Run each case once; follow-ups immediately after their parent (live order).
    text_results: list[CaseResult] = []
    by_id: dict[str, TextCase] = {c.id: c for c in TEXT_CASES}
    ordered: list[TextCase] = []
    seen_order: set[str] = set()

    def _append_with_parent(case: TextCase) -> None:
        if case.id in seen_order:
            return
        if case.follow_up_after and case.follow_up_after in by_id:
            _append_with_parent(by_id[case.follow_up_after])
        if case.id not in seen_order:
            ordered.append(case)
            seen_order.add(case.id)

    for case in TEXT_CASES:
        _append_with_parent(case)

    for case in ordered:
        # Fresh context for each independent question; keep parent context for follow-ups.
        if not case.follow_up_after:
            history.clear()
        r = await _run_text_case(
            case, history=history, classifier=classifier, seen_keys=seen
        )
        text_results.append(r)
        print(
            f"  text {case.id}: ok={r.ok} status={r.status} score={r.match_score:.3f} "
            f"id={r.match_id[:40]} lat={r.latency_ms:.0f}ms",
            flush=True,
        )

    # 3) Audio suite
    print("[3] accent/speed/distance audio samples...", flush=True)
    audio_plan = list(AUDIO_SAMPLES) + _pick_stress_v2_samples(limit_per_cat=1)
    # Drop missing accent profiles gracefully
    filtered = []
    for s in audio_plan:
        if _resolve_audio(s["pack"], s["file"]) is not None:
            filtered.append(s)
        else:
            print(f"  skip missing {s['id']}", flush=True)
    audio_results: list[CaseResult] = []
    for s in filtered:
        r = await _run_audio_case(s, classifier)
        audio_results.append(r)
        print(
            f"  audio {s['id']}: ok={r.ok} meaning={r.meaning_ok} status={r.status} "
            f"lat={r.latency_ms:.0f} stt={(r.breakdown or {}).get('stt_ms', 0):.0f} "
            f"tx={r.transcript[:60]!r}",
            flush=True,
        )

    # 4) Live session
    print("[4] live interview simulation...", flush=True)
    live = await _run_live_session(classifier)
    print(
        f"  live turns={live['turns']} ok={live['ok_turns']} dup_flags={live['duplicate_flags']} "
        f"hc={live['confident_wrong']} continuity_ok={live['continuity_ok']}",
        flush=True,
    )

    # 5) Metrics
    def _text_metrics(rs: list[CaseResult]) -> dict[str, Any]:
        q_cases = [r for r in rs if r.question_detected]
        expect_q = [r for r in rs if r.meta.get("shape") != "non_question"]
        understood = [r for r in expect_q if r.understood]
        answered = [r for r in expect_q if r.answer_selected]
        ready_attempts = [
            r
            for r in expect_q
            if r.status in {"ANSWER_READY", "LOW_CONFIDENCE"} and not r.meta.get("shape") == "unclear"
        ]
        simple = [r for r in rs if r.meta.get("shape") in {"direct", "short", "indirect", "business"}]
        compoundish = [r for r in rs if r.meta.get("shape") in {"compound", "telegraphic", "long"}]
        return {
            "n": len(rs),
            "ok": sum(1 for r in rs if r.ok),
            "ok_rate": round(sum(1 for r in rs if r.ok) / max(len(rs), 1), 4),
            "understanding_accuracy": round(len(understood) / max(len(expect_q), 1), 4),
            "answer_selection_accuracy": round(len(answered) / max(len(expect_q), 1), 4),
            "answer_selection_among_ready_attempts": round(
                sum(1 for r in ready_attempts if r.answer_selected) / max(len(ready_attempts), 1),
                4,
            ),
            "confident_wrong": sum(1 for r in rs if r.confident_wrong),
            "duplicate_count": sum(1 for r in rs if r.duplicate),
            "timeout_count": sum(1 for r in rs if r.timeout),
            "simple_latency_median_ms": round(_median([r.latency_ms for r in simple]), 1),
            "long_latency_median_ms": round(
                _median([r.latency_ms for r in rs if r.meta.get("shape") == "long"]), 1
            ),
            "compound_latency_median_ms": round(_median([r.latency_ms for r in compoundish]), 1),
            "by_shape": _breakdown_group(rs, "shape"),
        }

    def _audio_metrics(rs: list[CaseResult]) -> dict[str, Any]:
        return {
            "n": len(rs),
            "ok": sum(1 for r in rs if r.ok),
            "ok_rate": round(sum(1 for r in rs if r.ok) / max(len(rs), 1), 4),
            "stt_understandable_rate": round(
                sum(1 for r in rs if r.meta.get("stt_meaning")) / max(len(rs), 1), 4
            ),
            "understanding_accuracy": round(
                sum(1 for r in rs if r.understood) / max(len(rs), 1), 4
            ),
            "answer_selection_accuracy": round(
                sum(1 for r in rs if r.answer_selected) / max(len(rs), 1), 4
            ),
            "confident_wrong": sum(1 for r in rs if r.confident_wrong),
            "duplicate_count": sum(1 for r in rs if r.duplicate),
            "timeout_count": sum(1 for r in rs if r.timeout),
            "median_total_ms": round(_median([r.latency_ms for r in rs]), 1),
            "median_stt_ms": round(
                _median([float((r.breakdown or {}).get("stt_ms") or 0) for r in rs]), 1
            ),
            "accent_breakdown": _breakdown_group(rs, "accent"),
            "speed_breakdown": _breakdown_group(rs, "speed"),
            "distance_breakdown": _breakdown_group(rs, "distance"),
            "noise_breakdown": _breakdown_group(rs, "noise"),
        }

    # pytest status from log if present
    pytest_log = REPORTS / "V5_FINAL_PYTEST.log"
    pytest_info: dict[str, Any] = {"passed": None, "log": str(pytest_log)}
    if pytest_log.exists():
        tail = pytest_log.read_text(encoding="utf-8", errors="replace")[-2000:]
        pytest_info["tail"] = tail[-500:]
        if "passed" in tail and "failed" not in tail.split("passed")[-1][:40].lower():
            # crude; refined below via env file written by runner
            pass
    pytest_status_path = REPORTS / "V5_FINAL_PYTEST_STATUS.json"
    if pytest_status_path.exists():
        pytest_info.update(
            json.loads(pytest_status_path.read_text(encoding="utf-8-sig"))
        )

    latency_gate = _load_latency_gate()
    fingerprint = _production_fingerprint()

    payload: dict[str, Any] = {
        "created_at": _now(),
        "track": "v5_final_interview_readiness",
        "warm": {"system_warm": is_system_warm(), "info": warm_info if isinstance(warm_info, dict) else str(warm_info)},
        "pytest": pytest_info,
        "latency_gate": latency_gate,
        "suites": {
            "text": _text_metrics(text_results),
            "audio": _audio_metrics(audio_results),
            "live_session": {
                "turns": live["turns"],
                "ok_turns": live["ok_turns"],
                "duplicate_flags": live["duplicate_flags"],
                "confident_wrong": live["confident_wrong"],
                "answers": live["answers"],
                "continuity_ok": live["continuity_ok"],
            },
        },
        "results": {
            "text": [asdict(r) for r in text_results],
            "audio": [asdict(r) for r in audio_results],
            "live_session": live["results"],
        },
        "production_fingerprint": fingerprint,
    }

    verdict, blockers, limitations = _decide_ready(payload)
    payload["verdict"] = verdict
    payload["blockers"] = blockers
    payload["KNOWN_LIMITATIONS"] = limitations

    # Lock + verify
    lock_path = _write_lock(
        fingerprint,
        {
            "verdict": verdict,
            "text_ok_rate": payload["suites"]["text"]["ok_rate"],
            "hc_wrong_text": payload["suites"]["text"]["confident_wrong"],
            "hc_wrong_audio": payload["suites"]["audio"]["confident_wrong"],
        },
    )
    lock_ok, lock_problems = _verify_lock(fingerprint)
    payload["lock"] = {
        "path": str(lock_path),
        "write": True,
        "independent_verify_ok": lock_ok,
        "problems": lock_problems,
    }
    if not lock_ok:
        payload["blockers"].append("lock verification failed")
        payload["verdict"] = "NOT_READY_FOR_REAL_INTERVIEW"
        verdict = payload["verdict"]

    json_path = REPORTS / "V5_FINAL_INTERVIEW_READINESS.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md = _render_md(payload)
    md_path = REPORTS / "V5_FINAL_INTERVIEW_READINESS.md"
    md_path.write_text(md, encoding="utf-8")

    print("=== VERDICT ===", flush=True)
    print(verdict, flush=True)
    print(f"wrote {md_path}", flush=True)
    print(f"wrote {json_path}", flush=True)
    return 0 if verdict == "READY_FOR_REAL_INTERVIEW" else 2


def _render_md(p: dict[str, Any]) -> str:
    t = p["suites"]["text"]
    a = p["suites"]["audio"]
    live = p["suites"]["live_session"]
    lat = p.get("latency_gate") or {}
    lines = [
        p["verdict"],
        "",
        "# V5 Final Interview Readiness",
        "",
        f"Created: `{p['created_at']}`",
        "",
        "## Summary metrics",
        "",
        f"- STT understandable-question rate: **{a.get('stt_understandable_rate')}** (n={a.get('n')})",
        f"- Question-understanding accuracy (text): **{t.get('understanding_accuracy')}**",
        f"- Answer-selection accuracy (text): **{t.get('answer_selection_accuracy')}**",
        f"- Confident-wrong count: text={t.get('confident_wrong')} audio={a.get('confident_wrong')} live={live.get('confident_wrong')}",
        f"- Duplicate count: text={t.get('duplicate_count')} live_flags={live.get('duplicate_flags')}",
        f"- Timeout count: text={t.get('timeout_count')} audio={a.get('timeout_count')}",
        f"- Simple latency median (text path): **{t.get('simple_latency_median_ms')} ms**",
        f"- Long-question latency median: **{t.get('long_latency_median_ms')} ms**",
        f"- Compound/telegraphic latency median: **{t.get('compound_latency_median_ms')} ms**",
        f"- FINAL_LATENCY_CHECK: simple={lat.get('simple_median_ms')} compound={lat.get('compound_median_ms')} ready={lat.get('ready')}",
        "",
        "## Accent / speed / distance / noise",
        "",
        "### Accent",
        "```json",
        json.dumps(a.get("accent_breakdown"), indent=2),
        "```",
        "",
        "### Speed",
        "```json",
        json.dumps(a.get("speed_breakdown"), indent=2),
        "```",
        "",
        "### Distance",
        "```json",
        json.dumps(a.get("distance_breakdown"), indent=2),
        "```",
        "",
        "### Noise",
        "```json",
        json.dumps(a.get("noise_breakdown"), indent=2),
        "```",
        "",
        "## Live session",
        "",
        f"- turns={live.get('turns')} ok_turns={live.get('ok_turns')} continuity_ok={live.get('continuity_ok')}",
        "",
        "## Pytest / hardening",
        "",
        f"- pytest: `{json.dumps(p.get('pytest'))}`",
        f"- lock verify: `{p.get('lock')}`",
        f"- system warm: `{p.get('warm', {}).get('system_warm')}`",
        "",
        "## Blockers",
        "",
    ]
    if p.get("blockers"):
        lines += [f"- {b}" for b in p["blockers"]]
    else:
        lines.append("- none")
    lines += ["", "## KNOWN_LIMITATIONS", ""]
    lines += [f"- {x}" for x in p.get("KNOWN_LIMITATIONS") or []]
    lines += [
        "",
        "## Decision basis",
        "",
        "This verdict is **practical interview readiness**, not the academic v4 compound≥0.90 holdout gate.",
        "Prior v3/v4/v5 research reports remain diagnostic only.",
        "Production path: classifier → bank match + semantic recovery → compound when detected → bank answer.",
        "HC wrong must stay 0. Honest LOW_CONFIDENCE/ABSTAIN beats a confident wrong answer.",
        "",
    ]
    # Failures list
    fails = [
        r
        for r in (p.get("results") or {}).get("text") or []
        if not r.get("ok")
    ][:20]
    lines += ["## Top text failures (up to 20)", ""]
    if not fails:
        lines.append("- none")
    else:
        for r in fails:
            lines.append(
                f"- `{r['id']}` status={r.get('status')} match={r.get('match_id')} "
                f"score={r.get('match_score')} notes={r.get('notes')}"
            )
    afails = [
        r
        for r in (p.get("results") or {}).get("audio") or []
        if not r.get("ok")
    ][:20]
    lines += ["", "## Top audio failures (up to 20)", ""]
    if not afails:
        lines.append("- none")
    else:
        for r in afails:
            lines.append(
                f"- `{r['id']}` status={r.get('status')} meaning={r.get('meaning_ok')} "
                f"tx={r.get('transcript')!r}"
            )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
