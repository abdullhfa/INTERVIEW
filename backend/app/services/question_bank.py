
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, cast

import numpy as np

from app.services.domain_terms import normalize_for_matching
from app.services.technical_term_repair import repair_technical_terms

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "question_bank"

STRONG_THRESHOLD = 0.70
WEAK_THRESHOLD = 0.56
# A very high lexical or semantic score alone is enough for a strong match.
LEXICAL_OVERRIDE = 0.93
SEMANTIC_OVERRIDE = 0.86
TOPIC_BOOST = 0.08
# A weak-band score still counts as strong when it clearly leads the runner-up.
CLEAR_WINNER_THRESHOLD = 0.62
CLEAR_WINNER_MARGIN = 0.15
# Ambiguous band: trigger top-3 semantic re-rank.
AMBIGUOUS_MARGIN = 0.05
AMBIGUOUS_TOP_MIN = 0.50
# A question about the candidate ("did you", "your projects") must never be
# answered with a textbook definition from the technical bank.
PERSONAL_VS_DEFINITION_PENALTY = 0.20

# PERF (pre-v3): batch the per-alias rapidfuzz calls with process.cdist.
# Same scorers, same values — set QB_FAST_LEXICAL=0 to force the scalar path.
_FAST_LEXICAL = os.getenv("QB_FAST_LEXICAL", "1") not in {"0", "false", "False"}
_FAST_LEXICAL_MIN = 1200

# Embedding-cost instrumentation (diagnostic only; never gates anything).
EMBED_STATS: dict[str, float] = {"calls": 0, "texts": 0, "ms": 0.0, "max_ms": 0.0}


def embed_stats() -> dict[str, float]:
    calls = max(1, int(EMBED_STATS["calls"]))
    return {**EMBED_STATS, "ms_per_call": round(EMBED_STATS["ms"] / calls, 1)}


def reset_embed_stats() -> None:
    EMBED_STATS.update({"calls": 0, "texts": 0, "ms": 0.0, "max_ms": 0.0})

# Distinctive interview terms: boost entries that own them; penalize generic
# definition entries that only share weak words like "llm" / "what is".
_DISTINCTIVE_TERMS: dict[str, tuple[str, float]] = {
    "guardrail": ("guardrails", 0.22),
    "guardrails": ("guardrails", 0.22),
    "rag": ("rag", 0.16),
    "agentic": ("agentic", 0.20),
    "langchain": ("langchain", 0.16),
    "langgraph": ("langgraph", 0.16),
    "orchestrator": ("orchestrator", 0.14),
    "hallucination": ("hallucination", 0.14),
    "chromadb": ("chromadb", 0.14),
    "whisper": ("whisper", 0.12),
}
_GENERIC_DEF_IDS = frozenset({
    "tech.what_is_llm",
    "tech.llm_what",
    "tech.what_is_ai",
})
_GENERIC_QUERY_TOKENS = frozenset({"llm", "llms", "model", "models", "ai"})

# "What projects did you do in Kuwait, and did you use LLMs there?" -- two
# questions in one utterance. A single prepared answer only fits if an alias
# covers the whole thing; otherwise the LLM composes the answer (weak mode).
_COMPOUND_RE = re.compile(
    r"(?:,|;|\band\b|\balso\b|\bplus\b)\s+"
    r"(?:(?:and|also|plus)\s+)?"
    r"(?:what|how|why|when|where|which|who|did|do|does|have|has|is|are|was|were|can|could|would|tell)\b"
)
_PERSONAL_RE = re.compile(
    r"\b(did you|have you|were you|do you have|you have|you worked|you did|you used|you built|"
    r"your (?:projects?|work|experience|role|roles|time|career|cv|resume|background|job)|"
    r"in your|for you|any work (?:been )?done|have any|has any)\b"
)


def is_compound_question(normalized: str) -> bool:
    return bool(_COMPOUND_RE.search(normalized)) or normalized.count("?") >= 2


def is_personal_question(normalized: str) -> bool:
    return bool(_PERSONAL_RE.search(normalized))

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "at", "by",
    "your", "you", "me", "i", "we", "my", "our", "us", "is", "are", "was", "were", "be",
    "do", "did", "does", "can", "could", "would", "will", "please", "kindly", "so", "okay",
    "ok", "right", "well", "just", "also", "about", "tell", "talk", "walk", "give", "share",
    "describe", "explain", "what", "why", "how", "who", "when", "where", "which", "that",
    "this", "it", "its", "there", "here", "have", "has", "had", "been", "some", "any",
    "let", "lets", "s", "um", "uh", "like", "yeah", "yes", "no", "now", "then", "little",
    "bit", "more", "than", "into", "from", "as", "if", "one", "thing", "things", "know",
    "want", "wanted", "curious", "mean", "actually", "really", "basically",
}

_FOLLOW_UP_GENERIC = (
    "what was your role", "your role in that", "what did you do", "what exactly did you do",
    "which technologies", "what technologies", "what tools", "what tech", "tech stack",
    "what was the result", "what was the outcome", "what challenges", "what was hard",
    "what was difficult", "how did you evaluate", "which metric", "how did you measure",
    "which model", "which llm", "what model", "why did you", "how did you choose",
    "can you go deeper", "more detail", "more details", "elaborate", "tell me more",
    "and then", "what happened next", "how does that work", "how did that work",
    "in that project", "in that model", "in that system", "in this project", "in that case",
    "for that project", "there", "in it",
)

