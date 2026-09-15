# V5 — pre-code root cause analysis

**Created:** 2026-09-13T23:17:57.268918+00:00
**Scope:** measurement only. No production code was modified.
**Baseline:** v4 unseen holdout — outcome VALID, `all_gates_pass = false`, NO-GO.

| Gate | v4 | required |
|---|---:|---:|
| Intent accuracy | 0.825 | >= 0.92 |
| HC wrong | 0 | = 0 |
| Meaning lost | 0.0 | <= 0.01 |
| Compound gold-part coverage | 0.3944 | >= 0.90 |
| Simple median | 977 ms | <= 1500 |
| Compound median | 1019 ms | <= 2000 |

---

## 1. The headline finding: v4 failed *safely*, not *wrongly*

All 21 non-compound intent failures, and every compound shortfall, were
**abstentions** (`abstain_low_confidence`). Not one was a confident wrong answer.
That is why HC wrong = 0 and meaning_lost = 0 held while accuracy fell to 0.825.

The system's failure mode is *silence*, not *hallucination*. That matters for v5:
the safety invariants are not under threat from the fixes we need; the work is to
convert justified silence into justified answers.

---

## 2. Why pre-one-shot was 0.9375 and unseen was 0.3944

This is not the same question asked more times. **compound-dev and holdout v4
compound are different question styles.**

| pack | clauses/clip | interrogative words/clip | **verbless clauses** |
|---|---:|---:|---:|
| compound-dev | 2.22 | 2.95 | **9 (10%)** |
| holdout-v3-compound | 2.8 | 3.67 | **2 (5%)** |
| holdout-v4-compound | 2.73 | 0.8 | **25 (61%)** |

compound-dev and v3 asked things like:

> *What is re-ranking, and when would you bother adding one?*
> *What is overfitting, how do you spot it, and what do you do about it?*

v4 asked things like:

> *Define overfitting, detection signals, and your mitigation playbook.*
> *Docker value, container versus VM, and if we need Kubernetes.*
> *STT internals, local Whisper rationale, and accuracy acceptance test.*
> *Early Warning Project Story, KPI, and Ministry Outcome.*

**61% of v4 compound clauses contain no verb and no interrogative** — they are
telegraphic noun phrases. In compound-dev that figure is 10%.

The decomposer splits on `and / then / ,` followed by an interrogative or an
imperative verb (`why|how|what|when|say|point|explain|define|give|name`). Against
a noun-phrase enumeration those patterns do not fire, so the utterance is
under-split, and whatever does get matched is matched from a fragment with no
action word to disambiguate *what is X* from *when do you use X*.

**Honest reading, both directions:**

1. This is a real generalization gap. Interviewers do speak in shorthand lists,
   and the system cannot currently parse them. Worth fixing.
2. But 0.9375 -> 0.3944 overstates a *regression*. No earlier pack contained this
   style, so v4 measured a capability that was never built or validated. The drop
   is mostly a new, untested axis, not decayed behaviour.

v5 must decide deliberately: is telegraphic compound in scope? If yes it is a
feature, not a bug fix, and the v5 pack must contain both styles so we can tell
them apart.

---

## 3. Compound — every missing gold part, one bucket each

15 clips, 41 gold parts, 15 hit, **26 missing** (coverage by part 0.3659).

| bucket | parts | share |
|---|---:|---:|
| MATCHING_RANKING | 11 | 42% |
| SEGMENTATION_FAILURE | 7 | 27% |
| STT_DISTORTION | 5 | 19% |
| CANDIDATE_GENERATION | 2 | 8% |
| ACCEPTANCE_GATE | 1 | 4% |

Segmentation adequacy (sub-questions split vs gold parts): **under-split 7**, equal 7, over-split 1 of 15.

### The two mechanisms behind MATCHING_RANKING

**(a) Granularity siblings.** The clause is isolated correctly and then matched to
the *definition* sibling instead of the *scenario* sibling:

| clip | clause | gold | chosen |
|---|---|---|---|
| fuh4_076 | "say when hybrid search needs it" | `hard.hybrid_when` | `tech.hybrid_search` |
| fuh4_087 | "when to halt tool loops" | `hard.agent_stop_tools` | `hard.agent_loop` |
| fuh4_090 | "hybrid search tradeoffs" | `tech.hybrid_search` | `hard.hybrid_when` (inverted!) |

Note fuh4_090 picks the *when* entry where gold wanted the *what* entry — the
confusion runs in both directions, so it is not a fixed preference for
definitions. It is that a verbless fragment carries no action signal at all, and
`_granularity_penalty` keys off `detect_intent(...)`, which returns nothing for a
noun phrase.

**(b) Facet fabrication.** When decomposition fails, the facet path invents
sub-questions out of the bank that were never spoken. fuh4_084 is the clearest:

