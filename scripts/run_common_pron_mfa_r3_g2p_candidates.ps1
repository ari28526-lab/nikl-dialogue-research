#Requires -Version 5.1
<#
Generate resumable 1-best Jamo G2P candidates for the r3 rule targets.

This script does not finalize the common pronunciation dictionary and does not
start annual MFA.  Candidate phones are admitted later only when they match the
independently computed broad-Roman rule target.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^common_pron_mfa_r3_[0-9]{8}$')]
    [string]$StageId = 'common_pron_mfa_r3_20260807',

    [ValidateRange(1, 16)]
    [int]$NumJobs = 4,

    [ValidateRange(10, 500)]
    [int]$MinimumFreeGiB = 30,

    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (
    Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')
).Path
$commonRoot = 'D:\mfa_common_pron'
$stageRoot = Join-Path (Join-Path $commonRoot 'staging') $StageId
$candidateRoot = Join-Path $stageRoot '03_g2p_rule_targets_1best'
$targetManifestPath = Join-Path $candidateRoot 'G2P_TARGETS_MANIFEST.json'
$expectedTargetManifestSha256 = `
    'af8cfdc93f4d1f354b9fd58abc51084a83a5788b8ffc68510486c1b51deaa5b3'
$bundlePath = Join-Path $projectRoot `
    'outputs\reports\korean_mfa_latest_jamo_bundle_20260728.json'
$releaseGatePath = Join-Path $projectRoot `
    'config\mfa_pronunciation_release_gate.json'
$python = Join-Path $env:USERPROFILE 'miniforge3\envs\mfa\python.exe'
$mfaEnvironment = Join-Path $env:USERPROFILE 'miniforge3\envs\mfa'
$mfa = Join-Path $mfaEnvironment 'Scripts\mfa.exe'
$verifier = Join-Path $PSScriptRoot `
    'python\verify_common_pron_r3_g2p_candidates.py'

function Say([string]$Message) {
    Write-Host (
        '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    ) -ForegroundColor Cyan
}

function Assert-Child([string]$Path, [string]$Root) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $allowed = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith(
        $allowed, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Path boundary violation: $resolved (root=$Root)"
    }
}

function Invoke-MfaLogged(
    [string[]]$Arguments,
    [string]$LogPath,
    [string]$AllowedRoot
) {
    Assert-Child $LogPath $AllowedRoot
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $script:mfa @Arguments 2>&1 |
            Tee-Object -FilePath $LogPath |
            ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return $code
}

function Archive-Incomplete(
    [string[]]$Paths,
    [string]$Root,
    [string]$Label
) {
    $present = @($Paths | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and
        (Test-Path -LiteralPath $_)
    })
    if ($present.Count -eq 0) { return }
    $archive = Join-Path $Root (
        'archive_interrupted\{0}\{1}' -f
        (Get-Date -Format 'yyyyMMdd_HHmmss'), $Label
    )
    Assert-Child $archive $Root
    New-Item -ItemType Directory -Force -Path $archive | Out-Null
    foreach ($path in $present) {
        Assert-Child $path $Root
        $destination = Join-Path $archive (Split-Path -Leaf $path)
        if (Test-Path -LiteralPath $destination) {
            throw "Archive collision: $destination"
        }
        Move-Item -LiteralPath $path -Destination $destination
    }
    Say "Interrupted shard preserved: $archive"
}

function Set-JsonAtomic([string]$Path, [object]$Value) {
    Assert-Child $Path $candidateRoot
    $temporary = "$Path.$PID.partial"
    $Value | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Acquire-Lock([string]$Path) {
    Assert-Child $Path $commonRoot
    New-Item -ItemType Directory -Force `
        -Path (Split-Path -Parent $Path) | Out-Null
    if (Test-Path -LiteralPath $Path) {
        $live = $false
        try {
            $old = Get-Content -Raw -Encoding UTF8 `
                -LiteralPath $Path | ConvertFrom-Json
            $live = [int]$old.pid -gt 0 -and $null -ne (
                Get-Process -Id ([int]$old.pid) -ErrorAction SilentlyContinue
            )
        } catch {}
        if ($live) {
            throw "r3 G2P candidate lock is active: $Path"
        }
        $staleRoot = Join-Path $commonRoot 'archive_stale_locks'
        $stale = Join-Path $staleRoot (
            '{0}_{1}.json' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $StageId
        )
        Assert-Child $stale $commonRoot
        New-Item -ItemType Directory -Force -Path $staleRoot | Out-Null
        Move-Item -LiteralPath $Path -Destination $stale
    }
    $temporary = "$Path.$PID.partial"
    [ordered]@{
        schema_version = 1
        pipeline = 'common_pron_r3_g2p_candidates'
        stage_id = $StageId
        pid = $PID
        host = $env:COMPUTERNAME
        acquired_at = (Get-Date).ToString('o')
    } | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $Path
}

