# 자산 대장 — 현재 생산 기준

최종 갱신: 2026-08-17 KST

이 문서는 현재 필요한 자산의 위치만 기록한다. 2026-07-24 전체 인벤토리는
[archive/ASSETS_LEDGER_20260724_full.md](archive/ASSETS_LEDGER_20260724_full.md)에
보존한다. 추정으로 완료를 선언하지 않고, 대량 이동 뒤에는 manifest 또는 보고서로
갱신한다.

## D: DATA_SSD — 원자료와 현재 생산 자산

| 자산 | 현재 역할 | 상태 |
|---|---|---|
| `D:\00_RAW\dialogue_json` | 전사 JSON 원본 | 보존, 수정 금지 |
| `D:\00_RAW\reference\*` | 우리말샘·MP·LS·다층위 reference | 4종 D: 확보 기록 있음; 사용 직전 실물·SHA 재확인 |
| `D:\10_LAYERS\01_bareun_raw` | 연도별 형태소 분석 CSV | 보존 |
| `D:\10_LAYERS\05_search_master` | 동결 5,103,356발화 연구 검색 master | 보존, `_build_meta` SHA 계약; r3 MFA 입력 root로 사용 금지 |
| `D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725` | 동결 pre-MFA 발음 입력 master | `pron_reference_form`과 실제 LAB tokenizer의 r3 발화 라우팅 정본 |
| `D:\10_LAYERS\09_morph_search_v3_staging` | pre-MFA 연도별 7개 조합검색표 | 2020–2025 생산 연도 manifest success. 2025는 30/30 shard·발화 master 587,121행·frozen source contract·독립 검사 12/12·연간표 SHA 7/7 통과; 재생성 금지 |
| `D:\10_LAYERS\10_pronunciation_reference\dictionary_pron_registry_v2_20260805` | 우리말샘 1:N·예외 발음, occurrence와 규칙/사전/MFA 비교표 | registry 1,192,729행 채택; 2020·2021 occurrence 5,767,506/12,015,453행, 비교표 3,042,451/6,610,698행, index 870,437/1,373,920행 전수 검증 |
| `D:\20_AUDIO\03_wav` | 원 WAV·LAB 코퍼스 | 원자료, 수정 금지 |
| `D:\20_AUDIO\04_wav_id_recovered_staging\individual\2020` | 2020 MFA 전용 파생 WAV | 868,603건, 계약 passed |
| `D:\20_AUDIO\08_textgrid_research_v2_staging\2020` | 2020 신규 r2 6-tier·동반표 출력 | TextGrid 868,187개·독립 감사 성공·Gate B 통과 |
| `D:\20_AUDIO\08_textgrid_research_v2_staging\2021` | 2021 신규 r2 6-tier·동반표 출력 | TextGrid·동반표 1,371,883발화 완료; 후행 무음 word 표지 19건 국소 정규화 |
| `D:\20_AUDIO\09_textgrid_pron_reference_v1_pilot_20260805` | 7번째 `pron_reference_utt` 구현 파일럿 | 2020 2세션 914개; 기존 6-tier 변경 0, 독립 감사 통과 |
| `D:\20_AUDIO\09_textgrid_pron_reference_v1_staging\2021` | 세션 checkpoint형 7-tier 파생 생산본 | 4,139세션·1,371,883개; 기존 6-tier 변경 0, 독립 감사 오류 0 |
| `D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728` | 구 공통 Jamo r2 사전·감사 증거 | 읽기 전용 보존, 신규 MFA 사용 금지 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807` | r3 canonical·donor·G2P 후보, 규칙 Gate, 발화 라우팅, safe-body 후보, 표적 회귀 | Stage 01–21 완료; safe 4,384,992·follow-up 718,364; 채택 release의 역사적 입력 근거, 직접 생산 입력으로 임의 변경 금지 |
| `D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809` | 채택된 r3 selected projection·796,061행 MFA 사전·독립 감사 | production Gate `adopted`; 2020–2025의 유일한 신규 MFA 발음 release, r2와 혼합 금지 |
| `D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\05_research_database` | r3 발음 유형–발화 scope–참조 어절 occurrence 정규화 정본 | 2020–2025 연도별 구축·독립 감사 passed; 2025 발화 587,121·occurrence 4,888,815·r3 input 458,413, post-MFA 결합 키와 SHA 고정 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\10_no_rule_hold_characterization` | no-rule 85,504형의 문자·사전·r2 출처·편집 유형 전수 특성화 | `success_characterized_not_candidate`; 모두 완성형 한글, 독립 감사 통과, 후보·selection·adoption 아님 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\11_rule_phone_coverage_audit` | no-rule 변이의 수의적 위치동화, frozen 기본사전 정확 일치, phone↔규칙키 비일대일성 전수 진단 | `success_audited_not_candidate`; 36,568형 all-optional, 811형 비중복 all-frozen, 48,043형 미해결, 독립 감사 통과 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\12_selection_readiness_v2` | stage 09 전체 readiness에 감사된 no-rule 정렬 후보 37,379형만 추가한 881,237형 계획표 | `success_planning_not_selected`; candidate 789,649형, zero-fallback hold 91,553형, 독립 감사 통과, adoption 아님 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\13_contextual_dictionary_donor_audit` | frozen 기본사전의 단어·음절·국소 분절·이차조음 donor inventory와 readiness v2 hold 전수 합의·충돌 감사 | `success_audited_not_candidate`; 단일 10,594형, 복수 22,171형, 충돌 48,780형, 근거 없음 10,008형; 독립 감사 통과 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\14_selection_readiness_v3` | phone 불변 이차조음 onset+glide 6,141형만 추가한 881,237형 계획표 | `success_planning_not_selected`; candidate 795,790형, zero-fallback hold 85,412형, phone·Roman 전수 불변 감사 통과, adoption 아님 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\15_unanimous_phone_change_audit` | 단일 문맥 근거지만 r2 phone 삽입·치환이 필요한 4,453형·4,900 issue의 규칙별 읽기 전용 inventory | `success_audited_not_candidate`; 자동 후보 0형, 4,453형 hold 보존, 독립 감사 통과 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\16_morph_context_evidence` | Stage 15 보류 4,453형을 동결 검색 master의 exact 표면 어절과 안전한 Bareun 형태소·품사 문맥에 연결한 읽기 전용 inventory | `success_evidence_linked_not_candidate`; 표면 68,285회·형태소 60,292회 연결, 자동 후보 0형, 독립 감사 통과 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\17_attested_full_sequence_projection` | 사전 등재 `pron_1/2`·규칙 exact 65형의 전체 model-phone열 문맥 projection | `success_candidate_plan_not_selected`; 14형·200회 candidate-only, 51형 hold, legacy 기계발음 76형 제외, 독립 감사 통과 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\18_selection_readiness_v4` | Stage 17 독립 감사 후보 14형만 병합한 881,237형 readiness v4 | `success_planning_not_selected`; candidate 795,804형, hold 85,398형, 비대상 행 변화 0, 독립 감사 통과 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\19_pre_adoption_routing` | 실제 pre-MFA tokenizer로 2020–2025 발화를 safe body/follow-up으로 전수 라우팅 | `passed_independent_full_scan`; 5,103,356발화 중 safe 4,384,992, follow-up 718,364, unknown 0 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\20_safe_body_candidate` | readiness candidate-only MFA 사전·projection | `passed_candidate_only_not_adopted`; 795,804형·796,061변이, inventory 밖 phone·`spn` 0, adoption 아님 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\21_targeted_regression_2022` | 기존 2022 발음 문제 네 발화의 r3 raw 표적 회귀 정렬 | 자동 검사 4/4·연구자 경계 승인 4/4; r2 원본 무변경; 승인 계약은 저장소 outputs에 보존 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\archive_intermediate\19_pre_adoption_routing_failed_*` | 구 검색 root·LAB tokenizer count 가정으로 안전 중단된 Stage 19 두 partial | 삭제하지 않고 원인별 이름으로 보존, 생산 입력 금지 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\archive_intermediate\08_global_projection_failed_field_order_20260808_1301` | 전역 projection 과도한 열 순서 검사 안전 중단 partial | 343B·192B 실패 증거; 생산 입력으로 사용 금지 |
| `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\archive_intermediate\05_g2p_mismatch_diagnostics_initial_20260808_1053` | 초기 mismatch 진단 중간본 | 활음 이차조음 분류 보강 전 결과와 manifest 보존; 생산 입력으로 사용 금지 |
| `D:\mfa_eojeol` | 입력·정렬 계약, marker, log, lock | 2020–2022 r2 marker·계약 보존; r2 신규 실행 Gate 차단, r3 production namespace 분리 |
| `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809` | r3 연도별 corpus·contract·temp/DB·log·marker·lock | 2020–2025 `ALIGN_DONE`·독립 QC passed. 2025 DB 6,702,276,608 bytes·SHA `5d7eab5a...c0e6`, 입력 458,413 = 성공 457,611 + 승인 후속 802. 여섯 연도 MFA·DB·완성 6-tier 재실행·수동 삭제·legacy 재사용 금지 |
| `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\research_6tier` | 최종 r3 6-tier TextGrid·연도별 gzip 동반표 | 2020 782,432·2021 1,206,862·2022 751,383·2023 494,228·2024 593,530·2025 457,611 TextGrid; 여섯 연도 모두 coverage 100%·hard failure 0·DB 표본 semantic/byte 24/24, 연도별 `QC_STATE.json` passed |
| `D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D9_CONTROLLED_BEAM_RETRY_0001` | D8 확인 미정렬 19건의 한 차례 beam 100/retry 400 격리 재시도 root | 실행 완료: TextGrid 19/19·누락 0·707.031초; 25개 초단편·전체연도 미실행, 자동 병합 0 |
| `D:\mfa_tmp\2020\2020.db` | 2020 공통 Jamo r2 보존 정렬 DB | 868,187 정렬 성공·363 승인 미정렬; Gate B 근거로 보존 |
| `D:\mfa_tmp\2021\2021.db` | 2021 공통 Jamo r2 보존 정렬 DB | 1,371,883 정렬 산출; 읽기 전용 비교 증거 |
| `D:\mfa_tmp\2022\2022.db` | 2022 공통 Jamo r2 보존 정렬 DB | 864,690 정렬 산출; 발음 입력 문제 발견 근거로 읽기 전용 보존 |
| `D:\mfa_eojeol_out` | 용량 폴백 작업경로 | 현재 연도 실행 중에만 사용 |

CSV는 정리 대상이 아니다. 형태소 CSV, 조합검색 7표, post-MFA 동반표 4개,
WAV–TextGrid–metadata 연결표, 승인·제외·미해결 기호표는 모두 연구 인프라의
필수 산출물로 유지한다.

사전 발음 registry v2는 공통 MFA 입력 phone 사전이 아니다. `pron_1/2`와
fallback의 표제어·품사·의미·출처를 occurrence에 조인하고 규칙 예상형·MFA
phone과 비교하기 위한 참조 자산이다. 비채택 v1은 감사 근거로만 보존한다.

## E: — 읽기 전용 archive

archive root:

```text
E:\READ_ONLY_ARCHIVE\2026_summer_research
```

| 묶음 | 내용 | 상태 |
|---|---|---|
| `pre_jamo_compressed_20260728` | 구 2020/2021 TextGrid, 구 2021 MFA DB/temp, stale temp, 실패 모델 clone | 검증 성공; D: 55.883GiB 정리 완료 |
| `wav_id_recovery_2020_eb64f80d9106` | 2020 WAV ID 복구 전 영향 세션 | 128 ZIP + 129 manifest, 계약 passed |
| `wav_id_recovery_2020_eba4f3c7debf` | 첫 복구 계약의 안전 중단 증거 | 역사·실패 근거로 보존 |
| `legacy_d_workspace_20260802` | 구 공통사전 r1/A-B/파일럿과 구 `06_textgrid_*` | 2026-08-02 완료; TextGrid 8항목 7,341,358파일/33.297GiB를 2.226GiB로 검증 보존 후 D: 정리 |
| `pre_2021_active_state_20260803` | D:에 남았던 구 2021 로그·LAB 완료표시·입력계약 9개 | 4,208,271 bytes → 458,443-byte 7z; CRC·SHA 검증 성공, 활성 사본 0 |
| `pronunciation_reference_pre_adoption_20260805` | 비채택 registry v1과 폐기된 2020 비교 좌표 파일럿 2종 | 6파일·84,513,545 bytes; 84,504,963-byte 7z, SHA-256·7-Zip 검사 통과; 채택 v2는 D: 유지 |

archive는 원자료 정본이 아니라 과거 산출물의 재현·감사 근거다. E: archive가
검증되기 전에는 대응하는 D: 경로를 제거하지 않는다.

## H: SAMSUNG — 과거 전체 백업

2026-08-02 여유가 약 93GiB여서 새 archive 대상으로 사용하지 않는다. D:와 E:의
현재 생산 경로와 혼동하지 않도록 읽기 전용 비교·비상 복구용으로만 취급한다.

## 저장소와 GitHub

| 자산 | 현재 역할 | 상태 |
|---|---|---|
| `outputs\releases\nikl_dialogue_research_db_v1_0_0_rc0_20260815` | 6개년 same-contract 감사·저장공간 계획·5,103,356 exact-ID 상태 장부 | 내부 rc0 A–C 완료; gzip 장부는 Git 제외, JSON·방법 문서는 추적; r3 원본 변경 0 |
| `outputs\reports\AUDIT_db_v1_release_prep_ac_20260815.json` | A–C 패키지 독립 510만 행 감사 | `passed`; 누락·중복·미분류·계약/상태/SHA 결속 오류 0 |
| `outputs\releases\nikl_dialogue_research_db_v1_recovery_d9_gate_20260817` | D9 19건 run shard·100/400 설정·execution contract·승인 template | `passed_gate_closed_before_D_write_and_mfa`; 실행·자동 병합 0 |
| `outputs\reports\PREFLIGHT_db_v1_recovery_D9_20260817.json` | D9 실자료 read-only preflight | `passed_ready_to_execute`; 승인 결속·19건·모델/사전/입력 SHA·D: 용량 확인 |
| `outputs\approvals\APPROVAL_db_v1_recovery_D9_CONTROLLED_BEAM_RETRY_0001.json` | D9 19건·100/400·1회·무병합 승인 | `ari30` 명시 승인; 세 계약 SHA 결속, 승인 포함 preflight 통과 |

```text
C:\Users\ari30\research\2026_summer_research
```

코드·설정·작은 CSV/보고서·방법론 문서의 정본이다. 대형 WAV/TextGrid/DB는 Git에
넣지 않는다. 현재 작업 브랜치는 `agent/harden-pre-bulk-pipelines`이며, 정리 기록은
검증 완료 뒤 커밋·푸시한다.

현행 r3 범위 계약은 `config/mfa_r3_full_realign_workflow_v1.json`이다. 단계적
범위 승인은
`outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json`,
단일 production Gate 승인은
`outputs/reviews/common_pron_r3_production_gate_20260809/RESEARCHER_APPROVAL_PRODUCTION_GATE.json`에
불변 기록했다. 정책 감사
`outputs/reports/AUDIT_mfa_r3_full_realign_policy_v2_gate_adopted_20260809.json`은
실제 Stage 19 연도 수량·Gate 증거·r3 실행 경로의 legacy token을 검사해 통과했고,
기존 Gate 직후 preflight
`outputs/reports/PREFLIGHT_mfa_r3_runner_2020_gate_adopted_go_20260809.json`은
18/18 `GO`였고, 발음 연구 DB Gate를 추가한 최신 runtime preflight
`work/mfa_r3_preflight/PREFLIGHT_common_pron_mfa_r3_20260809_2020.json`은
19/19 `GO`다. 이후 같은 계약으로 2020–2025 r3 정렬·6-tier·독립 QC를
완료했다. 2024 수출의 원문 내장 줄바꿈 두 건은 DB와 기존 산출물을 보존한 표적
복구로 완료했고, 2025는 입력 458,413 = 정렬 성공 457,611 + 승인 후속 802로
동결했다. 다음은 여섯 연도 완료 state의 읽기 전용 교차 감사와 별도 follow-up
shard다.

## 2020 현재 계약

- source contract: `morph_search_v3_20260801/2020/SOURCE_CONTRACT.json`
- WAV recovery contract ID:
  `eb64f80d9106d14c7b2a267811cdf2dc2fe29e890cc335a7029a8cca24a7375f`
- 승인 제외: 음원 미대응 1,834 + 빈 LAB 미해결 기호 53 = 1,887
- 부분 LAB 미해결 기호 6,158: 제외하지 않고 동반 CSV 경고로 보존
- 연구자 승인: 2026-08-02 `ari30`, 두 범주 모두 승인
- MFA 상태: 2020 신규 r2 계산 완료; 보존 DB 868,187 정렬 성공·363 미정렬
- post-MFA 연결 QC: 16표본 완료, 13 match + 3 `audio_unusable`
- 결합 승인 계약:
  `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_export_20260803/2020/`
  — pre-MFA 1,887 + post-MFA 363(청취 불가 3 + 정렬 실패 360) = 2,250;
  보존 DB의 실제 미정렬 ID와 exact match
- TextGrid·동반표: `D:\20_AUDIO\08_textgrid_research_v2_staging\2020`에
  868,187개 export 완료. utterance 868,187, word 4,973,795,
  phone 19,101,192, excluded 2,250행이며 독립 감사 하드 실패 0
- TextGrid 경계: 2020 DB 868,187/868,187 word-phone 바깥 경계 일치;
  모든 tier가 0–xmax를 연속적으로 덮음
- 생산 표본: 24/24 연구자 승인, 실제 실현 판정은 수행하지 않음
- Gate B: 16/16 core check 통과, 실패 0, `allow_remaining_years=true`

2021–2025 LAB·pending 제외 후보표와 safe-body 5행 요약은 완료됐다. 저장소의
현행 검토 root는
`outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_safe_body_2021_2025_20260803`이며,
검색 4,232,919 중 안전 본체 4,120,627, 후보 112,292다. 이 승인·제외 계약은
r3 재정렬에서도 재사용하되 r2 MFA를 새로 시작하는 근거로 쓰지 않는다. 다음
생산 단계는 r3 발음 release 채택이며 실행 순서는
[RUNBOOK_production_2020_2025.md](RUNBOOK_production_2020_2025.md)만 따른다.

위 4,120,627은 과거 음원·CSV·승인제외 기준의 safe-body 수이며, Stage 19의
발음 coverage safe-body 4,384,992와 다른 집합이다. r3 연도 입력기는 두 값을
혼용하지 않고 `pron_safe_body`와 기존 제외 계약의 exact-ID 교집합을 별도로
계산·보고해야 한다.

2021 기존 `.lab`은 동결 CSV 기반의 재사용 입력이라 보존했다. r3 재정렬 시에도
LAB 자체는 전수 재생성하지 않고 frozen source contract를 재검증해 불일치만
재작성한다.

## 2026-08-15 recovery D0–D4 자산

| 자산 | 역할 | 상태 |
|---|---|---|
| `outputs\releases\nikl_dialogue_research_db_v1_recovery_d0_d4_20260815` | 후속 817,310건 reason별 exact-ID 장부, 기술 회수 감사, 발음 유형 축약, 첫 진단 shard | 독립 감사 `passed`; gzip 대형 장부는 Git 제외, JSON·방법 문서 추적; r3 본체 변경·파일 생성·MFA 0 |
| `outputs\reports\PREFLIGHT_db_v1_recovery_D4_20260815.json` | 55건 첫 진단 shard의 Windows PowerShell 5.1 읽기 전용 사전검사 | `passed_gate_closed`; 승인 없음·materialization 0·MFA 0 |

D:의 향후 recovery root는 계획 경로일 뿐 아직 생성하지 않았다. E:로 archive
복사하거나 D: 자산을 이동·삭제한 작업도 없다.

## 2026-08-15 recovery D5 Gate 자산

| 자산 | 역할 | 상태 |
|---|---|---|
| `outputs\releases\nikl_dialogue_research_db_v1_recovery_d5_gate_20260815` | D4 55건의 WAV/LAB/사전 감사, 25건 no-run 길이 회수 장부, 30건 exact 실행 shard와 scope-bound 승인 계약 | 승인 범위대로 D5 실행 완료; 입력·no-run SHA 동결 유지 |
| `outputs\reports\PREFLIGHT_db_v1_recovery_D5_20260815.json` | 30건 source·모델·용량·출력 namespace와 승인 계약 읽기 전용 검사 | `passed_ready_to_execute`; 실제 실행 직전 commit·시각으로 갱신 |
| `outputs\reports\RESULT_db_v1_recovery_D5_20260815.json` | D5 30건 진단의 성공·미정렬 exact-ID 회계와 안전성 정본 요약 | `completed_diagnostic_no_merge`; TextGrid 11, missing 19, no-run 25 보존 |
| `scripts\run_db_v1_recovery_d5_shard.ps1` | 승인 후 30건만 copy-materialize하고 진단 MFA·결과 감사를 수행하는 재개형 실행기 | 승인 SHA·copy SHA·lock·heartbeat·실패 보존·자동 병합 금지; 실행 완료 |

D5의 격리 D: root에는 입력 WAV/LAB 각 30개, 진단 TextGrid 11개, 미정렬 19개
장부와 temp·로그가 보존되어 있다. 25건은 삭제된 것이 아니라
`D5_NO_RUN_AUDIO_DURATION_RECOVERY.csv`에 원 음원 길이 회수 대상으로 남아 있다.
이 D5 산출물은 r3 본체·연구용 6-tier·DB v1에 자동 병합되지 않았다.

## 2026-08-15 recovery D6 Gate 자산

| 자산 | 역할 | 상태 |
|---|---|---|
| `outputs\releases\nikl_dialogue_research_db_v1_recovery_d6_gate_20260815` | 성공 11·미정렬 19·짧은 음원 25건의 사후 분기 권위 장부와 Gate | 독립 감사 통과; 본체·6-tier·DB v1 병합 0 |
| `outputs\reviews\db_v1_recovery_d6_20260815` | 11건 번호별 WAV·LAB·2-tier TextGrid와 입력 가능한 검토 CSV | flat 35개 입력/안내 파일+manifest; `decision=pending` |
| `outputs\reports\RESULT_db_v1_recovery_D6_20260815.json` | D6 생성 결과와 기술 분류 요약 | `built_gate_closed_pending_researcher_review` |

공식 XLSX는 현재 작업에 `load_workspace_dependencies`가 등록되지 않아 만들지
않았다. CSV가 권위 정본이며 임의 의존성·`openpyxl` 우회는 하지 않았다.

## 2026-08-17 recovery D7 부분 정렬 보존 자산

| 자산 | 역할 | 상태 |
|---|---|---|
| `outputs\releases\nikl_dialogue_research_db_v1_recovery_d7_partial_alignment_gate_20260817` | Dropbox 검토 원본, 11건 exact-ID 결정 JSON, 별도 부분 정렬 SQLite와 Gate | 독립 감사 통과; 본체 제외 11, 부분 정렬 보존 6, 파일 삭제·자동 병합 0 |
| `outputs\reports\RESULT_db_v1_recovery_D7_20260817.json` | D7 분류와 안전 상태 요약 | `closed_researcher_review_recorded_no_main_body_adoption` |

D6의 11개 WAV·LAB·TextGrid는 기존 검토 root에 유지한다. D7 SQLite는 경로와
SHA를 참조할 뿐 음성·TextGrid를 중복 복사하거나 본체 DB에 삽입하지 않는다.

## 2026-08-17 recovery D8 회수 가능성 감사 자산

| 자산 | 역할 | 상태 |
|---|---|---|
| `outputs\releases\nikl_dialogue_research_db_v1_recovery_d8_feasibility_audit_20260817` | 미정렬 19·0.1초 미만 25건의 JSON/CSV/LAB/canonical-r3-H 음원 identity와 D9 routing | 독립 감사 통과; D9 후보 19, 동일 exact-ID 기술 제외 25, MFA·파일 생성·본체 변경 0 |
| `outputs\reports\RESULT_db_v1_recovery_D8_20260817.json` | D8 수량·안전 상태 요약 | `read_only_feasibility_audit_complete_gate_closed` |

D8 SQLite는 로컬 조회용이며 Git에는 넣지 않는다. exact-ID 판정 JSON, Gate,
manifest와 독립 감사 보고서가 재현 가능한 정본이다. H:의 대형 평면 PCM 폴더를
반복 열거하지 않고, 기존 direct-stat 장부와 세션 구조 H WAV의 payload/길이를
결합해 검사했다.

## 2026-08-17 recovery D9 실행·검토 자산

| 자산 | 역할 | 상태 |
|---|---|---|
| `D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D9_CONTROLLED_BEAM_RETRY_0001` | 19건의 격리 beam 100/retry 400 실행·DB·2-tier TextGrid·로그·marker | `completed_controlled_retry_no_merge`; TextGrid 19/19, 누락 0, 본체 채택 0 |
| `outputs\reviews\db_v1_recovery_d9_review_19_20260817` | 번호별 WAV·LAB·2-tier TextGrid와 JSON 검토표 | 독립 감사 `passed_flat_review_bundle_no_adoption`; 19세트, overlap 4건 표시 |
| `outputs\reports\RESULT_db_v1_recovery_D9_20260817.json` | 실행 수량·계약 SHA·검토 묶음 SHA·안전 상태 정본 | `completed_controlled_retry_review_ready_no_adoption` |
| `C:\Users\ari30\Dropbox\DB_V1_RECOVERY_D9_REVIEW_19_20260817` | D9 19세트의 개인 연구자 검토용 Dropbox 동기화 사본 | 로컬 복사 61개·1,780,531 bytes·SHA 전수 일치; 공유 링크/외부 공유 변경 0, 클라우드 동기화 완료는 사용자 확인 |
| `outputs\reports\COPY_db_v1_recovery_D9_review_to_Dropbox_20260817.json` | 승인 범위·파일집합 SHA·복사 안전성 기록 | `passed_local_dropbox_copy_sha256_verified` |
| `outputs\reviews\db_v1_recovery_d9_review_19_20260817\01_RESEARCHER_DECISIONS_WORKING.json` | D9 19건 연구자 청취·경계 exact-ID 상세 판정 | 검토 완료: 승인 1, 수동 overlay 16, 기술 제외 2, pending 0; SHA `dfae3884...f1d8` |
| `outputs\reports\RESULT_db_v1_recovery_D9_researcher_review_20260818.json` | D9 연구자 검토 수량·ID·다음 Gate 요약 | `researcher_review_complete_gate_closed_pending_adoption`; 자동 병합 0 |
| `outputs\reports\AUDIT_db_v1_recovery_D9_researcher_review_20260818.json` | 원 검토표–19개 연구자 판정 exact-ID·수량·상태 독립 검사 | `passed_researcher_review_complete_no_adoption`; 누락·중복·pending 0 |
| `outputs\releases\nikl_dialogue_research_db_v1_recovery_d10_manual_overlay_gate_20260818` | 16건 수정 전사·수동 overlay queue, 기술 제외 2·승인 1 별도 routing, 해시 manifest | `passed_gate_closed_before_overlay_materialization`; WAV 복사·TextGrid/DB 변경·MFA 0 |
| `outputs\reports\AUDIT_db_v1_recovery_D10_manual_overlay_gate_20260818.json` | D10 queue와 D9 판정 exact-ID·분류·제안 전사 독립 검사 | 통과: 국소 9·전체 6·단일어 1, 제외 2, 승인 1, pending 0 |
| `D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D10_MANUAL_OVERLAY_0001` | D9 부분 보존 16건의 번호순 WAV·원/제안 LAB·D9 참고/수동 작업 TextGrid와 상태·감사 | `materialized_pending_researcher_manual_overlay`; 16세트×5종, 전체 85파일·1,730,225 bytes, 자동 채택 0 |
| `outputs\reports\RESULT_db_v1_recovery_D10_materialization_20260818.json` | D10 실물 수량·tier 초기화 정책·D: 증거 SHA·안전 정지점 정본 | 생성·독립 감사 통과; 원본·r3·6-tier·DB v1 변경과 MFA 0 |
| `C:\Users\ari30\Dropbox\04_MFA_배치결과\DB_V1_RECOVERY_D10_MANUAL_OVERLAY_16_20260818` | D10 16세트의 개인 연구자 수동 경계 작업용 Dropbox 사본 | 로컬 복사·배치결과 하위 이동 뒤 85파일·1,730,225 bytes·동일 SHA 전수 확인; D: 원본 보존, 공유 링크/권한 변경 0 |
| `outputs\reports\COPY_db_v1_recovery_D10_manual_overlay_to_Dropbox_20260818.json` | D10 Dropbox 복사 범위·파일집합 SHA·원본 보존 증거 | `passed_local_dropbox_copy_sha256_verified`; mismatch 0 |
| `outputs\reports\MOVE_db_v1_recovery_D10_Dropbox_into_mfa_batch_20260818.json` | Dropbox root의 D10 사본을 `04_MFA_배치결과` 아래로 이동한 경로·SHA 증거 | `passed_dropbox_relocation_verified`; 이동 전후 파일집합 SHA 동일, D: 보존 |
| `C:\Users\ari30\Dropbox\04_MFA_배치결과\DB_V1_RECOVERY_D10_MANUAL_OVERLAY_16_20260818.zip` | 다중 파일 동기화를 기다리지 않고 원격 컴퓨터에서 받기 위한 D10 단일 ZIP | 1,143,822 bytes, 7-Zip test와 내부 85파일 source SHA 전수 일치, SHA `78283ae2...47f2` |
| `outputs\reports\ARCHIVE_db_v1_recovery_D10_remote_review_zip_20260818.json` | 원격 검토 ZIP의 범위·압축 검사·entry SHA 증거 | `passed_zip_test_and_entry_sha256`; D:와 Dropbox 폴더 사본 모두 보존 |

WAV·LAB·TextGrid는 Git 전역 제외 규칙에 따라 로컬 검토 root에만 있고, JSON·MD
manifest와 생성·감사 코드는 Git으로 추적한다. Dropbox 사본은 개인 검토 목적이며
외부 공개·공유는 승인되지 않았다.
