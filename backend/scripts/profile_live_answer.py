"""Per-stage latency profile of the live answer path (measurement only).

Runs exactly what the WebSocket path runs — question_classifier.classify(
prefer_speed=True) then answer_generator.generate(prefer_speed=True) — without
audio, Whisper or the browser, and prints where the milliseconds actually go.

    cd backend
    python scripts\\profile_live_answer.py
    python scripts\\profile_live_answer.py "What is RAG?" "Tell me about yourself."

No app/ file is imported for writing; nothing is changed.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.candidate import AnswerLanguageMode, AnswerLengthMode  # noqa: E402
from app.db.repository import repository  # noqa: E402
from app.services.answer_generator import answer_generator  # noqa: E402
from app.services.candidate_profile import candidate_profile_service  # noqa: E402
from app.services.question_bank import embed_stats, question_bank  # noqa: E402
from app.services.question_classifier import question_classifier  # noqa: E402

DEFAULT_QUESTIONS = [
    "What is RAG?",
    "Tell me about yourself.",
    "Explain your project.",
    "How do you prevent overfitting?",
]


def _embed_stats() -> dict:
    try:
        return dict(embed_stats())
    except Exception:
        return {}


def _print_embed_stats(label: str) -> None:
    stats = _embed_stats()
    calls = float(stats.get("calls", 0) or 0)
    texts = float(stats.get("texts", 0) or 0)
    ms = float(stats.get("ms", 0.0) or 0.0)
    print(
        f"{label}: calls={calls:.0f} texts={texts:.0f} total={ms:.0f} ms | "
        f"ms_per_call={(ms / calls if calls else 0):.0f} | "
        f"**ms_per_text={(ms / texts if texts else 0):.1f}** | "
        f"max_call={stats.get('max_ms')}"
    )


def profile_whisper() -> None:
    """Time the real Whisper decode on dev-pack audio (never a holdout pack)."""
    import glob
    import wave

    import numpy as np

    from app.audio import whisper_stt

    clips = sorted(
        glob.glob(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "frontend", "public", "voice-drill", "compound-dev", "audio", "*.wav",
            )
        )
    )[:3]
    if not clips:
        print("no compound-dev audio found — skipping Whisper timing")
        return

    print("\n--- Whisper ---")
    for path in clips:
        with wave.open(path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            rate = wf.getframerate()
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        t0 = time.perf_counter()
        text = whisper_stt.transcribe_whisper(audio, rate)
        ms = (time.perf_counter() - t0) * 1000
        secs = len(audio) / float(rate)
        print(
            f"  {os.path.basename(path)}: {ms:.0f} ms for {secs:.1f}s audio "
            f"(rtf {ms / 1000.0 / secs:.2f}) -> {text[:60]!r}"
        )
    print(f"  active model: {whisper_stt.active_stt_info()}")


def profile_bank_stages(questions: list[str]) -> None:
    """Split the ~0.4-1.2 s bank lookup into its three real stages."""
    from app.services.main_request_extraction import match_with_main_request
    from app.services.semantic_intent_recovery import recover_semantic_intent

    print("\n--- bank lookup stages (ms) ---")
    print(f"{'match':>8} {'match#2':>8} {'MRE':>8} {'semantic':>9}   question")
    for q in questions:
        t0 = time.perf_counter()
        m1 = question_bank.match(q)
        ms_match = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        question_bank.match(q)  # second identical call — shows memo effectiveness
        ms_match2 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        m2, _ext, _meta = match_with_main_request(q, conversation_history=[])
        ms_mre = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        try:
            recover_semantic_intent(q, m2, conversation_history=[])
        except Exception as exc:
            print(f"  semantic recovery failed: {exc}")
        ms_sem = (time.perf_counter() - t0) * 1000

        print(
            f"{ms_match:>8.0f} {ms_match2:>8.0f} {ms_mre:>8.0f} {ms_sem:>9.0f}   {q}"
            + ("" if m1 is None else f"  [{m1.entry.id} {m1.mode} {m1.score:.2f}]")
        )
    print(
        "  match   = question_bank.match (the call hidden inside _transcribe_interviewer)\n"
        "  match#2 = same call again (large drop = memoized; no drop = recomputed every time)\n"
        "  MRE + semantic = the extra stages answer_generator._match_question_bank adds"
    )


async def profile_one(question: str, profile) -> dict:
    first_partial_ms: list[float] = []
    t_start = time.perf_counter()

    async def on_partial(_text: str) -> None:
        if not first_partial_ms:
            first_partial_ms.append((time.perf_counter() - t_start) * 1000)

    t0 = time.perf_counter()
    classification = await question_classifier.classify(
        question, conversation_history=[], prefer_speed=True
    )
    classify_ms = (time.perf_counter() - t0) * 1000
    action = question_classifier.determine_action(classification)

    embed_before = _embed_stats()

    t0 = time.perf_counter()
    generated = await answer_generator.generate(
        classification=classification,
        profile=profile,
        conversation_history=[],
        question_id="profile-run",
        length_mode=AnswerLengthMode.QUICK,
        language_mode=AnswerLanguageMode.SHOW_ARABIC_AND_ENGLISH,
        prefer_speed=True,
        on_partial=on_partial,
    )
    generate_ms = (time.perf_counter() - t0) * 1000
    embed_after = _embed_stats()

    return {
        "question": question,
        "action": action.value,
        "classify_ms": round(classify_ms, 1),
        "bank_lookup_ms": round(getattr(answer_generator, "_last_bank_lookup_ms", 0.0) or 0.0, 1),
        "answer_source": getattr(answer_generator, "_last_answer_source", "?"),
        "first_visible_ms": round(first_partial_ms[0], 1) if first_partial_ms else None,
        "generate_ms": round(generate_ms, 1),
        "total_ms": round(classify_ms + generate_ms, 1),
        "embed_calls": embed_after.get("calls", 0) - embed_before.get("calls", 0),
        "embed_ms": round(
            float(embed_after.get("ms", 0.0)) - float(embed_before.get("ms", 0.0)), 1
        ),
        "answer_chars": len((generated.answer_en or "").strip()),
    }


async def main() -> int:
    questions = sys.argv[1:] or DEFAULT_QUESTIONS

    loaded = await repository.load_all_profiles()
    if loaded:
        candidate_profile_service._profiles = loaded
    profiles = candidate_profile_service.list_profiles()
    if not profiles:
        print("No candidate profile found — create one in the UI first.")
        return 2
    profile = profiles[0]
    print(f"profile: {getattr(profile, 'id', '?')}")

    t0 = time.perf_counter()
    question_bank.warm()
    print(f"question_bank.warm(): {(time.perf_counter() - t0) * 1000:.0f} ms")
    _print_embed_stats("embed after warm")

    profile_whisper()
    profile_bank_stages(questions)
    print()
    _print_embed_stats("embed before live questions")
    print()

    rows = []
    for q in questions:
        row = await profile_one(q, profile)
        rows.append(row)
        print(
            f"{row['total_ms']:>8.0f} ms total | first visible "
            f"{row['first_visible_ms'] if row['first_visible_ms'] is not None else 'NEVER':>8} ms | "
            f"classify {row['classify_ms']:.0f} | bank {row['bank_lookup_ms']:.0f} | "
            f"gen {row['generate_ms']:.0f} | src {row['answer_source']} | "
            f"embeds {row['embed_calls']} ({row['embed_ms']:.0f} ms) | {row['question']}"
        )

    print("\n--- verdict ---")
    for row in rows:
        if row["first_visible_ms"] is None and row["answer_source"] != "bank":
            print(f"  {row['question']!r}: NO streamed text — the 5 s stream cap fired.")
        elif row["answer_source"] == "bank":
            print(f"  {row['question']!r}: answered from the prepared bank ({row['total_ms']:.0f} ms).")
        else:
            print(
                f"  {row['question']!r}: LLM answer, first text at "
                f"{row['first_visible_ms']:.0f} ms of {row['total_ms']:.0f} ms."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
