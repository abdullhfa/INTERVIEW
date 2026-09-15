# V5 Phase B3 — routing entry + evidence-grounded acceptance

Created: 2026-09-13T23:54:05.738193+00:00
`semantic_index_ready=False` — COLD — ordering only; absolute coverage is a lower bound

Measurement only. No `app/` file was modified.

## Step 1 — why telegraphic compound never enters the path

10 of 15 compound clips are classified SINGLE by `detect_question_complexity`, so `compound_question_pipeline.py:230` returns with `used_compound_path=False`.

| clip | terminal branch | fragments | action cue in utterance | rules that would open |
|---|---|---:|---|---|
| fuh4_079 | no_multi_request_signal | 2 | True | R5_multi_sentence_request, R5_min8w, R1_or_R5_min8w, R1_or_R4_or_R5_min8w, R1_or_R5_min10w |
| fuh4_080 | no_multi_request_signal | 1 | True | — |
| fuh4_081 | no_multi_request_signal | 3 | True | R1_verbless_series, R4_determiner_series, R1_or_R2, R1_or_R4, R1_or_R2_or_R4, R1_min8w, R1_or_R5_min8w, R1_or_R4_or_R5_min8w, R1_or_R5_min10w |
| fuh4_082 | no_multi_request_signal | 1 | True | R5_multi_sentence_request, R5_min8w, R1_or_R5_min8w, R1_or_R4_or_R5_min8w, R1_or_R5_min10w |
| fuh4_084 | no_multi_request_signal | 3 | False | R1_verbless_series, R3_no_finite_verb_series, R1_or_R2, R1_or_R4, R1_or_R2_or_R4, R1_min8w, R1_or_R5_min8w, R1_or_R4_or_R5_min8w |
| fuh4_085 | no_multi_request_signal | 3 | True | R1_verbless_series, R1_or_R2, R1_or_R4, R1_or_R2_or_R4, R1_min8w, R1_or_R5_min8w, R1_or_R4_or_R5_min8w, R1_or_R5_min10w |
| fuh4_086 | no_multi_request_signal | 3 | False | R1_verbless_series, R3_no_finite_verb_series, R1_or_R2, R1_or_R4, R1_or_R2_or_R4, R1_min8w, R1_or_R5_min8w, R1_or_R4_or_R5_min8w |
| fuh4_088 | no_multi_request_signal | 3 | False | R1_verbless_series, R3_no_finite_verb_series, R1_or_R2, R1_or_R4, R1_or_R2_or_R4, R1_min8w, R1_or_R5_min8w, R1_or_R4_or_R5_min8w |
| fuh4_089 | no_multi_request_signal | 2 | True | R5_multi_sentence_request, R5_min8w, R1_or_R5_min8w, R1_or_R4_or_R5_min8w, R1_or_R5_min10w |
| fuh4_090 | no_multi_request_signal | 4 | True | R1_verbless_series, R1_or_R2, R1_or_R4, R1_or_R2_or_R4, R1_min8w, R1_or_R5_min8w, R1_or_R4_or_R5_min8w, R1_or_R5_min10w |

### Recall vs false-positive for each candidate routing rule

| rule | recovers (of blocked) | opens non-compound | pre-empted | loses gold | **newly broken** | newly broken with >=2-intent guard |
|---|---:|---:|---:|---:|---:|---:|
| R1_verbless_series | 6/10 | 9/105 | 4 | 1 | **1** | 0 |
| R2_trailing_request_fragment | 0/10 | 1/105 | 0 | 0 | **0** | 0 |
| R3_no_finite_verb_series | 3/10 | 9/105 | 3 | 2 | **2** | 0 |
| R4_determiner_series | 1/10 | 0/105 | 0 | 0 | **0** | 0 |
| R1_or_R2 | 6/10 | 10/105 | 4 | 1 | **1** | 0 |
| R1_and_R2 | 0/10 | 0/105 | 0 | 0 | **0** | 0 |
| R1_or_R4 | 6/10 | 9/105 | 4 | 1 | **1** | 0 |
| R1_or_R2_or_R4 | 6/10 | 10/105 | 4 | 1 | **1** | 0 |
| R1_min8w | 6/10 | 7/105 | 2 | 0 | **0** | 0 |
| R5_multi_sentence_request | 3/10 | 13/105 | 6 | 3 | **3** | 1 |
| R5_min8w | 3/10 | 13/105 | 6 | 3 | **3** | 1 |
| R1_or_R5_min8w | 9/10 | 19/105 | 7 | 3 | **3** | 1 |
| R1_or_R4_or_R5_min8w | 9/10 | 19/105 | 7 | 3 | **3** | 1 |
| R1_or_R5_min10w | 6/10 | 18/105 | 7 | 3 | **3** | 1 |

