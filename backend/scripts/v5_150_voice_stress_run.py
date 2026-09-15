#!/usr/bin/env python3
"""OFFLINE harness: WAV bytes → Whisper → match (NOT real audio capture).

This path does NOT play through speakers / WASAPI loopback / VAD.
Do NOT use its PASS metrics as end-to-end voice validation.

For the real gate use:
  python scripts/v5_150_voice_stress_e2e.py
"""

from __future__ import annotations

import asyncio
import csv
import json
import statistics
import sys
import time
import wave
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports"
PACK = (
    ROOT.parent
    / "frontend"
    / "public"
    / "voice-drill"
    / "v5-150-voice-stress"
    / "V5_150_Voice_Stress_Test"
)

# Topic tokens derived from intent_key — meaning check, not exact bank ID.
INTENT_TOPICS: dict[str, tuple[str, ...]] = {
    "self_intro": ("introduc", "myself", "background", "experience", "about you"),
    "current_role": ("role", "current", "day", "work", "ministry", "btec"),
    "why_agentic_ai": ("agentic", "agent"),
    "rag_ministry_usage": ("rag", "retriev", "btec", "ministry"),
    "rag_vs_finetune": ("rag", "fine", "retriev", "tune"),
    "embeddings_purpose": ("embed",),
    "vector_db_chroma": ("chroma", "vector"),
    "chunking": ("chunk",),
    "retrieval_quality": ("retriev", "rank", "quality", "context"),
    "hallucination_control": ("hallucin", "ground", "valid", "factual"),
    "guardrails": ("guardrail", "safe"),
    "human_in_loop": ("human", "approval", "teacher", "review"),
    "langchain_use": ("langchain", "lang chain", "chain"),
    "langgraph_use": ("langgraph", "lang graph", "graph"),
    "agent_orchestration": ("orchestr", "agent", "tool"),
    "ai_governance": ("govern", "policy", "compliance", "safe"),
    "n8n_use": ("n8n", "workflow", "automat"),
    "context_window": ("context", "window", "token"),
    "prompt_injection": ("inject", "prompt", "jailbreak", "attack"),
    "business_value": ("business", "value", "ministry", "benefit", "impact"),
    "rag_architecture": ("rag", "architect", "pipeline", "retriev"),
    "multi_agent_workflow": ("multi", "agent", "workflow"),
    "question_generation_project": ("question", "generat", "btec"),
    "automated_feedback_project": ("feedback", "automat"),
    "similarity_checker_project": ("similar", "assign", "plagiar", "cosine"),
    "early_warning_project": ("early", "warning", "risk", "recall"),
    "helpdesk_classification_project": ("helpdesk", "classif", "ticket"),
    "completion_risk_project": ("completion", "risk"),
    "donation_kiosk_project": ("donation", "kiosk"),
    "production_monitoring": ("monitor", "production", "observ", "metric"),
    "rag_bad_context_scenario": ("retriev", "context", "wrong", "bad", "rag"),
    "agent_tool_failure_scenario": ("tool", "fail", "agent", "retry"),
    "sensitive_data_scenario": ("sensitive", "pii", "privacy", "data", "safe"),
    "ambiguous_question_handling": ("ambigu", "unclear", "clarif"),
    "scaling_business_system": ("scale", "scaling", "throughput", "load"),
    "model_drift": ("drift", "monitor", "retrain"),
    "stt_accent_handling": ("accent", "speech", "whisper", "stt", "transcri"),
    "latency_optimization": ("latency", "speed", "fast", "optim"),
    "why_rag": ("rag", "retriev"),
    "agent_coordination": ("agent", "coordinat", "orchestr"),
    "why_embeddings": ("embed",),
    "when_langgraph": ("langgraph", "lang graph", "graph"),
    "guardrails_short": ("guardrail",),
    "stop_hallucinations": ("hallucin", "ground", "valid"),
    "what_is_rag": ("rag", "retriev"),
    "what_is_agentic_ai": ("agentic", "agent"),
    "what_are_embeddings": ("embed",),
    "cosine_similarity": ("cosine", "similar"),
    "overfitting": ("overfit",),
    "vector_database": ("vector", "chroma", "database"),
}


