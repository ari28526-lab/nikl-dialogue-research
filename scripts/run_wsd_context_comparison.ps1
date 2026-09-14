#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [switch]$Execute,
    [switch]$Status,
    [string]$ApprovalToken = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (([int]$PreflightOnly.IsPresent + [int]$Execute.IsPresent + [int]$Status.IsPresent) -ne 1) {
    throw 'Specify exactly one of PreflightOnly, Execute or Status.'
}
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $projectRoot 'work\bareun_wsd_full_20260828\.venv\Scripts\python.exe'
$runner = Join-Path $projectRoot 'scripts\python\run_wsd_context_comparison.py'
$arguments = [Collections.Generic.List[string]]::new()
$arguments.Add($runner)
if ($Status) { $arguments.Add('--status') }
if ($Execute) {
    if ($ApprovalToken -cne 'BAREUN_CONTEXT_COMPARISON_36_CALLS_20260905') {
        throw 'The exact 36-call comparison approval token is required.'
    }
    $arguments.Add('--execute')
    $arguments.Add('--approval-token')
    $arguments.Add($ApprovalToken)
}
& $python $arguments.ToArray()
exit $LASTEXITCODE
