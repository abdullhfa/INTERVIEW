# V5 Final Bank-Guided Interview Understanding

**Verdict:** `BANK_GUIDED_INTERVIEW_READY`

## Principle
STT is a raw hypothesis. Question Bank + lexicon + context decide intent.

## Pipeline
`STT RAW → BANK CANDIDATE SEARCH → ACRONYM → TECH → PHRASE → MRE → BANK INTENT → ANSWER`

## Metrics
| metric | value |
|---|---:|
| n | 91 |
| pass_rate | 0.9451 |
| bank_match_accuracy | 0.9405 |
| acronym_recovery | 1.0 |
| phrase_recovery | 1.0 |
| personal_question_accuracy | 0.9091 |
| AI_question_accuracy | 0.8235 |
| project_question_accuracy | 1.0 |
| indirect_accuracy | 0.6667 |
| short_accuracy | 0.9286 |
| long_accuracy | 0.0 |
| false_corrections | 0 |
| HC_wrong | 0 |
| latency_delta_ms_avg | 2732.74 |

## Critical
- `BG_lalam` raw=`What is the Lalam?` → canonical=`What is a large language model?` intent=`tech.what_is_llm` pass=True
- `BG_and_you_plan` raw=`and you plan your project` → canonical=`What projects have you worked on?` intent=`cv.projects_overview` pass=True
- `BG_how_plan_project` raw=`How do you plan your project?` → canonical=`How do you plan your project?` intent=`None` pass=True
- `BG_llm_clean` raw=`What is LLM?` → canonical=`What is a large language model?` intent=`tech.what_is_llm` pass=True

## Dual transcript
Logs keep `raw_transcript`, `recovered_transcript`, `canonical_question`, `intent_id`.

## Offline expansion
Draft paraphrases: `reports/V5_BANK_EXPANSION_DRAFT.json` (validation required before production).
