"""Whisper STT latency microbench (Track A) — NOT a holdout / not for Intent tuning.

Uses stress-holdout-v2 length folders (dev audio), never final-unseen-holdout*.
Reports p50/p90 whisper_ms and RTF for first-pass (+ optional accurate) on CUDA.
"""

from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

HOLD = (
    ROOT
    / "frontend"
    / "public"
    / "voice-drill"
    / "stress-holdout-v2"
)
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


def _pick_wavs(limit: int) -> list[Path]:
    folders = [
        ("08_short_sentences", 10),
        ("07_medium_sentences", 8),
        ("06_long_sentences", 6),
    ]
    out: list[Path] = []
    for name, n in folders:
        d = HOLD / name
        if not d.is_dir():
            continue
        wavs = sorted(d.rglob("*.wav"))[:n]
        out.extend(wavs)
    return out[:limit]


def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round((len(s) - 1) * p))))
    return s[i]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--accurate", action="store_true", help="Also time one accurate pass")
    parser.add_argument("--label", type=str, default="current")
    args = parser.parse_args()

    from app.audio.whisper_stt import (
        active_stt_info,
        clear_decode_log,
        last_decode_info,
        transcribe_whisper,
        _load_model,
    )
    from app.config import settings

    wavs = _pick_wavs(args.limit)
    if not wavs:
        raise SystemExit(f"No WAVs under {HOLD} (need 06/07/08 folders)")

    _load_model()
    info = active_stt_info()
    clear_decode_log()

    first_ms: list[float] = []
    acc_ms: list[float] = []
    rows: list[dict] = []

    # Warm CUDA kernels with first clip (discard).
    a0, sr0 = _load_wav(wavs[0])
    transcribe_whisper(a0, sr0, accurate=False)

    for path in wavs:
        audio, sr = _load_wav(path)
        clear_decode_log()
        text = transcribe_whisper(audio, sr, accurate=False)
        d1 = last_decode_info()
        first_ms.append(float(d1.get("whisper_ms") or 0.0))
        row = {
            "file": str(path.relative_to(HOLD)).replace("\\", "/"),
            "first": d1,
            "transcript": (text or "")[:120],
        }
        if args.accurate:
            clear_decode_log()
            transcribe_whisper(audio, sr, accurate=True)
            d2 = last_decode_info()
            acc_ms.append(float(d2.get("whisper_ms") or 0.0))
            row["accurate"] = d2
        rows.append(row)

    summary = {
        "label": args.label,
        "n": len(wavs),
        "active": info,
        "settings": {
            "whisper_model_size": settings.whisper_model_size,
            "whisper_beam_size": settings.whisper_beam_size,
            "whisper_device": settings.whisper_device,
            "whisper_compute_type": settings.whisper_compute_type,
        },
        "first_pass": {
            "p50_ms": round(_pct(first_ms, 0.5), 1),
            "p90_ms": round(_pct(first_ms, 0.9), 1),
            "mean_ms": round(sum(first_ms) / len(first_ms), 1) if first_ms else 0.0,
            "max_ms": round(max(first_ms), 1) if first_ms else 0.0,
        },
        "pack": "stress-holdout-v2 (06/07/08) — latency-dev only",
        "goal_p50_ms": 1200.0,
        "pass_goal": (_pct(first_ms, 0.5) <= 1200.0) if first_ms else False,
    }
    if acc_ms:
        summary["accurate_pass"] = {
            "p50_ms": round(_pct(acc_ms, 0.5), 1),
            "p90_ms": round(_pct(acc_ms, 0.9), 1),
            "mean_ms": round(sum(acc_ms) / len(acc_ms), 1),
        }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / f"STT_LATENCY_BENCH_{args.label}.json"
    payload = {"summary": summary, "rows": rows}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = REPORTS / "STT_LATENCY_BENCH_LATEST.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
