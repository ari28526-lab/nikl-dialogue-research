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
| 11:42–12:02 | 20분 연속 감시 | worker 3개가 각각 약 5,984–5,987→6,972–6,978 CPU초, heartbeat 20,789.75→23,765.56초. DB는 G2P 반환 전 구조대로 1,140,953,088바이트 유지, 오류·marker 없음 | 317.84GB | 세 worker가 거의 균등하게 계속 계산한 정상 CPU-bound G2P. 무로그·DB 미갱신을 교착으로 오판하지 않고 실행 유지 |
| 12:24–12:52 | 외부 리뷰 수신·P1 사전감사 | 외부 리뷰 원문 336행 보존, MFA 모델 3종 SHA256 기록. 2021 형태소 원천 감사를 570.354초에 완료: usable 1,373,521건 중 원천 TextGrid 누락 1,109건/61세션 | 317.84GB | 현재 MFA는 worker CPU·heartbeat 계속 증가해 중단하지 않음. 현 exporter의 말단 연도 실패 조건이 실제로 발현될 것을 사전에 확인. 정렬 export 성공과 형태소 analysis-ready를 분리하고 누락 전수 inventory를 남기는 호환 수정·시험 진행 |
| 13:23–14:26 | 장시간 G2P 지속 | 남은 worker 3개 CPU가 각각 약 10,570→13,616–13,623초로 증가했고 heartbeat 누적값도 34,881.84→44,240.88초로 증가했다. G2P 벽시계 5.17시간, DB는 일괄 commit 전 1,140,953,088바이트, stderr 오류 0, watchdog false | 317.84GB | 1시간 이상 세 worker 모두 계산을 계속한 정상 CPU 병목. 중단하지 않음. 신규 연도는 공통 G2P cache와 신규/동일계약-resume gate 분리로 이 구간을 줄이되 기존 DB 복구 가능성을 보존 |
| 15:14 | G2P 약 5시간 58분 | 남은 worker 3개 CPU가 각각 16,093–16,103초까지 계속 증가했고 heartbeat live CPU도 51,649.30초로 증가했다. MFA·주 Python·wrapper가 모두 생존하며 DB 1,140,953,088바이트, stderr 마지막 단계 `Generating pronunciations...`, traceback·marker 없음 | 317.84GB | 세 worker의 연속 CPU 증가와 매분 heartbeat로 교착을 배제했다. DB mtime 정지는 G2P 결과 일괄 반영 전 상태와 일치하며 중단·재시작하지 않음 |
| 15:30 | G2P 약 6시간 14분 | worker 3개 CPU 16,849–16,857초, heartbeat live CPU 54,002.34초. 직전 1분 증가량 약 150초로 평균 약 2.5개 논리 코어를 계속 사용. lock·`mfa_running` temp 계약·동결 `_build_meta.json` SHA256 `1649d60a…`도 시작 marker와 일치 | 317.84GB | 장기 꼬리는 실제 CPU 계산이며 입력 변경·교착이 아님. 현 N200의 4 logical processor에서 worker 수만 늘리는 가속은 기대하기 어렵고 공통 vocabulary/G2P cache가 2022의 핵심 가속 후보 |
| 15:40–15:45 | G2P 결과 회수 중 메모리 추적 | 주 Python working set이 약 59→531→639MB로 증가했고 private memory는 약 2.37GB. 전체 MFA tree working set 0.98GB/private 3.06GB, 시스템 가용 물리 메모리 최저 관측 511MB. commit 사용률은 약 69.1–69.5%(한도 25.50GB). 15초 연속 표본에서 page reads 15.17→4.19→3.79/s, pages 95.64→26.54→16.94/s로 낮아지고 가용 메모리는 517→575→576MB로 회복. worker CPU·heartbeat 계속 증가 | 317.84GB | 물리 메모리 여유는 낮지만 commit headroom 약 7.8GB이고 지속 thrashing은 아님. G2P 결과 회수/축적 가능성이 있어 사용자 프로그램을 임의 종료하거나 MFA를 중단하지 않고 가용 메모리·page reads·주 Python working set 추세를 추가 감시 |
| 16:00 | G2P 약 6시간 44분 | worker 3개 CPU 18,331–18,338초, heartbeat live CPU 58,425.61초. 주 Python working set 약 535MB/private 2.37GB, 가용 메모리 632MB, commit 68.62%, page reads 0/s. stderr·DB·marker 변화 없음 | 317.84GB | 장기 G2P는 계속 정상 CPU-bound. 15:40의 일시적 physical-memory 압박은 확대되지 않았고 paging도 해소돼 중단·프로세스 종료 불필요 |
| 16:21 | G2P 약 7시간 5분 | 45초 표본에서 남은 worker 3개의 CPU가 각각 41.00·40.64·40.53초 증가했고 주 Python도 1.64초 증가했다. worker working set은 124.5–137.0MB, 주 Python working set은 66.4MB/private 2.21GB. heartbeat CPU는 61,914.81초까지 증가, stderr 오류·완료 marker 없음 | 317.84GB | 장시간 같은 로그 문구가 유지되지만 세 worker 모두 실제 계산 중이므로 교착이 아니다. 15:40 메모리 압박도 확대되지 않아 실행을 보존하고 감시 지속 |
| 16:45 | G2P 약 7시간 29분 | 16:34–16:44 읽기 전용 변화 감시 동안 다음 단계 전환·프로세스 종료가 없었다. 16:44 heartbeat CPU 65,367.44초, worker 3개 CPU 각각 20,616–20,623초, working set 122.1–136.8MB. DB 크기·mtime, stderr, 완료 marker 변화와 오류 없음 | 317.84GB | 약 10분 동안 세 worker가 합계 약 1,900 CPU초를 추가 사용해 교착을 재차 배제했다. 단계 변화 감시용 별도 PowerShell은 로그/PID만 읽고 종료했으며 MFA에는 개입하지 않음 |
| 17:00 | G2P 약 7시간 44분 | 16:46–17:01 15분 읽기 전용 변화 감시에서 단계 전환·비정상 종료가 없었다. 17:00 heartbeat CPU 67,912.22초, worker CPU 21,457–21,465초. 가용 물리 메모리 773–775MB, commit 약 17.64/25.50GB, page reads 0–1.53/s. DB·stderr·marker 변화와 오류 없음 | 317.84GB | CPU 진행과 메모리 회복이 함께 확인돼 장기 G2P를 정상 계산으로 계속 판정. 중간 DB를 폐기하거나 재시작하지 않음 |
| 17:39 | G2P 약 8시간 23분 | 17:18–17:38 약 20분 변화 감시에서 단계 전환·비정상 종료가 없었다. 17:39 heartbeat CPU 73,824.97초. 30초 표본에서 worker 3개 CPU가 각각 25.62·25.47·26.34초 증가했다. 가용 메모리 677–706MB, page reads 약 6.9–14.7/s와 순간 pages 91.49/s가 관측됐으나 worker 계산률은 합계 약 2.58코어로 유지 | 317.84GB | 약한 paging 변동이 있으나 commit 여유·가용 메모리·CPU 처리량이 유지돼 지속 thrashing 또는 중단 사유가 아니다. 사용자 프로세스 종료·MFA 재시작 없이 감시 지속 |
| 17:42–17:46 | G2P 완료·MFCC 진입 | 약 17:42에 세 G2P worker가 정상 종료했고 `normalize_oov.log`는 73,529,786바이트로 닫혔다. SQLite DB는 1,140,953,088→1,213,358,080바이트로 증가해 17:44:10 갱신됐다. 17:46 stderr가 `Generating MFCCs...`로 전환했다. 종료 worker의 CPU가 기존 heartbeat 합계에서 빠져 74,110.25→3,807.33초로 보인 것은 이미 확인한 구 runner 계측 한계이며 계산 역행이 아님 | 317.44–317.71GB | G2P 벽시계 병목은 발음 생성 약 8시간 26분과 DB 일괄 반영 약 2분으로 실측. 2022 공통 vocabulary/G2P cache 우선순위를 강화하며, 현재 DB 반영 성공을 확인해 재시작하지 않음 |
| 17:46–17:48 | MFCC 준비·메모리 압력 | 주 Python working set이 약 2.13GB(private 2.52GB), 가용 메모리 최저 371MB, page reads 566–840/s까지 상승했다. 30초 뒤 가용 메모리는 722MB, 주 Python working set은 1.65GB로 회복했으나 page reads는 계속 높았다. commit은 약 16.96–17.00/25.50GB로 8GB 이상 여유, heartbeat CPU는 4,180.05초까지 증가, watchdog false | 약 317.45GB | G2P 결과 반영 뒤 MFCC 목록/데이터 준비 전환의 메모리·page-in 구간으로 판정. 처리 진행과 commit 여유가 있어 중단하지 않고, MFCC worker·ark/scp 성장과 paging 지속 시간을 추가 감시 |
| 17:49–18:23 | MFCC 내부 worker 처리 | 주 Python CPU가 4,424.92→9,359.09초로 계속 증가했고 working set은 1.47GB→약 656MB, 가용 메모리는 약 1.0GB로 회복했다. `feats.1–4.ark/scp`와 `make_mfcc.1–4.log`는 계속 0바이트지만 page reads 약 500–730/s, D: 여유 317.42→316.19GB로 진행 중이었다. 오류·watchdog 조건 없음 | 316.19GB | 설치된 MFA 3.4.0 `acoustic_corpus.py:502-526`, `features.py:MfccFunction._run`을 확인했다. MFCC는 주 Python 내부 4 job worker가 10,000발화 청크로 처리하고 writer를 job 끝에서 닫으므로 별도 실행 파일이 안 보이고 처리 중 파일 길이가 0인 것은 정지 증거가 아니다. 다음 runner heartbeat에 실제 tree thread 수를 추가하고 PowerShell 안전성 검사 통과 |
| 18:42 | MFCC 약 57분 | 주 Python CPU 12,299.36초, 10 threads, 분당 약 150 CPU초, working set 717MB/private 2.54GB. 가용 메모리 962–970MB, commit 약 16.82/25.50GB, page reads 약 643–656/s. D: 여유는 315.43GB로 감소했지만 `feats.*`의 directory length는 writer close 전 0바이트, 오류 없음 | 315.43GB | Windows paging file 카운터는 `C:\pagefile.sys`만 보고돼 D: 감소는 pagefile 확장이 아니다. MFA writer가 열린 feature archive에 데이터를 쓰되 directory 길이/로그를 close 때 반영하는 상태와 실측 CPU·D 감소가 일치한다. 315GB 이상 여유가 있어 용량 누수나 중단 사유가 아님 |
| 19:42–19:45 | MFCC 완료·CMVN·final features 진입 | MFCC 4 jobs가 19:42:49–19:43:09 정상 종료했다. 처리 수는 343,803+343,102+343,596+341,937=`1,372,438`, 오류 합계 0. ark 4개 합계 4,458,523,142바이트, scp 합계 86,376,851바이트. 약 19:40 계산 CPU가 낮아진 뒤 writer close 중 D 쓰기가 계속됐고, 19:43 CMVN, 19:45 final features로 전환. CMVN 4,143화자 처리, 오류 로그 없음. DB 1,213,358,080→1,220,665,344바이트, 19:45:15 갱신 | 312.95GB | MFCC 벽시계 약 1시간 57분. 예상 usable lab보다 1,083개 적은 MFCC 수는 0.1초 미만 등 입력 제외와 후속 alignment/QC에서 ID 단위 조인할 사항이며 MFCC 자체 오류는 0. final feature writer도 같은 close-at-end 구조라 중간 0바이트만으로 중단하지 않음 |
| 19:55–19:57 | final features 완료·corpus split | final feature 4 jobs도 각 343,803·343,102·343,596·341,937건, 오류 0으로 닫혔다. final ark 합계는 원 MFCC와 같은 4,458,523,142바이트. stderr는 OOV 1,025건 제외, feature issue 42,753건 경고 뒤 `Creating corpus split...`으로 전환했다. DB는 1,315,770,368바이트, 19:57:27 갱신 | 약 312.57GB | 경고는 수량상 `corpus에만 있는 WAV 42,296 + 빈 reference 399 + 추가 feature 제외 58 = 42,753`, 그리고 `usable lab 1,373,521 - 58 - OOV 1,025 = 처리 1,372,438`로 정확히 닫힌다. 무작위 대량 손실은 아니나 OOV 1,025 ID는 완료 뒤 unresolved-symbol inventory·missing alignment와 전수 조인해 원인 분류 |
| 19:58–20:23 | training graph 완료·정렬 진입 | Windows thread mode 4 jobs가 1,494.1–1,510.0초에 정상 종료했다. `fsts.korean_mfa.1–4.ark`는 각각 약 4.66–4.70GB, 합계 18,739,878,694바이트. 주 Python은 9 threads, 분당 약 165 CPU초. 20:23 stderr가 `Performing first-pass alignment`/`Generating alignments`로 전환했고 20:23 heartbeat부터 `phase=align`, watchdog false | 295.07GB | graph 벽시계 약 25분, D: 최저 여유도 295GB 이상. align archive 역시 writer close 전 0바이트이므로 CPU와 heartbeat로 감시. 카운터는 stderr에 없지만 15분 누적 CPU 폴백이 작동하며 현재 분당 약 150 CPU초라 거짓 교착 종료 위험 없음 |
| 21:09 | first-pass 약 46% | `align.1–4.log`의 `Processing` 전수 계수는 156,907+159,264+159,225+158,837=`634,233`, feature 대상 1,372,438건의 46.21%였다. 네 job 진도 편차는 최대 2,357건(전체 대상의 0.17%p)으로 균등했다. `Retried`는 합계 10,605건(현재 처리량의 1.67%), error·exception·traceback·failed 일치는 0건. 주 Python CPU 33,513.7초, 10 threads, heartbeat·각 align log가 현재 시각까지 갱신됐다 | 293.74GB | 장기 무출력이나 특정 job 교착이 아니다. 재시도는 MFA의 자동 beam 확대 회수 경로이므로 최종 failed 수와 독립 QC 결과가 나오기 전 오류로 세지 않는다. 중단하지 않고 first-pass 종료와 후속 fMLLR/final alignment 전환을 감시 |
| 21:25–21:26 | first-pass 약 62%·차기 계측 검증 | 실제 로그 증분 카운터는 857,067/1,372,438건(62.45%), 재시도 13,988건(1.63%), 오류 신호 0건이었다. 70.8MB 첫 전수 스캔 7.5초, 이후 1,852건 추가분 스캔 67ms. heartbeat CPU 36,171.27초, watchdog false | 293.23GB | 현재 실행은 기존 메모리상 runner라 새 필드의 영향을 받지 않는다. 다음 연도용 PowerShell 전수 행 처리는 30초 초과 병목으로 폐기하고 64KiB C# 증분 스캐너로 교체·합성 회귀시험 통과. 성공 판정에는 사용하지 않고 진행 관측에만 사용 |

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

