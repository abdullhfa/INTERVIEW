"""
TECH_ACRONYM_RECOVERY

Runs BEFORE TECH_TERM_RECOVERY / short_tech_recovery:

  STT → Acronym Recovery → Technical Term Recovery → Question Understanding

Purpose: spoken letter-by-letter acronyms (\"el el em\") and compact STT
garbles (\"Lalam\") must not be force-mapped to lookalike product names
(LLaMA / Llama). Prefer bank-backed acronyms when evidence + margin are clear;
otherwise abstain.

Bug-fix for live semantic miscorrection (What is LLM? → Lalam → LLaMA).
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
_VOCAB_CACHE: tuple[str, ...] | None = None
_LAST_RESULT: "AcronymRecoveryResult | None" = None

# Spoken letter names commonly produced by Whisper for letter-by-letter speech.
_LETTER_NAMES: dict[str, tuple[str, ...]] = {
    "a": ("a", "ay", "eh"),
    "b": ("b", "be", "bee"),
    "c": ("c", "see", "sea", "cee"),
    "d": ("d", "dee", "de"),
    "e": ("e", "ee", "eh"),
    "f": ("f", "ef", "eff"),
    "g": ("g", "gee", "jee"),
    "h": ("h", "aitch", "aitch"),
    "i": ("i", "eye", "ai"),
    "j": ("j", "jay"),
    "k": ("k", "kay"),
    "l": ("l", "el", "ell", "al"),
    "m": ("m", "em", "um"),
    "n": ("n", "en", "an"),
    "o": ("o", "oh", "owe"),
    "p": ("p", "pee", "pea"),
    "q": ("q", "cue", "queue"),
    "r": ("r", "are", "ar"),
    "s": ("s", "ess", "es"),
    "t": ("t", "tee", "tea", "ti"),
    "u": ("u", "you", "yu"),
    "v": ("v", "vee"),
    "w": ("w", "doubleu", "double-u"),
    "x": ("x", "ex", "ecks"),
    "y": ("y", "why", "wye"),
    "z": ("z", "zee", "zed"),
}

# Compact STT merges that must NOT auto-map to product names.
# Each entry: (pattern, preferred_acronym, evidence_tag)
_COMPACT_GARBLES: list[tuple[re.Pattern[str], str, str]] = [
    # LLM spoken merges — never prefer LLaMA from these alone
    (re.compile(r"(?i)\blalam\b"), "LLM", "compact_llm"),
    (re.compile(r"(?i)\bellem\b"), "LLM", "compact_llm"),
    (re.compile(r"(?i)\belem\b"), "LLM", "compact_llm"),
    (re.compile(r"(?i)\bellm\b"), "LLM", "compact_llm"),
    (re.compile(r"(?i)\bllum\b"), "LLM", "compact_llm"),
    (re.compile(r"(?i)\bel\s*el\s*em\b"), "LLM", "spoken_letters"),
    (re.compile(r"(?i)\bl\s+l\s+m\b"), "LLM", "spoken_letters"),
    (re.compile(r"(?i)\bl[\.\-\s]*l[\.\-\s]*m\b"), "LLM", "spoken_letters"),
    # RAG
    (re.compile(r"(?i)\bare\s+a\s+g\b"), "RAG", "spoken_letters"),
    (re.compile(r"(?i)\br\s+a\s+g\b"), "RAG", "spoken_letters"),
    # NLP
    (re.compile(r"(?i)\ben\s+el\s+pee\b"), "NLP", "spoken_letters"),
    (re.compile(r"(?i)\bn\s+l\s+p\b"), "NLP", "spoken_letters"),
    # CNN / RNN
    (re.compile(r"(?i)\bsee\s+en\s+en\b"), "CNN", "spoken_letters"),
    (re.compile(r"(?i)\bc\s+n\s+n\b"), "CNN", "spoken_letters"),
    (re.compile(r"(?i)\bare\s+en\s+en\b"), "RNN", "spoken_letters"),
    (re.compile(r"(?i)\br\s+n\s+n\b"), "RNN", "spoken_letters"),
    # LSTM
    (re.compile(r"(?i)\bel\s+es\s+tee\s+em\b"), "LSTM", "spoken_letters"),
    (re.compile(r"(?i)\bl\s+s\s+t\s+m\b"), "LSTM", "spoken_letters"),
    # GPU / CPU
    (re.compile(r"(?i)\bgee\s+pee\s+you\b"), "GPU", "spoken_letters"),
    (re.compile(r"(?i)\bg\s+p\s+u\b"), "GPU", "spoken_letters"),
    (re.compile(r"(?i)\bsee\s+pee\s+you\b"), "CPU", "spoken_letters"),
    (re.compile(r"(?i)\bc\s+p\s+u\b"), "CPU", "spoken_letters"),
    # STT / TTS / VAD
    (re.compile(r"(?i)\bess\s+tee\s+tee\b"), "STT", "spoken_letters"),
    (re.compile(r"(?i)\bs\s+t\s+t\b"), "STT", "spoken_letters"),
    (re.compile(r"(?i)\btee\s+tee\s+ess\b"), "TTS", "spoken_letters"),
    (re.compile(r"(?i)\bt\s+t\s+s\b"), "TTS", "spoken_letters"),
    (re.compile(r"(?i)\bvee\s+ay\s+dee\b"), "VAD", "spoken_letters"),
    (re.compile(r"(?i)\bv\s+a\s+d\b"), "VAD", "spoken_letters"),
    # n8n
    (re.compile(r"(?i)\ben\s+eight\s+en\b"), "n8n", "spoken_letters"),
    (re.compile(r"(?i)\bn\s+eight\s+n\b"), "n8n", "spoken_letters"),
    # ML / DL / AI / API / SQL / ANN
    (re.compile(r"(?i)\bem\s+el\b"), "ML", "spoken_letters"),
    (re.compile(r"(?i)\bm\s+l\b"), "ML", "spoken_letters"),
    (re.compile(r"(?i)\bdee\s+el\b"), "DL", "spoken_letters"),
    (re.compile(r"(?i)\bd\s+l\b"), "DL", "spoken_letters"),
    (re.compile(r"(?i)\bay\s+eye\b"), "AI", "spoken_letters"),
    (re.compile(r"(?i)\ba\s+i\b"), "AI", "spoken_letters"),
    (re.compile(r"(?i)\bay\s+pee\s+eye\b"), "API", "spoken_letters"),
    (re.compile(r"(?i)\ba\s+p\s+i\b"), "API", "spoken_letters"),
    (re.compile(r"(?i)\bess\s+queue\s+el\b"), "SQL", "spoken_letters"),
    (re.compile(r"(?i)\bs\s+q\s+l\b"), "SQL", "spoken_letters"),
    (re.compile(r"(?i)\bay\s+en\s+en\b"), "ANN", "spoken_letters"),
    (re.compile(r"(?i)\ba\s+n\s+n\b"), "ANN", "spoken_letters"),
]

# Product / model names that collide with acronym garbles.
# Used only as competing candidates — never as automatic compact remap.
_COLLISION_RIVALS: dict[str, tuple[str, ...]] = {
    "LLM": ("LLaMA", "Llama", "Ollama"),
    "RAG": ("RAGAS",),
    "API": (),
}

_MIN_ACCEPT = 0.72
_MIN_MARGIN = 0.12

# Seed acronyms always considered (bank + CV coverage).
_SEED_ACRONYMS: tuple[str, ...] = (
    "AI",
    "ML",
    "DL",
    "LLM",
    "RAG",
    "NLP",
    "ANN",
    "CNN",
    "RNN",
    "LSTM",
    "API",
    "SQL",
    "GPU",
    "CPU",
    "STT",
    "TTS",
    "VAD",
    "RAGAS",
    "MCP",
    "GPT",
    "WER",
    "VRAM",
    "CUDA",
    "n8n",
    "TF-IDF",
    "LoRA",
)


@dataclass(frozen=True)
class AcronymCandidate:
    acronym: str
    score: float
    evidence: tuple[str, ...]


@dataclass
class AcronymRecoveryResult:
    raw_transcript: str
    recovered_transcript: str
    replacements: list[tuple[str, str, float]] = field(default_factory=list)
    candidates: list[AcronymCandidate] = field(default_factory=list)
    abstained: bool = False
    matched_intent: str = ""

    def as_dict(self) -> dict:
        return {
            "raw_transcript": self.raw_transcript,
            "recovered_transcript": self.recovered_transcript,
            "replacements": [
                {"raw": a, "normalized": b, "score": round(c, 3)} for a, b, c in self.replacements
            ],
            "candidates": [
                {
                    "acronym": c.acronym,
                    "score": round(c.score, 3),
                    "evidence": list(c.evidence),
                }
                for c in self.candidates
            ],
            "abstained": self.abstained,
            "matched_intent": self.matched_intent,
        }


def last_acronym_recovery() -> Optional[AcronymRecoveryResult]:
    return _LAST_RESULT


def clear_acronym_vocab_cache() -> None:
    global _VOCAB_CACHE
    with _LOCK:
        _VOCAB_CACHE = None
    _bank_acronym_hits.cache_clear()
    _spoken_patterns.cache_clear()


def _norm_space(text: str) -> str:
    return " ".join((text or "").strip().split())


def _is_acronym_like(token: str) -> bool:
    t = (token or "").strip()
    if not t:
        return False
    if t.lower() == "n8n":
        return True
    if re.fullmatch(r"[A-Za-z]{2,6}", t) and t.upper() == t:
        return True
    if re.fullmatch(r"[A-Za-z][\w\-]{1,7}", t) and sum(ch.isupper() for ch in t) >= 2:
        return True
    return False


def _seed_acronym_vocab() -> set[str]:
    vocab: set[str] = set(_SEED_ACRONYMS)
    try:
        from app.services.domain_terms import _TERMS  # noqa: SLC001

        for canon in _TERMS:
            if _is_acronym_like(canon) or canon in _SEED_ACRONYMS:
                vocab.add(canon)
    except Exception:
        pass
    try:
        from app.services.question_bank import question_bank

        question_bank.load()
        for e in question_bank.entries:
            for kw in e.keywords or ():
                k = (kw or "").strip()
                if _is_acronym_like(k) or k.upper() in {a.upper() for a in _SEED_ACRONYMS}:
                    # Prefer seed casing when available
                    hit = next((s for s in _SEED_ACRONYMS if s.lower() == k.lower()), k.upper() if k.isalpha() else k)
                    vocab.add(hit)
            for tok in _WORD.findall(e.question or ""):
                if _is_acronym_like(tok):
                    hit = next((s for s in _SEED_ACRONYMS if s.lower() == tok.lower()), tok)
                    vocab.add(hit)
    except Exception:
        pass
    # Competing model names for scoring only (not automatic targets from letter garbles)
    vocab.update({"LLaMA", "Llama"})
    return vocab


def get_acronym_vocabulary() -> tuple[str, ...]:
    global _VOCAB_CACHE
    with _LOCK:
        if _VOCAB_CACHE is None:
            items = sorted(_seed_acronym_vocab(), key=lambda s: (-len(s), s.lower()))
            _VOCAB_CACHE = tuple(items)
        return _VOCAB_CACHE


@lru_cache(maxsize=1)
def _spoken_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Generate letter-name sequences for every acronym in vocab (e.g. el el em)."""
    out: list[tuple[re.Pattern[str], str]] = []
    for acr in get_acronym_vocabulary():
        if acr.lower() in {"llama", "ollama"}:
            continue
        letters = [ch.lower() for ch in acr if ch.isalnum()]
        if acr.lower() == "n8n":
            letters = ["n", "8", "n"]
        if len(letters) < 2 or len(letters) > 6:
            continue
        parts: list[str] = []
        ok = True
        for ch in letters:
            if ch == "8":
                parts.append(r"(?:eight|8)")
                continue
            names = _LETTER_NAMES.get(ch)
            if not names:
                ok = False
                break
            parts.append("(?:%s)" % "|".join(re.escape(n) for n in names))
        if not ok:
            continue
        body = r"[\s\.\-]+".join(parts)
        pat = re.compile(rf"(?i)\b{body}\b")
        out.append((pat, acr))
    return out


