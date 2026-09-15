"""
SHORT_QUESTION_AND_TECH_TERM_RECOVERY

FROZEN 2026-09-15 with V5 Live Interview Assistant — bug-fix only.
See reports/V5_LIVE_ASSISTANT_FREEZE.json.

Conservative post-STT layer:
  STT → TECH_ACRONYM_RECOVERY → TECH_TERM_RECOVERY → short-question understanding

Rules:
  - Correct terms only with multi-evidence (phonetic + vocab + context).
  - Prefer abstain over a wrong correction (false_normalization ≈ 0).
  - Never mint strong mode from recovery alone.
  - Does not change HC / accept thresholds / MAIN_REQUEST_EXTRACTION.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Optional

_WORD = re.compile(r"[A-Za-z0-9']+")
_LOCK = threading.Lock()
_VOCAB_CACHE: tuple[str, ...] | None = None

# High-precision STT confusion pairs (raw pattern → canonical).
# Applied only when the pattern matches AND the canonical term is in vocabulary.
_CURATED_PHRASES: list[tuple[re.Pattern[str], str, str]] = [
    # (pattern, replacement, canonical_term_for_vocab_gate)
    (re.compile(r"(?i)\bam\s+beddings?\b"), "embeddings", "embeddings"),
    (re.compile(r"(?i)\bam\s+bedding\b"), "embeddings", "embeddings"),
    (re.compile(r"(?i)\bimbbedding\b"), "embeddings", "embeddings"),
    (re.compile(r"(?i)\bimbbeddings?\b"), "embeddings", "embeddings"),
    (re.compile(r"(?i)\bm[\-\s]?embeddings?\b"), "embeddings", "embeddings"),
    (re.compile(r"(?i)\bfector\s+databases?\b"), "vector database", "vector database"),
    (re.compile(r"(?i)\bfector\s+stores?\b"), "vector store", "vector store"),
    (re.compile(r"(?i)\baffect\s+your\s+database\s+store\b"), "a vector database store", "vector database"),
    (re.compile(r"(?i)\ba\s+fect(?:or)?\s+database\b"), "a vector database", "vector database"),
    (re.compile(r"(?i)\blankan\b"), "LangChain", "LangChain"),
    (re.compile(r"(?i)\bland\s+chain\b"), "LangChain", "LangChain"),
    (re.compile(r"(?i)\blang\s+chain\b"), "LangChain", "LangChain"),
    (re.compile(r"(?i)\bland\s+graph\b"), "LangGraph", "LangGraph"),
    (re.compile(r"(?i)\blang\s+draft\b"), "LangGraph", "LangGraph"),
    (re.compile(r"(?i)\blangdraft\b"), "LangGraph", "LangGraph"),
    (re.compile(r"(?i)\bwhyland\s+draft\b"), "Why LangGraph", "LangGraph"),
    (re.compile(r"(?i)^whyland\s+draft\s+here\.?$"), "Why LangGraph here?", "LangGraph"),
    (re.compile(r"(?i)\bn[\-\s]?hash[\-\s]?n\b"), "n8n", "n8n"),
    (re.compile(r"(?i)\bn[\-\s]?h[\-\s]?n\b"), "n8n", "n8n"),
    (re.compile(r"(?i)\bn[\-\s]?eight[\-\s]?n\b"), "n8n", "n8n"),
    (re.compile(r"(?i)\bragged\b"), "RAG", "RAG"),
    (re.compile(r"(?i)\brabar\b"), "RAG", "RAG"),
]

# Whole-utterance short rewrites (only when vocab gate passes).
_SHORT_UTTERANCE: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"(?i)^why\s+(?:am\s+)?beddings?\??\.?$"),
        "Why embeddings?",
        "embeddings",
    ),
    (
        re.compile(r"(?i)^why\s+am\s+bedding\??\.?$"),
        "Why embeddings?",
        "embeddings",
    ),
    (
        re.compile(r"(?i)^when\s+(?:will|would)\s+you\s+use\s+zandra\??\.?$"),
        "When would you use Chroma?",
        "Chroma",
    ),
    (
        re.compile(r"(?i)^whyland\s+draft\s+here\.?$"),
        "Why LangGraph here?",
        "LangGraph",
    ),
    (
        re.compile(r"(?i)^what\s+does\s+affect\s+your\s+database\s+store\??\.?$"),
        "What does a vector database store?",
        "vector database",
    ),
    (
        re.compile(r"(?i)^what\s+does\s+a\s+fector\s+database\s+store\??\.?$"),
        "What does a vector database store?",
        "vector database",
    ),
]

# Single-token fuzzy candidates must beat this + margin over runner-up.
_FUZZY_MIN = 0.78
_FUZZY_MARGIN = 0.12

_QUESTION_WORDS = {
    "why": "reason",
    "how": "method",
    "when": "use_case",
    "what": "definition",
    "where": "location",
    "which": "choice",
}


@dataclass(frozen=True)
class RecoveredTerm:
    raw: str
    normalized: str
    confidence: float
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class ShortQuestionStructure:
    question_word: str = ""
    topic: str = ""
    action_type: str = ""
    is_short: bool = False
    is_bare_followup: bool = False


@dataclass
class TechTermRecoveryResult:
    raw_transcript: str
    normalized_transcript: str
    recovered_terms: list[RecoveredTerm] = field(default_factory=list)
    short_structure: ShortQuestionStructure = field(default_factory=ShortQuestionStructure)
    confidence: float = 0.0

    def as_dict(self) -> dict:
        return {
            "raw_transcript": self.raw_transcript,
            "normalized_transcript": self.normalized_transcript,
            "recovered_terms": [
                {
                    "raw": t.raw,
                    "normalized": t.normalized,
                    "confidence": round(t.confidence, 3),
                    "evidence": list(t.evidence),
                }
                for t in self.recovered_terms
            ],
            "short_structure": {
                "question_word": self.short_structure.question_word,
                "topic": self.short_structure.topic,
                "action_type": self.short_structure.action_type,
                "is_short": self.short_structure.is_short,
                "is_bare_followup": self.short_structure.is_bare_followup,
            },
            "confidence": round(float(self.confidence), 3),
        }


def _seed_vocab() -> set[str]:
    """Build vocabulary from domain terms + question bank (no random hardcoding)."""
    from app.services.domain_terms import _TERMS  # noqa: SLC001 — shared table

    vocab: set[str] = set()
    for canon in _TERMS:
        vocab.add(canon)
        vocab.add(canon.lower())
    # Always include interview-critical display forms.
    for extra in (
        "RAG",
        "LLM",
        "LangChain",
        "LangGraph",
        "Chroma",
        "ChromaDB",
        "embeddings",
        "embedding",
        "vector database",
        "vector store",
        "guardrails",
        "n8n",
        "Whisper",
        "Scikit-learn",
        "orchestration",
        "retrieval",
        "reranking",
        "chunking",
        "hallucination",
        "semantic search",
        "hybrid search",
        "fine-tuning",
        "prompt engineering",
        "cosine similarity",
        "tokenization",
        "transformer",
        "context window",
        "agentic AI",
    ):
        vocab.add(extra)
    try:
        from app.services.question_bank import question_bank

        question_bank.load()
        for e in question_bank.entries:
            for kw in e.keywords or ():
                k = (kw).strip()
                if 2 <= len(k) <= 40:
                    vocab.add(k)
            # Pull distinctive tech tokens from canonical questions.
            for tok in _WORD.findall(e.question or ""):
                if tok[:1].isupper() and len(tok) >= 3:
                    vocab.add(tok)
                low = tok.lower()
                if low in {
                    "embeddings",
                    "embedding",
                    "rag",
                    "llm",
                    "langchain",
                    "langgraph",
                    "chroma",
                    "chromadb",
                    "guardrails",
                    "whisper",
                    "retrieval",
                    "reranking",
                    "chunking",
                    "orchestration",
                }:
                    vocab.add(tok)
    except Exception:
        pass
    return vocab


def get_technical_vocabulary() -> tuple[str, ...]:
    global _VOCAB_CACHE
    with _LOCK:
        if _VOCAB_CACHE is None:
            # Prefer longer phrases first when matching.
            items = sorted(_seed_vocab(), key=lambda s: (-len(s), s.lower()))
            _VOCAB_CACHE = tuple(items)
        return _VOCAB_CACHE


def clear_vocab_cache() -> None:
    global _VOCAB_CACHE
    with _LOCK:
        _VOCAB_CACHE = None
    _vocab_lower.cache_clear()


@lru_cache(maxsize=1)
def _vocab_lower() -> dict[str, str]:
    """lowercase → preferred display form."""
    out: dict[str, str] = {}
    for v in get_technical_vocabulary():
        key = v.lower()
        # Prefer canonical casing from domain_terms-style names.
        if key not in out or (v[0].isupper() and not out[key][0].isupper()):
            out[key] = v
    return out


def _in_vocab(term: str) -> bool:
    return term.lower() in _vocab_lower()


def _norm_space(text: str) -> str:
    return " ".join((text or "").strip().split())


def _fuzzy_best(token: str, *, candidates: list[str]) -> tuple[str, float, float]:
    """Return (best, score, margin_over_second)."""
    raw = re.sub(r"[^a-z0-9]", "", token.lower())
    if len(raw) < 3:
        return "", 0.0, 0.0
    scored: list[tuple[float, str]] = []
    for c in candidates:
        cc = re.sub(r"[^a-z0-9]", "", c.lower())
        if not cc:
            continue
        ratio = SequenceMatcher(None, raw, cc).ratio()
        scored.append((ratio, c))
    if not scored:
        return "", 0.0, 0.0
    scored.sort(key=lambda x: x[0], reverse=True)
    best_s, best = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    return best, best_s, best_s - second


def _tech_context(text: str) -> bool:
    low = (text or "").lower()
    cues = (
        "why",
        "how",
        "when",
        "what",
        "use",
        "need",
        "rag",
        "llm",
        "agent",
        "retriev",
        "embed",
        "vector",
        "model",
        "database",
        "store",
        "graph",
        "chain",
        "guard",
        "orchestr",
        "framework",
        "pipeline",
    )
    return any(c in low for c in cues)


def extract_short_structure(text: str) -> ShortQuestionStructure:
    cleaned = _norm_space(text)
    words = _WORD.findall(cleaned)
    wc = len(words)
    is_short = wc <= 8
    low_words = [w.lower() for w in words]
    qword = ""
    for w in low_words[:3]:
        if w in _QUESTION_WORDS:
            qword = w
            break
    bare = cleaned.lower().rstrip("?.").strip() in {
        "why",
        "how",
        "when",
        "where",
        "what",
        "and why",
        "and how",
    }
    topic = ""
    vocab = _vocab_lower()
    # Prefer multi-word topics present in text.
    low = cleaned.lower()
    for phrase in ("vector database", "vector store", "agentic ai", "cosine similarity", "fine-tuning"):
        if phrase in low and phrase in vocab:
            topic = vocab[phrase]
            break
    if not topic:
        for w in words:
            key = w.lower()
            if key in vocab and key not in _QUESTION_WORDS and key not in {
                "you",
                "your",
                "the",
                "a",
                "an",
                "do",
                "does",
                "did",
                "is",
                "are",
                "use",
                "need",
                "here",
            }:
                topic = vocab[key]
                break
    action = _QUESTION_WORDS.get(qword, "")
    return ShortQuestionStructure(
        question_word=qword,
        topic=topic,
        action_type=action,
        is_short=is_short,
        is_bare_followup=bare,
    )


def recover_tech_terms(text: str) -> TechTermRecoveryResult:
    """
    Recover known technical terms from an STT transcript when evidence is strong.
    """
    raw = _norm_space(text)
    if not raw:
        return TechTermRecoveryResult(raw_transcript="", normalized_transcript="")

    vocab = _vocab_lower()
    recovered: list[RecoveredTerm] = []
    out = raw

    # 1) Whole short-utterance curated rewrites.
    for pat, repl, gate in _SHORT_UTTERANCE:
        if pat.match(out) and gate.lower() in vocab:
            recovered.append(
                RecoveredTerm(
                    raw=out,
                    normalized=repl,
                    confidence=0.93,
                    evidence=("curated_short", "technical_vocab", "question_shape"),
                )
            )
            out = repl
            break

    # 2) Curated phrase replacements inside the string.
    for pat, repl, gate in _CURATED_PHRASES:
        if not pat.search(out):
            continue
        if gate.lower() not in vocab:
            continue
        new_out = pat.sub(repl, out)
        if new_out == out:
            continue
        # Find a sample raw span for logging.
        m = pat.search(out)
        raw_span = m.group(0) if m else out
        recovered.append(
            RecoveredTerm(
                raw=raw_span,
                normalized=repl,
                confidence=0.90,
                evidence=("curated_phrase", "technical_vocab", "phonetic"),
            )
        )
        out = new_out

    # 3) Conservative single-token fuzzy recovery (short questions / tech context only).
    structure = extract_short_structure(out)
    if (structure.is_short or _tech_context(out)) and len(recovered) < 3:
        candidates = [
            v
            for v in get_technical_vocabulary()
            if " " not in v.strip() and 3 <= len(v) <= 24
        ]
        tokens = _WORD.findall(out)
        for tok in tokens:
            low = tok.lower()
            if low in vocab or low in _QUESTION_WORDS:
                continue
            if low in {
                "the",
                "you",
                "your",
                "will",
                "would",
                "does",
                "what",
                "when",
                "why",
                "how",
                "here",
                "them",
                "they",
                "need",
                "use",
                "store",
                "database",
                "a",
                "an",
                "is",
                "are",
                "do",
                "did",
                "and",
                "or",
                "of",
                "to",
                "in",
                "on",
                "for",
            }:
                continue
            # Skip likely English words that aren't tech garbles.
            if low in {"affect", "effect", "draft", "panel", "mate", "amaze", "real"}:
                # "affect" handled by curated phrase with database store only.
                continue
            best, score, margin = _fuzzy_best(tok, candidates=candidates)
            if not best or score < _FUZZY_MIN or margin < _FUZZY_MARGIN:
                continue
            # Never rewrite a word into its own plural/singular (project→projects).
            if re.sub(r"s$", "", best.lower()) == re.sub(r"s$", "", low):
                continue
            if not _tech_context(out) and not structure.is_short:
                continue
            # Require question-word or use-cue for fuzzy swaps (reduces false normals).
            if structure.question_word not in {"why", "how", "when", "what", "which"} and "use" not in out.lower():
                continue
            out2 = re.sub(rf"\b{re.escape(tok)}\b", best, out, count=1)
            if out2 == out:
                continue
            recovered.append(
                RecoveredTerm(
                    raw=tok,
                    normalized=best,
                    confidence=min(0.92, 0.55 + score * 0.4),
                    evidence=("phonetic", "technical_vocab", "question_intent"),
                )
            )
            out = out2

    # Refresh structure on normalized text.
    structure = extract_short_structure(out)
    conf = max((t.confidence for t in recovered), default=0.0)
    return TechTermRecoveryResult(
        raw_transcript=raw,
        normalized_transcript=out,
        recovered_terms=recovered,
        short_structure=structure,
        confidence=conf,
    )


def apply_tech_term_recovery(text: str) -> str:
    """Return normalized transcript (identity when no safe recovery)."""
    return recover_tech_terms(text).normalized_transcript


def demote_match_to_weak(match):
    """HC safety: recovery must not mint strong alone."""
    if match is None or getattr(match, "mode", None) != "strong":
        return match
    from app.services.question_bank import BankMatch

    return BankMatch(
        entry=match.entry,
        score=match.score,
        semantic=match.semantic,
        lexical=match.lexical,
        keyword=match.keyword,
        alias=match.alias,
        mode="weak",
        runner_up=match.runner_up,
        runner_up_score=match.runner_up_score,
    )


def reconcile_dual_matches(
    *,
    raw_match,
    norm_match,
    recovery: TechTermRecoveryResult,
):
    """
    Dual scoring: raw vs normalized.
    Agree → keep normalized (never promote to strong here).
    Disagree → prefer abstain / weaker path; do not trust recovery alone for strong.
    """
    if not recovery.recovered_terms:
        return norm_match if norm_match is not None else raw_match

    if norm_match is None and raw_match is None:
        return None

    if norm_match is None:
        return raw_match

    if raw_match is None:
        # Recovery-only hit: keep but force weak when confidence not rock-solid.
        if recovery.confidence >= 0.88:
            return demote_match_to_weak(norm_match)
        # Low confidence recovery without raw support → abstain
        if recovery.confidence < 0.80:
            return None
        return demote_match_to_weak(norm_match)

    if raw_match.entry.id == norm_match.entry.id:
        # Agreement: keep existing mode from scorer (do not upgrade).
        return norm_match

    # Disagreement: stay weak / prefer raw if recovery not highly confident.
    if recovery.confidence < 0.90:
        return demote_match_to_weak(raw_match)
    return demote_match_to_weak(norm_match)
