#Requires -Version 5.1
<#
검증된 사전 발음 registry를 형태소 표면형+품사 후보 그룹으로 정규화한다.

기존 registry와 MFA 산출물은 수정하지 않는다. 용언은 word_stem+정확 품사,
그 밖의 품사는 headword+정확 품사로 그룹을 만든다.
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 100)]
    [int]$MinimumFreeGiB = 5,

    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (
    Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')
).Path
$config = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath (Join-Path $projectRoot 'config\paths.json') |
    ConvertFrom-Json

function Expand-CfgPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
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
$referenceRoot = Expand-CfgPath ([string]$config.pronunciation_reference)
$releaseRoot = Join-Path $referenceRoot `
    'dictionary_pron_registry_v2_20260805'
$registry = Join-Path $releaseRoot `
    'dictionary_pronunciation_registry.csv.gz'
$registryManifest = Join-Path $releaseRoot `
    'dictionary_pronunciation_registry_manifest.json'
$outputDir = Join-Path $releaseRoot 'match_index_v1'
$builder = Join-Path $projectRoot `
    'scripts\python\build_dictionary_pronunciation_match_index.py'
Assert-Child $releaseRoot $referenceRoot
Assert-Child $outputDir $releaseRoot

foreach ($path in @($python, $registry, $registryManifest, $builder)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "필수 파일 없음: $path"
    }
}

$driveInfo = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($referenceRoot))
$freeGiB = $driveInfo.AvailableFreeSpace / 1GB
if ($freeGiB -lt $MinimumFreeGiB) {
    throw ('저장 공간 부족: {0:N2} GiB < {1} GiB' -f `
        $freeGiB, $MinimumFreeGiB)
}

$arguments = [Collections.Generic.List[string]]::new()
foreach ($value in @(
    $builder,
    '--registry', $registry,
    '--registry-manifest', $registryManifest,
    '--output-dir', $outputDir
)) {
    $arguments.Add([string]$value)
}
if ($PreflightOnly) {
    $arguments.Add('--preflight-only')
}

Write-Host ('사전 발음 match index {0}: {1}' -f `
    $(if ($PreflightOnly) { 'preflight' } else { '생성' }), $outputDir) `
    -ForegroundColor Cyan
Write-Host '정책: 용언 stem+POS, 기타 headword+POS; 의미 자동 선택 없음'
& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "사전 발음 match index 작업 실패(exit=$LASTEXITCODE)"
}

if ($PreflightOnly) {
    Write-Host '[OK] preflight만 완료; D: match index는 만들지 않음' `
        -ForegroundColor Green
} else {
    Write-Host ('[OK] match index 완료: {0}' -f $outputDir) `
        -ForegroundColor Green
}
