"""Semantic index over intent profiles (reuses question_bank MiniLM embedder).

FROZEN 2026-09-12 with the semantic intent layer — bug-fix only.
See reports/INTENT_LAYER_FREEZE.json.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.services.intent_profile import IntentProfile, build_profiles_for_bank
from app.services.question_bank import question_bank

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SemanticHit:
    intent_id: str
    score: float
    profile: IntentProfile


class SemanticIntentIndex:
    """Top-K cosine retrieval over profile blobs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: dict[str, IntentProfile] = {}
        self._ids: list[str] = []
        self._matrix: Optional[np.ndarray] = None
        self._id_pos: dict[str, int] = {}
        self._warm = False

    @property
    def ready(self) -> bool:
        return self._warm and self._matrix is not None and bool(self._ids)

    def profiles(self) -> dict[str, IntentProfile]:
        self.ensure_loaded()
        return self._profiles

    def get(self, intent_id: str) -> Optional[IntentProfile]:
        self.ensure_loaded()
        return self._profiles.get(intent_id)

    def ensure_loaded(self) -> None:
        question_bank.load()
        if self._profiles and len(self._profiles) == len(question_bank.entries):
            return
        with self._lock:
            entries = question_bank.entries
            self._profiles = build_profiles_for_bank(entries)

    def warm(self) -> None:
        """Build profile embeddings using the bank embedder."""
        self.ensure_loaded()
        if self._warm and self._matrix is not None:
            return
        with self._lock:
            if self._warm and self._matrix is not None:
                return
            # Ensure alias matrix path is warm (loads embedder).
            question_bank.warm()
            started = time.perf_counter()
            ids = [e.id for e in question_bank.entries]
            blobs = [
                self._profiles[i].profile_blob if i in self._profiles else question_bank.get(i).question  # type: ignore[union-attr]
                for i in ids
            ]
            chunks: list[np.ndarray] = []
            batch = 32
            ok = True
            for start in range(0, len(blobs), batch):
                part = question_bank._embed(blobs[start : start + batch])  # noqa: SLF001 — shared embedder
                if part is None:
                    ok = False
                    break
                chunks.append(part)
            if ok and chunks:
                self._matrix = np.vstack(chunks)
                self._ids = ids
                self._id_pos = {pid: i for i, pid in enumerate(ids)}
                self._warm = True
            else:
                self._matrix = None
                self._ids = []
                self._id_pos = {}
                self._warm = True  # mark attempted; lexical-only fallback
            logger.info(
                "Semantic intent index warm (matrix=%s n=%s) in %.0f ms",
                self._matrix is not None,
                len(self._ids),
                (time.perf_counter() - started) * 1000,
            )

    def vector_for(self, intent_id: str) -> Optional[np.ndarray]:
        """
        Cached profile-blob embedding row, or None.

        PERF: the re-ranker used to re-embed the very blobs this matrix was
        built from. The row is the identical (L2-normalized) vector.
        """
        if self._matrix is None or not self._ids:
            return None
        if not self._id_pos or len(self._id_pos) != len(self._ids):
            self._id_pos = {pid: i for i, pid in enumerate(self._ids)}
        pos = self._id_pos.get(intent_id)
        if pos is None:
            return None
        return self._matrix[pos]

    def top_k(self, query: str, *, k: int = 5) -> list[SemanticHit]:
        hits = self.top_k_many([query], k=k)
        return hits[0] if hits else []

    def top_k_many(self, queries: list[str], *, k: int = 5) -> list[list[SemanticHit]]:
        """Batch-embed queries and search the cached profile matrix once."""
        self.ensure_loaded()
        if not queries:
            return []
        if self._matrix is None or not self._ids:
            return [[] for _ in queries]
        cleaned = [(q or "").strip() for q in queries]
        nonempty_idx = [i for i, q in enumerate(cleaned) if q]
        out: list[list[SemanticHit]] = [[] for _ in queries]
        if not nonempty_idx:
            return out
        vecs = question_bank._embed([cleaned[i] for i in nonempty_idx])  # noqa: SLF001
        if vecs is None:
            return out
        k = max(1, min((k), len(self._ids)))
        for row, qi in enumerate(nonempty_idx):
            scores = self._matrix @ vecs[row]
            if len(scores) > k:
                idx = np.argpartition(-scores, k)[:k]
                idx = idx[np.argsort(-scores[idx])]
            else:
                idx = np.argsort(-scores)
            hits: list[SemanticHit] = []
            for i in idx[:k]:
                intent_id = self._ids[int(i)]
                profile = self._profiles.get(intent_id)
                if profile is None:
                    continue
                hits.append(
                    SemanticHit(
                        intent_id=intent_id,
                        score=float(scores[int(i)]),
                        profile=profile,
                    )
                )
            out[qi] = hits
        return out


semantic_intent_index = SemanticIntentIndex()
