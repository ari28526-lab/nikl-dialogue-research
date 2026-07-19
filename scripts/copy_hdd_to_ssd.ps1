# HDD(D:) → 외장 SSD 이전 복사 러너 (2026-07-19 작성, 실행 예정 7/20 오후)
# 목적: SSD를 데이터 정본으로 승격. robocopy라 끊겨도 재실행하면 이어서 복사됨.
# 사용: powershell -ExecutionPolicy Bypass -File scripts\copy_hdd_to_ssd.ps1 -Dst E:\
#   -Dst = 이 기기에서 SSD가 받은 드라이브 문자 (복사 후 새 기기에서 D:로 문자 재부여)
#   -Tier2 스위치를 주면 원본(00_RAW)·아카이브까지 전부 복사 (용량 확인 후)
# 복사 순서: 파이프라인 필수분(Tier1) 먼저 → 끝나는 대로 새 기기 작업 시작 가능.
# ★복사 중 D:를 읽는 다른 작업 금지(경합). V3 검사 예외에 SSD 경로도 추가 권장.
param(
    [Parameter(Mandatory=$true)][string]$Dst,   # 예: E:\
    [switch]$Tier2
)
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8

$src = "D:\"
$Dst = $Dst.TrimEnd('\') + '\'
if (-not (Test-Path $Dst)) { Write-Host "!! 대상 드라이브 없음: $Dst" -ForegroundColor Red; return }
$logDir = Join-Path $Dst "_migration_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Tier1: 어절 재정렬 파이프라인 + 분석에 필수
$tier1 = @(
    "10_LAYERS",                     # 바른 원출력 CSV·빈도사전·gold 등
    "20_AUDIO\03_wav",               # wav 585만 + 어절 lab (최대 항목, ~290GB)
    "20_AUDIO\06_textgrid_merged",   # 기존 3-tier (병합의 형태소 출처, 읽기전용)
    "20_AUDIO\06_textgrid_eojeol",   # 어절 4-tier (있는 만큼)
    "mfa_eojeol"                     # done 마커·로그·격리(quarantine)
)
# Tier2: 원본·아카이브·현상 (SSD 용량 여유 시 — 안 옮겨도 HDD가 백업으로 보존)
$tier2 = @("00_RAW", "20_AUDIO\05_mfa_output", "30_PHENOMENA", "90_ARCHIVE")

$targets = $tier1; if ($Tier2) { $targets += $tier2 }
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
if ($failed.Count) { Write-Host "`n!! 실패 목록: $($failed -join ', ') — 재실행하면 이어서 복사" -ForegroundColor Red }
else { Write-Host "`n복사 완료. 다음: python scripts\python\restructure_wav_sessions.py --root ${Dst}20_AUDIO\03_wav\individual --year all --apply" -ForegroundColor Green }
