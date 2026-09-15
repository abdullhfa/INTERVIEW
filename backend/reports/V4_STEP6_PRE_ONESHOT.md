# V4 step 6 — pre-one-shot verification

**Verdict:** STEP6_PASS
**Created:** 2026-09-13T21:48:49.453232+00:00

No new features. Confirms Steps 2–5 + latency/HC gates + voice spot-check + synthesis smoke + lock tooling. Unseen pack v4 + one-shot holdout remain step 7.

## Gates

| gate | result |
|---|---|
| pytest | PASS |
| latency / warm-valid | PASS (LATENCY_READY_FOR_V3) |
| simple median ms | 1138.6 ≤ 1500 |
| compound median ms | 1187.2 ≤ 2000 |
| HC wrong (simple/compound) | 0 / 0 |
| compound intent / coverage | 1.0 / 0.9375 |
| steps 2–5 still PASS | PASS {'step2': 'STEP2_PASS', 'step3': 'STEP3_PASS', 'step4': 'STEP4_PASS', 'step5': 'STEP5_PASS'} |
| spot-check worst rate | 0.75 (PASS ≥0.65) |
| synthesis smoke | PASS |
| lock verify (frozen v3 tooling) | PASS |

## Next

On **STEP6_PASS** only: step **7/7** — author + synthesize + lock the new unseen holdout **v4** pack, then one-shot → GO / NO-GO.
