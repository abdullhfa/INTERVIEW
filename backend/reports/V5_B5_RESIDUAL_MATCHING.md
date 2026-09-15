# V5 Phase B5 — residual matching / profile analysis

Created: 2026-09-14T00:13:30.760666+00:00
`semantic_index_ready=True`

Measurement only. Routing is **closed**. Candidate under analysis:
`R1_min8w + evidence 0.4 + I + H (+ >=2-intent guard)`

## Bucket tally (one bucket per missing gold part)

| bucket | count | share |
|---|---:|---:|
| **HYBRID_RANKING** | 9 | 0.375 |
| **ACTION_GRANULARITY** | 4 | 0.1667 |
| **SEGMENTATION_RESIDUAL** | 3 | 0.125 |
| **CANDIDATE_GENERATION** | 3 | 0.125 |
| **EVIDENCE_REJECTED** | 2 | 0.0833 |
| **SEMANTIC_PROFILE_QUALITY** | 1 | 0.0417 |
| **STT_DISTORTION** | 1 | 0.0417 |
| **ACCEPTANCE_GATE** | 1 | 0.0417 |

**Dominant:** `HYBRID_RANKING` (9/24 = 0.375) — clear

**Next step:** One counterfactual on ranking / action-type discrimination (measurement only first).

Path-closed misses: 11/24 (re-open routing only if these dominate — they should not).

## Per missing gold part

| clip | gold | bucket | fragment | hy rank | sem rank | top1 | sibling? | evid | reject |
|---|---|---|---|---:|---:|---|---|---:|---|
| fuh4_079 | `proj.similarity.describe` | **EVIDENCE_REJECTED** | Summurize the assignment similarity project. It' | 1 | 1 | `proj.similarity.describe` | False | 1.0 | low_score |
| fuh4_079 | `proj.similarity.tech` | **ACTION_GRANULARITY** | Summurize the assignment similarity project. It' | 4 | 8 | `proj.similarity.describe` | True | 1.0 | low_score |
| fuh4_079 | `proj.similarity.is_rag` | **EVIDENCE_REJECTED** | Summurize the assignment similarity project. It' | 8 | 2 | `proj.similarity.describe` | True | 1.0 | low_score |
| fuh4_080 | `tech.overfitting` | **SEGMENTATION_RESIDUAL** | Define overfitting detection signals in your mit | 1 | 4 | `tech.overfitting` | False | 1.0 | low_score |
| fuh4_080 | `tech.overfitting_prevent` | **SEGMENTATION_RESIDUAL** | Define overfitting detection signals in your mit | — | 1 | `tech.overfitting` | True | 1.0 | low_score |
| fuh4_080 | `tech.evaluate_classification` | **SEGMENTATION_RESIDUAL** | Define overfitting detection signals in your mit | — | 49 | `tech.overfitting` | True | 1.0 | low_score |
| fuh4_081 | `tech.vector_db_choice` | **HYBRID_RANKING** | Your vector DB history | 2 | 3 | `cv.vector_db` | False | 1.0 | — |
| fuh4_082 | `tech.agent_orchestrator` | **HYBRID_RANKING** | Role of an orchestrator versus a lone tool-calli | 3 | 4 | `hard.agent_terms_difference` | False | 1.0 | — |
| fuh4_082 | `tech.multi_agent_when` | **HYBRID_RANKING** | Role of an orchestrator versus a lone tool-calli | 4 | 1 | `hard.agent_terms_difference` | False | 1.0 | — |
| fuh4_083 | `cv.pmp_value` | **CANDIDATE_GENERATION** | certification | — | 40 | `cv.certifications` | True | 1.0 | — |
| fuh4_084 | `tech.prompt_injection_what` | **SEMANTIC_PROFILE_QUALITY** | What are guardrails? | — | 6 | `tech.guardrails_what` | True | 1.0 | — |
| fuh4_084 | `hard.injection_in_pdf` | **CANDIDATE_GENERATION** | What are guardrails? | — | 30 | `tech.guardrails_what` | False | 1.0 | — |
| fuh4_084 | `tech.guardrails_how` | **ACTION_GRANULARITY** | What are guardrails? | 2 | 2 | `tech.guardrails_what` | True | 1.0 | — |
| fuh4_085 | `tech.kubernetes` | **HYBRID_RANKING** | If we need Cuba needs | 2 | — | `tech.sklearn_vs_neural` | True | 1.0 | low_score |
| fuh4_086 | `proj.early_warning.describe` | **HYBRID_RANKING** | How do you evaluate an early warning model for s | — | 2 | `proj.early_warning.metric` | True | 0.4 | — |
| fuh4_086 | `proj.early_warning.metric` | **HYBRID_RANKING** | Why does recall matter more than accuracy for ea | 1 | 1 | `proj.early_warning.metric` | False | 0.4 | — |
| fuh4_087 | `hard.tool_schema` | **HYBRID_RANKING** | Tool calling basics schema need | 2 | 1 | `tech.tool_calling` | False | 1.0 | — |
| fuh4_087 | `hard.agent_stop_tools` | **ACTION_GRANULARITY** | When to halt tool loops? | 2 | 1 | `hard.agent_loop` | True | 1.0 | — |
| fuh4_088 | `tech.whisper_vs_cloud` | **ACTION_GRANULARITY** | local Whisper rationale | 4 | 3 | `tech.what_is_whisper` | True | 1.0 | — |
| fuh4_088 | `tech.transcription_quality` | **HYBRID_RANKING** | STT internals | 5 | — | `tech.how_stt_works` | True | 1.0 | — |
| fuh4_089 | `tech.langgraph_vs_langchain` | **STT_DISTORTION** | Nantler versus Lanskings. You use it and survivi | — | 3 | `tech.rag_vs_finetuning` | True | 1.0 | low_score |
| fuh4_089 | `cv.langgraph` | **CANDIDATE_GENERATION** | Nantler versus Lanskings. You use it and survivi | — | 33 | `tech.rag_vs_finetuning` | False | 1.0 | low_score |
| fuh4_089 | `hard.remove_langchain` | **HYBRID_RANKING** | Nantler versus Lanskings. You use it and survivi | 5 | 36 | `tech.rag_vs_finetuning` | False | 1.0 | low_score |
| fuh4_090 | `tech.metadata_filtering` | **ACCEPTANCE_GATE** | metadata filters | 1 | 1 | `tech.metadata_filtering` | False | 1.0 | ambiguous_margin |

## Detail blocks

### fuh4_079 — `proj.similarity.describe` → EVIDENCE_REJECTED

