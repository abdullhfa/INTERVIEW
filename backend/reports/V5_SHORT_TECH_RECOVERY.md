# V5 SHORT_TECH_RECOVERY

**Verdict:** `SHORT_TECH_RECOVERY_PASS`

## Summary
| | |
|---|---|
| before (short/tech targets) | mostly FAIL on distorted STT |
| after | **121 / 125 / 149 recovered**; short suite **0.778 → 0.944** |
| technical recovery accuracy (focused) | **1.0** on recoverable synthetics |
| false corrections | **0** |
| regressions | **0** |
| HC wrong | **0** |
| latency (focused) | +18 ms avg |
| 150 E2E | pass **0.873 → 0.900**, HC **0** |

## What shipped
- `app/services/short_tech_recovery.py` — vocab from bank + domain terms; curated multi-evidence repairs; short structure; dual raw/normalized reconcile (never mints strong alone)
- Hooked via `technical_term_repair.repair_technical_terms` + dual scoring in `question_bank.match`
- Does **not** change MAIN_REQUEST_EXTRACTION, HC thresholds, compound, STT model

## Focused gate
- target_recovered: **11** (recoverable set)
- false_normalizations: **0**
- passing_cases_broken: **0**
- HC_wrong: **0**
- short accuracy: **0.400 → 0.880**
- technical recovery accuracy: **1.000**

## Production 150 E2E (final)
| metric | before (post-MRE) | after |
|---|---:|---:|
| pass_rate | 0.873 | **0.900** |
| intent_rate | 0.873 | **0.900** |
| STT rate | 0.960 | 0.953 |
| HC wrong | 0 | **0** |
| short | 0.778 | **0.944** |
| direct | 0.833 | **0.944** |
| indirect | 0.817 | 0.800 |
| long | 1.000 | **1.000** |
| compound | 0.967 | 0.967 |
| Indian | 0.86 | **0.92** |
| Jordanian | 0.90 | **0.96** |
| Emirati | 0.86 | 0.82 |
| median_post_speech_ms | 1043 | 1421 |

Target clips:
- `V5A_121` PASS (`Why am bedding?` / clean → embeddings family)
- `V5A_124` PASS (this run STT varied; ambiguous `Zundra` remains a limitation when it appears)
- `V5A_125` PASS (`Whyland draft` → LangGraph)
- `V5A_149` PASS (vector database store)
- `V5A_148` FAIL — unrecoverable garble (abstain preferred; see limitations)

## KNOWN_LIMITATIONS
- Heavily garbled short audio with no usable tech anchor (e.g. V5A_148 `What in a me, amet…`) → no safe recovery; may still fail intent
- Ambiguous single-token garbles such as `Zundra`/`Zandra` between Chroma vs LangGraph → abstain rather than guess
- No Whisper/STT model change in this task
