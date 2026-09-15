NOT_VALIDATED_END_TO_END

> **CORRECTION:** Previous PASS / 0.90 metrics were an offline WAV	o Whisper harness, not the real play	o WASAPI loopback	o VAD	o STT path. Treat those numbers as simulation only.


# V5 150 Voice Stress Results

Created: `2026-09-14T10:40:19.930578+00:00`

Pack: `C:\Users\aalsa\OneDrive\Desktop\interview (2)\interview11\frontend\public\voice-drill\v5-150-voice-stress\V5_150_Voice_Stress_Test`

> Accent audio is synthetic proxy audio, not recordings of real speakers.

## Summary

- n=150
- ok_rate=**0.9**
- meaning_preserved_rate=**0.94**
- question_understood_rate=**0.5933**
- answer_selected_rate=**0.4267**
- confident_wrong=**0**
- median_latency_ms=**2305.2** (stt=871.6, match=1363.1)

## Accent
```json
{
  "emirati": {
    "n": 50,
    "ok": 43,
    "ok_rate": 0.86,
    "meaning_rate": 0.92,
    "understood_rate": 0.54,
    "answer_rate": 0.34,
    "hc_wrong": 0,
    "median_latency_ms": 2305.2,
    "median_stt_ms": 871.2
  },
  "indian": {
    "n": 50,
    "ok": 46,
    "ok_rate": 0.92,
    "meaning_rate": 0.92,
    "understood_rate": 0.7,
    "answer_rate": 0.58,
    "hc_wrong": 0,
    "median_latency_ms": 2425.9,
    "median_stt_ms": 864.4
  },
  "jordanian": {
    "n": 50,
    "ok": 46,
    "ok_rate": 0.92,
    "meaning_rate": 0.98,
    "understood_rate": 0.54,
    "answer_rate": 0.36,
    "hc_wrong": 0,
    "median_latency_ms": 2155.6,
    "median_stt_ms": 878.9
  }
}
```

## Speed
```json
{
  "fast": {
    "n": 37,
    "ok": 33,
    "ok_rate": 0.8919,
    "meaning_rate": 0.9459,
    "understood_rate": 0.5676,
    "answer_rate": 0.4324,
    "hc_wrong": 0,
    "median_latency_ms": 2273.2,
    "median_stt_ms": 870.6
  },
  "normal": {
    "n": 38,
    "ok": 34,
    "ok_rate": 0.8947,
    "meaning_rate": 0.9211,
    "understood_rate": 0.5263,
    "answer_rate": 0.3421,
    "hc_wrong": 0,
    "median_latency_ms": 2355.8,
    "median_stt_ms": 862.0
  },
  "slow": {
    "n": 38,
    "ok": 37,
    "ok_rate": 0.9737,
    "meaning_rate": 0.9737,
    "understood_rate": 0.7368,
    "answer_rate": 0.5,
    "hc_wrong": 0,
    "median_latency_ms": 2175.0,
    "median_stt_ms": 895.0
  },
  "very_fast": {
    "n": 37,
    "ok": 31,
    "ok_rate": 0.8378,
    "meaning_rate": 0.9189,
    "understood_rate": 0.5405,
    "answer_rate": 0.4324,
    "hc_wrong": 0,
    "median_latency_ms": 2316.3,
    "median_stt_ms": 865.2
  }
}
```

## Distance
```json
{
  "close": {
    "n": 50,
    "ok": 47,
    "ok_rate": 0.94,
    "meaning_rate": 0.98,
    "understood_rate": 0.72,
    "answer_rate": 0.46,
    "hc_wrong": 0,
    "median_latency_ms": 2291.8,
    "median_stt_ms": 872.6
  },
  "far": {
    "n": 50,
    "ok": 44,
    "ok_rate": 0.88,
    "meaning_rate": 0.88,
    "understood_rate": 0.58,
    "answer_rate": 0.46,
    "hc_wrong": 0,
    "median_latency_ms": 2306.7,
    "median_stt_ms": 917.9
  },
  "medium": {
    "n": 50,
    "ok": 44,
    "ok_rate": 0.88,
    "meaning_rate": 0.96,
    "understood_rate": 0.48,
    "answer_rate": 0.36,
    "hc_wrong": 0,
    "median_latency_ms": 2305.2,
    "median_stt_ms": 857.7
  }
}
```

## Noise
```json
{
  "clean": {
    "n": 37,
    "ok": 35,
    "ok_rate": 0.9459,
    "meaning_rate": 0.9459,
    "understood_rate": 0.6757,
    "answer_rate": 0.4054,
    "hc_wrong": 0,
    "median_latency_ms": 2154.1,
    "median_stt_ms": 859.6
  },
  "fan": {
    "n": 38,
    "ok": 35,
    "ok_rate": 0.9211,
    "meaning_rate": 0.9474,
    "understood_rate": 0.7105,
    "answer_rate": 0.5789,
    "hc_wrong": 0,
    "median_latency_ms": 2114.4,
    "median_stt_ms": 922.2
  },
  "keyboard": {
    "n": 37,
    "ok": 35,
    "ok_rate": 0.9459,
    "meaning_rate": 0.973,
    "understood_rate": 0.6216,
    "answer_rate": 0.4054,
    "hc_wrong": 0,
    "median_latency_ms": 2316.3,
    "median_stt_ms": 858.7
  },
  "room": {
    "n": 38,
    "ok": 30,
    "ok_rate": 0.7895,
    "meaning_rate": 0.8947,
    "understood_rate": 0.3684,
    "answer_rate": 0.3158,
    "hc_wrong": 0,
    "median_latency_ms": 2421.2,
    "median_stt_ms": 871.5
  }
}
```

