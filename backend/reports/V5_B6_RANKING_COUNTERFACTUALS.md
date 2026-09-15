# V5 Phase B6 — ranking / action-type counterfactuals

Created: 2026-09-14T03:42:52.972679+00:00
`semantic_index_ready=True`

Measurement only. Routing/evidence/profiles frozen.
Target: HYBRID_RANKING + ACTION_GRANULARITY from B5.

| variant | coverage | hit | wrong | hc_risk | target recovered | newly_broken | beats? |
|---|---:|---:|---:|---:|---:|---:|---|
| A_baseline | 0.4146 | 17/41 | 4 | 0 | 0/13 | 1 | — |
| B_action_rerank | 0.439 | 18/41 | 5 | 0 | 0/13 | 1 | no |
| C_action_rerank_same_topic | 0.439 | 18/41 | 5 | 0 | 0/13 | 1 | no |
| D_sem_close_promote | 0.439 | 18/41 | 5 | 0 | 0/13 | 1 | no |
| F_stronger_bank_intent_weights | 0.439 | 18/41 | 5 | 0 | 0/13 | 1 | no |
| G_distinct_across_parts | 0.439 | 18/41 | 5 | 0 | 0/13 | 1 | no |
| H_sem_top1_in_hybrid_pool | 0.3902 | 16/41 | 7 | 0 | 0/13 | 1 | no |
| I_distinct_plus_sem_in_pool | 0.3902 | 16/41 | 7 | 0 | 0/13 | 1 | no |
| J_action_on_distinct | 0.439 | 18/41 | 5 | 0 | 0/13 | 1 | no |

**Baseline:** cov=0.4146 wrong=4 hc=0
**Winners:** none
**VERDICT:** NO_IMPLEMENT — no variant beat baseline under gates; redesign hypothesis