- script: `Summarise the assignment similarity project, its stack, and whether it is RAG.`
- asr: `Summurize the assignment similarity project. It's fact and whether it is R-18.`
- path_opened: False
- fragment: `Summurize the assignment similarity project. It's fact and whether it is R-18.`
- gold Q: `Tell me about the BTEC Assignment Similarity Checker`
- gold action: `describe` topic=`project:similarity`
- hybrid top5: `[{'rank': 1, 'id': 'proj.similarity.describe', 'topic': 'project:similarity', 'score': 0.5145, 'semantic': 0.0, 'lexical': 0.5182, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.similarity.challenges', 'runner_up_score': 0.4767, 'action_type': 'describe'}, {'rank': 2, 'id': 'proj.similarity.challenges', 'topic': 'project:similarity', 'score': 0.4767, 'semantic': 0.0, 'lexical': 0.5958, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'experience'}, {'rank': 3, 'id': 'tech.cosine_semantic_search', 'topic': 'rag', 'score': 0.4184, 'semantic': 0.0, 'lexical': 0.3981, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'definition'}, {'rank': 4, 'id': 'proj.similarity.tech', 'topic': 'project:similarity', 'score': 0.4158, 'semantic': 0.0, 'lexical': 0.5198, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'experience'}, {'rank': 5, 'id': 'proj.similarity.role', 'topic': 'project:similarity', 'score': 0.3988, 'semantic': 0.0, 'lexical': 0.4985, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'experience'}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.similarity.describe', 'score': 0.5737}, {'rank': 2, 'id': 'proj.similarity.is_rag', 'score': 0.4621}, {'rank': 3, 'id': 'proj.similarity.challenges', 'score': 0.4574}, {'rank': 4, 'id': 'hard.similarity_vs_qgen_arch', 'score': 0.4198}, {'rank': 5, 'id': 'proj.similarity.threshold', 'score': 0.4191}]`
- gold score: 0.5145  evid: 1.0
- top1: `proj.similarity.describe` action=`describe` sibling=False
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=False lost=[]
- evidence_rejected=True seg=False gran=False

### fuh4_079 — `proj.similarity.tech` → ACTION_GRANULARITY

- script: `Summarise the assignment similarity project, its stack, and whether it is RAG.`
- asr: `Summurize the assignment similarity project. It's fact and whether it is R-18.`
- path_opened: False
- fragment: `Summurize the assignment similarity project. It's fact and whether it is R-18.`
- gold Q: `What technologies did you use in the similarity checker?`
- gold action: `experience` topic=`project:similarity`
- hybrid top5: `[{'rank': 1, 'id': 'proj.similarity.describe', 'topic': 'project:similarity', 'score': 0.5145, 'semantic': 0.0, 'lexical': 0.5182, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.similarity.challenges', 'runner_up_score': 0.4767, 'action_type': 'describe'}, {'rank': 2, 'id': 'proj.similarity.challenges', 'topic': 'project:similarity', 'score': 0.4767, 'semantic': 0.0, 'lexical': 0.5958, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'experience'}, {'rank': 3, 'id': 'tech.cosine_semantic_search', 'topic': 'rag', 'score': 0.4184, 'semantic': 0.0, 'lexical': 0.3981, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'definition'}, {'rank': 4, 'id': 'proj.similarity.tech', 'topic': 'project:similarity', 'score': 0.4158, 'semantic': 0.0, 'lexical': 0.5198, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'experience'}, {'rank': 5, 'id': 'proj.similarity.role', 'topic': 'project:similarity', 'score': 0.3988, 'semantic': 0.0, 'lexical': 0.4985, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'experience'}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.similarity.describe', 'score': 0.5737}, {'rank': 2, 'id': 'proj.similarity.is_rag', 'score': 0.4621}, {'rank': 3, 'id': 'proj.similarity.challenges', 'score': 0.4574}, {'rank': 4, 'id': 'hard.similarity_vs_qgen_arch', 'score': 0.4198}, {'rank': 5, 'id': 'proj.similarity.threshold', 'score': 0.4191}]`
- gold score: 0.4158  evid: 1.0
- top1: `proj.similarity.describe` action=`describe` sibling=True
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=True

### fuh4_079 — `proj.similarity.is_rag` → EVIDENCE_REJECTED

- script: `Summarise the assignment similarity project, its stack, and whether it is RAG.`
- asr: `Summurize the assignment similarity project. It's fact and whether it is R-18.`
- path_opened: False
- fragment: `Summurize the assignment similarity project. It's fact and whether it is R-18.`
- gold Q: `Is the similarity checker a RAG system?`
- gold action: `None` topic=`project:similarity`
- hybrid top5: `[{'rank': 1, 'id': 'proj.similarity.describe', 'topic': 'project:similarity', 'score': 0.5145, 'semantic': 0.0, 'lexical': 0.5182, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.similarity.challenges', 'runner_up_score': 0.4767, 'action_type': 'describe'}, {'rank': 2, 'id': 'proj.similarity.challenges', 'topic': 'project:similarity', 'score': 0.4767, 'semantic': 0.0, 'lexical': 0.5958, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'experience'}, {'rank': 3, 'id': 'tech.cosine_semantic_search', 'topic': 'rag', 'score': 0.4184, 'semantic': 0.0, 'lexical': 0.3981, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'definition'}, {'rank': 4, 'id': 'proj.similarity.tech', 'topic': 'project:similarity', 'score': 0.4158, 'semantic': 0.0, 'lexical': 0.5198, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'experience'}, {'rank': 5, 'id': 'proj.similarity.role', 'topic': 'project:similarity', 'score': 0.3988, 'semantic': 0.0, 'lexical': 0.4985, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.similarity.describe', 'runner_up_score': 0.5145, 'action_type': 'experience'}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.similarity.describe', 'score': 0.5737}, {'rank': 2, 'id': 'proj.similarity.is_rag', 'score': 0.4621}, {'rank': 3, 'id': 'proj.similarity.challenges', 'score': 0.4574}, {'rank': 4, 'id': 'hard.similarity_vs_qgen_arch', 'score': 0.4198}, {'rank': 5, 'id': 'proj.similarity.threshold', 'score': 0.4191}]`
- gold score: 0.3527  evid: 1.0
- top1: `proj.similarity.describe` action=`describe` sibling=True
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=False lost=[]
- evidence_rejected=True seg=False gran=False

### fuh4_080 — `tech.overfitting` → SEGMENTATION_RESIDUAL

- script: `Define overfitting, detection signals, and your mitigation playbook.`
- asr: `Define overfitting detection signals in your mitigation playbook.`
- path_opened: False
- fragment: `Define overfitting detection signals in your mitigation playbook.`
- gold Q: `What is overfitting?`
- gold action: `definition` topic=`ml`
- hybrid top5: `[{'rank': 1, 'id': 'tech.overfitting', 'topic': 'ml', 'score': 0.515, 'semantic': 0.0, 'lexical': 0.4688, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.what_is_llm', 'runner_up_score': 0.4106, 'action_type': 'definition'}, {'rank': 2, 'id': 'tech.what_is_llm', 'topic': 'llm', 'score': 0.4106, 'semantic': 0.0, 'lexical': 0.4632, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}, {'rank': 3, 'id': 'tech.rag_what', 'topic': 'rag', 'score': 0.4106, 'semantic': 0.0, 'lexical': 0.4632, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}, {'rank': 4, 'id': 'tech.what_is_ml', 'topic': 'ml', 'score': 0.4034, 'semantic': 0.0, 'lexical': 0.3293, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}, {'rank': 5, 'id': 'tech.agentic_what', 'topic': 'agents', 'score': 0.328, 'semantic': 0.0, 'lexical': 0.36, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.overfitting_prevent', 'score': 0.4543}, {'rank': 2, 'id': 'tech.data_leakage_prevent', 'score': 0.3809}, {'rank': 3, 'id': 'tech.imbalanced_data', 'score': 0.3706}, {'rank': 4, 'id': 'tech.overfitting', 'score': 0.3488}, {'rank': 5, 'id': 'proj.early_warning.leakage', 'score': 0.3371}]`
- gold score: 0.515  evid: 1.0
- top1: `tech.overfitting` action=`definition` sibling=False
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=False lost=[]
- evidence_rejected=False seg=True gran=False

