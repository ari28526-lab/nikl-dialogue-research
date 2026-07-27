# 2022 개선 MFA 실행안 — 2020·2021 실측 반영

작성 시작: 2026-07-27
상태: **초안 — 2021 전량 완료·QC 뒤 확정**
원칙: 2022 전량은 사용자 확인 전 시작하지 않음

## 목적

2020에서 발견한 raw TextGrid export 병목과 2021 direct-DB 전량 실측을 함께
반영해, 2022를 처음부터 재현 가능하고 복구 가능한 방식으로 수행한다.

연구 흐름은 변하지 않는다.

```text
동결 CSV에서 형태소·표기/음운형태 환경 후보 검색
  → WAV·4-tier TextGrid 수집
  → 필요한 구간 KOINA
  → 연구자의 음성·TextGrid 수동 실현 판정
```

MFA `phones`는 대략적 G2P 시간정렬이며 실제 실현 판정값이 아니다.

## 2022 입력 기준선

읽기 전용 감사:
`outputs/reports/AUDIT_mfa_year_readiness_2021-2025_20260726.json`

| 항목 | 2022 |
|---|---:|
| pre-MFA CSV 세션 | 2,654 |
| 검색행 | 866,359 |
| WAV | 878,157 |
| 예상 usable lab | 866,106 |
| 현재 lab | 0 |
| 빈 reference form | 253 |
| reference form 변경 | 43,972 |
| 미해결 기호 | 10,106 |
| search master 밖 WAV | 11,798 |
| 과거 source PCM 없음 위험 | 15 |

`search master 밖 WAV`는 주로 빈 form 등으로 검색 입력에 들어가지 않는 원
음성이다. 예상하지 않은 lab이 함께 남아 있지 않으므로 그 자체를 오류로
간주하지 않는다.

## 2020에서 계승할 개선

- 동결 pre-MFA search master와 lab SHA256 입력계약
- 다른 계약의 temp를 삭제하지 않고 archive
- exit 0만 믿지 않는 coverage·실물 수량 gate
- 1분 heartbeat와 watchdog
- 실패 시 다음 연도로 진행하지 않음
- 기존 `06_textgrid_eojeol` 및 원 WAV 비변경
- staging 전수검증 뒤에만 별도 승격

2020의 가장 큰 병목은 raw TextGrid export 15시간 57분과 후속 4-tier merge
1시간 43분이었다. 2022에서는 이 구 경로를 기본으로 사용하지 않는다.

## 2021에서 확정·조정할 개선

현재 2021은 다음 경로를 실제 전량 실행 중이다.

```text
pron_reference_form lab
  → MFA word/phone interval SQLite
  → raw 2-tier 생략
  → DB에서 4-tier partial 병렬 생성
  → coverage·hard-failure gate
  → final staging 이동
  → QC 전 DB 보존
```

2022 확정 전에 2021에서 다음 실측을 가져온다.

1. lab 검증·재작성 시간
2. corpus loading, G2P/MFCC/graph, alignment, interval collect 시간
3. temp peak와 D: 최소 여유
4. direct 4-tier 발화/초와 worker 4의 안정성
5. 난정렬·source 결함·form/morpheme 누락 수
6. heartbeat 단계 판별과 watchdog 오판 여부
7. direct 결과의 tier·양끝 경계·duration 전수검사

2021 완료 전에는 이 항목을 추정치로 확정하지 않는다.

2021의 G2P 교차점검에서 MFA가 주 Python 외에 보조 Python 4개를 사용하고,
보조 작업 각각의 CPU가 지속 증가하는 것이 확인되었다. 기존 heartbeat의
프로세스 트리 합산 CPU는 정상 진행을 반영했지만, 사람이 주 Python 하나만
점검하면 정체로 오판할 수 있다. 2022 실행 전 모니터링 출력에는 최소한
`전체 tree CPU`, `활성 worker 수`, `tree RAM`을 함께 표시한다.