### 12:24 외부 리뷰 재검증과 12:52 형태소 원천 전수 감사

외부 도구가 커밋 `ce421dbe8c6b7f5bb50202b69f3ff1785508ba5f`를
읽기 전용 검토해 P0 0, P1 2, P2 7, P3 8건을 보고했다. 원문과 현재
프로젝트 판정은 각각 다음에 보존했다.

- `docs/reviews/incoming/EXTERNAL_REVIEW_CSV_MFA_ce421db_20260727.md`
- `docs/reviews/TRIAGE_external_review_CSV_MFA_ce421db_20260727.md`

설치된 MFA 소스를 다시 확인한 결과, 현재 G2P는 전체 함수 반환 뒤
`Word`·`Pronunciation` bulk insert와 commit을 수행한다
(`corpus/base.py:2007-2022, 2063-2072, 2115-2135`). 따라서 진행 중인
2021을 끊지 않는 기존 판정은 유지했다. 동시에 현재 설치본을 읽기 전용으로
해시해 다음 보고서에 고정했다.

- `outputs/reports/MFA_MODEL_FINGERPRINT_baseline_20260727.json`
- acoustic SHA256:
  `46f7a73ab46828c679562b160e0577beecfb4a9a827efe5ab392aee947451a4d`
- dictionary SHA256:
  `75683f4dc2a7dd95295a068206d248a30bd2f4f2231fd4449210c91d1e78150b`
