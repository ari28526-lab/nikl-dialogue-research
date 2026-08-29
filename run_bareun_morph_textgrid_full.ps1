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

function Read-Utf8Text {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = New-Object IO.FileStream(
        $Path,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::Read
    )
    try {
        $reader = New-Object IO.StreamReader(
            $stream,
            (New-Object Text.UTF8Encoding($false)),
            $true
        )
        try {
            return $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

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
$pathsConfig = Join-Path $projectRoot 'config\paths.json'
$runner = Join-Path $projectRoot 'scripts\python\run_bareun_morph_textgrid_full.py'
$auditor = Join-Path $projectRoot 'scripts\python\audit_bareun_morph_textgrid_full.py'
$config = Join-Path $projectRoot 'config\bareun_morph_textgrid_full_v1.json'

foreach ($required in @($pathsConfig, $runner, $auditor, $config)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 파일이 없습니다: $required"
    }
}

$pathSettings = Read-Utf8Text -Path $pathsConfig | ConvertFrom-Json
$pythonValue = [Environment]::ExpandEnvironmentVariables(
    [string]$pathSettings.pipeline_python
)
$python = [IO.Path]::GetFullPath($pythonValue.Replace('/', '\'))
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "pipeline_python이 없습니다: $python"
}

$preflightArguments = New-Object 'System.Collections.Generic.List[string]'
[void]$preflightArguments.Add($runner)
[void]$preflightArguments.Add('--config')
[void]$preflightArguments.Add($config)
[void]$preflightArguments.Add('--preflight-only')
if ($Resume) {
    [void]$preflightArguments.Add('--resume')
}

if ($PreflightOnly) {
    Write-Host '바른 v3.1 형태소 TextGrid 전수 preflight만 실행합니다.'
    & $python $preflightArguments.ToArray()
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($ApprovedBy)) {
    throw '-Execute에는 -ApprovedBy가 필요합니다.'
}
$expectedToken = 'BAREUN_MORPH_TEXTGRID_FULL_20260829'
if ($ApprovalToken -cne $expectedToken) {
    throw "정확한 -ApprovalToken $expectedToken 이 필요합니다."
}

Write-Host '실행 직전 preflight를 다시 확인합니다.'
& $python $preflightArguments.ToArray()
if ($LASTEXITCODE -ne 0) {
    throw "preflight가 통과하지 못했습니다. exit=$LASTEXITCODE"
}

$typeName = 'BareunMorphTextGridExecutionState'
if (-not ($typeName -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class BareunMorphTextGridExecutionState {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
}
$ES_CONTINUOUS = [Convert]::ToUInt32('80000000', 16)
$keepAwake = [Convert]::ToUInt32('80000041', 16)

$runArguments = New-Object 'System.Collections.Generic.List[string]'
[void]$runArguments.Add($runner)
[void]$runArguments.Add('--config')
[void]$runArguments.Add($config)
[void]$runArguments.Add('--execute')
[void]$runArguments.Add('--approved-by')
[void]$runArguments.Add($ApprovedBy.Trim())
[void]$runArguments.Add('--approval-token')
[void]$runArguments.Add($ApprovalToken)
if ($Resume) {
    [void]$runArguments.Add('--resume')
}

Write-Host '파생 TextGrid 전수를 시작합니다. 원본 TextGrid·WAV는 수정하지 않습니다.'
Write-Host '상태 확인: .\show_bareun_morph_textgrid_status.ps1'
[void][BareunMorphTextGridExecutionState]::SetThreadExecutionState($keepAwake)
try {
    & $python $runArguments.ToArray()
    $buildExit = $LASTEXITCODE
    if ($buildExit -ne 0) {
        Write-Host '완료분은 보존되었습니다. 상태를 확인한 뒤 -Resume으로 재개하세요.'
        exit $buildExit
    }

    Write-Host '생성이 끝났습니다. 독립 전수 SHA 감사를 이어서 실행합니다.'
    $auditArguments = New-Object 'System.Collections.Generic.List[string]'
    [void]$auditArguments.Add($auditor)
    [void]$auditArguments.Add('--config')
    [void]$auditArguments.Add($config)
    [void]$auditArguments.Add('--execute')
    if ($Resume) {
        [void]$auditArguments.Add('--resume')
    }
    & $python $auditArguments.ToArray()
    $auditExit = $LASTEXITCODE
    if ($auditExit -ne 0) {
        Write-Host '생성 결과는 보존되었습니다. 감사 상태를 확인한 뒤 -Resume으로 재개하세요.'
    }
    exit $auditExit
} finally {
    [void][BareunMorphTextGridExecutionState]::SetThreadExecutionState($ES_CONTINUOUS)
}
