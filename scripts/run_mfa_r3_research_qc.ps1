#Requires -Version 5.1
<#
Run the independent annual semantic QC for an already exported r3 6-tier year.

The source MFA database, LAB/WAV corpus, TextGrids, and companion tables are
read-only inputs.  A passed full-year audit is checkpointed independently from
the 24-session DB re-export sample so an interrupted sample does not repeat the
full audit.
#>
param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year = '2020',
    [ValidateRange(1, 16)]
    [int]$Workers = 4,
    [ValidateRange(5, 100)]
    [int]$SampleSize = 24,
    [ValidateRange(1000, 1000000)]
    [int]$ProgressEvery = 25000,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\ari30\miniforge3\envs\mfa\python.exe'
$policyPath = Join-Path $projectRoot 'config\mfa_r3_runner_v1.json'
$reportsRoot = Join-Path $projectRoot 'outputs\reports'

function Read-Json([string]$Path) {
    Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-FileFingerprint([string]$Path, [bool]$WithSha256 = $true) {
    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    $value = [ordered]@{
        path = $item.FullName
        bytes = [int64]$item.Length
        mtime_utc_ticks = [int64]$item.LastWriteTimeUtc.Ticks
    }
    if ($WithSha256) {
        $value.sha256 = (
            Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256
        ).Hash.ToLowerInvariant()
    }
    return $value
}

function Get-TextSha256([string]$Value) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
        $hash = $hasher.ComputeHash($bytes)
        return ([BitConverter]::ToString($hash)).Replace('-', '').ToLowerInvariant()
    } finally {
        $hasher.Dispose()
    }
}

function Write-JsonAtomic([string]$Path, $Payload) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temp = Join-Path $parent (
        '.{0}.{1}.partial' -f (Split-Path -Leaf $Path),
        [guid]::NewGuid().ToString('N')
    )
    try {
        $json = $Payload | ConvertTo-Json -Depth 20
        [IO.File]::WriteAllText(
            $temp,
            $json + [Environment]::NewLine,
            [Text.UTF8Encoding]::new($false)
        )
        Move-Item -LiteralPath $temp -Destination $Path -Force
    } finally {
        if (Test-Path -LiteralPath $temp -PathType Leaf) {
            Remove-Item -LiteralPath $temp -Force
        }
    }
}

function Test-AllZero($Values) {
    if ($null -eq $Values) { return $false }
    foreach ($property in @($Values.PSObject.Properties)) {
        if ([int64]$property.Value -ne 0) { return $false }
    }
    return $true
}

function Get-LiveLockPid([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return 0 }
    try {
        $lock = Read-Json $Path
        $lockPid = 0
        if (
            [int]::TryParse([string]$lock.owner_pid, [ref]$lockPid) -and
            $lockPid -gt 0 -and
            $null -ne (Get-Process -Id $lockPid -ErrorAction SilentlyContinue)
        ) {
            return $lockPid
        }
    } catch {
        return -1
    }
    return 0
}

function Enable-SleepGuard {
    if (-not ('MfaR3ResearchQcSleepGuard' -as [type])) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MfaR3ResearchQcSleepGuard {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
    }
    $state = [convert]::ToUInt32('80000001', 16)
    if ([MfaR3ResearchQcSleepGuard]::SetThreadExecutionState($state) -eq 0) {
        throw 'Windows sleep guard 활성화 실패'
    }
}

function Disable-SleepGuard {
    if ('MfaR3ResearchQcSleepGuard' -as [type]) {
        $state = [convert]::ToUInt32('80000000', 16)
        [void][MfaR3ResearchQcSleepGuard]::SetThreadExecutionState($state)
    }
}

foreach ($required in @($python, $policyPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 r3 QC 입력 없음: $required"
    }
}

$policy = Read-Json $policyPath
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
$labYear = Join-Path $labRoot $Year
$outputRoot = Join-Path $releaseRoot 'research_6tier'
$outputYear = Join-Path $outputRoot $Year
$tableManifestPath = Join-Path $outputYear '_tables\TABLES_MANIFEST.json'
$reviewRoot = Join-Path $projectRoot (
    'outputs\reviews\mfa_r3_post_mfa_reconciliation_{0}_{1}' -f
    $releaseId, $Year
)
$approvalManifest = Join-Path $reviewRoot '06_RESEARCHER_APPROVAL.json'
$approvedContract = Join-Path $reviewRoot '05_APPROVED_EXCLUSIONS.json'