- G2P SHA256:
  `6938db05d83fa92c5c80681bf76fd7dd7af7f3ea8c7d7df1093790c641ad0344`

첫 형태소 감사 시도는 일반 `05_search_master`를 가리켜 build meta status가
없다는 이유로 즉시 실패했다. 현재 실행 계약의 실제 root는
`D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725`다.
실패 로그를 보존하고 계약 파일에서 읽은 root로 재실행했다. 이는 pre-MFA
staging을 하드코딩하지 않고 현재 계약에서 유도해야 한다는 운영 교훈이다.

재시도 결과:

```text
search sessions          4,143
search rows          1,373,920
expected usable lab  1,373,521
lab/WAV/stale gate           PASS
morph source checked 1,373,521
morph source nonzero 1,372,412
morph source missing     1,109
affected sessions            61
elapsed                  570.354s
```

누락의 1,017/1,109건은 네 세션에 집중됐다.

- `SDRW2100003249`: 260
- `SDRW2100001747`: 258
- `SDRW2100001872`: 251
- `SDRW2100002153`: 248

기존 direct exporter는 이 1,109건도 빈 morphemes tier로 파일을 쓴 뒤
마지막에 `morpheme_tier_missing>0`을 연도 hard failure로 계산했다. 즉
약 20시간의 정렬·출력이 끝난 뒤 DB와 partial을 보존한 채 실패할 것이
사전에 확정됐다.

