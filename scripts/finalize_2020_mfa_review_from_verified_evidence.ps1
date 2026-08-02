<#
2020 전수 LAB/WAV 검사를 반복하지 않고 이미 검증된 증거만 결합해
Gate B 전 2020 전용 큐의 연구자 승인 후보표를 최종화한다.

이 스크립트는 MFA, LAB 생성, WAV 스캔/이동, 자동 승인을 수행하지 않는다.
기존 결과를 덮어쓰지 않으며 대상 폴더가 비어 있지 않으면 중단한다.
#>

[CmdletBinding()]
param(
    [string]$EvidenceRoot = '',
    [string]$ReviewRoot = '',
    [string]$SearchMasterRoot = '',
    [string]$AudioRecoveryPlan = ''
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

function Write-JsonAtomic([string]$Path, $Payload) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $partial = "$Path.$PID.partial"
    $Payload | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $Path -Force
}

function Write-TextAtomic([string]$Path, [string[]]$Lines) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $partial = "$Path.$PID.partial"
    $Lines | Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $Path -Force
}

$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
if ([string]::IsNullOrWhiteSpace($EvidenceRoot)) {
    $EvidenceRoot = Join-Path $projectRoot (
        'outputs\reviews\archive\' +
        'mfa_exclusions_queue_mfa_r2_prod_2020_20260801_' +
        'pre_symbol_accounting_20260802'
    )
}
if ([string]::IsNullOrWhiteSpace($ReviewRoot)) {
    $ReviewRoot = Join-Path $projectRoot (
        'outputs\reviews\mfa_exclusions_queue_mfa_r2_prod_2020_20260801'
    )
}
$EvidenceRoot = [IO.Path]::GetFullPath($EvidenceRoot)
$ReviewRoot = [IO.Path]::GetFullPath($ReviewRoot)
$yearRoot = Join-Path $ReviewRoot '2020'
$auditReport = Join-Path $EvidenceRoot '2020\01_input_audit_unapproved.json'
$quarantineLog = Join-Path $EvidenceRoot '2020\02_bad_wav_candidates.csv'
$labReport = 'D:\mfa_eojeol\logs\lab_build_2020_latest.json'
if ([string]::IsNullOrWhiteSpace($AudioRecoveryPlan)) {
    $AudioRecoveryPlan = Join-Path $projectRoot (
        'outputs\reports\PLAN_2020_wav_duration_recovery_20260801.csv'
    )
}
$AudioRecoveryPlan = [IO.Path]::GetFullPath($AudioRecoveryPlan)

foreach ($required in @(
    $python, $auditReport, $quarantineLog, $labReport, $AudioRecoveryPlan
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "검증 증거 없음: $required"
    }
}

$labData = Get-Content -LiteralPath $labReport -Raw -Encoding UTF8 |
    ConvertFrom-Json
if (
    [string]$labData.status -ne 'passed' -or
    [string]$labData.year -ne '2020'
) {
    throw '2020 LAB 검증 보고서 identity/status 불일치'
}
$inputContractId = [string]$labData.input_contract_id
if ([string]::IsNullOrWhiteSpace($inputContractId)) {
    throw '2020 LAB 검증 보고서 input_contract_id 누락'
}
if ([string]::IsNullOrWhiteSpace($SearchMasterRoot)) {
    $SearchMasterRoot = [string]$labData.search_master_root
}
$SearchMasterRoot = [IO.Path]::GetFullPath($SearchMasterRoot)
if (-not (Test-Path -LiteralPath $SearchMasterRoot -PathType Container)) {
    throw "search master 없음: $SearchMasterRoot"
}

if (Test-Path -LiteralPath $yearRoot -PathType Container) {
    $existing = @(Get-ChildItem -LiteralPath $yearRoot -Force)
    if ($existing.Count -gt 0) {
        throw "2020 최종 검토 폴더가 비어 있지 않아 덮어쓰지 않음: $yearRoot"
    }
} else {
    New-Item -ItemType Directory -Path $yearRoot | Out-Null
}

$reviewCsv = Join-Path $yearRoot '03_RESEARCHER_REVIEW.csv'
$reviewManifest = Join-Path $yearRoot '03_RESEARCHER_REVIEW_MANIFEST.json'
& $python (Join-Path $PSScriptRoot (
    'python\prepare_mfa_exclusion_review.py'
)) --audit-report $auditReport --year 2020 `
    --search-master-root $SearchMasterRoot `
    --input-contract-id $inputContractId `
    --quarantine-log $quarantineLog `
    --audio-recovery-plan $AudioRecoveryPlan `
    --lab-report $labReport `
    --output-csv $reviewCsv --output-report $reviewManifest
