"""Combine approved bank answers into one concise spoken reply.

Rules:
- bank text only (no invented CV claims)
- ~4–7 short sentences
- preserve interviewer order of intents
- simple English, speakable
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from app.services.question_bank import BankMatch


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class BuiltCompoundAnswer:
    answer_en: str
    source_ids: tuple[str, ...]
    sentence_count: int


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split((text or "").strip()) if p.strip()]
    return parts


def _first_useful_sentence(text: str) -> str:
    for sent in _sentences(text):
        # Skip tiny fragments.
        if len(sent.split()) >= 5:
            return sent.rstrip(".")
    raw = (text or "").strip().rstrip(".")
    return raw


def _trim_overlap(sentence: str, already: Sequence[str], *, strict: bool = False) -> str | None:
    """Drop only near-identical repeats. Different intents may share topic words."""
    tokens = set(re.findall(r"[a-z0-9]{3,}", sentence.lower()))
    if not tokens:
        return None
    threshold = 0.88 if not strict else 0.72
    for prev in already:
        prev_tok = set(re.findall(r"[a-z0-9]{3,}", prev.lower()))
        if not prev_tok:
            continue
        overlap = len(tokens & prev_tok) / max(1, len(tokens | prev_tok))
        if overlap >= threshold:
            return None
    return sentence


def build_compound_answer(
    matches: Sequence[BankMatch],
    *,
    max_sentences: int = 8,
    min_sentences: int = 2,
) -> BuiltCompoundAnswer | None:
    """One short sentence per distinct intent — order preserved, no unbounded length."""
    if not matches:
        return None

    lines: list[str] = []
    source_ids: list[str] = []

    for match in matches:
        entry = match.entry
        body = (entry.answer_en or "").strip()
        if not body:
            continue
        primary = _first_useful_sentence(body)
        # Prefer keeping a part sentence even if topical overlap (Track B).
        kept = _trim_overlap(primary, lines, strict=False)
        if kept is None and primary:
            # Last resort: keep a shortened unique lead-in if totally overlapping.
            words = primary.split()
            if len(words) >= 8:
                kept = _trim_overlap(" ".join(words[:8]), lines, strict=False)
        if kept:
            lines.append(kept)
            source_ids.append(entry.id)
        if len(lines) >= max_sentences:
            break

    if not lines:
        return None

    # Soft floor only when we have fewer sentences than matches (missing fragment).
    if len(lines) < min(min_sentences, len(matches)) and matches:
        for match in matches:
            if match.entry.id in source_ids:
                continue
            body = (match.entry.answer_en or "").strip()
            primary = _first_useful_sentence(body)
            kept = _trim_overlap(primary, lines, strict=False)
            if kept:
                lines.append(kept)
                source_ids.append(match.entry.id)
            if len(lines) >= min(min_sentences, len(matches)):
                break

    lines = lines[:max_sentences]
    spoken = " ".join(s if s.endswith((".", "!", "?")) else f"{s}." for s in lines)
    return BuiltCompoundAnswer(
        answer_en=spoken,
        source_ids=tuple(dict.fromkeys(source_ids)),
        sentence_count=len(lines),
    )
