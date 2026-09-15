# Holdout v3 — voice spot-check

Created: 2026-09-13T21:44:44.425494+00:00

Probe sentences only. No v3 clip was synthesized or transcribed, so the
holdout stays unseen.

| voice set / profile | kind | clips | terms kept | rate | missed |
|---|---|---|---|---|---|
| multilingual/en-IN | native | 12 | 27/36 | 0.75 | ChromaDB, FastAPI, LangGraph, Pydantic, TF-IDF, cosine |
| multilingual/proxy-ar-AE | synthetic proxy | 12 | 32/36 | 0.889 | LangGraph, Pydantic, TF-IDF |
| multilingual/proxy-ar-EG | synthetic proxy | 12 | 30/36 | 0.833 | ChromaDB, LoRA, RAG, TF-IDF |
| multilingual/proxy-ar-JO | synthetic proxy | 12 | 31/36 | 0.861 | Pydantic, TF-IDF, embeddings, guardrails |

## Reading this

- A low rate for a profile means the TTS mangles the vocabulary, so a v3
  failure on that profile would not be the system's fault. Switch voice
  set (`--voices multilingual`) or drop the profile BEFORE synthesis.
- `proxy-ar-*` are Arabic-locale voices reading English. They are labelled
  synthetic proxies everywhere and must never be reported as real dialects.

## Transcripts

