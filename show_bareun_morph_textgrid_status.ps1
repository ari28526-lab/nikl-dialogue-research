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

function Read-Utf8Text {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = New-Object IO.FileStream(
        $Path,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::Read
    )
    try {
        $reader = New-Object IO.StreamReader(
            $stream,
            (New-Object Text.UTF8Encoding($false)),
            $true
        )
        try {
            return $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
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

$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$configPath = Join-Path $projectRoot 'config\bareun_morph_textgrid_full_v1.json'
$config = Read-Utf8Text -Path $configPath | ConvertFrom-Json
$primaryRoot = [IO.Path]::GetFullPath(
    ([string]$config.storage.primary_building_root).Replace('/', '\')
)
$spillValue = ([string]$config.storage.spill_building_root).Replace('/', '\')
if ([IO.Path]::IsPathRooted($spillValue)) {
    $spillRoot = [IO.Path]::GetFullPath($spillValue)
} else {
    $spillRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot $spillValue))
}

$phase = 'not_started'
$state = $null
$auditState = $null
$lock = $null
$auditLock = $null
if (Test-Path -LiteralPath $primaryRoot -PathType Container) {
    $phase = 'building'
    $statePath = Join-Path $primaryRoot 'STATE.json'
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        $state = Read-SharedJson $statePath
        $stateStatus = [string](Get-PropertyValue $state 'status' '')
        if ($stateStatus -eq 'built_pending_external_consolidation') {
            $phase = 'built'
        }
    }
    $auditPath = Join-Path $primaryRoot 'AUDIT_STATE.json'
    if (Test-Path -LiteralPath $auditPath -PathType Leaf) {
        $auditState = Read-SharedJson $auditPath
        $auditStatus = [string](Get-PropertyValue $auditState 'status' '')
        if ($auditStatus -eq 'passed_pending_external_consolidation') {
            $phase = 'audited_pending_external_consolidation'
        } elseif ($auditStatus -eq 'running') {
            $phase = 'auditing'
        }
    }
    $auditLockPath = Join-Path $primaryRoot 'AUDIT.lock.json'
    if (Test-Path -LiteralPath $auditLockPath -PathType Leaf) {
        $auditLock = Read-SharedJson $auditLockPath
    }
    $lockPath = Join-Path $primaryRoot 'RUN.lock.json'
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        $lock = Read-SharedJson $lockPath
    }
}

$lockAlive = $false
if ($null -ne $lock) {
    $lockPid = [int](Get-PropertyValue $lock 'pid' -1)
    if ($lockPid -gt 0) {
        $lockAlive = $null -ne (Get-Process -Id $lockPid -ErrorAction SilentlyContinue)
    }
}
$auditLockAlive = $false
if ($null -ne $auditLock) {
    $auditLockPid = [int](Get-PropertyValue $auditLock 'pid' -1)
    if ($auditLockPid -gt 0) {
        $auditLockAlive = $null -ne (
            Get-Process -Id $auditLockPid -ErrorAction SilentlyContinue
        )
    }
}

$primaryDrive = New-Object IO.DriveInfo(([IO.Path]::GetPathRoot($primaryRoot)))
$spillDrive = New-Object IO.DriveInfo(([IO.Path]::GetPathRoot($spillRoot)))
$result = [ordered]@{
    schema = 'bareun_morph_textgrid_status.v1'
    phase = $phase
    primary_root = $primaryRoot
    spill_root = $spillRoot
    state = $state
    audit_state = $auditState
    lock = $lock
    lock_alive = $lockAlive
    audit_lock = $auditLock
    audit_lock_alive = $auditLockAlive
    primary_free_gib = [Math]::Round($primaryDrive.AvailableFreeSpace / 1GB, 3)
    primary_minimum_free_gib = [double]$config.storage.primary_minimum_free_gib
    spill_free_gib = [Math]::Round($spillDrive.AvailableFreeSpace / 1GB, 3)
    spill_minimum_free_gib = [double]$config.storage.spill_minimum_free_gib
    read_only_status = $true
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
    exit 0
}

Write-Host "phase=$phase"
Write-Host "D_free_gib=$($result.primary_free_gib) floor=$($result.primary_minimum_free_gib)"
Write-Host "C_free_gib=$($result.spill_free_gib) floor=$($result.spill_minimum_free_gib)"
if ($null -eq $state) {
    Write-Host 'state=none'
} else {
    Write-Host "status=$([string](Get-PropertyValue $state 'status' 'unknown'))"
    $counts = Get-PropertyValue $state 'counts'
    if ($null -ne $counts) {
        Write-Host "receipts=$(Get-PropertyValue $counts 'completed_receipts' 0)/$($config.input.expected_bareun_receipts)"
        Write-Host "textgrids=$(Get-PropertyValue $counts 'derived' 0)/$($config.input.expected_aligned_textgrids)"
        Write-Host "no_mfa=$(Get-PropertyValue $counts 'no_mfa_alignment' 0)/$($config.input.expected_no_mfa_alignment)"
        Write-Host "conflicts=$(Get-PropertyValue $counts 'alignment_conflicts' 0)"
    }
    $eta = Get-PropertyValue $state 'eta_seconds'
    if ($null -ne $eta) {
        Write-Host "build_eta_hours=$([Math]::Round([double]$eta / 3600, 2))"
    }
    $errorText = Get-PropertyValue $state 'error'
    if ($null -ne $errorText) {
        Write-Host "error=$errorText"
    }
}
if ($null -ne $auditState) {
    Write-Host "audit_status=$([string](Get-PropertyValue $auditState 'status' 'unknown'))"
    Write-Host "audit_receipts=$(Get-PropertyValue $auditState 'completed_receipts' 0)/$(Get-PropertyValue $auditState 'total_receipts' $config.input.expected_bareun_receipts)"
    $auditEta = Get-PropertyValue $auditState 'eta_seconds'
    if ($null -ne $auditEta) {
        Write-Host "audit_eta_hours=$([Math]::Round([double]$auditEta / 3600, 2))"
    }
    $auditError = Get-PropertyValue $auditState 'error'
    if ($null -ne $auditError) {
        Write-Host "audit_error=$auditError"
    }
}
if ($null -ne $lock) {
    Write-Host "lock_pid=$(Get-PropertyValue $lock 'pid' -1) alive=$lockAlive"
}
if ($null -ne $auditLock) {
    Write-Host "audit_lock_pid=$(Get-PropertyValue $auditLock 'pid' -1) alive=$auditLockAlive"
}
