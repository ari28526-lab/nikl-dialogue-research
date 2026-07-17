# 병목 계측 파일럿 (2026-07-17) — 본 배치 전 "CPU vs USB I/O 병목" 확정용.
#   1) 소표본 코퍼스(D:\mfa_eojeol\pilot\corpus, 기본 2020 50세션) 구성
#   2) 5초 간격 CPU%·디스크(C:/D:) 사용률 샘플러를 백그라운드로 켠 채
#   3) MFA 정렬(temp=C:\mfa_tmp, 본 배치와 동일 설정) 실행·시간 측정
#   4) 분 단위 요약 출력 + 원시 CSV 저장 → 판정(CPU≥85% 지속=CPU병목 / CPU낮고 D:바쁨=I/O병목)
# 실행: powershell -ExecutionPolicy Bypass -File scripts\run_pilot_bottleneck.ps1
# 주의: 도는 동안 D:를 읽는 다른 작업 금지(경합).

$py     = "python"
# ★ conda run 대신 mfa.exe 직접 호출 (2026-07-17): conda run은 출력을 버퍼링해
#   진행바가 안 보이고, MFA 에러 시 래퍼가 안 죽고 매달리는 사고 확인됨.
$mfa    = "C:\Users\ari30\miniforge3\envs\mfa\Scripts\mfa.exe"
$pydir  = Join-Path $PSScriptRoot "python"
$corpus = "D:\mfa_eojeol\pilot\corpus"
$out    = "D:\mfa_eojeol\pilot\out"
$tmp    = "C:\mfa_tmp"
$logDir = "D:\mfa_eojeol\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$stamp  = Get-Date -Format "yyyyMMdd_HHmmss"
$csv    = Join-Path $logDir "pilot_perf_$stamp.csv"

function Say($m) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $m" -ForegroundColor Cyan }

# 1) 소표본 코퍼스 (재실행 시 .ready 마커로 건너뜀)
Say "[1/3] 파일럿 코퍼스 구성 (2020, 50세션)..."
& $py (Join-Path $pydir "build_pilot_corpus.py") --year 2020 --sessions 50
if ($LASTEXITCODE -ne 0) { Say "!! 코퍼스 구성 실패 — 중단"; return }
$nutt = (Get-ChildItem $corpus -Recurse -Filter *.lab | Measure-Object).Count
Say "코퍼스 발화(lab) 수: $nutt"
if ($nutt -eq 0) { Say "!! 코퍼스가 비어 있음 — MFA 돌리지 않고 중단"; return }

# 2) 샘플러 시작 (5초 간격, CIM — 한글 Windows 카운터명 문제 회피)
Say "[2/3] 성능 샘플러 시작 → $csv"
$sampler = Start-Job -ScriptBlock {
    param($csvPath)
    "time,cpu_pct,c_disk_pct,c_queue,c_MBps,d_disk_pct,d_queue,d_MBps" |
        Out-File $csvPath -Encoding utf8
    while ($true) {
        try {
            $cpu = (Get-CimInstance Win32_Processor |
                Measure-Object -Property LoadPercentage -Average).Average
            $disks = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk
            $c = $disks | Where-Object { $_.Name -like '*C:*' } | Select-Object -First 1
            $d = $disks | Where-Object { $_.Name -like '*D:*' } | Select-Object -First 1
            $line = "{0},{1},{2},{3},{4:N1},{5},{6},{7:N1}" -f `
                (Get-Date -Format 'HH:mm:ss'), [int]$cpu, `
                $c.PercentDiskTime, $c.CurrentDiskQueueLength, ($c.DiskBytesPersec/1MB), `
                $d.PercentDiskTime, $d.CurrentDiskQueueLength, ($d.DiskBytesPersec/1MB)
            Add-Content $csvPath $line
        } catch {}
        Start-Sleep -Seconds 5
    }
} -ArgumentList $csv

# 3) MFA 정렬 (본 배치와 동일 설정) + 시간 측정
Say "[3/3] MFA 파일럿 정렬 시작 (num_jobs 4, temp=C:)..."
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& $mfa align $corpus korean_mfa korean_mfa $out --num_jobs 4 --no_tokenization --clean --temporary_directory $tmp --output_format long_textgrid
$mfaExit = $LASTEXITCODE
$sw.Stop()

Stop-Job $sampler; Remove-Job $sampler -Force

# 4) 요약
$sec = [math]::Round($sw.Elapsed.TotalSeconds)
$rate = if ($sec -gt 0) { [math]::Round($nutt / $sec, 1) } else { 0 }
Say "MFA exit=$mfaExit · 총 $sec 초 · $rate 발화/s (전체 510만 발화 환산: $([math]::Round(5100000/$rate/86400,1))일)"
Say "--- 분 단위 평균 (CPU% / D:디스크% / D:MB/s) ---"
Import-Csv $csv | Group-Object { $_.time.Substring(0,5) } | ForEach-Object {
    $cpuAvg = [int](($_.Group | Measure-Object -Property cpu_pct -Average).Average)
    $dPct   = [int](($_.Group | Measure-Object -Property d_disk_pct -Average).Average)
    $dMB    = [math]::Round((($_.Group | Measure-Object -Property d_MBps -Average).Average), 1)
    "{0}  CPU {1,3}%   D: {2,3}%  {3,6} MB/s" -f $_.Name, $cpuAvg, $dPct, $dMB
}
Say "원시 CSV: $csv — 이 파일을 Claude에게 보여주면 병목 판정·본배치 ETA를 계산합니다."
