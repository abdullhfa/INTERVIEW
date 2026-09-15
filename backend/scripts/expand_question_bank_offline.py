"""
Offline bank expansion (DRAFT ONLY — not production).

For each canonical bank question, propose:
  3 direct paraphrases, 3 indirect, 2 short, 2 spoken

Writes reports/V5_BANK_EXPANSION_DRAFT.json for human validation.
Does NOT mutate production question bank files.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.question_bank import question_bank

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def _variants(q: str) -> dict:
    q = (q or "").strip().rstrip("?")
    low = q.lower()
    direct = [
        f"Can you {low}?",
        f"Please {low}",
        f"I'd like you to {low}",
    ]
    if low.startswith("what is"):
        topic = q[7:].strip()
        direct = [
            f"Explain {topic}",
            f"Define {topic}",
            f"Tell me what {topic} means",
        ]
        indirect = [
            f"In simple terms, how would you describe {topic}?",
            f"If a non-engineer asked about {topic}, what would you say?",
            f"Where does {topic} show up in your work?",
        ]
        short = [f"{topic}?", f"Meaning of {topic}?"]
        spoken = [f"what is {topic.lower()}", f"explain {topic.lower()}"]
    elif low.startswith(("explain", "tell me", "walk me")):
        indirect = [
            f"If I only had two minutes, {low}",
            f"Without buzzwords, {low}",
            f"From a hiring manager view, {low}",
        ]
        short = [q.split()[-2] + "?" if len(q.split()) > 2 else q + "?", q.split()[0] + "?"]
        spoken = [low, low.replace("explain", "and you plan") if "explain" in low else low]
        direct = [f"Could you {low}?", f"Please {low}", f"Can you {low}?"]
    else:
        indirect = [
            f"From your experience, {low}?",
            f"In a real project, {low}?",
            f"Practically speaking, {low}?",
        ]
        short = [f"{' '.join(q.split()[:3])}?", f"{q.split()[0]}?"]
        spoken = [low, low]
    return {
        "direct_paraphrases": direct[:3],
        "indirect_paraphrases": indirect[:3],
        "short_variants": short[:2],
        "spoken_variants": spoken[:2],
    }


def main() -> int:
    question_bank.load(force=True)
    rows = []
    for e in question_bank.entries:
        rows.append(
            {
                "intent_id": e.id,
                "category": e.category,
                "topic": e.topic,
                "canonical_question": e.question,
                "existing_aliases": list(e.aliases)[:8],
                "proposed": _variants(e.question),
                "status": "DRAFT_NEEDS_VALIDATION",
            }
        )
    payload = {
        "note": "DRAFT only — do not merge into production without validation",
        "n": len(rows),
        "entries": rows,
    }
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / "V5_BANK_EXPANSION_DRAFT.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {path} n={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
