# Medium paraphrase diagnosis

Read-only. No matcher / compound changes.

Gate reminder: E2E `intent_ok` requires `intent_score >= 0.70` where
**Fail-gate tallies:** intent_score_gate=7, would_pass_current_gate=1

`intent_score = semantic(bank_question, spoken)`. That fails when the bank
entry is right but its canonical question is much shorter than the paraphrase.

## Case 1 — E2E `FAIL` | HC=False

- **transcript:** Explain how RAG retrieves information before the language model generates an answer.
- **expected:** Explain how RAG retrieves information before the language model generates an answer.
- **detector:** `single` conf=0.92 signals=['no_multi_request_signal']
- **top-5 intents:**
  1. `tech.rag_what` score=0.728 mode=strong intent_vs_spoken=0.208 margin=0.104 — What is RAG?
  2. `proj.similarity.is_rag` score=0.624 mode=weak intent_vs_spoken=0.390 margin=-0.104 — Is the similarity checker a RAG system?
  3. `moe.ai_solutions` score=0.590 mode=weak intent_vs_spoken=0.372 margin=-0.138 — What AI solutions did you build at the Ministry of Education?
  4. `hard.why_rag_for_btec` score=0.589 mode=weak intent_vs_spoken=0.463 margin=-0.139 — Why did you choose RAG for the question generator?
  5. `hard.mixed_language_query` score=0.584 mode=weak intent_vs_spoken=0.450 margin=-0.144 — The user asks in English about an Arabic regulation. What does retrieval do?
- **raw match:** `{'id': 'tech.rag_what', 'score': 0.728, 'mode': 'weak'}`
- **selected (after abstain/recovery):** id=`tech.rag_what` score=0.728 mode=`weak` | e2e intent_score=0.208 intent_ok=False
- **selected/abstain reason:** risk:reason=ok | realistic_recovery:recovered:margin=0.104
- **fail gate:** intent_score_gate: semantic(bankQ,spoken)=0.208 < 0.70 (paraphrase vs short bank question)
- **top-5 best by intent_vs_spoken:** `hard.why_rag_for_btec` (0.463)
- **e2e notes:** e2e_loopback; realistic_recovery:recovered:margin=0.104

## Case 2 — E2E `FAIL` | HC=False

- **transcript:** Why do you use embeddings and cosine similarity instead of an LLM in the similarity checker?
- **expected:** Why do you use embeddings and cosine similarity instead of an LLM in the similarity checker?
- **detector:** `single` conf=0.92 signals=['no_multi_request_signal']
- **top-5 intents:**
  1. `proj.similarity.stack` score=0.820 mode=strong intent_vs_spoken=0.494 margin=0.126 — Does the similarity checker use LLM, RAG, agentic AI, LangChain, or ChromaDB?
  2. `proj.similarity.describe` score=0.694 mode=weak intent_vs_spoken=0.421 margin=-0.126 — Tell me about the BTEC Assignment Similarity Checker
  3. `hard.which_rag_layer_failed` score=0.630 mode=weak intent_vs_spoken=0.466 margin=-0.190 — How do you know whether the problem is the embedding model, retrieval, prompt, or LLM?
  4. `tech.cosine_semantic_search` score=0.630 mode=weak intent_vs_spoken=0.596 margin=-0.190 — What is cosine similarity and how does semantic search work?
  5. `proj.similarity.is_rag` score=0.627 mode=weak intent_vs_spoken=0.528 margin=-0.193 — Is the similarity checker a RAG system?
- **raw match:** `{'id': 'proj.similarity.stack', 'score': 0.82, 'mode': 'weak'}`
- **selected (after abstain/recovery):** id=`proj.similarity.stack` score=0.82 mode=`weak` | e2e intent_score=0.494 intent_ok=False
- **selected/abstain reason:** risk:reason=ok | realistic_recovery:recovered:margin=0.126
- **fail gate:** intent_score_gate: semantic(bankQ,spoken)=0.494 < 0.70 (paraphrase vs short bank question)
- **top-5 best by intent_vs_spoken:** `tech.cosine_semantic_search` (0.596)
- **e2e notes:** e2e_loopback; realistic_recovery:recovered:margin=0.126

## Case 3 — E2E `FAIL` | HC=False

- **transcript:** How does your BTEC workflow validate a generated question before a teacher can approve it?
- **expected:** How does your BTEC workflow validate a generated question before a teacher can approve it?
- **detector:** `single` conf=0.92 signals=['no_multi_request_signal']
- **top-5 intents:**
  1. `hard.teacher_rejects` score=0.598 mode=weak intent_vs_spoken=0.550 margin=0.135 — The teacher rejects the generated question. What happens next in the system?
  2. `moe.what_is_btec` score=0.464 mode=weak intent_vs_spoken=0.198 margin=-0.135 — What is BTEC?
  3. `hard.streaming_vs_validate` score=0.430 mode=weak intent_vs_spoken=0.443 margin=-0.169 — Do you stream the LLM tokens to the user in a government RAG app?
  4. `hard.hitl_where` score=0.418 mode=weak intent_vs_spoken=0.366 margin=-0.180 — Where exactly do you put the human in the loop?
  5. `cv.pydantic` score=0.397 mode=weak intent_vs_spoken=0.342 margin=-0.202 — Have you used Pydantic?
