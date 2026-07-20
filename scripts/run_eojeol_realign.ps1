# 어절(語節) 전량 재정렬 배치 — 목적 B: 4-tier TextGrid. ★실시간 출력판★
#   words(어절)+phones(연결 실제 발음, 교정)+morphemes(형태소 경계)+utterance
# lab은 wav 옆에 제자리 생성(하드링크 없음). 기존 06_textgrid_merged는 읽기전용 보존.
# 결과: D:\20_AUDIO\06_textgrid_eojeol
# ★lab·병합 단계는 화면 실시간. MFA 단계는 stderr를 파일로 캡처(실패 traceback 보존)
#   + 1분 하트비트로 진행바 요약 표시 (2026-07-18: 7/17 실패 원인 유실 사고 후 전환).
# 실행: powershell -ExecutionPolicy Bypass -File <리포>\scripts\run_eojeol_realign.ps1
# 주의: 도는 동안 D:를 읽는 다른 작업 금지(경합).
# ★전제(2026-07-19): wav 코퍼스는 세션 하위폴더 구조여야 함(세션=화자). 평면이면
#   MFA가 연도 전체를 화자 1명으로 오인 → 가드가 중단시킴. restructure_wav_sessions.py 먼저.
#   기기 이식: miniforge는 %USERPROFILE%\miniforge3, 데이터는 D: 문자 기준 — 새 기기에서
#   SSD에 D: 부여하면 무수정 실행. num_jobs·작업드라이브는 자동 선택.

