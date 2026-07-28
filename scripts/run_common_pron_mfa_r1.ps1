#Requires -Version 5.1
<#
2020–2025 공통 surface G2P cache와 MFA 효율화 사전 r1을 만든다.

- 기존 korean_mfa.dict 행·확률열을 그대로 보존한다.
- 관측 OOV만 같은 korean_mfa G2P 1-best/strict로 한 번 생성한다.
- 우리말샘·형태소 조건 발음은 이 MFA 생산 사전에 넣지 않는다.
- 긴 G2P는 shard별 출력·검증으로 재개한다.
- 기존 파일럿 release와 2020/2021 결과는 수정하지 않는다.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^common_pron_mfa_r1_[0-9]{8}$')]
    [string]$ReleaseId = 'common_pron_mfa_r1_20260728',

    [ValidatePattern('^common_pron_pilot_[a-z0-9_]+_[0-9]{8}$')]
    [string]$SourceReleaseId = 'common_pron_pilot_full6y_20260728',

    [ValidateRange(1000, 100000)]
    [int]$ShardSize = 25000,

    [ValidateRange(1, 16)]
    [int]$NumJobs = 0,

    [ValidateRange(10, 500)]
    [int]$MinimumFreeGiB = 30,

    [switch]$PrepareOnly
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
        throw "경로 경계 위반: $resolved (root=$Root)"
    }
}
function Invoke-MfaLogged(
    [string[]]$Arguments,
    [string]$LogPath,
    [string]$AllowedRoot
) {
    Assert-Child $LogPath $AllowedRoot
    $previous = $ErrorActionPreference
    try {
        # MFA의 정상 progress도 stderr이므로 네이티브 호출 경계에서만 완화한다.
        $ErrorActionPreference = 'Continue'
        & $script:mfa @Arguments 2>&1 |
            Tee-Object -FilePath $LogPath |
            ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return $code
}
function Archive-Incomplete(
    [string[]]$Paths,
    [string]$ReleaseRoot,
    [string]$Label
) {
    $present = @($Paths | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and
        (Test-Path -LiteralPath $_)
    })
    if ($present.Count -eq 0) { return }
    $archive = Join-Path $ReleaseRoot (
        'archive_failed\{0}\{1}' -f
        (Get-Date -Format 'yyyyMMdd_HHmmss'), $Label
    )
    Assert-Child $archive $ReleaseRoot
    New-Item -ItemType Directory -Force -Path $archive | Out-Null
    foreach ($path in $present) {
        Assert-Child $path $ReleaseRoot
        $destination = Join-Path $archive (Split-Path -Leaf $path)
        if (Test-Path -LiteralPath $destination) {
            throw "archive 충돌: $destination"
        }
        Move-Item -LiteralPath $path -Destination $destination
    }
    Say "미완료 산출물 보존: $archive"
}
function Acquire-Lock([string]$LockPath, [string]$CommonRoot) {
    Assert-Child $LockPath $CommonRoot
    New-Item -ItemType Directory -Force `
        -Path (Split-Path -Parent $LockPath) | Out-Null
    if (Test-Path -LiteralPath $LockPath) {
        $live = $false
        try {
            $old = Get-Content -Raw -Encoding UTF8 -LiteralPath $LockPath |
                ConvertFrom-Json
            if ([int]$old.pid -gt 0) {
                $live = $null -ne (
                    Get-Process -Id ([int]$old.pid) -ErrorAction SilentlyContinue
                )
            }
        } catch {}
        if ($live) {
            throw "공통 G2P 실행 lock이 이미 사용 중: $LockPath"
        }
        $archive = Join-Path $CommonRoot (
            'archive_stale_locks\{0}_{1}.json' -f
            (Get-Date -Format 'yyyyMMdd_HHmmss'), $ReleaseId
        )
        Assert-Child $archive $CommonRoot
        New-Item -ItemType Directory -Force `
            -Path (Split-Path -Parent $archive) | Out-Null
        Move-Item -LiteralPath $LockPath -Destination $archive
        Say "종료된 프로세스의 stale lock 보존: $archive"
    }
    $temp = "$LockPath.$PID.partial"
    [ordered]@{
        schema_version = 1
        release_id = $ReleaseId
        pid = $PID
        host = $env:COMPUTERNAME
        acquired_at = (Get-Date).ToString('o')
    } | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $LockPath
}
function Release-Lock([string]$LockPath) {
    if (-not (Test-Path -LiteralPath $LockPath)) { return }
    try {
        $lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $LockPath |
            ConvertFrom-Json
        if (
            [int]$lock.pid -eq $PID -and
            [string]$lock.release_id -eq $ReleaseId
        ) {
            Remove-Item -LiteralPath $LockPath -Force
        }
    } catch {
        Write-Warning "lock 해제 실패; 수동 확인 필요: $LockPath"
    }
}

