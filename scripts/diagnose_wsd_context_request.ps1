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
$runner = Join-Path $projectRoot 'scripts\python\diagnose_wsd_context_request.py'
$arguments = [Collections.Generic.List[string]]::new()
$arguments.Add($runner)
if ($Execute) {
    if ($ApprovalToken -cne 'BAREUN_CONTEXT_DIAGNOSTIC_ONE_CALL_20260905') {
        throw 'The exact single-call diagnostic token is required.'
    }
    $arguments.Add('--execute')
    $arguments.Add('--approval-token')
    $arguments.Add($ApprovalToken)
}
& $python $arguments.ToArray()
exit $LASTEXITCODE
