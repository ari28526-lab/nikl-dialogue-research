<# Gate 2021 entry on exact 2020 production contracts and researcher review. #>
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_prod_2020_export_20260803',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725',
    [string]$Output = ''
)
$ErrorActionPreference = 'Stop'
$requiredQueueId = 'mfa_r2_prod_2020_export_20260803'
if ($QueueId -ne $requiredQueueId) {
    throw (
        "2020 Gate B는 최종 생산 queue만 허용: " +
        "expected=$requiredQueueId, actual=$QueueId"
    )
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
$finalRoot = Resolve-ConfiguredPath ([string]$config.textgrid_research_v2_staging)
$reportRoot = Join-Path $projectRoot "outputs\reports\mfa_year_queue_$QueueId\2020"
$reviewRoot = Join-Path $projectRoot "outputs\reviews\mfa_production_2020_$QueueId"
$sourceReport = Join-Path $projectRoot 'outputs\reports\GATE_B_2020_source.json'
$coreReport = Join-Path $projectRoot 'outputs\reports\GATE_B_2020_core.json'
if ([string]::IsNullOrWhiteSpace($Output)) {
    $Output = Join-Path $projectRoot 'outputs\reports\GATE_B_2020_TO_2021.json'
}
$Output = [IO.Path]::GetFullPath($Output)

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
    Join-Path $PSScriptRoot 'verify_production_source_contract.ps1'
) -Year 2020 -RequireMorphYearSuccess -Output $sourceReport
$sourceExit = $LASTEXITCODE

$reviewCsv = Join-Path $reviewRoot '03_RESEARCHER_REVIEW.csv'
$reviewApproval = Join-Path $reviewRoot '04_RESEARCHER_APPROVAL.json'
& $python (Join-Path $PSScriptRoot 'python\mfa_production_year_review.py') `
    validate --report $reviewApproval --review-csv $reviewCsv
$reviewExit = $LASTEXITCODE

& $python (Join-Path $PSScriptRoot 'python\preflight_next_year_after_qc.py') `
    --prior-year 2020 --next-year 2021 `
    --audit-report (Join-Path $reportRoot '01_year_audit.json') `
    --align-marker (Join-Path $stateRoot 'done\2020.align_done') `
    --merge-marker (Join-Path $stateRoot 'done\2020.merge_done') `
    --temp-contract (Join-Path $stateRoot 'input_contracts\2020.json') `
    --sample-equivalence-report (Join-Path $reportRoot '02_db_sample.json') `
    --researcher-review-report $reviewApproval `
    --expected-search-master-root (Join-Path $layers "05_search_master_pre_mfa_staging\$SearchMasterRunId") `
    --expected-final-year-root (Join-Path $finalRoot '2020') `
    --expected-pronunciation-mode common_pron_mfa_r2_latest_jamo `
    --report $coreReport
$coreExit = $LASTEXITCODE

$source = if (Test-Path $sourceReport) {
    Get-Content -Raw -Encoding UTF8 $sourceReport | ConvertFrom-Json
} else { $null }
$core = if (Test-Path $coreReport) {
    Get-Content -Raw -Encoding UTF8 $coreReport | ConvertFrom-Json
} else { $null }
$passed = (
    $sourceExit -eq 0 -and $reviewExit -eq 0 -and $coreExit -eq 0 -and
    $null -ne $source -and [string]$source.status -eq 'passed' -and
    $null -ne $core -and [string]$core.status -eq 'passed'
)
$report = [ordered]@{
    schema_version = 'mfa_2020_to_2021_gate_b.v1'
    status = if ($passed) { 'passed' } else { 'failed' }
    checked_at = (Get-Date).ToString('o')
    prior_year = '2020'
    next_year = '2021'
    source_contract_report = $sourceReport
    production_researcher_review = $reviewApproval
    research_qc_gate_report = $coreReport
    allow_remaining_years = [bool]$passed
}
Write-JsonAtomic $Output $report
Write-Host "Gate B status=$($report.status)"
Write-Host "report=$Output"
if (-not $passed) { exit 1 }
