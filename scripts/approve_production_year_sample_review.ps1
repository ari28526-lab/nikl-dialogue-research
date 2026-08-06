#Requires -Version 5.1
<# 한 생산 연도의 완료된 인프라 표본 검토를 명시 승인 기록으로 만든다. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2021','2022','2023','2024','2025')]
    [string]$Year,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$ApprovedBy,
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovalStatement,
    [Parameter(Mandatory=$true)]
    [ValidateRange(5,10000)]
    [int]$ExpectedRowCount,
    [ValidatePattern('^$|^[A-Za-z0-9._-]+$')]
    [string]$ExecutionQueueId = ''
)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($ExecutionQueueId)) {
    $ExecutionQueueId = "mfa_r2_prod_safe_body_${Year}_20260803"
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
$reviewRoot = Join-Path $projectRoot (
    "outputs\reviews\mfa_production_${Year}_$ExecutionQueueId"
)
$reviewCsv = Join-Path $reviewRoot '03_RESEARCHER_REVIEW.csv'
$reviewManifest = Join-Path $reviewRoot (
    '03_RESEARCHER_REVIEW_MANIFEST.json'
)
$approval = Join-Path $reviewRoot '04_RESEARCHER_APPROVAL.json'
$pendingArchive = Join-Path $reviewRoot (
    '03_RESEARCHER_REVIEW_PENDING_ORIGINAL.csv'
)
$decisionRecord = Join-Path $reviewRoot '03_RESEARCHER_DECISION.json'
$rowNote = (
    '연구자 직접 검토 승인: 동일 발화·6-tier·정렬·검색 정보가 ' +
    '대체로 적절함; 실제 음운 실현 판정 아님'
)
& $python (Join-Path $PSScriptRoot (
    'python\mfa_production_year_review.py'
)) approve-explicit --review-csv $reviewCsv `
    --review-manifest $reviewManifest `
    --approved-by $ApprovedBy `
    --approval-statement $ApprovalStatement `
    --expected-row-count $ExpectedRowCount `
    --pending-archive $pendingArchive `
    --decision-record $decisionRecord `
    --row-note $rowNote `
    --output $approval
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "[$Year] 연구자 인프라 검토 승인 기록: $approval"
Write-Host "원 pending CSV 보존: $pendingArchive"
Write-Host "명시 결정 근거: $decisionRecord"
Write-Host '수동 CSV 편집이나 자동 승인 추론을 수행하지 않았다.'
Write-Host '이 승인은 실제 음운 실현 판정이 아니다.'
exit 0
