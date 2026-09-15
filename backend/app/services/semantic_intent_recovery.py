"""Conditional semantic intent recovery — meaning match when the fast path is weak.

Does not replace question_bank.match. Runs only when triggered.
Preserves HC-wrong=0 via margin + agreement gates.

FROZEN 2026-09-12: bug-fix only. Do not retune weights / thresholds / aliases
for score chasing. See reports/INTENT_LAYER_FREEZE.json.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional

from rapidfuzz import fuzz

from app.services.domain_terms import normalize_for_matching
from app.services.intent_profile import intent_agreement, intent_meaning_ok
from app.services.question_bank import (
    BankMatch,
    STRONG_THRESHOLD,
    WEAK_THRESHOLD,
    _content_tokens,
    detect_intent,
    question_bank,
)
from app.services.semantic_intent_index import semantic_intent_index
from app.services.technical_term_repair import repair_technical_terms

logger = logging.getLogger(__name__)

# Hybrid weights (dev-tuned; not lowered global thresholds).
_W_SEM = 0.34
_W_LEX = 0.22
_W_KW = 0.10
_W_ACT = 0.12
_W_DIST = 0.12
_W_EXIST = 0.18

# Reranker observability (Phase 7): trigger rate must stay low without
# changing when the reranker is allowed to run.
_RERANK_STATS: dict[str, int] = {
    "calls": 0,
    "triggered": 0,
    "vector_reuse": 0,
    "embedded": 0,
}


def rerank_stats() -> dict[str, float]:
    calls = max(1, _RERANK_STATS["calls"])
    return {
        **_RERANK_STATS,
        "reranker_trigger_rate": round(_RERANK_STATS["triggered"] / calls, 4),
    }


def reset_rerank_stats() -> None:
    for key in _RERANK_STATS:
        _RERANK_STATS[key] = 0


_MIN_ACCEPT = 0.58
_MIN_STRONG_AGREE = 0.62
_MIN_MARGIN = 0.045
_CLOSE_RERANK = 0.05
_THIN_MARGIN = 0.06


@dataclass
class SemanticRecoveryDecision:
    match: Optional[BankMatch]
    applied: bool
    reason: str
    triggered: bool = False
    semantic_top5: list[dict] = field(default_factory=list)
    hybrid_top5: list[dict] = field(default_factory=list)
    agreement: float = 0.0
    margin: float = 0.0
    reranker_used: bool = False
    latency_ms: float = 0.0
    rerank_ms: float = 0.0
    embedding_ms: float = 0.0
    search_ms: float = 0.0
    abstain_reason: Optional[str] = None


def _content_len(text: str) -> int:
    return len(_content_tokens(normalize_for_matching(text)))


def _query_distinctive(normalized: str, content: list[str]) -> set[str]:
    from app.services.intent_profile import _PROFILE_DISTINCTIVE

    bag = set(content) | set(normalized.split())
    hits: set[str] = set()
    for term in _PROFILE_DISTINCTIVE:
        if term in bag or term in normalized:
            # normalize multiword
            hits.add(term.replace(" ", "").replace("-", ""))
    return hits


def should_trigger_semantic_recovery(
    text: str,
    current: Optional[BankMatch],
) -> tuple[bool, str]:
    """Return (trigger, reason). Fast path: no trigger when strong + agrees."""
    raw = (text or "").strip()
    if not raw:
        return False, "empty"

    repaired = repair_technical_terms(raw)
    norm = normalize_for_matching(repaired)
    content = _content_tokens(norm)
    n_content = len(content)

    # Bare continuers must keep the remembered topic entry. Re-ranking "Why?"
    # / "How?" via semantic recovery previously swapped in unrelated strong/weak
    # intents (e.g. chroma) and created confident-wrong risk on the live path.
    if current is not None and norm in {
        "why",
        "how",
        "when",
        "where",
        "example",
        "more",
        "else",
        "continue",
        "and why",
        "and how",
        "how so",
        "why though",
    }:
        return False, "bare_continuer_keep"

    agreement = 0.0
    if current is not None:
        profile = semantic_intent_index.get(current.entry.id)
        agreement = intent_agreement(current.entry, repaired, profile=profile)
        margin = float(current.score) - float(current.runner_up_score or 0.0)
        if current.runner_up is None:
            margin = float(current.score)
        # Before MiniLM warm, bank demotes strong→weak; still skip recovery when
        # the lexical hit clearly agrees with the spoken question.
        effective_strong = current.mode == "strong" or (
            float(current.score) >= STRONG_THRESHOLD
            and agreement >= 0.70
            and n_content <= 8
        )
        if effective_strong and agreement >= 0.70 and margin >= _THIN_MARGIN:
            return False, "strong_agrees"

    # Weak / missing
    if current is None:
        return True, "no_match"
    if current.mode != "strong" and not (
        float(current.score) >= STRONG_THRESHOLD and agreement >= 0.70 and n_content <= 8
    ):
        return True, "weak_match"

    margin = float(current.score) - float(current.runner_up_score or 0.0)
    if current.runner_up and margin < _THIN_MARGIN:
        return True, "thin_margin"

    # Short + distinctive
    if n_content <= 4 and _query_distinctive(norm, content):
        if agreement < 0.75:
            return True, "short_distinctive"

    # Paraphrase suspected: spoken much longer than bank Q, low agreement
    bank_q_len = _content_len(current.entry.question)
    if n_content >= bank_q_len + 4 and agreement < 0.70 and current.score >= 0.55:
        return True, "paraphrase_suspected"

    # Action-type mismatch
    q_intent = detect_intent(norm)
    profile = semantic_intent_index.get(current.entry.id)
    if (
        q_intent
        and profile
        and profile.action_type
        and q_intent != profile.action_type
        and frozenset({q_intent, profile.action_type})
        not in {
            frozenset({"describe", "definition"}),
            frozenset({"describe", "how"}),
            frozenset({"how", "compare"}),
        }
    ):
        return True, "action_mismatch"

    if agreement < 0.55 and current.score >= 0.70:
        return True, "strong_low_agreement"

    return False, "not_needed"


# ── per-entry static strings (PERF: built once per bank load) ──────────────
#
# Every value below is exactly what the inline code recomputed on each call;
# only the repeated regex-normalization / string joining is removed.
_ENTRY_STATIC: dict[tuple[int, str], dict] = {}
_ENTRY_STATIC_GEN = -1


def _bank_generation() -> int:
    return int(getattr(question_bank, "generation", 0) or 0)


def _entry_static(entry) -> dict:
    global _ENTRY_STATIC_GEN
    gen = _bank_generation()
    if gen != _ENTRY_STATIC_GEN:
        _ENTRY_STATIC.clear()
        _ENTRY_STATIC_GEN = gen
    key = (gen, entry.id)
    hit = _ENTRY_STATIC.get(key)
    if hit is not None:
        return hit
    alias_norms = tuple(
        a
        for a in (
            normalize_for_matching(alias)
            for alias in (entry.aliases[:10] or (entry.question,))
        )
        if a
    )
    static = {
        "alias_norms": alias_norms,
        "kw_norms": tuple(normalize_for_matching(k) for k in (entry.keywords or ()) if k),
        "kw_count": len(entry.keywords or ()),
        "conflict_blob": " ".join(
            [entry.id, entry.topic, entry.question, " ".join(entry.keywords or ())]
        ).lower(),
    }
    _ENTRY_STATIC[key] = static
    return static


def _profile_blob_norm(profile, limit: int) -> str:
    """Normalized profile blob prefix, memoized per (intent, limit)."""
    gen = _bank_generation()
    key = (gen, profile.intent_id, limit)
    hit = _PROFILE_BLOB_NORM.get(key)
    if hit is None:
        if gen != _PROFILE_BLOB_GEN[0]:
            _PROFILE_BLOB_NORM.clear()
            _PROFILE_BLOB_GEN[0] = gen
        hit = normalize_for_matching((profile.profile_blob or "")[:limit])
        _PROFILE_BLOB_NORM[key] = hit
    return hit


_PROFILE_BLOB_NORM: dict[tuple[int, str, int], str] = {}
_PROFILE_BLOB_GEN = [-1]
_PROFILE_BLOB_LOWER: dict[tuple[int, str], str] = {}
_PROFILE_OWNED_TERMS: dict[tuple[int, str], frozenset] = {}


def _profile_blob_lower(profile) -> str:
    key = (_bank_generation(), profile.intent_id)
    hit = _PROFILE_BLOB_LOWER.get(key)
    if hit is None:
        hit = (profile.profile_blob or profile.canonical_question or "").lower()
        _PROFILE_BLOB_LOWER[key] = hit
    return hit


def _profile_owned_terms(profile) -> frozenset:
    key = (_bank_generation(), profile.intent_id)
    hit = _PROFILE_OWNED_TERMS.get(key)
    if hit is None:
        hit = frozenset(
            t.replace(" ", "").replace("-", "") for t in profile.distinctive_terms
        )
        _PROFILE_OWNED_TERMS[key] = hit
    return hit


def _alias_lex(query_norm: str, content: list[str], entry) -> float:
    content_text = " ".join(content) or query_norm
    best = 0.0
    for a in _entry_static(entry)["alias_norms"]:
        best = max(best, fuzz.token_set_ratio(content_text, a) / 100.0)
    return best


def _keyword_score(normalized: str, entry) -> float:
    static = _entry_static(entry)
    kw_count = static["kw_count"]
    if not kw_count:
        return 0.0
    # NOTE: mirrors the original `if k and normalize_for_matching(k) in normalized`
    # exactly — raw-empty keywords are dropped at build time, normalized-empty
    # ones are kept (an empty string is "in" everything, as before).
    hits = sum(1 for k in static["kw_norms"] if k in normalized)
    return min(1.0, hits / max(1.0, min(2.0, float(kw_count))))


def _action_align(q_intent: Optional[str], profile_action: Optional[str]) -> float:
    if not q_intent or not profile_action:
        return 0.5
    if q_intent == profile_action:
        return 1.0
    if frozenset({q_intent, profile_action}) in {
        frozenset({"describe", "definition"}),
        frozenset({"describe", "how"}),
        frozenset({"how", "compare"}),
        frozenset({"describe", "experience"}),
    }:
        return 0.7
    return 0.15


def _distinctive_score(q_hits: set[str], profile_terms: tuple[str, ...], entry_id: str) -> float:
    if not q_hits:
        return 0.4
    owned = {t.replace(" ", "").replace("-", "") for t in profile_terms}
    owned |= {p for p in entry_id.lower().replace(".", " ").split()}
    overlap = len(q_hits & owned)
    if overlap:
        return min(1.0, 0.45 + 0.25 * overlap)
    # Penalty when query has distinctive terms the entry does not own
    return 0.05


def _granularity_penalty(q_intent: Optional[str], entry_id: str, profile_action: Optional[str]) -> float:
    """Prefer how/why/compare entries over bare definitions when query asks how/why."""
    if q_intent in {"how", "why", "compare"} and (
        "what_is" in entry_id or entry_id.endswith("_what") or profile_action == "definition"
    ):
        return 0.18
    if q_intent == "definition" and profile_action in {"how", "why"} and "what_is" not in entry_id:
        return 0.06
    # Prefer empty-retrieval / abstain intents when query asks what to do with thin context.
    return 0.0


def _conflict_penalty(normalized: str, entry) -> float:
    """Negative evidence: e.g. similarity+no LLM should not pick RAG generation."""
    pen = 0.0
    blob = _entry_static(entry)["conflict_blob"]
    if "similarity" in normalized and ("no llm" in normalized or "instead of an llm" in normalized or "without" in normalized and "llm" in normalized):
        if "rag" in blob and "similarity" not in blob and "similarity" not in entry.id:
            pen += 0.20
    if "whisper" in normalized or "voice" in normalized:
        if "helpdesk" in blob and "whisper" not in blob and "kiosk" not in blob:
            pen += 0.15
    if "langgraph" in normalized and ("complex" in normalized or "workflow" in normalized or "help" in normalized):
        if "what_is_langgraph" in entry.id:
            pen += 0.16
        if "plain_python_still_agentic" in entry.id and "langgraph" in normalized and "help" in normalized:
            pen += 0.12
    if (
        ("retrieval" in normalized or "retrieved" in normalized)
        and ("nothing" in normalized or "enough" in normalized or "empty" in normalized or "not contain" in normalized)
    ):
        if "finance" in entry.id or "wrong_info" in entry.id:
            pen += 0.12
        if "empty_retrieval" in entry.id or "abstain" in entry.id:
            pen -= 0.05  # small bonus via negative penalty
    if "human approval" in normalized or ("approval" in normalized and "important" in normalized):
        if "hallucination_prevent" in entry.id or "hitl" in entry.id or "human" in blob or "approval" in blob:
            pen -= 0.08
        if "wer" in entry.id or "transcription" in entry.id:
            pen += 0.10
        if "hallucination_prevent" in entry.id:
            pen -= 0.06
    if "rag" in normalized and ("retriev" in normalized) and ("generat" in normalized or "language model" in normalized):
        if entry.id.endswith("rag_what") or entry.id == "tech.rag_what":
            pen += 0.12
        if "rag_two_phases" in entry.id or "rag_build" in entry.id or "how" in entry.question.lower():
            pen -= 0.05
    return pen

def _lexical_expand_candidates(norm: str, content: list[str], *, limit: int = 12) -> list[str]:
    """Scan profiles/aliases when embedding index is cold or bank top-k is thin."""
    profiles = semantic_intent_index.profiles()
    content_text = " ".join(content) or norm
    content_set = set(content)
    # Cheap prefilter: keep entries that share a content token or distinctive term.
    q_dist = _query_distinctive(norm, content)
    scored: list[tuple[float, str]] = []
    long_toks = [tok for tok in content_set if len(tok) >= 4]
    for pid, profile in profiles.items():
        entry = question_bank.get(pid)
        if entry is None:
            continue
        blob_l = _profile_blob_lower(profile)
        if content_set and not any(tok in blob_l for tok in long_toks):
            if q_dist:
                owned = _profile_owned_terms(profile)
                if not (q_dist & owned):
                    continue
            else:
                continue
        lex = _alias_lex(norm, content, entry)
        if lex < 0.35:
            # Skip expensive blob fuzz when alias lex is hopeless.
            blob_n = _profile_blob_norm(profile, 220)
            if not blob_n:
                continue
            blob_score = fuzz.token_set_ratio(content_text, blob_n) / 100.0
            if blob_score < 0.40:
                continue
            score = 0.85 * blob_score
        else:
            blob_n2 = (
                _profile_blob_norm(profile, 280)
                if profile.profile_blob
                else normalize_for_matching(profile.canonical_question)
            )
            blob_score = fuzz.token_set_ratio(content_text, blob_n2) / 100.0
            partial = (
                fuzz.partial_ratio(norm, blob_n2) / 100.0
                if len(norm) >= 20
                else 0.0
            )
            score = max(lex, 0.85 * blob_score, 0.80 * partial)
        if score >= 0.42:
            scored.append((score, pid))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [pid for _, pid in scored[:limit]]


# Profile-blob lexical proxy for the `sem` slot.
#   "auto"   (default, v4 step 2 conservative):
#            • cold index → proxy fills `sem` for both ranking and apply (legacy)
#            • warm index → ranking uses real cosine only; apply still uses the
#              legacy blob fill so already-successful recovery applies do not flip
#   "always" pre-v4 behaviour — proxy for every non-retrieved candidate
#   "never"  proxy disabled outright, even on a cold index
# Kept as a switch so the change can be reverted or A/B-ed without editing code.
SEMANTIC_BLOB_PROXY = os.getenv("SEMANTIC_BLOB_PROXY", "auto").strip().lower()

# v4 step 3 — when recovering the same intent as `current`, fold current.score
# into the recovered score floor. Toggle exists only so step-3 measurement can
# A/B the pre-fix behaviour without editing the apply gate.
SCORE_FLOOR_INCLUDE_CURRENT = os.getenv(
    "SCORE_FLOOR_INCLUDE_CURRENT", "1"
).strip().lower() not in {"0", "false", "no", "off"}

# v4 step 4 — conservative apply from true-cosine ranking when legacy (blob)
# apply abstains. Special-path gates only; does not change _MIN_ACCEPT /
# _MIN_ANSWER_SCORE / strong thresholds. Forced weak mode → HC risk stays 0.
CONSERVATIVE_RANK_APPLY = os.getenv(
    "CONSERVATIVE_RANK_APPLY", "1"
).strip().lower() not in {"0", "false", "no", "off"}
_CONSERVATIVE_RANK_MIN_FINAL = 0.45
_CONSERVATIVE_RANK_MIN_AGREE = 0.88


def _blob_proxy_mode() -> str:
    return (SEMANTIC_BLOB_PROXY or "auto").strip().lower()


def _split_rank_apply_scores() -> bool:
    """Warm+auto: expose true-cosine hybrid ranking without changing apply."""
    return _blob_proxy_mode() == "auto" and (semantic_intent_index.ready)


def _legacy_blob_sem(norm: str, content: list[str], profile) -> float:
    """Pre-v4 profile-blob lexical stand-in for a missing cosine."""
    if profile is None or not profile.profile_blob:
        return 0.0
    blob_n = _profile_blob_norm(profile, 360)
    if not blob_n:
        return 0.0
    return max(
        fuzz.token_set_ratio(" ".join(content) or norm, blob_n) / 100.0 * 0.9,
        fuzz.partial_ratio(norm, blob_n) / 100.0 * 0.85 if len(norm) >= 18 else 0.0,
    )


def _try_conservative_rank_apply(
    *,
    scored_rank: list[tuple[float, str, dict]],
    semantic_top5: list[dict],
    repaired: str,
    current: Optional[BankMatch],
    existing: dict,
    norm: str,
    content: list[str],
    sem_scores: dict[str, float],
) -> Optional[BankMatch]:
    """
    Step-4 safe convert: only when embedding #1 == hybrid-rank #1, agreement and
    final are high, meaning_ok holds, and current is not already strong.
    Always returns weak mode (never strong) so HC risk cannot rise here.
    """
    if not CONSERVATIVE_RANK_APPLY or not scored_rank or not semantic_top5:
        return None
    if current is not None and current.mode == "strong":
        return None
    best_score, best_id, _detail = scored_rank[0]
    if semantic_top5[0].get("id") != best_id:
        return None
    if best_score < _CONSERVATIVE_RANK_MIN_FINAL:
        return None
    second = scored_rank[1][0] if len(scored_rank) > 1 else 0.0
    if best_score - second < _MIN_MARGIN:
        return None
    entry = question_bank.get(best_id)
    if entry is None:
        return None
    profile = semantic_intent_index.get(best_id)
    agreement = intent_agreement(entry, repaired, profile=profile)
    if agreement < _CONSERVATIVE_RANK_MIN_AGREE:
        return None
    ok, _ = intent_meaning_ok(
        entry,
        repaired,
        match_score=float(best_score),
        profile=profile,
        agreement=agreement,
    )
    if not ok:
        return None
    exist_m = existing.get(best_id)
    floor = float(exist_m.score) if exist_m else 0.0
    if (
        SCORE_FLOOR_INCLUDE_CURRENT
        and current is not None
        and current.entry.id == best_id
    ):
        floor = max(floor, float(current.score))
    return BankMatch(
        entry=entry,
        score=max(floor, float(best_score)),
        semantic=float(exist_m.semantic) if exist_m else float(sem_scores.get(best_id, 0.0)),
        lexical=float(exist_m.lexical) if exist_m else _alias_lex(norm, content, entry),
        keyword=float(exist_m.keyword) if exist_m else _keyword_score(norm, entry),
        alias=exist_m.alias if exist_m else entry.question,
        mode="weak",  # HC: never promote to strong on this path
        runner_up=scored_rank[1][1] if len(scored_rank) > 1 else None,
        runner_up_score=float(second) if len(scored_rank) > 1 else 0.0,
    )


def _embedder_ready() -> bool:
    """True only if MiniLM is already loaded — never trigger a blocking load here."""
    return getattr(question_bank, "_embedder", None) is not None and not getattr(
        question_bank, "_embedder_failed", False
    )


def _ultra_short_distinctive_gate(
    content: list[str],
    q_hits: set[str],
    scored: list[tuple[float, str, dict]],
) -> Optional[str]:
    """
    Phase 3: for ultra-short distinctive queries, require one family to dominate.
    Returns abstain reason or None if OK to accept #1.
    """
    if len(content) > 3 or not q_hits or len(scored) < 2:
        return None
    best_score, best_id, _ = scored[0]
    second_score, second_id, _ = scored[1]
    margin = best_score - second_score

    def _family(eid: str) -> set[str]:
        entry = question_bank.get(eid)
        if entry is None:
            return set()
        blob = " ".join([eid, entry.topic, entry.question, " ".join(entry.keywords or ())])
        return set(_query_distinctive(normalize_for_matching(blob), _content_tokens(normalize_for_matching(blob))))

    best_f = _family(best_id) & q_hits
    second_f = _family(second_id) & q_hits
    # Two different families both claim the distinctive term → abstain unless clear margin.
    if best_f and second_f and best_f != second_f and margin < 0.08:
        return "ultra_short_ambiguous_family"
    if not best_f and margin < 0.10:
        return "ultra_short_no_family"
    return None


def recover_semantic_intent(
    text: str,
    current: Optional[BankMatch],
    *,
    conversation_history: Optional[Iterable[dict]] = None,
    precomputed_sem_hits: Optional[list] = None,
    precomputed_trigger: Optional[tuple[bool, str]] = None,
) -> SemanticRecoveryDecision:
    """
    `precomputed_trigger` (PERF): callers that already ran
    `should_trigger_semantic_recovery(text, current)` pass the identical
    (trigger, reason) tuple instead of paying for a second
    repair + normalize + intent_agreement pass. Same decision either way.
    """
    t0 = time.perf_counter()
    if precomputed_trigger is not None:
        trigger, trigger_reason = precomputed_trigger
    else:
        trigger, trigger_reason = should_trigger_semantic_recovery(text, current)
    if not trigger:
        agreement = 0.0
        margin = 0.0
        if current is not None:
            repaired = repair_technical_terms(text or "")
            profile = semantic_intent_index.get(current.entry.id)
            agreement = intent_agreement(current.entry, repaired, profile=profile)
            margin = float(current.score) - float(current.runner_up_score or 0.0)
            if current.runner_up is None:
                margin = float(current.score)
        return SemanticRecoveryDecision(
            match=current,
            applied=False,
            reason=trigger_reason,
            triggered=False,
            agreement=agreement,
            margin=margin,
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )

    _RERANK_STATS["calls"] += 1
    semantic_intent_index.ensure_loaded()
    # Do not block the hot path on embedder warm-up; cosine is optional.
    t_rep = time.perf_counter()
    repaired = repair_technical_terms(
        text,
        prior_topic=question_bank.topic_for_history(conversation_history),
    )
    repair_ms = (time.perf_counter() - t_rep) * 1000
    del repair_ms  # folded into search path; kept timed for future split
    norm = normalize_for_matching(repaired)
    content = _content_tokens(norm)
    q_intent = detect_intent(norm)
    q_hits = _query_distinctive(norm, content)

    t_lex = time.perf_counter()
    # Latency-cut: if current match is already usable, skip full-bank top_matches(8).
    existing: dict = {}
    if current is not None and float(current.score) >= 0.70 and current.runner_up is not None:
        existing[current.entry.id] = current
    else:
        existing = {
            m.entry.id: m
            for m in question_bank.top_matches(
                repaired,
                top_k=8,
                conversation_history=conversation_history,
            )
        }
        if current is not None:
            existing[current.entry.id] = current
    lex_ms = (time.perf_counter() - t_lex) * 1000

    t_emb = time.perf_counter()
    if precomputed_sem_hits is not None:
        sem_hits = list(precomputed_sem_hits)
    else:
        sem_hits = semantic_intent_index.top_k(repaired, k=5) if semantic_intent_index.ready else []
    embedding_ms = (time.perf_counter() - t_emb) * 1000
    search_ms = embedding_ms + lex_ms
    semantic_top5 = [
        {"id": h.intent_id, "score": round(h.score, 3)} for h in sem_hits
    ]
    sem_scores = {h.intent_id: h.score for h in sem_hits}

    lexical_extra: list[str] = []
    # Full-bank lexical expand is for short/medium paraphrases — skip on long compounds
    # and when the current match is already strong (Latency-cut).
    cur_strong = (
        current is not None
        and current.mode == "strong"
        and float(current.score) >= STRONG_THRESHOLD
    )
    if len(content) <= 36 and not cur_strong:
        lexical_extra = _lexical_expand_candidates(norm, content, limit=12)
    # Topic siblings of current / top existing — helps granularity swaps.
    sibling_ids: list[str] = []
    seed_ids = [*(existing.keys()), *(lexical_extra[:3])]
    for sid in seed_ids:
        prof = semantic_intent_index.get(sid)
        if prof and prof.related_intents:
            sibling_ids.extend(prof.related_intents[:8])

    candidate_ids = list(
        dict.fromkeys(
            [
                *existing.keys(),
                *[h.intent_id for h in sem_hits],
                *lexical_extra,
                *sibling_ids,
            ]
        )
    )
    scored: list[tuple[float, str, dict]] = []
    scored_apply: list[tuple[float, str, dict]] = []
    split_rank_apply = _split_rank_apply_scores()
    mode = _blob_proxy_mode()

    for cid in candidate_ids:
        entry = question_bank.get(cid)
        if entry is None:
            continue
        profile = semantic_intent_index.get(cid)
        exist_m = existing.get(cid)
        exist_score = float(exist_m.score) if exist_m else 0.0
        sem_real = float(sem_scores.get(cid, 0.0))
        lex = _alias_lex(norm, content, entry)
        # BUG FIX (v4 step 2 — hybrid ranking, conservative).
        #
        # The `sem <= 0` blob fill was meant for a cold index, but also fired for
        # every warm non-retrieved candidate and polluted the heaviest blend slot.
        #
        # Unsafe first cut (`auto` = never fill when warm) improved ranking but
        # flipped applied intents on passing clips and created strong+non-gold.
        #
        # Conservative cut kept here:
        #   • hybrid_top5 / ranking → real cosine only when warm+auto
        #   • apply decision       → legacy blob fill (identical to pre-v4 apply)
        # No weight, threshold, alias, or accept-gate change.
        blob_sem = 0.0
        if sem_real <= 0.0:
            if mode == "never":
                blob_sem = 0.0
            elif mode == "always" or not semantic_intent_index.ready:
                blob_sem = _legacy_blob_sem(norm, content, profile)
            elif split_rank_apply:
                blob_sem = _legacy_blob_sem(norm, content, profile)
            else:
                blob_sem = 0.0

        if split_rank_apply:
            sem_rank = sem_real
            sem_apply = sem_real if sem_real > 0.0 else blob_sem
        elif mode == "never":
            sem_rank = sem_real
            sem_apply = sem_real
        else:
            # always, or auto+cold: legacy single path
            filled = sem_real if sem_real > 0.0 else blob_sem
            sem_rank = filled
            sem_apply = filled

        kw = _keyword_score(norm, entry)
        act = _action_align(q_intent, profile.action_type if profile else None)
        dist = _distinctive_score(
            q_hits,
            profile.distinctive_terms if profile else (),
            entry.id,
        )
        pen = _conflict_penalty(norm, entry) + _granularity_penalty(
            q_intent, entry.id, profile.action_type if profile else None
        )
        # Ultra-short: only distinctive-dominant families may climb.
        if len(content) <= 3 and q_hits:
            if dist < 0.4:
                pen += 0.18

        def _blend(sem: float) -> float:
            return (
                _W_SEM * sem
                + _W_LEX * lex
                + _W_KW * kw
                + _W_ACT * act
                + _W_DIST * dist
                + _W_EXIST * min(1.0, exist_score)
                - pen
            )

        final_rank = _blend(sem_rank)
        detail_rank = {
            "id": cid,
            "final": round(final_rank, 3),
            "sem": round(sem_rank, 3),
            "lex": round(lex, 3),
            "kw": round(kw, 3),
            "act": round(act, 3),
            "dist": round(dist, 3),
            "exist": round(exist_score, 3),
            "penalty": round(pen, 3),
        }
        scored.append((final_rank, cid, detail_rank))

        if split_rank_apply and abs(sem_apply - sem_rank) > 1e-12:
            final_apply = _blend(sem_apply)
            detail_apply = {
                "id": cid,
                "final": round(final_apply, 3),
                "sem": round(sem_apply, 3),
                "lex": round(lex, 3),
                "kw": round(kw, 3),
                "act": round(act, 3),
                "dist": round(dist, 3),
                "exist": round(exist_score, 3),
                "penalty": round(pen, 3),
            }
            scored_apply.append((final_apply, cid, detail_apply))
        else:
            scored_apply.append((final_rank, cid, detail_rank))

    def _thin_margin_swap(rows: list[tuple[float, str, dict]]) -> None:
        if len(rows) < 2 or (rows[0][0] - rows[1][0]) > 0.02:
            return
        e0 = question_bank.get(rows[0][1])
        e1 = question_bank.get(rows[1][1])
        if e0 is None or e1 is None:
            return
        a0 = intent_agreement(
            e0, repaired, profile=semantic_intent_index.get(rows[0][1])
        )
        a1 = intent_agreement(
            e1, repaired, profile=semantic_intent_index.get(rows[1][1])
        )
        sem0 = float(rows[0][2].get("sem") or 0.0)
        sem1 = float(rows[1][2].get("sem") or 0.0)
        if (a1 >= a0 + 0.04 and a1 >= 0.70) or (
            abs(a1 - a0) <= 0.05 and sem1 >= sem0 + 0.04 and a1 >= 0.70
        ):
            rows[0], rows[1] = rows[1], rows[0]

    scored.sort(key=lambda x: x[0], reverse=True)
    scored_apply.sort(key=lambda x: x[0], reverse=True)
    # Thin-margin paraphrase: prefer near-#2 when it agrees more with spoken text
    # (or has clearly stronger semantic proxy) — no global weight retune.
    _thin_margin_swap(scored)
    if split_rank_apply:
        _thin_margin_swap(scored_apply)
    else:
        scored_apply = scored
    hybrid_top5 = [d for _, _, d in scored[:5]]
    hybrid_top5_rank = hybrid_top5  # freeze true-cosine ranking for step-2 observability

    if not scored:
        return SemanticRecoveryDecision(
            match=current,
            applied=True,
            reason="no_semantic_candidates",
            triggered=True,
            semantic_top5=semantic_top5,
            hybrid_top5=[],
            abstain_reason="no_candidates",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )

    # Apply path uses legacy (blob-filled) order when split; ranking already captured.
    scored_rank = list(scored)
    if split_rank_apply:
        scored = scored_apply

    # Optional MiniLM re-rank when leaders are close — only if embedder already warm.
    reranker_used = False
    rerank_ms = 0.0
    if (
        _embedder_ready()
        and len(scored) >= 2
        and abs(scored[0][0] - scored[1][0]) <= _CLOSE_RERANK
    ):
        t_rr = time.perf_counter()
        _RERANK_STATS["triggered"] += 1
        top_n = scored[: min(5, len(scored))]
        blobs = []
        cached_vecs: list = []
        for _, cid, _ in top_n:
            p = semantic_intent_index.get(cid)
            if p:
                blobs.append(p.profile_blob)
                cached_vecs.append(semantic_intent_index.vector_for(cid))
            else:
                entry = question_bank.get(cid)
                blobs.append(entry.question if entry is not None else cid)
                cached_vecs.append(None)
        # PERF: the profile-blob vectors are exactly the rows of the semantic
        # index matrix, and the query vector is cached by question_bank — so the
        # common case needs no ONNX call at all.
        # NOTE: the original embedded `repaired` RAW (not normalized) here —
        # keep that exact input or the re-rank cosines change.
        qv_cached = question_bank._query_vector(repaired)  # noqa: SLF001
        if qv_cached is not None and all(v is not None for v in cached_vecs):
            import numpy as _np

            vecs = _np.vstack([qv_cached, *cached_vecs])
            _RERANK_STATS["vector_reuse"] += 1
        else:
            vecs = question_bank._embed([repaired, *blobs])  # noqa: SLF001
            _RERANK_STATS["embedded"] += 1
        if vecs is not None and len(vecs) == 1 + len(blobs):
            qv = vecs[0]
            reranked = []
            for i, (final, cid, detail) in enumerate(top_n):
                cos = float(qv @ vecs[i + 1])
                blended = 0.65 * final + 0.35 * cos
                d2 = dict(detail)
                d2["rerank_cos"] = round(cos, 3)
                d2["final"] = round(blended, 3)
                reranked.append((blended, cid, d2))
            reranked.sort(key=lambda x: x[0], reverse=True)
            scored = reranked + scored[len(top_n) :]
            if not split_rank_apply:
                hybrid_top5 = [d for _, _, d in scored[:5]]
            reranker_used = True
        rerank_ms = (time.perf_counter() - t_rr) * 1000

    if split_rank_apply:
        hybrid_top5 = hybrid_top5_rank

    best_score, best_id, best_detail = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    margin = best_score - second_score
    entry = question_bank.get(best_id)
    if entry is None:
        return SemanticRecoveryDecision(
            match=current,
            applied=True,
            reason="missing_entry",
            triggered=True,
            semantic_top5=semantic_top5,
            hybrid_top5=hybrid_top5,
            abstain_reason="missing_entry",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )

    profile = semantic_intent_index.get(best_id)
    agreement = intent_agreement(entry, repaired, profile=profile)

    # High agreement can rescue a slightly soft hybrid score (paraphrase cases).
    accept_floor = _MIN_ACCEPT
    if agreement >= 0.70:
        accept_floor = min(_MIN_ACCEPT, 0.52)
    if agreement >= 0.78:
        accept_floor = min(accept_floor, 0.48)
    if agreement >= 0.85:
        accept_floor = min(accept_floor, 0.46)

    ultra_abstain = _ultra_short_distinctive_gate(content, q_hits, scored)
    if ultra_abstain:
        out = current
        if current is not None and current.mode == "strong" and agreement < 0.70:
            out = BankMatch(
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
        return SemanticRecoveryDecision(
            match=out,
            applied=True,
            reason="abstain_ultra_short",
            triggered=True,
            semantic_top5=semantic_top5,
            hybrid_top5=hybrid_top5,
            agreement=agreement,
            margin=margin,
            reranker_used=reranker_used,
            abstain_reason=ultra_abstain,
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            rerank_ms=round(rerank_ms, 1),
            embedding_ms=round(embedding_ms, 1),
            search_ms=round(search_ms, 1),
        )

    # Confidence gate — never force #1.
    if best_score < accept_floor or agreement < 0.48:
        cons = _try_conservative_rank_apply(
            scored_rank=scored_rank,
            semantic_top5=semantic_top5,
            repaired=repaired,
            current=current,
            existing=existing,
            norm=norm,
            content=content,
            sem_scores=sem_scores,
        )
        if cons is not None:
            cons_agree = intent_agreement(
                cons.entry, repaired, profile=semantic_intent_index.get(cons.entry.id)
            )
            return SemanticRecoveryDecision(
                match=cons,
                applied=True,
                reason=f"recovered:conservative_rank:{trigger_reason}",
                triggered=True,
                semantic_top5=semantic_top5,
                hybrid_top5=hybrid_top5,
                agreement=cons_agree,
                margin=float(cons.score) - float(cons.runner_up_score or 0.0),
                reranker_used=reranker_used,
                latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                rerank_ms=round(rerank_ms, 1),
                embedding_ms=round(embedding_ms, 1),
                search_ms=round(search_ms, 1),
            )
        # Demote current strong if low agreement (HC protection).
        out = current
        if current is not None and current.mode == "strong" and intent_agreement(current.entry, repaired) < 0.55:
            out = BankMatch(
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
        return SemanticRecoveryDecision(
            match=out,
            applied=True,
            reason="abstain_low_confidence",
            triggered=True,
            semantic_top5=semantic_top5,
            hybrid_top5=hybrid_top5,
            agreement=agreement,
            margin=margin,
            reranker_used=reranker_used,
            abstain_reason=f"score={best_score:.3f} agree={agreement:.3f}",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            rerank_ms=round(rerank_ms, 1),
            embedding_ms=round(embedding_ms, 1),
            search_ms=round(search_ms, 1),
        )

    if margin < _MIN_MARGIN and agreement < 0.72:
        # Clear paraphrase agreement still wins a weak recovery.
        if not (agreement >= 0.75 and best_score >= 0.55):
            cons = _try_conservative_rank_apply(
                scored_rank=scored_rank,
                semantic_top5=semantic_top5,
                repaired=repaired,
                current=current,
                existing=existing,
                norm=norm,
                content=content,
                sem_scores=sem_scores,
            )
            if cons is not None:
                cons_agree = intent_agreement(
                    cons.entry, repaired, profile=semantic_intent_index.get(cons.entry.id)
                )
                return SemanticRecoveryDecision(
                    match=cons,
                    applied=True,
                    reason=f"recovered:conservative_rank:{trigger_reason}",
                    triggered=True,
                    semantic_top5=semantic_top5,
                    hybrid_top5=hybrid_top5,
                    agreement=cons_agree,
                    margin=float(cons.score) - float(cons.runner_up_score or 0.0),
                    reranker_used=reranker_used,
                    latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                    rerank_ms=round(rerank_ms, 1),
                    embedding_ms=round(embedding_ms, 1),
                    search_ms=round(search_ms, 1),
                )
            out = current
            if current is not None and current.mode == "strong":
                out = BankMatch(
                    entry=current.entry,
                    score=current.score,
                    semantic=current.semantic,
                    lexical=current.lexical,
                    keyword=current.keyword,
                    alias=current.alias,
                    mode="weak",
                    runner_up=best_id,
                    runner_up_score=second_score,
                )
            return SemanticRecoveryDecision(
                match=out,
                applied=True,
                reason="abstain_thin_margin",
                triggered=True,
                semantic_top5=semantic_top5,
                hybrid_top5=hybrid_top5,
                agreement=agreement,
                margin=margin,
                reranker_used=reranker_used,
                abstain_reason=f"margin={margin:.3f}",
                latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                rerank_ms=round(rerank_ms, 1),
                embedding_ms=round(embedding_ms, 1),
                search_ms=round(search_ms, 1),
            )

    mode = "weak"
    if best_score >= STRONG_THRESHOLD and agreement >= _MIN_STRONG_AGREE and margin >= _MIN_MARGIN:
        mode = "strong"
    elif best_score >= 0.72 and agreement >= 0.70 and margin >= 0.08:
        mode = "strong"
    elif agreement >= 0.78 and best_score >= WEAK_THRESHOLD and margin >= 0.06:
        mode = "strong"
    # Never strong when agreement is weak (HC protection).
    if agreement < 0.55:
        mode = "weak"
    # HC: never promote to strong when the spoken question has informative
    # long tokens that never appear on the entry surface. Inflated agreement
    # (answer-blob fuzz) previously made off-topic asks look "strong".
    if mode == "strong":
        long_q = {t for t in content if len(t) >= 6}
        if long_q:
            surface = normalize_for_matching(
                " ".join(
                    [
                        entry.id.replace(".", " ").replace("_", " "),
                        entry.question or "",
                        " ".join(entry.aliases or ()),
                        " ".join(entry.keywords or ()),
                        entry.topic or "",
                    ]
                )
            )
            if not any(tok in surface for tok in long_q):
                mode = "weak"
    # HC: benefit/help/value asks must not become strong on design/whiteboard
    # scenario intents just because aliases share "ministry"/"solution".
    if mode == "strong":
        spoken_benefit = bool(
            re.search(r"\b(help|helps|helped|benefit|value|impact|useful|roi)\b", norm)
        )
        spoken_design = bool(
            re.search(
                r"\b(design|architect|architecture|whiteboard|build|implement)\b",
                norm,
            )
        )
        entry_design = bool(
            re.search(
                r"\b(design|architect|architecture|whiteboard)\b",
                (entry.question or "").lower(),
            )
        ) or (entry.category or "").startswith("scenario")
        if spoken_benefit and not spoken_design and entry_design:
            mode = "weak"
    # HC: "invents/hallucinates" asks must not become strong on "I don't know"
    # / abstain-style intents — those are different meanings.
    if mode == "strong":
        spoken_halluc = bool(
            re.search(
                r"\b(invents?|invented|hallucin|fabricat|makes?\s+up|made\s+up)\b",
                norm,
            )
        )
        if spoken_halluc:
            eid = (entry.id or "").lower()
            eq = (entry.question or "").lower()
            surface = f"{eid} {eq}"
            halluc_family = bool(
                re.search(
                    r"\b(hallucin|invent|fabricat|ground|factual|validat|citation|"
                    r"prevent|wrong.?chunk|empty.?retriev)\b",
                    surface,
                )
            )
            dont_know_family = bool(
                re.search(r"(dont_know|don.?t know|too_often|i_dont_know)", surface)
            )
            if dont_know_family and not halluc_family:
                mode = "weak"

    exist_m = existing.get(best_id)
    # Score floor (v4 step 3): recovery must not lower the score of an intent
    # that was already the lexical current. `exist_m` can be a weaker top_matches
    # row (or absent on the strong-current fast path), so fold in current.score
    # when the recovered id is the same. No gate / threshold change.
    floor = float(exist_m.score) if exist_m else 0.0
    if (
        SCORE_FLOOR_INCLUDE_CURRENT
        and current is not None
        and current.entry.id == best_id
    ):
        floor = max(floor, float(current.score))
    recovered = BankMatch(
        entry=entry,
        score=max(floor, best_score),
        semantic=float(exist_m.semantic) if exist_m else float(sem_scores.get(best_id, 0.0)),
        lexical=float(exist_m.lexical) if exist_m else _alias_lex(norm, content, entry),
        keyword=float(exist_m.keyword) if exist_m else _keyword_score(norm, entry),
        alias=exist_m.alias if exist_m else entry.question,
        mode=mode,
        runner_up=scored[1][1] if len(scored) > 1 else None,
        runner_up_score=float(second_score) if len(scored) > 1 else 0.0,
    )

    decision = SemanticRecoveryDecision(
        match=recovered,
        applied=True,
        reason=f"recovered:{trigger_reason}",
        triggered=True,
        semantic_top5=semantic_top5,
        hybrid_top5=hybrid_top5,
        agreement=agreement,
        margin=margin,
        reranker_used=reranker_used,
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        rerank_ms=round(rerank_ms, 1),
        embedding_ms=round(embedding_ms, 1),
        search_ms=round(search_ms, 1),
    )
    logger.info(
        "SEMANTIC INTENT RECOVERY reason=%s id=%s mode=%s score=%.3f agree=%.3f "
        "margin=%.3f rerank=%s ms=%.1f top=%s",
        decision.reason,
        recovered.entry.id,
        recovered.mode,
        recovered.score,
        agreement,
        margin,
        reranker_used,
        decision.latency_ms,
        hybrid_top5[:3],
    )
    return decision
