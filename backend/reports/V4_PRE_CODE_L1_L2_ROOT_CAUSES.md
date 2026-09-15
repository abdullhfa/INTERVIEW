# v4 pre-code analysis — L1 & L2 root causes

Source: official VALID `FINAL_UNSEEN_HOLDOUT_V3_*`. **Analysis only — no code changes.**
Immutable: **HC=0**, **meaning_lost=0**.

Suite design signal (all scored clips): semantic recovery **triggered 86 / applied 0**.

---

## L1 — indirect_paraphrase failures (12/15)

### Per-case table

| id | gold | lex (id/mode/score) | hyb top1 | gold in lists | abstain detail | surface cues that should help |
|---|---|---|---|---|---|---|
| `fuh3_091` | `tech.hallucination_what` | `tech.rag_access_control` / weak / 0.358 | `tech.rag_access_control` @ 0.371 (lex=0.524, sem=0.264) | sem:absent; hyb:absent | abstain_low_confidence: score=0.371 agree=0.880 | tech.hallucination_what:makes things up |
| `fuh3_092` | `tech.reindex_embedding_change` | `∅` / none / 0.0 | `hard.change_embedding` @ 0.388 (lex=0.414, sem=0.315) | sem:absent; hyb:absent | abstain_low_confidence: score=0.388 agree=0.880 | tech.reindex_embedding_change:swapped, tech.reindex_embedding_change:re-index, tech.reindex_embedding_change:answers changed |
| `fuh3_093` | `hard.cost_spike` | `hard.least_privilege_example` / weak / 0.34 | `hard.least_privilege_example` @ 0.35 (lex=0.467, sem=0.389) | sem#1; hyb:absent | abstain_low_confidence: score=0.350 agree=0.880 | hard.cost_spike:invoice, hard.cost_spike:tripled, hard.cost_spike:finance |
| `fuh3_094` | `hard.wrong_chunk` | `∅` / none / 0.0 | `tech.rag_what` @ 0.555 (lex=0.438, sem=0.405) | sem#2; hyb:absent | abstain_low_confidence: score=0.555 agree=0.583 | hard.wrong_chunk:wrong paragraph, hard.wrong_chunk:right document |
| `fuh3_096` | `hard.citation_lie`, `tech.faithfulness_check` | `gen.why_this_role` / weak / 0.319 | `tech.what_is_ml` @ 0.313 (lex=0.615, sem=0.415) | sem:absent; hyb#2 final=0.312 | abstain_low_confidence: score=0.313 agree=0.615 | hard.citation_lie:where the sentence came from, tech.faithfulness_check:where the sentence came from |
| `fuh3_097` | `tech.i_dont_know_too_often` | `∅` / none / 0.0 | `proj.early_warning.result` @ 0.376 (lex=0.44, sem=0.414) | sem#5; hyb:absent | abstain_low_confidence: score=0.376 agree=0.850 | tech.i_dont_know_too_often:cannot help, tech.i_dont_know_too_often:ignoring |
| `fuh3_098` | `tech.rag_access_control` | `tech.conflict_of_interest_scenario` / weak / 0.35 | `tech.rag_access_control` @ 0.418 (lex=0.495, sem=0.415) | sem#1; hyb#1 final=0.418 | abstain_low_confidence: score=0.418 agree=0.556 | tech.rag_access_control:procurement, tech.rag_access_control:human resources, tech.rag_access_control:read a file |
| `fuh3_099` | `hard.agent_loop`, `hard.timeout_vs_steps` | `hard.accountability` / weak / 0.299 | `hard.agent_stop_tools` @ 0.337 (lex=0.495, sem=0.436) | sem#2; hyb:absent | abstain_low_confidence: score=0.337 agree=0.556 | hard.agent_loop:round in circles, hard.agent_loop:gave up, hard.timeout_vs_steps:four minutes |
| `fuh3_100` | `tech.good_enough_to_launch`, `hard.evaluate_rag` | `proj.early_warning.metric` / weak / 0.367 | `tech.wer` @ 0.337 (lex=0.418, sem=0.399) | sem#1; hyb:absent | abstain_low_confidence: score=0.337 agree=0.556 | tech.good_enough_to_launch:pilot, tech.good_enough_to_launch:actually good, hard.evaluate_rag:whether it is actually good, hard.evaluate_rag:pilot |
| `fuh3_101` | `tech.temperature`, `hard.prompt_versioning` | `∅` / none / 0.0 | `tech.temperature` @ 0.337 (lex=0.565, sem=0.478) | sem:absent; hyb#1 final=0.337 | abstain_low_confidence: score=0.337 agree=0.629 | tech.temperature:different answers, tech.temperature:same afternoon, hard.prompt_versioning:same thing, hard.prompt_versioning:different answers |
| `fuh3_102` | `tech.audio_retention`, `tech.external_api_risks` | `proj.kiosk.describe` / weak / 0.429 | `tech.audio_retention` @ 0.41 (lex=0.517, sem=0.326) | sem#1; hyb#1 final=0.41 | abstain_low_confidence: score=0.410 agree=0.880 | tech.audio_retention:recordings, tech.audio_retention:leaving the building, tech.audio_retention:lawyers, tech.external_api_risks:leaving the building |
| `fuh3_104` | `gen.motivation` | `∅` / none / 0.0 | `proj.similarity.challenges` @ 0.399 (lex=0.5, sem=0.42) | sem:absent; hyb#5 final=0.345 | abstain_low_confidence: score=0.399 agree=0.880 | gen.motivation:hired you, gen.motivation:interesting problems |

