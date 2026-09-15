"""Generate clean TTS interview clips for noisy/distant voice drills."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import edge_tts

OUT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public" / "voice-drill" / "clips"
VOICE = "en-US-GuyNeural"

CLIPS = [
    {
        "id": "q01_intro",
        "condition_hint": "clean",
        "text": "Please introduce yourself briefly, and tell me about the AI work you are doing now.",
    },
    {
        "id": "q02_rag",
        "condition_hint": "noise",
        "text": "What is RAG, and why did you use it for BTEC questions?",
    },
    {
        "id": "q03_similarity",
        "condition_hint": "distant",
        "text": "Is the similarity checker a RAG system? Why or why not?",
    },
    {
        "id": "q04_agentic",
        "condition_hint": "muffled",
        "text": "What is Agentic AI, and which of your projects used it?",
    },
    {
        "id": "q05_langgraph",
        "condition_hint": "noise",
        "text": "Have you used LangGraph in production? What did you use instead?",
    },
    {
        "id": "q06_recall",
        "condition_hint": "distant",
        "text": "Why did you use Recall, not Accuracy, in the early-warning project?",
    },
    {
        "id": "q07_whisper",
        "condition_hint": "muffled",
        "text": "How does Whisper fit in your kiosk project? Did you use an LLM there?",
    },
    {
        "id": "q08_school",
        "condition_hint": "noise",
        "text": "How do you stop School A from seeing School B documents in search?",
    },
]


async def synthesize(text: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(out_path))


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, clip in enumerate(CLIPS, start=1):
        filename = f"{clip['id']}.mp3"
        out_path = OUT_DIR / filename
        print(f"[{i}/{len(CLIPS)}] {filename}")
        await synthesize(clip["text"], out_path)
        manifest.append(
            {
                "id": clip["id"],
                "file": f"clips/{filename}",
                "text": clip["text"],
                "suggested_effect": clip["condition_hint"],
            }
        )
    (OUT_DIR.parent / "manifest.json").write_text(
        json.dumps({"voice": VOICE, "clips": manifest}, indent=2),
        encoding="utf-8",
    )
    print(f"Done: {len(manifest)} clips -> {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
