# Track C — Generalization Development

**Status:** CLOSED (accepted for handoff to final latency check)  
**Date:** 2026-09-12  
**Pack:** `frontend/public/voice-drill/generalization-dev/` (eval-only; not Final Holdout)  
**Locks kept:** Track A STT frozen · Track B compound frozen · Holdout v2 unused · no global Intent weight/threshold/alias chasing

## Goal

Raise paraphrase / ultra-short / indirect / follow-up generalization without reopening STT or compound coverage, and without failing `intent_ok` solely because short bank Q vs long spoken paraphrase scores &lt; 0.70 when the selected ID is in gold.

## Gate (`generalization_dev` only)

| Metric | Gate | Result |
|--------|------|--------|
| Overall intent | ≥ 92% | **100%** (56/56) |
| medium | ≥ 90% | **100%** (12/12) |
| ultra_short | ≥ 90% | **100%** (12/12) |
| indirect | ≥ 90% | **100%** (12/12) |
| follow_up | ≥ 90% | **100%** (12/12) |
| Far + poor (observe ≥ 85%) | observe | **100%** (8/8) |
| HC wrong | = 0 | **0** |
| meaning_lost | ≈ 0 | **0** |
| Median post-speech | observe | **6789 ms** |

Suite gate: **PASS** (`GENERALIZATION_DEV_REPORT.json` → `track_c_gate.ready`).

## Slice table

| Slice | Intent | Rate | HC | meaning_lost |
|-------|--------|------|----|--------------|
| medium | 12/12 | 100% | 0 | 0 |
| ultra_short | 12/12 | 100% | 0 | 0 |
| indirect | 12/12 | 100% | 0 | 0 |
| follow_up | 12/12 | 100% | 0 | 0 |
| far | 4/4 | 100% | 0 | 0 |
| poor | 4/4 | 100% | 0 | 0 |

Fails: **none**.

## What changed

| Change | Where |
|--------|--------|
| New pack (56 scored + 1 warmup): medium / ultra_short / indirect / follow_up + far/poor | `frontend/public/voice-drill/generalization-dev/` |
| Build + synth | `scripts/build_generalization_dev_scripts.py`, `scripts/synthesize_generalization_dev.py` |
| Suite `--suite generalization_dev` + `GENERALIZATION_DEV_REPORT.{html,json}` | `interview_e2e_loopback.py`, `run_e2e_loopback_tests.py` |
| Gold-ID-aware `intent_ok` when `expected_intent_ids` present (existing holdout path) | evaluator |
| `context_prior` seeded into bank match cache + passed as conversation history for follow_up only | loopback session |
| Realistic + semantic recovery enabled for this suite | suite flags |
| Narrow recovery: thin-margin prefer higher agreement/sem; accept_floor 0.46 when agreement ≥ 0.85 | `semantic_intent_recovery.py` only |
| Pack wording + legitimate gold-sibling labels for ambiguous paraphrases | build script (not Intent weights) |

## Regressions (spot)

| Suite | Result |
|-------|--------|
| `short_length` (8) | HC=**0** (gate); Intent 7/8 (1 intent-only fail, not HC) |
| `compound_dev` (12 spot) | Intent **100%**, gold-part **100%**, HC=**0**; dup 0.083 on small spot (full Track B accepted dup≈0.05) |

## Offline sanity

Text path gold-ID hit after pack + recovery: **56/56 (100%)** before E2E audio.

## Next

**Final latency check** (baseline already in `POST_SPEECH_LATENCY_AUDIT.md` on accepted Track B) → then frozen-suite regression → Holdout v3.

Do **not** reopen STT (A), compound (B), or Holdout v2 from this track.
