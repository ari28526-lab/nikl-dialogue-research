#Requires -Version 5.1
<#
2020–2025 공통 발음사전 정책 A/B MFA 소표본 실행기.

정책 A: 기본 korean_mfa 사전 + 표본 OOV의 현재 G2P 1-best
정책 B: A + exact-word 우리말샘 연계 pron_1/2 변이

원자료·기존 2020/2021 결과를 수정하지 않고 공통 발음 release 안에만 쓴다.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^common_pron_pilot_[a-z0-9_]+_[0-9]{8}$')]
    [string]$ReleaseId = 'common_pron_pilot_full6y_20260728',

    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$RunId,

    [ValidateRange(1, 20)]
    [int]$SpeakersPerYear = 5,

    [ValidateRange(1, 16)]
    [int]$NumJobs = 0,

    [ValidateRange(10, 500)]
    [int]$MinimumFreeGiB = 40
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$config = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath (Join-Path $projectRoot 'config\paths.json') |
    ConvertFrom-Json
function Expand-CfgPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}
function Say([string]$Message) {
    Write-Host (
        '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    ) -ForegroundColor Cyan
}
function Assert-Child([string]$Path, [string]$Root) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $allowed = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith(
        $allowed, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "실행 폴더 경계 위반: $resolved (root=$Root)"
    }
}
function Invoke-MfaLogged(
    [string[]]$Arguments,
    [string]$LogPath,
    [string]$RunRoot
) {
    Assert-Child $LogPath $RunRoot
    # Windows PowerShell 5.1은 네이티브 stderr를 ErrorRecord로 바꾼다.
    # MFA의 정상 progress도 stderr를 쓰므로 전역 Stop을 그대로 두면
    # 첫 progress 출력에서 MFA가 강제 중단된다. 네이티브 호출 경계에서만
    # Continue로 낮추고, 실제 판정은 즉시 보존한 process exit code로 한다.
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $script:mfa @Arguments 2>&1 |
            Tee-Object -FilePath $LogPath |
            ForEach-Object { Write-Host $_ }
        $mfaExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return $mfaExitCode
}
function Write-Marker(
    [string]$Path,
    [string]$Stage,
    [hashtable]$Details,
    [string]$RunRoot
) {
    Assert-Child $Path $RunRoot
    $temp = "$Path.$PID.partial"
    [ordered]@{
        schema_version = 1
        run_id = $script:RunId
        stage = $Stage
        completed_at = (Get-Date).ToString('o')
        git_commit = (& git -C $projectRoot rev-parse HEAD).Trim()
        details = $Details
    } | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $Path -Force
}
function Marker-Matches(
    [string]$Path,
    [string]$Stage
) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path |
            ConvertFrom-Json
        return (
            $data.run_id -eq $script:RunId -and
            $data.stage -eq $Stage
        )
    } catch {
        return $false
    }
}
function Marker-FileHashMatches(
    [string]$MarkerPath,
    [string]$Stage,
    [string]$FilePath
) {
    if (
        -not (Marker-Matches $MarkerPath $Stage) -or
        -not (Test-Path -LiteralPath $FilePath -PathType Leaf)
    ) {
        return $false
    }
    try {
        $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $MarkerPath |
            ConvertFrom-Json
        $actual = (
            Get-FileHash -Algorithm SHA256 -LiteralPath $FilePath
        ).Hash.ToLowerInvariant()
        return $actual -eq [string]$data.details.sha256
    } catch {
        return $false
    }
}
function Archive-Incomplete(
    [string]$Path,
    [string]$PolicyRoot,
    [string]$Label
) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Assert-Child $Path $PolicyRoot
    $archiveRoot = Join-Path $PolicyRoot (
        'archive_failed\' + (Get-Date -Format 'yyyyMMdd_HHmmss') + "\$Label"
    )
    Assert-Child $archiveRoot $PolicyRoot
    New-Item -ItemType Directory -Force `
        -Path (Split-Path -Parent $archiveRoot) | Out-Null
    Move-Item -LiteralPath $Path -Destination $archiveRoot
    Say "미완료 $Label 보존: $archiveRoot"
}

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = 'ab_stress_control_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
}
if ($NumJobs -eq 0) {
    $NumJobs = [Math]::Min(4, [Environment]::ProcessorCount)
}
$commonRoot = Expand-CfgPath ([string]$config.common_pron_home)
$expectedCommonRoot = [IO.Path]::GetFullPath('D:\mfa_common_pron')
if ($commonRoot.TrimEnd('\') -ne $expectedCommonRoot.TrimEnd('\')) {
    throw "공통 발음 root 안전 차단: $commonRoot"
}
$releaseRoot = Join-Path (Join-Path $commonRoot 'releases') $ReleaseId
if (-not (Test-Path -LiteralPath $releaseRoot -PathType Container)) {
    throw "공통 발음 release 없음: $releaseRoot"
}
$releaseManifest = Join-Path $releaseRoot '00_contract\release_manifest.json'
if (-not (Test-Path -LiteralPath $releaseManifest -PathType Leaf)) {
    throw "release manifest 없음: $releaseManifest"
}
$releaseData = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath $releaseManifest | ConvertFrom-Json
if (
    $releaseData.release_id -ne $ReleaseId -or
    $releaseData.scope -ne 'full_frozen_corpus_vocabulary_2020_2025'
) {
    throw "release manifest 계약 불일치: $releaseManifest"
}
$drive = [IO.DriveInfo]::new('D')
if (-not $drive.IsReady -or $drive.VolumeLabel -ne 'DATA_SSD') {
    throw (
        "D: 안전 차단: ready=$($drive.IsReady), " +
        "label=$($drive.VolumeLabel)"
    )
}
$freeGiB = [math]::Round($drive.AvailableFreeSpace / 1GB, 3)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw "D: 공간 부족: ${freeGiB}GiB < ${MinimumFreeGiB}GiB"
}
$bulkLock = 'D:\mfa_eojeol\locks\pre_mfa_bulk.lock'
if (Test-Path -LiteralPath $bulkLock) {
    throw "대량 MFA lock 존재 — A/B 동시 실행 금지: $bulkLock"
}

$py = Expand-CfgPath ([string]$config.pipeline_python)
$envRoot = Join-Path $env:USERPROFILE 'miniforge3\envs\mfa'
$mfa = Join-Path $envRoot 'Scripts\mfa.exe'
$env:Path = (
    "$envRoot;$envRoot\Library\bin;$envRoot\Scripts;$envRoot\bin;" +
    $env:Path
)
$env:PYTHONUTF8 = '1'
$driver = Join-Path $PSScriptRoot 'python\common_pron_ab_pilot.py'
$finalizer = Join-Path $PSScriptRoot 'python\finalize_stratified_mfa_pilot.py'
$verifier = Join-Path $PSScriptRoot 'python\verify_mfa_install.py'
$modelRoot = Join-Path $env:USERPROFILE 'Documents\MFA\pretrained_models'
$baseDict = Join-Path $modelRoot 'dictionary\korean_mfa.dict'
$g2pModel = Join-Path $modelRoot 'g2p\korean_mfa.zip'
$acousticModel = Join-Path $modelRoot 'acoustic\korean_mfa.zip'
foreach ($path in @(
    $py, $mfa, $driver, $finalizer, $verifier,
    $baseDict, $g2pModel, $acousticModel
)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "필수 파일 없음: $path"
    }
}

$registryDir = Join-Path $releaseRoot '03_registry'
$registry = Join-Path $registryDir 'pronunciation_registry_seed.csv'
$registryManifest = Join-Path $registryDir 'registry_seed_manifest.json'
$sharedRoot = Join-Path (Join-Path $releaseRoot '05_ab_corpus') $RunId
$resultRoot = Join-Path (Join-Path $releaseRoot '06_ab_results') $RunId
$policyRoots = [ordered]@{
    A = Join-Path $resultRoot 'A'
    B = Join-Path $resultRoot 'B'
}
$lexiconDir = Join-Path (
    Join-Path $releaseRoot '04_mfa_lexicons\pilots'
) $RunId
$comparisonDir = Join-Path $resultRoot 'comparison'
foreach ($path in @($sharedRoot, $resultRoot, $lexiconDir, $comparisonDir)) {
    Assert-Child $path $releaseRoot
}

Say "공통 발음 A/B 파일럿: release=$ReleaseId run=$RunId"
Say (
    "6개년 × ${SpeakersPerYear}화자 × stress/control 2발화; " +
    "num_jobs=$NumJobs; D free=${freeGiB}GiB"
)
Say "기존 2020/2021 결과와 canonical CSV/TextGrid는 수정하지 않음"

$patchReport = Join-Path $projectRoot (
    "logs\mfa_common_pron_ab_install_${RunId}.json"
)
& $py $verifier --json-output $patchReport
if ($LASTEXITCODE -ne 0) {
    throw "MFA 설치 검증 실패: $patchReport"
}

# 1. 전수 vocabulary와 사전 exact-word 후보 registry. 현재 parser 계약과
# SHA256이 모두 맞는 성공 결과만 재사용한다.
$registryReusable = $false
if (
    (Test-Path -LiteralPath $registry -PathType Leaf) -and
    (Test-Path -LiteralPath $registryManifest -PathType Leaf)
) {
    $registryData = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $registryManifest | ConvertFrom-Json
    $registryContract = [string](
        $registryData.policy.base_dictionary_parse_contract
    )
    if (
        [int]$registryData.schema_version -ne 2 -or
        $registryContract -ne 'mfa_3_4_optional_probability_columns_v1'
    ) {
        Say (
            "[1/7] 구 registry parser 계약 폐기·보존 " +
            "(schema=$($registryData.schema_version), " +
            "contract='$registryContract')"
        )
        Archive-Incomplete $sharedRoot $releaseRoot `
            'dependent_sample_before_dictionary_probability_fix'
        Archive-Incomplete $resultRoot $releaseRoot `
            'dependent_results_before_dictionary_probability_fix'
        Archive-Incomplete $lexiconDir $releaseRoot `
            'dependent_lexicons_before_dictionary_probability_fix'
        Archive-Incomplete $registryDir $releaseRoot `
            'registry_before_dictionary_probability_fix'
        New-Item -ItemType Directory -Path $registryDir | Out-Null
    } elseif ($registryData.status -ne 'success') {
        throw "기존 registry manifest가 success가 아님: $registryManifest"
    } else {
        $registryHash = (
            Get-FileHash -Algorithm SHA256 -LiteralPath $registry
        ).Hash.ToLowerInvariant()
        if ($registryHash -ne [string]$registryData.outputs.registry.sha256) {
            throw "기존 registry SHA256 불일치: $registry"
        }
        $registryReusable = $true
    }
} elseif (
    (Test-Path -LiteralPath $registry) -or
    (Test-Path -LiteralPath $registryManifest)
) {
    throw "registry 부분 산출물 존재 — 자동 덮어쓰기 금지: $registryDir"
}
if ($registryReusable) {
    Say "[1/7] 현재 parser 계약의 전수 registry 재사용"
} else {
    Say "[1/7] 6개년 전수 vocabulary·사전 후보 registry"
    & $py $driver registry `
        --release-root $releaseRoot `
        --output-dir $registryDir
    if ($LASTEXITCODE -ne 0) { throw "registry 구축 실패" }
}

# 2. 연도별 5화자 × stress/control 및 정책 A/B byte-identical corpus.
Say "[2/7] A/B stress/control 표본 구성 또는 검증"
& $py $driver sample `
    --release-root $releaseRoot `
    --run-id $RunId `
    --registry $registry `
    --speakers-per-year $SpeakersPerYear
if ($LASTEXITCODE -ne 0) { throw "A/B 표본 구성 실패" }

$sampleWords = Join-Path $sharedRoot 'sample_words.txt'
$pronForms = Join-Path $sharedRoot 'sample_attested_pron_forms.txt'
$registrySubset = Join-Path $sharedRoot 'stress_registry_subset.csv'
$wordG2p = Join-Path $sharedRoot 'sample_words_g2p_1best.dict'
$pronG2p = Join-Path $sharedRoot 'attested_pron_g2p_1best.dict'
$g2pTempRoot = Join-Path $sharedRoot 'g2p_temp'
$g2pLogRoot = Join-Path $sharedRoot 'logs'
$sharedStateDir = Join-Path $sharedRoot 'state'
New-Item -ItemType Directory -Force `
    -Path $g2pLogRoot, $sharedStateDir | Out-Null

