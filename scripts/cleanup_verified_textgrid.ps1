#Requires -Version 5.1
[CmdletBinding(DefaultParameterSetName = 'Preflight')]
param(
    [Parameter(ParameterSetName = 'Preflight')][switch]$PreflightOnly,
    [Parameter(Mandatory = $true, ParameterSetName = 'Execute')][switch]$Execute,
    [Parameter(Mandatory = $true, ParameterSetName = 'Status')][switch]$Status,
    [Parameter(Mandatory = $true, ParameterSetName = 'Stop')][switch]$Stop
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (Join-Path $root 'config\paths.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$runtime = [Environment]::ExpandEnvironmentVariables([string]$config.pipeline_python)
if (-not (Test-Path -LiteralPath $runtime -PathType Leaf)) { throw 'Pipeline Python is unavailable.' }
$mode = '--preflight'
if ($Execute) { $mode = '--execute' }
if ($Status) { $mode = '--status' }
if ($Stop) { $mode = '--stop' }
$env:PYTHONIOENCODING = 'utf-8'
& $runtime (Join-Path $root 'scripts\python\cleanup_verified_textgrid.py') $mode
if ($LASTEXITCODE -ne 0) { throw "Cleanup runner failed with exit code $LASTEXITCODE. Existing results are preserved." }
