# Debt: canonical question replaces spoken transcript (open)

**Status:** documented · not fixing before interview (frozen live path)  
**Severity:** operational / interview defense — matching can be correct while display hides STT truth

## Symptom

The live «السؤال» pane shows the **matched bank entry question** (e.g. `Which framework do you use, and why?`) instead of the interviewer utterance (e.g. `What platforms can you use to build Agentic AI workflows?`).

When aliases intentionally share an entry (`tech.which_framework`), both a smart alias hit and a wrong match to the same entry look identical on screen.

## Path (measured from code)

1. [`question_bank.py`](../app/services/question_bank.py) **:627** — after bank-guided understanding:
   `repaired = understanding.canonical_question` (entry title), not the raw transcript.
   (Same statement was ~614 before post-files6 line drift; verify with
   `Select-String -Pattern "repaired = understanding.canonical_question"`.)
2. That repaired text flows as `raw_utterance` / `asked`.
3. [`answer_generator.py`](../app/services/answer_generator.py) **:2806** —
   `_answer_from_bank(..., question=asked)` puts it on `GeneratedAnswer.question`.
4. [`session_manager.py`](../app/services/session_manager.py) **:228** —
   `publish_live_answer` sets `session.current_question = answer.question`.
5. Frontend polls `current_question` (~1.5s) into the question pane.

Replacement happens **after** answer generation, not at question accept.

## Interview workaround

Watch status/`TRANSCRIPT_CREATED` at finalize — that is the true STT text **before** canonical replace.

## Later fix (design required)

Keep spoken transcript in the primary question pane; show matched entry id/title as a secondary line. Touches bank repair → generator → session → UI; needs an explicit design pass and must not reopen frozen intent/match thresholds.

## Related

Same blind spot as the live `agantic` incident: STT error invisible if only the bank title is shown.