# 3. 파일럿 표본에 필요한 항목만 현재 MFA inline 계약과 같은 1-best/strict G2P.
$wordG2pMarker = Join-Path $sharedStateDir 'sample_words_g2p_done.json'
$wordG2pLog = Join-Path $g2pLogRoot 'sample_words_g2p.log'
$wordG2pTemp = Join-Path $g2pTempRoot 'words'
if (
    (Marker-FileHashMatches `
        $wordG2pMarker 'sample_words_g2p' $wordG2p)
) {
    Say "[3/7] 기존 표본 어절 G2P 완료 마커 재사용"
} else {
    if (Test-Path -LiteralPath $wordG2pMarker) {
        throw "표본 어절 G2P marker 불일치: $wordG2pMarker"
    }
    Archive-Incomplete $wordG2p $sharedRoot 'sample_words_g2p_orphan'
    Archive-Incomplete $wordG2pTemp $sharedRoot 'sample_words_g2p_temp'
    Archive-Incomplete $wordG2pLog $sharedRoot 'sample_words_g2p_log'
    Say "[3/7] 표본 어절 current G2P 1-best"
    $wordArgs = @(
        'g2p', $sampleWords, $g2pModel, $wordG2p,
        '--num_pronunciations', '1',
        '--strict_graphemes',
        '--sorted',
        '--temporary_directory', $wordG2pTemp,
        '--num_jobs', "$NumJobs",
        '--clean'
    )
    $code = Invoke-MfaLogged $wordArgs $wordG2pLog $sharedRoot
    if ($code -ne 0) { throw "표본 어절 G2P 실패(exit=$code)" }
    if (
        -not (Test-Path -LiteralPath $wordG2p -PathType Leaf) -or
        (Get-Item -LiteralPath $wordG2p).Length -eq 0
    ) {
        throw "표본 어절 G2P 출력 누락/0바이트: $wordG2p"
    }
    Write-Marker $wordG2pMarker 'sample_words_g2p' @{
        output = $wordG2p
        sha256 = (
            Get-FileHash -Algorithm SHA256 -LiteralPath $wordG2p
        ).Hash.ToLowerInvariant()
        num_pronunciations = 1
        strict_graphemes = $true
    } $sharedRoot
}
$pronG2pMarker = Join-Path $sharedStateDir 'attested_pron_g2p_done.json'
$pronG2pLog = Join-Path $g2pLogRoot 'attested_pron_g2p.log'
$pronG2pTemp = Join-Path $g2pTempRoot 'pron_forms'
if (
    (Marker-FileHashMatches `
        $pronG2pMarker 'attested_pron_g2p' $pronG2p)
) {
    Say "[4/7] 기존 사전 발음 phone encoding 완료 마커 재사용"
} else {
    if (Test-Path -LiteralPath $pronG2pMarker) {
        throw "사전 발음 G2P marker 불일치: $pronG2pMarker"
    }
    Archive-Incomplete $pronG2p $sharedRoot 'attested_pron_g2p_orphan'
    Archive-Incomplete $pronG2pTemp $sharedRoot 'attested_pron_g2p_temp'
    Archive-Incomplete $pronG2pLog $sharedRoot 'attested_pron_g2p_log'
    Say "[4/7] 사전 한글 발음의 current phone encoding 1-best"
    $pronArgs = @(
        'g2p', $pronForms, $g2pModel, $pronG2p,
        '--num_pronunciations', '1',
        '--strict_graphemes',
        '--sorted',
        '--temporary_directory', $pronG2pTemp,
        '--num_jobs', "$NumJobs",
        '--clean'
    )
    $code = Invoke-MfaLogged $pronArgs $pronG2pLog $sharedRoot
    if ($code -ne 0) { throw "사전 발음 phone encoding 실패(exit=$code)" }
    if (
        -not (Test-Path -LiteralPath $pronG2p -PathType Leaf) -or
        (Get-Item -LiteralPath $pronG2p).Length -eq 0
    ) {
        throw "사전 발음 G2P 출력 누락/0바이트: $pronG2p"
    }
    Write-Marker $pronG2pMarker 'attested_pron_g2p' @{
        output = $pronG2p
        sha256 = (
            Get-FileHash -Algorithm SHA256 -LiteralPath $pronG2p
        ).Hash.ToLowerInvariant()
        num_pronunciations = 1
        strict_graphemes = $true
    } $sharedRoot
}