if ($NumJobs -eq 0) {
    $NumJobs = [Math]::Min(4, [Environment]::ProcessorCount)
}
$commonRoot = Expand-CfgPath ([string]$config.common_pron_home)
$expectedRoot = [IO.Path]::GetFullPath('D:\mfa_common_pron')
if ($commonRoot.TrimEnd('\') -ne $expectedRoot.TrimEnd('\')) {
    throw "공통 발음 root 안전 차단: $commonRoot"
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
    throw "대량 MFA lock 존재 — 공통 G2P 동시 실행 금지: $bulkLock"
}

$sourceRoot = Join-Path (Join-Path $commonRoot 'releases') $SourceReleaseId
$releaseRoot = Join-Path (Join-Path $commonRoot 'releases') $ReleaseId
Assert-Child $sourceRoot $commonRoot
Assert-Child $releaseRoot $commonRoot
$sourceVocabulary = Join-Path (
    Join-Path $sourceRoot '01_vocabulary'
) 'common_vocabulary_2020_2025.csv'
$sourceManifest = Join-Path (
    Join-Path $sourceRoot '01_vocabulary'
) 'vocabulary_manifest.json'
foreach ($path in @($sourceVocabulary, $sourceManifest)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "공통 vocabulary 원천 없음: $path"
    }
}

$py = Expand-CfgPath ([string]$config.pipeline_python)
$envRoot = Join-Path $env:USERPROFILE 'miniforge3\envs\mfa'
$mfa = Join-Path $envRoot 'Scripts\mfa.exe'
$env:Path = (
    "$envRoot;$envRoot\Library\bin;$envRoot\Scripts;$envRoot\bin;" +
    $env:Path
)
$env:PYTHONUTF8 = '1'
$driver = Join-Path $PSScriptRoot 'python\build_common_pron_mfa_lexicon.py'
$equivalenceDriver = Join-Path (
    Join-Path $PSScriptRoot 'python'
) 'audit_common_pron_mfa_equivalence.py'
$modelRoot = Join-Path $env:USERPROFILE 'Documents\MFA\pretrained_models'
$baseDictionary = Join-Path $modelRoot 'dictionary\korean_mfa.dict'
$g2pModel = Join-Path $modelRoot 'g2p\korean_mfa.zip'
$acousticModel = Join-Path $modelRoot 'acoustic\korean_mfa.zip'
foreach ($path in @(
    $py, $mfa, $driver, $equivalenceDriver, $baseDictionary,
    $g2pModel, $acousticModel
)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "필수 실행 파일 없음: $path"
    }
}

