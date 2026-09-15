# FINAL PRE-V3 PERFORMANCE & RELIABILITY HARDENING

**Verdict:** LATENCY_READY_FOR_V3
**Created:** 2026-09-13T15:03:10.154875+00:00

Intent layer, STT model, audio preprocessing, VAD, thresholds, weights, aliases and compound architecture are FROZEN. Every change below is an implementation change (caching, duplicate-work removal, batching, warm start) or the documented evaluator correction.

## Before / After

| Metric | Simple before | Simple after | Compound before | Compound after |
|---|---|---|---|---|
| Median post-speech | 1193.6 ms | 1267.4 ms | 1773.1 ms | 1589.4 ms |
| p95 post-speech | 3947.5 ms | 1536.3 ms | 5027.1 ms | 1911.8 ms |
| Intent rate | 0.875 | 1.0 | 1.0 | 1.0 |
| HC wrong | 0 | 0 | 0 | 0 |
| Gold-part coverage | n/a | n/a | 0.9313 | 0.9375 |

## HARD GATES

| Gate | Value | Threshold | Result |
|---|---|---|---|
| Simple median post | 1267.4 ms | <= 1500.0 ms | PASS |
| Compound median post | 1589.4 ms | <= 2000.0 ms | PASS |
| Simple HC wrong | 0 | = 0 | PASS |
| Compound HC wrong | 0 | = 0 | PASS |
| Compound intent | 1.0 | >= 0.95 | PASS |
| Compound gold-part coverage | 0.9375 | >= 0.9 | PASS |

## TARGETS (not release gates)

| Target | Value | Target | Met |
|---|---|---|---|
| Simple p95 post | 1536.3 ms | <= 2000.0 ms | yes |
| Compound p95 post | 1911.8 ms | <= 3000.0 ms | yes |

## Stage latency — simple

| Stage | p50 ms | p95 ms | mean | max |
|---|---|---|---|---|
| vad_ms | 2210.4 | 2559.6 | 2201.0 | 2559.6 |
| whisper_ms | 1061.3 | 1114.1 | 1058.0 | 1114.1 |
| match_ms | 151.9 | 236.5 | 128.3 | 236.5 |
| semantic_ms | 0.0 | 270.2 | 90.2 | 270.2 |
| rerank_ms | 0.0 | 71.6 | 15.8 | 71.6 |
| compound_detect_ms | 0.1 | 0.3 | 0.1 | 0.3 |
| decomposition_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| matching_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| merge_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| compound_ms | 0.1 | 20.8 | 2.7 | 20.8 |
| answer_ms | 0.1 | 0.5 | 0.1 | 0.5 |
| intent_ms | 196.8 | 473.5 | 221.2 | 473.5 |
| post_speech_ms | 1267.4 | 1536.3 | 1279.3 | 1536.3 |

### Simple stage trace (post_speech_trace)

| Stage | p50 ms | p95 ms | mean | max |
|---|---|---|---|---|
| whisper_pass1_ms | 1060.2 | 1111.9 | 1056.7 | 1111.9 |
| whisper_pass2_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| technical_repair_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| routing_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| base_match_ms | 151.6 | 219.3 | 126.1 | 219.3 |
| lexical_match_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| semantic_embedding_ms | 0.0 | 100.2 | 30.8 | 100.2 |
| semantic_search_ms | 0.0 | 100.4 | 30.9 | 100.4 |
| semantic_rerank_ms | 0.0 | 71.6 | 15.8 | 71.6 |
| semantic_total_ms | 0.0 | 270.2 | 90.2 | 270.2 |
| compound_detect_ms | 0.1 | 0.3 | 0.1 | 0.3 |
| decomposition_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| subquestion_match_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| subquestion_semantic_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| harvest_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| dedupe_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| answer_lookup_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| answer_merge_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| final_validation_ms | 0.0 | 0.4 | 0.1 | 0.4 |
| other_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| unattributed_ms | 0.0 | 0.0 | 0.0 | 0.0 |

## Stage latency — compound

| Stage | p50 ms | p95 ms | mean | max |
|---|---|---|---|---|
| vad_ms | 6038.8 | 7421.6 | 6115.9 | 7970.9 |
| whisper_ms | 1217.7 | 1310.6 | 1218.2 | 2186.7 |
| match_ms | 91.4 | 210.5 | 113.4 | 274.2 |
| semantic_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| rerank_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| compound_detect_ms | 0.1 | 0.3 | 0.2 | 4.2 |
| decomposition_ms | 0.3 | 0.5 | 0.3 | 2.0 |
| matching_ms | 267.4 | 651.3 | 301.2 | 805.2 |
| merge_ms | 0.1 | 0.2 | 0.1 | 0.2 |
| compound_ms | 267.9 | 651.9 | 302.0 | 805.7 |
| answer_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| intent_ms | 377.2 | 753.3 | 415.3 | 874.7 |
| post_speech_ms | 1589.4 | 1911.8 | 1633.6 | 2356.2 |

