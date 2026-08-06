# 연도별 표본의 명시 승인 기록·checkpoint Gate 동등성 결정 — 2026-08-06

상태: **채택·2021 적용 완료**

## 문제

연도별 MFA 기계 QC가 끝난 뒤 연구자는 번호가 붙은 WAV·LAB·6-tier TextGrid
표본을 확인한다. 기존 절차는 그 뒤 연구자가 `03_RESEARCHER_REVIEW.csv`의 각
`decision`을 직접 `approved`로 바꾸고 별도 승인 명령을 실행해야 했다.

이 방식은 다음 문제를 만들었다.

- 채팅에서 검토를 마쳤어도 CSV가 `pending`으로 남아 완료 상태와 기록이 달랐다.
- 스프레드시트 앱·원격 접속·파일 경로 문제 때문에 동일 검토를 반복할 위험이 컸다.
- 사람이 검토한 결과를 기계가 **기록**하는 것과 기계가 승인 여부를 **추론**하는
  것이 구분되지 않았다.
- checkpoint-resume로 완성된 2021 marker를 다음 연도 Gate가 구형 단일
  `export_mode`와 옛 temp status로만 검사해 정상 완료를 실패로 판정했다.

## 결정

### 1. 검토와 기록을 분리한다

연구자는 표본을 직접 확인하고 승인 범위·정확한 행 수·승인자를 명시한다. 코드는
그 결정을 추론하지 않고 다음 조건을 모두 확인한 뒤 기계적으로 기록한다.

1. 비어 있지 않은 `approved_by`와 `approval_statement`
2. 연구자가 말한 `expected_row_count`와 실제 행 수의 정확 일치
3. manifest의 행 identity·WAV/LAB/TextGrid 경로와 현재 CSV의 정확 일치
4. 기존 결정값이 `pending` 또는 `approved`뿐임
5. 원 pending CSV의 manifest SHA 일치

조건이 통과하면 원 pending CSV를
`03_RESEARCHER_REVIEW_PENDING_ORIGINAL.csv`에 바이트 그대로 보존하고,
승인 CSV·`03_RESEARCHER_DECISION.json`·`04_RESEARCHER_APPROVAL.json`을 원자적으로
생성한다. 같은 명령을 다시 실행해도 CSV·원본 archive SHA가 바뀌지 않아야 한다.

`automatic_approval_performed=false`와
`materialized_from_explicit_researcher_statement=true`를 함께 기록한다. 즉 사람이
한 결정을 코드가 옮겨 적는 것이며 자동 승인이나 실제 음운 실현 판정이 아니다.

### 2. 현대 checkpoint 완료 marker를 동등한 생산 모드로 인정한다

연구 6-tier Gate는 다음 두 mode를 동일 schema의 호환 실행 방식으로 인정한다.

- `direct_db_research_6tier_v1`
- `direct_db_research_6tier_v1_checkpoint_resume`

후자는 계산 기준이나 tier schema를 바꾼 모드가 아니라 성공한 checkpoint를
재검증해 승격한 실행 방식이다. align·merge marker의 mode가 서로 같고 위 집합에
속해야 한다.

옛 input contract의 status가 `alignment_computation_complete_export_pending`에
남아 있더라도, 별도 `YEAR.direct_db_ready` marker가 같은 input/alignment 계약·
보존 DB·G2P model을 가리키고 `computation_complete=true`이면 보존 DB 완료 근거로
인정한다. 원 marker를 사후 수정하지 않는다.

## 2021 적용 결과

- 연구자 `ari30`은 1–20번과 21–24번, 총 24개 표본의 WAV·LAB·TextGrid 연결,
  6-tier, 정렬, 검색 정보가 대체로 적절하다고 확인했다.
- 승인 CSV 24/24, 세션 24, 화자 24다.
- 원 pending CSV 24행을 바이트 동일 보존했다.
- 같은 승인 명령을 재실행한 뒤 승인 CSV와 pending archive SHA 변화는 0이었다.
- `automatic_approval_performed=false`, `allow_next_year_mfa=true`다.
- 처음 Gate의 다른 14개 검사는 통과했고, 구 mode/temp 판정 두 개만 실패했다.
  호환 계약을 적용한 뒤 `2021 → 2022` Gate는 실패 검사 0으로 통과했다.

## 구현·근거

- `scripts/python/mfa_production_year_review.py`
- `scripts/approve_production_year_sample_review.ps1`
- `scripts/python/preflight_next_year_after_research_qc.py`
- `scripts/preflight_production_next_year_gate.ps1`
- `outputs/reviews/mfa_production_2021_mfa_checkpoint_qc_2021_20260805_retry1/`
- `outputs/reports/GATE_2021_TO_2022.json`

회귀 검사는 원 pending 보존, 명시 승인, identity 불변, 잘못된 행 수 거부,
재실행 무변경, checkpoint-resume mode와 `direct_db_ready` 계약을 포함한다.
Windows PowerShell 5.1 안전성·런타임 호환성 검사도 통과했다.

## 방법론적 해석

논문에서는 “기계 QC를 통과한 연도별 층화 표본을 연구자가 직접 확인했고, 그
명시 판정을 불변 identity·원본 SHA와 결합한 승인 계약으로 기록했다”고 기술할
수 있다. 이 승인은 정렬 인프라의 연결성과 연구 사용 가능성에 관한 것이며,
개별 음운 현상의 실제 실현 여부 판정과는 분리된다.