$lockPath = Join-Path $commonRoot "locks\$ReleaseId.lock"
Acquire-Lock $lockPath $commonRoot
try {
    New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
    Say (
        "공통 MFA 사전 r1: release=$ReleaseId, shard=$ShardSize, " +
        "jobs=$NumJobs, D free=${freeGiB}GiB"
    )
    Say "정책: 기본사전 보존 + 동일 G2P 1-best만; 우리말샘 변이 0"

    & $py $driver prepare `
        --vocabulary $sourceVocabulary `
        --vocabulary-manifest $sourceManifest `
        --base-dictionary $baseDictionary `
        --g2p-model $g2pModel `
        --acoustic-model $acousticModel `
        --release-root $releaseRoot `
        --shard-size $ShardSize
    if ($LASTEXITCODE -ne 0) {
        throw "공통 G2P prepare 실패"
    }
    $prepareManifestPath = Join-Path (
        Join-Path $releaseRoot '00_contract'
    ) 'prepare_manifest.json'
    $prepared = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $prepareManifestPath | ConvertFrom-Json
    if ($prepared.status -ne 'prepared') {
        throw "prepare manifest status 불일치"
    }
    Say (
        "관측 $($prepared.counts.vocabulary_words)어절; " +
        "G2P OOV $($prepared.counts.observed_oov_words); " +
        "$($prepared.counts.shards) shards"
    )
    if ($PrepareOnly) {
        Say "PrepareOnly 완료 — G2P 계산은 시작하지 않음"
        return
    }

    $inputDir = Join-Path $releaseRoot '01_g2p\input_shards'
    $outputDir = Join-Path $releaseRoot '01_g2p\output_shards'
    $reportDir = Join-Path $releaseRoot '_state\shard_reports'
    $logDir = Join-Path $releaseRoot 'logs'
    $tempDir = Join-Path $releaseRoot 'work\g2p_temp'
    foreach ($path in @($outputDir, $reportDir, $logDir)) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
    }
    $shards = @($prepared.outputs.input_shards)
    $completed = 0
    foreach ($shard in $shards) {
        $index = [int]$shard.shard_index
        $inputPath = Join-Path $inputDir (
            'oov_{0:D5}.txt' -f $index
        )
        $outputPath = Join-Path $outputDir (
            'oov_{0:D5}.dict' -f $index
        )
        $reportPath = Join-Path $reportDir (
            'oov_{0:D5}.json' -f $index
        )
        $logPath = Join-Path $logDir (
            'g2p_oov_{0:D5}.log' -f $index
        )
        $shardTempDir = Join-Path $tempDir (
            'oov_{0:D5}' -f $index
        )
        foreach ($path in @(
            $inputPath, $outputPath, $reportPath, $logPath, $shardTempDir
        )) {
            Assert-Child $path $releaseRoot
        }

        $validExisting = $false
        if (Test-Path -LiteralPath $outputPath -PathType Leaf) {
            & $py $driver verify-shard `
                --input-shard $inputPath `
                --output-shard $outputPath `
                --acoustic-model $acousticModel `
                --report $reportPath
            $validExisting = $LASTEXITCODE -eq 0
        }
        if ($validExisting) {
            $completed += 1
            Say "shard $index/$($shards.Count) 검증된 기존 출력 재사용"
            continue
        }
        $incomplete = @(
            @(
                $outputPath, $reportPath, $logPath, $shardTempDir
            ) | Where-Object { Test-Path -LiteralPath $_ }
        )
        if ($incomplete.Count -gt 0) {
            Archive-Incomplete `
                @($outputPath, $reportPath, $logPath, $shardTempDir) `
                $releaseRoot ('shard_{0:D5}_invalid_existing' -f $index)
        }
        Say (
            "shard $index/$($shards.Count) G2P 시작 " +
            "($($shard.row_count) words)"
        )
        $arguments = @(
            'g2p', $inputPath, $g2pModel, $outputPath,
            '--num_pronunciations', '1',
            '--strict_graphemes',
            '--temporary_directory', $shardTempDir,
            '--num_jobs', "$NumJobs",
            '--clean'
        )
        $code = Invoke-MfaLogged $arguments $logPath $releaseRoot
        if ($code -ne 0) {
            Archive-Incomplete `
                @($outputPath, $reportPath, $logPath, $shardTempDir) `
                $releaseRoot ('shard_{0:D5}_mfa_failed' -f $index)
            throw "G2P shard $index 실패(exit=$code)"
        }
        & $py $driver verify-shard `
            --input-shard $inputPath `
            --output-shard $outputPath `
            --acoustic-model $acousticModel `
            --report $reportPath
        if ($LASTEXITCODE -ne 0) {
            Archive-Incomplete `
                @($outputPath, $reportPath, $logPath, $shardTempDir) `
                $releaseRoot ('shard_{0:D5}_verification_failed' -f $index)
            throw "G2P shard $index 완전성 검사 실패"
        }
        $completed += 1
        Say "shard $index 완료 ($completed/$($shards.Count))"
    }

    & $py $driver finalize --release-root $releaseRoot
    if ($LASTEXITCODE -ne 0) {
        throw "공통 MFA 사전 finalize 실패"
    }
    $finalManifest = Join-Path (
        Join-Path $releaseRoot '00_contract'
    ) 'release_manifest.json'
    $final = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $finalManifest | ConvertFrom-Json
    if (
        $final.status -ne 'success' -or
        [int]$final.counts.g2p_missing -ne 0 -or
        [int]$final.counts.g2p_spn_words -ne 0 -or
        [int]$final.counts.phone_outside_acoustic_inventory -ne 0 -or
        [int]$final.dictionary_contract.attested_dictionary_variants_added -ne 0
    ) {
        throw "최종 공통 MFA 사전 hard gate 실패"
    }
    Say "공통 MFA 사전 계산 완료: $finalManifest"

    # 공통 사전을 2022에 사용하기 전에 두 baseline을 전수 검사한다.
    # 2020 archive DB에는 word/phone interval이 없으므로 최종 4-tier 전체가
    # 실제 정렬 phone의 정본이다. 2021은 보존된 완성 DB의 후보 집합을 쓴다.
    $equivalenceDir = Join-Path $releaseRoot '03_equivalence'
    $equivalenceJson = Join-Path (
        $equivalenceDir
    ) 'common_pron_mfa_equivalence_2020_2021.json'
    $equivalenceCsv = Join-Path (
        $equivalenceDir
    ) 'common_pron_mfa_equivalence_mismatches.csv'
    $textgrid2020 = Join-Path (
        Expand-CfgPath ([string]$config.textgrid_eojeol_staging)
    ) '2020'
    $database2021 = Join-Path (
        Expand-CfgPath ([string]$config.mfa_temp_secondary)
    ) '2021\2021.db'
    $partialDatabase2020 = (
        'D:\mfa_eojeol\archive_stale_temp\20260725_141701\' +
        'C\2020\2020.db'
    )
    $qc2020 = Join-Path (
        Join-Path $projectRoot 'outputs\reports'
    ) 'AUDIT_mfa_4tier_2020_pre_mfa_v1_20260728.json'
    $integrity2021 = Join-Path (
        Join-Path $projectRoot 'outputs\reports'
    ) 'SQLITE_integrity_2021_pre_mfa_v1_20260728.json'
    foreach ($path in @(
        $textgrid2020, $partialDatabase2020, $database2021,
        $qc2020, $integrity2021
    )) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw "전수 동등성 baseline/evidence 없음: $path"
        }
    }
    Assert-Child $equivalenceJson $releaseRoot
    Assert-Child $equivalenceCsv $releaseRoot
    New-Item -ItemType Directory -Force -Path $equivalenceDir | Out-Null

    if (
        (Test-Path -LiteralPath $equivalenceJson) -xor
        (Test-Path -LiteralPath $equivalenceCsv)
    ) {
        Archive-Incomplete `
            @($equivalenceJson, $equivalenceCsv) `
            $releaseRoot 'equivalence_interrupted'
    }
    if (-not (Test-Path -LiteralPath $equivalenceJson)) {
        Say (
            '2020 TextGrid 866,196개 + 2021 완성 DB ' +
            'phone 전수 동등성 검사 시작'
        )
        & $py $equivalenceDriver `
            --common-manifest $finalManifest `
            --vocabulary $sourceVocabulary `
            --textgrid-2020-root $textgrid2020 `
            --qc-2020-report $qc2020 `
            --partial-database-2020 $partialDatabase2020 `
            --database-2021 $database2021 `
            --integrity-2021-report $integrity2021 `
            --output-json $equivalenceJson `
            --output-csv $equivalenceCsv `
            --workers $NumJobs
        if ($LASTEXITCODE -ne 0) {
            throw (
                '2020/2021 전수 phone 동등성 실패. ' +
                "공통사전 MFA 사용 금지: $equivalenceJson"
            )
        }
    } else {
        Say "기존 전수 동등성 보고서 재검증: $equivalenceJson"
    }
    $equivalence = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $equivalenceJson | ConvertFrom-Json
    $finalManifestHash = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $finalManifest
    ).Hash.ToLowerInvariant()
    $finalDictionaryHash = (
        Get-FileHash -Algorithm SHA256 `
            -LiteralPath ([string]$final.outputs.dictionary.path)
    ).Hash.ToLowerInvariant()
    if (
        $equivalence.status -ne 'passed' -or
        $equivalence.policy -ne 'no_phone_standard_change' -or
        $equivalence.baseline_2020.status -ne 'passed' -or
        $equivalence.baseline_2020_partial_db_auxiliary.status -ne
            'passed' -or
        $equivalence.baseline_2021.status -ne 'passed' -or
        -not [bool]$equivalence.gate.requires_2020_pass -or
        -not [bool]$equivalence.gate.requires_2020_partial_db_auxiliary_pass -or
        -not [bool]$equivalence.gate.requires_2021_pass -or
        -not [bool]$equivalence.gate.allow_common_dictionary_for_2022 -or
        [int]$equivalence.mismatches.rows -ne 0 -or
        $finalManifestHash -ne
            [string]$equivalence.common_release.manifest.sha256 -or
        $finalDictionaryHash -ne
            [string]$equivalence.common_release.dictionary.sha256
    ) {
        throw (
            '전수 동등성 보고서 hard gate 실패. ' +
            '2020·2021 결과를 보존한 채 원인을 먼저 조사할 것'
        )
    }
    Say (
        '2020·2021 전수 phone 동등성 통과 — ' +
        "2022 공통사전 사용 허용: $equivalenceJson"
    )
} finally {
    Release-Lock $lockPath
}