foreach ($required in @(
    $alignmentContract, $alignmentMarker, $database, $labYear, $outputYear,
    $tableManifestPath, $approvalManifest, $approvedContract
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "필수 r3 QC 입력 없음: $required"
    }
}

$alignment = Read-Json $alignmentContract
$alignmentId = [string]$alignment.alignment_contract_id
$inputId = [string]$alignment.identity.year_input_contract_id
$yearInputPath = [string]$alignment.inputs.year_input_contract.path
$acousticModel = [string]$alignment.models.acoustic.path
if (
    [string]$alignment.schema_version -ne 'mfa_r3_alignment_contract.v1' -or
    [string]$alignment.status -ne
        'materialized_pending_runner_preflight_and_release_gate' -or
    [string]$alignment.year -ne $Year -or
    -not [bool]$alignment.r3_full_realign
) {
    throw 'r3 alignment contract identity/status 불일치'
}
foreach ($required in @($yearInputPath, $acousticModel)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "r3 alignment 계약 파일 없음: $required"
    }
}
$yearInput = Read-Json $yearInputPath
$searchMasterRoot = [string](
    $yearInput.inputs.frozen_search_master_inventory.root
)
if (-not (Test-Path -LiteralPath $searchMasterRoot -PathType Container)) {
    throw "frozen search master root 없음: $searchMasterRoot"
}

$marker = Read-Json $alignmentMarker
if (
    [string]$marker.schema_version -ne 'mfa_r3_alignment_done.v1' -or
    [string]$marker.status -ne 'passed' -or
    [string]$marker.year -ne $Year -or
    [string]$marker.release_id -ne $releaseId -or
    [string]$marker.alignment_contract_id -ne $alignmentId -or
    -not [bool]$marker.r3_full_realign
) {
    throw 'r3 ALIGN_DONE marker identity/status 불일치'
}
$databaseItem = Get-Item -LiteralPath $database
if (
    [IO.Path]::GetFullPath([string]$marker.source_db.path) -ne
        [IO.Path]::GetFullPath($database) -or
    [int64]$marker.source_db.bytes -ne [int64]$databaseItem.Length
) {
    throw 'r3 source DB path/size가 ALIGN_DONE marker와 다름'
}

$approval = Read-Json $approvalManifest
if (
    [string]$approval.schema_version -ne
        'mfa_r3_post_mfa_explicit_approval.v1' -or
    [string]$approval.status -ne 'approved' -or
    [string]$approval.year -ne $Year -or
    [bool]$approval.automatic_approval_performed
) {
    throw 'r3 post-MFA explicit approval identity/status 불일치'
}
$approvedFingerprint = Get-FileFingerprint $approvedContract
if (
    [string]$approvedFingerprint.sha256 -ne
    ([string]$approval.approved_exclusions_contract.sha256).ToLowerInvariant()
) {
    throw 'r3 approved exclusions contract SHA-256 불일치'
}

