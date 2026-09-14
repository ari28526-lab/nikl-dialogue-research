#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [switch]$Execute,
    [switch]$Status,
    [string]$ApprovedBy = '',
    [string]$ApprovalToken = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (([int]$PreflightOnly.IsPresent + [int]$Execute.IsPresent + [int]$Status.IsPresent) -ne 1) {
    throw 'Specify exactly one of PreflightOnly, Execute or Status.'
}
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $projectRoot 'work\bareun_wsd_full_20260828\.venv\Scripts\python.exe'
$runner = Join-Path $projectRoot 'scripts\python\run_wsd_short_bootstrap.py'
$arguments = [Collections.Generic.List[string]]::new()
$arguments.Add($runner)
if ($Execute) {
    if ($ApprovedBy -cne 'ari30' -or $ApprovalToken -cne 'BAREUN_SHORT_CONTEXT_FIRST_HOUR_300_CALLS_20260905') {
        throw 'Explicit approver and exact first-hour approval token are required.'
    }
    Write-Host 'Limited WSD speed check: 1 hour, at most 300 API attempts and 120000 input characters.'
    Write-Host 'This is NOT a full-corpus execution. Preserve the output folder on F:.'
    $arguments.Add('--execute')
    $arguments.Add('--approval-token')
    $arguments.Add($ApprovalToken)
}
if ($Status) { $arguments.Add('--status') }
& $python $arguments.ToArray()
exit $LASTEXITCODE
