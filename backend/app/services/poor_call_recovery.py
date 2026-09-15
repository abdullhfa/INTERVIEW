"""
Conditional Poor-Call / narrowband intent recovery.

Runs ONLY after normal STT + normal intent when confidence is weak.
Does not change Clean/Office audio, aliases, or the global matcher path.

Flow:
  Poor/narrowband detected → normal STT → normal match
  → if low confidence → recovery pass (wider canonicalize + top-k semantic)
  → if top-1 vs top-2 margin is small → abstain (weak/None), never HC wrong
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.services.domain_terms import normalize_for_matching
from app.services.question_bank import BankMatch, question_bank
from app.services.technical_term_repair import repair_technical_terms

# Slightly wider than the live technical repair — recovery-only.
_POOR_EXTRA_REPAIRS: list[tuple[re.Pattern[str], str]] = [
    # Fine-tune / RAG (Poor Call STT)
    (
        re.compile(
            r"^(?:raddle|rattle|radled|radol)[\-\s]*(?:eye|i|i'?m|i'?s|fine)?[\-\s]*"
            r"tun(?:e|ing)\.?$",
            re.I,
        ),
        "Should we fine-tune the model or use RAG?",
    ),
    (re.compile(r"\b(?:raddle|rattle)[\-\s]*eye\b", re.I), "fine-tune"),
    # Agentic AI garbles
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is|in|an?)?\s*"
            r"(?:again[, ]+)?(?:b[\.\s]*)?k[\.\s]*i[\.\s]*i?\??\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+in\s+again,?\s*b\.?\s*k\.?\s*i\.?\s*i\.?\??\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    # Guardrails
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:are|is|on|our)?\s*"
            r"god\s*rails?\??\.?$",
            re.I,
        ),
        "What are guardrails?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:are|is)\s+(?:llm\s+)?"
            r"(?:drawbrail|draw\s*brail|godrails|gardrails|god\s*rails?|"
            r"guard\s*rails?|guardrails?)\??\.?$",
            re.I,
        ),
        "What are guardrails?",
    ),
    (re.compile(r"\bgod\s*rail\b", re.I), "guardrails"),
    (re.compile(r"\bdrawbrail\b", re.I), "guardrails"),
    # Agent orchestrator (Poor STT)
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is|in)\s+"
            r"(?:an?\s+)?agent(?:'s|s)?'?\s+orchestrat(?:or|ion)\??\.?$",
            re.I,
        ),
        "What is an agent orchestrator?",
    ),
    (re.compile(r"\bagent(?:'s|s)?'?\s+orchestrat(?:or|ion)\b", re.I), "agent orchestrator"),
    # Agent loop (school↔loop STT confusion)
    (
        re.compile(
            r"^(?:how\s+do\s+you\s+)?(?:stop|prevent)\s+(?:into\s+)?(?:the\s+)?"
            r"(?:school|infinite|forever)?\s*loop\??\.?$",
            re.I,
        ),
        "How do you prevent an agent from looping forever?",
    ),
    (re.compile(r"\bschool\s+loop\b", re.I), "looping forever"),
    (re.compile(r"\bagents?\b", re.I), "agent"),
    (re.compile(r"\borchestra(?:tor|tion)?\b", re.I), "orchestrator"),
    (re.compile(r"\b(?:looping|loops?)\s+forever\b", re.I), "looping forever"),
    (re.compile(r"\binfinite\s+loop\b", re.I), "looping forever"),
    # Empty retrieval
    (
        re.compile(
            r"^(?:no|empty)\s+chunks?,?\s*(?:town|down|pound|sown)?\.?$",
            re.I,
        ),
        "What should the system do when retrieval returns nothing useful?",
    ),
    (re.compile(r"\bno\s+chunks?,?\s*sown\b", re.I), "retrieval returns nothing"),
    (re.compile(r"\bempty\s+retrieval\b", re.I), "retrieval returns nothing"),
    (re.compile(r"\bno\s+useful\s+(?:chunks?|results?)\b", re.I), "retrieval returns nothing"),
    # Debug bad RAG
    (
        re.compile(
            r"^(?:how\s+(?:will|would|do)\s+you\s+)?(?:be\s+)?"
            r"(?:murder|murga|debug)\s+(?:by\s+)?(?:norwegian|a\s+bad\s+rag|rag).*?"
            r"step\s+by\s+step\.?$",
            re.I,
        ),
        "How would you debug a bad RAG answer step by step?",
    ),
    (
        re.compile(
            r"^(?:i\s+will\s+)?(?:do\s+the\s+)?"
            r"(?:mergaban|murgaban|murga(?:bana)?)\s+"
            r"(?:rag[\-\s]*on|region|rag).*?step[\-\s]*by[\-\s]*step\.?$",
            re.I,
        ),
        "How would you debug a bad RAG answer step by step?",
    ),
    (re.compile(r"\bmurder\s+by\s+norwegian\b", re.I), "debug a bad RAG"),
    (re.compile(r"\bmergaban\b", re.I), "debug"),
    (re.compile(r"\bfine[\s\-]?tun(?:e|ing)\b", re.I), "fine-tune"),
    (re.compile(r"\bversus\b", re.I), "vs"),
]


@dataclass
class RecoveryDecision:
    match: Optional[BankMatch]
    applied: bool
    reason: str
    margin: float = 0.0
    candidates: int = 0


def is_narrowband(audio_levels: Optional[dict[str, Any]], *, bandwidth_hz: float = 2500.0) -> bool:
    if not audio_levels:
        return False
    bw = float(audio_levels.get("bandwidth_hz_est") or 0.0)
    hf = float(audio_levels.get("high_freq_energy_ratio") or 1.0)
    # Poor Call stress clips clustered ~1.7 kHz bandwidth / HF≈0.01.
    return (bw > 0 and bw < bandwidth_hz) or hf < 0.03


def should_attempt_poor_recovery(
    match: Optional[BankMatch],
    *,
    condition: Optional[str] = None,
    audio_levels: Optional[dict[str, Any]] = None,
) -> bool:
    """Only Poor/narrowband + weak/ambiguous/absent match (or abstained strong)."""
    poorish = (condition or "").lower() in {"poor_call", "poor"} or is_narrowband(audio_levels)
    if not poorish:
        return False
    if match is None:
        return True
    # Weak / abstained answers are fair game — including high-score near-misses.
    if match.mode != "strong":
        return True
    gap = float(match.score) - float(match.runner_up_score or 0.0)
    if float(match.score) < 0.70:
        return True
    if match.runner_up is not None and gap < 0.08:
        return True
    return False


def poor_canonicalize(text: str, *, prior_topic: Optional[str] = None) -> str:
    """Normal technical repair + a few recovery-only expansions."""
    cleaned = repair_technical_terms(text, prior_topic=prior_topic)
    out = cleaned
    for pattern, repl in _POOR_EXTRA_REPAIRS:
        out = pattern.sub(repl, out)
    return " ".join(out.split())


def _distinctive_delta(text: str, match: BankMatch) -> float:
    """
    Recovery ranking: reward entries that own distinctive query terms in the
    question/id (not merely a keyword list), so near-ties like
    orchestrator vs agent-terms flip correctly.
    """
    from app.services.question_bank import _DISTINCTIVE_TERMS  # noqa: PLC0415

    norm = normalize_for_matching(text)
    bag = set(norm.split())
    q_blob = " ".join([match.entry.id, match.entry.topic, match.entry.question]).casefold()
    kw_blob = " ".join(match.entry.keywords).casefold()
    q_norm = normalize_for_matching(match.entry.question)

    # Near-exact question match after canonicalize — strongest recovery signal.
    if norm and (norm == q_norm or norm in q_norm or q_norm in norm):
        return 0.28

    delta = 0.0
    seen_families: set[str] = set()
    for token, (family, weight) in _DISTINCTIVE_TERMS.items():
        if token not in bag and family not in bag:
            continue
        if family in seen_families:
            continue
        seen_families.add(family)
        in_question = family in q_blob or token in q_blob
        in_keywords = family in kw_blob or token in kw_blob
        w = max(0.08, float(weight))
        if in_question:
            delta += min(0.24, 0.70 * w)
        elif in_keywords:
            delta += min(0.04, 0.15 * w)
        else:
            delta -= min(0.30, 0.85 * w)
    return max(-0.35, min(0.32, delta))


def recover_poor_match(
    text: str,
    current: Optional[BankMatch],
    *,
    condition: Optional[str] = None,
    audio_levels: Optional[dict[str, Any]] = None,
    conversation_history: Optional[Iterable[dict]] = None,
    abstain_margin: float = 0.045,
) -> RecoveryDecision:
    """
    Recovery pass for Poor/narrowband only.
    Returns abstain (weak/None) when top-2 are too close — never invent HC answers.
    """
    if not should_attempt_poor_recovery(
        current, condition=condition, audio_levels=audio_levels
    ):
        return RecoveryDecision(current, False, "not_eligible")

    topic = question_bank.topic_for_history(conversation_history)
    canon = poor_canonicalize(text, prior_topic=topic)
    cands = question_bank.top_matches(
        canon,
        top_k=5,
        topic_hint=topic,
        conversation_history=conversation_history,
    )
    if not cands:
        if current is not None and current.mode == "strong":
            weakened = BankMatch(
                entry=current.entry,
                score=current.score,
                semantic=current.semantic,
                lexical=current.lexical,
                keyword=current.keyword,
                alias=current.alias,
                mode="weak",
                runner_up=current.runner_up,
                runner_up_score=current.runner_up_score,
            )
            return RecoveryDecision(weakened, True, "no_candidates_abstain_strong")
        return RecoveryDecision(current, True, "no_candidates")

    ranked: list[tuple[float, BankMatch]] = []
    for m in cands:
        ranked.append((float(m.score) + _distinctive_delta(canon, m), m))
    ranked.sort(key=lambda item: item[0], reverse=True)
    best_adj, best = ranked[0]
    second_adj = ranked[1][0] if len(ranked) > 1 else 0.0
    margin = best_adj - second_adj

    if margin < abstain_margin:
        return RecoveryDecision(
            BankMatch(
                entry=best.entry,
                score=best.score,
                semantic=best.semantic,
                lexical=best.lexical,
                keyword=best.keyword,
                alias=best.alias,
                mode="weak",
                runner_up=ranked[1][1].entry.id if len(ranked) > 1 else best.runner_up,
                runner_up_score=ranked[1][1].score if len(ranked) > 1 else best.runner_up_score,
            ),
            True,
            "ambiguous_abstain",
            margin=margin,
            candidates=len(cands),
        )

    mode = "strong" if best.score >= 0.70 and margin >= 0.15 and _distinctive_delta(canon, best) >= 0.08 else "weak"
    # Near-exact canonicalize → allow strong with slightly softer margin.
    q_norm = normalize_for_matching(best.entry.question)
    canon_norm = normalize_for_matching(canon)
    if (
        canon_norm
        and q_norm
        and (canon_norm == q_norm or canon_norm in q_norm or q_norm in canon_norm)
        and best.score >= 0.62
        and margin >= 0.08
    ):
        mode = "strong"
    if best.score < 0.48:
        return RecoveryDecision(current, True, "score_too_low", margin=margin, candidates=len(cands))

    recovered = BankMatch(
        entry=best.entry,
        score=float(best.score),
        semantic=best.semantic,
        lexical=best.lexical,
        keyword=best.keyword,
        alias=best.alias,
        mode=mode,
        runner_up=ranked[1][1].entry.id if len(ranked) > 1 else None,
        runner_up_score=float(ranked[1][1].score) if len(ranked) > 1 else 0.0,
    )
    # Prefer recovery when current was missing/weak, or recovery is clearer.
    prefer = (
        current is None
        or current.mode != "strong"
        or float(recovered.score) >= float(current.score) - 0.02
        or (
            recovered.entry.id != current.entry.id
            and _distinctive_delta(canon, recovered)
            > _distinctive_delta(canon, current) + 0.05
        )
    )
    if prefer:
        return RecoveryDecision(
            recovered, True, "recovered", margin=margin, candidates=len(cands)
        )
    return RecoveryDecision(current, True, "kept_current", margin=margin, candidates=len(cands))
