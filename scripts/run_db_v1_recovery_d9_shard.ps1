#Requires -Version 5.1
param(
    [switch]$PreflightOnly,
    [string]$ApprovalContract = '',
    [ValidateRange(1, 8)]
    [int]$NumJobs = 4
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\ari30\miniforge3\envs\mfa\python.exe'
$mfa = 'C:\Users\ari30\miniforge3\envs\mfa\Scripts\mfa.exe'
$package = Join-Path $projectRoot (
    'outputs\releases\nikl_dialogue_research_db_v1_recovery_d9_gate_20260817'
)
$outputRoot = 'D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D9_CONTROLLED_BEAM_RETRY_0001'
$preflight = Join-Path $PSScriptRoot 'python\preflight_db_v1_recovery_d9.py'
$materializer = Join-Path $PSScriptRoot 'python\materialize_db_v1_recovery_d9_shard.py'
$auditor = Join-Path $PSScriptRoot 'python\audit_db_v1_recovery_d9_mfa.py'
$configPath = Join-Path $package 'D9_MFA_CONFIG.json'
$preflightReport = Join-Path $projectRoot 'outputs\reports\PREFLIGHT_db_v1_recovery_D9_20260817.json'
$lockPath = Join-Path $projectRoot 'work\locks\db_v1_recovery_d9.lock'
$conflictingLocks = @(
    'D:\mfa_eojeol\locks\pre_mfa_bulk.lock',
    'D:\mfa_eojeol\locks\mfa_year_queue.lock',
    'D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\locks\mfa_r3_year.lock',
    (Join-Path $projectRoot 'work\locks\db_v1_recovery_d5.lock')
)

function Write-JsonAtomic {
    param([string]$Path, [object]$Value)
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temp = $Path + '.' + [guid]::NewGuid().ToString('N') + '.partial'
    [IO.File]::WriteAllText(
        $temp,
        (($Value | ConvertTo-Json -Depth 20) + [Environment]::NewLine),
        [Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Write-JsonLineRetry {
    param([string]$Path, [object]$Value)
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(
        (($Value | ConvertTo-Json -Compress -Depth 10) + [Environment]::NewLine)
    )
    for ($attempt = 1; $attempt -le 6; $attempt++) {
        try {
            $stream = [IO.FileStream]::new(
                $Path, [IO.FileMode]::Append, [IO.FileAccess]::Write,
                [IO.FileShare]::ReadWrite
            )
            try {
                $stream.Write($bytes, 0, $bytes.Length)
                $stream.Flush($true)
            } finally {
                $stream.Dispose()
            }
            return
        } catch [IO.IOException] {
            Start-Sleep -Milliseconds (100 * $attempt)
        }
    }
    Write-Warning 'D9 heartbeat append를 건너뜀; MFA 계산은 계속함.'
}

function Get-MfaRuntimePath {
    $environmentRoot = Split-Path -Parent (Split-Path -Parent $mfa)
    $parts = [Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
        $environmentRoot,
        (Join-Path $environmentRoot 'Library\mingw-w64\bin'),
        (Join-Path $environmentRoot 'Library\usr\bin'),
        (Join-Path $environmentRoot 'Library\bin'),
        (Join-Path $environmentRoot 'Scripts'),
        (Join-Path $environmentRoot 'bin')
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Container) {
            $parts.Add($candidate)
        }
    }
    $parts.Add([string]$env:Path)
    return [string]::Join(';', $parts.ToArray())
}

foreach ($required in @($python, $mfa, $preflight, $materializer, $auditor, $configPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "D9 required file missing: $required"
    }
}
if ($NumJobs -ne 4) {
    throw 'D9 execution contract fixes NumJobs=4; a different value requires a new contract.'
}
foreach ($conflictingLock in $conflictingLocks) {
    if (Test-Path -LiteralPath $conflictingLock -PathType Leaf) {
        throw "Another MFA workflow lock is present; D9 remains closed: $conflictingLock"
    }
}
if (@(Get-Process -Name 'mfa' -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'An MFA process is already active; D9 remains closed.'
}

$preflightArguments = @(
    $preflight, '--project-root', $projectRoot, '--package', $package,
    '--report', $preflightReport
)
if (-not [string]::IsNullOrWhiteSpace($ApprovalContract)) {
    $preflightArguments += @('--approval-contract', [IO.Path]::GetFullPath($ApprovalContract))
}
& $python @preflightArguments
if ($LASTEXITCODE -ne 0) {
    throw "D9 read-only preflight failed(exit=$LASTEXITCODE): $preflightReport"
}
if ($PreflightOnly) {
    Write-Host "[GO] D9 read-only preflight passed; Gate remains closed: $preflightReport" -ForegroundColor Green
    exit 0
}
if ([string]::IsNullOrWhiteSpace($ApprovalContract)) {
    throw 'D9 scope-bound approval contract missing; no D: files created and MFA not run.'
}

$approvalPath = [IO.Path]::GetFullPath($ApprovalContract)
$lockStream = $null
try {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $lockPath) | Out-Null
    $lockStream = [IO.File]::Open(
        $lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read
    )
    $lockJson = [ordered]@{
        schema_version = 'research_db_v1_recovery_d9_lock.v1'
        status = 'owned'
        owner_pid = $PID
        child_pid = $null
        shard_id = 'D9_CONTROLLED_BEAM_RETRY_0001'
        started_at = [DateTimeOffset]::Now.ToString('o')
    } | ConvertTo-Json -Depth 8
    $lockBytes = [Text.UTF8Encoding]::new($false).GetBytes($lockJson + [Environment]::NewLine)
    $lockStream.Write($lockBytes, 0, $lockBytes.Length)
    $lockStream.Flush($true)
    $lockStream.Dispose()
    $lockStream = $null

    & $python $materializer --package $package --approval-contract $approvalPath --output-root $outputRoot
    if ($LASTEXITCODE -ne 0) { throw "D9 exact-copy materialization failed(exit=$LASTEXITCODE)" }

    $stateRoot = Join-Path $outputRoot 'state'
    $doneMarker = Join-Path $stateRoot 'MFA_DONE.json'
    if (Test-Path -LiteralPath $doneMarker -PathType Leaf) {
        $done = Get-Content -LiteralPath $doneMarker -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([string]$done.status -eq 'completed_controlled_retry_no_merge') {
            Write-Host "[OK] D9 already complete: $doneMarker" -ForegroundColor Green
            exit 0
        }
        throw "D9 done marker status differs: $doneMarker"
    }
    $failedMarker = Join-Path $stateRoot 'MFA_FAILED.json'
    if (Test-Path -LiteralPath $failedMarker -PathType Leaf) {
        throw "D9 prior controlled run failed; a second run requires a new contract: $failedMarker"
    }

    $execution = Get-Content -LiteralPath (Join-Path $package 'D9_EXECUTION_CONTRACT.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $dictionary = [string]$execution.models.dictionary.path
    $acoustic = [string]$execution.models.acoustic.path
    $corpus = Join-Path $outputRoot 'corpus'
    $mfaOutput = Join-Path $outputRoot 'mfa_output'
    $temp = Join-Path $outputRoot 'temp'
    $logs = Join-Path $outputRoot 'logs'
    New-Item -ItemType Directory -Force -Path @($logs, $temp) | Out-Null
    if (Test-Path -LiteralPath $mfaOutput -PathType Container) {
        $existingAudit = Join-Path $stateRoot 'MFA_AUDIT_EXISTING_OUTPUT.json'
        & $python $auditor --package $package --output-root $mfaOutput --report $existingAudit
        if ($LASTEXITCODE -ne 0) {
            throw "D9 existing-output audit failed(exit=$LASTEXITCODE): $existingAudit"
        }
        $existing = Get-Content -LiteralPath $existingAudit -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([int]$existing.textgrid_present -eq [int]$existing.expected) {
            Write-JsonAtomic -Path $doneMarker -Value ([ordered]@{
                schema_version = 'research_db_v1_recovery_d9_done.v1'
                status = 'completed_controlled_retry_no_merge'
                shard_id = 'D9_CONTROLLED_BEAM_RETRY_0001'
                expected = [int]$existing.expected
                textgrid_present = [int]$existing.textgrid_present
                textgrid_missing = [int]$existing.textgrid_missing
                beam = 100
                retry_beam = 400
                audit = $existingAudit
                recovered_from_existing_complete_output = $true
                automatic_merge_performed = $false
                completed_at = [DateTimeOffset]::Now.ToString('o')
            })
            Write-Host "[OK] D9 complete output audited; no duplicate MFA launch: $doneMarker" -ForegroundColor Green
            exit 0
        }
    }
    $tempContract = Join-Path $stateRoot 'TEMP_CONTRACT.json'
    $tempChildren = @(Get-ChildItem -LiteralPath $temp -Force -ErrorAction SilentlyContinue)
    $resume = $tempChildren.Count -gt 0
    if ($resume -and -not (Test-Path -LiteralPath $tempContract -PathType Leaf)) {
        throw 'D9 temp exists without TEMP_CONTRACT; automatic clean/reuse forbidden.'
    }
    if (-not $resume) {
        Write-JsonAtomic -Path $tempContract -Value ([ordered]@{
            schema_version = 'research_db_v1_recovery_d9_temp.v1'
            status = 'clean_start_pending_or_running'
            shard_id = 'D9_CONTROLLED_BEAM_RETRY_0001'
            beam = 100
            retry_beam = 400
            approval_sha256 = (Get-FileHash -LiteralPath $approvalPath -Algorithm SHA256).Hash.ToLowerInvariant()
            created_at = [DateTimeOffset]::Now.ToString('o')
        })
    }

    $runId = '{0}_{1}' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PID
    $stdout = Join-Path $logs "mfa_D9_${runId}_stdout.log"
    $stderr = Join-Path $logs "mfa_D9_${runId}_stderr.log"
    $heartbeat = Join-Path $logs "mfa_D9_${runId}_heartbeat.jsonl"
    $arguments = @(
        'align', $corpus, $dictionary, $acoustic, $mfaOutput,
        '--config_path', $configPath,
        '--beam', '100', '--retry_beam', '400',
        '--num_jobs', [string]$NumJobs,
        '--no_tokenization', '--temporary_directory', $temp,
        '--output_format', 'long_textgrid'
    )
    if (-not $resume) { $arguments += '--clean' } else { $arguments += '--no_clean' }
    Write-JsonAtomic -Path (Join-Path $stateRoot "MFA_RUN_${runId}.json") -Value ([ordered]@{
        schema_version = 'research_db_v1_recovery_d9_run.v1'
        status = 'starting'
        run_id = $runId
        resume = $resume
        beam = 100
        retry_beam = 400
        num_jobs = $NumJobs
        arguments = $arguments
        automatic_merge = $false
        recorded_at = [DateTimeOffset]::Now.ToString('o')
    })
    $oldPath = [string]$env:Path
    $oldSkipExport = $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT
    $env:Path = Get-MfaRuntimePath
    Remove-Item Env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT -ErrorAction SilentlyContinue
    try {
        & $python -c 'from montreal_forced_aligner.utils import check_third_party; check_third_party()'
        if ($LASTEXITCODE -ne 0) { throw 'MFA third-party dependency check failed' }
        $process = Start-Process -FilePath $mfa -ArgumentList $arguments `
            -NoNewWindow -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    } finally {
        $env:Path = $oldPath
        if ($null -ne $oldSkipExport) { $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT = $oldSkipExport }
    }
    $null = $process.Handle
    while (-not $process.HasExited) {
        Write-JsonLineRetry -Path $heartbeat -Value ([ordered]@{
            observed_at = [DateTimeOffset]::Now.ToString('o')
            shard_id = 'D9_CONTROLLED_BEAM_RETRY_0001'
            wrapper_pid = $PID
            child_pid = $process.Id
            child_alive = $true
            stdout_bytes = $(if (Test-Path $stdout) { (Get-Item $stdout).Length } else { 0 })
            stderr_bytes = $(if (Test-Path $stderr) { (Get-Item $stderr).Length } else { 0 })
        })
        Start-Sleep -Seconds 60
        $process.Refresh()
    }
    $exitCode = $process.ExitCode
    if ($exitCode -ne 0) {
        Write-JsonAtomic -Path (Join-Path $stateRoot 'MFA_FAILED.json') -Value ([ordered]@{
            schema_version = 'research_db_v1_recovery_d9_mfa_failure.v1'
            status = 'failed_preserved_for_diagnosis'
            exit_code = $exitCode
            stdout = $stdout
            stderr = $stderr
            automatic_retry_performed = $false
            recorded_at = [DateTimeOffset]::Now.ToString('o')
        })
        throw "D9 controlled retry failed(exit=$exitCode); no second automatic run: $stderr"
    }

    $auditReport = Join-Path $stateRoot 'MFA_AUDIT.json'
    & $python $auditor --package $package --output-root $mfaOutput --report $auditReport
    if ($LASTEXITCODE -ne 0) { throw "D9 audit failed(exit=$LASTEXITCODE): $auditReport" }
    $audit = Get-Content -LiteralPath $auditReport -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-JsonAtomic -Path $doneMarker -Value ([ordered]@{
        schema_version = 'research_db_v1_recovery_d9_done.v1'
        status = 'completed_controlled_retry_no_merge'
        shard_id = 'D9_CONTROLLED_BEAM_RETRY_0001'
        expected = [int]$audit.expected
        textgrid_present = [int]$audit.textgrid_present
        textgrid_missing = [int]$audit.textgrid_missing
        beam = 100
        retry_beam = 400
        stdout = $stdout
        stderr = $stderr
        audit = $auditReport
        automatic_merge_performed = $false
        completed_at = [DateTimeOffset]::Now.ToString('o')
    })
    Write-Host "[OK] D9 complete; no automatic merge: $doneMarker" -ForegroundColor Green
} finally {
    if ($null -ne $lockStream) { $lockStream.Dispose() }
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        try {
            $lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ([int]$lock.owner_pid -eq $PID) { Remove-Item -LiteralPath $lockPath -Force }
        } catch {
            Write-Warning "D9 lock cleanup requires inspection: $lockPath"
        }
    }
}
