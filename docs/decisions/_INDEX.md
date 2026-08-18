# 현행 결정 문서 색인

- [RESULT_db_v1_recovery_D10_researcher_return_20260818.md](RESULT_db_v1_recovery_D10_researcher_return_20260818.md) — 연구자 반환 16/16 raw 보존·정규화 완료: 1–4번 tier 위치만 교정, 수정 전사 5·분절 차이 1 보존, 독립 감사 통과·DB 채택 전 정지
- [PLAN_db_v1_recovery_D10_researcher_return_normalization_20260818.md](PLAN_db_v1_recovery_D10_researcher_return_normalization_20260818.md) — Dropbox 연구자 반환 16개의 raw 보존, 1–4번 작업 tier 위치만 기계 정규화, 수정 전사 5건·분절 차이 1건 보존과 비채택 Gate
- [PLAN_db_v1_recovery_D10_manual_overlay_20260818.md](PLAN_db_v1_recovery_D10_manual_overlay_20260818.md) — D9 부분 보존 16건을 국소 수정 9·전체 재정렬 6·단일어 1로 나눈 수정 전사·수동 TextGrid overlay 계획; 원본·본체 무수정 Gate
- [RESULT_db_v1_recovery_D9_researcher_review_20260818.md](RESULT_db_v1_recovery_D9_researcher_review_20260818.md) — D9 새 정렬 19건 연구자 청취·경계 검토 완료: 직접 승인 1, 수동 overlay 16, 기술 제외 2; TextGrid 생성과 연구 사용 승인을 분리하고 D10 수동 복구로 전환
- [RESULT_db_v1_recovery_D9_completed_20260817.md](RESULT_db_v1_recovery_D9_completed_20260817.md) — 동일 모델·사전·LAB과 beam 100/retry 400 한 차례 격리 실행으로 19/19 회수, flat 검토 묶음·독립 감사 완료; 본체·6-tier·DB v1 채택은 별도 Gate
- [RESULT_db_v1_recovery_D9_gate_20260817.md](RESULT_db_v1_recovery_D9_gate_20260817.md) — D8 identity 확인 잔여 19건만 beam 100/retry 400으로 한 차례 격리 재시도하는 해시 결속 계약·재개 runner·무병합 감사와 승인 전 Gate

- [RESULT_db_v1_recovery_D8_feasibility_20260817.md](RESULT_db_v1_recovery_D8_feasibility_20260817.md) — 미정렬 19건은 원 JSON·CSV·LAB·canonical/r3/H WAV identity를 확인해 한 차례 D9 후보로 고정하고, 0.1초 미만 25건은 H 백업 음원까지 같은 짧은 원자료 조각임을 확인; 읽기 전용 감사·Gate 통과
- [RESULT_db_v1_recovery_D7_partial_alignment_preservation_20260817.md](RESULT_db_v1_recovery_D7_partial_alignment_preservation_20260817.md) — 검토 11건을 본체에서는 제외하되 D5 진단 자료를 보존하고, 6건을 부분 정렬 검색 가능 상태로 별도 JSON·SQLite에 기록; 무병합·무삭제 감사 통과
- [PLAN_after_D7_recovery_to_DB_v1_RC1_20260817.md](PLAN_after_D7_recovery_to_DB_v1_RC1_20260817.md) — 19+25건 읽기 전용 회수 감사와 한 차례 exact-ID 통제 재정렬 뒤 recovery를 종료하고 DB v1 RC1·표적 추출·manual overlay·HTML/세션 JSON으로 이동하는 순서
- [RESULT_db_v1_recovery_D6_gate_20260815.md](RESULT_db_v1_recovery_D6_gate_20260815.md) — D5 성공 11건 flat 검토 묶음, 계속 미정렬 19건 DB 근거 장부, 0.1초 미만 25건 원음원 회수 경로와 독립 감사; 본체·6-tier·DB v1 자동 병합 0, 연구자 Gate 정지
- [RESULT_db_v1_recovery_D5_gate_20260815.md](RESULT_db_v1_recovery_D5_gate_20260815.md) — D4 55건 전수 재감사 후 25건은 0.1초 미만 원음원 길이 회수로 보존하고, 연도별 5건씩 30건만 D5 MFA 후보로 고정; `passed_gate_closed`, D: 생성·MFA·자동 병합 0
- [RESULT_db_v1_recovery_D0_D4_20260815.md](RESULT_db_v1_recovery_D0_D4_20260815.md) — 817,310건 이유별 exact-ID 장부, 기술 98,946건 회수 가능성 감사, 발음 85,433유형 축약, 55건 첫 진단 shard와 `passed_gate_closed`; r3 본체 변경·파일 생성·MFA 0
- [RESULT_mfa_r3_post_qc_storage_cleanup_2024_2025_20260815.md](RESULT_mfa_r3_post_qc_storage_cleanup_2024_2025_20260815.md) — D: 정본 유지 전제의 exact temp 126개·35.987 GiB 정리, DB SHA·6-tier·원자료 보존 사후 감사와 D단계 용량 Gate 완료
- [RESULT_db_v1_release_prep_A_C_20260815.md](RESULT_db_v1_release_prep_A_C_20260815.md) — 6개년 같은 방법론 교차 감사, 읽기 전용 저장계획, 5,103,356발화 exact-ID 통합 장부와 독립 QA 완료; D recovery 직전 정지
- [RESULT_mfa_r3_alignment_database_2025_20260815.md](RESULT_mfa_r3_alignment_database_2025_20260815.md) — 2025 r3 신규 정렬·802건 명시 승인·457,611개 6-tier·동반표·독립 QC 완료와 2020–2025 본체 동결

