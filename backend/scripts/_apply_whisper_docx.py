"""One-shot: adopt Whisper.docx into technical_ai_senior (answers + new entries)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "app" / "data" / "question_bank" / "technical_ai_senior.json"
BAK = ROOT / "app" / "data" / "question_bank_pre_whisper_docx"

path = BANK
BAK.mkdir(exist_ok=True)
shutil.copy2(path, BAK / "technical_ai_senior.json")

raw = json.loads(path.read_text(encoding="utf-8"))
entries = raw["entries"]
by = {e["id"]: e for e in entries}


def upd(
    eid: str,
    answer_en: str,
    answer_ar: str,
    followup_en: str | None = None,
    aliases_extra: list[str] | None = None,
) -> None:
    e = by[eid]
    e["answer_en"] = answer_en
    e["answer_ar"] = answer_ar
    if followup_en is not None:
        e["followup_en"] = followup_en
    if aliases_extra:
        aliases = list(e.get("aliases") or [])
        for a in aliases_extra:
            if a not in aliases:
                aliases.insert(0, a)
        e["aliases"] = aliases
    print("UPD", eid)


NEWS: list[dict] = []


def add(
    eid: str,
    question: str,
    aliases: list[str],
    keywords: list[str],
    answer_en: str,
    answer_ar: str,
    *,
    topic: str = "whisper",
    followup_en: str = "",
    category: str = "technical.speech",
) -> None:
    if eid in by:
        print("SKIP", eid)
        return
    NEWS.append(
        {
            "id": eid,
            "category": category,
            "topic": topic,
            "question": question,
            "aliases": aliases,
            "keywords": keywords,
            "answer_en": answer_en,
            "followup_en": followup_en or answer_en,
            "listen_for": keywords[:6],
            "answer_ar": answer_ar,
        }
    )
    print("ADD", eid)


# --- Updates ---
upd(
    "tech.what_is_whisper",
    "Whisper is a speech recognition model that converts audio into text.",
    "Whisper نموذج تعرّف على الكلام يحوّل الصوت إلى نص.",
    aliases_extra=["what is whisper", "explain whisper", "what does whisper do"],
)

upd(
    "tech.how_stt_works",
    "We capture audio, clean it, and often use VAD to drop silence. The model turns sound into features and decodes text. Whisper takes audio, processes it, recognizes the spoken words, and converts them into text.",
    "نلتقط الصوت وننظّفه وغالباً نستخدم VAD لإسقاط الصمت. النموذج يحوّل الصوت إلى ميزات ثم إلى نص. Whisper يأخذ الصوت ويعالجه ويتعرّف على الكلام ويحوّله إلى نص.",
    aliases_extra=["how does speech to text work", "how does stt work"],
)

# --- New entries ---
add(
    "tech.whisper_how",
    "How does Whisper work?",
    [
        "how does whisper work",
        "explain how whisper works",
        "how whisper converts audio to text",
    ],
    ["whisper", "audio", "recognize", "text"],
    "Whisper takes audio, processes it, recognizes the spoken words, and converts them into text.",
    "Whisper يأخذ الصوت ويعالجه ويتعرّف على الكلمات المنطوقة ويحوّلها إلى نص.",
)

add(
    "tech.vad_what",
    "What is Voice Activity Detection (VAD)?",
    [
        "what is voice activity detection",
        "what is vad",
        "explain vad",
        "what does vad do",
    ],
    ["vad", "voice activity", "speaking", "silence"],
    "VAD detects when a person starts and stops speaking.",
    "VAD يكتشف متى يبدأ الشخص بالكلام ومتى يتوقف.",
)

add(
    "tech.speech_accuracy_factors",
    "What factors affect speech recognition accuracy?",
    [
        "what factors affect speech recognition accuracy",
        "what affects speech recognition accuracy",
        "what affects whisper accuracy",
        "stt accuracy factors",
    ],
    ["audio quality", "noise", "accent", "microphone", "clarity"],
    "Audio quality, background noise, accent, microphone quality, and speech clarity can affect accuracy.",
    "جودة الصوت والضوضاء واللهجة وجودة الميكروفون ووضوح الكلام تؤثر على الدقة.",
)

add(
    "tech.speech_accuracy_improve",
    "How can you improve speech recognition accuracy?",
    [
        "how can you improve speech recognition accuracy",
        "how to improve speech recognition",
        "how to improve whisper accuracy",
        "improve stt accuracy",
    ],
    ["clean audio", "noise reduction", "vad", "microphone", "model"],
    "We can improve accuracy using clean audio, noise reduction, VAD, a good microphone, and the right speech model.",
    "نحسّن الدقة بصوت نظيف وتقليل الضوضاء وVAD وميكروفون جيد والنموذج المناسب.",
)

add(
    "tech.stt_latency",
    "How do you reduce Speech-to-Text latency?",
    [
        "how do you reduce speech-to-text latency",
        "how to reduce stt latency",
        "reduce whisper latency",
        "faster speech to text",
    ],
    ["latency", "gpu", "vad", "streaming", "chunks"],
    "We can reduce latency using a faster model, GPU processing, VAD, streaming, and smaller audio chunks.",
    "نقلّل زمن الاستجابة بنموذج أسرع ومعالجة GPU وVAD والبث وأجزاء صوت أصغر.",
)

add(
    "tech.batch_vs_streaming_transcription",
    "What is the difference between batch and streaming transcription?",
    [
        "what is the difference between batch and streaming transcription",
        "batch vs streaming transcription",
        "batch versus streaming stt",
        "real time vs batch transcription",
    ],
    ["batch", "streaming", "transcription", "real time"],
    "Batch transcription processes the complete audio, while streaming transcription processes audio in real time.",
    "التفريغ بالدفعات يعالج الصوت كاملاً، بينما التفريغ البثي يعالج الصوت في الزمن الحقيقي.",
)

add(
    "tech.whisper_llm_integrate",
    "How can Whisper be integrated with an LLM or AI Agent?",
    [
        "how can whisper be integrated with an llm or ai agent",
        "how to integrate whisper with llm",
        "whisper with ai agent",
        "connect whisper to llm",
    ],
    ["whisper", "llm", "agent", "text", "speech"],
    "Whisper converts speech into text, then the text is sent to the LLM or AI agent for understanding and action.",
    "Whisper يحوّل الكلام إلى نص، ثم يُرسل النص إلى النموذج أو الوكيل للفهم والتنفيذ.",
)

add(
    "tech.speech_ai_agent",
    "How can Speech AI be connected to an AI Agent?",
    [
        "how can speech ai be connected to an ai agent",
        "connect speech ai to agent",
        "speech to ai agent",
        "voice to agent pipeline",
    ],
    ["speech ai", "agent", "voice", "text", "actions"],
    "Speech AI converts voice into text, and the text is sent to the agent to make decisions and take actions.",
    "Speech AI يحوّل الصوت إلى نص، ويُرسل النص إلى الوكيل لاتخاذ القرار والتنفيذ.",
)

add(
    "tech.whisper_agentic",
    "How can Whisper be used in an Agentic AI workflow?",
    [
        "how can whisper be used in an agentic ai workflow",
        "whisper in agentic workflow",
        "whisper agentic ai",
        "use whisper with agentic ai",
    ],
    ["whisper", "agent", "tools", "speech", "workflow"],
    "Whisper converts user speech into text, then the agent analyzes the request, chooses tools, and performs the task.",
    "Whisper يحوّل كلام المستخدم إلى نص، ثم يحلّل الوكيل الطلب ويختار الأدوات وينفّذ المهمة.",
)

add(
    "tech.pass_transcription_to_llm",
    "How do you pass transcribed speech to an LLM or AI Agent?",
    [
        "how do you pass transcribed speech to an llm or ai agent",
        "how to send transcription to llm",
        "pass whisper output to agent",
        "send stt text to llm",
    ],
    ["transcription", "text input", "llm", "agent"],
    "I send the transcription as text input to the LLM or agent.",
    "أرسل التفريغ كنص إدخال إلى النموذج أو الوكيل.",
)

add(
    "tech.validate_question_before_llm",
    "How do you validate the detected question before generating an answer?",
    [
        "how do you validate the detected question before generating an answer",
        "validate transcription before llm",
        "check question before answering",
        "validate detected question",
    ],
    ["transcription", "language", "confidence", "meaning", "validation"],
    "I check the transcription, language, confidence, and question meaning before sending it to the LLM.",
    "أتحقق من التفريغ واللغة والثقة ومعنى السؤال قبل إرساله إلى النموذج.",
)

add(
    "tech.audio_stt_llm_error_reduce",
    "How do you reduce errors between audio capture, transcription, and LLM response?",
    [
        "how do you reduce errors between audio capture transcription and llm response",
        "reduce errors audio transcription llm",
        "audio to llm error handling",
        "reduce stt to llm pipeline errors",
    ],
    ["clean audio", "vad", "validation", "error handling", "context"],
    "I use clean audio, VAD, validation, error handling, and context checking before generating the answer.",
    "أستخدم صوتاً نظيفاً وVAD وتحققاً ومعالجة أخطاء وفحص سياق قبل توليد الجواب.",
)

idx = next(i for i, e in enumerate(entries) if e["id"] == "tech.what_is_whisper")
for i, e in enumerate(NEWS):
    entries.insert(idx + 1 + i, e)
    by[e["id"]] = e

raw["entries"] = entries
path.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("TOTAL", len(entries), "new", len(NEWS), "backup", BAK)
