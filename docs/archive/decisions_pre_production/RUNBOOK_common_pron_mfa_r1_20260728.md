# 공통 MFA 발음사전 r1 — 종료된 역사 기록

기록일: 2026-07-28  
현재 상태: PrepareOnly 성공, G2P output shard 0/35, 장시간 계산 미시작

## 실행 목적

2020–2025 전체 동결 vocabulary의 관측 OOV 866,691개를 같은
`korean_mfa` G2P 1-best/strict로 한 번 계산한다. 최종 사전은 기본
`korean_mfa.dict`의 원문 21,009행을 그대로 두고 OOV 행만 추가한다.

계산이 끝나면 같은 명령 안에서 자동으로 다음을 실행한다.

1. shard 35개 각각 입력/출력 단어 집합, `spn`, acoustic inventory 검사
2. 최종 공통사전 생성과 모델·원천 SHA 검사
3. 2020 최종 TextGrid 866,196개 word–phone 전수 비교
4. 2020 archive 부분 DB 내부 발음 후보 전수 비교
5. 2021 완성 DB 관측 어절 발음 후보 집합 전수 비교

세 baseline이 모두 mismatch 0이어야 2022 사용 허용 보고서가 생성된다.

## 실행 전 조건

- 다른 MFA 대량 실행이 없어야 한다.
- D: 볼륨 라벨은 `DATA_SSD`여야 한다.
- 노트북 전원과 D: 연결을 유지한다.
- 절전·재부팅·PowerShell 창 닫기를 피한다.
- 공통 release나 shard 파일을 수동 이동·수정·삭제하지 않는다.

## 실행 명령

프로젝트의 최신 커밋·푸시 완료 안내를 받은 뒤 일반 PowerShell에서 실행한다.

```powershell
Set-Location "C:\Users\ari30\research\2026_summer_research"

& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\run_common_pron_mfa_r1.ps1"
```

예상 시간은 공통 G2P 약 24–36시간, 전수 동등성 약 1–2시간이다. 실제 시간은
G2P worker와 D: I/O에 따라 달라질 수 있다.

## 중간 확인

완료 shard 수:

```powershell
$release = "D:\mfa_common_pron\releases\common_pron_mfa_r1_20260728"
(Get-ChildItem "$release\01_g2p\output_shards" -File `
  -Filter "oov_*.dict" -ErrorAction SilentlyContinue).Count
```

가장 최근 G2P 로그:

```powershell
$release = "D:\mfa_common_pron\releases\common_pron_mfa_r1_20260728"
$latest = Get-ChildItem "$release\logs" -File -Filter "g2p_oov_*.log" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
$latest | Select-Object FullName, Length, LastWriteTime
if ($latest) { Get-Content $latest.FullName -Tail 30 }
```

실행 lock과 프로세스:

```powershell
Test-Path "D:\mfa_common_pron\locks\common_pron_mfa_r1_20260728.lock"
Get-Process |
  Where-Object { $_.ProcessName -match "powershell|mfa|python" } |
  Select-Object Id, ProcessName, CPU, StartTime
```

## 중단·재개

창이 닫히거나 시스템이 재부팅돼도 완료 shard는 다시 계산하지 않는다. 같은
실행 명령을 그대로 다시 실행한다. 기존 출력은 먼저 전수 검증되고, 유효한
shard만 재사용한다. 불완전하거나 불일치한 파일은 release 아래
`archive_failed`에 보존한 뒤 해당 shard만 다시 계산한다.

수동으로 lock이나 부분 파일을 삭제하지 않는다. 오류 화면과 다음 정보를
그대로 전달한다.

```powershell
$release = "D:\mfa_common_pron\releases\common_pron_mfa_r1_20260728"
Get-ChildItem "$release\logs" -File |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 3 FullName, Length, LastWriteTime
```

## 완료 판정

다음 두 파일이 모두 있어야 한다.

```text
D:\mfa_common_pron\releases\common_pron_mfa_r1_20260728\
  00_contract\release_manifest.json
D:\mfa_common_pron\releases\common_pron_mfa_r1_20260728\
  03_equivalence\common_pron_mfa_equivalence_2020_2021.json
```

동등성 JSON의 조건:

```text
status = passed
baseline_2020.status = passed
baseline_2020_partial_db_auxiliary.status = passed
baseline_2021.status = passed
mismatches.rows = 0
gate.allow_common_dictionary_for_2022 = true
```

실행기가 마지막에 “2020·2021 전수 phone 동등성 통과”를 출력하기 전에는
2022 MFA 명령을 실행하지 않는다.