### fuh4_080 — `tech.overfitting_prevent` → SEGMENTATION_RESIDUAL

- script: `Define overfitting, detection signals, and your mitigation playbook.`
- asr: `Define overfitting detection signals in your mitigation playbook.`
- path_opened: False
- fragment: `Define overfitting detection signals in your mitigation playbook.`
- gold Q: `How do you prevent overfitting?`
- gold action: `how` topic=`ml`
- hybrid top5: `[{'rank': 1, 'id': 'tech.overfitting', 'topic': 'ml', 'score': 0.515, 'semantic': 0.0, 'lexical': 0.4688, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.what_is_llm', 'runner_up_score': 0.4106, 'action_type': 'definition'}, {'rank': 2, 'id': 'tech.what_is_llm', 'topic': 'llm', 'score': 0.4106, 'semantic': 0.0, 'lexical': 0.4632, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}, {'rank': 3, 'id': 'tech.rag_what', 'topic': 'rag', 'score': 0.4106, 'semantic': 0.0, 'lexical': 0.4632, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}, {'rank': 4, 'id': 'tech.what_is_ml', 'topic': 'ml', 'score': 0.4034, 'semantic': 0.0, 'lexical': 0.3293, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}, {'rank': 5, 'id': 'tech.agentic_what', 'topic': 'agents', 'score': 0.328, 'semantic': 0.0, 'lexical': 0.36, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.overfitting_prevent', 'score': 0.4543}, {'rank': 2, 'id': 'tech.data_leakage_prevent', 'score': 0.3809}, {'rank': 3, 'id': 'tech.imbalanced_data', 'score': 0.3706}, {'rank': 4, 'id': 'tech.overfitting', 'score': 0.3488}, {'rank': 5, 'id': 'proj.early_warning.leakage', 'score': 0.3371}]`
- gold score: None  evid: 1.0
- top1: `tech.overfitting` action=`definition` sibling=True
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=False lost=[]
- evidence_rejected=False seg=True gran=False

### fuh4_080 — `tech.evaluate_classification` → SEGMENTATION_RESIDUAL

- script: `Define overfitting, detection signals, and your mitigation playbook.`
- asr: `Define overfitting detection signals in your mitigation playbook.`
- path_opened: False
- fragment: `Define overfitting detection signals in your mitigation playbook.`
- gold Q: `How do you evaluate a classification model?`
- gold action: `how` topic=`ml`
- hybrid top5: `[{'rank': 1, 'id': 'tech.overfitting', 'topic': 'ml', 'score': 0.515, 'semantic': 0.0, 'lexical': 0.4688, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.what_is_llm', 'runner_up_score': 0.4106, 'action_type': 'definition'}, {'rank': 2, 'id': 'tech.what_is_llm', 'topic': 'llm', 'score': 0.4106, 'semantic': 0.0, 'lexical': 0.4632, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}, {'rank': 3, 'id': 'tech.rag_what', 'topic': 'rag', 'score': 0.4106, 'semantic': 0.0, 'lexical': 0.4632, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}, {'rank': 4, 'id': 'tech.what_is_ml', 'topic': 'ml', 'score': 0.4034, 'semantic': 0.0, 'lexical': 0.3293, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}, {'rank': 5, 'id': 'tech.agentic_what', 'topic': 'agents', 'score': 0.328, 'semantic': 0.0, 'lexical': 0.36, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.overfitting', 'runner_up_score': 0.515, 'action_type': 'definition'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.overfitting_prevent', 'score': 0.4543}, {'rank': 2, 'id': 'tech.data_leakage_prevent', 'score': 0.3809}, {'rank': 3, 'id': 'tech.imbalanced_data', 'score': 0.3706}, {'rank': 4, 'id': 'tech.overfitting', 'score': 0.3488}, {'rank': 5, 'id': 'proj.early_warning.leakage', 'score': 0.3371}]`
- gold score: None  evid: 1.0
- top1: `tech.overfitting` action=`definition` sibling=True
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=False lost=[]
- evidence_rejected=False seg=True gran=False

### fuh4_081 — `tech.vector_db_choice` → HYBRID_RANKING

- script: `Your vector DB history, then your pick for our workload and why.`
- asr: `Your vector DB history, then your pick for our workload and Y.`
- path_opened: True
- fragment: `Your vector DB history`
- gold Q: `Which vector database would you choose for us?`
- gold action: `None` topic=`rag`
- hybrid top5: `[{'rank': 1, 'id': 'cv.vector_db', 'topic': 'skills', 'score': 0.9059, 'semantic': 0.0, 'lexical': 0.8824, 'keyword': 1.0, 'mode': 'strong', 'runner_up': 'tech.vector_db_choice', 'runner_up_score': 0.7486, 'action_type': 'experience'}, {'rank': 2, 'id': 'tech.vector_db_choice', 'topic': 'rag', 'score': 0.7486, 'semantic': 0.0, 'lexical': 0.8108, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'cv.vector_db', 'runner_up_score': 0.9059, 'action_type': None}, {'rank': 3, 'id': 'hard.graph_vs_vector', 'topic': 'rag', 'score': 0.7316, 'semantic': 0.0, 'lexical': 0.7895, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'cv.vector_db', 'runner_up_score': 0.9059, 'action_type': 'when'}, {'rank': 4, 'id': 'proj.similarity.tech', 'topic': 'project:similarity', 'score': 0.7316, 'semantic': 0.0, 'lexical': 0.7895, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'cv.vector_db', 'runner_up_score': 0.9059, 'action_type': 'experience'}, {'rank': 5, 'id': 'proj.completion_risk.tech', 'topic': 'project:completion', 'score': 0.6857, 'semantic': 0.0, 'lexical': 0.8571, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'cv.vector_db', 'runner_up_score': 0.9059, 'action_type': 'experience'}]`
- semantic top5: `[{'rank': 1, 'id': 'cv.vector_db', 'score': 0.4721}, {'rank': 2, 'id': 'proj.completion_risk.tech', 'score': 0.4401}, {'rank': 3, 'id': 'tech.vector_db_choice', 'score': 0.4211}, {'rank': 4, 'id': 'proj.similarity.tech', 'score': 0.3756}, {'rank': 5, 'id': 'hard.graph_vs_vector', 'score': 0.3398}]`
- gold score: 0.7486  evid: 1.0
- top1: `cv.vector_db` action=`experience` sibling=False
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False

### fuh4_082 — `tech.agent_orchestrator` → HYBRID_RANKING

