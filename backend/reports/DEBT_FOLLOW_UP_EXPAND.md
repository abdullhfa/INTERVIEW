# Debt: LIVE_FOLLOW_UP_EXPAND (open)

**Status:** built · measured · **default OFF** · not freeze-ready  
**Freeze target (when closed):** `V7_FOLLOW_UP`  
**Flag:** `LIVE_FOLLOW_UP_EXPAND` default `off` (`backend/app/services/follow_up_expand.py`)  
**Standing freeze:** V6.5 bank coverage untouched; this debt must not reopen bank/intent thresholds.

Measured 2026-09-17 on experiment copy (post V6.5).  
Report: `backend/reports/_follow_up_pairs_audit.txt`

---

## Verdict from evidence

Feature design (hint · subject-append · weak-cap) is directionally correct.
Default stays **off** until all exit gates pass. Do not ship “on” from golden + T3 alone.

Session close state (2026-09-17): V6.5 frozen & pushed (341 entries, warm `strong_and_wrong = 0`); this feature built, disabled by evidence; exit gates written below. Outside code: update CV with LangGraph / FAISS / pgvector (freeze debt #9).

---

## Implementation order

1. **Move expand out of `match` → answer-path only** (solves ج and د coupling first).
2. **Immediately re-measure gate (د)** on the same live clips — do **not** wait until hint work is done. If answer count is still short after decoupling, the cause is elsewhere; stop before investing in the hint rule.
3. Then replace the length hint with absent-domain-subject (أ), re-run the **same 20 pairs**, compare to baseline below.

---

## Baseline pair audit (before hint change)

Same 20 pairs in `scripts/audit_follow_up_pairs.py` / `_follow_up_pairs_audit.txt`:

| metric | value |
|---|---:|
| value added (expand → correct intent) | **7** |
| wrong intent (any confidence) | **0** |
| wrong intent at `strong` | **0** |
| false fire changing intent on standalones | **0** |
| missed true follow-ups | **2** |

After the new hint rule: measure on **these same pairs**. Expect miss **> 2** — that rise is **by design**, not a regression. Without this baseline written down, the comparison becomes an impression.

---

## Blocking items (priority order)

### 1 — PRIMARY: deleted answers (functional regression)

Live same clips (`gdev_013`…`016`):

| | answers shown |
|---|---:|
| OFF | **4 / 4** |
| ON  | **2 / 4** |

`Define embeddings.` → expand appended prior subject `rag` → wrong bank intent → gate `LISTEN` / `NON_QUESTION_IGNORED`.

Silence in a live interview is worse than a slow answer and worse than a wrong answer the candidate can ignore. **This is the first exit blocker — ahead of latency.**

### 2 — Coupling: expand inside `question_bank.match`

`match` feeds three independent decisions today:

1. STT second-pass / `assess_match_risk` / `simple_need_second_pass` (prelim inside `_transcribe_interviewer`)
2. Question gate override (`bank_match.is_strong`)
3. Answer generation

The original spec assumed (3) only. Wrong expand reaching `LISTEN` is that coupling, not an answer-path bug alone.

**Architectural correction (required for exit):** move expand out of `match` to **one call site on the answer path only**. Then STT and question gate always see raw `match`. Latency gate (ج) largely falls out (work once, not 2–3×).

### 3 — Hint rule: length was the wrong signal

`len(content) <= 4` measures shortness; the need is **absent domain subject**.

| utterance | content | verdict |
|---|---|---|
| `Define embeddings.` | `{embeddings}` domain | **standalone** |
| `Explain LoRA.` | `{lora}` | **standalone** |
| `Are you use in your project?` | `{project}` generic | **follow-up** |
| `What about it?` | `{}` | **follow-up** |

Rule: hint only when the utterance does **not** already carry its own domain noun (reuse `_DISTINCTIVE_TERMS` / `distinctive_to_alias` / `_content_tokens` — no new lexicon). **Length must not appear in the rule.**

### 4 — Bias: prefer miss over false fire

Tightening the hint will raise missed true follow-ups above the baseline of 2/20. **Accept that deliberately.**

- Missed follow-up → candidate rephrases (~2 s).
- False fire → deleted answer or flipped intent.

Spec forbids later “coverage chase” that reintroduces false fire.

---

## Exit gates (all required)

| # | Gate | Requirement | When to check |
|---|---|---|---|
| **د** | **Answers shown** | **ON answer count = OFF answer count on the same clips** | **Immediately after step 1 (decouple)** — before hint work |
| ج | Live `bank=` / `total=` | ON within ~50 ms of OFF on same clips | After step 1 (should largely be free) |
| أ | Hint = absent domain subject | No length rule; short domain questions stay standalone | After hint change |
| ب | No wrong expand → flipped intent at `strong` | `wrong_intent_STRONG` = 0 on **same 20 pairs**; report value/miss vs baseline 7 / 2 | After hint change |

Also retain:

- `pytest` with flag ON ≡ OFF counts (currently 277/4).
- Warm self-match `strong_and_wrong = 0` (does **not** prove expand safety — history-less).
- Golden: prior agentic → `Are you use in your project?` → agentic-family / `weak`.

When all pass: default `on`, write freeze `V7_FOLLOW_UP`, close this debt.

---

## Weak-path note (measured)

`answer_generator`: `weak` still reaches LLM with `reference_answer` (not abstain).  
Gate path: expansion-sourced weak/wrong can still become `NON_QUESTION_IGNORED` **before** generation — that is how answers disappear. Answer-path-only expand removes that channel.

---

## Hard ban — do not re-couple

Expand must **not** touch any of:

- `question_bank.match` (no expand hook / `_apply_follow_up_expand` / `_skip_follow_up` inside it)
- `prelim` / bank match inside `_transcribe_interviewer`
- the question-gate path that keys off `bank_match.is_strong`

One answer-path call site only. “Cleaner to put it back in `match`” is explicitly forbidden — that is how deleted answers returned.

---

## Do not

- Turn default `on` without gates أ–د.
- Skip re-checking (د) right after decoupling.
- Loosen hint toward length / `<= N tokens` to recover missed follow-ups.
- Chase T3 / self-match as expand safety evidence.
- Treat miss rising above baseline 2 as a regression to “fix” by widening the hint.