# 4. 정책 A/B 파생사전. 자동 채택하지 않는다.
$policyADict = Join-Path $lexiconDir 'policy_A_baseline_cache.dict'
$policyBDict = Join-Path $lexiconDir 'policy_B_attested_variants.dict'
$diffCsv = Join-Path $lexiconDir 'policy_B_added_variants.csv'
$lexiconManifest = Join-Path $lexiconDir 'pilot_lexicon_manifest.json'
if (
    (Test-Path -LiteralPath $policyADict -PathType Leaf) -and
    (Test-Path -LiteralPath $policyBDict -PathType Leaf) -and
    (Test-Path -LiteralPath $diffCsv -PathType Leaf) -and
    (Test-Path -LiteralPath $lexiconManifest -PathType Leaf)
) {
    $lexiconData = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $lexiconManifest | ConvertFrom-Json
    if ($lexiconData.status -ne 'needs_manual_review') {
        throw "A/B lexicon manifest 상태 불일치: $lexiconManifest"
    }
    foreach ($check in @(
        @($policyADict, [string]$lexiconData.outputs.policy_a.sha256),
        @($policyBDict, [string]$lexiconData.outputs.policy_b.sha256),
        @($diffCsv, [string]$lexiconData.outputs.diff.sha256)
    )) {
        $actualHash = (
            Get-FileHash -Algorithm SHA256 -LiteralPath $check[0]
        ).Hash.ToLowerInvariant()
        if ($actualHash -ne $check[1]) {
            throw "A/B lexicon SHA256 불일치: $($check[0])"
        }
    }
    Say "[5/7] 기존 검증 A/B 파생사전 재사용"
} elseif (Test-Path -LiteralPath $lexiconDir) {
    $existingLexiconFiles = (
        Get-ChildItem -LiteralPath $lexiconDir -Force -ErrorAction SilentlyContinue |
        Measure-Object
    ).Count
    if ($existingLexiconFiles -gt 0) {
        throw "A/B 사전 부분 산출물 존재 — 자동 덮어쓰기 금지: $lexiconDir"
    }
} else {
    New-Item -ItemType Directory -Path $lexiconDir | Out-Null
}
if (-not (Test-Path -LiteralPath $lexiconManifest -PathType Leaf)) {
    Say "[5/7] 정책 A/B 표본 파생사전 생성·phone gate"
    & $py $driver lexicons `
        --release-root $releaseRoot `
        --base-dictionary $baseDict `
        --acoustic-model $acousticModel `
        --sample-words $sampleWords `
        --registry-subset $registrySubset `
        --word-g2p $wordG2p `
        --pron-g2p $pronG2p `
        --output-dir $lexiconDir
    if ($LASTEXITCODE -ne 0) { throw "A/B 파생사전 생성 실패" }
}

