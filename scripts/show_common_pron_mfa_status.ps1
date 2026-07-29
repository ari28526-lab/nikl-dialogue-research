#Requires -Version 5.1
<#
Read-only status dashboard for the common MFA pronunciation release.

This script never starts, stops, deletes, moves, or rewrites release data.
It treats a shard as complete only when its verification JSON passes every
hard gate. An output .dict file by itself is never counted as verified.
#>
[CmdletBinding()]
param(
    [string]$ReleaseRoot = (
        'D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728'
    ),

    [string]$LockPath = (
        'D:\mfa_common_pron\locks\common_pron_mfa_r2_20260728.lock'
    ),

    [ValidateRange(0, 3600)]
    [int]$WatchSeconds = 0,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($AsJson -and $WatchSeconds -gt 0) {
    throw 'AsJson and WatchSeconds cannot be used together.'
}

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    return (
        Get-Content -Raw -Encoding UTF8 -LiteralPath $Path |
        ConvertFrom-Json
    )
}

function Get-SharedLineCount([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return 0
    }
    $stream = $null
    $reader = $null
    try {
        $stream = [IO.File]::Open(
            $Path,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            [IO.FileShare]::ReadWrite
        )
        $reader = [IO.StreamReader]::new(
            $stream,
            [Text.Encoding]::UTF8,
            $true
        )
        $count = 0
        while ($null -ne $reader.ReadLine()) {
            $count += 1
        }
        return $count
    } finally {
        if ($null -ne $reader) {
            $reader.Dispose()
        } elseif ($null -ne $stream) {
            $stream.Dispose()
        }
    }
}

$releaseRootFull = [IO.Path]::GetFullPath($ReleaseRoot)
$preparePath = Join-Path $releaseRootFull (
    '00_contract\prepare_manifest.json'
)
$finalPath = Join-Path $releaseRootFull (
    '00_contract\release_manifest.json'
)
$differencePath = Join-Path $releaseRootFull (
    '03_equivalence\common_pron_mfa_difference_inventory_2020_2021.json'
)
$differenceCheckpointPath = Join-Path $releaseRootFull (
    '03_equivalence\common_pron_mfa_difference_inventory_2020.checkpoint.json'
)
$commonRoot = Split-Path (
    Split-Path $releaseRootFull -Parent
) -Parent
$differenceLockPath = Join-Path (
    Join-Path $commonRoot 'locks'
) 'common_pron_mfa_difference_inventory.lock'
$adoptionPath = Join-Path $releaseRootFull (
    '00_contract\adoption_contract.json'
)
$specialCandidatePath = Join-Path $releaseRootFull (
    '_state\jamo_ls_candidate_report.json'
)
$reportDir = Join-Path $releaseRootFull '_state\shard_reports'
$outputDir = Join-Path $releaseRootFull '01_g2p\output_shards'
$logDir = Join-Path $releaseRootFull 'logs'

$prepared = Read-JsonFile $preparePath
if ($null -eq $prepared -or $prepared.status -ne 'prepared') {
    throw "Prepared manifest is missing or invalid: $preparePath"
}

