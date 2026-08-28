#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Read-SharedJson {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = New-Object IO.FileStream(
        $Path,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)
    )
    try {
        $reader = New-Object IO.StreamReader(
            $stream,
            (New-Object Text.UTF8Encoding($false)),
            $true
        )
        try {
            $text = $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
    return ($text | ConvertFrom-Json)
}

$buildingRoot = 'D:\10_LAYERS\11_bareun_wsd\bareun_wsd_full_20260828\bulk_csv_v1.building'
$finalRoot = 'D:\10_LAYERS\11_bareun_wsd\bareun_wsd_full_20260828\bulk_csv_v1'
$activeRoot = $null
$phase = 'not_started'
if (Test-Path -LiteralPath $finalRoot -PathType Container) {
    $activeRoot = $finalRoot
    $phase = 'completed'
} elseif (Test-Path -LiteralPath $buildingRoot -PathType Container) {
    $activeRoot = $buildingRoot
    $phase = 'building'
}

$state = $null
$lock = $null
if ($null -ne $activeRoot) {
    $statePath = Join-Path $activeRoot 'STATE.json'
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        $state = Read-SharedJson $statePath
    }
    $lockPath = Join-Path $activeRoot 'RUN.lock.json'
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        $lock = Read-SharedJson $lockPath
    }
}

$drive = New-Object IO.DriveInfo('D')
$result = [ordered]@{
    schema = 'bareun_wsd_csv_status.v1'
    phase = $phase
    root = $activeRoot
    state = $state
    lock = $lock
    free_gib = [Math]::Round($drive.AvailableFreeSpace / 1GB, 3)
    read_only_status = $true
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
    exit 0
}

Write-Host "phase=$phase"
Write-Host "free_gib=$($result.free_gib)"
if ($null -eq $state) {
    Write-Host 'state=none'
} else {
    Write-Host "status=$($state.status)"
    if ($null -ne $state.completed_files) {
        Write-Host "files=$($state.completed_files)/$($state.total_files)"
    }
    if ($null -ne $state.counts) {
        Write-Host "utterances=$($state.counts.utterances)"
    }
    if ($null -ne $state.session_rate_utterances_per_second) {
        Write-Host "session_rate=$($state.session_rate_utterances_per_second) utterances/s"
    }
    if ($null -ne $state.eta_seconds) {
        $etaDays = [Math]::Round([double]$state.eta_seconds / 86400, 2)
        Write-Host "eta_days=$etaDays"
    }
}
if ($null -ne $lock) {
    Write-Host "lock_pid=$($lock.pid)"
}
