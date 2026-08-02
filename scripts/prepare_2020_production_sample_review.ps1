<# Prepare a minimal 2020 production sample review after machine QC. #>
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_prod_2020_20260801',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
. (Join-Path $PSScriptRoot 'mfa_wav_corpus.ps1')
function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}
$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$layers = Resolve-ConfiguredPath ([string]$config.layers)
$wavRoot = [string](
    Resolve-MfaWavCorpusForYear -Config $config -Year '2020'
).WavRoot
$reportRoot = Join-Path $projectRoot "outputs\reports\mfa_year_queue_$QueueId\2020"
$reviewRoot = Join-Path $projectRoot "outputs\reviews\mfa_production_2020_$QueueId"
$queueState = Join-Path $stateRoot "year_queue\$QueueId\queue_state.json"
if (-not (Test-Path -LiteralPath $queueState -PathType Leaf)) {
    throw "2020 queue state missing: $queueState"
}
$queue = Get-Content -LiteralPath $queueState -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$queue.years.'2020'.status -ne 'machine_qc_passed_human_review_pending') {
    throw "2020 machine QC is not ready: $($queue.years.'2020'.status)"
}
$args = @(
    (Join-Path $PSScriptRoot 'python\mfa_production_year_review.py'),
    'prepare', '--year', '2020',
    '--sample-csv', (Join-Path $reportRoot '02_db_sample.csv'),
    '--sample-report', (Join-Path $reportRoot '02_db_sample.json'),
    '--align-marker', (Join-Path $stateRoot 'done\2020.align_done'),
    '--alignment-contract', (Join-Path $stateRoot 'alignment_contracts\2020.json'),
    '--search-master-root', (Join-Path $layers "05_search_master_pre_mfa_staging\$SearchMasterRunId"),
    '--wav-root', $wavRoot,
    '--output-csv', (Join-Path $reviewRoot '03_RESEARCHER_REVIEW.csv'),
    '--output-manifest', (Join-Path $reviewRoot '03_RESEARCHER_REVIEW_MANIFEST.json')
)
& $python @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Review CSV: $(Join-Path $reviewRoot '03_RESEARCHER_REVIEW.csv')"
Write-Host 'Set decision=approved only after checking linkage and six-tier usability.'
