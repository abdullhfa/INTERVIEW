# V4 step 5 — L2 Variant D compound trailing rescue

**Verdict:** STEP5_PASS
**Created:** 2026-09-13T21:39:07.942177+00:00

After harvest: for dropped/duplicate trailing (or pronoun-heavy) sub-questions, re-rank with clause kept + parent subject carry + same-topic soft filter + exclude parent/already; accept via existing _accept_match only (COMPOUND_VARIANT_D_RESCUE).

## Primary

| metric | before | after |
|---|---|---|
| mean gold-part coverage | 0.5556 | 0.5778 |
| gold parts hit (sum) | 22 | 23 |
| surfaced_correct_rank1 | 5 | 5 |
| rescue gold / wrong | — | 1 / 0 |

## Guards

| guard | result |
|---|---|
| new wrong intents | 0 (PASS) |
| coverage drops | 0 (PASS) |
| _MIN_ANSWER_SCORE unchanged (0.58) | 0.58 (PASS) |

## Coverage gains

| clip | before | after | new gold |
|---|---|---|---|
| fuh3_080 | 0.333 | 0.667 | tech.overfitting_prevent |