$validExports = [Collections.Generic.List[object]]::new()
$exportFiles = @(
    Get-ChildItem -LiteralPath $reportsRoot -File -Filter (
        "EXPORT_mfa_r3_research_6tier_${Year}_*.json"
    ) -ErrorAction SilentlyContinue
    Get-ChildItem -LiteralPath $reportsRoot -File -Filter (
        "EXPORT_RECOVERED_mfa_r3_research_6tier_${Year}_*.json"
    ) -ErrorAction SilentlyContinue
) | Sort-Object FullName -Unique
foreach ($file in $exportFiles) {
    try {
        $candidate = Read-Json $file.FullName
        if (
            [string]$candidate.schema_version -eq
                'mfa_research_6tier_export.v1' -and
            [string]$candidate.status -eq 'success' -and
            [string]$candidate.year -eq $Year -and
            [string]$candidate.pronunciation_release_id -eq $releaseId -and
            [string]$candidate.alignment_contract_id -eq $alignmentId -and
            [string]$candidate.input_contract_id -eq $inputId -and
            [string]$candidate.source_db_sha256 -eq
                [string]$marker.source_db.sha256 -and
            [string]$candidate.exact_id_reconciliation.status -eq 'passed' -and
            [double]$candidate.coverage_pct -eq 100.0 -and
            [int64]$candidate.counts.spn_intervals -eq 0 -and
            [bool]$candidate.r3_full_realign
        ) {
            $validExports.Add([pscustomobject]@{
                file = $file
                data = $candidate
            })
        }
    } catch {
        # A malformed historical report is not a valid completion candidate.
    }
}
if ($validExports.Count -eq 0) {
    throw "현재 r3 identity와 일치하는 성공 export 보고서 없음: $Year"
}
$selectedExport = @(
    $validExports | Sort-Object { $_.file.LastWriteTimeUtc } -Descending
)[0]
$exportReportPath = [string]$selectedExport.file.FullName
$export = $selectedExport.data
$exactCounts = $export.exact_id_reconciliation.counts
$expectedMfaInputIds = [int64]$exactCounts.expected_mfa_input_ids
$activeLabIds = [int64]$exactCounts.active_lab_ids
$databaseUtteranceIds = [int64]$exactCounts.database_utterance_ids
$alignedDatabaseIds = [int64]$exactCounts.aligned_database_ids
$approvedDatabaseExclusions = [int64](
    $exactCounts.approved_database_exclusions
)
$approvedDatabaseUnalignedIds = [int64](
    $exactCounts.approved_database_unaligned_ids
)
$approvedTechnicalFailureIds = [int64](
    $exactCounts.approved_technical_failure_ids
)
$approvedAlignmentExclusions = [int64](
    $exactCounts.approved_alignment_exclusions
)
if (
    [IO.Path]::GetFullPath([string]$export.db_path) -ne
        [IO.Path]::GetFullPath($database) -or
    [IO.Path]::GetFullPath([string]$export.output_root) -ne
        [IO.Path]::GetFullPath($outputRoot) -or
    $expectedMfaInputIds -ne [int64]$marker.expected_mfa_input -or
    $activeLabIds -ne $expectedMfaInputIds -or
    ($databaseUtteranceIds + $approvedDatabaseExclusions) -ne
        $expectedMfaInputIds -or
    ($alignedDatabaseIds + $approvedDatabaseUnalignedIds) -ne
        $databaseUtteranceIds -or
    ($approvedDatabaseExclusions + $approvedDatabaseUnalignedIds) -ne
        $approvedTechnicalFailureIds -or
    $approvedTechnicalFailureIds -ne $approvedAlignmentExclusions -or
    [int64]$approval.approved_row_count -ne
        $approvedAlignmentExclusions -or
    [int64]$approval.contract_row_count -ne
        $approvedAlignmentExclusions -or
    [int64]$export.accounted -ne $databaseUtteranceIds -or
    [int64]$export.counts.source_utterances -ne $databaseUtteranceIds -or
    ([int64]$export.counts.created +
        [int64]$export.counts.approved_excluded) -ne
        $databaseUtteranceIds -or
    [int64]$export.counts.approved_excluded -ne
        $approvedDatabaseUnalignedIds -or
    [int64]$exactCounts.unaligned_ids_without_approval -ne 0 -or
    [int64]$exactCounts.expected_input_ids_missing_from_database_without_approval -ne 0
) {
    throw 'r3 export 보고서의 DB/output/exact-ID 회계 불일치'
}

$tableManifest = Read-Json $tableManifestPath
if (
    [string]$tableManifest.schema_version -ne
        'mfa_research_companion_tables.v2' -or
    [string]$tableManifest.status -ne 'success' -or
    [string]$tableManifest.year -ne $Year -or
    [string]$tableManifest.input_contract_id -ne $inputId -or
    [string]$tableManifest.alignment_contract_id -ne $alignmentId -or
    [string]$tableManifest.source_db_sha256 -ne
        [string]$marker.source_db.sha256 -or
    [int64]$tableManifest.counts.utterances -ne
        [int64]$export.counts.created -or
    [int64]$tableManifest.counts.excluded_utterances -ne
        $approvedAlignmentExclusions
) {
    throw 'r3 companion table manifest identity/count 불일치'
}
foreach ($tableName in @('utterances','words','phones','excluded')) {
    $tableRecord = $tableManifest.tables.$tableName
    $tablePath = [string]$tableRecord.path
    if (-not [IO.Path]::IsPathRooted($tablePath)) {
        $tablePath = Join-Path (Split-Path -Parent $tableManifestPath) $tablePath
    }
    if (
        -not (Test-Path -LiteralPath $tablePath -PathType Leaf) -or
        [int64](Get-Item -LiteralPath $tablePath).Length -ne
            [int64]$tableRecord.bytes
    ) {
        throw "r3 companion table 없음/크기 불일치: $tableName"
    }
}

