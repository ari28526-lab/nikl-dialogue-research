# 데이터 드라이브 간 복사 러너 (2026-07-19 작성; 1차 용도: 7/20 HDD→SSD 이전)
# 목적: SSD를 데이터 정본으로 승격. robocopy라 끊겨도 재실행하면 이어서 복사됨.
# 사용: powershell -ExecutionPolicy Bypass -File scripts\copy_hdd_to_ssd.ps1 -Dst E:\
#   -Src = 원본 드라이브 (기본 D:\) / -Dst = 대상 드라이브
#   -Tier2 스위치를 주면 원본(00_RAW)·아카이브까지 전부 복사 (용량 확인 후)
# ★추후 백업(역방향)에도 같은 스크립트: SSD가 D:가 된 뒤 HDD를 꽂아(예: F:)
#   `-Src D:\ -Dst F:\` — SSD에서 처리한 산출물을 HDD로 역복사(추가/갱신만,
#   삭제 미러링 없음 → HDD에만 있는 항목은 보존됨).
# 복사 순서: 파이프라인 필수분(Tier1) 먼저. 복사 중 원본 드라이브 다른 작업 금지.
# V3 검사 예외에 SSD 경로도 추가 권장.
param(
    [Parameter(Mandatory=$true)][string]$Dst,   # 예: E:\
    [string]$Src = "D:\",
    [switch]$Tier2
)
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8

$src = $Src.TrimEnd('\') + '\'
$Dst = $Dst.TrimEnd('\') + '\'
if (-not (Test-Path $src)) { Write-Host "!! 원본 드라이브 없음: $src" -ForegroundColor Red; return }
if ($src -eq $Dst) { Write-Host "!! 원본과 대상이 같음: $src" -ForegroundColor Red; return }
if (-not (Test-Path $Dst)) { Write-Host "!! 대상 드라이브 없음: $Dst" -ForegroundColor Red; return }
$logDir = Join-Path $Dst "_migration_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Tier1: 어절 재정렬 파이프라인 + 분석에 필수
$tier1 = @(
    "10_LAYERS",                     # 바른 원출력 CSV·빈도사전·gold 등
    "00_RAW\dialogue_json",          # 모두의말뭉치 전사 JSON 원본 (사용자 지시 7/20 — SSD에도 동봉)
    "20_AUDIO\03_wav",               # wav 585만 + 어절 lab (최대 항목, ~290GB)
    "20_AUDIO\06_textgrid_merged",   # 기존 3-tier (병합의 형태소 출처, 읽기전용)
    "20_AUDIO\06_textgrid_eojeol",   # 어절 4-tier (있는 만큼)
    "mfa_eojeol"                     # done 마커·로그·격리(quarantine)
)
# Tier2: 원본·아카이브·현상 (SSD 용량 여유 시 — 안 옮겨도 HDD가 백업으로 보존)
# ※변수명 주의: PS는 대소문자 무구분 — 스위치 $Tier2와 겹치지 않게 $tier2Dirs (7/20 버그 수정)
$tier2Dirs = @("00_RAW", "20_AUDIO\05_mfa_output", "30_PHENOMENA", "90_ARCHIVE")

$targets = $tier1; if ($Tier2) { $targets += $tier2Dirs }
$failed = @()
foreach ($rel in $targets) {
    $s = Join-Path $src $rel
    if (-not (Test-Path $s)) { Write-Host "[$rel] 원본 없음 — 건너뜀" -ForegroundColor Yellow; continue }
    $d = Join-Path $Dst $rel
    $log = Join-Path $logDir ("robocopy_" + ($rel -replace '[\\/]', '_') + "_$stamp.log")
    Write-Host "`n=== [$rel] 복사 시작 $(Get-Date -Format 'HH:mm:ss') ===" -ForegroundColor Cyan
    # /MT:16 소형파일 병렬 / /R:1 /W:1 재시도 최소 / /NFL /NDL /NP 로그 폭주 방지
    robocopy $s $d /E /MT:16 /R:1 /W:1 /NFL /NDL /NP /DCOPY:T /LOG+:$log | Out-Null
    $rc = $LASTEXITCODE   # robocopy: 0-7 정상(3=복사+추가 등), 8+ 오류
    if ($rc -ge 8) {
        Write-Host "[$rel] !! robocopy 오류 (code $rc) — $log 확인" -ForegroundColor Red
        $failed += $rel
    } else {
        Write-Host "[$rel] 완료 (code $rc)" -ForegroundColor Green
    }
}

# MFA 모델 동봉 — 새 기기에서 재다운로드 대신 동일 버전 보장 (Documents\MFA\pretrained_models)
$models = Join-Path $env:USERPROFILE "Documents\MFA\pretrained_models"
if (Test-Path $models) {
    Write-Host "`n=== [MFA 모델] 동봉 복사 ===" -ForegroundColor Cyan
    robocopy $models (Join-Path $Dst "_migration\mfa_pretrained_models") /E /R:1 /W:1 /NFL /NDL /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { $failed += "MFA모델" } else { Write-Host "[MFA 모델] 완료" -ForegroundColor Green }
}

Write-Host "`n=== 검증: 파일 수 대조 (원본 vs SSD) ===" -ForegroundColor Cyan
foreach ($rel in $targets) {
    $s = Join-Path $src $rel; $d = Join-Path $Dst $rel
    if (-not (Test-Path $s)) { continue }
    $ns = (robocopy $s $d /E /L /NFL /NDL /NJH /NP /BYTES | Select-String '^\s+Files\s*:' | Out-String)
    # /L(목록만)+요약의 'Files : total copied skipped ...'에서 copied=0이면 완전 일치
    Write-Host "[$rel] $($ns.Trim())"
}
if ($failed.Count) {
    Write-Host "`n!! 실패 목록: $($failed -join ', ') — 재실행하면 이어서 복사" -ForegroundColor Red
    return
}

# ★ 세션 재구성 자동 연결 (2026-07-19): 복사 성공 시 SSD 쪽 평면 연도(wav/lab)를
#   세션 폴더로 재구성(1화자 사고 근본 해결 + 탐색기에서 열리는 크기로).
#   연도별 자동 감지·멱등이라 이미 세션 구조면 할 일 없이 통과. HDD 원본은 안 건드림.
Write-Host "`n=== 세션 재구성 (SSD, 평면 연도 자동 감지) ===" -ForegroundColor Cyan
$indiv = Join-Path $Dst "20_AUDIO\03_wav\individual"
python (Join-Path $PSScriptRoot "python\restructure_wav_sessions.py") --root $indiv --year all --apply
if ($LASTEXITCODE -ne 0) {
    Write-Host "!! 재구성 실패 — 위 출력 확인 후 수동 재실행:" -ForegroundColor Red
    Write-Host "   python scripts\python\restructure_wav_sessions.py --root $indiv --year all --apply"
} else {
    Write-Host "`n복사+재구성 완료 — SSD를 안전 제거 후 새 기기로 (RUNBOOK_SSD_migration.md 절차 B)" -ForegroundColor Green
}
