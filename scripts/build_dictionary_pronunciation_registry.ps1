#Requires -Version 5.1
<#
우리말샘 발음 후보를 재사용 가능한 type-level registry로 만든다.

이 작업은 기존 MFA 사전·DB·TextGrid를 수정하지 않는다. pron_1/pron_2는
사전 등재 후보로, legacy pron_g2p는 기계 fallback으로 명시해 저장한다.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^dictionary_pron_registry_v[0-9]+_[0-9]{8}$')]
    [string]$ReleaseId = 'dictionary_pron_registry_v1_20260805',

    [ValidateRange(1, 100)]
    [int]$MinimumFreeGiB = 5,

    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (
    Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')
).Path
$configPath = Join-Path $projectRoot 'config\paths.json'
$config = Get-Content -Raw -Encoding UTF8 -LiteralPath $configPath |
    ConvertFrom-Json

function Expand-CfgPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables(
            $Value.Replace('/', '\')
        )
    )
}

function Assert-Child([string]$Path, [string]$Root) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $allowed = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith(
        $allowed, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "경로 경계 위반: $resolved (root=$Root)"
    }
}

$python = Expand-CfgPath ([string]$config.pipeline_python)
$dictionaryRoot = Expand-CfgPath ([string]$config.reference_dictionary)
$legacy = Expand-CfgPath ([string]$config.lexicon_full)
$referenceRoot = Expand-CfgPath ([string]$config.pronunciation_reference)
$enriched = Join-Path $dictionaryRoot '01_NIKL_lexicon_full_v2.csv'
$sourceAudit = Join-Path $projectRoot `
    'outputs\reports\AUDIT_common_pron_sources_20260728.json'
$builder = Join-Path $projectRoot `
    'scripts\python\build_dictionary_pronunciation_registry.py'
$outputDir = Join-Path $referenceRoot $ReleaseId
Assert-Child $outputDir $referenceRoot

foreach ($path in @($python, $enriched, $legacy, $sourceAudit, $builder)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "필수 파일 없음: $path"
    }
}

$drive = [IO.Path]::GetPathRoot($referenceRoot)
$driveInfo = [IO.DriveInfo]::new($drive)
$freeGiB = $driveInfo.AvailableFreeSpace / 1GB
if ($freeGiB -lt $MinimumFreeGiB) {
    throw ('저장 공간 부족: {0:N2} GiB < {1} GiB' -f `
        $freeGiB, $MinimumFreeGiB)
}

$arguments = [Collections.Generic.List[string]]::new()
foreach ($value in @(
    $builder,
    '--enriched', $enriched,
    '--legacy', $legacy,
    '--source-audit', $sourceAudit,
    '--output-dir', $outputDir
)) {
    $arguments.Add([string]$value)
}
if ($PreflightOnly) {
    $arguments.Add('--preflight-only')
}

Write-Host ('사전 발음 registry {0}: {1}' -f `
    $(if ($PreflightOnly) { 'preflight' } else { '생성' }), $outputDir) `
    -ForegroundColor Cyan
Write-Host ('정책: pron_1/2=사전 후보, legacy pron_g2p=기계 fallback, MFA 변경 없음')

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "사전 발음 registry 작업 실패(exit=$LASTEXITCODE)"
}

if ($PreflightOnly) {
    Write-Host '[OK] preflight만 완료; D: 산출물은 만들지 않음' `
        -ForegroundColor Green
} else {
    Write-Host ('[OK] registry 완료: {0}' -f $outputDir) `
        -ForegroundColor Green
}
