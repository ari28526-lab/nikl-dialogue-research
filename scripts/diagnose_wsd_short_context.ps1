#Requires -Version 5.1
[CmdletBinding()]
param([switch]$PreflightOnly, [switch]$Execute, [string]$ApprovalToken = '')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (([int]$PreflightOnly.IsPresent + [int]$Execute.IsPresent) -ne 1) {
    throw 'Specify PreflightOnly or Execute.'
}
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $projectRoot 'work\bareun_wsd_full_20260828\.venv\Scripts\python.exe'
$runner = Join-Path $projectRoot 'scripts\python\diagnose_wsd_short_context.py'
$arguments = [Collections.Generic.List[string]]::new()
$arguments.Add($runner)
if ($Execute) {
    if ($ApprovalToken -cne 'BAREUN_SHORT_CONTEXT_3_CALLS_20260905') {
        throw 'The exact bounded three-call approval token is required.'
    }
    $arguments.Add('--execute')
    $arguments.Add('--approval-token')
    $arguments.Add($ApprovalToken)
}
& $python $arguments.ToArray()
exit $LASTEXITCODE
