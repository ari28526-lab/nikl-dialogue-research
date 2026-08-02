# 연도별 무인 MFA 계산 큐의 read-only 상태판.

param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_full6y_20260801'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}
$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$statePath = Join-Path $stateRoot "year_queue\$QueueId\queue_state.json"
$lockPath = Join-Path $stateRoot 'locks\mfa_year_queue.lock'
if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    Write-Host "연도 큐 상태 없음: $statePath" -ForegroundColor Yellow
    exit 1
}
$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$lockPresent = Test-Path -LiteralPath $lockPath -PathType Leaf
$lockAlive = $false
$lockPid = $null
if ($lockPresent) {
    try {
        $lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        $lockPid = [int]$lock.pid
        $lockAlive = $null -ne (
            Get-Process -Id $lockPid -ErrorAction SilentlyContinue
        )
    } catch {}
}
$freeGiB = $null
try {
    $freeGiB = [math]::Round(
        ([IO.DriveInfo]::new('D')).AvailableFreeSpace / 1GB, 2
    )
} catch {}

Write-Host 'MFA r2 연도별 무인 계산 큐 - read-only dashboard' `
    -ForegroundColor Cyan
Write-Host "Observed:  $((Get-Date).ToString('o'))"
Write-Host "Queue ID:  $($state.queue_id)"
Write-Host "Status:    $($state.status)"
Write-Host "Lock:      present=$lockPresent, pid=$lockPid, alive=$lockAlive"
Write-Host "D free:    ${freeGiB} GiB"
Write-Host "State JSON: $statePath"
Write-Host ''

$rows = foreach ($year in @($state.years_requested)) {
    $record = $state.years.$year
    $checkpointPath = Join-Path $stateRoot "done\$year.direct_db_ready"
    $checkpoint = $null
    $checkpointDb = ''
    if (Test-Path -LiteralPath $checkpointPath -PathType Leaf) {
        try {
            $candidate = Get-Content -LiteralPath $checkpointPath `
                -Raw -Encoding UTF8 | ConvertFrom-Json
            $candidateDb = [string]$candidate.details.alignment_db
            if (
                $candidate.stage -eq 'direct_db_ready' -and
                [bool]$candidate.details.computation_complete -and
                -not [string]::IsNullOrWhiteSpace($candidateDb) -and
                (Test-Path -LiteralPath $candidateDb -PathType Leaf)
            ) {
                $checkpoint = $candidate
                $checkpointDb = [IO.Path]::GetFullPath($candidateDb)
            }
        } catch {}
    }
    $inputContract = [string]$record.input_contract_id
    $alignmentContract = [string]$record.alignment_contract_id
    $retainedDb = [string]$record.retained_alignment_db
    if ($null -ne $checkpoint) {
        if ([string]::IsNullOrWhiteSpace($inputContract)) {
            $inputContract = [string]$checkpoint.details.input_contract_id
        }
        if ([string]::IsNullOrWhiteSpace($alignmentContract)) {
            $alignmentContract = [string](
                $checkpoint.details.alignment_contract_id
            )
        }
        if ([string]::IsNullOrWhiteSpace($retainedDb)) {
            $retainedDb = $checkpointDb
        }
    }
    [PSCustomObject]@{
        year = $year
        status = $record.status
        phase = $record.phase
        input_contract = $(if ($inputContract) {
            $inputContract.Substring(
                0, [Math]::Min(12, $inputContract.Length)
            )
        } else { '' })
        alignment_contract = $(if ($alignmentContract) {
            $alignmentContract.Substring(
                0, [Math]::Min(12, $alignmentContract.Length)
            )
        } else { '' })
        db_retained = (
            -not [string]::IsNullOrWhiteSpace($retainedDb) -and
            (Test-Path -LiteralPath $retainedDb -PathType Leaf)
        )
        direct_checkpoint = ($null -ne $checkpoint)
        human_review = [bool]$record.researcher_review_required
        promoted = [bool]$record.canonical_promotion_allowed
        updated_at = $record.updated_at
    }
}
$rows | Format-Table -AutoSize
Write-Host ''
Write-Host '해석:'
Write-Host '- *_preserved: 계산 결과를 지우지 않고 해당 단계에서 멈춤'
Write-Host '- researcher_*_required: 자동 승인하지 않은 연구자 검토 대기'
Write-Host '- machine_qc_passed_human_review_pending: 계산·기계 QC 완료, 정본 아님'
Write-Host '- 이 상태판은 파일이나 프로세스를 변경하지 않음'
