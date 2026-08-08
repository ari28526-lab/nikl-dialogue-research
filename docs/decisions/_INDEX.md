# 현행 결정 문서 색인

최종 갱신: 2026-08-08 KST

이 폴더에는 현재 생산·방법론에 실제로 적용되는 결정만 둔다. 종료된 감사,
파일럿, 구 RUNBOOK, MONITOR, 과거 계획 33개는 원문을 삭제하지 않고
`../archive/decisions_pre_production/`으로 이동했다. MFA·6-tier 생산 명령은
`../RUNBOOK_production_2020_2025.md`, 사전 발음 참조표·7번째 파생 tier는
`../RUNBOOK_pronunciation_reference_layer_2020_2025.md`만 따른다.

## 연구 흐름과 출력 계약

| 문서 | 역할 |
|---|---|
| `DESIGN_candidate_infrastructure_layers_2026-07-24.md` | 검색→수집→보조분석→연구자 판정의 층 분리 |
| `DESIGN_pronunciation_environment_search_2026-07-25.md` | 철자·규칙·사전·MFA 정보 분리 |
| `DECISION_pre_MFA_combination_search_v3_20260801.md` | 형태소·Roman·기호 조합검색 7표 |
| `PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md` | 6-tier TextGrid·post-MFA 동반표 4개 |
| `PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md` | 서울 코퍼스·KOINA·이어붙이기 설계 근거 |
| `DECISION_auto_phoneme_roman_aux_layer_20260731.md` | `phoneme_r_auto`의 보조적 범위 |
| `WORKFLOW_r2_MFA_research_data_contract_20260730.md` | 좌표계·provenance·연결 계약 |

## 공통 발음사전과 6개년 동일성

| 문서 | 역할 |
|---|---|
| `DECISION_common_pronunciation_resource_v2_20260728.md` | 공통 발음 자원 구조 |
| `DECISION_latest_jamo_common_pron_mfa_20260728.md` | acoustic v3.3.0·Jamo G2P v3.2.0·r2 선택 |
| `DECISION_common_pron_G2P_no_path_fallback_20260728.md` | G2P 누락 fail-closed와 승인 예외 |
| `METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md` | 연도간 phone 기준 동일성 근거 |
| `DECISION_dictionary_pronunciation_registry_and_reference_tier_20260805.md` | 우리말샘 1:N·예외 발음 registry, occurrence 조인표, 7번째 규칙 참조 tier와 공통발음열 감사 계약 |
| `DECISION_2022_pronunciation_input_gate_hold_20260807.md` | 2022 표본·881,237형 전수 감사로 r2 규칙 배선 공백을 확인하고 신규 실행을 차단한 결정; r3 단일 선택표와 6개년 재정렬 요구 |
| `DECISION_common_pron_r3_candidate_resolution_20260807.md` | r3 canonical·donor·G2P 후보를 최종 선택과 분리하고, 2020–2022 동등 단위 증명 재사용·변경 단위 재정렬·2023–2025 최초 정렬을 규정 |
| `METHODS_NOTE_common_pron_r3_revision_for_reporting_20260807.md` | r2 입력 배선 문제 발견, 881,237형 전수 감사, r3 후보·선택 분리, 재정렬 범위 수정과 논문 각주용 축약문을 기록 |
| `RESULT_common_pron_r3_g2p_candidate_phase_20260808.md` | Jamo G2P 310,605개 후보의 13 shard 완결성·no-path/`spn` 0·읽기 전용 감사 기록 |
| `RESULT_common_pron_r3_g2p_agreement_gate_20260808.md` | 후보–독립 규칙 Roman 전수 exact/mismatch, 사전 근거별 보류, 연도별 동일 기준 회계와 독립 감사 기록 |
| `RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md` | mismatch 214,321 target의 편집·model 표상·사전/형태소/연도 근거 전수 진단, 2,625패턴·56행 handoff와 독립 감사 기록 |
| `RESULT_common_pron_r3_model_projection_candidates_20260808.md` | 좁은 model 단위화 관계와 exact 문맥 donor로 target 후보 264,906개를 마련하고 잔여 45,699개를 보류한 전수 projection·독립 감사 기록 |
| `RESULT_common_pron_r3_selection_readiness_20260808.md` | 881,237형에 r2·donor·사전·projection을 연결한 candidate/복수변이/zero-fallback 전수 회계, 국소 복구와 전역 donor 확장 필요성 기록 |

## 현재 생산과 안전 계약