- script: `Role of an orchestrator versus a lone tool-calling model — when is each enough?`
- asr: `Role of an orchestrator versus a lone tool-calling model. When is each enough?`
- path_opened: False
- fragment: `Role of an orchestrator versus a lone tool-calling model`
- gold Q: `What is an agent orchestrator?`
- gold action: `definition` topic=`agents`
- hybrid top5: `[{'rank': 1, 'id': 'hard.agent_terms_difference', 'topic': 'agents', 'score': 0.6461, 'semantic': 0.0, 'lexical': 0.4576, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.tool_calling', 'runner_up_score': 0.5429, 'action_type': 'compare'}, {'rank': 2, 'id': 'tech.tool_calling', 'topic': 'agents', 'score': 0.5429, 'semantic': 0.0, 'lexical': 0.6786, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_terms_difference', 'runner_up_score': 0.6461, 'action_type': 'definition'}, {'rank': 3, 'id': 'tech.agent_orchestrator', 'topic': 'agents', 'score': 0.5196, 'semantic': 0.0, 'lexical': 0.2995, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_terms_difference', 'runner_up_score': 0.6461, 'action_type': 'definition'}, {'rank': 4, 'id': 'tech.multi_agent_when', 'topic': 'agents', 'score': 0.4231, 'semantic': 0.0, 'lexical': 0.3538, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_terms_difference', 'runner_up_score': 0.6461, 'action_type': 'when'}, {'rank': 5, 'id': 'hard.tool_schema', 'topic': 'agents', 'score': 0.3785, 'semantic': 0.0, 'lexical': 0.3481, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_terms_difference', 'runner_up_score': 0.6461, 'action_type': 'why'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.multi_agent_when', 'score': 0.4589}, {'rank': 2, 'id': 'hard.agent_terms_difference', 'score': 0.4552}, {'rank': 3, 'id': 'hard.langgraph_vs_n8n_vs_python', 'score': 0.454}, {'rank': 4, 'id': 'tech.agent_orchestrator', 'score': 0.4328}, {'rank': 5, 'id': 'tech.tool_calling', 'score': 0.39}]`
- gold score: 0.5196  evid: 1.0
- top1: `hard.agent_terms_difference` action=`compare` sibling=False
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False

### fuh4_082 — `tech.multi_agent_when` → HYBRID_RANKING

- script: `Role of an orchestrator versus a lone tool-calling model — when is each enough?`
- asr: `Role of an orchestrator versus a lone tool-calling model. When is each enough?`
- path_opened: False
- fragment: `Role of an orchestrator versus a lone tool-calling model`
- gold Q: `When do you need multiple agents instead of one?`
- gold action: `when` topic=`agents`
- hybrid top5: `[{'rank': 1, 'id': 'hard.agent_terms_difference', 'topic': 'agents', 'score': 0.6461, 'semantic': 0.0, 'lexical': 0.4576, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.tool_calling', 'runner_up_score': 0.5429, 'action_type': 'compare'}, {'rank': 2, 'id': 'tech.tool_calling', 'topic': 'agents', 'score': 0.5429, 'semantic': 0.0, 'lexical': 0.6786, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_terms_difference', 'runner_up_score': 0.6461, 'action_type': 'definition'}, {'rank': 3, 'id': 'tech.agent_orchestrator', 'topic': 'agents', 'score': 0.5196, 'semantic': 0.0, 'lexical': 0.2995, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_terms_difference', 'runner_up_score': 0.6461, 'action_type': 'definition'}, {'rank': 4, 'id': 'tech.multi_agent_when', 'topic': 'agents', 'score': 0.4231, 'semantic': 0.0, 'lexical': 0.3538, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_terms_difference', 'runner_up_score': 0.6461, 'action_type': 'when'}, {'rank': 5, 'id': 'hard.tool_schema', 'topic': 'agents', 'score': 0.3785, 'semantic': 0.0, 'lexical': 0.3481, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_terms_difference', 'runner_up_score': 0.6461, 'action_type': 'why'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.multi_agent_when', 'score': 0.4589}, {'rank': 2, 'id': 'hard.agent_terms_difference', 'score': 0.4552}, {'rank': 3, 'id': 'hard.langgraph_vs_n8n_vs_python', 'score': 0.454}, {'rank': 4, 'id': 'tech.agent_orchestrator', 'score': 0.4328}, {'rank': 5, 'id': 'tech.tool_calling', 'score': 0.39}]`
- gold score: 0.4231  evid: 1.0
- top1: `hard.agent_terms_difference` action=`compare` sibling=False
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False

### fuh4_083 — `cv.pmp_value` → CANDIDATE_GENERATION

- script: `Education, certifications, and how they matter for this role.`
- asr: `Education, certification, and how they matter for this role.`
- path_opened: True
- fragment: `certification`
- gold Q: `How does PMP help you as an AI engineer?`
- gold action: `how` topic=`certifications`
- hybrid top5: `[{'rank': 1, 'id': 'cv.certifications', 'topic': 'certifications', 'score': 0.7704, 'semantic': 0.0, 'lexical': 0.963, 'keyword': 0.0, 'mode': 'strong', 'runner_up': 'proj.kiosk.voice_classifier', 'runner_up_score': 0.66, 'action_type': None}, {'rank': 2, 'id': 'proj.kiosk.voice_classifier', 'topic': 'project:kiosk', 'score': 0.66, 'semantic': 0.0, 'lexical': 0.825, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'cv.certifications', 'runner_up_score': 0.7704, 'action_type': None}, {'rank': 3, 'id': 'cv.prince2', 'topic': 'certifications', 'score': 0.6092, 'semantic': 0.0, 'lexical': 0.7615, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'cv.certifications', 'runner_up_score': 0.7704, 'action_type': 'definition'}, {'rank': 4, 'id': 'proj.helpdesk.tech', 'topic': 'project:helpdesk', 'score': 0.5891, 'semantic': 0.0, 'lexical': 0.7364, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'cv.certifications', 'runner_up_score': 0.7704, 'action_type': 'experience'}, {'rank': 5, 'id': 'cv.nlp_experience', 'topic': 'skills', 'score': 0.5891, 'semantic': 0.0, 'lexical': 0.7364, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'cv.certifications', 'runner_up_score': 0.7704, 'action_type': 'experience'}]`
- semantic top5: `[{'rank': 1, 'id': 'cv.certifications', 'score': 0.4591}, {'rank': 2, 'id': 'cv.ccnp', 'score': 0.3755}, {'rank': 3, 'id': 'cv.n8n', 'score': 0.3497}, {'rank': 4, 'id': 'cv.langchain', 'score': 0.3381}, {'rank': 5, 'id': 'cv.prince2', 'score': 0.3368}]`
- gold score: None  evid: 1.0
- top1: `cv.certifications` action=`None` sibling=True
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False

### fuh4_084 — `tech.prompt_injection_what` → SEMANTIC_PROFILE_QUALITY

- script: `Prompt injection sources, PDF risk, and guardrails that block it.`
- asr: `Compt injection sources, PDF risk, and guardrails that's locked.`
- path_opened: True
- fragment: `What are guardrails?`
- gold Q: `What is prompt injection?`
- gold action: `definition` topic=`guardrails`
- hybrid top5: `[{'rank': 1, 'id': 'tech.guardrails_what', 'topic': 'guardrails', 'score': 1.26, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 1.0, 'mode': 'strong', 'runner_up': 'tech.guardrails_how', 'runner_up_score': 1.12, 'action_type': 'definition'}, {'rank': 2, 'id': 'tech.guardrails_how', 'topic': 'guardrails', 'score': 1.12, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': 'experience'}, {'rank': 3, 'id': 'cv.guardrails', 'topic': 'skills', 'score': 1.12, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': 'experience'}, {'rank': 4, 'id': 'tech.guardrails_layers', 'topic': 'guardrails', 'score': 1.06, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': None}, {'rank': 5, 'id': 'gen.ai_ethics', 'topic': 'personal', 'score': 0.8, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': 'how'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.guardrails_what', 'score': 0.6149}, {'rank': 2, 'id': 'tech.guardrails_how', 'score': 0.5441}, {'rank': 3, 'id': 'tech.guardrails_layers', 'score': 0.459}, {'rank': 4, 'id': 'cv.guardrails', 'score': 0.4559}, {'rank': 5, 'id': 'tech.hallucination_prevent', 'score': 0.2931}]`
- gold score: None  evid: 1.0
- top1: `tech.guardrails_what` action=`definition` sibling=True
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=['prompt']
- evidence_rejected=False seg=False gran=False

