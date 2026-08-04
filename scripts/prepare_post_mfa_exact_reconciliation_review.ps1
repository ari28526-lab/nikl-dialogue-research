<#
MFA 계산이 끝났지만 exact-ID gate에서 direct export가 멈춘 연도의
연구자 검토표를 만든다.

- 보존 DB, 실패 export 보고서, pre-MFA 승인 계약의 identity를 대조한다.
- 후보를 자동 승인하지 않는다.
- 원본 WAV/LAB와 MFA DB는 읽기만 한다.
- 가장 최근의 같은 정렬 계약 실패 보고서만 사용한다.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2021','2022','2023','2024','2025')]
    [string]$Year,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SourceQueueId,
    [ValidatePattern('^[A-Za-z0-9._-]*$')]
    [string]$ReviewId = '',
    [switch]$SkipSampleFiles,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
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
$queueStatePath = Join-Path $stateRoot (
    "year_queue\$SourceQueueId\queue_state.json"
)
$readyMarkerPath = Join-Path $stateRoot "done\$Year.direct_db_ready"
foreach ($required in @($python, $queueStatePath, $readyMarkerPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 파일 없음: $required"
    }
}

$queue = Get-Content -LiteralPath $queueStatePath -Raw -Encoding UTF8 |
    ConvertFrom-Json
if ([string]$queue.queue_id -ne $SourceQueueId) {
    throw 'source queue identity 불일치'
}
$yearProperty = $queue.years.PSObject.Properties[$Year]
if ($null -eq $yearProperty) {
    throw "source queue에 $Year 상태가 없음"
}
$yearState = $yearProperty.Value
if (
    [string]$queue.status -eq 'running' -or
    [string]$yearState.status -ne 'post_mfa_export_failed_db_preserved'
) {
    throw (
        "아직 post-MFA export 보존 중단 상태가 아님: " +
        "queue=$($queue.status), year=$($yearState.status)"
    )
}

$ready = Get-Content -LiteralPath $readyMarkerPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$inputContractId = [string]$ready.details.input_contract_id
$alignmentContractId = [string]$ready.details.alignment_contract_id
$db = [string]$ready.details.alignment_db
if (
    [string]$ready.stage -ne 'direct_db_ready' -or
    -not [bool]$ready.details.computation_complete -or
    [string]::IsNullOrWhiteSpace($inputContractId) -or
    [string]::IsNullOrWhiteSpace($alignmentContractId) -or
    [string]::IsNullOrWhiteSpace($db) -or
    -not (Test-Path -LiteralPath $db -PathType Leaf) -or
    [string]$yearState.input_contract_id -ne $inputContractId -or
    [string]$yearState.alignment_contract_id -ne $alignmentContractId -or
    [IO.Path]::GetFullPath([string]$yearState.retained_alignment_db) -ne
        [IO.Path]::GetFullPath($db)
) {
    throw 'source queue와 direct_db_ready의 DB/입력/정렬 identity 불일치'
}

$preContract = [IO.Path]::GetFullPath(
    [string]$yearState.approved_exclusions_contract
)
if (-not (Test-Path -LiteralPath $preContract -PathType Leaf)) {
    throw "pre-MFA 승인 계약 없음: $preContract"
}
& $python (Join-Path $PSScriptRoot 'python\mfa_exclusion_contract.py') `
    validate --contract $preContract --year $Year `
    --input-contract-id $inputContractId
if ($LASTEXITCODE -ne 0) {
    throw 'pre-MFA 승인 계약 검증 실패'
}

$markerCompletedAt = [DateTimeOffset]::Parse([string]$ready.completed_at)
$reportCandidates = New-Object 'System.Collections.Generic.List[object]'
$logRoot = Join-Path $stateRoot 'logs'
$reportFiles = @(
    Get-ChildItem -LiteralPath $logRoot `
        -Filter "direct_db_export_${Year}_*.json" -File `
        -ErrorAction SilentlyContinue
)
foreach ($file in $reportFiles) {
    if ($file.LastWriteTimeUtc -lt $markerCompletedAt.UtcDateTime) {
        continue
    }
    try {
        $report = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if (
            [string]$report.schema_version -eq 'mfa_research_6tier_export.v1' -and
            [string]$report.status -eq 'failed' -and
            [string]$report.analysis_ready_status -eq
                'blocked_exact_id_reconciliation' -and
            [string]$report.year -eq $Year -and
            [string]$report.alignment_contract_id -eq $alignmentContractId
        ) {
            [void]$reportCandidates.Add($file)
        }
    } catch {
        continue
    }
}
$matchingReports = @(
    $reportCandidates | Sort-Object LastWriteTimeUtc -Descending
)
if ($matchingReports.Count -eq 0) {
    throw '현재 보존 DB 계약에 맞는 blocked exact-ID export 보고서 없음'
}
$exportReport = [string]$matchingReports[0].FullName

if ([string]::IsNullOrWhiteSpace($ReviewId)) {
    $ReviewId = "mfa_post_exact_${Year}_${SourceQueueId}"
}
$outputRoot = Join-Path $projectRoot "outputs\reviews\$ReviewId"
$wavSelection = Resolve-MfaWavCorpusForYear -Config $config -Year $Year
$labRoot = [string]$wavSelection.WavRoot

Write-Host "[$Year] post-MFA exact-ID 검토 준비 확인" -ForegroundColor Cyan
Write-Host "  DB: $db"
Write-Host "  export report: $exportReport"
Write-Host "  pre-MFA contract: $preContract"
Write-Host "  review output: $outputRoot"
Write-Host "  matching failed reports: $($matchingReports.Count) (최신 1개 사용)"
if ($PreflightOnly) {
    Write-Host '[OK] 읽기 전용 preflight 통과; 파일을 만들지 않음' `
        -ForegroundColor Green
    exit 0
}
if (Test-Path -LiteralPath $outputRoot) {
    throw "기존 검토 출력 보호: $outputRoot"
}

$prepareArgs = New-Object 'System.Collections.Generic.List[string]'
foreach ($value in @(
    '--db', $db,
    '--year', $Year,
    '--export-report', $exportReport,
    '--approved-exclusions-contract', $preContract,
    '--lab-root', $labRoot,
    '--output-root', $outputRoot
)) {
    [void]$prepareArgs.Add([string]$value)
}
if (-not $SkipSampleFiles) {
    [void]$prepareArgs.Add('--copy-sample-files')
}
& $python (Join-Path $PSScriptRoot (
    'python\prepare_post_mfa_alignment_review.py'
)) @prepareArgs
if ($LASTEXITCODE -ne 0) {
    throw "post-MFA exact-ID 검토표 생성 실패(exit=$LASTEXITCODE)"
}

$summaryPath = Join-Path $outputRoot 'SUMMARY.json'
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
Write-Host (
    "[OK] $Year 연구자 검토 필요: 후보=$($summary.candidate_count), " +
    "token=$($summary.required_approval_token)"
) -ForegroundColor Green
Write-Host "편집할 파일: $(Join-Path $outputRoot '04_RESEARCHER_APPROVAL.csv')"
Write-Host '원본 pending 표(02_RESEARCHER_DECISIONS.csv)는 수정하지 말 것.'
