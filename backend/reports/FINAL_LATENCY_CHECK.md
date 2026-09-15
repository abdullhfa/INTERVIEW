# Final Latency Check (A+B+C) — evaluator v2

**Verdict:** LATENCY_READY_FOR_V3
**Created:** 2026-09-13T21:19:52.284542+00:00

> Scoring correction: v1 applied a single `gate_ms = 1500` to both cohorts.
> The documented frozen gates are cohort-specific (`simple_median_gate_ms = 1500`, `compound_median_gate_ms = 2000`).
> p95 values are TARGETS, not hard gates.

## HARD GATES

| Gate | Value | Threshold | Result |
|---|---|---|---|
| Simple median post | 1138.6 ms | <= 1500.0 ms | PASS |
| Compound median post | 1187.2 ms | <= 2000.0 ms | PASS |
| Simple HC wrong | 0 | = 0 | PASS |
| Compound HC wrong | 0 | = 0 | PASS |
| Compound intent | 1.0 | >= 0.95 | PASS |
| Compound gold-part coverage | 0.9375 | >= 0.9 | PASS |
| Simple run warm-valid | True (warm before first clip; alias matrix present for every scored clip) | must be True | PASS |
| Compound run warm-valid | True (warm before first clip; alias matrix present for every scored clip) | must be True | PASS |

> A run is warm-valid only when warm-up finished before the first clip and every scored clip saw the alias matrix. A mixed run measured two different systems.

## TARGETS (diagnostic only)

| Target | Value | Target | Met |
|---|---|---|---|
| Simple p95 post | 1352.3 ms | <= 2000.0 ms | yes |
| Compound p95 post | 1340.5 ms | <= 3000.0 ms | yes |
| Simple intent rate | 0.875 | observe | — |

## Simple — short_length (n=8)

Source: `C:\Users\aalsa\OneDrive\Desktop\interview (2)\interview11\backend\reports\LENGTH_SHORT_REGRESSION_REPORT.json`

| Stage | p50 ms | p95 ms | mean | max |
|---|---|---|---|---|
| vad_ms | 2241.8 | 2559.8 | 2214.8 | 2559.8 |
| whisper_ms | 926.6 | 1081.9 | 938.7 | 1081.9 |
| match_ms | 38.2 | 110.1 | 56.1 | 110.1 |
| semantic_ms | 83.1 | 426.3 | 91.1 | 426.3 |
| rerank_ms | 23.0 | 48.8 | 16.8 | 48.8 |
| compound_detect_ms | 0.1 | 0.4 | 0.1 | 0.4 |
| decomposition_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| matching_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| merge_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| compound_ms | 0.1 | 28.4 | 3.6 | 28.4 |
| answer_ms | 0.1 | 0.2 | 0.1 | 0.2 |
| intent_ms | 120.9 | 436.3 | 150.8 | 436.3 |
| post_speech_ms | 1138.6 | 1352.3 | 1089.6 | 1352.3 |

### Slowest 10

| clip | type | post | whisper | calls | lexical | semantic | rerank | parts | harvest | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| 10059 | single | 1352.3 | 915.9 | 1 | 0.0 | 426.3 | 48.8 |  | 0.0 | semantic:abstain_low_confidence |
| 10057 | single | 1185.4 | 1081.9 | 1 | 0.0 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| 10064 | single | 1162.9 | 923.5 | 1 | 0.0 | 129.2 | 31.2 |  | 0.0 | whisper_only |
| 10061 | single | 1138.6 | 940.1 | 1 | 0.0 | 90.2 | 23.0 |  | 0.0 | whisper_only |
| 10063 | single | 1033.1 | 912.1 | 1 | 0.0 | 83.1 | 31.7 |  | 0.0 | whisper_only |
| 10062 | single | 975.9 | 943.1 | 1 | 0.0 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| 10060 | single | 965.0 | 926.6 | 1 | 0.0 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| 10058 | single | 903.8 | 866.3 | 1 | 0.0 | 0.0 | 0.0 |  | 0.0 | whisper_only |

## Compound — compound_dev (n=40)

Source: `C:\Users\aalsa\OneDrive\Desktop\interview (2)\interview11\backend\reports\COMPOUND_DEV_REPORT.json`

| Stage | p50 ms | p95 ms | mean | max |
|---|---|---|---|---|
| vad_ms | 6051.3 | 7420.3 | 6111.3 | 7970.9 |
| whisper_ms | 1027.1 | 1137.0 | 1040.1 | 1789.7 |
| match_ms | 38.2 | 106.0 | 59.9 | 279.5 |
| semantic_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| rerank_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| compound_detect_ms | 0.1 | 0.2 | 0.1 | 0.3 |
| decomposition_ms | 0.2 | 0.5 | 0.3 | 1.2 |
| matching_ms | 101.1 | 187.4 | 108.4 | 231.2 |
| merge_ms | 0.1 | 0.2 | 0.1 | 0.2 |
| compound_ms | 102.0 | 187.7 | 108.9 | 231.8 |
| answer_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| intent_ms | 158.3 | 266.3 | 168.8 | 375.0 |
| post_speech_ms | 1187.2 | 1340.5 | 1208.9 | 1894.5 |

### Slowest 10

| clip | type | post | whisper | calls | lexical | semantic | rerank | parts | harvest | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| cdev_022 | compound | 1894.5 | 1789.7 | 2 | 59.7 | 0.0 | 0.0 |  | 0.0 | stt_pass2:stt_retry |
| cdev_019 | compound | 1343.6 | 968.6 | 1 | 95.0 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| cdev_015 | compound | 1340.5 | 1113.1 | 1 | 135.3 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| cdev_006 | compound | 1338.9 | 1072.9 | 1 | 100.8 | 0.0 | 0.0 |  | 0.3 | whisper_only |
| cdev_002 | compound | 1321.3 | 1105.1 | 1 | 124.3 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| cdev_004 | compound | 1301.8 | 1143.5 | 1 | 119.1 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| cdev_029 | compound | 1291.3 | 1137.0 | 1 | 52.3 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| cdev_024 | compound | 1256.0 | 1086.0 | 1 | 67.3 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| cdev_025 | compound | 1255.1 | 1086.7 | 1 | 130.2 | 0.0 | 0.0 |  | 0.0 | whisper_only |
| cdev_038 | compound | 1250.9 | 1027.1 | 1 | 96.4 | 0.0 | 0.0 |  | 0.8 | whisper_only |

## Next

- **LATENCY_READY_FOR_V3** — proceed to Final Unseen Holdout v3.
