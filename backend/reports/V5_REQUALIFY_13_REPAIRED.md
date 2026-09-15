# V5 — re-qualify the original 13 on repaired harness

Created: 2026-09-14T06:21:08.715231+00:00

Provisional baseline: `cov=0.4878 wrong=4 HC=0`.
Instrument: `alias_matrix=True`, probe hybrid semantic=`1.0` (must be > 0).

B5 buckets were **ignored** — labels below are assigned fresh.

Resolved under repaired baseline: **1/13**
Still missing: **12/13** (reachable=6, unreachable=6)

## Still-missing bucket tally (all)

| bucket | count |
|---|---:|
| **ACTION_GRANULARITY** | 5 |
| **CANDIDATE_GENERATION** | 4 |
| **STT_DISTORTION** | 2 |
| **HYBRID_RANKING** | 1 |

## Reachable still-missing only (decision basis)

| bucket | count | share |
|---|---:|---:|
| **ACTION_GRANULARITY** | 5 | 0.8333 |
| **HYBRID_RANKING** | 1 | 0.1667 |

Ranking family among reachable (HYBRID+ACTION): **6**
Profile/seg/candidate among reachable: **0**
Reachable still-missing upside if all hit: **+0.1463** coverage

**DECISION: REOPEN_RANKING — under repaired harness a real HYBRID/ACTION block remains among reachable misses; re-open ranking only on this instrument**

## Per case

| clip | gold | status | NEW bucket | legacy (ignored) | hy | sem | top1 | hy_sem | reachable |
|---|---|---|---|---|---:|---:|---|---:|---|
| fuh4_079 | `proj.similarity.tech` | STILL_MISSING | **ACTION_GRANULARITY** | ACTION_GRANULARITY | 4 | 8 | `proj.similarity.describe` | 0.6037 | True |
| fuh4_081 | `tech.vector_db_choice` | STILL_MISSING | **HYBRID_RANKING** | HYBRID_RANKING | 3 | 3 | `cv.vector_db` | 0.781 | True |
| fuh4_082 | `tech.agent_orchestrator` | STILL_MISSING | **ACTION_GRANULARITY** | HYBRID_RANKING | 2 | 4 | `hard.agent_terms_difference` | 0.6596 | True |
| fuh4_082 | `tech.multi_agent_when` | STILL_MISSING | **CANDIDATE_GENERATION** | HYBRID_RANKING | 3 | 1 | `hard.agent_terms_difference` | 0.6596 | False |
| fuh4_084 | `tech.guardrails_how` | STILL_MISSING | **ACTION_GRANULARITY** | ACTION_GRANULARITY | 2 | 2 | `tech.guardrails_what` | 1.0 | True |
| fuh4_085 | `tech.kubernetes` | STILL_MISSING | **STT_DISTORTION** | HYBRID_RANKING | 5 | 3 | `tech.docker_why` | 0.6621 | False |
| fuh4_086 | `proj.early_warning.describe` | STILL_MISSING | **ACTION_GRANULARITY** | HYBRID_RANKING | 4 | 2 | `proj.early_warning.metric` | 0.8071 | True |
| fuh4_086 | `proj.early_warning.metric` | STILL_MISSING | **CANDIDATE_GENERATION** | HYBRID_RANKING | 1 | 1 | `proj.early_warning.metric` | 0.7808 | False |
| fuh4_087 | `hard.tool_schema` | NOW_HIT | **RESOLVED_UNDER_REPAIRED_BASELINE** | HYBRID_RANKING | 1 | 1 | `hard.tool_schema` | 0.6905 | True |
| fuh4_087 | `hard.agent_stop_tools` | STILL_MISSING | **CANDIDATE_GENERATION** | ACTION_GRANULARITY | 2 | 1 | `hard.agent_loop` | 0.7199 | False |
| fuh4_088 | `tech.whisper_vs_cloud` | STILL_MISSING | **ACTION_GRANULARITY** | ACTION_GRANULARITY | 4 | 3 | `tech.what_is_whisper` | 0.6569 | True |
| fuh4_088 | `tech.transcription_quality` | STILL_MISSING | **CANDIDATE_GENERATION** | HYBRID_RANKING | 4 | 3 | `proj.early_warning.metric` | 0.5569 | False |
| fuh4_089 | `hard.remove_langchain` | STILL_MISSING | **STT_DISTORTION** | HYBRID_RANKING | 5 | 36 | `tech.langgraph_vs_langchain` | 0.3475 | False |