- **raw match:** `{'id': 'hard.teacher_rejects', 'score': 0.598, 'mode': 'weak'}`
- **selected (after abstain/recovery):** id=`hard.teacher_rejects` score=0.598 mode=`weak` | e2e intent_score=0.55 intent_ok=False
- **selected/abstain reason:** risk:reason=ok | realistic_recovery:recovered:margin=0.135
- **fail gate:** intent_score_gate: semantic(bankQ,spoken)=0.550 < 0.70 (paraphrase vs short bank question)
- **top-5 best by intent_vs_spoken:** `hard.teacher_rejects` (0.550)
- **e2e notes:** e2e_loopback; realistic_recovery:recovered:margin=0.135

## Case 4 — E2E `FAIL` | HC=False

- **transcript:** Why is human approval important when an AI system can already generate a good answer?
- **expected:** Why is human approval important when an AI system can already generate a good answer?
- **detector:** `single` conf=0.92 signals=['no_multi_request_signal']
- **top-5 intents:**
  1. `hard.hitl_where` score=0.506 mode=weak intent_vs_spoken=0.422 margin=0.100 — Where exactly do you put the human in the loop?
  2. `tech.wer` score=0.406 mode=weak intent_vs_spoken=0.349 margin=-0.100 — What is word error rate?
  3. `gen.why_ai_field` score=0.400 mode=weak intent_vs_spoken=0.403 margin=-0.106 — Why did you choose AI as a career?
  4. `tech.transcription_quality` score=0.389 mode=weak intent_vs_spoken=0.468 margin=-0.117 — How do you know the transcription system is good enough?
  5. `hard.why_agent_not_rag` score=0.361 mode=weak intent_vs_spoken=0.458 margin=-0.145 — Why do you need an agent here? Why not normal RAG?
- **raw match:** `None`
- **selected (after abstain/recovery):** id=`hard.hitl_where` score=0.506 mode=`weak` | e2e intent_score=0.422 intent_ok=False
- **selected/abstain reason:** risk:reason=no_match | realistic_recovery:recovered:margin=0.100
- **fail gate:** intent_score_gate: semantic(bankQ,spoken)=0.422 < 0.70 (paraphrase vs short bank question)
- **top-5 best by intent_vs_spoken:** `tech.transcription_quality` (0.468)
- **e2e notes:** e2e_loopback; realistic_recovery:recovered:margin=0.100

## Case 5 — E2E `FAIL` | HC=False

- **transcript:** How would LangGraph help if your Pythonagentic workflow became more complex?
- **expected:** How would LangGraph help if your Python agentic workflow became more complex?
- **detector:** `single` conf=0.92 signals=['no_multi_request_signal']
- **top-5 intents:**
  1. `tech.what_is_langgraph` score=0.735 mode=strong intent_vs_spoken=0.319 margin=0.006 — What is LangGraph?
  2. `hard.langgraph_vs_n8n_vs_python` score=0.729 mode=strong intent_vs_spoken=0.548 margin=-0.006 — Would you use LangGraph, n8n, or plain Python for this workflow? Why?
  3. `cv.langgraph` score=0.683 mode=weak intent_vs_spoken=0.380 margin=-0.052 — Have you used LangGraph?
  4. `tech.langgraph_vs_langchain` score=0.680 mode=weak intent_vs_spoken=0.409 margin=-0.055 — What is the difference between LangChain and LangGraph?
  5. `hard.plain_python_still_agentic` score=0.632 mode=weak intent_vs_spoken=0.518 margin=-0.103 — If you did not use LangGraph, was your BTEC flow still agentic?
- **raw match:** `{'id': 'tech.what_is_langgraph', 'score': 0.735, 'mode': 'weak'}`
- **selected (after abstain/recovery):** id=`tech.what_is_langgraph` score=0.735 mode=`weak` | e2e intent_score=0.316 intent_ok=False
- **selected/abstain reason:** risk:needs_stt_retry=True,reason=ambiguous_top2 | realistic_recovery:ambiguous_abstain:margin=0.006
- **fail gate:** intent_score_gate: semantic(bankQ,spoken)=0.319 < 0.70 (paraphrase vs short bank question)
- **top-5 best by intent_vs_spoken:** `hard.langgraph_vs_n8n_vs_python` (0.548)
- **e2e notes:** e2e_loopback; realistic_recovery:ambiguous_abstain:margin=0.006

## Case 6 — E2E `FAIL` | HC=True

