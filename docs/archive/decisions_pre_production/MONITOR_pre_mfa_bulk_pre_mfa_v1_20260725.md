# pre-MFA 전량 배치 중간 점검대장 (역사 기록)

대상 run: `pre_mfa_v1_20260725`

실행 코드: Git `195d71f377993dedd6dab4fae4133682b74fb576`

원칙: 실행 중 temp·marker·원자료·정본은 읽기만 한다. 문제를
`즉시 차단`과 `후속 추적`으로 구분해, 완료 뒤 처음부터 다시 돌리는 일을 막는다.

> 이 파일은 실행 중인 Git HEAD를 바꾸지 않기 위해 `logs`에 둔다. 배치가
> 끝나면 최종 실행결과와 함께 `docs/decisions`로 정리해 커밋한다.

## 중간 점검의 연구·재현성 목적

중간 점검의 목적은 단순한 생존 확인이 아니라 다음 두 가지다.

1. 전량 작업이 끝난 뒤 결함을 발견해 처음부터 다시 실행하는 일을 막는다.
2. 지금 멈출 필요가 없는 문제도 빠뜨리지 않고 추적해, 나중에 필요한
   범위만 선택적으로 수정·재실행할 수 있게 한다.

따라서 각 관찰사항에는 가능한 한 `영향 단계`, `즉시 차단 여부`,
`근거/대상 ID`, `후속 수정`, `최소 재실행 시작점`을 함께 남긴다.
현재 실행의 원자료·정본·temp·marker는 변경하지 않으며, 검사 자체가
D: 대량 I/O와 경쟁하지 않도록 전수 파일 열거는 연도 완료 게이트까지
미룬다.

## 2020 완료 뒤 의도적 일시정지 결정

2026-07-26 15:50 사용자는 2020 한 연도를 전 단계 완주한 뒤 병목과
개선점을 먼저 점검하는 방향을 선택했다. 현 실행은 `Years=2020..2025`가
이미 고정되어 있으므로 다음과 같이 연도 경계 가드를 적용했다.

- 요청:
  `work/control/pause_after_year_pre_mfa_v1_20260725.json`
- 적용 지점: 새 연도의 `run_eojeol_realign.ps1` 프로세스가 config·원자료·
  temp에 접근하기 전
- 현재 2020 프로세스: 스크립트를 이미 파싱해 실행 중이므로 영향 없음
- 2021 호출: exit 75로 작업 시작 전 종료
- 바깥 wrapper: 의도적 비정상 종료를 받아 summary 작성, lock과 transcript 정리
- 검증: PowerShell parser 오류 0건, 별도 2021 시험 호출 `guard_exit=75`

이 실행의 wrapper summary는 구조상 `failed`로 기록될 수 있으나 실제 실패가
아니라 사용자가 요청한 `paused_after_2020`이다. 최종 점검 문서에서 이를
명시하고, 2020의 `align_done`·`merge_done`·staging 검증이 통과해야만
“2020 파이프라인 완료”로 판정한다. 모든 발화의 정렬 성공과는 구분하며,
기본+retry beam에서 실패한 3,644건은 후속 부분 재시도 대상으로 유지한다.

## 실행 정체성

| 항목 | 값 |
|---|---|
| wrapper 시작 | 2026-07-25 13:23:06 |
| 연도 순서 | 2020 → 2021 → 2022 → 2023 → 2024 → 2025 |
| 드라이브 정책 | `-PreferD` |
| pre-MFA root | `D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725` |
| pre-MFA build status | `success` |
| build 행·세션 | 5,103,356행·17,156세션 |
| 2020 입력계약 | `fa96caf4a37c556b929febbfa172500b2dfe615cfb554e816b070766bc8b3038` |

## 체크포인트

