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

function Get-PropertyValue {
    param(
        [AllowNull()]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        $Default = $null
    )

    if ($null -eq $Object) {
        return $Default
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }
    return $property.Value
}

$base = 'D:\10_LAYERS\12_bareun_morph_v3_1\bareun_morph_full_20260828'
$buildingRoot = Join-Path $base 'bulk_csv_v1.building'
$finalRoot = Join-Path $base 'bulk_csv_v1'
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
    schema = 'bareun_morph_csv_status.v1'
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
    $displayStatus = [string](Get-PropertyValue $state 'status' 'unknown')
    if ($phase -eq 'building' -and $null -ne $lock) {
        $displayStatus = 'running'
    }
    Write-Host "status=$displayStatus"
    $completedFiles = Get-PropertyValue $state 'completed_files'
    if ($null -ne $completedFiles) {
        $totalFiles = Get-PropertyValue $state 'total_files' 17156
        Write-Host "files=$completedFiles/$totalFiles"
    }
    $counts = Get-PropertyValue $state 'counts'
    if ($null -ne $counts) {
        $utterances = Get-PropertyValue $counts 'utterances'
        if ($null -ne $utterances) {
            Write-Host "utterances=$utterances"
        }
    }
    $sessionRate = Get-PropertyValue $state 'session_rate_utterances_per_second'
    if ($null -ne $sessionRate) {
        Write-Host "session_rate=$sessionRate utterances/s"
    }
    $etaSeconds = Get-PropertyValue $state 'eta_seconds'
    if ($null -ne $etaSeconds) {
        $etaHours = [Math]::Round([double]$etaSeconds / 3600, 2)
        Write-Host "eta_hours=$etaHours"
    }
    $errorText = Get-PropertyValue $state 'error'
    if ($null -ne $errorText) {
        Write-Host "error=$errorText"
    }
}
if ($null -ne $lock) {
    Write-Host "lock_pid=$($lock.pid)"
}
