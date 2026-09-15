"""
Light utterance audio prep for far/noisy loopback capture.

Keep processing mild: strong denoise destroys short tech terms (RAG, LangGraph).
"""

from __future__ import annotations

import numpy as np


def normalize_rms(
    audio: np.ndarray,
    *,
    target_rms: float = 0.085,
    max_gain: float = 6.0,
    floor: float = 1e-4,
) -> np.ndarray:
    """Scale mono float audio toward a stable RMS without hard clipping."""
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    if x.size == 0:
        return x
    rms = float(np.sqrt(np.mean(np.square(x))))
    if rms < floor:
        return x
    gain = min(max_gain, target_rms / rms)
    y = x * gain
    return np.clip(y, -0.98, 0.98).astype(np.float32)


def light_denoise(audio: np.ndarray, *, sample_rate: int = 16000) -> np.ndarray:
    """
    Very light noise control:
    - DC remove
    - gentle high-pass (~80 Hz) via simple IIR
    - soft noise gate on very quiet samples
    """
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    if x.size < 8:
        return x
    x = x - float(np.mean(x))
    # One-pole high-pass ~80 Hz at 16 kHz
    rc = 1.0 / (2.0 * np.pi * 80.0)
    dt = 1.0 / float(sample_rate)
    alpha = rc / (rc + dt)
    y = np.empty_like(x)
    prev_x = 0.0
    prev_y = 0.0
    for i, sample in enumerate(x):
        prev_y = alpha * (prev_y + sample - prev_x)
        prev_x = float(sample)
        y[i] = prev_y
    # Soft gate relative to utterance energy
    rms = float(np.sqrt(np.mean(np.square(y)))) + 1e-8
    gate = 0.18 * rms
    mask = np.abs(y) < gate
    y = y.copy()
    y[mask] *= 0.35
    return y.astype(np.float32)