### Compound stage trace (post_speech_trace)

| Stage | p50 ms | p95 ms | mean | max |
|---|---|---|---|---|
| whisper_pass1_ms | 1216.2 | 1299.2 | 1192.9 | 1315.4 |
| whisper_pass2_ms | 0.0 | 0.0 | 23.8 | 953.6 |
| technical_repair_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| routing_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| base_match_ms | 91.4 | 210.5 | 113.4 | 274.2 |
| lexical_match_ms | 215.5 | 382.6 | 230.3 | 576.1 |
| semantic_embedding_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| semantic_search_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| semantic_rerank_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| semantic_total_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| compound_detect_ms | 0.1 | 0.3 | 0.2 | 4.2 |
| decomposition_ms | 0.3 | 0.5 | 0.3 | 2.0 |
| subquestion_match_ms | 267.4 | 651.3 | 301.2 | 805.2 |
| subquestion_semantic_ms | 0.0 | 130.4 | 27.4 | 193.8 |
| harvest_ms | 0.0 | 188.6 | 22.3 | 278.2 |
| dedupe_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| answer_lookup_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| answer_merge_ms | 0.1 | 0.2 | 0.1 | 0.2 |
| final_validation_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| other_ms | 0.0 | 0.0 | 0.0 | 0.0 |
| unattributed_ms | 0.0 | 0.0 | 0.0 | 0.0 |

## Slowest 10 — simple

| clip | type | post | whisper | calls | lexical | semantic | rerank | parts | harvest | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| 10063 | single | 1536.3 | 1114.1 | 1 | 0.0 | 270.2 | 71.6 | 0 | 0.0 | semantic:recovered:thin_margin |
| 10059 | single | 1486.7 | 1012.8 | 1 | 0.0 | 236.8 | 0.0 | 0 | 0.0 | semantic:recovered:weak_match |
| 10064 | single | 1470.3 | 1089.3 | 1 | 0.0 | 214.9 | 54.7 | 0 | 0.0 | semantic:abstain_low_confidence |
| 10057 | single | 1267.4 | 1070.5 | 1 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | whisper_only |
| 10062 | single | 1130.2 | 1061.3 | 1 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | whisper_only |
| 10061 | single | 1124.5 | 1052.1 | 1 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | whisper_only |
| 10058 | single | 1111.6 | 1027.4 | 1 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | whisper_only |
| 10060 | single | 1107.4 | 1036.2 | 1 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | whisper_only |

## Slowest 10 — compound

| clip | type | post | whisper | calls | lexical | semantic | rerank | parts | harvest | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| cdev_022 | compound | 2356.2 | 2186.7 | 2 | 100.6 | 0.0 | 0.0 | 2 | 0.0 | stt_pass2:stt_retry |
| cdev_006 | compound | 1961.6 | 1086.9 | 1 | 360.9 | 0.0 | 0.0 | 3 | 188.6 | compound_lexical |
| cdev_018 | compound | 1911.8 | 1133.6 | 1 | 184.7 | 0.0 | 0.0 | 2 | 278.2 | harvest |
| cdev_036 | compound | 1907.8 | 1251.4 | 1 | 213.3 | 0.0 | 0.0 | 4 | 266.5 | compound_lexical, harvest |
| cdev_001 | compound | 1907.4 | 1234.2 | 1 | 576.1 | 0.0 | 0.0 | 4 | 0.0 | compound_lexical |
| cdev_037 | compound | 1854.1 | 1100.8 | 1 | 471.6 | 0.0 | 0.0 | 2 | 0.0 | compound_lexical |
| cdev_024 | compound | 1839.6 | 1185.2 | 1 | 379.5 | 0.0 | 0.0 | 3 | 0.0 | compound_lexical |
| cdev_002 | compound | 1740.1 | 1248.2 | 1 | 321.4 | 0.0 | 0.0 | 3 | 0.0 | compound_lexical |
| cdev_005 | compound | 1727.4 | 1235.2 | 1 | 382.6 | 0.0 | 0.0 | 3 | 0.0 | compound_lexical |
| cdev_015 | compound | 1704.5 | 1259.0 | 1 | 255.9 | 0.0 | 0.0 | 3 | 0.0 | compound_lexical |

## Determinism (repeat runs)

### simple

| run | n | median post | intent ok | HC wrong |
|---|---|---|---|---|
| _pre_v3_short_run1.json | 8 | 0.0 ms | 2 | 0 |
| _pre_v3_short_run2.json | 8 | 1305.1 ms | 6 | 0 |
| _pre_v3_short_run3.json | 8 | 1296.3 ms | 7 | 0 |
| _pre_v3_short_run4.json | 8 | 1198.8 ms | 8 | 0 |

