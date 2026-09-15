"""Synthesize Generalization Dev Track C WAVs from scripts.json.

Does NOT modify the frozen interview system.
Output: mono 16 kHz PCM WAV under generalization-dev/audio/
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "frontend" / "public" / "voice-drill" / "generalization-dev"
SCRIPTS = PACK / "scripts.json"
AUDIO = PACK / "audio"
FFMPEG = "ffmpeg"

VOICE_BY_ACCENT = {
    "indian": "en-IN-PrabhatNeural",
    "jordanian": "en-US-ChristopherNeural",
    "egyptian": "en-GB-ThomasNeural",
    "emirati": "en-AU-WilliamMultilingualNeural",
}

RATE_BY_CONDITION = {
    "clean": "+0%",
    "office": "+0%",
    "poor": "-5%",
    "far": "-8%",
    "fast": "+28%",
}


def _ffmpeg_condition_filter(condition: str) -> list[str]:
    if condition == "clean":
        af = "aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono"
    elif condition == "fast":
        af = "aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono"
    elif condition == "office":
        return [
            "-y",
            "-i",
            "{inp}",
            "-f",
            "lavfi",
            "-i",
            "anoisesrc=color=pink:amplitude=0.025:sample_rate=48000",
            "-filter_complex",
            "[0:a]aresample=16000,aformat=channel_layouts=mono,volume=1.0[a0];"
            "[1:a]aresample=16000,aformat=channel_layouts=mono,volume=0.22[n];"
            "[a0][n]amix=inputs=2:duration=first:dropout_transition=0,"
            "aformat=sample_fmts=s16:channel_layouts=mono",
            "{out}",
        ]
    elif condition == "poor":
        af = (
            "aresample=16000,highpass=f=300,lowpass=f=3400,volume=0.75,"
            "aformat=sample_fmts=s16:channel_layouts=mono"
        )
    elif condition == "far":
        af = (
            "aresample=16000,volume=0.32,aecho=0.8:0.9:40|80:0.25|0.15,"
            "lowpass=f=4500,aformat=sample_fmts=s16:channel_layouts=mono"
        )
    else:
        af = "aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono"
    return ["-y", "-i", "{inp}", "-af", af, "{out}"]


async def _tts_mp3(text: str, voice: str, rate: str, mp3_path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(mp3_path))


def _run_ffmpeg(template: list[str], inp: Path, out: Path) -> None:
    cmd = [FFMPEG]
    for part in template:
        if part == "{inp}":
            cmd.append(str(inp))
        elif part == "{out}":
            cmd.append(str(out))
        else:
            cmd.append(part)
    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def synthesize_one(row: dict, sem: asyncio.Semaphore, idx: int, total: int) -> None:
    async with sem:
        out = PACK / str(row["file"])
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.is_file() and out.stat().st_size > 1000:
            print(f"[{idx}/{total}] skip existing {out.name}", flush=True)
            return
        accent = str(row.get("accent") or "indian")
        condition = str(row.get("condition") or "clean")
        voice = VOICE_BY_ACCENT.get(accent, VOICE_BY_ACCENT["indian"])
        rate = RATE_BY_CONDITION.get(condition, "+0%")
        text = str(row.get("transcript") or "").strip()
        if not text:
            raise ValueError(f"empty transcript for {row.get('id')}")
        with tempfile.TemporaryDirectory() as td:
            mp3 = Path(td) / "t.mp3"
            await _tts_mp3(text, voice, rate, mp3)
            tmpl = _ffmpeg_condition_filter(condition)
            _run_ffmpeg(tmpl, mp3, out)
        print(
            f"[{idx}/{total}] {out.name} accent={accent} cond={condition} voice={voice}",
            flush=True,
        )


async def main() -> None:
    rows = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    AUDIO.mkdir(parents=True, exist_ok=True)
    total = len(rows)
    sem = asyncio.Semaphore(4)
    await asyncio.gather(
        *[synthesize_one(row, sem, i, total) for i, row in enumerate(rows, start=1)]
    )
    missing = [r["file"] for r in rows if not (PACK / r["file"]).is_file()]
    print(f"Done. missing={len(missing)} / {total}", flush=True)
    if missing:
        raise SystemExit(1)
    meta_path = PACK / "pack_meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["audio_status"] = "synthesized"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
