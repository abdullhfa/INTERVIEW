# Evaluator Audit — Final Unseen Holdout (2026-09-12)

**Scope:** Measurement / scoring / timing only. **No Intent weight/threshold/alias changes.**

**Source run:** `FINAL_UNSEEN_HOLDOUT_REPORT` · 120 scored · frozen system

## Verdict on the three questions

| Question | Finding |
|----------|---------|
| Is HC wrong=14 true system failure? | **No — scoring bug.** All 14 have `intent_ok=True` and `result=PASS`. They are gold-ID mismatches after `meaning_ok` already accepted the answer. |
| Is compound coverage=16.7% true failure? | **No — metric bug.** Compound **Intent = 15/15**. Gate averaged `intent_coverage_rate` on rows that mostly used the **single-intent path** (coverage stays 0.0). |
| Is median post-speech 3.86s true? | **Mostly yes as wall-clock**, dominated by Whisper. Also a **timer attribution bug**: bank match + semantic recovery were folded into `stt_ms`, so stage labels lied even though end-to-end delay is real. |

## 1) HC wrong

### What the code did
```text
intent_ok = gold_hit OR meaning_ok
if not gold_hit and match.mode == "strong":
    high_conf_wrong_gold = True   # forced HC even when intent_ok became True
```

### Evidence from the run
- HC count = 14
- HC ∩ intent_ok = **14/14**
- HC ∩ FAIL = **0/14**
- gold_miss ∧ intent_ok = 40 (14 of them flagged HC because mode was strong)

### Correct definitions (evaluator)
- `gold_id_mismatch`: selected ID ∉ expected gold set (observability)
- `high_confidence_wrong`: **strong mode AND final intent_ok == False** (and score ≥ 0.70)
- Never call gold-only sibling mismatch “HC wrong” when meaning was accepted

## 2) Compound coverage

### What the gate did
Average of `intent_coverage_rate` over `question_type_label == compound`.

### Evidence
- Compound Intent: **15/15**
- Per-row coverage values: mostly `0.0`, few `0.5`/`1.0` → mean ≈ 0.167
- Most compound items answered via single strong match / meaning_ok, so compound pipeline coverage stayed 0

### Correct definition (evaluator)
For compound-labeled items:
```text
gold_part_coverage = |selected_ids ∩ expected_intent_ids| / |expected_intent_ids|
```
Report separately: `compound_path_used_rate` (router diagnostic only).

## 3) Latency

### Wall-clock truth
`post_speech_ms = stt_ms + intent_ms + answer_ms` (after speech ends).

| Type | median post | median “stt” bucket | median intent bucket |
|------|-------------|---------------------|----------------------|
| ultra_short | 3516 | 3507 | 0.3 |
| short | 1269 | 1262 | 0.2 |
| medium | 4413 | 4402 | 0.3 |
| long | 4755 | 4675 | 0.6 |
| very_long | 5602 | 5414 | 0.6 |
| compound | 2091 | 2082 | 0.3 |

Overall median post **3861 ms**; median reported STT **3852 ms**; intent bucket ~0.3–0.6 ms after compound-only timer.

### Attribution bug
Order in `run_clip` was:
1. Whisper (+ optional accurate second pass)
2. `question_bank.match` / recoveries / **semantic recovery**
3. **then** `stt_ms` was closed  
4. compound-only timed as `intent_ms`

So semantic (~median 618 ms when triggered, 85/120) and matching were labeled “STT”.

Even after subtracting semantic latency, median post remains ~**3.4 s** → still fails the 1.5 s gate. Primary driver: **Whisper on longer / second-pass / loopback clips**, not Intent.

### Extra suite wiring note
Holdout conditions use `poor`, while recovery gates on `poor_call` → Poor recovery never armed on this pack. Far (`far`) did arm. Evaluator/suite label mismatch.

## Actions taken after this audit
1. Fixed HC / gold mismatch split (evaluator only) — HC no longer forced on gold miss when `intent_ok`
2. Fixed compound gate to **gold-part coverage**; `compound_path_used_rate` is diagnostic only
3. Fixed stage timers: `whisper_ms` / `match_ms` / `semantic_ms` / `compound_ms` (STT bucket = Whisper only)
4. Mapped holdout `poor` → `poor_call` for recovery gating
5. **Voided** Final Unseen Holdout v1 (`VOIDED_FINAL_UNSEEN_HOLDOUT_V1.json`)
6. Built **final-unseen-holdout-v2** scripts (new texts; audio pending synthesis)

## Retrospective on voided v1 run (fixed definitions, same transcripts)

| Metric | Reported | After fix definition |
|--------|----------|----------------------|
| HC wrong | 14 | **0** (all 14 were intent_ok + gold mismatch) |
| gold_id_mismatch (intent_ok) | — | 40 |
| Compound coverage | 16.7% | **~46.7%** gold-part (still &lt;90%; Intent type still 15/15) |
| median post-speech | 3861 ms | **~3861 ms** (wall-clock real; labels were wrong) |

## What we are NOT doing
- No Intent weight / threshold / alias / profile tuning
- Not chasing 91.7% → 92% on the voided sample
- Not declaring READY from v1 under any reinterpretation