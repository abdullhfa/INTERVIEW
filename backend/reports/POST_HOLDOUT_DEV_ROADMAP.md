# Post-Holdout Development Roadmap

**Official status:** NOT READY FOR INTERVIEW  
**Holdout v2:** FROZEN / eval-only — do **not** tune Intent weights, thresholds, aliases, or profiles from v2 texts or audio.  
**Track A / STT:** FROZEN — do not reopen Whisper beam/`best_of`/second-pass unless a real STT bug blocks later tracks.  
**Track B / Compound coverage:** FROZEN — do not retune compound on Holdout v2; coverage gate already closed on compound-dev.

| Artifact | Role |
|----------|------|
| `final-unseen-holdout` (v1) | VOIDED (evaluator bugs) |
| `final-unseen-holdout-v2` | Official NOT READY sample — locked |
| `compound-dev` | Track B pack only (not Final Holdout) |
| `generalization-dev` | Track C pack only — new wording + audio |
| Holdout v3 | Only after A → B → C + final latency check + frozen regressions |

## Track order (strict)

1. **Track A — STT / Whisper latency** — **DONE / FROZEN** (`STT_LATENCY_TRACK_A.md`)  
   Whisper p50 ≈ **924 ms** on latency-dev; Clean 28/30 HC=0; short 8/8 HC=0.

2. **Track B — Compound gold-part coverage** — **DONE / FROZEN** (`COMPOUND_COVERAGE_TRACK_B.md`)  
   Accepted final: offline **100%** · E2E gold-part **95%** · Intent **100%** · HC=0.

3. **Track C — Generalization development** — **DONE / FROZEN** (`GENERALIZATION_TRACK_C.md`)  
   Pack: `generalization-dev` · E2E Intent **100%** (56/56) · all major slices **100%** · HC=0 · meaning_lost=0.  
   Short spot HC=0; compound spot gold-part 100% / HC=0.

4. **Final latency check (A+B+C)** — **FAIL** (`FINAL_LATENCY_CHECK.md`)  
   Fresh measure: simple median **4538 ms**, compound **4852 ms** (gate ≤1500).  
   Quality OK; do not start v3 on that alone.

5. **Latency-cut / Pre-V3 hardening** — **`LATENCY_READY_FOR_V3`** (`FINAL_PRE_V3_LATENCY_HARDENING.md`)  
   Hard gates PASS: simple median **1266** ≤1500 · compound median **1711** ≤2000 · HC=0 · Intent 100% · gold-part **92.5%**.  
   Targets: compound p95 **2519** ≤3000 PASS · simple p95 **2210** ≤2000 miss (observe).  
   `unattributed_ms ≈ 0`. R-E→RAG deferred (abstain, HC=0). **Holdout v3 may start.**

6. After latency PASS → frozen-suite regression → **Final Holdout v3** (new pack only).

## Forbidden now

- Chasing Intent % via thresholds/aliases on holdout data  
- Using Holdout v2 as a development set  
- Further STT latency chasing that reopens Track A beam/`best_of` unless a real STT bug blocks  
- Reopening Track B compound coverage or Track C generalization for score chasing  
- Declaring READY while median post-speech stays multi-second  
- **Starting Holdout v3 before Final Latency Check PASSes**