| 시각 | 단계 | 프로세스/CPU | 공간 | 판단 |
|---|---|---|---|---|
| 13:23–14:05 | pre-MFA CSV 전량 생성 | build 정상 종료 | staging 6.41GB | 통과 |
| 14:05–14:17 | 2020 lab 전수 검증 | `lab_input_done` 생성 | 구 C temp 0.68GB를 D archive로 보존 | 통과 |
| 14:17–21:44 | 2020 MFA setup·G2P·MFCC·graph | MFCC 4 jobs | D temp 12.64GB | 통과 |
| 21:44 | 2020 actual alignment 시작 | `Generating alignments` | D 여유 약 313GB | 진행 |
| 22:14 | live check | 5초 CPU +15.03초, error 0 | D 313.3GB | 정상 |
| 22:15 | live check | 10초 CPU +19.70초, error 0 | D 313.3GB | 정상 |
| 22:21 | 5분 비교 | 10초 CPU +26.06초, error 0 | D 313.2GB | 정상 |
| 22:30 | 9분 비교 | CPU 총계 +1,231.1초(21,298.3→22,529.4), 10초 +26.38초, error 0 | D 313.0GB | 정상 |
| 22:36 | 6분 비교 | CPU 총계 +927.9초(22,529.4→23,457.3), 10초 +26.77초, error 0; align log는 아직 버퍼링 0B | D 312.8GB | 정상 |
| 22:47 | 11분 비교 | CPU 총계 +1,725.4초(23,457.3→25,182.7), 10초 +26.98초, error 0; stderr 62.8분 고정이나 계산 지속 | D 312.5GB | 정상 |
| 22:58 | alignment→collect 전환 | stderr 22:53 갱신, align log 74,029,078B, `Collecting phone and word alignments`; error/traceback 0 | D 310.6GB | 정렬 계산 완료·수집 진행 |
| 23:11 | collect 13분 비교 | CPU 총계 +796.1초(26,187.4→26,983.5), 10초 +10.45초, error 0; 원출력/marker 아직 없음 | D 310.1GB | 정상 수집 진행 |
| 23:22 | collect 11분 비교 | CPU 총계 +673.0초(26,983.5→27,656.5), 10초 +11.05초, error 0; 원출력/marker 아직 없음 | D 309.7GB | 정상 수집 진행 |
| 23:32 | collect 10분 비교 | CPU 총계 +682.5초(27,656.5→28,339.0), 10초 +10.61초, error 0; 원출력/marker 아직 없음 | D 309.3GB | 정상 수집 진행 |
| 23:48 | collect 16분 비교 | CPU 총계 +899.8초(28,339.0→29,238.8), 10초 +9.69초, error 0; DB 수집으로 D 약 2.8GB 증가 | D 306.5GB | 정상 수집 진행 |
| 00:04 | collect 16분 비교 | CPU 총계 +858.6초(29,238.8→30,097.4), 10초 +9.41초, error 0; stderr 70.3분 고정이나 계산·쓰기 지속 | D 305.5GB | 정상 수집 진행 |
| 00:19 | collect 16분 비교 | CPU 총계 +833.4초(30,097.4→30,930.8), 10초 +9.08초, error 0; collect 86분째 계산·쓰기 지속 | D 304.6GB | 정상 수집 진행 |
| 00:35 | collect→export 전환 | stderr 00:30 갱신, `Exporting alignment TextGrids`; 별도 Python worker PID 23616 생성 | D 304.1GB | export 시작 |
| 00:36 | export 초기 확인 | TextGrid 0건, error file 0; worker 10초 CPU +3.88초·프로세스 생존 | D 304GB대 | 아직 준비 단계, 5분 후 재확인 |
| 00:42 | export 12분 확인 | TextGrid 0건, worker 생존·5분 CPU 약 +128.5초·error 0 | D 304.1GB | 준비/DB 조회로 판단, 30분 시점까지 집중 감시 |
| 00:53 | export 23분 확인 | TextGrid 0건, worker 누적 CPU 499.6초·RAM 430.7MB·error file 0 | D 304.1GB | 워커 활동 지속, 30분 시점 재판정 |
| 01:01 | export 31분 확인 | TextGrid 0건, worker 누적 CPU 691.8초·RAM 448.6MB·error file 0; DB 5.61GB | D 304.1GB | CPU 활동 지속, 45분 시점 집중 재확인 |

stderr가 alignment 시작 뒤 줄 단위로 갱신되지 않아도 CPU가 계속 증가하므로
현재는 교착으로 판정하지 않는다. 출력 TextGrid와 `align_done`이 아직 없는 것은
export 전 단계라 정상이다.

## 전체 재작업을 막는 즉시 차단 기준

