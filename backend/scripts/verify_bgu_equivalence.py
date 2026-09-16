"""Prove bank_guided_understanding still decides identically after an edit.

Loads the version of the module at a git ref alongside the working-tree version
and compares BOTH stages over a corpus:

  * search_bank_candidates   — the cached scan (L2)
  * understand_interview_question — the merge/boost stage (where BankCandidate
    is rebuilt, i.e. the code the Pyrefly fix touched)

    cd backend
    python scripts\\verify_bgu_equivalence.py                 # vs HEAD
    python scripts\\verify_bgu_equivalence.py <git-ref>

Exit code 0 = identical, 1 = a decision moved.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REL = "backend/app/services/bank_guided_understanding.py"


def load_ref_module(ref: str):
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = subprocess.check_output(["git", "show", f"{ref}:{REL}"], cwd=repo)
    tmp = os.path.join(tempfile.mkdtemp(), "bgu_ref.py")
    with open(tmp, "wb") as fh:
        fh.write(src)
    spec = importlib.util.spec_from_file_location("bgu_ref", tmp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bgu_ref"] = mod
    spec.loader.exec_module(mod)
    return mod


def cand_key(cands) -> list:
    return [
        (
            c.intent_id, c.canonical, c.category, c.topic, c.question_type,
            round(c.phonetic, 9), round(c.lexical, 9), round(c.structure, 9),
            round(c.lexicon, 9), round(c.bank_prior, 9), round(c.combined, 9),
            c.alias_hit,
        )
        for c in cands
    ]


def result_key(r) -> tuple:
    return (
        r.raw_transcript, r.recovered_transcript, r.canonical_question,
        r.intent_id, round(float(r.confidence), 9), bool(r.ambiguous),
    )


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    from app.services import bank_guided_understanding as NEW
    from app.services.question_bank import question_bank

    OLD = load_ref_module(ref)
    question_bank.load()

    corpus: list[str] = []
    for e in question_bank.entries:
        corpus.append(e.question)
        for a in list(e.aliases)[:1]:
            corpus.append(a)
    corpus += [
        "What is RAG?", "Define embeddings.", "Explain LoRA.", "Yeah John",
        "Your download is ready", "water transformers", "wht is r-e",
        "Tell me about yourself.", "Explain your project.", "when hybrid search",
        "Kindly enter your text here to convert it to natural Indian English speech",
        "What is hallucination and why does it happen?",
    ]
    limit = int(os.environ.get("BGU_EQ_LIMIT", "300"))
    corpus = corpus[:limit]

    search_diffs = 0
    understand_diffs = 0
    for q in corpus:
        if cand_key(OLD.search_bank_candidates(q, k=5)) != cand_key(
            NEW.search_bank_candidates(q, k=5)
        ):
            search_diffs += 1
            if search_diffs <= 3:
                print(f"  SEARCH DIFF: {q!r}")
        try:
            o = OLD.understand_interview_question(q)
            n = NEW.understand_interview_question(q)
        except Exception as exc:
            print(f"  ERROR on {q!r}: {exc}")
            return 1
        if result_key(o) != result_key(n):
            understand_diffs += 1
            if understand_diffs <= 3:
                print(f"  UNDERSTAND DIFF: {q!r}\n    ref={result_key(o)}\n    new={result_key(n)}")

    print(f"corpus={len(corpus)} ref={ref}")
    print(f"search_bank_candidates differing:      {search_diffs}")
    print(f"understand_interview_question differing: {understand_diffs}")
    ok = search_diffs == 0 and understand_diffs == 0
    print("EQUIVALENT" if ok else "NOT EQUIVALENT — do not freeze")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