@lru_cache(maxsize=512)
def _bank_acronym_hits(acronym: str) -> tuple[float, str]:
    """
    Return (bank_support_score, best_intent_id) for definition-style questions.
    """
    try:
        from app.services.question_bank import question_bank

        question_bank.load()
    except Exception:
        return 0.0, ""

    acr = acronym.lower()
    best = 0.0
    best_id = ""
    for e in question_bank.entries:
        blob = " ".join(
            [
                e.question or "",
                " ".join(e.aliases or ()),
                " ".join(e.keywords or ()),
                e.id or "",
            ]
        ).lower()
        if acr not in blob and acr.replace("-", "") not in blob.replace("-", ""):
            continue
        score = 0.35
        q = (e.question or "").lower()
        if re.search(rf"\bwhat is (an? |the )?{re.escape(acr)}\b", q) or "large language model" in q and acr == "llm":
            score = 0.95
        elif any(
            re.search(rf"\bwhat is (an? |the )?{re.escape(acr)}\b", (a or "").lower())
            for a in (e.aliases or ())
        ):
            score = 0.90
        elif acr in {k.lower() for k in (e.keywords or ())}:
            score = max(score, 0.70)
        elif acr in (e.id or "").lower():
            score = max(score, 0.55)
        if score > best:
            best = score
            best_id = e.id
    return best, best_id


