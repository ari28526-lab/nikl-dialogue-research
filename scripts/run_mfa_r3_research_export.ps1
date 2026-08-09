#Requires -Version 5.1
<# Export an already completed r3 MFA database to research 6-tier TextGrids. #>
param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year = '2020',
    [ValidateRange(1, 16)]
    [int]$Workers = 4,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\ari30\miniforge3\envs\mfa\python.exe'
$policyPath = Join-Path $projectRoot 'config\mfa_r3_runner_v1.json'
$policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$releaseId = [string]$policy.release_id
$releaseRoot = [IO.Path]::GetFullPath([string]$policy.release_root)
$commonRoot = [IO.Path]::GetFullPath(
    [string]$policy.common_pron_release_root
)
$alignmentContract = Join-Path $commonRoot (
    '04_alignment_contracts\{0}\ALIGNMENT_CONTRACT_{0}.json' -f $Year
)
$alignmentMarker = Join-Path $releaseRoot "markers\ALIGN_DONE_$Year.json"
$database = Join-Path $releaseRoot "temp\$Year\$Year.db"
$labRoot = Join-Path $releaseRoot 'corpus'
$outputRoot = Join-Path $releaseRoot 'research_6tier'
$reviewRoot = Join-Path $projectRoot (
    'outputs\reviews\mfa_r3_post_mfa_reconciliation_{0}_{1}' -f
    $releaseId, $Year
)
$approvalManifest = Join-Path $reviewRoot '06_RESEARCHER_APPROVAL.json'
$approvedContract = Join-Path $reviewRoot '05_APPROVED_EXCLUSIONS.json'
$reportName = $(
    if ($PreflightOnly) { 'PREFLIGHT' } else { 'EXPORT' }
)
$report = Join-Path $projectRoot (
    'outputs\reports\{0}_mfa_r3_research_6tier_{1}_{2}.json' -f
    $reportName, $Year, (Get-Date -Format 'yyyyMMdd_HHmmss')
)

foreach ($required in @(
    $python, $alignmentContract, $alignmentMarker, $database,
    $approvalManifest, $approvedContract
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 r3 export 입력 없음: $required"
    }
}
$alignment = Get-Content -LiteralPath $alignmentContract -Raw -Encoding UTF8 |
    ConvertFrom-Json
$yearInputPath = [string]$alignment.inputs.year_input_contract.path
if (-not (Test-Path -LiteralPath $yearInputPath -PathType Leaf)) {
    throw "r3 year input contract 없음: $yearInputPath"
}
$yearInput = Get-Content -LiteralPath $yearInputPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$searchMasterRoot = [string](
    $yearInput.inputs.frozen_search_master_inventory.root
)
if (-not (Test-Path -LiteralPath $searchMasterRoot -PathType Container)) {
    throw "frozen search master root 없음: $searchMasterRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $labRoot $Year) `
    -PathType Container)) {
    throw "r3 active LAB root 없음: $(Join-Path $labRoot $Year)"
}
$approval = Get-Content -LiteralPath $approvalManifest -Raw -Encoding UTF8 |
    ConvertFrom-Json
if (
    [string]$approval.schema_version -ne
        'mfa_r3_post_mfa_explicit_approval.v1' -or
    [string]$approval.status -ne 'approved' -or
    [string]$approval.year -ne $Year -or
    [bool]$approval.automatic_approval_performed
) {
    throw 'r3 post-MFA explicit approval identity/status 불일치'
}
$approvedContractSha = (
    Get-FileHash -LiteralPath $approvedContract -Algorithm SHA256
).Hash.ToLowerInvariant()
if ($approvedContractSha -ne (
    [string]$approval.approved_exclusions_contract.sha256
).ToLowerInvariant()) {
    throw 'r3 approved exclusions contract SHA-256 불일치'
}

function Enable-SleepGuard {
    if (-not ('MfaR3ExportSleepGuard' -as [type])) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MfaR3ExportSleepGuard {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
    }
    $state = [convert]::ToUInt32('80000001', 16)
    if ([MfaR3ExportSleepGuard]::SetThreadExecutionState($state) -eq 0) {
        throw 'Windows sleep guard 활성화 실패'
    }
}

function Disable-SleepGuard {
    if ('MfaR3ExportSleepGuard' -as [type]) {
        $state = [convert]::ToUInt32('80000000', 16)
        [void][MfaR3ExportSleepGuard]::SetThreadExecutionState($state)
    }
}

$lockRoot = Join-Path $releaseRoot 'locks'
$lockPath = Join-Path $lockRoot "research_export_$Year.lock.json"
New-Item -ItemType Directory -Force -Path $lockRoot | Out-Null
if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
    $existing = $null
    try {
        $existing = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
    } catch {
        throw "읽을 수 없는 r3 export lock: $lockPath"
    }
    $existingPid = 0
    $isLive = [int]::TryParse(
        [string]$existing.owner_pid, [ref]$existingPid
    ) -and $existingPid -gt 0 -and $null -ne (
        Get-Process -Id $existingPid -ErrorAction SilentlyContinue
    )
    if ($isLive) {
        throw "이미 실행 중인 r3 export가 있음(pid=$existingPid)"
    }
    $archive = Join-Path $lockRoot 'stale'
    New-Item -ItemType Directory -Force -Path $archive | Out-Null
    Move-Item -LiteralPath $lockPath -Destination (
        Join-Path $archive (
            'research_export_{0}_{1}.lock.json' -f
            $Year, (Get-Date -Format 'yyyyMMdd_HHmmss')
        )
    )
}
$lockValue = [ordered]@{
    schema_version = 'mfa_r3_research_export_lock.v1'
    status = 'owned'
    owner_pid = $PID
    year = $Year
    release_id = $releaseId
    preflight_only = [bool]$PreflightOnly
    started_at = [DateTimeOffset]::Now.ToString('o')
}
$lockJson = $lockValue | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText(
    $lockPath,
    $lockJson + [Environment]::NewLine,
    [Text.UTF8Encoding]::new($false)
)

Enable-SleepGuard
try {
    $arguments = @(
        (Join-Path $PSScriptRoot 'python\export_mfa_db_research_6tier.py'),
        '--db', $database,
        '--year', $Year,
        '--search-master-root', $searchMasterRoot,
        '--output-root', $outputRoot,
        '--acoustic-model', [string]$alignment.models.acoustic.path,
        '--alignment-contract', $alignmentContract,
        '--alignment-marker', $alignmentMarker,
        '--approved-exclusions-contract', $approvedContract,
        '--lab-root', $labRoot,
        '--workers', [string]$Workers,
        '--report', $report
    )
    if ($PreflightOnly) { $arguments += '--preflight-only' }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "r3 $Year research export 실패(exit=$LASTEXITCODE): $report"
    }
    $result = Get-Content -LiteralPath $report -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $expectedStatus = $(
        if ($PreflightOnly) { 'preflight_passed' } else { 'success' }
    )
    if ([string]$result.status -ne $expectedStatus) {
        throw "r3 export report status 불일치: $($result.status)"
    }
    if ($PreflightOnly) {
        Write-Host "[GO] r3 $Year research export preflight: $report" `
            -ForegroundColor Green
    } else {
        Write-Host "[OK] r3 $Year research 6-tier export: $report" `
            -ForegroundColor Green
    }
} finally {
    Disable-SleepGuard
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        $resolvedLock = [IO.Path]::GetFullPath($lockPath)
        $resolvedLockRoot = [IO.Path]::GetFullPath($lockRoot)
        if ($resolvedLock.StartsWith(
            $resolvedLockRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            Remove-Item -LiteralPath $resolvedLock -Force
        }
    }
}