$exportFingerprint = Get-FileFingerprint $exportReportPath
$manifestFingerprint = Get-FileFingerprint $tableManifestPath
$alignmentFingerprint = Get-FileFingerprint $alignmentContract
$markerFingerprint = Get-FileFingerprint $alignmentMarker
$databaseFingerprint = Get-FileFingerprint $database $false
$qcInput = [ordered]@{
    release_id = $releaseId
    year = $Year
    input_contract_id = $inputId
    alignment_contract_id = $alignmentId
    export_report_sha256 = [string]$exportFingerprint.sha256
    table_manifest_sha256 = [string]$manifestFingerprint.sha256
    alignment_contract_sha256 = [string]$alignmentFingerprint.sha256
    alignment_marker_sha256 = [string]$markerFingerprint.sha256
    approved_contract_sha256 = [string]$approvedFingerprint.sha256
    source_db_expected_sha256 = [string]$marker.source_db.sha256
    source_db_bytes = [int64]$databaseFingerprint.bytes
    source_db_mtime_utc_ticks = [int64]$databaseFingerprint.mtime_utc_ticks
}
$qcInputJson = $qcInput | ConvertTo-Json -Compress -Depth 8
$qcInputCheckpointId = Get-TextSha256 $qcInputJson

$qcRoot = Join-Path $reportsRoot (
    "mfa_r3_research_qc_${releaseId}\$Year"
)
$auditReport = Join-Path $qcRoot '01_year_audit.json'
$missingCsv = Join-Path $qcRoot '01_id_inventory.csv'
$sampleReport = Join-Path $qcRoot '02_db_sample.json'
$sampleCsv = Join-Path $qcRoot '02_db_sample.csv'
$statePath = Join-Path $qcRoot 'QC_STATE.json'
$scratchRoot = Join-Path $releaseRoot "qc_scratch\$Year"
$preflightReport = Join-Path $reportsRoot (
    'PREFLIGHT_mfa_r3_research_qc_{0}_{1}.json' -f
    $Year, (Get-Date -Format 'yyyyMMdd_HHmmss')
)
$lockRoot = Join-Path $releaseRoot 'locks'
$lockPath = Join-Path $lockRoot "research_qc_$Year.lock.json"
$exportLock = Join-Path $lockRoot "research_export_$Year.lock.json"
$exportLockPid = Get-LiveLockPid $exportLock
if ($exportLockPid -ne 0) {
    throw "r3 export lock이 남아 있어 QC를 시작하지 않음(pid=$exportLockPid)"
}
$qcLockPid = Get-LiveLockPid $lockPath
if ($qcLockPid -gt 0) {
    throw "이미 실행 중인 r3 research QC가 있음(pid=$qcLockPid)"
}
if ($qcLockPid -lt 0) {
    throw "읽을 수 없는 r3 research QC lock: $lockPath"
}