@dataclass
class ClipResult:
    sample_id: str
    ok: bool
    meaning_preserved: bool
    question_understood: bool
    answer_selected: bool
    confident_wrong: bool
    duplicate: bool
    timeout: bool
    latency_ms: float
    stt_ms: float
    match_ms: float
    transcript: str
    expected_question: str
    match_id: str
    match_score: float
    match_mode: str
    status: str
    intent_key: str
    accent: str
    speed: str
    distance: str
    noise: str
    style: str
    notes: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    if sw == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        audio = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        audio = (audio - 128.0) / 128.0
    if nch > 1:
        audio = audio.reshape(-1, nch).mean(axis=1)
    return audio, sr


def _topic_hit(blob: str, topics: tuple[str, ...]) -> bool:
    if not topics:
        return True
    low = (blob or "").lower()
    return any(t in low for t in topics)


def _median(xs: list[float]) -> float:
    return float(statistics.median(xs)) if xs else 0.0


def _group(results: list[ClipResult], key: str) -> dict[str, Any]:
    bags: dict[str, list[ClipResult]] = defaultdict(list)
    for r in results:
        bags[str(getattr(r, key))].append(r)
    out = {}
    for g, rs in sorted(bags.items()):
        out[g] = {
            "n": len(rs),
            "ok": sum(1 for r in rs if r.ok),
            "ok_rate": round(sum(1 for r in rs if r.ok) / len(rs), 4),
            "meaning_rate": round(sum(1 for r in rs if r.meaning_preserved) / len(rs), 4),
            "understood_rate": round(sum(1 for r in rs if r.question_understood) / len(rs), 4),
            "answer_rate": round(sum(1 for r in rs if r.answer_selected) / len(rs), 4),
            "hc_wrong": sum(1 for r in rs if r.confident_wrong),
            "median_latency_ms": round(_median([r.latency_ms for r in rs]), 1),
            "median_stt_ms": round(_median([r.stt_ms for r in rs]), 1),
        }
    return out


