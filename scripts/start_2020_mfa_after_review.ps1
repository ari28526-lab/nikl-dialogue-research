<# Single-purpose entrypoint: start only 2020 after approved exclusions. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovedBy,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_prod_2020_20260801',
    [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$verify = Join-Path $PSScriptRoot 'verify_production_source_contract.ps1'
$start = Join-Path $PSScriptRoot 'start_full_mfa_after_review.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verify `
    -Year 2020 -RequireMorphYearSuccess
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$args = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $start,
    '-ApprovedBy', $ApprovedBy,
    '-QueueId', $QueueId,
    '-Years', '2020'
)
if ($PreflightOnly) { $args += '-PreflightOnly' }
& powershell.exe @args
exit $LASTEXITCODE
