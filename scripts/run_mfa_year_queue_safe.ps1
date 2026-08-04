# r2 공통사전 MFA를 연도별 독립 작업으로 순회하는 무인 계산 큐.
#
# 핵심 계약:
# - 한 연도의 일부 오류 때문에 그 연도 전체를 자동 --clean 재계산하지 않는다.
# - 실패 연도의 MFA temp·SQLite DB·partial·로그를 보존한다.
# - 연도별 연구자 승인 제외 계약이 없으면 후보표만 만들고 그 연도는 건너뛴다.
# - 성공 연도는 독립 6-tier 전수 감사와 DB 표본 재수출까지 자동 수행한다.
# - 연구자 인프라 검토와 정본 승격은 자동 수행하지 않는다.

[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_full6y_20260801',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725',
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string[]]$Years = @('2020','2021','2022','2023','2024','2025'),
    [string]$YearsCsv = '',
    [Parameter(Mandatory=$true)]
    [string]$CommonPronManifest,
    [Parameter(Mandatory=$true)]
    [string]$CommonPronAdoptionContract,
    [string]$ApprovedExclusionsRoot = '',
    [string]$AlignmentApprovedExclusionsRoot = '',
    [string]$DirectExportFailedReport = '',
    [string]$DirectExportRepairManifest = '',
    [switch]$PrepareMissingReviews,
    [switch]$StopAfterBlockedYear,
    [ValidateRange(5, 200)]
    [int]$QcSampleSize = 24
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'mfa_year_selection.ps1')
$Years = @(
    Resolve-MfaYearSelection -Years $Years -YearsCsv $YearsCsv
)
if (
    [string]::IsNullOrWhiteSpace($DirectExportFailedReport) -ne
    [string]::IsNullOrWhiteSpace($DirectExportRepairManifest)
) {
    throw (
        '-DirectExportFailedReport와 -DirectExportRepairManifest는 ' +
        '함께 지정해야 함'
    )
}
if (
    -not [string]::IsNullOrWhiteSpace($DirectExportFailedReport) -and
    $Years.Count -ne 1
) {
    throw 'direct export repair 재개 큐는 정확히 한 연도만 허용함'
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $projectRoot 'config\paths.json'
$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
. (Join-Path $PSScriptRoot 'mfa_wav_corpus.ps1')

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MfaYearQueueSleepGuard {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@

function Enable-MfaYearQueueSleepGuard {
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED; 화면 꺼짐은 허용한다.
    $result = [MfaYearQueueSleepGuard]::SetThreadExecutionState(
        [uint32]2147483649
    )
    if ($result -eq 0) {
        throw 'Windows 절전 억제 설정 실패'
    }
}

function Disable-MfaYearQueueSleepGuard {
    # ES_CONTINUOUS만 남겨 정상 전원 정책으로 복원한다.
    [void][MfaYearQueueSleepGuard]::SetThreadExecutionState(
        [uint32]2147483648
    )
}

function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}
function Write-JsonAtomic([string]$Path, $Payload) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $partial = "$Path.$PID.partial"
    $Payload | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $Path -Force
}
function Find-Approval([string]$Root, [string]$Year) {
    $candidates = @(
        (Join-Path $Root "$Year\approved_exclusions.json"),
        (Join-Path $Root "approved_exclusions_${Year}.json")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}
function Read-Json([string]$Path) {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 |
        ConvertFrom-Json
}
function Set-YearStateFromDirectDbCheckpoint(
    $State,
    [string]$StateRoot,
    [string]$Year
) {
    $markerPath = Join-Path $StateRoot "done\$Year.direct_db_ready"
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        return $false
    }
    $marker = Read-Json $markerPath
    $db = [string]$marker.details.alignment_db
    if (
        $marker.stage -ne 'direct_db_ready' -or
        -not [bool]$marker.details.computation_complete -or
        [string]::IsNullOrWhiteSpace($db) -or
        -not (Test-Path -LiteralPath $db -PathType Leaf)
    ) {
        return $false
    }
    $State.input_contract_id = [string]$marker.details.input_contract_id
    $State.alignment_contract_id = [string](
        $marker.details.alignment_contract_id
    )
    $State.retained_alignment_db = [IO.Path]::GetFullPath($db)
    return $true
}
function New-YearState([string]$Year) {
    return [ordered]@{
        year = $Year
        status = 'queued'
        phase = 'queued'
        attempts_this_invocation = 0
        approved_exclusions_contract = $null
        export_approved_exclusions_contract = $null
        input_contract_id = $null
        alignment_contract_id = $null
        retained_alignment_db = $null
        machine_audit_report = $null
        db_sample_report = $null
        researcher_review_required = $true
        canonical_promotion_allowed = $false
        failed_reason = $null
        started_at = $null
        updated_at = (Get-Date).ToString('o')
    }
}

