#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [switch]$Execute,
    [switch]$Resume,
    [string]$ApprovedBy = '',
    [string]$ApprovalToken = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($PreflightOnly -and $Execute) {
    throw '-PreflightOnly와 -Execute는 함께 사용할 수 없습니다.'
}
if (-not $PreflightOnly -and -not $Execute) {
    throw '기본 동작은 없습니다. -PreflightOnly 또는 -Execute를 명시하세요.'
}
if ($Resume -and -not $Execute) {
    throw '-Resume은 -Execute와 함께 사용해야 합니다.'
}

$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$python = Join-Path $projectRoot `
    'work\bareun_wsd_full_20260828\.venv\Scripts\python.exe'
$runner = Join-Path $projectRoot `
    'scripts\python\run_bareun_wsd_csv_full.py'
$config = Join-Path $projectRoot 'config\bareun_morph_reanalysis_v1.json'

foreach ($required in @($python, $runner, $config)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 실행 파일이 없습니다: $required"
    }
}

$arguments = New-Object 'System.Collections.Generic.List[string]'
[void]$arguments.Add($runner)
[void]$arguments.Add('--config')
[void]$arguments.Add($config)
[void]$arguments.Add('--batch-size')
[void]$arguments.Add('40')

if ($Resume) {
    [void]$arguments.Add('--resume')
}

$typeName = 'BareunMorphExecutionState'
if (-not ($typeName -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class BareunMorphExecutionState {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
}

$ES_CONTINUOUS = [Convert]::ToUInt32('80000000', 16)
$keepAwake = [Convert]::ToUInt32('80000041', 16)

if ($PreflightOnly) {
    Write-Host 'Bareun v3.1.0+ 형태소-only CSV 전수 preflight만 실행합니다.'
    & $python $arguments.ToArray()
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($ApprovedBy)) {
    throw '-Execute에는 -ApprovedBy가 필요합니다.'
}
$expectedToken = 'BAREUN_MORPH_CSV_FULL_20260828'
if ($ApprovalToken -cne $expectedToken) {
    throw "정확한 -ApprovalToken $expectedToken 이 필요합니다."
}

[void]$arguments.Add('--execute')
[void]$arguments.Add('--approved-by')
[void]$arguments.Add($ApprovedBy.Trim())
[void]$arguments.Add('--approval-token')
[void]$arguments.Add($ApprovalToken)

Write-Host '새 형태소 전수 분석을 시작합니다. 기존 tagged·TextGrid·WAV는 읽거나 수정하지 않습니다.'
Write-Host '상태 확인: .\show_bareun_morph_csv_status.ps1'
[void][BareunMorphExecutionState]::SetThreadExecutionState($keepAwake)
try {
    & $python $arguments.ToArray()
    $exitCode = $LASTEXITCODE
} finally {
    [void][BareunMorphExecutionState]::SetThreadExecutionState($ES_CONTINUOUS)
}
exit $exitCode
