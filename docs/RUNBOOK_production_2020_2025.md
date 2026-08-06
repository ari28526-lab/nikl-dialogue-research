# 2020–2025 연구 인프라 전수 생산 RUNBOOK

최종 갱신: 2026-08-06 KST

이 문서는 현재 생산 순서의 정본이다. 2021 완료 전의 상세 명령·시행착오는
`docs/archive/pre_2022_refresh_20260806/RUNBOOK_production_2020_2025_pre_2022_20260806.md`에
보존한다.

## 1. 완료 산출물

연도마다 다음 core를 완성한다.

1. pre-MFA `morph_search.v3` 7표와 source contract
2. 동결된 공통 Jamo r2 기준 MFA
3. 보존 DB와 exact-ID 미정렬 회계
4. 6-tier TextGrid
5. post-MFA gzip 동반표 4개
6. 입력·정렬·출력·DB 동등성 감사
7. 한 번의 연구자 인프라 표본 Gate

이후 파생층으로 우리말샘 occurrence·규칙/사전/MFA 비교표와 선택적 7번째
`pron_reference_utt` tier를 만든다. 파생층은 실제 음운 실현 판정이 아니며 다음
연도 MFA를 미루기 위한 새 gate가 아니다.

## 2. 절대 규칙

- 2020 Gate B를 다시 실행하지 않는다.
- 완료된 2021 MFA·DB·6-tier·7-tier를 다시 실행하지 않는다.
- 2020–2025는 같은 acoustic v3.3.0, Jamo G2P v3.2.0,
  `common_pron_mfa_r2_20260728`을 사용한다.
- 한 번에 한 연도만 실행한다.
- 직전 연도 연구자 Gate와 당해 연도 source contract가 없으면 시작하지 않는다.
- 승인 제외·post-MFA 미정렬은 삭제하지 않고 ID·사유·계약을 보존한다.
- 실패 시 전체 연도를 지우지 않고 DB·세션·stage checkpoint에서 재개한다.
- 장시간 명령을 주기 전에 PowerShell 안전·5.1 검사와 가능한 preflight를 먼저
  통과시킨다.

## 3. 현재 시작점

```text
2020 Gate B 완료·동결
  → 2021 MFA·6-tier·기계 감사·발음 참조 전수 완료
  → 2021 공식 연구자 검토 기록 대기  ← 현재
  → 2021→2022 Gate
  → 2022 검색표/source contract
  → 2022 MFA
```

2022 MFA는 아직 시작되지 않았다.

## 4. 2021 Gate 종료

현행 2021 생산 queue는 다음이다.

```text
mfa_checkpoint_qc_2021_20260805_retry1
```

정본 검토 파일:

```text
outputs/reviews/
  mfa_production_2021_mfa_checkpoint_qc_2021_20260805_retry1/
    03_RESEARCHER_REVIEW.csv
    03_RESEARCHER_REVIEW_MANIFEST.json
```

기계 감사·DB 표본은 통과했지만 공식 CSV 24행은 아직 모두 `pending`이다.
대화에서 확인한 20개를 어느 행인지 추측해 채우지 않는다. 기존 검토 증거를
대조하고 실제 미확인 행만 연구자에게 제시한다.

모든 행이 기록된 뒤에만 다음 승인기를 사용한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\approve_production_year_sample_review.ps1" `
  -Year "2021" `
  -ApprovedBy "ari30" `
  -ExecutionQueueId "mfa_checkpoint_qc_2021_20260805_retry1"
```

승인 보고서 생성 뒤 다음 읽기 전용 Gate가 `passed`여야 한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\preflight_production_next_year_gate.ps1" `
  -PriorYear "2021" `
  -ExecutionQueueId "mfa_checkpoint_qc_2021_20260805_retry1"
```

## 5. 2022 준비

2021 Gate가 통과한 뒤에만 수행한다.

1. `prepare_production_year_before_mfa.ps1 -Year 2022`로 검색표와 source
   contract를 checkpoint 생성한다.
2. 승인 제외 1,231건과 LAB marker의 input contract를 다시 대조한다.
3. 모델·공통사전·phone inventory SHA와 D: 여유 공간을 확인한다.
4. `start_next_mfa_year_after_gate.ps1`의 `-PreflightOnly`를 통과시킨다.
5. 같은 인자로 `-PreflightOnly`만 제거해 2022 한 연도를 시작한다.

실행 queue ID와 장시간 명령은 위 검사 직후 현재 값으로 고정해 사용자에게 한 줄로
제공한다. 문서에 날짜가 지난 queue ID를 미리 복사해 두지 않는다.

## 6. 연도별 반복 절차

2022–2025는 다음 순서만 반복한다.

```text
직전 연도 Gate
  → 당해 morph_search.v3/source contract
  → 승인 제외·LAB·모델 preflight
  → MFA·보존 DB
  → post-MFA exact-ID 회계
  → 6-tier·동반표
  → 독립 전수 감사·DB 표본
  → 연구자 표본 1회
  → 다음 연도 Gate
```

2023의 승인 제외 103,930건은 이미 결정된 안전 본체 계약이다. main MFA에 억지로
섞지 않고 후속 회수 shard와 계속 분리한다.

## 7. 발음 참조 파생층

각 연도 6-tier 뒤 다음을 같은 계약으로 생성한다.

1. 형태소 occurrence–사전 group 연결표
2. 원 표기 어절 규칙/사전/MFA 비교표
3. 발화 index
4. 필요 시 7-tier backfill

정본은 `docs/RUNBOOK_pronunciation_reference_layer_2020_2025.md`다. 2020과
2022–2025의 물리적 7-tier 전수 backfill은 core MFA와 D: I/O가 겹치지 않는
시간에 수행하며 다음 연도 진입을 막지 않는다.

## 8. 사용자에게 요청하는 경우

사용자 행동은 다음 두 경우로 제한한다.

- 공식 표본 중 실제로 남은 소수 행의 WAV·TextGrid 확인
- 안전검사와 preflight가 통과한 장시간 PowerShell 시작

이미 승인한 제외 범주, 통과한 표본, 완료 연도는 반복 검토하지 않는다.
