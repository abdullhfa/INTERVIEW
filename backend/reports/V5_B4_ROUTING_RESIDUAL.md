# V5 Phase B4 — residual routing

Created: 2026-09-14T00:06:14.116153+00:00
`semantic_index_ready=True` — warm

Measurement only. No `app/` file modified. No ranking/threshold changes.
R1_min8w is fixed. Question under test: does guarded R5 buy enough entry?

## Routing family (guard = ≥2 accepted intents before pre-empt)

| routing | telegraphic recovered | still blocked | opens non-compound | newly_broken unguarded | newly_broken GUARDED |
|---|---:|---|---:|---:|---:|
| detector_only | 0/10 | fuh4_079, fuh4_080, fuh4_081, fuh4_082, fuh4_084, fuh4_085, fuh4_086, fuh4_088, fuh4_089, fuh4_090 | 0/105 | 0 | **0** |
| R1_min8w | 6/10 | fuh4_079, fuh4_080, fuh4_082, fuh4_089 | 7/105 | 0 | **0** |
| R5_min8w | 3/10 | fuh4_080, fuh4_081, fuh4_084, fuh4_085, fuh4_086, fuh4_088, fuh4_090 | 13/105 | 2 | **0** |
| R1_or_R5_min8w | 9/10 | fuh4_080 | 19/105 | 2 | **0** |

## fuh4_080 — structural diagnosis only (no special rule)

- transcript: `Define overfitting detection signals in your mitigation playbook.`
- fragments (comma/and/then): 1 → `['Define overfitting detection signals in your mitigation playbook']`
- sentences ([.?!]): 1 → `['Define overfitting detection signals in your mitigation playbook.']`
- R1_min8w=False — needs >=2 short verbless fragments under comma/and/then split
- R5_min8w=False — needs >=2 sentences under [.?!] split
- hypothesis: Likely a single orthographic sentence / single detector fragment that packs two asks without a comma/and/then OR a sentence boundary the current R5 sees. Missing family is probably 'juxtaposed asks without list punctuation' (e.g. colon, em-dash, bare apposition, or soft conjunction the splitter ignores), not a vocabulary gap.

## Evidence trade-off (forced path on all 15)

| config | coverage | hit | wrong |
|---|---:|---:|---:|
| forced | evidence=off | split=- | action=- | 0.3171 | 13/41 | 10 |
| forced | evidence=off | split=I | action=H | 0.4634 | 19/41 | 10 |
| forced | evidence=0.4 | split=I | action=H | 0.4146 | 17/41 | 5 |
| forced | evidence=0.4 | split=- | action=- | 0.2927 | 12/41 | 6 |

**Forced I+H delta with evidence 0.4:** coverage 0.4634 → 0.4146 (-0.0488); wrong 10 → 5 (-5).

## Production projection (entry rule + ≥2-intent guard + optional evidence/I/H)

| config | recovered | opens NC | newly_broken | coverage | hit | wrong |
|---|---:|---:|---:|---:|---:|---:|
| PROJ detector_only | evidence=off | split=- | action=- | guard=ge2 | 0/10 | 0 | 0 | 0.2439 | 10/41 | 6 |
| PROJ detector_only | evidence=off | split=I | action=H | guard=ge2 | 0/10 | 0 | 0 | 0.3171 | 13/41 | 5 |
| PROJ detector_only | evidence=0.4 | split=I | action=H | guard=ge2 | 0/10 | 0 | 0 | 0.3171 | 13/41 | 4 |
| PROJ R1_min8w | evidence=off | split=- | action=- | guard=ge2 | 6/10 | 7 | 0 | 0.2683 | 11/41 | 9 |
| PROJ R1_min8w | evidence=off | split=I | action=H | guard=ge2 | 6/10 | 7 | 0 | 0.4146 | 17/41 | 8 |
| PROJ R1_min8w | evidence=0.4 | split=I | action=H | guard=ge2 | 6/10 | 7 | 0 | 0.4146 | 17/41 | 4 |
| PROJ R5_min8w | evidence=off | split=- | action=- | guard=ge2 | 3/10 | 13 | 0 | 0.2927 | 12/41 | 8 |
| PROJ R5_min8w | evidence=off | split=I | action=H | guard=ge2 | 3/10 | 13 | 0 | 0.3659 | 15/41 | 7 |
| PROJ R5_min8w | evidence=0.4 | split=I | action=H | guard=ge2 | 3/10 | 13 | 0 | 0.3171 | 13/41 | 5 |
| PROJ R1_or_R5_min8w | evidence=off | split=- | action=- | guard=ge2 | 9/10 | 19 | 0 | 0.3171 | 13/41 | 11 |
| PROJ R1_or_R5_min8w | evidence=off | split=I | action=H | guard=ge2 | 9/10 | 19 | 0 | 0.4634 | 19/41 | 10 |
| PROJ R1_or_R5_min8w | evidence=0.4 | split=I | action=H | guard=ge2 | 9/10 | 19 | 0 | 0.4146 | 17/41 | 5 |

## Decision

- B3 bar (re-measured): cov=0.4146 wrong=4 recovered=6/10
- B4 combo R1+guarded R5+evidence0.4+I/H: cov=0.4146 wrong=5 recovered=9/10 gain=0.0
- Gate: material_gain≥0.02=False; wrong≤4=False; newly_broken=0=True

**VERDICT: STOP_EXPANDING_ROUTING — residual is matching/profile, not entry; do not add more shape rules before analysing remaining misses**
