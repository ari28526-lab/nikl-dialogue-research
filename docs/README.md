# docs — 문서 색인

이 리포의 모든 문서 길잡이. **처음이면 위에서부터** 읽으면 된다.

## 먼저 읽기
| 문서 | 무엇 |
|---|---|
| [environment/PROJECT_CURRENT_STATE.md](environment/PROJECT_CURRENT_STATE.md) | **현재 상태 정본** — 확정 결정, 완료 상태, 바로 다음 명령, 세션 복구 절차 |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | 연구 개요 1페이지 (무엇을·왜·자료·1기/2기) |
| [자료구축_코드해설.md](자료구축_코드해설.md) | **A단계 코드 이해** — 어떤 자료로·어떤 코드로·왜·무슨 역할 |
| [DATA_LAYOUT.md](DATA_LAYOUT.md) | **데이터 배치도** — D: 전 폴더 구조·규약(세션 하위폴더)·대용량 열람 요령 |
| [WORK_HISTORY_2026-07.md](WORK_HISTORY_2026-07.md) | 작업 이력 (시간순 · Claude 협업 기록) |
| [WORKLOG_infrastructure_audit_2026-07-24.md](WORKLOG_infrastructure_audit_2026-07-24.md) | CSV·MFA 인프라 감사의 확인·판단·실행·커밋 작업일지 |

## 진행 관리
| 문서 | 무엇 |
|---|---|
| [WORKFLOW.md](WORKFLOW.md) | 작업 흐름 (A/B단계 구조) |
| [TODO_A단계.md](TODO_A단계.md) | 남은 일·사용자 결정 대기 목록 |

