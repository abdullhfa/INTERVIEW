# Final Unseen Holdout — Protocol (EVAL ONLY)

**Status:** Intent layer FROZEN · Holdout **v2 = FROZEN / NOT READY** · Next official gate = **v3** only after Tracks A→B→C.

| Pack | Suite | Status |
|------|-------|--------|
| `final-unseen-holdout` | `final_unseen_holdout` | **VOIDED** — see `VOIDED_FINAL_UNSEEN_HOLDOUT_V1.json` |
| `final-unseen-holdout-v2` | `final_unseen_holdout_v2` | **FROZEN** — official NOT READY; do not tune on this pack |
| *(future)* Holdout v3 | TBD | Only after STT latency + compound coverage + generalization dev |

Development order: see `POST_HOLDOUT_DEV_ROADMAP.md` (Track A Whisper latency first).

## Purpose

Judge whether the **frozen** system is READY for a real interview.  
Not a development set. Not for threshold / alias / weight tuning.

## Pack

- **Size:** 120 entirely new cases
- **No reuse** of development transcripts or old WAV files (stress-pilot, stress-holdout-v2, long-accent, realistic suites, etc.)
- **Question types (15 each):**
  - ultra_short
  - short
  - medium
  - long
  - very_long
  - compound
  - indirect_paraphrase
  - follow_up_contextual
- **Conditions (spread, not siloed by type):** clean · office · poor · far · fast
- **Accents (synthetic mix, not one type per accent):** indian · jordanian · egyptian · emirati

## Execution rules (strict)

1. **Warm-up** before scored measurement (discard warm-up from metrics).
2. Run with **frozen** settings only (no live config changes).
3. **Do not** open the report mid-run to retune the system.
4. If a **real bug** is found and fixed → **this sample is no longer Final Holdout**. Build a **new** holdout for the final judgment.
5. `last_word_missing` on very-long is a **diagnostic** metric only — not an automatic fail if intent/meaning still succeed.

## Adoption gate (READY)

| Metric | Gate |
|--------|------|
| Overall Intent | ≥ 92% |
| HC wrong | = 0 |
| meaning_lost | ≤ 1% |
| median post-speech | ≤ 1.5 s |
| Compound coverage | ≥ 90% (**gold-part** coverage of expected intent IDs — not `compound_path` usage) |
| Short / ultra-short fast path | no unnecessary compound regression |

**HC definition:** `match_mode == strong` AND final `intent_ok == False` (score ≥ 0.70).  
Do **not** count gold-ID sibling mismatch as HC when meaning was accepted (`gold_id_mismatch` is separate).

## Report

`FINAL_UNSEEN_HOLDOUT_V2_REPORT.{html,json}` must show:

1. Overall + gate pass/fail  
2. By question type  
3. By audio condition  
4. By accent  
5. Every FAIL: `transcript → expected intent → selected/abstain → failure stage`

## CLI

```bash
# After audio pack is built under frontend/public/voice-drill/final-unseen-holdout-v2/
python scripts/run_e2e_loopback_tests.py --suite final_unseen_holdout_v2
```

## Paths

- Pack (current): `frontend/public/voice-drill/final-unseen-holdout-v2/`
- Pack (voided v1): `frontend/public/voice-drill/final-unseen-holdout/`
- Scripts: `.../scripts.json` + `manifest.json`
- Freeze record: `backend/reports/INTENT_LAYER_FREEZE.json`
- Evaluator audit: `backend/reports/EVALUATOR_AUDIT_FINAL_UNSEEN_HOLDOUT.md`