$totalShards = [int]$prepared.counts.shards
$totalWords = [int64]$prepared.counts.observed_oov_words
$totalStandardWords = [int64]$prepared.counts.g2p_standard_words
$verifiedIndices = [Collections.Generic.HashSet[int]]::new()
$verifiedWords = [int64]0
$verifiedReportRecords = @()
$invalidReports = 0
$reportFiles = @(
    Get-ChildItem -LiteralPath $reportDir -Filter 'oov_*.json' -File `
        -ErrorAction SilentlyContinue |
        Sort-Object Name
)

foreach ($reportFile in $reportFiles) {
    try {
        $report = Read-JsonFile $reportFile.FullName
        $match = [regex]::Match(
            $reportFile.BaseName,
            '^oov_([0-9]{5})$'
        )
        $valid = (
            $null -ne $report -and
            $match.Success -and
            $report.status -eq 'success' -and
            [int64]$report.counts.input_words -eq
                [int64]$report.counts.output_words -and
            [int64]$report.counts.missing -eq 0 -and
            [int64]$report.counts.extras -eq 0 -and
            [int64]$report.counts.spn_words -eq 0 -and
            [int64]$report.counts.phone_outside_acoustic_inventory -eq 0
        )
        if ($valid) {
            $index = [int]$match.Groups[1].Value
            [void]$verifiedIndices.Add($index)
            $verifiedWords += [int64]$report.counts.output_words
            $repairManifestPath = Join-Path (
                Join-Path (
                    Join-Path $releaseRootFull '_state\no_path_repairs'
                ) $reportFile.BaseName
            ) 'repair_manifest.json'
            $repairManifest = Read-JsonFile $repairManifestPath
            $isReviewedRepair = (
                $null -ne $repairManifest -and
                $repairManifest.status -eq 'success' -and
                [string]$repairManifest.output.repaired_shard.sha256 -eq
                    [string]$report.inputs.output_shard.sha256
            )
            $verifiedReportRecords += [pscustomobject]@{
                shard_index = $index
                words = [int64]$report.counts.output_words
                recorded_at = [datetimeoffset]::Parse(
                    [string]$report.recorded_at
                )
                output_mtime_ns = [int64](
                    $report.inputs.output_shard.mtime_ns
                )
                is_reviewed_repair = $isReviewedRepair
            }
        } else {
            $invalidReports += 1
        }
    } catch {
        $invalidReports += 1
    }
}

$unverifiedOutputRecords = @()
$unverifiedWords = [int64]0
foreach ($outputFile in @(
    Get-ChildItem -LiteralPath $outputDir -Filter 'oov_*.dict' -File `
        -ErrorAction SilentlyContinue
)) {
    $match = [regex]::Match($outputFile.BaseName, '^oov_([0-9]{5})$')
    if (-not $match.Success) { continue }
    $index = [int]$match.Groups[1].Value
    if ($verifiedIndices.Contains($index)) { continue }
    $rows = [int64](Get-SharedLineCount $outputFile.FullName)
    $unverifiedWords += $rows
    $unverifiedOutputRecords += [pscustomobject]@{
        index = $index
        path = $outputFile.FullName
        rows = $rows
        last_write = $outputFile.LastWriteTime
    }
}
$currentRecord = @(
    $unverifiedOutputRecords | Sort-Object last_write -Descending
) | Select-Object -First 1
$currentIndex = $null
$currentOutput = $null
$currentRows = 0
$currentOutputWrite = $null
if ($null -ne $currentRecord) {
    $currentIndex = [int]$currentRecord.index
    $currentOutput = [string]$currentRecord.path
    $currentRows = [int64]$currentRecord.rows
    $currentOutputWrite = $currentRecord.last_write.ToString('o')
} else {
    for ($index = 1; $index -le $totalShards; $index += 1) {
        if (-not $verifiedIndices.Contains($index)) {
            $currentIndex = $index
            break
        }
    }
}

$lock = Read-JsonFile $LockPath
$lockPid = $null
$lockAlive = $false
$startedAt = $null
if ($null -ne $lock) {
    $lockPid = [int]$lock.pid
    $lockAlive = $null -ne (
        Get-Process -Id $lockPid -ErrorAction SilentlyContinue
    )
    $startedAt = [datetimeoffset]::Parse([string]$lock.acquired_at)
}
$differenceLock = Read-JsonFile $differenceLockPath
$differenceLockPid = $null
$differenceLockAlive = $false
if ($null -ne $differenceLock) {
    $differenceLockPid = [int]$differenceLock.pid
    $differenceLockAlive = $null -ne (
        Get-Process -Id $differenceLockPid -ErrorAction SilentlyContinue
    )
}