## 결정·표준 (decisions/)
논문 인용 수준의 방법론·표준·계획 기록.
| 문서 | 무엇 |
|---|---|
| [decisions/METHODS_bareun_dialogue_reanalysis.md](decisions/METHODS_bareun_dialogue_reanalysis.md) | 형태소 재분석·의미부여·빈도 **방법론(정본)** |
| [decisions/STANDARD_textgrid_tiers.md](decisions/STANDARD_textgrid_tiers.md) | TextGrid tier 표준 v2 |
| [decisions/WORKFLOW_r2_MFA_research_data_contract_20260730.md](decisions/WORKFLOW_r2_MFA_research_data_contract_20260730.md) | **현재 r2 전수 MFA 연구 데이터 계약** — 입력·발음 의미·4-tier·QC·검색 CSV·후보/KOINA/판정의 전 과정 |
| [decisions/PLAN_KOINA_intonation_IP_AP.md](decisions/PLAN_KOINA_intonation_IP_AP.md) | 운율 주석(IP/AP) 계획 |
| [decisions/000_project_folder_structure.md](decisions/000_project_folder_structure.md) | 폴더 구조 결정 |
| [decisions/RUNBOOK_MFA_eojeol_realign.md](decisions/RUNBOOK_MFA_eojeol_realign.md) | 어절 전량 재정렬 런북 (실패 분석 이력 포함) |
| [decisions/RUNBOOK_pre_MFA_bulk_safe_2026-07-25.md](decisions/RUNBOOK_pre_MFA_bulk_safe_2026-07-25.md) | **현재 실행 정본** — pre-MFA CSV 동결·숫자/기호 lab·입력계약·stale temp 보존·무인 MFA 명령 |
| [decisions/RUNBOOK_MFA_stratified_year10_pilot_2026-07-24.md](decisions/RUNBOOK_MFA_stratified_year10_pilot_2026-07-24.md) | 연도별 10발화·실제 화자 5명 MFA 파일럿 실행·QC·시행착오 |
| [decisions/AUDIT_pre_bulk_MFA_CSV_2026-07-24.md](decisions/AUDIT_pre_bulk_MFA_CSV_2026-07-24.md) | 대량 실행 전 실패·시행착오 27건과 수용 기준 |
| [decisions/DESIGN_safe_pre_bulk_pipeline_2026-07-24.md](decisions/DESIGN_safe_pre_bulk_pipeline_2026-07-24.md) | 원자 출력·구판 보존·MFA/CSV 검증 설계와 연구적 근거 |
| [decisions/DESIGN_candidate_infrastructure_layers_2026-07-24.md](decisions/DESIGN_candidate_infrastructure_layers_2026-07-24.md) | 후보 검색→파일 수집→KOINA→수동 판정의 층 분리와 2020 파일럿 게이트 |
| [decisions/DESIGN_pronunciation_environment_search_2026-07-25.md](decisions/DESIGN_pronunciation_environment_search_2026-07-25.md) | 사전·규칙·MFA 발음 분리, 음운·형태 경계 검색표와 CSV–WAV–TextGrid 연동 설계 |
| [decisions/DESIGN_common_pronunciation_lexicon_2020_2025_20260727.md](decisions/DESIGN_common_pronunciation_lexicon_2020_2025_20260727.md) | **2020–2025 공통 발음 자원** — G2P 판본·우리말샘 예외·출처·MFA 파생사전·재실행 정책 |
| [decisions/PILOT_common_pronunciation_full_corpus_20260728.md](decisions/PILOT_common_pronunciation_full_corpus_20260728.md) | **공통 발음 파일럿 착수 실측** — 6개년 전체 510만행·88만 고유 어절, 사전 원천 감사, D: release·Git·phone 체계 gate |
| [../outputs/reports/RESULT_common_pron_AB_pilot_20260728.md](../outputs/reports/RESULT_common_pron_AB_pilot_20260728.md) | **공통 발음 A/B 파일럿 결과** — A/B 60/60, 4-tier·사전 확률열·효과군 20·phone 변화 3·control 잡음과 수동 검토 순서 |
| [decisions/DECISION_common_pronunciation_resource_v2_20260728.md](decisions/DECISION_common_pronunciation_resource_v2_20260728.md) | **공통 발음 자원 v2 정본** — 어절 type/occurrence 분리, 형태소 조건 사전 후보, 수동 A/B 결과, MFA 주 정렬·wav2vec2/KFaligner 보조 역할 |
| [decisions/METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md](decisions/METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md) | **6개년 phone 방법론 동일성 정본** — 같은 모델·사전·G2P·입력/tier 기준, 2020 TextGrid+부분 DB·2021 DB 전수 gate, 논문용 주장 범위 |
| [decisions/RUNBOOK_common_pron_mfa_r1_20260728.md](decisions/RUNBOOK_common_pron_mfa_r1_20260728.md) | **공통 G2P 장시간 실행 정본** — 한 줄 실행, 35 shard 진행 확인·재개, 2020 TextGrid/부분 DB·2021 DB 자동 전수 gate |
| [decisions/MONITOR_common_pron_mfa_r1_20260728.md](decisions/MONITOR_common_pron_mfa_r1_20260728.md) | 공통 G2P 35 shard와 2020 TextGrid·부분 DB/2021 DB 전수 동등성의 실시간 진행·오류·무손상 점검대장 |
| [decisions/AUDIT_2020_pre_mfa_full_pipeline_2026-07-26.md](decisions/AUDIT_2020_pre_mfa_full_pipeline_2026-07-26.md) | **2020 전 단계 완료 감사** — 510만행 CSV, 86만 TextGrid, 4-tier 경계, 16시간 export 병목과 2021 전 개선 gate |
| [decisions/AUDIT_remaining_MFA_years_and_direct_DB_export_2026-07-26.md](decisions/AUDIT_remaining_MFA_years_and_direct_DB_export_2026-07-26.md) | **2021–2025 실행 준비도와 병목 개선 감사** — 연도별 CSV/WAV/lab 위험, export 경쟁 원인, 21,962개 direct 동등성, 2021 GO 명령·복구 정책 |
| [decisions/MONITOR_pre_mfa_bulk_pre_mfa_v1_20260725.md](decisions/MONITOR_pre_mfa_bulk_pre_mfa_v1_20260725.md) | 29시간 실행의 CPU·I/O·디스크·마커·오류·시행착오 시간순 점검대장 |
| [decisions/MONITOR_2021_pre_mfa_v1_20260727.md](decisions/MONITOR_2021_pre_mfa_v1_20260727.md) | 현재 2021 direct-DB 실행의 lab·MFA 단계·CPU·용량·watchdog 실측 점검대장 |
| [decisions/MONITOR_common_pron_AB_pilot_20260728.md](decisions/MONITOR_common_pron_AB_pilot_20260728.md) | 공통 발음 A/B의 단계·오류·부분 성공·무손상·재개를 기록하는 실시간 점검대장 |
| [decisions/PLAN_2022_improved_MFA_after_2020_2021.md](decisions/PLAN_2022_improved_MFA_after_2020_2021.md) | 2020·2021 실측을 반영한 2022 개선 실행안과 GO/NO-GO |
| [decisions/AUDIT_2020_2021_MFA_comparison_and_2022_gate_20260728.md](decisions/AUDIT_2020_2021_MFA_comparison_and_2022_gate_20260728.md) | **2020·2021 최종 비교 정본** — 전수 QC·속도·DB 증거·D: dry-run·2022 기술 GO/방법론 HOLD와 승인 후 명령 |
| [decisions/NOTE_wav2vec2_phone_candidate_layer_20260727.md](decisions/NOTE_wav2vec2_phone_candidate_layer_20260727.md) | 한국어 wav2vec2 phone 모델을 MFA 대체가 아닌 음향 후보 탐지층으로 검증하는 방법·한계·소표본 gate |
| [decisions/PLAN_2021_post_QC_storage_cleanup_20260727.md](decisions/PLAN_2021_post_QC_storage_cleanup_20260727.md) | 2021 QC 뒤 DB·계약·최종 결과를 보존하고 재계산 가능한 대형 temp만 dry-run·승인 후 정리하는 용량 정책 |
| [decisions/ANALYSIS_runtime_pre_hardening_vs_current_20260727.md](decisions/ANALYSIS_runtime_pre_hardening_vs_current_20260727.md) | 2020이 아닌 수정 전 보존 코드·과거 로그를 기준으로 현재 처리시간과 추가 검증 비용을 분리한 분석 |
| [decisions/RUNBOOK_SSD_migration.md](decisions/RUNBOOK_SSD_migration.md) | **SSD 이전+세션 재구성 런북 (7/20 실행)** |