다음 중 하나면 “일단 계속”으로 넘기지 않고 현재 로그·temp를 보존한 채 원인을
판정한다.

1. wrapper lock PID 또는 MFA/Python 프로세스가 사라졌는데 성공 marker가 없음
2. alignment 단계에서 30분 이상 진행 신호가 없고 CPU 누적 증가도 10초 미만
3. traceback, DB lock, SQL export 오류, 디스크 부족, 강제종료 신호
4. D:가 해당 연도 시작 문턱(2021 55GB, 그 밖 45GB) 아래로 내려감
5. MFA exit 0인데 TextGrid 0건
6. 연도별 TextGrid/lab coverage가 99% 미만
7. 4-tier 병합 실패 또는 tier/duration 검증 실패
8. 기존 `06_textgrid_eojeol` 정본에 예상하지 않은 쓰기 발생

자동 삭제·marker 수정·재실행은 하지 않는다. 입력계약이 맞는 temp는 원인
수정 뒤 이어가기에 사용한다.

## 후속 추적대장

| ID | 관측 | 지금 판단 | 후속 조치 | 상태 |
|---|---|---|---|---|
| CSV-001 | full build `speaker_missing=1,767` | MFA 차단 아님. 연구 CSV 사회변수 결측 가능성 | 원 JSON/metadata에 실제 화자 ID가 없는지 ID 목록과 사유 분류 | 대기 |
| PRON-001 | `pron_reference_unresolved=55,198`; 2020은 6,214 | 숫자·기호 읽기를 추측하지 않은 기록. MFA 전체 재실행 사유 아님 | 우리말샘·legacy 발음 결합 뒤 해결/미해결을 구분해 최종 CSV에 유지 | 대기 |
| PRON-002 | 2020 `empty_reference_form=53` | Hangul-only 안전 정책상 lab 생성 불가 | utt_id·원전사·숫자/기호 유형을 추출해 수동/사전 보완 여부 결정 | 대기 |
| AUDIO-001 | 2020 search 행 중 `wav_missing=544` | 없는 음성을 MFA가 만들 수 없으므로 연도 전체 재실행 사유 아님 | 기존 coverage inventory·원 PCM/원 corpus와 대조해 복구 가능/불가 분류 | 대기 |
| AUDIO-002 | MFA 로드 870,158 − usable lab 869,840 = 318 | MFCC 실패가 아님. 4개 MFCC log 합계 869,840, `errors on 0` | 연도 완료 후 WAV-only/비대상 ID 318개를 추출해 AUDIO-001과 교차표 작성 | 대기 |
| SESSION-001 | MFA speaker 2,231 vs search session 2,232 | usable lab이 0인 세션 가능성. 현재 정렬 품질 차단 근거는 아님 | AUDIO/PRON 결측 ID와 세션별 usable lab 수를 대조 | 대기 |
| ALIGN-001 | 2020 기본 `beam=10/retry_beam=40`: 성공 866,196, 난정렬 3,644, 합계 869,840 | 성공률 99.581%; 99% 자동 차단 기준은 통과. 전체 재실행보다 누락 ID 선택 재시도가 적절 | export 뒤 usable lab − TextGrid 차집합으로 3,644 ID를 저장하고 확대 beam 격리 재시도 | 진행 |
| EXPORT-001 | 2020 export 시작 후 31분까지 TextGrid 0건 | worker CPU·메모리 증가, 오류 0. 5.61GB DB와 phone/word interval CSV 1.52GB/262MB를 준비·조회하는 단계로 추정 | 첫 출력 확인 완료. 다음 연도에서 초기 지연 기준으로 재사용 | 관찰 완료 |
| EXPORT-002 | DB job 4개인데 export 하위 Python worker는 시작 직후부터 1개만 생존 | 현재 worker는 정상 계산·I/O 중이라 정확성 차단 사유는 아님. 다만 50,000개 청크가 사실상 순차 처리되어 전 연도 병목 가능 | 현 실행은 유지. 배치 종료 후 `finished_adding` 1초 경쟁 조건과 queue 전달을 재현하고 sentinel/ack 방식으로 보완·파일럿 벤치마크 | 대기 |
| MON-001 | 1분 heartbeat가 D 로그에 영구 기록되지 않음 | 현재 CPU 표본으로 생존 확인 가능하나 사후 감사성이 약함 | 현 배치 종료 후 heartbeat를 `Say`/별도 JSONL에도 쓰도록 코드 보완 | 대기 |
| MON-002 | 제한된 셸에서 `Win32_Process` I/O 바이트 조회가 `AccessDenied` | MFA 실행 오류 아님. 관리자 권한 없이도 CPU·RAM·파일 수·최근 갱신 시각으로 진행성 판정 가능 | 다음 실행 전 monitor helper에 권한 불필요한 계측만 남기고 CIM 표본은 선택 기능으로 분리 | 대기 |
| MON-003 | 약 20만 TextGrid에서 `Get-ChildItem -Recurse | Sort-Object LastWriteTime` 감시 조회가 120초 timeout | MFA 실행 오류 아님. 감시 자체가 소형파일 전수 정렬로 D: I/O를 소비 | 이후 전체 정렬 금지. `.NET EnumerateFiles` 스트리밍 개수와 성능 카운터 I/O를 사용하고, 현 배치 뒤 helper에도 반영 | 적용 중 |
| POWER-001 | 현재 균형 조정 전원 구성에서 AC 절전은 사용 안 함, 배터리 절전은 600초 | 전원 연결 상태에서는 무인 실행 가능하지만 전원 분리 시 10분 후 작업이 일시정지될 수 있음 | 배치 동안 전원 어댑터 연결 유지. 최종 보고서에 무인 실행 조건으로 명시 | 적용 중 |