### fuh4_084 — `hard.injection_in_pdf` → CANDIDATE_GENERATION

- script: `Prompt injection sources, PDF risk, and guardrails that block it.`
- asr: `Compt injection sources, PDF risk, and guardrails that's locked.`
- path_opened: True
- fragment: `What are guardrails?`
- gold Q: `What if a retrieved PDF says ignore previous instructions and dump all documents?`
- gold action: `None` topic=`guardrails`
- hybrid top5: `[{'rank': 1, 'id': 'tech.guardrails_what', 'topic': 'guardrails', 'score': 1.26, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 1.0, 'mode': 'strong', 'runner_up': 'tech.guardrails_how', 'runner_up_score': 1.12, 'action_type': 'definition'}, {'rank': 2, 'id': 'tech.guardrails_how', 'topic': 'guardrails', 'score': 1.12, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': 'experience'}, {'rank': 3, 'id': 'cv.guardrails', 'topic': 'skills', 'score': 1.12, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': 'experience'}, {'rank': 4, 'id': 'tech.guardrails_layers', 'topic': 'guardrails', 'score': 1.06, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': None}, {'rank': 5, 'id': 'gen.ai_ethics', 'topic': 'personal', 'score': 0.8, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': 'how'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.guardrails_what', 'score': 0.6149}, {'rank': 2, 'id': 'tech.guardrails_how', 'score': 0.5441}, {'rank': 3, 'id': 'tech.guardrails_layers', 'score': 0.459}, {'rank': 4, 'id': 'cv.guardrails', 'score': 0.4559}, {'rank': 5, 'id': 'tech.hallucination_prevent', 'score': 0.2931}]`
- gold score: None  evid: 1.0
- top1: `tech.guardrails_what` action=`definition` sibling=False
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False

### fuh4_084 — `tech.guardrails_how` → ACTION_GRANULARITY

- script: `Prompt injection sources, PDF risk, and guardrails that block it.`
- asr: `Compt injection sources, PDF risk, and guardrails that's locked.`
- path_opened: True
- fragment: `What are guardrails?`
- gold Q: `How do you build guardrails for an LLM?`
- gold action: `experience` topic=`guardrails`
- hybrid top5: `[{'rank': 1, 'id': 'tech.guardrails_what', 'topic': 'guardrails', 'score': 1.26, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 1.0, 'mode': 'strong', 'runner_up': 'tech.guardrails_how', 'runner_up_score': 1.12, 'action_type': 'definition'}, {'rank': 2, 'id': 'tech.guardrails_how', 'topic': 'guardrails', 'score': 1.12, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': 'experience'}, {'rank': 3, 'id': 'cv.guardrails', 'topic': 'skills', 'score': 1.12, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': 'experience'}, {'rank': 4, 'id': 'tech.guardrails_layers', 'topic': 'guardrails', 'score': 1.06, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': None}, {'rank': 5, 'id': 'gen.ai_ethics', 'topic': 'personal', 'score': 0.8, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'runner_up': 'tech.guardrails_what', 'runner_up_score': 1.26, 'action_type': 'how'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.guardrails_what', 'score': 0.6149}, {'rank': 2, 'id': 'tech.guardrails_how', 'score': 0.5441}, {'rank': 3, 'id': 'tech.guardrails_layers', 'score': 0.459}, {'rank': 4, 'id': 'cv.guardrails', 'score': 0.4559}, {'rank': 5, 'id': 'tech.hallucination_prevent', 'score': 0.2931}]`
- gold score: 1.12  evid: 1.0
- top1: `tech.guardrails_what` action=`definition` sibling=True
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=True

### fuh4_085 — `tech.kubernetes` → HYBRID_RANKING

- script: `Docker value, container versus VM, and if we need Kubernetes.`
- asr: `Docker value, container versus VM, and if we need Cuba needs.`
- path_opened: True
- fragment: `If we need Cuba needs`
- gold Q: `Would you use Kubernetes?`
- gold action: `None` topic=`infra`
- hybrid top5: `[{'rank': 1, 'id': 'tech.sklearn_vs_neural', 'topic': 'ml', 'score': 0.364, 'semantic': 0.0, 'lexical': 0.455, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.kubernetes', 'runner_up_score': 0.36, 'action_type': 'why'}, {'rank': 2, 'id': 'tech.kubernetes', 'topic': 'infra', 'score': 0.36, 'semantic': 0.0, 'lexical': 0.45, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.sklearn_vs_neural', 'runner_up_score': 0.364, 'action_type': None}, {'rank': 3, 'id': 'tech.explain_ai_project_structure', 'topic': 'general', 'score': 0.336, 'semantic': 0.0, 'lexical': 0.42, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.sklearn_vs_neural', 'runner_up_score': 0.364, 'action_type': 'how'}, {'rank': 4, 'id': 'tech.gpu_sizing', 'topic': 'hosting', 'score': 0.3261, 'semantic': 0.0, 'lexical': 0.4076, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.sklearn_vs_neural', 'runner_up_score': 0.364, 'action_type': 'how'}, {'rank': 5, 'id': 'hard.supervisor_vs_router', 'topic': 'agents', 'score': 0.312, 'semantic': 0.0, 'lexical': 0.39, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.sklearn_vs_neural', 'runner_up_score': 0.364, 'action_type': 'when'}]`
- semantic top5: `[{'rank': 1, 'id': 'gen.anything_else', 'score': 0.2181}, {'rank': 2, 'id': 'tech.emirati_dialect', 'score': 0.1997}, {'rank': 3, 'id': 'gen.questions_for_us', 'score': 0.1932}, {'rank': 4, 'id': 'hard.agent_cannot_delete', 'score': 0.1661}, {'rank': 5, 'id': 'hard.empty_retrieval', 'score': 0.163}]`
- gold score: 0.36  evid: 1.0
- top1: `tech.sklearn_vs_neural` action=`why` sibling=True
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=False lost=['kubernetes']
- evidence_rejected=False seg=False gran=False

### fuh4_086 — `proj.early_warning.describe` → HYBRID_RANKING

- script: `Early-warning project story, KPI, and ministry outcome.`
- asr: `Early Warning Project Story, KPI, and Ministry Outcome`
- path_opened: True
- fragment: `How do you evaluate an early warning model for students?`
- gold Q: `Tell me about the Student Performance Early-Warning project`
- gold action: `describe` topic=`project:early_warning`
- hybrid top5: `[{'rank': 1, 'id': 'proj.early_warning.metric', 'topic': 'project:early_warning', 'score': 0.8, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'proj.early_warning.tech', 'runner_up_score': 0.5935, 'action_type': 'experience'}, {'rank': 2, 'id': 'proj.early_warning.tech', 'topic': 'project:early_warning', 'score': 0.5935, 'semantic': 0.0, 'lexical': 0.7419, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.early_warning.metric', 'runner_up_score': 0.8, 'action_type': 'experience'}, {'rank': 3, 'id': 'tech.evaluate_classification', 'topic': 'ml', 'score': 0.5405, 'semantic': 0.0, 'lexical': 0.5006, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.early_warning.metric', 'runner_up_score': 0.8, 'action_type': 'how'}, {'rank': 4, 'id': 'proj.early_warning.stack', 'topic': 'project:early_warning', 'score': 0.5247, 'semantic': 0.0, 'lexical': 0.5309, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.early_warning.metric', 'runner_up_score': 0.8, 'action_type': None}, {'rank': 5, 'id': 'tech.good_enough_to_launch', 'topic': 'evaluation', 'score': 0.5185, 'semantic': 0.0, 'lexical': 0.4731, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.early_warning.metric', 'runner_up_score': 0.8, 'action_type': 'how'}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.early_warning.result', 'score': 0.6195}, {'rank': 2, 'id': 'proj.early_warning.describe', 'score': 0.5807}, {'rank': 3, 'id': 'proj.early_warning.metric', 'score': 0.5738}, {'rank': 4, 'id': 'proj.early_warning.stack', 'score': 0.5302}, {'rank': 5, 'id': 'proj.early_warning.leakage', 'score': 0.5302}]`
- gold score: None  evid: 0.4
- top1: `proj.early_warning.metric` action=`experience` sibling=True
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False

