param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year = '2020',
    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$policyPath = Join-Path $projectRoot 'config\mfa_r3_runner_v1.json'
$gatePath = Join-Path $projectRoot 'config\mfa_pronunciation_release_gate.json'
$policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$gate = Get-Content -LiteralPath $gatePath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$releaseId = [string]$policy.release_id
$releaseRoot = [IO.Path]::GetFullPath([string]$policy.release_root)
$corpusYear = Join-Path $releaseRoot "corpus\$Year"
$contractRoot = Join-Path $releaseRoot 'contracts'
$tempYear = Join-Path $releaseRoot "temp\$Year"
$markerRoot = Join-Path $releaseRoot 'markers'
$logRoot = Join-Path $releaseRoot 'logs'
$lockPath = Join-Path $releaseRoot 'locks\mfa_r3_year.lock'
$corpusManifestPath = Join-Path $contractRoot (
    "CORPUS_MATERIALIZATION_$Year.json"
)
$corpusBuildingPath = Join-Path $contractRoot (
    "CORPUS_MATERIALIZATION_$Year.building.json"
)
$tempContractPath = Join-Path $contractRoot "TEMP_CONTRACT_$Year.json"
$doneMarkerPath = Join-Path $markerRoot "ALIGN_DONE_$Year.json"
$preflightPath = Join-Path $projectRoot (
    'work\mfa_r3_preflight\PREFLIGHT_{0}_{1}.json' -f
    $releaseId, $Year
)