## 2020 완료 직후 필수 게이트

1. `align_done`의 lab/TextGrid 수와 coverage 확인
2. usable lab 869,840과 MFA 원출력 TextGrid의 basename 차집합을 저장해
   기본 beam 난정렬 3,644건을 ID 수준으로 복원
3. 4-tier 병합 성공·tier 이름·WAV/TextGrid duration 확인
4. staging 표본을 세션·화자·경고유형별로 추출
5. 정본 자동 승격 금지 확인
6. 위 추적대장의 318/544/53건이 서로 어떤 집합인지 ID 수준으로 대조

### 2020 alignment worker summary

정렬 옵션: `beam=10`, `retry_beam=40`, `num_jobs=4`.

| job | 성공 | 난정렬 | 입력 합계 |
|---:|---:|---:|---:|
| 1 | 216,437 | 1,052 | 217,489 |
| 2 | 216,866 | 641 | 217,507 |
| 3 | 216,563 | 789 | 217,352 |
| 4 | 216,330 | 1,162 | 217,492 |
| **합계** | **866,196** | **3,644** | **869,840** |

4개 MFCC job의 입력 합계도 869,840이고 MFCC 오류는 모두 0이다. 따라서
현재 3,644건은 입력 누락이나 특징 생성 실패가 아니라 기본+retry beam에서도
정렬을 얻지 못한 발화로 분리해 다룬다.

### 2020 export 시작 확인

