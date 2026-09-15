"""
Conditional Far / narrowband intent recovery (independent of Poor path).

Does NOT change Clean/Office/Poor freezes, Whisper, global canonicalize,
aliases, or audio preprocess.

Flow:
  Far/narrowband → normal STT → normal intent
  → if eligible → Far recovery (recovery-only canonicalize + top-5)
  → margin check → strong answer or abstain (never HC wrong)
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from app.services.domain_terms import normalize_for_matching
from app.services.poor_call_recovery import (
    RecoveryDecision,
    _distinctive_delta,
    is_narrowband,
    poor_canonicalize,
)
from app.services.question_bank import BankMatch, question_bank

# Far-only STT garble repairs — never applied on Clean/Office/Poor paths.
_FAR_EXTRA_REPAIRS: list[tuple[re.Pattern[str], str]] = [
    # RAG short forms
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is|are)\s+r[\-\s]*a[\-\s]*[deg]\??\.?$",
            re.I,
        ),
        "What is RAG?",
    ),
    (re.compile(r"^(?:explain|define)\s+rob\.?$", re.I), "Explain RAG?"),
    # Hyphen/spaced letter forms only — never bare "Rae" (collides with guardrails).
    (re.compile(r"\br[\-\.\s]+a[\-\.\s]+[deg]\b", re.I), "RAG"),
    # Fine-tune vs RAG
    (
        re.compile(r"^fine[\-\s]?tun(?:e|ing)\s+tubing\.?$", re.I),
        "Should we fine-tune the model or use RAG?",
    ),
    (re.compile(r"\bfine[\-\s]?tun(?:e|ing)\s+tubing\b", re.I), "fine-tune or RAG"),
    (
        re.compile(
            r"^(?:rattle|raddle|radled)[\.,]?\s+(?:i'?m|i'?s|fine)?\s*tun(?:e|ing)\.?$",
            re.I,
        ),
        "Should we fine-tune the model or use RAG?",
    ),
    # Agentic AI
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is|in)\s+(?:i\s+can\s+)?decay\??\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+in\s+(?:the\s+|a\s+)?"
            r"(?:nbk?ai|vki|nicai)\??\.?i?\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+in\s+(?:a\s+)?identity,?\s*k\.?i\??\.?i?\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+in\s+again,?\s*v?\.?k\.?i\.?\s*i\.?\??\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (re.compile(r"\b(?:nbk?ai|vki|nicai)\.?i?\b", re.I), "agentic AI"),
    (re.compile(r"\bi\s+can\s+decay\b", re.I), "agentic AI"),
    # Agent orchestrator
    (
        re.compile(
            r"^(?:what|whats|what's|was)\s+(?:is|in)\s+"
            r"(?:an?\s+)?agent(?:'s|s)?'?\s+"
            r"(?:orchestrat(?:or|ion)|talkistrator)\??\.?$",
            re.I,
        ),
        "What is an agent orchestrator?",
    ),
    (
        re.compile(
            r"^what in agent orchestrator\??\.?"
            r"(?:\s+what'?s in agent orchestrator\??\.?)?$",
            re.I,
        ),
        "What is an agent orchestrator?",
    ),
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is|in)\s+(?:an?\s+)?"
            r"maiden\s+darkest\s+raider\??\.?$",
            re.I,
        ),
        "What is an agent orchestrator?",
    ),
    (re.compile(r"\bmaiden\s+darkest\s+raider\b", re.I), "agent orchestrator"),
    (re.compile(r"\btalkistrator\b", re.I), "orchestrator"),
    (re.compile(r"\bagent\s+orchestrat(?:or|ion)\b", re.I), "agent orchestrator"),
    # Guardrails
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:are|is|a)\s+"
            r"(?:llm\s+|a\s+l+l+\.?|you\s+are\s+|your\s+|dog\s+are\s+)?"
            r"(?:radio|rave|rail|rails?|guard\s*rails?|dara\s*rave|drae|rae|"
            r"god\s*rails?|guardrails?)\??\.?$",
            re.I,
        ),
        "What are guardrails?",
    ),
    (
        re.compile(r"^(?:what|whats|what's)\s+(?:are|is)\s+a\s+l+l+\.?rae\??\.?$", re.I),
        "What are guardrails?",
    ),
    (
        re.compile(r"^(?:what|whats|what's)\s+a\s+dog\s+are\s+rave\??\.?$", re.I),
        "What are guardrails?",
    ),
    (re.compile(r"\bl+l+\.?rae\b", re.I), "guardrails"),
    (re.compile(r"\bdara\s*rave\b", re.I), "guardrails"),
    (re.compile(r"\bdrae\b", re.I), "guardrails"),
    (re.compile(r"\bguard\s*rails?\b", re.I), "guardrails"),
    (re.compile(r"^what are (?:you are |your )?rails?\??\.?$", re.I), "What are guardrails?"),
    (re.compile(r"^what are radio\??\.?$", re.I), "What are guardrails?"),
    # Debug bad RAG
    (
        re.compile(
            r"^(?:how\s+(?:will|would|do)\s+you\s+)?"
            r"(?:be\s+)?"
            r"(?:bug\s+a\s+man\s+already|murder\s+man\s+are\s+aliens|"
            r"burger\s+man\s+are\s+ready).*?"
            r"step[\-\s,]*(?:by|my)[\-\s]*step\.?$",
            re.I,
        ),
        "How would you debug a bad RAG answer step by step?",
    ),
    (re.compile(r"\bbug\s+a\s+man\s+already\b", re.I), "debug a bad RAG"),
    (re.compile(r"\bmurder\s+man\s+are\s+aliens\b", re.I), "debug a bad RAG"),
    (re.compile(r"\bburger\s+man\s+are\s+ready\b", re.I), "debug a bad RAG"),
]


def should_attempt_far_recovery(
    match: Optional[BankMatch],
    *,
    condition: Optional[str] = None,
    audio_levels: Optional[dict[str, Any]] = None,
) -> bool:
    """Far label always re-ranks; live narrowband only when match is weak/ambiguous."""
    cond = (condition or "").lower()
    if cond == "far":
        return True
    if not is_narrowband(audio_levels):
        return False
    if match is None or match.mode != "strong":
        return True
    gap = float(match.score) - float(match.runner_up_score or 0.0)
    if float(match.score) < 0.70:
        return True
    if match.runner_up is not None and gap < 0.08:
        return True
    return False


def far_canonicalize(text: str, *, prior_topic: Optional[str] = None) -> str:
    """Poor recovery canonicalize + Far-only expansions (Far path only)."""
    out = poor_canonicalize(text, prior_topic=prior_topic)
    for pattern, repl in _FAR_EXTRA_REPAIRS:
        out = pattern.sub(repl, out)
    return " ".join(out.split())


def _near_exact(canon: str, question: str) -> bool:
    q_norm = normalize_for_matching(question)
    c_norm = normalize_for_matching(canon)
    return bool(c_norm and q_norm and (c_norm == q_norm or c_norm in q_norm or q_norm in c_norm))


def recover_far_match(
    text: str,
    current: Optional[BankMatch],
    *,
    condition: Optional[str] = None,
    audio_levels: Optional[dict[str, Any]] = None,
    conversation_history: Optional[Iterable[dict]] = None,
    abstain_margin: float = 0.05,
) -> RecoveryDecision:
    """
    Far recovery pass. Prefers abstain (weak) over high-confidence wrong.
    Strong answers require clearer margin than Poor.
    """
    if not should_attempt_far_recovery(
        current, condition=condition, audio_levels=audio_levels
    ):
        return RecoveryDecision(current, False, "not_eligible")

    topic = question_bank.topic_for_history(conversation_history)
    canon = far_canonicalize(text, prior_topic=topic)
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
    near = _near_exact(canon, best.entry.question)

    # Near-exact canonicalize: never abstain as ambiguous — intent can still score.
    if margin < abstain_margin and not near:
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

    mode = "weak"
    delta = _distinctive_delta(canon, best)
    if near and best.score >= 0.55 and margin >= 0.08:
        mode = "strong"
    elif best.score >= 0.75 and margin >= 0.18 and delta >= 0.10:
        mode = "strong"

    if best.score < 0.48 and not near:
        if current is not None and current.mode == "strong":
            return RecoveryDecision(
                BankMatch(
                    entry=current.entry,
                    score=current.score,
                    semantic=current.semantic,
                    lexical=current.lexical,
                    keyword=current.keyword,
                    alias=current.alias,
                    mode="weak",
                    runner_up=current.runner_up,
                    runner_up_score=current.runner_up_score,
                ),
                True,
                "score_too_low_abstain_strong",
                margin=margin,
                candidates=len(cands),
            )
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

    if (condition or "").lower() == "far":
        return RecoveryDecision(
            recovered, True, "recovered", margin=margin, candidates=len(cands)
        )

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
    if current is not None and current.mode == "strong":
        return RecoveryDecision(
            BankMatch(
                entry=current.entry,
                score=current.score,
                semantic=current.semantic,
                lexical=current.lexical,
                keyword=current.keyword,
                alias=current.alias,
                mode="weak",
                runner_up=current.runner_up,
                runner_up_score=current.runner_up_score,
            ),
            True,
            "kept_current_abstain_strong",
            margin=margin,
            candidates=len(cands),
        )
    return RecoveryDecision(current, True, "kept_current", margin=margin, candidates=len(cands))