최종 갱신: 2026-08-15 KST

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
| `DECISION_r3_pronunciation_research_database_contract_20260809.md` | r3 선택 발음 type catalog–발화 scope–참조 어절 occurrence–post-MFA interval을 정규화 키와 SHA Gate로 연결 |
| `RESULT_mfa_r3_research_database_2020_20260809.md` | 2020 870,437발화·3,056,807 occurrence 전수 구축, 23-shard 재개, 독립 감사와 runner preflight 19/19 GO 결과 |
| `RESULT_mfa_r3_alignment_database_2020_20260809.md` | 2020 r3 782,715발화 신규 정렬, 보존 DB SHA·SQLite·interval 독립 감사, 782,432 성공·283 exact-ID 후속 회계와 2021 정지점 |
| `RESULT_mfa_r3_2021_preflight_20260810.md` | 2020 최종 QC SHA 동결, 2021 exact-ID 1,207,299·발음 연구 DB 6,648,515 occurrence·alignment 독립 감사·PowerShell 5.1·실제 GO preflight와 장시간 실행 직전 정지점 |
| `RESULT_mfa_r3_alignment_database_2021_20260811.md` | 2021 r3 1,207,299발화 신규 정렬, DB SHA 동결, 1,206,862 성공·437 post-MFA exact-ID 회계와 연구자 승인 정지점 |
| `RESULT_mfa_r3_alignment_database_2022_20260812.md` | 2022 r3 751,721발화 신규 정렬, 751,383 성공·338 명시 승인, 6-tier·동반표 4종·독립 전수 QC·DB 재수출 24/24 완료와 2023 안전 정지점 |
| `RESULT_mfa_r3_2023_preflight_20260812.md` | 2022 완료 SHA를 보존한 2022→2023 Gate, 2023 조합검색 20/20·발음 연구 DB·exact-ID 494,580 입력과 장시간 runner preflight GO |
| `RESULT_mfa_r3_alignment_database_2023_20260813.md` | 2023 r3 494,580발화 신규 정렬, 494,228 성공·352 명시 승인, 6-tier·동반표 4종·독립 전수 QC·DB 재수출 24/24 완료와 2024 전환 정지점 |
| `RESULT_mfa_r3_alignment_database_2024_20260814.md` | 2024 r3 594,404발화 신규 정렬, 593,530 성공·874 명시 승인, 표적 수출 복구와 6-tier·동반표 4종·독립 전수 QC 완료 |
| `RESULT_mfa_r3_alignment_database_2025_20260815.md` | 2025 r3 458,413발화 신규 정렬, 457,611 성공·802 명시 승인, 6-tier·동반표 4종·독립 전수 QC 완료와 2020–2025 안전 본체 동결 |
| `RESULT_morph_search_2025_source_contract_20260814.md` | 2025 조합검색 30/30 shard·연간 7표·frozen source contract와 독립 검사 12/12·표 SHA 7/7 완료, 2025 연구 DB 전 정지점 |
| `INCIDENT_mfa_r3_2024_textgrid_embedded_line_separator_20260814.md` | 원문 내장 줄바꿈 두 건의 TextGrid 표시 label 안전 중단, 원 CSV·DB·기존 출력 보존과 exact-ID 표적 복구 정책 |
| `INCIDENT_morph_search_2024_embedded_newline_20260813.md` | 2024 조합검색 shard 1의 인용 필드 내부 줄바꿈 안전 중단, 논리 CSV 레코드 처리 수정, 실패 증거 격리와 1-shard 실제 회귀 통과 |
| `INCIDENT_bareun_literal_plus_delimiter_collision_20260813.md` | 2024 shard 32의 Bareun literal `+`/형태소 구분자 충돌, 원 JSON 대조, 6개년 전수 감사, 2025 선제 탐지와 무손실 회귀 |