## Detail

### fuh4_079 — `proj.similarity.tech` → ACTION_GRANULARITY (STILL_MISSING)

- fragment: `Summurize the assignment similarity project. It's fact and whether it is R-18.`
- hybrid top5: `[{'rank': 1, 'id': 'proj.similarity.describe', 'topic': 'project:similarity', 'score': 0.5634, 'semantic': 0.6037, 'lexical': 0.5182, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'describe'}, {'rank': 2, 'id': 'proj.similarity.challenges', 'topic': 'project:similarity', 'score': 0.4912, 'semantic': 0.514, 'lexical': 0.5958, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 3, 'id': 'proj.similarity.role', 'topic': 'project:similarity', 'score': 0.4703, 'semantic': 0.5379, 'lexical': 0.4985, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 4, 'id': 'proj.similarity.tech', 'topic': 'project:similarity', 'score': 0.4653, 'semantic': 0.5152, 'lexical': 0.5198, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 5, 'id': 'tech.cosine_semantic_search', 'topic': 'rag', 'score': 0.4412, 'semantic': 0.5114, 'lexical': 0.3141, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'definition'}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.similarity.describe', 'score': 0.5737}, {'rank': 2, 'id': 'proj.similarity.is_rag', 'score': 0.4621}, {'rank': 3, 'id': 'proj.similarity.challenges', 'score': 0.4574}, {'rank': 4, 'id': 'hard.similarity_vs_qgen_arch', 'score': 0.4198}, {'rank': 5, 'id': 'proj.similarity.threshold', 'score': 0.4191}]`
- gold action=experience query_action=None top1_action=describe sibling=True
- evidence=1.0 rejected=False
- accept_top1={'accepted': False, 'reason': 'below_answer_threshold', 'top1': 'proj.similarity.describe', 'probed_id': 'proj.similarity.describe', 'score': 0.5634, 'margin': 0.0722} gold_as_top1_accepted=False (not_top1)
- reachable=True (overlap=['similarity'])
- stt=False lost=[]

### fuh4_081 — `tech.vector_db_choice` → HYBRID_RANKING (STILL_MISSING)

- fragment: `Your vector DB history`
- hybrid top5: `[{'rank': 1, 'id': 'cv.vector_db', 'topic': 'skills', 'score': 0.8384, 'semantic': 0.781, 'lexical': 0.8824, 'keyword': 1.0, 'mode': 'strong', 'action_type': 'experience'}, {'rank': 2, 'id': 'proj.completion_risk.tech', 'topic': 'project:completion', 'score': 0.688, 'semantic': 0.7054, 'lexical': 0.8571, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 3, 'id': 'tech.vector_db_choice', 'topic': 'rag', 'score': 0.6879, 'semantic': 0.6439, 'lexical': 0.8108, 'keyword': 0.5, 'mode': 'weak', 'action_type': None}, {'rank': 4, 'id': 'proj.similarity.tech', 'topic': 'project:similarity', 'score': 0.6541, 'semantic': 0.596, 'lexical': 0.7895, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 5, 'id': 'hard.checkpoint_vs_memory', 'topic': 'agents', 'score': 0.6104, 'semantic': 0.6075, 'lexical': 0.7895, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'compare'}]`
- semantic top5: `[{'rank': 1, 'id': 'cv.vector_db', 'score': 0.4721}, {'rank': 2, 'id': 'proj.completion_risk.tech', 'score': 0.4401}, {'rank': 3, 'id': 'tech.vector_db_choice', 'score': 0.4211}, {'rank': 4, 'id': 'proj.similarity.tech', 'score': 0.3756}, {'rank': 5, 'id': 'hard.graph_vs_vector', 'score': 0.3398}]`
- gold action=None query_action=None top1_action=experience sibling=False
- evidence=1.0 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'cv.vector_db', 'probed_id': 'cv.vector_db', 'score': 0.8384, 'margin': 0.1504} gold_as_top1_accepted=False (not_top1)
- reachable=True (overlap=['database', 'vector'])
- stt=False lost=[]

