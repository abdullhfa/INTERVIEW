"""
Interview-only technical term repair for STT transcripts.

Applies BEFORE intent matching. Scope is intentionally narrow: known interview
domain terms only, so we do not invent meaning for arbitrary speech.

Pipeline:
  STT → TECH_ACRONYM_RECOVERY → phrase/token repairs → SHORT_TECH_RECOVERY
    → INTERVIEW_PHRASE_RECOVERY
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

# Phrase-level repairs (order matters: more specific first).
_PHRASE_REPAIRS: list[tuple[re.Pattern[str], str]] = [
    # RAG short questions
    (
        re.compile(
            r"^(?:what|wapid|watt|water|whats|what's)\s+"
            r"(?:is|did|it|in|the|been)?\s*"
            r"(?:r[\s\-\.]*a[\s\-\.]*[gb]|drag|rack|rags|rag|r\s*&\s*e|rng)\??\.?$",
            re.I,
        ),
        "What is RAG?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is|in)?\s*(?:r\s*(?:and|&)\s*e|rng)\??\.?$",
            re.I,
        ),
        "What is RAG?",
    ),
    (
        # STT garble only. Never rewrite a clean "What are embeddings?" — that is
        # the definition entry; mapping it to "Why embeddings?" steers to TF-IDF vs
        # embeddings and breaks the bank test / live definition path.
        re.compile(
            r"^what\s+are\s+(?:am\s+)?(?:badings?)\??\.?$",
            re.I,
        ),
        "What are embeddings?",
    ),
    (
        re.compile(
            r"^why\s+(?:am\s+)?(?:badings?|embeddings?|embedding)\??\.?$",
            re.I,
        ),
        "Why embeddings?",
    ),
    (
        re.compile(r"\b(?:badings?|am\s+badings?)\b", re.I),
        "embeddings",
    ),
    (
        re.compile(
            r"^(?:explain|define)\s+(?:rod|wrong|rack|drag|rags|rag)\??\.?$",
            re.I,
        ),
        "Explain RAG?",
    ),
    (
        re.compile(r"^(?:explain|exclaim)\s+(?:rod|wrong|last|rag)\??\.?$", re.I),
        "Explain RAG?",
    ),
    # Agentic AI
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is\s+)?(?:a\s+|an\s+)?"
            r"(?:genetic|gentic)\s*(?:k[\-\s\.\?]*i[?.]*i?|a\.?i\.?)\??\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is|in|a|an)?\s*"
            r"(?:agency\s*k[\-\s\.]*i[?.]*i?|agency\s*ai|agentic\s*i[?.]*i?|gigantic\s*(?:ai|i)|"
            r"a\s*gigantic\s*i|h\s*&\s*b\s*k\s*i[?.]*i?|identity\s*,?\s*k\.?i|"
            r"genetic\s*k[\-\s\.\?]*i[?.]*i?|gentic\s*a\.?i\.?)\??\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+in\s+agency[\s\.]*k[\s\.]*i[\s\.]*i?\.?\??\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (
        re.compile(
            r"^(?:we(?:'ve| have)?\s+been\s+again[,]?\s*)?(?:b\s*k\s*i|agency\s*k\.?i)[?.]*i?\??\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+in\s+agentic\s+ai[?.]*i?\??\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (
        re.compile(
            r"\b(?:agency\s*k[\-\s\.]*i\.?i?|agency\s*ai|agentic\s*i|gigantic\s*(?:ai|i)|"
            r"h\s*&\s*b\s*k\s*i\.?i?)\b",
            re.I,
        ),
        "agentic AI",
    ),
    # Agent orchestrator
    (
        re.compile(
            r"^(?:what|whats|what's|was)\s+(?:is|in|an?)?\s*"
            r"(?:an?\s+)?agents?\s*(?:'s)?\s*"
            r"(?:orchestrator|orchestra(?:tor)?|tarkist\s*trader|orchestrater)\??\.?$",
            re.I,
        ),
        "What is an agent orchestrator?",
    ),
    (
        re.compile(r"\bagent'?s\s+orchestrator\b", re.I),
        "agent orchestrator",
    ),
    (
        re.compile(r"\bagent\s+tarkist\s+trader\b", re.I),
        "agent orchestrator",
    ),
    # Guardrails
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:are|is|on|our)?\s*"
            r"(?:llm\s+)?(?:godrails|gardrails|god\s*rails|goddrail|braille|dara|"
            r"guard\s*rails?|guardrails?|grades)\??\.?$",
            re.I,
        ),
        "What are guardrails?",
    ),
    (
        re.compile(
            r"\b(?:godrails|gardrails|god\s*rails|goddrail|god\s*ray)\b",
            re.I,
        ),
        "guardrails",
    ),
    (
        re.compile(
            r"^langgraph\s+and\s+not\s+lan+k?ane\.?$",
            re.I,
        ),
        "What is the difference between LangChain and LangGraph?",
    ),
    (
        re.compile(
            r"\b(?:y[\-\s]*)?leng[\-\s]*(?:chain|came|gen)\b",
            re.I,
        ),
        "LangChain",
    ),
    (
        re.compile(r"\blankane\b", re.I),
        "LangChain",
    ),
    (
        re.compile(
            r"\b(?:y[\-\s]*)?leng[\-\s]*(?:graph|ref|raph|breath|rep)\b",
            re.I,
        ),
        "LangGraph",
    ),
    (
        re.compile(
            r"\b(?:langdraff|langraff|angraf|lang\s*draft)\b",
            re.I,
        ),
        "LangGraph",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is|in)?\s*"
            r"(?:langdraff|langraff|angraf|lang\s*draft)\??\.?$",
            re.I,
        ),
        "What is LangGraph?",
    ),
    (
        re.compile(r"\bland\s+chain\b", re.I),
        "LangChain",
    ),
    (
        re.compile(r"\bland\s+(?:graph|ref)\b", re.I),
        "LangGraph",
    ),
    # Fine-tuning mishearings in RAG-vs-FT questions
    (
        re.compile(r"\b(?:find\s+june|behind\s+tune|rattle[\-\s]?ind|ruddled\s+by\s+the)\b", re.I),
        "fine-tune",
    ),
    (
        re.compile(
            r"^(?:rattle|radled|raddle)\s+(?:i'?m|i'?s|fine)?\s*tun(?:e|ing)\.?$",
            re.I,
        ),
        "Should we fine-tune the model or use RAG?",
    ),
    (
        re.compile(r"\b(?:radol|raddle|rattle)\s+(?:fine\s+)?tun(?:e|ing)\b", re.I),
        "RAG or fine-tuning",
    ),
    # Agent loop prevention
    (
        re.compile(
            r"^(?:how\s+do\s+you\s+)?(?:stop|prevent)\s+(?:into\s+a\s+)?(?:school|infinite|forever)?\s*loop\??\.?$",
            re.I,
        ),
        "How do you prevent an agent from looping forever?",
    ),
    # Debug bad RAG
    (
        re.compile(
            r"^(?:i\s+will\s+)?(?:do\s+the\s+)?murga(?:bana)?\s+region.*step\s+by\s+step\.?$",
            re.I,
        ),
        "How would you debug a bad RAG answer step by step?",
    ),
    # Empty retrieval follow-ups
    (
        re.compile(
            r"^(?:and\s+)?(?:if\s+)?(?:no|empty)\s+(?:chunks?|chance|chunk,?\s*pound|chunk\s*town)\??\.?$",
            re.I,
        ),
        "What if retrieval returns no chunks?",
    ),
    (
        re.compile(r"^no\s+chunks?\s*(?:down|pound|town)?\.?$", re.I),
        "What if retrieval returns no chunks?",
    ),
]

# Token-level repairs inside longer sentences.
_TOKEN_REPAIRS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\br[\s\-\.]*a[\s\-\.]*g\b", re.I), "RAG"),
    (re.compile(r"\br\s*&\s*e\b", re.I), "RAG"),
    (re.compile(r"\b(?:drag|rack|rags)\b", re.I), "RAG"),
    # Common STT garble: "vector store" → "factor store" / "victor store"
    (re.compile(r"\b(?:factor|victor|vecter|vectorr)\s+stores?\b", re.I), "vector store"),
    (re.compile(r"\b(?:factor|victor|vecter)\s+databases?\b", re.I), "vector database"),
    (re.compile(r"\bdebug\s+a\s+(?:man\s+or\s+regi|madragender|wrong\s+rock)\b", re.I), "debug a bad RAG"),
    (re.compile(r"\bbe\s+bug\s+a\s+bad\b", re.I), "debug a bad"),
    (re.compile(r"\bdemurg(?:ing)?\b", re.I), "debug"),
]


@lru_cache(maxsize=16384)
def _repair_technical_terms_uncached(text: str, prior_topic: Optional[str]) -> str:
    """Repair interview technical terms in an STT transcript."""
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return ""

    # Context-aware short follow-ups.
    if prior_topic:
        topic = prior_topic.casefold()
        low = cleaned.casefold()
        if topic in {"rag", "retrieval"} and re.search(
            r"\b(?:no chunks?|nothing|empty|no results?)\b", low
        ):
            if len(cleaned.split()) <= 6:
                return "What should the system do when retrieval returns nothing?"

    original = cleaned

    # 0) Acronym recovery first (letter-by-letter / compact STT merges).
    # Must run before fuzzy tech-term recovery so "Lalam" → LLM, not LLaMA.
    try:
        from app.services.tech_acronym_recovery import recover_acronyms

        acr = recover_acronyms(cleaned)
        if acr.replacements and acr.recovered_transcript:
            cleaned = acr.recovered_transcript
    except Exception:
        pass

    for pattern, replacement in _PHRASE_REPAIRS:
        if pattern.pattern.startswith("^"):
            cleaned = pattern.sub(replacement, cleaned)
        else:
            cleaned = pattern.sub(replacement, cleaned)

    for pattern, replacement in _TOKEN_REPAIRS:
        cleaned = pattern.sub(replacement, cleaned)

    cleaned = " ".join(cleaned.split())

    # SHORT_TECH recovery (vocab + curated STT pairs). Runs after acronym + regex.
    try:
        from app.services.short_tech_recovery import recover_tech_terms

        rec = recover_tech_terms(cleaned)
        if rec.recovered_terms and rec.normalized_transcript:
            cleaned = rec.normalized_transcript
    except Exception:
        pass

    cleaned = " ".join(cleaned.split())

    # INTERVIEW_PHRASE recovery (common interview utterances from phonetic STT).
    try:
        from app.services.interview_phrase_recovery import recover_interview_phrases

        phr = recover_interview_phrases(cleaned)
        if phr.applied and phr.recovered_transcript:
            cleaned = phr.recovered_transcript
    except Exception:
        pass

    cleaned = " ".join(cleaned.split())
    return cleaned if cleaned else original


def repair_technical_terms(text: str, *, prior_topic: Optional[str] = None) -> str:
    """
    Memoized wrapper. Pure function of (text, prior_topic), so the cached value
    is byte-identical to recomputing the ~30 regex passes. The same transcript /
    sub-question is repaired several times per request (question_bank.match,
    prefetch_scores, should_trigger_semantic_recovery, recover_semantic_intent).
    """
    return _repair_technical_terms_uncached(text or "", prior_topic)


def repair_cache_info():  # pragma: no cover - diagnostics only
    return _repair_technical_terms_uncached.cache_info()


def clear_repair_cache() -> None:
    _repair_technical_terms_uncached.cache_clear()
    try:
        from app.services.tech_acronym_recovery import clear_acronym_vocab_cache

        clear_acronym_vocab_cache()
    except Exception:
        pass
    try:
        from app.services.short_tech_recovery import clear_vocab_cache

        clear_vocab_cache()
    except Exception:
        pass
    try:
        from app.services.interview_phrase_recovery import clear_phrase_cache

        clear_phrase_cache()
    except Exception:
        pass
    try:
        from app.services.bank_guided_understanding import clear_bank_guided_cache

        clear_bank_guided_cache()
    except Exception:
        pass
