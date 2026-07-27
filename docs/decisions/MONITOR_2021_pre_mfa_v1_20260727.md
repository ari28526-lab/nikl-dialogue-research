# 2021 pre-MFA·MFA 실행 점검대장

작성 시작: 2026-07-27
입력 계약: `pre_mfa_v1_20260725`
대상: 2021 한 연도
실행 방식: `-PreferD -UseDirectDbExport`

## 목적과 판정 원칙

2021 lab 검증부터 MFA DB direct 4-tier 생성까지 완료 여부를 시간순으로
기록한다. 화면의 진행문구만으로 성공을 판단하지 않고 다음을 함께 본다.

- wrapper PID lock과 실제 child 프로세스
- 단계별 로그와 1분 heartbeat
- CPU·진행 카운터·D: 여유
- 입력계약 marker와 MFA SQLite DB
- partial/final 4-tier 수량·coverage·tier·경계
- 난정렬, source 결함, 형태소/form 누락의 분리

MFA `phones`는 연구자의 실현 판정이 아니라 G2P 라벨의 대략적 시간정렬이다.
완료 후에도 KOINA와 사람의 WAV·TextGrid 판정을 대신하지 않는다.

오류가 생기면 원 WAV·동결 CSV·기존 TextGrid를 수정하지 않는다. 먼저
SQLite DB, partial, temp, stderr, heartbeat를 보존하고 원인을 확인한다.

## 실행 기준선

```text
시작 시각       2026-07-27 08:27:14
wrapper PID     22816
연도            2021
PreferD         true
direct DB       true
시작 D: 여유    약 319GB
2021 세션       4,143/4,143
예상 usable lab 1,373,521
기존 lab 일치   1,335,015
재작성 예상     38,320
신규 예상       186
```

## 시간순 점검

| 시각 | 단계 | 실제 관측 | D: 여유 | 판정·조치 |
|---|---|---|---:|---|
| 08:27 | 시작 | wrapper lock 생성, `Years=[2021]`, `PreferD=true`, `direct_db_export=true` | 약 319GB | 2021 한 연도 개선 경로로 정상 시작 |
| 08:37 | lab 검증 | Python PID 5904 생존, 누적 CPU 약 496초, `[1/3] pre-MFA 입력계약 확인 + lab 생성/내용검증` | 318.98GB | 정상. MFA 전 단계이므로 heartbeat 부재가 예상됨 |
| 08:40 | lab 검증 | PID 5904 누적 CPU 616.7초로 계속 증가, lock 유지, temp/partial 아직 없음 | 318.97GB | 정상 진행. 중단·재실행하지 않음 |
| 08:42 | lab 완료 | 4,143세션; 신규 186, 불일치 재작성 38,320, 기존 일치 1,335,015, WAV 누락 0, 빈 reference 399 | 318.90GB | 입력계약 `ef22e9b38901…` 통과. 사전 감사 예상치와 정확히 일치 |
| 08:42 | MFA 시작 | `--clean`, 4 jobs, MFA PID 25188, temp `D:\mfa_tmp\2021`, direct 모드 heartbeat 생성 | 318.90GB | `[2/3]` 정상 진입. stderr는 새 실행의 `Setting up corpus information`, `Loading corpus` |
| 08:43 | corpus loading | 첫 heartbeat `phase=setup`, CPU 79.4초, watchdog false. 실제 Python child PID 26912 CPU 101.6초, temp 0.069GB/11파일 | 318.90GB | 정상. 이 구간의 counter 부재는 예상되며 CPU·temp가 증가함 |
| 08:44 | corpus loading | 두 번째 heartbeat CPU 163.6초, watchdog false; 20초 뒤 child CPU 194.6초·RAM 928MB | 318.90GB | CPU와 메모리 적재가 지속돼 정상. stderr 무변화만으로 교착 판정하지 않음 |
| 08:57 | corpus loading 15분 | heartbeat CPU 1,340.8초, Python child CPU 1,341.5초, RAM 1.12GB, watchdog false | 318.90GB | 15분간 CPU 지속 증가. stderr 무변화는 대용량 source loading의 정상 저출력 구간 |
| 08:59 | 일시 CPU 둔화 재검증 | 한 스냅샷에서 CPU 증가가 작아 10초 교차측정: CPU +30.8초, D: 60–88MB/s, RAM 1.21GB | 318.90GB | 교착 아님. source loading의 고속 I/O·병렬 처리 확인, 중단하지 않음 |
| 09:10 | corpus loading 27분 | heartbeat CPU 2,143.5초, child CPU 2,173.0초, RAM 2.47GB, temp 적재로 D: 사용 약 0.37GB 증가 | 318.53GB | 10분 감시창 동안 경고 0. 2020 단순 비례 예상보다 조금 길지만 CPU·RAM·디스크가 모두 진행 중 |
| 09:12 | corpus loading 완료 | 4,143 speakers, 1,416,216 files 인식; loading 약 30분. multiprocessing 초기화로 전환 | 318.04GB | 세션·파일 수가 감사 기준과 일치. watchdog false |
| 09:13 | text normalization | stderr `Normalizing text...`, child CPU 2,325.9초, RAM 1.70GB | 318.03GB | 정상 setup 다음 단계 진입 |
| 09:16 | G2P pronunciation | 정규화 약 3.5분 뒤 `Generating pronunciations...`; heartbeat CPU 2,504.5초, RAM 1.77GB | 317.84GB | 정상. 과거 watchdog 오판이 있었던 저출력 G2P 구간이므로 강제종료 금지 |
| 09:27 | G2P 10분 교차점검 | MFA 보조 Python 4개가 각각 CPU 444–446초 사용, 주 Python 포함 프로세스 트리 CPU 합계가 heartbeat 4,325초와 일치. D: 순간 I/O도 관측 | 317.84GB | 교착 아님. 주 Python 하나만 보는 모니터는 병렬 G2P 진행을 과소평가하므로 2022 모니터에 프로세스 트리 CPU를 반영 |
| 09:50 | G2P 34분·모니터 개선 | worker 4개 CPU 각각 1,312–1,316초, heartbeat CPU 7,798초, watchdog false. 기존 코드는 모든 `mfa/python`을 합산한다는 사실 확인 | 317.84GB | 현재 실행은 정상 유지. 다음 실행부터 Windows Toolhelp 기반 실제 descendant tree CPU·RAM·PID·Python 수를 heartbeat에 기록하도록 수정하고 동적 회귀시험 통과 |
| 10:15 | G2P 약 59분 | heartbeat CPU 11,154초, MFA·wrapper 생존, watchdog false, D: 여유 불변 | 317.84GB | 긴 단계이지만 09:50 대비 CPU가 3,356초 증가해 교착 아님. 수정 전 속도와의 비교는 2020이 아니라 보존 코드 `e1075ee`·과거 실패 로그를 기준으로 별도 분석 |

