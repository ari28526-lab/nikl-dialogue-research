# recover_reference_from_hdd.ps1 — HDD 유일본 reference 4종 → D:\00_RAW\reference 회수 (2026-07-24)
# 근거: docs\ASSETS_LEDGER.md 거점2 + "reference 4종 활용처와 D: 확보 계획".
# 원칙: HDD 원본은 절대 삭제하지 않음(역백업·유일본 보호). D: 배치(MFA) 멈춘 시간에 실행.
# 실행: powershell -ExecutionPolicy Bypass -File <리포>\scripts\recover_reference_from_hdd.ps1
# 결과: 콘솔 + <리포>\logs\recover_reference_YYYYMMDD_HHMMSS.log

$ErrorActionPreference = 'Continue'
$refs = @('00_DICTIONARY','01_NIKL_MP_v_1_1','02_NIKL_LS','NIKL_Multi-layered_2025_v1.0')
$repoLogs = Join-Path (Split-Path $PSScriptRoot -Parent) "logs"
New-Item -ItemType Directory -Force $repoLogs | Out-Null
$log = Join-Path $repoLogs ("recover_reference_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")
function L($m) { $s = "[$(Get-Date -Format 'MM-dd HH:mm:ss')] $m"; Write-Host $s; Add-Content $log $s -Encoding UTF8 }

# 가드 1: D: 라벨 = DATA_SSD (러너와 동일, Get-Volume + CIM 폴백)
$dLabel = $null
if (Get-Command Get-Volume -ErrorAction SilentlyContinue) {
    $dLabel = (Get-Volume -DriveLetter D -ErrorAction SilentlyContinue).FileSystemLabel
}
if ([string]::IsNullOrEmpty($dLabel)) {
    $dLabel = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='D:'" -ErrorAction SilentlyContinue).VolumeName
}
if ($dLabel -ne 'DATA_SSD') { L "!! D: 라벨이 DATA_SSD 아님('$dLabel') — HDD 오인 위험, 중단"; exit 1 }

# 가드 2: MFA 배치 진행 의심 시 중단 (mfa stderr가 최근 10분 내 갱신이면)
$err = Get-ChildItem "D:\mfa_eojeol\logs\mfa_*_stderr.log" -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($err -and ((Get-Date) - $err.LastWriteTime).TotalMinutes -lt 10) {
    L "!! MFA stderr가 10분 내 갱신됨(배치 진행 의심) — 배치를 멈춘 뒤 재실행"; exit 1
}

# HDD 자동 탐지: C/D 제외 드라이브 중 \00_RAW\reference\00_DICTIONARY 보유 드라이브
$hdd = $null
foreach ($dl in (Get-CimInstance Win32_LogicalDisk).DeviceID) {
    if ($dl -in @('C:','D:')) { continue }
    if (Test-Path (Join-Path $dl "00_RAW\reference\00_DICTIONARY")) { $hdd = $dl; break }
}
if (-not $hdd) { L "!! reference를 보유한 HDD 드라이브를 못 찾음 — HDD 연결 확인"; exit 1 }
L "HDD=$hdd / D: 라벨 OK / 배치 정지 확인 — 회수 시작 (robocopy /E, 원본 보존)"

$fail = 0
foreach ($r in $refs) {
    $src = Join-Path $hdd "00_RAW\reference\$r"
    $dst = "D:\00_RAW\reference\$r"
    if (-not (Test-Path $src)) { L "!! 원본 없음: $src"; $fail++; continue }
    L "복사: $src -> $dst"
    robocopy $src $dst /E /R:2 /W:5 /NP /NFL /NDL /TEE /LOG+:$log | Out-Null
    $rc = $LASTEXITCODE
    if ($rc -ge 8) { L "!! robocopy 실패(rc=$rc): $r"; $fail++ } else { L "완료(rc=$rc): $r" }
}

# 검증: 대상 4종에 파일이 실제로 존재하는지
foreach ($r in $refs) {
    $dst = "D:\00_RAW\reference\$r"
    $any = $null
    if (Test-Path $dst) {
        $any = [IO.Directory]::EnumerateFiles($dst, '*', [IO.SearchOption]::AllDirectories) |
               Select-Object -First 1
    }
    if ($any) { L "확인: $dst 파일 존재" } else { L "!! $dst 비어 있음"; $fail++ }
}

# ASSETS_LEDGER 절차 3: preflight_search_master 재실행으로 reference [OK] 판정
L "preflight_search_master.py 재실행..."
& python (Join-Path $PSScriptRoot "python\preflight_search_master.py") *>&1 |
    ForEach-Object { Add-Content $log ("  PF| " + $_) -Encoding UTF8 }
L "preflight exit=$LASTEXITCODE"

if ($fail -gt 0) { L "== 회수 미완(문제 $fail건) — 로그: $log"; exit 1 }
L "== reference 4종 회수 완료 — 로그: $log. ASSETS_LEDGER 표 갱신할 것(HDD 원본은 보존)."
exit 0
