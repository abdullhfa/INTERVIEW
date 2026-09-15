"""Narrow A/B on Office/Poor E2E failures — ASR second-pass only (no audio EQ).

Compares baseline vs stronger accurate decode on the same WAV files from the
last Office+Poor report. Does not change Clean config, matcher, or aliases.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

STRESS_ROOT = ROOT / "frontend" / "public" / "voice-drill" / "stress-pilot"
REPORTS = BACKEND / "reports"


def _score(a: str, b: str) -> float:
    if not (a or "").strip() or not (b or "").strip():
        return 0.0
    return round(fuzz.token_set_ratio(a, b) / 100.0, 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--from-report",
        default=str(REPORTS / "INTERVIEW_E2E_OFFICE_POOR_REPORT.json"),
    )
    args = parser.parse_args()

    from app.audio.utterance_preprocess import estimate_audio_levels, preprocess_utterance
    from app.audio.whisper_stt import transcribe_whisper, warm_whisper_model
    from app.services.interview_audio_runner import load_wav_mono
    from app.services.question_bank import question_bank
    from app.services.stt_confidence import classify_fail_bucket
    import asyncio

    asyncio.run(warm_whisper_model())
    question_bank.load(force=True)

    payload = json.loads(Path(args.from_report).read_text(encoding="utf-8"))
    fails = [r for r in payload.get("results", []) if r.get("result") != "PASS"]
    print(f"A/B on {len(fails)} Office/Poor fails from {args.from_report}", flush=True)

    rows = []
    for i, fail in enumerate(fails, start=1):
        path = STRESS_ROOT / str(fail["file"])
        expected = str(fail.get("expected_question") or "")
        spoken = expected
        # Prefer spoken wording from metadata when available
        meta_path = STRESS_ROOT / "metadata.json"
        # file already in fail
        audio, sr = load_wav_mono(path)
        if sr != 16000 and len(audio):
            ratio = sr / 16000
            if ratio > 1:
                audio = audio[:: int(ratio)]
                sr = 16000
        prepared = preprocess_utterance(audio, sample_rate=sr)
        levels = estimate_audio_levels(audio, prepared, sample_rate=sr)

        t0 = time.perf_counter()
        base = transcribe_whisper(prepared, sr, accurate=False)
        base_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        strong = transcribe_whisper(prepared, sr, accurate=True)
        strong_ms = (time.perf_counter() - t1) * 1000

        m_base = question_bank.match(base) if base.strip() else None
        m_strong = question_bank.match(strong) if strong.strip() else None

        def intent_ok(m, text: str) -> bool:
            if m is None:
                return False
            iscore = max(_score(m.entry.question, expected), _score(m.entry.question, text))
            return iscore >= 0.70 and float(m.score) >= 0.40

        base_ok = intent_ok(m_base, base)
        strong_ok = intent_ok(m_strong, strong)
        bucket = classify_fail_bucket(
            stt_ok=_score(base, expected) >= 0.72,
            intent_ok=base_ok,
            stt_score=_score(base, expected),
            transcript=base,
            expected=expected,
        )
        row = {
            "file": fail.get("file"),
            "condition": fail.get("condition"),
            "question_id": fail.get("question_id"),
            "expected": expected,
            "baseline": base,
            "strong_second_pass": strong,
            "baseline_intent_ok": base_ok,
            "strong_intent_ok": strong_ok,
            "baseline_ms": round(base_ms, 1),
            "strong_ms": round(strong_ms, 1),
            "improved": (not base_ok) and strong_ok,
            "fail_bucket_baseline": bucket,
            "audio_levels": levels,
        }
        rows.append(row)
        print(
            f"[{i}/{len(fails)}] {fail.get('condition')} Q{fail.get('question_id')} "
            f"base={base_ok} strong={strong_ok} improved={row['improved']} "
            f"bw={levels.get('bandwidth_hz_est')} centroid={levels.get('spectral_centroid_hz')}",
            flush=True,
        )
        print(f"  base: {base}", flush=True)
        print(f"  strong: {strong}", flush=True)

    improved = sum(1 for r in rows if r["improved"])
    still_fail = sum(1 for r in rows if not r["strong_intent_ok"])
    out = {
        "total_fails": len(rows),
        "strong_recovers": improved,
        "still_fail_after_strong": still_fail,
        "avg_bandwidth_hz": round(
            sum(r["audio_levels"].get("bandwidth_hz_est", 0) for r in rows) / max(1, len(rows)), 1
        ),
        "avg_high_freq_ratio": round(
            sum(r["audio_levels"].get("high_freq_energy_ratio", 0) for r in rows) / max(1, len(rows)), 4
        ),
        "rows": rows,
        "note": "No larger Whisper than distil-large-v3 cached; strong=beam10+tech prompt+en",
    }
    path = REPORTS / "POOR_ASR_FALLBACK_AB_REPORT.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== POOR ASR FALLBACK A/B ===")
    print(f"Fails: {len(rows)} | strong recovers: {improved} | still fail: {still_fail}")
    print(f"avg bandwidth Hz: {out['avg_bandwidth_hz']} | avg HF ratio: {out['avg_high_freq_ratio']}")
    print("JSON:", path)


if __name__ == "__main__":
    main()
