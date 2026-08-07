<#
2022 post-MFA 438건의 기록된 명시 승인을 읽어, 같은 보존 DB에서 export를
재개한다. 긴 승인 문장과 token을 사용자가 다시 입력하지 않게 하는 고정 wrapper다.

- 기본 실행은 PreflightOnly다.
- 실제 재개는 -Start를 명시해야 한다.
- MFA 정렬을 다시 실행하지 않는다.
#>
[CmdletBinding()]
param(
    [switch]$Start
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$reviewId = 'mfa_post_exact_2022_mfa_r2_prod_safe_body_2022_20260806'
$reviewRoot = Join-Path $projectRoot "outputs\reviews\$reviewId"
$approvalManifest = Join-Path $reviewRoot (
    '04_RESEARCHER_APPROVAL_MANIFEST.json'
)
if (-not (Test-Path -LiteralPath $approvalManifest -PathType Leaf)) {
    throw "2022 explicit approval manifest 없음: $approvalManifest"
}
$approval = Get-Content -LiteralPath $approvalManifest -Raw -Encoding UTF8 |
    ConvertFrom-Json
if (
    [string]$approval.schema_version -ne
        'mfa_post_exact_explicit_approval.v1' -or
    [string]$approval.status -ne 'approved' -or
    [string]$approval.year -ne '2022' -or
    [int]$approval.approved_row_count -ne 438 -or
    [string]$approval.reason_code -ne 'mfa_alignment_missing' -or
    [string]$approval.exclusion_scope -ne 'alignment_and_analysis' -or
    [bool]$approval.automatic_approval_performed -or
    [bool]$approval.mfa_database_modified -or
    -not [bool]$approval.recovery_inputs_preserved
) {
    throw '2022 explicit approval manifest identity/policy 불일치'
}
$approvedCsv = [string]$approval.approved_review_csv.path
if (-not (Test-Path -LiteralPath $approvedCsv -PathType Leaf)) {
    throw "2022 approved working CSV 없음: $approvedCsv"
}
$actualSha = (Get-FileHash -LiteralPath $approvedCsv -Algorithm SHA256).Hash.ToLower()
if ($actualSha -ne [string]$approval.approved_review_csv.sha256) {
    throw '2022 approved working CSV SHA256 불일치'
}

$runner = Join-Path $PSScriptRoot (
    'resume_year_export_after_post_mfa_review.ps1'
)
$arguments = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $runner,
    '-Year', '2022',
    '-SourceQueueId', 'mfa_r2_prod_safe_body_2022_20260806',
    '-ReviewId', $reviewId,
    '-ApprovedBy', [string]$approval.approved_by,
    '-ApprovalToken', [string]$approval.approval_token,
    '-ApprovalStatement', [string]$approval.approval_statement
)
if ($Start) {
    $arguments += '-ApprovePostMfaExactReconciliation'
    Write-Host (
        '[START] 2022 보존 DB direct export·6-tier·동반표 재개; ' +
        'MFA 재정렬 없음'
    ) -ForegroundColor Cyan
} else {
    $arguments += '-PreflightOnly'
    Write-Host '[PREFLIGHT] 산출물 생성·MFA·export 시작 없음' -ForegroundColor Cyan
}
& powershell.exe @arguments
exit $LASTEXITCODE
