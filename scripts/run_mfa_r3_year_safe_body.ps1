param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year = '2020',
    [ValidateRange(1, 16)]
    [int]$NumJobs = 4,
    [switch]$PreflightOnly,
    [string]$PreflightReport = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$policyPath = Join-Path $projectRoot 'config\mfa_r3_runner_v1.json'
$gatePath = Join-Path $projectRoot 'config\mfa_pronunciation_release_gate.json'
$python = 'C:\Users\ari30\miniforge3\envs\mfa\python.exe'
$policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$releaseId = [string]$policy.release_id
$releaseRoot = [IO.Path]::GetFullPath([string]$policy.release_root)
$commonReleaseRoot = [IO.Path]::GetFullPath(
    [string]$policy.common_pron_release_root
)
$alignmentContract = Join-Path $commonReleaseRoot (
    '04_alignment_contracts\{0}\ALIGNMENT_CONTRACT_{0}.json' -f $Year
)
$alignmentAudit = Join-Path $projectRoot (
    'outputs\reports\AUDIT_mfa_r3_alignment_contract_{0}_20260809.json' -f
    $Year
)
$researchDatabaseAudit = Join-Path $commonReleaseRoot (
    '05_research_database\{0}\AUDIT_RESEARCH_DATABASE_{0}.json' -f $Year
)
$mfa = [IO.Path]::GetFullPath([string]$policy.mfa_executable)
$heartbeatSeconds = [int]$policy.heartbeat_seconds

if ([string]::IsNullOrWhiteSpace($PreflightReport)) {
    $PreflightReport = Join-Path $projectRoot (
        'work\mfa_r3_preflight\PREFLIGHT_{0}_{1}.json' -f
        $releaseId, $Year
    )
}
$preflightParent = Split-Path -Parent $PreflightReport
New-Item -ItemType Directory -Force -Path $preflightParent | Out-Null

function Get-DataDriveLabel {
    try {
        return [string]([IO.DriveInfo]::new('D:\')).VolumeLabel
    } catch {
        return ''
    }
}

function Get-LockProblems {
    param([string[]]$Paths)
    $problems = [System.Collections.Generic.List[object]]::new()
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $record = $null
        try {
            $record = Get-Content -LiteralPath $path -Raw -Encoding UTF8 |
                ConvertFrom-Json
        } catch {
            $problems.Add([pscustomobject]@{
                path = $path; status = 'unreadable'; live_pids = @()
            })
            continue
        }
        $pids = [System.Collections.Generic.List[int]]::new()
        foreach ($name in @('pid','owner_pid','wrapper_pid','child_pid')) {
            $property = $record.PSObject.Properties[$name]
            if ($null -eq $property) { continue }
            $value = 0
            if ([int]::TryParse([string]$property.Value, [ref]$value) -and
                $value -gt 0 -and -not $pids.Contains($value)) {
                $pids.Add($value)
            }
        }
        $live = @(
            $pids | Where-Object {
                $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue)
            }
        )
        $problems.Add([pscustomobject]@{
            path = $path
            status = $(if ($live.Count -gt 0) { 'live' } else { 'stale' })
            live_pids = @($live)
        })
    }
    return @($problems)
}