### fuh4_086 — `proj.early_warning.metric` → HYBRID_RANKING

- script: `Early-warning project story, KPI, and ministry outcome.`
- asr: `Early Warning Project Story, KPI, and Ministry Outcome`
- path_opened: True
- fragment: `Why does recall matter more than accuracy for early warning?`
- gold Q: `Which metric did you use and why?`
- gold action: `experience` topic=`project:early_warning`
- hybrid top5: `[{'rank': 1, 'id': 'proj.early_warning.metric', 'topic': 'project:early_warning', 'score': 0.7553, 'semantic': 0.0, 'lexical': 0.6441, 'keyword': 1.0, 'mode': 'strong', 'runner_up': 'tech.precision_recall', 'runner_up_score': 0.5171, 'action_type': 'experience'}, {'rank': 2, 'id': 'tech.precision_recall', 'topic': 'ml', 'score': 0.5171, 'semantic': 0.0, 'lexical': 0.5214, 'keyword': 1.0, 'mode': 'weak', 'runner_up': 'proj.early_warning.metric', 'runner_up_score': 0.7553, 'action_type': 'definition'}, {'rank': 3, 'id': 'proj.early_warning.stack', 'topic': 'project:early_warning', 'score': 0.4774, 'semantic': 0.0, 'lexical': 0.4717, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'proj.early_warning.metric', 'runner_up_score': 0.7553, 'action_type': None}, {'rank': 4, 'id': 'proj.early_warning.result', 'topic': 'project:early_warning', 'score': 0.3833, 'semantic': 0.0, 'lexical': 0.4791, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.early_warning.metric', 'runner_up_score': 0.7553, 'action_type': None}, {'rank': 5, 'id': 'tech.mcp', 'topic': 'agents', 'score': 0.3795, 'semantic': 0.0, 'lexical': 0.4244, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'proj.early_warning.metric', 'runner_up_score': 0.7553, 'action_type': 'definition'}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.early_warning.metric', 'score': 0.4872}, {'rank': 2, 'id': 'tech.precision_recall', 'score': 0.4283}, {'rank': 3, 'id': 'proj.early_warning.stack', 'score': 0.4138}, {'rank': 4, 'id': 'gen.failure', 'score': 0.366}, {'rank': 5, 'id': 'proj.early_warning.leakage', 'score': 0.3493}]`
- gold score: 0.7553  evid: 0.4
- top1: `proj.early_warning.metric` action=`experience` sibling=False
- accept: gold_top1_accepted=True reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False

### fuh4_087 — `hard.tool_schema` → HYBRID_RANKING

- script: `Tool calling basics, schema need, and when to halt tool loops.`
- asr: `Tool calling basics schema need and when to halt tool loops.`
- path_opened: True
- fragment: `Tool calling basics schema need`
- gold Q: `Why do tool arguments need a schema if the model is smart?`
- gold action: `why` topic=`agents`
- hybrid top5: `[{'rank': 1, 'id': 'tech.tool_calling', 'topic': 'agents', 'score': 0.684, 'semantic': 0.0, 'lexical': 0.73, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.tool_schema', 'runner_up_score': 0.6466, 'action_type': 'definition'}, {'rank': 2, 'id': 'hard.tool_schema', 'topic': 'agents', 'score': 0.6466, 'semantic': 0.0, 'lexical': 0.5583, 'keyword': 1.0, 'mode': 'weak', 'runner_up': 'tech.tool_calling', 'runner_up_score': 0.684, 'action_type': 'why'}, {'rank': 3, 'id': 'hard.agent_loop', 'topic': 'agents', 'score': 0.3893, 'semantic': 0.0, 'lexical': 0.4867, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.tool_calling', 'runner_up_score': 0.684, 'action_type': 'how'}, {'rank': 4, 'id': 'hard.wrong_tool', 'topic': 'agents', 'score': 0.3409, 'semantic': 0.0, 'lexical': 0.3012, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.tool_calling', 'runner_up_score': 0.684, 'action_type': None}, {'rank': 5, 'id': 'hard.agent_cannot_delete', 'topic': 'agents', 'score': 0.3225, 'semantic': 0.0, 'lexical': 0.2781, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.tool_calling', 'runner_up_score': 0.684, 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'hard.tool_schema', 'score': 0.6331}, {'rank': 2, 'id': 'tech.tool_calling', 'score': 0.6209}, {'rank': 3, 'id': 'hard.wrong_tool', 'score': 0.3979}, {'rank': 4, 'id': 'tech.agent_tools_permissions', 'score': 0.3831}, {'rank': 5, 'id': 'tech.guardrails_how', 'score': 0.376}]`
- gold score: 0.6466  evid: 1.0
- top1: `tech.tool_calling` action=`definition` sibling=False
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False

### fuh4_087 — `hard.agent_stop_tools` → ACTION_GRANULARITY

- script: `Tool calling basics, schema need, and when to halt tool loops.`
- asr: `Tool calling basics schema need and when to halt tool loops.`
- path_opened: True
- fragment: `When to halt tool loops?`
- gold Q: `When should an agent stop using tools?`
- gold action: `when` topic=`agents`
- hybrid top5: `[{'rank': 1, 'id': 'hard.agent_loop', 'topic': 'agents', 'score': 0.64, 'semantic': 0.0, 'lexical': 0.8, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_stop_tools', 'runner_up_score': 0.3942, 'action_type': 'how'}, {'rank': 2, 'id': 'hard.agent_stop_tools', 'topic': 'agents', 'score': 0.3942, 'semantic': 0.0, 'lexical': 0.4427, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'hard.agent_loop', 'runner_up_score': 0.64, 'action_type': 'when'}, {'rank': 3, 'id': 'hard.agent_cannot_delete', 'topic': 'agents', 'score': 0.3912, 'semantic': 0.0, 'lexical': 0.364, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_loop', 'runner_up_score': 0.64, 'action_type': None}, {'rank': 4, 'id': 'hard.tool_schema', 'topic': 'agents', 'score': 0.38, 'semantic': 0.0, 'lexical': 0.35, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'hard.agent_loop', 'runner_up_score': 0.64, 'action_type': 'why'}, {'rank': 5, 'id': 'tech.classify_or_llm', 'topic': 'ml', 'score': 0.3104, 'semantic': 0.0, 'lexical': 0.338, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'hard.agent_loop', 'runner_up_score': 0.64, 'action_type': 'when'}]`
- semantic top5: `[{'rank': 1, 'id': 'hard.agent_stop_tools', 'score': 0.5859}, {'rank': 2, 'id': 'hard.agent_loop', 'score': 0.5633}, {'rank': 3, 'id': 'hard.timeout_vs_steps', 'score': 0.4261}, {'rank': 4, 'id': 'hard.circuit_breaker', 'score': 0.3462}, {'rank': 5, 'id': 'hard.agent_cannot_delete', 'score': 0.3442}]`
- gold score: 0.3942  evid: 1.0
- top1: `hard.agent_loop` action=`how` sibling=True
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=True