# ── question intent ───────────────────────────────────────────────────
# "What is Whisper?", "Have you used Whisper?" and "How does Whisper work?" share
# every keyword but need three different answers. Intent is detected on the
# normalized text and used to separate such siblings.
_LEADING_FILLER_RE = re.compile(
    r"^(?:(?:okay|ok|so|um|uh|alright|right|now|then|and|well|please|great|good|also|"
    r"first|next|finally|basically|actually|just|maybe|perhaps|let s say|let us say|"
    r"i want to know|i would like to know|i am curious|curious|quick question|one more question|"
    r"my question is|can you|could you|would you|will you|kindly|"
    r"in your opinion|from your experience)\s+)+",
)
_INTENT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("experience", re.compile(
        r"\b(have you|did you|were you|was your|have you ever|your experience with|your experience in|"
        r"you (?:used|built|build|worked|done|did|faced|managed|deployed|trained|handled|chose|picked|"
        r"decided|avoided|evaluated|measured|split|implemented|applied|designed|created|developed|"
        r"tuned|compared|classified|predicted|detected|mentioned)|in your (?:project|projects|work|cv|"
        r"resume|experience|career)|in that (?:project|model|system|case)|in the (?:similarity|early|"
        r"helpdesk|kiosk|btec|completion|ministry|najat|knet)|what was your|which .* did you|"
        r"what .* did you|how did you|why did you|where did you|when did you)\b"
    )),
    ("compare", re.compile(
        r"\b(difference between|differences between|versus|vs|compared to|compare|or .* which|which one|rather than)\b"
    )),
    # Must run before "what is / what are", otherwise "What are the steps to create an LLM?"
    # is scored as a definition and the prepared "what is an LLM" answer is read aloud.
    ("how", re.compile(
        r"\b(?:what are the (?:main )?steps|steps to (?:create|train|build|make|pre-?train)|"
        r"how (?:do you|would you|can you|to) (?:create|train|build|pre-?train)|"
        r"how (?:is|are) (?:an? )?(?:llm|large language model|language model) (?:created|trained|built|made)|"
        r"walk me through the steps|"
        r"explain how|describe how)\b"
    )),
    ("definition", re.compile(
        r"^(?:what is|what are|what s|what does .* mean|define|explain what|explain the (?:concept|term|idea) of|"
        r"what do you mean by|what is meant by|explain (?!how|why)|describe what)\b"
    )),
    ("how", re.compile(r"^(?:how do|how would|how does|how can|how should|how to|how is|how are|how will|in what way|explain how|describe how)\b")),
    ("why", re.compile(r"^(?:why|what is the reason|what makes)\b")),
    ("describe", re.compile(r"^(?:tell me about|tell us about|talk about|walk me through|describe|give me an overview)\b")),
)


def detect_intent(normalized: str) -> Optional[str]:
    text = _LEADING_FILLER_RE.sub("", normalized).strip()
    if not text:
        return None
    for name, pattern in _INTENT_RULES:
        if pattern.search(text):
            return name
    return None


# Score adjustment when the query intent and the alias intent are known.
INTENT_MATCH_BONUS = 0.04
INTENT_MISMATCH_PENALTY = 0.10
# Intents that are close enough not to be penalised against each other.
_INTENT_COMPATIBLE = {
    frozenset({"describe", "experience"}),
    frozenset({"describe", "definition"}),
    frozenset({"how", "compare"}),
}


@dataclass(frozen=True)
class BankEntry:
    id: str
    bank: str
    category: str
    topic: str
    question: str
    aliases: tuple[str, ...]
    keywords: tuple[str, ...]
    answer_en: str
    answer_ar: Optional[str] = None
    followup_en: Optional[str] = None
    listen_for: tuple[str, ...] = ()

    def to_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bank": self.bank,
            "category": self.category,
            "topic": self.topic,
            "question": self.question,
            "aliases": list(self.aliases),
            "keywords": list(self.keywords),
            "listen_for": list(self.listen_for),
            "answer_en": self.answer_en,
            "answer_ar": self.answer_ar,
            "followup_en": self.followup_en,
        }


@dataclass(frozen=True)
class BankMatch:
    entry: BankEntry
    score: float
    semantic: float
    lexical: float
    keyword: float
    alias: str
    mode: str  # "strong" | "weak"
    runner_up: Optional[str] = None
    runner_up_score: float = 0.0

    @property
    def is_strong(self) -> bool:
        return self.mode == "strong"


@dataclass
class _Index:
    entries: list[BankEntry] = field(default_factory=list)
    alias_texts: list[str] = field(default_factory=list)      # normalized alias text
    alias_entry: list[int] = field(default_factory=list)      # alias -> entry index
    alias_raw: list[str] = field(default_factory=list)        # original alias text
    alias_intent: list[Optional[str]] = field(default_factory=list)
    alias_matrix: Optional[np.ndarray] = None                 # (n_alias, dim), L2-normalized
    entry_keywords: list[tuple[str, ...]] = field(default_factory=list)
    by_id: dict[str, BankEntry] = field(default_factory=dict)
    # Latency-cut: precomputed lexical structures (built once at load).
    alias_content_text: list[str] = field(default_factory=list)
    alias_token_sets: list[frozenset[str]] = field(default_factory=list)
    entry_alias_positions: list[list[int]] = field(default_factory=list)
    token_to_alias: dict[str, tuple[int, ...]] = field(default_factory=dict)
    distinctive_to_alias: dict[str, tuple[int, ...]] = field(default_factory=dict)
    # PERF (pre-v3): per-entry static facts hoisted out of the per-alias scoring
    # loop. Values are computed from the exact same expressions the loop used,
    # so scores are unchanged — only the repeated string building is removed.
    alias_text_pos: dict[str, int] = field(default_factory=dict)
    entry_owned_families: list[frozenset[str]] = field(default_factory=list)
    entry_guardrail_penalty: list[bool] = field(default_factory=list)
    entry_cv_definition_penalty: list[bool] = field(default_factory=list)
    entry_is_technical: list[bool] = field(default_factory=list)
    entry_topic: list[str] = field(default_factory=list)


@lru_cache(maxsize=32768)
def _content_tokens_cached(normalized: str) -> tuple[str, ...]:
    return tuple(t for t in normalized.split() if len(t) >= 2 and t not in _STOPWORDS)


def _content_tokens(normalized: str) -> list[str]:
    """Memoized; returns a fresh list so callers keep their existing contract."""
    return list(_content_tokens_cached(normalized or ""))


