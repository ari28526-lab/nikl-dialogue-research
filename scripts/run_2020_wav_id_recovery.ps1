# Build the reviewed 2020 WAV-ID recovery corpus without changing source WAVs.
[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$ApprovedBy = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WavRecoverySleepGuard {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
function Enable-WavRecoverySleepGuard {
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED; the display may turn off.
    $result = [WavRecoverySleepGuard]::SetThreadExecutionState(
        [uint32]2147483649
    )
    if ($result -eq 0) {
        throw 'Windows 절전 억제 설정 실패'
    }
}
function Disable-WavRecoverySleepGuard {
    # ES_CONTINUOUS only: restore the thread's normal execution state.
    [void][WavRecoverySleepGuard]::SetThreadExecutionState(
        [uint32]2147483648
    )
}
$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$sourceWavRoot = Join-Path (
    Resolve-ConfiguredPath ([string]$config.wav)
) 'individual'
$outputWavRoot = Resolve-ConfiguredPath (
    [string]$config.mfa_wav_corpus_2020
)
$archiveBase = Resolve-ConfiguredPath ([string]$config.wav_recovery_archive)
$searchMasterRoot = Resolve-ConfiguredPath (
    [string]$config.pre_mfa_search_master
)
$plan = Join-Path $projectRoot (
    'outputs\reports\PLAN_2020_wav_duration_recovery_20260801.csv'
)
$reviewRoot = Join-Path $projectRoot (
    'outputs\2020_wav_id_recovery_review_20260802'
)
$reviewManifest = Join-Path $reviewRoot 'REVIEW_MANIFEST.json'
$reviewDecisions = Join-Path $reviewRoot 'REVIEW_DECISIONS.json'
$builder = Join-Path $PSScriptRoot 'python\build_wav_recovery_corpus.py'
$report = Join-Path $projectRoot (
    'outputs\reports\' + $(if ($Apply) {
        'APPLY_2020_wav_recovery_corpus_20260802.json'
    } else {
        'PREFLIGHT_2020_wav_recovery_corpus_20260802.json'
    })
)
$progress = Join-Path $projectRoot (
    'logs\wav_recovery_2020_20260802_progress.jsonl'
)
$transcript = Join-Path $projectRoot (
    'logs\wav_recovery_2020_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log'
)

foreach ($required in @(
    $python, $plan, $reviewManifest, $reviewDecisions, $builder,
    $searchMasterRoot, $sourceWavRoot, $archiveBase
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "필수 입력 없음: $required"
    }
}
if ($Apply -and [string]::IsNullOrWhiteSpace($ApprovedBy)) {
    throw '-Apply에는 -ApprovedBy 연구자 ID가 필요함'
}
if ($Apply) {
    $tracked = @(& git -C $projectRoot status --porcelain `
        --untracked-files=no)
    if ($LASTEXITCODE -ne 0 -or $tracked.Count -gt 0) {
        throw '추적 파일 변경이 남아 있어 apply 금지 — 먼저 검증·커밋할 것'
    }
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $transcript) |
    Out-Null
Start-Transcript -LiteralPath $transcript | Out-Null
$sleepGuardEnabled = $false
try {
    Write-Host (
        "2020 WAV-ID recovery: mode=" + $(if ($Apply) {'APPLY'} else {'DRY-RUN'})
    ) -ForegroundColor Cyan
    Write-Host "source(변경 금지): $sourceWavRoot"
    Write-Host "derived corpus: $outputWavRoot"
    Write-Host "independent archive: $archiveBase"
    if ($Apply) {
        Enable-WavRecoverySleepGuard
        $sleepGuardEnabled = $true
        Write-Host 'Windows system sleep guard: enabled' -ForegroundColor Cyan
    }
    $arguments = @(
        $builder,
        '--year', '2020',
        '--plan-csv', $plan,
        '--search-master-root', $searchMasterRoot,
        '--source-wav-root', $sourceWavRoot,
        '--output-wav-root', $outputWavRoot,
        '--archive-base', $archiveBase,
        '--review-manifest', $reviewManifest,
        '--review-decisions', $reviewDecisions,
        '--report', $report,
        '--progress-jsonl', $progress
    )
    if ($Apply) {
        $arguments += @('--apply', '--approved-by', $ApprovedBy)
    }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "WAV recovery 실행 실패(exit=$LASTEXITCODE)"
    }
    $result = Get-Content -LiteralPath $report -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $expectedStatus = if ($Apply) {'apply_passed'} else {'dry_run_passed'}
    if ($result.status -ne $expectedStatus) {
        throw "WAV recovery 보고서 status 불일치: $($result.status)"
    }
    if ($Apply) {
        $contractPath = Resolve-ConfiguredPath (
            [string]$config.mfa_wav_corpus_contract_2020
        )
        $contract = Get-Content -LiteralPath $contractPath -Raw `
            -Encoding UTF8 | ConvertFrom-Json
        if (
            $contract.status -ne 'passed' -or
            [string]$contract.corpus_contract_id -ne
                [string]$result.application.corpus_contract_id
        ) {
            throw '최종 복구 corpus contract 검증 실패'
        }
    }
    Write-Host "[OK] report: $report" -ForegroundColor Green
} finally {
    if ($sleepGuardEnabled) {
        Disable-WavRecoverySleepGuard
    }
    Stop-Transcript | Out-Null
}
