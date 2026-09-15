# V5_MEASUREMENT_PARITY

- generated: 2026-09-13T23:39:12.539787+00:00
- semantic_index_ready: **False**   alias_matrix: **False** (0 rows)
- compound clips: 15

## Coverage on the identical 15 clips

| run | gold parts hit | coverage_by_part | wrong_intent |
|---|---|---|---|
| recorded | 15/41 | 0.3659 | 12 |
| live_prod_parity | 16/41 | 0.3902 | 12 |
| live_bare | 7/41 | 0.1707 | 3 |

## First divergence vs the recorded v4 trace

- `live_bare` (what variant A did): {'DETECTION': 10, 'ACCEPT_DECISION': 1, 'NONE': 4}
- `live_prod_parity` (forced detection, as v4 ran): {'CANDIDATE_POOL': 5, 'ACCEPT_DECISION': 1, 'NONE': 9}
- clips reproduced exactly by prod parity: **9/15**

## VERDICT

- coverage gap cause: **HARNESS_MISMATCH_FORCED_DETECTION** (forced detection closes 112.4% of the 0.1707 -> 0.3659 gap)
- residual live-vs-recorded difference: **PRESENT_BUT_AGGREGATE_NEUTRAL** (6 clip(s))
- previous `A_current_live` baseline: **INVALID**

| clip | rec type | bare detector | forced | bare stage | prod stage |
|---|---|---|---|---|---|
| fuh4_076 | compound | compound | False | NONE | NONE |
| fuh4_077 | compound | compound | False | NONE | NONE |
| fuh4_078 | compound | compound | False | NONE | NONE |
| fuh4_079 | compound | single | True | DETECTION | NONE |
| fuh4_080 | compound | single | True | DETECTION | NONE |
| fuh4_081 | compound | single | True | DETECTION | CANDIDATE_POOL |
| fuh4_082 | compound | single | True | DETECTION | CANDIDATE_POOL |
| fuh4_083 | compound | compound | False | ACCEPT_DECISION | ACCEPT_DECISION |
| fuh4_084 | compound | single | True | DETECTION | NONE |
| fuh4_085 | compound | single | True | DETECTION | CANDIDATE_POOL |
| fuh4_086 | compound | single | True | DETECTION | NONE |
| fuh4_087 | compound | compound | False | NONE | NONE |
| fuh4_088 | compound | single | True | DETECTION | CANDIDATE_POOL |
| fuh4_089 | compound | single | True | DETECTION | NONE |
| fuh4_090 | compound | single | True | DETECTION | CANDIDATE_POOL |

## Stage 1 — detection (the whole coverage gap)

The bare detector classifies **10 of 15** labeled-compound clips as SINGLE. `resolve_compound_question` then returns at line 230 of `compound_question_pipeline.py` with `used_compound_path=False` and no selected intents. `interview_e2e_loopback.run_clip` never hits this because it overrides the detector for labeled packs (`ComplexityDetection("compound", 0.9, ..., ("labeled_compound_pack",))`).

Clips broken by this: `fuh4_079`, `fuh4_080`, `fuh4_081`, `fuh4_082`, `fuh4_084`, `fuh4_085`, `fuh4_086`, `fuh4_088`, `fuh4_089`, `fuh4_090`

## Stage 3-4 — residual live-vs-recorded differences under forced detection

| clip | stage | detail | recorded selected | live selected |
|---|---|---|---|---|
| fuh4_081 | CANDIDATE_POOL | 'Your pick for our workload and Y': recorded=hard.langgraph_vs_n8n_vs_python@0.363 live=gen.what_do_you_know_about_us@0.461 | cv.vector_db | cv.vector_db |
| fuh4_082 | CANDIDATE_POOL | 'When is each enough?': recorded=hard.supervisor_vs_router@0.452 live=hard.why_agent_not_rag@0.623 | hard.agent_terms_difference | hard.agent_terms_difference, hard.why_agent_not_rag |
| fuh4_083 | ACCEPT_DECISION | 'How they matter for this role?': recorded_accept=True live_accept=False live_reason=below_answer_threshold | cv.education, gen.why_this_role | cv.education |
| fuh4_085 | CANDIDATE_POOL | 'If we need Cuba needs': recorded=tech.gpu_sizing@0.327 live=tech.sklearn_vs_neural@0.364 | tech.container_vs_vm | tech.container_vs_vm |
| fuh4_088 | CANDIDATE_POOL | 'STT internals, local Whisper rationale': recorded=proj.kiosk.describe@0.579 live=tech.what_is_whisper@0.704 | tech.what_is_whisper | tech.what_is_whisper, tech.overfitting |
| fuh4_090 | CANDIDATE_POOL | 'Embedings, cosine search, metadata filters': recorded=tech.metadata_filtering@0.559 live=tech.embeddings@0.66 | hard.hybrid_when, tech.hybrid_search | tech.embeddings, tech.hybrid_search |

