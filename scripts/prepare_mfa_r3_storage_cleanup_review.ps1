[CmdletBinding()]
param(
    [switch]$PreflightOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\ari30\miniforge3\envs\mfa\python.exe'
$inventoryScript = Join-Path $PSScriptRoot 'python\inventory_mfa_storage.py'
$releaseId = 'common_pron_mfa_r3_20260809'
$releaseRoot = "D:\mfa_eojeol\r3\$releaseId"
$qcRoot = Join-Path $projectRoot (
    "outputs\reports\mfa_r3_research_qc_$releaseId"
)
$outputRoot = Join-Path $projectRoot (
    'outputs\reports\mfa_r3_storage_cleanup_review_20260813'
)
$years = @('2020', '2021', '2022', '2023')

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "파이프라인 Python이 없음: $python"
}
if (-not (Test-Path -LiteralPath $inventoryScript -PathType Leaf)) {
    throw "저장공간 inventory 도구가 없음: $inventoryScript"
}

$drive = [IO.DriveInfo]::new('D:\')
if (-not $drive.IsReady -or $drive.VolumeLabel -ne 'DATA_SSD') {
    throw "D: DATA_SSD 식별 실패"
}

$checks = [System.Collections.Generic.List[object]]::new()
foreach ($year in $years) {
    $tempYear = Join-Path $releaseRoot "temp\$year"
    $database = Join-Path $tempYear "$year.db"
    $qcState = Join-Path $qcRoot "$year\QC_STATE.json"
    $transactionFiles = @(
        "$database-journal", "$database-wal", "$database-shm"
    ) | Where-Object { Test-Path -LiteralPath $_ }
    $checks.Add([pscustomobject]@{
        year = $year
        temp_year_exists = Test-Path -LiteralPath $tempYear -PathType Container
        database_exists = Test-Path -LiteralPath $database -PathType Leaf
        qc_state_exists = Test-Path -LiteralPath $qcState -PathType Leaf
        active_transaction_files = @($transactionFiles)
    })
}

$failed = @(
    $checks | Where-Object {
        -not $_.temp_year_exists -or
        -not $_.database_exists -or
        -not $_.qc_state_exists -or
        @($_.active_transaction_files).Count -gt 0
    }
)
if ($failed.Count -gt 0) {
    $failed | Format-List | Out-Host
    throw 'r3 temp inventory 선행검사 실패; 어떤 파일도 정리하지 않음'
}

$freeGiB = [math]::Round($drive.AvailableFreeSpace / 1GB, 3)
Write-Host (
    '[OK] r3 저장공간 inventory preflight: years={0}, D free={1}GiB' -f
    ($years -join ','), $freeGiB
) -ForegroundColor Green
Write-Host '이 명령은 D:/E: 파일을 삭제·이동·압축하지 않습니다.'
Write-Host '대용량 DB SHA와 temp 파일 목록을 읽어 검토용 JSON만 만듭니다.'

if ($PreflightOnly) {
    Write-Host '[OK] PreflightOnly 완료; inventory는 아직 실행하지 않음'
    exit 0
}

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$reports = [System.Collections.Generic.List[object]]::new()
foreach ($year in $years) {
    $tempYear = Join-Path $releaseRoot "temp\$year"
    $qcState = Join-Path $qcRoot "$year\QC_STATE.json"
    $output = Join-Path $outputRoot "INVENTORY_r3_temp_$year.json"
    Write-Host "[$year] DB SHA·temp inventory 시작"
    & $python $inventoryScript `
        --year $year `
        --temp-year $tempYear `
        --qc-gate-report $qcState `
        --output $output `
        --hash-db
    if ($LASTEXITCODE -ne 0) {
        throw "$year inventory가 정리 검토 가능 상태가 아님(exit=$LASTEXITCODE)"
    }
    $report = Get-Content -LiteralPath $output -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $candidate = $report.estimated_reclaim
    $reports.Add([pscustomobject]@{
        year = $year
        status = [string]$report.status
        total_files = [long]$report.totals.files
        total_bytes = [long]$report.totals.bytes
        candidate_files = [long]$candidate.files
        candidate_bytes = [long]$candidate.bytes
        candidate_gib = [math]::Round([long]$candidate.bytes / 1GB, 3)
        retained_db = $report.retained_db_fingerprint
        report_path = $output
    })
}

$candidateBytes = [long](
    ($reports | Measure-Object -Property candidate_bytes -Sum).Sum
)
$summary = [ordered]@{
    schema_version = 'mfa_r3_storage_cleanup_review.v1'
    status = 'ready_for_researcher_review'
    recorded_at = (Get-Date).ToString('o')
    release_id = $releaseId
    drive = [ordered]@{
        name = 'D:'
        volume_label = $drive.VolumeLabel
        free_gib_before_inventory = $freeGiB
    }
    scope = [ordered]@{
        years = $years
        temp_only = $true
        corpus_scanned = $false
        final_textgrids_scanned = $false
        legacy_r2_scanned = $false
    }
    reports = @($reports)
    estimated_reclaim = [ordered]@{
        bytes = $candidateBytes
        gib = [math]::Round($candidateBytes / 1GB, 3)
    }
    safety = [ordered]@{
        deletion_performed = $false
        move_performed = $false
        archive_performed = $false
        apply_supported = $false
        authorization_required_for_cleanup = $true
        databases_retained = $true
        final_6tier_retained = $true
        source_corpus_modified = $false
    }
    next_step = (
        '검토 뒤 exact allowlist archive/apply 스크립트를 별도로 만들고 ' +
        '연구자 승인을 받는다.'
    )
}
$summaryPath = Join-Path $outputRoot 'SUMMARY.json'
$partial = "$summaryPath.partial"
$summary | ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath $partial -Encoding UTF8
Move-Item -LiteralPath $partial -Destination $summaryPath -Force

Write-Host ''
$reports | Select-Object year, candidate_files, candidate_gib |
    Format-Table -AutoSize | Out-Host
Write-Host (
    '[OK] temp 정리 후보 합계: {0}GiB; 삭제·이동 0건' -f
    [math]::Round($candidateBytes / 1GB, 3)
) -ForegroundColor Green
Write-Host "요약: $summaryPath"
