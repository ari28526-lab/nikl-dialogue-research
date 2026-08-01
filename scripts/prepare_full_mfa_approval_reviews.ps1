<#
2020–2025 전수 MFA 전에 필요한 연구자 제외 검토표만 준비한다.

이 스크립트는 MFA, WAV 이동, 제외 승인, 정본 승격을 수행하지 않는다.
기존 검토 CSV가 있으면 연구자 입력 보호를 위해 덮어쓰지 않는다.
#>

[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_full6y_20260801',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725',
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string[]]$Years = @('2020','2021','2022','2023','2024','2025'),
    [string]$ReviewRoot = ''
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
    $Payload | ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $Path -Force
}

$layersRoot = Resolve-ConfiguredPath ([string]$config.layers)
$searchMasterRoot = Join-Path $layersRoot (
    "05_search_master_pre_mfa_staging\$SearchMasterRunId"
)
if (-not (Test-Path -LiteralPath (
    Join-Path $searchMasterRoot '_build_meta.json'
) -PathType Leaf)) {
    throw "동결 search master 없음: $searchMasterRoot"
}
if ([string]::IsNullOrWhiteSpace($ReviewRoot)) {
    $ReviewRoot = Join-Path $projectRoot (
        "outputs\reviews\mfa_exclusions_queue_$QueueId"
    )
}
$ReviewRoot = [IO.Path]::GetFullPath($ReviewRoot)
New-Item -ItemType Directory -Force -Path $ReviewRoot | Out-Null

$records = New-Object System.Collections.Generic.List[object]
foreach ($year in $Years) {
    $yearRoot = Join-Path $ReviewRoot $year
    $reviewCsv = Join-Path $yearRoot '03_RESEARCHER_REVIEW.csv'
    $manifest = Join-Path $yearRoot '03_RESEARCHER_REVIEW_MANIFEST.json'
    $approval = Join-Path $yearRoot 'approved_exclusions.json'
    if (Test-Path -LiteralPath $approval -PathType Leaf) {
        throw (
            "$year 승인 계약이 이미 있음. 준비 스크립트로 덮어쓰지 않음: " +
            $approval
        )
    }
    $csvExists = Test-Path -LiteralPath $reviewCsv -PathType Leaf
    $manifestExists = Test-Path -LiteralPath $manifest -PathType Leaf
    if ($csvExists -xor $manifestExists) {
        throw "$year 검토자료가 부분 상태임; 자동 덮어쓰기 금지: $yearRoot"
    }
    if ($csvExists -and $manifestExists) {
        $data = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if (
            [string]$data.year -ne $year -or
            [string]$data.status -ne 'pending_researcher_review' -or
            [bool]$data.automatic_approval_performed
        ) {
            throw "$year 기존 검토 manifest identity/status 불일치"
        }
        $records.Add([ordered]@{
            year = $year
            status = 'existing_review_preserved'
            candidate_count = [int]$data.candidate_count
            input_contract_id = [string]$data.input_contract_id
            review_csv = $reviewCsv
            manifest = $manifest
        })
        continue
    }

    Write-Host "===== $year 승인 후보표 준비 =====" -ForegroundColor Cyan
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
        Join-Path $PSScriptRoot 'prepare_mfa_year_exclusion_review.ps1'
    ) -Year $year -SearchMasterRoot $searchMasterRoot `
        -OutputRoot $yearRoot
    if ($LASTEXITCODE -ne 0) {
        throw "$year 승인 후보표 준비 실패; 기존 원자료는 변경하지 않음"
    }
    $data = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $records.Add([ordered]@{
        year = $year
        status = 'prepared_pending_researcher_review'
        candidate_count = [int]$data.candidate_count
        input_contract_id = [string]$data.input_contract_id
        review_csv = $reviewCsv
        manifest = $manifest
    })
}

$rows = @($records.ToArray())
$summary = [ordered]@{
    schema_version = 'mfa_full6y_approval_review_preparation.v1'
    status = 'researcher_review_required'
    created_at = (Get-Date).ToString('o')
    queue_id = $QueueId
    search_master_run_id = $SearchMasterRunId
    review_root = $ReviewRoot
    years = @($Years)
    total_candidates = [int](
        ($rows | Measure-Object -Property candidate_count -Sum).Sum
    )
    records = $rows
    starts_mfa = $false
    moves_wav = $false
    approves_exclusions = $false
    promotes_canonical_outputs = $false
}
$summaryPath = Join-Path $ReviewRoot 'PREPARE_SUMMARY.json'
Write-JsonAtomic $summaryPath $summary

Write-Host ''
Write-Host '[OK] 6개년 승인 후보표 준비 완료' -ForegroundColor Green
Write-Host "후보 합계: $($summary.total_candidates)"
Write-Host "검토 root: $ReviewRoot"
Write-Host "요약: $summaryPath"
Write-Host '각 연도 03_RESEARCHER_REVIEW.csv의 후보를 확인할 것.'
Write-Host '제외에 동의하는 행만 decision=approved로 변경한다.'
Write-Host '동의하지 않는 후보는 approved로 바꾸지 말고 원인 수정이 필요하다.'
Write-Host '이 스크립트는 MFA·WAV 이동·자동 승인·정본 승격을 하지 않았다.'
