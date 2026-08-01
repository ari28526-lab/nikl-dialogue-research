# 결정 문서 상태 색인

최종 갱신: 2026-08-01 KST

이 색인은 50여 개 결정 문서를 삭제하지 않으면서 현재 계약과 역사 기록을
구분한다. 현재 실행 명령은 `../RUNBOOK_production_2020_2025.md`가 우선한다.

## 현행 정본

| 문서 | 현재 역할 |
|---|---|
| `METHODS_bareun_dialogue_reanalysis.md` | 형태소 분석 출처·방법 |
| `DECISION_bareun_engine_provenance_20260801.md` | Bareun 엔진·provenance 동결 |
| `DECISION_pre_MFA_combination_search_v3_20260801.md` | 7개 검색표와 구분자·기호 후보 계약 |
| `PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md` | 6-tier·4 동반표 생산 계약 |
| `PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md` | tier·KOINA·이어붙이기 설계 근거 |
| `DECISION_auto_phoneme_roman_aux_layer_20260731.md` | `phoneme_r_auto`의 보조적 범위 |
| `DECISION_common_pronunciation_resource_v2_20260728.md` | 공통 발음 자원 구조 |
| `DECISION_latest_jamo_common_pron_mfa_20260728.md` | 최신 Jamo r2 선택 |
| `DECISION_common_pron_G2P_no_path_fallback_20260728.md` | G2P 누락 fail-closed·승인 예외 |
| `DECISION_r2_realign_all_six_years_20260729.md` | 6개년 전부 신규 정렬 |
| `METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md` | phone 기준의 연도간 동일성 |
| `DECISION_incremental_unattended_year_MFA_20260801.md` | 연도별 checkpoint·실패 보존 |
| `DECISION_workflow_reset_and_production_entrypoints_20260801.md` | 활성 문서·2020-only·source contract·Gate B |
| `DESIGN_candidate_infrastructure_layers_2026-07-24.md` | 검색→수집→보조분석→수동판정 층 분리 |
| `DESIGN_pronunciation_environment_search_2026-07-25.md` | 철자·규칙·사전·MFA 정보 분리 |
| `PLAN_KOINA_intonation_IP_AP.md` | 선별 운율 분석 계획 |

## 현행을 뒷받침하는 감사·설계 이력

- `AUDIT_pre_bulk_MFA_CSV_2026-07-24.md`
- `DESIGN_safe_pre_bulk_pipeline_2026-07-24.md`
- `WORKFLOW_r2_MFA_research_data_contract_20260730.md`
- `DECISION_mfa_r2_infrastructure_acceptance_pilot_20260730.md`
- `PLAN_integrated_CSV_MFA_research_infrastructure_20260731.md`
- `PROPOSAL_prebulk_execution_order_20260801.md`
- `NOTE_wav2vec2_phone_candidate_layer_20260727.md`
- `DECISION_compressed_external_archive_20260728.md`

이 문서들은 근거와 시행착오를 보존하지만 최신 명령을 제공하지 않는다.

## 대체되었거나 종료된 실행 문서

다음 문서의 실측·오류 기록은 유효하지만 명령과 “다음 단계”는 대체되었다.

- `RUNBOOK_common_pron_mfa_r1_20260728.md`: r1 실패 역사. r2로 대체.
- `RUNBOOK_common_pron_AB_pilot_20260728.md`: A/B 파일럿 종료.
- `RUNBOOK_MFA_stratified_year10_pilot_2026-07-24.md`: 6-tier 생산 전 파일럿 종료.
- `RUNBOOK_pre_MFA_bulk_safe_2026-07-25.md`: 구 4-tier/연도 실행 경로.
- `RUNBOOK_MFA_realign_2020-2025.md`, `RUNBOOK_MFA_eojeol_realign.md`:
  과거 재정렬·복구 근거만 보존.
- `MONITOR_*.md`, `PILOT_*.md`, `PLAN_2021_*`, `PLAN_2022_*`:
  해당 실행 시점의 기록이며 현재 작업 지시가 아님.
- `DECISION_mfa_r2_review_global_issues_20260730.md`와
  `GUIDE_mfa_r2_infrastructure_review_columns_20260730.md`:
  검토에서 발견한 요구사항은 현 6-tier/sidecar에 흡수됨.

## 이동 금지

`PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md`는 생성 manifest가
경로를 기록하므로 이동하지 않는다. 최종 점검 슬라이드도 계약 증거로 보존한다.
