"""Lightweight question-complexity detector (single vs compound).

Fast, deterministic heuristics only — no LLM. Length alone is never enough:
we look for multiple semantic *requests* (WH clauses, staged lists, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.services.question_bank import is_compound_question, normalize_for_matching

QuestionType = Literal["single", "compound", "uncertain"]

_WH = ("what", "why", "how", "when", "where", "which", "who")

# Second request after a connector (classic multi-intent).
_SECOND_REQUEST_RE = re.compile(
    r"(?:,|;|\band\b|\balso\b|\bplus\b|\bas well as\b)\s+"
    r"(?:(?:and|also|plus)\s+)?"
    r"(?:what|how|why|when|where|which|who|did|do|does|have|has|is|are|"
    r"was|were|can|could|would|tell|explain|describe|compare|walk)\b",
    re.I,
)

_STAGE_PATH_RE = re.compile(
    r"\bstarting from\b.+\bthen\b.+\b(?:finally|and finally)\b",
    re.I | re.S,
)

_COMPARE_RE = re.compile(
    r"\b(?:compare|contrast|difference between)\b.+\band\b",
    re.I,
)

_INCLUDING_LIST_RE = re.compile(
    r"\bincluding\b([^.?]+)",
    re.I,
)

_EXPLAIN_AND_EXPLAIN_RE = re.compile(
    r"\b(?:explain|describe|walk me through|tell me|define|give)\b.+\band\b.+\b"
    r"(?:explain|describe|tell|say|point|define|give|why|how|what|when|where|which|prefer|pick)\b",
    re.I | re.S,
)

# "Define X, and say why Y" / "Explain X, then point to Y" — imperative + second ask.
_IMPERATIVE_SECOND_RE = re.compile(
    r"\b(?:define|explain|describe|give|separate|walk|compare)\b.{8,}?"
    r"(?:,|;|\band\b|\bthen\b)\s+"
    r"(?:(?:and|then|also)\s+)?"
    r"(?:say|tell|explain|describe|point|define|give|how|why|what|when|where|which|"
    r"prefer|pick|block|stop|judge|matter|sit|depend|keep|prevent|validate|name)\b",
    re.I | re.S,
)

_FIRST_THEN_RE = re.compile(
    r"\b(?:first|then|next|finally)\b",
    re.I,
)

_IN_THAT_ORDER_RE = re.compile(r"\bin that order\b", re.I)

# "Define A, B, and C" / "Explain X, Y, and Z — in that order"
_ORDERED_TOPIC_LIST_RE = re.compile(
    r"\b(?:define|explain|describe|cover|list|walk)\b[^?]{6,}?"
    r"(?:,|;)\s*[^?]{3,}?\band\b[^?]{3,}",
    re.I | re.S,
)

# Technical / process nouns that mark distinct requested facets when listed.
_FACET_TERMS = (
    "chunking",
    "embeddings",
    "embedding",
    "retrieval",
    "generation",
    "validation",
    "approval",
    "logging",
    "permissions",
    "retries",
    "retry",
    "ranking",
    "metadata",
    "filters",
    "collections",
    "precision",
    "recall",
    "accuracy",
    "latency",
    "fallback",
    "vad",
    "stt",
    "whisper",
    "intent",
    "confidence",
    "rag",
    "fine tuning",
    "finetuning",
    "agentic",
    "workflow",
    "checkpoints",
    "human approval",
    "teacher",
    "hallucination",
    "abstain",
    "empty-retrieval",
    "empty retrieval",
    "number check",
)


@dataclass(frozen=True)
class ComplexityDetection:
    question_type: QuestionType
    confidence: float
    request_count_estimate: int
    signals: tuple[str, ...]


def _count_wh_requests(normalized: str) -> int:
    """Count WH tokens that look like distinct request heads."""
    tokens = normalized.split()
    count = 0
    for i, tok in enumerate(tokens):
        if tok not in _WH:
            continue
        # Skip "what happens if" double-count noise by requiring request-ish context.
        if i == 0 or tokens[i - 1] in {
            "and",
            "also",
            "plus",
            "then",
            "or",
            "including",
            ",",
        }:
            count += 1
        elif i > 0 and tokens[i - 1] in {"me", "us"} and i > 1 and tokens[i - 2] in {
            "tell",
            "ask",
            "show",
        }:
            count += 1
        elif count == 0:
            count = 1
    return count


def _including_facet_count(text: str) -> int:
    m = _INCLUDING_LIST_RE.search(text)
    if not m:
        return 0
    chunk = m.group(1)
    parts = re.split(r",|\band\b", chunk, flags=re.I)
    parts = [p.strip() for p in parts if p.strip()]
    return len(parts)


def _facet_hits(normalized: str) -> int:
    hits = 0
    for term in _FACET_TERMS:
        if term in normalized:
            hits += 1
    return hits


def detect_question_complexity(text: str) -> ComplexityDetection:
    """Classify SINGLE / COMPOUND / UNCERTAIN without calling an LLM."""
    raw = (text or "").strip()
    if not raw:
        return ComplexityDetection("single", 0.99, 1, ("empty",))

    normalized = normalize_for_matching(raw)
    signals: list[str] = []
    request_est = 1

    wh_n = _count_wh_requests(normalized)
    if wh_n >= 2:
        signals.append(f"wh_requests:{wh_n}")
        request_est = max(request_est, wh_n)

    if is_compound_question(normalized) or _SECOND_REQUEST_RE.search(raw):
        signals.append("connector_second_request")
        request_est = max(request_est, 2)

    if _IMPERATIVE_SECOND_RE.search(raw) or _EXPLAIN_AND_EXPLAIN_RE.search(raw):
        signals.append("imperative_second_request")
        request_est = max(request_est, 2)

    if _ORDERED_TOPIC_LIST_RE.search(raw) or _IN_THAT_ORDER_RE.search(raw):
        signals.append("ordered_topic_list")
        commas = raw.count(",")
        request_est = max(request_est, min(4, 2 + max(0, commas - 1)))

    if _STAGE_PATH_RE.search(raw):
        signals.append("stage_path")
        request_est = max(request_est, 3)

    if _COMPARE_RE.search(raw):
        signals.append("compare_contrast")
        request_est = max(request_est, 2)

    if _EXPLAIN_AND_EXPLAIN_RE.search(raw) and "imperative_second_request" not in signals:
        signals.append("explain_and_explain")
        request_est = max(request_est, 2)

    incl_n = _including_facet_count(raw)
    if incl_n >= 3:
        signals.append(f"including_list:{incl_n}")
        # Group facets thematically — do not treat every list item as its own intent.
        request_est = max(request_est, min(4, 1 + (incl_n + 1) // 3))

    facet_n = _facet_hits(normalized)
    stage_words = len(_FIRST_THEN_RE.findall(raw))
    if facet_n >= 4 and ("," in raw) and stage_words >= 1:
        signals.append(f"staged_facets:{facet_n}")
        request_est = max(request_est, min(4, 2 + facet_n // 4))
    elif facet_n >= 5 and raw.count(",") >= 3:
        signals.append(f"comma_facets:{facet_n}")
        request_est = max(request_est, 3)

    # "what X and how Y" / "why X and why Y" without relying only on is_compound_question.
    if re.search(
        r"\b(?:what|why|how)\b.+\band\b.+\b(?:what|why|how|when|where|which)\b",
        normalized,
    ):
        if "wh_and_wh" not in "".join(signals):
            signals.append("wh_and_wh")
        request_est = max(request_est, 2)

    word_count = len(normalized.split())
    signal_n = len(signals)

    # Long but single-request: e.g. one "why" with a long clause.
    if signal_n == 0:
        return ComplexityDetection("single", 0.92, 1, ("no_multi_request_signal",))

    if request_est >= 3 and signal_n >= 2:
        conf = min(0.97, 0.78 + 0.04 * signal_n + (0.04 if word_count >= 35 else 0.0))
        return ComplexityDetection("compound", conf, request_est, tuple(signals))

    if request_est >= 2 and signal_n >= 2:
        conf = min(0.94, 0.72 + 0.05 * signal_n)
        return ComplexityDetection("compound", conf, request_est, tuple(signals))

    if signal_n >= 2 or (request_est >= 2 and signal_n >= 1 and word_count >= 28):
        conf = min(0.80, 0.55 + 0.08 * signal_n)
        return ComplexityDetection("uncertain", conf, max(2, request_est), tuple(signals))

    # One soft signal (e.g. classic compound RE on a short question) → compound when
    # request_est>=2 (Track B: do not bury multi-ask under uncertain-only).
    if signal_n == 1 and request_est >= 2:
        return ComplexityDetection("compound", 0.72, request_est, tuple(signals))

    return ComplexityDetection("single", 0.85, 1, tuple(signals) or ("weak_signal",))