$specialCandidate = Read-JsonFile $specialCandidatePath
$specialWords = [int64]0
if (
    $null -ne $specialCandidate -and
    $specialCandidate.status -eq
        'candidate_ready_researcher_review_required' -and
    [int64]$specialCandidate.counts.missing -eq 0 -and
    [int64]$specialCandidate.counts.extras -eq 0 -and
    [int64]$specialCandidate.counts.spn_words -eq 0 -and
    [int64]$specialCandidate.counts.phone_outside_acoustic_inventory -eq 0
) {
    $specialWords = [int64](
        $specialCandidate.counts.surface_keys_restored
    )
}
$generatedWords = [int64](
    $specialWords + $verifiedWords + $unverifiedWords
)
$progressPct = if ($totalWords -gt 0) {
    [math]::Round(100.0 * $generatedWords / $totalWords, 3)
} else {
    0
}
$rate = $null
$eta = $null
if ($null -ne $startedAt) {
    $elapsedSeconds = (
        [datetimeoffset]::Now - $startedAt
    ).TotalSeconds
    # Under StrictMode, selecting .Sum from an empty Measure-Object pipeline
    # fails before the first shard report exists. Sum explicitly so the
    # normal 0/N startup state remains observable.
    $sessionVerifiedWords = [int64]0
    $startedAtUnixNs = [int64](
        $startedAt.ToUnixTimeMilliseconds() * 1000000
    )
    foreach ($record in @($verifiedReportRecords)) {
        if (
            $record.recorded_at -ge $startedAt -and
            $record.output_mtime_ns -ge $startedAtUnixNs -and
            -not $record.is_reviewed_repair
        ) {
            $sessionVerifiedWords += [int64]$record.words
        }
    }
    $sessionCurrentRows = [int64]0
    if (
        $null -ne $currentOutputWrite -and
        [datetimeoffset]::Parse($currentOutputWrite) -ge $startedAt
    ) {
        $sessionCurrentRows = [int64]$currentRows
    }
    $sessionWords = [int64](
        $sessionVerifiedWords + $sessionCurrentRows
    )
    if ($elapsedSeconds -gt 0 -and $sessionWords -gt 0) {
        $rate = [math]::Round($sessionWords / $elapsedSeconds, 2)
        if ($rate -gt 0 -and $generatedWords -lt $totalWords) {
            $eta = [datetimeoffset]::Now.AddSeconds(
                ($totalWords - $generatedWords) / $rate
            ).ToString('o')
        }
    }
}