### fuh4_082 — `tech.agent_orchestrator` → ACTION_GRANULARITY (STILL_MISSING)

- fragment: `Role of an orchestrator versus a lone tool-calling model`
- hybrid top5: `[{'rank': 1, 'id': 'hard.agent_terms_difference', 'topic': 'agents', 'score': 0.753, 'semantic': 0.6596, 'lexical': 0.4576, 'keyword': 0.5, 'mode': 'strong', 'action_type': 'compare'}, {'rank': 2, 'id': 'tech.agent_orchestrator', 'topic': 'agents', 'score': 0.6805, 'semantic': 0.6908, 'lexical': 0.3159, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'definition'}, {'rank': 3, 'id': 'tech.multi_agent_when', 'topic': 'agents', 'score': 0.5826, 'semantic': 0.6705, 'lexical': 0.3538, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'when'}, {'rank': 4, 'id': 'tech.which_framework', 'topic': 'frameworks', 'score': 0.4998, 'semantic': 0.6965, 'lexical': 0.3335, 'keyword': 0.0, 'mode': 'weak', 'action_type': None}, {'rank': 5, 'id': 'hard.langgraph_vs_n8n_vs_python', 'topic': 'frameworks', 'score': 0.4981, 'semantic': 0.6629, 'lexical': 0.3813, 'keyword': 0.0, 'mode': 'weak', 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.multi_agent_when', 'score': 0.4589}, {'rank': 2, 'id': 'hard.agent_terms_difference', 'score': 0.4552}, {'rank': 3, 'id': 'hard.langgraph_vs_n8n_vs_python', 'score': 0.454}, {'rank': 4, 'id': 'tech.agent_orchestrator', 'score': 0.4328}, {'rank': 5, 'id': 'tech.tool_calling', 'score': 0.39}]`
- gold action=definition query_action=compare top1_action=compare sibling=True
- evidence=1.0 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'hard.agent_terms_difference', 'probed_id': 'hard.agent_terms_difference', 'score': 0.753, 'margin': 0.0724} gold_as_top1_accepted=False (not_top1)
- reachable=True (overlap=['orchestrator'])
- stt=False lost=[]

### fuh4_082 — `tech.multi_agent_when` → CANDIDATE_GENERATION (STILL_MISSING)