$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$wavRoot = Join-Path (
    Resolve-ConfiguredPath ([string]$config.wav)
) 'individual'
$finalRoot = Resolve-ConfiguredPath (
    [string]$config.textgrid_research_v2_staging
)
$searchMasterRoot = Join-Path (
    Resolve-ConfiguredPath ([string]$config.layers)
) "05_search_master_pre_mfa_staging\$SearchMasterRunId"
$CommonPronManifest = [IO.Path]::GetFullPath($CommonPronManifest)
$CommonPronAdoptionContract = [IO.Path]::GetFullPath(
    $CommonPronAdoptionContract
)
if ([string]::IsNullOrWhiteSpace($ApprovedExclusionsRoot)) {
    $ApprovedExclusionsRoot = Join-Path $projectRoot (
        "outputs\reviews\mfa_exclusions_queue_$QueueId"
    )
}
$ApprovedExclusionsRoot = [IO.Path]::GetFullPath(
    $ApprovedExclusionsRoot
)
if ([string]::IsNullOrWhiteSpace($AlignmentApprovedExclusionsRoot)) {
    $AlignmentApprovedExclusionsRoot = $ApprovedExclusionsRoot
}
$AlignmentApprovedExclusionsRoot = [IO.Path]::GetFullPath(
    $AlignmentApprovedExclusionsRoot
)
foreach ($required in @(
    $python, $CommonPronManifest, $CommonPronAdoptionContract
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 파일 없음: $required"
    }
}

