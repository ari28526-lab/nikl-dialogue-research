#Requires -Version 5.1
<# 기계 QC를 통과한 한 생산 연도의 연구자 인프라 표본을 준비한다. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2021','2022','2023','2024','2025')]
    [string]$Year,
    [ValidatePattern('^$|^[A-Za-z0-9._-]+$')]
    [string]$ExecutionQueueId = '',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725'
)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($ExecutionQueueId)) {
    $ExecutionQueueId = "mfa_r2_prod_safe_body_${Year}_20260803"
}
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
    Resolve-MfaWavCorpusForYear -Config $config -Year $Year
).WavRoot
$reportRoot = Join-Path $projectRoot (
    "outputs\reports\mfa_year_queue_$ExecutionQueueId\$Year"
)
$reviewRoot = Join-Path $projectRoot (
    "outputs\reviews\mfa_production_${Year}_$ExecutionQueueId"
)
$queueState = Join-Path $stateRoot (
    "year_queue\$ExecutionQueueId\queue_state.json"
)
if (-not (Test-Path -LiteralPath $queueState -PathType Leaf)) {
    throw "생산 연도 queue state 없음: $queueState"
}
$queue = Get-Content -LiteralPath $queueState -Raw -Encoding UTF8 |
    ConvertFrom-Json
$requested = @($queue.years_requested)
$yearState = $queue.years.PSObject.Properties[$Year].Value
if (
    [string]$queue.queue_id -ne $ExecutionQueueId -or
    $requested.Count -ne 1 -or $requested[0] -ne $Year -or
    $null -eq $yearState -or
    [string]$yearState.status -ne
        'machine_qc_passed_human_review_pending'
) {
    throw "$Year 기계 QC 완료 단독 큐가 아님"
}
$args = @(
    (Join-Path $PSScriptRoot 'python\mfa_production_year_review.py'),
    'prepare', '--year', $Year,
    '--sample-csv', (Join-Path $reportRoot '02_db_sample.csv'),
    '--sample-report', (Join-Path $reportRoot '02_db_sample.json'),
    '--align-marker', (Join-Path $stateRoot "done\$Year.align_done"),
    '--alignment-contract', (
        Join-Path $stateRoot "alignment_contracts\$Year.json"
    ),
    '--search-master-root', (
        Join-Path $layers "05_search_master_pre_mfa_staging\$SearchMasterRunId"
    ),
    '--wav-root', $wavRoot,
    '--output-csv', (Join-Path $reviewRoot '03_RESEARCHER_REVIEW.csv'),
    '--output-manifest', (
        Join-Path $reviewRoot '03_RESEARCHER_REVIEW_MANIFEST.json'
    )
)
& $python @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Review CSV: $(Join-Path $reviewRoot '03_RESEARCHER_REVIEW.csv')"
Write-Host 'WAV/LAB/6-tier 연결과 사용 가능성만 검토한다.'
Write-Host '실제 음운 실현 판정은 이 gate의 대상이 아니다.'
exit 0