- fragment: `Role of an orchestrator versus a lone tool-calling model`
- hybrid top5: `[{'rank': 1, 'id': 'hard.agent_terms_difference', 'topic': 'agents', 'score': 0.753, 'semantic': 0.6596, 'lexical': 0.4576, 'keyword': 0.5, 'mode': 'strong', 'action_type': 'compare'}, {'rank': 2, 'id': 'tech.agent_orchestrator', 'topic': 'agents', 'score': 0.6805, 'semantic': 0.6908, 'lexical': 0.3159, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'definition'}, {'rank': 3, 'id': 'tech.multi_agent_when', 'topic': 'agents', 'score': 0.5826, 'semantic': 0.6705, 'lexical': 0.3538, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'when'}, {'rank': 4, 'id': 'tech.which_framework', 'topic': 'frameworks', 'score': 0.4998, 'semantic': 0.6965, 'lexical': 0.3335, 'keyword': 0.0, 'mode': 'weak', 'action_type': None}, {'rank': 5, 'id': 'hard.langgraph_vs_n8n_vs_python', 'topic': 'frameworks', 'score': 0.4981, 'semantic': 0.6629, 'lexical': 0.3813, 'keyword': 0.0, 'mode': 'weak', 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.multi_agent_when', 'score': 0.4589}, {'rank': 2, 'id': 'hard.agent_terms_difference', 'score': 0.4552}, {'rank': 3, 'id': 'hard.langgraph_vs_n8n_vs_python', 'score': 0.454}, {'rank': 4, 'id': 'tech.agent_orchestrator', 'score': 0.4328}, {'rank': 5, 'id': 'tech.tool_calling', 'score': 0.39}]`
- gold action=when query_action=compare top1_action=compare sibling=True
- evidence=1.0 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'hard.agent_terms_difference', 'probed_id': 'hard.agent_terms_difference', 'score': 0.753, 'margin': 0.0724} gold_as_top1_accepted=False (not_top1)
- reachable=False (no_gold_token_in_utterance)
- stt=False lost=[]

### fuh4_084 — `tech.guardrails_how` → ACTION_GRANULARITY (STILL_MISSING)

- fragment: `What are guardrails?`
- hybrid top5: `[{'rank': 1, 'id': 'tech.guardrails_what', 'topic': 'guardrails', 'score': 1.26, 'semantic': 1.0, 'lexical': 1.0, 'keyword': 1.0, 'mode': 'strong', 'action_type': 'definition'}, {'rank': 2, 'id': 'tech.guardrails_how', 'topic': 'guardrails', 'score': 1.0585, 'semantic': 0.7973, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'action_type': 'experience'}, {'rank': 3, 'id': 'tech.guardrails_layers', 'topic': 'guardrails', 'score': 1.0003, 'semantic': 0.7097, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'action_type': None}, {'rank': 4, 'id': 'cv.guardrails', 'topic': 'skills', 'score': 0.9722, 'semantic': 0.6404, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'action_type': 'experience'}, {'rank': 5, 'id': 'gen.ai_ethics', 'topic': 'personal', 'score': 0.8176, 'semantic': 0.8502, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'action_type': 'how'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.guardrails_what', 'score': 0.6149}, {'rank': 2, 'id': 'tech.guardrails_how', 'score': 0.5441}, {'rank': 3, 'id': 'tech.guardrails_layers', 'score': 0.459}, {'rank': 4, 'id': 'cv.guardrails', 'score': 0.4559}, {'rank': 5, 'id': 'tech.hallucination_prevent', 'score': 0.2931}]`
- gold action=experience query_action=definition top1_action=definition sibling=True
- evidence=1.0 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'tech.guardrails_what', 'probed_id': 'tech.guardrails_what', 'score': 1.26, 'margin': 0.2015} gold_as_top1_accepted=False (not_top1)
- reachable=True (overlap=['guardrails'])
- stt=False lost=[]

### fuh4_085 — `tech.kubernetes` → STT_DISTORTION (STILL_MISSING)