# 주의: $ErrorActionPreference는 Stop 안 씀(네이티브 exe stderr가 오류로 오인되는 것 방지).
$py    = "python"
# ★ conda run 대신 mfa.exe 직접 호출 (2026-07-17): conda run은 출력을 버퍼링해
#   진행바가 안 보이고, MFA 에러 시 래퍼가 안 죽고 매달리는 사고 확인됨(파일럿).
#   단 OpenFST 등 서드파티 실행파일(fstcompile)을 PATH에서 찾으므로 env 경로를 얹는다.
# ★ 기기 이식성 (2026-07-19): 경로를 사용자 홈 기준으로 — 새 노트북에서도 무수정 실행.
$envRoot = Join-Path $env:USERPROFILE "miniforge3\envs\mfa"
$mfa   = Join-Path $envRoot "Scripts\mfa.exe"
$env:Path = "$envRoot;$envRoot\Library\bin;$envRoot\Scripts;$envRoot\bin;" + $env:Path
$pydir = Join-Path $PSScriptRoot "python"
$wavRoot = "D:\20_AUDIO\03_wav\individual"
# ★ 병렬 자동 (2026-07-19): 논리코어 12+(i5-1240P=16) → 8job, 그 외(N200=4) → 4job.
#   세션=화자 재구성 후에야 유효 — 1화자면 MFA가 어차피 1job으로 강등함.
$numJobs = if ([Environment]::ProcessorCount -ge 12) { 8 } else { 4 }
# ★ 작업 드라이브 자동 (2026-07-19): temp·MFA 원출력을 둘 빠른 디스크 선택.
#   구 기기: C:(SSD, 여유 ~48GB) → C: 사용 / 새 노트북: C: 여유 ~22GB뿐 → D:(외장 SSD).
#   판정: C: 여유 40GB 이상이면 C:, 아니면 D:. (구 기기에서 C:가 40GB 밑으로 떨어지면
#   D:=USB HDD로 넘어가 느려지므로 그땐 C:를 정리할 것.)
$workDrive = if ((Get-PSDrive C).Free / 1GB -ge 40) { "C:" } else { "D:" }
$out     = "$workDrive\mfa_eojeol_out"
$doneDir = "D:\mfa_eojeol\done"
New-Item -ItemType Directory -Force $doneDir | Out-Null
# temp: MFA는 정렬 반복 중 wav이 아니라 temp의 특징값(MFCC)·DB를 계속 읽음.
#   연도당 temp ~20-35GB 추정, --clean이라 연도마다 비워짐. 여유 30GB 미만이면 중단.
$tmp     = "$workDrive\mfa_tmp"
$minTmpFreeGB = 30
$logDir  = "D:\mfa_eojeol\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
New-Item -ItemType Directory -Force $out    | Out-Null
$log = Join-Path $logDir ("eojeol_realign_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

function Say($m) { $l = "[$(Get-Date -Format 'MM-dd HH:mm:ss')] $m"; Write-Host $l -ForegroundColor Cyan; Add-Content $log $l -Encoding UTF8 }

$years = @('2020','2021','2022','2023','2024','2025')

# ★ 드라이브 엉킴 가드 (2026-07-20, 사용자 지시): HDD(백업)와 SSD(정본)가 동시에
#   꽂혀 있어도 파이프라인이 HDD를 잘못 잡지 않게 — D:는 반드시 라벨 DATA_SSD(SSD).
#   이전 완료 후 SSD=D:, HDD=H:(백업 전용)로 문자 고정. 의도적으로 HDD에서 돌릴
#   일이 생기면 아래 $expectLabel만 바꿀 것.
$expectLabel = 'DATA_SSD'
$dLabel = (Get-Volume -DriveLetter D -ErrorAction SilentlyContinue).FileSystemLabel
if ($dLabel -ne $expectLabel) {
    Say "!! D: 볼륨 라벨이 '$expectLabel'이 아님(현재: '$dLabel') — HDD를 D:로 오인했을 수 있어 중단."
    Say "   SSD에 D: 문자를 부여했는지 확인 (RUNBOOK_SSD_migration 절차 참조)."
    return
}

Say "어절 재정렬 시작 (실시간 출력). 진행줄이 화면에 바로 뜹니다."

foreach ($y in $years) {
    Say "===== $y 시작 ====="

    # 1) 어절 lab 제자리 생성 — 파이썬이 10세션마다 '발화/s·남은분' 실시간 출력
    Say "$y [1/3] lab 생성 (아래 진행줄 실시간)..."
    & $py (Join-Path $pydir "realign_eojeol_build_corpus.py") --year $y
    if ($LASTEXITCODE -ne 0) { Say "!! $y lab 실패 (exit $LASTEXITCODE) — 중단"; return }

    # 2) MFA 정렬 — 완료 마커 있으면 건너뜀. 진행바가 화면에 실시간.
    $doneMark = Join-Path $doneDir "$y.align_done"
    if (Test-Path $doneMark) {
        Say "$y [2/3] MFA 이미 완료(.done) — 건너뜀"
    } else {
        # 작업 드라이브 여유 가드 — temp가 도중에 차면 연도 전체 재작업이라 미리 중단
        $freeGB = [math]::Round((Get-PSDrive $workDrive.Substring(0,1)).Free / 1GB, 1)
        if ($freeGB -lt $minTmpFreeGB) {
            Say "!! $workDrive 여유 ${freeGB}GB < ${minTmpFreeGB}GB — temp($tmp) 부족 위험, 중단. 정리 후 재실행."
            return
        }

        # ★ 평면 구조 가드 (2026-07-19, 1화자 사고 재발 방지): 연도 루트에 wav가 바로
        #   있으면 = 세션 재구성 안 됨 → MFA가 연도 전체를 화자 1명으로 오인(품질·병렬
        #   붕괴). 지연 열거라 세션 구조면 즉시 통과, 평면이면 첫 파일에서 걸림.
        $flatWav = [IO.Directory]::EnumerateFiles((Join-Path $wavRoot $y), "*.wav") |
                   Select-Object -First 1
        if ($flatWav) {
            Say "!! $y 코퍼스가 평면 구조(예: $(Split-Path $flatWav -Leaf)) — 1화자 오인 위험."
            Say "   먼저 실행: python scripts\python\restructure_wav_sessions.py --root $wavRoot --year $y --apply"
            return
        }
        # 1.5) 깨진 wav 격리 (2026-07-18): 0바이트 wav 1개가 MFA 로딩 '말미'에 전체를
        #   실패시킴(7/17·7/18 두 차례, 각 5h+ 손실). 연도당 ~5분 보험.
        Say "$y [1.5/3] 깨진 wav 스캔·격리 (0바이트 등)..."
        & $py (Join-Path $pydir "quarantine_bad_wavs.py") --year $y --apply
        if ($LASTEXITCODE -ne 0) { Say "!! $y wav 스캔 실패 (exit $LASTEXITCODE) — 중단"; return }

        # ★ stderr를 파일로 캡처 (2026-07-18): MFA는 진행바·traceback을 전부 stderr로 쓰고,
        #   에러 traceback은 자기 로그 파일이 닫힌 '뒤' 출력되는 구조라 콘솔이 닫히면 유실됨
        #   (7/17 2020 실패 원인 유실 사고). 파일로 받되, 1분마다 파일 끝(=현재 진행바)을
        #   요약해 콘솔에 하트비트로 찍음 — 실시간성 유지 + 실패 원인 영구 보존.
        # ★ 이어가기 (2026-07-18): 같은 연도 재시도 시 temp DB가 남아 있으면 1차는
        #   --clean 없이 실행 → MFA가 끝난 단계(코퍼스 로딩 5.5h, MFCC 등)를 재사용.
        #   실패하면 temp 비우고 --clean 전체 재실행(2차 폴백 — 어중간한 DB 방어).
        #   lab을 바꾼 적 없는 동일-연도 재시도에만 안전(연도 첫 시도는 항상 --clean).
        $errFile = Join-Path $logDir "mfa_${y}_stderr.log"
        $tmpYear = Join-Path $tmp $y
        $tries = @(); if (Test-Path $tmpYear) { $tries += $false }; $tries += $true
        $ok = $false
        foreach ($doClean in $tries) {
            $mode = if ($doClean) { "--clean 전체" } else { "이어가기(temp 재사용)" }
            Say "$y [2/3] MFA 정렬 — $mode (num_jobs $numJobs, temp=$tmp 여유 ${freeGB}GB, 진행=1분 하트비트)..."
            if (Test-Path $errFile) { Move-Item $errFile "$errFile.prev" -Force }
            $aArgs = @('align', (Join-Path $wavRoot $y), 'korean_mfa', 'korean_mfa',
                       (Join-Path $out $y), '--num_jobs', "$numJobs", '--no_tokenization',
                       '--temporary_directory', $tmp, '--output_format', 'long_textgrid')
            if ($doClean) { $aArgs += '--clean' }
            $p = Start-Process -FilePath $mfa -ArgumentList $aArgs -NoNewWindow -PassThru `
                 -RedirectStandardError $errFile
            $null = $p.Handle   # PS5.1 함정: 핸들 미참조 시 ExitCode가 빈 값이 됨(성공을 실패로 오판)
            while (-not $p.HasExited) {
                Start-Sleep -Seconds 60
                $tail = ""
                try {
                    $fs = [IO.File]::Open($errFile, 'Open', 'Read', 'ReadWrite')
                    $n = [Math]::Min(400, $fs.Length)
                    if ($n -gt 0) {
                        [void]$fs.Seek(-$n, 'End')
                        $buf = New-Object byte[] $n
                        [void]$fs.Read($buf, 0, $n)
                        $seg = [Text.Encoding]::UTF8.GetString($buf) -split "[`r`n]" |
                               Where-Object { $_ -match '\S' }
                        if ($seg) { $tail = ($seg[-1] -replace '\e\[[0-9;]*m', '').Trim() }
                    }
                    $fs.Close()
                } catch {}
                Write-Host ("[{0}] {1} MFA 진행: {2}" -f (Get-Date -Format 'HH:mm:ss'), $y, $tail)
            }
            $p.WaitForExit()
            if ($p.ExitCode -eq 0) { $ok = $true; break }
            Say "!! $y MFA 실패 (exit $($p.ExitCode)) — 원인 traceback: $errFile"
            if (-not $doClean) {
                Say "$y 이어가기 실패 → temp 비우고 --clean 전체로 재시도"
                Remove-Item $tmpYear -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
        if (-not $ok) { Say "!! $y MFA 최종 실패 — 중단"; return }
        New-Item -ItemType File -Force $doneMark | Out-Null
        # temp(~26GB/년) 즉시 회수 — 안 지우면 다음 연도의 C: 여유 가드에 걸려 헛중단
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
        Say "$y MFA 정렬 완료 (temp 정리됨)"
    }

    # 3) 4-tier 병합 — 진행줄 실시간. MFA 원출력은 C:에 있음(--mfa-out).
    #    완료 마커 있으면 건너뜀(완료 연도는 C: 원출력이 이미 삭제돼 있음).
    if (Test-Path (Join-Path $doneDir "$y.merge_done")) {
        Say "$y [3/3] 병합 이미 완료 — 건너뜀"; Say "===== $y 완료 ====="; continue
    }
    Say "$y [3/3] 4-tier 병합 -> 06_textgrid_eojeol (아래 진행줄 실시간)..."
    & $py (Join-Path $pydir "realign_eojeol_merge_output.py") --year $y --mfa-out $out
    if ($LASTEXITCODE -ne 0) { Say "!! $y 병합 실패 (exit $LASTEXITCODE) — 중단"; return }

    # 4) 병합 성공 → C:의 MFA 원출력 삭제(공간 회수). 재개는 D:의 마커·최종본 기준.
    Remove-Item (Join-Path $out $y) -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType File -Force (Join-Path $doneDir "$y.merge_done") | Out-Null
    Say "===== $y 완료 (C: 중간산출 정리됨) ====="
}
Say "전체 완료 - D:\20_AUDIO\06_textgrid_eojeol (4-tier). 기존 06_textgrid_merged 보존."
