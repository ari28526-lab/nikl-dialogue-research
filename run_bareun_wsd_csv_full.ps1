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

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "고정 Bareun WSD Python이 없습니다: $python"
}
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "전수 runner가 없습니다: $runner"
}

$arguments = New-Object 'System.Collections.Generic.List[string]'
[void]$arguments.Add($runner)
[void]$arguments.Add('--batch-size')
[void]$arguments.Add('40')

if ($Resume) {
    [void]$arguments.Add('--resume')
}

$typeName = 'BareunWsdExecutionState'
if (-not ($typeName -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class BareunWsdExecutionState {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
}

# Windows PowerShell 5.1은 0x80000000을 음수 Int32로 먼저 해석한다.
# 16진수 문자열을 UInt32로 직접 변환해 overflow를 피한다.
$ES_CONTINUOUS = [Convert]::ToUInt32('80000000', 16)
$ES_SYSTEM_REQUIRED = [Convert]::ToUInt32('00000001', 16)
$ES_AWAYMODE_REQUIRED = [Convert]::ToUInt32('00000040', 16)
$keepAwake = [Convert]::ToUInt32('80000041', 16)
if ($keepAwake -ne ($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_AWAYMODE_REQUIRED)) {
    throw '절전 억제 flag 계산이 일치하지 않습니다.'
}

if ($PreflightOnly) {
    Write-Host 'Bareun v3.1.0+ 형태소+WSD CSV 전수 preflight만 실행합니다.'
    & $python $arguments.ToArray()
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($ApprovedBy)) {
    throw '-Execute에는 -ApprovedBy가 필요합니다.'
}
$expectedToken = 'BAREUN_WSD_CSV_FULL_20260828'
if ($ApprovalToken -cne $expectedToken) {
    throw "정확한 -ApprovalToken $expectedToken 이 필요합니다."
}

[void]$arguments.Add('--execute')
[void]$arguments.Add('--approved-by')
[void]$arguments.Add($ApprovedBy.Trim())
[void]$arguments.Add('--approval-token')
[void]$arguments.Add($ApprovalToken)

Write-Host '전수 실행을 시작합니다. 원 CSV·TextGrid·WAV는 읽기 전용입니다.'
Write-Host '상태 확인: .\show_bareun_wsd_csv_status.ps1'
[void][BareunWsdExecutionState]::SetThreadExecutionState($keepAwake)
try {
    & $python $arguments.ToArray()
    $exitCode = $LASTEXITCODE
} finally {
    [void][BareunWsdExecutionState]::SetThreadExecutionState($ES_CONTINUOUS)
}
exit $exitCode
