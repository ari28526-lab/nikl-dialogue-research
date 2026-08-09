param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year = '2020'
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
    "outputs\reports\PREFLIGHT_mfa_r3_runner_${Year}_gate_adopted_go_20260809.json"
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
$driveFreeGiB = [math]::Round(
    ([IO.DriveInfo]::new('D:\')).AvailableFreeSpace / 1GB, 3
)
$preflightStatus = if ($null -ne $preflight) {
    [string]$preflight.status
} else { 'missing' }
$preflightFailed = if ($null -ne $preflight) {
    @($preflight.failed_checks) -join ','
} else { '' }

Write-Host 'MFA r3 annual status - read only' -ForegroundColor Cyan
[pscustomobject]@{
    observed_at = [DateTimeOffset]::Now.ToString('o')
    phase = $phase
    year = $Year
    release_id = $releaseId
    gate_status = [string]$gate.status
    gate_allowed_release_ids = @($gate.allowed_release_ids) -join ','
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
} | Format-List

Write-Host (
    'Note: active corpus file totals are not recursively counted; final manifest ' +
    'counts appear after materialization completes.'
) -ForegroundColor DarkGray