def _pronunciation_score(span: str, acronym: str) -> float:
    """Score how well a raw span looks like spoken/letter form of acronym."""
    raw = re.sub(r"[^a-z0-9]", "", (span or "").lower())
    letters = re.sub(r"[^a-z0-9]", "", acronym.lower())
    if not raw or not letters:
        return 0.0

    # Exact compacted letters (llm, rag)
    if raw == letters:
        return 1.0

    if acronym.upper() == "RAG":
        if raw in {"rag", "areag", "rag"}:
            return 0.93
        if "are" in (span or "").lower() and "g" in raw:
            return 0.90

    # Letter-name sequence already matched by pattern → high
    # Compact garbles for LLM family
    if acronym.upper() == "LLM":
        if raw in {"lalam", "ellem", "elem", "ellm", "llum", "llm"}:
            return 0.92
        # phonetic distance to letter collapse
        collapsed = raw
        for a, b in (("el", "l"), ("ell", "l"), ("em", "m"), ("al", "l"), ("um", "m")):
            collapsed = collapsed.replace(a, b)
        if collapsed == "llm" or collapsed.startswith("llm"):
            return 0.88

    # Rival product names
    if acronym.lower() in {"llama", "llma"}:
        if raw in {"llama", "lama", "llamma"}:
            return 0.95
        if raw == "lalam":
            # Compact letter merge is closer to L-L-M than to "llama"
            return 0.55
        return min(0.45, SequenceMatcher(None, raw, "llama").ratio())

    if acronym.upper() == "RAGAS":
        if raw in {"ragas", "rag ass", "ragas"}:
            return 0.95
        # Three-letter RAG spoken forms are not RAGAS
        if raw in {"areag", "rag", "raga"} or len(raw) <= 4:
            return 0.25

    if acronym.lower() == "n8n":
        if raw in {"n8n", "nen", "neightn", "eneighten"} or "eight" in (span or "").lower():
            return 0.95
        return SequenceMatcher(None, raw, "n8n").ratio()

    ratio = SequenceMatcher(None, raw, letters).ratio()
    # Slight boost when span length ≈ letter count * 1–2 (spoken names)
    return min(1.0, ratio)


