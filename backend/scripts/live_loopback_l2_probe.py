"""Drive a real live loopback session with compound-dev WAVs (measurement only)."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws/interview/{session_id}"
AUDIO_DIR = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "public"
    / "voice-drill"
    / "generalization-dev"
    / "audio"
)
# Simple single-intent clips (not compound-dev).
CLIPS = [AUDIO_DIR / f"gdev_01{i}.wav" for i in (3, 4, 5, 6)]


async def main() -> int:
    for p in CLIPS:
        if not p.is_file():
            print(f"missing clip: {p}")
            return 2

    async with httpx.AsyncClient(base_url=BASE, timeout=60.0) as client:
        warm = (await client.get("/api/health/warm")).json()
        print("SYSTEM_WARM=", warm.get("system_warm"), "whisper_probe=", (warm.get("steps") or {}).get("whisper_decode_probe"))
        if not warm.get("system_warm"):
            print("ABORT: system not warm yet")
            return 3

        profiles = (await client.get("/api/candidates/profiles")).json()
        candidate_id = profiles[0]["id"]
        session = (
            await client.post(
                "/api/interviews/sessions",
                json={
                    "candidate_id": candidate_id,
                    "mode": "COACHING",
                    "meeting_platform": "Zoom",
                },
            )
        ).json()
        if "id" not in session:
            print("session create failed:", session)
            return 6
        session_id = session["id"]
        print("session=", session_id)

    answers = 0
    events: list[str] = []

    async with websockets.connect(WS.format(session_id=session_id), max_size=8_000_000) as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print("ws:", hello.get("type"))

        await ws.send(json.dumps({
            "type": "config",
            "data": {
                "mic_device_index": None,
                "loopback_device_index": None,
                "length_mode": "QUICK",
                "language_mode": "ALWAYS_ENGLISH",
            },
        }))
        await ws.send(json.dumps({"type": "start"}))

        # Drain until capture ready (or error).
        ready = False
        deadline = time.perf_counter() + 30
        while time.perf_counter() < deadline and not ready:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            msg = json.loads(raw)
            events.append(msg.get("type", "?"))
            print("evt:", msg.get("type"), (msg.get("message") or "")[:80])
            if msg.get("type") in ("AUDIO_CAPTURE_READY", "AUDIO_STREAM_ACTIVE"):
                ready = True
            if msg.get("type") == "error":
                print("FATAL", msg)
                return 4

        print("playing clips via default speakers (winsound)...")

        async def wait_answer(timeout: float = 40.0) -> bool:
            deadline = time.perf_counter() + timeout
            while time.perf_counter() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.perf_counter()))
                except asyncio.TimeoutError:
                    return False
                msg = json.loads(raw)
                t = msg.get("type", "?")
                events.append(t)
                if t in ("ANSWER_READY", "ANSWER_PARTIAL", "QUESTION_ACCEPTED", "STT_RETRYING", "NON_QUESTION_IGNORED"):
                    print("evt:", t)
                if t == "ANSWER_READY":
                    return True
                if t in ("NON_QUESTION_IGNORED", "QUESTION_IGNORED"):
                    return False
            return False

        def play_blocking(path: Path) -> None:
            import winsound
            print(f"PLAY {path.name}")
            winsound.PlaySound(str(path), winsound.SND_FILENAME)

        answers = 0
        for clip in CLIPS:
            await asyncio.to_thread(play_blocking, clip)
            ok = await wait_answer(45.0)
            if ok:
                answers += 1
            await asyncio.sleep(2.0)

        await ws.send(json.dumps({"type": "end"}))

    print(f"ANSWER_READY count={answers}")
    print("event_types=", sorted(set(events)))
    return 0 if answers >= 1 else 5


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