### Readable case notes

- **`fuh3_091`** → gold `tech.hallucination_what`
  - Original: Our head of department keeps saying the assistant 'makes things up'. What is he actually describing?
  - ASR: Our head of department keeps saying the assistant makes things up. What is he actually describing?
  - Lexical: `tech.rag_access_control` (weak, score=0.358); hyb#1=`tech.rag_access_control` final=0.371; agree=0.88; lists: sem:absent; hyb:absent
  - sem top3: ['tech.responsibility', 'hard.accountability', 'tech.rag_access_control']
  - hyb top3: ['tech.rag_access_control', 'gen.non_technical_stakeholders', 'hard.agent_loop']
- **`fuh3_092`** → gold `tech.reindex_embedding_change`
  - Original: Staff complain the answers changed after we swapped something last month, and nobody reindexed anything.
  - ASR: Staff complained the answers changed after we swapped something last month, and nobody re-indexed anything.
  - Lexical: `None` (None, score=0.0); hyb#1=`hard.change_embedding` final=0.388; agree=0.88; lists: sem:absent; hyb:absent
  - sem top3: ['hard.change_embedding', 'tech.rag_two_phases', 'tech.rag_vs_finetuning']
  - hyb top3: ['hard.change_embedding', 'hard.streaming_vs_validate', 'gen.anything_else']
- **`fuh3_093`** → gold `hard.cost_spike`
  - Original: Finance noticed the invoice tripled between Tuesday and Wednesday with no new users.
  - ASR: Finance notice the invoice tripled between Tuesday and Wednesday with no new users. Finance notice, they invoice tripled between Tuesday and Wednesday with no new users.
  - Lexical: `hard.least_privilege_example` (weak, score=0.34); hyb#1=`hard.least_privilege_example` final=0.35; agree=0.88; lists: sem#1; hyb:absent
  - sem top3: ['hard.cost_spike', 'cv.knet_role', 'gen.what_do_you_know_about_us']
  - hyb top3: ['hard.least_privilege_example', 'cv.csharp_dotnet', 'cv.kuwait_projects_and_llm']
- **`fuh3_094`** → gold `hard.wrong_chunk`
  - Original: We keep getting the right document but the wrong paragraph out of it.
  - ASR: We keep in the right document, but the wrong paragraph out of it.
  - Lexical: `None` (None, score=0.0); hyb#1=`tech.rag_what` final=0.555; agree=0.583; lists: sem#2; hyb:absent
  - sem top3: ['hard.conflicting_docs', 'hard.wrong_chunk', 'hard.citation_lie']
  - hyb top3: ['tech.rag_what', 'tech.knowledge_graph_what', 'tech.rag_vs_finetuning']
- **`fuh3_096`** → gold `hard.citation_lie`, `tech.faithfulness_check`
  - Original: The assistant answers beautifully but nobody can tell where the sentence came from.
  - ASR: The assistant answers beautifully, but nobody can tell where the sentence came from.
  - Lexical: `gen.why_this_role` (weak, score=0.319); hyb#1=`tech.what_is_ml` final=0.313; agree=0.615; lists: sem:absent; hyb#2 final=0.312
  - sem top3: ['tech.responsibility', 'hard.accountability', 'hard.hitl_where']
  - hyb top3: ['tech.what_is_ml', 'hard.citation_lie', 'hard.wrong_chunk']
