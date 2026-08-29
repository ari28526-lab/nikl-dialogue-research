#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [switch]$Execute,
    [string]$ApprovedBy = '',
    [string]$ApprovalToken = '',
    [ValidateRange(10, 600)]
    [int]$PollSeconds = 30,
    [ValidateRange(60, 3600)]
    [int]$InitialCooldownSeconds = 300,
    [ValidateRange(1, 48)]
    [int]$MaxAutoResumes = 24
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($PreflightOnly -and $Execute) {
    throw '-PreflightOnly and -Execute cannot be used together.'
}
if (-not $PreflightOnly -and -not $Execute) {
    throw 'Specify -PreflightOnly or -Execute.'
}

$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$runner = Join-Path $projectRoot 'run_bareun_morph_csv_full.ps1'
$statusScript = Join-Path $projectRoot 'show_bareun_morph_csv_status.ps1'
$python = Join-Path $projectRoot 'work\bareun_wsd_full_20260828\.venv\Scripts\python.exe'
$auditScript = Join-Path $projectRoot 'scripts\python\audit_bareun_wsd_csv_full.py'
$configPath = Join-Path $projectRoot 'config\bareun_morph_reanalysis_v1.json'
$auditReport = Join-Path $projectRoot `
    'outputs\reports\AUDIT_bareun_morph_csv_full_20260828.json'
$outputRoot = 'D:\10_LAYERS\12_bareun_morph_v3_1\bareun_morph_full_20260828'
$buildingRoot = Join-Path $outputRoot 'bulk_csv_v1.building'
$finalRoot = Join-Path $outputRoot 'bulk_csv_v1'
$statePath = Join-Path $buildingRoot 'STATE.json'
$lockPath = Join-Path $buildingRoot 'RUN.lock.json'
$logPath = Join-Path $projectRoot 'logs\bareun_morph_csv_unattended_20260828.jsonl'
$expectedToken = 'BAREUN_MORPH_CSV_FULL_20260828'

foreach ($required in @($runner, $statusScript, $python, $auditScript, $configPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file is missing: $required"
    }
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    for ($attempt = 0; $attempt -lt 4; $attempt++) {
        try {
            $shareMode = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
            $stream = [IO.File]::Open(
                $Path,
                [IO.FileMode]::Open,
                [IO.FileAccess]::Read,
                $shareMode
            )
            try {
                $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::UTF8)
                try {
                    $text = $reader.ReadToEnd()
                } finally {
                    $reader.Dispose()
                }
            } finally {
                $stream.Dispose()
            }
            if ([string]::IsNullOrWhiteSpace($text)) {
                return $null
            }
            return ($text | ConvertFrom-Json)
        } catch {
            if ($attempt -eq 3) {
                throw
            }
            Start-Sleep -Milliseconds 250
        }
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

function Test-ProcessAlive {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return $false
    }
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Get-FreeGiB {
    $drive = New-Object IO.DriveInfo('D')
    return [math]::Round($drive.AvailableFreeSpace / 1GB, 3)
}

function Test-RetryableApiFailure {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $false
    }
    $pattern = '(?i)(gateway\s*time-?out|service\s*unavailable|' +
        'deadline_exceeded|statuscode\.unavailable|resource_exhausted|' +
        'too\s*many\s*requests|http[^\r\n]*(429|502|503|504)|' +
        '\b(429|502|503|504)\b|timed?\s*out|connection\s*(reset|closed)|' +
        'temporarily\s*unavailable|socketexception|transport\s*(closed|error))'
    return $Text -match $pattern
}

function Write-SupervisorEvent {
    param(
        [Parameter(Mandatory = $true)][string]$Event,
        [hashtable]$Detail = @{}
    )

    $payload = [ordered]@{
        recorded_at = [DateTime]::UtcNow.ToString('o')
        event = $Event
    }
    foreach ($key in $Detail.Keys) {
        $payload[$key] = $Detail[$key]
    }
    $json = $payload | ConvertTo-Json -Compress -Depth 8
    Write-Host $json
    $logDirectory = Split-Path -Parent $logPath
    if (-not (Test-Path -LiteralPath $logDirectory -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $logDirectory)
    }
    [IO.File]::AppendAllText(
        $logPath,
        $json + [Environment]::NewLine,
        (New-Object Text.UTF8Encoding($false))
    )
}

function Invoke-MorphRunner {
    param([bool]$Resume)

    $childArguments = New-Object 'System.Collections.Generic.List[string]'
    [void]$childArguments.Add('-NoProfile')
    [void]$childArguments.Add('-ExecutionPolicy')
    [void]$childArguments.Add('Bypass')
    [void]$childArguments.Add('-File')
    [void]$childArguments.Add($runner)
    [void]$childArguments.Add('-Execute')
    if ($Resume) {
        [void]$childArguments.Add('-Resume')
    }
    [void]$childArguments.Add('-ApprovedBy')
    [void]$childArguments.Add($ApprovedBy.Trim())
    [void]$childArguments.Add('-ApprovalToken')
    [void]$childArguments.Add($ApprovalToken)
    $process = Start-Process `
        -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
        -ArgumentList $childArguments.ToArray() `
        -NoNewWindow -Wait -PassThru
    return $process.ExitCode
}

function Invoke-FinalAudit {
    $auditArguments = @(
        $auditScript,
        '--config',
        $configPath,
        '--report',
        $auditReport
    )
    $auditOutput = @(& $python $auditArguments 2>&1)
    $auditExitCode = [int]$LASTEXITCODE
    foreach ($line in $auditOutput) {
        Write-Host ([string]$line)
    }
    return $auditExitCode
}

$phase = if (Test-Path -LiteralPath $finalRoot -PathType Container) {
    'final'
} elseif (Test-Path -LiteralPath $buildingRoot -PathType Container) {
    'building'
} else {
    'not_started'
}
$state = Read-JsonFile -Path $statePath
$lock = Read-JsonFile -Path $lockPath
$lockPid = [int](Get-PropertyValue -Object $lock -Name 'pid' -Default -1)
$preflight = [ordered]@{
    schema = 'bareun_morph_csv_unattended_preflight.v1'
    ready = (Get-FreeGiB) -ge 15
    phase = $phase
    state = [string](Get-PropertyValue -Object $state -Name 'status' -Default 'none')
    lock_pid = $lockPid
    lock_process_alive = Test-ProcessAlive -ProcessId $lockPid
    free_gib = Get-FreeGiB
    poll_seconds = $PollSeconds
    initial_cooldown_seconds = $InitialCooldownSeconds
    max_auto_resumes = $MaxAutoResumes
    source_or_audio_mutation = $false
}

if ($PreflightOnly) {
    $preflight | ConvertTo-Json -Depth 5
    exit 0
}
if ([string]::IsNullOrWhiteSpace($ApprovedBy)) {
    throw '-Execute requires -ApprovedBy.'
}
if ($ApprovalToken -cne $expectedToken) {
    throw "Exact -ApprovalToken $expectedToken is required."
}
if ($preflight.free_gib -lt 15) {
    throw 'D: free space is below the 15 GiB safety floor.'
}

$mutex = New-Object Threading.Mutex($false, 'Local\BareunMorphCsvUnattended20260828')
$ownsMutex = $false
$typeName = 'BareunMorphSupervisorExecutionState'
if (-not ($typeName -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class BareunMorphSupervisorExecutionState {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
}
$ES_CONTINUOUS = [Convert]::ToUInt32('80000000', 16)
$keepAwake = [Convert]::ToUInt32('80000041', 16)

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        throw 'Another Bareun morphology unattended supervisor is already running.'
    }
    [void][BareunMorphSupervisorExecutionState]::SetThreadExecutionState($keepAwake)
    Write-SupervisorEvent -Event 'supervisor_started' -Detail @{
        phase = $phase
        free_gib = $preflight.free_gib
        max_auto_resumes = $MaxAutoResumes
    }

    $autoResumeCount = 0
    $consecutiveNoProgressFailures = 0
    [long]$lastFailureUtterances = -1

    while ($true) {
        if (Test-Path -LiteralPath $finalRoot -PathType Container) {
            Write-SupervisorEvent -Event 'final_detected_audit_started'
            $auditExitCode = Invoke-FinalAudit
            if ($auditExitCode -ne 0) {
                Write-SupervisorEvent -Event 'final_audit_failed' -Detail @{
                    exit_code = $auditExitCode
                    report = $auditReport
                }
                exit 3
            }
            Write-SupervisorEvent -Event 'completed_and_audited' -Detail @{
                report = $auditReport
            }
            exit 0
        }

        $state = Read-JsonFile -Path $statePath
        $lock = Read-JsonFile -Path $lockPath
        $lockPid = [int](Get-PropertyValue -Object $lock -Name 'pid' -Default -1)
        if (Test-ProcessAlive -ProcessId $lockPid) {
            Start-Sleep -Seconds $PollSeconds
            continue
        }

        $freeGiB = Get-FreeGiB
        if ($freeGiB -lt 15) {
            Write-SupervisorEvent -Event 'stopped_low_disk_space' -Detail @{
                free_gib = $freeGiB
            }
            exit 4
        }

        $status = [string](Get-PropertyValue -Object $state -Name 'status' -Default 'none')
        $errorText = [string](Get-PropertyValue -Object $state -Name 'error' -Default '')
        $counts = Get-PropertyValue -Object $state -Name 'counts' -Default $null
        [long]$utterances = Get-PropertyValue -Object $counts -Name 'utterances' -Default 0
        $resume = Test-Path -LiteralPath $buildingRoot -PathType Container

        if ($status -eq 'failed_safe_to_resume') {
            if (-not (Test-RetryableApiFailure -Text $errorText)) {
                Write-SupervisorEvent -Event 'stopped_nonretryable_failure' -Detail @{
                    error = $errorText
                    utterances = $utterances
                }
                exit 5
            }
            if ($utterances -gt $lastFailureUtterances) {
                $consecutiveNoProgressFailures = 0
            } else {
                $consecutiveNoProgressFailures++
            }
            $lastFailureUtterances = $utterances
            $exponent = [math]::Min($consecutiveNoProgressFailures, 4)
            $cooldownSeconds = [math]::Min(
                3600,
                [int]($InitialCooldownSeconds * [math]::Pow(2, $exponent))
            )
            Write-SupervisorEvent -Event 'retryable_api_failure_cooldown' -Detail @{
                cooldown_seconds = $cooldownSeconds
                utterances = $utterances
                error = $errorText
            }
            Start-Sleep -Seconds $cooldownSeconds
        } elseif (
            $status -ne 'none' -and
            $status -ne 'running' -and
            $status -ne 'completed'
        ) {
            Write-SupervisorEvent -Event 'stopped_unexpected_state' -Detail @{
                status = $status
            }
            exit 6
        } elseif ($status -eq 'running' -or $status -eq 'completed') {
            Write-SupervisorEvent -Event 'orphaned_running_state_resume' -Detail @{
                utterances = $utterances
            }
        }

        if ($autoResumeCount -ge $MaxAutoResumes) {
            Write-SupervisorEvent -Event 'stopped_resume_limit' -Detail @{
                auto_resumes = $autoResumeCount
                utterances = $utterances
            }
            exit 7
        }
        $autoResumeCount++
        Write-SupervisorEvent -Event 'runner_started' -Detail @{
            resume = $resume
            auto_resume_number = $autoResumeCount
            free_gib = $freeGiB
        }
        $runnerExitCode = Invoke-MorphRunner -Resume $resume
        Write-SupervisorEvent -Event 'runner_exited' -Detail @{
            exit_code = $runnerExitCode
            auto_resume_number = $autoResumeCount
        }
    }
} finally {
    [void][BareunMorphSupervisorExecutionState]::SetThreadExecutionState($ES_CONTINUOUS)
    if ($ownsMutex) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
