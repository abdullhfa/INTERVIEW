# V5 INTERVIEW_PHRASE_RECOVERY

**Verdict:** `INTERVIEW_PHRASE_RECOVERY_PASS`

## Pipeline
`STT → ACRONYM → TECH_TERM → INTERVIEW_PHRASE → MAIN_REQUEST → INTENT`

## Summary
| metric | value |
|---|---:|
| n | 42 |
| pass_rate | 1.0 |
| phrase_recovery_accuracy | 1.0 (23/23) |
| false_phrase_corrections | 0 |
| passing_cases_broken | 0 |
| intent_before → after | 21 → 24 / 24 |
| HC_wrong | 0 |
| latency_delta_ms_avg | 22.39 |

## Critical
- `PHR_and_you_plan` raw=`and you plan your project` → `Explain your project` intent=cv.projects_overview pass=True
- `PHR_how_plan_keep` raw=`How do you plan your project?` → `How do you plan your project?` intent=cv.projects_overview pass=True
- `PHR_boat_yourself` raw=`tell me a boat yourself` → `Tell me about yourself` intent=intro.tell_me_about_yourself pass=True

## Rules
- Multi-signal scoring: phonetic + semantic + bank + structure
- Rewrite only when combined score and margin clear
- `How do you plan your project?` must not become `Explain your project`
- raw_transcript always retained alongside recovered_transcript
