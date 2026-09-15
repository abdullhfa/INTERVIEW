# FINAL PRE-V3 PERFORMANCE & RELIABILITY HARDENING — one-shot runner
#
# Run from the backend folder:
#     cd "C:\Users\aalsa\OneDrive\Desktop\interview (2)\interview11\backend"
#     powershell -ExecutionPolicy Bypass -File .\scripts\run_pre_v3_hardening.ps1
#
# Test order is Phase 16 and is NOT optional:
#   unit tests -> short_length -> compound_dev(40) -> short_length x3
#   -> compound latency sample -> Final Latency Check
# Holdout v3 is never started by this script.

$ErrorActionPreference = "Continue"
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$log = ".\reports\pre_v3_hardening_run.log"
New-Item -ItemType Directory -Force -Path ".\reports" | Out-Null
"=== PRE-V3 HARDENING RUN $(Get-Date -Format o) ===" | Out-File $log

function Step($name, $block) {
    Write-Host ""
    Write-Host "=============================================================="
    Write-Host "== $name"
    Write-Host "=============================================================="
    "`n=== $name $(Get-Date -Format o) ===" | Out-File $log -Append
    & $block 2>&1 | Tee-Object -FilePath $log -Append
}

# 0. Equivalence snapshot — proves the optimizations moved no decision.
Step "0/7 equivalence dump (lexical)" { & $py scripts\verify_intent_equivalence.py --dump reports\EQUIV_AFTER.json }
Step "0b/7 equivalence dump (semantic)" { & $py scripts\verify_intent_equivalence.py --dump reports\EQUIV_AFTER_SEM.json --semantic }

# 1. Unit tests
Step "1/7 unit tests" { & $py -m pytest -q }

# 2. Simple cohort
Step "2/7 short_length" { & $py scripts\run_suite.py short_length }
Copy-Item .\reports\LENGTH_SHORT_REGRESSION_REPORT.json .\reports\_pre_v3_short_run1.json -Force

# 3. Compound cohort (full 40)
Step "3/7 compound_dev (40)" { & $py scripts\run_suite.py compound_dev }
Copy-Item .\reports\COMPOUND_DEV_REPORT.json .\reports\_pre_v3_compound_run1.json -Force

# 4. Determinism: repeat short_length 3x
foreach ($i in 2..4) {
    Step "4/7 short_length repeat $i" { & $py scripts\run_suite.py short_length }
    Copy-Item .\reports\LENGTH_SHORT_REGRESSION_REPORT.json ".\reports\_pre_v3_short_run$i.json" -Force
}

# 5. Compound latency sample (second compound run)
Step "5/7 compound_dev repeat" { & $py scripts\run_suite.py compound_dev }
Copy-Item .\reports\COMPOUND_DEV_REPORT.json .\reports\_pre_v3_compound_run2.json -Force

# 6. Final Latency Check (evaluator v2 — cohort-specific gates)
Step "6/7 Final Latency Check" { & $py scripts\final_latency_check.py }

# 7. Hardening report
Step "7/7 hardening report" { & $py scripts\write_pre_v3_report.py }

Write-Host ""
Write-Host "Done. Read reports\FINAL_PRE_V3_LATENCY_HARDENING.md"
Write-Host "If the verdict is NOT_READY_FOR_V3, do NOT start Holdout v3."
Write-Host ""
Write-Host "A run only counts as a gate if it is warm-valid: warm-up finished"
Write-Host "before the first clip and every scored clip saw the alias matrix."
Write-Host "The evaluator now fails the gate otherwise."
Write-Host ""
Write-Host "Only if this run is READY and both cohorts are warm-valid:"
Write-Host "  python scripts\spotcheck_holdout_v3_voices.py"
Write-Host "  python scripts\synthesize_final_unseen_holdout_v3.py"
Write-Host "  python scripts\lock_holdout_v3.py --write"
Write-Host "  python scripts\lock_holdout_v3.py          # independent verify, then touch nothing"
Write-Host "  python scripts\run_holdout_v3.py           # one shot"
