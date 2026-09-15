# V4 step 3 — score floor

**Verdict:** STEP3_PASS
**Created:** 2026-09-13T21:31:12.152960+00:00

Change: when recovery re-selects the same intent as `current`, the emitted
score is `max(exist_m.score, current.score, best_score)` so recovery cannot
lower an already-held score. Apply gates / thresholds / L2 untouched.

## Synthetic proof (exist &lt; current, same id)

| | score |
|---|---|
| before (no current in max) | 0.55 |
| after (include current) | 0.6 |
| expected after | 0.60 |
| ok | True |

## Live invariant

| metric | before | after |
|---|---|---|
| identical-id score lowered | 0 | 0 |
| identical-id score lifts | — | 0 |

## Ranking non-regression (failing clips)

| metric | before | after |
|---|---|---|
| gold in hybrid top-5 | 13 | 13 |
| gold at hybrid #1 | 6 | 6 |

## Guards

| guard | result |
|---|---|
| applied intent changed on currently-passing | 0 (PASS) |
| new strong + non-gold | 0 (PASS) |

Live v3 re-score may already have exist_m.score >= current.score after step 2; the synthetic case proves the deferred bug class is closed.
