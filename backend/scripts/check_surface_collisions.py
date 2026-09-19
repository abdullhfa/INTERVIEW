"""Collision precheck for proposed surfaces (bank hygiene gate)."""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parents[1]
STOP = set(
    "what is the a an of to in for do does did you your how why when which who are was can could would should will have has and or with on at by from it its as that this these i me my about tell me explain describe walk through we our us".split()
)
norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()
tok = lambda s: {
    w for w in re.findall(r"[a-z0-9]+", norm(s)) if w not in STOP and len(w) > 2
}


def load_surfaces(bank_dir: Path):
    surf, st, owners = [], [], []
    for f in sorted(bank_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        ents = data if isinstance(data, list) else data["entries"]
        for e in ents:
            eid = e["id"]
            for s in [e["question"], *e.get("aliases", [])]:
                surf.append(norm(s))
                st.append(tok(s))
                owners.append(eid)
    return surf, st, owners


def main() -> int:
    bank = ROOT / "app/data/question_bank"
    # Exclude tech.agentic_platforms from collision baseline if present
    # (we're removing it); check against rest of bank only.
    surf, st, owners = [], [], []
    for f in sorted(bank.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        ents = data if isinstance(data, list) else data["entries"]
        for e in ents:
            if e["id"] == "tech.agentic_platforms":
                continue
            for s in [e["question"], *e.get("aliases", [])]:
                surf.append(norm(s))
                st.append(tok(s))
                owners.append(e["id"])

    new = [
        "What platforms can you use to build agentic AI workflows?",
        "what platforms can you use to build agentic ai workflows",
        "which frameworks can you use for agentic ai workflows",
        "platforms for building agentic ai workflows",
        "what tools do you use to build agentic workflows",
        "what is an orchestrator",
    ]
    bad = 0
    for s in new:
        n, t = norm(s), tok(s)
        hit = process.extractOne(
            n, surf, scorer=fuzz.token_sort_ratio, score_cutoff=80
        )
        sub = [i for i, e in enumerate(st) if e and t and (t == e or t <= e)]
        if hit or sub:
            bad += 1
            who = []
            if hit:
                who.append(f"fuzz={hit[1]}@{owners[surf.index(hit[0])]}:{hit[0][:60]}")
            for i in sub[:3]:
                who.append(f"subset@{owners[i]}")
            print("COLLIDES", s, "|", "; ".join(who))
        else:
            print("clear   ", s)
    print("RESULT", "FAIL" if bad else "PASS", f"collides={bad}")
    return 2 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
