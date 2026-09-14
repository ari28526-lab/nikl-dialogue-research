#Requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$config = Get-Content -LiteralPath (Join-Path $projectRoot 'config\homonym_context_pilot_20260906.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$config.output_root = & (Join-Path $PSScriptRoot 'get_research_data_path.ps1') -Key 'homonym_review_source'
$statePath = Join-Path $config.output_root 'STATE.json'
if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    Write-Output '문맥사전 파일럿: 아직 시작하지 않았습니다.'
    exit 0
}
$taskShare = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
$taskStream = [IO.FileStream]::new($statePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, $taskShare)
try {
    $taskReader = [IO.StreamReader]::new($taskStream, [Text.Encoding]::UTF8)
    try { $taskState = $taskReader.ReadToEnd() | ConvertFrom-Json }
    finally { $taskReader.Dispose() }
} finally { $taskStream.Dispose() }
$taskAlive = $false
if ($null -ne $taskState.pid) {
    $taskProcess = Get-Process -Id ([int]$taskState.pid) -ErrorAction SilentlyContinue
    $taskAlive = ($null -ne $taskProcess)
}
Write-Output ('상태: {0}' -f $taskState.status)
Write-Output ('단계: {0} / 기록 PID: {1} / PID 생존: {2}' -f $taskState.phase, $taskState.pid, $taskAlive)
Write-Output ('출력: {0}' -f $config.output_root)
if ($taskState.PSObject.Properties.Name -contains 'summary') {
    $taskSummary = $taskState.summary
    Write-Output ('문서 {0} / 문장 {1} / 형태소 {2} / 결합 패턴 {3}' -f $taskSummary.audit.documents, $taskSummary.audit.sentences, $taskSummary.audit.morphemes, $taskSummary.patterns)
    Write-Output ('구조 감사 통과: {0} / 새 API 호출: {1} / 음성 필요: {2}' -f $taskSummary.audit.passed, $taskSummary.api_called, $taskSummary.audio_required)
}
if ($taskState.PSObject.Properties.Name -contains 'error_type') {
    Write-Output ('중단/오류 종류: {0}' -f $taskState.error_type)
}
