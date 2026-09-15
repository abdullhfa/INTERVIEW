"""Intent profiles derived from existing question-bank entries (no invented facts).

FROZEN 2026-09-12 with the semantic intent layer — bug-fix only.
See reports/INTENT_LAYER_FREEZE.json.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz

from app.services.domain_terms import normalize_for_matching
from app.services.question_bank import BankEntry, detect_intent

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Informative interview terms (beyond the bank's distinctive set).
_PROFILE_DISTINCTIVE = (
    "rag",
    "retrieval",
    "augmented",
    "guardrail",
    "guardrails",
    "langgraph",
    "langchain",
    "chromadb",
    "chroma",
    "whisper",
    "embedding",
    "embeddings",
    "cosine",
    "similarity",
    "recall",
    "precision",
    "accuracy",
    "finetuning",
    "fine-tuning",
    "fine tuning",
    "agentic",
    "orchestrator",
    "hallucination",
    "chunk",
    "chunks",
    "metadata",
    "tenant",
    "pydantic",
    "btec",
)


@dataclass(frozen=True)
class IntentProfile:
    intent_id: str
    canonical_question: str
    semantic_description: str
    concepts: tuple[str, ...]
    distinctive_terms: tuple[str, ...]
    action_type: Optional[str]
    topic: str
    category: str
    related_intents: tuple[str, ...] = ()
    profile_blob: str = ""

    def agreement_targets(self) -> tuple[str, ...]:
        targets = [self.canonical_question, self.semantic_description[:240]]
        if self.concepts:
            targets.append(" ".join(self.concepts[:12]))
        return tuple(t for t in targets if t.strip())


def _first_sentences(text: str, n: int = 2) -> str:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split((text or "").strip()) if p.strip()]
    return " ".join(parts[:n]) if parts else (text or "").strip()[:240]


def _distinctive_in_text(text: str) -> list[str]:
    norm = normalize_for_matching(text)
    found: list[str] = []
    for term in _PROFILE_DISTINCTIVE:
        if term in norm and term not in found:
            found.append(term)
    return found


def build_intent_profile(
    entry: BankEntry,
    *,
    related_ids: tuple[str, ...] = (),
) -> IntentProfile:
    """Build a semantic profile from approved bank fields only."""
    answer_snip = _first_sentences(entry.answer_en or "", 2)
    description = " ".join(
        p
        for p in (
            f"topic:{entry.topic}" if entry.topic else "",
            f"category:{entry.category}" if entry.category else "",
            answer_snip,
        )
        if p
    ).strip()

    concepts: list[str] = []
    for src in (entry.keywords, entry.listen_for):
        for item in src or ():
            t = (item or "").strip()
            if t and t.lower() not in {c.lower() for c in concepts}:
                concepts.append(t)

    blob_parts = [
        entry.question,
        " | ".join(entry.aliases[:8]),
        description,
        " ".join(concepts[:16]),
    ]
    profile_blob = " | ".join(p for p in blob_parts if p.strip())
    distinctive = tuple(_distinctive_in_text(profile_blob + " " + entry.id))

    q_norm = normalize_for_matching(entry.question)
    action = detect_intent(q_norm)
    if action is None:
        for alias in entry.aliases[:6]:
            action = detect_intent(normalize_for_matching(alias))
            if action:
                break

    return IntentProfile(
        intent_id=entry.id,
        canonical_question=entry.question,
        semantic_description=description,
        concepts=tuple(concepts),
        distinctive_terms=distinctive,
        action_type=action,
        topic=entry.topic or "",
        category=entry.category or "",
        related_intents=related_ids,
        profile_blob=profile_blob,
    )


@dataclass(frozen=True)
class _EntryAgreementStatic:
    """Per-entry strings used by `intent_agreement`, built once per bank load."""

    raw_targets: tuple[str, ...]          # entry.question + aliases[:12]
    phrases: tuple[str, ...]              # normalized listen_for + keywords
    kw_blob: str
    blob_tokens: frozenset


_STATIC_CACHE: dict[tuple[int, str], _EntryAgreementStatic] = {}
_STATIC_GENERATION = -1
_AGREEMENT_CACHE: "OrderedDict[tuple[int, str, str, Optional[str]], float]" = OrderedDict()
_AGREEMENT_CACHE_LIMIT = 8192


def _bank_generation() -> int:
    from app.services.question_bank import question_bank

    return int(getattr(question_bank, "generation", 0) or 0)


def _entry_static(entry: BankEntry, profile: "IntentProfile | None") -> _EntryAgreementStatic:
    """Memoized per-entry constants. Same values the inline code built per call."""
    global _STATIC_GENERATION
    gen = _bank_generation()
    if gen != _STATIC_GENERATION:
        _STATIC_CACHE.clear()
        _AGREEMENT_CACHE.clear()
        _STATIC_GENERATION = gen
    key = (gen, entry.id)
    hit = _STATIC_CACHE.get(key)
    if hit is not None:
        return hit
    raw_targets = tuple(
        [entry.question or ""] + [a for a in entry.aliases[:12] if a.strip()]
    )
    phrases = tuple(
        pn
        for pn in (
            normalize_for_matching(phrase)
            for phrase in (*(entry.listen_for or ()), *(entry.keywords or ()))
        )
        if pn
    )
    kw_blob = " ".join([*(entry.keywords or ()), *(entry.listen_for or ())]).strip()
    from app.services.question_bank import _content_tokens

    blob = " ".join(
        [
            entry.question or "",
            " ".join(entry.aliases[:10]),
            " ".join(entry.keywords or ()),
            " ".join(entry.listen_for or ()),
            (profile.semantic_description if profile else "")[:240],
            (entry.answer_en or "")[:240],
        ]
    )
    static = _EntryAgreementStatic(
        raw_targets=raw_targets,
        phrases=phrases,
        kw_blob=kw_blob,
        blob_tokens=frozenset(_content_tokens(normalize_for_matching(blob))),
    )
    _STATIC_CACHE[key] = static
    return static


def _agreement_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    token = fuzz.token_set_ratio(a, b) / 100.0
    # Long paraphrases vs short bank text: partial helps coverage.
    partial = fuzz.partial_ratio(a, b) / 100.0 if min(len(a), len(b)) >= 12 else 0.0
    sort = fuzz.token_sort_ratio(a, b) / 100.0 if min(len(a), len(b)) >= 12 else 0.0
    return max(token, 0.92 * partial, 0.88 * sort)


def intent_agreement(entry: BankEntry, spoken: str, *, profile: IntentProfile | None = None) -> float:
    """
    Meaning agreement between spoken question and bank entry.

    Uses canonical question, aliases, keywords/listen_for, and profile description —
    not canonical wording alone.

    PERF (pre-v3): per-entry strings are precomputed once per bank load and the
    (entry, spoken) result is memoized. The arithmetic is unchanged — this
    function is called 3-5x for the same pair inside a single request.
    """
    spoken = (spoken or "").strip()
    if not spoken or entry is None:
        return 0.0
    static = _entry_static(entry, profile)
    cache_key = (
        _STATIC_GENERATION,
        entry.id,
        spoken,
        profile.intent_id if profile is not None else None,
    )
    cached = _AGREEMENT_CACHE.get(cache_key)
    if cached is not None:
        _AGREEMENT_CACHE.move_to_end(cache_key)
        return cached

    spoken_norm = normalize_for_matching(spoken)
    _score = _agreement_score

    scores: list[float] = [_score(spoken, target) for target in static.raw_targets]
    # Phrase-level hits (listen_for / keywords) — strong meaning signal.
    for pn in static.phrases:
        if len(pn) >= 6 and pn in spoken_norm:
            scores.append(0.88)
        else:
            scores.append(_score(spoken_norm, pn) * (0.95 if len(pn.split()) >= 2 else 0.85))
    if static.kw_blob:
        scores.append(_score(spoken, static.kw_blob))
    if profile is not None and profile.semantic_description:
        scores.append(_score(spoken, profile.semantic_description[:280]))
    elif entry.answer_en:
        scores.append(_score(spoken, _first_sentences(entry.answer_en, 2)[:280]))
    if entry.answer_en:
        scores.append(0.90 * _score(spoken, entry.answer_en[:320]))

    # Distinctive / content-token coverage against the profile blob.
    from app.services.question_bank import _content_tokens

    spoken_toks = set(_content_tokens(spoken_norm))
    if spoken_toks:
        overlap = len(spoken_toks & static.blob_tokens) / float(len(spoken_toks))
        scores.append(0.50 + 0.45 * overlap)

    value = max(scores) if scores else 0.0
    _AGREEMENT_CACHE[cache_key] = value
    while len(_AGREEMENT_CACHE) > _AGREEMENT_CACHE_LIMIT:
        _AGREEMENT_CACHE.popitem(last=False)
    return value


def intent_family_consistent(entry: BankEntry, spoken: str, *, profile: IntentProfile | None = None) -> bool:
    """True when spoken distinctive terms overlap the entry (or spoken has none)."""
    spoken_norm = normalize_for_matching(spoken or "")
    q_hits = set(_distinctive_in_text(spoken_norm))
    if not q_hits:
        return True
    blob = " ".join(
        [
            entry.id,
            entry.topic or "",
            entry.question or "",
            " ".join(entry.aliases[:8]),
            " ".join(entry.keywords or ()),
            " ".join((profile.distinctive_terms if profile else ())),
        ]
    )
    e_hits = set(_distinctive_in_text(normalize_for_matching(blob)))
    return bool(q_hits & e_hits)


def intent_meaning_ok(
    entry: BankEntry,
    spoken: str,
    *,
    match_score: float,
    profile: IntentProfile | None = None,
    agreement: float | None = None,
) -> tuple[bool, float]:
    """
    Evaluation gate: paraphrases may score below 0.70 vs short bank text
    while still being the right intent family.
    """
    agr = float(agreement) if agreement is not None else intent_agreement(entry, spoken, profile=profile)
    if match_score < 0.40:
        return False, agr
    if agr >= 0.70:
        return True, agr
    if agr >= 0.52 and intent_family_consistent(entry, spoken, profile=profile) and match_score >= 0.45:
        return True, agr
    return False, agr

def build_profiles_for_bank(entries: list[BankEntry]) -> dict[str, IntentProfile]:
    by_topic: dict[str, list[str]] = {}
    for e in entries:
        by_topic.setdefault(e.topic or "", []).append(e.id)
    profiles: dict[str, IntentProfile] = {}
    for e in entries:
        siblings = tuple(i for i in by_topic.get(e.topic or "", []) if i != e.id)[:8]
        profiles[e.id] = build_intent_profile(e, related_ids=siblings)
    return profiles