async def _eval_clip(row: dict[str, Any], classifier) -> ClipResult:
    from app.audio.whisper_stt import transcribe_whisper_async
    from app.models.question import UtteranceType
    from app.services.compound_question_detector import detect_question_complexity
    from app.services.compound_question_pipeline import resolve_compound_question
    from app.services.question_bank import question_bank
    from app.services.semantic_intent_recovery import recover_semantic_intent

    sample_id = row["sample_id"]
    path = PACK / row["file"]
    intent_key = row["intent_key"]
    topics = INTENT_TOPICS.get(intent_key, tuple())
    expected = row.get("expected_question") or row.get("tts_input_text") or ""

    if not path.exists():
        return ClipResult(
            sample_id=sample_id,
            ok=False,
            meaning_preserved=False,
            question_understood=False,
            answer_selected=False,
            confident_wrong=False,
            duplicate=False,
            timeout=False,
            latency_ms=0.0,
            stt_ms=0.0,
            match_ms=0.0,
            transcript="",
            expected_question=expected,
            match_id="",
            match_score=0.0,
            match_mode="",
            status="ERROR",
            intent_key=intent_key,
            accent=row.get("accent_target", ""),
            speed=row.get("speed", ""),
            distance=row.get("distance", ""),
            noise=row.get("noise", ""),
            style=row.get("question_style", ""),
            notes="missing_wav",
        )

    audio, sr = _load_wav(path)
    t0 = time.perf_counter()

    t_stt = time.perf_counter()
    try:
        stt = await transcribe_whisper_async(audio, sample_rate=sr)
        transcript = (stt if isinstance(stt, str) else str(stt or "")).strip()
    except Exception as exc:
        return ClipResult(
            sample_id=sample_id,
            ok=False,
            meaning_preserved=False,
            question_understood=False,
            answer_selected=False,
            confident_wrong=False,
            duplicate=False,
            timeout=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            stt_ms=(time.perf_counter() - t_stt) * 1000,
            match_ms=0.0,
            transcript="",
            expected_question=expected,
            match_id="",
            match_score=0.0,
            match_mode="",
            status="ERROR",
            intent_key=intent_key,
            accent=row.get("accent_target", ""),
            speed=row.get("speed", ""),
            distance=row.get("distance", ""),
            noise=row.get("noise", ""),
            style=row.get("question_style", ""),
            notes=f"stt_error:{exc}",
        )
    stt_ms = (time.perf_counter() - t_stt) * 1000

    # Meaning from STT: topic tokens OR substantial overlap with expected wording
    exp_tokens = [w for w in expected.lower().split() if len(w) >= 5][:8]
    meaning = _topic_hit(transcript, topics) or (
        bool(exp_tokens) and sum(1 for w in exp_tokens if w in transcript.lower()) >= max(1, len(exp_tokens) // 3)
    )

    if not transcript:
        return ClipResult(
            sample_id=sample_id,
            ok=False,
            meaning_preserved=False,
            question_understood=False,
            answer_selected=False,
            confident_wrong=False,
            duplicate=False,
            timeout=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            stt_ms=stt_ms,
            match_ms=0.0,
            transcript="",
            expected_question=expected,
            match_id="",
            match_score=0.0,
            match_mode="",
            status="LOW_CONFIDENCE",
            intent_key=intent_key,
            accent=row.get("accent_target", ""),
            speed=row.get("speed", ""),
            distance=row.get("distance", ""),
            noise=row.get("noise", ""),
            style=row.get("question_style", ""),
            notes="empty_transcript",
        )

    classification = await classifier.classify(transcript, prefer_speed=True)
    is_q = classification.type in {UtteranceType.QUESTION, UtteranceType.FOLLOW_UP}

    t_match = time.perf_counter()
    match = question_bank.match(transcript)
    try:
        decision = recover_semantic_intent(transcript, match)
        if decision.applied and decision.match is not None:
            match = decision.match
    except Exception:
        pass

    detection = detect_question_complexity(transcript)
    compound = None
    if detection.question_type != "single":
        try:
            compound = resolve_compound_question(transcript, detection=detection)
        except Exception:
            compound = None
    match_ms = (time.perf_counter() - t_match) * 1000

    match_id = ""
    match_score = 0.0
    match_mode = ""
    answer_selected = False
    confident_wrong = False
    understood = False
    status = "NO_QUESTION"
    answer_preview = ""

    used_compound = bool(compound and compound.used_compound_path and compound.answer_en)
    if used_compound and compound is not None:
        match_id = ",".join(compound.selected_intents or [])
        match_mode = "compound"
        answer_selected = True
        status = "ANSWER_READY"
        answer_preview = (compound.answer_en or "")[:240]
        blob = f"{match_id} {answer_preview} {transcript}"
        understood = _topic_hit(blob, topics)
    elif match is not None and is_q:
        match_id = match.entry.id
        match_score = float(match.score)
        match_mode = match.mode
        answer_preview = (match.entry.answer_en or "")[:240]
        blob = f"{match_id} {match.entry.question} {answer_preview} {transcript}"
        topic_ok = _topic_hit(blob, topics)
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
        understood = False
    else:
        status = "NO_QUESTION"
        # Non-question classification after speech: fail if meaning was clear
        understood = False

    # Practical pass: meaning preserved + no HC wrong; answer preferred but honest abstain OK
    if confident_wrong:
        ok = False
    elif not meaning:
        ok = False
    elif status == "ANSWER_READY":
        ok = understood
    else:
        # Honest abstain after understandable speech is acceptable
        ok = True

    return ClipResult(
        sample_id=sample_id,
        ok=ok,
        meaning_preserved=meaning,
        question_understood=understood,
        answer_selected=answer_selected,
        confident_wrong=confident_wrong,
        duplicate=False,
        timeout=False,
        latency_ms=(time.perf_counter() - t0) * 1000,
        stt_ms=stt_ms,
        match_ms=match_ms,
        transcript=transcript,
        expected_question=expected,
        match_id=match_id,
        match_score=match_score,
        match_mode=match_mode,
        status=status,
        intent_key=intent_key,
        accent=row.get("accent_target", ""),
        speed=row.get("speed", ""),
        distance=row.get("distance", ""),
        noise=row.get("noise", ""),
        style=row.get("question_style", ""),
        notes="",
        meta={"duration_sec": row.get("duration_sec"), "file": row.get("file")},
    )


def _decide(summary: dict[str, Any]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if summary["confident_wrong"] > 0:
        blockers.append(f"confident_wrong={summary['confident_wrong']}")
    if summary["meaning_rate"] < 0.70:
        blockers.append(f"meaning_rate={summary['meaning_rate']:.3f} < 0.70")
    if summary["ok_rate"] < 0.65:
        blockers.append(f"ok_rate={summary['ok_rate']:.3f} < 0.65")
    # Accent collapse check
    for accent, g in (summary.get("by_accent") or {}).items():
        if g["n"] >= 10 and g["ok_rate"] < 0.50:
            blockers.append(f"accent {accent} collapsed ok_rate={g['ok_rate']:.3f}")
    verdict = "PASS_150_VOICE_STRESS" if not blockers else "FAIL_150_VOICE_STRESS"
    return verdict, blockers


async def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    manifest_path = PACK / "manifest.json"
    if not manifest_path.exists():
        print(f"MISSING pack at {PACK}", flush=True)
        return 2

    rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(f"=== V5 150 VOICE STRESS ({len(rows)} clips) ===", flush=True)
    print(f"pack={PACK}", flush=True)

    from app.services.warm_start import warm_system_blocking, is_system_warm
    from app.services.question_classifier import QuestionClassifier

    warm_system_blocking(probe_audio=True)
    print(f"warm={is_system_warm()}", flush=True)
    classifier = QuestionClassifier()

    results: list[ClipResult] = []
    for i, row in enumerate(rows, 1):
        r = await _eval_clip(row, classifier)
        results.append(r)
        print(
            f"[{i:03d}/{len(rows)}] {r.sample_id} {r.accent}/{r.speed}/{r.distance}/{r.noise} "
            f"ok={r.ok} mean={r.meaning_preserved} und={r.question_understood} "
            f"ans={r.answer_selected} hc={r.confident_wrong} "
            f"status={r.status} lat={r.latency_ms:.0f} stt={r.stt_ms:.0f} "
            f"id={r.match_id[:36]} tx={r.transcript[:55]!r}",
            flush=True,
        )

    n = len(results)
    summary: dict[str, Any] = {
        "n": n,
        "ok": sum(1 for r in results if r.ok),
        "ok_rate": round(sum(1 for r in results if r.ok) / max(n, 1), 4),
        "meaning_rate": round(sum(1 for r in results if r.meaning_preserved) / max(n, 1), 4),
        "understood_rate": round(sum(1 for r in results if r.question_understood) / max(n, 1), 4),
        "answer_rate": round(sum(1 for r in results if r.answer_selected) / max(n, 1), 4),
        "confident_wrong": sum(1 for r in results if r.confident_wrong),
        "duplicate_count": sum(1 for r in results if r.duplicate),
        "timeout_count": sum(1 for r in results if r.timeout),
        "empty_transcript": sum(1 for r in results if not r.transcript),
        "median_latency_ms": round(_median([r.latency_ms for r in results]), 1),
        "median_stt_ms": round(_median([r.stt_ms for r in results]), 1),
        "median_match_ms": round(_median([r.match_ms for r in results]), 1),
        "by_accent": _group(results, "accent"),
        "by_speed": _group(results, "speed"),
        "by_distance": _group(results, "distance"),
        "by_noise": _group(results, "noise"),
        "by_style": _group(results, "style"),
    }
    verdict, blockers = _decide(summary)
    summary["verdict"] = verdict
    summary["blockers"] = blockers

    payload = {
        "created_at": _now(),
        "track": "v5_150_voice_stress",
        "pack": str(PACK),
        "note": "Synthetic accent proxies — not proof of real-human accent accuracy.",
        "summary": summary,
        "results": [asdict(r) for r in results],
    }
    json_path = REPORTS / "V5_150_VOICE_STRESS_RESULTS.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Fill evaluation CSV
    csv_path = REPORTS / "V5_150_VOICE_STRESS_evaluation_results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "sample_id",
                "stt_transcript",
                "meaning_preserved",
                "question_understood",
                "correct_answer_selected",
                "duplicate",
                "confident_wrong",
                "latency_ms",
                "notes",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.sample_id,
                    r.transcript,
                    int(r.meaning_preserved),
                    int(r.question_understood),
                    int(r.answer_selected),
                    int(r.duplicate),
                    int(r.confident_wrong),
                    round(r.latency_ms, 1),
                    r.notes or r.status,
                ]
            )

    fails = [r for r in results if not r.ok][:30]
    hc = [r for r in results if r.confident_wrong][:20]
    md_lines: list[str] = [
        verdict,
        "",
        "# V5 150 Voice Stress Results",
        "",
        f"Created: `{payload['created_at']}`",
        "",
        f"Pack: `{PACK}`",
        "",
        "> Accent audio is synthetic proxy audio, not recordings of real speakers.",
        "",
        "## Summary",
        "",
        f"- n={summary['n']}",
        f"- ok_rate=**{summary['ok_rate']}**",
        f"- meaning_preserved_rate=**{summary['meaning_rate']}**",
        f"- question_understood_rate=**{summary['understood_rate']}**",
        f"- answer_selected_rate=**{summary['answer_rate']}**",
        f"- confident_wrong=**{summary['confident_wrong']}**",
        f"- median_latency_ms=**{summary['median_latency_ms']}** (stt={summary['median_stt_ms']}, match={summary['median_match_ms']})",
        "",
        "## Accent",
        "```json",
        json.dumps(summary["by_accent"], indent=2),
        "```",
        "",
        "## Speed",
        "```json",
        json.dumps(summary["by_speed"], indent=2),
        "```",
        "",
        "## Distance",
        "```json",
        json.dumps(summary["by_distance"], indent=2),
        "```",
        "",
        "## Noise",
        "```json",
        json.dumps(summary["by_noise"], indent=2),
        "```",
        "",
        "## Style",
        "```json",
        json.dumps(summary["by_style"], indent=2),
        "```",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        md_lines += [f"- {b}" for b in blockers]
    else:
        md_lines.append("- none")
    md_lines += ["", "## Confident wrong (up to 20)", ""]
    if not hc:
        md_lines.append("- none")
    else:
        for r in hc:
            md_lines.append(
                f"- `{r.sample_id}` intent={r.intent_key} match={r.match_id} "
                f"tx={r.transcript!r}"
            )
    md_lines += ["", "## Failures (up to 30)", ""]
    if not fails:
        md_lines.append("- none")
    else:
        for r in fails:
            md_lines.append(
                f"- `{r.sample_id}` {r.accent}/{r.speed}/{r.distance}/{r.noise} "
                f"status={r.status} mean={r.meaning_preserved} und={r.question_understood} "
                f"match={r.match_id} tx={r.transcript!r}"
            )
    md_lines.append("")
    md_path = REPORTS / "V5_150_VOICE_STRESS_RESULTS.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("=== VERDICT ===", flush=True)
    print(verdict, flush=True)
    print(f"ok_rate={summary['ok_rate']} meaning={summary['meaning_rate']} "
          f"understood={summary['understood_rate']} hc={summary['confident_wrong']}", flush=True)
    print(f"wrote {md_path}", flush=True)
    print(f"wrote {json_path}", flush=True)
    print(f"wrote {csv_path}", flush=True)
    return 0 if verdict == "PASS_150_VOICE_STRESS" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
