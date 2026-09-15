# V5 Live Interview Assistant — FREEZE

**Status:** FROZEN  
**Freeze ID:** V5_LIVE_INTERVIEW_ASSISTANT_2026_09_15  
**Frozen at:** 2026-09-15T08:19:35.598650+00:00  
**Restorable snapshot:** interview11_FROZEN_V5_20260915 (sibling of interview11)

## Policy
- Further changes: **bug-fix only**
- Forbidden: threshold/weight/alias chasing, HC/accept relaxation, STT/VAD retune for metrics, B8/B9, new ranking/compound/routing research

## Frozen pipeline
STT → TECH_TERM_RECOVERY → MAIN_REQUEST_EXTRACTION (long/indirect) → match → answer  
HC guards / strong thresholds / accept gate / mode ladder: **unchanged**  
Question banks + live frontend: **frozen with this snapshot**

## Accepted improvements
- MAIN_REQUEST_EXTRACTION: MAIN_REQUEST_EXTRACTION_PASS
- SHORT_TECH_RECOVERY: SHORT_TECH_RECOVERY_PASS

## Baseline — V5 150 Voice Stress E2E
| metric | value |
|---|---:|
| verdict | PASS_150_VOICE_STRESS_E2E |
| pass_rate | 0.9 |
| intent_rate | 0.9 |
| STT rate | 0.9533 |
| HC wrong | 0 |
| audio_fail | 0 |
| median_post_speech_ms | 1420.8 |
| short | 0.9444 |
| long | 1.0 |
| compound | 0.9667 |
| Indian | 0.92 |
| Jordanian | 0.96 |
| Emirati | 0.82 |

## KNOWN_LIMITATIONS
- Unrecoverable short STT garble (e.g. V5A_148) — abstain over guess
- Ambiguous tech tokens (Zundra/Zandra vs Chroma/LangGraph) — no force-correct
- Holdout v3/v4 remain historical NO-GO; this freeze is practical readiness + V5 150 E2E

## Restore
Copy interview11_FROZEN_V5_20260915 over interview11, then keep the live .venv and rontend/node_modules (not stored in the snapshot).

## Lock
SHA256 fingerprints: 
eports/V5_LIVE_ASSISTANT_FREEZE.lock.json (32 files)