## 외부 리뷰 (reviews/)

| 문서 | 무엇 |
|---|---|
| [reviews/HANDOFF_external_review_CSV_MFA_20260727.md](reviews/HANDOFF_external_review_CSV_MFA_20260727.md) | 다른 도구에 GitHub 주소와 함께 전달할 전체 CSV·MFA 코드리뷰 범위·제약·피드백 양식 |
| [reviews/PROMPT_external_review_r2_MFA_research_workflow_20260730.md](reviews/PROMPT_external_review_r2_MFA_research_workflow_20260730.md) | r2 전수 MFA 시작 전 입력·출력·조인·실패복구·방법론 중심 외부 리뷰 프롬프트 |
| [reviews/incoming/EXTERNAL_REVIEW_CSV_MFA_ce421db_20260727.md](reviews/incoming/EXTERNAL_REVIEW_CSV_MFA_ce421db_20260727.md) | 커밋 `ce421db` 대상 외부 리뷰 수신 원문 336행(줄바꿈 정규화 SHA256 기록) |
| [reviews/TRIAGE_external_review_CSV_MFA_ce421db_20260727.md](reviews/TRIAGE_external_review_CSV_MFA_ce421db_20260727.md) | 외부 finding별 독립 재검증·수용/수정/보류 판정과 2021/2022 적용 순서 |

## 환경 설정 (environment/)
기계·도구 셋업 노트(바른·MFA·R·Praat·VS Code 등). 색인은
[environment/ENVIRONMENT_NOTES_INDEX.md](environment/ENVIRONMENT_NOTES_INDEX.md).

## 지난 문서 (archive/)
역할을 다한 과정 문서(초기 GitHub 준비·전문가 세션 전달문·구 START_HERE·
세션 핸드오프). 이력 보존용이며 현재 지침은 아님.

---
*코드 한 줄 색인은 [../scripts/SCRIPTS_INDEX.md](../scripts/SCRIPTS_INDEX.md).*
