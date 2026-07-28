#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^common_pron_pilot_[a-z0-9_]+_[0-9]{8}$')]
    [string]$ReleaseId,

    [ValidateRange(10, 500)]
    [int]$MinimumFreeGiB = 50
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pathsConfig = Join-Path $projectRoot 'config\paths.json'
$config = Get-Content -Raw -Encoding UTF8 -LiteralPath $pathsConfig |
    ConvertFrom-Json

$commonRoot = [System.IO.Path]::GetFullPath(
    [Environment]::ExpandEnvironmentVariables(
        [string]$config.common_pron_home
    )
)
$expectedRoot = [System.IO.Path]::GetFullPath('D:\mfa_common_pron')
if ($commonRoot.TrimEnd('\') -ne $expectedRoot.TrimEnd('\')) {
    throw "공통 발음 root 안전 차단: expected=$expectedRoot actual=$commonRoot"
}

$drive = [System.IO.DriveInfo]::new('D')
if (-not $drive.IsReady -or $drive.VolumeLabel -ne 'DATA_SSD') {
    throw "D: 드라이브 안전 차단: ready=$($drive.IsReady), label=$($drive.VolumeLabel)"
}
$freeGiB = [math]::Round($drive.AvailableFreeSpace / 1GB, 3)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw "공통 발음 파일럿 공간 부족: free=${freeGiB}GiB, required=${MinimumFreeGiB}GiB"
}

$bulkLock = 'D:\mfa_eojeol\locks\pre_mfa_bulk.lock'
if (Test-Path -LiteralPath $bulkLock) {
    throw "MFA 대량 실행 lock이 있어 파일럿 폴더를 만들지 않음: $bulkLock"
}

$releaseRoot = Join-Path (Join-Path $commonRoot 'releases') $ReleaseId
if (Test-Path -LiteralPath $releaseRoot) {
    throw "기존 release를 덮어쓰지 않음: $releaseRoot"
}

$relativeDirs = @(
    '00_contract',
    '01_vocabulary',
    '02_source_audit',
    '03_registry',
    '04_mfa_lexicons',
    '05_ab_corpus',
    '06_ab_results',
    '07_review',
    'logs',
    'archive'
)

$didInitialize = $false
if ($PSCmdlet.ShouldProcess($releaseRoot, '공통 발음 파일럿 release 구조 생성')) {
    New-Item -ItemType Directory -Path $releaseRoot -ErrorAction Stop |
        Out-Null
    foreach ($relative in $relativeDirs) {
        New-Item -ItemType Directory -Path (Join-Path $releaseRoot $relative) `
            -ErrorAction Stop | Out-Null
    }

    $manifest = [ordered]@{
        schema_version = 1
        kind = 'common_pronunciation_pilot_release'
        release_id = $ReleaseId
        scope = 'full_frozen_corpus_vocabulary_2020_2025'
        years = @(2020, 2021, 2022, 2023, 2024, 2025)
        search_master_root = [string]$config.pre_mfa_search_master
        common_pron_root = $commonRoot
        created_at = (Get-Date).ToString('o')
        project_root = $projectRoot
        git_commit = (& git -C $projectRoot rev-parse HEAD).Trim()
        drive = [ordered]@{
            name = $drive.Name
            label = $drive.VolumeLabel
            free_bytes_before = $drive.AvailableFreeSpace
            free_gib_before = $freeGiB
        }
        policy = [ordered]@{
            raw_corpus_read_only = $true
            baseline_2020_2021_read_only = $true
            no_automatic_promotion = $true
            no_automatic_cleanup = $true
            ab_alignment_uses_sample_only = $true
            vocabulary_and_registry_use_all_six_years = $true
        }
        status = 'initialized'
    }
    $manifestPath = Join-Path $releaseRoot '00_contract\release_manifest.json'
    $manifest | ConvertTo-Json -Depth 8 |
        Set-Content -Encoding UTF8 -LiteralPath $manifestPath

    $readme = @"
# $ReleaseId

범위: 2020–2025 전체 동결 코퍼스의 MFA 입력 어휘.

- 전체 vocabulary와 발음 registry는 6개년 전수 자료로 만든다.
- 소표본은 정책 A/B의 정렬 품질 검증에만 사용한다.
- 2020·2021 baseline, 원 WAV, 원 JSON, 동결 CSV는 읽기 전용이다.
- 이 release는 검증 전 canonical 결과로 승격하지 않는다.
- 대형 산출물은 이 폴더에 두고 Git에는 코드·작은 manifest·보고서만 둔다.
"@
    $readme | Set-Content -Encoding UTF8 `
        -LiteralPath (Join-Path $releaseRoot 'README.md')
    $didInitialize = $true
}

[pscustomobject]@{
    status = if ($didInitialize) { 'initialized' } else { 'would_initialize' }
    release_id = $ReleaseId
    release_root = $releaseRoot
    free_gib_before = $freeGiB
    directories = if ($didInitialize) { $relativeDirs.Count } else { 0 }
} | ConvertTo-Json -Depth 4
