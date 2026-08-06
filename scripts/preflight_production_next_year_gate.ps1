#Requires -Version 5.1
<# 직전 생산 연도의 6-tier·동반표·DB·표본·연구자 승인을 결합한다. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2021','2022','2023','2024')]
    [string]$PriorYear,
    [ValidatePattern('^$|^[A-Za-z0-9._-]+$')]
    [string]$ExecutionQueueId = '',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725',
    [string]$Output = ''
)
$ErrorActionPreference = 'Stop'
$nextByPrior = @{
    '2021' = '2022'; '2022' = '2023';
    '2023' = '2024'; '2024' = '2025'
}
$NextYear = [string]$nextByPrior[$PriorYear]
if ([string]::IsNullOrWhiteSpace($ExecutionQueueId)) {
    $ExecutionQueueId = "mfa_r2_prod_safe_body_${PriorYear}_20260803"
}
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
$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$layers = Resolve-ConfiguredPath ([string]$config.layers)
$finalRoot = Resolve-ConfiguredPath (
    [string]$config.textgrid_research_v2_staging
)
$reportRoot = Join-Path $projectRoot (
    "outputs\reports\mfa_year_queue_$ExecutionQueueId\$PriorYear"
)
$reviewRoot = Join-Path $projectRoot (
    "outputs\reviews\mfa_production_${PriorYear}_$ExecutionQueueId"
)
if ([string]::IsNullOrWhiteSpace($Output)) {
    $Output = Join-Path $projectRoot (
        "outputs\reports\GATE_${PriorYear}_TO_${NextYear}.json"
    )
}
$Output = [IO.Path]::GetFullPath($Output)
$sourceReport = Join-Path $projectRoot (
    "outputs\reports\GATE_${PriorYear}_source.json"
)
$coreReport = Join-Path $projectRoot (
    "outputs\reports\GATE_${PriorYear}_core.json"
)
$reviewCsv = Join-Path $reviewRoot '03_RESEARCHER_REVIEW.csv'
$reviewApproval = Join-Path $reviewRoot '04_RESEARCHER_APPROVAL.json'

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
    Join-Path $PSScriptRoot 'verify_production_source_contract.ps1'
) -Year $PriorYear -RequireMorphYearSuccess -Output $sourceReport
$sourceExit = $LASTEXITCODE
& $python (Join-Path $PSScriptRoot (
    'python\mfa_production_year_review.py'
)) validate --report $reviewApproval --review-csv $reviewCsv
$reviewExit = $LASTEXITCODE
& $python (Join-Path $PSScriptRoot (
    'python\preflight_next_year_after_qc.py'
)) --prior-year $PriorYear --next-year $NextYear `
    --audit-report (Join-Path $reportRoot '01_year_audit.json') `
    --align-marker (Join-Path $stateRoot "done\$PriorYear.align_done") `
    --merge-marker (Join-Path $stateRoot "done\$PriorYear.merge_done") `
    --direct-db-ready-marker (Join-Path $stateRoot (
        "done\$PriorYear.direct_db_ready"
    )) `
    --temp-contract (Join-Path $stateRoot (
        "input_contracts\$PriorYear.json"
    )) `
    --sample-equivalence-report (Join-Path $reportRoot (
        '02_db_sample.json'
    )) `
    --researcher-review-report $reviewApproval `
    --expected-search-master-root (Join-Path $layers (
        "05_search_master_pre_mfa_staging\$SearchMasterRunId"
    )) `
    --expected-final-year-root (Join-Path $finalRoot $PriorYear) `
    --expected-pronunciation-mode common_pron_mfa_r2_latest_jamo `
    --report $coreReport
$coreExit = $LASTEXITCODE
$source = if (Test-Path -LiteralPath $sourceReport -PathType Leaf) {
    Get-Content -LiteralPath $sourceReport -Raw -Encoding UTF8 |
        ConvertFrom-Json
} else { $null }
$core = if (Test-Path -LiteralPath $coreReport -PathType Leaf) {
    Get-Content -LiteralPath $coreReport -Raw -Encoding UTF8 |
        ConvertFrom-Json
} else { $null }
$passed = (
    $sourceExit -eq 0 -and $reviewExit -eq 0 -and $coreExit -eq 0 -and
    $null -ne $source -and [string]$source.status -eq 'passed' -and
    $null -ne $core -and [string]$core.status -eq 'passed'
)
$report = [ordered]@{
    schema_version = 'mfa_production_next_year_gate.v1'
    status = if ($passed) { 'passed' } else { 'failed' }
    checked_at = (Get-Date).ToString('o')
    prior_year = $PriorYear
    next_year = $NextYear
    prior_execution_queue_id = $ExecutionQueueId
    source_contract_report = $sourceReport
    production_researcher_review = $reviewApproval
    research_qc_gate_report = $coreReport
    allow_next_year = [bool]$passed
}
Write-JsonAtomic $Output $report
Write-Host "$PriorYear -> $NextYear gate status=$($report.status)"
Write-Host "report=$Output"
if (-not $passed) { exit 1 }
exit 0
