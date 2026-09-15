# Latency-cut Track

**Status:** Simple multi-pass **CLOSED** (short_length median gate PASS) · overall track still open (compound + Final Latency Check)  
**Date:** 2026-09-13  
**Locks:** Intent thresholds/aliases/abstain untouched · Track A beam=3 `best_of=1` kept · B/C coverage not retuned

## Phase 1 — Whisper bench vs E2E (root cause)

Script: `scripts/compare_whisper_e2e_vs_bench.py` → `WHISPER_BENCH_VS_E2E.json`

| Path | Result |
|------|--------|
| Device | **CUDA** `distil-large-v3` / `int8_float16` (same as Track A) |
| Bench first-pass p50 | **~917 ms** (matches Track A ~924 ms) |
| Dominant E2E cause (pre-cut) | **Second/third Whisper passes**, not wrong model/device |

## Simple multi-pass (this close)

### Policy shipped

| Rule | Implementation |
|------|----------------|
| `MAX_STT_PASSES_SIMPLE = 2` | `stt_confidence.py` + E2E/live |
| Pass1 + `strong_agrees` / high lexical → stop | `simple_need_second_pass` + fast path |
| Never short-alone as second-pass reason | gate ignores short-only |
| Never third STT on simple | raw pass3 compound-only |
| Accurate pass2 lightened | `whisper_stt.py`: single temp `0.0`, beam capped, `best_of=1` |
| Second pass only for STT doubt | broken / `stt_retry` / strong disagree — **not** `thin_margin` |
| Fluent `no_viable` → Intent path, not Whisper | avoids wasted pass2 on clean text |
| Narrow STT term repairs | R&E/RNG, genetic→agentic, Langdraff, badings→embeddings |
| Skip semantic tax on simple when score ≥ 0.90 | loopback fast path (thresholds unchanged) |

### Per-clip report fields (`post_speech_trace`)

`whisper_call_count`, `whisper_pass1_ms`/`pass2`/`pass3`, `second_pass_trigger_reason`, `first_pass_text`, `first_pass_intent`, `first_pass_confidence`, `strong_agrees`, `final_text`, `total_whisper_ms`, `total_post_ms`

### Measure — `short_length` n=8 (post simple close)

| Metric | Before (Final Latency) | Mid (multi-pass still on) | **Now** | Gate |
|--------|------------------------|---------------------------|---------|------|
| Median post | 4538 ms | ~4728 / ~2920 | **1379 ms** | ≤1500 **PASS** |
| p95 post | 5395 ms | — | **3715 ms** | observe (clip 8 semantic) |
| Intent | 8/8 | 7/8 | **8/8** | ≥7/8 **PASS** |
| HC wrong | 0 | 0 | **0** | **PASS** |
| Median Whisper calls | ~2–3 | 2 | **1** | ≈1 **PASS** |
| % simple ≤2 STT | — | 100% | **100%** | ≥95% **PASS** |

All 8 clips: `whisper_call_count=1`, `whisper_pass3_ms=None`.  
Clips 7–8 still pay semantic recovery (no strong first-pass match) → p95 elevated; **median already under gate**.

### Compound

Full `compound_dev` n=40 (no code changes this round):

| Metric | Value | Gate | |
|--------|------:|------|--|
| Intent | **100%** (40/40) | ≥95% | PASS |
| Gold-part coverage | **95%** | ≥90% | PASS |
| HC wrong | **0** | =0 | PASS |
| Median post-speech | **4770 ms** | ≤2000 | **FAIL** |
| p95 post-speech | **7070 ms** | ≤~3000 | **FAIL** |
| Median whisper_calls | **1** (dist 1:23 / 2:1 / 3:16) | observe | |
| compound_detect_ms median | **0.4** | | |
| decomposition_ms median | **0.2** | | |
| subquestion_match_ms median | **737** (p95 2392) | | |
| semantic_ms median | **670** (p95 1514) | | |
| merge_ms median | **0.1** | | |

Dominant post cost: Whisper multi-pass on ~40% of clips (16/40 hit 3 calls) + subquestion match + semantic — detect/decompose/merge are negligible.

**Do not run Final Latency Check yet** (compound latency gate FAIL).

### Deferred (Simple p95 tail)

Simple `p95 ≈ 3.7s` from semantic on 2 shorts only — **logged, not opened** until after compound latency decision.

## Compound latency-cut round (after attribution)

### Unattributed ~2s — resolved

