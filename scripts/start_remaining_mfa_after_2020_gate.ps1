<# Start 2021-2025 only after the exact 2020 Gate B passes. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovedBy,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_prod_safe_body_2021_2025_20260803',
    [ValidateSet('2021')]
    [string]$Year = '2021',
    [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$gateQueueId = 'mfa_r2_prod_2020_export_20260803'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
    Join-Path $PSScriptRoot 'preflight_2020_gate_b.ps1'
) -QueueId $gateQueueId
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$start = Join-Path $PSScriptRoot 'start_full_mfa_after_review.ps1'
$args = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $start,
    '-ApprovedBy', $ApprovedBy,
    '-QueueId', $QueueId,
    '-YearsCsv', $Year
)
if ($PreflightOnly) { $args += '-PreflightOnly' }
& powershell.exe @args
exit $LASTEXITCODE
