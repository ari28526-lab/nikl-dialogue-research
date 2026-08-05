#Requires -Version 5.1
<#
연도별 morph_tokens의 각 행을 사전 발음 후보 group과 1:1로 연결한다.

사전 후보를 occurrence 수만큼 폭발시키지 않고 group_id만 기록한다. 완성된
연도는 manifest를 확인해 재사용하고, 실패한 연도는 다른 연도를 무효화하지 않는다.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^(2020|2021)(,(2020|2021))*$')]
    [string]$YearsCsv = '2020,2021',

    [ValidateRange(1, 100)]
    [int]$MinimumFreeGiB = 10,

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

$years = [Collections.Generic.List[string]]::new()
foreach ($year in @($YearsCsv.Split(','))) {
    if ($years.Contains($year)) {
        throw "중복 연도: $year"
    }
    $years.Add($year)
}

$python = Expand-CfgPath ([string]$config.pipeline_python)
$referenceRoot = Expand-CfgPath ([string]$config.pronunciation_reference)
$morphRoot = Expand-CfgPath ([string]$config.morph_search_v3_staging)
$releaseRoot = Join-Path $referenceRoot `
    'dictionary_pron_registry_v2_20260805'
$matchRoot = Join-Path $releaseRoot 'match_index_v1'
$groups = Join-Path $matchRoot `
    'dictionary_pronunciation_match_groups.csv.gz'
$matchManifest = Join-Path $matchRoot `
    'dictionary_pronunciation_match_index_manifest.json'
$occurrenceRoot = Join-Path $releaseRoot 'occurrences_v1'
$linker = Join-Path $projectRoot `
    'scripts\python\link_morph_occurrences_to_dictionary_pronunciation.py'
Assert-Child $releaseRoot $referenceRoot
Assert-Child $matchRoot $releaseRoot
Assert-Child $occurrenceRoot $releaseRoot

foreach ($path in @($python, $groups, $matchManifest, $linker)) {
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

foreach ($year in $years) {
    $annualRoot = Join-Path $morphRoot `
        ("morph_search_v3_20260801\{0}\annual_tables" -f $year)
    $morphTokens = Join-Path $annualRoot 'morph_tokens.csv.gz'
    $yearManifest = Join-Path $annualRoot 'YEAR_MANIFEST.json'
    $outputDir = Join-Path $occurrenceRoot $year
    $outputFile = Join-Path $outputDir `
        'morph_dictionary_pron_occurrences.csv.gz'
    $outputManifest = Join-Path $outputDir `
        'morph_dictionary_pron_occurrences_manifest.json'
    Assert-Child $outputDir $occurrenceRoot
    foreach ($path in @($morphTokens, $yearManifest)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "필수 연도 파일 없음: $path"
        }
    }

    if (-not $PreflightOnly -and (Test-Path -LiteralPath $outputManifest)) {
        $existing = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $outputManifest | ConvertFrom-Json
        if ($existing.status -eq 'success' -and
            $existing.coverage_complete -eq $true -and
            (Test-Path -LiteralPath $outputFile -PathType Leaf)) {
            Write-Host "[REUSE] $year occurrence link 완료본" `
                -ForegroundColor Green
            continue
        }
        throw "불완전한 기존 연도 manifest: $outputManifest"
    }
    if (-not $PreflightOnly -and (Test-Path -LiteralPath $outputFile)) {
        throw "manifest 없는 기존 output 덮어쓰기 금지: $outputFile"
    }

    $arguments = [Collections.Generic.List[string]]::new()
    foreach ($value in @(
        $linker,
        '--year', $year,
        '--morph-tokens', $morphTokens,
        '--year-manifest', $yearManifest,
        '--match-groups', $groups,
        '--match-manifest', $matchManifest,
        '--output-dir', $outputDir
    )) {
        $arguments.Add([string]$value)
    }
    if ($PreflightOnly) {
        $arguments.Add('--preflight-only')
    }

    Write-Host ("[{0}] 사전 발음 occurrence link {1}" -f `
        $year, $(if ($PreflightOnly) { 'preflight' } else { '생성' })) `
        -ForegroundColor Cyan
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$year occurrence link 실패(exit=$LASTEXITCODE)"
    }
}

if ($PreflightOnly) {
    Write-Host '[OK] 선택 연도 preflight 완료; D: occurrence는 만들지 않음' `
        -ForegroundColor Green
} else {
    Write-Host ('[OK] occurrence link 완료: {0}' -f ($years -join ',')) `
        -ForegroundColor Green
}