- **`fuh3_097`** → gold `tech.i_dont_know_too_often`
  - Original: It keeps saying it cannot help, and the staff have started ignoring it entirely.
  - ASR: It keeps saying it cannot help, and the staff have started ignoring it entirely.
  - Lexical: `None` (None, score=0.0); hyb#1=`proj.early_warning.result` final=0.376; agree=0.85; lists: sem#5; hyb:absent
  - sem top3: ['proj.helpdesk.challenges', 'gen.feedback', 'tech.responsibility']
  - hyb top3: ['proj.early_warning.result', 'hard.agent_loop', 'hard.citation_lie']
- **`fuh3_098`** → gold `tech.rag_access_control`
  - Original: Somebody from procurement was able to read a file that belongs to human resources.
  - ASR: Somebody from procurement was able to read a file that belongs to human resources.
  - Lexical: `tech.conflict_of_interest_scenario` (weak, score=0.35); hyb#1=`tech.rag_access_control` final=0.418; agree=0.556; lists: sem#1; hyb#1 final=0.418
  - sem top3: ['tech.rag_access_control', 'tech.prompt_injection_supplier', 'tech.conflict_of_interest_scenario']
  - hyb top3: ['tech.rag_access_control', 'cv.csharp_dotnet', 'tech.conflict_of_interest_scenario']
- **`fuh3_099`** → gold `hard.agent_loop`, `hard.timeout_vs_steps`
  - Original: The assistant went round in circles for four minutes and then gave up on its own.
  - ASR: The assistant went round in circles for four minutes and they gave up on its own.
  - Lexical: `hard.accountability` (weak, score=0.299); hyb#1=`hard.agent_stop_tools` final=0.337; agree=0.556; lists: sem#2; hyb:absent
  - sem top3: ['hard.hitl_where', 'hard.agent_loop', 'hard.timeout_vs_steps']
  - hyb top3: ['hard.agent_stop_tools', 'hard.wrong_tool', 'hard.accountability']
- **`fuh3_100`** → gold `tech.good_enough_to_launch`, `hard.evaluate_rag`
  - Original: We ran a pilot and everyone liked it, but I have no idea how to say whether it is actually good.
  - ASR: We were in a pilot, and everyone liked it, but I have no idea how to say whether it is actually good.
  - Lexical: `proj.early_warning.metric` (weak, score=0.367); hyb#1=`tech.wer` final=0.337; agree=0.556; lists: sem#1; hyb:absent
  - sem top3: ['tech.good_enough_to_launch', 'proj.early_warning.metric', 'hard.evaluate_rag']
  - hyb top3: ['tech.wer', 'tech.transcription_quality', 'gen.feedback']
- **`fuh3_101`** → gold `tech.temperature`, `hard.prompt_versioning`
  - Original: Two people ask the same thing and get two different answers on the same afternoon.
  - ASR: Do people ask the same thing and get to different answers on the same afternoon?
  - Lexical: `None` (None, score=0.0); hyb#1=`tech.temperature` final=0.337; agree=0.629; lists: sem:absent; hyb#1 final=0.337
  - sem top3: ['tech.i_dont_know_too_often', 'hard.faithfulness_vs_relevance', 'hard.similarity_vs_qgen_arch']
  - hyb top3: ['tech.temperature', 'cv.why_hire_you', 'hard.streaming_vs_validate']
- **`fuh3_102`** → gold `tech.audio_retention`, `tech.external_api_risks`
  - Original: Our lawyers are nervous about anything leaving the building, including the recordings.
  - ASR: Our lawyers are nervous about anything leaving the building, including the recordings.
  - Lexical: `proj.kiosk.describe` (weak, score=0.429); hyb#1=`tech.audio_retention` final=0.41; agree=0.88; lists: sem#1; hyb#1 final=0.41
  - sem top3: ['tech.audio_retention', 'proj.kiosk.challenges', 'cv.guardrails']
  - hyb top3: ['tech.audio_retention', 'proj.kiosk.describe', 'tech.whisper_vs_cloud']
- **`fuh3_104`** → gold `gen.motivation`
  - Original: If we hired you and then stopped giving you interesting problems, what would happen?
  - ASR: If we hired you, then you stop giving you interesting problems, what would happen?
  - Lexical: `None` (None, score=0.0); hyb#1=`proj.similarity.challenges` final=0.399; agree=0.88; lists: sem:absent; hyb#5 final=0.345
  - sem top3: ['gen.biggest_challenge_career', 'gen.questions_for_us', 'cv.why_hire_you']
  - hyb top3: ['proj.similarity.challenges', 'gen.why_this_role', 'gen.weaknesses']

### L1 pattern counts (n=12)

