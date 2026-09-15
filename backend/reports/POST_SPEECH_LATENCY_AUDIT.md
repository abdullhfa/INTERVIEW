# Post-Speech Latency Audit

**Status:** DIAGNOSTIC (Track A/B frozen — no STT or compound-coverage retune)
**E2E source:** `COMPOUND_DEV_REPORT.json` (compound-dev, n=40)
**Offline source:** text-only compound-dev (n=40)

## Verdict

- E2E median **total_post_ms = 4608.0 ms** (observe gate <=1500 for READY later).
- E2E median **whisper_ms = 1605.6 ms** — STT is not the main leftover after Track A.
- Dominant leftover: **compound matching_ms p50 = 1001.4 ms** + **semantic_ms p50 = 711.6 ms** (+ first-pass **match_ms p50 = 528.0 ms**).
- Decomposition / merge are tiny (decomp p50=0.3 ms, merge p50=0.1 ms).

## E2E breakdown (compound-dev audio)

| Stage | p50 ms | p90 ms | mean | max |
|-------|--------|--------|------|-----|
| whisper_ms | 1605.6 | 3199.0 | 2157.5 | 4326.6 |
| match_ms (pre-compound bank) | 528.0 | 953.9 | 586.5 | 1236.7 |
| semantic_ms | 711.6 | 1193.7 | 586.7 | 1996.1 |
| rerank_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| compound_detect_ms | 0.6 | 0.7 | 0.7 | 3.6 |
| decomposition_ms | 0.3 | 0.4 | 0.4 | 2.4 |
| matching_ms (compound) | 1001.4 | 2140.7 | 1121.1 | 2770.6 |
| merge_ms | 0.1 | 0.2 | 0.1 | 0.2 |
| compound_ms (detect+resolve) | 1002.3 | 2141.6 | 1122.3 | 2771.5 |
| intent_ms (match+sem+compound) | 2304.3 | 3430.7 | 2295.5 | 4283.9 |
| **total_post_ms** | 4608.0 | 6347.5 | 4453.0 | 7360.4 |

## Offline compound stages (no Whisper)

| Stage | p50 ms | p90 ms | mean | max |
|-------|--------|--------|------|-----|
| compound_detect_ms | 0.5 | 0.7 | 0.5 | 0.8 |
| decomposition_ms | 0.3 | 0.4 | 0.3 | 0.5 |
| matching_ms | 723.5 | 1409.7 | 817.5 | 2575.4 |
| merge_ms | 0.1 | 0.3 | 0.2 | 0.3 |
| compound resolve total | 724.1 | 1410.2 | 818.0 | 2576.0 |

## Interpretation

1. Track A succeeded: Whisper is ~1–2s median on this pack, not ~3s.
2. Compound **matching** (per-part `question_bank.match` + harvest `top_matches`) is the largest compound-internal cost (~1s median).
3. **Semantic recovery** often adds hundreds of ms–>1s when triggered (compound-dev enables realistic recovery).
4. Detect / decompose / merge are not the bottleneck.
5. Do **not** hide this behind Track C Intent gains — READY still needs post-speech well below 4.6s after generalization.

## Next (ordered)

1. **Track C — Generalization** (new dev set; no Holdout v2).
2. Separate **compound/semantic latency cut** (still frozen STT) once C is underway or after C gate.
3. Only then Final Holdout v3.

## Instrumentation note

`StageTimings` now records `compound_detect_ms`, `decomposition_ms`, `matching_ms`, `rerank_ms`, `merge_ms` on new E2E runs. This audit used the frozen Track B report plus offline text timing.
