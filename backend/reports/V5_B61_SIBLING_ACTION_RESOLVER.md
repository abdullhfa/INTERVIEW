# V5 Phase B6.1 — same-topic sibling action resolver

Created: 2026-09-14T03:49:26.763098+00:00
`semantic_index_ready=True`

LAST ranking experiment. Measurement only.

## Eligibility probe (B5 fragments for the 13)

| clip | gold | would_fire | reason | q_action | alt |
|---|---|---|---|---|---|
| fuh4_079 | `proj.similarity.tech` | False | no_clear_query_action | None | `None` |
| fuh4_081 | `tech.vector_db_choice` | False | no_clear_query_action | None | `None` |
| fuh4_082 | `tech.agent_orchestrator` | False | top1_already_matches_action | compare | `None` |
| fuh4_082 | `tech.multi_agent_when` | False | top1_already_matches_action | compare | `None` |
| fuh4_084 | `tech.guardrails_how` | False | top1_already_matches_action | definition | `None` |
| fuh4_085 | `tech.kubernetes` | False | no_clear_query_action | None | `None` |
| fuh4_086 | `proj.early_warning.describe` | False | no_eligible_same_topic_alt | how | `None` |
| fuh4_086 | `proj.early_warning.metric` | False | no_eligible_same_topic_alt | why | `None` |
| fuh4_087 | `hard.tool_schema` | False | no_clear_query_action | None | `None` |
| fuh4_087 | `hard.agent_stop_tools` | False | alt_failed_accept_gate_fallback_top1 | when | `hard.agent_stop_tools` |
| fuh4_088 | `tech.whisper_vs_cloud` | False | no_clear_query_action | None | `None` |
| fuh4_088 | `tech.transcription_quality` | False | no_clear_query_action | None | `None` |
| fuh4_089 | `hard.remove_langchain` | False | no_eligible_same_topic_alt | compare | `None` |

## Full projection

| variant | coverage | hit | wrong | hc | target_rec | fires | newly_broken |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_baseline | 0.4146 | 17/41 | 4 | 0 | 0/13 | 0 | 1 |
| B61_sibling_action | 0.4146 | 17/41 | 4 | 0 | 0/13 | 0 | 1 |

Recovered detail: []

Hard gate: `{'recovered_target_ge_3': False, 'wrong_le_4': True, 'wrong_le_baseline': True, 'newly_broken_le_baseline': True, 'hc_le_baseline': True, 'coverage_ge_baseline': True, 'all_pass': False}`

**VERDICT: CLOSE_RANKING_PATH — B6.1 failed hard gate; stop ranking/action reranking; reclassify the 13 toward profile/candidate + segmentation**
