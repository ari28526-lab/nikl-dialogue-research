# 연도별 10발화·실제 화자 5명 G2P MFA end-to-end 파일럿
# 원본은 읽기만 하고 D:\mfa_eojeol\pilots\year10_speaker5\<run_id>에
# WAV/lab, 관련 CSV, MFA 원출력, 표준 4-tier, QC, 로그를 모두 격리한다.

param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string[]]$Years = @('2020','2021','2022','2023','2024','2025'),
    [ValidateRange(1,100)]
    [int]$UtterancesPerYear = 10,
    [ValidateRange(1,50)]
    [int]$SpeakersPerYear = 5,
    [ValidateRange(0,16)]
    [int]$NumJobs = 0,
    [string]$RunId,
    [string]$Seed = 'speaker5_year10_v1'
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root 'config\paths.json'
try {
    $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 |
           ConvertFrom-Json
    function Expand-CfgPath($value) {
        return [IO.Path]::GetFullPath(
            [Environment]::ExpandEnvironmentVariables(
                ([string]$value).Replace('/', '\')
            )
        )
    }
    $py = Expand-CfgPath $cfg.pipeline_python
    $stateRoot = Expand-CfgPath $cfg.mfa_state
} catch {
    Write-Error "config/paths.json 해석 실패: $($_.Exception.Message)"
    exit 1
}

if ($UtterancesPerYear % $SpeakersPerYear -ne 0) {
    Write-Error 'UtterancesPerYear는 SpeakersPerYear의 배수여야 합니다.'
    exit 1
}
if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = 'pilot_year10_speaker5_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
}
if ($RunId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
    Write-Error "RunId는 영문자·숫자로 시작하고 영문자·숫자·._-만 써야 함: $RunId"
    exit 1
}
if ($NumJobs -eq 0) {
    $NumJobs = [Math]::Min(4, [Environment]::ProcessorCount)
}

$envRoot = Join-Path $env:USERPROFILE 'miniforge3\envs\mfa'
$mfa = Join-Path $envRoot 'Scripts\mfa.exe'
$env:Path = "$envRoot;$envRoot\Library\bin;$envRoot\Scripts;$envRoot\bin;" +
            $env:Path
$pydir = Join-Path $PSScriptRoot 'python'
$pilotBase = Join-Path $stateRoot 'pilots\year10_speaker5'
$runRoot = Join-Path $pilotBase $RunId
$projectLogDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $projectLogDir | Out-Null