function Release-Lock([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    try {
        $lock = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $Path | ConvertFrom-Json
        if (
            [int]$lock.pid -eq $PID -and
            [string]$lock.stage_id -eq $StageId
        ) {
            Remove-Item -LiteralPath $Path -Force
        }
    } catch {
        Write-Warning "Lock release failed; inspect manually: $Path"
    }
}

if (-not ('CommonPronR3G2pSleepGuard' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class CommonPronR3G2pSleepGuard {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
}

function Enable-SleepGuard {
    $result = [CommonPronR3G2pSleepGuard]::SetThreadExecutionState(
        [uint32]0x80000001
    )
    if ($result -eq 0) { throw 'Windows sleep guard activation failed' }
}

function Disable-SleepGuard {
    [void][CommonPronR3G2pSleepGuard]::SetThreadExecutionState(
        [uint32]0x80000000
    )
}

foreach ($path in @(
    $targetManifestPath, $bundlePath, $releaseGatePath, $python, $mfa,
    $verifier
)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required input or executable is missing: $path"
    }
}

$drive = [IO.DriveInfo]::new('D')
if (-not $drive.IsReady -or $drive.VolumeLabel -ne 'DATA_SSD') {
    throw 'D: DATA_SSD safety gate failed'
}
$freeGiB = [math]::Round($drive.AvailableFreeSpace / 1GB, 3)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw "D: free space is too low: ${freeGiB}GiB < ${MinimumFreeGiB}GiB"
}

$gate = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath $releaseGatePath | ConvertFrom-Json
if (
    [string]$gate.status -ne 'blocked_pending_r3' -or
    -not (@($gate.blocked_release_ids) -contains 'common_pron_mfa_r2_20260728')
) {
    throw 'Project pronunciation gate is not the expected r3 hold state'
}
$bundle = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath $bundlePath | ConvertFrom-Json
$targets = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath $targetManifestPath | ConvertFrom-Json
$targetManifestSha256 = (
    Get-FileHash -LiteralPath $targetManifestPath -Algorithm SHA256
).Hash.ToLowerInvariant()
if (
    $targetManifestSha256 -ne $expectedTargetManifestSha256 -or
    [string]$targets.schema_version -ne 'common_pron_r3_g2p_targets.v1' -or
    [string]$targets.status -ne 'prepared' -or
    [int]$targets.counts.unique_targets -ne 310605 -or
    [int]$targets.counts.shards -ne 13
) {
    throw 'r3 G2P target manifest contract mismatch'
}
$g2pModel = [IO.Path]::GetFullPath(
    [string]$bundle.outputs.g2p_model.path
)
$acousticModel = [IO.Path]::GetFullPath(
    [string]$bundle.outputs.acoustic_model.path
)
if (
    $g2pModel -ne [IO.Path]::GetFullPath(
        [string]$targets.inputs.g2p_model.path
    ) -or
    [string]$bundle.outputs.g2p_model.sha256 -ne
        [string]$targets.inputs.g2p_model.sha256 -or
    -not [bool]$bundle.contract.acoustic_g2p_phone_inventory_equal
) {
    throw 'Frozen acoustic/G2P bundle does not match the target manifest'
}
foreach ($modelRecord in @(
    $bundle.outputs.g2p_model, $bundle.outputs.acoustic_model
)) {
    $modelPath = [IO.Path]::GetFullPath([string]$modelRecord.path)
    if (-not (Test-Path -LiteralPath $modelPath -PathType Leaf)) {
        throw "Frozen model is missing: $modelPath"
    }
    $actualSha = (Get-FileHash -LiteralPath $modelPath -Algorithm SHA256).Hash
    if ($actualSha -ne [string]$modelRecord.sha256) {
        throw "Frozen model SHA256 mismatch: $modelPath"
    }
}

$shards = @($targets.outputs.input_shards)
if ($shards.Count -ne [int]$targets.counts.shards) {
    throw 'Target shard array count mismatch'
}
foreach ($shard in $shards) {
    $inputPath = [IO.Path]::GetFullPath([string]$shard.path)
    Assert-Child $inputPath $candidateRoot
    if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) {
        throw "Target shard is missing: $inputPath"
    }
    $actualSha = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash
    if ($actualSha -ne [string]$shard.sha256) {
        throw "Target shard SHA256 mismatch: $inputPath"
    }
}

$annualBulkLock = 'D:\mfa_eojeol\locks\pre_mfa_bulk.lock'
if (Test-Path -LiteralPath $annualBulkLock) {
    throw "Annual MFA lock exists; concurrent G2P is blocked: $annualBulkLock"
}
if (
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -match '^(mfa|conda)$' }
) {
    throw 'Another MFA/conda process is already active'
}

Say (
    "Preflight passed: targets=$($targets.counts.unique_targets), " +
    "shards=$($shards.Count), jobs=$NumJobs, D free=${freeGiB}GiB"
)
Say 'This phase creates candidates only; it does not modify TextGrids or run MFA.'
if ($PreflightOnly) {
    Write-Host 'PreflightOnly: no output directory, lock, or G2P process was created.'
    exit 0
}