- fragment: `Docker value`
- hybrid top5: `[{'rank': 1, 'id': 'tech.docker_why', 'topic': 'infra', 'score': 0.8142, 'semantic': 0.6621, 'lexical': 1.0, 'keyword': 1.0, 'mode': 'strong', 'action_type': 'why'}, {'rank': 2, 'id': 'tech.container_vs_vm', 'topic': 'infra', 'score': 0.5781, 'semantic': 0.5602, 'lexical': 0.7714, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'definition'}, {'rank': 3, 'id': 'cv.kubernetes', 'topic': 'skills', 'score': 0.5095, 'semantic': 0.4111, 'lexical': 0.6667, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 4, 'id': 'tech.deploy_on_prem', 'topic': 'infra', 'score': 0.4848, 'semantic': 0.4571, 'lexical': 0.6667, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'how'}, {'rank': 5, 'id': 'tech.kubernetes', 'topic': 'infra', 'score': 0.481, 'semantic': 0.4503, 'lexical': 0.6667, 'keyword': 0.0, 'mode': 'weak', 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.docker_why', 'score': 0.3858}, {'rank': 2, 'id': 'tech.container_vs_vm', 'score': 0.35}, {'rank': 3, 'id': 'tech.kubernetes', 'score': 0.2527}, {'rank': 4, 'id': 'cv.kubernetes', 'score': 0.2464}, {'rank': 5, 'id': 'tech.deploy_on_prem', 'score': 0.2377}]`
- gold action=None query_action=None top1_action=why sibling=True
- evidence=1.0 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'tech.docker_why', 'probed_id': 'tech.docker_why', 'score': 0.8142, 'margin': 0.236} gold_as_top1_accepted=False (not_top1)
- reachable=False (no_gold_token_in_utterance)
- stt=False lost=['kubernetes']

### fuh4_086 — `proj.early_warning.describe` → ACTION_GRANULARITY (STILL_MISSING)

- fragment: `How do you evaluate an early warning model for students?`
- hybrid top5: `[{'rank': 1, 'id': 'proj.early_warning.metric', 'topic': 'project:early_warning', 'score': 0.7439, 'semantic': 0.8071, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'action_type': 'experience'}, {'rank': 2, 'id': 'proj.completion_risk.describe', 'topic': 'project:completion', 'score': 0.6289, 'semantic': 0.7406, 'lexical': 0.5187, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'describe'}, {'rank': 3, 'id': 'proj.early_warning.tech', 'topic': 'project:early_warning', 'score': 0.5792, 'semantic': 0.6719, 'lexical': 0.7419, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 4, 'id': 'proj.early_warning.describe', 'topic': 'project:early_warning', 'score': 0.5514, 'semantic': 0.7599, 'lexical': 0.5241, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'describe'}, {'rank': 5, 'id': 'proj.early_warning.stack', 'topic': 'project:early_warning', 'score': 0.534, 'semantic': 0.5421, 'lexical': 0.5309, 'keyword': 0.5, 'mode': 'weak', 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.early_warning.result', 'score': 0.6195}, {'rank': 2, 'id': 'proj.early_warning.describe', 'score': 0.5807}, {'rank': 3, 'id': 'proj.early_warning.metric', 'score': 0.5738}, {'rank': 4, 'id': 'proj.early_warning.stack', 'score': 0.5302}, {'rank': 5, 'id': 'proj.early_warning.leakage', 'score': 0.5302}]`
- gold action=describe query_action=how top1_action=experience sibling=True
- evidence=0.4 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'proj.early_warning.metric', 'probed_id': 'proj.early_warning.metric', 'score': 0.7439, 'margin': 0.115} gold_as_top1_accepted=False (not_top1)
- reachable=True (overlap=['early', 'project', 'warning'])
- stt=False lost=[]

### fuh4_086 — `proj.early_warning.metric` → CANDIDATE_GENERATION (STILL_MISSING)

