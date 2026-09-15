PASS_150_VOICE_STRESS_E2E

# V5 150 Voice Stress — End-to-End Loopback Verdict

Created: `2026-09-15T03:49:12.734131+00:00`

Path: `WAV → speakers → WASAPI loopback → VAD → STT → understanding → answer`

## Summary

- n=150
- pass_rate=**0.9**
- stt_rate=**0.9533**
- intent_rate=**0.9**
- confident_wrong=**0**
- audio_fail=**0**
- median_total_ms=**8639.5**
- median_post_speech_ms=**1420.8**

## Accent / speed / distance / noise

### Accent
```json
{
  "emirati": {
    "n": 50,
    "pass": 41,
    "pass_rate": 0.82,
    "stt_ok": 48,
    "intent_ok": 41,
    "hc_wrong": 0,
    "median_total_ms": 8558.85,
    "median_post_speech_ms": 1365.65
  },
  "indian": {
    "n": 50,
    "pass": 46,
    "pass_rate": 0.92,
    "stt_ok": 45,
    "intent_ok": 46,
    "hc_wrong": 0,
    "median_total_ms": 8735.55,
    "median_post_speech_ms": 1447.4
  },
  "jordanian": {
    "n": 50,
    "pass": 48,
    "pass_rate": 0.96,
    "stt_ok": 50,
    "intent_ok": 48,
    "hc_wrong": 0,
    "median_total_ms": 8643.7,
    "median_post_speech_ms": 1424.1999999999998
  }
}
```

### Speed
```json
{
  "fast": {
    "n": 37,
    "pass": 33,
    "pass_rate": 0.8919,
    "stt_ok": 35,
    "intent_ok": 33,
    "hc_wrong": 0,
    "median_total_ms": 7853.3,
    "median_post_speech_ms": 1424.1
  },
  "normal": {
    "n": 38,
    "pass": 33,
    "pass_rate": 0.8684,
    "stt_ok": 35,
    "intent_ok": 33,
    "hc_wrong": 0,
    "median_total_ms": 9339.05,
    "median_post_speech_ms": 1451.9499999999998
  },
  "slow": {
    "n": 38,
    "pass": 37,
    "pass_rate": 0.9737,
    "stt_ok": 37,
    "intent_ok": 37,
    "hc_wrong": 0,
    "median_total_ms": 10937.75,
    "median_post_speech_ms": 1384.2
  },
  "very_fast": {
    "n": 37,
    "pass": 32,
    "pass_rate": 0.8649,
    "stt_ok": 36,
    "intent_ok": 32,
    "hc_wrong": 0,
    "median_total_ms": 7260.7,
    "median_post_speech_ms": 1410.9
  }
}
```

### Distance
```json
{
  "close": {
    "n": 50,
    "pass": 49,
    "pass_rate": 0.98,
    "stt_ok": 50,
    "intent_ok": 49,
    "hc_wrong": 0,
    "median_total_ms": 8413.6,
    "median_post_speech_ms": 1422.8
  },
  "far": {
    "n": 50,
    "pass": 40,
    "pass_rate": 0.8,
    "stt_ok": 46,
    "intent_ok": 40,
    "hc_wrong": 0,
    "median_total_ms": 8533.400000000001,
    "median_post_speech_ms": 1413.65
  },
  "medium": {
    "n": 50,
    "pass": 46,
    "pass_rate": 0.92,
    "stt_ok": 47,
    "intent_ok": 46,
    "hc_wrong": 0,
    "median_total_ms": 8760.8,
    "median_post_speech_ms": 1442.35
  }
}
```

### Noise
```json
{
  "clean": {
    "n": 37,
    "pass": 34,
    "pass_rate": 0.9189,
    "stt_ok": 37,
    "intent_ok": 34,
    "hc_wrong": 0,
    "median_total_ms": 8658.3,
    "median_post_speech_ms": 1374.1
  },
  "fan": {
    "n": 38,
    "pass": 36,
    "pass_rate": 0.9474,
    "stt_ok": 35,
    "intent_ok": 36,
    "hc_wrong": 0,
    "median_total_ms": 8088.7,
    "median_post_speech_ms": 1419.55
  },
  "keyboard": {
    "n": 37,
    "pass": 34,
    "pass_rate": 0.9189,
    "stt_ok": 37,
    "intent_ok": 34,
    "hc_wrong": 0,
    "median_total_ms": 9536.7,
    "median_post_speech_ms": 1452.8
  },
  "room": {
    "n": 38,
    "pass": 31,
    "pass_rate": 0.8158,
    "stt_ok": 34,
    "intent_ok": 31,
    "hc_wrong": 0,
    "median_total_ms": 8473.150000000001,
    "median_post_speech_ms": 1444.65
  }
}
```

## Blockers

- none

## Confident wrong

- none

## Failures (up to 30)

- `V5A_010` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='Can you explain where retrieval actually fitted into the Ministry-Betech solution you worked on?'
- `V5A_012` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='What we through how external BAT knowledge reached the languages model in your robot.'
- `V5A_017` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='How with turning the theft into vector help the system finds the right detect information.'
- `V5A_021` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='What role is the vector for play between your documents and the languages model?'
- `V5A_030` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='How do you keep an AI assistance ground when the unavailable context does not container the answer?'
- `V5A_033` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='If this system were used by a government organization, what controls what you place around the model?'
- `V5A_040` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='When none are slow become complex enough that you would critter and wrap over a simple chain?'
- `V5A_042` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='What problems does a graph-based workflow solve when the AI process is no longer a straight line?'
- `V5A_048` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx="How will you make AEM's decision on an over-remanulated organization?"
- `V5A_051` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='What kind of automation would you give to n-hashed n rather than writing the whole integration in code?'
- `V5A_052` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='What happens when the information you want to send is larger than the model can keep in context?'
- `V5A_057` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='What controls what you have is untrusted contents cause try to manipulate the aliens.'
- `V5A_062` stage=QUESTION_UNDERSTANDING detail=Transcript usable but wrong intent (intent_only). tx='Rad architecture, retrieval theft, contest selection, and final answer, though, walk be through all of it.'
- `V5A_120` stage=STT detail=Poor loopback transcription (stt_wrong_intent_recoverable). tx="Pay and panel, I've done it work."
- `V5A_148` stage=STT detail=Poor loopback transcription (stt_wrong_intent_recoverable). tx='What in a me, ametamate, amaze.'

## Prior offline harness

Previous `PASS_150_VOICE_STRESS` / 0.90 metrics are **invalidated** for E2E claims (see `V5_150_VOICE_STRESS_RESULTS.md` marked `NOT_VALIDATED_END_TO_END`).
