"""Live typed utterance: platforms question → capture ANSWER_READY lengths."""
from __future__ import annotations

import asyncio
import json
import time

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws/interview/{session_id}"
Q = "What platforms can you use to build Agentic AI workflows?"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=60.0) as client:
        warm = (await client.get("/api/health/warm")).json()
        print("SYSTEM_WARM=", warm.get("system_warm"), flush=True)
        if not warm.get("system_warm"):
            print("ABORT: not warm")
            return 3
        profiles = (await client.get("/api/candidates/profiles")).json()
        session = (
            await client.post(
                "/api/interviews/sessions",
                json={
                    "candidate_id": profiles[0]["id"],
                    "mode": "COACHING",
                    "meeting_platform": "Zoom",
                },
            )
        ).json()
        session_id = session["id"]
        print("session=", session_id, flush=True)

    async with websockets.connect(WS.format(session_id=session_id), max_size=8_000_000) as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print("ws:", hello.get("type"), flush=True)
        await ws.send(
            json.dumps(
                {
                    "type": "config",
                    "data": {
                        "mic_device_index": None,
                        "loopback_device_index": None,
                        "length_mode": "QUICK",
                        "language_mode": "ALWAYS_ENGLISH",
                    },
                }
            )
        )
        await ws.send(json.dumps({"type": "start"}))
        # Typed path does not need capture; still drain a few events
        await asyncio.sleep(0.5)
        print("SEND utterance:", Q, flush=True)
        await ws.send(
            json.dumps(
                {
                    "type": "utterance",
                    "data": {
                        "text": Q,
                        "length_mode": "QUICK",
                        "language_mode": "ALWAYS_ENGLISH",
                    },
                }
            )
        )

        deadline = time.perf_counter() + 60
        while time.perf_counter() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            msg = json.loads(raw)
            t = msg.get("type")
            if t in (
                "classification",
                "QUESTION_ACCEPTED",
                "QUESTION_DETECTED",
                "ANSWER_GENERATING",
                "ANSWER_READY",
                "ANSWER_PARTIAL",
                "error",
            ):
                print("evt:", t, flush=True)
            if t == "ANSWER_READY":
                data = msg.get("data") or msg.get("answer") or msg
                # shape may nest
                ans = data.get("answer") if isinstance(data, dict) and "answer" in data else data
                if not isinstance(ans, dict):
                    ans = msg
                en = (
                    ans.get("answer_en")
                    or (ans.get("data") or {}).get("answer_en")
                    or ""
                )
                ar = (
                    ans.get("answer_ar")
                    or (ans.get("data") or {}).get("answer_ar")
                    or ""
                )
                q = (
                    ans.get("question")
                    or (ans.get("data") or {}).get("question")
                    or ""
                )
                # dump keys for debug if empty
                if not en:
                    print("RAW_KEYS", list(msg.keys()), flush=True)
                    print("RAW_MSG", json.dumps(msg, ensure_ascii=False)[:800], flush=True)
                print("displayed_question=", repr(q), flush=True)
                print("answer_en_len=", len(en), flush=True)
                print("answer_ar_len=", len(ar), flush=True)
                print("answer_en=", en, flush=True)
                print("answer_ar=", ar, flush=True)
                await ws.send(json.dumps({"type": "end"}))
                return 0 if len(en) > 200 else 2
            if t == "error":
                print("FATAL", msg, flush=True)
                return 4
        print("TIMEOUT")
        return 5


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