$queueRoot = Join-Path $stateRoot "year_queue\$QueueId"
$reportRoot = Join-Path $projectRoot (
    "outputs\reports\mfa_year_queue_$QueueId"
)
$queueStatePath = Join-Path $queueRoot 'queue_state.json'
$queueLock = Join-Path $stateRoot 'locks\mfa_year_queue.lock'
$priorQueueStateArchive = $null
if (Test-Path -LiteralPath $queueStatePath -PathType Leaf) {
    $priorQueue = Read-Json $queueStatePath
    $priorYears = @($priorQueue.years_requested)
    if (
        [string]$priorQueue.queue_id -ne $QueueId -or
        ($priorYears -join ',') -ne (@($Years) -join ',')
    ) {
        throw (
            '기존 queue state의 ID/연도 선택이 이번 실행과 다름; ' +
            '새 ExecutionQueueId를 사용할 것'
        )
    }
    $priorMachineComplete = (
        [string]$priorQueue.status -eq
            'machine_qc_complete_human_review_pending'
    )
    foreach ($year in $Years) {
        $priorYearState = $priorQueue.years.PSObject.Properties[$year].Value
        if (
            $null -eq $priorYearState -or
            [string]$priorYearState.status -ne
                'machine_qc_passed_human_review_pending'
        ) {
            $priorMachineComplete = $false
        }
    }
    if ($priorMachineComplete) {
        throw (
            '이 execution queue는 이미 기계 QC까지 완료됨; ' +
            '연구자 표본 검토와 다음 연도 gate로 진행할 것'
        )
    }
    $historyRoot = Join-Path $queueRoot 'history'
    New-Item -ItemType Directory -Force -Path $historyRoot | Out-Null
    $priorQueueStateArchive = Join-Path $historyRoot (
        'queue_state_{0}_{1}.json' -f (
            (Get-Date -Format 'yyyyMMdd_HHmmss'),
            ([Guid]::NewGuid().ToString('N').Substring(0, 8))
        )
    )
    Copy-Item -LiteralPath $queueStatePath `
        -Destination $priorQueueStateArchive
    $sourceHash = (Get-FileHash -Algorithm SHA256 `
        -LiteralPath $queueStatePath).Hash
    $archiveHash = (Get-FileHash -Algorithm SHA256 `
        -LiteralPath $priorQueueStateArchive).Hash
    if ($sourceHash -ne $archiveHash) {
        throw '기존 queue state history SHA256 검증 실패'
    }
}
New-Item -ItemType Directory -Force -Path (
    Split-Path -Parent $queueLock
) | Out-Null
if (Test-Path -LiteralPath $queueLock) {
    $prior = $null
    try { $prior = Read-Json $queueLock } catch {}
    $alive = $false
    if ($null -ne $prior -and $prior.pid) {
        $alive = $null -ne (
            Get-Process -Id ([int]$prior.pid) -ErrorAction SilentlyContinue
        )
    }
    if ($alive) {
        throw "다른 연도 큐 실행 중(pid=$($prior.pid)): $queueLock"
    }
    $archive = Join-Path $stateRoot 'locks\archive_stale'
    New-Item -ItemType Directory -Force -Path $archive | Out-Null
    Move-Item -LiteralPath $queueLock -Destination (
        Join-Path $archive (
            'mfa_year_queue_{0}.lock' -f (Get-Date -Format 'yyyyMMdd_HHmmss')
        )
    )
}
Write-JsonAtomic $queueLock ([ordered]@{
    pid = $PID
    queue_id = $QueueId
    search_master_run_id = $SearchMasterRunId
    years = @($Years)
    started_at = (Get-Date).ToString('o')
    no_automatic_full_clean_retry = $true
})

$yearStates = [ordered]@{}
foreach ($year in $Years) { $yearStates[$year] = New-YearState $year }
$queue = [ordered]@{
    schema_version = 'mfa_r2_unattended_year_queue.v1'
    queue_id = $QueueId
    search_master_run_id = $SearchMasterRunId
    status = 'running'
    years_requested = @($Years)
    search_master_root = $searchMasterRoot
    common_pron_manifest = $CommonPronManifest
    common_pron_adoption_contract = $CommonPronAdoptionContract
    approved_exclusions_root = $ApprovedExclusionsRoot
    alignment_approved_exclusions_root =
        $AlignmentApprovedExclusionsRoot
    direct_export_failed_report = $DirectExportFailedReport
    direct_export_repair_manifest = $DirectExportRepairManifest
    no_automatic_full_clean_retry = $true
    continue_after_blocked_year = (-not [bool]$StopAfterBlockedYear)
    researcher_approval_automatic = $false
    canonical_promotion_automatic = $false
    prior_queue_state_archive = $priorQueueStateArchive
    started_at = (Get-Date).ToString('o')
    updated_at = (Get-Date).ToString('o')
    years = $yearStates
}
Write-JsonAtomic $queueStatePath $queue

$blocked = 0
$machinePassed = 0
$exitCode = 0
$sleepGuardEnabled = $false
try {
    Enable-MfaYearQueueSleepGuard
    $sleepGuardEnabled = $true
    Write-Host 'Windows system sleep guard: enabled' -ForegroundColor Cyan
    # 모든 연도가 공유할 동결 search master를 한 번만 준비한다. 성공 meta가
    # 있으면 다시 쓰지 않으며, 이후 연도별 child runner도 같은 root를 재사용한다.
    $searchMeta = Join-Path $searchMasterRoot '_build_meta.json'
    $searchReady = $false
    if (Test-Path -LiteralPath $searchMeta -PathType Leaf) {
        try { $searchReady = (Read-Json $searchMeta).status -eq 'success' }
        catch { $searchReady = $false }
    }
    if (-not $searchReady) {
        & $python (Join-Path $PSScriptRoot 'python\preflight_search_master.py')
        if ($LASTEXITCODE -ne 0) { throw 'search master preflight 실패' }
        & $python (Join-Path $PSScriptRoot 'python\build_search_master.py') `
            --output-root $searchMasterRoot --run-id $SearchMasterRunId
        if ($LASTEXITCODE -ne 0) { throw 'search master build 실패' }
        if (-not (Test-Path -LiteralPath $searchMeta -PathType Leaf)) {
            throw "search master success meta 없음: $searchMeta"
        }
    }

    foreach ($year in $Years) {
        $state = $yearStates[$year]
        $state.started_at = (Get-Date).ToString('o')
        $state.updated_at = $state.started_at
        $state.attempts_this_invocation = 1
        $state.phase = 'approval_contract'
        Write-JsonAtomic $queueStatePath $queue
        Write-Host "===== $year 무인 연도 큐 =====" -ForegroundColor Cyan
        try {
            $yearWavSelection = Resolve-MfaWavCorpusForYear `
                -Config $config -Year $year
            $yearWavRoot = [string]$yearWavSelection.WavRoot
        } catch {
            $state.status = 'wav_corpus_contract_missing_or_invalid'
            $state.phase = 'blocked_before_mfa'
            $state.failed_reason = $_.Exception.Message
            $state.updated_at = (Get-Date).ToString('o')
            $blocked += 1
            Write-JsonAtomic $queueStatePath $queue
            if ($StopAfterBlockedYear) { break }
            continue
        }

        $approval = Find-Approval $ApprovedExclusionsRoot $year
        $alignmentApproval = Find-Approval `
            $AlignmentApprovedExclusionsRoot $year
        if ($null -eq $approval -and $PrepareMissingReviews) {
            $reviewRoot = Join-Path $ApprovedExclusionsRoot $year
            Write-Host "$year 승인 계약 없음 — pending 검토표 생성"
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
                Join-Path $PSScriptRoot 'prepare_mfa_year_exclusion_review.ps1'
            ) -Year $year -SearchMasterRoot $searchMasterRoot `
                -OutputRoot $reviewRoot
            if ($LASTEXITCODE -ne 0) {
                $state.status = 'review_preparation_failed_preserved'
                $state.failed_reason = "review preparation exit $LASTEXITCODE"
            } else {
                $state.status = 'researcher_exclusion_review_required'
                $state.failed_reason = (
                    'pending 후보를 연구자가 확인하고 승인 계약을 만들 것'
                )
            }
            $state.phase = 'blocked_before_mfa'
            $state.updated_at = (Get-Date).ToString('o')
            $blocked += 1
            Write-JsonAtomic $queueStatePath $queue
            if ($StopAfterBlockedYear) { break }
            continue
        }
        if ($null -eq $approval) {
            $state.status = 'researcher_exclusion_contract_missing'
            $state.phase = 'blocked_before_mfa'
            $state.failed_reason = '승인 제외 계약 없음; MFA는 시작하지 않음'
            $state.updated_at = (Get-Date).ToString('o')
            $blocked += 1
            Write-JsonAtomic $queueStatePath $queue
            if ($StopAfterBlockedYear) { break }
            continue
        }
        if ($null -eq $alignmentApproval) {
            $state.status = 'alignment_exclusion_contract_missing'
            $state.phase = 'blocked_before_mfa'
            $state.failed_reason = (
                '정렬 provenance 승인 제외 계약 없음; MFA/export 시작 안 함'
            )
            $state.updated_at = (Get-Date).ToString('o')
            $blocked += 1
            Write-JsonAtomic $queueStatePath $queue
            if ($StopAfterBlockedYear) { break }
            continue
        }
        $state.approved_exclusions_contract = $alignmentApproval
        $state.export_approved_exclusions_contract = $approval
        $state.phase = 'mfa_or_resume'
        Write-JsonAtomic $queueStatePath $queue

        $runArgs = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            (Join-Path $PSScriptRoot 'run_pre_mfa_bulk_safe.ps1'),
            '-RunId', $SearchMasterRunId, '-Years', $year,
            '-UseDirectDbExport', '-PreferD', '-ForceVerifyLabInput',
            '-CommonPronManifest', $CommonPronManifest,
            '-CommonPronAdoptionContract', $CommonPronAdoptionContract,
            '-ApprovedExclusionsContract', $alignmentApproval,
            '-ExportApprovedExclusionsContract', $approval
        )
        if (-not [string]::IsNullOrWhiteSpace($DirectExportFailedReport)) {
            $runArgs += @(
                '-DirectExportFailedReport', $DirectExportFailedReport,
                '-DirectExportRepairManifest',
                $DirectExportRepairManifest
            )
        }
        if ($year -in @('2020','2021')) {
            $runArgs += '-AllowBaselineCommonPronRerun'
        }
        # 의도적으로 -AllowFullCleanRetry를 전달하지 않는다.
        & powershell.exe @runArgs
        $yearExit = $LASTEXITCODE
        if ($yearExit -ne 0) {
            $directDbPreserved = $false
            try {
                $directDbPreserved = Set-YearStateFromDirectDbCheckpoint `
                    -State $state -StateRoot $stateRoot -Year $year
            } catch {
                $directDbPreserved = $false
            }
            $state.status = if ($directDbPreserved) {
                'post_mfa_export_failed_db_preserved'
            } else {
                'mfa_failed_checkpoint_preserved'
            }
            $state.phase = 'blocked_after_partial_work'
            $state.failed_reason = if ($directDbPreserved) {
                "연도 runner exit $yearExit; MFA 계산 완료 DB checkpoint 보존, " +
                'direct export부터 재개, full clean 금지'
            } else {
                "연도 runner exit $yearExit; temp/DB/log 보존, full clean 금지"
            }
            $state.updated_at = (Get-Date).ToString('o')
            $blocked += 1
            Write-JsonAtomic $queueStatePath $queue
            if ($StopAfterBlockedYear) { break }
            continue
        }

        $state.phase = 'independent_machine_qc'
        Write-JsonAtomic $queueStatePath $queue
        $alignMarker = Join-Path $stateRoot "done\$year.align_done"
        $mergeMarker = Join-Path $stateRoot "done\$year.merge_done"
        $alignmentContractPath = Join-Path $stateRoot (
            "alignment_contracts\$year.json"
        )
        try {
            $align = Read-Json $alignMarker
            $merge = Read-Json $mergeMarker
            $alignment = Read-Json $alignmentContractPath
            if (
                $align.stage -ne 'align' -or $merge.stage -ne 'merge' -or
                $alignment.status -ne 'passed'
            ) {
                throw '완료 marker 또는 alignment contract status 불일치'
            }
            $inputId = [string]$alignment.lab_input_contract_id
            $alignmentId = [string]$alignment.alignment_contract_id
            $db = [string]$align.details.alignment_db
            $acoustic = [string]$alignment.models.acoustic.path
            if (-not (Test-Path -LiteralPath $db -PathType Leaf)) {
                throw "보존 DB 없음: $db"
            }
            if (-not (Test-Path -LiteralPath $acoustic -PathType Leaf)) {
                throw "음향모델 없음: $acoustic"
            }
            $state.input_contract_id = $inputId
            $state.alignment_contract_id = $alignmentId
            $state.retained_alignment_db = $db
            $yearReportRoot = Join-Path $reportRoot $year
            $auditReport = Join-Path $yearReportRoot '01_year_audit.json'
            $missingCsv = Join-Path $yearReportRoot '01_id_inventory.csv'
            $sampleReport = Join-Path $yearReportRoot '02_db_sample.json'
            $sampleCsv = Join-Path $yearReportRoot '02_db_sample.csv'
            $sampleScratch = Join-Path $queueRoot "qc_scratch\$year"
            New-Item -ItemType Directory -Force -Path $yearReportRoot |
                Out-Null
            & $python (Join-Path $PSScriptRoot (
                'python\audit_mfa_research_6tier_year.py'
            )) --year $year --lab-root $yearWavRoot `
                --textgrid-root $finalRoot --acoustic-model $acoustic `
                --approved-exclusions-contract $approval `
                --input-contract-id $inputId `
                --alignment-contract-id $alignmentId `
                --report $auditReport --missing-csv $missingCsv --workers 4
            if ($LASTEXITCODE -ne 0) {
                throw "독립 연도 감사 실패: $auditReport"
            }
            & $python (Join-Path $PSScriptRoot (
                'python\verify_mfa_db_research_6tier_sample.py'
            )) --db $db --year $year `
                --search-master-root $searchMasterRoot `
                --final-root $finalRoot --scratch-root $sampleScratch `
                --acoustic-model $acoustic `
                --alignment-contract $alignmentContractPath `
                --approved-exclusions-contract $approval `
                --report $sampleReport --sample-csv $sampleCsv `
                --sample-size $QcSampleSize
            if ($LASTEXITCODE -ne 0) {
                throw "DB 표본 재수출 검사 실패: $sampleReport"
            }
            $state.machine_audit_report = $auditReport
            $state.db_sample_report = $sampleReport
            $state.status = 'machine_qc_passed_human_review_pending'
            $state.phase = 'complete_not_promoted'
            $machinePassed += 1
        } catch {
            $state.status = 'machine_qc_failed_outputs_preserved'
            $state.phase = 'blocked_after_mfa'
            $state.failed_reason = $_.Exception.Message
            $blocked += 1
        }
        $state.updated_at = (Get-Date).ToString('o')
        Write-JsonAtomic $queueStatePath $queue
        if ($StopAfterBlockedYear -and $state.status -ne (
            'machine_qc_passed_human_review_pending'
        )) { break }
    }
    $queue.status = if ($blocked -gt 0) {
        'completed_with_blocked_years'
    } elseif ($machinePassed -eq $Years.Count) {
        'machine_qc_complete_human_review_pending'
    } else {
        'incomplete'
    }
    if ($blocked -gt 0) { $exitCode = 2 }
} catch {
    $queue.status = 'queue_failed'
    $queue.failure = $_.Exception.Message
    $exitCode = 1
} finally {
    if ($sleepGuardEnabled) {
        Disable-MfaYearQueueSleepGuard
        $sleepGuardEnabled = $false
    }
    $queue.updated_at = (Get-Date).ToString('o')
    $queue.finished_at = (Get-Date).ToString('o')
    $queue.machine_qc_passed_years = $machinePassed
    $queue.blocked_years = $blocked
    Write-JsonAtomic $queueStatePath $queue
    if (Test-Path -LiteralPath $queueLock) {
        try {
            $owned = Read-Json $queueLock
            if (
                [int]$owned.pid -eq $PID -and
                [string]$owned.queue_id -eq $QueueId
            ) {
                Remove-Item -LiteralPath $queueLock -Force
            }
        } catch {
            Write-Warning "연도 큐 lock 해제 확인 필요: $queueLock"
        }
    }
}

Write-Host "연도 큐 상태: $($queue.status)" -ForegroundColor Cyan
Write-Host "상태판 JSON: $queueStatePath"
Write-Host "QC 보고서: $reportRoot"
Write-Host '정본 승격은 연구자 검토 뒤 별도 수행한다.'
exit $exitCode
