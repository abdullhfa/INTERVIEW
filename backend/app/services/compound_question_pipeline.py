"""Multi-intent / compound question orchestration.

Simple questions stay on the existing single-intent path (detector only).
Compound / uncertain questions: decompose → wrap question_bank.match →
dedupe → ordered combined answer. No LLM by default.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional

from app.services.compound_answer_builder import build_compound_answer
from app.services.compound_question_decomposer import decompose_compound_question
from app.services.compound_question_detector import (
    ComplexityDetection,
    detect_question_complexity,
)
from app.services.question_bank import BankMatch, question_bank

logger = logging.getLogger(__name__)

# Accept a sub-question match for answer composition only when safe.
# Slightly below STRONG_THRESHOLD is OK when margin is clear — compound
# sub-questions often score 0.65–0.69 before embedding warm-up.
_MIN_ANSWER_SCORE = 0.58
_MIN_KEEP_SCORE = 0.52
_MIN_MARGIN = 0.025
_AMBIGUOUS_MARGIN = 0.015
_HARVEST_MIN_SCORE = 0.55

# V4 step 5 — Variant D trailing rescue: keep clause discriminator, carry
# prior-part subject, exclude parent/already-selected. Does NOT change
# _MIN_ANSWER_SCORE or other accept thresholds.
COMPOUND_VARIANT_D_RESCUE = os.getenv(
    "COMPOUND_VARIANT_D_RESCUE", "1"
).strip().lower() in ("1", "true", "yes", "on")

_PRONOUN_RE = re.compile(r"\b(one|it|that|them|those|this)\b", re.I)
_TRAILING_CLAUSE_RE = re.compile(
    r"^\s*(?:and\s+|then\s+)?"
    r"(?:say|tell me|point me to|give me|explain|describe)?\s*"
    r"(when|what do you do|what you do|which|how|whether|why)\b",
    re.I,
)


def _subject_of_question(question: str) -> str:
    """Head noun / topic phrase from a prior sub-question (subject carry)."""
    q = (question or "").strip().rstrip("?.").strip()
    m = re.search(
        r"\b(?:what is|what are|tell me what|explain what|describe|"
        r"point me to|give me|point me to)\s+"
        r"(?:an?\s+|the\s+|your\s+)?(.+)$",
        q,
        re.I,
    )
    return m.group(1).strip() if m else q


def _variant_d_rescue_match(
    clause: str,
    parent: BankMatch,
    exclude: set[str],
    *,
    conversation_history: Optional[Iterable[dict]] = None,
) -> Optional[BankMatch]:
    """
    Variant D: rank on the trailing clause (discriminator kept), soft-filter
    to the parent topic, substitute pronouns with the prior subject, and
    never re-accept the parent / already-selected intents.
    """
    topic = parent.entry.topic
    subject = _subject_of_question(parent.entry.question)
    resolved = (
        _PRONOUN_RE.sub(subject, clause, count=1) if subject else clause
    )
    probes: list[BankMatch] = []
    for text in dict.fromkeys([clause, resolved]):
        if not (text or "").strip():
            continue
        for tm in question_bank.top_matches(
            text,
            top_k=6,
            topic_hint=topic,
            conversation_history=conversation_history,
        ):
            if tm.entry.id in exclude:
                continue
            # Same-topic lock — the offline surgical probe's wrong=0 guard.
            if tm.entry.topic != topic:
                continue
            probes.append(tm)
    best_by_id: dict[str, BankMatch] = {}
    for tm in probes:
        prev = best_by_id.get(tm.entry.id)
        if prev is None or float(tm.score) > float(prev.score):
            best_by_id[tm.entry.id] = tm
    ranked = sorted(
        best_by_id.values(), key=lambda m: float(m.score), reverse=True
    )
    for tm in ranked:
        ok, _reason, _margin = _accept_match(tm)
        if ok:
            return tm
    return None


@dataclass
class SubIntentMatch:
    sub_question: str
    intent_id: Optional[str]
    score: float
    semantic: float
    lexical: float
    mode: str
    runner_up: Optional[str]
    runner_up_score: float
    margin: float
    accepted: bool
    drop_reason: Optional[str] = None
    bank_match: Optional[BankMatch] = None


@dataclass
class CompoundResolution:
    question_type: str
    compound_confidence: float
    request_count_estimate: int
    used_compound_path: bool
    sub_questions: list[str] = field(default_factory=list)
    candidate_intents: list[dict[str, Any]] = field(default_factory=list)
    selected_intents: list[str] = field(default_factory=list)
    dropped_intents: list[dict[str, Any]] = field(default_factory=list)
    duplicate_intents: list[str] = field(default_factory=list)
    unknown_parts: list[str] = field(default_factory=list)
    answer_en: Optional[str] = None
    answer_sources: list[str] = field(default_factory=list)
    partial_compound_match: bool = False
    full_compound_success: bool = False
    intent_coverage_rate: float = 0.0
    matched_parts_count: int = 0
    requested_parts_count: int = 0
    unsupported_parts_count: int = 0
    answer_order_correct: bool = True
    selected_matches: list[BankMatch] = field(default_factory=list)
    detection_signals: list[str] = field(default_factory=list)
    decomposition_notes: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    total_latency_ms: float = 0.0
    # Track B stage observability
    detected_parts_count: int = 0
    answered_parts_count: int = 0
    missed_parts: list[str] = field(default_factory=list)
    duplicate_parts: list[str] = field(default_factory=list)
    final_coverage: float = 0.0
    failure_code: str = "OK"

    def to_trace(self) -> dict[str, Any]:
        return {
            "question_type": self.question_type,
            "compound_confidence": self.compound_confidence,
            "request_count_estimate": self.request_count_estimate,
            "used_compound_path": self.used_compound_path,
            "sub_questions": self.sub_questions,
            "candidate_intents": self.candidate_intents,
            "selected_intents": self.selected_intents,
            "dropped_intents": self.dropped_intents,
            "duplicate_intents": self.duplicate_intents,
            "unknown_parts": self.unknown_parts,
            "answer_sources": self.answer_sources,
            "final_answer": self.answer_en,
            "partial_compound_match": self.partial_compound_match,
            "full_compound_success": self.full_compound_success,
            "intent_coverage_rate": self.intent_coverage_rate,
            "matched_parts_count": self.matched_parts_count,
            "requested_parts_count": self.requested_parts_count,
            "unsupported_parts_count": self.unsupported_parts_count,
            "detected_parts_count": self.detected_parts_count,
            "answered_parts_count": self.answered_parts_count,
            "missed_parts": self.missed_parts,
            "duplicate_parts": self.duplicate_parts,
            "final_coverage": self.final_coverage,
            "failure_code": self.failure_code,
            "detection_signals": self.detection_signals,
            "decomposition_notes": self.decomposition_notes,
            "timings": self.timings,
            "total_latency_ms": self.total_latency_ms,
        }


def _token_jaccard(a: str, b: str) -> float:
    ta = set(re_findall_tokens(a))
    tb = set(re_findall_tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def re_findall_tokens(text: str) -> list[str]:
    import re

    return re.findall(r"[a-z0-9]{3,}", (text or "").lower())


def _parent_topic(intent_id: str) -> str:
    # moe.question_generation.stack -> moe.question_generation
    parts = (intent_id or "").split(".")
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return intent_id


def _accept_match(match: BankMatch | None) -> tuple[bool, Optional[str], float]:
    if match is None:
        return False, "no_match", 0.0
    margin = float(match.score) - float(match.runner_up_score or 0.0)
    if match.runner_up is None:
        margin = float(match.score)
    if match.score < _MIN_KEEP_SCORE:
        return False, "low_score", margin
    if match.score < _MIN_ANSWER_SCORE:
        return False, "below_answer_threshold", margin
    # Very strong scores: do not reject on thin margin (related sibling intents).
    if match.score >= 0.90:
        return True, None, margin
    # Ambiguous across topics → omit rather than guess (HC safety).
    if (
        match.runner_up
        and margin < _AMBIGUOUS_MARGIN
        and _parent_topic(match.runner_up) != _parent_topic(match.entry.id)
    ):
        return False, "ambiguous_margin", margin
    if match.runner_up and margin < _MIN_MARGIN and match.score < 0.85:
        return False, "thin_margin", margin
    return True, None, margin


def _dedupe_matches(matches: list[BankMatch]) -> tuple[list[BankMatch], list[str]]:
    """Keep distinct intent IDs in order. Same-id only — do not collapse siblings by answer overlap."""
    kept: list[BankMatch] = []
    duplicates: list[str] = []
    seen: set[str] = set()
    for match in matches:
        eid = match.entry.id
        if eid in seen:
            duplicates.append(eid)
            continue
        seen.add(eid)
        kept.append(match)
    return kept, duplicates


def _assign_failure_code(base: "CompoundResolution") -> str:
    if base.requested_parts_count <= 1 and not base.used_compound_path:
        return "DECOMPOSITION_MISS"
    if base.matched_parts_count == 0 and base.requested_parts_count >= 2:
        return "INTENT_MATCH_MISS"
    if base.matched_parts_count >= 1 and base.answered_parts_count == 0:
        return "ANSWER_FRAGMENT_MISS"
    if base.duplicate_parts and base.answered_parts_count < base.matched_parts_count:
        return "DEDUP_REMOVED_VALID_PART"
    if (
        base.matched_parts_count >= 2
        and base.answered_parts_count < base.matched_parts_count
        and base.answered_parts_count >= 1
    ):
        return "MERGE_DROPPED_PART"
    if base.answered_parts_count < max(2, min(base.requested_parts_count, base.matched_parts_count)):
        return "ANSWER_TOO_SHORT"
    if base.used_compound_path and base.final_coverage >= 0.99:
        return "OK"
    if base.used_compound_path and base.unsupported_parts_count == 0 and base.answered_parts_count >= base.requested_parts_count:
        return "OK"
    if base.unsupported_parts_count > 0:
        return "INTENT_MATCH_MISS"
    return "OK" if base.used_compound_path else "DECOMPOSITION_MISS"


def resolve_compound_question(
    text: str,
    *,
    conversation_history: Optional[Iterable[dict]] = None,
    detection: Optional[ComplexityDetection] = None,
) -> CompoundResolution:
    """
    Run complexity detection and, when warranted, the multi-intent path.

    For SINGLE results, used_compound_path=False and the caller must keep the
    existing single-intent matcher as the fast default.
    """
    t0 = time.perf_counter()
    raw = (text or "").strip()
    detection = detection or detect_question_complexity(raw)

    base = CompoundResolution(
        question_type=detection.question_type,
        compound_confidence=detection.confidence,
        request_count_estimate=detection.request_count_estimate,
        used_compound_path=False,
        detection_signals=list(detection.signals),
    )

    if detection.question_type == "single":
        base.total_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        base.timings = {"detection_ms": base.total_latency_ms}
        return base

    # COMPOUND or UNCERTAIN → attempt decomposition + multi-match.
    t_decomp = time.perf_counter()
    decomp = decompose_compound_question(raw)
    decomposition_ms = (time.perf_counter() - t_decomp) * 1000
    sub_questions = list(decomp.sub_questions)
    base.sub_questions = sub_questions
    base.decomposition_notes = list(decomp.notes)
    base.requested_parts_count = len(sub_questions)
    base.detected_parts_count = len(sub_questions)

    # Prefer the smallest useful set: if only one sub-question, soft-split
    # again from the raw utterance before abandoning the compound path.
    if len(sub_questions) <= 1:
        import re as _re

        soft_parts = [
            p.strip()
            for p in _re.split(
                r",\s+(?:and|then)\s+|\s+(?:and|then)\s+(?=why\b|how\b|what\b|"
                r"when\b|where\b|which\b|say\b|point\b|explain\b|define\b|give\b|name\b)",
                raw,
                flags=_re.I,
            )
            if p and len(p.split()) >= 3
        ]
        if len(soft_parts) >= 2:
            sub_questions = soft_parts[:4]
            base.sub_questions = sub_questions
            base.requested_parts_count = len(sub_questions)
            base.detected_parts_count = len(sub_questions)
            base.decomposition_notes = list(base.decomposition_notes) + ["soft_split_rescue"]
        elif (detection.request_count_estimate or 0) >= 2 or detection.question_type == "compound":
            # Keep compound path alive: match full utterance + harvest siblings.
            sub_questions = [raw]
            base.sub_questions = sub_questions
            base.requested_parts_count = max(2, (detection.request_count_estimate or 2))
            base.detected_parts_count = 1
            base.decomposition_notes = list(base.decomposition_notes) + [
                "decomp_miss_force_harvest"
            ]
        else:
            # Uncertain with no real split → treat as single (fast path).
            base.question_type = (
                "single" if detection.question_type == "uncertain" else detection.question_type
            )
            base.used_compound_path = False
            base.failure_code = "DECOMPOSITION_MISS"
            base.missed_parts = list(sub_questions) if sub_questions else [raw]
            base.total_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            base.timings = {
                "detection_ms": round(base.total_latency_ms - decomposition_ms, 1),
                "decomposition_ms": round(decomposition_ms, 1),
            }
            _log_trace(raw, base)
            return base

    t_match = time.perf_counter()
    accepted: list[BankMatch] = []
    sub_rows: list[SubIntentMatch] = []
    history = list(conversation_history) if conversation_history else None
    semantic_parts_ms = 0.0
    batch_embed_ms = 0.0
    lexical_match_ms = 0.0
    harvest_ms = 0.0

    # Phase 1 — lexical match every sub-question (no semantic yet).
    t_lex0 = time.perf_counter()
    pending: list[dict[str, Any]] = []
    # Batch prefetch: one embed + score pass for unique sub-questions (+ stripped forms).
    prefetch_texts: list[str] = list(sub_questions)
    import re as _re_pref

    for sq in sub_questions:
        stripped = _re_pref.sub(
            r"^(?:say|tell|explain|describe|point to|give|define)\s+",
            "",
            sq.strip(),
            flags=_re_pref.I,
        ).strip()
        if stripped and stripped.casefold() != sq.strip().casefold():
            prefetch_texts.append(stripped)
    question_bank.prefetch_scores(prefetch_texts, conversation_history=history)

    for sq in sub_questions:
        match = question_bank.match(sq, conversation_history=history)
        # Latency-cut: skip duplicate top_matches when match already usable.
        # Fast lexical accept: strong/high score → no second full search.
        tops: list = []
        score_m = float(getattr(match, "score", 0.0) or 0.0) if match is not None else 0.0
        fast_accept = (
            match is not None
            and (
                score_m >= 0.90
                or (match.mode == "strong" and score_m >= 0.70)
            )
        )
        need_tops = (not fast_accept) and (
            match is None
            or match.runner_up is None
            or score_m < _MIN_ANSWER_SCORE
        )
        if need_tops:
            tops = question_bank.top_matches(sq, top_k=4, conversation_history=history)
        if match is None and tops:
            match = tops[0]
        # Imperative lead-ins ("Say why…") often hurt lexical match — retry stripped.
        if match is None or float(getattr(match, "score", 0.0) or 0.0) < _MIN_ANSWER_SCORE:
            import re as _re

            stripped = _re.sub(
                r"^(?:say|tell|explain|describe|point to|give|define)\s+",
                "",
                sq.strip(),
                flags=_re.I,
            ).strip()
            if stripped and stripped.casefold() != sq.strip().casefold():
                alt = question_bank.match(stripped, conversation_history=history)
                if alt is not None and (
                    match is None or float(alt.score) > float(match.score) + 0.02
                ):
                    match = alt
                    if need_tops or match.runner_up is None:
                        tops = question_bank.top_matches(
                            stripped, top_k=4, conversation_history=history
                        )
        # Prefer a distinct intent when this sub-question's top hit was already taken.
        already = {
            m.entry.id
            for m in (p["match"] for p in pending if p.get("match") is not None)
        }
        if match is not None and match.entry.id in already and not tops:
            tops = question_bank.top_matches(sq, top_k=4, conversation_history=history)
        if match is not None and match.entry.id in already and tops:
            for cand in tops:
                if cand.entry.id in already:
                    continue
                ok_alt, _r_alt, _m_alt = _accept_match(cand)
                if ok_alt or float(cand.score) >= _HARVEST_MIN_SCORE:
                    match = cand
                    break
        if match is not None and tops and len(tops) >= 2 and match.runner_up is None:
            if tops[0].entry.id == match.entry.id:
                match = BankMatch(
                    entry=match.entry,
                    score=match.score,
                    semantic=match.semantic,
                    lexical=match.lexical,
                    keyword=match.keyword,
                    alias=match.alias,
                    mode=match.mode,
                    runner_up=tops[1].entry.id,
                    runner_up_score=tops[1].score,
                )
            else:
                # Runner-up relative to the chosen alternate.
                other = next((t for t in tops if t.entry.id != match.entry.id), None)
                if other is not None:
                    match = BankMatch(
                        entry=match.entry,
                        score=match.score,
                        semantic=match.semantic,
                        lexical=match.lexical,
                        keyword=match.keyword,
                        alias=match.alias,
                        mode=match.mode,
                        runner_up=other.entry.id,
                        runner_up_score=other.score,
                    )

        ok_pre, _reason_pre, _margin_pre = _accept_match(match)
        # Fast path: strong/distinctive lexical already safe to accept → no semantic.
        fast_lexical = bool(
            ok_pre
            and match is not None
            and (
                float(match.score) >= 0.90
                or (match.mode == "strong" and float(match.score) >= 0.70)
            )
        )
        from app.services.semantic_intent_recovery import should_trigger_semantic_recovery

        trig, treason = (
            (False, "fast_lexical")
            if fast_lexical
            else should_trigger_semantic_recovery(sq, match)
        )
        pending.append(
            {
                "sq": sq,
                "match": match,
                "trig": trig,
                "treason": treason,
                "fast_lexical": fast_lexical,
            }
        )
    lexical_match_ms = (time.perf_counter() - t_lex0) * 1000

    # Phase 2 — one batch embed/search for all parts that need semantic.
    from app.services.semantic_intent_index import semantic_intent_index
    from app.services.semantic_intent_recovery import recover_semantic_intent
    from app.services.technical_term_repair import repair_technical_terms

    need_sem_idx = [i for i, p in enumerate(pending) if p["trig"]]
    pre_hits: dict[int, list] = {}
    if need_sem_idx and semantic_intent_index.ready:
        t_be0 = time.perf_counter()
        queries = [
            repair_technical_terms(
                pending[i]["sq"],
                prior_topic=question_bank.topic_for_history(history),
            )
            for i in need_sem_idx
        ]
        batch_hits = semantic_intent_index.top_k_many(queries, k=5)
        for i, hits in zip(need_sem_idx, batch_hits):
            pre_hits[i] = hits
        batch_embed_ms = (time.perf_counter() - t_be0) * 1000

    # Phase 3 — apply semantic only on weak parts (reuse batched hits).
    t_sem0 = time.perf_counter()
    for i, p in enumerate(pending):
        sq = p["sq"]
        match = p["match"]
        if p["trig"]:
            sem = recover_semantic_intent(
                sq,
                match,
                conversation_history=history,
                precomputed_sem_hits=pre_hits.get(i),
            )
            if sem.applied and sem.match is not None:
                match = sem.match

        ok, reason, margin = _accept_match(match)
        row = SubIntentMatch(
            sub_question=sq,
            intent_id=match.entry.id if match else None,
            score=float(match.score) if match else 0.0,
            semantic=float(match.semantic) if match else 0.0,
            lexical=float(match.lexical) if match else 0.0,
            mode=match.mode if match else "none",
            runner_up=match.runner_up if match else None,
            runner_up_score=float(match.runner_up_score) if match else 0.0,
            margin=margin,
            accepted=ok,
            drop_reason=None if ok else (reason or "rejected"),
            bank_match=match if ok else None,
        )
        sub_rows.append(row)
        base.candidate_intents.append(
            {
                "sub_question": sq,
                "intent_id": row.intent_id,
                "score": round(row.score, 3),
                "mode": row.mode,
                "runner_up": row.runner_up,
                "margin": round(row.margin, 3),
                "accepted": row.accepted,
                "drop_reason": row.drop_reason,
                "fast_lexical": bool(p.get("fast_lexical")),
                "semantic_triggered": bool(p.get("trig")),
            }
        )
        if ok and match is not None:
            accepted.append(match)
        else:
            base.unknown_parts.append(sq)
            base.dropped_intents.append(
                {
                    "sub_question": sq,
                    "intent_id": row.intent_id,
                    "reason": row.drop_reason,
                    "score": round(row.score, 3),
                }
            )
    semantic_parts_ms = (time.perf_counter() - t_sem0) * 1000

    # Track B: if sub-matches under-cover, harvest additional distinct intents from the
    # full utterance (multi-ask questions often bury the second topic in one clause).
    t_hv0 = time.perf_counter()
    need = max(base.requested_parts_count, (detection.request_count_estimate or 2))
    if len({m.entry.id for m in accepted}) < need:
        seen_ids = {m.entry.id for m in accepted}

        def _harvest_ok(cand: BankMatch) -> bool:
            ok_c, _reason_c, _margin_c = _accept_match(cand)
            if ok_c:
                return True
            # Softer second-chance for under-covered compounds only.
            score = float(getattr(cand, "score", 0.0) or 0.0)
            if score < _HARVEST_MIN_SCORE:
                return False
            # Still reject cross-topic coin-flips.
            margin = score - float(getattr(cand, "runner_up_score", 0.0) or 0.0)
            if (
                cand.runner_up
                and margin < _AMBIGUOUS_MARGIN
                and _parent_topic(cand.runner_up) != _parent_topic(cand.entry.id)
            ):
                return False
            return True

        # Also try matching each soft clause independently for buried parts.
        import re as _re

        clause_bits = [
            p.strip()
            for p in _re.split(
                r",\s+(?:and|then)\s+|\s+and\s+(?=why\b|how\b|what\b|when\b|"
                r"where\b|which\b|say\b|point\b)|;\s+",
                raw,
                flags=_re.I,
            )
            if p and len(p.split()) >= 3
        ]
        harvest_queries = [raw] + [c for c in clause_bits if c.casefold() != raw.casefold()]
        for hq in harvest_queries:
            for cand in question_bank.top_matches(hq, top_k=8, conversation_history=history):
                if cand.entry.id in seen_ids:
                    continue
                if not _harvest_ok(cand):
                    continue
                accepted.append(cand)
                seen_ids.add(cand.entry.id)
                base.candidate_intents.append(
                    {
                        "sub_question": hq,
                        "intent_id": cand.entry.id,
                        "score": round(float(cand.score), 3),
                        "mode": cand.mode,
                        "runner_up": cand.runner_up,
                        "margin": round(
                            float(cand.score) - float(cand.runner_up_score or 0.0), 3
                        ),
                        "accepted": True,
                        "drop_reason": None,
                        "source": "full_utterance_harvest",
                    }
                )
                if len(seen_ids) >= need:
                    break
            if len(seen_ids) >= need:
                break
        # Drop unknown_parts that are now covered by harvested ids.
        harvested = {m.entry.id for m in accepted}
        base.unknown_parts = [
            u
            for u in base.unknown_parts
            if not any(
                (row.get("intent_id") in harvested)
                for row in base.dropped_intents
                if row.get("sub_question") == u
            )
        ]

    harvest_ms = (time.perf_counter() - t_hv0) * 1000

    # Phase 3b — Variant D surgical trailing rescue (flagged; thresholds untouched).
    variant_d_ms = 0.0
    if COMPOUND_VARIANT_D_RESCUE and len(sub_rows) >= 2:
        t_vd0 = time.perf_counter()
        seen_ids = {m.entry.id for m in accepted}
        walk_seen: set[str] = set()
        parent_match: Optional[BankMatch] = None
        for i, row in enumerate(sub_rows):
            if row.accepted and row.bank_match is not None:
                eid = row.bank_match.entry.id
                if eid not in walk_seen:
                    walk_seen.add(eid)
                    parent_match = row.bank_match
                    continue
                # Same intent accepted again → fall through for a distinct rescue.
                if parent_match is None:
                    parent_match = row.bank_match
            if i == 0 or parent_match is None:
                continue
            # Prefer clear trailing / follow-on clauses; still allow pronoun-heavy
            # drops that need subject carry (e.g. "What do you do about it?").
            sq = row.sub_question
            looks_trailing = bool(_TRAILING_CLAUSE_RE.match(sq))
            has_pronoun = bool(_PRONOUN_RE.search(sq))
            if not looks_trailing and not has_pronoun:
                continue
            exclude = set(seen_ids) | set(walk_seen) | {parent_match.entry.id}
            rescued = _variant_d_rescue_match(
                sq,
                parent_match,
                exclude,
                conversation_history=history,
            )
            if rescued is None:
                continue
            accepted.append(rescued)
            seen_ids.add(rescued.entry.id)
            walk_seen.add(rescued.entry.id)
            parent_match = rescued
            margin = float(rescued.score) - float(rescued.runner_up_score or 0.0)
            row.intent_id = rescued.entry.id
            row.score = float(rescued.score)
            row.semantic = float(rescued.semantic)
            row.lexical = float(rescued.lexical)
            row.mode = rescued.mode
            row.runner_up = rescued.runner_up
            row.runner_up_score = float(rescued.runner_up_score or 0.0)
            row.margin = margin
            row.accepted = True
            row.drop_reason = None
            row.bank_match = rescued
            base.candidate_intents.append(
                {
                    "sub_question": sq,
                    "intent_id": rescued.entry.id,
                    "score": round(float(rescued.score), 3),
                    "mode": rescued.mode,
                    "runner_up": rescued.runner_up,
                    "margin": round(margin, 3),
                    "accepted": True,
                    "drop_reason": None,
                    "source": "variant_d_trailing_rescue",
                }
            )
            base.dropped_intents = [
                d for d in base.dropped_intents if d.get("sub_question") != sq
            ]
            base.unknown_parts = [u for u in base.unknown_parts if u != sq]
            base.decomposition_notes = list(base.decomposition_notes) + [
                "variant_d_trailing_rescue"
            ]
        variant_d_ms = (time.perf_counter() - t_vd0) * 1000

    matching_ms = (time.perf_counter() - t_match) * 1000

    t_merge = time.perf_counter()
    deduped, dupes = _dedupe_matches(accepted)
    base.duplicate_intents = dupes
    base.duplicate_parts = list(dupes)
    base.selected_matches = deduped
    base.selected_intents = [m.entry.id for m in deduped]
    base.matched_parts_count = len(deduped)

    # Parts covered = accepted unique intents + sub-questions that hit a
    # duplicate of a selected intent (smallest useful set still covers them).
    selected_ids = set(base.selected_intents)
    covered_parts = 0
    still_unknown: list[str] = []
    for row in sub_rows:
        if row.accepted and row.intent_id in selected_ids:
            covered_parts += 1
        elif row.intent_id and (
            row.intent_id in selected_ids or row.intent_id in dupes
        ):
            covered_parts += 1
        elif row.accepted:
            covered_parts += 1
        else:
            still_unknown.append(row.sub_question)
    base.unknown_parts = still_unknown
    base.missed_parts = list(still_unknown)
    # Rebuild dropped list without duplicate-collapse noise.
    base.dropped_intents = [
        d
        for d in base.dropped_intents
        if d.get("sub_question") in still_unknown
    ]
    base.unsupported_parts_count = len(still_unknown)
    base.intent_coverage_rate = round(
        covered_parts / max(1, base.requested_parts_count), 3
    )
    base.partial_compound_match = (
        base.matched_parts_count >= 1 and base.unsupported_parts_count >= 1
    )
    base.full_compound_success = (
        base.matched_parts_count >= 1 and base.unsupported_parts_count == 0
    )

    built = build_compound_answer(deduped) if deduped else None
    answer_merge_ms = (time.perf_counter() - t_merge) * 1000

    if built is None or not deduped:
        base.used_compound_path = False
        base.answered_parts_count = 0
        base.final_coverage = 0.0
        base.failure_code = _assign_failure_code(base)
        base.timings = {
            "decomposition_ms": round(decomposition_ms, 1),
            "matching_ms": round(matching_ms, 1),
            "lexical_match_ms": round(lexical_match_ms, 1),
            "batch_embed_ms": round(batch_embed_ms, 1),
            "semantic_parts_ms": round(semantic_parts_ms, 1),
            "harvest_ms": round(harvest_ms, 1),
            "variant_d_ms": round(variant_d_ms, 1),
            "answer_merge_ms": round(answer_merge_ms, 1),
        }
        base.total_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        _log_trace(raw, base)
        return base

    base.used_compound_path = True
    base.answer_en = built.answer_en
    base.answer_sources = list(built.source_ids)
    base.answered_parts_count = len(built.source_ids)
    base.answer_order_correct = True
    # Honest coverage: require answered fragments for every requested part when all matched.
    if (
        base.unsupported_parts_count == 0
        and base.answered_parts_count >= base.requested_parts_count
    ):
        base.full_compound_success = True
        base.partial_compound_match = False
        base.intent_coverage_rate = 1.0
    elif base.unsupported_parts_count == 0:
        # Matched all intents but merge dropped sentence(s).
        base.full_compound_success = False
        base.partial_compound_match = True
        base.intent_coverage_rate = round(
            base.answered_parts_count / max(1, base.requested_parts_count), 3
        )
    else:
        base.partial_compound_match = True
        base.full_compound_success = False

    base.final_coverage = float(base.intent_coverage_rate)
    base.failure_code = _assign_failure_code(base)

    base.timings = {
        "decomposition_ms": round(decomposition_ms, 1),
        "matching_ms": round(matching_ms, 1),
        "lexical_match_ms": round(lexical_match_ms, 1),
        "batch_embed_ms": round(batch_embed_ms, 1),
        "semantic_parts_ms": round(semantic_parts_ms, 1),
        "harvest_ms": round(harvest_ms, 1),
        "variant_d_ms": round(variant_d_ms, 1),
        "answer_merge_ms": round(answer_merge_ms, 1),
    }
    base.total_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    _log_trace(raw, base)
    return base


def _log_trace(original: str, result: CompoundResolution) -> None:
    logger.info(
        "COMPOUND QUESTION TRACE original_transcript=%r question_type=%s "
        "compound_confidence=%.2f sub_questions=%s selected_intents=%s "
        "dropped_intents=%s duplicate_intents=%s unknown_parts=%s "
        "answer_sources=%s final_answer=%r total_latency_ms=%.1f timings=%s",
        original,
        result.question_type,
        result.compound_confidence,
        result.sub_questions,
        result.selected_intents,
        result.dropped_intents,
        result.duplicate_intents,
        result.unknown_parts,
        result.answer_sources,
        (result.answer_en or "")[:400],
        result.total_latency_ms,
        result.timings,
    )


# Avoid unused import warning if asdict not used
_ = asdict
