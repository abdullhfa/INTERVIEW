"""Live conversational follow-up expand (subject append).

Feature flag LIVE_FOLLOW_UP_EXPAND=on|off (default off until debt exit gates).
Open debt / exit gates: backend/reports/DEBT_FOLLOW_UP_EXPAND.md

Hint never filters: raw match is always computed alongside expand.
Expansion-sourced wins are force-capped to weak so they cannot create HC wrong.

Known: wiring expand inside question_bank.match also feeds STT prelim + question
gate — live ON deleted answers (2/4). Next fix moves expand to answer-path only
(check gate د immediately), then absent-domain-subject hint (bias: miss > false fire).
Hard ban: never re-hook expand into match / prelim / is_strong gate.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)

LIVE_FOLLOW_UP_EXPAND = os.getenv("LIVE_FOLLOW_UP_EXPAND", "off").strip().lower()

# Prefer expanded only if it beats raw by this score margin, or raw is empty.
_EXPAND_MARGIN = 0.05

_DEICTIC_RE = re.compile(r"\b(it|that|this|them|they)\b", re.IGNORECASE)
_USE_IN_PROJECT_RE = re.compile(
    r"(?i)\b(?:are|do|have|did|were)\s+you\s+(?:use|used|using)\b"
    r".*\bin\s+(?:your|the|that)\s+projects?\b"
)
_USE_VERB_RE = re.compile(r"(?i)\b(use|used|using)\b")

# Multi-word subjects first (longest match wins).
_SUBJECT_PHRASES: tuple[str, ...] = (
    "agentic ai",
    "multi agent",
    "semantic kernel",
    "knowledge graph",
    "hybrid search",
    "vector database",
    "lang graph",
    "lang chain",
)


def follow_up_expand_enabled() -> bool:
    return (LIVE_FOLLOW_UP_EXPAND or "off").strip().lower() in {"on", "1", "true", "yes"}


def follow_up_hint(text: str, *, has_prior: bool) -> bool:
    """True when the utterance *may* be a follow-up. Hint only — never a filter."""
    if not has_prior:
        return False
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _DISTINCTIVE_TERMS, _FOLLOW_UP_GENERIC, _content_tokens

    raw = " ".join((text or "").strip().split())
    if not raw:
        return False
    normalized = normalize_for_matching(raw)
    if not normalized:
        return False
    content = _content_tokens(normalized)
    bag = set(normalized.split()) | set(content)

    # Already carries a distinctive bank term → treat as standalone.
    for tok, (family, _boost) in _DISTINCTIVE_TERMS.items():
        if tok in bag or family in bag:
            return False
    for phrase in _SUBJECT_PHRASES:
        if phrase in normalized:
            return False

    if any(marker in normalized for marker in _FOLLOW_UP_GENERIC):
        return True
    if _USE_IN_PROJECT_RE.search(raw) and not _has_local_object_noun(normalized, bag):
        return True
    if _DEICTIC_RE.search(normalized) and not _has_local_object_noun(normalized, bag):
        return True
    if len(content) <= 4:
        return True
    return False


def _has_local_object_noun(normalized: str, bag: set[str]) -> bool:
    """True if the utterance already names a concrete object beyond stop/deictic noise."""
    from app.services.question_bank import _DISTINCTIVE_TERMS

    for tok in _DISTINCTIVE_TERMS:
        if tok in bag:
            return True
    # Project/org proper-ish tokens that should block expand.
    for tok in (
        "rag", "llm", "whisper", "chroma", "langgraph", "langchain", "knet", "najat",
        "btec", "ministry", "kiosk", "helpdesk", "early", "warning", "agentic",
    ):
        if tok in bag:
            return True
    return False


def subject_from_prior(
    conversation_history: Optional[Iterable[dict]],
    *,
    recent_entry: Any = None,
) -> Optional[str]:
    """Distinctive subject to append — from prior question text, else prior bank entry."""
    from app.services.domain_terms import normalize_for_matching
    from app.services.question_bank import _DISTINCTIVE_TERMS
    from app.services.technical_term_repair import repair_technical_terms

    prior_text = _last_interviewer_text(conversation_history)
    if prior_text:
        repaired = repair_technical_terms(prior_text)
        normalized = normalize_for_matching(repaired)
        subject = _subject_from_normalized(normalized)
        if subject:
            return subject

    if recent_entry is not None:
        kws = list(getattr(recent_entry, "keywords", ()) or ())
        blob = normalize_for_matching(" ".join(kws + [getattr(recent_entry, "question", "") or ""]))
        subject = _subject_from_normalized(blob)
        if subject:
            return subject
        # id stem: tech.agentic_what -> agentic
        eid = str(getattr(recent_entry, "id", "") or "")
        parts = eid.split(".")
        for part in reversed(parts):
            token = part.replace("_", " ").strip()
            if token and token not in {"what", "how", "why", "tech", "cv", "hard", "gen", "proj"}:
                if token in _DISTINCTIVE_TERMS or any(token.startswith(p) for p in ("agentic", "rag")):
                    return token
    return None


def _last_interviewer_text(conversation_history: Optional[Iterable[dict]]) -> Optional[str]:
    if not conversation_history:
        return None
    for entry in reversed(list(conversation_history)):
        if entry.get("role") == "interviewer":
            text = str(entry.get("text") or "").strip()
            return text or None
    return None


def _subject_from_normalized(normalized: str) -> Optional[str]:
    from app.services.question_bank import _DISTINCTIVE_TERMS

    if not normalized:
        return None
    for phrase in _SUBJECT_PHRASES:
        if phrase in normalized:
            return phrase
    # Single distinctive tokens (prefer longer keys first).
    hits = [tok for tok in _DISTINCTIVE_TERMS if re.search(rf"\b{re.escape(tok)}\b", normalized)]
    if not hits:
        # Common interview subjects not all in _DISTINCTIVE_TERMS.
        for tok in ("agentic", "rag", "embeddings", "lora", "mcp", "whisper", "guardrails"):
            if re.search(rf"\b{re.escape(tok)}\b", normalized):
                hits.append(tok)
    if not hits:
        return None
    hits.sort(key=len, reverse=True)
    return hits[0]


def append_subject(text: str, subject: str) -> str:
    """Append subject without replacing pronouns (avoids re-asking the parent)."""
    raw = " ".join((text or "").strip().split())
    sub = " ".join((subject or "").strip().split())
    if not raw or not sub:
        return raw
    low = raw.casefold()
    if sub.casefold() in low:
        return raw

    # Object-less use-in-project: insert after the use verb.
    m = _USE_VERB_RE.search(raw)
    if m and _USE_IN_PROJECT_RE.search(raw):
        insert_at = m.end()
        return (raw[:insert_at] + " " + sub + raw[insert_at:]).strip()

    # Generic append before trailing '?' 
    if raw.endswith("?"):
        return f"{raw[:-1].rstrip()} {sub}?".strip()
    return f"{raw} {sub}".strip()


def reconcile_raw_and_expanded(
    raw_match: Any,
    exp_match: Any,
    *,
    expanded_text: str,
) -> Any:
    """Pick expanded only when it wins; force weak if expansion changed the intent."""
    if exp_match is None:
        return raw_match
    if raw_match is None:
        return _force_weak(exp_match, reason="expand_only")

    raw_id = raw_match.entry.id
    exp_id = exp_match.entry.id
    if exp_id == raw_id:
        return raw_match

    if float(exp_match.score) + 1e-9 < float(raw_match.score) + _EXPAND_MARGIN:
        return raw_match

    logger.info(
        "FOLLOW_UP_EXPAND prefer expanded id=%s score=%.3f over raw id=%s score=%.3f text=%r",
        exp_id,
        float(exp_match.score),
        raw_id,
        float(raw_match.score),
        expanded_text[:120],
    )
    return _force_weak(exp_match, reason="expansion_sourced", runner=raw_id, runner_score=raw_match.score)


def _force_weak(match: Any, *, reason: str, runner: Optional[str] = None, runner_score: float = 0.0) -> Any:
    from app.services.question_bank import BankMatch

    if match is None:
        return None
    if match.mode == "weak":
        logger.info("FOLLOW_UP_STRONG_CAPPED skip reason=%s already_weak id=%s", reason, match.entry.id)
        return match
    logger.info(
        "FOLLOW_UP_STRONG_CAPPED reason=%s id=%s was=%s",
        reason,
        match.entry.id,
        match.mode,
    )
    return BankMatch(
        entry=match.entry,
        score=match.score,
        semantic=match.semantic,
        lexical=match.lexical,
        keyword=match.keyword,
        alias=match.alias,
        mode="weak",
        runner_up=runner if runner is not None else match.runner_up,
        runner_up_score=runner_score if runner else match.runner_up_score,
    )


def apply_follow_up_expand(
    *,
    raw_text: str,
    raw_match: Any,
    conversation_history: Optional[Iterable[dict]],
    match_expanded: Callable[[str], Any],
    recent_entry: Any = None,
) -> Any:
    """If flag+hint+subject: match expanded text and reconcile with strong-cap."""
    if not follow_up_expand_enabled():
        return raw_match

    history = list(conversation_history or [])
    has_prior = _last_interviewer_text(history) is not None
    if not follow_up_hint(raw_text, has_prior=has_prior):
        return raw_match

    logger.info("FOLLOW_UP_HINT text=%r", (raw_text or "")[:120])
    subject = subject_from_prior(history, recent_entry=recent_entry)
    if not subject:
        logger.info("FOLLOW_UP_EXPAND skip: no subject from prior")
        return raw_match

    expanded = append_subject(raw_text, subject)
    if expanded == " ".join((raw_text or "").strip().split()):
        return raw_match

    logger.info("FOLLOW_UP_EXPAND subject=%r expanded=%r", subject, expanded[:160])
    try:
        exp_match = match_expanded(expanded)
    except Exception as exc:
        logger.warning("FOLLOW_UP_EXPAND match failed: %s", exc)
        return raw_match

    return reconcile_raw_and_expanded(raw_match, exp_match, expanded_text=expanded)
