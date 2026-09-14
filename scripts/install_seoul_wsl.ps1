#Requires -Version 5.1
[CmdletBinding()]
param([switch]$PreflightOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = Split-Path -Parent $PSScriptRoot
$logRoot = Join-Path $projectRoot 'work\koina_seoul_20260911'
$wslPath = Join-Path $env:WINDIR 'System32\wsl.exe'
$admin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($PreflightOnly) {
    [pscustomobject]@{wsl_present=(Test-Path -LiteralPath $wslPath);administrator=$admin;automatic_reboot=$false;install_arguments=@('--install','--no-distribution','--web-download')} | ConvertTo-Json
    return
}
if (-not $admin) { throw 'Administrator token required for WSL installation.' }
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$stdout = Join-Path $logRoot ($stamp + '_wsl_install_stdout.log')
$stderr = Join-Path $logRoot ($stamp + '_wsl_install_stderr.log')
$resultPath = Join-Path $logRoot 'WSL_ADMIN_INSTALL_RESULT.json'
$statusPath = Join-Path $logRoot 'WSL_ADMIN_INSTALL_STATE.json'
[IO.File]::WriteAllText($statusPath,(@{status='installing';pid=$PID;started_at=(Get-Date).ToString('o');stdout=$stdout;stderr=$stderr} | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
try {
    $proc = Start-Process -FilePath $wslPath -ArgumentList @('--install','--no-distribution','--web-download') -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -Wait -PassThru
    $result = @{status='installer_returned';exit_code=$proc.ExitCode;finished_at=(Get-Date).ToString('o');stdout=$stdout;stderr=$stderr;automatic_reboot=$false}
    [IO.File]::WriteAllText($resultPath,($result | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($statusPath,($result | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
} catch {
    [IO.File]::WriteAllText($statusPath,(@{status='failed';error=$_.Exception.Message;automatic_reboot=$false} | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
    throw
}