- 01:16:08(내보내기 시작 후 약 46분): MFA 본체와 export worker가 모두 생존했고, 10초 합산 CPU 증가량은 4.16초, 오류 일치는 0건이었다.
- 01:16:24: `D:\mfa_eojeol_out\2020`에서 TextGrid 49,948개를 처음 확인했다. 따라서 `EXPORT-001`은 거짓 성공이나 완전 정지가 아니라, 5.61GB 정렬 DB를 읽고 첫 출력 묶음을 준비하는 초기 지연으로 판정한다.
- 01:17:20: TextGrid 수는 49,948개로 같았지만 export worker CPU가 1,110.39초에서 1,132.11초로 증가했다. 파일을 약 5만 개 단위로 기록하거나 다음 묶음을 준비하는 패턴일 수 있으므로, 오류가 없는 한 작업을 중단하지 않고 다음 묶음 증가를 확인한다.
- 01:23:46: TextGrid는 여전히 49,948개였고 최신 파일의 기록 시각은 01:05:49였다. 01:25:03 export worker 누적 CPU는 1,296.66초, RAM은 469.4MB로 계속 증가했다. 즉 약 20분 동안 새 파일은 없지만 worker 계산은 진행 중이다. 첫 묶음 준비에도 약 35분이 걸렸으므로 다음 묶음까지 장시간 지연될 가능성을 열어 둔다.
- 설치된 MFA 소스의 `construct_textgrid_output()`에는 프로젝트가 2026-07-22 적용한 `_CHUNK = 50_000` 안전 패치가 있다. 첫 50,000개 중 정렬 성공 49,948개가 출력된 것이므로 고정된 49,948은 부분 성공 상한이 아니라 첫 SQL 청크 완료 수량이다.
- 01:46:13에도 TextGrid는 49,948개였지만 worker 누적 CPU는 1,683.22초로 증가했다. Windows 권한 불필요 성능 카운터 `\Process(python#1)\IO Data Bytes/sec`에서 PID 23616이 약 40.2MB/s, MFA 본체 PID 22268이 0MB/s로 측정됐다. 두 번째 50,000개 청크의 phone/word interval 조회·정렬이 실제 진행 중이므로 교착으로 판정하지 않는다.
- 01:51:57 두 번째 50,000개 청크가 끝나 TextGrid가 99,672개로 증가했다(두 번째 청크 증가분 49,724개). 01:58:48에는 다음 청크 I/O가 약 20.2MB/s로 계속됐다. 첫 청크 49,948개와 합쳐 100,000개 입력 중 99,672개가 출력된 것이므로 청크 안전 패치와 난정렬 제외가 의도대로 작동한다.
- 02:10:31: TextGrid 99,672개, 최신 기록 01:51:57로 아직 세 번째 청크 출력 전이다. worker I/O 약 20.3MB/s, 마지막 10초 CPU +3.48초, 오류 0건, D: 여유 303.5GB이므로 정상 SQL 조회 단계로 판정했다.
- 02:37:49 세 번째 50,000개 청크가 끝나 TextGrid가 149,405개로 증가했다(세 번째 증가분 49,733개). 150,000개 입력 기준 누적 출력률은 99.603%로 전체 alignment 성공률 99.581%와 일관된다. 02:43:25 다음 청크 I/O 약 20.6MB/s, 오류 0건, D: 여유 303.3GB이므로 정상 진행 판정을 유지한다.
- 03:29:55 네 번째 50,000개 청크 완료를 확인했다. TextGrid 199,366개(증가분 49,961개), 200,000개 입력 기준 누적 출력률 99.683%, worker RAM 530.6MB였다. 직후 다음 청크 I/O 약 16.7MB/s, 오류 0건, D: 여유 303.0GB로 정상 진행이다.
- 같은 점검에서 최신 TextGrid를 찾기 위한 전수 `Sort-Object LastWriteTime`이 산출물 약 20만 개에서 120초 timeout됐다. 실행 문제가 아니라 감시 쿼리 병목이다. 스트리밍 개수만 세는 방식은 35.76초에 끝났으므로 이후 최신 파일 전수 정렬을 중단하고 `MON-003`으로 추적한다.
- 첫 file batch 크기는 약 217,540개이므로 50,000개 청크 4개 뒤 약 17,540개 소청크가 이어진다. 04:23 무렵 D: 사용량 약 0.2GB 증가와 CPU 전환이 나타났고, 이후 worker I/O가 약 6KB/s까지 낮아져 첫 batch 결과 큐 정리·다음 batch 전환 구간으로 관찰됐다.
- 04:38:26까지 5분 CPU가 약 93초 증가하고 마지막 10초 +3.05초, 직후 worker I/O 약 15.4MB/s로 회복됐다. 같은 PID 23616이 다음 큰 batch 처리를 시작했으므로 나머지 batch가 유실된 것은 아니며, 단일 worker 순차 처리 병목이라는 `EXPORT-002` 판정을 유지한다.
- 05:31:39 D: 여유가 302.8GB에서 302.6GB로 감소했고, worker는 종료되지 않은 채 다음 조회 I/O 약 27.1MB/s를 보였다. 고정 50,000개 청크 구조와 전환 패턴상 두 번째 큰 file batch의 첫 청크가 완료되고 다음 청크로 넘어간 것으로 판정한다. 정확한 누적 TextGrid 수는 export I/O가 낮아지는 시점 또는 연도 완료 게이트에서 확인한다.
- 06:41 무렵 worker CPU가 10초에 9.64초, I/O 약 2.0MB/s로 올라 소형 TextGrid 다량 쓰기 단계를 직접 확인했다. 06:52:08에는 D: 여유가 302.5GB에서 302.2GB로 감소했고, 직후 I/O가 14.6~15.2MB/s로 회복돼 다음 50,000개 조회에 진입했다. 오류 0건이며 동일 worker PID 23616이 연속 처리 중이다.
- 이 전환 구간에서 `.NET EnumerateFiles` 120초와 `rg --files` 30초가 모두 timeout됐다. D: export가 활발할 때 정확한 누적 파일 수를 억지로 세면 감시가 본 작업과 경쟁하므로, 청크 경계에서는 CPU·D: 사용량·I/O로 전환을 판정하고 정확 수량은 디스크 부하가 낮거나 연도 완료 게이트에서 확인한다.
- 실측 청크 간격은 첫 청크 약 35분, 두 번째 청크 약 46분이다. 870,158개는 총 18개 청크이므로 단일 worker가 유지되면 2020 export만 대략 11~13시간 범위를 예상한다. 이는 결과 무결성 문제는 아니지만 전 연도 소요시간을 크게 늘리는 병목이며, 현 실행 뒤 `EXPORT-002` 보완의 우선순위를 높인다.
- DB 읽기 전용 조회에서 `job=4`, `file=870,158`을 확인했다. MFA `base.py`는 약 217,540개씩 4 batch와 4 export worker를 만들지만, 현 실행에서는 하위 Python worker가 처음부터 1개만 보였다. 대형 `multiprocessing.Queue`에 batch를 넣은 뒤 고정 1초 후 `finished_adding`을 세우고 worker가 1초 `Empty`에서 종료하는 경쟁 조건이 유력하다. 정확성은 유지되나 순차 export 병목이므로 `EXPORT-002`로 분리한다.
- 더 강한 진행성 판정을 위해 `Win32_Process`의 읽기·쓰기 바이트를 30초 표본 측정하려 했으나 제한된 셸에서 `0x80041003 AccessDenied`가 발생했다. 실행 실패가 아니라 감시 계측의 제약이다. 관리자 권한을 추가로 요구하지 않고 CPU·메모리·출력 개수·최신 파일 시각·오류 파일을 사용한다(`MON-002`).
- 이 관찰은 다음 연도에도 재사용한다. export 직후 TextGrid가 0개라고 곧바로 실패 처리하지 않고, worker CPU·오류·첫 출력 지연·출력 묶음 증가를 함께 판정한다.
- 11:15:34→11:26:26 점검에서 Python 누적 CPU가 43,566.7초에서
  43,903.1초로 336.4초 증가했고 D: 여유는 301.6GB에서 301.3GB로
  감소했다. 직후 export worker PID 23616의 I/O를 두 번 표본 측정한
  결과 약 16.3MB/s와 14.9MB/s였으며 오류 문자열은 0건이었다.
  따라서 2020 export는 계속 전진 중이고, 지금 중단하거나 처음부터
  재실행할 근거는 없다.