## 2022 고유 병목과 대응

### lab 866,106개 신규 생성

2021은 기존 lab 133만 개를 검증하면서 38,320개만 재작성했지만, 2022는 현재
lab이 0개다. 따라서 정렬 이전의 소형파일 쓰기 비용이 2021보다 상대적으로
커질 수 있다.

대응:

- 세션당 디렉터리 목록 1회 캐시 유지
- 발화별 존재확인 왕복 금지
- 원자적 `.lab` 쓰기
- 세션·발화 처리율과 ETA를 로그에 즉시 출력
- lab marker는 입력계약이 정확히 같을 때만 재사용

2021 완료 뒤 실제 SSD 쓰기율을 반영해 ETA를 계산한다. lab 생성이 느리다고
MFA temp를 삭제하거나 runner를 중복 실행하지 않는다.

### known source 위험 15건

과거 PCM 감사의 `PCM 없음` 15건은 사후 미정렬 inventory에서 먼저 source
결함 후보로 분류한다. 현재 감사에서는 44 byte 미만 WAV가 없었으므로 전량
시작 자체를 막지 않되, 난정렬과 같은 범주로 합치지 않는다.

### 2021 DB 보존과 용량

첫 2021 direct 실행의 SQLite DB는 QC 전까지 보존한다. 2022 preflight에서는
다음을 다시 계산한다.

- 2021 retained temp 실제 크기
- 2021 final 4-tier 실제 크기
- D: 남은 여유
- 2022 예상 temp peak

공간이 충분하더라도 2021 QC와 기록이 끝나기 전에는 2022를 자동 시작하지
않는다.

## 2022 GO/NO-GO

다음이 모두 충족돼야 GO다.

- 2021 final 4-tier 전수검증 통과
- 2021 align/merge marker가 같은 입력계약을 가리킴
- 2021 누락 inventory와 source/난정렬 분류 저장
- 2021 DB 보존 또는 검증 후 정리 결정 기록
- MFA 설치 패치 10/10
- 2022 세션 coverage 2,654/2,654
- D: `DATA_SSD` 및 실측 기반 여유 공간 통과
- 2022 temp/output/staging/marker 충돌 없음
- 다른 MFA·KOINA·Dropbox 대량 복사 없음

## 준비된 실행 명령

아래 명령은 **준비용 기록이며 아직 실행하지 않는다**.

```powershell
cd "C:\Users\ari30\research\2026_summer_research"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  ".\scripts\run_pre_mfa_bulk_safe.ps1" `
  -RunId "pre_mfa_v1_20260725" `
  -Years 2022 `
  -PreferD `
  -UseDirectDbExport
```

첫 2022 direct 결과도 QC 전에는 `-CleanupDirectDbAfterMerge`를 붙이지 않는다.

## 완료 후 채울 실측 표

| 지표 | 2020 | 2021 | 2022 실행 결정 |
|---|---:|---:|---|
| usable lab | 869,840 | 1,373,521 | 866,106 |
| lab 단계 | 12분 | 실행 후 입력 | 실행 후 예측 |
| corpus loading | 약 14분 | **30분 실측** | 잠정 15–20분, 전체 완료 뒤 확정 |
| setup/G2P/MFCC/graph | 7시간 27분 | 실행 후 입력 | 비례·보정 |
| alignment | 1시간 7분 | 실행 후 입력 | 비례·보정 |
| interval collect | 1시간 37분 | 실행 후 입력 | 비례·보정 |
| raw export | 15시간 57분 | direct면 생략 | 생략 |
| 4-tier 출력 | 1시간 43분 별도 merge | 실행 후 입력 | direct 예상 |
| temp peak | 약 33GB 미만 | 실행 후 입력 | 실측 기반 |
| 난정렬/누락 | 3,644 | 실행 후 입력 | source 위험과 분리 |
