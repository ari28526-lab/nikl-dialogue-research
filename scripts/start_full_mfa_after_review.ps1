<#
연구자가 6개년 제외 후보표를 확인한 뒤 실행하는 단일 안전 진입점.

1. approved로 표시된 검토 CSV만 연도별 승인 계약으로 만든다.
2. 전체 repository test를 포함한 최종 preflight를 실행한다.
3. 정확히 GO일 때만 체크포인트형 연도 MFA 큐를 시작한다.

실제 발음·음운 실현을 승인하지 않으며 정본 승격도 자동화하지 않는다.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovedBy,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_full6y_20260801',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725',
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string[]]$Years = @('2020','2021','2022','2023','2024','2025'),
    [string]$YearsCsv = '',
    [string]$ReviewRoot = '',
    [string]$CommonPronManifest = (
        'D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\' +
        '00_contract\release_manifest.json'
    ),
    [string]$CommonPronAdoptionContract = (
        'D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\' +
        '00_contract\adoption_contract.json'
    ),
    [ValidateRange(5, 200)]
    [int]$QcSampleSize = 24,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
. (Join-Path $PSScriptRoot 'mfa_year_selection.ps1')
$Years = @(
    Resolve-MfaYearSelection -Years $Years -YearsCsv $YearsCsv
)
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}

$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
if ([string]::IsNullOrWhiteSpace($ReviewRoot)) {
    $ReviewRoot = Join-Path $projectRoot (
        "outputs\reviews\mfa_exclusions_queue_$QueueId"
    )
}
$ReviewRoot = [IO.Path]::GetFullPath($ReviewRoot)
$CommonPronManifest = [IO.Path]::GetFullPath($CommonPronManifest)
$CommonPronAdoptionContract = [IO.Path]::GetFullPath(
    $CommonPronAdoptionContract
)
foreach ($required in @(
    $python, $CommonPronManifest, $CommonPronAdoptionContract
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 파일 없음: $required"
    }
}

$approvedAt = (Get-Date).ToString('o')
foreach ($year in $Years) {
    $yearRoot = Join-Path $ReviewRoot $year
    $reviewCsv = Join-Path $yearRoot '03_RESEARCHER_REVIEW.csv'
    $manifest = Join-Path $yearRoot '03_RESEARCHER_REVIEW_MANIFEST.json'
    $approval = Join-Path $yearRoot 'approved_exclusions.json'
    foreach ($required in @($reviewCsv, $manifest)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "$year 연구자 검토자료 없음: $required"
        }
    }
    $reviewMeta = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $inputContractId = [string]$reviewMeta.input_contract_id
    if (
        [string]$reviewMeta.year -ne $year -or
        [string]::IsNullOrWhiteSpace($inputContractId) -or
        [bool]$reviewMeta.automatic_approval_performed
    ) {
        throw "$year 검토 manifest identity/자동승인 정책 불일치"
    }
    if (Test-Path -LiteralPath $approval -PathType Leaf) {
        & $python (Join-Path $PSScriptRoot (
            'python\mfa_exclusion_contract.py'
        )) validate --contract $approval --year $year `
            --input-contract-id $inputContractId
        if ($LASTEXITCODE -ne 0) {
            throw "$year 기존 승인 계약 검증 실패; 자동 덮어쓰기 금지"
        }
        continue
    }
    & $python (Join-Path $PSScriptRoot (
        'python\mfa_exclusion_contract.py'
    )) build --review-csv $reviewCsv --output $approval `
        --year $year --input-contract-id $inputContractId `
        --approved-by $ApprovedBy --approved-at $approvedAt
    if ($LASTEXITCODE -ne 0) {
        throw (
            "$year 승인 계약 생성 실패. pending 행이 남았거나 " +
            '검토표가 입력 계약과 다름; MFA는 시작하지 않음.'
        )
    }
}

$preflightReport = Join-Path $projectRoot (
    "outputs\reports\PREFLIGHT_mfa_year_queue_${QueueId}_after_review.json"
)
$preflightArgs = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    (Join-Path $PSScriptRoot 'preflight_mfa_year_queue.ps1'),
    '-QueueId', $QueueId,
    '-SearchMasterRunId', $SearchMasterRunId,
    '-YearsCsv', (@($Years) -join ','),
    '-CommonPronManifest', $CommonPronManifest,
    '-CommonPronAdoptionContract', $CommonPronAdoptionContract,
    '-ApprovedExclusionsRoot', $ReviewRoot,
    '-Output', $preflightReport,
    '-RunRepositoryTests'
)
& powershell.exe @preflightArgs
$preflightExit = $LASTEXITCODE
if (-not (Test-Path -LiteralPath $preflightReport -PathType Leaf)) {
    throw '최종 preflight 보고서가 생성되지 않음; MFA는 시작하지 않음.'
}
$preflight = Get-Content -LiteralPath $preflightReport -Raw -Encoding UTF8 |
    ConvertFrom-Json
if (
    $preflightExit -ne 0 -or
    [string]$preflight.status -ne 'GO' -or
    [bool]$preflight.starts_mfa -ne $false -or
    [bool]$preflight.approves_exclusions -ne $false -or
    [bool]$preflight.promotes_canonical_outputs -ne $false
) {
    Write-Host '최종 preflight가 GO가 아님; MFA를 시작하지 않음.' `
        -ForegroundColor Red
    Write-Host "보고서: $preflightReport"
    exit 1
}

Write-Host '[GO] 승인 계약·입력·모델·저장공간·테스트 통과' `
    -ForegroundColor Green
Write-Host "preflight: $preflightReport"
if ($PreflightOnly) {
    Write-Host 'PreflightOnly: 연도 MFA 큐는 시작하지 않음.'
    exit 0
}

$queueArgs = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    (Join-Path $PSScriptRoot 'run_mfa_year_queue_safe.ps1'),
    '-QueueId', $QueueId,
    '-SearchMasterRunId', $SearchMasterRunId,
    '-YearsCsv', (@($Years) -join ','),
    '-CommonPronManifest', $CommonPronManifest,
    '-CommonPronAdoptionContract', $CommonPronAdoptionContract,
    '-ApprovedExclusionsRoot', $ReviewRoot,
    '-QcSampleSize', $QcSampleSize
)

Write-Host '전수 연도 큐를 시작한다. 이 창을 닫지 말 것.' `
    -ForegroundColor Cyan
Write-Host '연도 전체 자동 clean 재계산·자동 정본 승격은 금지된 상태다.'
# 의도적으로 -AllowFullCleanRetry와 -PrepareMissingReviews를 전달하지 않는다.
& powershell.exe @queueArgs
exit $LASTEXITCODE
