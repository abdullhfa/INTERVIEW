"""
Interview technical lexicon — bank + CV guided.

Canonical terms with spoken forms and known STT confusions.
Used by BANK_GUIDED candidate search; never force-corrects alone.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from functools import lru_cache

_LOCK = threading.Lock()
_CACHE: tuple["LexiconTerm", ...] | None = None

# Seed lexicon (expanded from domain_terms + interview experience).
_SEED: dict[str, dict] = {
    "LLM": {
        "type": "acronym",
        "spoken": ("el el em", "l l m", "ell em"),
        "stt": ("lalam", "ellem", "elem", "ellm", "llum", "lm"),
        "rivals": ("LLaMA", "Llama", "Ollama"),
    },
    "LLaMA": {
        "type": "model",
        "spoken": ("llama", "lama"),
        "stt": ("llama", "lama", "llamma"),
        "rivals": ("LLM",),
    },
    "RAG": {
        "type": "acronym",
        "spoken": ("are a g", "r a g"),
        "stt": ("rag", "ragged", "rack", "drag", "rags", "rabar"),
        "rivals": ("RAGAS",),
    },
    "LangChain": {
        "type": "framework",
        "spoken": ("lang chain",),
        "stt": ("lankan", "land chain", "lang jane", "lang chain"),
        "rivals": ("LangGraph",),
    },
    "LangGraph": {
        "type": "framework",
        "spoken": ("lang graph",),
        "stt": ("land graph", "lang graft", "whyland draft", "langdraft"),
        "rivals": ("LangChain",),
    },
    "embeddings": {
        "type": "concept",
        "spoken": ("embeddings", "embedding"),
        "stt": ("am bedding", "am beddings", "embeding", "imbbedding"),
        "rivals": (),
    },
    "vector store": {
        "type": "concept",
        "spoken": ("vector store",),
        "stt": ("factor store", "victor store", "vector storage"),
        "rivals": (),
    },
    "n8n": {
        "type": "tool",
        "spoken": ("en eight en", "n eight n"),
        "stt": ("n-hash-n", "n h n", "neightn"),
        "rivals": (),
    },
    "ChromaDB": {
        "type": "tool",
        "spoken": ("chroma d b", "chroma"),
        "stt": ("chroma", "chromadb", "zundra", "zandra"),
        "rivals": ("LangGraph",),
    },
    "NLP": {"type": "acronym", "spoken": ("en el pee",), "stt": ("nlp",), "rivals": ()},
    "CNN": {"type": "acronym", "spoken": ("see en en",), "stt": ("cnn",), "rivals": ()},
    "RNN": {"type": "acronym", "spoken": ("are en en",), "stt": ("rnn",), "rivals": ()},
    "LSTM": {"type": "acronym", "spoken": ("el es tee em",), "stt": ("lstm",), "rivals": ()},
    "GPU": {"type": "acronym", "spoken": ("gee pee you",), "stt": ("gpu",), "rivals": ()},
    "STT": {"type": "acronym", "spoken": ("ess tee tee",), "stt": ("stt",), "rivals": ()},
    "TTS": {"type": "acronym", "spoken": ("tee tee ess",), "stt": ("tts",), "rivals": ()},
    "VAD": {"type": "acronym", "spoken": ("vee ay dee",), "stt": ("vad",), "rivals": ()},
    "API": {"type": "acronym", "spoken": ("ay pee eye",), "stt": ("api",), "rivals": ()},
    "SQL": {"type": "acronym", "spoken": ("ess queue el", "sequel"), "stt": ("sql",), "rivals": ()},
    "Agentic AI": {
        "type": "concept",
        "spoken": ("agentic a i",),
        "stt": ("agency ki", "genetic ai", "agentic i"),
        "rivals": (),
    },
}


@dataclass(frozen=True)
class LexiconTerm:
    canonical: str
    type: str
    spoken_forms: tuple[str, ...]
    common_stt_errors: tuple[str, ...]
    rivals: tuple[str, ...]


def clear_lexicon_cache() -> None:
    global _CACHE
    with _LOCK:
        _CACHE = None
    get_lexicon.cache_clear()


@lru_cache(maxsize=1)
def get_lexicon() -> tuple[LexiconTerm, ...]:
    terms: dict[str, LexiconTerm] = {}
    for canon, meta in _SEED.items():
        terms[canon.lower()] = LexiconTerm(
            canonical=canon,
            type=str(meta["type"]),
            spoken_forms=tuple(meta.get("spoken") or ()),
            common_stt_errors=tuple(meta.get("stt") or ()),
            rivals=tuple(meta.get("rivals") or ()),
        )
    try:
        from app.services.domain_terms import _TERMS  # noqa: SLC001

        for canon in _TERMS:
            key = canon.lower()
            if key not in terms:
                terms[key] = LexiconTerm(
                    canonical=canon,
                    type="domain",
                    spoken_forms=(canon.lower(),),
                    common_stt_errors=(),
                    rivals=(),
                )
    except Exception:
        pass
    try:
        from app.services.question_bank import question_bank

        question_bank.load()
        for e in question_bank.entries:
            for kw in e.keywords or ():
                k = (kw or "").strip()
                if not k or len(k) > 40:
                    continue
                key = k.lower()
                if key not in terms and re.fullmatch(r"[A-Za-z][A-Za-z0-9\-]{1,24}", k):
                    terms[key] = LexiconTerm(
                        canonical=k,
                        type="bank_keyword",
                        spoken_forms=(k.lower(),),
                        common_stt_errors=(),
                        rivals=(),
                    )
    except Exception:
        pass
    return tuple(terms.values())


def lexicon_hit(span: str) -> list[tuple[LexiconTerm, float]]:
    """Return lexicon terms whose spoken/stt forms match span, with strength."""
    raw = re.sub(r"[^a-z0-9\s]", " ", (span or "").lower())
    raw = " ".join(raw.split())
    compact = re.sub(r"[^a-z0-9]", "", raw)
    hits: list[tuple[LexiconTerm, float]] = []
    for term in get_lexicon():
        score = 0.0
        if compact == re.sub(r"[^a-z0-9]", "", term.canonical.lower()):
            score = 1.0
        for form in term.spoken_forms + term.common_stt_errors:
            f = form.lower()
            if raw == f or compact == re.sub(r"[^a-z0-9]", "", f):
                score = max(score, 0.95)
            elif f in raw or raw in f:
                score = max(score, 0.75)
        if score > 0:
            hits.append((term, score))
    hits.sort(key=lambda x: x[1], reverse=True)
    return hits
