# 결정: post-MFA exact-ID 후보는 명시 승인 뒤 보존 DB에서 export만 재개

날짜: 2026-08-04
상태: 현행 생산 계약
적용: 2021–2025 공통 Jamo r2 전수 MFA

## 문제와 연구 목적

MFA가 정상적으로 계산을 마쳐도 극단적으로 짧은 음원처럼 acoustic feature를
만들지 못한 발화나, beam·retry beam 뒤에도 word/phone interval이 없는 발화가
소수 남을 수 있다. 이들은 pre-MFA 입력 문제와 다르며 실제 MFA DB를 보아야만
확정할 수 있다. 조용히 누락하면 연도별 모수가 달라지고, 소수 누락 때문에 전
연도 정렬을 다시 돌리면 시간·재현성·오류 위험이 커진다.

따라서 연구 인프라의 목표는 다음 두 조건을 동시에 만족하는 것이다.

1. active LAB와 정렬 결과의 exact-ID 등식에서 빠진 발화를 자동으로 숨기지 않는다.
2. 이미 끝난 동일 입력·모델·phone 계약의 MFA 계산은 보존하고, 승인 뒤 6-tier
   export와 독립 감사만 재개한다.

## 확정 절차

1. direct exporter가 `unknown_active_lab_without_alignment`를 한 건이라도 찾으면
   `blocked_exact_id_reconciliation`으로 멈춘다. SQLite DB와 partial은 보존한다.
2. 후보 준비기는 실패 보고서의 ID, 보존 DB의 상태, pre-MFA 승인 계약을 전수
   대조한다.
3. DB에서 `ignored=1`이고 usable frame이 없는 후보는
   `mfa_feature_generation_failed`, `ignored=0`이지만 word/phone interval이 없는
   후보는 `mfa_alignment_missing`으로 구분한다.
   연구자 표본도 두 사유를 각각 포함하도록 층화한다.
4. `02_RESEARCHER_DECISIONS.csv`는 생성 당시 pending inventory로 보존한다.
   연구자는 별도 `04_RESEARCHER_APPROVAL.csv`만 검토·편집한다.
5. 자동 승인은 금지한다. 모든 행의 `decision=approved`, 후보 identity SHA,
   실패 보고서 ID 집합, 보존 DB 분류, 입력 계약, 명시 승인 token이 모두 맞아야
   pre-MFA·post-MFA 결합 제외 계약을 만들 수 있다.
6. 결합 계약은 새 execution queue에 둔다. 기존 승인 계약과 2020 완성본은
   덮어쓰지 않는다.
7. 같은 `direct_db_ready`의 input/alignment contract와 DB count가 다시 맞을 때만
   MFA 계산을 건너뛰고 6-tier·동반표 export를 재개한다.
8. export 뒤 독립 전수 감사, DB 표본 재수출, 연구자 표본 확인을 모두 통과해야
   다음 연도로 간다.

## 2021에서 확인된 적용 사유

2021 feature 생성 단계에서 MFA 경고 43,822건은 검색표 밖 WAV-only 42,296건,
승인된 pre-MFA 제외 1,502건, 초단시간 feature 실패 후보 24건으로 완전히
분해됐다. 24건은 현재 자동 승인하지 않았고, MFA 완료 뒤 exporter가 산출하는
exact-ID 집합과 동일한지 다시 확인한다. 실제 후보 수와 사유는 그 시점의
보존 DB·실패 보고서가 정본이다.

## 재현 가능한 진입점

- 후보 준비: `scripts/prepare_post_mfa_exact_reconciliation_review.ps1`
- 명시 승인·DB 재개: `scripts/resume_year_export_after_post_mfa_review.ps1`
- 후보 분류: `scripts/python/prepare_post_mfa_alignment_review.py`
- 결합 계약: `scripts/python/finalize_post_mfa_exact_reconciliation_exclusions.py`

이 절차는 정렬 생략이나 연구대상 축소를 위한 것이 아니다. 2020–2025의 안전
본체는 모두 동일 기준으로 새로 정렬하고, MFA 계산 뒤 기술적으로 정렬 불가능한
발화만 정확한 근거와 승인 계보를 남겨 분석 본체에서 분리한다.
