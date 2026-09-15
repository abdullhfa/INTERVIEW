# V4 step 6 — PRE-ONE-SHOT HARDENING (no new features, no holdout run)
#
#     cd backend
#     powershell -ExecutionPolicy Bypass -File .\scripts\run_pre_v4_hardening.ps1
#
# Or:
#     python scripts/v4_step6_pre_oneshot.py --run-all
#
# Holdout v4 one-shot is NEVER started here (that is step 7).

$ErrorActionPreference = "Continue"
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "Starting V4 step 6 pre-one-shot verification..."
& $py scripts\v4_step6_pre_oneshot.py --run-all
exit $LASTEXITCODE
