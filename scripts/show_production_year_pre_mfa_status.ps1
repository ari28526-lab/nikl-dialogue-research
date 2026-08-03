#Requires -Version 5.1
<# 읽기 전용: 연도별 morph_search.v3/source contract 준비 상태판. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2021','2022','2023','2024','2025')]
    [string]$Year,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$MorphRunId = 'morph_search_v3_20260801'
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
function Read-JsonIfPresent([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 |
        ConvertFrom-Json
}
$outputBase = Resolve-ConfiguredPath (
    [string]$config.morph_search_v3_staging
)
$yearRoot = Join-Path (Join-Path $outputBase $MorphRunId) $Year
$progressPath = Join-Path $yearRoot 'YEAR_PROGRESS.json'
$manifestPath = Join-Path $yearRoot 'annual_tables\YEAR_MANIFEST.json'
$contractPath = Join-Path $yearRoot 'SOURCE_CONTRACT.json'
$lockPath = Join-Path $yearRoot 'RUNNING.lock.json'
$progress = Read-JsonIfPresent $progressPath
$manifest = Read-JsonIfPresent $manifestPath
$contract = Read-JsonIfPresent $contractPath
$lock = Read-JsonIfPresent $lockPath
$lockPid = if ($null -ne $lock -and $lock.pid) {
    [int]$lock.pid
} else { 0 }
$lockProcessAlive = (
    $lockPid -gt 0 -and
    $null -ne (Get-Process -Id $lockPid -ErrorAction SilentlyContinue)
)
$completedShards = if ($null -ne $progress) {
    [int]$progress.completed_shards
} else {
    @(Get-ChildItem -LiteralPath (Join-Path $yearRoot 'shards') `
        -Recurse -Filter 'SHARD_MANIFEST.json' -File `
        -ErrorAction SilentlyContinue).Count
}
$totalShards = if ($null -ne $progress) {
    [int]$progress.total_shards
} else { 0 }
$percent = if ($totalShards -gt 0) {
    [math]::Round(100.0 * $completedShards / $totalShards, 3)
} else { 0.0 }
$phase = if (
    $null -ne $manifest -and [string]$manifest.status -eq 'success' -and
    $null -ne $contract -and [string]$contract.status -eq 'frozen'
) {
    'complete'
} elseif ($null -ne $manifest -and [string]$manifest.status -eq 'success') {
    'annual_tables_ready_source_contract_pending'
} elseif ($lockProcessAlive) {
    'running'
} elseif ($completedShards -gt 0) {
    'interrupted_or_paused_resumable'
} else {
    'not_started'
}
$latestWrite = @(
    $progressPath, $manifestPath, $contractPath, $lockPath |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        ForEach-Object { (Get-Item -LiteralPath $_).LastWriteTime }
) | Sort-Object -Descending | Select-Object -First 1
$driveRoot = [IO.Path]::GetPathRoot($outputBase)
$drive = [IO.DriveInfo]::new($driveRoot)
[pscustomobject]@{
    observed_at = (Get-Date).ToString('o')
    year = $Year
    phase = $phase
    completed_shards = $completedShards
    total_shards = $totalShards
    percent = $percent
    progress_status = if ($null -ne $progress) {
        [string]$progress.status
    } else { 'missing' }
    annual_manifest_status = if ($null -ne $manifest) {
        [string]$manifest.status
    } else { 'missing' }
    source_contract_status = if ($null -ne $contract) {
        [string]$contract.status
    } else { 'missing' }
    lock_present = ($null -ne $lock)
    lock_pid = $lockPid
    lock_process_alive = [bool]$lockProcessAlive
    latest_write = $latestWrite
    drive_free_gib = [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
    year_root = $yearRoot
}
exit 0
