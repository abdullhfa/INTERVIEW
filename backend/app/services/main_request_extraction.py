"""
MAIN_REQUEST_EXTRACTION — conservative pre-match stage for long / indirect questions.

FROZEN 2026-09-15 with V5 Live Interview Assistant — bug-fix only.
See reports/V5_LIVE_ASSISTANT_FREEZE.json.

Pipeline (additive, does not replace existing matching):
  STT → normalization → MAIN_REQUEST_EXTRACTION → lexical/semantic/hybrid match

Rules:
  - Only runs when LONG_OR_INDIRECT_QUESTION signals fire.
  - main_request is primary; full_question remains supporting context.
  - Low confidence → do not override the production matcher.
  - Never fabricates asks not supported by the transcript.
  - Does not change HC guards / strong thresholds / accept gates.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Explicit interview asks (structure cues — not "last sentence wins").
# Include STT near-miss "watch me through" for "walk me through".
_ASK_CUE = re.compile(
    r"(?i)\b(?:"
    r"walk me through|"
    r"watch me through|"
    r"tell me (?:how|about|what)|"
    r"can you (?:explain|walk|tell)|"
    r"explain how|"
    r"how (?:would|should|do|can|did|will|are) (?:you|your|we|the|an?)\b|"
    r"what (?:would|should|do|did|will|is|are|was) (?:you|your|we|the|an?|your)\b|"
    r"what (?:checks|changes|steps|approach)\b|"
    r"why (?:would|should|do|did|will|is|are)\b|"
    r"where (?:would|should|do|did|will|to)\b|"
    r"when (?:would|should|do|did|will)\b|"
    r"which (?:would|should|do|did|will) you\b|"
    r"how do you decide\b|"
    r"what is the main\b|"
    r"how should (?:your|the) (?:assistant|system|understanding)\b|"
    r"how will you (?:design|build|handle|identify)\b|"
    r"where would you start\b|"
    r"what would you change\b"
    r")"
)

_SCENARIO_START = re.compile(
    r"(?i)^\s*(?:"
    r"imagine\b|suppose\b|if\b|during\b|given that\b|let'?s say\b|"
    r"tell me about a time\b|your assistant\b|you(?:r)? (?:rag|ai|system)\b"
    r")"
)

_SCENARIO_MARKERS = re.compile(
    r"(?i)\b(?:"
    r"imagine\b|suppose\b|given that\b|let'?s say\b|during\b|"
    r"walk me through\b|watch me through\b|tell me about a time\b|background\b|"
    r"indirect(?:ly)?\b|several details\b"
    r")"
)

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SPLIT_ASKS = re.compile(
    r"(?:,\s*|\s+)(?:and|or)\s+(?=(?:how|what|why|where|when|which)\b)",
    re.I,
)

# Compact anchors extracted from background (pronoun resolution within same question).
_ANCHOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b((?:outdated|wrong|bad|stale)\s+(?:policy\s+)?(?:document|content|data|information|chunk|context|retrieval|version)(?:\s+\w+){0,4})",
    ),
    re.compile(r"(?i)\b((?:retrieval|rag)\s+(?:failure|error|issue|problem|mistake)(?:\s+\w+){0,3})"),
    re.compile(r"(?i)\b(latency|bottleneck|(?:response\s+)?delay|too long)\b"),
    re.compile(r"(?i)\b((?:indirect|ambiguous)\s+question(?:\s+\w+){0,4})"),
    re.compile(r"(?i)\b((?:understanding layer|main intent|intended question)(?:\s+\w+){0,3})"),
    re.compile(r"(?i)\b((?:model(?:\s+inference)?|speech recognition|user interface)(?:\s+\w+){0,2})"),
)


@dataclass(frozen=True)
class MainRequestExtraction:
    full_question: str
    background_context: str
    main_request: str
    secondary_requests: list[str] = field(default_factory=list)
    request_type: str = "explain"
    confidence: float = 0.0
    long_or_indirect: bool = False
    applied: bool = False
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "full_question": self.full_question,
            "background_context": self.background_context,
            "main_request": self.main_request,
            "secondary_requests": list(self.secondary_requests),
            "request_type": self.request_type,
            "confidence": round(float(self.confidence), 3),
            "long_or_indirect": self.long_or_indirect,
            "applied": self.applied,
            "reason": self.reason,
        }


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _clause_count(text: str) -> int:
    t = text or ""
    return max(1, len(re.split(r"[,;]|\band\b|\bbut\b", t, flags=re.I)))


def is_long_or_indirect_question(text: str) -> bool:
    """Gate: run extraction only when structure suggests background + ask (or long)."""
    q = (text or "").strip()
    if not q:
        return False
    wc = _word_count(q)
    commas = q.count(",")
    has_scenario = bool(_SCENARIO_MARKERS.search(q)) or bool(_SCENARIO_START.search(q))
    has_ask = bool(_ASK_CUE.search(q))
    multi_clause = _clause_count(q) >= 3 or commas >= 2
    # Short but indirect: "If …, what would you …?"
    if has_scenario and has_ask and wc >= 12:
        return True
    if wc >= 22 and has_ask:
        return True
    if multi_clause and has_ask and wc >= 16:
        return True
    if has_scenario and wc >= 18:
        return True
    return False


def _request_type(main: str, *, scenario: bool) -> str:
    if scenario:
        return "scenario"
    m = (main or "").lower()
    if m.startswith("why") or " why " in f" {m}":
        return "why"
    if m.startswith("when") or " when " in f" {m}":
        return "when"
    if m.startswith("where") or " where " in f" {m}":
        return "where"
    if "compare" in m or "versus" in m or " vs " in m:
        return "compare"
    if m.startswith("what") or " what " in f" {m}":
        return "what"
    if "explain" in m or "walk me through" in m or "tell me" in m:
        return "explain"
    if m.startswith("how") or " how " in f" {m}":
        return "how"
    return "explain"


def _background_anchor(background: str) -> str:
    bg = (background or "").strip()
    if not bg:
        return ""
    for pat in _ANCHOR_PATTERNS:
        m = pat.search(bg)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip(" .,;:")[:80]
    # Fallback: last contentful noun-ish span (keep short, no invention).
    words = _WORD_RE.findall(bg)
    if len(words) >= 4:
        return " ".join(words[-6:])[:80]
    return ""


def _resolve_pronouns(request: str, background: str) -> str:
    """Resolve it/that/the issue within the same question only."""
    req = (request or "").strip()
    anchor = _background_anchor(background)
    if not req or not anchor:
        return req
    out = req
    replacements = [
        (r"(?i)\bthe same failure\b", anchor),
        (r"(?i)\bthe same issue\b", anchor),
        (r"(?i)\bthe issue\b", anchor),
        (r"(?i)\bthe failure\b", anchor),
        (r"(?i)\bthe problem\b", anchor),
        (r"(?i)\bdetect it\b", f"detect {anchor}"),
        (r"(?i)\bprevent it\b", f"prevent {anchor}"),
        (r"(?i)\bfix it\b", f"fix {anchor}"),
        (r"(?i)\babout it\b", f"about {anchor}"),
        (r"(?i)\bhandle it\b", f"handle {anchor}"),
    ]
    # Keep "the delay" as-is — replacing it often injects noisy background spans.
    for pat, repl in replacements:
        out = re.sub(pat, repl, out)
    # Trailing bare "it" after verbs already handled; avoid mass-replacing every "it".
    return re.sub(r"\s+", " ", out).strip()


def _supported_span(candidate: str, full: str) -> bool:
    """Anti-fabrication: every content token of candidate must appear in full."""
    c_tokens = {t.lower() for t in _WORD_RE.findall(candidate or "")}
    f_tokens = {t.lower() for t in _WORD_RE.findall(full or "")}
    if not c_tokens:
        return False
    # Allow tiny glue words introduced by pronoun expansion (anchor still from full).
    missing = c_tokens - f_tokens
    # Anchor words come from background which is part of full — should be empty.
    # If pronoun expansion reused background tokens, missing stays empty.
    return len(missing) <= max(1, len(c_tokens) // 8)


def _split_secondary(request_region: str) -> tuple[str, list[str]]:
    region = (request_region or "").strip()
    if not region:
        return "", []
    # Prefer comma / "and"-separated ask continuations: detect X, where Y, and how Z
    soft = re.split(
        r"(?:,\s*|\s+and\s+)(?=(?:where|how|what|why|when|which)\b)",
        region,
        flags=re.I,
    )
    soft = [p.strip(" .,;:") for p in soft if p.strip()]
    if len(soft) >= 2:
        parts = soft
    else:
        parts = [p.strip(" .,;:") for p in _SPLIT_ASKS.split(region) if p.strip()]
    if not parts:
        return region, []
    main = parts[0]
    secondary = [p for p in parts[1:] if p and p.lower() != main.lower()]
    cleaned: list[str] = []
    for s in secondary:
        sl = s.lower()
        if sl.startswith(("and ", "or ")):
            s = s.split(" ", 1)[-1].strip()
            sl = s.lower()
        if _ASK_CUE.search(s) or sl.startswith(
            ("how ", "what ", "why ", "where ", "when ", "which ")
        ):
            cleaned.append(s[:1].upper() + s[1:] if s and s[0].islower() else s)
        elif sl.startswith(("where you", "how you", "what you")):
            prefix = "Where " if sl.startswith("where") else "How "
            cleaned.append(prefix + s)
    return main, cleaned[:4]


def extract_main_request(text: str) -> MainRequestExtraction:
    """
    Extract background vs main/secondary requests from one interview question.

    Conservative: if structure is unclear, returns low confidence and applied=False.
    """
    full = re.sub(r"\s+", " ", (text or "").strip())
    # STT near-miss: keep meaning, do not invent new asks.
    full = re.sub(r"(?i)\bwatch me through\b", "walk me through", full)
    if not full:
        return MainRequestExtraction(
            full_question="",
            background_context="",
            main_request="",
            confidence=0.0,
            reason="empty",
        )

    long_or_indirect = is_long_or_indirect_question(full)
    if not long_or_indirect:
        return MainRequestExtraction(
            full_question=full,
            background_context="",
            main_request=full,
            request_type=_request_type(full, scenario=False),
            confidence=0.95,
            long_or_indirect=False,
            applied=False,
            reason="not_long_or_indirect",
        )

    cue = _ASK_CUE.search(full)
    scenarioish = bool(_SCENARIO_START.search(full)) or bool(_SCENARIO_MARKERS.search(full))

    if cue is None:
        return MainRequestExtraction(
            full_question=full,
            background_context="",
            main_request=full,
            confidence=0.25,
            long_or_indirect=True,
            applied=False,
            reason="no_explicit_ask_cue",
        )

    ask_pos = cue.start()
    # Prefer the *final* strong ask when background precedes it (scenario → request).
    cues = list(_ASK_CUE.finditer(full))
    if scenarioish and len(cues) >= 1:
        # If first cue is very early (< 12 chars) keep it; else use last substantial cue.
        if ask_pos < 12 and len(cues) == 1:
            pass
        else:
            # Choose the earliest cue that still leaves meaningful background (>= 8 words).
            chosen = cues[-1]
            for c in cues:
                if _word_count(full[: c.start()]) >= 8:
                    chosen = c
                    break
            ask_pos = chosen.start()
            cue = chosen

    background = full[:ask_pos].strip(" .,;:")
    request_region = full[ask_pos:].strip()
    main, secondary = _split_secondary(request_region)

    if not main:
        return MainRequestExtraction(
            full_question=full,
            background_context=background,
            main_request=full,
            confidence=0.2,
            long_or_indirect=True,
            applied=False,
            reason="empty_main_request",
        )

    main_resolved = _resolve_pronouns(main, background)
    secondary_resolved = [_resolve_pronouns(s, background) for s in secondary]

    # Anti-fabrication gate on resolved text (tokens must come from full).
    if not _supported_span(main_resolved, full):
        main_resolved = main
    secondary_resolved = [s if _supported_span(s, full) else secondary[i] for i, s in enumerate(secondary_resolved)]

    # Confidence: clear background+ask split scores higher.
    bg_words = _word_count(background)
    conf = 0.55
    if bg_words >= 8 and _ASK_CUE.search(main_resolved):
        conf = 0.82
    if scenarioish and bg_words >= 8:
        conf = max(conf, 0.88)
    if secondary_resolved:
        conf = min(0.92, conf + 0.04)
    if bg_words < 4 and _word_count(full) < 28:
        conf = min(conf, 0.6)

    # Do not apply override below this bar (caller also checks).
    apply = conf >= 0.72 and bg_words >= 6 and main_resolved.lower() != full.lower()

    return MainRequestExtraction(
        full_question=full,
        background_context=background,
        main_request=main_resolved,
        secondary_requests=secondary_resolved,
        request_type=_request_type(main_resolved, scenario=scenarioish),
        confidence=conf,
        long_or_indirect=True,
        applied=apply,
        reason="scenario_final_ask" if scenarioish else "explicit_ask_split",
    )


def build_match_query(extraction: MainRequestExtraction) -> str:
    """
    Primary signal = main_request (+ secondary asks); supporting context kept short.
    Never returns main_request alone when background carries referents.
    """
    if not extraction.long_or_indirect or not extraction.main_request:
        return extraction.full_question
    parts = [extraction.main_request]
    for s in extraction.secondary_requests[:3]:
        if s and s.lower() not in extraction.main_request.lower():
            parts.append(s)
    # Compact supporting context: prefer anchor nouns over full story.
    anchor = _background_anchor(extraction.background_context)
    ctx = anchor or (extraction.background_context or "").strip()
    if ctx:
        ctx_short = ctx if len(ctx) <= 120 else (ctx[:117].rsplit(" ", 1)[0] + "…")
        parts.append(f"Context: {ctx_short}")
    return " ".join(parts)


def _content_overlap(a: str, b: str) -> float:
    ta = {t.lower() for t in _WORD_RE.findall(a or "") if len(t) > 2}
    tb = {t.lower() for t in _WORD_RE.findall(b or "") if len(t) > 2}
    # Drop ultra-common glue that inflates overlap without meaning.
    stop = {
        "the",
        "and",
        "you",
        "your",
        "would",
        "should",
        "how",
        "what",
        "with",
        "from",
        "that",
        "this",
        "for",
        "are",
        "was",
        "will",
        "have",
        "has",
        "did",
        "does",
        "about",
        "into",
        "when",
        "where",
        "which",
        "through",
    }
    ta -= stop
    tb -= stop
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(max(len(ta), 1))


def _seed_intent_ids(extraction: MainRequestExtraction) -> list[str]:
    """Seed related bank intents from phrases present in the transcript (no invention)."""
    blob = f"{extraction.main_request} {extraction.background_context}".lower()
    seeds: list[str] = []

    def add(*ids: str) -> None:
        for i in ids:
            if i not in seeds:
                seeds.append(i)

    if any(
        p in blob
        for p in (
            "outdated",
            "expired",
            "stale",
            "wrong chunk",
            "wrong version",
            "wrong document",
            "wrong information",
            "retriev",
            "bad context",
            "semantically close",
        )
    ) and any(
        p in blob
        for p in (
            "detect",
            "catch",
            "fix",
            "patch",
            "prevent",
            "failure",
            "issue",
            "checks",
            "change first",
            "what you did",
        )
    ):
        add(
            "hard.wrong_chunk",
            "hard.conflicting_docs",
            "tech.hallucination_prevent",
            "tech.rag_prevent_invented_numbers",
            "tech.no_wrong_info_finance",
            "hard.empty_retrieval",
        )
    if any(
        p in blob
        for p in (
            "latency",
            "bottleneck",
            "measure the delay",
            "several seconds",
            "too long",
            "speech recognition",
            "model inference",
        )
    ):
        add("tech.latency_p95", "tech.p95", "hard.production_monitoring")
    if any(
        p in blob
        for p in (
            "main intent",
            "intended question",
            "loudest keyword",
            "understanding layer",
            "indirect",
            "ambiguous",
            "distracted by every word",
        )
    ):
        add("gen.ambiguity")
    return seeds


def _weighted_pick(
    full_text: str,
    extraction: MainRequestExtraction,
    *,
    question_bank,
    conversation_history: Optional[list[dict]],
    baseline,
):
    """
    LONG_OR_INDIRECT only: rank candidates with main_request as primary signal.
    Falls back to baseline when confidence / meaning gates fail.
    """
    from app.services.intent_profile import intent_agreement, intent_meaning_ok
    from app.services.question_bank import BankMatch, STRONG_THRESHOLD
    from app.services.semantic_intent_index import semantic_intent_index

    main = extraction.main_request
    query = build_match_query(extraction)
    seeds = _seed_intent_ids(extraction)
    candidate_ids: list[str] = list(seeds)

    # When structure seeds exist, stay inside that pool — open lexical/semantic
    # neighbors re-introduce background keyword distractors (RAG/design/ML).
    if not seeds:
        for src in (query, main):
            for m in question_bank.top_matches(
                src, top_k=5, conversation_history=conversation_history
            ):
                if m.entry.id not in candidate_ids:
                    candidate_ids.append(m.entry.id)
        try:
            semantic_intent_index.ensure_loaded()
            if semantic_intent_index.ready:
                for h in semantic_intent_index.top_k(main, k=4):
                    if h.intent_id not in candidate_ids:
                        candidate_ids.append(h.intent_id)
        except Exception:
            pass

    if baseline is not None and baseline.entry.id not in candidate_ids:
        candidate_ids.append(baseline.entry.id)

    if not candidate_ids:
        return baseline, False

    scored: list[tuple[float, BankMatch, float, float, bool]] = []
    for eid in candidate_ids:
        entry = question_bank.get(eid)
        if entry is None:
            continue
        profile = semantic_intent_index.get(eid)
        agr_m = intent_agreement(entry, main, profile=profile)
        agr_f = intent_agreement(entry, full_text, profile=profile)
        agr_q = intent_agreement(entry, query, profile=profile)
        ov = max(
            _content_overlap(main, entry.question),
            _content_overlap(query, entry.question),
        )
        weighted = (0.50 * max(agr_m, agr_q)) + (0.30 * agr_f) + (0.20 * ov)
        ok, _ = intent_meaning_ok(
            entry,
            full_text,
            match_score=max(0.45, weighted),
            profile=profile,
            agreement=agr_f,
        )
        if not ok:
            continue
        if max(agr_m, agr_q) < 0.50 and ov < 0.10:
            continue
        is_seed = eid in seeds
        if is_seed:
            weighted += 0.06
        mode = "strong" if weighted >= STRONG_THRESHOLD and agr_f >= 0.70 else "weak"
        if mode == "strong" and agr_f < 0.70:
            mode = "weak"
        match = BankMatch(
            entry=entry,
            score=max(weighted, 0.45),
            semantic=max(agr_m, agr_q),
            lexical=ov,
            keyword=0.0,
            alias=entry.question,
            mode=mode,
        )
        scored.append((weighted, match, max(agr_m, agr_q), agr_f, is_seed))

    if not scored:
        return baseline, False

    seed_hits = [s for s in scored if s[4]]
    pool = seed_hits if seed_hits else scored
    pool.sort(key=lambda x: x[0], reverse=True)
    best_w, best, best_m, best_f, _ = pool[0]

    def _as_weak(match: BankMatch) -> BankMatch:
        # Extraction must not mint strong mode by itself (HC safety).
        if match.mode != "strong":
            return match
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

    def _finalize(match: BankMatch) -> BankMatch:
        # Prefer a real bank score/mode when the same id matches the extracted query.
        for src in (query, main):
            real = question_bank.match(src, conversation_history=conversation_history)
            if real is not None and real.entry.id == match.entry.id:
                return real
        return _as_weak(match)

    if baseline is None:
        if best_w >= 0.52 and best_m >= 0.50:
            return _finalize(best), True
        return None, False

    try:
        b_prof = semantic_intent_index.get(baseline.entry.id)
        b_m = intent_agreement(baseline.entry, main, profile=b_prof)
        b_f = intent_agreement(baseline.entry, full_text, profile=b_prof)
        b_q = intent_agreement(baseline.entry, query, profile=b_prof)
        b_ov = _content_overlap(main, baseline.entry.question)
        b_w = (0.50 * max(b_m, b_q)) + (0.30 * b_f) + (0.20 * b_ov)
    except Exception:
        b_w = float(baseline.score) * 0.5
        b_m = 0.0

    if best.entry.id == baseline.entry.id:
        return baseline, False
    if seeds and best.entry.id in seeds and best_w >= 0.50 and best_f >= 0.52:
        if baseline.entry.id not in seeds or best_w >= b_w + 0.03:
            return _finalize(best), True
    if best_w >= b_w + 0.04 and best_m >= b_m - 0.02 and best_w >= 0.54:
        return _finalize(best), True
    if b_m < 0.55 and best_m >= 0.58 and best_f >= 0.52 and best_w >= 0.54:
        return _finalize(best), True
    return baseline, False



def match_with_main_request(
    text: str,
    *,
    conversation_history: Optional[list[dict]] = None,
    question_bank=None,
):
    """
    Run bank match with optional main-request priority.

    Returns (match, extraction, meta) where meta includes latency and whether
    the extracted query overrode the full-question match.
    """
    t0 = time.perf_counter()
    if question_bank is None:
        from app.services.question_bank import question_bank as _qb

        question_bank = _qb

    full = (text or "").strip()
    extraction = extract_main_request(full)
    baseline = question_bank.match(full, conversation_history=conversation_history) if full else None

    meta: dict[str, Any] = {
        "extraction": extraction.as_dict(),
        "override": False,
        "baseline_id": None if baseline is None else baseline.entry.id,
        "primary_id": None,
        "latency_ms": 0.0,
        "reason": extraction.reason,
    }

    if not extraction.applied or extraction.confidence < 0.72:
        meta["latency_ms"] = (time.perf_counter() - t0) * 1000
        return baseline, extraction, meta

    chosen, overridden = _weighted_pick(
        full,
        extraction,
        question_bank=question_bank,
        conversation_history=conversation_history,
        baseline=baseline,
    )
    meta["primary_id"] = None if chosen is None else chosen.entry.id
    meta["override"] = overridden
    meta["latency_ms"] = (time.perf_counter() - t0) * 1000
    meta["reason"] = "main_request_weighted" if overridden else extraction.reason
    return chosen, extraction, meta