### Fragment-level component breakdown for those clips

Live `top_matches` on the recorded fragment, showing where the cosine term sits.

**fuh4_081** — `Your vector DB history, then your pick for our workload and Y.`

| fragment | intent | score | semantic | lexical | keyword | mode | accept |
|---|---|---:|---:|---:|---:|---|---|
| Your vector DB history | cv.vector_db | 0.9059 | 0.0 | 0.8824 | 1.0 | strong | True |
| Your vector DB history | tech.vector_db_choice | 0.7486 | 0.0 | 0.8108 | 0.5 | strong | False (ambiguous_margin) |
| Your vector DB history | hard.graph_vs_vector | 0.7316 | 0.0 | 0.7895 | 0.5 | strong | False (ambiguous_margin) |
| Your pick for our workload and Y | proj.similarity.threshold | 0.4741 | 0.0 | 0.5926 | 0.0 | weak | False (low_score) |
| Your pick for our workload and Y | hard.langgraph_vs_n8n_vs_python | 0.4267 | 0.0 | 0.5333 | 0.0 | weak | False (low_score) |
| Your pick for our workload and Y | hard.why_not_chroma_prod | 0.4013 | 0.0 | 0.5016 | 0.0 | weak | False (low_score) |

**fuh4_082** — `Role of an orchestrator versus a lone tool-calling model. When is each enough?`

| fragment | intent | score | semantic | lexical | keyword | mode | accept |
|---|---|---:|---:|---:|---:|---|---|
| Role of an orchestrator versus a lone tool-calling model | hard.agent_terms_difference | 0.6461 | 0.0 | 0.4576 | 0.5 | weak | True |
| Role of an orchestrator versus a lone tool-calling model | tech.tool_calling | 0.5429 | 0.0 | 0.6786 | 0.5 | weak | False (below_answer_threshold) |
| Role of an orchestrator versus a lone tool-calling model | tech.agent_orchestrator | 0.5196 | 0.0 | 0.2995 | 0.5 | weak | False (low_score) |
| When is each enough? | hard.why_agent_not_rag | 0.6227 | 0.0 | 0.7784 | 0.0 | weak | True |
| When is each enough? | hard.why_not_chroma_prod | 0.5647 | 0.0 | 0.7059 | 0.0 | weak | False (below_answer_threshold) |
| When is each enough? | tech.tfidf_vs_embeddings | 0.5647 | 0.0 | 0.7059 | 0.0 | weak | False (below_answer_threshold) |

**fuh4_083** — `Education, certification, and how they matter for this role.`

| fragment | intent | score | semantic | lexical | keyword | mode | accept |
|---|---|---:|---:|---:|---:|---|---|
| Education, certification | cv.education | 0.9 | 0.0 | 1.0 | 0.5 | strong | True |
| Education, certification | cv.why_leaving | 0.5565 | 0.0 | 0.6957 | 0.0 | weak | False (below_answer_threshold) |
| Education, certification | intro.current_role | 0.5333 | 0.0 | 0.6667 | 0.0 | weak | False (below_answer_threshold) |
| How they matter for this role? | gen.why_this_role | 0.5383 | 0.0 | 0.5478 | 0.5 | weak | False (below_answer_threshold) |
| How they matter for this role? | gen.strengths | 0.3725 | 0.0 | 0.4657 | 0.0 | weak | False (low_score) |
| How they matter for this role? | cv.why_hire_you | 0.3683 | 0.0 | 0.4604 | 0.0 | weak | False (low_score) |

