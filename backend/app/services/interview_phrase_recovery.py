"""
INTERVIEW_PHRASE_RECOVERY

Runs AFTER acronym + technical-term recovery, BEFORE MAIN_REQUEST_EXTRACTION:

  STT → ACRONYM → TECH_TERM → INTERVIEW_PHRASE → MAIN_REQUEST → INTENT

Recovers common interview utterances when STT produces a phonetically similar
but linguistically wrong sentence (e.g. \"and you plan your project\" →
\"Explain your project\").

Never uses fuzzy text alone. Requires phonetic + semantic + bank + structure
evidence with a margin over the runner-up. Prefer abstain over wrong rewrite.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[A-Za-z0-9']+")
_LOCK = threading.Lock()
_PHRASE_CACHE: tuple["PhraseEntry", ...] | None = None
_LAST_RESULT: "PhraseRecoveryResult | None" = None

_MIN_COMBINED = 0.78
_MIN_MARGIN = 0.10

# Seed interview phrases with preferred bank intents when known.
_SEED_PHRASES: tuple[tuple[str, str], ...] = (
    ("Tell me about yourself", "intro.tell_me_about_yourself"),
    ("Explain your project", "cv.projects_overview"),
    ("Tell me about your project", "cv.projects_overview"),
    ("Walk me through your project", "cv.projects_overview"),
    ("What projects have you worked on?", "cv.projects_overview"),
    ("What did you build?", ""),
    ("What was your role?", "proj.similarity.role"),
    ("What problem did you solve?", ""),
    ("How did you implement it?", ""),
    ("Why did you choose it?", ""),
    ("Why did you use RAG?", "proj.similarity.is_rag"),
    ("How did you use RAG?", ""),
    ("What challenges did you face?", "proj.similarity.challenges"),
    ("How did you solve the problem?", ""),
    ("How did you test it?", ""),
    ("How did you evaluate it?", ""),
    ("How did you evaluate the model?", ""),
    ("What was the result?", ""),
    ("What was the outcome?", ""),
    ("What was the business value?", ""),
    ("What would you improve?", ""),
    ("How does the system work?", ""),
    ("Describe your experience", ""),
    ("Tell me about your AI experience", ""),
    ("Why should we hire you?", ""),
    ("Why do you want this role?", ""),
    ("How do you plan your project?", ""),
)

# High-precision STT utterance corruptions → canonical phrase.
# Applied only after multi-candidate scoring confirms margin.
_CURATED: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?i)^(?:and\s+you\s+plan|and\s+explain|an\s+explain)\s+your\s+projects?\??\.?$"),
        "Explain your project",
    ),
    (
        re.compile(r"(?i)^explain\s+you(?:r)?\s+projects?\??\.?$"),
        "Explain your project",
    ),
    (
        re.compile(r"(?i)^(?:tell\s+me\s+a\s+boat|tell\s+me\s+about\s+you\s+self|tell\s+me\s+aboat)\s*(?:yourself)?\??\.?$"),
        "Tell me about yourself",
    ),
    (
        re.compile(r"(?i)^tell\s+me\s+about\s+you\s+self\??\.?$"),
        "Tell me about yourself",
    ),
    (
        re.compile(r"(?i)^(?:walk|watch)\s+me\s+through\s+(?:a\s+|your\s+|the\s+)?projects?\??\.?$"),
        "Walk me through your project",
    ),
    (
        re.compile(r"(?i)^tell\s+me\s+about\s+(?:a\s+|the\s+|your\s+)?projects?\??\.?$"),
        "Tell me about your project",
    ),
    (
        re.compile(r"(?i)^what\s+(?:was|is)\s+your\s+roll\??\.?$"),
        "What was your role?",
    ),
    (
        re.compile(r"(?i)^what\s+did\s+you\s+(?:built|bill)\??\.?$"),
        "What did you build?",
    ),
    (
        re.compile(r"(?i)^why\s+did\s+you\s+use\s+(?:rack|drag|rags|ragged)\??\.?$"),
        "Why did you use RAG?",
    ),
    (
        re.compile(r"(?i)^how\s+did\s+you\s+(?:implement|implemen|in\s+plement)\s+it\??\.?$"),
        "How did you implement it?",
    ),
    (
        re.compile(r"(?i)^what\s+challenges?\s+did\s+you\s+(?:face|faced|phase)\??\.?$"),
        "What challenges did you face?",
    ),
    (
        re.compile(r"(?i)^what\s+was\s+the\s+(?:outcome|out\s+come)\??\.?$"),
        "What was the outcome?",
    ),
    (
        re.compile(r"(?i)^what\s+was\s+the\s+results?\??\.?$"),
        "What was the result?",
    ),
    (
        re.compile(r"(?i)^how\s+did\s+you\s+evaluate\s+(?:the\s+)?(?:model|it)\??\.?$"),
        "How did you evaluate the model?",
    ),
    (
        re.compile(r"(?i)^describe\s+your\s+(?:experience|experiences)\??\.?$"),
        "Describe your experience",
    ),
    (
        re.compile(r"(?i)^why\s+should\s+we\s+(?:hire|higher)\s+you\??\.?$"),
        "Why should we hire you?",
    ),
]

_STOP = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "in",
    "on",
    "for",
    "and",
    "or",
    "me",
    "you",
    "your",
    "it",
    "is",
    "was",
    "did",
    "do",
    "does",
    "about",
}


@dataclass(frozen=True)
class PhraseEntry:
    phrase: str
    intent_id: str = ""
    source: str = "seed"


@dataclass(frozen=True)
class PhraseCandidateScore:
    phrase: str
    phonetic: float
    semantic: float
    bank_support: float
    structure: float
    combined: float
    intent_id: str = ""
    evidence: tuple[str, ...] = ()


@dataclass
class PhraseRecoveryResult:
    raw_transcript: str
    recovered_transcript: str
    recovery_type: str = ""
    applied: bool = False
    abstained: bool = False
    candidates: list[PhraseCandidateScore] = field(default_factory=list)
    margin: float = 0.0
    matched_intent: str = ""

    def as_dict(self) -> dict:
        return {
            "raw_transcript": self.raw_transcript,
            "recovered_transcript": self.recovered_transcript,
            "recovery_type": self.recovery_type,
            "applied": self.applied,
            "abstained": self.abstained,
            "margin": round(self.margin, 3),
            "matched_intent": self.matched_intent,
            "candidates": [
                {
                    "candidate": c.phrase,
                    "phonetic_score": round(c.phonetic, 3),
                    "semantic_score": round(c.semantic, 3),
                    "bank_support": round(c.bank_support, 3),
                    "structure_score": round(c.structure, 3),
                    "combined_score": round(c.combined, 3),
                    "intent_id": c.intent_id,
                    "evidence": list(c.evidence),
                }
                for c in self.candidates
            ],
        }


def last_phrase_recovery() -> Optional[PhraseRecoveryResult]:
    return _LAST_RESULT


def clear_phrase_cache() -> None:
    global _PHRASE_CACHE
    with _LOCK:
        _PHRASE_CACHE = None
    _content_tokens.cache_clear()


def _norm(text: str) -> str:
    return " ".join((text or "").strip().split())


def _fold(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    return " ".join(cleaned.split())


@lru_cache(maxsize=4096)
def _content_tokens(text: str) -> tuple[str, ...]:
    return tuple(t for t in _WORD.findall(_fold(text)) if t not in _STOP and len(t) > 1)


def _consonant_skel(text: str) -> str:
    raw = re.sub(r"[^a-z]", "", _fold(text))
    return re.sub(r"[aeiou]", "", raw)


def _action_type(text: str) -> str:
    low = _fold(text)
    if re.search(r"\bhow (?:do|did|would|can) you plan\b", low) or (
        re.search(r"\bplan your\b", low) and re.search(r"\bhow\b", low)
    ):
        return "plan_method"
    if re.search(r"\bwhy\b", low):
        return "reason"
    if re.search(r"\bhow\b", low):
        return "method"
    if re.search(r"\bwhat (?:was|were|is|are)\b", low):
        return "fact"
    if re.search(r"\bwhat did you\b", low):
        return "fact"
    if re.search(r"\b(?:explain|describe|tell me|walk me|watch me)\b", low):
        return "describe"
    # Known STT garble of "explain …"
    if re.search(r"\band you plan\b", low) or re.search(r"\band explain\b", low):
        return "describe"
    if re.search(r"\bplan\b", low):
        return "plan_method"
    return "other"


def _phonetic_score(raw: str, phrase: str) -> float:
    a = _fold(raw)
    b = _fold(phrase)
    seq = SequenceMatcher(None, a, b).ratio()
    sk = SequenceMatcher(None, _consonant_skel(raw), _consonant_skel(phrase)).ratio()
    # Token-level best alignment
    ta, tb = list(_content_tokens(raw)), list(_content_tokens(phrase))
    if ta and tb:
        hits = 0.0
        used = set()
        for x in ta:
            best_i, best_s = -1, 0.0
            for i, y in enumerate(tb):
                if i in used:
                    continue
                s = SequenceMatcher(None, x, y).ratio()
                # Soft phonetic near-equals
                if {x, y} <= {"explain", "plan"} or ({x, y} == {"and", "explain"}):
                    s = max(s, 0.55)
                if {x, y} <= {"role", "roll"}:
                    s = max(s, 0.95)
                if {x, y} <= {"rag", "rack", "drag", "rags", "ragged"}:
                    s = max(s, 0.9)
                if s > best_s:
                    best_s, best_i = s, i
            if best_s >= 0.72:
                hits += best_s
                used.add(best_i)
        tok = hits / max(len(ta), len(tb))
    else:
        tok = 0.0
    return max(0.0, min(1.0, 0.35 * seq + 0.25 * sk + 0.40 * tok))


def _semantic_score(raw: str, phrase: str) -> float:
    ta, tb = set(_content_tokens(raw)), set(_content_tokens(phrase))
    if not ta or not tb:
        return 0.0
    overlap = len(ta & tb) / len(ta | tb)
    # Soft synonym / STT bridges
    bridges = {
        frozenset({"explain", "plan"}),  # only with describe_garble handled in structure
        frozenset({"role", "roll"}),
        frozenset({"build", "built", "bill"}),
        frozenset({"outcome", "result"}),
        frozenset({"face", "phase", "faced"}),
    }
    bridge_hit = 0.0
    for pair in bridges:
        if (pair & ta) and (pair & tb):
            bridge_hit = 0.15
            break
    # Topic anchors
    topic_bonus = 0.0
    for anchor in ("project", "yourself", "rag", "role", "challenge", "experience", "model"):
        if anchor in ta and anchor in tb:
            topic_bonus = 0.2
            break
    return max(0.0, min(1.0, 0.65 * overlap + bridge_hit + topic_bonus))


def _structure_score(raw: str, phrase: str) -> float:
    ra, pa = _action_type(raw), _action_type(phrase)
    if ra == pa:
        base = 0.9
    elif {ra, pa} == {"describe", "other"}:
        base = 0.55
    elif ra == "describe" and pa == "plan_method":
        # Critical: do not treat plan-method as explain
        base = 0.15
    elif ra == "plan_method" and pa == "describe":
        base = 0.10
    else:
        base = 0.35
    # Length compatibility
    nw_r = max(1, len(_WORD.findall(raw)))
    nw_p = max(1, len(_WORD.findall(phrase)))
    ratio = min(nw_r, nw_p) / max(nw_r, nw_p)
    return max(0.0, min(1.0, 0.7 * base + 0.3 * ratio))


def _seed_phrase_bank() -> list[PhraseEntry]:
    entries: dict[str, PhraseEntry] = {}
    for p, intent in _SEED_PHRASES:
        key = _fold(p)
        entries[key] = PhraseEntry(phrase=p, intent_id=intent, source="seed")

    try:
        from app.services.question_bank import question_bank

        question_bank.load()
        for e in question_bank.entries:
            q = (e.question or "").strip()
            if 3 <= len(_WORD.findall(q)) <= 14:
                key = _fold(q)
                if key not in entries or not entries[key].intent_id:
                    entries[key] = PhraseEntry(phrase=q.rstrip("?"), intent_id=e.id, source="bank")
            for alias in e.aliases or ():
                a = (alias or "").strip()
                if not a or not (3 <= len(_WORD.findall(a)) <= 14):
                    continue
                # Prefer interview-shaped aliases
                low = a.lower()
                if not re.search(
                    r"\b(tell me|explain|walk me|describe|what|why|how|who)\b",
                    low,
                ):
                    continue
                if len(_WORD.findall(a)) > 10:
                    continue
                key = _fold(a)
                display = a[0].upper() + a[1:] if a else a
                if not display.endswith("?") and re.match(
                    r"(?i)^(what|why|how|who|when|where)\b", display
                ):
                    display = display.rstrip(".") + "?"
                if key not in entries:
                    entries[key] = PhraseEntry(phrase=display, intent_id=e.id, source="alias")
                elif not entries[key].intent_id:
                    entries[key] = PhraseEntry(
                        phrase=entries[key].phrase,
                        intent_id=e.id,
                        source=entries[key].source,
                    )
    except Exception:
        pass

    # Attach intents lazily only for seed phrases missing intent (avoid N bank matches).
    return list(entries.values())


def _lookup_intent(phrase: str) -> str:
    try:
        from app.services.question_bank import question_bank

        question_bank.load()
        m = question_bank.match(phrase, tech_repair=False)
        return m.entry.id if m is not None else ""
    except Exception:
        return ""


def get_phrase_bank() -> tuple[PhraseEntry, ...]:
    global _PHRASE_CACHE
    with _LOCK:
        if _PHRASE_CACHE is None:
            items = _seed_phrase_bank()
            # Prefer shorter canonical interview prompts first when equal
            items.sort(key=lambda e: (0 if e.source == "seed" else 1, len(e.phrase)))
            _PHRASE_CACHE = tuple(items)
        return _PHRASE_CACHE


def _bank_support(entry: PhraseEntry) -> float:
    if entry.intent_id:
        return 0.95 if entry.source in {"bank", "alias"} else 0.85
    # Seed without intent still counts as interview-phrase prior
    return 0.55 if entry.source == "seed" else 0.35


def _score_pair(raw: str, entry: PhraseEntry) -> PhraseCandidateScore:
    phonetic = _phonetic_score(raw, entry.phrase)
    semantic = _semantic_score(raw, entry.phrase)
    bank = _bank_support(entry)
    structure = _structure_score(raw, entry.phrase)
    combined = (
        0.30 * phonetic
        + 0.25 * semantic
        + 0.25 * bank
        + 0.15 * structure
        + 0.05 * (0.6 if _action_type(raw) == _action_type(entry.phrase) else 0.2)
    )
    # Hard penalty: plan-method raw must not win describe phrase
    if _action_type(raw) == "plan_method" and _action_type(entry.phrase) == "describe":
        combined *= 0.45
        structure = min(structure, 0.2)
    if _action_type(raw) == "describe" and _action_type(entry.phrase) == "plan_method":
        # "and you plan" (describe garble) vs true plan phrase — penalize plan
        if re.search(r"(?i)\band you plan\b", raw):
            combined *= 0.55
    evidence = []
    if phonetic >= 0.7:
        evidence.append("phonetic")
    if semantic >= 0.55:
        evidence.append("semantic")
    if bank >= 0.7:
        evidence.append("question_bank")
    if structure >= 0.7:
        evidence.append("structure")
    return PhraseCandidateScore(
        phrase=entry.phrase,
        phonetic=phonetic,
        semantic=semantic,
        bank_support=bank,
        structure=structure,
        combined=combined,
        intent_id=entry.intent_id,
        evidence=tuple(evidence or ("weak",)),
    )


def _top_candidates(raw: str, *, k: int = 3) -> list[PhraseCandidateScore]:
    """Score seeds + a tiny filtered alias subset."""
    raw_toks = set(_content_tokens(raw))
    raw_skel = _consonant_skel(raw)
    raw_n = len(_WORD.findall(raw))
    filtered: list[PhraseEntry] = []
    for e in get_phrase_bank():
        if e.source == "seed":
            filtered.append(e)
            continue
        pn = len(_WORD.findall(e.phrase))
        if pn > 8 or abs(pn - raw_n) > 3:
            continue
        et = set(_content_tokens(e.phrase))
        if raw_toks and et and len(raw_toks & et) >= 1:
            if SequenceMatcher(None, raw_skel, _consonant_skel(e.phrase)).ratio() >= 0.5:
                filtered.append(e)
        if len(filtered) > 80:
            break
    scored = [_score_pair(raw, e) for e in filtered]
    scored.sort(key=lambda c: c.combined, reverse=True)
    out: list[PhraseCandidateScore] = []
    seen = set()
    for c in scored:
        key = _fold(c.phrase)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= k:
            break
    return out


def recover_interview_phrases(text: str) -> PhraseRecoveryResult:
    """Recover a common interview phrase when evidence + margin are strong."""
    global _LAST_RESULT
    raw = _norm(text)
    if not raw:
        result = PhraseRecoveryResult(raw_transcript="", recovered_transcript="")
        _LAST_RESULT = result
        return result

    # Already a clean seed/bank phrase → no-op (check seeds + short index only)
    folded = _fold(raw)
    seed_folds = {_fold(p): intent for p, intent in _SEED_PHRASES}
    if folded in seed_folds:
        result = PhraseRecoveryResult(
            raw_transcript=raw,
            recovered_transcript=raw,
            recovery_type="",
            applied=False,
            matched_intent=seed_folds[folded],
        )
        _LAST_RESULT = result
        return result
    for e in get_phrase_bank():
        if e.source != "seed" and len(_WORD.findall(e.phrase)) > 8:
            continue
        if _fold(e.phrase) == folded:
            result = PhraseRecoveryResult(
                raw_transcript=raw,
                recovered_transcript=raw,
                recovery_type="",
                applied=False,
                matched_intent=e.intent_id,
            )
            _LAST_RESULT = result
            return result

    # Curated STT corruptions first (cheap); only score rivals when needed.
    curated_target = None
    for pat, phrase in _CURATED:
        if pat.match(raw):
            curated_target = phrase
            break

    candidates: list[PhraseCandidateScore] = []
    applied = False
    abstained = False
    recovered = raw
    recovery_type = ""
    matched_intent = ""
    margin = 0.0

    if curated_target:
        if _fold(curated_target) == folded:
            result = PhraseRecoveryResult(
                raw_transcript=raw,
                recovered_transcript=raw,
                recovery_type="",
                applied=False,
                matched_intent=_lookup_intent(curated_target),
            )
            _LAST_RESULT = result
            return result
        if _action_type(raw) == "plan_method" and _action_type(curated_target) == "describe":
            abstained = True
            candidates = _top_candidates(raw, k=3)
        else:
            curated_entry = next(
                (e for e in get_phrase_bank() if _fold(e.phrase) == _fold(curated_target)),
                PhraseEntry(phrase=curated_target, source="seed"),
            )
            curated_score = _score_pair(raw, curated_entry)
            curated_score = PhraseCandidateScore(
                phrase=curated_score.phrase,
                phonetic=max(curated_score.phonetic, 0.88),
                semantic=curated_score.semantic,
                bank_support=curated_score.bank_support,
                structure=max(curated_score.structure, 0.8),
                combined=max(curated_score.combined, 0.82),
                intent_id=curated_score.intent_id,
                evidence=tuple(
                    dict.fromkeys(curated_score.evidence + ("curated_pattern", "phonetic"))
                ),
            )
            # Only score seed rivals for margin (keep curated path fast).
            rivals: list[PhraseCandidateScore] = []
            for e in get_phrase_bank():
                if e.source != "seed":
                    continue
                if _fold(e.phrase) == _fold(curated_target):
                    continue
                rivals.append(_score_pair(raw, e))
            rivals.sort(key=lambda c: c.combined, reverse=True)
            rival_score = 0.0
            for c in rivals[:5]:
                if _action_type(c.phrase) != _action_type(curated_target):
                    rival_score = max(rival_score, c.combined)
                    continue
                sk = SequenceMatcher(
                    None, _consonant_skel(c.phrase), _consonant_skel(curated_target)
                ).ratio()
                if sk < 0.8:
                    rival_score = max(rival_score, c.combined)
            margin = curated_score.combined - rival_score
            candidates = [curated_score] + rivals[:2]
            if margin >= 0.06 and curated_score.phonetic >= 0.75:
                recovered = curated_target
                applied = True
                recovery_type = "interview_phrase"
                matched_intent = curated_score.intent_id or _lookup_intent(curated_target)
            else:
                abstained = True
    else:
        candidates = _top_candidates(raw, k=3)
        best = candidates[0] if candidates else None
        second = candidates[1].combined if len(candidates) > 1 else 0.0
        margin = (best.combined - second) if best else 0.0
        if best is not None:
            if SequenceMatcher(None, _fold(raw), _fold(best.phrase)).ratio() >= 0.92:
                recovered = raw
            elif (
                best.combined >= _MIN_COMBINED
                and margin >= _MIN_MARGIN
                and best.phonetic >= 0.62
                and best.structure >= 0.55
            ):
                recovered = best.phrase
                applied = True
                recovery_type = "interview_phrase"
                matched_intent = best.intent_id or _lookup_intent(best.phrase)
            else:
                abstained = True

    result = PhraseRecoveryResult(
        raw_transcript=raw,
        recovered_transcript=recovered,
        recovery_type=recovery_type,
        applied=applied,
        abstained=abstained and not applied,
        candidates=candidates,
        margin=margin,
        matched_intent=matched_intent,
    )
    _LAST_RESULT = result
    if applied or abstained:
        logger.info(
            "INTERVIEW_PHRASE_RECOVERY raw=%r recovered=%r applied=%s margin=%.3f "
            "matched_intent=%s top=%s",
            result.raw_transcript,
            result.recovered_transcript,
            result.applied,
            result.margin,
            result.matched_intent or "-",
            [
                (
                    c.phrase,
                    round(c.combined, 3),
                    round(c.phonetic, 3),
                    round(c.semantic, 3),
                    round(c.bank_support, 3),
                )
                for c in result.candidates[:3]
            ],
        )
    return result


def apply_interview_phrase_recovery(text: str) -> str:
    return recover_interview_phrases(text).recovered_transcript
