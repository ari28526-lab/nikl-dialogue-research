<#
실행 중이거나 최근 종료된 연도 MFA heartbeat와 queue를 읽기 전용으로 표시한다.

활성 JSONL에는 Get-Content를 사용하지 않는다. FileShare.ReadWrite/Delete로
마지막 완결 JSON 행만 읽어 writer 잠금 충돌을 피한다.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year,
    [ValidatePattern('^[A-Za-z0-9._-]*$')]
    [string]$RunId = '',
    [switch]$AsJson
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

function Read-LastJsonLineShared([string]$Path) {
    $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $stream = [IO.File]::Open(
        $Path,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        $share
    )
    try {
        $take = [Math]::Min([int64](1024 * 1024), $stream.Length)
        if ($take -le 0) { return $null }
        [void]$stream.Seek(-$take, [IO.SeekOrigin]::End)
        $buffer = New-Object byte[] ([int]$take)
        $read = $stream.Read($buffer, 0, $buffer.Length)
        $text = [Text.Encoding]::UTF8.GetString($buffer, 0, $read)
        $lines = @($text -split "`r?`n")
        for ($index = $lines.Count - 1; $index -ge 0; $index--) {
            if ([string]::IsNullOrWhiteSpace($lines[$index])) { continue }
            try {
                return ($lines[$index] | ConvertFrom-Json)
            } catch {
                continue
            }
        }
        return $null
    } finally {
        $stream.Dispose()
    }
}

function Find-LatestYearQueue([string]$StateRoot, [string]$TargetYear) {
    $queueRoot = Join-Path $StateRoot 'year_queue'
    if (-not (Test-Path -LiteralPath $queueRoot -PathType Container)) {
        return $null
    }
    $states = @(
        Get-ChildItem -LiteralPath $queueRoot -Filter 'queue_state.json' `
            -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTimeUtc -Descending
    )
    foreach ($stateFile in $states) {
        try {
            $state = Get-Content -LiteralPath $stateFile.FullName -Raw `
                -Encoding UTF8 | ConvertFrom-Json
            $yearProperty = $state.years.PSObject.Properties[$TargetYear]
            if ($null -ne $yearProperty) {
                return [pscustomobject]@{
                    path = $stateFile.FullName
                    state = $state
                    year_state = $yearProperty.Value
                }
            }
        } catch {
            continue
        }
    }
    return $null
}

$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$logRoot = Join-Path $stateRoot 'logs'
if ([string]::IsNullOrWhiteSpace($RunId)) {
    $heartbeatCandidates = @(
        Get-ChildItem -LiteralPath $logRoot `
            -Filter "mfa_${Year}_*_heartbeat.jsonl" -File `
            -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTimeUtc -Descending
    )
    if ($heartbeatCandidates.Count -eq 0) {
        throw "$Year MFA heartbeat 없음: $logRoot"
    }
    $heartbeatPath = [string]$heartbeatCandidates[0].FullName
} else {
    $heartbeatPath = Join-Path $logRoot (
        "mfa_${Year}_${RunId}_heartbeat.jsonl"
    )
    if (-not (Test-Path -LiteralPath $heartbeatPath -PathType Leaf)) {
        throw "지정 heartbeat 없음: $heartbeatPath"
    }
}

$heartbeat = Read-LastJsonLineShared $heartbeatPath
if ($null -eq $heartbeat) {
    throw "완결 heartbeat JSON 행을 읽지 못함: $heartbeatPath"
}
$recordedAt = [DateTimeOffset]::Parse([string]$heartbeat.recorded_at)
$ageSeconds = [math]::Round(
    ((Get-Date).ToUniversalTime() - $recordedAt.UtcDateTime).TotalSeconds,
    1
)
$treePids = @($heartbeat.tree_process_ids | ForEach-Object { [int]$_ })
$livePids = New-Object 'System.Collections.Generic.List[int]'
foreach ($processId in $treePids) {
    if ($null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        [void]$livePids.Add($processId)
    }
}

$alignmentTarget = $null
$alignmentPercent = $null
$integrityReportPath = Join-Path $projectRoot (
    "outputs\reports\PREFLIGHT_mfa_input_integrity_{0}_{1}.json" -f
        $Year, [string]$heartbeat.run_id
)
if (Test-Path -LiteralPath $integrityReportPath -PathType Leaf) {
    try {
        $integrity = Get-Content -LiteralPath $integrityReportPath -Raw `
            -Encoding UTF8 | ConvertFrom-Json
        $integrityYear = @(
            $integrity.years |
            Where-Object { [string]$_.year -eq $Year }
        )
        if ($integrityYear.Count -eq 1) {
            $alignmentTarget = [int64](
                $integrityYear[0].counts.expected_usable_lab
            )
            if (
                $alignmentTarget -gt 0 -and
                $null -ne $heartbeat.alignment_processed
            ) {
                $alignmentPercent = [math]::Round(
                    100.0 * [double]$heartbeat.alignment_processed /
                        $alignmentTarget,
                    3
                )
            }
        }
    } catch {
        $alignmentTarget = $null
        $alignmentPercent = $null
    }
}

$queueInfo = Find-LatestYearQueue $stateRoot $Year
$queueId = $null
$queueStatus = $null
$yearStatus = $null
$yearPhase = $null
$queuePath = $null
if ($null -ne $queueInfo) {
    $queueId = [string]$queueInfo.state.queue_id
    $queueStatus = [string]$queueInfo.state.status
    $yearStatus = [string]$queueInfo.year_state.status
    $yearPhase = [string]$queueInfo.year_state.phase
    $queuePath = [string]$queueInfo.path
}

$result = [ordered]@{
    schema_version = 'active_mfa_progress.v1'
    observed_at = (Get-Date).ToString('o')
    year = $Year
    run_id = [string]$heartbeat.run_id
    heartbeat_path = $heartbeatPath
    heartbeat_recorded_at = [string]$heartbeat.recorded_at
    heartbeat_age_seconds = $ageSeconds
    heartbeat_stale_over_5_minutes = ($ageSeconds -gt 300)
    event = [string]$heartbeat.event
    phase = [string]$heartbeat.phase
    alignment_processed = $heartbeat.alignment_processed
    alignment_target = $alignmentTarget
    alignment_percent = $alignmentPercent
    alignment_retried = $heartbeat.alignment_retried
    alignment_error_signals = $heartbeat.alignment_error_signals
    interval_word_utterances = $heartbeat.interval_word_utterances
    interval_phone_rows = $heartbeat.interval_phone_rows
    watchdog_will_kill = $heartbeat.watchdog_will_kill
    system_commit_percent = $heartbeat.system_commit_percent
    system_memory_available_mb = $heartbeat.system_memory_available_mb
    work_drive_free_gb = $heartbeat.work_drive_free_gb
    tree_process_ids = $treePids
    live_tree_process_ids = @($livePids)
    live_tree_process_count = $livePids.Count
    queue_id = $queueId
    queue_status = $queueStatus
    year_status = $yearStatus
    year_phase = $yearPhase
    queue_state_path = $queuePath
    input_integrity_report = $(if ($null -eq $alignmentTarget) {
        $null
    } else {
        $integrityReportPath
    })
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 8
} else {
    Write-Host "MFA read-only progress: $Year" -ForegroundColor Cyan
    [pscustomobject]$result | Format-List
}
