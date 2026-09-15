FINAL UNSEEN HOLDOUT (EVAL ONLY)
================================

120 scored cases + 2 warm-up clips.
Brand-new transcripts — not copied from development packs.

Layout
------
scripts.json     All rows including warmup
manifest.json    120 scored rows only
pack_meta.json   Counts / gate pointer
audio/*.wav      REQUIRED before E2E (not shipped until synthesized)
PROTOCOL         backend/reports/FINAL_UNSEEN_HOLDOUT_PROTOCOL.md

Build text pack
---------------
  python scripts/build_final_unseen_holdout_scripts.py

Synthesize audio (separate step — do not tune system after listening to fails)
-----------------------------------------------------------------------------
  Produce mono 16 kHz PCM WAV per scripts.json "file" field.
  Mix accents (indian/jordanian/egyptian/emirati synthetic) and conditions
  (clean/office/poor/far/fast) as labeled — do not silo one question type
  to one accent.

Run (frozen settings only)
--------------------------
  python scripts/run_e2e_loopback_tests.py --suite final_unseen_holdout

Rules
-----
- Warm-up plays first; excluded from metrics.
- Do not open the report mid-run to retune.
- If a real bug is fixed, this sample is VOID — build a new Final Holdout.
- last_word_missing on very_long is diagnostic only.

Adoption gate → READY
---------------------
Intent ≥92% · HC wrong=0 · meaning_lost≤1% · median post-speech≤1.5s
· compound coverage≥90% · no unnecessary compound on ultra-short/short

Report: backend/reports/FINAL_UNSEEN_HOLDOUT_REPORT.html