- **abstain_low_confidence:** 12/12
- **agreement_ge_0.75:** 6/12
- **gold_absent_both_lists:** 2/12
- **gold_in_hybrid_still_abstain:** 5/12
- **gold_in_sem_not_hybrid:** 5/12
- **hyb_top1_final_ge_0.5:** 1/12
- **hyb_top1_final_lt_0.5:** 11/12
- **lex_none:** 5/12
- **lex_weak:** 7/12
- **surface_cues_present:** 12/12

### Root causes L1 (shared patterns only)

1. **Weak / empty lexical coverage on scenario paraphrases**  
   Bank aliases expect definitional phrasing; holdout uses workplace stories. Lexical is `none` or `weak` on a wrong neighbor.

2. **Surface cues present, but lexical never elevates them**  
   **12/12** transcripts already contain human-obvious symptom phrases, yet lex is weak/∅. Only **2/12** miss gold in *both* recovery lists — so pure “never retrieves” is minority; the bigger split is demotion / non-apply.

3. **Hybrid demotion when semantic already finds gold**  
   **5/12**: gold is in semantic top-k but **not** in hybrid top-k (e.g. `hard.cost_spike` as sem#1 → hyb prefers `hard.least_privilege_example`). Ranking/mix, not only retrieval.

4. **Gold in hybrid still abstains (apply gate)**  
   **5/12** have gold somewhere in hybrid top-5 but still `abstain_low_confidence` — final score / agreement path never **applies**. Thresholding *and* wrong top1 both matter.

5. **Recovery is paid abstain, not a paraphrase bridge**  
   All 12 fail via `abstain_low_confidence`; **11/12** have hyb top1 final &lt;0.5. High agreement (≥0.75) often means agreement with the *current wrong weak match*, not that recovery found gold. Aligns with suite **triggered ≫ applied**.

### L1 design read on `triggered / applied = 0`

| Hypothesis | Supported by L1? |
|---|---|
| Semantic retrieval alone is weak (gold absent both lists) | Partial — **2/12** |
| Hybrid demotes a usable semantic hit | **Yes** — **5/12** |
| Threshold / apply blocks usable hybrid hits | **Yes** — **5/12**; hyb top1 final &lt;0.5 in **11/12** |
| Recovery over-triggers on hopeless weak lexical | **Yes** — every miss paid recovery then abstained |
| Latency-only explanation | **No** — design: call without apply |

---

## L2 — compound (15 clips; intent_ok 15/15; mean gold-part coverage ≈ 0.556)

Note: coverage is **gold-intent** coverage, not merely part count. Clips can show `matched == requested` yet cov &lt; 1.0 when accepted intents are the wrong family.

### Per-question part table

| id | cov | req/det/matched/answered | missed part(s) | trailing pattern | locus | dropped / weak candidates |
|---|---|---|---|---|---|---|
| `fuh3_089` | 0.0 | 2/2/0/0 | Give me the difference between the two draft libraries, save which you use; Tell me whether the flow still works without stairs? | which-pick, say/tell-followon | matching:low_score | Give me the difference between the two dra→`tech.library_framework_platform` (low_score/0.439); Tell me whether the flow still works witho→`hard.remove_llm_from_rag` (low_score/0.319) |
| `fuh3_080` | 0.3333 | 2/2/1/1 | What do you do about it? | what-do-you-do | answer_too_short, matching:no_match | What do you do about it?→`None` (no_match/0.0) |
| `fuh3_083` | 0.3333 | 2/2/1/1 | How any of that helps you hear? | how-followon | answer_too_short, matching:below_answer_threshold | How any of that helps you hear?→`cv.certifications` (below_answer_threshold/0.525) |
| `fuh3_084` | 0.3333 | 2/2/2/2 | — | — | wrong_intent_on_accepted_parts | — |
| `fuh3_076` | 0.5 | 2/2/1/1 | When would you bother adding one? | when-clause | answer_too_short, matching:low_score | When would you bother adding one?→`gen.anything_else` (low_score/0.373) |
| `fuh3_078` | 0.5 | 2/2/1/1 | Say what you do when a document will not fit inside one | say/tell-followon | answer_too_short, matching:below_answer_threshold | Say what you do when a document will not f→`tech.prompt_injection_supplier` (below_answer_threshold/0.564) |
| `fuh3_081` | 0.5 | 2/2/1/1 | Say which one you would pick for us | which-pick | answer_too_short, matching:low_score | Say which one you would pick for us→`gen.strengths` (low_score/0.493) |
| `fuh3_090` | 0.5 | 2/2/2/2 | — | — | matching:ambiguous_margin, wrong_intent_on_accepted_parts | Cover four things for me, what embeddings →`tech.metadata_filtering` (ambiguous_margin/0.663) |
| `fuh3_079` | 0.6667 | 3/3/3/3 | — | — | wrong_intent_on_accepted_parts | — |
| `fuh3_085` | 0.6667 | 2/2/2/2 | — | — | wrong_intent_on_accepted_parts | — |
| `fuh3_086` | 0.6667 | 3/3/3/3 | — | — | dedupe, wrong_intent_on_accepted_parts | — |
| `fuh3_087` | 0.6667 | 2/2/2/2 | — | — | wrong_intent_on_accepted_parts | — |
| `fuh3_088` | 0.6667 | 3/3/3/3 | — | — | wrong_intent_on_accepted_parts | — |
| `fuh3_077` | 1.0 | 3/3/3/3 | — | — | ok_or_unclassified | — |
| `fuh3_082` | 1.0 | 2/2/2/2 | When a single tool-using model is already enough? | when-clause | matching:low_score | When a single tool-using model is already →`hard.tool_schema` (low_score/0.501) |

### Locus / trailing tallies

- Cases with det≥req but matched&lt;req (**seg OK, match fail**): **6**
- Trailing patterns among missed: `{'when-clause': 2, 'say/tell-followon': 2, 'what-do-you-do': 1, 'which-pick': 2, 'how-followon': 1}`
- Locus counts (clips can contribute multiple tags):
  - `matching:low_score`: 10
  - `wrong_intent_on_accepted_parts`: 7
  - `answer_too_short`: 5
  - `matching:below_answer_threshold`: 4
  - `matching:no_match`: 2
  - `dedupe`: 1
  - `matching:ambiguous_margin`: 1

### Root causes L2

1. **Trailing / dependent-clause loss after a strong first part**  
   Patterns: `when would you…`, `what do you do…`, `which would you pick…`, `say what you do…`. Part1 often matches strongly (`reranking`, `overfitting`, `vector_db`); part2 drops as `low_score` / `no_match` / `below_answer_threshold`, frequently collapsing to `gen.anything_else` / `gen.strengths`.

2. **Pronoun / ellipsis matching failure (not segmentation)**  
   Segmentation usually finds the right part count (`detected ≈ requested`). Failure is **matching** on under-specified follow-ons (`adding one`, `fit inside one`, `pick for us`).

3. **Wrong-intent acceptance lowers gold coverage even when all parts “match”**  
   Several clips have full req/det/matched/answered but cov 0.33–0.67 — accepted intents are adjacent/wrong. That is a **matching quality** issue, not merge.

4. **Dedupe / merge are secondary**  
   Duplicates rare. `ANSWER_TOO_SHORT` appears after partial select, not as the primary drop mechanism.

5. **STT garble amplifies worst case**  
   Lowest cov (0.0) coincides with damaged transcript (`stairs` / draft libraries); still, clean trailing-clause misses dominate the mean.

---

## Fixed protection rules

- **HC wrong = 0** — hard gate, no exceptions for coverage.
- **meaning_lost = 0** — hard gate.
- Do **not** force-apply hybrid top1 solely to raise intent rate.
- Do **not** retune on v3 clips; v4 requires a **new** unseen pack + one-shot path.

## Hypotheses only (no implementation)

### H-L1
1. Improve recovery **candidate generation** for symptom/scenario language (without global strong-threshold cuts).
2. Inspect **hybrid demotion** of correct semantic hits (act/dist/exist / neighbor bias on `hard.*`).
3. Tighten **when** recovery triggers *or* enable conservative **apply** when gold-like symptom cues + margin allow — measured offline.
4. Limited explicit symptom→intent patterns as A/B hypotheses (e.g. *makes things up* → hallucination) on held-out paraphrases.

### H-L2
1. Carry **head noun / prior-part topic** into trailing-clause matching.
2. Dependent WH-clause acceptance when part1 is strong same-topic (margin-aware), without accepting unrelated intents.
3. Revisit second-part `low_score` / `below_answer_threshold` floors separately from first-part floors.
4. Latency: expect partial win from fewer useless outer recoveries (L1) before Whisper micro-opts.

## Success criteria for v4

| Gate | Target |
|---|---|
| Indirect / overall intent | ≥ **0.92** |
| Compound gold-part coverage | ≥ **0.90** |
| HC wrong | **0** |
| meaning_lost | **0** |
| Latency | re-measure after L1/L2; expect partial drop if recovery applies or triggers less |

## Bottom line

L1 is a **paraphrase→candidate→apply** failure chain (not STT). L2 is mostly **trailing-clause matching** (not segmentation). The `triggered 86 / applied 0` signal is the design key for v4: recovery currently buys abstain safety, not generalization.