- 11:37:47 worker I/O가 약 5~7KB/s, 마지막 10초 CPU가 0.28초까지
  낮아졌으나 10분 누적 CPU는 121.3초 증가했다. 중단하지 않고 기존
  batch 전환 패턴과 비교 관찰했다. 11:48:23에는 누적 CPU가 다시
  179.3초 증가하고 마지막 10초 CPU 3.33초, worker I/O 약 15.7MB/s로
  회복됐다. 이는 정지가 아니라 결과 큐 정리·다음 청크 전환 구간이므로
  재시작 대상이 아니다.
- 11:59:22→13:02:28 동안 Python 누적 CPU는 44,638.6초에서
  46,455.9초로 1,817.3초 증가했고 D: 여유는 301.0GB에서 300.3GB로
  감소했다. 12:21·12:52에는 worker가 10초 표본에서 각각 10.08초,
  10.11초를 사용해 TextGrid 대량 쓰기를 확인했고, 그 사이에는
  17.5MB/s 안팎의 조회 I/O가 확인됐다. 오류 0건, 동일 PID 유지,
  완료 마커 전이므로 정상 export 판정을 유지한다.
- 13:02:28→15:38:42 동안 Python 누적 CPU는 46,455.9초에서
  49,498.4초로 3,042.5초 증가했고 D: 여유는 300.3GB에서 299.4GB로
  감소했다. 청크 경계에서 10초 CPU와 I/O가 잠시 낮아지는 구간이
  반복됐으나 다음 점검에서 모두 회복됐고, 오류 0건·동일 worker
  PID 23616을 유지했다. 2020 완료 마커 전이므로 계속 관찰한다.