class QuestionBank:
    """Loads bank JSON files and matches live questions against them."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self._data_dir = Path(data_dir)
        self._index = _Index()
        self._embedder: Any = None
        self._embedder_failed = False
        self._lock = threading.Lock()
        self._loaded = False
        self._warm = False
        # Bumped on every (re)load so derived caches elsewhere can invalidate.
        self._generation = 0
        # Remember which entry answered a given transcript so follow-ups can be
        # scoped to the same topic later.
        self._recent_matches: OrderedDict[str, str] = OrderedDict()
        # Latency-cut: reuse identical _score_all work within an utterance / short window.
        self._score_cache: OrderedDict[str, list[tuple[float, float, float, float, int, int]]] = (
            OrderedDict()
        )
        self._score_cache_limit = 128
        # PERF: reuse the query embedding across match/top_matches/rerank.
        self._query_vec_cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._query_vec_cache_limit = 256

    # ── loading ────────────────────────────────────────────────────────

    def load(self, force: bool = False) -> None:
        if self._loaded and not force:
            return
        with self._lock:
            if self._loaded and not force:
                return
            index = _Index()
            files = sorted(self._data_dir.glob("*.json")) if self._data_dir.exists() else []
            for path in files:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:  # pragma: no cover - corrupt file
                    logger.error("Question bank file %s failed to load: %s", path.name, exc)
                    continue
                bank_name = str(payload.get("bank") or path.stem)
                for raw in payload.get("entries", []):
                    entry = self._entry_from_raw(raw, bank_name)
                    if entry is None:
                        continue
                    if entry.id in index.by_id:
                        logger.warning("Duplicate question bank id %s (file %s)", entry.id, path.name)
                        continue
                    entry_pos = len(index.entries)
                    index.entries.append(entry)
                    index.by_id[entry.id] = entry
                    index.entry_keywords.append(
                        tuple(normalize_for_matching(k) for k in entry.keywords if k.strip())
                    )
                    seen: set[str] = set()
                    for alias in (entry.question, *entry.aliases):
                        normalized = normalize_for_matching(alias)
                        if not normalized or normalized in seen:
                            continue
                        seen.add(normalized)
                        index.alias_texts.append(normalized)
                        index.alias_entry.append(entry_pos)
                        index.alias_raw.append(alias)
                        index.alias_intent.append(detect_intent(normalized))
            self._build_lexical_structures(index)
            self._index = index
            self._loaded = True
            self._generation += 1
            self._warm = False
            self._score_cache.clear()
            self._query_vec_cache.clear()
            logger.info(
                "Question bank loaded: %d entries, %d aliases from %d file(s) "
                "(lexical_index tokens=%d distinctive=%d)",
                len(index.entries),
                len(index.alias_texts),
                len(files),
                len(index.token_to_alias),
                len(index.distinctive_to_alias),
            )

    @staticmethod
    def _build_lexical_structures(index: _Index) -> None:
        """Precompute token sets + inverted indexes once (Latency-cut)."""
        n_entries = len(index.entries)
        index.entry_alias_positions = [[] for _ in range(n_entries)]
        token_map: dict[str, list[int]] = {}
        dist_map: dict[str, list[int]] = {}
        for pos, alias in enumerate(index.alias_texts):
            tokens = _content_tokens(alias)
            index.alias_content_text.append(" ".join(tokens) or alias)
            tset = frozenset(tokens)
            index.alias_token_sets.append(tset)
            entry_pos = index.alias_entry[pos]
            index.entry_alias_positions[entry_pos].append(pos)
            for tok in tset:
                token_map.setdefault(tok, []).append(pos)
            bag = tset | set(alias.split())
            for token, (family, _boost) in _DISTINCTIVE_TERMS.items():
                if token in bag or family in bag:
                    dist_map.setdefault(family, []).append(pos)
            # Entry keywords also invert into alias positions for that entry.
            for kw in index.entry_keywords[entry_pos]:
                if kw:
                    token_map.setdefault(kw, []).append(pos)
        index.token_to_alias = {k: tuple(dict.fromkeys(v)) for k, v in token_map.items()}
        index.distinctive_to_alias = {
            k: tuple(dict.fromkeys(v)) for k, v in dist_map.items()
        }
        # First alias position for each normalized text (embedding-row lookup).
        for pos, alias in enumerate(index.alias_texts):
            if alias not in index.alias_text_pos:
                index.alias_text_pos[alias] = pos
        # PERF: hoist per-entry constants out of `_score_positions`.
        families = {fam for _tok, (fam, _b) in _DISTINCTIVE_TERMS.items()}
        owned: list[frozenset[str]] = []
        guard: list[bool] = []
        cvdef: list[bool] = []
        is_tech: list[bool] = []
        topics: list[str] = []
        for entry in index.entries:
            kw_blob = " ".join(entry.keywords).casefold()
            blob = " ".join(
                [entry.id, entry.topic, " ".join(entry.keywords), entry.question]
            ).casefold()
            owned.append(frozenset(fam for fam in families if fam in blob))
            guard.append(
                entry.id in _GENERIC_DEF_IDS
                or (
                    "guardrail" not in entry.topic
                    and "guardrail" not in kw_blob
                    and "llm" in entry.topic
                )
            )
            cvdef.append(
                entry.bank == "cv"
                and entry.topic in {"agentic", "rag", "guardrails", "langchain", "langgraph"}
            )
            is_tech.append(entry.bank == "technical")
            topics.append(entry.topic)
        index.entry_owned_families = owned
        index.entry_guardrail_penalty = guard
        index.entry_cv_definition_penalty = cvdef
        index.entry_is_technical = is_tech
        index.entry_topic = topics

    @staticmethod
    def _entry_from_raw(raw: dict[str, Any], bank_name: str) -> Optional[BankEntry]:
        entry_id = str(raw.get("id") or "").strip()
        question = str(raw.get("question") or "").strip()
        answer = str(raw.get("answer_en") or raw.get("answer") or "").strip()
        if not entry_id or not question or not answer:
            return None
        aliases = tuple(str(a).strip() for a in raw.get("aliases", []) if str(a).strip())
        keywords = tuple(str(k).strip() for k in raw.get("keywords", []) if str(k).strip())
        listen = tuple(str(k).strip() for k in raw.get("listen_for", []) if str(k).strip())
        followup = str(raw.get("followup_en") or "").strip() or None
        return BankEntry(
            id=entry_id,
            bank=bank_name,
            category=str(raw.get("category") or bank_name),
            topic=str(raw.get("topic") or ""),
            question=question,
            aliases=aliases,
            keywords=keywords,
            answer_en=answer,
            answer_ar=(str(raw.get("answer_ar")).strip() or None) if raw.get("answer_ar") else None,
            followup_en=followup,
            listen_for=listen,
        )

    # ── embeddings ─────────────────────────────────────────────────────

    def _get_embedder(self) -> Any:
        if self._embedder is not None or self._embedder_failed:
            return self._embedder
        try:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

            self._embedder = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        except Exception as exc:
            self._embedder_failed = True
            logger.warning("Question bank semantic matching disabled (embedder unavailable): %s", exc)
        return self._embedder

    def _embed(self, texts: list[str]) -> Optional[np.ndarray]:
        embedder = self._get_embedder()
        if embedder is None or not texts:
            return None
        started = time.perf_counter()
        try:
            vectors = np.asarray(embedder(texts), dtype=np.float32)
        except Exception as exc:
            logger.warning("Question bank embedding failed: %s", exc)
            return None
        finally:
            # Instrumentation: the re-rank traces suggest ~1 s per ONNX call on
            # the target machine. Measure it instead of guessing.
            elapsed = (time.perf_counter() - started) * 1000
            EMBED_STATS["calls"] += 1
            EMBED_STATS["texts"] += len(texts)
            EMBED_STATS["ms"] += elapsed
            if elapsed > EMBED_STATS["max_ms"]:
                EMBED_STATS["max_ms"] = round(elapsed, 1)
        if vectors.ndim != 2:
            return None
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def warm(self) -> None:
        """Load files and pre-embed every alias. Safe to call repeatedly."""
        self.load()
        if self._warm:
            return
        with self._lock:
            if self._warm:
                return
            started = time.perf_counter()
            matrix = None
            if self._index.alias_texts:
                chunks: list[np.ndarray] = []
                batch = 64
                texts = self._index.alias_texts
                for start in range(0, len(texts), batch):
                    part = self._embed(texts[start:start + batch])
                    if part is None:
                        chunks = []
                        break
                    chunks.append(part)
                if chunks:
                    matrix = np.vstack(chunks)
            self._index.alias_matrix = matrix
            self._warm = True
            self._score_cache.clear()
            self._query_vec_cache.clear()
            logger.info(
                "Question bank warm (semantic=%s) in %.0f ms",
                matrix is not None,
                (time.perf_counter() - started) * 1000,
            )

    async def warm_async(self) -> None:
        import asyncio

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.warm)

    # ── public read API ────────────────────────────────────────────────

    @property
    def generation(self) -> int:
        """Increments on each bank load; derived caches key on it."""
        return self._generation

    @property
    def entries(self) -> list[BankEntry]:
        self.load()
        return list(self._index.entries)

    def get(self, entry_id: str) -> Optional[BankEntry]:
        self.load()
        return self._index.by_id.get(entry_id)

    def categories(self) -> list[str]:
        self.load()
        return sorted({e.category for e in self._index.entries})

    def search(self, query: str, limit: int = 10) -> list[BankMatch]:
        """Ranked matches for browsing (no thresholds applied)."""
        self.warm()
        scored = self._score_all(query)
        if not scored:
            return []
        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[BankMatch] = []
        for score, sem, lex, kw, entry_pos, alias_pos in scored[:limit]:
            entry = self._index.entries[entry_pos]
            results.append(BankMatch(
                entry=entry, score=score, semantic=sem, lexical=lex, keyword=kw,
                alias=self._index.alias_raw[alias_pos] if alias_pos >= 0 else entry.question,
                mode="strong" if score >= STRONG_THRESHOLD else ("weak" if score >= WEAK_THRESHOLD else "none"),
            ))
        return results

    # ── matching ───────────────────────────────────────────────────────

    def remember(self, transcript: str, entry_id: str) -> None:
        key = normalize_for_matching(transcript)
        if not key:
            return
        self._recent_matches[key] = entry_id
        self._recent_matches.move_to_end(key)
        while len(self._recent_matches) > 64:
            self._recent_matches.popitem(last=False)

    def topic_for_history(self, conversation_history: Optional[Iterable[dict]]) -> Optional[str]:
        """Topic of the most recent interviewer question that the bank answered."""
        if not conversation_history:
            return None
        for entry in reversed(list(conversation_history)):
            if entry.get("role") != "interviewer":
                continue
            key = normalize_for_matching(str(entry.get("text") or ""))
            entry_id = self._recent_matches.get(key)
            if entry_id:
                bank_entry = self._index.by_id.get(entry_id)
                if bank_entry is not None:
                    return bank_entry.topic or None
            # Only the latest interviewer question counts as the live topic.
            return None
        return None

    def match(
        self,
        text: str,
        *,
        topic_hint: Optional[str] = None,
        conversation_history: Optional[Iterable[dict]] = None,
        tech_repair: bool = True,
        _skip_follow_up: bool = False,
    ) -> Optional[BankMatch]:
        """Best bank entry for a transcribed question, or None below WEAK_THRESHOLD."""
        # Never block a live question on embedding warm-up: before `warm()` has
        # finished, scoring transparently falls back to lexical-only.
        self.load()
        if topic_hint is None:
            topic_hint = self.topic_for_history(conversation_history)

        raw_text = " ".join((text or "").strip().split())

        def _finish(result: Optional[BankMatch]) -> Optional[BankMatch]:
            if _skip_follow_up:
                return result
            return self._apply_follow_up_expand(
                raw_text,
                result,
                conversation_history=conversation_history,
                topic_hint=topic_hint,
                tech_repair=tech_repair,
            )

        recovery = None
        understanding = None
        if tech_repair:
            from app.services.bank_guided_understanding import understand_interview_question
            from app.services.short_tech_recovery import recover_tech_terms

            # Bank-primary understanding: STT is hypothesis; bank is reference.
            understanding = understand_interview_question(
                raw_text, prior_topic=topic_hint
            )
            if understanding.intent_id and not understanding.ambiguous:
                repaired = understanding.canonical_question
            else:
                repaired = understanding.recovered_transcript or repair_technical_terms(
                    raw_text, prior_topic=topic_hint
                )
            recovery = recover_tech_terms(raw_text)
        else:
            repaired = raw_text

        primary = self._match_repaired(
            repaired,
            topic_hint=topic_hint,
            conversation_history=conversation_history,
        )

        # Ambiguity guard: "How do you plan your project/work?" must not
        # become project-overview just because of the word "project".
        if tech_repair and understanding is not None:
            low = raw_text.casefold()
            if re.search(
                r"\bhow (?:do|did|would) you plan your (?:project|work|time|week)\b",
                low,
            ):
                if primary is not None and primary.entry.id in {
                    "cv.projects_overview",
                    "cv.projects.most_recent",
                    "cv.projects.most_proud",
                }:
                    alt = self._index.by_id.get("gen.prioritize")
                    if alt is not None and "work" in low:
                        primary = BankMatch(
                            entry=alt,
                            score=max(WEAK_THRESHOLD, 0.6),
                            semantic=0.0,
                            lexical=0.6,
                            keyword=0.0,
                            alias=alt.question,
                            mode="weak",
                            runner_up=primary.entry.id,
                            runner_up_score=primary.score,
                        )
                    else:
                        # Prefer abstain over confident wrong project answer
                        primary = None

        # Bank-guided clear winner overrides a miss / wrong primary (weak-safe).
        if (
            tech_repair
            and understanding is not None
            and understanding.intent_id
            and not understanding.ambiguous
            and understanding.confidence >= 0.72
            and understanding.margin >= 0.12
        ):
            guided_entry = self._index.by_id.get(understanding.intent_id)
            if guided_entry is not None:
                if primary is not None and primary.entry.id == guided_entry.id:
                    return _finish(primary)
                if primary is None or primary.entry.id != guided_entry.id:
                    runner = primary.entry.id if primary is not None else None
                    runner_score = primary.score if primary is not None else 0.0
                    mode = "weak"
                    if understanding.confidence >= STRONG_THRESHOLD and understanding.margin >= 0.18:
                        mode = "strong"
                    return _finish(
                        BankMatch(
                            entry=guided_entry,
                            score=float(understanding.confidence),
                            semantic=0.0,
                            lexical=float(understanding.confidence),
                            keyword=0.0,
                            alias=understanding.canonical_question or guided_entry.question,
                            mode=mode,
                            runner_up=runner,
                            runner_up_score=runner_score,
                        )
                    )

        # Dual scoring for tech-term recovery: raw vs normalized.
        if (
            tech_repair
            and recovery is not None
            and recovery.recovered_terms
            and recovery.short_structure.is_short
        ):
            from app.services.short_tech_recovery import reconcile_dual_matches

            raw_match = self._match_repaired(
                raw_text,
                topic_hint=topic_hint,
                conversation_history=conversation_history,
            )
            return _finish(
                reconcile_dual_matches(
                    raw_match=raw_match,
                    norm_match=primary,
                    recovery=recovery,
                )
            )
        return _finish(primary)

    def _apply_follow_up_expand(
        self,
        raw_text: str,
        raw_match: Optional[BankMatch],
        *,
        conversation_history: Optional[Iterable[dict]],
        topic_hint: Optional[str],
        tech_repair: bool,
    ) -> Optional[BankMatch]:
        from app.services.follow_up_expand import apply_follow_up_expand

        recent_entry = None
        if conversation_history:
            for hist in reversed(list(conversation_history)):
                if hist.get("role") != "interviewer":
                    continue
                key = normalize_for_matching(str(hist.get("text") or ""))
                eid = self._recent_matches.get(key)
                if eid:
                    recent_entry = self._index.by_id.get(eid)
                break

        def _match_expanded(expanded: str) -> Optional[BankMatch]:
            return self.match(
                expanded,
                topic_hint=topic_hint,
                conversation_history=conversation_history,
                tech_repair=tech_repair,
                _skip_follow_up=True,
            )

        return apply_follow_up_expand(
            raw_text=raw_text,
            raw_match=raw_match,
            conversation_history=conversation_history,
            match_expanded=_match_expanded,
            recent_entry=recent_entry,
        )

    def _match_repaired(
        self,
        repaired: str,
        *,
        topic_hint: Optional[str] = None,
        conversation_history: Optional[Iterable[dict]] = None,
    ) -> Optional[BankMatch]:
        """Score a transcript that is already tech-repaired (or intentionally raw)."""
        normalized = normalize_for_matching(repaired)
        if not normalized:
            return None
        content = _content_tokens(normalized)
        # Bare continuers ("Why?", "How?") lose all tokens to the stopword list.
        # Re-use the remembered prior bank entry as WEAK grounding only — never
        # re-rank an expanded string (that created strong wrong intents).
        _BARE_CONTINUERS = {
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
        }
        if not content:
            if topic_hint and normalized in _BARE_CONTINUERS and conversation_history:
                for hist_entry in reversed(list(conversation_history)):
                    if hist_entry.get("role") != "interviewer":
                        continue
                    key = normalize_for_matching(str(hist_entry.get("text") or ""))
                    entry_id = self._recent_matches.get(key)
                    bank_entry = self._index.by_id.get(entry_id) if entry_id else None
                    if bank_entry is not None:
                        return BankMatch(
                            entry=bank_entry,
                            score=max(WEAK_THRESHOLD, 0.55),
                            semantic=0.0,
                            lexical=0.0,
                            keyword=0.0,
                            alias=bank_entry.question,
                            mode="weak",
                        )
                    break
            return None

        scored = self._score_all(
            repaired, normalized=normalized, content=content, topic_hint=topic_hint
        )
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        scored = self._maybe_semantic_rerank(repaired, scored)
        score, sem, lex, kw, entry_pos, alias_pos = scored[0]
        entry = self._index.entries[entry_pos]

        # Generic follow-up ("what was your role in it?") right after a bank
        # answer: stay inside that topic rather than jumping elsewhere. The
        # best in-topic entry is handed to the LLM as grounding (weak mode).
        # Do not let a high off-topic score escape this lock — pronouns like
        # "it"/"that" make other projects look like exact aliases.
        if (
            topic_hint
            and entry.topic != topic_hint
            and any(marker in normalized for marker in _FOLLOW_UP_GENERIC)
        ):
            in_topic = [c for c in scored if self._index.entries[c[4]].topic == topic_hint]
            if in_topic:
                t_score, t_sem, t_lex, t_kw, t_pos, t_alias = in_topic[0]
                t_entry = self._index.entries[t_pos]
                return BankMatch(
                    entry=t_entry, score=t_score, semantic=t_sem, lexical=t_lex, keyword=t_kw,
                    alias=self._index.alias_raw[t_alias] if t_alias >= 0 else t_entry.question,
                    mode="strong" if t_score >= STRONG_THRESHOLD else "weak",
                    runner_up=entry.id, runner_up_score=score,
                )

        # Very short utterances: allow distinctive tech terms (RAG, agentic)
        # even when lexical coverage is thin after normalization.
        distinctive_hit = self._distinctive_query_terms(normalized, content)
        if len(content) <= 2 and not distinctive_hit:
            # Near-verbatim alias (e.g. "explain your project") must not be
            # dropped just because verbs like explain/tell are stopwords.
            near_verbatim = lex >= 0.95 and score >= WEAK_THRESHOLD
            if not near_verbatim and (lex < 0.80 or (sem < 0.55 and kw <= 0.0)):
                return None
        elif len(content) <= 2 and distinctive_hit:
            if score < WEAK_THRESHOLD and kw <= 0.0 and lex < 0.55 and sem < 0.50:
                return None

        mode = "none"
        lexical_override = lex >= LEXICAL_OVERRIDE and len(content) >= 3
        if score >= STRONG_THRESHOLD or lexical_override or sem >= SEMANTIC_OVERRIDE:
            mode = "strong"
        elif score >= WEAK_THRESHOLD:
            mode = "weak"
        # Distinctive short tech questions can still be strong via keyword hit.
        if mode == "none" and distinctive_hit and kw >= 0.5 and score >= 0.48:
            mode = "weak"
        if mode == "none":
            return None

        # Two questions in one utterance: only an alias that covers the whole
        # utterance may answer it verbatim. Otherwise the best entry grounds
        # the LLM, which must answer every part.
        if mode == "strong" and not lexical_override and is_compound_question(normalized):
            mode = "weak"
        # Before the embedding index is warm, scoring is lexical-only, which is
        # too coarse to read a prepared answer aloud unless it is near-verbatim.
        if mode == "strong" and self._index.alias_matrix is None and not lexical_override:
            mode = "weak"

        runner = None
        runner_score = 0.0
        for cand in scored[1:]:
            if cand[4] != entry_pos:
                runner = self._index.entries[cand[4]].id
                runner_score = cand[0]
                break
        # Long paraphrases lose lexical score to coverage damping, but when one
        # entry leads the runner-up by a wide margin the question is not
        # ambiguous: read the prepared answer.
        if (
            mode == "weak"
            and self._index.alias_matrix is not None
            and score >= CLEAR_WINNER_THRESHOLD
            and runner is not None
            and score - runner_score >= CLEAR_WINNER_MARGIN
            and not is_compound_question(normalized)
        ):
            mode = "strong"
        # Ambiguous between two different topics -> let the LLM adapt instead of
        # confidently reading the wrong prepared answer.
        if (
            mode == "strong"
            and runner is not None
            and score - runner_score < 0.025
            and self._index.by_id[runner].topic != entry.topic
            and not lexical_override
        ):
            mode = "weak"

        key = normalize_for_matching(repaired)
        if key:
            self._recent_matches[key] = entry.id
            while len(self._recent_matches) > 64:
                self._recent_matches.popitem(last=False)

        return BankMatch(
            entry=entry, score=score, semantic=sem, lexical=lex, keyword=kw,
            alias=self._index.alias_raw[alias_pos] if alias_pos >= 0 else entry.question,
            mode=mode, runner_up=runner, runner_up_score=runner_score,
        )

    def prefetch_scores(
        self,
        texts: list[str],
        *,
        topic_hint: Optional[str] = None,
        conversation_history: Optional[Iterable[dict]] = None,
    ) -> None:
        """
        Batch-embed + score unique queries once (Latency-cut for compound).
        Populates `_score_cache` so subsequent match()/top_matches() reuse work.
        """
        self.load()
        if topic_hint is None:
            topic_hint = self.topic_for_history(conversation_history)
        prepared: list[tuple[str, str, list[str]]] = []
        seen: set[str] = set()
        for text in texts:
            if not (text or "").strip():
                continue
            repaired = repair_technical_terms(text, prior_topic=topic_hint)
            normalized = normalize_for_matching(repaired)
            if not normalized or normalized in seen:
                continue
            content = _content_tokens(normalized)
            if not content:
                continue
            seen.add(normalized)
            prepared.append((repaired, normalized, content))
        if not prepared:
            return
        vecs = None
        if self._index.alias_matrix is not None:
            vecs = self._embed([n for _r, n, _c in prepared])
        for i, (repaired, normalized, content) in enumerate(prepared):
            qv = vecs[i] if vecs is not None else None
            if qv is not None:
                # Share the batched vector with match()/top_matches()/rerank.
                self._query_vec_cache[normalized] = qv
                self._query_vec_cache.move_to_end(normalized)
            self._score_all(
                repaired,
                normalized=normalized,
                content=content,
                topic_hint=topic_hint,
                query_vec=qv,
            )
        while len(self._query_vec_cache) > self._query_vec_cache_limit:
            self._query_vec_cache.popitem(last=False)

    def top_matches(
        self,
        text: str,
        *,
        top_k: int = 5,
        topic_hint: Optional[str] = None,
        conversation_history: Optional[Iterable[dict]] = None,
    ) -> list[BankMatch]:
        """
        Rank unique bank entries for recovery passes (Poor Call).
        Does not change `match()` thresholds; returns up to top_k candidates.
        """
        self.load()
        if topic_hint is None:
            topic_hint = self.topic_for_history(conversation_history)
        repaired = repair_technical_terms(text, prior_topic=topic_hint)
        normalized = normalize_for_matching(repaired)
        if not normalized:
            return []
        content = _content_tokens(normalized)
        if not content:
            return []
        scored = self._score_all(
            repaired, normalized=normalized, content=content, topic_hint=topic_hint
        )
        if not scored:
            return []
        scored.sort(key=lambda item: item[0], reverse=True)
        scored = self._maybe_semantic_rerank(repaired, scored)

        out: list[BankMatch] = []
        seen: set[int] = set()
        for score, sem, lex, kw, entry_pos, alias_pos in scored:
            if entry_pos in seen:
                continue
            seen.add(entry_pos)
            entry = self._index.entries[entry_pos]
            runner = None
            runner_score = 0.0
            for cand in scored:
                if cand[4] != entry_pos:
                    runner = self._index.entries[cand[4]].id
                    runner_score = cand[0]
                    break
            mode = "weak"
            if score >= STRONG_THRESHOLD:
                mode = "strong"
            elif score < WEAK_THRESHOLD:
                mode = "weak"
            out.append(
                BankMatch(
                    entry=entry,
                    score=float(score),
                    semantic=float(sem),
                    lexical=float(lex),
                    keyword=float(kw),
                    alias=self._index.alias_raw[alias_pos] if alias_pos >= 0 else entry.question,
                    mode=mode,
                    runner_up=runner,
                    runner_up_score=float(runner_score),
                )
            )
            if len(out) >= max(1, (top_k)):
                break
        return out

    @staticmethod
    def _distinctive_query_terms(normalized: str, content: list[str]) -> set[str]:
        hits: set[str] = set()
        bag = set(content) | set(normalized.split())
        for token, (family, _boost) in _DISTINCTIVE_TERMS.items():
            if token in bag or family in bag:
                hits.add(family)
        return hits

    def _entry_owns_distinctive(self, entry_pos: int, family: str) -> bool:
        entry = self._index.entries[entry_pos]
        blob = " ".join(
            [
                entry.id,
                entry.topic,
                entry.question,
                " ".join(entry.keywords),
                " ".join(entry.aliases[:12]),
            ]
        ).casefold()
        return family in blob

    def _maybe_semantic_rerank(
        self,
        text: str,
        scored: list[tuple[float, float, float, float, int, int]],
    ) -> list[tuple[float, float, float, float, int, int]]:
        """When top scores are close, re-rank top-3 by embedding similarity to question text."""
        if len(scored) < 2:
            return scored
        top = scored[0][0]
        second = scored[1][0]
        if top < AMBIGUOUS_TOP_MIN or (top - second) > AMBIGUOUS_MARGIN:
            return scored
        if self._index.alias_matrix is None:
            return scored
        top3 = scored[:3]
        questions = [self._index.entries[item[4]].question for item in top3]
        # PERF: every bank question is already an indexed alias, so its embedding
        # is a row of `alias_matrix`, and the query vector was embedded during
        # `_score_all`. Reuse both instead of a fresh 4-text ONNX call.
        wanted = [normalize_for_matching(text), *[normalize_for_matching(q) for q in questions]]
        reused: list[Optional[np.ndarray]] = [self._query_vector(wanted[0])]
        reused.extend(self.alias_vector(w) for w in wanted[1:])
        if any(v is None for v in reused):
            vectors = self._embed(wanted)
        else:
            vectors = np.vstack([v for v in reused if v is not None])
        if vectors is None or len(vectors) < 2:
            return scored
        qv = vectors[0]
        best_i = 0
        best_sim = -1.0
        for i in range(1, len(vectors)):
            denom = float(np.linalg.norm(qv) * np.linalg.norm(vectors[i])) + 1e-9
            sim = float(np.dot(qv, vectors[i]) / denom)
            if sim > best_sim:
                best_sim = sim
                best_i = i - 1
        if best_i == 0:
            return scored
        chosen = top3[best_i]
        rest = [item for j, item in enumerate(scored) if j != best_i]
        return [chosen, *rest]

    def _alias_candidates(
        self,
        content: list[str],
        normalized: str,
    ) -> Optional[list[int]]:
        """
        Inverted-index candidate pool for lexical scoring.
        Returns None → caller should score all aliases (safe fallback).
        """
        index = self._index
        n_alias = len(index.alias_texts)
        if n_alias == 0 or not index.token_to_alias:
            return None
        bag = set(content) | set(normalized.split())
        cand: set[int] = set()
        for tok in content:
            hits = index.token_to_alias.get(tok)
            if hits:
                cand.update(hits)
        for token, (family, _boost) in _DISTINCTIVE_TERMS.items():
            if token in bag or family in bag:
                hits = index.distinctive_to_alias.get(family)
                if hits:
                    cand.update(hits)
        # Too sparse → full scan (avoid missing weak paraphrases).
        if len(cand) < 12:
            return None
        # Nearly everything → full scan (pruning saves nothing).
        if len(cand) >= int(0.55 * n_alias):
            return None
        # Cap extreme pools: keep highest-overlap aliases only would change ranking;
        # instead allow up to ~400 candidates before falling back.
        if len(cand) > 400:
            return None
        return list(cand)

    def _score_all(
        self,
        text: str,
        *,
        normalized: Optional[str] = None,
        content: Optional[list[str]] = None,
        topic_hint: Optional[str] = None,
        query_vec: Optional[np.ndarray] = None,
    ) -> list[tuple[float, float, float, float, int, int]]:
        """Return (score, semantic, lexical, keyword, entry_pos, alias_pos) per entry."""
        index = self._index
        if not index.entries:
            return []
        normalized = normalized if normalized is not None else normalize_for_matching(text)
        if not normalized:
            return []
        content = content if content is not None else _content_tokens(normalized)
        content_text = " ".join(content) or normalized
        # Cache must key on bank generation + whether semantic matrix is live.
        # Otherwise a lexical-only score computed before warm() is reused after
        # warm and can flip how/definition winners (e.g. RAG) under the full suite.
        matrix_state = "sem" if index.alias_matrix is not None else "lex"
        cache_key = f"{self._generation}|{matrix_state}|{normalized}||{topic_hint or ''}"
        cached = self._score_cache.get(cache_key)
        if cached is not None:
            self._score_cache.move_to_end(cache_key)
            return list(cached)

        from rapidfuzz import fuzz

        n_alias = len(index.alias_texts)
        semantic = np.zeros(n_alias, dtype=np.float32)
        if index.alias_matrix is not None:
            if query_vec is None:
                query_vec = self._query_vector(normalized)
            if query_vec is not None:
                semantic = index.alias_matrix @ query_vec

        # Prefer precomputed content strings/sets; fall back if index is mid-load.
        use_pre = len(index.alias_content_text) == n_alias and len(index.alias_token_sets) == n_alias
        pruned = self._alias_candidates(content, normalized)
        # Generic follow-ups need every in-topic alias visible so the topic lock
        # can fire. Inverted-index pruning often drops them (few shared tokens
        # with "what was your role in it?"), which let off-topic intros win.
        if (
            topic_hint
            and pruned is not None
            and any(marker in normalized for marker in _FOLLOW_UP_GENERIC)
        ):
            topic_alias_pos = [
                i
                for i, entry_pos in enumerate(index.alias_entry)
                if index.entry_topic[entry_pos] == topic_hint
                or index.entries[entry_pos].topic == topic_hint
            ]
            if topic_alias_pos:
                pruned = list(set(pruned) | set(topic_alias_pos))
        used_prune = pruned is not None
        alias_positions = pruned if used_prune else list(range(n_alias))

        generic_follow_up = any(marker in normalized for marker in _FOLLOW_UP_GENERIC)
        query_intent = detect_intent(normalized)
        personal = is_personal_question(normalized)
        q_distinctive = {
            fam: b
            for tok, (fam, b) in _DISTINCTIVE_TERMS.items()
            if tok in content or fam in content or tok in normalized.split()
        }
        guardrail_query = "guardrail" in normalized or "guardrails" in content
        content_set = set(content)
        n_content = len(content)
        cv_def_query = query_intent == "definition"
        has_owned = bool(index.entry_owned_families) and len(index.entry_owned_families) == len(index.entries)
        best_per_entry: dict[int, tuple[float, float, float, float, int]] = {}

        def _lexical_batch(positions: list[int]) -> tuple[Any, Any]:
            """
            Batch the two rapidfuzz calls for `positions`.

            `process.cdist` runs the *same* C++ scorers as the scalar calls, so
            each value is identical to `fuzz.token_set_ratio(...)` /
            `fuzz.partial_ratio(...)`; only the Python-level loop disappears.
            Returns (token_set_ratios, partial_ratios) or (None, None) to use
            the scalar path.
            """
            if not _FAST_LEXICAL or not use_pre or len(positions) < _FAST_LEXICAL_MIN:
                return None, None
            try:
                from rapidfuzz import process as _rf_process

                contents = [index.alias_content_text[p] for p in positions]
                raws = [index.alias_texts[p] for p in positions]
                # rapidfuzz stubs type `scorer` more narrowly than the runtime API.
                ts = _rf_process.cdist(
                    [content_text],
                    contents,
                    scorer=cast(Any, fuzz.token_set_ratio),
                    workers=-1,
                    dtype=np.float64,
                )[0]
                pr = _rf_process.cdist(
                    [normalized],
                    raws,
                    scorer=cast(Any, fuzz.partial_ratio),
                    workers=-1,
                    dtype=np.float64,
                )[0]
                return ts, pr
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Vectorized lexical scoring unavailable (%s); using scalar path", exc)
                return None, None

        def _score_positions(positions: list[int]) -> None:
            ts_batch, pr_batch = _lexical_batch(positions)
            for slot, pos in enumerate(positions):
                entry_pos = index.alias_entry[pos]
                alias = index.alias_texts[pos]
                if use_pre:
                    alias_content = index.alias_content_text[pos]
                    alias_tokens = index.alias_token_sets[pos]
                else:
                    alias_tokens_list = _content_tokens(alias)
                    alias_content = " ".join(alias_tokens_list) or alias
                    alias_tokens = set(alias_tokens_list)
                if ts_batch is not None:
                    token_set = float(ts_batch[slot]) / 100.0
                    partial = float(pr_batch[slot]) / 100.0 if len(alias) >= 10 else 0.0
                else:
                    token_set = fuzz.token_set_ratio(content_text, alias_content) / 100.0
                    partial = fuzz.partial_ratio(normalized, alias) / 100.0 if len(alias) >= 10 else 0.0
                shared = len(content_set & alias_tokens)
                if shared <= 1 and n_content >= 3:
                    token_set *= 0.75
                lex_value = max(token_set, 0.9 * partial)
                if content:
                    coverage = shared / float(n_content)
                    uncovered = n_content - shared
                    if uncovered >= 2 and coverage < 0.75:
                        lex_value *= 0.55 + 0.45 * coverage
                sem = float(semantic[pos]) if n_alias else 0.0
                lex = float(lex_value)
                intent_adjust = 0.0
                alias_intent = index.alias_intent[pos]
                if query_intent and alias_intent:
                    if query_intent == alias_intent:
                        intent_adjust = INTENT_MATCH_BONUS
                    elif frozenset({query_intent, alias_intent}) not in _INTENT_COMPATIBLE:
                        intent_adjust = -INTENT_MISMATCH_PENALTY
                kws = index.entry_keywords[entry_pos]
                if kws:
                    hits = sum(1 for k in kws if k and k in normalized)
                    kw = min(1.0, hits / max(1.0, min(2.0, float(len(kws)))))
                else:
                    kw = 0.0
                if index.alias_matrix is not None:
                    score = 0.55 * sem + 0.35 * lex + 0.10 * kw
                else:
                    score = 0.80 * lex + 0.20 * kw
                score += intent_adjust
                entry = index.entries[entry_pos]
                entry_topic = index.entry_topic[entry_pos] if has_owned else entry.topic
                if q_distinctive:
                    owned_families = (
                        index.entry_owned_families[entry_pos] if has_owned else None
                    )
                    for family, boost in q_distinctive.items():
                        if owned_families is not None:
                            owns = family in owned_families
                        else:
                            owns = family in " ".join(
                                [entry.id, entry.topic, " ".join(entry.keywords), entry.question]
                            ).casefold()
                        if owns:
                            score += boost
                        elif entry.id in _GENERIC_DEF_IDS or (
                            entry_topic in {"llm", "ai"} and family not in {"llm", "ai"}
                        ):
                            score -= boost * 0.85
                if guardrail_query:
                    if has_owned:
                        penalize = index.entry_guardrail_penalty[entry_pos]
                    else:
                        penalize = entry.id in _GENERIC_DEF_IDS or (
                            "guardrail" not in entry.topic
                            and "guardrail" not in " ".join(entry.keywords).casefold()
                            and "llm" in entry.topic
                        )
                    if penalize:
                        score -= 0.18
                if cv_def_query and (
                    index.entry_cv_definition_penalty[entry_pos]
                    if has_owned
                    else (
                        entry.bank == "cv"
                        and entry.topic
                        in {"agentic", "rag", "guardrails", "langchain", "langgraph"}
                    )
                ):
                    score -= 0.12
                if (
                    personal
                    and (index.entry_is_technical[entry_pos] if has_owned else entry.bank == "technical")
                    and alias_intent in ("definition", "how")
                    and query_intent not in ("definition", "how")
                ):
                    score -= PERSONAL_VS_DEFINITION_PENALTY
                if topic_hint and entry_topic == topic_hint:
                    score += TOPIC_BOOST if generic_follow_up else TOPIC_BOOST / 2
                current = best_per_entry.get(entry_pos)
                if current is None or score > current[0]:
                    best_per_entry[entry_pos] = (score, sem, lex, kw, pos)

        _score_positions(alias_positions)
        # Quality safety: pruned pool too weak → full scan (same scoring math).
        if used_prune and (
            not best_per_entry
            or max(v[0] for v in best_per_entry.values()) < WEAK_THRESHOLD
        ):
            best_per_entry.clear()
            _score_positions(list(range(n_alias)))

        result = [
            (score, sem, lex, kw, entry_pos, alias_pos)
            for entry_pos, (score, sem, lex, kw, alias_pos) in best_per_entry.items()
        ]
        self._score_cache[cache_key] = list(result)
        while len(self._score_cache) > self._score_cache_limit:
            self._score_cache.popitem(last=False)
        return result

    # ── embedding reuse (PERF) ─────────────────────────────────────────

    def _query_vector(self, normalized: str) -> Optional[np.ndarray]:
        """
        Embed a *normalized* query once and reuse it inside the request.

        Same vector the previous code produced with `self._embed([normalized])`;
        the cache only removes repeated ONNX calls for the same string.
        """
        if not normalized:
            return None
        hit = self._query_vec_cache.get(normalized)
        if hit is not None:
            self._query_vec_cache.move_to_end(normalized)
            return hit
        embedded = self._embed([normalized])
        if embedded is None:
            return None
        vec = embedded[0]
        self._query_vec_cache[normalized] = vec
        while len(self._query_vec_cache) > self._query_vec_cache_limit:
            self._query_vec_cache.popitem(last=False)
        return vec

    def alias_vector(self, normalized_alias: str) -> Optional[np.ndarray]:
        """Row of `alias_matrix` for an already-indexed normalized alias, if any."""
        if self._index.alias_matrix is None:
            return None
        pos = self._index.alias_text_pos.get(normalized_alias)
        if pos is None:
            return None
        return self._index.alias_matrix[pos]


question_bank = QuestionBank()