# 5. 같은 WAV/lab을 A/B 사전만 바꿔 정렬하고 기존 4-tier finalizer로 QC.
foreach ($policy in @('A', 'B')) {
    $policyRoot = $policyRoots[$policy]
    $dictionary = if ($policy -eq 'A') { $policyADict } else { $policyBDict }
    $stateDir = Join-Path $policyRoot 'state'
    $logDir = Join-Path $policyRoot 'logs'
    New-Item -ItemType Directory -Force -Path $stateDir, $logDir | Out-Null
    $alignMarker = Join-Path $stateDir 'align_done.json'
    $rawOut = Join-Path $policyRoot 'mfa_raw'
    if (Marker-Matches $alignMarker "align_policy_$policy") {
        Say "[6/7] 정책 $policy align 완료 마커 확인"
    } else {
        if (Test-Path -LiteralPath $alignMarker) {
            throw "정책 $policy align marker 불일치: $alignMarker"
        }
        $alignTemp = Join-Path $policyRoot 'temp\align'
        $alignLog = Join-Path $logDir 'align.log'
        Archive-Incomplete $rawOut $policyRoot 'align_orphan_output'
        Archive-Incomplete $alignTemp $policyRoot 'align_orphan_temp'
        Archive-Incomplete $alignLog $policyRoot 'align_orphan_log'
        $corpus = Join-Path $policyRoot 'corpus'
        $expected = (
            Get-ChildItem -LiteralPath $corpus -Recurse -File -Filter '*.lab' |
            Measure-Object
        ).Count
        $alignArgs = @(
            'align', $corpus, $dictionary, $acousticModel, $rawOut,
            '--no_tokenization',
            '--temporary_directory', $alignTemp,
            '--num_jobs', "$NumJobs",
            '--output_format', 'long_textgrid',
            '--clean'
        )
        Say "[6/7] 정책 $policy MFA align (${expected}발화)"
        $code = Invoke-MfaLogged $alignArgs $alignLog $policyRoot
        if ($code -ne 0) {
            throw "정책 $policy MFA align 실패(exit=$code): $alignLog"
        }
        $actual = (
            Get-ChildItem -LiteralPath $rawOut -Recurse -File `
                -Filter '*.TextGrid' | Measure-Object
        ).Count
        $alignMode = 'default_beam_10_40'
        if ($actual -ne $expected) {
            Say "정책 $policy 부분 성공 $actual/$expected — 확대 beam 재시도"
            Archive-Incomplete $rawOut $policyRoot 'align_default_partial'
            Archive-Incomplete $alignTemp $policyRoot 'align_default_temp'
            Archive-Incomplete $alignLog $policyRoot 'align_default_log'
            $retryTemp = Join-Path $policyRoot 'temp\align_retry_beam100_400'
            $retryLog = Join-Path $logDir 'align_retry_beam100_400.log'
            $retryArgs = @(
                'align', $corpus, $dictionary, $acousticModel, $rawOut,
                '--no_tokenization',
                '--temporary_directory', $retryTemp,
                '--num_jobs', "$NumJobs",
                '--output_format', 'long_textgrid',
                '--beam', '100',
                '--retry_beam', '400',
                '--clean'
            )
            $code = Invoke-MfaLogged $retryArgs $retryLog $policyRoot
            if ($code -ne 0) {
                throw "정책 $policy 확대 beam 실패(exit=$code)"
            }
            $actual = (
                Get-ChildItem -LiteralPath $rawOut -Recurse -File `
                    -Filter '*.TextGrid' | Measure-Object
            ).Count
            $alignMode = 'retry_beam_100_400'
            if ($actual -ne $expected) {
                throw "정책 $policy 확대 beam 후 부분 성공: $actual/$expected"
            }
            $alignLog = $retryLog
        }
        Write-Marker $alignMarker "align_policy_$policy" @{
            policy = $policy
            dictionary = $dictionary
            corpus = $corpus
            textgrids = $actual
            expected = $expected
            num_jobs = $NumJobs
            align_mode = $alignMode
            log = $alignLog
        } $policyRoot
    }

    $finalMarker = Join-Path $stateDir 'finalize_done.json'
    if (Marker-Matches $finalMarker "finalize_policy_$policy") {
        Say "정책 $policy 4-tier/QC 완료 마커 확인"
    } else {
        $years = @('2020', '2021', '2022', '2023', '2024', '2025')
        foreach ($year in $years) {
            & $py $finalizer --run-root $policyRoot --year $year
            if ($LASTEXITCODE -ne 0) {
                throw "정책 $policy $year 4-tier/QC 실패"
            }
        }
        & $py $finalizer --run-root $policyRoot --summarize --years @years
        if ($LASTEXITCODE -ne 0) {
            throw "정책 $policy 전체 QC 요약 실패"
        }
        Write-Marker $finalMarker "finalize_policy_$policy" @{
            policy = $policy
            results = (Join-Path $policyRoot 'RESULTS.md')
        } $policyRoot
    }
}

