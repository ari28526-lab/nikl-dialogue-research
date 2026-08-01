# 2020–2025 연구 인프라 전수 생산 RUNBOOK

최종 갱신: 2026-08-01 KST

이 문서가 전수 작업의 유일한 실행 정본이다. 구 RUNBOOK·MONITOR·PILOT의
명령이 이 문서와 다르면 이 문서가 우선한다.

## 1. 목적과 완료 산출물

전수 작업은 실제 음운 실현을 자동 판정하는 과정이 아니다. 연구자가 후보를
찾고 음성·TextGrid를 연결해 판단할 수 있는 인프라를 만든다.

연도마다 다음을 완성한다.

1. pre-MFA `morph_search.v3` 7표
2. 공통 Jamo r2 기준 신규 MFA
3. 6-tier TextGrid
4. post-MFA gzip 동반표 4개
5. 입력·정렬·출력·DB·표본 동등성 manifest
6. 승인 제외 기록과 연구자 표본 확인 기록

## 2. 절대 순서

```text
workflow 수정·시험
  → 2020 검색표 완주
  → 2020 제외 후보 검토·승인
  → 2020 신규 MFA·6-tier·동반표·기계 QC
  → 2020 생산 표본 연구자 확인
  → Gate B
  → 2021–2025 연도별 체크포인트 큐
  → 7표+4표 join/Parquet·DuckDB
  → 우리말샘 1:N 보조표
  → 실제 연구 후보 bundle·KOINA/보조모델·수동 판정
```

2020 Gate B 전에는 2021–2025 MFA를 시작하지 않는다. 검색표 계산은 D: I/O와
겹치지 않는 때에 별도로 할 수 있으나 MFA를 미루기 위한 새 gate로 삼지 않는다.

## 3. 단계별 사용자 행동

### A. 2020 검색표

코드·시험이 커밋된 뒤 다음 wrapper 하나만 실행한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\resume_2020_morph_search.ps1"
```

기존 성공 shard 1은 SHA 검증 후 재사용한다. 완료 기준은
`annual_tables\YEAR_MANIFEST.json`의 `status=success`와 source contract 일치다.

### B. 2020 제외 후보 준비

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_2020_mfa_approval_review.ps1"
```

이 단계는 전수 LAB을 검증하고 2020 후보표만 만든다. MFA, WAV 이동, 자동 승인,
정본 승격을 하지 않는다. 연구자는 실제로 제외에 동의하는 행만 `approved`로
바꾼다. 후보가 0건이어도 입력 계약에 결속된 0행 승인을 남긴다.

### C. 2020 신규 MFA 시작

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\start_2020_mfa_after_review.ps1" -ApprovedBy "ari30"
```

wrapper는 2020 검색표 완료, 같은 `_build_meta` SHA, 승인 계약, 공통사전,
저장공간, repository test를 확인한다. 정확히 GO일 때만 2020 한 연도를 시작한다.

완료 상태 `machine_qc_passed_human_review_pending`은 기계 QC가 통과했지만 아직
정본 승격이나 다음 연도 허가가 아니라는 뜻이다.

### D. 2020 생산 표본 연구자 확인

기계 QC 완료 뒤 검토표를 만든다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_2020_production_sample_review.ps1"
```

기계가 선택한 최소 5세션 표본에서 다음만 확인한다.

- WAV·LAB·TextGrid·CSV가 같은 `utt_id`인가
- 6개 tier 이름·내용·0–xmax 경계가 계약과 맞는가
- 검색용 Roman·형태소 정보가 읽히고 원자료와 연결되는가
- 재수출/제외가 필요한 명백한 인프라 오류가 있는가

여기서는 ㄴ 삽입 등 실제 실현 여부를 판정하지 않는다. 같은 전역 이슈를 행마다
반복해서 쓰지 않고 issue code 한 번과 적용 범위를 기록한다.

모든 행을 확인해 `decision=approved`로 저장한 뒤 승인 보고서를 만든다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\approve_2020_production_sample_review.ps1" -ApprovedBy "ari30"
```

### E. Gate B와 2021–2025

2020 연구자 보고서가 승인되면 Gate B를 통과시킨 뒤 2021–2025 제외 후보표를
준비한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\prepare_remaining_mfa_approval_reviews.ps1"
```

남은 연도의 제외 후보를 확인해 승인한 뒤 다음 wrapper를 사용한다.

```powershell
& "C:\Users\ari30\research\2026_summer_research\scripts\start_remaining_mfa_after_2020_gate.ps1" -ApprovedBy "ari30"
```

Gate B는 2020 audit, align/merge marker, retained DB, DB 표본 동등성, 연구자
확인, input/alignment/source contract, 모델·방법 계약을 대조한다. 실패하면
2021을 시작하지 않고 보고서만 남긴다.

2021–2025에서는 연도별 실패 상태·partial·DB를 보존하고 다음 조치를 분리한다.
full-clean 재실행이나 정본 승격은 자동으로 하지 않는다.

## 4. 정지·재개 원칙

- 콘솔 창이 닫혔으면 먼저 상태판과 lock/process를 읽고 같은 wrapper를 재실행한다.
- 성공 shard, LAB contract, MFA DB, export partial은 검증 후 재사용한다.
- 일부 누락 때문에 연도 전체를 처음부터 자동 재계산하지 않는다.
- 실패 파일은 승인 제외 또는 국소 재처리 목록으로 분리한다.
- D: 공간 정리는 QC·보존 목록·dry-run·사용자 승인 뒤에만 한다.

## 5. 방법론 보고 범위

논문에는 2020–2025가 같은 acoustic model, 공통 Jamo G2P, phone inventory,
입력 정규화, 6-tier exporter, QC 계약으로 처리되었다고 보고할 수 있다.
MFA phone을 실제 발음 또는 실현 판정이라고 쓰지 않는다. `phoneme_r_auto`도
MFA phone을 기계적으로 넓게 Roman화한 보조층이며 기저형 분석이 아니다.

## 6. 동결 형식 변경 절차

6-tier 이름, Roman 구분자·대소문자, 7표/4표 schema, phone 기준을 바꾸려면
생산을 멈추고 새 결정문·회귀시험·migration 영향을 기록한다. 그 외 단순 오류
복구는 새 파일럿이나 외부 설계 리뷰 없이 checkpoint에서 수정·재개한다.