### fuh4_088 — `tech.whisper_vs_cloud` → ACTION_GRANULARITY

- script: `STT internals, local Whisper rationale, and accuracy acceptance tests.`
- asr: `STT internals, local Whisper rationale, and accuracy acceptance test.`
- path_opened: True
- fragment: `local Whisper rationale`
- gold Q: `Why Whisper and not a cloud speech API?`
- gold action: `why` topic=`speech`
- hybrid top5: `[{'rank': 1, 'id': 'tech.what_is_whisper', 'topic': 'speech', 'score': 0.74, 'semantic': 0.0, 'lexical': 0.525, 'keyword': 1.0, 'mode': 'strong', 'runner_up': 'cv.whisper_experience', 'runner_up_score': 0.556, 'action_type': 'definition'}, {'rank': 2, 'id': 'cv.whisper_experience', 'topic': 'skills', 'score': 0.556, 'semantic': 0.0, 'lexical': 0.42, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.what_is_whisper', 'runner_up_score': 0.74, 'action_type': 'experience'}, {'rank': 3, 'id': 'proj.kiosk.describe', 'topic': 'project:kiosk', 'score': 0.5476, 'semantic': 0.0, 'lexical': 0.4095, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.what_is_whisper', 'runner_up_score': 0.74, 'action_type': 'describe'}, {'rank': 4, 'id': 'tech.whisper_vs_cloud', 'topic': 'speech', 'score': 0.5197, 'semantic': 0.0, 'lexical': 0.3746, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.what_is_whisper', 'runner_up_score': 0.74, 'action_type': 'why'}, {'rank': 5, 'id': 'proj.kiosk.stack', 'topic': 'project:kiosk', 'score': 0.5049, 'semantic': 0.0, 'lexical': 0.3561, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.what_is_whisper', 'runner_up_score': 0.74, 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'proj.kiosk.describe', 'score': 0.4226}, {'rank': 2, 'id': 'proj.kiosk.challenges', 'score': 0.3525}, {'rank': 3, 'id': 'tech.whisper_vs_cloud', 'score': 0.3394}, {'rank': 4, 'id': 'cv.whisper_experience', 'score': 0.3052}, {'rank': 5, 'id': 'tech.voice_assistant_design', 'score': 0.294}]`
- gold score: 0.5197  evid: 1.0
- top1: `tech.what_is_whisper` action=`definition` sibling=True
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=True

### fuh4_088 — `tech.transcription_quality` → HYBRID_RANKING

- script: `STT internals, local Whisper rationale, and accuracy acceptance tests.`
- asr: `STT internals, local Whisper rationale, and accuracy acceptance test.`
- path_opened: True
- fragment: `STT internals`
- gold Q: `How do you know the transcription system is good enough?`
- gold action: `how` topic=`speech`
- hybrid top5: `[{'rank': 1, 'id': 'tech.how_stt_works', 'topic': 'speech', 'score': 1.0, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 1.0, 'mode': 'strong', 'runner_up': 'tech.voice_assistant_design', 'runner_up_score': 0.8, 'action_type': 'how'}, {'rank': 2, 'id': 'tech.voice_assistant_design', 'topic': 'speech', 'score': 0.8, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'runner_up': 'tech.how_stt_works', 'runner_up_score': 1.0, 'action_type': 'experience'}, {'rank': 3, 'id': 'proj.kiosk.describe', 'topic': 'project:kiosk', 'score': 0.6148, 'semantic': 0.0, 'lexical': 0.5185, 'keyword': 1.0, 'mode': 'weak', 'runner_up': 'tech.how_stt_works', 'runner_up_score': 1.0, 'action_type': 'describe'}, {'rank': 4, 'id': 'cv.whisper_experience', 'topic': 'skills', 'score': 0.4692, 'semantic': 0.0, 'lexical': 0.4615, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.how_stt_works', 'runner_up_score': 1.0, 'action_type': 'experience'}, {'rank': 5, 'id': 'tech.transcription_quality', 'topic': 'speech', 'score': 0.448, 'semantic': 0.0, 'lexical': 0.56, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.how_stt_works', 'runner_up_score': 1.0, 'action_type': 'how'}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.prompt_injection_supplier', 'score': 0.2237}, {'rank': 2, 'id': 'tech.air_gapped', 'score': 0.203}, {'rank': 3, 'id': 'hard.why_not_chroma_prod', 'score': 0.1942}, {'rank': 4, 'id': 'tech.vector_db_choice', 'score': 0.1939}, {'rank': 5, 'id': 'tech.hosting_decision', 'score': 0.1825}]`
- gold score: 0.448  evid: 1.0
- top1: `tech.how_stt_works` action=`how` sibling=True
- accept: gold_top1_accepted=False reason=None
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False

### fuh4_089 — `tech.langgraph_vs_langchain` → STT_DISTORTION

- script: `LangGraph versus LangChain, your usage, and surviving without LangChain.`
- asr: `Nantler versus Lanskings. You use it and surviving without Lanschain.`
- path_opened: False
- fragment: `Nantler versus Lanskings. You use it and surviving without Lanschain.`
- gold Q: `What is the difference between LangChain and LangGraph?`
- gold action: `compare` topic=`agents`
- hybrid top5: `[{'rank': 1, 'id': 'tech.rag_vs_finetuning', 'topic': 'rag', 'score': 0.4114, 'semantic': 0.0, 'lexical': 0.3393, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.tfidf_vs_embeddings', 'runner_up_score': 0.3334, 'action_type': None}, {'rank': 2, 'id': 'tech.tfidf_vs_embeddings', 'topic': 'nlp', 'score': 0.3334, 'semantic': 0.0, 'lexical': 0.3668, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': 'compare'}, {'rank': 3, 'id': 'tech.sklearn_vs_neural', 'topic': 'ml', 'score': 0.3319, 'semantic': 0.0, 'lexical': 0.3648, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': 'why'}, {'rank': 4, 'id': 'tech.agent_vs_workflow', 'topic': 'agents', 'score': 0.3269, 'semantic': 0.0, 'lexical': 0.3586, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': 'compare'}, {'rank': 5, 'id': 'hard.remove_langchain', 'topic': 'frameworks', 'score': 0.3259, 'semantic': 0.0, 'lexical': 0.4074, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'hard.langgraph_vs_n8n_vs_python', 'score': 0.2578}, {'rank': 2, 'id': 'cv.image_processing', 'score': 0.2417}, {'rank': 3, 'id': 'tech.langgraph_vs_langchain', 'score': 0.2379}, {'rank': 4, 'id': 'cv.core_skills', 'score': 0.2286}, {'rank': 5, 'id': 'hard.why_not_chroma_prod', 'score': 0.2271}]`
- gold score: None  evid: 1.0
- top1: `tech.rag_vs_finetuning` action=`None` sibling=True
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=True lost=['langchain', 'langgraph']
- evidence_rejected=False seg=False gran=False

