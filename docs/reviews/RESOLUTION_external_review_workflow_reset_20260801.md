# workflow reset 외부 리뷰 조치 기록

- 원문: `incoming/EXTERNAL_REVIEW_workflow_reset_20260801.md`
- 동반 원자료: `incoming/WORKFLOW_DECISION_TRACE_20260801.csv`,
  `incoming/WORKFLOW_VALIDATION_VALUE_20260801.csv`,
  `incoming/WORKFLOW_ARCHIVE_CANDIDATES_20260801.csv`
- 조치일: 2026-08-01 KST
- 최종 판정: **GO AFTER SMALL WORKFLOW FIXES**

외부 리뷰 원문과 CSV는 수정하지 않고 보존한다. 이 문서는 원문을 실제 코드·
실물 상태와 다시 대조한 뒤 어떤 제안을 수용·수정·보류했는지 기록한다.

## 수용

- 구 4-tier 60행 잔여 검토(V01), 12발화 utterance_search 검토(V02),
  5-tier phoneme 검토(V03), difference inventory 반복(V13)을 종료한다.
- mini pilot 육안 검토(V05)는 2020 첫 생산 표본 검토에 흡수한다.
- 현재 상태 문서를 append-only 일지가 아닌 교체형 정본으로 바꾼다.
- 활성 문서는 README, CURRENT_STATE, production RUNBOOK, ASSETS_LEDGER로
  축소하고 나머지는 결정·증거·역사로 색인한다.
- 2020을 먼저 완결하고 표본 연구자 확인 후 다음 연도를 연다.
- 7표+4표 joined 검색층과 우리말샘 1:N은 정렬을 막지 않는 후속 단계로 둔다.

## 사실관계 수정

| 원문 주장 | 재확인 | 조치 |
|---|---|---|
| 7/24 이후 5주간 | 2026-07-24~08-01은 약 8일 | 기간 표현 수정 |
| Python 287개 통과 | morph_search.v3 반영 뒤 292개, 본 조치 뒤 293개 | 상태 정본 수정, 전수 시험 통과 |
| 코드 수정 없이 GO | 기본 진입점이 6개년이며 2020 이후에도 큐가 계속됨 | 2020-only 진입점 추가 |
| Gate B 구현·배선 완료 | validator는 있으나 생산 큐에서 호출되지 않음 | 실제 다음 연도 진입점에 배선 |
| 같은 `_build_meta`를 양쪽이 검증 | 각자 success만 확인하며 동일 SHA 계약은 없음 | source contract를 명시·대조 |
| 사람 행동은 제외 승인 1회 | 2020 생산 표본 연구자 확인도 필요 | 승인 종류를 분리해 RUNBOOK에 명시 |

## 보류 또는 수정 수용

- 2021–2025 사람 표본 검토는 계산 차단 gate로 두지 않되, 연도별 기계 QC와
  이상 징후 표본은 남긴다. 정본 승격은 별도 결정이다.
- 2일 1회 승인 창구는 운영 원칙으로 채택하되, 승인되지 않은 제외 후보를
  자동 승인하거나 건너뛰지 않는다.
- 문서 이동은 링크와 산출물 manifest를 깨지 않는 범위에서만 한다.
  `PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md`와 최종 점검
  슬라이드는 이동하지 않는다.

## 전수 시작 전 완료 조건

1. 2020-only 준비·시작 스크립트가 기본 6개년 진입을 차단한다.
2. morph_search와 MFA가 같은 동결 `_build_meta` SHA를 사용했음을 기록한다.
3. 2020 완료 후 생산 표본 연구자 보고서와 machine contract를 결합한 Gate B가
   통과해야 2021–2025 진입점이 실행된다.
4. 전체 Python·PowerShell 안전검사와 preflight가 통과한다.

이 네 조건 뒤에는 추가 설계 파일럿을 만들지 않고 2020 생산으로 진입한다.