if ($LASTEXITCODE -ne 0) {
    throw '기존 검증 증거 결합 실패; MFA/LAB/WAV 작업은 시작하지 않음'
}

$manifest = Get-Content -LiteralPath $reviewManifest -Raw -Encoding UTF8 |
    ConvertFrom-Json
$audioCount = [int]$manifest.candidate_counts_by_reason.audio_pairing_unresolved
$emptyCount = [int](
    $manifest.candidate_counts_by_reason.empty_reference_unresolved_symbol
)
$partialCount = [int]$manifest.partial_lab_unresolved_symbol_count
if (
    [int]$manifest.candidate_count -ne 1887 -or
    $audioCount -ne 1834 -or
    $emptyCount -ne 53 -or
    $partialCount -ne 6158 -or
    [int]$manifest.uncovered_audio_pairing_issue_count -ne 0
) {
    throw (
        '2020 고정 증거 합계 불일치: expected candidates=1887, ' +
        'audio=1834, empty=53, partial=6158'
    )
}

$categorySummary = [ordered]@{
    schema_version = 'mfa_exclusion_review_category_summary.v1'
    status = 'pending_researcher_review'
    year = '2020'
    input_contract_id = $inputContractId
    final_review_csv = $reviewCsv
    final_review_manifest = $reviewManifest
    candidates = [ordered]@{
        audio_pairing_unresolved = $audioCount
        empty_reference_unresolved_symbol = $emptyCount
        total = [int]$manifest.candidate_count
    }
    retained_with_warning = [ordered]@{
        partial_lab_unresolved_symbol = $partialCount
        exclusion_candidate = $false
        warning_field = 'pron_reference_status=unresolved_symbol'
    }
    policy = [ordered]@{
        no_global_symbol_guessing = $true
        no_automatic_approval = $true
        no_full_lab_or_wav_rescan = $true
        no_mfa_started = $true
        prior_1834_review = 'superseded_and_archived'
    }
}
$categoryPath = Join-Path $yearRoot '00_CATEGORY_SUMMARY.json'
Write-JsonAtomic $categoryPath $categorySummary

$guidePath = Join-Path $yearRoot '00_READ_ME_FIRST.md'
$guide = @(
    '# 2020 MFA 제외 최종 승인표',
    '',
    '이 폴더가 2020년 승인 검토의 유일한 활성본이다.',
    '기존 1,834건 표는 미해결 기호 빈 LAB 53건이 빠져 archive했다.',
    '',
    '- `audio_pairing_unresolved`: 1,834건',
    '- `empty_reference_unresolved_symbol`: 53건',
    '- 최종 승인 후보: 1,887건',
    '- 부분 LAB 보존·경고: 6,158건(승인 제외 후보가 아님)',
    '',
    '전수 WAV/LAB 검사는 다시 수행하지 않았다. 기존 보고서와 인벤토리의',
    '계약 ID·합계·SHA-256을 검증한 뒤 결합했다.',
    '',
    '아직 자동 승인, MFA 정렬, WAV 이동, 정본 승격은 수행하지 않았다.'
)
Write-TextAtomic $guidePath $guide

$summary = [ordered]@{
    schema_version = 'mfa_full6y_approval_review_preparation.v1'
    status = 'researcher_review_required'
    created_at = (Get-Date).ToString('o')
    queue_id = 'mfa_r2_prod_2020_20260801'
    search_master_run_id = 'pre_mfa_v1_20260725'
    review_root = $ReviewRoot
    years = @('2020')
    total_candidates = [int]$manifest.candidate_count
    records = @([ordered]@{
        year = '2020'
        status = 'prepared_from_verified_evidence'
        candidate_count = [int]$manifest.candidate_count
        input_contract_id = $inputContractId
        review_csv = $reviewCsv
        manifest = $reviewManifest
    })
    starts_mfa = $false
    moves_wav = $false
    approves_exclusions = $false
    promotes_canonical_outputs = $false
}
Write-JsonAtomic (Join-Path $ReviewRoot 'PREPARE_SUMMARY.json') $summary

$evidenceReport = Join-Path $projectRoot (
    'outputs\reports\EVIDENCE_2020_mfa_exclusion_final_20260802.json'
)
Write-JsonAtomic $evidenceReport $categorySummary

Write-Host '[OK] 기존 증거만 결합한 2020 최종 승인표 준비 완료' `
    -ForegroundColor Green
Write-Host '전수 WAV/LAB 재검사: 실행하지 않음'
Write-Host "후보: $($manifest.candidate_count) (1,834 + 53)"
Write-Host "부분 LAB 경고 보존: $partialCount"
Write-Host "검토 파일: $reviewCsv"
Write-Host 'MFA·자동 승인: 실행하지 않음'
