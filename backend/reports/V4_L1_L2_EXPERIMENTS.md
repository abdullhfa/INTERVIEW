# V4 L1/L2 offline experiments

Created: 2026-09-13T18:59:51.028083+00:00

measurement only — no threshold, weight, alias or pipeline change; does not touch _MIN_ANSWER_SCORE / margin rules

## L1 VERDICT

**HYBRID_RANKING** — Gold demoted out of hybrid on 5/12 clips (semantic hit, hybrid miss) — ranking before depth.

Buckets: `{'6-25': 1, '>25': 4, '1-5': 7}`

| count | n |
|---|---|
| rank_1_5 | 7 |
| rank_6_25 | 1 |
| rank_gt_25_or_absent | 4 |
| gold_in_semantic_top5 | 7 |
| gold_in_hybrid_top5 | 5 |
| gold_at_hybrid_1 | 3 |
| semantic_hit_hybrid_demote | 5 |
| hybrid_present_still_failed | 5 |

### Depth per clip

| id | sem rank | bucket | hyb rank | in hyb |
|---|---|---|---|---|
| fuh3_091 | 8 | 6-25 | None | False |
| fuh3_092 | 27 | >25 | None | False |
| fuh3_093 | 1 | 1-5 | None | False |
| fuh3_094 | 2 | 1-5 | None | False |
| fuh3_096 | 53 | >25 | 2 | True |
| fuh3_097 | 5 | 1-5 | None | False |
| fuh3_098 | 1 | 1-5 | 1 | True |
| fuh3_099 | 2 | 1-5 | None | False |
| fuh3_100 | 1 | 1-5 | None | False |
| fuh3_101 | 38 | >25 | 1 | True |
| fuh3_102 | 1 | 1-5 | 1 | True |
| fuh3_104 | 35 | >25 | 5 | True |

### Variants

```json
{
  "A_current": {
    "n_failures": 12,
    "gold_in_hybrid_top5": 5,
    "gold_at_hybrid_1": 3,
    "applied_and_gold": 0
  },
  "B_no_blob_proxy": {
    "n_failures": 12,
    "gold_in_hybrid_top5": 8,
    "gold_at_hybrid_1": 4,
    "applied_and_gold": 0
  },
  "C_score_floor_observation": {
    "clips_where_apply_would_lower_identical_id": 1,
    "of_those_currently_passing": 1,
    "examples": [
      {
        "clip": "fuh3_083",
        "was": 0.597,
        "would_be": 0.568,
        "intent_ok": true
      }
    ]
  }
}
```

## L2 summary

n_cases=7 · **D_VERDICT:** SURFACES_GOLD_WEAKLY_ACCEPT_BLOCKED — promising direction, not yet base

Note: C accepts often but mostly duplicate_of_parent (4/5); D keeps wrong=0 and surfaces 1/7 via real cosine+exclude — too thin to adopt; do not touch accept thresholds yet.

| variant | accepted | new_gold | duplicate | wrong | surfaced_correct_rank1 |
|---|---|---|---|---|---|
| A_alone | 0 | 0 | 0 | 0 | — |
| B_topic_hint | 0 | 0 | 0 | 0 | — |
| C_subject_carry | 5 | 1 | 4 | 0 | — |
| D_embed_exclude_parent | 0 | 0 | 0 | 0 | 1 |