$outputDir = Join-Path $candidateRoot 'output_shards'
$reportDir = Join-Path $candidateRoot 'shard_reports'
$logDir = Join-Path $candidateRoot 'logs'
$tempDir = Join-Path $candidateRoot 'work\g2p_temp'
$archiveRoot = Join-Path $candidateRoot 'archive_interrupted'
foreach ($path in @(
    $outputDir, $reportDir, $logDir, $tempDir, $archiveRoot
)) {
    Assert-Child $path $candidateRoot
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$lockPath = Join-Path $commonRoot 'locks\common_pron_r3_g2p_candidates.lock'
Acquire-Lock $lockPath
$sleepGuardEnabled = $false
try {
    Enable-SleepGuard
    $sleepGuardEnabled = $true
    Write-Host 'Windows system sleep guard: enabled' -ForegroundColor Cyan
    $env:Path = (
        "$mfaEnvironment;$mfaEnvironment\Library\bin;" +
        "$mfaEnvironment\Scripts;$mfaEnvironment\bin;$env:Path"
    )
    $env:PYTHONUTF8 = '1'
    $completed = 0
    foreach ($shard in $shards) {
        $index = [int]$shard.shard_index
        $inputPath = [IO.Path]::GetFullPath([string]$shard.path)
        $outputPath = Join-Path $outputDir `
            ([string]$shard.expected_output_name)
        $reportPath = Join-Path $reportDir (
            'g2p_target_{0:D5}.json' -f $index
        )
        $logPath = Join-Path $logDir (
            'g2p_target_{0:D5}.log' -f $index
        )
        $shardTemp = Join-Path $tempDir ('g2p_target_{0:D5}' -f $index)
        $validCompletion = $false
        if (
            (Test-Path -LiteralPath $outputPath -PathType Leaf) -and
            (Test-Path -LiteralPath $reportPath -PathType Leaf)
        ) {
            & $python $verifier verify-existing-report `
                --input-shard $inputPath `
                --output-shard $outputPath `
                --acoustic-model $acousticModel `
                --report $reportPath
            $validCompletion = $LASTEXITCODE -eq 0
        }
        if ($validCompletion) {
            $completed += 1
            Say "Shard $index/$($shards.Count): verified output reused"
            continue
        }
        Archive-Incomplete `
            @($outputPath, $reportPath, $logPath, $shardTemp) `
            $candidateRoot ('shard_{0:D5}' -f $index)
        Say "Shard $index/$($shards.Count): Jamo G2P started"
        $arguments = @(
            'g2p', $inputPath, $g2pModel, $outputPath,
            '--num_pronunciations', '1',
            '--strict_graphemes',
            '--temporary_directory', $shardTemp,
            '--num_jobs', "$NumJobs",
            '--clean'
        )
        $code = Invoke-MfaLogged $arguments $logPath $candidateRoot
        if ($code -ne 0) {
            throw "G2P shard $index failed (exit=$code)"
        }
        & $python $verifier verify-shard `
            --input-shard $inputPath `
            --output-shard $outputPath `
            --acoustic-model $acousticModel `
            --report $reportPath
        if ($LASTEXITCODE -ne 0) {
            throw "G2P shard $index candidate verification failed"
        }
        $completed += 1
        Set-JsonAtomic (Join-Path $candidateRoot 'RUN_STATUS.json') `
            ([ordered]@{
                schema_version = 1
                status = 'g2p_running'
                recorded_at = (Get-Date).ToString('o')
                stage_id = $StageId
                pid = $PID
                completed_shards = $completed
                total_shards = $shards.Count
                last_completed_shard = $index
                candidate_is_final_selection = $false
            })
        Say "Shard $index completed ($completed/$($shards.Count))"
    }
    $phaseManifest = Join-Path $candidateRoot `
        'G2P_CANDIDATE_OUTPUTS_MANIFEST.json'
    & $python $verifier finalize `
        --target-manifest $targetManifestPath `
        --output-root $candidateRoot `
        --acoustic-model $acousticModel `
        --phase-manifest $phaseManifest
    if ($LASTEXITCODE -ne 0) {
        throw 'r3 G2P candidate phase final verification failed'
    }
    Set-JsonAtomic (Join-Path $candidateRoot 'RUN_STATUS.json') `
        ([ordered]@{
            schema_version = 1
            status = 'success_candidates_not_selected'
            recorded_at = (Get-Date).ToString('o')
            stage_id = $StageId
            pid = $PID
            completed_shards = $shards.Count
            total_shards = $shards.Count
            phase_manifest = $phaseManifest
            candidate_is_final_selection = $false
            next_required_gate = 'exact broad-Roman target agreement'
        })
    Say "Candidate G2P phase complete: $phaseManifest"
    Say 'No final dictionary was adopted and no annual MFA was started.'
} finally {
    if ($sleepGuardEnabled) {
        Disable-SleepGuard
        Write-Host 'Windows system sleep guard: disabled' -ForegroundColor Cyan
    }
    Release-Lock $lockPath
}
