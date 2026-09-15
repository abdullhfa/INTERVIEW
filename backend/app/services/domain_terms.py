"""
Domain vocabulary for the live interview pipeline.

Two jobs:
1. `canonicalize_display()` — fix how STT writes domain terms so the transcript
   shown to the user reads correctly ("Lang Chain" -> "LangChain").
2. `normalize_for_matching()` — collapse every spelling/mishearing variant of a
   term into one lowercase token so question-bank matching is tolerant to
   accented English and ASR noise ("b tech", "bee tech", "btech" -> "btec").

Both are built from the same table so they never drift apart.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# canonical display form -> variants (case-insensitive regexes, word-bounded)
_TERMS: dict[str, tuple[str, ...]] = {
    "BTEC": (r"b[\s\-]?tec[hk]?", r"bee[\s\-]?tec[hk]?", r"be[\s\-]?tec[hk]", r"b\s?tech"),
    "KNET": (r"k[\s\-]?net", r"kay[\s\-]?net", r"knet"),
    "Al Najat": (r"al[\s\-]?najat", r"an[\s\-]?najat", r"al[\s\-]?nagat", r"el[\s\-]?najat", r"najat"),
    "LangChain": (r"lang[\s\-]?chain", r"lan[\s\-]?chain", r"long[\s\-]?chain", r"length[\s\-]?chain"),
    "LangGraph": (r"lang[\s\-]?graph", r"lan[\s\-]?graph", r"langraph", r"long[\s\-]?graph", r"lang[\s\-]?raph"),
    "RAG": (r"r[\s.]?a[\s.]?g", r"rag", r"wrag", r"rags", r"drag", r"rack", r"ragg"),
    "LLM": (r"l[\s.]?l[\s.]?m\.?s?", r"llms?", r"ell?\s?ell?\s?em"),
    "Whisper": (r"whisper", r"wisper", r"whispers"),
    "Pydantic": (r"pydantic", r"pie[\s\-]?dantic", r"py[\s\-]?dantic", r"pi[\s\-]?dantic"),
    "FastAPI": (r"fast[\s\-]?api", r"fastapi", r"fast\s?a\s?p\s?i"),
    "Scikit-learn": (r"scikit[\s\-]?learn", r"sci[\s\-]?kit[\s\-]?learn", r"sky[\s\-]?kit[\s\-]?learn", r"sk[\s\-]?learn", r"sklearn", r"psychic[\s\-]?learn"),
    "Pandas": (r"pandas", r"panda's", r"pandus"),
    "NumPy": (r"num[\s\-]?py", r"numpy", r"nump[iy]e?"),
    "PyTorch": (r"py[\s\-]?torch", r"pytorch", r"pie[\s\-]?torch"),
    "TensorFlow": (r"tensor[\s\-]?flow", r"tensorflow"),
    "Hugging Face": (r"hugging[\s\-]?face", r"huggingface", r"hugging\s?phase"),
    "ChromaDB": (r"chroma[\s\-]?db", r"chromadb", r"chroma[\s\-]?d\s?b", r"chroma database", r"chroma"),
    "Qdrant": (r"qdrant", r"q[\s\-]?drant", r"quadrant", r"cue[\s\-]?drant"),
    "pgvector": (r"pg[\s\-]?vector", r"pgvector", r"p\s?g\s?vector", r"postgres vector"),
    "Pinecone": (r"pine[\s\-]?cone", r"pinecone"),
    "Milvus": (r"milvus", r"mill?\s?vus"),
    "vLLM": (r"v[\s\-]?llm", r"vllm", r"vee[\s\-]?llm", r"v\s?l\s?l\s?m"),
    "Ollama": (r"ollama", r"o[\s\-]?llama", r"olama"),
    "OpenAI": (r"open[\s\-]?ai", r"openai", r"open\s?a\s?i"),
    "GPT": (r"g[\s.]?p[\s.]?t", r"gpt", r"chat\s?gpt", r"chatgpt"),
    "MCP": (r"m[\s.]?c[\s.]?p", r"mcp"),
    "PMP": (r"p[\s.]?m[\s.]?p", r"pmp"),
    "PRINCE2": (r"prince[\s\-]?2", r"prince[\s\-]?two", r"prince2"),
    "CCNP": (r"c[\s.]?c[\s.]?n[\s.]?p", r"ccnp", r"cisco ccnp"),
    "n8n": (r"n[\s\-]?8[\s\-]?n", r"n8n", r"n[\s\-]?eight[\s\-]?n"),
    "TF-IDF": (r"tf[\s\-]?idf", r"tfidf", r"t\s?f\s?i\s?d\s?f"),
    "RAGAS": (r"ragas", r"rag[\s\-]?as", r"ragass"),
    "Redis": (r"redis", r"reddis", r"red\s?is"),
    "Docker": (r"docker", r"dockers"),
    "Kubernetes": (r"kubernetes", r"kubernetis", r"k8s", r"kube"),
    "CUDA": (r"cuda", r"kuda", r"cooda"),
    "GPU": (r"g[\s.]?p[\s.]?u\.?s?", r"gpus?"),
    "SQL": (r"s[\s.]?q[\s.]?l", r"sql", r"sequel"),
    "API": (r"a[\s.]?p[\s.]?i\.?s?", r"apis?"),
    "JSON": (r"json", r"jason", r"j\s?son"),
    "NLP": (r"n[\s.]?l[\s.]?p", r"nlp"),
    "STT": (r"s[\s.]?t[\s.]?t",),
    "TTS": (r"t[\s.]?t[\s.]?s",),
    "VAD": (r"v[\s.]?a[\s.]?d",),
    "WER": (r"w[\s.]?e[\s.]?r",),
    "VRAM": (r"v[\s\-]?ram", r"vram"),
    "LoRA": (r"lo[\s\-]?ra", r"lora", r"laura"),
    "GraphRAG": (r"graph[\s\-]?rag", r"graphrag"),
    "SageMaker": (r"sage[\s\-]?maker", r"sagemaker"),
    "Vertex AI": (r"vertex[\s\-]?ai", r"vertex"),
    "Core42": (r"core[\s\-]?42", r"core[\s\-]?forty[\s\-]?two", r"core42"),
    "G42": (r"g[\s\-]?42", r"g[\s\-]?forty[\s\-]?two"),
    "ReAct": (r"re[\s\-]?act", r"react"),
    "Semantic Kernel": (r"semantic[\s\-]?kernel",),
    "LlamaIndex": (r"llama[\s\-]?index", r"lama[\s\-]?index"),
    "CV": (r"c\.?v\.?", r"resume", r"résumé", r"curriculum vitae"),
    "fine-tuning": (r"fine[\s\-]?tuning", r"fine[\s\-]?tune[ds]?", r"finetuning", r"finetune[ds]?"),
    "on-premise": (r"on[\s\-]?prem(?:ise|ises|s)?", r"on[\s\-]?premise[s]?"),
    "embeddings": (r"embeddings?", r"imbeddings?", r"embed?ings?"),
    "vector database": (r"vector[\s\-]?d\s?b", r"vector[\s\-]?database[s]?", r"vector[\s\-]?store[s]?", r"vector[\s\-]?db[s]?"),
    "Agentic AI": (r"agentic[\s\-]?ai", r"agentic", r"agent\s?tick"),
    "Ministry of Education": (r"ministry of education", r"education ministry", r"moe"),
    "Ministry of Finance": (r"ministry of finance", r"finance ministry", r"mof"),
    "Kuwait": (r"kuwait", r"kuwai", r"quwait"),
    "Jordan": (r"jordan", r"jordon"),
}

# Phrase variants that must collapse for matching but must never be rewritten
# in the on-screen transcript.
_MATCH_ONLY: dict[str, tuple[str, ...]] = {
    "LLM": (r"large language models?",),
    "MCP": (r"model context protocol",),
    "TF-IDF": (r"term frequency inverse document frequency",),
    "STT": (r"speech to text", r"speech recognition"),
    "TTS": (r"text to speech",),
    "VAD": (r"voice activity detection",),
    "WER": (r"word error rate",),
    "RAG": (r"retrieval[\s\-]?augmented generation",),
    "GPU": (r"graphics? cards?",),
}

# For matching, every term collapses to this lowercase token.
_MATCH_TOKEN: dict[str, str] = {
    "Al Najat": "najat",
    "Hugging Face": "huggingface",
    "Scikit-learn": "scikit learn",
    "TF-IDF": "tf idf",
    "Vertex AI": "vertex",
    "Semantic Kernel": "semantic kernel",
    "CV": "cv",
    "fine-tuning": "fine tuning",
    "on-premise": "on premise",
    "embeddings": "embedding",
    "vector database": "vector database",
    "Agentic AI": "agentic",
    "Ministry of Education": "ministry of education",
    "Ministry of Finance": "ministry of finance",
}

# Ambiguous short variants are only rewritten when the sentence is clearly technical.
_CONTEXT_ONLY_DISPLAY = {"RAG": {"rag", "wrag", "rags", "drag", "rack", "ragg"}, "ReAct": {"react"}, "Qdrant": {"quadrant"}, "GPT": set()}

_TECH_CONTEXT_RE = re.compile(
    r"\b(model|models|pipeline|retriev\w*|embedding\w*|vector\w*|llm\w*|prompt\w*|"
    r"agent\w*|fine|tun\w*|langchain|langgraph|chunk\w*|document\w*|knowledge|"
    r"generat\w*|search|database|system|architecture|hallucinat\w*|api|deploy\w*|"
    r"whisper|speech|python|pydantic|fastapi|btec|project\w*)\b",
    re.IGNORECASE,
)


def _compile(variants: tuple[str, ...]) -> re.Pattern[str]:
    body = "|".join(f"(?:{v})" for v in variants)
    return re.compile(rf"(?<![\w-])(?:{body})(?![\w-])", re.IGNORECASE)


_DISPLAY_RULES: list[tuple[str, re.Pattern[str]]] = [
    (canon, _compile(variants)) for canon, variants in _TERMS.items()
]
_MATCH_RULES: list[tuple[str, re.Pattern[str]]] = [
    (canon, _compile(tuple(variants) + _MATCH_ONLY.get(canon, ())))
    for canon, variants in _TERMS.items()
]

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def canonicalize_display(text: str) -> str:
    """Rewrite domain terms to their canonical spelling for on-screen transcripts."""
    cleaned = _WS_RE.sub(" ", (text or "").strip())
    if not cleaned:
        return ""
    technical = bool(_TECH_CONTEXT_RE.search(cleaned))
    out = cleaned
    for canon, pattern in _DISPLAY_RULES:
        if canon in ("CV", "embeddings", "vector database", "fine-tuning", "on-premise", "ReAct",
                     "Agentic AI", "Ministry of Education", "Ministry of Finance", "Kuwait", "Jordan"):
            # Keep natural-language phrases as spoken; only fix obvious brand names.
            continue
        gated = _CONTEXT_ONLY_DISPLAY.get(canon)
        if gated is not None and not technical:
            continue

        def _sub(match: re.Match[str], _canon: str = canon, _gated=gated) -> str:
            token = match.group(0)
            if _gated and token.casefold() in _gated and not technical:
                return token
            return _canon

        out = pattern.sub(_sub, out)
    return out


@lru_cache(maxsize=65536)
def _normalize_for_matching_uncached(text: str) -> str:
    """Lowercase, strip punctuation, collapse every term variant to one token."""
    folded = unicodedata.normalize("NFKC", text or "").casefold()
    folded = folded.replace("’", "'").replace("`", "'")
    folded = re.sub(r"\b(\w+)'s\b", r"\1 s", folded)  # "that's" -> "that s"
    folded = re.sub(r"\bwhat s\b", "what is", folded)
    folded = re.sub(r"\bthat s\b", "that is", folded)
    folded = re.sub(r"\bit s\b", "it is", folded)
    for canon, pattern in _MATCH_RULES:
        token = _MATCH_TOKEN.get(canon, canon.casefold())
        folded = pattern.sub(f" {token} ", folded)
    folded = _PUNCT_RE.sub(" ", folded)
    return _WS_RE.sub(" ", folded).strip()


def normalize_for_matching(text: str) -> str:
    """
    Memoized wrapper around the ~80-regex normalizer.

    Pure function of `text`, so caching returns byte-identical output. Static
    bank/profile strings are normalized thousands of times per request on the
    recovery path (PERF: `_lexical_expand_candidates`, `_alias_lex`,
    `intent_agreement`); the cache removes that repeated regex work without
    changing any score.
    """
    return _normalize_for_matching_uncached(text or "")


def normalize_cache_info():  # pragma: no cover - diagnostics only
    return _normalize_for_matching_uncached.cache_info()


def clear_normalize_cache() -> None:
    _normalize_for_matching_uncached.cache_clear()


# Vocabulary handed to Whisper as `initial_prompt` so decoding is biased towards
# these spellings when the acoustics are ambiguous (accented English).
WHISPER_DOMAIN_PROMPT = (
    "Senior AI engineer job interview in English. "
    "Terms: LLM, RAG, retrieval-augmented generation, embeddings, vector database, "
    "ChromaDB, Qdrant, pgvector, LangChain, LangGraph, agentic AI, agents, MCP, "
    "fine-tuning, LoRA, hallucination, guardrails, faithfulness, RAGAS, Pydantic, "
    "FastAPI, Python, SQL, Scikit-learn, Pandas, NumPy, PyTorch, Hugging Face, TF-IDF, "
    "Whisper, speech recognition, Docker, Kubernetes, Redis, vLLM, Ollama, GPU, CUDA, "
    "on-premise, sovereign cloud, Core42, BTEC, Ministry of Education, Al Najat, KNET, "
    "Kuwait, Jordan, PMP, PRINCE2, CCNP. "
    "Tell me about yourself. What is RAG? Have you used LangChain? "
    "Tell me about the BTEC assignment similarity checker."
)

# Shorter vocabulary for second-pass only — guides acoustics, not question choice.
WHISPER_TECH_SECOND_PASS_PROMPT = (
    "Short spoken interview question in English. "
    "Possible terms if heard: RAG, Agentic AI, LangChain, LangGraph, Guardrails, "
    "Embeddings, ChromaDB, n8n, LLM, retrieval, agentic, agent orchestrator, "
    "fine-tune, fine-tuning, hallucination, looping forever."
)