## 공통 발음사전과 6개년 동일성

| 문서 | 역할 |
|---|---|
| `DECISION_common_pronunciation_resource_v2_20260728.md` | 공통 발음 자원 구조 |
| `DECISION_latest_jamo_common_pron_mfa_20260728.md` | acoustic v3.3.0·Jamo G2P v3.2.0·r2 선택 |
| `DECISION_common_pron_G2P_no_path_fallback_20260728.md` | G2P 누락 fail-closed와 승인 예외 |
| `METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md` | 연도간 phone 기준 동일성 근거 |
| `DECISION_dictionary_pronunciation_registry_and_reference_tier_20260805.md` | 우리말샘 1:N·예외 발음 registry, occurrence 조인표, 7번째 규칙 참조 tier와 공통발음열 감사 계약 |
| `DECISION_2022_pronunciation_input_gate_hold_20260807.md` | 2022 표본·881,237형 전수 감사로 r2 규칙 배선 공백을 확인하고 신규 실행을 차단한 결정; r3 단일 선택표와 6개년 재정렬 요구 |
| `DECISION_common_pron_r3_candidate_resolution_20260807.md` | r3 canonical·donor·G2P 후보를 최종 선택과 분리한 결정; 정렬 재사용 범위는 2026-08-09 후속 결정으로 대체됨 |
| `METHODS_NOTE_common_pron_r3_revision_for_reporting_20260807.md` | r2 입력 배선 문제 발견, 881,237형 전수 감사, r3 후보·선택 분리, 재정렬 범위 수정과 논문 각주용 축약문을 기록 |
| `RESULT_common_pron_r3_g2p_candidate_phase_20260808.md` | Jamo G2P 310,605개 후보의 13 shard 완결성·no-path/`spn` 0·읽기 전용 감사 기록 |
| `RESULT_common_pron_r3_g2p_agreement_gate_20260808.md` | 후보–독립 규칙 Roman 전수 exact/mismatch, 사전 근거별 보류, 연도별 동일 기준 회계와 독립 감사 기록 |
| `RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md` | mismatch 214,321 target의 편집·model 표상·사전/형태소/연도 근거 전수 진단, 2,625패턴·56행 handoff와 독립 감사 기록 |
| `RESULT_common_pron_r3_model_projection_candidates_20260808.md` | 좁은 model 단위화 관계와 exact 문맥 donor로 target 후보 264,906개를 마련하고 잔여 45,699개를 보류한 전수 projection·독립 감사 기록 |
| `RESULT_common_pron_r3_selection_readiness_20260808.md` | 881,237형에 r2·donor·사전·projection을 연결한 candidate/복수변이/zero-fallback 전수 회계, 국소 복구와 전역 donor 확장 필요성 기록 |
| `RESULT_common_pron_r3_global_projection_v2_20260808.md` | canonical exact donor 382,891형 전역 projection, 후보 획득·상실·변경, 09 readiness와 독립 감사 결과 |
| `RESULT_common_pron_r3_no_rule_hold_characterization_20260808.md` | no-rule 보류 85,504형을 문자·사전·r2 출처·편집 유형으로 전수 분류하고 규칙/phone 매핑 감사 우선순위를 정한 결과 |
| `RESULT_common_pron_r3_rule_phone_coverage_audit_20260808.md` | 수의적 위치동화·frozen MFA 사전 변이·비일대일 phone을 분리한 85,504형 전수 읽기 전용 감사와 다음 candidate-only 정책 |
| `RESULT_common_pron_r3_selection_readiness_v2_20260808.md` | 감사된 no-rule 37,379형만 정렬용 계획 후보로 추가한 881,237형 readiness v2와 잔여 91,553형 회계 |
| `RESULT_common_pron_r3_readiness_v2_residual_priorities_20260808.md` | 잔여 zero-fallback 91,553형을 target donor 불합의와 no-rule phone/단위화 반복 패턴으로 분리한 다음 구현 우선순위 |
| `RESULT_common_pron_r3_contextual_dictionary_donor_audit_20260808.md` | frozen 기본사전의 단어·음절·이차조음 문맥 donor inventory와 91,553형의 합의·복수·충돌·근거 없음 전수 감사 |
| `RESULT_common_pron_r3_selection_readiness_v3_20260808.md` | 기존 phone·Roman을 바꾸지 않는 이차조음 6,141형만 정렬용 후보로 추가한 readiness v3와 잔여 85,412형 회계 |
| `RESULT_common_pron_r3_unanimous_phone_change_audit_20260808.md` | 단일 문맥 donor가 있지만 phone 삽입·치환이 필요한 4,453형·4,900 issue를 규칙별로 분류하고 모두 hold한 Stage 15 감사 |
| `RESULT_common_pron_r3_morph_context_evidence_20260808.md` | Stage 15 보류 4,453형을 6개년 검색 master의 exact 표면 어절과 안전한 형태소·품사 문맥에 연결하고 자동 후보 없이 보존한 Stage 16 감사 |
| `RESULT_common_pron_r3_attested_full_sequence_projection_20260808.md` | 실제 사전 등재 `pron_1/2`·규칙 exact 65형의 전체 model-phone열을 감사해 14형만 candidate-only로 계획한 Stage 17 |
| `RESULT_common_pron_r3_selection_readiness_v4_20260808.md` | Stage 17의 14형만 병합하고 v3 비대상 881,223행 변동 0을 확인한 readiness v4 |
| `RESULT_common_pron_r3_pre_adoption_routing_20260808.md` | 실제 pre-MFA tokenizer로 5,103,356발화를 safe body 4,384,992와 follow-up 718,364로 전수 라우팅한 Stage 19 |
| `RESULT_common_pron_r3_safe_body_candidate_20260808.md` | 795,804형·796,061변이의 `NOT_ADOPTED` 후보 사전과 frozen acoustic inventory 전수 감사 |
| `RESULT_common_pron_r3_targeted_regression_20260808.md` | 기존 2022 문제 표본 네 발화의 r3 표적 정렬·자동 구조 검사와 최소 연구자 검토 절차 |
| `RESULT_db_v1_recovery_D10_materialization_20260818.md` | D9 부분 보존 16건을 D: 격리 수동 작업본으로 생성하고 4-tier·파일 SHA·비채택 상태를 감사한 결과 |
| `DECISION_common_pron_r3_adoption_choice_pending_20260808.md` | 단계적 safe-body 채택 전 선택 Gate의 역사 기록; 2026-08-09 승인으로 해소됨 |
| `DECISION_common_pron_r3_full_realign_2020_2025_20260809.md` | safe-body 4,384,992발화의 6개년 신규 r3 정렬, r2 interval 비재사용, follow-up 718,364 별도 보존을 확정한 현행 결정 |
| `DECISION_common_pron_r3_v3_1_staged_adoption_amendment_20260809.md` | 승인된 단계적 safe-body 범위를 v3.1 계약으로 고정하고 최초 승인과 provenance sidecar를 분리한 결정 |
| `RESULT_common_pron_mfa_r3_staged_release_20260809.md` | staged selected projection·796,061행 MFA 사전 byte 동등성과 독립 adoption 감사 결과 |
| `RESULT_mfa_r3_year_input_contract_2020_20260809.md` | 2020 safe/follow-up·pre-MFA 기술 제외·복구 corpus를 exact-ID로 결속한 입력 계약 결과 |
| `RESULT_mfa_r3_alignment_contract_2020_20260809.md` | r3 release·routing·입력·모델·사전을 단일 alignment contract ID로 동결한 결과 |
| `RESULT_mfa_r3_runner_preflight_2020_20260809.md` | r3 전용 이름공간·checkpoint·lock·용량 산식 runner와 Gate-closed 실자료 preflight 결과 |
| `RESULT_mfa_r3_exporter_audit_contract_20260809.md` | 승인 6-tier를 유지하며 r3 provenance 10필드·DB SHA·phoneme label 독립 감사를 추가한 결과 |
| `RESULT_mfa_r3_checklist_1_7_candidate_20260809.md` | 외부 리뷰 체크리스트 1–7 통합 통과와 release Gate 직전 안전 정지점 |
| `RESULT_mfa_r3_production_gate_and_2020_go_20260809.md` | 연구자 Gate 승인, r3 단일 release 채택, 정책 감사 v2와 2020 preflight 18/18 GO, 장시간 실행·재개 경계 |

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
| `DECISION_post_search_acoustic_measurement_tooling_20260814.md` | kPhonetica는 참고로 제한하고 선택 발화 manifest·음향 측정 동반표·Praat/Parselmouth 중심 후처리를 채택한 결정 |
| `PLAN_post_production_recovery_target_manual_session_json_20260814.md` | 6개년 완료 뒤 제외분 재처리, 의미번호 포함 표적 추출, 수동 TextGrid overlay, 세션 JSON, 재사용 HTML 매뉴얼과 공동연구·공개용 버전형 release의 순서·schema·Gate 계획 |
| `RESULT_mfa_r3_2025_preflight_20260814.md` | 2025 exact-ID 458,413 입력·연구 DB·정렬 계약·runtime preflight·2024→2025 Gate 8/8 통과와 제한 셸 runtime 오탐 처리 기록 |
| `../reviews/REVIEW_hyunjung_joo_KOINA_prosody_literature_20260810.md` | 조현정 AP 자료·Dual-Glob·fuzzy/R 코드와 KOINA·자연대화 AP/IP 문헌의 역할·한계·프로젝트 적용 판단 |
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
- [PLAN_db_v1_rc1_recovery_adoption_gate_20260818.md](PLAN_db_v1_rc1_recovery_adoption_gate_20260818.md) — D7–D10 exact-ID 55건을 RC0 불변 append-only 상태 overlay와 D10 수동 snapshot 후보로 묶고 단일 연구자 승인 전 정지하는 계획
- [RESULT_db_v1_rc1_recovery_adoption_gate_20260818.md](RESULT_db_v1_rc1_recovery_adoption_gate_20260818.md) — D7–D10 exact-ID 55건과 수동 word·전사 16건을 RC0 불변 overlay 후보로 통합하고 독립 감사 통과, 실제 채택 전 단일 승인 Gate에서 정지
- [DECISION_db_v1_rc1_recovery_sidecar_adoption_20260818.md](DECISION_db_v1_rc1_recovery_sidecar_adoption_20260818.md) — 연구자 승인 exact-ID 55건과 수동 word·전사 16건을 RC0 불변 append-only RC1 sidecar로 채택하되 D9 phone·형태소 보완은 후속 Gate로 분리
- [RESULT_db_v1_rc1_recovery_sidecar_20260818.md](RESULT_db_v1_rc1_recovery_sidecar_20260818.md) — 승인 exact-ID 55건·curated snapshot/pointer 16건의 RC0 불변 RC1 sidecar 채택과 독립 감사 완료, 본체 회계 delta 0
- [DECISION_post_RC1_priority_reset_20260818.md](DECISION_post_RC1_priority_reset_20260818.md) — 16건 enrichment를 실제 표적 포함 시 exact-ID로 지연하고 RC0 기본+RC1 curated pointer precedence와 범용 target 조회 인프라를 우선하는 방향 재설정
- [RESULT_db_v1_target_manifest_pilot_20260818.md](RESULT_db_v1_target_manifest_pilot_20260818.md) — RC0+RC1 active precedence와 ㄴ 삽입 유사 철자·형태소 환경 후보 22건을 검증하고, 실현 판정·시간 연결·MFA와 분리한 범용 표적 manifest 파일럿 결과
- [RESULT_db_v1_target_interval_link_pilot_20260818.md](RESULT_db_v1_target_interval_link_pilot_20260818.md) — 형태소 어절 index를 기존 TextGrid words tier에 연결해 19개 검토 문맥 시간을 파생하고 좁은 음운 경계·실현 판정과 분리한 파일럿 결과
- [PLAN_n_insertion_B1_to_production_query_20260818.md](PLAN_n_insertion_B1_to_production_query_20260818.md) — 구 MFA phone 실현 판정 문구를 폐기하고 ㄴ 삽입의 어절 내부/간 모집단·의미번호·active pointer·수동 판정 Gate를 생산 질의 순서로 고정한 계획
- [DECISION_stage1_data_infrastructure_closure_20260818.md](DECISION_stage1_data_infrastructure_closure_20260818.md) — 자료구축 1단계 공식 종료: 완료 7범위와 machine-readable 근거 결속, 비승인 항목 명시, 잔여 recovery·enrichment·의미번호 join·cleanup·main 동기화의 소속 Gate 라우팅
- [PLAN_stage2_target_query_and_realization_design_20260818.md](PLAN_stage2_target_query_and_realization_design_20260818.md) — 2단계 정본 설계: G0–G8 Gate 순서(query 동결→의미번호 join→2020 생산 감사→6개년 후보→문맥 연결→검토 bundle→연구자 실현 ledger→표적 후속), 산출물 schema 계약과 미실행 범위
- [RESULT_stage1_closeout_D_share_package_20260818.md](RESULT_stage1_closeout_D_share_package_20260818.md) — D:\30_RELEASES에 closeout 문서·RC0/RC1/active view·HTML 보고서·repo snapshot을 미러 배치한 공유 패키지, 48파일 SHA 전수 대조 mismatch 0과 PACKAGE_MANIFEST 기록
- [RESULT_stage2_G1_query_freeze_20260818.md](RESULT_stage2_G1_query_freeze_20260818.md) — ㄴ 삽입 생산 query v1(QN1 intra/QN2 inter) 동결: builder 무수정 선언형 조건, 실측 열 확인과 23케이스 검증, 연구자 승인 SHA 결속; 실행은 G3부터 별도 GO
- [RESULT_stage2_G2_variable_join_contract_20260818.md](RESULT_stage2_G2_variable_join_contract_20260818.md) — A2 의미번호·A3 어원/빈도 join 계약 동결: index 대응 26/26·A3 probe 16/16 실측, MFS 주의·etym_origin 참고 전용 내장, zero-drop 커버리지 감사 사양; 실행은 G3 GO 후
- [RESULT_stage2_G3_2020_production_audit_20260818.md](RESULT_stage2_G3_2020_production_audit_20260818.md) — 2020 후보 101,638행(intra 42,604/inter 59,034) 생성·변수 join zero-drop·sense 불일치 0·독립 감사 13/13 passed; 한자어 내부 후보 111, RC1 curated 1 포함; G4는 별도 GO
