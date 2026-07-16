# 어절(語節) 전량 재정렬 배치 — 목적 B: 4-tier TextGrid.
#   words(어절)+phones(연결 실제 발음, 교정)+morphemes(형태소 경계)+utterance
# ★ 원래 파이프라인처럼 lab을 wav 옆에 '제자리' 생성(하드링크 없음) → 원래 속도(<3일).
# 기존 형태소 TextGrid(06_textgrid_merged)는 읽기 전용(morphemes tier 소스) — 안 건드림.
# 결과: D:\20_AUDIO\06_textgrid_eojeol
# 연도별 lab -> align -> merge. 재개 가능(연도 완료 .done). 밤샘용.
# 실행: powershell -ExecutionPolicy Bypass -File C:\Users\ari30\research\2026_summer_research\scripts\run_eojeol_realign.ps1
# 주의: 도는 동안 D:를 읽는 다른 작업 금지(경합).

$ErrorActionPreference = "Stop"
$py    = "python"
$conda = "C:\Users\ari30\miniforge3\Scripts\conda.exe"
$pydir = Join-Path $PSScriptRoot "python"
$wavRoot = "D:\20_AUDIO\03_wav\individual"      # 코퍼스=wav폴더(제자리, lab 여기 생성)
$out     = "D:\mfa_eojeol\out"
$tmp     = "D:\mfa_eojeol\tmp"
$logDir  = "D:\mfa_eojeol\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
New-Item -ItemType Directory -Force $out    | Out-Null
$log = Join-Path $logDir ("eojeol_realign_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

function Say($m) { $l = "[$(Get-Date -Format 'MM-dd HH:mm:ss')] $m"; Write-Host $l; Add-Content $log $l -Encoding UTF8 }

$years = @('2020','2021','2022','2023','2024','2025')
Say "어절 재정렬 배치 시작 (제자리 lab, 목적 B). log: $log"

foreach ($y in $years) {
    Say "=== $y 시작 ==="

    # 1) 어절 lab 제자리 생성 (wav 옆). 하드링크 없음. 재개 가능.
    Say "$y [1/3] lab 제자리 생성..."
    & $py (Join-Path $pydir "realign_eojeol_build_corpus.py") --year $y | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { Say "!! $y lab 생성 실패 (exit $LASTEXITCODE)"; exit 1 }

    # 2) MFA 정렬 (코퍼스=individual\{y}). 완료 마커 .done 있으면 건너뜀.
    $doneMark = Join-Path $out "$y\.done"
    if (Test-Path $doneMark) {
        Say "$y [2/3] MFA 정렬 이미 완료(.done) - 건너뜀"
    } else {
        Say "$y [2/3] MFA 정렬 (korean_mfa, num_jobs 4)..."
        $al = @('run','-n','mfa','mfa','align',
            (Join-Path $wavRoot $y), 'korean_mfa', 'korean_mfa', (Join-Path $out $y),
            '--num_jobs','4','--no_tokenization','--clean',
            '--temporary_directory', $tmp, '--output_format','long_textgrid')
        Start-Process -FilePath $conda -ArgumentList $al -NoNewWindow -Wait `
            -RedirectStandardOutput (Join-Path $logDir "align_$y.out.log") `
            -RedirectStandardError  (Join-Path $logDir "align_$y.err.log")
        if (-not (Test-Path (Join-Path $out $y))) { Say "!! $y MFA 출력 없음 - 중단"; exit 1 }
        New-Item -ItemType File -Force $doneMark | Out-Null
        Say "$y MFA 정렬 완료"
    }

    # 3) 4-tier 병합 (어절+phones 신규 + 형태소 경계 기존서 얹기). 재개 가능.
    Say "$y [3/3] 4-tier TextGrid 병합 -> 06_textgrid_eojeol..."
    & $py (Join-Path $pydir "realign_eojeol_merge_output.py") --year $y | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { Say "!! $y 병합 실패 (exit $LASTEXITCODE)"; exit 1 }

    Say "=== $y 완료 ==="
}
Say "전체 완료 - 결과: D:\20_AUDIO\06_textgrid_eojeol (4-tier). 기존 06_textgrid_merged 보존."