### fuh4_089 — `cv.langgraph` → CANDIDATE_GENERATION

- script: `LangGraph versus LangChain, your usage, and surviving without LangChain.`
- asr: `Nantler versus Lanskings. You use it and surviving without Lanschain.`
- path_opened: False
- fragment: `Nantler versus Lanskings. You use it and surviving without Lanschain.`
- gold Q: `Have you used LangGraph?`
- gold action: `experience` topic=`skills`
- hybrid top5: `[{'rank': 1, 'id': 'tech.rag_vs_finetuning', 'topic': 'rag', 'score': 0.4114, 'semantic': 0.0, 'lexical': 0.3393, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.tfidf_vs_embeddings', 'runner_up_score': 0.3334, 'action_type': None}, {'rank': 2, 'id': 'tech.tfidf_vs_embeddings', 'topic': 'nlp', 'score': 0.3334, 'semantic': 0.0, 'lexical': 0.3668, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': 'compare'}, {'rank': 3, 'id': 'tech.sklearn_vs_neural', 'topic': 'ml', 'score': 0.3319, 'semantic': 0.0, 'lexical': 0.3648, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': 'why'}, {'rank': 4, 'id': 'tech.agent_vs_workflow', 'topic': 'agents', 'score': 0.3269, 'semantic': 0.0, 'lexical': 0.3586, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': 'compare'}, {'rank': 5, 'id': 'hard.remove_langchain', 'topic': 'frameworks', 'score': 0.3259, 'semantic': 0.0, 'lexical': 0.4074, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'hard.langgraph_vs_n8n_vs_python', 'score': 0.2578}, {'rank': 2, 'id': 'cv.image_processing', 'score': 0.2417}, {'rank': 3, 'id': 'tech.langgraph_vs_langchain', 'score': 0.2379}, {'rank': 4, 'id': 'cv.core_skills', 'score': 0.2286}, {'rank': 5, 'id': 'hard.why_not_chroma_prod', 'score': 0.2271}]`
- gold score: None  evid: 1.0
- top1: `tech.rag_vs_finetuning` action=`None` sibling=False
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=False lost=['langgraph']
- evidence_rejected=False seg=False gran=False

### fuh4_089 — `hard.remove_langchain` → HYBRID_RANKING

- script: `LangGraph versus LangChain, your usage, and surviving without LangChain.`
- asr: `Nantler versus Lanskings. You use it and surviving without Lanschain.`
- path_opened: False
- fragment: `Nantler versus Lanskings. You use it and surviving without Lanschain.`
- gold Q: `If I remove LangChain from your system, can it still work?`
- gold action: `None` topic=`frameworks`
- hybrid top5: `[{'rank': 1, 'id': 'tech.rag_vs_finetuning', 'topic': 'rag', 'score': 0.4114, 'semantic': 0.0, 'lexical': 0.3393, 'keyword': 0.5, 'mode': 'weak', 'runner_up': 'tech.tfidf_vs_embeddings', 'runner_up_score': 0.3334, 'action_type': None}, {'rank': 2, 'id': 'tech.tfidf_vs_embeddings', 'topic': 'nlp', 'score': 0.3334, 'semantic': 0.0, 'lexical': 0.3668, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': 'compare'}, {'rank': 3, 'id': 'tech.sklearn_vs_neural', 'topic': 'ml', 'score': 0.3319, 'semantic': 0.0, 'lexical': 0.3648, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': 'why'}, {'rank': 4, 'id': 'tech.agent_vs_workflow', 'topic': 'agents', 'score': 0.3269, 'semantic': 0.0, 'lexical': 0.3586, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': 'compare'}, {'rank': 5, 'id': 'hard.remove_langchain', 'topic': 'frameworks', 'score': 0.3259, 'semantic': 0.0, 'lexical': 0.4074, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.rag_vs_finetuning', 'runner_up_score': 0.4114, 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'hard.langgraph_vs_n8n_vs_python', 'score': 0.2578}, {'rank': 2, 'id': 'cv.image_processing', 'score': 0.2417}, {'rank': 3, 'id': 'tech.langgraph_vs_langchain', 'score': 0.2379}, {'rank': 4, 'id': 'cv.core_skills', 'score': 0.2286}, {'rank': 5, 'id': 'hard.why_not_chroma_prod', 'score': 0.2271}]`
- gold score: 0.3259  evid: 1.0
- top1: `tech.rag_vs_finetuning` action=`None` sibling=False
- accept: gold_top1_accepted=False reason=low_score
- stt_distortion=False lost=['langchain']
- evidence_rejected=False seg=False gran=False

### fuh4_090 — `tech.metadata_filtering` → ACCEPTANCE_GATE

- script: `Embeddings, cosine search, metadata filters, and hybrid search trade-offs — cover all four.`
- asr: `Embedings, cosine search, metadata filters, and hybrid search tradeoffs cover all four.`
- path_opened: True
- fragment: `metadata filters`
- gold Q: `What is metadata filtering in RAG?`
- gold action: `definition` topic=`rag`
- hybrid top5: `[{'rank': 1, 'id': 'tech.metadata_filtering', 'topic': 'rag', 'score': 0.8059, 'semantic': 0.0, 'lexical': 0.8824, 'keyword': 0.5, 'mode': 'strong', 'runner_up': 'cv.chromadb', 'runner_up_score': 0.8, 'action_type': 'definition'}, {'rank': 2, 'id': 'cv.chromadb', 'topic': 'skills', 'score': 0.8, 'semantic': 0.0, 'lexical': 1.0, 'keyword': 0.0, 'mode': 'strong', 'runner_up': 'tech.metadata_filtering', 'runner_up_score': 0.8059, 'action_type': 'experience'}, {'rank': 3, 'id': 'tech.guardrails_what', 'topic': 'guardrails', 'score': 0.5184, 'semantic': 0.0, 'lexical': 0.648, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.metadata_filtering', 'runner_up_score': 0.8059, 'action_type': 'definition'}, {'rank': 4, 'id': 'tech.rag_access_control', 'topic': 'rag', 'score': 0.2534, 'semantic': 0.0, 'lexical': 0.3168, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.metadata_filtering', 'runner_up_score': 0.8059, 'action_type': None}, {'rank': 5, 'id': 'hard.agent_cannot_delete', 'topic': 'agents', 'score': 0.2475, 'semantic': 0.0, 'lexical': 0.3094, 'keyword': 0.0, 'mode': 'weak', 'runner_up': 'tech.metadata_filtering', 'runner_up_score': 0.8059, 'action_type': None}]`
- semantic top5: `[{'rank': 1, 'id': 'tech.metadata_filtering', 'score': 0.6585}, {'rank': 2, 'id': 'cv.chromadb', 'score': 0.4656}, {'rank': 3, 'id': 'tech.rag_access_control', 'score': 0.3772}, {'rank': 4, 'id': 'tech.rag_build', 'score': 0.3664}, {'rank': 5, 'id': 'proj.similarity.stack', 'score': 0.3371}]`
- gold score: 0.8059  evid: 1.0
- top1: `tech.metadata_filtering` action=`definition` sibling=False
- accept: gold_top1_accepted=False reason=ambiguous_margin
- stt_distortion=False lost=[]
- evidence_rejected=False seg=False gran=False
