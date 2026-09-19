"""Verify bank JSON pack: answer-text-only or expected index diffs.

Usage:
  python scripts/verify_bank_pack.py --old DIR --new DIR --mode text-only
  python scripts/verify_bank_pack.py --old DIR --new DIR --mode files6
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FILES = [
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


def compare_text_only(old_dir: Path, new_dir: Path) -> int:
    ok = True
    diffs: list[str] = []
    total = 0
    en_total = fu_total = 0
    for name in FILES:
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
            diffs.append(f"{name}: ID SET differs")
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
        en_total += en_c
        fu_total += fu_c
        print(f"  {name}: n={len(new_e)} answer_en={en_c} followup_en={fu_c}")
    print(f"TOTAL={total} answer_en_entries={en_total} followup_en_entries={fu_total}")
    print("result=", "OK" if ok else "FAIL")
    for d in diffs[:40]:
        print("DIFF:", d)
    if len(diffs) > 40:
        print(f"... +{len(diffs) - 40} more")
    return 0 if ok and total == 341 else 2


def compare_files6(old_dir: Path, new_dir: Path) -> int:
    """Allow only the three documented index/answer_ar changes + new hard entry."""
    expected_extra = {"hard.bank_weekly_policies"}
    allowed_q_alias = {"tech.use_pgvector_production"}
    allowed_ar = {"tech.use_pgvector_production", "tech.explain_ai_project_structure"}
    ok = True
    diffs: list[str] = []
    total = 0
    seen_extra: set[str] = set()

    for name in FILES:
        old_e = load(old_dir / name)
        new_e = load(new_dir / name)
        total += len(new_e)
        old_by = {e["id"]: e for e in old_e}
        new_by = {e["id"]: e for e in new_e}
        extra = set(new_by) - set(old_by)
        missing = set(old_by) - set(new_by)
        if missing:
            ok = False
            diffs.append(f"{name}: missing ids {sorted(missing)[:5]}")
        for eid in extra:
            if eid not in expected_extra:
                ok = False
                diffs.append(f"{name}: unexpected EXTRA id {eid}")
            else:
                seen_extra.add(eid)
                print(f"  EXTRA ok: {eid}")

        if name == "hard_scenarios.json":
            if len(old_e) != 63 or len(new_e) != 64:
                ok = False
                diffs.append(
                    f"hard_scenarios count old={len(old_e)} new={len(new_e)} (want 63->64)"
                )

        shared = set(old_by) & set(new_by)
        for eid in shared:
            o, n = old_by[eid], new_by[eid]
            for k in INDEX_KEYS:
                ov, nv = o.get(k), n.get(k)
                if k in ("aliases", "keywords"):
                    ov, nv = norm_list(ov), norm_list(nv)
                if ov != nv:
                    if eid in allowed_q_alias and k in ("question", "aliases"):
                        print(f"  ALLOWED index change {eid}.{k}")
                    else:
                        ok = False
                        diffs.append(f"{name}:{eid}: FIELD {k} CHANGED")
            if o.get("answer_ar") != n.get("answer_ar"):
                if eid in allowed_ar:
                    print(f"  ALLOWED answer_ar change {eid}")
                else:
                    ok = False
                    diffs.append(f"{name}:{eid}: answer_ar CHANGED")
            if o.get("followup_ar") != n.get("followup_ar"):
                # not in the allowed list for files6 prompt
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

        print(f"  {name}: old={len(old_e)} new={len(new_e)}")

    if seen_extra != expected_extra:
        ok = False
        diffs.append(f"extra set mismatch got={sorted(seen_extra)} want={sorted(expected_extra)}")

    print(f"TOTAL={total}")
    print("result=", "OK" if ok else "FAIL")
    for d in diffs[:40]:
        print("DIFF:", d)
    if len(diffs) > 40:
        print(f"... +{len(diffs) - 40} more")
    return 0 if ok and total == 342 else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--mode", choices=("text-only", "files6"), required=True)
    args = ap.parse_args()
    old_dir = Path(args.old)
    new_dir = Path(args.new)
    if args.mode == "text-only":
        return compare_text_only(old_dir, new_dir)
    return compare_files6(old_dir, new_dir)


if __name__ == "__main__":
    raise SystemExit(main())
