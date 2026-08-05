#Requires -Version 5.1
<# 직전 연도 생산 gate를 통과한 다음 한 연도만 시작한다. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2022','2023','2024','2025')]
    [string]$Year,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$ApprovedBy,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$ApprovalQueueId = (
        'mfa_r2_prod_safe_body_2021_2025_20260803'
    ),
    [ValidatePattern('^$|^[A-Za-z0-9._-]+$')]
    [string]$PriorExecutionQueueId = '',
    [ValidatePattern('^$|^[A-Za-z0-9._-]+$')]
    [string]$ExecutionQueueId = '',
    [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$priorByYear = @{
    '2022' = '2021'; '2023' = '2022';
    '2024' = '2023'; '2025' = '2024'
}
$PriorYear = [string]$priorByYear[$Year]
if ([string]::IsNullOrWhiteSpace($ExecutionQueueId)) {
    $ExecutionQueueId = "mfa_r2_prod_safe_body_${Year}_20260803"
}
$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PriorExecutionQueueId)) {
    $PriorExecutionQueueId = (
        "mfa_r2_prod_safe_body_${PriorYear}_20260803"
    )
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
    Join-Path $PSScriptRoot 'preflight_production_next_year_gate.ps1'
) -PriorYear $PriorYear -ExecutionQueueId $PriorExecutionQueueId
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$sourceReport = Join-Path $projectRoot (
    "outputs\reports\PREFLIGHT_source_contract_${Year}_before_mfa.json"
)
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
    Join-Path $PSScriptRoot 'verify_production_source_contract.ps1'
) -Year $Year -RequireMorphYearSuccess -Output $sourceReport
if ($LASTEXITCODE -ne 0) {
    Write-Host (
        "$Year morph_search.v3/source contract가 준비되지 않음. " +
        'prepare_production_year_before_mfa.ps1을 먼저 실행할 것.'
    ) -ForegroundColor Red
    exit $LASTEXITCODE
}
$reviewRoot = Join-Path $projectRoot (
    "outputs\reviews\mfa_exclusions_queue_$ApprovalQueueId"
)
$args = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    (Join-Path $PSScriptRoot 'start_full_mfa_after_review.ps1'),
    '-ApprovedBy', $ApprovedBy,
    '-QueueId', $ExecutionQueueId,
    '-ReviewRoot', $reviewRoot,
    '-YearsCsv', $Year
)
if ($PreflightOnly) { $args += '-PreflightOnly' }
& powershell.exe @args
exit $LASTEXITCODE
