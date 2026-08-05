#Requires -Version 5.1
<#
2020--2025에 같은 계약으로 사전 발음 occurrence, 어절 비교표, 발화 index와
선택적 7-tier 파생 TextGrid를 만든다. 기존 MFA DB와 6-tier는 읽기 전용이다.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year,

    [ValidateSet('Tables','Pilot','Full')]
    [string]$Mode = 'Tables',

    [ValidateRange(1, 20)]
    [int]$PilotSessions = 2,

    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pathsConfig = Get-Content -Raw -Encoding UTF8 -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) | ConvertFrom-Json
$contractPath = Join-Path $projectRoot `
    'config\pronunciation_reference_layer_v1.json'
$contract = Get-Content -Raw -Encoding UTF8 -LiteralPath $contractPath |
    ConvertFrom-Json

function Expand-CfgPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}

function Assert-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "필수 파일 없음: $Path"
    }
}

function Read-SuccessManifest([string]$Path, [string]$Label) {
    Assert-File $Path
    $value = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path |
        ConvertFrom-Json
    if ([string]$value.status -ne 'success') {
        throw "$Label manifest가 success가 아님: $Path"
    }
    return $value
}

function Invoke-PipelinePython([string[]]$Arguments, [string]$Label) {
    Write-Host "[$Year] $Label" -ForegroundColor Cyan
    & $script:python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label 실패(exit=$LASTEXITCODE)"
    }
}

function Test-ArtifactPair([string]$Manifest, [string]$Artifact) {
    if (-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) { return $false }
    if (-not (Test-Path -LiteralPath $Artifact -PathType Leaf)) { return $false }
    $value = Get-Content -Raw -Encoding UTF8 -LiteralPath $Manifest |
        ConvertFrom-Json
    return ([string]$value.status -eq 'success')
}

function Assert-PassedVerification(
    [string]$Path,
    [string]$Label,
    [string]$VerifiedInputName,
    [string]$ExpectedSha256
) {
    Assert-File $Path
    $value = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path |
        ConvertFrom-Json
    if ([string]$value.status -ne 'passed') {
        throw "$Label 독립 검증 보고서가 passed가 아님: $Path"
    }
    if (@($value.partial_files).Count -ne 0) {
        throw "$Label 독립 검증 보고서에 partial이 있음: $Path"
    }
    if (@($value.error_counts.PSObject.Properties).Count -ne 0) {
        throw "$Label 독립 검증 보고서에 오류가 있음: $Path"
    }
    $inputProperty = $value.inputs.PSObject.Properties[$VerifiedInputName]
    if ($null -eq $inputProperty) {
        throw "$Label 독립 검증 보고서에 입력 SHA 항목이 없음: $VerifiedInputName"
    }
    $verifiedSha256 = [string]$inputProperty.Value.sha256
    if ($verifiedSha256 -ne $ExpectedSha256) {
        throw "$Label 산출물과 독립 검증 보고서 SHA가 다름"
    }
}

$python = Expand-CfgPath ([string]$pathsConfig.pipeline_python)
$morphRoot = Join-Path (
    Expand-CfgPath ([string]$pathsConfig.morph_search_v3_staging)
) ([string]$contract.frozen_resources.morph_search_release)
$referenceRoot = Expand-CfgPath ([string]$pathsConfig.pronunciation_reference)
$releaseRoot = Join-Path $referenceRoot `
    ([string]$contract.frozen_resources.registry_release)
