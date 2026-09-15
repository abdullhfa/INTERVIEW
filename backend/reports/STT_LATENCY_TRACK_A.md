# Track A — Whisper STT Latency

**Status:** CLOSED (accepted for handoff to Track B)  
**Date:** 2026-09-12  
**Constraint:** No Intent weight / threshold / alias changes. Holdout v2 unused for tuning.

## Goal

Median first-pass `whisper_ms` ≤ **1.2 s** on latency-dev audio (CUDA `distil-large-v3`).

## Baseline (pre–Track A)

From Final Unseen Holdout **v2** (eval-only, frozen) under old decode settings (`beam=5`, `best_of=beam`, dual accurate on retry):

| Metric | Value |
|--------|-------|
| Whisper median | **3269 ms** |
| Post-speech median | 4459 ms |
| Active STT | distil-large-v3 / cuda / int8_float16 |

## Changes shipped

| Change | Where |
|--------|--------|
| First-pass `whisper_beam_size` default **3** (was 5) | [`config.py`](../app/config.py) |
| `best_of=1` always (was `best_of=beam`) | [`whisper_stt.py`](../app/audio/whisper_stt.py) |
| Accurate: beam capped ≤8, multi-temp kept; first pass stays single-temp | `whisper_stt.py` |
| Per-decode timing log (`last_decode_info` / decode log) | `whisper_stt.py` |
| E2E second pass: **one** accurate (processed) first; raw only if still weak | [`interview_e2e_loopback.py`](../app/services/interview_e2e_loopback.py) |
| Skip edge-only second pass on short + strong bank hit (≥0.78, ≤6 words) | [`stt_confidence.py`](../app/services/stt_confidence.py) |
| Bench script (stress-holdout-v2 06/07/08 only) | [`scripts/bench_whisper_latency.py`](../../scripts/bench_whisper_latency.py) |

Live path already used single accurate then raw-if-weak; left aligned.

## Latency-dev bench (after)

Pack: `stress-holdout-v2` short/medium/long folders — **not** holdout v2.

| Label | beam | first-pass p50 | p90 | goal ≤1200 |
|-------|------|----------------|-----|------------|
| track_a_after | 2 | 921.6 ms | 1045 ms | PASS |
| **track_a_beam3 (final)** | **3** | **923.5 ms** | **1053 ms** | **PASS** |

Artifacts: `STT_LATENCY_BENCH_track_a_beam3.json`, `STT_LATENCY_BENCH_LATEST.json`

Beam **2** met the latency goal but regressed short length (5/8). Final choice: **beam=3** + `best_of=1`.

## Frozen regressions (after final settings)

| Suite | Intent | HC wrong | Notes |
|-------|--------|----------|-------|
| `clean` | **28/30 (93.3%)** | **0** | Post median ≈1225 ms |
| `short_length` | **8/8 (100%)** | **0** | Restored after beam=3 |

## Out of scope (deferred)

- Track B — Compound part coverage / answer composition  
- Track C — Generalization dev corpus  
- Holdout v3  
- Semantic recovery latency (~0.5–1 s still in post-speech on long E2E paths)

## Verdict

**Track A accepted.** Whisper first-pass median on latency-dev is **~0.92 s** (≤1.2 s). Ready for **Track B** when scheduled. System remains **NOT READY** for interview until B+C+v3.
