# V5 Phase B7 — representation (P) + segmentation residual (S)

Created: 2026-09-14T05:52:47.102789+00:00

Measurement only. No `app/` file modified.

## Instrument defect found before running B7

- question_bank.load(force=True) without warm() drops alias_matrix
- effect: hybrid semantic term (_W_SEM=0.34) = 0; every strong match demoted to weak
- proof: all 120 hybrid_top5 rows in V5_B5_RESIDUAL_MATCHING.json have semantic=0.0 while semantic_intent_index scored 0.57 on the same fragments
- affected: V5_B3 (H rows onward), V5_B4, V5_B5, V5_B6, V5_B61

| baseline | coverage | wrong | hc |
|---|---:|---:|---:|
| as measured in B6/B6.1 (alias_matrix=None) | 0.4146 | 4 | 0 |
| repaired (semantic term restored) | 0.4878 | 4 | 0 |

> the B5 bucket HYBRID_RANKING and the B6/B6.1 verdict 'ranking path closed' were measured with the bank's semantic term disabled and must be re-qualified before that path is treated as closed

## Target reachability (before any arm runs)

| clip | gold | bucket | verdict | why |
|---|---|---|---|---|
| fuh4_080 | `tech.overfitting` | SEGMENTATION_RESIDUAL | **REACHABLE** | gold tokens present in the utterance |
| fuh4_080 | `tech.overfitting_prevent` | SEGMENTATION_RESIDUAL | **REACHABLE** | gold tokens present in the utterance |
| fuh4_080 | `tech.evaluate_classification` | SEGMENTATION_RESIDUAL | **UNREACHABLE_NO_EVIDENCE** | no gold token occurs in the utterance |
| fuh4_083 | `cv.pmp_value` | CANDIDATE_GENERATION | **UNREACHABLE_NO_EVIDENCE** | no gold token occurs in the utterance |
| fuh4_084 | `tech.prompt_injection_what` | SEMANTIC_PROFILE_QUALITY | **UNREACHABLE_STT_LOSS** | ASR lost ['prompt'] |
| fuh4_084 | `hard.injection_in_pdf` | CANDIDATE_GENERATION | **UNREACHABLE_NO_EVIDENCE** | no gold token occurs in the utterance |
| fuh4_089 | `cv.langgraph` | CANDIDATE_GENERATION | **UNREACHABLE_STT_LOSS** | ASR lost ['langgraph'] |

Reachable targets: **2 / 7** — the ceiling for B7.

## Arms

| arm | coverage | hit | wrong | hc | target recovered | newly broken (opened) | newly broken (all) |
|---|---:|---:|---:|---:|---:|---:|---:|
| A0_baseline_as_measured_in_B6 (alias_matrix=None) | 0.4146 | 17/41 | 4 | 0 | 0/7 | 1 | 17 |
| A_baseline_semantic_restored | 0.4878 | 20/41 | 4 | 0 | 1/7 | 1 | 10 |
| P_representation | 0.439 | 18/41 | 4 | 0 | 1/7 | 1 | 12 |
| S_segmentation | 0.4878 | 20/41 | 4 | 0 | 1/7 | 1 | 10 |
| PS_representation_plus_segmentation | 0.439 | 18/41 | 4 | 0 | 1/7 | 1 | 12 |

## Gates

Baseline newly_broken: opened=1, all_single=10. The `all_single` baseline is not zero — it counts pre-existing single-path misses — so for that column the test is 'no worse than baseline'.

| arm | coverage +0.02 | wrong<=4 | hc=0 | nb_opened=0 | nb_opened<=base | nb_all<=base | target>0 | ALL |
|---|---|---|---|---|---|---|---|---|
| P_representation | False | True | True | False | True | False | True | **False** |
| S_segmentation | False | True | True | False | True | True | True | **False** |
| PS_representation_plus_segmentation | False | True | True | False | True | False | True | **False** |

## VERDICT: NO_WINNER_BUT_BASELINE_MOVED — no arm passed the gates, and the repaired baseline differs from the one B6/B6.1 used, so phase 2 cannot be closed on those numbers

