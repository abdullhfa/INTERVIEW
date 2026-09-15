# V4 step 4 — conservative apply recovery

**Verdict:** STEP4_PASS
**Created:** 2026-09-13T21:35:22.200299+00:00

When legacy blob-apply abstains: if hybrid-rank #1 == semantic #1, final>=0.45, agree>=0.88, meaning_ok, margin ok, and current is not strong → apply that intent as weak only (CONSERVATIVE_RANK_APPLY).

## Primary — failing clips

| metric | before | after |
|---|---|---|
| applied and gold | 0 | 1 |
| applied wrong | 0 | 0 |
| gold in hybrid top-5 | 13 | 13 |
| gold at hybrid #1 | 6 | 6 |
| conservative applies | 0 | 1 |

## Guards

| guard | result |
|---|---|
| applied intent changed on currently-passing | 0 (PASS) |
| new strong + non-gold | 0 (PASS) |
| passing-cohort wrong applies | 27 -> 27 (PASS) |

## Newly applied gold

| clip | after id | reason |
|---|---|---|
| fuh3_102 | tech.audio_retention | recovered:conservative_rank:no_match |
