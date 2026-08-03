# run_realign_all.ps1 — 정렬 실패분 6개년 일괄 재정렬 (돌려놓고 나가도 됨)
# 각 연도: 1) MFA 재정렬(빔 100/400) → 2) 품질통계 추출 → 3) 표준 3-tier 병합
# 마지막에 연도별 회수 요약 출력. 작은 연도부터, 2023(최대)은 맨 끝.
# 실행: scripts\run_realign_all.ps1  (아래 설명 참조)

$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8   # 한글 로그 깨짐 방지

$py    = "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke\.venv\Scripts\python.exe"
$conda = "C:\Users\ari30\miniforge3\Scripts\conda.exe"
$repo  = "C:\Users\ari30\research\2026_summer_research"
$logdir = "D:\mfa_realign"
$master = "$logdir\run_realign_all.log"
"=== 재정렬 시작 $(Get-Date) ===" | Tee-Object -FilePath $master

$years = @("2022","2024","2025","2021","2020","2023")   # 2023 마지막(최대 부하)
$failed_years = @()

foreach ($Y in $years) {
    $corpus = "$logdir\corpus\$Y"
    if (-not (Test-Path $corpus)) {
        "[$Y] 코퍼스 없음 — 건너뜀" | Tee-Object -FilePath $master -Append; continue
    }
    "`n### [$Y] 정렬 시작 $(Get-Date -Format 'HH:mm:ss') ###" | Tee-Object -FilePath $master -Append

    # 1) MFA 재정렬 (stderr는 파일로 직접 — 2>&1/Tee 금지)
    $a = @('run','-n','mfa','mfa','align',$corpus,'korean_mfa','korean_mfa',
           "$logdir\out\$Y",'--num_jobs','4','--no_tokenization',
           '--beam','100','--retry_beam','400','--clean','--output_format','long_textgrid')
    $p = Start-Process -FilePath $conda -ArgumentList $a -NoNewWindow -Wait -PassThru `
         -RedirectStandardOutput "$logdir\align_${Y}_out.log" `
         -RedirectStandardError  "$logdir\align_${Y}_err.log"
    if ($p.ExitCode -ne 0) {
        "[$Y] !! 정렬 실패 (exit $($p.ExitCode)) — align_${Y}_err.log 확인" |
            Tee-Object -FilePath $master -Append
        $failed_years += $Y; continue
    }

    # 2) 품질통계 추출 (다음 연도 진행 전에)
    & $py "$repo\scripts\python\realign_export_quality.py" --year $Y 2>&1 |
        Tee-Object -FilePath $master -Append

    # 3) 표준 3-tier 변환·병합 (기존 정렬 보존, 회수분만 채움)
    & $py "$repo\scripts\python\realign_merge_output.py" --year $Y 2>&1 |
        Tee-Object -FilePath $master -Append

    "### [$Y] 완료 $(Get-Date -Format 'HH:mm:ss') ###" | Tee-Object -FilePath $master -Append
}

"`n=== 전체 회수 요약 ===" | Tee-Object -FilePath $master -Append
& $py "$repo\scripts\python\realign_summary.py" 2>&1 | Tee-Object -FilePath $master -Append

if ($failed_years.Count -gt 0) {
    "`n!! 정렬 실패 연도: $($failed_years -join ', ') — 해당 err 로그 확인 필요" |
        Tee-Object -FilePath $master -Append
}
"`n=== 모두 종료 $(Get-Date) ===" | Tee-Object -FilePath $master -Append
