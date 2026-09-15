"""
Voice spot-check for Final Unseen Holdout v3 — run BEFORE synthesizing the pack.

Purpose: prove that the TTS itself can pronounce the domain vocabulary, so that a
v3 failure is a system failure and not a synthesis artefact.

IMPORTANT — this deliberately does NOT touch v3 clips. Transcribing pack audio
would reveal v3 outcomes before the run and contaminate the holdout. Instead it
synthesizes a handful of throwaway PROBE SENTENCES that carry the same technical
terms, and checks whether those terms survive TTS -> Whisper.

    python scripts/spotcheck_holdout_v3_voices.py
    python scripts/spotcheck_holdout_v3_voices.py --voices multilingual
    python scripts/spotcheck_holdout_v3_voices.py --voices proxy multilingual   # compare

Output: reports/HOLDOUT_V3_VOICE_SPOTCHECK.{md,json}
Scratch audio: reports/_v3_voice_spotcheck/ (safe to delete; never part of the pack)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT_DIR = ROOT / "reports" / "_v3_voice_spotcheck"
PACK_ROOT = ROOT.parent / "frontend" / "public" / "voice-drill" / "final-unseen-holdout-v3"

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_v3_synth", Path(__file__).with_name("synthesize_final_unseen_holdout_v3.py")
)
_synth = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_synth)  # type: ignore[union-attr]

# Throwaway probes. Declarative sentences, never interview questions, so they
# cannot resemble anything in v3 or any earlier pack.
PROBES: list[tuple[str, list[str]]] = [
    ("The RAG layer and the embeddings index both sit behind the same guardrails.",
     ["RAG", "embeddings", "guardrails"]),
    ("LangGraph checkpoints, ChromaDB collections and Whisper transcripts are logged together.",
     ["LangGraph", "ChromaDB", "Whisper"]),
    ("Agentic orchestration, cosine similarity and re-ranking all appear in this sentence.",
     ["agentic", "cosine", "re-ranking"]),
    ("Pydantic validates the FastAPI payload before the model sees any token.",
     ["Pydantic", "FastAPI", "token"]),
    ("Fine-tuning, LoRA adapters and hallucination checks belong to different layers.",
     ["fine-tuning", "LoRA", "hallucination"]),
    ("TF-IDF, hybrid search and metadata filtering are three distinct retrieval tricks.",
     ["TF-IDF", "hybrid search", "metadata"]),
]

CONDITIONS = ("clean", "poor")   # best case + the harshest realistic channel


def _assert_probes_are_not_pack_text() -> None:
    scripts_path = PACK_ROOT / "scripts.json"
    if not scripts_path.is_file():
        return
    pack = {r["transcript"].strip().casefold()
            for r in json.loads(scripts_path.read_text(encoding="utf-8"))}
    clash = [p for p, _ in PROBES if p.strip().casefold() in pack]
    if clash:
        raise SystemExit(f"probe sentence is also a pack clip — change it: {clash}")


async def _tts(text: str, voice: str, out_mp3: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice).save(str(out_mp3))


def _term_survived(term: str, transcript: str) -> bool:
    """Match the way the pipeline does: normalized, so spelling variants count."""
    from app.services.domain_terms import normalize_for_matching
    from app.services.technical_term_repair import repair_technical_terms

    hay = normalize_for_matching(repair_technical_terms(transcript))
    return normalize_for_matching(term) in hay


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voices", nargs="+", choices=sorted(_synth.VOICE_SETS), default=["proxy"])
    ap.add_argument("--conditions", nargs="+", default=list(CONDITIONS))
    args = ap.parse_args()

    _assert_probes_are_not_pack_text()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    from app.audio.whisper_stt import transcribe_whisper
    from app.services.warm_start import warm_system_blocking

    warm_system_blocking()

    rows: list[dict] = []
    for voice_set in args.voices:
        voices = _synth.VOICE_SETS[voice_set]
        for accent, (female, male) in voices.items():
            for i, (probe, terms) in enumerate(PROBES):
                voice = female if i % 2 == 0 else male
                for condition in args.conditions:
                    tag = f"{voice_set}_{accent}_{condition}_{i:02d}"
                    wav = OUT_DIR / f"{tag}.wav"
                    with tempfile.TemporaryDirectory() as tmp:
                        mp3 = Path(tmp) / "p.mp3"
                        asyncio.run(_tts(probe, voice, mp3))
                        raw = _synth._decode_to_mono16k(mp3)
                    audio = _synth.apply_condition(
                        _synth._pad(raw), condition, abs(hash(tag)) % (2**32)
                    )
                    _synth._write_wav(wav, audio)
                    text = transcribe_whisper(np.asarray(audio, dtype=np.float32), _synth.SR) or ""
                    found = {t: _term_survived(t, text) for t in terms}
                    rows.append(
                        {
                            "voice_set": voice_set,
                            "accent": accent,
                            "accent_kind": "native_locale" if accent == "en-IN" else "synthetic_proxy",
                            "condition": condition,
                            "voice": voice,
                            "probe": probe,
                            "transcript": text.strip(),
                            "terms": found,
                            "terms_ok": sum(1 for v in found.values() if v),
                            "terms_total": len(found),
                        }
                    )
                    print(
                        f"  {tag:38s} {sum(found.values())}/{len(found)}  {text.strip()[:70]}"
                    )

    summary: dict[str, dict] = {}
    for r in rows:
        key = f"{r['voice_set']}/{r['accent']}"
        acc = summary.setdefault(key, {"ok": 0, "total": 0, "clips": 0, "missed": []})
        acc["ok"] += r["terms_ok"]
        acc["total"] += r["terms_total"]
        acc["clips"] += 1
        acc["missed"].extend(t for t, v in r["terms"].items() if not v)
    for acc in summary.values():
        acc["rate"] = round(acc["ok"] / max(1, acc["total"]), 3)
        acc["missed"] = sorted(set(acc["missed"]))

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "validate TTS pronunciation of domain terms before v3 synthesis",
        "note": "probe sentences only — no v3 clip was synthesized or transcribed",
        "voice_sets": args.voices,
        "conditions": args.conditions,
        "summary": summary,
        "rows": rows,
    }
    (ROOT / "reports" / "HOLDOUT_V3_VOICE_SPOTCHECK.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        "# Holdout v3 — voice spot-check",
        "",
        f"Created: {payload['created_at']}",
        "",
        "Probe sentences only. No v3 clip was synthesized or transcribed, so the",
        "holdout stays unseen.",
        "",
        "| voice set / profile | kind | clips | terms kept | rate | missed |",
        "|---|---|---|---|---|---|",
    ]
    for key in sorted(summary):
        a = summary[key]
        kind = "native" if key.endswith("en-IN") else "synthetic proxy"
        md.append(
            f"| {key} | {kind} | {a['clips']} | {a['ok']}/{a['total']} | {a['rate']} | "
            f"{', '.join(a['missed']) or '—'} |"
        )
    md += [
        "",
        "## Reading this",
        "",
        "- A low rate for a profile means the TTS mangles the vocabulary, so a v3",
        "  failure on that profile would not be the system's fault. Switch voice",
        "  set (`--voices multilingual`) or drop the profile BEFORE synthesis.",
        "- `proxy-ar-*` are Arabic-locale voices reading English. They are labelled",
        "  synthetic proxies everywhere and must never be reported as real dialects.",
        "",
        "## Transcripts",
        "",
    ]
    for r in rows:
        md.append(
            f"- `{r['voice_set']}/{r['accent']}/{r['condition']}` ({r['voice']}): "
            f"**{r['terms_ok']}/{r['terms_total']}** — {r['transcript'] or '(empty)'}"
        )
    (ROOT / "reports" / "HOLDOUT_V3_VOICE_SPOTCHECK.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8"
    )
    print("\nwrote reports/HOLDOUT_V3_VOICE_SPOTCHECK.md")
    worst = min((a["rate"] for a in summary.values()), default=1.0)
    print(f"worst profile term-retention rate: {worst}")
    return 0 if worst >= 0.80 else 2


if __name__ == "__main__":
    raise SystemExit(main())
