# V5 Phase B — compound counterfactuals

Created: 2026-09-13T23:46:55.618440+00:00

Measurement only. Telegraphic compound is in scope; the 0.90 gate is unchanged.
Starting condition shared by every variant: `--parts live` with production-parity forced detection.

> Supersedes the Phase B run. That run's `A_current_live` baseline (0.1707 / wrong_intent 4) is **invalid**: A skipped the compound path on 10 of 15 clips while B-I were handed the forced decomposition. See `V5_MEASUREMENT_PARITY`.

Guard: `wrong_intent` must not exceed the baseline (12).


| variant | coverage (by part) | hit | wrong | dup | ms/clip |
|---|---:|---:|---:|---:|---:|
| A_current_live | 0.3659 | 15/41 | 12 | 0 | 186.5 |
| A_recorded_warm_reference | 0.3659 | 15/41 | 12 | 0 | 0.0 |
| B_clause_alone | 0.3171 | 13/41 | 10 | 1 | 0.1 |
| C_clause_plus_subject | 0.3415 | 14/41 | 9 | 2 | 12.2 |
| D_discriminator_plus_subject_excl_parent | 0.2439 | 10/41 | 7 | 0 | 42.1 |
| E_compact_parent_context | 0.3171 | 13/41 | 10 | 0 | 9.2 |
| F_independent_no_carry | 0.3171 | 13/41 | 10 | 1 | 0.1 |
| G_standalone_rewrite | 0.3415 | 14/41 | 10 | 1 | 25.8 |
| I_enumeration_split | 0.4634 | 19/41 | 10 | 2 | 28.2 |
| H_action_type_completion | 0.3659 | 15/41 | 10 | 1 | 19.8 |
| HI_action_plus_enumeration | 0.4634 | 19/41 | 10 | 3 | 17.3 |

**Beat baseline A (full pipeline) without raising wrong_intent:** I_enumeration_split, HI_action_plus_enumeration
**Beat the within-family null F (per-part matcher) without raising wrong_intent:** I_enumeration_split, HI_action_plus_enumeration, H_action_type_completion, C_clause_plus_subject, G_standalone_rewrite

A runs the full pipeline; B-I run a per-part matcher over the shared parts. The F comparison is the like-for-like one.

**Status: PROVISIONAL.** No variant may be called a winner until this table is reproduced with `semantic_index_ready=True`.