- fragment: `Why does recall matter more than accuracy for early warning?`
- hybrid top5: `[{'rank': 1, 'id': 'proj.early_warning.metric', 'topic': 'project:early_warning', 'score': 0.7949, 'semantic': 0.7808, 'lexical': 0.6441, 'keyword': 1.0, 'mode': 'strong', 'action_type': 'experience'}, {'rank': 2, 'id': 'tech.precision_recall', 'topic': 'ml', 'score': 0.5909, 'semantic': 0.7426, 'lexical': 0.5214, 'keyword': 1.0, 'mode': 'weak', 'action_type': 'definition'}, {'rank': 3, 'id': 'proj.early_warning.result', 'topic': 'project:early_warning', 'score': 0.4281, 'semantic': 0.4734, 'lexical': 0.4791, 'keyword': 0.0, 'mode': 'weak', 'action_type': None}, {'rank': 4, 'id': 'proj.early_warning.stack', 'topic': 'project:early_warning', 'score': 0.3949, 'semantic': 0.327, 'lexical': 0.4717, 'keyword': 0.5, 'mode': 'weak', 'action_type': None}, {'rank': 5, 'id': 'tech.overfitting', 'topic': 'ml', 'score': 0.389, 'semantic': 0.4522, 'lexical': 0.2866, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'definition'}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.early_warning.metric', 'score': 0.4872}, {'rank': 2, 'id': 'tech.precision_recall', 'score': 0.4283}, {'rank': 3, 'id': 'proj.early_warning.stack', 'score': 0.4138}, {'rank': 4, 'id': 'gen.failure', 'score': 0.366}, {'rank': 5, 'id': 'proj.early_warning.leakage', 'score': 0.3493}]`
- gold action=experience query_action=why top1_action=experience sibling=False
- evidence=0.4 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'proj.early_warning.metric', 'probed_id': 'proj.early_warning.metric', 'score': 0.7949, 'margin': 0.204} gold_as_top1_accepted=True (None)
- reachable=False (no_gold_token_in_utterance)
- stt=False lost=[]

### fuh4_087 — `hard.tool_schema` → RESOLVED_UNDER_REPAIRED_BASELINE (NOW_HIT)

- fragment: `Tool calling basics schema need`
- hybrid top5: `[{'rank': 1, 'id': 'hard.tool_schema', 'topic': 'agents', 'score': 0.6752, 'semantic': 0.6905, 'lexical': 0.5583, 'keyword': 1.0, 'mode': 'weak', 'action_type': 'why'}, {'rank': 2, 'id': 'tech.tool_calling', 'topic': 'agents', 'score': 0.6302, 'semantic': 0.5903, 'lexical': 0.73, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'definition'}, {'rank': 3, 'id': 'hard.wrong_tool', 'topic': 'agents', 'score': 0.3649, 'semantic': 0.3808, 'lexical': 0.3012, 'keyword': 0.5, 'mode': 'weak', 'action_type': None}, {'rank': 4, 'id': 'hard.agent_loop', 'topic': 'agents', 'score': 0.3486, 'semantic': 0.3241, 'lexical': 0.4867, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'how'}, {'rank': 5, 'id': 'cv.pydantic', 'topic': 'skills', 'score': 0.34, 'semantic': 0.4466, 'lexical': 0.2696, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'experience'}]`
- semantic top5: `[{'rank': 1, 'id': 'hard.tool_schema', 'score': 0.6331}, {'rank': 2, 'id': 'tech.tool_calling', 'score': 0.6209}, {'rank': 3, 'id': 'hard.wrong_tool', 'score': 0.3979}, {'rank': 4, 'id': 'tech.agent_tools_permissions', 'score': 0.3831}, {'rank': 5, 'id': 'tech.guardrails_how', 'score': 0.376}]`
- gold action=why query_action=None top1_action=why sibling=False
- evidence=1.0 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'hard.tool_schema', 'probed_id': 'hard.tool_schema', 'score': 0.6752, 'margin': 0.045} gold_as_top1_accepted=True (None)
- reachable=True (overlap=['need', 'schema', 'tool'])
- stt=False lost=[]

### fuh4_087 — `hard.agent_stop_tools` → CANDIDATE_GENERATION (STILL_MISSING)

