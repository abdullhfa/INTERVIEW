"""
BANK_GUIDED_INTERVIEW_UNDERSTANDING

STT is a raw hypothesis — Question Bank is the primary reference.

Pipeline (additive; does not change Whisper / VAD / HC / MRE internals):

  STT RAW
  → BANK CANDIDATE SEARCH (top-5)
  → ACRONYM / TECH / PHRASE recovery (existing)
  → MAIN REQUEST (existing, unchanged)
  → BANK INTENT RESOLUTION (margin guard)
  → ANSWER SELECTION

Returns dual transcript + canonical question + intent for logs/UI.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[A-Za-z0-9']+")
_LOCK = threading.Lock()
_LAST: "UnderstandingResult | None" = None

_MIN_ACCEPT = 0.72
_MIN_MARGIN = 0.12

_STOP = {
    "a", "an", "the", "to", "of", "in", "on", "for", "and", "or", "me", "you",
    "your", "it", "is", "was", "did", "do", "does", "about", "please",
}


@dataclass(frozen=True)
class BankCandidate:
    intent_id: str
    canonical: str
    category: str
    topic: str
    question_type: str
    phonetic: float
    lexical: float
    structure: float
    lexicon: float
    bank_prior: float
    combined: float
    alias_hit: str = ""


@dataclass
class UnderstandingResult:
    raw_transcript: str
    recovered_transcript: str
    canonical_question: str
    intent_id: str
    confidence: float
    ambiguous: bool = False
    candidates: list[BankCandidate] = field(default_factory=list)
    recovery_stages: dict[str, Any] = field(default_factory=dict)
    margin: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_transcript": self.raw_transcript,
            "recovered_transcript": self.recovered_transcript,
            "canonical_question": self.canonical_question,
            "intent_id": self.intent_id,
            "confidence": round(self.confidence, 3),
            "ambiguous": self.ambiguous,
            "margin": round(self.margin, 3),
            "candidates": [
                {
                    "intent_id": c.intent_id,
                    "canonical": c.canonical,
                    "category": c.category,
                    "question_type": c.question_type,
                    "phonetic": round(c.phonetic, 3),
                    "lexical": round(c.lexical, 3),
                    "structure": round(c.structure, 3),
                    "lexicon": round(c.lexicon, 3),
                    "combined": round(c.combined, 3),
                    "alias_hit": c.alias_hit,
                }
                for c in self.candidates[:5]
            ],
            "recovery_stages": self.recovery_stages,
        }


def last_understanding() -> Optional[UnderstandingResult]:
    return _LAST


def _norm(text: str) -> str:
    return " ".join((text or "").strip().split())


def _fold(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).split())


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(t for t in _WORD.findall(_fold(text)) if t not in _STOP and len(t) > 1)


def _skel(text: str) -> str:
    return re.sub(r"[aeiou]", "", re.sub(r"[^a-z]", "", _fold(text)))


def _question_type(text: str) -> str:
    from app.services.question_bank import detect_intent

    try:
        from app.services.domain_terms import normalize_for_matching as nfm

        n = nfm(text)
    except Exception:
        n = _fold(text)
    intent = detect_intent(n) if n else None
    if intent:
        return intent
    low = _fold(text)
    if re.search(r"\bwalk me through\b|\btell me about\b|\bdescribe\b|\bexplain\b", low):
        return "describe"
    if re.search(r"\bwhy\b", low):
        return "why"
    if re.search(r"\bhow\b", low):
        return "how"
    if re.search(r"\bwhen\b", low):
        return "when"
    if re.search(r"\bwhat\b", low):
        return "definition"
    return "other"


def _category_bucket(entry) -> str:
    cat = (entry.category or "").lower()
    bank = (entry.bank or "").lower()
    eid = (entry.id or "").lower()
    if bank == "cv" or cat.startswith("cv") or eid.startswith(("cv.", "proj.", "intro.")):
        if "intro" in eid or "yourself" in (entry.question or "").lower():
            return "PERSONAL_HR"
        return "PROJECT"
    if cat.startswith("general") or eid.startswith("gen."):
        return "PERSONAL_HR"
    if "scenario" in cat or eid.startswith("hard."):
        return "SCENARIO"
    if "business" in cat or "value" in (entry.question or "").lower():
        return "BUSINESS"
    return "TECHNICAL_AI"


def _phonetic(a: str, b: str) -> float:
    fa, fb = _fold(a), _fold(b)
    seq = SequenceMatcher(None, fa, fb).ratio()
    sk = SequenceMatcher(None, _skel(a), _skel(b)).ratio()
    ta, tb = list(_tokens(a)), list(_tokens(b))
    tok = 0.0
    if ta and tb:
        hits = 0.0
        used = set()
        for x in ta:
            best_s, best_i = 0.0, -1
            for i, y in enumerate(tb):
                if i in used:
                    continue
                s = SequenceMatcher(None, x, y).ratio()
                # Known STT bridges
                pairs = {
                    frozenset({"llm", "lalam", "ellem", "elem"}),
                    frozenset({"explain", "plan"}),
                    frozenset({"langchain", "lankan"}),
                    frozenset({"embeddings", "bedding", "beddings"}),
                    frozenset({"rag", "rack", "drag", "ragged"}),
                    frozenset({"role", "roll"}),
                }
                for p in pairs:
                    if x in p and y in p:
                        s = max(s, 0.85)
                if {x, y} <= {"explain", "plan", "and"}:
                    s = max(s, 0.55)
                if s > best_s:
                    best_s, best_i = s, i
            if best_s >= 0.7 and best_i >= 0:
                hits += best_s
                used.add(best_i)
        tok = hits / max(len(ta), len(tb))
    return max(0.0, min(1.0, 0.35 * seq + 0.25 * sk + 0.40 * tok))


def _lexical(a: str, b: str) -> float:
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta or not tb:
        return SequenceMatcher(None, _fold(a), _fold(b)).ratio() * 0.5
    return len(ta & tb) / len(ta | tb)


def _structure(raw_type: str, cand_type: str, raw: str, cand: str) -> float:
    if raw_type == cand_type:
        base = 0.95
    elif {raw_type, cand_type} <= {"describe", "definition", "experience"}:
        base = 0.7
    elif {raw_type, cand_type} == {"how", "describe"}:
        base = 0.55
    else:
        base = 0.25
    # Critical: plan-method vs explain-project
    rl, cl = _fold(raw), _fold(cand)
    if re.search(r"\bhow (?:do|did|would) you plan\b", rl) and re.search(
        r"\bexplain\b|\btell me about your project\b", cl
    ):
        base = 0.05
    if re.search(r"\band you plan\b", rl) and re.search(r"\bexplain\b", cl):
        base = max(base, 0.85)
    if re.search(r"\bhow (?:do|did) you plan your work\b", rl) and "project" in cl:
        base = 0.05
    return base


def _lexicon_score(raw: str, entry) -> float:
    from app.services.interview_lexicon import lexicon_hit

    blob = " ".join(
        [entry.question or "", " ".join(entry.keywords or ()), " ".join(entry.aliases[:5] or ())]
    ).lower()
    score = 0.0
    for term, strength in lexicon_hit(raw)[:5]:
        if term.canonical.lower() in blob or any(
            t.lower() in blob for t in term.spoken_forms[:2]
        ):
            # Rival collision: if rival also in bank entry, don't over-boost
            rival_in = any(r.lower() in blob for r in term.rivals)
            if rival_in and strength < 0.9:
                score = max(score, strength * 0.4)
            else:
                score = max(score, strength)
    return min(1.0, score)


@lru_cache(maxsize=1)
def _probe_index() -> tuple[tuple[str, str, str, int, str, str], ...]:
    """(text, entry_id, kind, entry_index, fold, skel) probes for candidate search."""
    from app.services.question_bank import question_bank

    question_bank.load()
    out: list[tuple[str, str, str, int, str, str]] = []
    for i, e in enumerate(question_bank.entries):
        q = e.question or ""
        out.append((q, e.id, "canonical", i, _fold(q), _skel(q)))
        for a in (e.aliases or ())[:8]:
            if a and len(_WORD.findall(a)) <= 14:
                out.append((a, e.id, "alias", i, _fold(a), _skel(a)))
    spoken_extra = [
        ("what is el el em", "tech.what_is_llm"),
        ("what is l l m", "tech.what_is_llm"),
        ("what is the lalam", "tech.what_is_llm"),
        ("what is lalam", "tech.what_is_llm"),
        ("explain your project", "cv.projects_overview"),
        ("and you plan your project", "cv.projects_overview"),
        ("tell me about yourself", "intro.tell_me_about_yourself"),
        ("how do you plan your work", "gen.prioritize"),
        ("how do you prioritize your work", "gen.prioritize"),
    ]
    id_to_idx = {e.id: i for i, e in enumerate(question_bank.entries)}
    for text, eid in spoken_extra:
        if eid in id_to_idx:
            out.append((text, eid, "spoken", id_to_idx[eid], _fold(text), _skel(text)))
    return tuple(out)


def clear_bank_guided_cache() -> None:
    global _LAST
    _LAST = None
    _probe_index.cache_clear()
    try:
        from app.services.interview_lexicon import clear_lexicon_cache

        clear_lexicon_cache()
    except Exception:
        pass


def search_bank_candidates(raw: str, *, k: int = 5) -> list[BankCandidate]:
    """Top-k bank questions for a raw STT hypothesis (bank-primary)."""
    from app.services.question_bank import question_bank

    question_bank.load()
    raw_n = _norm(raw)
    if not raw_n:
        return []
    raw_type = _question_type(raw_n)
    raw_skel = _skel(raw_n)
    raw_toks = set(_tokens(raw_n))
    scored: dict[str, BankCandidate] = {}

    for text, eid, kind, idx, tf, ts in _probe_index():
        # Cheap gates before full scoring
        sk_ratio = SequenceMatcher(None, raw_skel, ts).ratio() if raw_skel and ts else 0.0
        if kind != "spoken" and sk_ratio < 0.25 and not (raw_toks & set(tf.split())):
            continue
        # silence unused canonical fold param use for token overlap speed
        _ = tf
        phon = _phonetic(raw_n, text)
        lex = _lexical(raw_n, text)
        if phon < 0.35 and lex < 0.15 and kind != "spoken":
            continue
        entry = question_bank.entries[idx]
        ctype = _question_type(text)
        struct = _structure(raw_type, ctype, raw_n, text)
        lexico = _lexicon_score(raw_n, entry)
        prior = 0.85 if kind == "canonical" else (0.8 if kind == "spoken" else 0.7)
        if kind == "spoken" and phon >= 0.75:
            phon = max(phon, 0.9)
            prior = 0.9
        combined = (
            0.32 * phon
            + 0.22 * lex
            + 0.20 * struct
            + 0.16 * lexico
            + 0.10 * prior
        )
        if struct < 0.2:
            combined *= 0.5
        prev = scored.get(eid)
        cand = BankCandidate(
            intent_id=eid,
            canonical=entry.question,
            category=_category_bucket(entry),
            topic=entry.topic or "",
            question_type=ctype,
            phonetic=phon,
            lexical=lex,
            structure=struct,
            lexicon=lexico,
            bank_prior=prior,
            combined=combined,
            alias_hit=text if kind != "canonical" else "",
        )
        if prev is None or cand.combined > prev.combined:
            scored[eid] = cand

    out = sorted(scored.values(), key=lambda c: c.combined, reverse=True)
    return out[:k]


def understand_interview_question(
    raw: str,
    *,
    prior_topic: Optional[str] = None,
) -> UnderstandingResult:
    """
    Bank-guided understanding of one STT hypothesis.

    Does not change Whisper/VAD/HC. Uses existing recovery modules in order.
    """
    global _LAST
    raw_n = _norm(raw)
    stages: dict[str, Any] = {}

    if not raw_n:
        result = UnderstandingResult(
            raw_transcript="",
            recovered_transcript="",
            canonical_question="",
            intent_id="",
            confidence=0.0,
            ambiguous=True,
        )
        _LAST = result
        return result

    # 1) Bank candidate search on RAW (primary)
    raw_cands = search_bank_candidates(raw_n, k=5)
    stages["bank_search_raw"] = [
        {"intent_id": c.intent_id, "combined": round(c.combined, 3), "phonetic": round(c.phonetic, 3)}
        for c in raw_cands
    ]

    # 2) Existing recovery stack (acronym → tech → phrase) via repair_technical_terms
    from app.services.technical_term_repair import repair_technical_terms

    recovered = repair_technical_terms(raw_n, prior_topic=prior_topic)
    stages["recovered_transcript"] = recovered

    try:
        from app.services.tech_acronym_recovery import last_acronym_recovery

        acr = last_acronym_recovery()
        if acr is not None:
            stages["acronym"] = {
                "applied": bool(acr.replacements),
                "recovered": acr.recovered_transcript,
                "matched_intent": acr.matched_intent,
            }
    except Exception:
        pass
    try:
        from app.services.interview_phrase_recovery import last_phrase_recovery

        phr = last_phrase_recovery()
        if phr is not None:
            stages["phrase"] = {
                "applied": phr.applied,
                "recovered": phr.recovered_transcript,
                "matched_intent": phr.matched_intent,
            }
    except Exception:
        pass

    # 3) Re-search on recovered text; merge best per intent
    rec_cands = search_bank_candidates(recovered, k=5) if recovered != raw_n else []
    stages["bank_search_recovered"] = [
        {"intent_id": c.intent_id, "combined": round(c.combined, 3)} for c in rec_cands
    ]

    merged: dict[str, BankCandidate] = {c.intent_id: c for c in raw_cands}
    for c in rec_cands:
        # Slight boost for recovered-path hits
        boosted = BankCandidate(
            intent_id=c.intent_id,
            canonical=c.canonical,
            category=c.category,
            topic=c.topic,
            question_type=c.question_type,
            phonetic=c.phonetic,
            lexical=c.lexical,
            structure=c.structure,
            lexicon=c.lexicon,
            bank_prior=c.bank_prior,
            combined=min(1.0, c.combined + 0.03),
            alias_hit=c.alias_hit,
        )
        prev = merged.get(c.intent_id)
        if prev is None or boosted.combined > prev.combined:
            merged[c.intent_id] = boosted

    # Phrase/acronym suggested intents get a nudge if present
    for key in ("phrase", "acronym"):
        mid = (stages.get(key) or {}).get("matched_intent") or ""
        if mid and mid in merged:
            c = merged[mid]
            merged[mid] = BankCandidate(
                **{**c.__dict__, "combined": min(1.0, c.combined + 0.04)}
            )

    candidates = sorted(merged.values(), key=lambda c: c.combined, reverse=True)[:5]
    best = candidates[0] if candidates else None
    second = candidates[1].combined if len(candidates) > 1 else 0.0
    margin = (best.combined - second) if best else 0.0

    ambiguous = False
    intent_id = ""
    canonical = recovered
    confidence = 0.0

    if best is None:
        ambiguous = True
    elif best.combined >= _MIN_ACCEPT and margin >= _MIN_MARGIN:
        intent_id = best.intent_id
        canonical = best.canonical
        confidence = best.combined
    elif best.combined >= _MIN_ACCEPT and margin < _MIN_MARGIN:
        ambiguous = True
        confidence = best.combined
        # Keep recovered text; do not force canonical
        canonical = recovered
    else:
        ambiguous = True
        confidence = best.combined if best else 0.0
        canonical = recovered

    # Special hard cases (evidence already in candidates; enforce safety)
    low_raw = _fold(raw_n)
    if re.search(r"\bhow (?:do|did|would) you plan your (?:project|work)\b", low_raw):
        if intent_id == "cv.projects_overview":
            ambiguous = True
            intent_id = ""
            canonical = recovered
            confidence = min(confidence, 0.55)

    result = UnderstandingResult(
        raw_transcript=raw_n,
        recovered_transcript=recovered,
        canonical_question=canonical,
        intent_id=intent_id,
        confidence=confidence,
        ambiguous=ambiguous,
        candidates=candidates,
        recovery_stages=stages,
        margin=margin,
    )
    _LAST = result
    logger.info(
        "BANK_GUIDED raw=%r recovered=%r canonical=%r intent=%s conf=%.3f amb=%s margin=%.3f top=%s",
        result.raw_transcript,
        result.recovered_transcript,
        result.canonical_question,
        result.intent_id or "-",
        result.confidence,
        result.ambiguous,
        result.margin,
        [(c.intent_id, round(c.combined, 3)) for c in result.candidates[:3]],
    )
    return result


def apply_bank_guided_transcript(raw: str, *, prior_topic: Optional[str] = None) -> str:
    """
    Transcript for display/match: prefer canonical when bank-guided is confident.
    """
    u = understand_interview_question(raw, prior_topic=prior_topic)
    if u.intent_id and not u.ambiguous and u.confidence >= _MIN_ACCEPT:
        return u.canonical_question
    return u.recovered_transcript or u.raw_transcript