$sixTierRoot = Expand-CfgPath ([string]$pathsConfig.textgrid_research_v2_staging)
$sevenTierRoot = Expand-CfgPath `
    ([string]$pathsConfig.textgrid_pron_reference_v1_staging)
$pilotRoot = Join-Path (
    Expand-CfgPath ([string]$pathsConfig.audio_home)
) '09_textgrid_pron_reference_v1_pilot_20260805'

$annualRoot = Join-Path (Join-Path $morphRoot $Year) 'annual_tables'
$sixTierTables = Join-Path (Join-Path $sixTierRoot $Year) '_tables'
$matchRoot = Join-Path $releaseRoot 'match_index_v1'
$summaryRoot = Join-Path $releaseRoot 'group_summaries_v1'
$occurrenceRoot = Join-Path (Join-Path $releaseRoot 'occurrences_v1') $Year
$compareRoot = Join-Path (Join-Path $releaseRoot 'compare_v2') $Year
$reportsRoot = Join-Path $projectRoot 'outputs\reports'

$morphTokens = Join-Path $annualRoot 'morph_tokens.csv.gz'
$orthEojeol = Join-Path $annualRoot 'orth_eojeol_tokens.csv.gz'
$utteranceMaster = Join-Path $annualRoot 'utterance_master_v2.csv.gz'
$yearManifest = Join-Path $annualRoot 'YEAR_MANIFEST.json'
$wordIntervals = Join-Path $sixTierTables 'word_intervals_mfa.csv.gz'
$utteranceAlignment = Join-Path $sixTierTables 'utterance_alignment.csv.gz'
$tablesManifest = Join-Path $sixTierTables 'TABLES_MANIFEST.json'
$matchGroups = Join-Path $matchRoot `
    'dictionary_pronunciation_match_groups.csv.gz'
$matchManifest = Join-Path $matchRoot `
    'dictionary_pronunciation_match_index_manifest.json'
$groupSummaries = Join-Path $summaryRoot `
    'dictionary_pronunciation_group_summaries.csv.gz'
$groupSummaryManifest = Join-Path $summaryRoot `
    'dictionary_pronunciation_group_summaries_manifest.json'
$occurrences = Join-Path $occurrenceRoot `
    'morph_dictionary_pron_occurrences.csv.gz'
$occurrenceManifest = Join-Path $occurrenceRoot `
    'morph_dictionary_pron_occurrences_manifest.json'
$compare = Join-Path $compareRoot 'eojeol_pronunciation_compare.csv.gz'
$compareManifest = Join-Path $compareRoot `
    'eojeol_pronunciation_compare_manifest.json'
$utteranceIndex = Join-Path $compareRoot 'pron_reference_utterance.csv.gz'
$utteranceIndexManifest = Join-Path $compareRoot `
    'PRON_REFERENCE_UTTERANCE_MANIFEST.json'

foreach ($path in @(
    $python, $contractPath, $morphTokens, $orthEojeol, $utteranceMaster,
    $yearManifest, $wordIntervals, $utteranceAlignment, $tablesManifest,
    $matchGroups, $matchManifest, $groupSummaries, $groupSummaryManifest
)) {
    Assert-File $path
}
$null = Read-SuccessManifest $yearManifest 'morph_search year'
$null = Read-SuccessManifest $tablesManifest 'six-tier companion'
$null = Read-SuccessManifest $matchManifest 'dictionary match index'
$null = Read-SuccessManifest $groupSummaryManifest 'dictionary group summary'

$occurrenceBuilder = Join-Path $projectRoot `
    'scripts\python\link_morph_occurrences_to_dictionary_pronunciation.py'
$occurrenceVerifier = Join-Path $projectRoot `
    'scripts\python\verify_dictionary_pronunciation_occurrences.py'
$compareBuilder = Join-Path $projectRoot `
    'scripts\python\build_eojeol_pronunciation_compare.py'
$compareVerifier = Join-Path $projectRoot `
    'scripts\python\verify_eojeol_pronunciation_compare.py'
$indexBuilder = Join-Path $projectRoot `
    'scripts\python\build_pron_reference_utterance_index.py'
$backfillBuilder = Join-Path $projectRoot `
    'scripts\python\backfill_pron_reference_textgrid.py'
$backfillVerifier = Join-Path $projectRoot `
    'scripts\python\verify_pron_reference_textgrid_backfill.py'
foreach ($path in @(
    $occurrenceBuilder, $occurrenceVerifier, $compareBuilder,
    $compareVerifier, $indexBuilder, $backfillBuilder, $backfillVerifier
)) {
    Assert-File $path
}

$occurrenceReport = Join-Path $reportsRoot `
    ("VERIFY_dictionary_pron_occurrences_{0}_20260805.json" -f $Year)
$compareReport = Join-Path $reportsRoot `
    ("VERIFY_eojeol_pronunciation_compare_{0}_20260805.json" -f $Year)
