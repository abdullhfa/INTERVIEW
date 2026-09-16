"""Synthesize 4 simple single-intent generalization-dev clips for L4 re-measure."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_synth_module() -> ModuleType:
    """Load repo-root scripts/synthesize_generalization_dev.py by path (not a package)."""
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "synthesize_generalization_dev.py"
    spec = importlib.util.spec_from_file_location("synthesize_generalization_dev", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load synthesizer from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_synth = _load_synth_module()
PACK = _synth.PACK
SCRIPTS = _synth.SCRIPTS
synthesize_one = _synth.synthesize_one


async def main() -> int:
    rows = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    simple = [
        r
        for r in rows
        if len(r.get("expected_intent_ids") or []) == 1
        and r.get("question_type") in ("ultra_short", "short", "medium")
        and "," not in (r.get("transcript") or "")
        and " and " not in (r.get("transcript") or "").lower()
        and " then " not in (r.get("transcript") or "").lower()
        and ":" not in (r.get("transcript") or "")
    ]
    # Prefer ultra_short/short first.
    simple.sort(key=lambda r: (0 if r.get("question_type") == "ultra_short" else 1, r["id"]))
    chosen = simple[:4]
    if len(chosen) < 4:
        # Fallback: any single-intent.
        simple = [r for r in rows if len(r.get("expected_intent_ids") or []) == 1]
        chosen = simple[:4]
    print("chosen:")
    for r in chosen:
        print(f"  {r['id']}: {r['transcript'][:80]}")
    sem = asyncio.Semaphore(2)
    await asyncio.gather(
        *[synthesize_one(r, sem, i, len(chosen)) for i, r in enumerate(chosen, start=1)]
    )
    out = PACK / "_l4_simple_clips.json"
    out.write_text(json.dumps([r["file"] for r in chosen], indent=2), encoding="utf-8")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
