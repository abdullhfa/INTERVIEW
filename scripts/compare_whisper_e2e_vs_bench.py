"""Compare Whisper bench path vs E2E STT second-pass logic (Latency-cut Phase 1).

Does NOT tune Intent. Uses stress-holdout-v2 short WAVs (dev), never holdout v2/v3.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
except ImportError:
    pass

HOLD = ROOT / "frontend" / "public" / "voice-drill" / "stress-holdout-v2"
REPORTS = BACKEND / "reports"


def _load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        raw = wf.readframes(n)
    if sw == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        audio = np.frombuffer(raw, dtype=np.float32)
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    return audio, sr


def main() -> None:
    from app.audio.utterance_preprocess import preprocess_utterance
    from app.audio.whisper_stt import (
        active_stt_info,
        clear_decode_log,
        last_decode_info,
        transcribe_whisper,
        _load_model,
    )
    from app.services.question_bank import question_bank
    from app.services.stt_confidence import (
        assess_match_risk,
        needs_accurate_second_pass,
        transcript_looks_weak,
    )

    short_dir = HOLD / "08_short_sentences"
    wavs = sorted(short_dir.rglob("*.wav"))[:10]
    if not wavs:
        raise SystemExit(f"No short WAVs in {short_dir}")

    _load_model()
    question_bank.load()
    info = active_stt_info()
    print(f"Active STT: {info}", flush=True)

    # Warm
    a0, sr0 = _load_wav(wavs[0])
    transcribe_whisper(a0, sr0, accurate=False)

    rows = []
    for path in wavs:
        audio, sr = _load_wav(path)
        clear_decode_log()
        t1 = transcribe_whisper(audio, sr, accurate=False)
        d_bench = last_decode_info()

        prepared = preprocess_utterance(audio, sample_rate=16000, boost=1.0)
        clear_decode_log()
        text = transcribe_whisper(prepared, 16000, accurate=False)
        d1 = last_decode_info()
        match = question_bank.match(text) if text.strip() else None
        risk = assess_match_risk(text, match)
        weak = match is None or float(getattr(match, "score", 0.0) or 0.0) < 0.65
        need_acc = needs_accurate_second_pass(text, match)
        need_second = bool(risk.needs_stt_retry or weak or need_acc)
        reason = (
            "stt_retry"
            if risk.needs_stt_retry
            else "weak_match"
            if weak
            else "accurate_gate"
            if need_acc
            else ""
        )
        pass2_ms = 0.0
        n_passes = 1
        d2 = {}
        if need_second:
            clear_decode_log()
            text2 = transcribe_whisper(prepared, 16000, accurate=True)
            d2 = last_decode_info()
            pass2_ms = float(d2.get("whisper_ms") or 0.0)
            n_passes = 2
            m2 = question_bank.match(text2) if text2.strip() else None
            still = (
                transcript_looks_weak(text2 or "")
                or m2 is None
                or float(getattr(m2, "score", 0.0) or 0.0) < 0.65
            )
            if still:
                clear_decode_log()
                transcribe_whisper(audio, 16000, accurate=True)
                d3 = last_decode_info()
                pass2_ms += float(d3.get("whisper_ms") or 0.0)
                n_passes = 3
                d2 = {"pass2": d2, "pass3": d3}

        row = {
            "file": str(path.relative_to(HOLD)).replace("\\", "/"),
            "bench_first_ms": d_bench.get("whisper_ms"),
            "bench_beam": d_bench.get("beam"),
            "bench_best_of": d_bench.get("best_of"),
            "bench_device": d_bench.get("device"),
            "e2e_pass1_ms": d1.get("whisper_ms"),
            "e2e_pass2_ms": pass2_ms,
            "e2e_n_passes": n_passes,
            "need_second": need_second,
            "need_second_reason": reason or None,
            "e2e_total_whisper_ms": round(
                float(d1.get("whisper_ms") or 0.0) + pass2_ms, 1
            ),
            "transcript_bench": (t1 or "")[:80],
            "transcript_e2e1": (text or "")[:80],
        }
        rows.append(row)
        print(
            f"{row['file']}: bench={row['bench_first_ms']} "
            f"e2e_p1={row['e2e_pass1_ms']} n={n_passes} "
            f"need={need_second}/{reason} total={row['e2e_total_whisper_ms']}",
            flush=True,
        )

    bench_vals = [float(r["bench_first_ms"] or 0) for r in rows]
    e2e_tot = [float(r["e2e_total_whisper_ms"] or 0) for r in rows]
    multi = sum(1 for r in rows if int(r["e2e_n_passes"]) > 1)

    def _p50(v: list[float]) -> float:
        s = sorted(v)
        return s[len(s) // 2] if s else 0.0

    summary = {
        "active_stt": info,
        "n": len(rows),
        "bench_p50_ms": round(_p50(bench_vals), 1),
        "e2e_total_whisper_p50_ms": round(_p50(e2e_tot), 1),
        "multi_pass_rate": round(multi / len(rows), 4) if rows else 0.0,
        "rows": rows,
    }
    out = REPORTS / "WHISPER_BENCH_VS_E2E.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2), flush=True)
    print(f"Wrote {out}", flush=True)


if __name__ == "__main__":
    main()
