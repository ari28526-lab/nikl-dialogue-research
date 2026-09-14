#Requires -Version 5.1
[CmdletBinding(DefaultParameterSetName='Status')]
param(
    [Parameter(Mandatory=$true,ParameterSetName='Execute')][switch]$Execute,
    [Parameter(Mandatory=$true,ParameterSetName='Preflight')][switch]$PreflightOnly,
    [Parameter(ParameterSetName='Status')][switch]$Status,
    [Parameter(Mandatory=$true,ParameterSetName='Stop')][switch]$Stop
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=Split-Path -Parent $PSScriptRoot
$paths=Get-Content -LiteralPath (Join-Path $root 'config\paths.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$runtime=[Environment]::ExpandEnvironmentVariables([string]$paths.pipeline_python)
$mode='--status'
if($PreflightOnly){$mode='--preflight'}
if($Execute){$mode='--execute'}
if($Stop){$mode='--stop'}
$env:PYTHONIOENCODING='utf-8'
& $runtime (Join-Path $root 'scripts\python\run_legacy_mfa_cleanup.py') $mode
if($LASTEXITCODE -ne 0){throw "Legacy MFA cleanup stopped with exit code $LASTEXITCODE; completed results are preserved."}
