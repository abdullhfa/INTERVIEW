"""
Lock (and later verify) the Final Unseen Holdout v3 pack.

    python scripts/lock_holdout_v3.py --write    # once, after synthesis
    python scripts/lock_holdout_v3.py            # verify nothing moved

Writes LOCK.json with a SHA-256 for scripts.json, gold.json, pack_meta.json,
manifest.json and every WAV. The suite refuses to run unless verification
passes, so the pack cannot be quietly edited between the decision to run it and
the run itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK_ROOT = ROOT.parent / "frontend" / "public" / "voice-drill" / "final-unseen-holdout-v3"
LOCK_PATH = PACK_ROOT / "LOCK.json"
META_FILES = ("scripts.json", "gold.json", "pack_meta.json", "manifest.json")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def digest_pack() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in META_FILES:
        p = PACK_ROOT / name
        if p.is_file():
            out[name] = _sha256(p)
    for wav in sorted((PACK_ROOT / "audio").glob("*.wav")):
        out[f"audio/{wav.name}"] = _sha256(wav)
    return out


def verify() -> tuple[bool, list[str]]:
    """(ok, problems). Used by the suite before it plays a single clip."""
    if not LOCK_PATH.is_file():
        return False, [f"pack is not locked: {LOCK_PATH} missing"]
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    expected: dict[str, str] = lock.get("files") or {}
    actual = digest_pack()
    problems: list[str] = []
    for name, digest in expected.items():
        if name not in actual:
            problems.append(f"missing since lock: {name}")
        elif actual[name] != digest:
            problems.append(f"changed since lock: {name}")
    for name in actual:
        if name not in expected:
            problems.append(f"added since lock: {name}")
    return (not problems), problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="create/replace LOCK.json")
    args = ap.parse_args()

    scripts_path = PACK_ROOT / "scripts.json"
    if not scripts_path.is_file():
        print("pack not built yet")
        return 1
    rows = json.loads(scripts_path.read_text(encoding="utf-8"))
    missing = [r["file"] for r in rows if not (PACK_ROOT / r["file"]).is_file()]

    if args.write:
        if missing:
            print(f"refusing to lock: {len(missing)} WAV(s) missing, e.g. {missing[0]}")
            return 1
        if LOCK_PATH.is_file():
            print(f"refusing to overwrite an existing lock at {LOCK_PATH}")
            print("delete it deliberately if you really mean to re-lock a new pack.")
            return 1
        files = digest_pack()
        LOCK_PATH.write_text(
            json.dumps(
                {
                    "pack": "final-unseen-holdout-v3",
                    "locked_at": datetime.now(timezone.utc).isoformat(),
                    "clips": len(rows),
                    "scored": sum(1 for r in rows if not r.get("warmup")),
                    "note": "EVAL ONLY, run once. Any change to these bytes voids the pack.",
                    "files": files,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"locked {len(files)} files -> {LOCK_PATH}")
        return 0

    if missing:
        print(f"audio incomplete: {len(missing)}/{len(rows)} missing (e.g. {missing[0]})")
        return 1
    ok, problems = verify()
    if ok:
        print("LOCK OK — pack matches its recorded digests")
        return 0
    print("LOCK VERIFICATION FAILED:")
    for p in problems:
        print("  -", p)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
