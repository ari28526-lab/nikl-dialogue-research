# 수정 전 코드 대비 현재 MFA 실행시간 분석

작성일: 2026-07-27

## 비교 기준

이 문서에서 말하는 “수정 전”은 2020 실행이 아니다. Codex의 대량 작업
안전성 개선 직전에 보존한 다음 아카이브를 기준으로 한다.

```text
archive/code_pre_bulk_20260724
기준 브랜치 main
기준 커밋 e1075ee
```

비교 자료:

- 수정 전 코드의 SHA256 manifest
- `D:\mfa_eojeol\logs\eojeol_realign_20260716_*.log` 이후 과거 로그
- 현재 2021 run의 lab 보고서·stderr·heartbeat
- 2020 완료 run은 현재 경로의 병목 실측 참고자료일 뿐, 수정 전 기준선으로
  대체하지 않는다.

## 결론

현재 파이프라인 전체가 같은 작업을 더 느리게 수행한다고 볼 증거는 없다.
수정 전 작업이 빠르게 보인 주요 원인은 기존 파일을 내용 확인 없이 건너뛰거나,
부분·거짓 성공을 완료로 처리한 데 있다.

반면 현재는 최초 입력계약 검증과 독립 전수 QC가 추가돼 실제로 시간이 더 드는
구간도 있다. 이 시간은 결과의 연구적 재사용 가능성을 확보하는 비용이며,
완료된 동일 입력계약의 재실행마다 반복하지 않도록 marker와 hash로 제한한다.

## lab 단계의 직접 비교

수정 전 `realign_eojeol_build_corpus.py`는 다음과 같이 `.lab` 파일이 존재하면
내용을 읽지 않았다.

```python
if not force and f"{u}.lab" in names:
    skipped += 1
    continue
```

따라서 기존 lab이 많은 재실행은 과거 로그에서 약 30–60초로 보였다. 하지만
다음은 검증하지 않았다.

- 동결 pre-MFA CSV의 `pron_reference_form`과 내용이 같은가
- 숫자·기호 reference 교정이 반영됐는가
- 다른 입력으로 만든 stale lab인가
- 빈 reference로 바뀐 발화의 구 lab이 남았는가

현재 2021 최초 입력계약 검증은 약 14분 40초 동안 다음을 실제로 수행했다.

| 항목 | 수량 |
|---|---:|
| 기존 내용 일치 전수 확인 | 1,335,015 |
| 불일치 재작성 | 38,320 |
| 신규 생성 | 186 |
| WAV 누락 | 0 |
| 빈 reference | 399 |

그러므로 수정 전 30–60초와 현재 14분 40초는 같은 작업의 속도 비교가 아니다.
수정 전 최초 전량 lab 작업은 2026-07-17 V3 백신 간섭으로 약 9시간 30분
걸렸고, 이 실측과 비교하면 현재 경로가 더 빠르다.

동일 입력계약의 `passed` marker가 생긴 뒤에는 현재 코드도 전수 재확인을
건너뛴다. 차이는 단순 존재가 아니라 CSV meta SHA256과 lab 입력 버전이 같은
경우에만 재사용한다는 점이다.

## 수정 전의 빠른 MFA 완료가 유효한 비교가 아닌 이유

과거 로그에는 2021 temp 재사용 후 약 2분 만에 MFA 완료로 표시된 실행이 있다.
그러나 즉시 4-tier 병합이 실패했다. 누적 실패 기록상 이 시기의 MFA는 대규모
SQLite `IN` 변수 한계로 TextGrid export가 전량 실패해도 exit 0을 반환할 수
있었고, 당시 러너는 temp를 정리했다.

다른 수정 전 clean 실행은 약 19시간 뒤 watchdog 오판으로 강제종료됐다.
따라서 다음 수치는 정상 완료 처리율로 사용하지 않는다.

| 과거 표시 | 실제 상태 |
|---|---|
| temp 재사용 뒤 약 2분 “완료” | 병합 실패; export 0/부분 성공 가능 |
| 약 19시간 실행 | watchdog 오살 뒤 temp 손실 |
| `.done` 즉시 skip | marker가 입력계약·실물 수량과 결합되지 않음 |

## 현재 코드에서 실제로 추가된 시간

- 최초 1회 lab 내용 전수 대조
- WAV·세션 구조·모델·패치 preflight
- 1분 heartbeat와 복구 가능한 상태 기록
- direct 4-tier 생성의 수량·hard-failure gate
- 완료 뒤 독립 4-tier 구조·coverage·WAV duration·누락 전수 QC

heartbeat는 1분마다 로그 끝과 프로세스 수치만 읽는다. 현재 MFA 실행 중에는
D: 전체 TextGrid 스캔을 하지 않으므로 감시 자체의 성능 영향은 미미하다.

## 속도 개선이 이미 확인된 부분

수정 전 기본 경로는 MFA raw 2-tier를 전량 쓴 뒤 다시 읽어 4-tier로
재작성했다. 2020 실측에서 raw export 15시간 57분, 별도 merge 1시간
43분이 걸렸다.

DB direct 경로는 21,962개 실자료에서 기존 경로와 tier·라벨·모든 시간이
전수 일치했고, worker 4개로 73.983초가 걸렸다. 2021 전량에서는 raw export를
생략하므로 이 구간은 수정 전보다 크게 짧아질 것으로 예상한다. 전량 실측 전에는
파일럿 처리율을 그대로 외삽해 완료시간을 확정하지 않는다.

## 남은 개선 후보와 수용 조건

### 1. G2P/OOV 발음 cache

현재 장시간 `Generating pronunciations` 구간은 worker 4개의 CPU가 계속
증가해 교착은 아니다. 2022 소표본에서 동결 입력계약의 고유 OOV 어절을
미리 G2P해 versioned 확장 사전으로 제공하는 A/B 시험을 검토한다.

수용 조건:

- baseline과 단어·phone label이 전수 동일
- 우리말샘 예외 발음과 규칙 reference의 역할을 혼동하지 않음
- 실제 실현 판정값으로 사용하지 않음
- 소표본 실측에서 유의미한 시간 감소

### 2. lab 세션 단위 bounded 병렬화

2022는 신규 lab 약 866,106개를 써야 한다. session 단위 2–4 worker를
시험하되 SSD small-file I/O 경합으로 오히려 느려질 수 있으므로 단일·2·4
worker 파일럿을 비교한다.

수용 조건:

- 생성 내용과 SHA256 전수 동일
- 원자적 쓰기·stale archive 정책 유지
- 세션별 오류가 전체 성공으로 묻히지 않음

### 3. QC 중복 I/O 축소

direct writer가 생성 시 수행한 tier 검증을 manifest에 남기고, 독립 QC는
최초 입력계약에서 전수 수행한다. 같은 계약의 재실행은 파일 수·ID 차집합·
manifest hash로 빠르게 확인하되, 코드·입력·산출 hash가 달라지면 전수 QC를
다시 수행한다.

### 4. worker·batch 실측 조정

MFA `num_jobs`와 direct writer worker를 무조건 늘리지 않는다. CPU 사용률,
D: 처리량, SQLite read 경합을 함께 측정해 2022 소표본에서 가장 빠르면서
동일한 결과를 만드는 조합만 채택한다.

## 2021 완료 뒤 채울 항목

- setup/G2P/MFCC/graph 각 실제 경과시간
- alignment와 interval collect 시간
- direct 4-tier 실제 발화/초와 peak disk
- 독립 QC 시간
- 수정 전 정상 완료라고 입증 가능한 동일 규모 run 존재 여부
- 2022 A/B 파일럿에 사용할 병목 우선순위
