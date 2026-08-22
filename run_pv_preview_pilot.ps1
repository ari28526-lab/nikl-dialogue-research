[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [switch]$Worker,
    [string]$OutputRoot = "C:\Users\ari30\research\2026_summer_research\outputs\pilots\pv_seven_phenomena_20260819",
    [string]$PythonPath = "C:\Users\ari30\miniforge3\envs\mfa\python.exe"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ProjectRoot = Split-Path -Parent $PSCommandPath
$PilotParent = Join-Path $ProjectRoot "outputs\pilots"
$ConfigPath = Join-Path $ProjectRoot "config\target_queries\pv_preview_boundary_20260819.json"
$InternalScript = Join-Path $ProjectRoot "scripts\python\scan_pv_morph_internal_lite.py"
$SampleScript = Join-Path $ProjectRoot "scripts\python\build_pv_preview_samples.py"
$ContextScript = Join-Path $ProjectRoot "scripts\python\build_pv_context_manifest.py"
$BundleScript = Join-Path $ProjectRoot "scripts\python\build_pv_review_bundle.py"
$AuditScript = Join-Path $ProjectRoot "scripts\python\audit_pv_preview.py"
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
$PartialRoot = $OutputRoot + ".partial"

function Assert-PathUnder {
    param([string]$Path, [string]$AllowedRoot)
    $ResolvedPath = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $ResolvedRoot = [IO.Path]::GetFullPath($AllowedRoot).TrimEnd('\')
    $Prefix = $ResolvedRoot + '\'
    if (-not $ResolvedPath.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "출력 경로는 $ResolvedRoot 아래여야 합니다: $ResolvedPath"
    }
}

function Assert-Prerequisites {
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw "파이프라인 Python을 찾지 못했습니다: $PythonPath"
    }
    $RequiredFiles = @(
        $ConfigPath,
        $InternalScript,
        $SampleScript,
        $ContextScript,
        $BundleScript,
        $AuditScript
    )
    foreach ($RequiredFile in $RequiredFiles) {
        if (-not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
            throw "필수 파일을 찾지 못했습니다: $RequiredFile"
        }
    }
    Assert-PathUnder -Path $OutputRoot -AllowedRoot $PilotParent
    $FirstBytes = [IO.File]::ReadAllBytes($PSCommandPath)
    if ($FirstBytes.Length -lt 3 -or $FirstBytes[0] -ne 0xEF -or $FirstBytes[1] -ne 0xBB -or $FirstBytes[2] -ne 0xBF) {
        throw "wrapper가 UTF-8 BOM이 아닙니다(EF BB BF 필요)."
    }
}

function Assert-NewOutput {
    if (Test-Path -LiteralPath $OutputRoot) {
        throw "기존 출력은 덮어쓰지 않습니다: $OutputRoot"
    }
    if (Test-Path -LiteralPath $PartialRoot) {
        throw "기존 partial은 조사할 수 있도록 보존합니다: $PartialRoot"
    }
}

function Invoke-PreflightStep {
    param([string]$ScriptPath)
    & $PythonPath $ScriptPath --config $ConfigPath --preflight-only
    if ($LASTEXITCODE -ne 0) {
        throw "preflight 실패(exit $LASTEXITCODE): $ScriptPath"
    }
}

function Write-RunLog {
    param([string]$Message)
    $LogDirectory = Join-Path $PartialRoot "logs"
    if (-not (Test-Path -LiteralPath $LogDirectory)) {
        New-Item -ItemType Directory -Path $LogDirectory | Out-Null
    }
    $Timestamp = [DateTimeOffset]::Now.ToString("o")
    Add-Content -LiteralPath (Join-Path $LogDirectory "runner.log") -Value ("{0}`t{1}" -f $Timestamp, $Message) -Encoding UTF8
}

function Invoke-LoggedPython {
    param(
        [string]$StepName,
        [string[]]$Arguments
    )
    $StepLog = Join-Path (Join-Path $PartialRoot "logs") ($StepName + ".log")
    Write-RunLog ("START " + $StepName)
    & $PythonPath @Arguments *> $StepLog
    $ExitCode = $LASTEXITCODE
    Write-RunLog ("END {0} exit={1}" -f $StepName, $ExitCode)
    if ($ExitCode -ne 0) {
        throw "단계 실패(exit $ExitCode): $StepName; 로그=$StepLog"
    }
}

function Write-AtomicUtf8Json {
    param([string]$Path, [object]$Value)
    if (Test-Path -LiteralPath $Path) {
        throw "기존 출력은 덮어쓰지 않습니다: $Path"
    }
    $Temporary = $Path + ".partial"
    if (Test-Path -LiteralPath $Temporary) {
        throw "기존 partial은 보존합니다: $Temporary"
    }
    $Json = $Value | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText($Temporary, $Json + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
    [IO.File]::Move($Temporary, $Path)
}

function Write-RootManifests {
    $AuditPath = Join-Path $PartialRoot "audit\PV_AUDIT.json"
    $Audit = Get-Content -LiteralPath $AuditPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $Audit.passed) {
        throw "독립 감사가 실패하여 최종 승격을 중단합니다: $AuditPath"
    }
    $RootManifestPath = Join-Path $PartialRoot "PV_MANIFEST.json"
    $RootManifest = [ordered]@{
        schema_version = "pv_preview_run_manifest.v1"
        status = "passed_listening_may_begin"
        recorded_at = [DateTimeOffset]::Now.ToString("o")
        output_root = $OutputRoot
        config_path = $ConfigPath
        config_sha256 = (Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256).Hash.ToLowerInvariant()
        audit_path = "audit/PV_AUDIT.json"
        audit_sha256 = (Get-FileHash -LiteralPath $AuditPath -Algorithm SHA256).Hash.ToLowerInvariant()
        physical_packages = [int]$Audit.counts.physical_packages
        logical_review_events = [int]$Audit.counts.logical_review_events
        listening_gate = "open"
        logs_sha_exclusion = "logs are operational diagnostics and can receive the final runner line before promotion"
        safety = [ordered]@{
            source_assets_modified = $false
            realization_judgement_performed = $false
            mfa_run = $false
            koina_run = $false
            wav2vec2_run = $false
            automatic_scan_cap_increase = $false
            annual_row_cap = 200000
        }
    }
    Write-AtomicUtf8Json -Path $RootManifestPath -Value $RootManifest

    $ShaManifestPath = Join-Path $PartialRoot "PV_SHA256_MANIFEST.csv"
    $ShaTemporary = $ShaManifestPath + ".partial"
    $HashRows = New-Object 'System.Collections.Generic.List[object]'
    $Files = @(Get-ChildItem -LiteralPath $PartialRoot -File -Recurse | Sort-Object FullName)
    foreach ($File in $Files) {
        $Relative = $File.FullName.Substring($PartialRoot.Length).TrimStart('\').Replace('\', '/')
        if ($Relative.StartsWith("logs/", [StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        if ($Relative -eq "PV_SHA256_MANIFEST.csv" -or $Relative -eq "PV_SHA256_MANIFEST.csv.partial") {
            continue
        }
        $HashRows.Add([pscustomobject][ordered]@{
            path = $Relative
            bytes = $File.Length
            sha256 = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        })
    }
    $HashRows | Export-Csv -LiteralPath $ShaTemporary -NoTypeInformation -Encoding UTF8
    [IO.File]::Move($ShaTemporary, $ShaManifestPath)
}

function Invoke-Worker {
    Assert-NewOutput
    New-Item -ItemType Directory -Path $PartialRoot | Out-Null
    try {
        Write-RunLog "PV-A worker 시작; 원자료는 읽기 전용이며 자동 실현 판정을 수행하지 않음"
        $SamplesRoot = Join-Path $PartialRoot "samples"
        $InternalRoot = Join-Path $SamplesRoot "internal"
        $ContextRoot = Join-Path $PartialRoot "context"
        $BundleRoot = Join-Path $PartialRoot "bundle"
        New-Item -ItemType Directory -Path $InternalRoot -Force | Out-Null

        Invoke-LoggedPython -StepName "01_internal_scan" -Arguments @(
            $InternalScript, "--config", $ConfigPath, "--output-dir", $InternalRoot
        )
        Invoke-LoggedPython -StepName "02_sample_build" -Arguments @(
            $SampleScript,
            "--config", $ConfigPath,
            "--internal-candidates", (Join-Path $InternalRoot "PV_INTERNAL_CANDIDATES.csv"),
            "--output-dir", $SamplesRoot
        )
        Invoke-LoggedPython -StepName "03_context_build" -Arguments @(
            $ContextScript,
            "--config", $ConfigPath,
            "--samples", (Join-Path $SamplesRoot "PV_SAMPLES.csv"),
            "--output-dir", $ContextRoot
        )
        Invoke-LoggedPython -StepName "04_bundle_build" -Arguments @(
            $BundleScript,
            "--config", $ConfigPath,
            "--samples", (Join-Path $SamplesRoot "PV_SAMPLES.csv"),
            "--events", (Join-Path $SamplesRoot "PV_REVIEW_EVENTS.csv"),
            "--context", (Join-Path $ContextRoot "PV_CONTEXT.csv"),
            "--output-dir", $BundleRoot
        )
        Invoke-LoggedPython -StepName "05_independent_audit" -Arguments @(
            $AuditScript,
            "--config", $ConfigPath,
            "--run-root", $PartialRoot,
            "--output-dir", (Join-Path $PartialRoot "audit")
        )
        Write-RootManifests
        Write-RunLog "PASS; atomic directory promotion 시작"
        [IO.Directory]::Move($PartialRoot, $OutputRoot)
    }
    catch {
        try {
            Write-RunLog ("FAIL " + $_.Exception.Message)
        }
        catch {
        }
        throw
    }
}

Assert-Prerequisites

if ($PreflightOnly) {
    if ($Worker) {
        throw "-PreflightOnly와 -Worker는 함께 사용할 수 없습니다."
    }
    Assert-NewOutput
    Invoke-PreflightStep -ScriptPath $InternalScript
    Invoke-PreflightStep -ScriptPath $SampleScript
    Write-Output "[PASS] preflight 완료: 후보 스캔·파일 생성·음성 처리 없음"
    Write-Output ("[INFO] 승인된 연간 row 상한=200000; 출력 예정={0}" -f $OutputRoot)
    exit 0
}

if ($Worker) {
    Invoke-Worker
    exit 0
}

Assert-NewOutput
$PowerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
if (-not (Test-Path -LiteralPath $PowerShellExe -PathType Leaf)) {
    throw "Windows PowerShell 5.1 실행 파일을 찾지 못했습니다: $PowerShellExe"
}
$WorkerArguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"{0}"' -f $PSCommandPath),
    "-Worker",
    "-OutputRoot", ('"{0}"' -f $OutputRoot),
    "-PythonPath", ('"{0}"' -f $PythonPath)
)
$Process = Start-Process -FilePath $PowerShellExe -ArgumentList $WorkerArguments -WindowStyle Hidden -PassThru
Write-Output ("[STARTED] detached PV-A worker PID={0}" -f $Process.Id)
Write-Output ("[STATUS] 진행 중: {0}\logs\runner.log" -f $PartialRoot)
Write-Output ("[STATUS] 완료: {0}\PV_MANIFEST.json 및 audit\PV_AUDIT.json" -f $OutputRoot)
