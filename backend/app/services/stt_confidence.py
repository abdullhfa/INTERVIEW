"""
Confidence / second-pass helpers for interviewer STT → bank answer.

Goal: high-confidence wrong prepared answers = 0.
Does not change aliases; only decides when to retry STT or abstain from a
strong bank answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.services.domain_terms import normalize_for_matching
from app.services.question_bank import BankMatch, _content_tokens


# Latency-cut: simple questions never exceed this many Whisper calls.
MAX_STT_PASSES_SIMPLE = 2
# Compound: never a third Whisper pass — broken audio gets at most one accurate retry.
MAX_STT_PASSES_COMPOUND = 2


def stt_need_second_pass(
    transcript: str,
    match: Optional[BankMatch],
    *,
    risk: Optional[MatchRisk] = None,
) -> tuple[bool, str, bool]:
    """
    STT-only second-pass gate (simple + compound).

    Pass-2 is for *audio/transcript* doubt only — never because intent is weak.
    Weak intent → semantic recovery, not another Whisper call.
    """
    from app.services.semantic_intent_recovery import should_trigger_semantic_recovery

    text = (transcript or "").strip()
    obvious_corruption = (not text) or transcript_looks_weak(text)
    trig, treason = should_trigger_semantic_recovery(text, match) if text else (True, "empty")
    strong_agrees = (not trig) and treason == "strong_agrees"
    first_pass_valid = bool(text) and not transcript_looks_weak(text)

    if first_pass_valid and strong_agrees and not obvious_corruption:
        return False, "", True

    if obvious_corruption:
        return True, "broken_transcript", strong_agrees

    if risk is not None and risk.needs_stt_retry:
        return True, "stt_retry", strong_agrees

    # Strong STT-vs-intent disagreement that often tracks garble (not thin_margin).
    if first_pass_valid and trig and treason in {
        "strong_low_agreement",
        "action_mismatch",
        "paraphrase_suspected",
    }:
        return True, f"disagree:{treason}", strong_agrees

    # Clean transcript with weak/missing intent → Intent path, not Whisper.
    return False, "", strong_agrees


def simple_need_second_pass(
    transcript: str,
    match: Optional[BankMatch],
    *,
    risk: Optional[MatchRisk] = None,
) -> tuple[bool, str, bool]:
    """Alias for stt_need_second_pass (simple budget)."""
    return stt_need_second_pass(transcript, match, risk=risk)


def compound_need_second_pass(
    transcript: str,
    match: Optional[BankMatch],
    *,
    risk: Optional[MatchRisk] = None,
) -> tuple[bool, str, bool]:
    """
    Compound STT second-pass gate.

    Same rule as simple: bad audio / broken transcript only.
    A fluent multi-part transcript with weak whole-utterance intent must NOT
    re-run Whisper — compound decompose + semantic handle that.
    """
    return stt_need_second_pass(transcript, match, risk=risk)

@dataclass
class MatchRisk:
    needs_stt_retry: bool
    abstain_strong: bool
    reason: str


def transcript_looks_weak(text: str) -> bool:
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return True
    words = [w for w in cleaned.replace("?", " ").replace(".", " ").split() if w]
    if len(words) <= 1:
        return True
    # Fragment-like single content token ("retrieval", "agent") without question shape.
    content = _content_tokens(normalize_for_matching(cleaned))
    wh = {
        "what", "why", "how", "when", "where", "who", "which",
        "tell", "explain", "describe", "should", "would", "could",
        "can", "do", "does", "did", "is", "are", "have", "has",
        "walk", "compare", "difference",
    }
    has_q_shape = any(w.casefold().strip(",'") in wh for w in words) or len(words) >= 4
    if len(content) <= 1 and not has_q_shape:
        return True
    return False


def word_count(text: str) -> int:
    return len((text or "").replace("?", " ").split())


def needs_accurate_second_pass(
    text: str,
    match: Optional[BankMatch] = None,
    *,
    first_word_missing: bool = False,
    last_word_missing: bool = False,
) -> bool:
    """
    True only when there is a real doubt signal — not merely because the
    question is short. Short clean questions like "What is RAG?" should not
    pay a second-pass latency tax when the first transcript looks complete.
    """
    if not (text or "").strip():
        return True
    short_strong = (
        match is not None
        and float(getattr(match, "score", 0.0) or 0.0) >= 0.78
        and word_count(text) <= 6
    )
    # Edge missing alone on a short strong bank hit is often a false trigger (latency tax).
    if (first_word_missing or last_word_missing) and not short_strong:
        return True
    if transcript_looks_weak(text):
        return True
    if match is not None:
        gap = float(match.score) - float(getattr(match, "runner_up_score", 0.0) or 0.0)
        # Weak intent margin between top-2.
        if match.runner_up is not None and gap < 0.05 and float(match.score) < 0.82:
            return True
        if float(match.score) < 0.55:
            return True
    return False


def edge_word_diagnostics(expected: str, transcript: str) -> dict[str, bool]:
    """Detect missing first/last content words vs the *spoken* wording."""
    exp = [w for w in re.findall(r"[a-z0-9]+", (expected or "").casefold()) if w]
    got = [w for w in re.findall(r"[a-z0-9]+", (transcript or "").casefold()) if w]
    if not exp:
        return {"first_word_missing": False, "last_word_missing": False}
    if not got:
        return {"first_word_missing": True, "last_word_missing": True}

    def _family(w: str) -> set[str]:
        base = w.rstrip("s")
        return {w, base, base + "s", w + "s"}

    first_ok = bool(_family(exp[0]) & _family(got[0])) or exp[0] in got[:3]
    last_ok = bool(_family(exp[-1]) & _family(got[-1])) or exp[-1] in got[-3:]
    return {
        "first_word_missing": not first_ok,
        "last_word_missing": not last_ok,
    }


def classify_failure_position(
    expected: str,
    transcript: str,
    *,
    intent_ok: bool,
    first_word_missing: bool,
    last_word_missing: bool,
) -> str:
    """
    Where a failure likely concentrated vs spoken wording:
      none | beginning | middle | end | both_ends | empty
    Diagnostic only — does not change matching.
    """
    if intent_ok:
        return "none"
    exp = [w for w in re.findall(r"[a-z0-9]+", (expected or "").casefold()) if w]
    got = [w for w in re.findall(r"[a-z0-9]+", (transcript or "").casefold()) if w]
    if not got:
        return "empty"
    if first_word_missing and last_word_missing:
        return "both_ends"
    if first_word_missing and not last_word_missing:
        return "beginning"
    if last_word_missing and not first_word_missing:
        return "end"
    if len(exp) < 6:
        return "middle"
    # Thirds coverage: which third of expected tokens is least present in transcript.
    bag = set(got)
    n = len(exp)
    thirds = [exp[: n // 3], exp[n // 3 : 2 * n // 3], exp[2 * n // 3 :]]
    scores = []
    for part in thirds:
        if not part:
            scores.append(1.0)
            continue
        hit = sum(1 for w in part if w in bag)
        scores.append(hit / len(part))
    worst = min(range(3), key=lambda i: scores[i])
    return ("beginning", "middle", "end")[worst]


def classify_fail_bucket(
    *,
    stt_ok: bool,
    intent_ok: bool,
    stt_score: float,
    transcript: str,
    expected: str,
) -> Optional[str]:
    """
    Split failures for Office/Poor diagnosis:
      stt_wrong_intent_recoverable — STT noisy but meaning still recoverable
      stt_wrong_meaning_lost — STT destroyed meaning
      intent_only — STT ok but intent/match failed
    """
    if intent_ok:
        return None
    if stt_ok or stt_score >= 0.72:
        return "intent_only"
    # Recoverable if lexical overlap remains meaningful after repair path.
    from rapidfuzz import fuzz

    overlap = fuzz.token_set_ratio((transcript or "").strip(), (expected or "").strip()) / 100.0
    if overlap >= 0.45 or stt_score >= 0.55:
        return "stt_wrong_intent_recoverable"
    return "stt_wrong_meaning_lost"


def assess_match_risk(
    text: str,
    match: Optional[BankMatch],
    *,
    ambiguous_margin: float = 0.05,
) -> MatchRisk:
    """Decide whether to retry STT and/or block a strong prepared answer."""
    if not (text or "").strip():
        return MatchRisk(True, True, "empty_transcript")
    if match is None:
        return MatchRisk(transcript_looks_weak(text), True, "no_match")

    weak_text = transcript_looks_weak(text)
    gap = float(match.score) - float(match.runner_up_score or 0.0)
    ambiguous = (
        match.runner_up is not None
        and gap < ambiguous_margin
        and float(match.score) >= 0.55
    )
    short_high = weak_text and float(match.score) >= 0.70

    # Retry STT only when transcript is weak/empty or top-2 is close *and*
    # the lead score is not already decisive — avoids doubling latency on
    # clear strong matches (abstain still covers HC-wrong for ambiguous).
    needs_retry = weak_text or (ambiguous and float(match.score) < 0.82)
    # Never fire a strong prepared answer when STT is weak, top-2 is close,
    # or the utterance is a short fragment — keep Intent, block HC wrong.
    abstain_strong = (
        short_high
        or ambiguous
        or (weak_text and match.runner_up is not None and gap < 0.12)
        or (weak_text and float(match.score) >= 0.55)
    )
    if short_high:
        reason = "short_high_confidence"
    elif ambiguous and weak_text:
        reason = "short_ambiguous"
    elif ambiguous:
        reason = "ambiguous_top2"
    elif weak_text:
        reason = "weak_transcript"
    else:
        reason = "ok"
    return MatchRisk(needs_retry, abstain_strong, reason)


def apply_strong_abstain(match: Optional[BankMatch], risk: MatchRisk) -> Optional[BankMatch]:
    """Block dangerous strong prepared answers (high-confidence wrong)."""
    if match is None:
        return None
    if not risk.abstain_strong:
        return match
    if match.mode != "strong":
        return match
    # Downgrade to weak: Intent can still score; prepared answer will not fire.
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