| 문서 | 역할 |
|---|---|
| `DECISION_workflow_reset_and_production_entrypoints_20260801.md` | 단일 RUNBOOK·2020 Gate B·구 검토 종료 |
| `DECISION_incremental_unattended_year_MFA_20260801.md` | 연도·shard checkpoint와 국소 재개 |
| `DECISION_2020_CSV_WAV_ID_recovery_20260801.md` | 2020 WAV ID 밀림 복구와 파생 코퍼스 |
| `DECISION_2020_MFA_exclusion_symbol_accounting_20260802.md` | 1,887 제외와 6,158 경고 보존 |
| `DECISION_2020_TextGrid_outer_edges_and_audio_unusable_20260803.md` | 2020 전수 tier 바깥 경계 감사·검토본 패딩·청취 불가 3건 |
| `DECISION_2020_production_complete_gate_b_20260803.md` | 2020 r2·6-tier·독립 QC·24표본 승인·Gate B 완료와 2021 안전 정지점 |
| `DECISION_2023_JSON_PCM_segment_id_mismatch_20260803.md` | 2023 배포 JSON 발화와 PCM/WAV 분절 ID 불일치의 원인·보수적 복구 기준 |
| `DECISION_year_safe_body_first_recovery_later_20260803.md` | 2021–2025 same-ID 안전 본체 우선 정렬·회수분 후속 shard·최종 제외 원칙 |
| `DECISION_sequential_year_gate_and_queue_isolation_20260803.md` | 2021–2025 연도별 독립 실행 queue·직전 연도 6-tier/DB/연구자 gate·상태 history 보존 |
| `DECISION_explicit_year_review_approval_and_gate_compatibility_20260806.md` | 표본 직접 검토 뒤 승인 문장·정확 행 수로 원 pending을 보존하며 계약화하고, checkpoint-resume·`direct_db_ready`를 동일 6-tier 생산 근거로 검증 |
| `DECISION_2021_feature_generation_ignored_pending_20260804.md` | 2021 feature 생성 실패 24건을 자동 누락하지 않고 MFA 완료 DB 보존·exact-ID 재확인·연구자 승인 뒤 export하는 절차 |
| `DECISION_post_MFA_exact_reconciliation_resume_20260804.md` | 2021–2025 post-MFA 기술적 미정렬을 DB·실패 보고서 exact-ID로 검증하고 명시 승인 뒤 전년 재정렬 없이 보존 DB에서 export·감사만 재개하는 공통 절차 |
| `DECISION_MFA_float32_terminal_boundary_normalization_20260805.md` | MFA DB float32 종단시각과 WAV 프레임 duration의 미세 표현 차이만 동적 허용치로 0/xmax 정규화하고 TextGrid·동반표·보고서에 동일 반영하는 생산 정책 |
| `DECISION_MFA_alignment_contract_semantic_checkpoint_identity_20260805.md` | 재실행 시각이 아닌 builder canonical identity로 정렬 계약 동일성을 재계산하고 같은 의미 계약 파일은 다시 쓰지 않는 checkpoint 정책 |
| `DECISION_MFA_direct_export_checkpoint_promotion_20260805.md` | 성공한 direct export의 계약·DB·exact-ID·동반표 SHA를 재검증해 연도 staging만 비재계산 승격하고 독립 QC로 넘기는 정책 |
| `DECISION_MFA_phone_only_silence_word_interval_20260805.md` | 전부 무음 phone만 연결된 word interval의 중복 어절 표지를 제거하되 시간·phone·텍스트·원본을 보존하는 정규화와 계층 repair 이력 정책 |
| `DECISION_compressed_external_archive_20260728.md` | E: 압축 archive 후 D: 정리 원칙 |

## 형태소·후속 연구

| 문서 | 역할 |
|---|---|
| `METHODS_bareun_dialogue_reanalysis.md` | 형태소 분석 방법 |
| `DECISION_bareun_engine_provenance_20260801.md` | Bareun 엔진·버전 provenance |
| `NOTE_wav2vec2_phone_candidate_layer_20260727.md` | wav2vec2를 MFA 비대체 보조층으로 사용 |
| `PLAN_KOINA_intonation_IP_AP.md` | 선별 자료 운율분석 계획 |
| `사회변수_코드북.md` | 화자·사회 변수 정의 |

## 구조

- 현재 저장소·D:/E: 구조: `../DATA_LAYOUT.md`, `../ASSETS_LEDGER.md`
- 구 Dropbox root 구조 결정: `../archive/pre_2021_cleanup_20260803/000_project_folder_structure.md`
- 역사 결정: `../archive/decisions_pre_production/`
- 외부 리뷰 원문·조치: `../reviews/`
- 상세 시행착오: `../WORK_HISTORY_2026-08.md`와
  `../archive/work_history/WORK_HISTORY_2026-07.md`

역사 문서의 “다음 단계”, 완료 표현, 실행 명령은 현재 지시가 아니다. 논문에서
방법을 설명할 때는 이 색인의 현행 문서와 실제 manifest를 함께 근거로 사용한다.

- `DECISION_MFA_2021_targeted_terminal_repair_checkpoint_resume_20260805.md` —
  2021 v5 끝검사에서 발견된 구 float32 종단 TextGrid 19개를 archive 후 표적
  교체하고, 전수 checkpoint 증거를 이어받아 동반표부터 재개하는 결정
- [MFA 체크포인트 감사 LAB 루트 계약 교정 (2026-08-05)](DECISION_MFA_checkpoint_audit_lab_root_contract_20260805.md)

## 대화 음원·분절 품질

| 문서 | 역할 |
|---|---|
| `DECISION_dialogue_audio_quality_gate_2020_2025_20260807.md` | 겹침·경계 잘림·소음·WAV 불량을 2020–2025 공통 근거 수준과 exclusion scope로 관리하며, 정렬 가능한 발화는 데이터 구축 목적으로 보존하는 품질 Gate |
