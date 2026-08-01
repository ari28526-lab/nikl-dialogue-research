<# Convert the completed 2020 production review CSV into a signed gate report. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovedBy,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_prod_2020_20260801'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
$python = [IO.Path]::GetFullPath(
    [Environment]::ExpandEnvironmentVariables(
        ([string]$config.pipeline_python).Replace('/', '\')
    )
)
$reviewRoot = Join-Path $projectRoot "outputs\reviews\mfa_production_2020_$QueueId"
& $python (Join-Path $PSScriptRoot 'python\mfa_production_year_review.py') `
    approve `
    --review-csv (Join-Path $reviewRoot '03_RESEARCHER_REVIEW.csv') `
    --review-manifest (Join-Path $reviewRoot '03_RESEARCHER_REVIEW_MANIFEST.json') `
    --approved-by $ApprovedBy `
    --output (Join-Path $reviewRoot '04_RESEARCHER_APPROVAL.json')
exit $LASTEXITCODE