# 6. 자동 비교는 차이를 기술할 뿐 승자를 정하지 않는다.
$compareMarker = Join-Path $resultRoot 'comparison_done.json'
if (Marker-Matches $compareMarker 'compare_ab') {
    Say "[7/7] 기존 A/B 비교 결과 재사용"
} else {
    if (Test-Path -LiteralPath $comparisonDir) {
        $comparisonFiles = (
            Get-ChildItem -LiteralPath $comparisonDir -Force `
                -ErrorAction SilentlyContinue | Measure-Object
        ).Count
        if ($comparisonFiles -gt 0) {
            Archive-Incomplete $comparisonDir $resultRoot `
                'comparison_incomplete'
        }
    }
    Say "[7/7] A/B phone열·경계 비교"
    & $py $driver compare `
        --release-root $releaseRoot `
        --selection-manifest (Join-Path $sharedRoot 'selection_manifest.csv') `
        --diff-csv $diffCsv `
        --policy-a-root $policyRoots.A `
        --policy-b-root $policyRoots.B `
        --output-dir $comparisonDir
    if ($LASTEXITCODE -ne 0) { throw "A/B 비교 실패" }
    Write-Marker $compareMarker 'compare_ab' @{
        comparison = (Join-Path $comparisonDir 'RESULTS.md')
        decision = 'manual_review_required'
    } $resultRoot
}

Say "A/B 파일럿 자동 단계 완료 — 아직 정책을 채택하지 않음"
Say "먼저 열 파일: $(Join-Path $comparisonDir 'RESULTS.md')"
Say "발화별 A/B 경로: $(Join-Path $comparisonDir 'ab_utterance_comparison.csv')"
exit 0