def estimate_audio_levels(
    raw: np.ndarray,
    processed: np.ndarray,
    *,
    sample_rate: int = 16000,
) -> dict[str, float]:
    """
    Level + simple spectral diagnostics for Office/Poor/Far reports.
    SNR estimate uses quietest vs loudest 50ms frames (not a calibrated meter).
    """
    def _rms(x: np.ndarray) -> float:
        y = np.asarray(x, dtype=np.float32).reshape(-1)
        if y.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(y))))

    def _frame_stats(x: np.ndarray) -> tuple[float, float, float]:
        y = np.asarray(x, dtype=np.float32).reshape(-1)
        if y.size == 0:
            return 0.0, 0.0, 0.0
        frame = max(1, int(sample_rate * 0.05))
        vals = []
        for i in range(0, len(y), frame):
            chunk = y[i : i + frame]
            if chunk.size:
                vals.append(float(np.sqrt(np.mean(np.square(chunk)))))
        if not vals:
            return 0.0, 0.0, 0.0
        vals_sorted = sorted(vals)
        noise = float(np.median(vals_sorted[: max(1, len(vals_sorted) // 5)]))
        speech = float(np.median(vals_sorted[-(max(1, len(vals_sorted) // 5)) :]))
        snr_db = 20.0 * float(np.log10((speech + 1e-8) / (noise + 1e-8)))
        return noise, speech, snr_db

    def _spectral(x: np.ndarray) -> tuple[float, float, float]:
        """centroid Hz, high-band energy ratio (>3.5kHz), effective bandwidth Hz."""
        y = np.asarray(x, dtype=np.float32).reshape(-1)
        if y.size < 64:
            return 0.0, 0.0, 0.0
        # Hann windowed rFFT on up to 1s center crop
        n = min(len(y), int(sample_rate))
        start = max(0, (len(y) - n) // 2)
        seg = y[start : start + n].astype(np.float64)
        window = np.hanning(len(seg))
        spec = np.abs(np.fft.rfft(seg * window)) + 1e-12
        freqs = np.fft.rfftfreq(len(seg), d=1.0 / float(sample_rate))
        power = spec * spec
        centroid = float(np.sum(freqs * power) / np.sum(power))
        high_mask = freqs >= 3500.0
        high_ratio = float(np.sum(power[high_mask]) / np.sum(power))
        # bandwidth: cumulative 90% power edge
        cump = np.cumsum(power) / np.sum(power)
        idx = int(np.searchsorted(cump, 0.90))
        bandwidth = float(freqs[min(idx, len(freqs) - 1)])
        return centroid, high_ratio, bandwidth

    noise_floor, speech_rms, snr_db = _frame_stats(raw)
    centroid, high_ratio, bandwidth = _spectral(raw)
    return {
        "rms_before": round(_rms(raw), 5),
        "rms_after": round(_rms(processed), 5),
        "noise_floor": round(noise_floor, 5),
        "speech_rms_est": round(speech_rms, 5),
        "snr_db_est": round(snr_db, 2),
        "spectral_centroid_hz": round(centroid, 1),
        "high_freq_energy_ratio": round(high_ratio, 4),
        "bandwidth_hz_est": round(bandwidth, 1),
    }


def apply_preprocess(
    audio: np.ndarray,
    variant: str,
    *,
    sample_rate: int = 16000,
    boost: float = 1.0,
) -> np.ndarray:
    """
    Named preprocess variants for A/B STT diagnosis.

    Variants:
      raw              — no processing
      preroll_pad      — 400ms leading silence (helps short/clipped onsets)
      normalize        — RMS gain only
      denoise          — light denoise only
      combo            — denoise + normalize (legacy; can hurt short tech terms)
      vad_crop         — drop first 300ms (simulates VAD onset loss)
      vad_crop_preroll — drop 300ms then restore via 400ms pre-roll buffer
    """
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    name = (variant or "raw").strip().lower()
    sr = (sample_rate)
    if name in {"raw", "none", "identity"}:
        return x.copy()
    if name == "preroll_pad":
        pad = np.zeros(int(sr * 0.40), dtype=np.float32)
        return np.concatenate([pad, x])
    if name in {"normalize", "norm", "rms"}:
        return normalize_rms(x, target_rms=0.085 * float(boost), max_gain=6.0 * float(boost))
    if name == "denoise":
        return light_denoise(x, sample_rate=sr)
    if name in {"combo", "current", "legacy_combo"}:
        y = light_denoise(x, sample_rate=sr)
        return normalize_rms(y, target_rms=0.085 * float(boost), max_gain=6.0 * float(boost))
    if name == "vad_crop":
        cut = int(sr * 0.30)
        return x[cut:].copy() if x.size > cut else x.copy()
    if name == "vad_crop_preroll":
        cut = int(sr * 0.30)
        preroll_n = int(sr * 0.40)
        head = x[: min(preroll_n, x.size)].copy()
        body = x[cut:] if x.size > cut else x
        # Pre-roll recovers audio that would have been buffered before SPEECH_DETECTED.
        recovered = x[max(0, cut - preroll_n) : cut]
        if recovered.size == 0:
            recovered = head[:0]
        return np.concatenate([recovered, body]).astype(np.float32)
    raise ValueError(f"Unknown preprocess variant: {variant}")


def preprocess_utterance(
    audio: np.ndarray,
    *,
    sample_rate: int = 16000,
    boost: float = 1.0,
) -> np.ndarray:
    """
    Default STT prep after Clean A/B benchmark.

    denoise+normalize (combo) slightly hurt Clean STT vs raw/preroll_pad
    and can soften short tech terms. Live default = 400ms leading silence
    pad only (no denoise gate). Far/noisy paths can still call apply_preprocess
    with normalize/denoise explicitly later.
    """
    _ = boost  # reserved for far-path gain; unused in clean-safe default
    return apply_preprocess(audio, "preroll_pad", sample_rate=sample_rate)
