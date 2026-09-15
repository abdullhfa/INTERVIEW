# V5_MEASUREMENT_PARITY

- generated: 2026-09-13T23:45:12.841631+00:00
- semantic_index_ready: **True**   alias_matrix: **True** (2350 rows)
- compound clips: 15

## Coverage on the identical 15 clips

| run | gold parts hit | coverage_by_part | wrong_intent |
|---|---|---|---|
| recorded | 15/41 | 0.3659 | 12 |
| live_prod_parity | 15/41 | 0.3659 | 12 |
| live_bare | 7/41 | 0.1707 | 4 |

## First divergence vs the recorded v4 trace

- `live_bare` (what variant A did): {'DETECTION': 10, 'NONE': 5}
- `live_prod_parity` (forced detection, as v4 ran): {'NONE': 15}
- clips reproduced exactly by prod parity: **15/15**

## VERDICT

- coverage gap cause: **HARNESS_MISMATCH_FORCED_DETECTION** (forced detection closes 100.0% of the 0.1707 -> 0.3659 gap)
- residual live-vs-recorded difference: **NONE_LIVE_REPRODUCES_RECORDED_EXACTLY** (0 clip(s))
- previous `A_current_live` baseline: **INVALID**

| clip | rec type | bare detector | forced | bare stage | prod stage |
|---|---|---|---|---|---|
| fuh4_076 | compound | compound | False | NONE | NONE |
| fuh4_077 | compound | compound | False | NONE | NONE |
| fuh4_078 | compound | compound | False | NONE | NONE |
| fuh4_079 | compound | single | True | DETECTION | NONE |
| fuh4_080 | compound | single | True | DETECTION | NONE |
| fuh4_081 | compound | single | True | DETECTION | NONE |
| fuh4_082 | compound | single | True | DETECTION | NONE |
| fuh4_083 | compound | compound | False | NONE | NONE |
| fuh4_084 | compound | single | True | DETECTION | NONE |
| fuh4_085 | compound | single | True | DETECTION | NONE |
| fuh4_086 | compound | single | True | DETECTION | NONE |
| fuh4_087 | compound | compound | False | NONE | NONE |
| fuh4_088 | compound | single | True | DETECTION | NONE |
| fuh4_089 | compound | single | True | DETECTION | NONE |
| fuh4_090 | compound | single | True | DETECTION | NONE |

## Stage 1 — detection (the whole coverage gap)

The bare detector classifies **10 of 15** labeled-compound clips as SINGLE. `resolve_compound_question` then returns at line 230 of `compound_question_pipeline.py` with `used_compound_path=False` and no selected intents. `interview_e2e_loopback.run_clip` never hits this because it overrides the detector for labeled packs (`ComplexityDetection("compound", 0.9, ..., ("labeled_compound_pack",))`).

Clips broken by this: `fuh4_079`, `fuh4_080`, `fuh4_081`, `fuh4_082`, `fuh4_084`, `fuh4_085`, `fuh4_086`, `fuh4_088`, `fuh4_089`, `fuh4_090`

## Stage 3-4 — residual live-vs-recorded differences under forced detection

| clip | stage | detail | recorded selected | live selected |
|---|---|---|---|---|

### Fragment-level component breakdown for those clips

Live `top_matches` on the recorded fragment, showing where the cosine term sits.

## Consequence for the Phase B baseline

`A_current_live` in `V5_COMPOUND_COUNTERFACTUALS` is **INVALID**: variant A called resolve_compound_question() with no detection, so the bare detector classified 10 of 15 labeled-compound clips as SINGLE and the pipeline returned immediately with used_compound_path=False and no selected intents. The v4 production harness forces ComplexityDetection('compound', 0.9, ...) for labeled compound packs. Variants B-I were additionally fed the RECORDED sub_questions, i.e. the output of that forced decomposition, so A and B-I never shared a starting condition.

Invalidated: A_current_live coverage_by_part; A_current_live wrong_intent (the Phase B guard baseline); every A-vs-variant delta in V5_COMPOUND_COUNTERFACTUALS.