## Style
```json
{
  "compound": {
    "n": 30,
    "ok": 30,
    "ok_rate": 1.0,
    "meaning_rate": 1.0,
    "understood_rate": 0.6333,
    "answer_rate": 0.4,
    "hc_wrong": 0,
    "median_latency_ms": 2468.2,
    "median_stt_ms": 917.1
  },
  "direct": {
    "n": 18,
    "ok": 16,
    "ok_rate": 0.8889,
    "meaning_rate": 0.8889,
    "understood_rate": 0.7222,
    "answer_rate": 0.6667,
    "hc_wrong": 0,
    "median_latency_ms": 1149.4,
    "median_stt_ms": 787.4
  },
  "indirect": {
    "n": 60,
    "ok": 55,
    "ok_rate": 0.9167,
    "meaning_rate": 0.9833,
    "understood_rate": 0.6,
    "answer_rate": 0.45,
    "hc_wrong": 0,
    "median_latency_ms": 2273.3,
    "median_stt_ms": 862.9
  },
  "long": {
    "n": 24,
    "ok": 23,
    "ok_rate": 0.9583,
    "meaning_rate": 1.0,
    "understood_rate": 0.5417,
    "answer_rate": 0.3333,
    "hc_wrong": 0,
    "median_latency_ms": 3189.5,
    "median_stt_ms": 1115.3
  },
  "short": {
    "n": 18,
    "ok": 11,
    "ok_rate": 0.6111,
    "meaning_rate": 0.6667,
    "understood_rate": 0.4444,
    "answer_rate": 0.2778,
    "hc_wrong": 0,
    "median_latency_ms": 1765.1,
    "median_stt_ms": 774.8
  }
}
```

## Blockers

- none

## Confident wrong (up to 20)

- none

## Failures (up to 30)

- `V5A_029` jordanian/very_fast/medium/fan status=ANSWER_READY mean=True und=False match=tech.reduce_cost tx='If the LLM starts giving unsupported answers, how would you reduce that behavior?'
- `V5A_036` emirati/very_fast/close/room status=ANSWER_READY mean=True und=False match=tech.agent_design_finance,hard.agent_stop_tools tx='How do you decide when an A agent can continue alone and when it must ask a person?'
- `V5A_038` jordanian/fast/medium/room status=ANSWER_READY mean=True und=False match=hard.which_rag_layer_failed tx='In a real project, where would then change it between the model, retrieval, prompts, and tools?'
- `V5A_048` emirati/very_fast/far/room status=LOW_CONFIDENCE mean=False und=False match= tx="How will you make AEM's decision on it an older-resulated organization?"
- `V5A_050` jordanian/fast/close/room status=ANSWER_READY mean=True und=False match=tech.agentic_what tx='If you needed to connect an AI agent to email databases and approvals, how can then hash 10 help.'
- `V5A_114` emirati/normal/medium/keyboard status=ANSWER_READY mean=True und=False match=tech.how_stt_works,tech.transcription_quality,hard.production_monitoring tx='If users complain that an AI interview assistant responds too late, how of you profile speech finalization, semantic retrieval, answer selection, and display time before making performance changes?'
- `V5A_115` indian/fast/medium/fan status=LOW_CONFIDENCE mean=False und=False match= tx='Why, right?'
- `V5A_117` emirati/fast/close/clean status=LOW_CONFIDENCE mean=False und=True match=hard.why_agent_not_rag tx='Rang, why use it?'
- `V5A_120` emirati/very_fast/far/room status=LOW_CONFIDENCE mean=False und=False match= tx="Pay and panel, I've done it work."
- `V5A_121` indian/slow/far/clean status=LOW_CONFIDENCE mean=False und=False match= tx='Why am bedding?'
- `V5A_124` indian/normal/medium/room status=LOW_CONFIDENCE mean=False und=False match= tx='When will you use Zundra?'
- `V5A_125` jordanian/very_fast/far/fan status=LOW_CONFIDENCE mean=False und=False match= tx='White and Rep here.'
- `V5A_132` emirati/very_fast/medium/room status=ANSWER_READY mean=True und=False match=tech.what_is_llm tx='No context, what shows the LLM do?'
- `V5A_138` emirati/normal/far/keyboard status=LOW_CONFIDENCE mean=False und=False match= tx='What do you mean by me and big chicken?'
- `V5A_148` indian/normal/far/room status=LOW_CONFIDENCE mean=False und=False match= tx='What in a met, a mate, amet, mate?'
