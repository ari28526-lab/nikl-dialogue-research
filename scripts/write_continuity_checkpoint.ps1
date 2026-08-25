#Requires -Version 5.1
<#
.SYNOPSIS
Append a public-safe project continuity checkpoint.

.DESCRIPTION
Records a short semantic handoff plus mechanical Git state in an append-only
JSONL file. The script never commits, pushes, or reads file contents.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Summary,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$NextStep,

    [ValidateSet('completed', 'in_progress', 'paused', 'blocked')]
    [string]$Status = 'paused',

    [string[]]$DecisionNeeded = @(),

    [string]$Actor = 'codex',

    [string]$LogPath = (
        'docs\environment\CONTINUITY_CHECKPOINTS.jsonl'
    ),

    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-ProjectRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    if ([IO.Path]::IsPathRooted($RelativePath)) {
        throw 'LogPath는 프로젝트 루트 기준 상대경로여야 합니다.'
    }
    if ([IO.Path]::GetExtension($RelativePath) -ne '.jsonl') {
        throw 'LogPath 확장자는 .jsonl이어야 합니다.'
    }

    $rootFull = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
    $candidate = [IO.Path]::GetFullPath((Join-Path $rootFull $RelativePath))
    $rootPrefix = $rootFull + '\'
    if (-not $candidate.StartsWith(
        $rootPrefix, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw 'LogPath가 프로젝트 루트 밖을 가리킵니다.'
    }
    return $candidate
}

function Invoke-GitText {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    $output = @(& git -C $ProjectRoot @Arguments 2>$null)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "git 명령 실패(exit=$exitCode): $($Arguments -join ' ')"
    }
    if ($exitCode -ne 0) { return @() }
    return @($output)
}

function Add-Utf8JsonLine {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Line
    )

    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw "체크포인트 디렉터리가 없습니다: $parent"
    }

    $attempts = 4
    for ($attempt = 1; $attempt -le $attempts; $attempt++) {
        try {
            $encoding = New-Object Text.UTF8Encoding($false)
            $stream = New-Object IO.FileStream(
                $Path,
                [IO.FileMode]::Append,
                [IO.FileAccess]::Write,
                [IO.FileShare]::Read
            )
            try {
                $writer = New-Object IO.StreamWriter($stream, $encoding)
                try {
                    $writer.WriteLine($Line)
                    $writer.Flush()
                } finally {
                    $writer.Dispose()
                }
            } finally {
                $stream.Dispose()
            }
            return
        } catch {
            if ($attempt -eq $attempts) { throw }
            Start-Sleep -Milliseconds (100 * $attempt)
        }
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$resolvedRoot = [IO.Path]::GetFullPath($projectRoot)
$resolvedLog = Resolve-ProjectRelativePath $resolvedRoot $LogPath

$branch = (Invoke-GitText $resolvedRoot @(
    'rev-parse', '--abbrev-ref', 'HEAD'
))[0]
$head = (Invoke-GitText $resolvedRoot @('rev-parse', 'HEAD'))[0]
$upstreamRows = @(Invoke-GitText $resolvedRoot @(
    'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}'
) -AllowFailure)
$upstream = $null
$ahead = $null
$behind = $null
if ($upstreamRows.Count -gt 0) {
    $upstream = [string]$upstreamRows[0]
    $counts = @(Invoke-GitText $resolvedRoot @(
        'rev-list', '--left-right', '--count', "$upstream...HEAD"
    ))
    if ($counts.Count -gt 0) {
        $parts = @($counts[0] -split '\s+')
        if ($parts.Count -eq 2) {
            $behind = [int]$parts[0]
            $ahead = [int]$parts[1]
        }
    }
}

$statusRows = @(Invoke-GitText $resolvedRoot @(
    'status', '--porcelain=v1', '-unormal'
))
$stagedCount = 0
$modifiedCount = 0
$untrackedCount = 0
$changedPaths = [Collections.Generic.List[string]]::new()
foreach ($rowValue in $statusRows) {
    $row = [string]$rowValue
    if ($row.Length -lt 3) { continue }
    if ($row.StartsWith('?? ')) {
        $untrackedCount++
    } else {
        if ($row[0] -ne ' ') { $stagedCount++ }
        if ($row[1] -ne ' ') { $modifiedCount++ }
    }
    if ($changedPaths.Count -lt 50) {
        $changedPaths.Add($row.Substring(3).Trim())
    }
}

$decisionList = [Collections.Generic.List[string]]::new()
foreach ($decision in @($DecisionNeeded)) {
    if (-not [string]::IsNullOrWhiteSpace($decision)) {
        $decisionList.Add($decision.Trim())
    }
}

$now = [DateTimeOffset]::Now
$checkpointId = 'continuity_' + $now.ToString('yyyyMMddTHHmmssfff') + '_' +
    [guid]::NewGuid().ToString('N').Substring(0, 8)
$record = [ordered]@{
    schema_version = 'project_continuity_checkpoint.v1'
    checkpoint_id = $checkpointId
    recorded_at = $now.ToString('yyyy-MM-ddTHH:mm:sszzz')
    actor = $Actor
    status = $Status
    summary = $Summary.Trim()
    next_step = $NextStep.Trim()
    decision_needed = @($decisionList)
    git = [ordered]@{
        branch = $branch
        head = $head
        upstream = $upstream
        ahead = $ahead
        behind = $behind
        working_tree_clean = ($statusRows.Count -eq 0)
        staged_count = $stagedCount
        modified_count = $modifiedCount
        untracked_count = $untrackedCount
        changed_paths_preview = @($changedPaths)
        changed_paths_truncated = ($statusRows.Count -gt 50)
    }
    safety = [ordered]@{
        automatic_commit = $false
        automatic_push = $false
        file_contents_recorded = $false
        absolute_paths_recorded = $false
    }
}
$jsonLine = $record | ConvertTo-Json -Depth 6 -Compress

if ($PreflightOnly) {
    [pscustomobject]@{
        status = 'preflight_passed'
        log_path = $LogPath
        checkpoint_id = $checkpointId
        record = $record
    } | ConvertTo-Json -Depth 7
    exit 0
}

Add-Utf8JsonLine $resolvedLog $jsonLine
$writtenHash = (Get-FileHash -LiteralPath $resolvedLog -Algorithm SHA256).Hash
[pscustomobject]@{
    status = 'checkpoint_appended'
    checkpoint_id = $checkpointId
    log_path = $LogPath
    log_sha256 = $writtenHash.ToLowerInvariant()
} | ConvertTo-Json
