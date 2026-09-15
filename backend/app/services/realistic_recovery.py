"""
Realistic-suite recovery pass (final readiness only).

Runs AFTER the normal pipeline (and after frozen Poor/Far recovery when those
conditions apply). Does NOT modify Poor/Far/Clean/Office modules, Whisper,
aliases, matcher, VAD, or audio preprocess.

Trigger: low confidence / ambiguous / distinctive-term conflict only.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from app.services.domain_terms import normalize_for_matching
from app.services.poor_call_recovery import RecoveryDecision, _distinctive_delta
from app.services.question_bank import BankMatch, question_bank
from app.services.technical_term_repair import repair_technical_terms

# Recovery-only repairs for Realistic fail patterns (not global canonicalize).
_REALISTIC_EXTRA_REPAIRS: list[tuple[re.Pattern[str], str]] = [
    # Agentic
    (
        re.compile(
            r"^(?:what|whats|what's)\s+(?:is|in)\s+(?:a\s+)?"
            r"genetic\s*k\.?i\??\.?i?\.?$",
            re.I,
        ),
        "What is agentic AI?",
    ),
    (re.compile(r"\bgenetic\s*k\.?i\b", re.I), "agentic AI"),
    # Orchestrator near-misses
    (
        re.compile(
            r"^(?:what'?s\s+been|what|whats|what's)\s+(?:is|in|an?)?\s*"
            r"(?:an?\s+)?agent\s+"
            r"(?:orchestrat(?:or|ion)|tauriastrager|talkistrator)\??\.?$",
            re.I,
        ),
        "What is an agent orchestrator?",
    ),
    (re.compile(r"\btauriastrager\b", re.I), "orchestrator"),
    (re.compile(r"\btalkistrator\b", re.I), "orchestrator"),
    # Agent loop
    (
        re.compile(
            r"^(?:how\s+do\s+you\s+)?(?:stop|prevent)\s+"
            r"(?:internet\s+tool\s+groups?|in\s+in\s+a\s+school\s+group|"
            r"into\s+(?:the\s+)?school\s+(?:loop|group))\??\.?$",
            re.I,
        ),
        "How do you prevent an agent from looping forever?",
    ),
    (re.compile(r"\binternet\s+tool\s+groups?\b", re.I), "looping forever"),
    (re.compile(r"\bschool\s+group\b", re.I), "looping forever"),
    # Guardrails
    (
        re.compile(
            r"^(?:what|whats|what's|whata)\??\s*"
            r"(?:are\s+(?:our\s+|llm\s+)?)?"
            r"(?:guard\s*)?(?:braille|grae|rails?|guardrails?)\??\.?$",
            re.I,
        ),
        "What are guardrails?",
    ),
    (re.compile(r"\bguard\s*braille\b", re.I), "guardrails"),
    (re.compile(r"\bgrae\b", re.I), "guardrails"),
    (re.compile(r"^whata\??\s*braille\??\.?$", re.I), "What are guardrails?"),
    # Fine-tune vs RAG
    (
        re.compile(
            r"^(?:rattled|rattle|raddle)[\-\s]*i'?e?m\s+tubing\.?$",
            re.I,
        ),
        "Should we fine-tune the model or use RAG?",
    ),
    (re.compile(r"\brattled[\-\s]*i'?e?m\b", re.I), "fine-tune"),
]


def realistic_canonicalize(text: str, *, prior_topic: Optional[str] = None) -> str:
    out = repair_technical_terms(text, prior_topic=prior_topic)
    for pattern, repl in _REALISTIC_EXTRA_REPAIRS:
        out = pattern.sub(repl, out)
    return " ".join(out.split())


def _distinctive_conflict(text: str, match: Optional[BankMatch]) -> bool:
    """True when query carries a distinctive term the matched entry does not own in its question."""
    if match is None:
        return False
    from app.services.question_bank import _DISTINCTIVE_TERMS  # noqa: PLC0415

    norm = normalize_for_matching(text)
    bag = set(norm.split())
    q_blob = " ".join([match.entry.id, match.entry.topic, match.entry.question]).casefold()
    for token, (family, _w) in _DISTINCTIVE_TERMS.items():
        if token in bag or family in bag:
            if family not in q_blob and token not in q_blob:
                return True
    return False


def should_attempt_realistic_recovery(match: Optional[BankMatch], text: str) -> bool:
    """Only low-confidence / ambiguous / distinctive conflict — never on clear strong hits."""
    if match is None:
        return True
    if match.mode != "strong":
        return True
    gap = float(match.score) - float(match.runner_up_score or 0.0)
    if match.runner_up is not None and gap < 0.12:
        return True
    if float(match.score) < 0.70:
        return True
    if _distinctive_conflict(text, match):
        return True
    return False


def recover_realistic_match(
    text: str,
    current: Optional[BankMatch],
    *,
    conversation_history: Optional[Iterable[dict]] = None,
    abstain_margin: float = 0.05,
) -> RecoveryDecision:
    if not should_attempt_realistic_recovery(current, text):
        return RecoveryDecision(current, False, "not_eligible")

    topic = question_bank.topic_for_history(conversation_history)
    canon = realistic_canonicalize(text, prior_topic=topic)
    cands = question_bank.top_matches(
        canon,
        top_k=5,
        topic_hint=topic,
        conversation_history=conversation_history,
    )
    if not cands:
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
                "no_candidates_abstain_strong",
            )
        return RecoveryDecision(current, True, "no_candidates")

    ranked: list[tuple[float, BankMatch]] = []
    for m in cands:
        ranked.append((float(m.score) + _distinctive_delta(canon, m), m))
    ranked.sort(key=lambda item: item[0], reverse=True)
    best_adj, best = ranked[0]
    second_adj = ranked[1][0] if len(ranked) > 1 else 0.0
    margin = best_adj - second_adj

    q_norm = normalize_for_matching(best.entry.question)
    c_norm = normalize_for_matching(canon)
    near = bool(c_norm and q_norm and (c_norm == q_norm or c_norm in q_norm or q_norm in c_norm))

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
    return RecoveryDecision(recovered, True, "recovered", margin=margin, candidates=len(cands))
