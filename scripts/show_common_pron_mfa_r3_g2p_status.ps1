#Requires -Version 5.1
<# Read-only status board for the r3 G2P candidate phase. #>
[CmdletBinding()]
param(
    [ValidatePattern('^common_pron_mfa_r3_[0-9]{8}$')]
    [string]$StageId = 'common_pron_mfa_r3_20260807'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Join-Path 'D:\mfa_common_pron\staging' $StageId
$candidateRoot = Join-Path $root '03_g2p_rule_targets_1best'
$targetManifestPath = Join-Path $candidateRoot 'G2P_TARGETS_MANIFEST.json'
$lockPath = 'D:\mfa_common_pron\locks\common_pron_r3_g2p_candidates.lock'
if (-not (Test-Path -LiteralPath $targetManifestPath -PathType Leaf)) {
    throw "r3 target manifest is missing: $targetManifestPath"
}
$target = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath $targetManifestPath | ConvertFrom-Json
$reports = @(
    Get-ChildItem -LiteralPath (Join-Path $candidateRoot 'shard_reports') `
        -Filter 'g2p_target_*.json' -File -ErrorAction SilentlyContinue
)
$validReports = [Collections.Generic.List[object]]::new()
foreach ($file in $reports) {
    try {
        $report = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $file.FullName | ConvertFrom-Json
        if (
            [string]$report.schema_version -eq
                'common_pron_r3_g2p_candidate_shard.v1' -and
            [string]$report.status -eq 'success_candidate_output'
        ) {
            $validReports.Add($report)
        }
    } catch {}
}
$completed = $validReports.Count
$candidateWords = 0L
$missingWords = 0L
foreach ($report in $validReports) {
    $candidateWords += [long]$report.counts.output_words
    $missingWords += [long]$report.counts.missing_no_path_words
}
$lockPresent = Test-Path -LiteralPath $lockPath -PathType Leaf
$lockPid = $null
$lockAlive = $false
if ($lockPresent) {
    try {
        $lock = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $lockPath | ConvertFrom-Json
        $lockPid = [int]$lock.pid
        $lockAlive = $lockPid -gt 0 -and $null -ne (
            Get-Process -Id $lockPid -ErrorAction SilentlyContinue
        )
    } catch {}
}
$partial = @(
    Get-ChildItem -LiteralPath (Join-Path $candidateRoot 'output_shards') `
        -Filter 'g2p_target_*.dict' -File -ErrorAction SilentlyContinue |
        Where-Object {
            $reportName = [IO.Path]::GetFileNameWithoutExtension($_.Name) +
                '.json'
            -not (Test-Path -LiteralPath (
                Join-Path (Join-Path $candidateRoot 'shard_reports') $reportName
            ))
        }
)
$phaseManifest = Join-Path $candidateRoot `
    'G2P_CANDIDATE_OUTPUTS_MANIFEST.json'
$phase = if (Test-Path -LiteralPath $phaseManifest -PathType Leaf) {
    'success_candidates_not_selected'
} elseif ($lockAlive) {
    'g2p_running'
} elseif ($completed -gt 0 -or $partial.Count -gt 0) {
    'interrupted_resumable'
} else {
    'prepared_not_started'
}
$activeUnverified = if ($lockAlive) { $partial.Count } else { 0 }
$interruptedUnverified = if ($lockAlive) { 0 } else { $partial.Count }
$drive = [IO.DriveInfo]::new('D')
[pscustomobject]@{
    observed_at = (Get-Date).ToString('o')
    phase = $phase
    completed_shards = $completed
    total_shards = [int]$target.counts.shards
    percent_by_shards = [math]::Round(
        100.0 * $completed / [int]$target.counts.shards, 3
    )
    verified_candidate_words = $candidateWords
    recorded_no_path_words = $missingWords
    active_unverified_outputs = $activeUnverified
    interrupted_unverified_outputs = $interruptedUnverified
    lock_present = $lockPresent
    lock_pid = $lockPid
    lock_process_alive = $lockAlive
    drive_free_gib = if ($drive.IsReady) {
        [math]::Round($drive.AvailableFreeSpace / 1GB, 3)
    } else { $null }
    candidate_is_final_selection = $false
    annual_mfa_started = $false
}
