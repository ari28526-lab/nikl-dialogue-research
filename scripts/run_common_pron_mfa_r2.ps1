#Requires -Version 5.1
<#
2020–2025 전체 동결 어휘로 최신 Jamo 공통 MFA 사전 r2를 만든다.

- 공식 동결 acoustic v3.3.0, Jamo G2P v3.2.0, dictionary의 SHA를 실행
  직전에 검증한다.
- 기본사전 OOV를 1-best strict G2P로 한 번만 계산한다.
- 미지원 grapheme는 U+11B3(종성 ㄽ) 4어절만 허용하고, 같은 Jamo 모델
  입력에서 U+11AF+U+11BA로 완전분해한다.
- 4어절의 원 표층키를 복원하고 연구자 검토표 승인이 있기 전에는
  final 사전과 연도별 MFA 사용 승인을 만들지 않는다.
- exit 0인데도 FST no-path로 표층형이 누락되면, 명시된 표준 발음
  재철자 후보를 같은 동결 Jamo 모델에 넣어 얻은 phone을 연구자가
  승인한 뒤에만 누락 키를 추가한다. 기존 모델 출력은 대체하지 않는다.
- 다른 모델, 우리말샘 변이, spn은 생산 사전에 넣지 않는다.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^common_pron_mfa_r2_[0-9]{8}$')]
    [string]$ReleaseId = 'common_pron_mfa_r2_20260728',

    [ValidatePattern('^common_pron_pilot_[a-z0-9_]+_[0-9]{8}$')]
    [string]$SourceReleaseId = 'common_pron_pilot_full6y_20260728',

    [ValidateRange(1000, 100000)]
    [int]$ShardSize = 25000,

    [ValidateRange(1, 16)]
    [int]$NumJobs = 4,

    [ValidateRange(10, 500)]
    [int]$MinimumFreeGiB = 30,

    [switch]$PrepareOnly,
    [switch]$SpecialOnly
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
        [Environment]::ExpandEnvironmentVariables(
            $Value.Replace('/', '\')
        )
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
            $old = Get-Content -Raw -Encoding UTF8 `
                -LiteralPath $LockPath | ConvertFrom-Json
            $live = [int]$old.pid -gt 0 -and $null -ne (
                Get-Process -Id ([int]$old.pid) `
                    -ErrorAction SilentlyContinue
            )
        } catch {}
        if ($live) {
            throw "공통 G2P 실행 lock 사용 중: $LockPath"
        }
        $archive = Join-Path $CommonRoot (
            'archive_stale_locks\{0}_{1}.json' -f
            (Get-Date -Format 'yyyyMMdd_HHmmss'), $ReleaseId
        )
        Assert-Child $archive $CommonRoot
        New-Item -ItemType Directory -Force `
            -Path (Split-Path -Parent $archive) | Out-Null
        Move-Item -LiteralPath $LockPath -Destination $archive
    }
    $temp = "$LockPath.$PID.partial"
    [ordered]@{
        schema_version = 2
        release_id = $ReleaseId
        pipeline = 'latest_jamo_common_pron_mfa_r2'
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
        $lock = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $LockPath | ConvertFrom-Json
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

$commonRoot = Expand-CfgPath ([string]$config.common_pron_home)
$expectedRoot = [IO.Path]::GetFullPath('D:\mfa_common_pron')
if ($commonRoot.TrimEnd('\') -ne $expectedRoot.TrimEnd('\')) {
    throw "공통 발음 root 안전 차단: $commonRoot"
}
$drive = [IO.DriveInfo]::new('D')
if (-not $drive.IsReady -or $drive.VolumeLabel -ne 'DATA_SSD') {
    throw "D: DATA_SSD 안전 차단"
}
$freeGiB = [math]::Round($drive.AvailableFreeSpace / 1GB, 3)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw "D: 공간 부족: ${freeGiB}GiB < ${MinimumFreeGiB}GiB"
}
if (
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -match '^(mfa|python|conda|robocopy|7z)$'
        }
) {
    throw "MFA/G2P/archive 동시 실행 금지"
}

$bulkLock = Join-Path (
    Expand-CfgPath ([string]$config.mfa_state)
) 'locks\pre_mfa_bulk.lock'
if (Test-Path -LiteralPath $bulkLock) {
    throw "연도별 MFA lock 존재 — 공통 G2P 동시 실행 금지: $bulkLock"
}

$sourceRoot = Join-Path (
    Join-Path $commonRoot 'releases'
) $SourceReleaseId
$releaseRoot = Join-Path (
    Join-Path $commonRoot 'releases'
) $ReleaseId
Assert-Child $sourceRoot $commonRoot
Assert-Child $releaseRoot $commonRoot
$sourceVocabulary = Join-Path (
    Join-Path $sourceRoot '01_vocabulary'
) 'common_vocabulary_2020_2025.csv'
$sourceManifest = Join-Path (
    Join-Path $sourceRoot '01_vocabulary'
) 'vocabulary_manifest.json'

$py = Expand-CfgPath ([string]$config.pipeline_python)
$envRoot = Join-Path $env:USERPROFILE 'miniforge3\envs\mfa'
$mfa = Join-Path $envRoot 'Scripts\mfa.exe'
$env:Path = (
    "$envRoot;$envRoot\Library\bin;$envRoot\Scripts;$envRoot\bin;" +
    $env:Path
)
$env:PYTHONUTF8 = '1'
$driver = Join-Path (
    $PSScriptRoot
) 'python\build_common_pron_mfa_lexicon.py'
$pinDriver = Join-Path (
    $PSScriptRoot
) 'python\verify_frozen_mfa_bundle.py'
$noPathDriver = Join-Path (
    $PSScriptRoot
) 'python\common_pron_no_path_review.py'
$noPathMapping = Join-Path (
    $projectRoot
) 'config\common_pron_g2p_no_path_exceptions.csv'
$bundleContract = Join-Path (
    $projectRoot
) 'outputs\reports\korean_mfa_latest_jamo_bundle_20260728.json'
foreach ($path in @(
    $sourceVocabulary, $sourceManifest, $py, $mfa, $driver,
    $pinDriver, $noPathDriver, $noPathMapping, $bundleContract
)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "필수 입력/실행 파일 없음: $path"
    }
}
$bundle = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath $bundleContract | ConvertFrom-Json
$acousticModel = [IO.Path]::GetFullPath(
    [string]$bundle.outputs.acoustic_model.path
)
$g2pModel = [IO.Path]::GetFullPath(
    [string]$bundle.outputs.g2p_model.path
)
$baseDictionary = [IO.Path]::GetFullPath(
    [string]$bundle.outputs.dictionary.path
)
foreach ($path in @($acousticModel, $g2pModel, $baseDictionary)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "동결 모델 실물 없음: $path"
    }
}

$lockPath = Join-Path $commonRoot "locks\$ReleaseId.lock"
Acquire-Lock $lockPath $commonRoot
try {
    New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
    $pinReport = Join-Path (
        Join-Path $releaseRoot '00_contract'
    ) 'frozen_model_pin.json'
    New-Item -ItemType Directory -Force `
        -Path (Split-Path -Parent $pinReport) | Out-Null
    & $py $pinDriver `
        --contract $bundleContract `
        --acoustic-model $acousticModel `
        --g2p-model $g2pModel `
        --base-dictionary $baseDictionary `
        --output $pinReport
    if ($LASTEXITCODE -ne 0) {
        throw "최신 acoustic/Jamo/dictionary SHA pin 실패"
    }

    Say (
        "공통사전 r2: acoustic v3.3.0 + Jamo G2P v3.2.0; " +
        "release=$ReleaseId, jobs=$NumJobs, D free=${freeGiB}GiB"
    )
    & $py $driver prepare `
        --vocabulary $sourceVocabulary `
        --vocabulary-manifest $sourceManifest `
        --base-dictionary $baseDictionary `
        --g2p-model $g2pModel `
        --acoustic-model $acousticModel `
        --release-root $releaseRoot `
        --shard-size $ShardSize
    if ($LASTEXITCODE -ne 0) {
        throw "공통사전 r2 prepare 실패"
    }
    $prepareManifestPath = Join-Path (
        Join-Path $releaseRoot '00_contract'
    ) 'prepare_manifest.json'
    $prepared = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $prepareManifestPath | ConvertFrom-Json
    $mappingPath = Join-Path $releaseRoot '01_g2p\jamo_ls_mapping.csv'
    $mapping = @(Import-Csv -LiteralPath $mappingPath -Encoding UTF8)
    $expectedSpecial = @(
        '외곬수적인', '외곬을', '외곬의', '천구백칤비육'
    )
    $actualSpecial = @($mapping.token | Sort-Object)
    if (
        [int]$prepared.counts.g2p_unsupported_other_words -ne 0 -or
        [int]$prepared.counts.g2p_jamo_ls_rewrite_words -ne 4 -or
        @(Compare-Object (
            $expectedSpecial | Sort-Object
        ) $actualSpecial).Count -ne 0
    ) {
        throw "Jamo grapheme gate 불일치: U+11B3 정확히 4어절이어야 함"
    }
    Say (
        "어휘 $($prepared.counts.vocabulary_words); OOV " +
        "$($prepared.counts.observed_oov_words); 표준 shard " +
        "$($prepared.counts.shards); U+11B3 rewrite 4"
    )
    if ($PrepareOnly) {
        Say "코드 준비만 완료. r2 사전 실물은 아직 없음"
        exit 76
    }

    $inputDir = Join-Path $releaseRoot '01_g2p\input_shards'
    $outputDir = Join-Path $releaseRoot '01_g2p\output_shards'
    $reportDir = Join-Path $releaseRoot '_state\shard_reports'
    $logDir = Join-Path $releaseRoot 'logs'
    $tempDir = Join-Path $releaseRoot 'work\g2p_temp'
    foreach ($path in @($outputDir, $reportDir, $logDir, $tempDir)) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
    }

    # 동일 Jamo 모델의 U+11B3 전용 미니 shard를 먼저 만든다.
    $specialInput = Join-Path $releaseRoot '01_g2p\jamo_ls_model_input.txt'
    $specialRaw = Join-Path $outputDir 'jamo_ls_raw.dict'
    $specialReport = Join-Path $reportDir 'jamo_ls_raw.json'
    $specialLog = Join-Path $logDir 'g2p_jamo_ls.log'
    $specialTemp = Join-Path $tempDir 'jamo_ls'
    $specialValid = $false
    if (Test-Path -LiteralPath $specialRaw -PathType Leaf) {
        & $py $driver verify-shard `
            --input-shard $specialInput `
            --output-shard $specialRaw `
            --acoustic-model $acousticModel `
            --report $specialReport
        $specialValid = $LASTEXITCODE -eq 0
    }
    if (-not $specialValid) {
        Archive-Incomplete `
            @($specialRaw, $specialReport, $specialLog, $specialTemp) `
            $releaseRoot 'jamo_ls_invalid_existing'
        $specialArgs = @(
            'g2p', $specialInput, $g2pModel, $specialRaw,
            '--num_pronunciations', '1',
            '--strict_graphemes',
            '--temporary_directory', $specialTemp,
            '--num_jobs', "$NumJobs",
            '--clean'
        )
        $specialCode = Invoke-MfaLogged `
            $specialArgs $specialLog $releaseRoot
        if ($specialCode -ne 0) {
            throw "Jamo ㄽ 미니 shard 실패(exit=$specialCode)"
        }
        & $py $driver verify-shard `
            --input-shard $specialInput `
            --output-shard $specialRaw `
            --acoustic-model $acousticModel `
            --report $specialReport
        if ($LASTEXITCODE -ne 0) {
            throw "Jamo ㄽ 미니 shard 검증 실패"
        }
    }
    & $py $driver restore-jamo-ls `
        --release-root $releaseRoot `
        --acoustic-model $acousticModel
    if ($LASTEXITCODE -ne 0) {
        throw "Jamo ㄽ 표층키 복원 실패"
    }
    $reviewPath = Join-Path (
        Join-Path $releaseRoot '03_review'
    ) 'jamo_ls_researcher_review.csv'
    Say "Jamo ㄽ 4건 후보 검토표: $reviewPath"
    if ($SpecialOnly) {
        Say "SpecialOnly 완료. r2 사전 실물은 아직 없음"
        exit 76
    }

    # 최신 Jamo FST가 exit 0이면서 0행을 내는 알려진 no-path 표층형은
    # 별도 검토표로 관리한다. 이 단계는 후보만 만들며 자동 승인하지 않는다.
    $noPathInput = Join-Path (
        Join-Path $releaseRoot '01_g2p'
    ) 'known_no_path_respelled.txt'
    $noPathRaw = Join-Path $outputDir 'known_no_path_respelled_raw.dict'
    $noPathReviewPath = Join-Path (
        Join-Path $releaseRoot '03_review'
    ) 'g2p_no_path_researcher_review.csv'
    $noPathReviewManifest = Join-Path (
        Join-Path $releaseRoot '00_contract'
    ) 'g2p_no_path_review_manifest.json'
    $noPathLog = Join-Path $logDir 'g2p_known_no_path_respelled.log'
    $noPathTemp = Join-Path $tempDir 'known_no_path_respelled'
    & $py $noPathDriver prepare-input `
        --mapping $noPathMapping `
        --output $noPathInput
    if ($LASTEXITCODE -ne 0) {
        throw "known no-path 재철자 입력 준비 실패"
    }
    if (-not (Test-Path -LiteralPath $noPathRaw -PathType Leaf)) {
        $noPathArguments = @(
            'g2p', $noPathInput, $g2pModel, $noPathRaw,
            '--num_pronunciations', '1',
            '--strict_graphemes',
            '--temporary_directory', $noPathTemp,
            '--num_jobs', "$NumJobs",
            '--clean'
        )
        $noPathCode = Invoke-MfaLogged `
            $noPathArguments $noPathLog $releaseRoot
        if ($noPathCode -ne 0) {
            throw "known no-path 재철자 G2P 실패(exit=$noPathCode)"
        }
    }
    & $py $noPathDriver build-review `
        --mapping $noPathMapping `
        --raw-dictionary $noPathRaw `
        --acoustic-model $acousticModel `
        --review $noPathReviewPath `
        --manifest $noPathReviewManifest
    if ($LASTEXITCODE -ne 0) {
        throw "known no-path 연구자 검토표 생성/검증 실패"
    }
    Say "G2P no-path 후보 검토표: $noPathReviewPath"

    $shards = @($prepared.outputs.input_shards)
    $completed = 0
    $approvalPendingShards = [Collections.Generic.List[int]]::new()
    $unknownMissingShards = [Collections.Generic.List[int]]::new()
    foreach ($shard in $shards) {
        $index = [int]$shard.shard_index
        $inputPath = Join-Path $inputDir ('oov_{0:D5}.txt' -f $index)
        $outputPath = Join-Path $outputDir (
            'oov_{0:D5}.dict' -f $index
        )
        $reportPath = Join-Path $reportDir (
            'oov_{0:D5}.json' -f $index
        )
        $logPath = Join-Path $logDir (
            'g2p_oov_{0:D5}.log' -f $index
        )
        $shardTemp = Join-Path $tempDir ('oov_{0:D5}' -f $index)
        $valid = $false
        if (Test-Path -LiteralPath $outputPath -PathType Leaf) {
            & $py $driver verify-shard `
                --input-shard $inputPath `
                --output-shard $outputPath `
                --acoustic-model $acousticModel `
                --report $reportPath
            $valid = $LASTEXITCODE -eq 0
            if (-not $valid) {
                $repairAttempt = Join-Path (
                    Join-Path (
                        Join-Path $releaseRoot '_state\no_path_repairs'
                    ) ([IO.Path]::GetFileNameWithoutExtension($outputPath))
                ) 'last_attempt.json'
                & $py $noPathDriver repair-shard `
                    --input-shard $inputPath `
                    --output-shard $outputPath `
                    --acoustic-model $acousticModel `
                    --review $noPathReviewPath `
                    --release-root $releaseRoot `
                    --attempt-report $repairAttempt
                $repairCode = $LASTEXITCODE
                if ($repairCode -eq 76) {
                    $approvalPendingShards.Add($index)
                    Say (
                        "shard $index partial 보존·승인 대기; " +
                        "다음 shard로 계속"
                    )
                    continue
                }
                if ($repairCode -eq 77) {
                    $unknownMissingShards.Add($index)
                    Say (
                        "shard $index partial 보존·미등록 누락어 기록; " +
                        "다음 shard로 계속: $repairAttempt"
                    )
                    continue
                }
                if ($repairCode -ne 0) {
                    throw (
                        "G2P shard $index no-path 안전 보수 실패" +
                        "(exit=$repairCode): $repairAttempt"
                    )
                }
                & $py $driver verify-shard `
                    --input-shard $inputPath `
                    --output-shard $outputPath `
                    --acoustic-model $acousticModel `
                    --report $reportPath
                $valid = $LASTEXITCODE -eq 0
                if (-not $valid) {
                    throw "G2P shard $index 보수 뒤 완전성 검사 실패"
                }
                Say "shard $index 승인된 no-path 누락만 보수 완료"
            }
        }
        if ($valid) {
            $completed += 1
            Say "shard $index/$($shards.Count) 검증본 재사용"
            continue
        }
        Archive-Incomplete `
            @($outputPath, $reportPath, $logPath, $shardTemp) `
            $releaseRoot ('shard_{0:D5}_invalid_existing' -f $index)
        Say "shard $index/$($shards.Count) G2P 시작"
        $arguments = @(
            'g2p', $inputPath, $g2pModel, $outputPath,
            '--num_pronunciations', '1',
            '--strict_graphemes',
            '--temporary_directory', $shardTemp,
            '--num_jobs', "$NumJobs",
            '--clean'
        )
        $code = Invoke-MfaLogged $arguments $logPath $releaseRoot
        if ($code -ne 0) {
            throw "G2P shard $index 실패(exit=$code)"
        }
        & $py $driver verify-shard `
            --input-shard $inputPath `
            --output-shard $outputPath `
            --acoustic-model $acousticModel `
            --report $reportPath
        if ($LASTEXITCODE -ne 0) {
            $repairAttempt = Join-Path (
                    Join-Path (
                        Join-Path $releaseRoot '_state\no_path_repairs'
                    ) ([IO.Path]::GetFileNameWithoutExtension($outputPath))
            ) 'last_attempt.json'
            & $py $noPathDriver repair-shard `
                --input-shard $inputPath `
                --output-shard $outputPath `
                --acoustic-model $acousticModel `
                --review $noPathReviewPath `
                --release-root $releaseRoot `
                --attempt-report $repairAttempt
            $repairCode = $LASTEXITCODE
            if ($repairCode -eq 76) {
                $approvalPendingShards.Add($index)
                Say (
                    "shard $index partial 보존·승인 대기; " +
                    "다음 shard로 계속"
                )
                continue
            }
            if ($repairCode -eq 77) {
                $unknownMissingShards.Add($index)
                Say (
                    "shard $index partial 보존·미등록 누락어 기록; " +
                    "다음 shard로 계속: $repairAttempt"
                )
                continue
            }
            if ($repairCode -ne 0) {
                throw (
                    "G2P shard $index no-path 안전 보수 실패" +
                    "(exit=$repairCode): $repairAttempt"
                )
            }
            & $py $driver verify-shard `
                --input-shard $inputPath `
                --output-shard $outputPath `
                --acoustic-model $acousticModel `
                --report $reportPath
            if ($LASTEXITCODE -ne 0) {
                throw "G2P shard $index 보수 뒤 완전성 검사 실패"
            }
            Say "shard $index 승인된 no-path 누락만 보수 완료"
        }
        $completed += 1
        Say "shard $index 완료 ($completed/$($shards.Count))"
    }

    if (
        $approvalPendingShards.Count -gt 0 -or
        $unknownMissingShards.Count -gt 0
    ) {
        Say (
            "전체 shard 계산은 계속했지만 final은 보류: 승인 대기=" +
            "$($approvalPendingShards -join ','); 미등록 누락=" +
            "$($unknownMissingShards -join ','). 검토 후 같은 명령으로 " +
            "partial shard만 보수"
        )
        exit 76
    }

    $review = @(Import-Csv -LiteralPath $reviewPath -Encoding UTF8)
    $approved = @($review | Where-Object {
        $_.decision -eq 'approved'
    })
    if ($review.Count -ne 4 -or $approved.Count -ne 4) {
        Say (
            "표준 G2P는 완료됐지만 Jamo ㄽ 4건 연구자 승인이 미완료. " +
            "finalize·연도별 MFA를 시작하지 않음"
        )
        exit 76
    }

    & $py $driver finalize --release-root $releaseRoot
    if ($LASTEXITCODE -ne 0) {
        throw "공통사전 r2 finalize 실패"
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
        [int]$final.counts.g2p_jamo_ls_rewrite_words -ne 4
    ) {
        throw "공통사전 r2 final hard gate 실패"
    }
    Say "r2 사전 실물 완료: $finalManifest"
    Say (
        "아직 연도별 MFA 사용 승인은 아님. 2020·2021 전수 차이 inventory와 " +
        "최종 adoption contract가 별도로 필요함"
    )
} finally {
    Release-Lock $lockPath
}
