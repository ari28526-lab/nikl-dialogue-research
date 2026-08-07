# 2020–2025 연구 인프라 전수 생산 RUNBOOK

최종 갱신: 2026-08-07 KST

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
8. 공통 대화 음원 품질층과 연도별 동반표 결합

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
- 겹침·소음·잘림 의심처럼 정렬 가능한 품질 문제는 MFA 본체에서 자동 제외하지
  않는다. 정렬 결과를 보존하고 연구자 승인 뒤 `analysis_only`로 표시한다.
- `<=44B`, 대응 불명, 불가능 시간처럼 정렬 자체가 성립하지 않는 항목만
  `alignment_and_analysis` 계약으로 본체에서 분리한다.
- 실패 시 전체 연도를 지우지 않고 DB·세션·stage checkpoint에서 재개한다.
- 장시간 명령을 주기 전에 PowerShell 안전·5.1 검사와 가능한 preflight를 먼저
  통과시킨다.

## 3. 현재 시작점

```text
2020 Gate B 완료·동결
  → 2021 MFA·6-tier·기계 감사·발음 참조 전수 완료
  → 2021 공식 연구자 24/24 승인·2021→2022 Gate 완료
  → 2022 MFA 계산 완료·보존 DB
  → 2022 post-MFA exact-ID 438건 명시 승인·preflight 완료
  → 2022 direct export·6-tier·동반표·독립 Gate  ← 현재
```

## 4. 2021 Gate 종료 — 완료

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

연구자는 1–20번과 21–24번 총 24개 표본을 확인했다. 승인 절차는 CSV 수동
편집을 요구하지 않는다. 승인자·명시 문장·정확한 행 수를 받은 뒤 아래 단일
명령이 원 pending CSV를 바이트 동일 보존하고, identity를 검증한 뒤 승인 CSV와
결정·승인 JSON을 원자적으로 만든다.

모든 행이 기록된 뒤에만 다음 승인기를 사용한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\approve_production_year_sample_review.ps1" `
  -Year "2021" `
  -ApprovedBy "ari30" `
  -ApprovalStatement "2021 생산 표본 24개를 직접 확인했으며 연결·6-tier·정렬·검색 정보가 대체로 적절함을 승인한다. 실제 음운 실현 판정은 수행하지 않았다." `
  -ExpectedRowCount 24 `
  -ExecutionQueueId "mfa_checkpoint_qc_2021_20260805_retry1"
```

이 명령은 연구자 결정을 기록할 뿐 자동으로 승인 여부를 추론하지 않는다. 같은
인자로 재실행해도 승인 CSV·원 pending archive SHA가 바뀌지 않는다.

승인 보고서 생성 뒤 다음 읽기 전용 Gate가 `passed`여야 한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\preflight_production_next_year_gate.ps1" `
  -PriorYear "2021" `
  -ExecutionQueueId "mfa_checkpoint_qc_2021_20260805_retry1"
```

2021은 2026-08-06에 이 Gate를 실패 검사 0으로 통과했다. Gate는 일반
`direct_db_research_6tier_v1`과 동일 schema의 checkpoint-resume 실행 mode를
함께 인정하고, 보존 DB 완료는 같은 계약의 `direct_db_ready` marker로 확인한다.

## 5. 2022 post-MFA 완료 절차

2022 MFA 계산은 완료됐고 `D:\mfa_tmp\2022\2022.db`를 보존했다. 활성 LAB
865,128개 중 864,690개가 정렬됐으며 interval이 없는 438개는 exact-ID 검토
집합이다. 전체 MFA를 다시 실행하지 않는다.

1. 438개와 aligned control의 연결·구조·음향 근거표를 확정했다.
2. 연구자는 438건의 기술적 미정렬 exact-ID 범위를 명시 승인했다.
3. 승인 materialization과 결합 승인 preflight가 통과했다.
4. 보존 DB에서 direct export를 재개한다.
5. 6-tier·동반표·독립 전수 감사·한 번의 연구자 표본 Gate를 완료한다.
6. 품질 플래그는 동반표에 결합하되 실제 실현 여부를 자동 판정하지 않는다.

재개 명령은 `resume_year_export_after_post_mfa_review.ps1`을 사용한다. 이 명령은
기존 1,231건과 새 438건을 결합한 계약을 만든 뒤 같은 `direct_db_ready` DB에서
export부터 시작한다. MFA 정렬 계산은 다시 실행하지 않는다.

실행 queue ID와 장시간 명령은 위 검사 직후 현재 값으로 고정해 사용자에게 한 줄로
제공한다. 문서에 날짜가 지난 queue ID를 미리 복사해 두지 않는다.

## 6. 연도별 반복 절차

2022–2025는 다음 순서만 반복한다.

```text
직전 연도 Gate
  → 당해 morph_search.v3/source contract
  → 공통 음원 구조 감사·음향 표본·<=44B 전수 inventory
  → 승인 제외·LAB·모델 preflight
  → MFA·보존 DB
  → post-MFA exact-ID 회계
  → 6-tier·동반표
  → 독립 전수 감사·DB 표본
  → 연구자 표본 1회
  → 다음 연도 Gate
```

2023의 승인 제외 103,930건은 이미 결정된 안전 본체 계약이다. main MFA에 억지로
섞지 않고 후속 회수 shard와 계속 분리한다. 2023의 header-only WAV 75건은 이
승인 집합에 전부 포함돼 있으므로 같은 후보 승인을 반복하지 않는다. 2024·2025는
전수 `<=44B` WAV가 0건이다. 구조 겹침과 noise proxy는 자동 제외가 아니라
동반표의 검토 열이다.

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

- 공식 표본 중 실제로 남은 소수 행의 WAV·TextGrid 확인 또는 정확한 exact-ID
  기술 제외 집합의 명시 승인
- 안전검사와 preflight가 통과한 장시간 PowerShell 시작

이미 승인한 제외 범주, 통과한 표본, 완료 연도는 반복 검토하지 않는다.
