# 어절(語節) 전량 재정렬 배치 — 목적 B: 4-tier TextGrid. ★실시간 출력판★
#   words(어절)+phones(연결 실제 발음, 교정)+morphemes(형태소 경계)+utterance
# lab은 wav 옆에 제자리 생성(하드링크 없음). 기존 06_textgrid_merged는 읽기전용 보존.
# 결과: D:\20_AUDIO\06_textgrid_eojeol
# ★모든 단계 출력을 화면에 그대로 흘림(Tee 버퍼링 제거) → lab 속도·ETA, MFA 진행바 실시간 확인.
# 실행: powershell -ExecutionPolicy Bypass -File C:\Users\ari30\research\2026_summer_research\scripts\run_eojeol_realign.ps1
# 주의: 도는 동안 D:를 읽는 다른 작업 금지(경합).

# 주의: $ErrorActionPreference는 Stop 안 씀(네이티브 exe stderr가 오류로 오인되는 것 방지).
$py    = "python"
$conda = "C:\Users\ari30\miniforge3\Scripts\conda.exe"
$pydir = Join-Path $PSScriptRoot "python"
$wavRoot = "D:\20_AUDIO\03_wav\individual"
$out     = "D:\mfa_eojeol\out"
$tmp     = "D:\mfa_eojeol\tmp"
$logDir  = "D:\mfa_eojeol\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
New-Item -ItemType Directory -Force $out    | Out-Null
$log = Join-Path $logDir ("eojeol_realign_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

function Say($m) { $l = "[$(Get-Date -Format 'MM-dd HH:mm:ss')] $m"; Write-Host $l -ForegroundColor Cyan; Add-Content $log $l -Encoding UTF8 }

$years = @('2020','2021','2022','2023','2024','2025')
Say "어절 재정렬 시작 (실시간 출력). 진행줄이 화면에 바로 뜹니다."

foreach ($y in $years) {
    Say "===== $y 시작 ====="

    # 1) 어절 lab 제자리 생성 — 파이썬이 10세션마다 '발화/s·남은분' 실시간 출력
    Say "$y [1/3] lab 생성 (아래 진행줄 실시간)..."
    & $py (Join-Path $pydir "realign_eojeol_build_corpus.py") --year $y
    if ($LASTEXITCODE -ne 0) { Say "!! $y lab 실패 (exit $LASTEXITCODE) — 중단"; return }

    # 2) MFA 정렬 — 완료 마커 있으면 건너뜀. 진행바가 화면에 실시간.
    $doneMark = Join-Path $out "$y\.done"
    if (Test-Path $doneMark) {
        Say "$y [2/3] MFA 이미 완료(.done) — 건너뜀"
    } else {
        Say "$y [2/3] MFA 정렬 (진행바 실시간, num_jobs 4)..."
        & $conda run -n mfa mfa align (Join-Path $wavRoot $y) korean_mfa korean_mfa (Join-Path $out $y) --num_jobs 4 --no_tokenization --clean --temporary_directory $tmp --output_format long_textgrid
        if ($LASTEXITCODE -ne 0) { Say "!! $y MFA 실패 (exit $LASTEXITCODE) — 중단"; return }
        New-Item -ItemType File -Force $doneMark | Out-Null
        Say "$y MFA 정렬 완료"
    }

    # 3) 4-tier 병합 — 진행줄 실시간
    Say "$y [3/3] 4-tier 병합 -> 06_textgrid_eojeol (아래 진행줄 실시간)..."
    & $py (Join-Path $pydir "realign_eojeol_merge_output.py") --year $y
    if ($LASTEXITCODE -ne 0) { Say "!! $y 병합 실패 (exit $LASTEXITCODE) — 중단"; return }

    Say "===== $y 완료 ====="
}
Say "전체 완료 - D:\20_AUDIO\06_textgrid_eojeol (4-tier). 기존 06_textgrid_merged 보존."
