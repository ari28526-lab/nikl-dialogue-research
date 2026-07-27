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
| 10:34–10:43 | G2P worker 4→3 | worker PID 26540이 먼저 종료했다. heartbeat의 live CPU 합계는 14,050.94→11,343.92초로 내려갔지만, 남은 worker 3개는 10:43 각각 3,320.56–3,324.05초까지 계속 증가했고 주 Python·MFA·wrapper도 생존했다. stderr 오류·traceback 없음 | 317.84GB | 한 partition이 먼저 끝난 정상 진행으로 판정. 현재 `Generating pronunciations`는 watchdog 종료 제외 단계라 재시작하지 않음. 다음 실행에서는 종료 worker의 마지막 CPU를 retired 합계에 보존해 누적치가 역행하지 않도록 수정 |
| 11:23 | 공통 G2P 사전 도입 시점 결정 | 남은 worker 3개 CPU 각각 5,180.5–5,185.6초, 주 Python·MFA·wrapper 생존, heartbeat 18,300.56초, 오류 0 | 317.84GB | 공통 사전은 채택 후보이나 현재 2021은 중단하지 않음. 완주 DB를 공통 사전 seed·동등성 기준으로 보존 |
| 11:28 | 공통 발음 자원으로 범위 확대 | 남은 worker 3개 CPU 각각 5,377.0–5,380.1초, heartbeat 18,926.03초, 오류·traceback 0 | 317.84GB | 단순 G2P cache가 아니라 G2P 판본+우리말샘 예외+출처·우선순위를 6개년 공통 release로 설계. 2021은 baseline으로 완주 |

### 10:34 CPU 합계 하락의 의미와 후속 수정

현재 실행의 heartbeat는 매 시점 살아 있는 `mfa/python` CPU를 더한다. 따라서
worker 하나가 정상 종료하면 그 worker가 이미 소비한 CPU 전체가 다음 표본에서
빠진다. 10:33→10:34의 약 2,707초 하락은 계산량이 되돌아간 것이 아니라 이
live-only 집계 방식의 관측 왜곡이다.

실행 중인 2021 코드는 이미 메모리에 로드되어 있어 소급 변경하지 않았다. 대신
다음 실행용 runner에는 PID별 마지막 CPU와 종료된 process의 retired CPU를
분리하고 다음 세 필드를 기록하도록 했다.

- `tree_live_cpu_seconds`: 현재 살아 있는 MFA 트리 CPU
- `tree_retired_cpu_seconds`: 종료된 worker의 마지막 CPU 누계
- `tree_cpu_seconds`: live+retired 단조 증가 누계

작업자 2개 30초→하나 종료 뒤 35초→같은 PID 재사용 뒤 37초→전부 종료 뒤
37초를 유지하는 동적 회귀시험과 PowerShell 안전성 검사를 통과했다. 이 수정은
2021의 결과나 프로세스를 바꾸지 않고 2022 이후 진행·교착 진단의 정확도만
높인다.

### 11:23 공통 G2P 사전과 현재 실행 중단 여부

판정: **공통 사전은 방법론·속도 개선 후보로 채택하되 2021은 중단하지 않는다.**

설치된 MFA 3.4.0 소스를 확인하면 현재 단계는 전체 고유 OOV에 대해
`gen.generate_dict_pronunciations()`가 반환된 뒤에야 `Word`와
`Pronunciation`을 DB에 bulk insert하고 commit한다. 따라서 지금 worker를
종료하면 진행 중인 G2P 결과 대부분을 안전한 사전 산출물로 회수할 수 없다.

또한 현재 `input_contract_id`는 동결 CSV·lab 계약을 중심으로 만들어졌고
dictionary/G2P model fingerprint를 포함하지 않는다. 새 공통 사전으로
바꾸면서 `D:\mfa_tmp\2021`을 그대로 resume하면 서로 다른 사전 상태가 한 DB에
섞일 위험이 있다. 안전하게 바꾸려면 현 temp를 삭제하지 않고 archive한 뒤,
사전·G2P·음향모델 fingerprint를 포함한 alignment contract로 clean 재시작해야
한다. 지금 중단은 08:42 이후 corpus loading·normalization·G2P 계산을 버리고
같은 계산을 다시 하는 선택이다.

완주 뒤에는 2021 DB의 실제 word–pronunciation을 common lexicon v1의 seed와
검증 기준으로 쓴다. 2020–2025 공통 사전이 현재와 같은 `korean_mfa` G2P의
동일 top-1 발음을 cache한 것이라면, 2020·2021은 계산 방식만 inline/cache로
다르고 음운 입력은 동일하므로 전수 동등성 확인 후 재정렬하지 않아도 된다.
우리말샘 예외처럼 phone이 실제로 달라지는 common lexicon v2는 별도 방법론
변경이며, 차이 목록·표본 정렬을 본 뒤 2020·2021 재정렬 여부를 결정한다.

### 11:28 사용자 결정 반영: 예외 발음까지 포함한 6개년 공통 자원

사용자는 공통 사전을 단순 속도 cache로 제한하지 않고, G2P 판본과 우리말샘
예외 발음을 함께 고정한 방법론적 공통 자원으로 진지하게 검토하기를 요청했다.
또한 필요한 재실행을 회피하지 말라고 명시했다.

이에 따라 앞 절의 “v1 cache 뒤 v2는 나중에 결정”이라는 좁은 구분은 다음
실행 순서로 구체화한다.

1. 현재 2021은 중단하지 않고 baseline v0로 완주·전수 QC한다.
2. 2020–2025 공통 vocabulary를 만들고 기본 MFA 사전, 현재 G2P,
   `lexicon_enriched.pron_1/2`, `lexicon_legacy_pron.pron_g2p`를 출처별로
   감사한다.
3. 현재와 phone 후보가 동일한 정책 A와 사전 예외·대체 발음을 포함한 정책 B를
   별도 manifest·사전으로 A/B 정렬한다.
4. 정책 B가 채택되면 2020·2021을 새 release로 먼저 재정렬하고 같은 정본으로
   2022–2025를 처리한다.

현재 2021을 살리는 이유는 재실행을 두려워해서가 아니다. 지금 중단해도 진행
중 G2P 부분 결과를 안전하게 회수할 수 없고, 완주 DB가 새 공통 사전의 후보
회수·차이 전수 대조·성능 비교에 필요한 기준선이기 때문이다.

공통 자원은 출처 보존 정본 `pronunciation_registry`, 검색 CSV용
`pre_mfa_pronunciation_index`, 정렬용 `mfa_alignment_lexicon`으로 분리한다.
사전 발음과 G2P를 한 열로 덮어쓰지 않으며, alignment contract에 사전·G2P·
음향모델·phone mapping fingerprint를 추가한다. 세부 설계는
`DESIGN_common_pronunciation_lexicon_2020_2025_20260727.md`에 기록했다.

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