function Read-JsonShared {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $stream = $null
    $reader = $null
    try {
        $stream = [IO.File]::Open(
            $Path, [IO.FileMode]::Open, [IO.FileAccess]::Read,
            [IO.FileShare]::ReadWrite
        )
        $reader = [IO.StreamReader]::new(
            $stream, [Text.UTF8Encoding]::new($false), $true, 4096, $true
        )
        $text = $reader.ReadToEnd()
        if ([string]::IsNullOrWhiteSpace($text)) { return $null }
        return ($text | ConvertFrom-Json)
    } catch {
        return $null
    } finally {
        if ($null -ne $reader) { $reader.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Read-LastJsonLineShared {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $stream = $null
    try {
        $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
        $stream = [IO.File]::Open(
            $Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, $share
        )
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
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Get-JsonPropertyValue {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Test-ProcessAlive {
    param([Nullable[int]]$Id)
    if ($null -eq $Id -or $Id -le 0) { return $false }
    return $null -ne (Get-Process -Id $Id -ErrorAction SilentlyContinue)
}

function Get-LatestFile {
    param([string]$Root, [string]$Filter)
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        return $null
    }
    return @(
        Get-ChildItem -LiteralPath $Root -Filter $Filter -File `
            -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending
    ) | Select-Object -First 1
}

$lock = Read-JsonShared -Path $lockPath
$corpusManifest = Read-JsonShared -Path $corpusManifestPath
$corpusBuilding = Read-JsonShared -Path $corpusBuildingPath
$tempContract = Read-JsonShared -Path $tempContractPath
$doneMarker = Read-JsonShared -Path $doneMarkerPath
$preflight = Read-JsonShared -Path $preflightPath

$wrapperPid = $null
$childPid = $null
if ($null -ne $lock) {
    $wrapperPid = [Nullable[int]]([int]$lock.owner_pid)
    if ($null -ne $lock.child_pid) {
        $childPid = [Nullable[int]]([int]$lock.child_pid)
    }
}
$wrapperAlive = Test-ProcessAlive -Id $wrapperPid
$childAlive = Test-ProcessAlive -Id $childPid
$lockPresent = Test-Path -LiteralPath $lockPath -PathType Leaf
$buildingPresent = Test-Path -LiteralPath $corpusBuildingPath -PathType Leaf
$tempPresent = Test-Path -LiteralPath $tempYear -PathType Container
$phase = 'ready_not_started'
if ($null -ne $doneMarker -and [string]$doneMarker.status -eq 'passed') {
    $phase = 'alignment_db_complete'
} elseif ($lockPresent -and $childAlive) {
    $phase = 'mfa_running'
} elseif ($lockPresent -and $wrapperAlive) {
    $phase = 'corpus_materializing_or_mfa_starting'
} elseif ($buildingPresent) {
    $phase = 'corpus_materialization_interrupted_resume_same_command'
} elseif ($tempPresent) {
    $phase = 'mfa_checkpoint_present_not_running_resume_same_command'
} elseif ($null -ne $corpusManifest) {
    $phase = 'corpus_ready_mfa_not_running_resume_same_command'
} elseif (Test-Path -LiteralPath $releaseRoot -PathType Container) {
    $phase = 'release_initialized_not_running'
}

$sessionDirectoryCount = 0
if (Test-Path -LiteralPath $corpusYear -PathType Container) {
    $sessionDirectoryCount = @(
        Get-ChildItem -LiteralPath $corpusYear -Directory `
            -ErrorAction SilentlyContinue
    ).Count
}
$expectedCorpus = $null
$physicalWav = $null
$physicalLab = $null
if ($null -ne $corpusManifest) {
    $expectedCorpus = [int]$corpusManifest.counts.expected_mfa_input
    $physicalWav = [int]$corpusManifest.counts.physical_wav
    $physicalLab = [int]$corpusManifest.counts.physical_lab
}
$latestStdout = Get-LatestFile -Root $logRoot -Filter "mfa_${Year}_*_stdout.log"
$latestStderr = Get-LatestFile -Root $logRoot -Filter "mfa_${Year}_*_stderr.log"
$latestHeartbeat = Get-LatestFile -Root $logRoot -Filter (
    "mfa_${Year}_*_heartbeat.jsonl"
)
$latestHeartbeatRecord = $null
$heartbeatAgeSeconds = $null
$heartbeatChildPid = $null
$heartbeatChildAlive = $false
if ($null -ne $latestHeartbeat) {
    $latestHeartbeatRecord = Read-LastJsonLineShared -Path (
        $latestHeartbeat.FullName
    )
    $heartbeatObservedAt = Get-JsonPropertyValue `
        -Object $latestHeartbeatRecord -Name 'observed_at'
    if (-not [string]::IsNullOrWhiteSpace([string]$heartbeatObservedAt)) {
        try {
            $recordedAt = [DateTimeOffset]::Parse([string]$heartbeatObservedAt)
            $heartbeatAgeSeconds = [math]::Round(
                ([DateTimeOffset]::Now - $recordedAt).TotalSeconds, 1
            )
        } catch {
            $heartbeatAgeSeconds = $null
        }
    }
    $heartbeatChildValue = Get-JsonPropertyValue `
        -Object $latestHeartbeatRecord -Name 'child_pid'
    if ($null -ne $heartbeatChildValue -and [int]$heartbeatChildValue -gt 0) {
        $heartbeatChildPid = [Nullable[int]]([int]$heartbeatChildValue)
        $heartbeatChildAlive = Test-ProcessAlive -Id $heartbeatChildPid
    }
}
$driveFreeGiB = [math]::Round(
    ([IO.DriveInfo]::new('D:\')).AvailableFreeSpace / 1GB, 3
)
$preflightStatus = if ($null -ne $preflight) {
    [string]$preflight.status
} else { 'missing' }
$preflightFailed = if ($null -ne $preflight) {
    @($preflight.failed_checks) -join ','
} else { '' }

$result = [ordered]@{
    schema_version = 'mfa_r3_year_status.v2'
    observed_at = [DateTimeOffset]::Now.ToString('o')
    phase = $phase
    year = $Year
    release_id = $releaseId
    gate_status = [string]$gate.status
    gate_allowed_release_ids = @($gate.allowed_release_ids) -join ','
    preflight_path = $preflightPath
    preflight_status = $preflightStatus
    preflight_failed_checks = $preflightFailed
    release_root = $releaseRoot
    drive_free_gib = $driveFreeGiB
    lock_present = $lockPresent
    wrapper_pid = $wrapperPid
    wrapper_process_alive = $wrapperAlive
    child_pid = $childPid
    child_process_alive = $childAlive
    corpus_building_contract = $buildingPresent
    corpus_final_manifest = ($null -ne $corpusManifest)
    corpus_session_directories = $sessionDirectoryCount
    corpus_expected_utterances = $expectedCorpus
    corpus_physical_wav = $physicalWav
    corpus_physical_lab = $physicalLab
    temp_checkpoint_present = $tempPresent
    temp_contract_present = ($null -ne $tempContract)
    alignment_done = (
        $null -ne $doneMarker -and [string]$doneMarker.status -eq 'passed'
    )
    latest_stdout = if ($null -ne $latestStdout) {
        $latestStdout.FullName
    } else { '' }
    latest_stdout_last_write = if ($null -ne $latestStdout) {
        $latestStdout.LastWriteTime.ToString('o')
    } else { '' }
    latest_stderr = if ($null -ne $latestStderr) {
        $latestStderr.FullName
    } else { '' }
    latest_stderr_last_write = if ($null -ne $latestStderr) {
        $latestStderr.LastWriteTime.ToString('o')
    } else { '' }
    latest_heartbeat = if ($null -ne $latestHeartbeat) {
        $latestHeartbeat.FullName
    } else { '' }
    latest_heartbeat_last_write = if ($null -ne $latestHeartbeat) {
        $latestHeartbeat.LastWriteTime.ToString('o')
    } else { '' }
    heartbeat_observed_at = [string](Get-JsonPropertyValue `
        -Object $latestHeartbeatRecord -Name 'observed_at')
    heartbeat_age_seconds = $heartbeatAgeSeconds
    heartbeat_stale_over_5_minutes = (
        $null -ne $heartbeatAgeSeconds -and $heartbeatAgeSeconds -gt 300
    )
    heartbeat_wrapper_pid = Get-JsonPropertyValue `
        -Object $latestHeartbeatRecord -Name 'wrapper_pid'
    heartbeat_child_pid = $heartbeatChildPid
    heartbeat_child_process_alive = $heartbeatChildAlive
    heartbeat_release_id = [string](Get-JsonPropertyValue `
        -Object $latestHeartbeatRecord -Name 'release_id')
    heartbeat_alignment_contract_id = [string](Get-JsonPropertyValue `
        -Object $latestHeartbeatRecord -Name 'alignment_contract_id')
}

if ($AsJson) {
    [pscustomobject]$result | ConvertTo-Json -Depth 8
} else {
    Write-Host 'MFA r3 annual status - read only' -ForegroundColor Cyan
    [pscustomobject]$result | Format-List

    Write-Host (
        'Note: active corpus file totals are not recursively counted; final ' +
        'manifest counts appear after materialization completes.'
    ) -ForegroundColor DarkGray
}