$backfillReport = Join-Path $reportsRoot `
    ("VERIFY_pron_reference_textgrid_backfill_{0}_20260805.json" -f $Year)

$lockStream = $null
$lockPath = Join-Path (Join-Path $releaseRoot '_locks') `
    ("pronunciation_reference_{0}.lock" -f $Year)
if (-not $PreflightOnly) {
    [IO.Directory]::CreateDirectory((Split-Path -Parent $lockPath)) | Out-Null
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        $oldPidText = (Get-Content -Raw -ErrorAction SilentlyContinue `
            -LiteralPath $lockPath).Trim()
        $oldPid = 0
        if ([int]::TryParse($oldPidText, [ref]$oldPid) -and
            $null -ne (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
            throw "같은 연도 작업이 실행 중임: PID=$oldPid"
        }
        Remove-Item -LiteralPath $lockPath -Force
    }
    $lockStream = [IO.File]::Open(
        $lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
        [IO.FileShare]::Read
    )
    $lockBytes = [Text.Encoding]::UTF8.GetBytes([string]$PID)
    $lockStream.Write($lockBytes, 0, $lockBytes.Length)
    $lockStream.Flush()
}

function Clear-PronunciationReferenceLock {
    if ($null -ne $script:lockStream) {
        $script:lockStream.Dispose()
        $script:lockStream = $null
        Remove-Item -LiteralPath $script:lockPath -Force `
            -ErrorAction SilentlyContinue
    }
}