- **transcript:** What is the difference between changing model knowledge with RAG and changing behavior with fine tuning?
- **expected:** What is the difference between changing model knowledge with RAG and changing behavior with fine tuning?
- **detector:** `uncertain` conf=0.58 signals=['compare_contrast']
- **top-5 intents:**
  1. `tech.rag_vs_finetuning` score=1.020 mode=strong intent_vs_spoken=0.470 margin=0.342 — Our regulations change every year. Should we fine-tune the model or use RAG?
  2. `hard.not_finetune_first` score=0.678 mode=weak intent_vs_spoken=0.450 margin=-0.342 — Why not fine-tune a model on all our documents instead of Agentic RAG?
  3. `cv.fine_tuning` score=0.633 mode=weak intent_vs_spoken=0.345 margin=-0.387 — Have you done fine-tuning?
  4. `tech.rag_what` score=0.621 mode=weak intent_vs_spoken=0.737 margin=-0.399 — What is RAG?
  5. `proj.similarity.is_rag` score=0.617 mode=weak intent_vs_spoken=0.372 margin=-0.403 — Is the similarity checker a RAG system?
- **raw match:** `{'id': 'tech.rag_vs_finetuning', 'score': 1.02, 'mode': 'weak'}`
- **selected (after abstain/recovery):** id=`tech.rag_vs_finetuning` score=1.02 mode=`strong` | e2e intent_score=0.47 intent_ok=False
- **selected/abstain reason:** risk:reason=ok | realistic_recovery:recovered:margin=0.342
- **fail gate:** intent_score_gate: semantic(bankQ,spoken)=0.470 < 0.70 (paraphrase vs short bank question)
- **top-5 best by intent_vs_spoken:** `tech.rag_what` (0.737)
- **e2e notes:** e2e_loopback; realistic_recovery:recovered:margin=0.342; compound_skipped:uncertain

## Case 7 — E2E `PASS` | HC=False

- **transcript:** How do metadata filters stop one school from retrieving documents that belong to another school?
- **expected:** How do metadata filters stop one school from retrieving documents that belong to another school?
- **detector:** `single` conf=0.92 signals=['no_multi_request_signal']
- **top-5 intents:**
  1. `hard.tenant_isolation` score=0.580 mode=weak intent_vs_spoken=0.747 margin=0.174 — How do you stop school A from retrieving school B's assignments?
  2. `cv.chromadb` score=0.406 mode=weak intent_vs_spoken=0.185 margin=-0.174 — Have you used ChromaDB?
  3. `hard.agent_stop_tools` score=0.358 mode=weak intent_vs_spoken=0.388 margin=-0.222 — When should an agent stop using tools?
  4. `gen.leadership` score=0.333 mode=weak intent_vs_spoken=0.323 margin=-0.247 — Do you have leadership experience?
  5. `tech.metadata_filtering` score=0.324 mode=weak intent_vs_spoken=0.385 margin=-0.256 — What is metadata filtering in RAG?
- **raw match:** `{'id': 'hard.tenant_isolation', 'score': 0.58, 'mode': 'weak'}`
- **selected (after abstain/recovery):** id=`hard.tenant_isolation` score=0.58 mode=`weak` | e2e intent_score=0.747 intent_ok=True
- **selected/abstain reason:** risk:reason=ok | realistic_recovery:recovered:margin=0.174
- **fail gate:** would_pass_current_gate
- **top-5 best by intent_vs_spoken:** `hard.tenant_isolation` (0.747)
- **e2e notes:** e2e_loopback; realistic_recovery:recovered:margin=0.174

## Case 8 — E2E `FAIL` | HC=False

- **transcript:** What should the system do when the retrieved context does not contain enough information?
- **expected:** What should the system do when the retrieved context does not contain enough information?
- **detector:** `single` conf=0.92 signals=['no_multi_request_signal']
- **top-5 intents:**
  1. `tech.no_wrong_info_finance` score=0.433 mode=weak intent_vs_spoken=0.651 margin=0.045 — How do you make sure the system does not give wrong information in a financial context?
  2. `hard.empty_retrieval` score=0.388 mode=weak intent_vs_spoken=0.638 margin=-0.045 — What should the system do when retrieval returns nothing useful?
  3. `tech.good_enough_to_launch` score=0.363 mode=weak intent_vs_spoken=0.556 margin=-0.070 — How do you know the system is good enough to launch?
  4. `hard.context_stuffing` score=0.355 mode=weak intent_vs_spoken=0.458 margin=-0.078 — What if you stuff twenty chunks into the prompt to be safe?
  5. `tech.pii_redaction` score=0.335 mode=weak intent_vs_spoken=0.380 margin=-0.098 — How do you handle personal data in prompts and logs?
- **raw match:** `None`
- **selected (after abstain/recovery):** id=`tech.no_wrong_info_finance` score=0.433 mode=`weak` | e2e intent_score=0.651 intent_ok=False
- **selected/abstain reason:** risk:reason=no_match | realistic_recovery:ambiguous_abstain:margin=0.045
- **fail gate:** intent_score_gate: semantic(bankQ,spoken)=0.651 < 0.70 (paraphrase vs short bank question)
- **top-5 best by intent_vs_spoken:** `tech.no_wrong_info_finance` (0.651)
- **e2e notes:** e2e_loopback; realistic_recovery:ambiguous_abstain:margin=0.045