def _context_boost(text: str) -> float:
    low = (text or "").lower()
    if re.search(r"\bwhat(?:'s| is| are)\b", low):
        return 0.12
    if re.search(r"\b(?:define|explain|why|how)\b", low):
        return 0.08
    return 0.0


def _score_candidate(span: str, acronym: str, full_text: str) -> AcronymCandidate:
    pron = _pronunciation_score(span, acronym)
    bank, intent = _bank_acronym_hits(acronym)
    ctx = _context_boost(full_text)
    # Weighted blend — bank evidence critical for LLM vs LLaMA
    score = 0.45 * pron + 0.40 * bank + 0.15 * (0.5 + ctx)
    evidence = []
    if pron >= 0.75:
        evidence.append("pronunciation")
    if bank >= 0.55:
        evidence.append("question_bank")
    if ctx > 0:
        evidence.append("question_context")
    if acronym.upper() == "LLM" and span.lower() in {"lalam", "ellem", "elem", "ellm"}:
        evidence.append("compact_not_llama")
    return AcronymCandidate(acronym=acronym, score=score, evidence=tuple(evidence or ("weak",)))


def _pick_winner(
    span: str,
    primary: str,
    full_text: str,
    *,
    pattern_confirmed: bool = False,
) -> tuple[Optional[str], list[AcronymCandidate], bool]:
    """Compare primary acronym vs collision rivals; abstain if too close."""
    rivals = _COLLISION_RIVALS.get(primary.upper(), ())
    cands = [_score_candidate(span, primary, full_text)]
    for r in rivals:
        cands.append(_score_candidate(span, r, full_text))

    # Curated regex already matched this span → strong pronunciation for primary.
    if pattern_confirmed:
        primary_c = cands[0]
        cands[0] = AcronymCandidate(
            acronym=primary_c.acronym,
            score=max(primary_c.score, 0.86),
            evidence=tuple(dict.fromkeys(primary_c.evidence + ("pattern_match",))),
        )
        # Crush rivals that do not phonetically fit the span (e.g. RAGAS vs "are a g").
        for i in range(1, len(cands)):
            riv = cands[i]
            riv_pron = _pronunciation_score(span, riv.acronym)
            if riv_pron < 0.70:
                cands[i] = AcronymCandidate(
                    acronym=riv.acronym,
                    score=min(riv.score, 0.55),
                    evidence=riv.evidence + ("weak_pronunciation",),
                )

    cands.sort(key=lambda c: c.score, reverse=True)
    best = cands[0]
    second = cands[1].score if len(cands) > 1 else 0.0
    margin = best.score - second

    # Hard rule: compact LLM garbles never become LLaMA/Llama
    if span.lower() in {"lalam", "ellem", "elem", "ellm", "llum"}:
        llm = next((c for c in cands if c.acronym.upper() == "LLM"), None)
        llama = next((c for c in cands if c.acronym.lower() in {"llama", "llma"}), None)
        if llm is not None:
            if llama is not None and (llm.score - llama.score) < _MIN_MARGIN and llm.score < 0.85:
                return None, cands, True
            if llm.score >= _MIN_ACCEPT or pattern_confirmed:
                return "LLM", cands, False

    if best.score < _MIN_ACCEPT or margin < _MIN_MARGIN:
        return None, cands, True
    # Prefer canonical seed casing
    winner = next(
        (s for s in get_acronym_vocabulary() if s.lower() == best.acronym.lower()),
        best.acronym,
    )
    return winner, cands, False