- `multilingual/en-IN/clean` (en-IN-NeerjaNeural): **3/3** — The RAG layer and the embeddings index both sit behind the same guardrails.
- `multilingual/en-IN/poor` (en-IN-NeerjaNeural): **3/3** — The RAG layer and the embeddings index both sit behind the same guardrails.
- `multilingual/en-IN/clean` (en-IN-PrabhatNeural): **1/3** — Landgraph checkpoints, Chromadibi collections and Whisper transcripts are logged together.
- `multilingual/en-IN/poor` (en-IN-PrabhatNeural): **2/3** — LangGraph checkpoints, chromaD collections and Whisper transcripts are logged together.
- `multilingual/en-IN/clean` (en-IN-NeerjaNeural): **3/3** — Agentic orchestration, cosine similarity and re-ranking all appear in this sentence.
- `multilingual/en-IN/poor` (en-IN-NeerjaNeural): **2/3** — Agentic orchestration, cosign similarity and re-ranking all appear in this sentence.
- `multilingual/en-IN/clean` (en-IN-PrabhatNeural): **2/3** — Pyentic validates the FastAPI payload before the model sees any token. Pytentic validates the FastAPI payload before the model sees any token.
- `multilingual/en-IN/poor` (en-IN-PrabhatNeural): **1/3** — PyTenic validates the past API payload before the model sees any token.
- `multilingual/en-IN/clean` (en-IN-NeerjaNeural): **3/3** — Fine tuning, LoRA adapters and hallucination checks belong to different layers.
- `multilingual/en-IN/poor` (en-IN-NeerjaNeural): **3/3** — Fine tuning, LoRA adapters and hallucination checks belong to different layers.
- `multilingual/en-IN/clean` (en-IN-PrabhatNeural): **2/3** — T-F-F, hybrid search and metadata filtering are three distinct retrieval tricks.
- `multilingual/en-IN/poor` (en-IN-PrabhatNeural): **2/3** — CFIDF, hybrid search and metadata filtering are three distinct retrieval tricks.
- `multilingual/proxy-ar-JO/clean` (en-US-AvaMultilingualNeural): **3/3** — The RAG layer and the embeddings index both sit behind the same guardrails.
- `multilingual/proxy-ar-JO/poor` (en-US-AvaMultilingualNeural): **1/3** — The RAG layer and the beddings index both sit behind the same guardrail.
- `multilingual/proxy-ar-JO/clean` (en-US-AndrewMultilingualNeural): **3/3** — LangGraph checkpoints, ChromaDB collections, and Whisper transcripts are logged together.
- `multilingual/proxy-ar-JO/poor` (en-US-AndrewMultilingualNeural): **3/3** — LangGraph checkpoints, ChromaDB collections, and Whisper transcripts are logged together.
- `multilingual/proxy-ar-JO/clean` (en-US-AvaMultilingualNeural): **3/3** — agentic orchestration, cosine similarity, and re-ranking all appear in this sentence.
- `multilingual/proxy-ar-JO/poor` (en-US-AvaMultilingualNeural): **3/3** — agentic orchestration, cosine similarity, and re-ranking all appear in this center.
- `multilingual/proxy-ar-JO/clean` (en-US-AndrewMultilingualNeural): **3/3** — Pydantic validates the FastAPI payload before the model sees any token. Pydantic validates the FastAPI payload before the model sees any token.
- `multilingual/proxy-ar-JO/poor` (en-US-AndrewMultilingualNeural): **2/3** — Hydantic validates the FastAPI payload before the model sees any token.
- `multilingual/proxy-ar-JO/clean` (en-US-AvaMultilingualNeural): **3/3** — Fine-tuning, LoRA adapters, and hallucination checks belong to different layers.
- `multilingual/proxy-ar-JO/poor` (en-US-AvaMultilingualNeural): **3/3** — Fine-tuning, LoRA adapters, and hallucination checks belong to different layers.
- `multilingual/proxy-ar-JO/clean` (en-US-AndrewMultilingualNeural): **2/3** — TIF, hybrid search and metadata filtering are three distinct retrieval tricks.
- `multilingual/proxy-ar-JO/poor` (en-US-AndrewMultilingualNeural): **2/3** — TideF, hybrid search and metadata filtering are three distinct retrieval tricks.
- `multilingual/proxy-ar-EG/clean` (en-US-EmmaMultilingualNeural): **3/3** — The RAG layer and the embeddings index both sit behind the same guardrails.
- `multilingual/proxy-ar-EG/poor` (en-US-EmmaMultilingualNeural): **2/3** — The Argy layer and the embeddings index both sit behind the same guardrails.
- `multilingual/proxy-ar-EG/clean` (en-US-BrianMultilingualNeural): **2/3** — LangGraph checkpoints, chromaD collections, and Whisper transcripts are logged together.
- `multilingual/proxy-ar-EG/poor` (en-US-BrianMultilingualNeural): **2/3** — LangGraph checkpoints, chromaD collections, and Whisper transcripts are logged together.
- `multilingual/proxy-ar-EG/clean` (en-US-EmmaMultilingualNeural): **3/3** — Agentic orchestration, cosine similarity, and re-ranking all appear in this sentence.
- `multilingual/proxy-ar-EG/poor` (en-US-EmmaMultilingualNeural): **3/3** — Agentic orchestration, cosine similarity in re-ranking all appear in this sentence.
- `multilingual/proxy-ar-EG/clean` (en-US-BrianMultilingualNeural): **3/3** — Pydantic validates the FastAPI payload before the model sees any token. PIDDantic validates the FastAPI payload before the model sees any token.
- `multilingual/proxy-ar-EG/poor` (en-US-BrianMultilingualNeural): **3/3** — Pydantic validates the FastAPI payload before the model sees any token.
- `multilingual/proxy-ar-EG/clean` (en-US-EmmaMultilingualNeural): **2/3** — Fine-tuning, lore adapters, and hallucination checks belong to different layers.
- `multilingual/proxy-ar-EG/poor` (en-US-EmmaMultilingualNeural): **2/3** — Fine-tuning, lore adapters, and hallucination checks belong to different layers.
- `multilingual/proxy-ar-EG/clean` (en-US-BrianMultilingualNeural): **2/3** — T-F, hybrid search, and metadata filtering are three distinct retrieval tricks.
- `multilingual/proxy-ar-EG/poor` (en-US-BrianMultilingualNeural): **3/3** — TF-IDF, hybrid search, and metadata filtering are three distinct retrieval tricks.
- `multilingual/proxy-ar-AE/clean` (de-DE-SeraphinaMultilingualNeural): **3/3** — The RAG layer and the embeddings index both sit behind the same guardrails.
- `multilingual/proxy-ar-AE/poor` (de-DE-SeraphinaMultilingualNeural): **3/3** — The RAG layer and the embeddings index both sit behind the same guardrails.
- `multilingual/proxy-ar-AE/clean` (en-US-AndrewMultilingualNeural): **3/3** — LangGraph checkpoints, ChromaDB collections, and Whisper transcripts are logged together.
- `multilingual/proxy-ar-AE/poor` (en-US-AndrewMultilingualNeural): **2/3** — Landgraph checkpoints, ChromaDB collections, and Whisper transcripts are logged together.
- `multilingual/proxy-ar-AE/clean` (de-DE-SeraphinaMultilingualNeural): **3/3** — Agentic orchestration, cosine similarity, and re-ranking all appear in this sentence.
- `multilingual/proxy-ar-AE/poor` (de-DE-SeraphinaMultilingualNeural): **3/3** — Agentic orchestration, cosine similarity, and re-ranking all appear in this sentence.
- `multilingual/proxy-ar-AE/clean` (en-US-AndrewMultilingualNeural): **3/3** — Pydantic validates the FastAPI payload before the model sees any token. Pydantic validates the FastAPI payload before the model sees any token.
- `multilingual/proxy-ar-AE/poor` (en-US-AndrewMultilingualNeural): **2/3** — Pythantic validates the FastAPI payload before the model sees any token.
- `multilingual/proxy-ar-AE/clean` (de-DE-SeraphinaMultilingualNeural): **3/3** — Fine-tuning, LoRA adapters, and hallucination checks belong to different layers.
- `multilingual/proxy-ar-AE/poor` (de-DE-SeraphinaMultilingualNeural): **3/3** — Fine-tuning, LoRA adapters, and hallucination checks belong to different layers.
- `multilingual/proxy-ar-AE/clean` (en-US-AndrewMultilingualNeural): **2/3** — TIF, hybrid search and metadata filtering are three distinct retrieval tricks.
- `multilingual/proxy-ar-AE/poor` (en-US-AndrewMultilingualNeural): **2/3** — Tidifidef, hybrid search and metadata filtering are three distinct retrieval tricks.