$driveRoot = [IO.Path]::GetPathRoot($releaseRootFull)
$drive = [IO.DriveInfo]::new($driveRoot)
$freeGiB = if ($drive.IsReady) {
    [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
} else {
    $null
}

$latestLog = @(
    Get-ChildItem -LiteralPath $logDir -Filter 'g2p_oov_*.log' -File `
        -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
) | Select-Object -First 1
$latestLogPath = $null
$latestLogWrite = $null
if ($null -ne $latestLog) {
    $latestLogPath = $latestLog.FullName
    $latestLogWrite = $latestLog.LastWriteTime.ToString('o')
}

$approvalPendingShards = @()
$unknownMissingShards = @()
$approvalPendingWords = @()
$unknownMissingWords = @()
$repairAttemptRoot = Join-Path $releaseRootFull '_state\no_path_repairs'
foreach ($attemptFile in @(
    Get-ChildItem -LiteralPath $repairAttemptRoot `
        -Filter 'last_attempt.json' -File -Recurse `
        -ErrorAction SilentlyContinue
)) {
    try {
        $attempt = Read-JsonFile $attemptFile.FullName
        $match = [regex]::Match(
            $attemptFile.Directory.Name,
            '^oov_([0-9]{5})$'
        )
        if ($null -eq $attempt -or -not $match.Success) { continue }
        $index = [int]$match.Groups[1].Value
        if ($attempt.status -eq 'researcher_approval_required') {
            $approvalPendingShards += $index
            $approvalPendingWords += @($attempt.not_approved_words)
        } elseif ($attempt.status -eq 'unknown_missing_words') {
            $unknownMissingShards += $index
            $unknownMissingWords += @($attempt.unknown_words)
        }
    } catch {
        $invalidReports += 1
    }
}
$approvalPendingShards = @($approvalPendingShards | Sort-Object -Unique)
$unknownMissingShards = @($unknownMissingShards | Sort-Object -Unique)
$approvalPendingWords = @($approvalPendingWords | Sort-Object -Unique)
$unknownMissingWords = @($unknownMissingWords | Sort-Object -Unique)

$final = Read-JsonFile $finalPath
$difference = Read-JsonFile $differencePath
$differenceCheckpoint = Read-JsonFile $differenceCheckpointPath
$adoption = Read-JsonFile $adoptionPath
$differenceFiles = [int64]0
$differenceExpectedFiles = [int64]0
$differencePercent = [double]0
$differenceCheckpointStatus = 'pending'
if ($null -ne $differenceCheckpoint) {
    $differenceCheckpointStatus = [string]$differenceCheckpoint.status
    $differenceFiles = [int64](
        $differenceCheckpoint.counts.textgrid_files
    )
    $differenceExpectedFiles = [int64](
        $differenceCheckpoint.contract.expected_valid_textgrids
    )
    if ($differenceExpectedFiles -gt 0) {
        $differencePercent = [math]::Round(
            100.0 * $differenceFiles / $differenceExpectedFiles,
            3
        )
    }
}
$phase = if (
    $null -ne $adoption -and
    $adoption.status -eq 'passed' -and
    [bool]$adoption.gate.allow_yearly_mfa
) {
    'yearly_mfa_approved'
} elseif (
    $null -ne $difference -and
    $difference.status -eq 'differences_inventoried'
) {
    'difference_inventory_ready_researcher_approval'
} elseif ($differenceLockAlive) {
    'difference_inventory_running'
} elseif (
    $null -ne $differenceCheckpoint -and
    $differenceCheckpoint.status -eq 'in_progress'
) {
    'difference_inventory_interrupted_resumable'
} elseif ($null -ne $final -and $final.status -eq 'success') {
    'artifact_ready_adoption_pending'
} elseif ($verifiedIndices.Count -eq $totalShards) {
    'finalizing'
} elseif (
    -not $lockAlive -and
    (
        $approvalPendingShards.Count -gt 0 -or
        $unknownMissingShards.Count -gt 0
    )
) {
    'g2p_review_blocked_not_running'
} elseif ($specialWords -gt 0 -and -not $lockAlive) {
    'special_review_ready_bulk_not_running'
} elseif ($lockAlive) {
    'g2p_running'
} elseif ($null -ne $lock) {
    'lock_without_live_process'
} else {
    'not_running'
}

$result = [ordered]@{
    schema_version = 'common_pron_mfa_status.v1'
    observed_at = [datetimeoffset]::Now.ToString('o')
    phase = $phase
    release_root = $releaseRootFull
    progress = [ordered]@{
        total_shards = $totalShards
        verified_shards = $verifiedIndices.Count
        invalid_reports = $invalidReports
        current_shard = $currentIndex
        current_shard_rows = $currentRows
        total_oov_words = $totalWords
        total_standard_shard_words = $totalStandardWords
        jamo_ls_candidate_words = $specialWords
        unverified_output_words = $unverifiedWords
        approval_pending_shards = (
            $approvalPendingShards -join ','
        )
        approval_pending_words = (
            $approvalPendingWords -join ','
        )
        unknown_missing_shards = (
            $unknownMissingShards -join ','
        )
        unknown_missing_words = (
            $unknownMissingWords -join ','
        )
        observed_generated_words = $generatedWords
        percent = $progressPct
        average_words_per_second = $rate
        estimated_completion = $eta
        difference_checkpoint_status = $differenceCheckpointStatus
        difference_textgrids = $differenceFiles
        difference_expected_textgrids = $differenceExpectedFiles
        difference_percent = $differencePercent
    }
    safety = [ordered]@{
        lock_present = $null -ne $lock
        lock_pid = $lockPid
        lock_process_alive = $lockAlive
        difference_lock_present = $null -ne $differenceLock
        difference_lock_pid = $differenceLockPid
        difference_lock_process_alive = $differenceLockAlive
        drive_free_gib = $freeGiB
        current_output_last_write = $currentOutputWrite
        latest_log = $latestLogPath
        latest_log_last_write = $latestLogWrite
    }
    gates = [ordered]@{
        final_manifest_status = if ($null -ne $final) {
            $final.status
        } else {
            'pending'
        }
        difference_inventory_status = if ($null -ne $difference) {
            $difference.status
        } else {
            'pending'
        }
        adoption_status = if ($null -ne $adoption) {
            $adoption.status
        } else {
            'pending'
        }
        allow_yearly_mfa = (
            $null -ne $adoption -and
            [bool]$adoption.gate.allow_yearly_mfa
        )
    }
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 8
    return
}

Write-Host 'Common MFA pronunciation r2 - read-only dashboard' `
    -ForegroundColor Cyan
Write-Host ('Observed: {0}' -f $result.observed_at)
Write-Host ('Phase:    {0}' -f $result.phase)
Write-Host ''
[pscustomobject]$result.progress | Format-List
[pscustomobject]$result.safety | Format-List
[pscustomobject]$result.gates | Format-List

if ($WatchSeconds -gt 0) {
    while ($true) {
        Start-Sleep -Seconds $WatchSeconds
        Clear-Host
        & $PSCommandPath `
            -ReleaseRoot $releaseRootFull `
            -LockPath $LockPath
    }
}
