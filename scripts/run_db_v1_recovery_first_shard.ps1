param(
    [switch]$PreflightOnly,
    [string]$ApprovalContract = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\ari30\miniforge3\envs\mfa\python.exe'
$preflight = Join-Path $PSScriptRoot 'python\preflight_db_v1_recovery_first_shard.py'
$report = Join-Path $projectRoot 'outputs\reports\PREFLIGHT_db_v1_recovery_D4_20260815.json'
$package = Join-Path $projectRoot (
    'outputs\releases\nikl_dialogue_research_db_v1_recovery_d0_d4_20260815'
)

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "pipeline Python 없음: $python"
}
if (-not (Test-Path -LiteralPath $preflight -PathType Leaf)) {
    throw "D4 preflight 없음: $preflight"
}

$arguments = @(
    $preflight,
    '--project-root', $projectRoot,
    '--package', $package,
    '--report', $report
)
if (-not [string]::IsNullOrWhiteSpace($ApprovalContract)) {
    $arguments += @('--approval-contract', [IO.Path]::GetFullPath($ApprovalContract))
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "D4 read-only preflight 실패(exit=$LASTEXITCODE): $report"
}

if ($PreflightOnly) {
    Write-Host "[GO] D4 read-only preflight passed; Gate remains closed: $report" -ForegroundColor Green
    exit 0
}
if ([string]::IsNullOrWhiteSpace($ApprovalContract)) {
    throw 'D4 corpus 생성/MFA 승인 계약 없음. 기존 r3 본체는 변경하지 않고 Gate에서 정지함.'
}

Write-Host '[GO] D4 scope-bound approval contract verified.' -ForegroundColor Green
Write-Host '[STOP] D0-D4 objective ends before corpus materialization/MFA; no files were copied and MFA was not run.' -ForegroundColor Yellow
Write-Host 'Next action requires a separately reviewed materializer/runner invocation.' -ForegroundColor Yellow
