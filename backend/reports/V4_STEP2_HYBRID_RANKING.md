# V4 step 2 — hybrid ranking

**Verdict:** STEP2_PASS
**Created:** 2026-09-13T21:26:18.782584+00:00

Change: warm+auto splits ranking from apply — hybrid_top5 drops the blob
proxy (real cosine only); apply still uses the legacy blob fill. Cold index
and `always` keep pre-v4 behaviour. No thresholds or apply gates touched.

## Primary — ranking on the failing clips

| metric | before | after |
|---|---|---|
| gold in hybrid top-5 | 8 | 13 |
| gold at hybrid rank 1 | 4 | 6 |
| applied and gold | 0 | 1 |

## Guards

| guard | result |
|---|---|
| applied intent changed on a currently-passing clip | 0 (PASS) |
| new strong + non-gold applies (HC risk) | 0 (PASS) |

## Note on pass rate

The apply gate was deliberately left alone, so `applied_and_gold` and the overall
intent rate are expected to stay flat. Step 2 buys ranking; step 3 converts it.
