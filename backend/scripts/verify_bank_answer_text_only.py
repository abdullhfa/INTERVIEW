"""Verify files4 staging is answer_en/followup_en only vs backups."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
backup = ROOT / "app/data/question_bank_V6_5_backup"
staging = ROOT / "app/data/_files4_staging"
orig = ROOT / "app/data/question_bank_V6_5_original_backup"
files = [
    "cv_abdullah.json",
    "general_personal.json",
    "hard_scenarios.json",
    "technical_ai_senior.json",
]
INDEX_KEYS = ("id", "question", "aliases", "keywords")


def load(p: Path):
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "entries" in data:
        return data["entries"]
    if isinstance(data, list):
        return data
    raise SystemExit(f"unexpected shape: {p}")


def norm_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def compare(old_dir: Path, new_dir: Path) -> tuple[bool, int]:
    ok = True
    diffs: list[str] = []
    total = 0
    for name in files:
        print(f"  checking {name}", flush=True)
        old_e = load(old_dir / name)
        new_e = load(new_dir / name)
        total += len(new_e)
        if len(old_e) != len(new_e):
            ok = False
            diffs.append(f"{name}: ENTRY COUNT old={len(old_e)} new={len(new_e)}")
            continue
        old_by = {e["id"]: e for e in old_e}
        new_by = {e["id"]: e for e in new_e}
        if set(old_by) != set(new_by):
            ok = False
            miss = sorted(set(old_by) - set(new_by))[:5]
            extra = sorted(set(new_by) - set(old_by))[:5]
            diffs.append(f"{name}: ID SET differs miss={miss} extra={extra}")
            continue
        en_c = fu_c = 0
        for eid in old_by:
            o, n = old_by[eid], new_by[eid]
            for k in INDEX_KEYS:
                ov, nv = o.get(k), n.get(k)
                if k in ("aliases", "keywords"):
                    ov, nv = norm_list(ov), norm_list(nv)
                if ov != nv:
                    ok = False
                    diffs.append(f"{name}:{eid}: FIELD {k} CHANGED")
            if o.get("answer_ar") != n.get("answer_ar"):
                ok = False
                diffs.append(f"{name}:{eid}: answer_ar CHANGED")
            if o.get("followup_ar") != n.get("followup_ar"):
                ok = False
                diffs.append(f"{name}:{eid}: followup_ar CHANGED")
            for k in set(o) | set(n):
                if k in INDEX_KEYS or k in (
                    "answer_ar",
                    "answer_en",
                    "followup_en",
                    "followup_ar",
                ):
                    continue
                if o.get(k) != n.get(k):
                    ok = False
                    diffs.append(f"{name}:{eid}: OTHER FIELD {k} CHANGED")
            if o.get("answer_en") != n.get("answer_en"):
                en_c += 1
            if o.get("followup_en") != n.get("followup_en"):
                fu_c += 1
        print(
            f"  {name}: n={len(new_e)} answer_en={en_c} followup_en={fu_c}",
            flush=True,
        )
    status = "OK" if ok else "FAIL"
    print(f"  TOTAL={total} result={status}", flush=True)
    for d in diffs[:50]:
        print(f"  DIFF: {d}")
    if len(diffs) > 50:
        print(f"  ... +{len(diffs) - 50} more")
    return ok, total


def main() -> int:
    print("=== vs current backup (pre-files4) ===")
    ok1, _ = compare(backup, staging)
    print("=== vs original V6.5 backup ===")
    ok2, _ = compare(orig, staging)
    print("GATE_STEP3", "PASS" if ok1 else "FAIL")
    print("GATE_INDEX_VS_V65", "PASS" if ok2 else "FAIL")
    return 0 if (ok1 and ok2) else 2


if __name__ == "__main__":
    raise SystemExit(main())