- fragment: `When to halt tool loops?`
- hybrid top5: `[{'rank': 1, 'id': 'hard.agent_loop', 'topic': 'agents', 'score': 0.626, 'semantic': 0.7199, 'lexical': 0.8, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'how'}, {'rank': 2, 'id': 'hard.agent_stop_tools', 'topic': 'agents', 'score': 0.5419, 'semantic': 0.6309, 'lexical': 0.4427, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'when'}, {'rank': 3, 'id': 'hard.agent_cannot_delete', 'topic': 'agents', 'score': 0.3534, 'semantic': 0.32, 'lexical': 0.364, 'keyword': 0.5, 'mode': 'weak', 'action_type': None}, {'rank': 4, 'id': 'tech.classify_or_llm', 'topic': 'ml', 'score': 0.3246, 'semantic': 0.3024, 'lexical': 0.338, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'when'}, {'rank': 5, 'id': 'hard.circuit_breaker', 'topic': 'agents', 'score': 0.3186, 'semantic': 0.3854, 'lexical': 0.3048, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'definition'}]`
- semantic top5: `[{'rank': 1, 'id': 'hard.agent_stop_tools', 'score': 0.5859}, {'rank': 2, 'id': 'hard.agent_loop', 'score': 0.5633}, {'rank': 3, 'id': 'hard.timeout_vs_steps', 'score': 0.4261}, {'rank': 4, 'id': 'hard.circuit_breaker', 'score': 0.3462}, {'rank': 5, 'id': 'hard.agent_cannot_delete', 'score': 0.3442}]`
- gold action=when query_action=when top1_action=how sibling=True
- evidence=1.0 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'hard.agent_loop', 'probed_id': 'hard.agent_loop', 'score': 0.626, 'margin': 0.084} gold_as_top1_accepted=False (not_top1)
- reachable=False (no_gold_token_in_utterance)
- stt=False lost=[]

### fuh4_088 — `tech.whisper_vs_cloud` → ACTION_GRANULARITY (STILL_MISSING)

- fragment: `local Whisper rationale`
- hybrid top5: `[{'rank': 1, 'id': 'tech.what_is_whisper', 'topic': 'speech', 'score': 0.765, 'semantic': 0.6569, 'lexical': 0.525, 'keyword': 1.0, 'mode': 'strong', 'action_type': 'definition'}, {'rank': 2, 'id': 'proj.kiosk.describe', 'topic': 'project:kiosk', 'score': 0.6146, 'semantic': 0.5479, 'lexical': 0.4095, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'describe'}, {'rank': 3, 'id': 'cv.whisper_experience', 'topic': 'skills', 'score': 0.6076, 'semantic': 0.541, 'lexical': 0.4, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 4, 'id': 'tech.whisper_vs_cloud', 'topic': 'speech', 'score': 0.5859, 'semantic': 0.5374, 'lexical': 0.3436, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'why'}, {'rank': 5, 'id': 'proj.kiosk.stack', 'topic': 'project:kiosk', 'score': 0.546, 'semantic': 0.457, 'lexical': 0.3561, 'keyword': 0.5, 'mode': 'weak', 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.kiosk.describe', 'score': 0.4226}, {'rank': 2, 'id': 'proj.kiosk.challenges', 'score': 0.3525}, {'rank': 3, 'id': 'tech.whisper_vs_cloud', 'score': 0.3394}, {'rank': 4, 'id': 'cv.whisper_experience', 'score': 0.3052}, {'rank': 5, 'id': 'tech.voice_assistant_design', 'score': 0.294}]`
- gold action=why query_action=None top1_action=definition sibling=True
- evidence=1.0 rejected=False
- accept_top1={'accepted': True, 'reason': None, 'top1': 'tech.what_is_whisper', 'probed_id': 'tech.what_is_whisper', 'score': 0.765, 'margin': 0.1504} gold_as_top1_accepted=False (not_top1)
- reachable=True (overlap=['whisper'])
- stt=False lost=[]

### fuh4_088 — `tech.transcription_quality` → CANDIDATE_GENERATION (STILL_MISSING)

