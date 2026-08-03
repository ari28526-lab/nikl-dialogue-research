#Requires -Version 5.1
<# 한 연도의 morph_search.v3 7표와 동결 source contract를 MFA 전에 완성한다. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2021','2022','2023','2024','2025')]
    [string]$Year,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$MorphRunId = 'morph_search_v3_20260801',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725',
    [ValidateRange(1, 1000)]
    [int]$FilesPerShard = 100
)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ProductionYearInputSleepGuard {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
function Enable-ProductionYearInputSleepGuard {
    $result = [ProductionYearInputSleepGuard]::SetThreadExecutionState(
        [uint32]2147483649
    )
    if ($result -eq 0) { throw 'Windows 절전 억제 설정 실패' }
}
function Disable-ProductionYearInputSleepGuard {
    [void][ProductionYearInputSleepGuard]::SetThreadExecutionState(
        [uint32]2147483648
    )
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$sourceReport = Join-Path $projectRoot (
    "outputs\reports\SOURCE_CONTRACT_${MorphRunId}_${Year}.json"
)
$sleepGuardEnabled = $false
try {
    Enable-ProductionYearInputSleepGuard
    $sleepGuardEnabled = $true
    Write-Host 'Windows system sleep guard: enabled' -ForegroundColor Cyan
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
        Join-Path $PSScriptRoot 'run_morph_search_year_safe.ps1'
    ) -Year $Year -RunId $MorphRunId -FilesPerShard $FilesPerShard
    if ($LASTEXITCODE -ne 0) {
        throw "$Year morph_search.v3 생성/재개 실패"
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
        Join-Path $PSScriptRoot 'verify_production_source_contract.ps1'
    ) -Year $Year -MorphRunId $MorphRunId `
        -SearchMasterRunId $SearchMasterRunId -Ensure `
        -RequireMorphYearSuccess -Output $sourceReport
    if ($LASTEXITCODE -ne 0) {
        throw "$Year morph search/source contract 검증 실패"
    }
} finally {
    if ($sleepGuardEnabled) {
        Disable-ProductionYearInputSleepGuard
    }
}
Write-Host "[$Year] pre-MFA 연구 검색표·source contract 완료" `
    -ForegroundColor Green
Write-Host "source report: $sourceReport"
Write-Host 'MFA·TextGrid·원본 WAV/CSV는 변경하지 않음'
exit 0
