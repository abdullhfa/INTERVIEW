# Latency-cut — Simple STT trace (latest short_length)

**Suite:** `short_length` n=8 · CUDA `distil-large-v3` / `int8_float16`  
**Verdict:** median post **1379 ms** · Intent **8/8** · HC **0** · Whisper calls **all 1**

| # | calls | pass1_ms | pass2 | trigger | strong_agrees | first_pass_text | first_intent | conf | final_text | whisper_ms | post_ms | fast |
|---|------:|---------:|------:|---------|---------------|-----------------|--------------|-----:|------------|-----------:|--------:|:----:|
| 1 | 1 | 1187 | — | — | Y | What is RAG? | tech.rag_what | 1.20 | What is RAG? | 1188 | 1327 | Y |
| 2 | 1 | 1267 | — | — | Y | What are guardrails? | tech.guardrails_what | 1.26 | What are guardrails? | 1268 | 1360 | Y |
| 3 | 1 | 1170 | — | — | N | What is a agentic AI? | tech.agentic_what | 1.24 | What is a agentic AI? | 1172 | 1324 | Y |
| 4 | 1 | 1259 | — | — | N | Why embeddings? | tech.tfidf_vs_embeddings | 0.94 | Why embeddings? | 1260 | 1407 | Y |
| 5 | 1 | 1290 | — | — | N | What is LangGraph? | tech.what_is_langgraph | 1.20 | What is LangGraph? | 1294 | 1379 | Y |
| 6 | 1 | 1277 | — | — | N | Why recall? | proj.early_warning.metric | 0.94 | Why recall? | 1278 | 1368 | Y |
| 7 | 1 | 1133 | — | — | N | What if retrieval fails? | — | 0 | What if retrieval fails? | 1134 | 2233 | N |
| 8 | 1 | 1203 | — | — | N | Who approves the result? | — | 0 | Who approves the result? | 1205 | 3715 | N |

**Notes**

- No second/third Whisper on any simple clip this run.  
- Fast path = `strong_agrees` or simple high-lexical (≥0.90) skip of semantic/realistic.  
- Remaining latency tail is **semantic recovery** on clips 7–8, not multi-pass STT.
