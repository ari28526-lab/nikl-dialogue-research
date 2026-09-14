#Requires -Version 5.1
[CmdletBinding()]
param([switch]$PreflightOnly,[switch]$Execute)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ($PreflightOnly -and $Execute) { throw 'Choose PreflightOnly or Execute.' }
$projectRoot=Split-Path -Parent $PSScriptRoot
$paths=Get-Content -LiteralPath (Join-Path $projectRoot 'config/paths.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$pipelinePython=[Environment]::ExpandEnvironmentVariables($paths.pipeline_python)
$arguments=[Collections.Generic.List[string]]::new()
$arguments.Add((Join-Path $PSScriptRoot 'python/probe_wsd_list.py'))
if ($Execute) {
    $arguments.Add('--execute')
    $arguments.Add('--confirm-scope')
    $arguments.Add('list-8-contexts-465-eojeol')
}
$previousEncoding=$env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING='utf-8'
    & $pipelinePython @arguments
    if ($LASTEXITCODE -ne 0) { throw "List probe stopped (exit $LASTEXITCODE); preserved ledger requires review." }
}
finally { $env:PYTHONIOENCODING=$previousEncoding }
