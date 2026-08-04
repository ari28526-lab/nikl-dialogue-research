#Requires -Version 5.1
<#
검증된 direct-DB export checkpoint를 연도 staging으로 승격하고 독립 QC를 잇는다.

- MFA, LAB 생성, 입력 전수 감사와 6-tier 전수 생성을 반복하지 않는다.
- 성공 export·현재 정렬 계약·DB checkpoint·입력 감사·동반표 SHA를 재검증한다.
- 정본 06_textgrid_eojeol은 승격하지 않는다.
- 독립 6-tier 전수 감사와 DB 표본 재수출 24건을 통과해야 완료 state를 쓴다.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2021','2022','2023','2024','2025')]
    [string]$Year,
    [Parameter(Mandatory=$true)]
    [string]$ExportReport,
    [Parameter(Mandatory=$true)]
    [string]$InputIntegrityReport,
    [Parameter(Mandatory=$true)]
    [string]$ApprovedExclusionsContract,
    [ValidatePattern('^$|^[A-Za-z0-9._-]+$')]
    [string]$QueueId = '',
    [ValidateRange(5, 200)]
    [int]$QcSampleSize = 24,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
. (Join-Path $PSScriptRoot 'mfa_wav_corpus.ps1')

function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}
function Write-JsonAtomic([string]$Path, $Payload) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $partial = "$Path.$PID.partial"
    $Payload | ConvertTo-Json -Depth 14 |
        Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $Path -Force
}
function Read-Json([string]$Path) {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 |
        ConvertFrom-Json
}
function Test-SuccessReport(
    [string]$Path, [string]$Schema, [string]$ExpectedYear,
    [string]$InputId, [string]$AlignmentId
) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    try {
        $value = Read-Json $Path
        return (
            [string]$value.schema_version -eq $Schema -and
            [string]$value.status -eq 'success' -and
            [string]$value.year -eq $ExpectedYear -and
            [string]$value.input_contract_id -eq $InputId -and
            [string]$value.alignment_contract_id -eq $AlignmentId
        )
    } catch {
        return $false
    }
}

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MfaCheckpointQcSleepGuard {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
function Enable-CheckpointSleepGuard {
    $result = [MfaCheckpointQcSleepGuard]::SetThreadExecutionState(
        [uint32]2147483649
    )
    if ($result -eq 0) { throw 'Windows 절전 억제 설정 실패' }
}
function Disable-CheckpointSleepGuard {
    [void][MfaCheckpointQcSleepGuard]::SetThreadExecutionState(
        [uint32]2147483648
    )
}

if ([string]::IsNullOrWhiteSpace($QueueId)) {
    $QueueId = "mfa_checkpoint_qc_${Year}_" + (Get-Date -Format 'yyyyMMdd_HHmmss')
}
$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$finalRoot = Resolve-ConfiguredPath (
    [string]$config.textgrid_research_v2_staging
)
$existingFinalRoot = Resolve-ConfiguredPath ([string]$config.textgrid_eojeol)
$searchMasterRoot = Resolve-ConfiguredPath (
    [string]$config.pre_mfa_search_master
)
$wavSelection = Resolve-MfaWavCorpusForYear -Config $config -Year $Year
$yearWavRoot = Join-Path ([string]$wavSelection.WavRoot) $Year

$ExportReport = [IO.Path]::GetFullPath($ExportReport)
$InputIntegrityReport = [IO.Path]::GetFullPath($InputIntegrityReport)
$ApprovedExclusionsContract = [IO.Path]::GetFullPath(
    $ApprovedExclusionsContract
)
$alignmentContractPath = Join-Path $stateRoot "alignment_contracts\$Year.json"
$readyMarkerPath = Join-Path $stateRoot "done\$Year.direct_db_ready"
$alignMarkerPath = Join-Path $stateRoot "done\$Year.align_done"
$mergeMarkerPath = Join-Path $stateRoot "done\$Year.merge_done"
foreach ($required in @(
    $python, $ExportReport, $InputIntegrityReport,
    $ApprovedExclusionsContract, $alignmentContractPath,
    $readyMarkerPath, $yearWavRoot, $searchMasterRoot
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "필수 checkpoint/QC 입력 없음: $required"
    }
}

$export = Read-Json $ExportReport
$alignment = Read-Json $alignmentContractPath
$ready = Read-Json $readyMarkerPath
$inputId = [string]$export.input_contract_id
$alignmentId = [string]$export.alignment_contract_id
$db = [IO.Path]::GetFullPath([string]$ready.details.alignment_db)
if (
    [string]$export.status -ne 'success' -or
    [string]$export.year -ne $Year -or
    [string]$alignment.status -ne 'passed' -or
    [string]$alignment.year -ne $Year -or
    [string]$alignment.lab_input_contract_id -ne $inputId -or
    [string]$alignment.alignment_contract_id -ne $alignmentId -or
    [string]$ready.stage -ne 'direct_db_ready' -or
    [string]$ready.details.input_contract_id -ne $inputId -or
    [string]$ready.details.alignment_contract_id -ne $alignmentId -or
    -not (Test-Path -LiteralPath $db -PathType Leaf)
) {
    throw 'export/alignment/direct_db_ready identity 또는 status 불일치'
}
$partialYear = Join-Path ([IO.Path]::GetFullPath(
    [string]$export.output_root
)) $Year
$finalYear = Join-Path $finalRoot $Year
$acoustic = [IO.Path]::GetFullPath(
    [string]$alignment.models.acoustic.path
)
if (-not (Test-Path -LiteralPath $acoustic -PathType Leaf)) {
    throw "동결 acoustic model 없음: $acoustic"
}

$queueRoot = Join-Path $stateRoot "year_queue\$QueueId"
$queueStatePath = Join-Path $queueRoot 'queue_state.json'
$reportRoot = Join-Path $projectRoot (
    "outputs\reports\mfa_year_queue_$QueueId\$Year"
)
$promotionReport = Join-Path $reportRoot '00_checkpoint_promotion.json'
$auditReport = Join-Path $reportRoot '01_year_audit.json'
$missingCsv = Join-Path $reportRoot '01_id_inventory.csv'
$sampleReport = Join-Path $reportRoot '02_db_sample.json'
$sampleCsv = Join-Path $reportRoot '02_db_sample.csv'
$scratchRoot = Join-Path $projectRoot "work\mfa_checkpoint_qc\$QueueId"

$queue = [ordered]@{
    schema_version = 'mfa_r2_unattended_year_queue.v1'
    queue_id = $QueueId
    search_master_run_id = Split-Path -Leaf $searchMasterRoot
    status = 'preflight'
    years_requested = @($Year)
    search_master_root = $searchMasterRoot
    checkpoint_resume = $true
    no_automatic_full_clean_retry = $true
    researcher_approval_automatic = $false
    canonical_promotion_automatic = $false
    source_export_report = $ExportReport
    started_at = (Get-Date).ToString('o')
    updated_at = (Get-Date).ToString('o')
    years = [ordered]@{
        $Year = [ordered]@{
            year = $Year
            status = 'checkpoint_preflight'
            phase = 'checkpoint_preflight'
            attempts_this_invocation = 1
            approved_exclusions_contract = $ApprovedExclusionsContract
            export_approved_exclusions_contract = $ApprovedExclusionsContract
            input_contract_id = $inputId
            alignment_contract_id = $alignmentId
            retained_alignment_db = $db
            machine_audit_report = $null
            db_sample_report = $null
            researcher_review_required = $true
            canonical_promotion_allowed = $false
            failed_reason = $null
            started_at = (Get-Date).ToString('o')
            updated_at = (Get-Date).ToString('o')
        }
    }
    finished_at = $null
    machine_qc_passed_years = 0
    blocked_years = 0
}
$yearState = $queue.years[$Year]

$promoter = Join-Path $PSScriptRoot (
    'python\promote_mfa_direct_export_checkpoint.py'
)
$promoteArgs = @(
    $promoter,
    '--project-root', $projectRoot,
    '--year', $Year,
    '--export-report', $ExportReport,
    '--alignment-contract', $alignmentContractPath,
    '--direct-db-ready', $readyMarkerPath,
    '--partial-year', $partialYear,
    '--final-year', $finalYear,
    '--align-marker', $alignMarkerPath,
    '--merge-marker', $mergeMarkerPath,
    '--promotion-report', $promotionReport,
    '--staging-root', $finalRoot,
    '--existing-final-root', $existingFinalRoot,
    '--input-integrity-report', $InputIntegrityReport,
    '--approved-exclusions-contract', $ApprovedExclusionsContract
)

& $python @promoteArgs --dry-run
if ($LASTEXITCODE -ne 0) {
    throw "checkpoint 승격 preflight 실패(exit=$LASTEXITCODE)"
}
if ($PreflightOnly) {
    Write-Host '[OK] checkpoint 승격·독립 QC preflight 통과; staging/marker/QC 변경 없음' `
        -ForegroundColor Green
    Write-Host "preflight report: $promotionReport"
    exit 0
}

$sleepGuardEnabled = $false
try {
    Enable-CheckpointSleepGuard
    $sleepGuardEnabled = $true
    Write-Host 'Windows system sleep guard: enabled' -ForegroundColor Cyan
    $queue.status = 'running'
    $yearState.status = 'checkpoint_promotion_running'
    $yearState.phase = 'checkpoint_promotion'
    $queue.updated_at = (Get-Date).ToString('o')
    Write-JsonAtomic $queueStatePath $queue

    & $python @promoteArgs
    if ($LASTEXITCODE -ne 0) {
        throw "checkpoint staging 승격 실패(exit=$LASTEXITCODE)"
    }
    $yearState.status = 'checkpoint_promoted_machine_qc_pending'
    $yearState.phase = 'independent_machine_qc'
    $yearState.updated_at = (Get-Date).ToString('o')
    $queue.updated_at = $yearState.updated_at
    Write-JsonAtomic $queueStatePath $queue

    if (-not (Test-SuccessReport $auditReport `
        'mfa_research_6tier_year_audit.v1' $Year $inputId $alignmentId)) {
        & $python (Join-Path $PSScriptRoot (
            'python\audit_mfa_research_6tier_year.py'
        )) --year $Year --lab-root $yearWavRoot `
            --textgrid-root $finalRoot --acoustic-model $acoustic `
            --approved-exclusions-contract $ApprovedExclusionsContract `
            --input-contract-id $inputId `
            --alignment-contract-id $alignmentId `
            --report $auditReport --missing-csv $missingCsv --workers 4
        if ($LASTEXITCODE -ne 0) {
            throw "독립 연도 전수 감사 실패: $auditReport"
        }
    }
    $yearState.machine_audit_report = $auditReport
    $yearState.status = 'machine_audit_passed_sample_pending'
    $yearState.phase = 'db_sample_equivalence'
    $yearState.updated_at = (Get-Date).ToString('o')
    $queue.updated_at = $yearState.updated_at
    Write-JsonAtomic $queueStatePath $queue

    if (-not (Test-SuccessReport $sampleReport `
        'mfa_db_research_6tier_sample_equivalence.v1' `
        $Year $inputId $alignmentId)) {
        & $python (Join-Path $PSScriptRoot (
            'python\verify_mfa_db_research_6tier_sample.py'
        )) --db $db --year $Year `
            --search-master-root $searchMasterRoot `
            --final-root $finalRoot --scratch-root $scratchRoot `
            --acoustic-model $acoustic `
            --alignment-contract $alignmentContractPath `
            --approved-exclusions-contract $ApprovedExclusionsContract `
            --report $sampleReport --sample-csv $sampleCsv `
            --sample-size $QcSampleSize
        if ($LASTEXITCODE -ne 0) {
            throw "DB 표본 재수출 검사 실패: $sampleReport"
        }
    }
    $yearState.db_sample_report = $sampleReport
    $yearState.status = 'machine_qc_passed_human_review_pending'
    $yearState.phase = 'complete_not_promoted'
    $yearState.updated_at = (Get-Date).ToString('o')
    $queue.status = 'machine_qc_complete_human_review_pending'
    $queue.machine_qc_passed_years = 1
    $queue.blocked_years = 0
    $queue.updated_at = $yearState.updated_at
    Write-Host "[OK] $Year checkpoint 승격·독립 QC·DB 표본 $QcSampleSize 건 통과" `
        -ForegroundColor Green
    Write-Host "queue state: $queueStatePath"
} catch {
    $yearState.status = 'machine_qc_failed_outputs_preserved'
    $yearState.phase = 'blocked_after_checkpoint'
    $yearState.failed_reason = $_.Exception.Message
    $yearState.updated_at = (Get-Date).ToString('o')
    $queue.status = 'completed_with_blocked_years'
    $queue.blocked_years = 1
    $queue.updated_at = $yearState.updated_at
    throw
} finally {
    if ($sleepGuardEnabled) {
        Disable-CheckpointSleepGuard
        Write-Host 'Windows system sleep guard: disabled' -ForegroundColor Cyan
    }
    $queue.finished_at = (Get-Date).ToString('o')
    $queue.updated_at = $queue.finished_at
    Write-JsonAtomic $queueStatePath $queue
}