function Write-JsonAtomic {
    param([string]$Path, [object]$Value)
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temp = $Path + '.' + [guid]::NewGuid().ToString('N') + '.partial'
    $json = $Value | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText(
        $temp, $json + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Write-JsonLineRetry {
    param([string]$Path, [object]$Value)
    $line = ($Value | ConvertTo-Json -Compress -Depth 10) +
        [Environment]::NewLine
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($line)
    for ($attempt = 1; $attempt -le 6; $attempt++) {
        try {
            $stream = [IO.FileStream]::new(
                $Path,
                [IO.FileMode]::Append,
                [IO.FileAccess]::Write,
                [IO.FileShare]::ReadWrite
            )
            try {
                $stream.Write($bytes, 0, $bytes.Length)
                $stream.Flush($true)
            } finally {
                $stream.Dispose()
            }
            return $true
        } catch [IO.IOException] {
            Start-Sleep -Milliseconds (100 * $attempt)
        }
    }
    Write-Warning 'heartbeat append를 건너뜀; MFA 계산은 계속함.'
    return $false
}

function Enable-SleepGuard {
    if (-not ('MfaR3SleepGuard' -as [type])) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MfaR3SleepGuard {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
    }
    $continuousSystemRequired = [convert]::ToUInt32('80000001', 16)
    $result = [MfaR3SleepGuard]::SetThreadExecutionState(
        $continuousSystemRequired
    )
    if ($result -eq 0) { throw 'Windows sleep guard 활성화 실패' }
}

function Disable-SleepGuard {
    if ('MfaR3SleepGuard' -as [type]) {
        $continuous = [convert]::ToUInt32('80000000', 16)
        [void][MfaR3SleepGuard]::SetThreadExecutionState($continuous)
    }
}

function Get-MfaRuntimeState {
    param(
        [string]$MfaExecutable,
        [string]$PythonExecutable
    )
    $mfaExists = Test-Path -LiteralPath $MfaExecutable -PathType Leaf
    $pythonExists = Test-Path -LiteralPath $PythonExecutable -PathType Leaf
    $envRoot = Split-Path -Parent (Split-Path -Parent $MfaExecutable)
    $pathEntries = [Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
        $envRoot,
        (Join-Path $envRoot 'Library\mingw-w64\bin'),
        (Join-Path $envRoot 'Library\usr\bin'),
        (Join-Path $envRoot 'Library\bin'),
        (Join-Path $envRoot 'Scripts'),
        (Join-Path $envRoot 'bin')
    )) {
        if ((Test-Path -LiteralPath $candidate -PathType Container) -and
            -not $pathEntries.Contains($candidate)) {
            $pathEntries.Add($candidate)
        }
    }
    $priorPath = [string]$env:Path
    $pathParts = [Collections.Generic.List[string]]::new()
    foreach ($entry in $pathEntries) { $pathParts.Add($entry) }
    if (-not [string]::IsNullOrWhiteSpace($priorPath)) {
        $pathParts.Add($priorPath)
    }
    $runtimePath = [string]::Join(';', $pathParts.ToArray())
    $fstcompilePath = Join-Path $envRoot 'Library\bin\fstcompile.exe'
    $resolvedFstcompile = ''
    $thirdPartyExit = -1
    $thirdPartyOutput = [Collections.Generic.List[string]]::new()
    if ($mfaExists -and $pythonExists -and
        (Test-Path -LiteralPath $fstcompilePath -PathType Leaf)) {
        try {
            $env:Path = $runtimePath
            $resolved = Get-Command 'fstcompile.exe' -CommandType Application `
                -ErrorAction SilentlyContinue
            if ($null -ne $resolved) {
                $resolvedFstcompile = [string]$resolved.Source
            }
            foreach ($line in @(
                & $PythonExecutable -c (
                    'from montreal_forced_aligner.utils import ' +
                    'check_third_party; check_third_party()'
                ) 2>&1
            )) {
                $thirdPartyOutput.Add([string]$line)
            }
            $thirdPartyExit = $LASTEXITCODE
        } catch {
            $thirdPartyOutput.Add([string]$_.Exception.Message)
        } finally {
            $env:Path = $priorPath
        }
    }
    $ready = [bool](
        $mfaExists -and $pythonExists -and
        (Test-Path -LiteralPath $fstcompilePath -PathType Leaf) -and
        -not [string]::IsNullOrWhiteSpace($resolvedFstcompile) -and
        $thirdPartyExit -eq 0
    )
    return [pscustomobject]@{
        ready = $ready
        env_root = $envRoot
        mfa_executable_exists = $mfaExists
        python_executable_exists = $pythonExists
        fstcompile_path = $fstcompilePath
        fstcompile_resolved = $resolvedFstcompile
        third_party_exit = $thirdPartyExit
        third_party_output = @($thirdPartyOutput)
        path_entries = @($pathEntries)
        path_value = $runtimePath
    }
}

function Invoke-RepositoryPreflightTests {
    param([string]$ReceiptPath)
    $ps51 = Join-Path $env:SystemRoot (
        'System32\WindowsPowerShell\v1.0\powershell.exe'
    )
    $safetyPath = Join-Path $projectRoot 'tests\test_powershell_safety.ps1'
    $runtimePath = Join-Path $projectRoot (
        'tests\test_powershell_runtime_compat.ps1'
    )
    $safetyPassed = $false
    $runtimePassed = $false
    $pythonPassed = $false
    $started = (Get-Date).ToString('o')
    Push-Location $projectRoot
    try {
        & $ps51 -NoProfile -ExecutionPolicy Bypass -File $safetyPath |
            Out-Host
        $safetyPassed = ($LASTEXITCODE -eq 0)
        & $ps51 -NoProfile -ExecutionPolicy Bypass -File $runtimePath |
            Out-Host
        $runtimePassed = ($LASTEXITCODE -eq 0)
        & $python -m unittest discover -s (Join-Path $projectRoot 'tests') `
            -p 'test_*.py' | Out-Host
        $pythonPassed = ($LASTEXITCODE -eq 0)
    } finally {
        Pop-Location
    }
    $receipt = [ordered]@{
        schema_version = 'mfa_r3_repository_test_receipt.v1'
        status = $(
            if ($safetyPassed -and $runtimePassed -and $pythonPassed) {
                'passed'
            } else { 'failed' }
        )
        recorded_at = (Get-Date).ToString('o')
        started_at = $started
        release_id = $releaseId
        year = $Year
        powershell_safety_passed = $safetyPassed
        powershell_runtime_compat_passed = $runtimePassed
        python_full_suite_passed = $pythonPassed
    }
    Write-JsonAtomic -Path $ReceiptPath -Value $receipt
    return [pscustomobject]$receipt
}

$globalLockRoot = 'D:\mfa_eojeol\locks'
$r3Lock = Join-Path $releaseRoot 'locks\mfa_r3_year.lock'
$lockPaths = @(
    (Join-Path $globalLockRoot 'pre_mfa_bulk.lock'),
    (Join-Path $globalLockRoot 'mfa_year_queue.lock'),
    $r3Lock
)
$repositoryTestReceipt = Join-Path $preflightParent (
    'REPOSITORY_TESTS_{0}_{1}.json' -f $releaseId, $Year
)
$mfaRuntime = Get-MfaRuntimeState `
    -MfaExecutable $mfa `
    -PythonExecutable $python
$repositoryTests = Invoke-RepositoryPreflightTests `
    -ReceiptPath $repositoryTestReceipt
$lockProblems = @(Get-LockProblems -Paths $lockPaths)
$driveLabel = Get-DataDriveLabel
$freeGiB = [math]::Round(
    ([IO.DriveInfo]::new('D:\')).AvailableFreeSpace / 1GB, 3
)

$preflightArgs = @(
    (Join-Path $PSScriptRoot 'python\preflight_mfa_r3_year_safe_body.py'),
    '--year', $Year,
    '--policy', $policyPath,
    '--alignment-contract', $alignmentContract,
    '--alignment-audit', $alignmentAudit,
    '--research-database-audit', $researchDatabaseAudit,
    '--release-gate', $gatePath,
    '--observed-drive-label', $driveLabel,
    '--observed-free-gib', [string]$freeGiB,
    '--lock-problem-count', [string]$lockProblems.Count,
    '--mfa-runtime-ready', $(
        if ($mfaRuntime.ready) { 'true' }
        else { 'false' }
    ),
    '--powershell-safety-passed', $(
        if ($repositoryTests.powershell_safety_passed) { 'true' }
        else { 'false' }
    ),
    '--powershell-runtime-compat-passed', $(
        if ($repositoryTests.powershell_runtime_compat_passed) { 'true' }
        else { 'false' }
    ),
    '--python-suite-passed', $(
        if ($repositoryTests.python_full_suite_passed) { 'true' }
        else { 'false' }
    ),
    '--output', $PreflightReport
)
& $python @preflightArgs
$preflightExit = $LASTEXITCODE
if ($PreflightOnly) {
    if ($preflightExit -eq 0) {
        Write-Host "[GO] r3 $Year preflight: $PreflightReport" -ForegroundColor Green
    } else {
        Write-Host "[NO-GO] r3 $Year preflight: $PreflightReport" -ForegroundColor Yellow
        if ($lockProblems.Count -gt 0) {
            $lockProblems | Format-Table path,status,live_pids -AutoSize
        }
    }
    exit $preflightExit
}
if ($preflightExit -ne 0) {
    throw "r3 $Year preflight NO-GO; MFA를 시작하지 않음: $PreflightReport"
}
if (-not $mfaRuntime.ready) {
    throw (
        "MFA runtime dependency 검사 실패; 코퍼스 materialization 전에 중단: " +
        ($mfaRuntime | Select-Object -Property * -ExcludeProperty path_value |
            ConvertTo-Json -Compress -Depth 8)
    )
}

$alignment = Get-Content -LiteralPath $alignmentContract -Raw -Encoding UTF8 |
    ConvertFrom-Json
$alignmentId = [string]$alignment.alignment_contract_id
$dictionary = [string]$alignment.models.dictionary.path
$acoustic = [string]$alignment.models.acoustic.path
$corpusYear = Join-Path $releaseRoot "corpus\$Year"
$contractRoot = Join-Path $releaseRoot 'contracts'
$tempRoot = Join-Path $releaseRoot 'temp'
$tempYear = Join-Path $tempRoot $Year
$mfaOutputRoot = Join-Path $releaseRoot 'mfa_output'
$mfaOutputYear = Join-Path $mfaOutputRoot $Year
$logRoot = Join-Path $releaseRoot 'logs'
$markerRoot = Join-Path $releaseRoot 'markers'
$tempContractPath = Join-Path $contractRoot "TEMP_CONTRACT_$Year.json"
$doneMarker = Join-Path $markerRoot "ALIGN_DONE_$Year.json"
$runId = '{0}_{1}' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PID
$stdoutLog = Join-Path $logRoot "mfa_${Year}_${runId}_stdout.log"
$stderrLog = Join-Path $logRoot "mfa_${Year}_${runId}_stderr.log"
$heartbeat = Join-Path $logRoot "mfa_${Year}_${runId}_heartbeat.jsonl"

New-Item -ItemType Directory -Force -Path (
    Split-Path -Parent $r3Lock
) | Out-Null
$lockStream = $null
try {
    $lockStream = [IO.File]::Open(
        $r3Lock, [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write, [IO.FileShare]::Read
    )
    $lockRecord = [ordered]@{
        schema_version = 'mfa_r3_year_lock.v1'
        status = 'owned'
        owner_pid = $PID
        child_pid = $null
        year = $Year
        release_id = $releaseId
        alignment_contract_id = $alignmentId
        started_at = [DateTimeOffset]::Now.ToString('o')
    }
    $lockBytes = [Text.UTF8Encoding]::new($false).GetBytes(
        ($lockRecord | ConvertTo-Json -Depth 8) + [Environment]::NewLine
    )
    $lockStream.Write($lockBytes, 0, $lockBytes.Length)
    $lockStream.Flush($true)
    $lockStream.Dispose()
    $lockStream = $null

    Enable-SleepGuard
    New-Item -ItemType Directory -Force -Path @(
        $contractRoot, $logRoot, $markerRoot, $mfaOutputRoot, $tempRoot
    ) | Out-Null

    & $python (Join-Path $PSScriptRoot 'python\materialize_mfa_r3_safe_body_corpus.py') `
        --year $Year `
        --alignment-contract $alignmentContract `
        --output-root $corpusYear `
        --state-root $contractRoot
    if ($LASTEXITCODE -ne 0) {
        throw "r3 $Year safe-body corpus materialization 실패"
    }

    $resume = Test-Path -LiteralPath $tempYear
    if ($resume) {
        if (-not (Test-Path -LiteralPath $tempContractPath)) {
            throw "기존 r3 temp에 TEMP_CONTRACT가 없음; 자동 clean 금지: $tempYear"
        }
        $tempContract = Get-Content -LiteralPath $tempContractPath -Raw `
            -Encoding UTF8 | ConvertFrom-Json
        if (
            [string]$tempContract.alignment_contract_id -ne $alignmentId -or
            [string]$tempContract.year -ne $Year
        ) {
            throw "기존 r3 temp 계약 불일치; 삭제·재사용 금지: $tempYear"
        }
    } else {
        Write-JsonAtomic -Path $tempContractPath -Value ([ordered]@{
            schema_version = 'mfa_r3_temp_contract.v1'
            status = 'clean_start_pending_or_running'
            year = $Year
            release_id = $releaseId
            alignment_contract_id = $alignmentId
            temp_year = $tempYear
            created_at = [DateTimeOffset]::Now.ToString('o')
        })
    }
    if ((Test-Path -LiteralPath $doneMarker) -and -not $resume) {
        throw "완료 marker가 있지만 같은 temp checkpoint가 없음: $doneMarker"
    }
    if (Test-Path -LiteralPath $doneMarker) {
        $done = Get-Content -LiteralPath $doneMarker -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if (
            [string]$done.alignment_contract_id -eq $alignmentId -and
            [string]$done.status -eq 'passed'
        ) {
            Write-Host "[OK] r3 $Year alignment already complete: $doneMarker"
            exit 0
        }
        throw "기존 r3 완료 marker 계약 불일치: $doneMarker"
    }

    $arguments = @(
        'align', $corpusYear, $dictionary, $acoustic, $mfaOutputYear,
        '--num_jobs', [string]$NumJobs,
        '--no_tokenization',
        '--temporary_directory', $tempRoot,
        '--output_format', 'long_textgrid'
    )
    if (-not $resume) { $arguments += '--clean' }
    $priorRuntimePath = [string]$env:Path
    $priorSkipExport = $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT
    $env:Path = [string]$mfaRuntime.path_value
    $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT = '1'
    try {
        $process = Start-Process -FilePath $mfa -ArgumentList $arguments `
            -NoNewWindow -PassThru `
            -RedirectStandardOutput $stdoutLog `
            -RedirectStandardError $stderrLog
    } finally {
        $env:Path = $priorRuntimePath
        if ($null -eq $priorSkipExport) {
            Remove-Item Env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT `
                -ErrorAction SilentlyContinue
        } else {
            $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT = $priorSkipExport
        }
    }
    $null = $process.Handle
    $lockRecord.child_pid = $process.Id
    Write-JsonAtomic -Path $r3Lock -Value $lockRecord
    while (-not $process.HasExited) {
        [void](Write-JsonLineRetry -Path $heartbeat -Value ([ordered]@{
            observed_at = [DateTimeOffset]::Now.ToString('o')
            year = $Year
            release_id = $releaseId
            alignment_contract_id = $alignmentId
            wrapper_pid = $PID
            child_pid = $process.Id
            child_alive = $true
            temp_year_exists = (Test-Path -LiteralPath $tempYear)
            stdout_bytes = $(
                if (Test-Path $stdoutLog) {
                    (Get-Item $stdoutLog).Length
                } else { 0 }
            )
            stderr_bytes = $(
                if (Test-Path $stderrLog) {
                    (Get-Item $stderrLog).Length
                } else { 0 }
            )
        }))
        Write-Host (
            '[{0}] r3 {1} MFA running; pid={2}; temp={3}' -f
            (Get-Date -Format 'HH:mm:ss'), $Year, $process.Id,
            (Test-Path -LiteralPath $tempYear)
        )
        Start-Sleep -Seconds $heartbeatSeconds
        $process.Refresh()
    }
    if ($process.ExitCode -ne 0) {
        throw (
            "r3 $Year MFA 실패(exit=$($process.ExitCode)); temp·DB 보존: " +
            "$stderrLog"
        )
    }
    $databaseCandidates = @(
        Get-ChildItem -LiteralPath $tempYear -Filter "$Year.db" -File `
            -Recurse -ErrorAction SilentlyContinue
    )
    if ($databaseCandidates.Count -ne 1 -or $databaseCandidates[0].Length -le 0) {
        throw "r3 $Year MFA exit 0이나 유일한 DB가 없음; temp 보존: $tempYear"
    }
    $database = $databaseCandidates[0]
    $databaseSha = (Get-FileHash -LiteralPath $database.FullName `
        -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-JsonAtomic -Path $doneMarker -Value ([ordered]@{
        schema_version = 'mfa_r3_alignment_done.v1'
        status = 'passed'
        completed_at = [DateTimeOffset]::Now.ToString('o')
        year = $Year
        release_id = $releaseId
        alignment_contract_id = $alignmentId
        r3_full_realign = $true
        expected_mfa_input = [int]$alignment.year_input.expected_mfa_input
        source_db = [ordered]@{
            path = $database.FullName
            bytes = $database.Length
            sha256 = $databaseSha
        }
        logs = [ordered]@{
            stdout = $stdoutLog
            stderr = $stderrLog
            heartbeat = $heartbeat
        }
        textgrid_materialized = $false
        temp_deleted = $false
        database_deleted = $false
    })
    Write-Host "[OK] r3 $Year MFA DB complete: $doneMarker" -ForegroundColor Green
} finally {
    if ($null -ne $lockStream) { $lockStream.Dispose() }
    Disable-SleepGuard
    if (Test-Path -LiteralPath $r3Lock) {
        try {
            $owned = Get-Content -LiteralPath $r3Lock -Raw -Encoding UTF8 |
                ConvertFrom-Json
            if ([int]$owned.owner_pid -eq $PID) {
                Remove-Item -LiteralPath $r3Lock -Force
            }
        } catch {
            Write-Warning "r3 lock 소유권 확인/해제 실패: $r3Lock"
        }
    }
}
