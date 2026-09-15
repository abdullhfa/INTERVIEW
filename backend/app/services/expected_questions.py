"""Match a live interviewer question to a candidate-prepared Q&A pair."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from app.models.candidate import ExpectedQuestion

_PUNCT_RE = re.compile(r"[^\w\u0600-\u06ff]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "your", "you", "me", "i", "we", "my", "our", "is", "are", "was", "were",
    "do", "did", "does", "can", "could", "would", "will", "please", "kindly",
    "about", "tell", "talk", "walk", "give", "share", "describe", "explain",
    "what", "why", "how", "who", "when", "where", "which",
    "من", "ما", "ماذا", "لماذا", "كيف", "هل", "عن", "في", "على", "إلى",
    "ال", "هذا", "هذه", "ذلك", "تلك", "لي", "لك", "لنا", "أنت", "انا",
    "أنا", "قلي", "قل لي", "حدثني", "احكي", "احك", "ممكن", "لو", "سمحت",
}

# Same-meaning groups: if asked and prepared prompts hit the same group, treat as match.
_ALIAS_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({
        "tell me about yourself",
        "introduce yourself",
        "walk me through your background",
        "give me a brief introduction",
        "who are you",
        "عرف عن نفسك",
        "عرفنا عن نفسك",
        "تعرفنا عن نفسك",
        "تعرف عن نفسك",
        "حدثني عن نفسك",
        "عرفني عن نفسك",
        "من أنت",
        "من انت",
        "مقدمة عن نفسك",
    }),
    frozenset({
        "what are your strengths",
        "what is your greatest strength",
        "what are you good at",
        "ما هي نقاط قوتك",
        "نقاط القوة",
        "ايش نقاط قوتك",
    }),
    frozenset({
        "what are your weaknesses",
        "what is your greatest weakness",
        "ما هي نقاط ضعفك",
        "نقاط الضعف",
        "ايش نقاط ضعفك",
    }),
    frozenset({
        "why do you want this job",
        "why this role",
        "why this company",
        "why should we hire you",
        "لماذا تريد هذه الوظيفة",
        "ليش تبي هالوظيفة",
        "لماذا هذه الشركة",
        "لماذا نوظفك",
    }),
    frozenset({
        "where do you see yourself in five years",
        "what are your career goals",
        "وين تشوف نفسك بعد خمس سنوات",
        "أين ترى نفسك بعد خمس سنوات",
        "اهدافك المهنية",
    }),
    frozenset({
        "why did you leave your last job",
        "why are you looking for a new job",
        "لماذا تركت عملك السابق",
        "ليش تبي تترك عملك",
        "سبب ترك العمل",
    }),
    frozenset({
        "what projects have you worked on",
        "tell me about your projects",
        "walk me through a project",
        "describe a project you worked on",
        "what is your most recent project",
        "شو المشاريع اللي اشتغلتها",
        "ما المشاريع التي عملت عليها",
        "حدثني عن مشاريعك",
        "احكي عن مشاريعك",
        "اشرح لي مشروعك",
        "وش مشاريعك",
    }),
    frozenset({
        "did you use rag in your projects",
        "have you used rag",
        "did you use llm in a project",
        "have you used langchain",
        "هل استخدمت rag في مشاريعك",
        "هل استخدمت ال rag في احدى مشاريعك",
        "هل استخدمت llm",
        "هل استخدمت langchain",
        "هل طبقت rag",
    }),
)

MATCH_THRESHOLD = 0.52


@dataclass(frozen=True)
class ExpectedQuestionMatch:
    item: ExpectedQuestion
    score: float
    reason: str


def normalize_question(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text or "").casefold()
    folded = _PUNCT_RE.sub(" ", folded)
    return _WS_RE.sub(" ", folded).strip()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_question(text).split()
        if len(token) >= 2 and token not in _STOPWORDS
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    if overlap == 0:
        return 0.0
    return overlap / len(a | b)


def _alias_group_id(normalized: str) -> Optional[int]:
    for index, group in enumerate(_ALIAS_GROUPS):
        for alias in group:
            alias_n = normalize_question(alias)
            if alias_n and (alias_n in normalized or normalized in alias_n):
                return index
    return None


def score_question_pair(asked: str, prepared_prompt: str) -> tuple[float, str]:
    asked_n = normalize_question(asked)
    prep_n = normalize_question(prepared_prompt)
    if not asked_n or not prep_n:
        return 0.0, "empty"

    if asked_n == prep_n:
        return 1.0, "exact"

    if len(asked_n) >= 12 and len(prep_n) >= 12:
        if asked_n in prep_n or prep_n in asked_n:
            return 0.92, "contains"

    asked_group = _alias_group_id(asked_n)
    prep_group = _alias_group_id(prep_n)
    if asked_group is not None and asked_group == prep_group:
        return 0.95, "similar_meaning"

    asked_tokens = _tokens(asked)
    prep_tokens = _tokens(prepared_prompt)
    jaccard = _jaccard(asked_tokens, prep_tokens)
    if prep_tokens and prep_tokens <= asked_tokens and len(prep_tokens) >= 2:
        return max(jaccard, 0.78), "token_subset"
    if asked_tokens and asked_tokens <= prep_tokens and len(asked_tokens) >= 2:
        return max(jaccard, 0.78), "token_subset"
    return jaccard, "jaccard"


def match_expected_question(
    asked: str,
    items: list[ExpectedQuestion],
    *,
    threshold: float = MATCH_THRESHOLD,
) -> Optional[ExpectedQuestionMatch]:
    best: Optional[ExpectedQuestionMatch] = None
    for item in items:
        if not (item.prompt or "").strip() or not (item.answer or "").strip():
            continue
        score, reason = score_question_pair(asked, item.prompt)
        if score < threshold:
            continue
        if best is None or score > best.score:
            best = ExpectedQuestionMatch(item=item, score=score, reason=reason)
    return best