`newly broken` = a non-compound clip that v4 answered with the correct intent and that the opened compound path would answer with the gold intent absent. `answer_generator.py:351-360` returns the compound answer *before* the strong single bank answer, so these are real regressions, at compound confidence 0.88-0.94 — i.e. high-confidence wrong.

Rules that recover something and break nothing: **R4_determiner_series, R1_min8w**
Same, once a compound answer may only pre-empt when it produced >=2 accepted intents: **R1_verbless_series, R3_no_finite_verb_series, R4_determiner_series, R1_or_R2, R1_or_R4, R1_or_R2_or_R4, R1_min8w**

## Step 2 — evidence-grounded acceptance

32 sub-questions audited, 12 of them facet-derived (`_FACETS` emits up to 3 canonical questions per matched key, which is where fabricated asks come from).

| theta | parts dropped | of which facet-derived |
|---:|---:|---:|
| 0.3 | 6/32 | 6 |
| 0.4 | 7/32 | 7 |
| 0.5 | 9/32 | 9 |
| 0.6 | 9/32 | 9 |

## Step 3 — I / HI measured on top of routing + evidence

| config | coverage | hit | wrong | guard wrong<=12 |
|---|---:|---:|---:|---|
| evidence=off | split=- | action_rules=- | 0.3415 | 14/41 | 11 | ok |
| evidence=off | split=- | action_rules=H | 0.3659 | 15/41 | 10 | ok |
| evidence=off | split=I | action_rules=- | 0.439 | 18/41 | 11 | ok |
| evidence=off | split=I | action_rules=H | 0.4634 | 19/41 | 10 | ok |
| evidence=0.3 | split=- | action_rules=- | 0.2927 | 12/41 | 7 | ok |
| evidence=0.3 | split=- | action_rules=H | 0.3171 | 13/41 | 6 | ok |
| evidence=0.3 | split=I | action_rules=- | 0.3902 | 16/41 | 7 | ok |
| evidence=0.3 | split=I | action_rules=H | 0.4146 | 17/41 | 6 | ok |
| evidence=0.3+anchor | split=- | action_rules=- | 0.2927 | 12/41 | 7 | ok |
| evidence=0.3+anchor | split=- | action_rules=H | 0.3171 | 13/41 | 6 | ok |
| evidence=0.3+anchor | split=I | action_rules=- | 0.3902 | 16/41 | 7 | ok |
| evidence=0.3+anchor | split=I | action_rules=H | 0.4146 | 17/41 | 6 | ok |
| evidence=0.4 | split=- | action_rules=- | 0.2927 | 12/41 | 6 | ok |
| evidence=0.4 | split=- | action_rules=H | 0.3171 | 13/41 | 5 | ok |
| evidence=0.4 | split=I | action_rules=- | 0.3902 | 16/41 | 6 | ok |
| evidence=0.4 | split=I | action_rules=H | 0.4146 | 17/41 | 5 | ok |
| evidence=0.4+anchor | split=- | action_rules=- | 0.2927 | 12/41 | 6 | ok |
| evidence=0.4+anchor | split=- | action_rules=H | 0.3171 | 13/41 | 5 | ok |
| evidence=0.4+anchor | split=I | action_rules=- | 0.3902 | 16/41 | 6 | ok |
| evidence=0.4+anchor | split=I | action_rules=H | 0.4146 | 17/41 | 5 | ok |
| evidence=0.5 | split=- | action_rules=- | 0.2683 | 11/41 | 6 | ok |
| evidence=0.5 | split=- | action_rules=H | 0.2927 | 12/41 | 5 | ok |
| evidence=0.5 | split=I | action_rules=- | 0.3659 | 15/41 | 6 | ok |
| evidence=0.5 | split=I | action_rules=H | 0.3902 | 16/41 | 5 | ok |
| evidence=0.5+anchor | split=- | action_rules=- | 0.2683 | 11/41 | 6 | ok |
| evidence=0.5+anchor | split=- | action_rules=H | 0.2927 | 12/41 | 5 | ok |
| evidence=0.5+anchor | split=I | action_rules=- | 0.3659 | 15/41 | 6 | ok |
| evidence=0.5+anchor | split=I | action_rules=H | 0.3902 | 16/41 | 5 | ok |
| evidence=0.6 | split=- | action_rules=- | 0.2683 | 11/41 | 6 | ok |
| evidence=0.6 | split=- | action_rules=H | 0.2927 | 12/41 | 5 | ok |
| evidence=0.6 | split=I | action_rules=- | 0.3659 | 15/41 | 6 | ok |
| evidence=0.6 | split=I | action_rules=H | 0.3902 | 16/41 | 5 | ok |
| evidence=0.6+anchor | split=- | action_rules=- | 0.2683 | 11/41 | 6 | ok |
| evidence=0.6+anchor | split=- | action_rules=H | 0.2927 | 12/41 | 5 | ok |
| evidence=0.6+anchor | split=I | action_rules=- | 0.3659 | 15/41 | 6 | ok |
| evidence=0.6+anchor | split=I | action_rules=H | 0.3902 | 16/41 | 5 | ok |

