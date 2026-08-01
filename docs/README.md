# 연구 인프라 문서 색인

이 폴더의 활성 문서는 네 개다. 새 세션과 외부 도구는 이 순서로 읽는다.

| 순서 | 문서 | 역할 |
|---:|---|---|
| 1 | [environment/PROJECT_CURRENT_STATE.md](environment/PROJECT_CURRENT_STATE.md) | 현재 완료·미완료·안전 정지점 |
| 2 | [RUNBOOK_production_2020_2025.md](RUNBOOK_production_2020_2025.md) | 전수 생산의 유일한 실행 순서 |
| 3 | [ASSETS_LEDGER.md](ASSETS_LEDGER.md) | D:/외장 HDD/저장소 실물 위치 정본 |
| 4 | 이 문서 | 문서 역할과 역사 기록의 위치 |

## 고정 연구 계약

- [decisions/_INDEX.md](decisions/_INDEX.md): 현행·역사·대체된 결정 색인
- [decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md](decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md): 6-tier·CSV/동반표 계약
- [decisions/DECISION_pre_MFA_combination_search_v3_20260801.md](decisions/DECISION_pre_MFA_combination_search_v3_20260801.md): 형태소·Roman·기호 조합검색 계약
- [decisions/DECISION_incremental_unattended_year_MFA_20260801.md](decisions/DECISION_incremental_unattended_year_MFA_20260801.md): 연도별 checkpoint와 실패 보존
- [decisions/METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md](decisions/METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md): 6개년 phone 방법 동일성
- [decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md](decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md): 서울 코퍼스·KOINA를 고려한 tier 근거

## 코드·증거·검토

- 코드 색인: [../scripts/SCRIPTS_INDEX.md](../scripts/SCRIPTS_INDEX.md)
- 결과·기계 증거: `outputs/reports/`
- 외부 리뷰 원문: `reviews/incoming/`
- 리뷰 조치: `reviews/RESOLUTION_*.md`, `reviews/TRIAGE_*.md`
- 시간순 시행착오: `WORK_HISTORY_*.md`, `WORKLOG_*.md`
- 환경: `environment/ENVIRONMENT_NOTES_INDEX.md`

## 역사 문서 규칙

`WORKFLOW.md`, `TODO_A단계.md`, `HANDOFF_*.md`, 구 RUNBOOK·MONITOR·PILOT은
삭제하지 않지만 현재 실행 지침으로 사용하지 않는다. 현재 명령과 충돌하면
반드시 `RUNBOOK_production_2020_2025.md`가 우선한다.

workflow reset 이전의 누적 현재 상태는
[archive/PROJECT_CURRENT_STATE_20260801_full.md](archive/PROJECT_CURRENT_STATE_20260801_full.md)에
보존한다. 최종 점검 슬라이드와
`decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md`는 산출물
계약과 manifest의 근거이므로 이동하지 않는다.