- fragment: `Accuracy acceptance test`
- hybrid top5: `[{'rank': 1, 'id': 'proj.early_warning.metric', 'topic': 'project:early_warning', 'score': 0.4877, 'semantic': 0.5569, 'lexical': 0.3753, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 2, 'id': 'tech.overfitting', 'topic': 'ml', 'score': 0.4599, 'semantic': 0.389, 'lexical': 0.7027, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'definition'}, {'rank': 3, 'id': 'tech.precision_recall', 'topic': 'ml', 'score': 0.4512, 'semantic': 0.48, 'lexical': 0.392, 'keyword': 0.5, 'mode': 'weak', 'action_type': 'definition'}, {'rank': 4, 'id': 'tech.transcription_quality', 'topic': 'speech', 'score': 0.4107, 'semantic': 0.5463, 'lexical': 0.315, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'how'}, {'rank': 5, 'id': 'hard.evaluate_rag', 'topic': 'evaluation', 'score': 0.3405, 'semantic': 0.4738, 'lexical': 0.2283, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'how'}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.early_warning.metric', 'score': 0.4212}, {'rank': 2, 'id': 'tech.faithfulness_check', 'score': 0.3857}, {'rank': 3, 'id': 'tech.transcription_quality', 'score': 0.3463}, {'rank': 4, 'id': 'tech.evaluate_classification', 'score': 0.3362}, {'rank': 5, 'id': 'tech.precision_recall', 'score': 0.3245}]`
- gold action=how query_action=None top1_action=experience sibling=False
- evidence=1.0 rejected=False
- accept_top1={'accepted': False, 'reason': 'low_score', 'top1': 'proj.early_warning.metric', 'probed_id': 'proj.early_warning.metric', 'score': 0.4877, 'margin': 0.0278} gold_as_top1_accepted=False (not_top1)
- reachable=False (no_gold_token_in_utterance)
- stt=False lost=[]

### fuh4_089 — `hard.remove_langchain` → STT_DISTORTION (STILL_MISSING)

- fragment: `Nantler versus Lanskings. You use it and surviving without Lanschain.`
- hybrid top5: `[{'rank': 1, 'id': 'tech.langgraph_vs_langchain', 'topic': 'agents', 'score': 0.3543, 'semantic': 0.3475, 'lexical': 0.3518, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'compare'}, {'rank': 2, 'id': 'tech.rag_vs_finetuning', 'topic': 'rag', 'score': 0.3399, 'semantic': 0.2384, 'lexical': 0.3393, 'keyword': 0.5, 'mode': 'weak', 'action_type': None}, {'rank': 3, 'id': 'hard.langgraph_vs_n8n_vs_python', 'topic': 'frameworks', 'score': 0.3291, 'semantic': 0.3296, 'lexical': 0.3081, 'keyword': 0.0, 'mode': 'weak', 'action_type': None}, {'rank': 4, 'id': 'cv.langchain', 'topic': 'skills', 'score': 0.3184, 'semantic': 0.3443, 'lexical': 0.3686, 'keyword': 0.0, 'mode': 'weak', 'action_type': 'experience'}, {'rank': 5, 'id': 'hard.remove_langchain', 'topic': 'frameworks', 'score': 0.2983, 'semantic': 0.2832, 'lexical': 0.4074, 'keyword': 0.0, 'mode': 'weak', 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'hard.langgraph_vs_n8n_vs_python', 'score': 0.2578}, {'rank': 2, 'id': 'cv.image_processing', 'score': 0.2417}, {'rank': 3, 'id': 'tech.langgraph_vs_langchain', 'score': 0.2379}, {'rank': 4, 'id': 'cv.core_skills', 'score': 0.2286}, {'rank': 5, 'id': 'hard.why_not_chroma_prod', 'score': 0.2271}]`
- gold action=None query_action=compare top1_action=compare sibling=False
- evidence=1.0 rejected=False
- accept_top1={'accepted': False, 'reason': 'low_score', 'top1': 'tech.langgraph_vs_langchain', 'probed_id': 'tech.langgraph_vs_langchain', 'score': 0.3543, 'margin': 0.0144} gold_as_top1_accepted=False (not_top1)
- reachable=False (no_gold_token_in_utterance)
- stt=False lost=['langchain']