정책은 다음처럼 분리한다.

1. words/phones/utterance 정렬과 4-tier 파일 생성이 구조적으로 성공하면
   `status=success`로 DB·TextGrid를 보존한다.
2. 형태소 원천 누락 발화도 0–xmax 경계가 있는 빈 morphemes tier를 가지지만,
   `morphology_complete=false`,
   `analysis_ready_status=blocked_morphology`와 전수 ID inventory를 남긴다.
3. 독립 4-tier QC와 다음 연도 gate는 유표 morphemes가 없는 발화를 거부한다.
   따라서 빈 tier가 최종 연구용으로 조용히 승격되지는 않는다.
4. 1,109건은 원천 형태소 정렬 보완 또는 명시적 연구 제외를 결정한 뒤에만
   analysis-ready로 승격한다.

이 구분은 정렬에 성공한 시간정보를 버리지 않으면서도 형태소 검색 인프라의
완전성을 과장하지 않는다. 수정 전 파일·현재 실행 DB·partial은 덮어쓰거나
삭제하지 않는다.

#### 과거 잔여분 근거와 1,109건 전수 조인

이 1,109건을 2026-07-16의
`D:\10_LAYERS\05_audio_index\source_pcm_check.csv`와 `utt_id`로 조인한
결과는 1,109/1,109 일치, 미분류 0이었다.

