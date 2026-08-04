<#
2021--2025 post-MFA exact-ID 후보를 연구자가 명시 승인한 뒤, 같은
direct_db_ready DB에서 6-tier export를 재개한다.

- MFA 정렬을 다시 실행하지 않는다.
- pre-MFA 계약과 post-MFA 승인 행을 새 결합 계약으로 만든다.
- 원 pending 표는 보존하고 04_RESEARCHER_APPROVAL.csv만 소비한다.
- 같은 입력·정렬 계약의 보존 DB가 아니면 중단한다.
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
    [ValidatePattern('^[A-Za-z0-9._-]*$')]
    [string]$ResumeQueueId = '',
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovedBy,
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovalToken,
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovalStatement,
    [switch]$ApprovePostMfaExactReconciliation,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json

function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}

if (-not $PreflightOnly -and -not $ApprovePostMfaExactReconciliation) {
    throw '-ApprovePostMfaExactReconciliation 명시 승인이 없으므로 중단'
}
if ([string]::IsNullOrWhiteSpace($ReviewId)) {
    $ReviewId = "mfa_post_exact_${Year}_${SourceQueueId}"
}
if ([string]::IsNullOrWhiteSpace($ResumeQueueId)) {
    $ResumeQueueId = "${SourceQueueId}_postmfa"
}
if ($ResumeQueueId -eq $SourceQueueId) {
    throw '재개 queue ID는 source queue와 달라야 함'
}

$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$queueStatePath = Join-Path $stateRoot (
    "year_queue\$SourceQueueId\queue_state.json"
)
$readyMarkerPath = Join-Path $stateRoot "done\$Year.direct_db_ready"
$reviewRoot = Join-Path $projectRoot "outputs\reviews\$ReviewId"
$reviewSummary = Join-Path $reviewRoot 'SUMMARY.json'
$approvedRows = Join-Path $reviewRoot '04_RESEARCHER_APPROVAL.csv'
foreach ($required in @(
    $python, $queueStatePath, $readyMarkerPath,
    $reviewSummary, $approvedRows
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 파일 없음: $required"
    }
}

$queue = Get-Content -LiteralPath $queueStatePath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$yearProperty = $queue.years.PSObject.Properties[$Year]
if (
    [string]$queue.queue_id -ne $SourceQueueId -or
    $null -eq $yearProperty
) {
    throw 'source queue/year identity 불일치'
}
$yearState = $yearProperty.Value
if (
    [string]$queue.status -eq 'running' -or
    [string]$yearState.status -ne 'post_mfa_export_failed_db_preserved'
) {
    throw (
        "post-MFA DB 보존 중단 상태가 아님: " +
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

$summary = Get-Content -LiteralPath $reviewSummary -Raw -Encoding UTF8 |
    ConvertFrom-Json
if (
    [string]$summary.schema_version -ne 'mfa_post_alignment_review.v2' -or
    [string]$summary.status -ne 'pending_researcher_review' -or
    [string]$summary.year -ne $Year -or
    [string]$summary.input_contract_id -ne $inputContractId -or
    [string]$summary.required_approval_token -ne $ApprovalToken
) {
    throw 'post-MFA review summary/approval token identity 불일치'
}

$markerCompletedAt = [DateTimeOffset]::Parse([string]$ready.completed_at)
$reportCandidates = New-Object 'System.Collections.Generic.List[object]'
$reportFiles = @(
    Get-ChildItem -LiteralPath (Join-Path $stateRoot 'logs') `
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

$combinedReviewRoot = Join-Path $projectRoot (
    "outputs\reviews\mfa_exclusions_queue_$ResumeQueueId"
)
$combinedYearRoot = Join-Path $combinedReviewRoot $Year
$finalContract = Join-Path $combinedYearRoot 'approved_exclusions.json'
$approvedAt = (Get-Date).ToString('o')
$finalizer = Join-Path $PSScriptRoot (
    'python\finalize_post_mfa_exact_reconciliation_exclusions.py'
)
$finalizeArgs = New-Object 'System.Collections.Generic.List[string]'
foreach ($value in @(
    '--year', $Year,
    '--input-contract-id', $inputContractId,
    '--db', $db,
    '--export-report', $exportReport,
    '--pre-approved-contract', $preContract,
    '--review-summary', $reviewSummary,
    '--researcher-decisions', $approvedRows,
    '--output-root', $combinedYearRoot,
    '--approved-by', $ApprovedBy,
    '--approved-at', $approvedAt,
    '--approval-token', $ApprovalToken,
    '--approval-statement', $ApprovalStatement
)) {
    [void]$finalizeArgs.Add([string]$value)
}

$preflightArgs = New-Object 'System.Collections.Generic.List[string]'
foreach ($value in $finalizeArgs) {
    [void]$preflightArgs.Add([string]$value)
}
[void]$preflightArgs.Add('--preflight-only')
& $python $finalizer @preflightArgs
if ($LASTEXITCODE -ne 0) {
    throw "post-MFA 결합 승인 preflight 실패(exit=$LASTEXITCODE)"
}
if ($PreflightOnly) {
    Write-Host (
        "[OK] $Year post-MFA 승인·DB·보고서 identity preflight 통과; " +
        '계약·MFA·export를 만들거나 시작하지 않음'
    ) -ForegroundColor Green
    exit 0
}

if (-not (Test-Path -LiteralPath $combinedYearRoot)) {
    & $python $finalizer @finalizeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "post-MFA 결합 승인 계약 생성 실패(exit=$LASTEXITCODE)"
    }
} else {
    $manifestPath = Join-Path $combinedYearRoot (
        '03_RESEARCHER_REVIEW_MANIFEST.json'
    )
    foreach ($required in @($manifestPath, $finalContract)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "기존 결합 승인 폴더가 불완전함: $required"
        }
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    if (
        [string]$manifest.status -ne 'approved' -or
        [string]$manifest.year -ne $Year -or
        [string]$manifest.input_contract_id -ne $inputContractId -or
        [string]$manifest.approval_token -ne $ApprovalToken
    ) {
        throw '기존 결합 승인 manifest identity 불일치; 자동 덮어쓰기 금지'
    }
}
& $python (Join-Path $PSScriptRoot 'python\mfa_exclusion_contract.py') `
    validate --contract $finalContract --year $Year `
    --input-contract-id $inputContractId
if ($LASTEXITCODE -ne 0) {
    throw '결합 승인 계약 재검증 실패'
}

$startArgs = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    (Join-Path $PSScriptRoot 'start_full_mfa_after_review.ps1'),
    '-ApprovedBy', $ApprovedBy,
    '-QueueId', $ResumeQueueId,
    '-Years', $Year,
    '-ReviewRoot', $combinedReviewRoot
)
Write-Host (
    "[OK] $Year 결합 승인 계약 통과. 같은 direct_db_ready DB에서 " +
    '재정렬 없이 6-tier export를 재개한다.'
) -ForegroundColor Green
& powershell.exe @startArgs
exit $LASTEXITCODE