trap {
    $failure = $_
    Clear-PronunciationReferenceLock
    throw $failure
}

    $occurrenceArgs = [Collections.Generic.List[string]]::new()
    foreach ($value in @(
        $occurrenceBuilder, '--year', $Year,
        '--morph-tokens', $morphTokens,
        '--year-manifest', $yearManifest,
        '--match-groups', $matchGroups,
        '--match-manifest', $matchManifest,
        '--output-dir', $occurrenceRoot
    )) { $occurrenceArgs.Add([string]$value) }
    if ($PreflightOnly) { $occurrenceArgs.Add('--preflight-only') }

    if (-not (Test-ArtifactPair $occurrenceManifest $occurrences)) {
        $stageArgs = $occurrenceArgs.ToArray()
        Invoke-PipelinePython -Arguments $stageArgs -Label '형태소 occurrence 연결'
        if ($PreflightOnly) {
            Write-Host '[OK] 다음 미완료 단계 preflight 통과; 산출물 생성 없음' `
                -ForegroundColor Green
            Clear-PronunciationReferenceLock
            exit 0
        }
        $verifyOccurrenceArgs = @(
            $occurrenceVerifier, '--year', $Year,
            '--morph-tokens', $morphTokens,
            '--occurrences', $occurrences,
            '--occurrence-manifest', $occurrenceManifest,
            '--output-report', $occurrenceReport
        )
        Invoke-PipelinePython -Arguments $verifyOccurrenceArgs -Label '형태소 occurrence 독립 전수 검증'
    } else {
        Write-Host "[$Year] occurrence 완료 checkpoint 재사용" -ForegroundColor DarkGreen
    }
    $occurrenceManifestValue = Read-SuccessManifest `
        $occurrenceManifest 'morph occurrence'
    Assert-PassedVerification `
        -Path $occurrenceReport `
        -Label '형태소 occurrence' `
        -VerifiedInputName 'occurrences' `
        -ExpectedSha256 ([string]$occurrenceManifestValue.outputs.occurrences.sha256)

    $compareArgs = [Collections.Generic.List[string]]::new()
    foreach ($value in @(
        $compareBuilder, '--year', $Year,
        '--utterance-master', $utteranceMaster,
        '--orth-eojeol-tokens', $orthEojeol,
        '--year-manifest', $yearManifest,
        '--morph-occurrences', $occurrences,
        '--occurrence-manifest', $occurrenceManifest,
        '--word-intervals', $wordIntervals,
        '--tables-manifest', $tablesManifest,
        '--group-summaries', $groupSummaries,
        '--group-summary-manifest', $groupSummaryManifest,
        '--output-dir', $compareRoot
    )) { $compareArgs.Add([string]$value) }
    if ($PreflightOnly) { $compareArgs.Add('--preflight-only') }
    if (-not (Test-ArtifactPair $compareManifest $compare)) {
        $stageArgs = $compareArgs.ToArray()
        Invoke-PipelinePython -Arguments $stageArgs -Label '어절 발음 비교표'
        if ($PreflightOnly) {
            Write-Host '[OK] 다음 미완료 단계 preflight 통과; 산출물 생성 없음' `
                -ForegroundColor Green
            Clear-PronunciationReferenceLock
            exit 0
        }
        $verifyCompareArgs = @(
            $compareVerifier, '--year', $Year,
            '--orth-eojeol-tokens', $orthEojeol,
            '--compare', $compare,
            '--compare-manifest', $compareManifest,
            '--output-report', $compareReport
        )
        Invoke-PipelinePython -Arguments $verifyCompareArgs -Label '어절 비교표 독립 전수 검증'
    } else {
        Write-Host "[$Year] 어절 비교표 완료 checkpoint 재사용" -ForegroundColor DarkGreen
    }
    $compareManifestValue = Read-SuccessManifest `
        $compareManifest 'eojeol pronunciation compare'
    Assert-PassedVerification `
        -Path $compareReport `
        -Label '어절 발음 비교표' `
        -VerifiedInputName 'compare' `
        -ExpectedSha256 ([string]$compareManifestValue.outputs.compare.sha256)

    $indexArgs = [Collections.Generic.List[string]]::new()
    foreach ($value in @(
        $indexBuilder, '--year', $Year,
        '--utterance-master', $utteranceMaster,
        '--year-manifest', $yearManifest,
        '--compare', $compare,
        '--compare-manifest', $compareManifest,
        '--output-dir', $compareRoot
    )) { $indexArgs.Add([string]$value) }
    if ($PreflightOnly) { $indexArgs.Add('--preflight-only') }
    if (-not (Test-ArtifactPair $utteranceIndexManifest $utteranceIndex)) {
        $stageArgs = $indexArgs.ToArray()
        Invoke-PipelinePython -Arguments $stageArgs -Label '발화 발음 참조 index'
        if ($PreflightOnly) {
            Write-Host '[OK] 다음 미완료 단계 preflight 통과; 산출물 생성 없음' `
                -ForegroundColor Green
            Clear-PronunciationReferenceLock
            exit 0
        }
    } else {
        Write-Host "[$Year] 발화 index 완료 checkpoint 재사용" -ForegroundColor DarkGreen
    }

    if ($Mode -eq 'Tables') {
        Write-Host "[OK] $Year 발음 참조 정규화 표 완료" -ForegroundColor Green
        Clear-PronunciationReferenceLock
        exit 0
    }

    $targetTextGridRoot = if ($Mode -eq 'Pilot') { $pilotRoot } else { $sevenTierRoot }
    $backfillArgs = [Collections.Generic.List[string]]::new()
    foreach ($value in @(
        $backfillBuilder, '--year', $Year,
        '--source-textgrid-root', $sixTierRoot,
        '--utterance-alignment', $utteranceAlignment,
        '--tables-manifest', $tablesManifest,
        '--utterance-index', $utteranceIndex,
        '--utterance-index-manifest', $utteranceIndexManifest,
        '--output-root', $targetTextGridRoot
    )) { $backfillArgs.Add([string]$value) }
    if ($Mode -eq 'Pilot') {
        $backfillArgs.Add('--max-sessions')
        $backfillArgs.Add([string]$PilotSessions)
    }
    if ($PreflightOnly) { $backfillArgs.Add('--preflight-only') }
    $stageArgs = $backfillArgs.ToArray()
    Invoke-PipelinePython -Arguments $stageArgs -Label '7-tier 파생 TextGrid backfill'
    if (-not $PreflightOnly) {
        $verifyBackfillArgs = @(
            $backfillVerifier, '--year', $Year,
            '--source-textgrid-root', $sixTierRoot,
            '--output-root', $targetTextGridRoot,
            '--report', $backfillReport
        )
        Invoke-PipelinePython -Arguments $verifyBackfillArgs -Label '7-tier 파생본 독립 전수 검증'
    }
    Write-Host "[OK] $Year 발음 참조 레이어 $Mode 완료" -ForegroundColor Green
    Clear-PronunciationReferenceLock