## 다음 확인 게이트

1. lab builder 종료 코드와 생성·재작성·일치·빈 입력 수량
2. preflight 재통과와 `[2/3] MFA` 진입
3. heartbeat의 PID·단계·진행 카운터·CPU 증가
4. 정렬 종료 뒤 SQLite DB 존재와 direct partial 생성
5. 99% coverage 및 형태소/form hard failure 0
6. final staging 이동, align/merge marker, DB 보존
7. 독립 전수 QC와 2020·2021 병목 비교

## final 승격 뒤 독립 전수 QC

아래 명령은 final 2021 폴더와 동일 입력계약의 direct 보고서·marker가 생성된
뒤에만 실행한다. partial 디렉터리를 final로 오인해 감사하지 않는다.

```powershell
& "C:\Users\ari30\miniforge3\envs\mfa\python.exe" `
  ".\scripts\python\audit_mfa_4tier_year.py" `
  --year 2021 `
  --lab-root "D:\20_AUDIO\03_wav\individual\2021" `
  --textgrid-root "D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2021" `
  --report ".\outputs\reports\AUDIT_mfa_4tier_2021_pre_mfa_v1_20260727.json" `
  --missing-csv ".\outputs\reports\MISSING_mfa_4tier_2021_pre_mfa_v1_20260727.csv" `
  --progress-jsonl "D:\mfa_eojeol\logs\audit_4tier_2021_pre_mfa_v1_20260727_heartbeat.jsonl" `
  --input-contract-id "ef22e9b38901a3dd0797cd9664cd72c1d04f496e2ad775cbd9b5f3f99292c3fe" `
  --workers 4
```

hard gate:

- 정확한 `words/phones/morphemes/utterance` 순서
- 모든 tier의 0–xmax 연속 coverage와 gap·overlap 0
- 네 tier 모두 핵심 유표 interval 존재
- TextGrid xmax와 원 WAV header duration 오차 1ms 이하
- lab/TextGrid 중복·반대 차집합·0바이트 lab 0
- lab→TextGrid coverage 99% 이상

운영본은 원 WAV 시간을 보존한다. 0.05초 가시적 좌우 빈 경계는 패딩된
연구자 점검 사본의 기준이므로 전량 운영본에서는 hard failure가 아니라
tier별 진단 수량으로 보고한다.
