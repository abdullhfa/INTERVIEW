"""
Synthesize the Final Unseen Holdout v3 audio.

TTS: edge-tts (already in the venv). Accent comes from the neural voice locale;
the acoustic condition is applied afterwards with numpy so no extra dependency
is needed. MP3 -> 16 kHz mono PCM decoding uses PyAV, which ships with
faster-whisper.

    python scripts/synthesize_final_unseen_holdout_v3.py
    python scripts/synthesize_final_unseen_holdout_v3.py --only fuh3_007 --force

The script is idempotent: an existing WAV is left alone unless --force.
Run it once, listen to a few clips, then lock the pack.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PACK_ROOT = ROOT.parent / "frontend" / "public" / "voice-drill" / "final-unseen-holdout-v3"
SR = 16_000

# Accent profile -> (female voice, male voice).
#
# HONESTY NOTE: only `en-IN` is a genuine English-locale neural voice. The three
# `proxy-ar-*` profiles are Arabic-locale voices reading English text. They are a
# synthetic stand-in for Arabic-accented English, NOT a recording of a Jordanian,
# Egyptian or Emirati speaker, and the pack names them that way so no report can
# claim otherwise.
#
# `--voices multilingual` swaps the three proxies for Azure multilingual voices.
# Decide between the two sets with scripts/spotcheck_holdout_v3_voices.py BEFORE
# synthesizing the pack — the spot-check runs on throwaway probe sentences, never
# on v3 clips.
VOICE_SETS = {
    "proxy": {
        "en-IN": ("en-IN-NeerjaNeural", "en-IN-PrabhatNeural"),
        "proxy-ar-JO": ("ar-JO-SanaNeural", "ar-JO-TaimNeural"),
        "proxy-ar-EG": ("ar-EG-SalmaNeural", "ar-EG-ShakirNeural"),
        "proxy-ar-AE": ("ar-AE-FatimaNeural", "ar-AE-HamdanNeural"),
    },
    "multilingual": {
        "en-IN": ("en-IN-NeerjaNeural", "en-IN-PrabhatNeural"),
        "proxy-ar-JO": ("en-US-AvaMultilingualNeural", "en-US-AndrewMultilingualNeural"),
        "proxy-ar-EG": ("en-US-EmmaMultilingualNeural", "en-US-BrianMultilingualNeural"),
        "proxy-ar-AE": ("de-DE-SeraphinaMultilingualNeural", "en-US-AndrewMultilingualNeural"),
    },
}
VOICES = VOICE_SETS["proxy"]

RATE = {"clean": "+0%", "office": "+0%", "poor": "+0%", "far": "+0%", "fast": "+28%"}


# ── tiny DSP helpers (numpy only) ──────────────────────────────────────────
def _sinc_kernel(cutoff_hz: float, taps: int = 129, kind: str = "low") -> np.ndarray:
    fc = cutoff_hz / SR
    n = np.arange(taps) - (taps - 1) / 2.0
    h = 2 * fc * np.sinc(2 * fc * n)
    h *= np.hamming(taps)
    h /= np.sum(h)
    if kind == "high":
        d = np.zeros(taps)
        d[(taps - 1) // 2] = 1.0
        h = d - h
    return h


def _filt(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    return np.convolve(x, h, mode="same").astype(np.float32)


def _band(x: np.ndarray, low_hz: float, high_hz: float) -> np.ndarray:
    return _filt(_filt(x, _sinc_kernel(high_hz, kind="low")), _sinc_kernel(low_hz, kind="high"))


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))) + 1e-12)


def _set_rms(x: np.ndarray, target: float) -> np.ndarray:
    return (x * (target / _rms(x))).astype(np.float32)


def _noise_at_snr(x: np.ndarray, snr_db: float, rng: np.random.Generator,
                  colour: str = "white") -> np.ndarray:
    n = rng.standard_normal(len(x)).astype(np.float32)
    if colour == "pink":
        n = _filt(n, _sinc_kernel(1800.0, kind="low"))
    return (n * (_rms(x) / (10 ** (snr_db / 20.0)) / _rms(n))).astype(np.float32)


def _reverb(x: np.ndarray, rng: np.random.Generator, seconds: float = 0.28,
            decay: float = 3.2) -> np.ndarray:
    taps = int(seconds * SR)
    ir = rng.standard_normal(taps).astype(np.float32) * np.exp(
        -decay * np.linspace(0, 1, taps)
    ).astype(np.float32)
    ir[0] = 1.0
    ir /= np.sqrt(np.sum(ir ** 2))
    return np.convolve(x, ir)[: len(x)].astype(np.float32)


def apply_condition(x: np.ndarray, condition: str, seed: int) -> np.ndarray:
    """Deterministic per-clip acoustics. Same seed -> same WAV, every time."""
    rng = np.random.default_rng(seed)
    x = _set_rms(x, 0.06)
    if condition == "clean":
        out = x + _noise_at_snr(x, 42.0, rng)
    elif condition == "fast":
        out = x + _noise_at_snr(x, 38.0, rng)
    elif condition == "office":
        out = _filt(x, _sinc_kernel(6500.0, kind="low"))
        out = out + _noise_at_snr(out, 19.0, rng, colour="pink")
    elif condition == "poor":
        out = _band(x, 300.0, 3400.0)
        out = out + _noise_at_snr(out, 12.0, rng)
        out = np.tanh(out * 3.2) / 3.2           # codec-ish saturation
    elif condition == "far":
        out = _reverb(x, rng)
        out = _filt(out, _sinc_kernel(2800.0, kind="low"))
        out = _set_rms(out, 0.020)                # genuinely quieter
        out = out + _noise_at_snr(out, 16.0, rng, colour="pink")
    else:
        raise ValueError(f"unknown condition {condition!r}")
    peak = float(np.max(np.abs(out)) or 1.0)
    if peak > 0.95:
        out = out * (0.95 / peak)
    return out.astype(np.float32)


def _decode_to_mono16k(path: Path) -> np.ndarray:
    import av

    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=SR)
        chunks: list[np.ndarray] = []
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        raise RuntimeError(f"no audio decoded from {path}")
    return (np.concatenate(chunks).astype(np.float32) / 32768.0)


def _write_wav(path: Path, x: np.ndarray) -> None:
    pcm = np.clip(x, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


async def _tts(text: str, voice: str, rate: str, out_mp3: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice, rate=rate).save(str(out_mp3))


def _pad(x: np.ndarray, lead_ms: int = 320, tail_ms: int = 420) -> np.ndarray:
    lead = np.zeros(int(SR * lead_ms / 1000), dtype=np.float32)
    tail = np.zeros(int(SR * tail_ms / 1000), dtype=np.float32)
    return np.concatenate([lead, x, tail])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-synthesize existing clips")
    ap.add_argument("--only", nargs="*", default=None, help="clip ids to (re)build")
    ap.add_argument(
        "--voices",
        choices=sorted(VOICE_SETS),
        default="proxy",
        help="voice set to use; run the spot-check before choosing",
    )
    args = ap.parse_args()
    voices = VOICE_SETS[args.voices]

    scripts_path = PACK_ROOT / "scripts.json"
    if not scripts_path.is_file():
        print(f"missing {scripts_path} — run build_final_unseen_holdout_v3_scripts.py first")
        return 1
    rows = json.loads(scripts_path.read_text(encoding="utf-8"))
    if args.only:
        rows = [r for r in rows if r["id"] in set(args.only)]

    made = skipped = 0
    for i, row in enumerate(rows):
        wav = PACK_ROOT / row["file"]
        if wav.is_file() and not args.force:
            skipped += 1
            continue
        female, male = voices[row["accent"]]
        voice = female if i % 2 == 0 else male
        rate = RATE[row["condition"]]
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "tts.mp3"
            asyncio.run(_tts(row["transcript"], voice, rate, mp3))
            raw = _decode_to_mono16k(mp3)
        # Seed from the clip id so every rebuild is byte-identical.
        seed = int.from_bytes(row["id"].encode("utf-8"), "little") % (2**32)
        shaped = apply_condition(_pad(raw), row["condition"], seed)
        _write_wav(wav, shaped)
        made += 1
        print(
            f"  {row['id']:14s} {row['condition']:6s} {row['accent']:10s} {voice:22s} "
            f"{len(shaped)/SR:5.2f}s  {row['transcript'][:48]}"
        )

    meta_path = PACK_ROOT / "pack_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    total = len(json.loads(scripts_path.read_text(encoding="utf-8")))
    have = sum(1 for r in json.loads(scripts_path.read_text(encoding="utf-8"))
               if (PACK_ROOT / r["file"]).is_file())
    meta["audio_status"] = "synthesized" if have == total else f"partial {have}/{total}"
    meta["tts"] = {
        "engine": "edge-tts",
        "voice_set": args.voices,
        "voices": voices,
        "rate": RATE,
        "sample_rate": SR,
        "accent_note": (
            "proxy-ar-* profiles are synthetic accent proxies, not human dialect "
            "recordings. Reports must not describe them as real dialects."
        ),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nsynthesized {made}, skipped {skipped}, audio present {have}/{total}")
    print("next: python scripts/lock_holdout_v3.py --write")
    return 0 if have == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
