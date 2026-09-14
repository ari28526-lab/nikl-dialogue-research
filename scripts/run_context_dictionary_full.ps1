#Requires -Version 5.1
<# Offline full-corpus application. Repeat -Execute -Resume after interruption. #>
[CmdletBinding(DefaultParameterSetName = 'Preflight')]
param(
    [Parameter(ParameterSetName = 'Run', Mandatory = $true)][switch]$Execute,
    [Parameter(ParameterSetName = 'Run')][switch]$Resume,
    [Parameter(ParameterSetName = 'Preflight')][switch]$PreflightOnly,
    [Parameter(ParameterSetName = 'Status', Mandatory = $true)][switch]$Status,
    [Parameter(ParameterSetName = 'Stop', Mandatory = $true)][switch]$Stop
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = Split-Path -Parent $PSScriptRoot
$paths = Get-Content -LiteralPath (Join-Path $projectRoot 'config\paths.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$pipelinePython = [Environment]::ExpandEnvironmentVariables($paths.pipeline_python)
if (-not (Test-Path -LiteralPath $pipelinePython -PathType Leaf)) {
    throw 'config/paths.json의 pipeline_python을 확인하세요.'
}
$runner = Join-Path $PSScriptRoot 'python\apply_context_dictionary_full.py'
$arguments = [Collections.Generic.List[string]]::new()
$arguments.Add('-B')
$arguments.Add($runner)
if ($Execute) {
    $arguments.Add('--execute')
    if ($Resume) { $arguments.Add('--resume') }
} elseif ($Status) { $arguments.Add('--status')
} elseif ($Stop) { $arguments.Add('--stop')
} else { $arguments.Add('--preflight-only') }
$previousEncoding = $env:PYTHONIOENCODING
$env:PYTHONIOENCODING = 'utf-8'
$keepAwake = $false
$runnerExit = 1
try {
    if ($Execute) {
        if (-not ('ContextDictionaryPower' -as [type])) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ContextDictionaryPower {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint flags);
}
'@
        }
        $powerState = [ContextDictionaryPower]::SetThreadExecutionState([uint32]2147483649)
        $keepAwake = ($powerState -ne 0)
        if (-not $keepAwake) { Write-Warning '자동 절전 방지 설정에 실패했습니다. Windows 전원 설정을 확인하세요.' }
        Write-Host '전체 17,156 JSON의 기존 바른 결과에 문맥사전을 적용합니다. 25발화마다 저장합니다.'
        Write-Host '중지: 다른 PowerShell에서 이 스크립트에 -Stop. 재개: -Execute -Resume.'
    }
    & $pipelinePython @arguments
    $runnerExit = $LASTEXITCODE
} finally {
    if ($keepAwake) { [void][ContextDictionaryPower]::SetThreadExecutionState([uint32]2147483648) }
    $env:PYTHONIOENCODING = $previousEncoding
}
if ($runnerExit -eq 130) { Write-Host '중단 지점이 보존되었습니다. -Execute -Resume으로 이어가세요.' }
elseif ($runnerExit -ne 0) { throw "문맥사전 실행기가 종료되었습니다(exit=$runnerExit). 오류를 확인한 뒤 재개하세요." }
