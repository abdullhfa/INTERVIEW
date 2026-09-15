# V5 TECH_ACRONYM_RECOVERY

**Verdict:** `ACRONYM_RECOVERY_PASS`

## Summary
| metric | value |
|---|---:|
| n | 42 |
| pass_rate | 1.0 |
| recover_rate | 1.0 (27/27) |
| clean unchanged | 15/15 |
| intent (gold) | 13/13 |
| false_llama | 0 |
| hc_wrong | 0 |

## Critical
- `ACR_lalam` raw=`What is the Lalam?` → `What is the LLM?` intent=`tech.what_is_llm` pass=True
- `ACR_lalam_short` raw=`What is Lalam?` → `What is LLM?` intent=`tech.what_is_llm` pass=True
- `ACR_el_el_em` raw=`What is el el em?` → `What is LLM?` intent=`tech.what_is_llm` pass=True
- `ACR_llm_clean` raw=`What is LLM?` → `What is LLM?` intent=`tech.what_is_llm` pass=True
