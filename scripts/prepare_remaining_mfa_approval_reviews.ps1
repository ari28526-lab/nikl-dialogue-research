<# After Gate B, prepare exclusion reviews for 2021-2025 only. #>
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_prod_2021_2025_20260803'
)
$ErrorActionPreference = 'Stop'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
    Join-Path $PSScriptRoot 'preflight_2020_gate_b.ps1'
)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
    Join-Path $PSScriptRoot 'prepare_full_mfa_approval_reviews.ps1'
) -QueueId $QueueId -Years 2021,2022,2023,2024,2025
exit $LASTEXITCODE
