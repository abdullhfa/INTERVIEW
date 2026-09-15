"""
Prepared question bank API — browse, search, and test-match bank entries.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.question_bank import question_bank

router = APIRouter()


class BankEntryOut(BaseModel):
    id: str
    bank: str
    category: str
    topic: str
    question: str
    aliases: list[str]
    keywords: list[str]
    answer_en: str
    answer_ar: Optional[str] = None
    followup_en: Optional[str] = None
    listen_for: list[str] = []


class BankListOut(BaseModel):
    total: int
    banks: list[str]
    categories: list[str]
    entries: list[BankEntryOut]


class BankMatchOut(BaseModel):
    id: str
    question: str
    topic: str
    bank: str
    mode: str
    score: float
    semantic: float
    lexical: float
    keyword: float
    matched_alias: str
    answer_en: str
    followup_en: Optional[str] = None
    runner_up: Optional[str] = None
    runner_up_score: float = 0.0


class MatchRequest(BaseModel):
    text: str = Field(min_length=1)
    topic_hint: Optional[str] = None


class MatchResponse(BaseModel):
    text: str
    match: Optional[BankMatchOut] = None
    candidates: list[BankMatchOut]


def _match_out(m: Any) -> BankMatchOut:
    return BankMatchOut(
        id=m.entry.id,
        question=m.entry.question,
        topic=m.entry.topic,
        bank=m.entry.bank,
        mode=m.mode,
        score=round(float(m.score), 3),
        semantic=round(float(m.semantic), 3),
        lexical=round(float(m.lexical), 3),
        keyword=round(float(m.keyword), 3),
        matched_alias=m.alias,
        answer_en=m.entry.answer_en,
        followup_en=m.entry.followup_en,
        runner_up=m.runner_up,
        runner_up_score=round(float(m.runner_up_score), 3),
    )


@router.get("", response_model=BankListOut)
async def list_bank(
    bank: Optional[str] = Query(None, description="Filter by bank: cv, general, technical"),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Free-text search (ranked)"),
    limit: int = Query(500, ge=1, le=1000),
) -> BankListOut:
    entries = question_bank.entries
    if q:
        ranked = question_bank.search(q, limit=limit)
        entries = [m.entry for m in ranked]
    if bank:
        entries = [e for e in entries if e.bank == bank]
    if category:
        entries = [e for e in entries if e.category == category]
    return BankListOut(
        total=len(entries),
        banks=sorted({e.bank for e in question_bank.entries}),
        categories=question_bank.categories(),
        entries=[BankEntryOut(**e.to_public()) for e in entries[:limit]],
    )


@router.get("/{entry_id}", response_model=BankEntryOut)
async def get_entry(entry_id: str) -> BankEntryOut:
    entry = question_bank.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Question bank entry not found")
    return BankEntryOut(**entry.to_public())


@router.post("/match", response_model=MatchResponse)
async def match_text(payload: MatchRequest) -> MatchResponse:
    """Dry-run the live matcher on any text (useful to test accents/paraphrases)."""
    match = question_bank.match(payload.text, topic_hint=payload.topic_hint)
    candidates = question_bank.search(payload.text, limit=5)
    return MatchResponse(
        text=payload.text,
        match=_match_out(match) if match else None,
        candidates=[_match_out(c) for c in candidates],
    )
