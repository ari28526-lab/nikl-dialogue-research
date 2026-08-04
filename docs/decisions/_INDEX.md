# 현행 결정 문서 색인

최종 갱신: 2026-08-04 KST

이 폴더에는 현재 생산·방법론에 실제로 적용되는 결정만 둔다. 종료된 감사,
파일럿, 구 RUNBOOK, MONITOR, 과거 계획 33개는 원문을 삭제하지 않고
`../archive/decisions_pre_production/`으로 이동했다. 현재 실행 명령은
`../RUNBOOK_production_2020_2025.md`만 따른다.

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
| `DECISION_r2_realign_all_six_years_20260729.md` | 구결과 재사용 없이 2020–2025 전부 신규 정렬 |
| `METHODS_MFA_phone_criterion_consistency_2020_2025_20260728.md` | 연도간 phone 기준 동일성 근거 |

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
| `DECISION_2021_feature_generation_ignored_pending_20260804.md` | 2021 feature 생성 실패 24건을 자동 누락하지 않고 MFA 완료 DB 보존·exact-ID 재확인·연구자 승인 뒤 export하는 절차 |
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