```text
원본짧음  1,091
PCM없음       1
원본정상     17
합계      1,109
```

즉 이번 감사가 새로운 원음 결함을 발견한 것은 아니다.
`METHODS_bareun_dialogue_reanalysis.md`와
`RUNBOOK_MFA_realign_2020-2025.md`에 이미 기록된 잔여분이 현재 direct
export의 형태소 원천 의존성과 연결되지 않았던 것이 문제였다.

- 1,092건: 배포 원음 자체가 0.1초로 잘렸거나 PCM이 없어 회수 불가.
  명시적 `exclude_source_audio_unusable`로 음성분석 denominator에서 제외한다.
- 17건: 과거 원본 실측이 정상. 새 어절 alignment 성공 여부를 확인한 뒤
  `recover_morpheme_alignment_candidate`로 형태소 경계를 표적 보완한다.
- 미분류: 0건.

위 17건은 2차 대조에서 회수 후보가 아닌 source segment 오류로 재분류됐다.
모두 CSV duration과 WAV PCM은 0.301–0.707초로 서로 맞지만,
`pron_reference_form`은 18–52개 한글 음절이다. 환산값은
47.0–119.3음절/s로, 가장 보수적으로 잡은 `10음절 이상 + 40음절/s 이상`
기준도 전부 넘는다. 따라서 이는 WAV 파일이 열리는지의 문제가 아니라
짧은 segment에 다른 긴 전사가 연결된 내용 대응 오류다.

최종 v2 분류:

```text
source_pcm_too_short                       1,091
source_pcm_missing                             1
source_segment_text_duration_impossible       17
합계                                       1,109
미분류                                         0
```

이 기준은 실제 발음 속도나 음운현상 실현을 판정하는 데 쓰지 않는다. 오직
source segment와 전사가 물리적으로 대응 가능한지를 판정해 분석 denominator를
정하는 자료 무결성 gate다. 발화 원문은 Git 보고서에 복제하지 않고 ID,
duration, 음절/어절 수, 비율, 제외 근거만 기록한다.

재현 가능한 조인 산출물:

- `outputs/reports/CLASSIFY_morph_source_missing_2021_pre_mfa_v1_20260727.csv`
- `outputs/reports/CLASSIFY_morph_source_missing_2021_pre_mfa_v1_20260727.json`