function Say($message) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message) `
        -ForegroundColor Cyan
}
function Assert-RunChild($path) {
    $resolved = [IO.Path]::GetFullPath($path).TrimEnd('\')
    $allowed = [IO.Path]::GetFullPath($runRoot).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
        throw "파일럿 실행 폴더 경계 위반: $resolved (허용 루트 $runRoot)"
    }
}
function Read-Marker($path, $year, $stage) {
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    try {
        $marker = Get-Content -LiteralPath $path -Raw -Encoding UTF8 |
                  ConvertFrom-Json
        return (
            $marker.run_id -eq $RunId -and
            $marker.year -eq $year -and
            $marker.stage -eq $stage -and
            $marker.g2p_model -eq 'korean_mfa'
        )
    } catch {
        return $false
    }
}
function Write-Marker($path, $year, $stage, $details) {
    Assert-RunChild $path
    $temp = "$path.$PID.partial"
    $payload = [ordered]@{
        run_id = $RunId
        year = $year
        stage = $stage
        g2p_model = 'korean_mfa'
        completed_at = (Get-Date).ToString('o')
        git_commit = (& git -C $root rev-parse HEAD 2>$null)
        details = $details
    }
    $payload | ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $path -Force
}
function Archive-PartialDirectory($path, $year, $stage) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    Assert-RunChild $path
    $archive = Join-Path $runRoot (
        'archive_failed\' + (Get-Date -Format 'yyyyMMdd_HHmmss') +
        "\${stage}\${year}"
    )
    Assert-RunChild $archive
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $archive) |
        Out-Null
    Move-Item -LiteralPath $path -Destination $archive
    Say "$year 이전 미완료 $stage 보존: $archive"
}
function Archive-RunFile($path, $year, $stage) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    Assert-RunChild $path
    $archiveDir = Join-Path $runRoot (
        'archive_failed\' + (Get-Date -Format 'yyyyMMdd_HHmmss') +
        "\${stage}\${year}"
    )
    Assert-RunChild $archiveDir
    New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null
    $archive = Join-Path $archiveDir (Split-Path $path -Leaf)
    Move-Item -LiteralPath $path -Destination $archive
    Say "$year 이전 미완료 $stage 로그 보존: $archive"
}
function Invoke-MfaLogged($arguments, $logPath) {
    Assert-RunChild $logPath
    & $mfa @arguments 2>&1 |
        Tee-Object -FilePath $logPath |
        ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

# 어떤 D: 경로도 만들기 전에 SSD 정본인지 먼저 확인한다.
$dLabel = $null
if (Get-Command Get-Volume -ErrorAction SilentlyContinue) {
    $dLabel = (Get-Volume -DriveLetter D -ErrorAction SilentlyContinue).
              FileSystemLabel
}
if ([string]::IsNullOrEmpty($dLabel)) {
    try { $dLabel = ([IO.DriveInfo]::new('D:\')).VolumeLabel } catch {}
}
if ($dLabel -ne 'DATA_SSD') {
    Write-Error "D: 볼륨 라벨이 DATA_SSD가 아님(현재 '$dLabel'). 파일 생성 전 중단."
    exit 1
}
foreach ($path in @($py, $mfa,
    (Join-Path $pydir 'build_stratified_mfa_pilot.py'),
    (Join-Path $pydir 'finalize_stratified_mfa_pilot.py'),
    (Join-Path $pydir 'verify_mfa_install.py'))) {
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Error "필수 실행파일 없음: $path"
        exit 1
    }
}
foreach ($model in @(
    (Join-Path $env:USERPROFILE 'Documents\MFA\pretrained_models\acoustic\korean_mfa.zip'),
    (Join-Path $env:USERPROFILE 'Documents\MFA\pretrained_models\dictionary\korean_mfa.dict'),
    (Join-Path $env:USERPROFILE 'Documents\MFA\pretrained_models\g2p\korean_mfa.zip')
)) {
    if (-not (Test-Path -LiteralPath $model)) {
        Write-Error "korean_mfa 모델 없음: $model"
        exit 1
    }
}

Say "파일럿 시작: run_id=$RunId"
Say ("대상=$($Years -join ', '), 연도당 ${UtterancesPerYear}발화, " +
     "${SpeakersPerYear}실제화자, num_jobs=$NumJobs")
Say "모든 산출물: $runRoot"

$patchReport = Join-Path $projectLogDir (
    "mfa_pilot_install_$($RunId)_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
)
& $py (Join-Path $pydir 'verify_mfa_install.py') --json-output $patchReport
if ($LASTEXITCODE -ne 0) {
    Write-Error "MFA 필수 패치 검증 실패. 실행하지 않음: $patchReport"
    exit 1
}

# 1. 실제 speaker_id 층화 표본 + 관련 CSV 구성. 완료 manifest가 있으면 검증 후 재사용.
$buildArgs = @(
    (Join-Path $pydir 'build_stratified_mfa_pilot.py'),
    '--run-root', $runRoot,
    '--utterances-per-year', "$UtterancesPerYear",
    '--speakers-per-year', "$SpeakersPerYear",
    '--seed', $Seed,
    '--years'
) + $Years
& $py @buildArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error '층화 표본/관련 CSV 구성 실패. MFA를 시작하지 않음.'
    exit 1
}
$selectionManifest = Join-Path $runRoot 'selection_manifest.csv'
if (-not (Test-Path -LiteralPath $selectionManifest)) {
    Write-Error "선정 manifest가 생성되지 않음: $selectionManifest"
    exit 1
}

$logDir = Join-Path $runRoot 'logs'
$stateDir = Join-Path $runRoot 'state'
$tempDir = Join-Path $runRoot 'temp'
foreach ($path in @($logDir, $stateDir, $tempDir)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

foreach ($year in $Years) {
    Say "===== $year 시작 ====="
    $corpus = Join-Path $runRoot "corpus\$year"
    $expected = (Get-ChildItem -LiteralPath $corpus -Recurse -File -Filter '*.lab' |
                 Measure-Object).Count
    $actualSpeakers = (Get-ChildItem -LiteralPath $corpus -Directory |
                       Measure-Object).Count
    if ($expected -ne $UtterancesPerYear -or
        $actualSpeakers -ne $SpeakersPerYear) {
        Write-Error "$year 입력 균형 실패: lab=$expected, 화자폴더=$actualSpeakers"
        exit 1
    }

    # 2. 입력 QC. MFA 3.4 validate는 align의 --no_tokenization 옵션이 없어서
    # 한국어 corpus에 python-mecab-ko를 강제한다(2026-07-24 실제 실패 확인).
    # 이 파일럿은 builder가 WAV 헤더·lab·CSV·형태소TG 대응을 전수 검사하고,
    # 여기서 화자/발화 수를 재검사한 뒤 실제 align은 --no_tokenization+G2P로
    # 수행한다. 불필요한 토크나이저 의존성 설치보다 본 파이프라인과 같은 경로다.
    $inputMarker = Join-Path $stateDir "$year.input_qc_done.json"
    if (Read-Marker $inputMarker $year 'input_qc') {
        Say "$year 입력 QC 완료 마커 확인 — 건너뜀"
    } else {
        if (Test-Path -LiteralPath $inputMarker) {
            Write-Error "$year input QC 마커 내용 불일치: $inputMarker"
            exit 1
        }
        Say "$year 입력 QC 통과: ${expected}발화 / ${actualSpeakers}실제화자"
        Write-Marker $inputMarker $year 'input_qc' @{
            corpus = $corpus
            utterances = $expected
            actual_speaker_folders = $actualSpeakers
            manifest = $selectionManifest
            mfa_validate = 'not_used'
            reason = 'MFA 3.4 validate lacks --no_tokenization; align uses it'
        }
    }

    # 3. G2P MFA 정렬. 미완료 원출력은 지우지 않고 run 내부 archive로 이동한다.
    $alignMarker = Join-Path $stateDir "$year.align_done.json"
    $rawOut = Join-Path $runRoot "mfa_raw\$year"
    if (Read-Marker $alignMarker $year 'align') {
        Say "$year G2P align 완료 마커 확인 — 건너뜀"
    } else {
        if (Test-Path -LiteralPath $alignMarker) {
            Write-Error "$year align 마커 내용 불일치: $alignMarker"
            exit 1
        }
        $alignTemp = Join-Path $tempDir "align_$year"
        $alignLog = Join-Path $logDir "$year.align.log"
        Archive-PartialDirectory $rawOut $year 'align_orphan_output'
        Archive-PartialDirectory $alignTemp $year 'align_orphan_temp'
        Archive-RunFile $alignLog $year 'align_orphan_log'
        $alignArgs = @(
            'align', $corpus, 'korean_mfa', 'korean_mfa', $rawOut,
            '--g2p_model_path', 'korean_mfa',
            '--no_tokenization',
            '--temporary_directory', $alignTemp,
            '--num_jobs', "$NumJobs",
            '--output_format', 'long_textgrid',
            '--clean'
        )
        Say "$year [1/2] G2P MFA align"
        $code = Invoke-MfaLogged $alignArgs $alignLog
        if ($code -ne 0) {
            Write-Error "$year MFA align 실패(exit $code): $alignLog"
            exit 1
        }
        $rawCount = (Get-ChildItem -LiteralPath $rawOut -Recurse -File `
                     -Filter '*.TextGrid' | Measure-Object).Count
        $alignMode = 'default_beam_10_40'
        if ($rawCount -ne $expected) {
            # MFA가 난정렬 발화를 누락하고도 exit 0을 반환할 수 있다. 잘못 매핑된
            # WAV 세션은 builder duration 가드가 먼저 차단한다. 대응이 검증된
            # 표본의 정렬만 기존 회수 파이프라인과 같은 확대 beam으로 1회 재시도.
            Say "$year MFA 부분 성공 감지: TextGrid=$rawCount/$expected"
            Say "$year 기본 beam 출력·temp·로그 보존 후 beam 100/400 재시도"
            Archive-PartialDirectory $rawOut $year 'align_default_partial'
            Archive-PartialDirectory $alignTemp $year 'align_default_temp'
            Archive-RunFile $alignLog $year 'align_default_log'

            $retryTemp = Join-Path $tempDir "align_retry_beam100_400_$year"
            $retryLog = Join-Path $logDir "$year.align_retry_beam100_400.log"
            Archive-PartialDirectory $retryTemp $year 'align_retry_orphan_temp'
            Archive-RunFile $retryLog $year 'align_retry_orphan_log'
            $retryArgs = @(
                'align', $corpus, 'korean_mfa', 'korean_mfa', $rawOut,
                '--g2p_model_path', 'korean_mfa',
                '--no_tokenization',
                '--temporary_directory', $retryTemp,
                '--num_jobs', "$NumJobs",
                '--output_format', 'long_textgrid',
                '--beam', '100',
                '--retry_beam', '400',
                '--clean'
            )
            $code = Invoke-MfaLogged $retryArgs $retryLog
            if ($code -ne 0) {
                Write-Error "$year 확대 beam MFA 실패(exit $code): $retryLog"
                exit 1
            }
            $rawCount = (Get-ChildItem -LiteralPath $rawOut -Recurse -File `
                         -Filter '*.TextGrid' | Measure-Object).Count
            $alignMode = 'retry_beam_100_400'
            $alignLog = $retryLog
            if ($rawCount -ne $expected) {
                Write-Error (
                    "$year 확대 beam 후에도 부분 성공: " +
                    "TextGrid=$rawCount/$expected. 출력·temp 보존 후 중단"
                )
                exit 1
            }
        }
        Write-Marker $alignMarker $year 'align' @{
            corpus = $corpus
            output = $rawOut
            log = $alignLog
            textgrids = $rawCount
            num_jobs = $NumJobs
            align_mode = $alignMode
        }
    }

    # 4. 기존 형태소 경계를 결합한 표준 4-tier + 발화별 전수 QC.
    $finalMarker = Join-Path $stateDir "$year.finalize_done.json"
    if (Read-Marker $finalMarker $year 'finalize') {
        Say "$year 최종 4-tier/QC 완료 마커 확인 — 건너뜀"
    } else {
        if (Test-Path -LiteralPath $finalMarker) {
            Write-Error "$year finalize 마커 내용 불일치: $finalMarker"
            exit 1
        }
        Say "$year [2/2] 표준 4-tier 병합 + 전수 QC"
        & $py (Join-Path $pydir 'finalize_stratified_mfa_pilot.py') `
            --run-root $runRoot --year $year
        if ($LASTEXITCODE -ne 0) {
            Write-Error "$year 최종 병합/QC 실패. 원출력은 보존됨."
            exit 1
        }
        $finalCount = (Get-ChildItem -LiteralPath `
                      (Join-Path $runRoot "textgrid_4tier\$year") `
                      -Recurse -File -Filter '*.TextGrid' |
                      Measure-Object).Count
        if ($finalCount -ne $expected) {
            Write-Error "$year 최종 TextGrid 수 불일치: $finalCount/$expected"
            exit 1
        }
        Write-Marker $finalMarker $year 'finalize' @{
            output = (Join-Path $runRoot "textgrid_4tier\$year")
            qc = (Join-Path $runRoot "qc\$year`_utterance_qc.csv")
            textgrids = $finalCount
        }
    }
    Say "===== $year 통과 ====="
}

& $py (Join-Path $pydir 'finalize_stratified_mfa_pilot.py') `
    --run-root $runRoot --summarize --years @Years
if ($LASTEXITCODE -ne 0) {
    Write-Error '전체 파일럿 요약 판정 실패. 연도별 QC를 확인하십시오.'
    exit 1
}
Say "전체 완료: $runRoot"
Say "먼저 열 파일: $(Join-Path $runRoot 'RESULTS.md')"
exit 0
