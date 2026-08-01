<# Single-purpose entrypoint: prepare exclusion review for 2020 only. #>
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_prod_2020_20260801'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$verify = Join-Path $PSScriptRoot 'verify_production_source_contract.ps1'
$prepare = Join-Path $PSScriptRoot 'prepare_full_mfa_approval_reviews.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verify `
    -Year 2020 -RequireMorphYearSuccess
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $prepare `
    -QueueId $QueueId -Years 2020 `
    -AudioRecoveryPlan (Join-Path $projectRoot `
        'outputs\reports\PLAN_2020_wav_duration_recovery_20260801.csv')
exit $LASTEXITCODE