따라서 최종 analysis-ready gate의 분모는 “WAV와 lab이 존재함”만으로 정하지
않고, 배포 원음 결함 제외표를 적용한 `analysis_eligible` 발화로 정의해야 한다.
그렇지 않으면 회수 불가능한 1,109건 때문에 어떤 코드도 영구히 통과할 수
없고, 반대로 단순히 형태소 누락을 허용하면 제외 근거와 raw 누락 규모를
잃는다.

#### 외부 리뷰 후속 구현 중 실행 보존

13:23까지 남은 G2P worker 3개의 CPU는 각각 약 10,570초로 계속 증가했고,
heartbeat의 process-tree 누적 CPU도 34,881.84초까지 증가했다. D: 여유는
317.84GB, stderr는 `Generating pronunciations...`, 오류와 watchdog kill
조건은 없었다. 따라서 중단 근거가 없다.

후속 코드 수정은 현재 PowerShell 프로세스가 이미 파싱을 끝낸 runner와 현재
G2P DB를 바꾸지 않는다. 특히 current runner가 MFA 종료 뒤 새 프로세스로
읽을 `export_mfa_db_4tier.py`는 커밋 `6ef6527` 상태에서 더 수정하지 않았다.
Git HEAD도 marker가 가리킬 판본을 보존하기 위해 같은 커밋에 고정했다.

다음 연도용 변경은 duration·형태소·모델 계약 gate, 단일 연도 wrapper,
미해결 기호 inventory, 고아 lab 차단, strict 감사, 격리 경로 교정,
`finalizing` heartbeat, direct crash 복구 안내다. 전체 Python unittest
82개와 PowerShell 안전성 검사를 통과했으며 2021 완료 뒤 하나의 검증된
후속 커밋으로 남긴다.

신규 연도는 `analysis` profile로 전사–구간 물리 불일치와 형태소 회수 후보까지
차단한다. 다만 동일 입력·정렬 계약의 temp가 이미 있으면 `execution` profile로
재개해 완료된 DB 계산을 새 분석 gate 때문에 버리지 않는다. 현재 실행 중인
2021 프로세스는 이 후속 runner 변경의 영향을 받지 않는다.

## 다음 확인 게이트

1. lab builder 종료 코드와 생성·재작성·일치·빈 입력 수량
2. preflight 재통과와 `[2/3] MFA` 진입
3. heartbeat의 PID·단계·진행 카운터·CPU 증가
4. 정렬 종료 뒤 SQLite DB 존재와 direct partial 생성
5. 99% export coverage 및 form/파일생성 hard failure 0
6. 형태소 completeness 별도 판정과 누락 ID inventory
7. final staging 이동, align/merge marker, DB 보존
8. 독립 전수 QC와 2020·2021 병목 비교

## final 승격 뒤 독립 전수 QC

아래 명령은 final 2021 폴더와 동일 입력계약의 direct 보고서·marker가 생성된
뒤에만 실행한다. partial 디렉터리를 final로 오인해 감사하지 않는다.

먼저 CSV–WAV–lab 내용과 형태소 원천을 다시 전수 감사한다.

```powershell
& "C:\Users\ari30\miniforge3\envs\mfa\python.exe" `
  ".\scripts\python\audit_mfa_year_readiness.py" `
  --years 2021 `
  --search-master-root `
    "D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725" `
  --wav-root "D:\20_AUDIO\03_wav\individual" `
  --morph-textgrid-root "D:\20_AUDIO\06_textgrid_merged" `
  --source-pcm-check "D:\10_LAYERS\05_audio_index\source_pcm_check.csv" `
  --compare-lab-content `
  --gate-profile analysis `
  --output `
    ".\outputs\reports\AUDIT_mfa_year_readiness_2021_post_mfa_20260727.json"