$existingState = $null
$auditReusable = $false
$sampleReusable = $false
if (Test-Path -LiteralPath $statePath -PathType Leaf) {
    try {
        $existingState = Read-Json $statePath
        if (
            [string]$existingState.qc_input_checkpoint_id -eq
                $qcInputCheckpointId -and
            (Test-Path -LiteralPath $auditReport -PathType Leaf) -and
            (Test-Path -LiteralPath $missingCsv -PathType Leaf)
        ) {
            $priorAudit = Read-Json $auditReport
            $currentAuditFingerprint = Get-FileFingerprint $auditReport
            $currentMissingFingerprint = Get-FileFingerprint $missingCsv
            $auditReusable = (
                [string]$priorAudit.schema_version -eq
                    'mfa_research_6tier_year_audit.v1' -and
                [string]$priorAudit.status -eq 'success' -and
                [string]$priorAudit.year -eq $Year -and
                [string]$priorAudit.input_contract_id -eq $inputId -and
                [string]$priorAudit.alignment_contract_id -eq $alignmentId -and
                [double]$priorAudit.coverage_pct -eq 100.0 -and
                (Test-AllZero $priorAudit.hard_failure_counts) -and
                [string]$existingState.audit_report.sha256 -eq
                    [string]$currentAuditFingerprint.sha256 -and
                [string]$existingState.missing_csv.sha256 -eq
                    [string]$currentMissingFingerprint.sha256
            )
        }
        if (
            $auditReusable -and
            (Test-Path -LiteralPath $sampleReport -PathType Leaf) -and
            (Test-Path -LiteralPath $sampleCsv -PathType Leaf)
        ) {
            $priorSample = Read-Json $sampleReport
            $currentSampleFingerprint = Get-FileFingerprint $sampleReport
            $currentSampleCsvFingerprint = Get-FileFingerprint $sampleCsv
            $sampleReusable = (
                [string]$priorSample.schema_version -eq
                    'mfa_db_research_6tier_sample_equivalence.v1' -and
                [string]$priorSample.status -eq 'success' -and
                [string]$priorSample.year -eq $Year -and
                [string]$priorSample.input_contract_id -eq $inputId -and
                [string]$priorSample.alignment_contract_id -eq $alignmentId -and
                [int]$priorSample.selection_counts.selected_utterances -eq
                    $SampleSize -and
                [int]$priorSample.selection_counts.selected_sessions -eq
                    $SampleSize -and
                [int]$priorSample.comparison_counts.semantic_equal -eq
                    $SampleSize -and
                [int]$priorSample.comparison_counts.byte_equal -eq
                    $SampleSize -and
                [string]$existingState.sample_report.sha256 -eq
                    [string]$currentSampleFingerprint.sha256 -and
                [string]$existingState.sample_csv.sha256 -eq
                    [string]$currentSampleCsvFingerprint.sha256
            )
        }
    } catch {
        $auditReusable = $false
        $sampleReusable = $false
    }
}

$preflight = [ordered]@{
    schema_version = 'mfa_r3_research_qc_preflight.v1'
    status = 'preflight_passed'
    recorded_at = [DateTimeOffset]::Now.ToString('o')
    year = $Year
    release_id = $releaseId
    qc_input_checkpoint_id = $qcInputCheckpointId
    qc_input = $qcInput
    source_export_report = $exportFingerprint
    source_table_manifest = $manifestFingerprint
    source_database = $databaseFingerprint
    source_database_expected_sha256 = [string]$marker.source_db.sha256
    counts = [ordered]@{
        expected_input = [int64]$marker.expected_mfa_input
        textgrids = [int64]$tableManifest.counts.utterances
        approved_exclusions = [int64]$tableManifest.counts.excluded_utterances
    }
    resume = [ordered]@{
        full_year_audit_reusable = [bool]$auditReusable
        db_sample_reusable = [bool]$sampleReusable
    }
    mutation_policy = [ordered]@{
        source_db_read_only = $true
        source_lab_wav_read_only = $true
        source_textgrid_read_only = $true
        source_companion_tables_read_only = $true
        mfa_recomputed = $false
        full_export_repeated = $false
    }
    materialization_started = $false
}
Write-JsonAtomic $preflightReport $preflight
if ($PreflightOnly) {
    Write-Host (
        "[GO] r3 $Year research QC preflight: TextGrid=" +
        "{0:N0}, approved exclusions={1:N0}" -f
        [int64]$tableManifest.counts.utterances,
        [int64]$tableManifest.counts.excluded_utterances
    ) -ForegroundColor Green
    Write-Host "report: $preflightReport"
    Write-Host (
        "resume: audit=$auditReusable, sample=$sampleReusable"
    ) -ForegroundColor Cyan
    exit 0
}

