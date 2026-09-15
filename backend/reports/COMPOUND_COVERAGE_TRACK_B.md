# Track B — Compound Gold-Part Coverage

**Status:** CLOSED (accepted for handoff to Track C)  
**Date:** 2026-09-12  
**Pack:** `frontend/public/voice-drill/compound-dev/` (eval-only; not Final Holdout)  
**Locks kept:** Track A STT frozen · Holdout v2 unused · no Intent weight/threshold/alias chasing

## Goal

Close the gap where compound **Intent** could pass while **gold-part coverage** stayed ~40%:

```text
requested_parts → detected_parts → matched_intents → answer_fragments → final_answer
```

Gate (compound-dev only):

| Metric | Gate | Result |
|--------|------|--------|
| Compound intent | ≥ 95% | **100%** (40/40) |
| Gold-part coverage | ≥ 90% | **95%** |
| HC wrong | = 0 | **0** |
| Duplicate answer rate | ≈ 0 | **0.05** (pass) |
| Failure codes in report | yes | OK:39, ANSWER_TOO_SHORT:1 |
| Median post-speech | observe (≤1.5s if possible) | **4608 ms** (not reopened Track A) |

Suite gate: **PASS** (`COMPOUND_DEV_REPORT.json` → `track_b_gate`).

## Before → after (compound-dev)

| Stage | Gold-part (mean) | Notes |
|-------|------------------|-------|
| Pre–Track B (Holdout v2 diagnostic) | ~43% | Path/intent vs gold-parts mismatch |
| Early Track B E2E | ~41–48% | Strong-single bypass; fake cov=1.0; weak split |
| Offline after facet/clause fixes | **100%** (40/40 ≥0.9) | Text path |
| Final E2E `compound_dev` | **95%** | Audio + STT; Intent 100%; HC=0 |

## Changes shipped

| Change | Where |
|--------|--------|
| Enter compound when labeled/detected compound (no strong-single skip) | `interview_e2e_loopback.py`, `answer_generator.py` |
| Honest coverage (no force 1.0 unless answered ≥ requested) | `compound_question_pipeline.py` |
| Same-id-only dedupe; one short sentence per part | `compound_question_pipeline.py`, `compound_answer_builder.py` |
| Stage metrics + `failure_code` | `CompoundResolution` / E2E / `COMPOUND_DEV_REPORT` |
| Clause-first + bank-friendly facets; avoid inventing project Qs from bare “cosine” | `compound_question_decomposer.py` |
| Ordered topic-list / “in that order” detection | `compound_question_detector.py` |
| Soft harvest + distinct-id alternate match | `compound_question_pipeline.py` |
| New 40-case pack + synth + `--suite compound_dev` | `scripts/build_compound_dev_scripts.py`, `synthesize_compound_dev.py` |

## Failure-code histogram (final E2E)

| Code | Count |
|------|------:|
| OK | 39 |
| ANSWER_TOO_SHORT | 1 |

## Artifacts

- `COMPOUND_DEV_REPORT.html` / `.json`
- Pack: `compound-dev/scripts.json` + `audio/`
- Unit: `tests/test_compound_question.py` — 9 passed

## Out of scope / next

- **Track C — Generalization** (medium / ultra-short / indirect / far / poor) on a **new** dev corpus  
- Holdout v3 only after C + frozen regressions  
- Do not chase median post-speech via Whisper reopen (Track A frozen); compound/semantic cost dominates remaining latency

## Verdict

**Track B accepted.** Compound-dev meets Intent ≥95%, gold-part ≥90%, HC=0. System remains **NOT READY** until Track C + Holdout v3.