- 16:27:13 MFA stderr에 `Finished exporting TextGrids`와
  `Done! Everything took 94172.982 seconds`가 기록됐다. MFA 전체 구간은
  약 26시간 9분이었고, 그중 export만 00:30:15→16:27:13 약 15시간
  57분이 걸렸다. 이는 정렬 자체보다 단일 export worker 병목이 전체
  소요시간을 지배한다는 `EXPORT-002`의 강한 실측 근거다.
- 16:28:54 `2020.align_done` 생성 확인: lab 869,840,
  TextGrid 866,196, coverage 99.58%, 입력계약
  `fa96caf4a37c556b929febbfa172500b2dfe615cfb554e816b070766bc8b3038`.
  차이 3,644건은 worker alignment 난정렬 합계와 정확히 일치한다.
  temp 정리 뒤 D: 여유는 299.1GB에서 321.0GB로 회복했고, 16:28:55
  Python PID 11944가 4-tier 병합을 시작했다. 아직 `merge_done` 전이므로
  2020 파이프라인 완료로 판정하지 않는다.

## 2020 최종 완료 감사

- `2020.merge_done`: 2026-07-26 18:12:14 생성. align과 같은
  입력계약 ID이며 staging과 기존 정본 경로가 분리되어 있고
  `promotion_required=true`다.
- 병합 보고서:
  `D:\mfa_eojeol\logs\merge_report_2020_eojeol_g2p_2020_20260725_140554.json`
  - source TextGrid 866,196
  - created 866,196
  - failed 0
  - form missing 0
  - morpheme tier missing 0
  - archived invalid 0
  - elapsed 6,188.807초(약 1시간 43분)
  - status success
- 독립 파일시스템 전수 열거:
  TextGrid 866,196, 0바이트 0, 세션 폴더 2,231, 보고서 차이 0.
- 경계 표본 감사:
  5개 균등 간격 세션의 처음·중간·끝 파일 15개를 직접 파싱했다.
  tier 순서는 모두 `words`, `phones`, `morphemes`, `utterance`였고,
  모든 tier가 0초에서 시작해 전체 duration에서 끝나며 interval 간
  공백·겹침이 없었다. 실패 0.
  - 첫 감사 시 파서를 `realign_eojeol_build_corpus`에서 import해
    `ImportError`가 1회 발생했다. 실제 병합 코드의 import를 따라
    `retrofit_textgrid_2020_2024`로 바로잡은 뒤 재실행해 통과했다.
- 18:23:30 wrapper 종료:
  `years_completed=["2020"]`, 2021 child는 가드 exit 75로 작업 시작 전
  종료. wrapper raw summary의 `status=failed`는 의도적 pause를 모르는
  기존 상태모델 때문이며 2020 실패가 아니다.
- 18:27:04 후처리 확인:
  lock 없음, 2020/2021 temp 없음, MFA 중간 output 없음,
  staging 2020 있음, staging 2021 없음, 2021 done marker 0.
- pre-MFA CSV build meta:
  status success, 5,103,356발화, 17,156세션, meta/json 누락 0,
  eojeol mismatch 0. `speaker_missing=1,767`과
  `pron_reference_unresolved=55,198`은 완료 차단이 아닌 후속 연구
  데이터 정비 대상으로 유지한다.

따라서 “2020 파이프라인 단계 완료”는 입증됐다. 이는 모든 발화가
정렬됐다는 뜻은 아니며, 869,840 usable lab 중 3,644건(0.419%)은
난정렬로 TextGrid가 없어 후속 ID 목록 추출과 확대 beam 부분 재시도가
필요하다. 2021–2025는 시작하지 않았다.

문서 상태: 실행 종료 뒤 `docs/decisions`로 이관한 최종 점검대장.
