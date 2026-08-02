[CmdletBinding()]
param(
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $projectRoot "config\paths.json"
$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 |
    ConvertFrom-Json

function Expand-ConfiguredPath {
    param([Parameter(Mandatory = $true)][string]$Value)

    $expanded = [Environment]::ExpandEnvironmentVariables($Value)
    return $expanded.Replace("/", "\")
}

function New-CheckResult {
    param(
        [string]$Label,
        [string]$Path,
        [string]$Status,
        [string]$Detail
    )

    return [pscustomobject]@{
        label = $Label
        path = $Path
        status = $Status
        detail = $Detail
    }
}

function Test-PythonExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$Arguments = @("--version")
    )

    try {
        $exists = Test-Path -LiteralPath $Path -PathType Leaf
    }
    catch [System.UnauthorizedAccessException] {
        return New-CheckResult $Label $Path "access_denied" (
            "The file may exist, but this process cannot inspect it. " +
            "Retry the read-only check with the required permission."
        )
    }

    if (-not $exists) {
        return New-CheckResult $Label $Path "missing" "File not found."
    }

    try {
        $output = & $Path @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        $detail = (($output | ForEach-Object { "$_".Trim() }) -join " | ").Trim()
        if ($exitCode -ne 0) {
            return New-CheckResult $Label $Path "failed" (
                "exit=$exitCode; $detail"
            )
        }
        return New-CheckResult $Label $Path "ok" $detail
    }
    catch [System.UnauthorizedAccessException] {
        return New-CheckResult $Label $Path "access_denied" (
            "The file exists, but execution is blocked for this process."
        )
    }
    catch {
        return New-CheckResult $Label $Path "failed" (
            "$($_.Exception.GetType().Name): $($_.Exception.Message)"
        )
    }
}

$globalPython = Join-Path $env:LOCALAPPDATA `
    "Programs\Python\Python313\python.exe"
$pyLauncher = Join-Path $env:LOCALAPPDATA `
    "Programs\Python\Launcher\py.exe"
$pipelinePython = Expand-ConfiguredPath $config.pipeline_python

$results = @(
    Test-PythonExecutable "global_python_313" $globalPython
    Test-PythonExecutable "py_launcher" $pyLauncher @("-0p")
    Test-PythonExecutable "pipeline_python" $pipelinePython
)

foreach ($commandName in @("python", "py")) {
    $command = Get-Command $commandName -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $command) {
        $results += New-CheckResult "path_$commandName" "" "missing" (
            "$commandName is not resolved from PATH in this process."
        )
    }
    else {
        $results += New-CheckResult "path_$commandName" $command.Source "ok" (
            "Resolved by Get-Command."
        )
    }
}

if ($Json) {
    $results | ConvertTo-Json -Depth 3
}
else {
    $results | Format-Table -AutoSize
}

$blocked = @($results | Where-Object { $_.status -eq "access_denied" })
$failed = @($results | Where-Object { $_.status -in @("missing", "failed") })

if ($failed.Count -gt 0) {
    exit 1
}
if ($blocked.Count -gt 0) {
    exit 2
}
exit 0
