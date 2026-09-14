#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [switch]$Execute,
    [switch]$Resume,
    [switch]$Status,
    [switch]$RequestStop
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$actionCount = [int]$PreflightOnly.IsPresent + [int]$Execute.IsPresent + [int]$Status.IsPresent + [int]$RequestStop.IsPresent
if ($actionCount -ne 1) { throw 'Specify exactly one of PreflightOnly, Execute, Status or RequestStop.' }
if ($Resume -and -not $Execute) { throw 'Resume requires Execute.' }
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$paths = Get-Content -LiteralPath (Join-Path $projectRoot 'config\paths.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$taskPython = [Environment]::ExpandEnvironmentVariables([string]$paths.pipeline_python)
$runner = Join-Path $projectRoot 'scripts\python\run_homonym_context_pilot.py'
if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) { throw 'Configured pipeline Python is unavailable.' }
$taskArguments = [Collections.Generic.List[string]]::new()
$taskArguments.Add('-u')
$taskArguments.Add($runner)
if ($PreflightOnly) { $taskArguments.Add('--preflight-only') }
if ($Execute) { $taskArguments.Add('--execute') }
if ($Resume) { $taskArguments.Add('--resume') }
if ($Status) { $taskArguments.Add('--status') }
if ($RequestStop) { $taskArguments.Add('--request-stop') }
$previousEncoding = $env:PYTHONIOENCODING
$env:PYTHONIOENCODING = 'utf-8'
try {
    & $taskPython $taskArguments.ToArray()
    $taskExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONIOENCODING = $previousEncoding
}
exit $taskExitCode