Best under guard: evidence=off | split=I | action_rules=H, evidence=off | split=I | action_rules=-, evidence=0.4 | split=I | action_rules=H, evidence=0.4+anchor | split=I | action_rules=H, evidence=0.3 | split=I | action_rules=H

Step 3 assumes routing is solved (every clip forced into the path).

## Step 4 — realistic projection (routing rule + >=2-intent pre-empt guard)

| config | coverage | hit | wrong |
|---|---:|---:|---:|
| routing=R1_min8w | evidence=off | split=- | action=- | 0.2683 | 11/41 | 9 |
| routing=R1_min8w | evidence=off | split=I | action=H | 0.4146 | 17/41 | 8 |
| routing=R1_min8w | evidence=0.4 | split=I | action=H | 0.4146 | 17/41 | 4 |
| routing=R1_min8w | evidence=0.4 | split=- | action=- | 0.2683 | 11/41 | 5 |
| routing=R1_or_R5_min8w | evidence=off | split=- | action=- | 0.3171 | 13/41 | 11 |
| routing=R1_or_R5_min8w | evidence=off | split=I | action=H | 0.4634 | 19/41 | 10 |
| routing=R1_or_R5_min8w | evidence=0.4 | split=I | action=H | 0.4146 | 17/41 | 5 |
| routing=R1_or_R5_min8w | evidence=0.4 | split=- | action=- | 0.2683 | 11/41 | 6 |
| routing=detector_only | evidence=off | split=- | action=- | 0.2439 | 10/41 | 6 |
| routing=detector_only | evidence=off | split=I | action=H | 0.3171 | 13/41 | 5 |
| routing=detector_only | evidence=0.4 | split=I | action=H | 0.3171 | 13/41 | 4 |
| routing=detector_only | evidence=0.4 | split=- | action=- | 0.2439 | 10/41 | 5 |


**Status: PROVISIONAL.** No configuration may be adopted until this table is reproduced with `semantic_index_ready=True` and the routing rule shows zero newly broken non-compound clips.

