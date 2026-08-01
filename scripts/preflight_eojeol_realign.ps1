# preflight_eojeol_realign.ps1 — run_eojeol_realign.ps1 실행 전 자가검진 (2026-07-24 신설)
# 목적: 배치를 몇 시간 돌린 뒤에야 드러나던 문제(모델 부재·평면 코퍼스·디스크 부족·
#   라벨 오인·orphan temp·헬퍼 부재)를 실행 전에 한 번에 점검. 읽기 전용 — 어떤 파일도
#   수정하지 않음(리포트 파일 생성만). 러너와 동일한 경로·가드 로직을 그대로 복제.
# 실행: powershell -ExecutionPolicy Bypass -File <리포>\scripts\preflight_eojeol_realign.ps1
# 결과: 콘솔 + 리포 logs\preflight_YYYYMMDD_HHMMSS.log. FAIL 있으면 exit 1.

param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year,
    [string]$SearchMasterRoot = "",
    [ValidateSet('korean_mfa','common_pron_mfa_r2_latest_jamo')]
    [string]$ExpectedPronunciationMode = 'korean_mfa',
    [switch]$PreferD
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root "config\paths.json"
try {
    $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    function Expand-CfgPath($value) {
        return [IO.Path]::GetFullPath(
            [Environment]::ExpandEnvironmentVariables(
                ([string]$value).Replace('/', '\')
            )
        )
    }
    $wavRoot = Join-Path (Expand-CfgPath $cfg.wav) "individual"
    $layersRoot = Expand-CfgPath $cfg.layers
    $stateRoot = Expand-CfgPath $cfg.mfa_state
    $doneDir = Join-Path $stateRoot "done"
    # D: 라벨 검증 전 잘못 연결된 드라이브에 쓰지 않도록 preflight 보고서는 리포에 둔다.
    $logDir = Join-Path $root "logs"
    $tmpPrimary = Expand-CfgPath $cfg.mfa_temp_primary
    $tmpSecondary = Expand-CfgPath $cfg.mfa_temp_secondary
    $outPrimary = Expand-CfgPath $cfg.mfa_output_primary
    $outSecondary = Expand-CfgPath $cfg.mfa_output_secondary
    $g2pStage = if (
        $ExpectedPronunciationMode -eq 'common_pron_mfa_r2_latest_jamo'
    ) {
        Expand-CfgPath $cfg.textgrid_research_v2_staging
    } else {
        Expand-CfgPath $cfg.textgrid_eojeol_staging
    }
    $py = Expand-CfgPath $cfg.pipeline_python
    if ([string]::IsNullOrWhiteSpace($SearchMasterRoot)) {
        $searchMasterRoot = Expand-CfgPath $cfg.search_master
    } else {
        $searchMasterRoot = [IO.Path]::GetFullPath($SearchMasterRoot)
    }
} catch {
    Write-Error "config/paths.json 해석 실패: $($_.Exception.Message)"
    exit 1
}
$envRoot = Join-Path $env:USERPROFILE "miniforge3\envs\mfa"
$years = if ($Year) { @($Year) } else {
    @('2020','2021','2022','2023','2024','2025')
}
$pydir   = Join-Path $PSScriptRoot "python"

New-Item -ItemType Directory -Force $logDir | Out-Null
$report = Join-Path $logDir ("preflight_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")
$script:fail = 0; $script:warn = 0
function Out-Line($m) { Write-Host $m; Add-Content $report $m -Encoding UTF8 }
function OK($m)   { Out-Line ("  [OK]   " + $m) }
function WARN($m) { $script:warn++; Out-Line ("  [WARN] " + $m) }
function FAIL($m) { $script:fail++; Out-Line ("  [FAIL] " + $m) }

Out-Line "== preflight_eojeol_realign $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =="
Out-Line "대상 연도: $($years -join ', ')"
Out-Line "연구 TextGrid staging: $g2pStage"
Out-Line "pre-MFA search master: $searchMasterRoot"
Out-Line "expected pronunciation mode: $ExpectedPronunciationMode"
Out-Line ("작업 드라이브 정책: " + $(if ($PreferD) {
    "PreferD — 신규 MFA temp/output은 D:"
} else {
    "자동 — C: 여유 문턱 미달 시 D:"
}))

# [1] 실행파일·python 헬퍼 존재
Out-Line "[1] 실행파일·헬퍼"
$mfa = Join-Path $envRoot "Scripts\mfa.exe"
if (Test-Path $mfa) { OK "mfa.exe: $mfa" } else { FAIL "mfa.exe 없음: $mfa" }
if (Test-Path $py) {
    & $py --version 2>&1 | ForEach-Object { OK "pipeline_python: $py ($_)" }
    if ($LASTEXITCODE -ne 0) { FAIL "pipeline_python 실행 실패(exit $LASTEXITCODE): $py" }
} else { FAIL "pipeline_python 없음: $py" }
foreach ($h in 'realign_eojeol_build_corpus.py','quarantine_bad_wavs.py',
                 'realign_eojeol_merge_output.py','export_mfa_db_4tier.py',
                 'export_mfa_db_research_6tier.py',
                 'inspect_mfa_db_checkpoint.py') {
    if (Test-Path (Join-Path $pydir $h)) { OK $h } else { FAIL "python 헬퍼 없음: $h" }
}
if ((Test-Path $py) -and (Test-Path (Join-Path $pydir 'verify_mfa_install.py'))) {
    $patchReport = Join-Path $logDir ("mfa_install_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
    & $py (Join-Path $pydir 'verify_mfa_install.py') --json-output $patchReport |
        ForEach-Object { Out-Line ("  " + $_) }
    if ($LASTEXITCODE -eq 0) { OK "MFA 프로젝트 필수 패치 검증 통과" }
    else { FAIL "MFA 프로젝트 필수 패치 누락 — 대량 실행 금지" }
} else { FAIL "verify_mfa_install.py 또는 pipeline_python 없음" }

# [2] korean_mfa 모델 3종 (음향·사전·g2p) — MFA 모델 저장소 기본 경로에서 확인
Out-Line "[2] korean_mfa 모델 (acoustic/dictionary/g2p)"
$mfaRoot = if ($env:MFA_ROOT_DIR) { $env:MFA_ROOT_DIR } else { Join-Path $env:USERPROFILE "Documents\MFA" }
$models = @{ acoustic = 'korean_mfa.zip'; dictionary = 'korean_mfa.dict'; g2p = 'korean_mfa.zip' }
foreach ($kind in @($models.Keys)) {
    $mPath = Join-Path $mfaRoot ("pretrained_models\" + $kind + "\" + $models[$kind])
    if (Test-Path $mPath) { OK ($kind + ": " + $mPath) }
    else { FAIL ($kind + " 모델 없음: " + $mPath) }
}

# [3] D: 볼륨 라벨 — 러너와 동일 가드(Get-Volume + CIM 폴백)
Out-Line "[3] D: 볼륨 라벨"
$dLabel = $null
if (Get-Command Get-Volume -ErrorAction SilentlyContinue) {   # Storage 모듈 없는 셸(브리지)에서 오류 노이즈 방지
    $dLabel = (Get-Volume -DriveLetter D -ErrorAction SilentlyContinue).FileSystemLabel
}
if ([string]::IsNullOrEmpty($dLabel)) {
    $dLabel = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='D:'" -ErrorAction SilentlyContinue).VolumeName
}
if ([string]::IsNullOrEmpty($dLabel)) {
    try { $dLabel = ([IO.DriveInfo]::new('D:\')).VolumeLabel } catch {}
}
if ($dLabel -eq 'DATA_SSD') { OK "라벨 DATA_SSD 확인" }
else { FAIL "D: 라벨이 DATA_SSD 아님(현재 '$dLabel') — HDD 오인 위험, 러너도 중단됨" }

# [4] 여유 공간. 신규 연도는 2021 55GB, 나머지 45GB를 시작 문턱으로 쓴다.
# PreferD에서는 C: 용량으로 D: 실행을 막지 않고, 선택된 D:만 FAIL 판정한다.
Out-Line "[4] 여유 공간"
$freeByDrive = @{}
foreach ($d in 'C','D') {
    try {
        $driveInfo = [IO.DriveInfo]::new("${d}:\")
        if (-not $driveInfo.IsReady) { throw "not ready" }
        $free = [math]::Round($driveInfo.AvailableFreeSpace / 1GB, 1)
        $freeByDrive[$d] = $free
    } catch { FAIL "드라이브 ${d}: 조회 실패"; continue }
    if ($PreferD -and $d -eq 'C') {
        OK "${d}: ${free}GB (PreferD 신규 작업에는 사용하지 않음)"
    } elseif (-not $PreferD) {
        if ($free -ge 45) { OK "${d}: ${free}GB" }
        elseif ($free -ge 30) { WARN "${d}: ${free}GB (45GB 미만 — 신규 temp 배치 빠듯)" }
        else { WARN "${d}: ${free}GB (30GB 미만 — 이 드라이브는 temp로 못 씀)" }
    }
}
if ($PreferD -and $freeByDrive.ContainsKey('D')) {
    $requiredD = if ($years -contains '2021') { 55 } else { 45 }
    if ([double]$freeByDrive['D'] -ge $requiredD) {
        OK "PreferD: D: $($freeByDrive['D'])GB >= 시작 문턱 ${requiredD}GB"
    } else {
        FAIL "PreferD: D: $($freeByDrive['D'])GB < 시작 문턱 ${requiredD}GB"
    }
}

# [5] wav 코퍼스 — 연도별 존재·세션(=화자) 구조. 지연 열거라 첫 항목만 보고 즉시 반환(가벼움).
Out-Line "[5] wav 코퍼스 (연도별 존재·세션 구조)"
foreach ($y in $years) {
    $yDir = Join-Path $wavRoot $y
    if (-not (Test-Path $yDir)) { FAIL "$y wav 루트 없음: $yDir"; continue }
    $flat = [IO.Directory]::EnumerateFiles($yDir, "*.wav") | Select-Object -First 1
    if ($flat) { FAIL "$y 평면 구조(wav가 연도 루트에 직접) — restructure_wav_sessions.py 먼저" }
    else {
        $firstSess = [IO.Directory]::EnumerateDirectories($yDir) | Select-Object -First 1
        if ($firstSess) { OK "$y 세션 구조 확인(예: $(Split-Path $firstSess -Leaf))" }
        else { FAIL "$y 폴더가 비어 있음: $yDir" }
    }
}

# [6] pre-MFA 입력 계약 — 구 search master로 숫자·기호를 지운 lab을 만들지 않음.
Out-Line "[6] pre-MFA search master 입력 계약"
$metaPath = Join-Path $searchMasterRoot "_build_meta.json"
$metaOK = $false
if (-not (Test-Path -LiteralPath $metaPath)) {
    FAIL "pre-MFA _build_meta.json 없음: $metaPath"
} else {
    try {
        $meta = Get-Content -LiteralPath $metaPath -Raw -Encoding UTF8 |
                ConvertFrom-Json
        if ($meta.status -eq 'success') {
            $metaOK = $true
            OK "search master build status=success"
        } else {
            FAIL "search master build 미통과(status=$($meta.status)): $metaPath"
        }
    } catch {
        FAIL "search master build meta 손상: $metaPath"
    }
}
foreach ($y in $years) {
    $yearDir = Join-Path $searchMasterRoot $y
    if (-not (Test-Path -LiteralPath $yearDir)) {
        FAIL "$y search master 폴더 없음: $yearDir"
        continue
    }
    $sample = Get-ChildItem -LiteralPath $yearDir -Filter *.csv -File |
              Where-Object { -not $_.Name.StartsWith('_') } |
              Select-Object -First 1
    if (-not $sample) {
        FAIL "$y search master CSV 0개: $yearDir"
        continue
    }
    $sourceNames = @{
        '2020' = 'NIKL_DIALOGUE_2020_v1.4'
        '2021' = 'NIKL_DIALOGUE_2021_v1.1'
        '2022' = 'NIKL_DIALOGUE_2022_v1.0_JSON'
        '2023' = 'NIKL_DIALOGUE_2023_v1.1'
        '2024' = 'NIKL_DIALOGUE_2024_v1.0'
        '2025' = 'NIKL_DIALOGUE_2025_v1.0'
    }
    $sourceYearDir = Join-Path (
        Join-Path $layersRoot '01_bareun_raw'
    ) $sourceNames[$y]
    $searchCount = @(
        Get-ChildItem -LiteralPath $yearDir -Filter *.csv -File |
        Where-Object { -not $_.Name.StartsWith('_') }
    ).Count
    $sourceCount = @(
        Get-ChildItem -LiteralPath $sourceYearDir -Filter *.csv -File |
        Where-Object { -not $_.Name.StartsWith('_') }
    ).Count
    if ($sourceCount -le 0 -or $searchCount -ne $sourceCount) {
        FAIL "$y search master 세션 coverage 불일치: search=$searchCount source=$sourceCount"
    } else {
        OK "$y 세션 coverage $searchCount/$sourceCount"
    }
    $header = Get-Content -LiteralPath $sample.FullName -Encoding UTF8 -TotalCount 1
    $required = @(
        'utt_id','form','pron_reference_form',
        'pron_reference_source','pron_reference_status'
    )
    $missing = @($required | Where-Object {
        $header -notmatch "(^|,)$([regex]::Escape($_))(,|$)"
    })
    if ($missing.Count -gt 0) {
        FAIL "$y pre-MFA 필수 열 누락($($missing -join ',')): $($sample.FullName)"
    } else {
        OK "$y reference-form 입력 열 확인"
    }
}

# [7] 완료 마커·이어가기 상태 — temp/원출력 위치까지 종합해 연도별 재개 시나리오 판정
Out-Line "[7] 완료 마커·이어가기 상태"
foreach ($y in $years) {
    $a  = Test-Path (Join-Path $doneDir "$y.align_done")
    $m  = Test-Path (Join-Path $doneDir "$y.merge_done")
    $alignExportMode = ""
    $tC = Test-Path (Join-Path $tmpPrimary $y)
    $tD = Test-Path (Join-Path $tmpSecondary $y)
    $oC = Test-Path (Join-Path $outPrimary $y)
    $oD = Test-Path (Join-Path $outSecondary $y)
    $directFinalYear = Join-Path $g2pStage $y
    $directFinalPresent = Test-Path -LiteralPath $directFinalYear
    $st = (
        "align_done=$a merge_done=$m temp(C=$tC,D=$tD) " +
        "mfa_out(C=$oC,D=$oD) final_staging=$directFinalPresent"
    )
    if ($a -or $m) {
        foreach ($marker in @((Join-Path $doneDir "$y.align_done"),
                              (Join-Path $doneDir "$y.merge_done"))) {
            if (-not (Test-Path $marker)) { continue }
            try {
                $markerData = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 |
                              ConvertFrom-Json
                $markerStage = if ($marker -like '*.align_done') { 'align' } else { 'merge' }
                $markerOK = (
                    $markerData.year -eq $y -and
                    $markerData.stage -eq $markerStage -and
                    $markerData.g2p_model -eq
                        $ExpectedPronunciationMode -and
                    -not [string]::IsNullOrWhiteSpace(
                        [string]$markerData.details.input_contract_id
                    ) -and
                    [IO.Path]::GetFullPath(
                        [string]$markerData.details.search_master_root
                    ).TrimEnd('\') -eq
                    [IO.Path]::GetFullPath($searchMasterRoot).TrimEnd('\')
                )
                if ($markerOK -and $markerStage -eq 'merge') {
                    $recordedStage = [string]$markerData.details.staging_output_root
                    $markerOK = (
                        -not [string]::IsNullOrWhiteSpace($recordedStage) -and
                        [IO.Path]::GetFullPath($recordedStage).TrimEnd('\') -eq
                        [IO.Path]::GetFullPath($g2pStage).TrimEnd('\')
                    )
                }
                if ($markerOK -and $markerStage -eq 'align') {
                    $alignExportMode = [string]$markerData.details.export_mode
                }
                if (-not $markerOK) {
                    FAIL "$y 완료 마커 내용 불일치: $marker"
                }
            } catch {
                FAIL "$y 레거시/손상 완료 마커(검증 정보 없음): $marker — 자동 완료로 인정하지 않음"
            }
        }
    }
    $contractPath = Join-Path $stateRoot "input_contracts\$y.json"
    if (($tC -or $tD) -and -not (Test-Path -LiteralPath $contractPath)) {
        WARN "$y temp는 있으나 입력 계약 기록 없음 — 러너가 stale temp로 보존 격리 후 clean 시작"
    } elseif (($tC -or $tD) -and (Test-Path -LiteralPath $contractPath)) {
        try {
            $tempContract = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 |
                            ConvertFrom-Json
            $recordedSearch = [IO.Path]::GetFullPath(
                [string]$tempContract.search_master_root
            ).TrimEnd('\')
            if ($recordedSearch -ne
                [IO.Path]::GetFullPath($searchMasterRoot).TrimEnd('\')) {
                WARN "$y temp 입력 search master가 현재와 다름 — 러너가 stale temp로 보존 격리"
            } else {
                OK "$y temp 입력 계약 경로 일치"
            }
        } catch {
            WARN "$y temp 입력 계약 손상 — 러너가 stale temp로 보존 격리"
        }
    }
    if ((-not $a) -and (-not $m) -and $directFinalPresent) {
        FAIL (
            "$y final staging은 있으나 완료 marker가 전무함 — 재정렬 금지. " +
            "direct report·retained DB·TABLES_MANIFEST를 검증한 뒤 marker만 " +
            "복구해야 함. $st"
        )
    }
    elseif ($a -and $m) { OK "$y 마커 파일 존재(위 내용 검증도 통과해야 완료) — $st" }
    elseif ($tC -and $tD) { WARN "$y temp가 C·D 양쪽에 있음 — 러너는 D:를 우선. 오래된 쪽 수동 확인 필요. $st" }
    elseif (
        $a -and -not $m -and
        $alignExportMode -in @(
            'direct_db_4tier', 'direct_db_research_6tier_v1'
        ) -and
        -not ($oC -or $oD)
    ) {
        if ($directFinalPresent) {
            FAIL (
                "$y direct DB align marker와 final staging은 있으나 " +
                "merge marker가 없음 — marker 삭제·재정렬 금지. final staging, " +
                "direct report, retained DB를 검증해 merge marker만 복구해야 함. $st"
            )
        } else {
            FAIL (
                "$y direct DB align marker 뒤 완료 기록이 중단됨 — " +
                "marker 삭제·재정렬 전에 retained DB와 partial을 보존·점검해야 함. $st"
            )
        }
    }
    elseif ($a -and -not ($oC -or $oD)) { FAIL "$y align_done인데 병합용 MFA 원출력이 어느 드라이브에도 없음 — 마커 삭제 후 재정렬 필요. $st" }
    elseif ((-not $a) -and ($oC -or $oD) -and -not ($tC -or $tD)) { FAIL "$y 정렬 마커·temp 없이 MFA 원출력만 남음 — stale/부분 출력 판별 전 실행 금지. $st" }
    elseif ($tC -or $tD -or $a) { OK "$y 이어가기 가능 상태 — $st" }
    else { OK "$y 신규(처음부터) — $st" }
}

Out-Line "== 요약: FAIL $script:fail / WARN $script:warn — 리포트: $report =="
if ($script:fail -gt 0) { exit 1 } else { exit 0 }
