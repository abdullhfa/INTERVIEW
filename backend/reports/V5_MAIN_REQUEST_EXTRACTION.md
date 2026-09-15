# V5 MAIN_REQUEST_EXTRACTION

**Verdict:** `MAIN_REQUEST_EXTRACTION_PASS`

## Summary
| | |
|---|---|
| before (targets) | 0/4 |
| after (targets) | **4/4** |
| recovered cases | V5A_091 → `tech.hallucination_prevent`, V5A_100 → `gen.ambiguity`, V5A_102 → `gen.ambiguity`, V5A_112 → `tech.latency_p95` |
| regressions | **0** (direct/short/compound/telegraphic/simple-indirect) |
| HC wrong | **0** |
| latency impact | +7.7 ms avg on focused match path; full E2E median_post **1043 ms** (was ~1297) |

## What shipped
Additive stage only:

`STT → normalization → MAIN_REQUEST_EXTRACTION → match`

- Module: `app/services/main_request_extraction.py`
- Wired in: `live_audio`, `answer_generator`, `interview_e2e_loopback`
- When extraction overrides, match is **mre_locked** so realistic/semantic recovery cannot re-introduce background keyword distraction
- HC thresholds / accept gates / mode ladder unchanged
- Extraction alone does not mint strong mode

## Focused gate
- target_cases_recovered: **4**
- target_pass_after: **4/4**
- passing_cases_broken: **0**
- HC_wrong: **0**
- latency_delta_ms_avg: **7.7**

## Production validation — full 150 E2E (final)
| metric | before | after |
|---|---:|---:|
| pass_rate | 0.867 | **0.873** |
| intent_rate | 0.867 | **0.873** |
| STT rate | 0.967 | 0.960 |
| HC wrong | 0 | **0** |
| audio_fail | 0 | 0 |
| median_post_speech_ms | ~1297 | **1043** |
| Indian | 0.80 | **0.86** |
| Jordanian | 0.94 | 0.90 |
| Emirati | 0.86 | 0.86 |
| long | (prev mixed) | **1.0** |
| indirect | — | 0.817 |
| short | — | 0.778 |
| compound | — | 0.967 |
| direct | — | 0.833 |

Target E2E outcomes after lock:
- `V5A_091` PASS (`tech.hallucination_prevent`, mre_locked)
- `V5A_100` PASS (`gen.ambiguity`, mre_locked)
- `V5A_102` PASS (`gen.ambiguity`, mre_locked)
- `V5A_112` PASS (`tech.latency_p95`, mre_locked)

Full suite verdict: `PASS_150_VOICE_STRESS_E2E`
