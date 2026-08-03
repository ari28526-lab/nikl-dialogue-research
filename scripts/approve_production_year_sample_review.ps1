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
& $python (Join-Path $PSScriptRoot (
    'python\mfa_production_year_review.py'
)) approve --review-csv $reviewCsv --review-manifest $reviewManifest `
    --approved-by $ApprovedBy --output $approval
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "[$Year] 연구자 인프라 검토 승인 기록: $approval"
Write-Host '이 승인은 실제 음운 실현 판정이 아니다.'
exit 0
