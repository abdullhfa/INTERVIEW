"""
Optimization equivalence harness.

Proves that a performance change did NOT move any decision: it dumps the full
decision surface (lexical scores, match, top_matches, semantic trigger,
semantic recovery outcome, compound resolution) for a fixed query set, and
diffs two dumps field by field.

    # before touching anything
    python scripts/verify_intent_equivalence.py --dump reports/EQUIV_BEFORE.json
    # after the change
    python scripts/verify_intent_equivalence.py --dump reports/EQUIV_AFTER.json
    python scripts/verify_intent_equivalence.py --compare reports/EQUIV_BEFORE.json reports/EQUIV_AFTER.json

Exit code 1 on any difference. Run with --semantic to include the embedding
path (requires a warm embedder); without it the run is lexical-only and fast.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BANK_DIR = ROOT / "app" / "data" / "question_bank"

PROBE_QUERIES = [
    "What is RAG?",
    "What are guardrails?",
    "What is agentic AI?",
    "Why embeddings?",
    "What is LangGraph?",
    "Why recall?",
    "What if retrieval fails?",
    "Who approves the result?",
    "What is LangGraph and how do checkpoints work, and why did you choose it?",
    "Tell me about the BTEC project, what stack did you use, and how did you measure quality?",
    "Explain embeddings and cosine similarity, then say why recall matters for student "
    "support, and point to guardrails and validation.",
]


def build_queries(n: int, seed: int = 7) -> list[str]:
    """Bank questions + aliases (deterministic sample) plus fixed probes."""
    pool: list[str] = []
    for path in sorted(BANK_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for entry in payload.get("entries", []):
            if entry.get("question"):
                pool.append(entry["question"])
            for alias in (entry.get("aliases") or [])[:2]:
                pool.append(alias)
    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool[:n] + PROBE_QUERIES


def dump(queries: list[str], *, semantic: bool) -> list[dict[str, Any]]:
    from app.services.question_bank import question_bank, _content_tokens
    from app.services.domain_terms import normalize_for_matching
    from app.services.semantic_intent_recovery import (
        should_trigger_semantic_recovery,
        recover_semantic_intent,
        _lexical_expand_candidates,
    )
    from app.services.compound_question_pipeline import resolve_compound_question

    question_bank.load()
    if semantic:
        question_bank.warm()
        from app.services.semantic_intent_index import semantic_intent_index

        semantic_intent_index.warm()

    rows: list[dict[str, Any]] = []
    for q in queries:
        norm = normalize_for_matching(q)
        content = _content_tokens(norm)
        scored = sorted(
            question_bank._score_all(q, normalized=norm, content=content),  # noqa: SLF001
            key=lambda x: (-x[0], x[4]),
        )
        m = question_bank.match(q)
        tops = question_bank.top_matches(q, top_k=5)
        trig = should_trigger_semantic_recovery(q, m)
        rec = recover_semantic_intent(q, m)
        cr = resolve_compound_question(q)
        rows.append(
            {
                "q": q,
                "norm": norm,
                "content": content,
                "scored_head": [
                    [round(float(a), 7), round(float(b), 7), round(float(c), 7),
                     round(float(d), 7), e, f]
                    for a, b, c, d, e, f in scored[:12]
                ],
                "n_scored": len(scored),
                "match": None if m is None else [
                    m.entry.id, round(float(m.score), 7), m.mode, m.runner_up,
                    round(float(m.runner_up_score or 0.0), 7),
                ],
                "tops": [[t.entry.id, round(float(t.score), 7), t.mode] for t in tops],
                "trigger": list(trig),
                "recover": [
                    rec.applied, rec.reason,
                    None if rec.match is None else rec.match.entry.id,
                    round(float(rec.agreement), 7), round(float(rec.margin), 7),
                    rec.reranker_used, rec.abstain_reason,
                    [d["id"] for d in rec.hybrid_top5],
                ],
                "expand": _lexical_expand_candidates(norm, content, limit=12),
                "compound": {
                    "type": cr.question_type,
                    "used": cr.used_compound_path,
                    "subs": cr.sub_questions,
                    "selected": cr.selected_intents,
                    "unknown": cr.unknown_parts,
                    "coverage": cr.intent_coverage_rate,
                    "answered": cr.answered_parts_count,
                    "failure": cr.failure_code,
                    "answer": (cr.answer_en or "")[:400],
                },
            }
        )
    return rows


def compare(a_path: Path, b_path: Path) -> int:
    a = json.loads(a_path.read_text(encoding="utf-8"))
    b = json.loads(b_path.read_text(encoding="utf-8"))
    if len(a) != len(b):
        print(f"DIFFERENT LENGTHS: {len(a)} vs {len(b)}")
        return 1
    diffs = []
    for x, y in zip(a, b):
        if x["q"] != y["q"]:
            diffs.append((x["q"], "query-order", x["q"], y["q"]))
            continue
        for key in x:
            if x[key] != y[key]:
                diffs.append((x["q"][:70], key, str(x[key])[:220], str(y[key])[:220]))
    print(f"rows={len(a)} differing_fields={len(diffs)}")
    for q, key, before, after in diffs[:25]:
        print(f"\n--- {q}\n  field: {key}\n  before: {before}\n  after : {after}")
    if diffs:
        print("\nEQUIVALENCE FAILED — the optimization changed a decision.")
        return 1
    print("EQUIVALENCE OK — every decision identical.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=Path)
    ap.add_argument("--compare", nargs=2, type=Path)
    ap.add_argument("--queries", type=int, default=160)
    ap.add_argument("--semantic", action="store_true")
    args = ap.parse_args()

    if args.compare:
        return compare(*args.compare)
    if not args.dump:
        ap.error("pass --dump PATH or --compare BEFORE AFTER")
    queries = build_queries(args.queries)
    rows = dump(queries, semantic=args.semantic)
    args.dump.parent.mkdir(parents=True, exist_ok=True)
    args.dump.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"dumped {len(rows)} rows -> {args.dump} (semantic={args.semantic})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