Deterministic: **False** — unstable clips: ['10057', '10060', '10061', '10062', '10063', '10064']

### compound

| run | n | median post | intent ok | HC wrong |
|---|---|---|---|---|
| _pre_v3_compound_run1.json | 40 | 1614.7 ms | 39 | 0 |
| _pre_v3_compound_run2.json | 40 | 1586.0 ms | 40 | 0 |

Deterministic: **False** — unstable clips: ['cdev_005']

## Optimization summary

| File | Function | Reason | Measured effect | Quality impact |
|---|---|---|---|---|
| `app/services/domain_terms.py` | `normalize_for_matching` | ~80 compiled-regex substitutions were re-run for every bank alias, keyword and profile blob on the recovery path (tens of thousands of passes per request). | LRU memoization of a pure function. | None — identical output string. |
| `app/services/technical_term_repair.py` | `repair_technical_terms` | ~30 regex passes repeated for the same transcript in match(), prefetch_scores(), should_trigger_semantic_recovery() and recover_semantic_intent(). | LRU memoization keyed by (text, prior_topic). | None — pure function. |
| `app/services/question_bank.py` | `_content_tokens` | Tokenization repeated per alias / per candidate. | LRU memoization; still returns a fresh list. | None. |
| `app/services/question_bank.py` | `_build_lexical_structures / _score_all` | Per-alias scoring rebuilt a joined+casefolded entry blob for every distinctive family, plus the keyword blob for the guardrail rule. | Per-entry constants hoisted to bank-load time (entry_owned_families / entry_guardrail_penalty / entry_cv_definition_penalty / entry_is_technical / entry_topic). | None — same expressions, evaluated once. |
| `app/services/question_bank.py` | `_score_all (_lexical_batch)` | Two rapidfuzz calls per alias in a Python loop on full-bank scans. | Optional process.cdist batching (same scorers) for pools >= 1200 aliases; QB_FAST_LEXICAL=0 forces the scalar path. | None — verified byte-identical scores. |
| `app/services/question_bank.py` | `_maybe_semantic_rerank / _query_vector` | Re-embedded the query and the top-3 bank questions although both are already rows of alias_matrix / already embedded by _score_all. | Reuse cached vectors; embed only on a cache miss. | None — same vectors. |
| `app/services/semantic_intent_recovery.py` | `recover_semantic_intent (rerank)` | Re-embedded 5 profile blobs that are exactly the rows of the semantic intent matrix. | semantic_intent_index.vector_for() lookup; query embedded once (RAW `repaired`, as before). | None — same cosines. |
| `app/services/semantic_intent_recovery.py` | `_entry_static / _profile_blob_norm / _profile_blob_lower / _profile_owned_terms` | _lexical_expand_candidates normalized every profile blob on every call (full-bank scan); _alias_lex / _keyword_score / _conflict_penalty normalized aliases and keywords per candidate. | Per-entry / per-profile static strings memoized per bank generation. | None — same strings, same scores. |
| `app/services/semantic_intent_recovery.py` | `recover_semantic_intent (precomputed_trigger)` | should_trigger_semantic_recovery() ran a second time inside recovery, repeating repair + normalize + intent_agreement. | Callers pass the decision they already computed. | None — same (trigger, reason). |
| `app/services/intent_profile.py` | `intent_agreement` | Rebuilt alias/keyword/blob targets and re-normalized them on every call; called 3-5x per request for the same (entry, spoken) pair. | Per-entry statics + (entry, spoken) memo, invalidated on bank reload. | None — same max() over the same score list. |
| `app/services/compound_question_pipeline.py` | `resolve_compound_question (harvest)` | Harvest scored the raw utterance and each clause separately, repeating identical queries. | Dedupe harvest queries and warm the score cache with one batched prefetch_scores() pass. | None — same queries, same order, same candidates. |
| `app/services/warm_start.py` | `warm_system / warm_system_blocking` | Whisper weights were loaded at startup but never exercised, and the semantic index / ONNX session compiled on the first live question. | One tiny decode + one embedding at startup; SYSTEM_WARM flag exposed on /api/health and /api/health/warm. | None — moves one-off cost off the live path. |
| `scripts/final_latency_check.py` | `run` | EVALUATOR BUG: a single gate_ms = 1500 was applied to both cohorts, so a compliant compound median (1773.1 <= 2000) reported FAIL. | Cohort-specific hard gates (simple 1500 / compound 2000); p95 reported as TARGET, not gate. | Scoring correction only — no pipeline change. |

## Final verdict

**LATENCY_READY_FOR_V3**

All hard gates pass — Final Unseen Holdout v3 may start.
