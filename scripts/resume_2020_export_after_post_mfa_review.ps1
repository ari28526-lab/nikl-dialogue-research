<#
2020 post-MFA 363건 검토를 명시 승인하고 보존 DB에서 direct export를 재개한다.

- 기존 pre-MFA 1,887건 승인 계약은 덮어쓰지 않는다.
- 3건 audio_unusable + 360건 mfa_alignment_missing을 새 결합 계약으로 만든다.
- direct_db_ready의 같은 DB/입력/정렬 계약만 재사용한다.
- MFA 전체 clean 재정렬과 정본 승격은 수행하지 않는다.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApprovedBy,
    [Parameter(Mandatory=$true)]
    [switch]$ApprovePostMfa363,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_prod_2020_export_20260803',
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
if (-not $ApprovePostMfa363) {
    throw '-ApprovePostMfa363 명시 승인이 없으므로 중단'
}

$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$readyMarker = Join-Path $stateRoot 'done\2020.direct_db_ready'
if (-not (Test-Path -LiteralPath $readyMarker -PathType Leaf)) {
    throw "2020 direct DB checkpoint 없음: $readyMarker"
}
$ready = Get-Content -LiteralPath $readyMarker -Raw -Encoding UTF8 |
    ConvertFrom-Json
$inputContractId = [string]$ready.details.input_contract_id
$db = [string]$ready.details.alignment_db
if (
    $ready.stage -ne 'direct_db_ready' -or
    -not [bool]$ready.details.computation_complete -or
    [string]::IsNullOrWhiteSpace($inputContractId) -or
    [string]::IsNullOrWhiteSpace($db) -or
    -not (Test-Path -LiteralPath $db -PathType Leaf)
) {
    throw '2020 direct DB checkpoint identity/DB 불일치'
}

$preContract = Join-Path $projectRoot (
    'outputs\reviews\mfa_exclusions_queue_' +
    'mfa_r2_prod_2020_20260801\2020\approved_exclusions.json'
)
$postRoot = Join-Path $projectRoot (
    'outputs\reviews\mfa_post_alignment_2020_' +
    'mfa_r2_prod_2020_20260802'
)
$postDecisions = Join-Path $postRoot '02_RESEARCHER_DECISIONS.csv'
$reviewManifest = Join-Path $projectRoot (
    'outputs\reviews\MFA_2020_REVIEW_SIMPLE_V2_20260803\MANIFEST.json'
)
$reviewRoot = Join-Path $projectRoot (
    "outputs\reviews\mfa_exclusions_queue_$QueueId"
)
$yearRoot = Join-Path $reviewRoot '2020'
$finalContract = Join-Path $yearRoot 'approved_exclusions.json'

foreach ($required in @(
    $python, $preContract, $postDecisions, $reviewManifest
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 파일 없음: $required"
    }
}

if (-not (Test-Path -LiteralPath $yearRoot)) {
    $approvedAt = (Get-Date).ToString('o')
    & $python (Join-Path $PSScriptRoot (
        'python\finalize_post_mfa_alignment_exclusions.py'
    )) --year 2020 --input-contract-id $inputContractId `
        --db $db --pre-approved-contract $preContract `
        --post-decisions $postDecisions `
        --review-bundle-manifest $reviewManifest `
        --output-root $yearRoot --approved-by $ApprovedBy `
        --approved-at $approvedAt `
        --approval-token 'APPROVE_2020_POST_MFA_363' `
        --approval-statement (
            '2026-08-03 researcher completed linked-sample review and ' +
            'directed proceeding: approve exact 363 post-MFA exclusions; ' +
            'retain DB and do not rerun full-year MFA'
        )
    if ($LASTEXITCODE -ne 0) {
        throw "2020 post-MFA 결합 승인 계약 생성 실패(exit=$LASTEXITCODE)"
    }
} else {
    foreach ($required in @(
        (Join-Path $yearRoot '03_RESEARCHER_REVIEW.csv'),
        (Join-Path $yearRoot '03_RESEARCHER_REVIEW_MANIFEST.json'),
        $finalContract
    )) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "기존 결합 승인 폴더가 불완전함; 자동 덮어쓰기 금지: $required"
        }
    }
}

& $python (Join-Path $PSScriptRoot 'python\mfa_exclusion_contract.py') `
    validate --contract $finalContract --year 2020 `
    --input-contract-id $inputContractId
if ($LASTEXITCODE -ne 0) {
    throw '2020 결합 승인 계약 재검증 실패'
}

$startArgs = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    (Join-Path $PSScriptRoot 'start_full_mfa_after_review.ps1'),
    '-ApprovedBy', $ApprovedBy,
    '-QueueId', $QueueId,
    '-Years', '2020',
    '-ReviewRoot', $reviewRoot
)
if ($PreflightOnly) { $startArgs += '-PreflightOnly' }

Write-Host (
    '2020 결합 제외 계약 통과: pre-MFA 1,887 + post-MFA 363. ' +
    '같은 direct_db_ready DB에서 export만 재개한다.'
) -ForegroundColor Green
& powershell.exe @startArgs
exit $LASTEXITCODE