def _utterance_safe_for_letter_gaps(text: str) -> bool:
    words = _WORD.findall(text or "")
    if len(words) <= 8:
        return True
    low = (text or "").lower()
    return bool(re.search(r"\b(?:what|define|explain|why|how)\b", low))


def recover_acronyms(text: str) -> AcronymRecoveryResult:
    """Recover spoken/garbled acronyms when evidence + margin are strong."""
    global _LAST_RESULT
    raw = _norm_space(text)
    if not raw:
        result = AcronymRecoveryResult(raw_transcript="", recovered_transcript="")
        _LAST_RESULT = result
        return result

    out = raw
    replacements: list[tuple[str, str, float]] = []
    all_cands: list[AcronymCandidate] = []
    abstained = False
    matched_intent = ""
    allow_gaps = _utterance_safe_for_letter_gaps(out)

    # 1) Compact / curated spoken garbles (with collision guard)
    for pat, preferred, tag in _COMPACT_GARBLES:
        # Spaced single letters are aggressive — only on short / definition asks.
        if tag == "spoken_letters" and not allow_gaps:
            continue
        m = pat.search(out)
        if not m:
            continue
        span = m.group(0)
        winner, cands, did_abstain = _pick_winner(
            span, preferred, out, pattern_confirmed=True
        )
        all_cands.extend(cands)
        if did_abstain or not winner:
            abstained = abstained or did_abstain
            continue
        # Avoid rewriting clean already-correct acronym
        if span.lower() == winner.lower():
            continue
        new_out = pat.sub(winner, out, count=1)
        if new_out == out:
            continue
        score = max(
            (c.score for c in cands if c.acronym.upper() == winner.upper()),
            default=0.0,
        )
        replacements.append((span, winner, score))
        out = new_out
        _, intent = _bank_acronym_hits(winner)
        if intent:
            matched_intent = intent

    # 2) Generated letter-name sequences for vocab acronyms
    if not replacements and allow_gaps:
        for pat, acr in _spoken_patterns():
            m = pat.search(out)
            if not m:
                continue
            span = m.group(0)
            winner, cands, did_abstain = _pick_winner(
                span, acr, out, pattern_confirmed=True
            )
            all_cands.extend(cands)
            if did_abstain or not winner:
                abstained = abstained or did_abstain
                continue
            new_out = pat.sub(winner, out, count=1)
            if new_out == out:
                continue
            score = max(
                (c.score for c in cands if c.acronym.upper() == winner.upper()),
                default=0.0,
            )
            replacements.append((span, winner, score))
            out = new_out
            _, intent = _bank_acronym_hits(winner)
            if intent:
                matched_intent = intent
            break  # one safe acronym remap per utterance

    result = AcronymRecoveryResult(
        raw_transcript=raw,
        recovered_transcript=out,
        replacements=replacements,
        candidates=all_cands,
        abstained=abstained and not replacements,
        matched_intent=matched_intent,
    )
    _LAST_RESULT = result
    if replacements or abstained:
        logger.info(
            "TECH_ACRONYM_RECOVERY raw=%r recovered=%r matched_intent=%s abstained=%s candidates=%s",
            result.raw_transcript,
            result.recovered_transcript,
            result.matched_intent or "-",
            result.abstained,
            [(c.acronym, round(c.score, 3)) for c in result.candidates[:6]],
        )
    return result


def apply_acronym_recovery(text: str) -> str:
    """Return recovered transcript (identity when abstaining)."""
    return recover_acronyms(text).recovered_transcript