Per-clip: `post = whisper + match_ms + outer_semantic + compound_ms + answer` → **`unattributed_ms ≈ 0`**.

The apparent gap was incomplete median arithmetic: missing **`match_ms ≈ 948 ms`** (pre-compound realistic/outer semantic), and `subquestion_match` already sits inside `compound_ms`.

### Changes (no Intent threshold edits)

| Change | Effect |
|--------|--------|
| `unattributed_ms` + full stage split in `post_speech_trace` | Attribution closed |
| `MAX_STT_PASSES_COMPOUND = 2` + STT-only second-pass gate | No pass3; no Whisper for weak intent |
| Skip outer realistic/semantic on labeled compound | Eliminated duplicate whole-utterance recovery |
| Batch `top_k_many` + per-part lexical fast path | Fewer serial embeds |

### Remeasure — `compound_dev` n=40

| Metric | Before | After | Gate |
|--------|-------:|------:|------|
| Intent | 100% | **100%** (40/40) | ≥95% **PASS** |
| Gold-part | 95% | **93.75%** | ≥90% **PASS** |
| HC wrong | 0 | **0** | **PASS** |
| Median Whisper calls | 1 (but 16×3) | **1** (39×1, 1×2) | ≈1 **PASS** |
| Max STT passes | 3 | **2** | ≤2 **PASS** |
| Median post | 4770 ms | **2273 ms** | ≤2000 **FAIL** (near) |
| p95 post | 7070 ms | **4059 ms** | ≤~3000 **FAIL** |
| unattributed_ms median | — | **0** | |
| outer_semantic / realistic | 670 / ~part of 948 | **0 / 0** | |
| subquestion_match median | 737 | **730** | remaining bottleneck |
| lexical_match_ms median | — | **556** | |

**Verdict:** Quality + STT budget PASS. Latency improved **~2.5s** median but still **~273 ms** over 2.0s median gate; p95 still high on heavy multi-part matching. **No Final Latency Check yet.**

Remaining compound cost is almost entirely **inside** `compound_ms` (lexical match / occasional semantic_parts / harvest) — not missing stages.

## Compound lexical-cut round

### Shipped (scoring thresholds/weights unchanged)

| Change | Where |
|--------|--------|
| Precomputed alias token sets + inverted token/distinctive index | `question_bank` load |
| `_score_all` candidate pruning + LRU score cache | `question_bank._score_all` |
| Batch `prefetch_scores` for compound sub-questions | compound phase-1 |
| Fast lexical accept (skip extra `top_matches` on strong hits) | `compound_question_pipeline` |

### Remeasure — `compound_dev` n=40

| Metric | Prior | Lexical cut | Gate |
|--------|------:|------------:|------|
| Intent | 100% | **100%** | ≥95% **PASS** |
| Gold-part | 93.75% | **93.13%** | ≥90% **PASS** |
| HC | 0 | **0** | **PASS** |
| Whisper max | 2 | **2** | ≤2 **PASS** |
| Median post | 2273 ms | **1773 ms** | ≤2000 **PASS** |
| p95 post | 4059 ms | **5027 ms** | ≤~3000 **FAIL** (tail) |
| lexical_match_ms median | 556 ms | **46 ms** | |

### p95 worst clips

| Clip | post | lex | sem_parts | harvest | parts |
|------|-----:|----:|----------:|--------:|------:|
| cdev_037 | 5428 | 1977 | 1491 | 0 | 2 |
| cdev_030 | 5037 | 3455 | 0 | 0 | 5 |
| cdev_036 | 5027 | 899 | 733 | 1394 | 4 |

Median ≤2.0s met → **Final Latency Check** next.

## Final Latency Check (fresh simple + compound reports)

| Cohort | Median post | Script gate ≤1500 | Your compound working gate ≤2000 |
|--------|------------:|:-----------------:|:--------------------------------:|
| Simple | **1194 ms** | **PASS** | — |
| Compound | **1773 ms** | **FAIL** | **PASS** |

**Official script verdict: FAIL** (both cohorts must be ≤1500). Do **not** start Holdout v3.

Also observe: fresh simple Intent **7/8** (one fail) · HC=0 · simple p95 **3948** (deferred semantic tail). Compound Intent **40/40** · gold-part **93.13%** · HC=0 · p95 **5027**.

To clear Final Latency Check as coded: need compound median **≤1500** (~273ms more) and preferably stabilize simple 8/8.

## Artifacts
