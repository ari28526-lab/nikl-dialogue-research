# A5 층화 빈도 재생성 배치 (age_norm 반영: 60대->60대 이상 통합).
# 밤샘용. 연도별 count -> merge. 재개 가능(완료 연도 partial 있으면 건너뜀).
# 실행: 리포 루트에서  powershell -ExecutionPolicy Bypass -File scripts\run_stratified_rebuild.ps1
# 주의: 도는 동안 D:를 읽는 다른 작업 금지(경합).

$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "python\build_stratified_freq.py"
$part   = "D:\10_LAYERS\03_freq_dictionaries\_partials_strat"
$logDir = "D:\10_LAYERS\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("stratified_rebuild_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

function Say($m) { $line = "[$(Get-Date -Format HH:mm:ss)] $m"; Write-Host $line; Add-Content $log $line }

Say "시작 (log: $log)"
foreach ($y in 2020,2021,2022,2023,2024,2025) {
    $p = Join-Path $part "strat_$y.csv"
    if (Test-Path $p) { Say "count $y 이미 완료 - 건너뜀"; continue }
    Say "count $y 시작..."
    python $script --stage count --year $y 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { Say "!! count $y 실패 (exit $LASTEXITCODE) - 중단"; exit 1 }
}
Say "merge 시작..."
python $script --stage merge 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { Say "!! merge 실패 (exit $LASTEXITCODE)"; exit 1 }
Say "완료 - morph_freq_stratified.csv / _strata_totals.csv / morph_dispersion.csv 갱신됨"