**fuh4_085** — `Docker value, container versus VM, and if we need Cuba needs.`

| fragment | intent | score | semantic | lexical | keyword | mode | accept |
|---|---|---:|---:|---:|---:|---|---|
| Docker value, container versus VM | tech.container_vs_vm | 0.896 | 0.0 | 0.82 | 1.0 | strong | True |
| Docker value, container versus VM | tech.docker_why | 0.584 | 0.0 | 0.48 | 1.0 | weak | False (ambiguous_margin) |
| Docker value, container versus VM | tech.rag_vs_finetuning | 0.4068 | 0.0 | 0.3335 | 0.5 | weak | False (low_score) |
| If we need Cuba needs | tech.sklearn_vs_neural | 0.364 | 0.0 | 0.455 | 0.0 | weak | False (low_score) |
| If we need Cuba needs | tech.kubernetes | 0.36 | 0.0 | 0.45 | 0.0 | weak | False (low_score) |
| If we need Cuba needs | tech.explain_ai_project_structure | 0.336 | 0.0 | 0.42 | 0.0 | weak | False (low_score) |

**fuh4_088** — `STT internals, local Whisper rationale, and accuracy acceptance test.`

| fragment | intent | score | semantic | lexical | keyword | mode | accept |
|---|---|---:|---:|---:|---:|---|---|
| STT internals, local Whisper rationale | tech.what_is_whisper | 0.704 | 0.0 | 0.48 | 1.0 | strong | True |
| STT internals, local Whisper rationale | cv.whisper_experience | 0.6029 | 0.0 | 0.3537 | 1.0 | weak | False (ambiguous_margin) |
| STT internals, local Whisper rationale | proj.kiosk.describe | 0.5888 | 0.0 | 0.336 | 1.0 | weak | False (ambiguous_margin) |
| Accuracy acceptance test | tech.overfitting | 0.5622 | 0.0 | 0.7027 | 0.0 | weak | False (below_answer_threshold) |
| Accuracy acceptance test | tech.precision_recall | 0.4136 | 0.0 | 0.392 | 0.5 | weak | False (low_score) |
| Accuracy acceptance test | proj.early_warning.metric | 0.4055 | 0.0 | 0.3818 | 0.5 | weak | False (low_score) |

**fuh4_090** — `Embedings, cosine search, metadata filters, and hybrid search tradeoffs cover all four.`

| fragment | intent | score | semantic | lexical | keyword | mode | accept |
|---|---|---:|---:|---:|---:|---|---|
| Embedings, cosine search, metadata filters | tech.embeddings | 0.584 | 0.0 | 0.48 | 1.0 | weak | True |
| Embedings, cosine search, metadata filters | tech.metadata_filtering | 0.4561 | 0.0 | 0.4451 | 0.5 | weak | False (low_score) |
| Embedings, cosine search, metadata filters | cv.chromadb | 0.4558 | 0.0 | 0.5698 | 0.0 | weak | False (low_score) |
| Hybrid search tradeoffs cover all four | tech.hybrid_search | 0.66 | 0.0 | 0.7 | 0.5 | weak | True |
| Hybrid search tradeoffs cover all four | hard.hybrid_when | 0.5853 | 0.0 | 0.6067 | 0.5 | weak | False (ambiguous_margin) |
| Hybrid search tradeoffs cover all four | gen.remote_onsite | 0.3045 | 0.0 | 0.2557 | 0.5 | weak | False (low_score) |

## Consequence for the Phase B baseline

`A_current_live` in `V5_COMPOUND_COUNTERFACTUALS` is **INVALID**: variant A called resolve_compound_question() with no detection, so the bare detector classified 10 of 15 labeled-compound clips as SINGLE and the pipeline returned immediately with used_compound_path=False and no selected intents. The v4 production harness forces ComplexityDetection('compound', 0.9, ...) for labeled compound packs. Variants B-I were additionally fed the RECORDED sub_questions, i.e. the output of that forced decomposition, so A and B-I never shared a starting condition.

Invalidated: A_current_live coverage_by_part; A_current_live wrong_intent (the Phase B guard baseline); every A-vs-variant delta in V5_COMPOUND_COUNTERFACTUALS.