if ($auditReusable -and $sampleReusable) {
    Write-Host "[OK] r3 $Year research QC already complete; no rerun" `
        -ForegroundColor Green
    Write-Host "state: $statePath"
    exit 0
}

New-Item -ItemType Directory -Force -Path $qcRoot | Out-Null
New-Item -ItemType Directory -Force -Path $lockRoot | Out-Null
if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
    $staleRoot = Join-Path $lockRoot 'stale'
    New-Item -ItemType Directory -Force -Path $staleRoot | Out-Null
    Move-Item -LiteralPath $lockPath -Destination (Join-Path $staleRoot (
        'research_qc_{0}_{1}.lock.json' -f
        $Year, (Get-Date -Format 'yyyyMMdd_HHmmss')
    ))
}
$lockRecord = [ordered]@{
    schema_version = 'mfa_r3_research_qc_lock.v1'
    status = 'owned'
    owner_pid = $PID
    year = $Year
    release_id = $releaseId
    qc_input_checkpoint_id = $qcInputCheckpointId
    started_at = [DateTimeOffset]::Now.ToString('o')
}
$lockBytes = [Text.UTF8Encoding]::new($false).GetBytes(
    ($lockRecord | ConvertTo-Json -Depth 8) + [Environment]::NewLine
)
$lockStream = $null
try {
    $lockStream = [IO.FileStream]::new(
        $lockPath,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,
        [IO.FileShare]::Read
    )
    $lockStream.Write($lockBytes, 0, $lockBytes.Length)
    $lockStream.Flush($true)
} finally {
    if ($null -ne $lockStream) { $lockStream.Dispose() }
}

$auditFingerprint = $null
$missingFingerprint = $null
$sampleFingerprint = $null
$sampleCsvFingerprint = $null
$currentPhase = 'starting'
Enable-SleepGuard
try {
    Write-Host 'Windows system sleep guard: enabled' -ForegroundColor Cyan
    if (-not $auditReusable) {
        $currentPhase = 'full_year_semantic_audit'
        Write-Host (
            "[START] r3 $Year independent full-year audit; " +
            "TextGrid={0:N0}" -f [int64]$tableManifest.counts.utterances
        ) -ForegroundColor Cyan
        & $python (Join-Path $PSScriptRoot (
            'python\audit_mfa_research_6tier_year.py'
        )) --year $Year --lab-root $labRoot `
            --textgrid-root $outputRoot --acoustic-model $acousticModel `
            --approved-exclusions-contract $approvedContract `
            --input-contract-id $inputId `
            --alignment-contract-id $alignmentId `
            --alignment-contract $alignmentContract --source-db $database `
            --report $auditReport --missing-csv $missingCsv `
            --workers $Workers --progress-every $ProgressEvery
        if ($LASTEXITCODE -ne 0) {
            throw "독립 연도 semantic audit 실패: $auditReport"
        }
        $auditResult = Read-Json $auditReport
        if (
            [string]$auditResult.status -ne 'success' -or
            [double]$auditResult.coverage_pct -ne 100.0 -or
            -not (Test-AllZero $auditResult.hard_failure_counts)
        ) {
            throw "독립 연도 semantic audit 결과 Gate 실패: $auditReport"
        }
        $auditFingerprint = Get-FileFingerprint $auditReport
        $missingFingerprint = Get-FileFingerprint $missingCsv
        Write-JsonAtomic $statePath ([ordered]@{
            schema_version = 'mfa_r3_research_qc_state.v1'
            status = 'audit_passed_sample_pending'
            updated_at = [DateTimeOffset]::Now.ToString('o')
            year = $Year
            release_id = $releaseId
            qc_input_checkpoint_id = $qcInputCheckpointId
            qc_input = $qcInput
            audit_report = $auditFingerprint
            missing_csv = $missingFingerprint
            sample_report = $null
            sample_csv = $null
            source_mutation_performed = $false
        })
        $auditReusable = $true
    } else {
        $auditFingerprint = Get-FileFingerprint $auditReport
        $missingFingerprint = Get-FileFingerprint $missingCsv
        Write-Host '[RESUME] passed full-year audit reused; no repeat' `
            -ForegroundColor Green
    }

    if (-not $sampleReusable) {
        $currentPhase = 'db_reexport_sample'
        Write-Host (
            "[START] r3 $Year retained-DB re-export sample: $SampleSize sessions"
        ) -ForegroundColor Cyan
        & $python (Join-Path $PSScriptRoot (
            'python\verify_mfa_db_research_6tier_sample.py'
        )) --db $database --year $Year `
            --search-master-root $searchMasterRoot `
            --final-root $outputRoot --scratch-root $scratchRoot `
            --acoustic-model $acousticModel `
            --alignment-contract $alignmentContract `
            --approved-exclusions-contract $approvedContract `
            --report $sampleReport --sample-csv $sampleCsv `
            --sample-size $SampleSize
        if ($LASTEXITCODE -ne 0) {
            throw "보존 DB 표본 재수출 검사 실패: $sampleReport"
        }
        $sampleResult = Read-Json $sampleReport
        if (
            [string]$sampleResult.status -ne 'success' -or
            [int]$sampleResult.selection_counts.selected_sessions -ne
                $SampleSize -or
            [int]$sampleResult.comparison_counts.semantic_equal -ne
                $SampleSize -or
            [int]$sampleResult.comparison_counts.byte_equal -ne $SampleSize
        ) {
            throw "보존 DB 표본 재수출 결과 Gate 실패: $sampleReport"
        }
        $sampleFingerprint = Get-FileFingerprint $sampleReport
        $sampleCsvFingerprint = Get-FileFingerprint $sampleCsv
    } else {
        $sampleFingerprint = Get-FileFingerprint $sampleReport
        $sampleCsvFingerprint = Get-FileFingerprint $sampleCsv
        Write-Host '[RESUME] passed DB sample reused; no repeat' `
            -ForegroundColor Green
    }

    $currentPhase = 'complete'
    Write-JsonAtomic $statePath ([ordered]@{
        schema_version = 'mfa_r3_research_qc_state.v1'
        status = 'passed'
        updated_at = [DateTimeOffset]::Now.ToString('o')
        year = $Year
        release_id = $releaseId
        qc_input_checkpoint_id = $qcInputCheckpointId
        qc_input = $qcInput
        audit_report = $auditFingerprint
        missing_csv = $missingFingerprint
        sample_report = $sampleFingerprint
        sample_csv = $sampleCsvFingerprint
        counts = [ordered]@{
            textgrids = [int64]$tableManifest.counts.utterances
            approved_exclusions = [int64]$tableManifest.counts.excluded_utterances
            sample_sessions = $SampleSize
            sample_semantic_equal = $SampleSize
            sample_byte_equal = $SampleSize
        }
        next_gate = "freeze $Year and prepare the next single year only"
        source_mutation_performed = $false
        mfa_recomputed = $false
        full_export_repeated = $false
    })
    Write-Host "[OK] r3 $Year independent research QC passed" `
        -ForegroundColor Green
    Write-Host "state: $statePath"
} catch {
    $failure = $_
    try {
        if (
            $null -eq $auditFingerprint -and
            (Test-Path -LiteralPath $auditReport -PathType Leaf)
        ) {
            $candidateAudit = Read-Json $auditReport
            if (
                [string]$candidateAudit.status -eq 'success' -and
                (Test-AllZero $candidateAudit.hard_failure_counts)
            ) {
                $auditFingerprint = Get-FileFingerprint $auditReport
                $missingFingerprint = Get-FileFingerprint $missingCsv
            }
        }
        Write-JsonAtomic $statePath ([ordered]@{
            schema_version = 'mfa_r3_research_qc_state.v1'
            status = 'failed_outputs_preserved'
            updated_at = [DateTimeOffset]::Now.ToString('o')
            year = $Year
            release_id = $releaseId
            qc_input_checkpoint_id = $qcInputCheckpointId
            qc_input = $qcInput
            failed_phase = $currentPhase
            error = $failure.Exception.Message
            audit_report = $auditFingerprint
            missing_csv = $missingFingerprint
            sample_report = $sampleFingerprint
            sample_csv = $sampleCsvFingerprint
            source_mutation_performed = $false
            rerun_policy = 'reuse passed audit; never rerun MFA or full export'
        })
    } catch {
        Write-Warning "QC 실패 상태 기록도 실패함: $($_.Exception.Message)"
    }
    throw $failure
} finally {
    Disable-SleepGuard
    Write-Host 'Windows system sleep guard: disabled' -ForegroundColor Cyan
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
