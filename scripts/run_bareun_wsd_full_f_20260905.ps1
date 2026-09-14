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
    throw '-PreflightOnly 또는 -Execute를 명시하세요.'
}
if ($Resume -and -not $Execute) {
    throw '-Resume은 -Execute와 함께 사용해야 합니다.'
}

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $projectRoot `
    'work\bareun_wsd_full_20260828\.venv\Scripts\python.exe'
$runner = Join-Path $projectRoot `
    'scripts\python\run_bareun_wsd_csv_full.py'
$auditor = Join-Path $projectRoot `
    'scripts\python\audit_bareun_wsd_csv_full.py'
$config = Join-Path $projectRoot `
    'config\bareun_wsd_full_f_20260905.json'
$auditReport = Join-Path $projectRoot `
    'outputs\reports\AUDIT_bareun_wsd_full_f_20260905.json'

foreach ($required in @($python, $runner, $auditor, $config)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 파일이 없습니다: $required"
    }
}

$dVolume = Get-Volume -DriveLetter D -ErrorAction Stop
$fVolume = Get-Volume -DriveLetter F -ErrorAction Stop
if ($dVolume.FileSystemLabel -cne 'DATA_SSD') {
    throw "D 볼륨 불일치: $($dVolume.FileSystemLabel)"
}
if ($fVolume.FileSystemLabel -cne 'DERIVED_WORK_2TB') {
    throw "F 볼륨 불일치: $($fVolume.FileSystemLabel)"
}
if ($dVolume.FileSystem -cne 'NTFS' -or $fVolume.FileSystem -cne 'NTFS') {
    throw 'D와 F는 NTFS여야 합니다.'
}
$fFreeGiB = $fVolume.SizeRemaining / 1GB
$cFreeGiB = (New-Object IO.DriveInfo('C')).AvailableFreeSpace / 1GB
if ($fFreeGiB -lt 100) { throw 'F 여유 공간이 100 GiB 미만입니다.' }
if ($cFreeGiB -lt 10) { throw 'C 여유 공간이 10 GiB 미만입니다.' }

$arguments = [Collections.Generic.List[string]]::new()
$arguments.Add($runner)
$arguments.Add('--config')
$arguments.Add($config)
$arguments.Add('--batch-size')
$arguments.Add('40')
if ($Resume) { $arguments.Add('--resume') }

if ($PreflightOnly) {
    & $python $arguments.ToArray()
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($ApprovedBy)) {
    throw '-Execute에는 -ApprovedBy가 필요합니다.'
}
$expectedToken = 'BAREUN_WSD_FULL_F_20260905'
if ($ApprovalToken -cne $expectedToken) {
    throw "정확한 -ApprovalToken $expectedToken 이 필요합니다."
}
$arguments.Add('--execute')
$arguments.Add('--approved-by')
$arguments.Add($ApprovedBy.Trim())
$arguments.Add('--approval-token')
$arguments.Add($ApprovalToken)

$typeName = 'BareunWsdFExecutionState'
if (-not ($typeName -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class BareunWsdFExecutionState {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
}
$keepAwake = [Convert]::ToUInt32('80000041', 16)
$continuous = [Convert]::ToUInt32('80000000', 16)

Write-Host '전체 5,103,356발화 WSD를 F에 시작합니다.'
Write-Host '상태 확인: .\scripts\show_bareun_wsd_full_f_20260905.ps1'
[void][BareunWsdFExecutionState]::SetThreadExecutionState($keepAwake)
try {
    & $python $arguments.ToArray()
    $runnerExit = $LASTEXITCODE
    if ($runnerExit -ne 0) { exit $runnerExit }
    & $python $auditor --config $config --report $auditReport
    exit $LASTEXITCODE
} finally {
    [void][BareunWsdFExecutionState]::SetThreadExecutionState($continuous)
}
