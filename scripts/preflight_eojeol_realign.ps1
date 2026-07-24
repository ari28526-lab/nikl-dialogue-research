# preflight_eojeol_realign.ps1 — run_eojeol_realign.ps1 실행 전 자가검진 (2026-07-24 신설)
# 목적: 배치를 몇 시간 돌린 뒤에야 드러나던 문제(모델 부재·평면 코퍼스·디스크 부족·
#   라벨 오인·orphan temp·헬퍼 부재)를 실행 전에 한 번에 점검. 읽기 전용 — 어떤 파일도
#   수정하지 않음(리포트 파일 생성만). 러너와 동일한 경로·가드 로직을 그대로 복제.
# 실행: powershell -ExecutionPolicy Bypass -File <리포>\scripts\preflight_eojeol_realign.ps1
# 결과: 콘솔 + 리포 logs\preflight_YYYYMMDD_HHMMSS.log. FAIL 있으면 exit 1.

param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year
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
    $stateRoot = Expand-CfgPath $cfg.mfa_state
    $doneDir = Join-Path $stateRoot "done"
    # D: 라벨 검증 전 잘못 연결된 드라이브에 쓰지 않도록 preflight 보고서는 리포에 둔다.
    $logDir = Join-Path $root "logs"
    $tmpPrimary = Expand-CfgPath $cfg.mfa_temp_primary
    $tmpSecondary = Expand-CfgPath $cfg.mfa_temp_secondary
    $outPrimary = Expand-CfgPath $cfg.mfa_output_primary
    $outSecondary = Expand-CfgPath $cfg.mfa_output_secondary
    $g2pStage = Expand-CfgPath $cfg.textgrid_eojeol_staging
    $py = Expand-CfgPath $cfg.pipeline_python
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
Out-Line "G2P 4-tier staging: $g2pStage"

# [1] 실행파일·python 헬퍼 존재
Out-Line "[1] 실행파일·헬퍼"
$mfa = Join-Path $envRoot "Scripts\mfa.exe"
if (Test-Path $mfa) { OK "mfa.exe: $mfa" } else { FAIL "mfa.exe 없음: $mfa" }
if (Test-Path $py) {
    & $py --version 2>&1 | ForEach-Object { OK "pipeline_python: $py ($_)" }
    if ($LASTEXITCODE -ne 0) { FAIL "pipeline_python 실행 실패(exit $LASTEXITCODE): $py" }
} else { FAIL "pipeline_python 없음: $py" }
foreach ($h in 'realign_eojeol_build_corpus.py','quarantine_bad_wavs.py','realign_eojeol_merge_output.py') {
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

# [4] 여유 공간 (러너 가드: temp 드라이브 최소 30GB, 신규 연도 C: 선택 문턱 40GB)
Out-Line "[4] 여유 공간"
foreach ($d in 'C','D') {
    try {
        $driveInfo = [IO.DriveInfo]::new("${d}:\")
        if (-not $driveInfo.IsReady) { throw "not ready" }
        $free = [math]::Round($driveInfo.AvailableFreeSpace / 1GB, 1)
    } catch { FAIL "드라이브 ${d}: 조회 실패"; continue }
    if ($free -ge 40) { OK "${d}: ${free}GB" }
    elseif ($free -ge 30) { WARN "${d}: ${free}GB (30~40GB — temp 배치 빠듯)" }
    else { WARN "${d}: ${free}GB (30GB 미만 — 이 드라이브는 temp로 못 씀)" }
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

# [6] 완료 마커·이어가기 상태 — temp/원출력 위치까지 종합해 연도별 재개 시나리오 판정
Out-Line "[6] 완료 마커·이어가기 상태"
foreach ($y in $years) {
    $a  = Test-Path (Join-Path $doneDir "$y.align_done")
    $m  = Test-Path (Join-Path $doneDir "$y.merge_done")
    $tC = Test-Path (Join-Path $tmpPrimary $y)
    $tD = Test-Path (Join-Path $tmpSecondary $y)
    $oC = Test-Path (Join-Path $outPrimary $y)
    $oD = Test-Path (Join-Path $outSecondary $y)
    $st = "align_done=$a merge_done=$m temp(C=$tC,D=$tD) mfa_out(C=$oC,D=$oD)"
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
                    $markerData.g2p_model -eq 'korean_mfa'
                )
                if ($markerOK -and $markerStage -eq 'merge') {
                    $recordedStage = [string]$markerData.details.staging_output_root
                    $markerOK = (
                        -not [string]::IsNullOrWhiteSpace($recordedStage) -and
                        [IO.Path]::GetFullPath($recordedStage).TrimEnd('\') -eq
                        [IO.Path]::GetFullPath($g2pStage).TrimEnd('\')
                    )
                }
                if (-not $markerOK) {
                    FAIL "$y 완료 마커 내용 불일치: $marker"
                }
            } catch {
                FAIL "$y 레거시/손상 완료 마커(검증 정보 없음): $marker — 자동 완료로 인정하지 않음"
            }
        }
    }
    if ($a -and $m) { OK "$y 마커 파일 존재(위 내용 검증도 통과해야 완료) — $st" }
    elseif ($tC -and $tD) { WARN "$y temp가 C·D 양쪽에 있음 — 러너는 C:를 우선. 오래된 쪽 수동 확인 필요. $st" }
    elseif ($a -and -not ($oC -or $oD)) { FAIL "$y align_done인데 병합용 MFA 원출력이 어느 드라이브에도 없음 — 마커 삭제 후 재정렬 필요. $st" }
    elseif ((-not $a) -and ($oC -or $oD) -and -not ($tC -or $tD)) { FAIL "$y 정렬 마커·temp 없이 MFA 원출력만 남음 — stale/부분 출력 판별 전 실행 금지. $st" }
    elseif ($tC -or $tD -or $a) { OK "$y 이어가기 가능 상태 — $st" }
    else { OK "$y 신규(처음부터) — $st" }
}

Out-Line "== 요약: FAIL $script:fail / WARN $script:warn — 리포트: $report =="
if ($script:fail -gt 0) { exit 1 } else { exit 0 }
