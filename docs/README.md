# 연구 인프라 문서 색인

새 세션과 외부 도구는 아래 문서를 이 순서로 읽는다.

| 순서 | 문서 | 역할 |
|---:|---|---|
| 1 | [environment/PROJECT_START_HERE.md](environment/PROJECT_START_HERE.md) | 연구 흐름·문서 사용 규칙 |
| 2 | [environment/PROJECT_CURRENT_STATE.md](environment/PROJECT_CURRENT_STATE.md) | 현재 완료·미완료·안전 정지점 |
| 3 | [../RELEASE.md](../RELEASE.md) | A단계 배포 범위·D: 인계·코드 재현판 진입점 |
| 4 | [../outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html](../outputs/reports/stage1_distribution_guide_for_nontechnical_readers_20260819.html) | 프로그램을 모르는 독자를 위한 단일 HTML 안내서 |
| 5 | [releases/20260818_six_year_infrastructure_closeout/README.md](releases/20260818_six_year_infrastructure_closeout/README.md) | 6개년 인프라 closeout·수량·한계·외부 설명 진입점 |
| 6 | [RUNBOOK_production_2020_2025.md](RUNBOOK_production_2020_2025.md) | 전수 생산의 유일한 실행 순서 |
| 7 | [ASSETS_LEDGER.md](ASSETS_LEDGER.md) | D:/E:/저장소 실물 위치 정본 |
| 8 | [environment/CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md](environment/CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md) | 리밋·새 대화 뒤 로컬 checkpoint 재개 |
| 9 | 이 문서 | 정본과 역사 기록의 경계 |

## 2단계 현재 진입점

- [decisions/PLAN_stage2_seven_phenomena_PV_pilot_20260819.md](decisions/PLAN_stage2_seven_phenomena_PV_pilot_20260819.md): 일곱 현상 PV-A 설계와 구현 범위, 완료 뒤 후속 결정 표지
- [decisions/RESULT_pv_preview_build_20260819.md](decisions/RESULT_pv_preview_build_20260819.md): 6개년 각 30개·합계 180개 PV-A 생성과 독립 감사
- [decisions/RESULT_stage2_pv_reviewer_v2_1_usability_fix_20260822.md](decisions/RESULT_stage2_pv_reviewer_v2_1_usability_fix_20260822.md): 균형 14개 reviewer v2.1의 독립 감사·사용자 최소 화면 Gate
- [decisions/HANDOFF_claude_cowork_four_hour_literature_synthesis_20260824.md](decisions/HANDOFF_claude_cowork_four_hour_literature_synthesis_20260824.md): 4시간 연구자 중심 문헌 종합의 Claude Cowork 인계 계약
- [decisions/RESULT_stage2_systematic_research_reviewer_v3_20260824.md](decisions/RESULT_stage2_systematic_research_reviewer_v3_20260824.md): 7현상 요인 지도·연구자 메모·Praat 연동·표본 감사 구현 결과

현재는 연도별 30개 후속 batch를 구현하지 않는다. 일곱 현상별 직접 문헌과
형태론 환경 분류를 먼저 정리하며, 진행 중인 Cowork 산출물은 승인 전까지
Git 밖 `work/`에 둔다.

## 고정 연구 계약

- [decisions/_INDEX.md](decisions/_INDEX.md): 현행·역사·대체된 결정 색인
- [decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md](decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md): 6-tier·CSV/동반표 계약
- [decisions/DECISION_pre_MFA_combination_search_v3_20260801.md](decisions/DECISION_pre_MFA_combination_search_v3_20260801.md): 형태소·Roman·기호 조합검색 계약
- [decisions/DECISION_incremental_unattended_year_MFA_20260801.md](decisions/DECISION_incremental_unattended_year_MFA_20260801.md): 연도별 checkpoint와 실패 보존
- [decisions/METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md](decisions/METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md): 6개년 phone 방법 동일성
- [decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md](decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md): 서울 코퍼스·KOINA를 고려한 tier 근거
- [RUNBOOK_pronunciation_reference_layer_2020_2025.md](RUNBOOK_pronunciation_reference_layer_2020_2025.md): 우리말샘 occurrence·규칙/MFA 비교표·7번째 파생 tier의 연도 공통 실행 절차
- [DATA_DICTIONARY_pronunciation_reference_layer.md](DATA_DICTIONARY_pronunciation_reference_layer.md): 발음 참조 레이어 열·좌표·상태값 정의

## 코드·증거·검토

- 코드 색인: [../scripts/SCRIPTS_INDEX.md](../scripts/SCRIPTS_INDEX.md)
- 결과·기계 증거: `outputs/reports/`
- 외부 리뷰 원문: `reviews/incoming/`
- 리뷰 조치: `reviews/RESOLUTION_*.md`, `reviews/TRIAGE_*.md`
- 8월 시행착오: `WORK_HISTORY_2026-08.md`
- 7월 시행착오: `archive/work_history/WORK_HISTORY_2026-07.md`
- 환경: `environment/ENVIRONMENT_NOTES_INDEX.md`
- 2020 완료·Gate B 결정:
  `decisions/DECISION_2020_production_complete_gate_b_20260803.md`
- 2021 진입 전 archive manifest:
  `archive/ARCHIVE_MANIFEST_pre_2021_20260803.md`

## 역사 문서 규칙

구 `WORKFLOW/TODO/HANDOFF/GUIDE/PROJECT_SUMMARY`는
`archive/pre_production_legacy/`에, 종료된 결정·RUNBOOK·MONITOR·PILOT은
`archive/decisions_pre_production/`에 원문 보존했다. 현재 실행 지침으로
사용하지 않는다.

workflow reset 이전의 누적 현재 상태는
[archive/PROJECT_CURRENT_STATE_20260801_full.md](archive/PROJECT_CURRENT_STATE_20260801_full.md)에
보존한다. 최종 점검 슬라이드와
`decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md`는 산출물
계약과 manifest의 근거이므로 이동하지 않는다.