> transcript: *"Compt injection sources, PDF risk, and guardrails that's locked."*
> sub-questions the pipeline created: *"What are guardrails?"*,
> *"Where exactly do you put the human in the loop?"*,
> *"Who is allowed to save a generated question?"*

None of those three phrases is in the utterance. All three matched, all three are
non-gold, coverage 0.0. **12 non-gold intents were selected across the compound
cohort** — that is the mechanism that produces them.

---

## 4. Intent (non-compound) — 21 failures

| bucket | clips |
|---|---:|
| SEMANTIC_PROFILE_QUALITY | 9 |
| STT | 5 |
| HYBRID_RANKING | 5 |
| APPLY_GATE | 2 |

By question type: indirect_paraphrase 10, short 3, very_long 3,
follow_up_contextual 3, ultra_short 2.

**SEMANTIC_PROFILE_QUALITY is the largest bucket (9/21):** the gold intent appears
in *neither* the semantic top-5 *nor* the hybrid top-5. No ranking or gate change
can reach those — the concept is not retrievable from its profile at all. Examples:

| clip | spoken | gold never retrieved |
|---|---|---|
| fuh4_094 | scenario phrasing | applied: none |
| fuh4_101 | scenario phrasing | applied: none |
| fuh4_103 | scenario phrasing | applied: none |
| fuh4_111 | follow-up | applied: none |

STT accounts for 5/21 and is genuinely out of scope for v5 (Track A is frozen and
the model is non-deterministic). HYBRID_RANKING 5, APPLY_GATE 2.

STT fidelity across all 120 clips: {'>=95': 87, '85-94': 18, '70-84': 12, '<70': 3}.

---

## 5. V5 ROOT CAUSE VERDICT

```
COMPOUND dominant cause
    MATCHING_RANKING          11/26 missing parts  (42%)
    SEGMENTATION_FAILURE       7/26                (27%)
  both downstream of one upstream fact: 61% of v4 compound clauses are
  verbless noun phrases, a style absent from every pack the pipeline was
  built and validated on.

INTENT dominant cause
    SEMANTIC_PROFILE_QUALITY   9/21 failures       (43%)
  gold reaches neither semantic nor hybrid top-5 — retrieval, not ranking,
  not the gate.

RECOMMENDED FIRST EXPERIMENT
  Compound variant H — action-type inference for verbless clauses.
  Infer the missing action signal (what / when / how / why / compare) for a
  clause that has none, from clause-internal structure only (head noun vs
  relational phrase vs conditional marker), then let the EXISTING granularity
  penalty do its job. Measurement-only counterfactual first, over all 15
  compound clips, scored per gold part.
  Rationale: it addresses 11/26 directly and is a precondition for the 7/26
  segmentation cases to be matched correctly even once they are split.

EXPECTED UPSIDE
  compound coverage 0.366 -> 0.55-0.70 by part, IF action inference lands on
  the granularity siblings. It does NOT on its own reach 0.90; segmentation
  of noun-phrase enumerations is a second, separate experiment.
  Intent: 0 — this experiment does not touch the intent path.

SAFETY RISK
  Low but not zero. Action inference changes which sibling is preferred; a
  wrong inference swaps one wrong intent for another, it does not create a
  confident wrong answer, because the compound accept thresholds and the mode
  ladder are untouched. Guard to enforce in the experiment: wrong_intent must
  not increase, and the 12 existing non-gold selections must not grow.

LATENCY RISK
  Negligible. Action inference is a regex/POS-shaped decision on a short
  string, inside a stage whose p50 is already ~1 ms. Compound median has
  980 ms of headroom.
```

---

## 6. What I recommend NOT doing next

- **Do not widen Variant D.** The v4 trailing clauses are not the shape it was
  designed for: they are verbless noun phrases, not pronoun-bearing follow-ups.
  Only 1 of the 26 missing parts is a pronoun-context case.
- **Do not touch the apply gate.** It accounts for 2 of 21 intent failures.
- **Do not touch hybrid ranking again yet.** 5 of 21. The v4 blob-proxy fix stays.
- **Do not treat the 9 SEMANTIC_PROFILE_QUALITY cases as a weights problem.**
  They need profile coverage of scenario phrasing, which is a separate track with
  its own overfitting risk — generalized phrasing only, never unseen text.

## 7. Open question for you before Phase B

Is telegraphic / noun-phrase compound in scope for v5?

- **If yes** — Phase B runs the action-inference and enumeration-splitting
  counterfactuals, and the v5 pack carries both styles in known proportions so
  the two can be scored separately.
- **If no** — compound coverage should be re-baselined on interrogative compound
  only, and the v5 pack should say so explicitly. The 0.3944 figure would then be
  measuring something we chose not to build.

I am not making that call unilaterally: it changes what the gate means.