```

이 보고서의 raw 형태소 원천 누락 1,109건과 극단적 전사–segment 불일치는
별도 분류 CSV에서 1:1로 설명해야 한다. readiness의 analysis exit 1을
정렬 실패나 전량 재실행 지시로 해석하지 않는다.

그 다음 final 4-tier를 독립 감사한다.

```powershell
& "C:\Users\ari30\miniforge3\envs\mfa\python.exe" `
  ".\scripts\python\audit_mfa_4tier_year.py" `
  --year 2021 `
  --lab-root "D:\20_AUDIO\03_wav\individual\2021" `
  --textgrid-root "D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2021" `
  --report ".\outputs\reports\AUDIT_mfa_4tier_2021_pre_mfa_v1_20260727.json" `
  --missing-csv ".\outputs\reports\MISSING_mfa_4tier_2021_pre_mfa_v1_20260727.csv" `
  --morph-classification-csv `
    ".\outputs\reports\CLASSIFY_morph_source_missing_2021_pre_mfa_v1_20260727.csv" `
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

## 21:54–22:13 first-pass 종료와 경계 수집 전환

21:54 first-pass 누적은 `1,190,760/1,372,438`(86.76%)였고, 네 job의
로그는 같은 시각까지 계속 갱신되었다. 이후 약 1분 간격으로 확인한 누적값은
다음과 같다.

| 시각 | Processing | 진행률 | Retried | 예외·traceback |
|---|---:|---:|---:|---:|
| 21:57 | 1,218,224 | 88.76% | 19,817 | 0 |
| 21:59 | 1,246,399 | 90.82% | 20,240 | 0 |
| 22:01 | 1,275,812 | 92.96% | 20,695 | 0 |
| 22:03 | 1,304,401 | 95.04% | 21,024 | 0 |
| 22:05 | 1,332,304 | 97.08% | 21,363 | 0 |
| 22:07 | 1,360,450 | 99.13% | 21,720 | 0 |

마지막 job은 22:08:32에 끝났다. 최종 job별 수량은 다음과 같다.

| job | Processing | Retried | 성공 | `errors on` |
|---:|---:|---:|---:|---:|
| 1 | 343,803 | 5,528 | 343,676 | 127 |
| 2 | 343,102 | 5,402 | 342,915 | 187 |
| 3 | 343,596 | 5,563 | 343,469 | 127 |
| 4 | 341,937 | 5,392 | 341,808 | 129 |
| 합계 | **1,372,438** | **21,885** | **1,371,868** | **570** |

`Retried`는 전체 처리의 1.595%, 최종 `errors on`은 0.0415%다. 후자는
PowerShell·Python 예외나 MFA 중단이 아니라 Kalpy job 종료 요약에 기록된
개별 발화 정렬 실패다. 570개 ID는 최종 DB·direct export·TextGrid
누락 inventory와 대조해 원인을 보존한다. 전체 입력 수가 앞선 MFCC와 final
feature의 `1,372,438`과 정확히 일치하므로 job 누락이나 조기 종료는 없다.

각 job 종료 뒤 0바이트로 보이던 `ali_first_pass`, `words_first_pass`,
`likelihoods_first_pass` archive가 정상 크기로 닫혔고, 같은 내용의 최종
alignment archive가 생성되었다. 이어 SQLite journal이 갱신되면서 결과가
`2021.db`에 반영되었고, 22:12 stderr가 다음 단계로 전환되었다.

```text
INFO Collecting phone and word alignments from alignment lattices...
```

22:13 `phone_intervals.csv`와 `word_intervals.csv`가 생성되어 실제 크기가
증가하기 시작했다. 이 단계는 연구에 쓸 phone·word 시간 경계를 수집하는
핵심 후처리다. stdout 진행바가 없으므로 파일 크기·mtime, process-tree CPU,
heartbeat와 DB journal을 함께 감시한다.

first-pass 종료 직후 D: 여유는 archive close와 SQLite transaction 때문에
약 292.2GB에서 288.8–289.2GB 사이로 일시 변동했다. 여전히 전체 용량의
약 30%가 남아 현재 실행을 중단하거나 temp를 정리할 근거가 없다.

### 22:13–22:30 interval collect 실측과 메모리 판정

설치된 MFA 3.4.0의
`montreal_forced_aligner/alignment/base.py`를 읽어 현재 동작을 확인했다.
SQLite 경로는 각 발화의 CTM을 받는 즉시 `phone_intervals.csv`와
`word_intervals.csv`에 쓰고, 수집이 끝난 뒤 파일을 닫아 `sqlite3 .import`로
임시 테이블에 넣은 다음 본 테이블로 `INSERT ... SELECT`한다. 전체 phone
interval 객체를 하나의 Python 목록에 쌓는 구조는 아니다. 따라서 CSV
증가가 현재 단계의 직접적인 진행 증거이며, 수집 뒤 별도의 대용량 SQLite
적재 구간이 남는다.

다음 실행용 runner에는 CSV byte 단위 증분 스캐너를 추가했다.

- phone·word 행 수와 byte 크기
- word CSV의 연속 `utterance_id` 전환 수
- first-pass `alignment_processed`를 분모로 한 참고 진행률
- process-tree private memory
- Windows `GetPerformanceInfo` 기반 시스템 available memory,
  commit used/limit/percent와 비강제 warning

현재 live runner는 시작할 때 이미 옛 스크립트를 읽었으므로 이 변경의 영향을
받지 않는다. 외부 관측으로 같은 계산을 검증했다.

```text
22:29:33
phone rows              6,805,313
word rows               1,849,337
word utterances           262,453
alignment 대비 참고율       19.12%
```

약 682MB의 당시 두 CSV를 처음 스캔하면서 발화 전환까지 세는 데 8.7초,
3초 뒤 증분 43,358행·1,021발화를 갱신하는 데 53.6ms가 걸렸다. 실제 다음
실행에서는 작은 파일부터 상태를 쌓으므로 큰 초기 스캔 비용도 없다.

22:18의 available memory는 442–536MB, commit은 19.63–19.65/23.75GB,
page input은 790–3,011 pages/s였다. 22:29에는 Python working set 1.26GB,
private memory 6.25GB, available 942MB, commit 19.65/23.75GB(82.8%),
page input 1,298/s였다. private memory는 22:25–22:29 약 6.25GB에서
안정됐고 CSV·CPU는 계속 증가했다. 메모리 압박과 paging은 실제 병목이지만
현재 시점에 OOM 또는 교착을 뜻하지 않는다.

word 발화 진행률의 단순 선형 추정은 interval 수집 종료를 23:35–23:45
전후로 보지만, 이는 참고값이다. 이후 SQLite import·DB 반영과 direct 4-tier
내보내기까지 끝나야 MFA 완료로 판정한다.

## 2026-07-28 최종 완료와 독립 QC

위 실시간 관측 뒤 MFA는 01:59:15 종료코드 0으로 끝났다. stderr의 최종
보고 시간은 62,149.774초였고 watchdog kill은 없었다. direct DB 4-tier
내보내기는 03:45:16에 끝났으며 03:45:51에 final staging과 align/merge
marker가 같은 입력계약으로 기록됐다.

최종 direct 회계:

```text
DB source utterances       1,372,438
created TextGrid           1,371,868
alignment missing                570
form missing                       0
write failed                       0
accounted                   1,372,438
```

MFA first-pass의 570개 최종 실패와 direct export의 570개 alignment missing은
정확히 일치했다.

post-MFA readiness는 LAB 1,373,521개가 동결 CSV와 100% 내용 일치함을
확인했다. 형태소 원천 누락 1,109건은 PCM 짧음 1,091, PCM 없음 1,
segment–전사 물리 불일치 17로 모두 분류됐으며 미분류는 0이었다. post-MFA
lab inventory 재실행은 같은 입력계약의 `lab_reused` 경로였고 LAB 내용을
재작성하지 않았다.

독립 final 4-tier 감사:

```text
final TextGrid             1,371,868
valid                       1,371,868
invalid                             0
source unusable 제외           1,109
분석 가능 정렬 실패               544
분석 가능 coverage          99.9604%
hard failure                       0
```

모든 tier는 `words/phones/morphemes/utterance` 순서이며 0–WAV xmax를
gap·overlap 없이 덮었다. 0.05초 가시적 빈 경계는 canonical hard gate가
아니며 padded review bundle에서 WAV와 TextGrid를 함께 이동해 보장한다.

보존 DB `D:\mfa_tmp\2021\2021.db`는 12,455,149,568바이트다. read-only
SQLite full integrity 검사는 4,255.2초 뒤 `ok`였고, 정렬 성공 4,139세션
가운데 결정적으로 뽑은 서로 다른 24세션을 DB에서 다시 생성한 결과 final과
tier·라벨·모든 시간·SHA256이 24/24 일치했다.

2022 선행 결합 gate는 20/20, 자체 환경 preflight는 FAIL 0/WARN 0으로
통과했다. 2022 전량은 시작하지 않았다.

상세 최종 보고:

- `outputs/reports/RESULT_2021_pre_mfa_full_pipeline_20260728.md`
- `docs/decisions/AUDIT_2020_2021_MFA_comparison_and_2022_gate_20260728.md`
