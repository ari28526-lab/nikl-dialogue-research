#Requires -Version 5.1
[CmdletBinding(DefaultParameterSetName = 'Preflight')]
param(
    [Parameter(ParameterSetName = 'Run', Mandatory = $true)][switch]$Execute,
    [Parameter(ParameterSetName = 'Run')][switch]$Resume,
    [Parameter(ParameterSetName = 'Preflight')][switch]$PreflightOnly,
    [Parameter(ParameterSetName = 'Status', Mandatory = $true)][switch]$Status
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = Split-Path -Parent $PSScriptRoot
$paths = Get-Content -LiteralPath (Join-Path $projectRoot 'config\paths.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$pipelinePython = [Environment]::ExpandEnvironmentVariables($paths.pipeline_python)
$taskArgs = [Collections.Generic.List[string]]::new()
$taskArgs.Add('-B')
$taskArgs.Add((Join-Path $PSScriptRoot 'python\prepare_wsd_residual.py'))
if ($Execute) { $taskArgs.Add('--build'); if ($Resume) { $taskArgs.Add('--resume') }
} elseif ($Status) { $taskArgs.Add('--status')
} else { $taskArgs.Add('--preflight-only') }
$previousEncoding = $env:PYTHONIOENCODING
$env:PYTHONIOENCODING = 'utf-8'
try {
    & $pipelinePython @taskArgs
    $taskExit = $LASTEXITCODE
} finally { $env:PYTHONIOENCODING = $previousEncoding }
if ($taskExit -eq 130) { Write-Host '중단 지점을 저장했습니다. -Execute -Resume으로 재개할 수 있습니다.' }
elseif ($taskExit -ne 0) { throw "WSD 입력 준비 오류(exit=$taskExit). 오류 원인을 확인하세요." }
