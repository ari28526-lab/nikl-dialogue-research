#Requires -Version 5.1
<#
2021-2025 안전 본체 제외 범주에 대한 연구자 승인을 연도별 계약으로 기록한다.

이 스크립트는 pending 후보표를 수정하지 않고 별도 승인 CSV/기록/계약만 만든다.
MFA, WAV/LAB 변경, 정본 승격은 수행하지 않는다.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$ApprovedBy,
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovalStatement,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_prod_safe_body_2021_2025_20260803',
    [string]$YearsCsv = '2021,2022,2023,2024,2025',
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
. (Join-Path $PSScriptRoot 'mfa_year_selection.ps1')
$years = @(
    Resolve-MfaYearSelection -YearsCsv $YearsCsv
)
if (@($years | Where-Object { $_ -eq '2020' }).Count -gt 0) {
    throw '이 진입점은 2020 완성본을 다루지 않음'
}

$requiredStatementTokens = @(
    '2021',
    '2025',
    'audio_pairing_unresolved',
    'empty_reference_unresolved_symbol',
    'text_duration_impossible',
    '안전 본체 MFA',
    '후속 shard'
)
foreach ($token in $requiredStatementTokens) {
    if (-not $ApprovalStatement.Contains($token)) {
        throw "승인 문구에 필수 정책이 없음: $token"
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
$python = [IO.Path]::GetFullPath(
    [Environment]::ExpandEnvironmentVariables(
        ([string]$config.pipeline_python).Replace('/', '\')
    )
)
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "pipeline Python 없음: $python"
}
$reviewRoot = Join-Path $projectRoot (
    "outputs\reviews\mfa_exclusions_queue_$QueueId"
)
if (-not (Test-Path -LiteralPath $reviewRoot -PathType Container)) {
    throw "검토 root 없음: $reviewRoot"
}

# 모든 연도의 후보 SHA·범주·행 수를 먼저 검증한다. 이 검사가 실패하면 어느
# 연도에도 승인 파일을 쓰지 않는다.
$validationRoot = Join-Path ([IO.Path]::GetTempPath()) (
    'mfa_category_approval_' + [Guid]::NewGuid().ToString('N')
)
try {
    [void](New-Item -ItemType Directory -Path $validationRoot)
    $summaryArgs = @(
        (Join-Path $PSScriptRoot (
            'python\build_mfa_exclusion_category_summary.py'
        )),
        '--review-root', $reviewRoot,
        '--years'
    )
    $summaryArgs += @($years)
    $summaryArgs += @(
        '--output-json', (Join-Path $validationRoot 'summary.json'),
        '--output-csv', (Join-Path $validationRoot 'summary.csv'),
        '--output-md', (Join-Path $validationRoot 'summary.md')
    )
    & $python @summaryArgs
    if ($LASTEXITCODE -ne 0) {
        throw '5개년 후보 SHA·범주 사전 검증 실패'
    }
} finally {
    if (Test-Path -LiteralPath $validationRoot -PathType Container) {
        Remove-Item -LiteralPath $validationRoot -Recurse -Force
    }
}

$reasonCodes = @(
    'audio_pairing_unresolved',
    'empty_reference_unresolved_symbol',
    'text_duration_impossible'
)
$approveScript = Join-Path $PSScriptRoot (
    'python\approve_mfa_exclusion_categories.py'
)
$contractScript = Join-Path $PSScriptRoot 'python\mfa_exclusion_contract.py'

foreach ($year in $years) {
    $yearRoot = Join-Path $reviewRoot $year
    $candidate = Join-Path $yearRoot '03_RESEARCHER_REVIEW.csv'
    $manifest = Join-Path $yearRoot '03_RESEARCHER_REVIEW_MANIFEST.json'
    $approvedCsv = Join-Path $yearRoot '04_RESEARCHER_APPROVED.csv'
    $approvalRecord = Join-Path $yearRoot '04_RESEARCHER_APPROVAL.json'
    $contract = Join-Path $yearRoot 'approved_exclusions.json'
    foreach ($required in @($candidate, $manifest)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "$year 승인 입력 없음: $required"
        }
    }
    $manifestData = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $inputContractId = [string]$manifestData.input_contract_id
    if (
        [string]$manifestData.year -ne $year -or
        [string]::IsNullOrWhiteSpace($inputContractId)
    ) {
        throw "$year 후보 manifest identity 불일치"
    }

    $outputs = @($approvedCsv, $approvalRecord, $contract)
    $existing = @(
        $outputs | Where-Object {
            Test-Path -LiteralPath $_ -PathType Leaf
        }
    )
    if ($existing.Count -gt 0 -and $existing.Count -lt $outputs.Count) {
        throw "$year 승인 산출물이 부분 생성됨; 자동 덮어쓰기 금지"
    }
    if ($existing.Count -eq $outputs.Count) {
        $record = Get-Content -LiteralPath $approvalRecord -Raw -Encoding UTF8 |
            ConvertFrom-Json
        $recordReasons = @(
            $record.approved_categories.PSObject.Properties.Name |
                Sort-Object
        )
        $expectedReasons = @($reasonCodes | Sort-Object)
        if (
            [string]$record.schema_version -ne
                'mfa_exclusion_category_approval.v1' -or
            [string]$record.status -ne 'approved' -or
            [string]$record.year -ne $year -or
            [string]$record.input_contract_id -ne $inputContractId -or
            [string]$record.approved_by -ne $ApprovedBy -or
            [string]$record.approval_statement -ne $ApprovalStatement -or
            ($recordReasons -join ',') -ne ($expectedReasons -join ',')
        ) {
            throw "$year 기존 범주 승인 기록이 이번 명시 승인과 다름"
        }
        & $python $contractScript validate --contract $contract `
            --year $year --input-contract-id $inputContractId
        if ($LASTEXITCODE -ne 0) {
            throw "$year 기존 승인 계약 검증 실패"
        }
        Write-Host "[$year] 기존 명시 승인 계약 재검증 완료"
        continue
    }

    if ($PreflightOnly) {
        Write-Host "[$year] 승인 입력 검증 완료; 아직 계약 생성 안 함"
        continue
    }

    $approveArgs = @(
        $approveScript,
        '--candidate-csv', $candidate,
        '--candidate-manifest', $manifest,
        '--output-approved-csv', $approvedCsv,
        '--output-approval-record', $approvalRecord,
        '--output-contract', $contract,
        '--approved-by', $ApprovedBy,
        '--approval-statement', $ApprovalStatement
    )
    foreach ($reason in $reasonCodes) {
        $approveArgs += @('--approve-reason-code', $reason)
    }
    & $python @approveArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$year 범주 승인 계약 생성 실패"
    }
    & $python $contractScript validate --contract $contract `
        --year $year --input-contract-id $inputContractId
    if ($LASTEXITCODE -ne 0) {
        throw "$year 생성 승인 계약 재검증 실패"
    }
    Write-Host "[$year] 범주 승인 계약 생성·재검증 완료"
}

if ($PreflightOnly) {
    Write-Host '[OK] 승인 전용 preflight 완료; 승인·MFA 실행 없음' `
        -ForegroundColor Green
} else {
    Write-Host '[OK] 명시 승인 계약 기록 완료; MFA는 시작하지 않음' `
        -ForegroundColor Green
}
Write-Host "review root: $reviewRoot"
exit 0
