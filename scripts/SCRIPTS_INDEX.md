# 스크립트 색인 — 최종 갱신 2026-08-06

## 현재 생산 진입점

| 순서 | wrapper | 상태 |
|---:|---|---|
| 1 | `prepare_remaining_mfa_approval_reviews.ps1` | 2020 Gate B 통과 뒤 아직 없는 2021–2025 연도별 제외 후보표만 준비; 2020 반복·MFA·자동승인 없음 |
| 2 | `prepare_production_year_before_mfa.ps1 -Year <YEAR>` | 해당 연도 `morph_search.v3` 7표와 동결 source contract를 checkpoint 방식으로 완성; MFA 없음 |
| 3 | `approve_remaining_mfa_exclusion_categories.ps1` | 연구자 명시 승인 뒤 세 범주의 5개년 제외 계약만 기록; MFA 시작 없음 |
| 4 | `start_remaining_mfa_after_2020_gate.ps1 -ApprovedBy ari30` | 검색·승인 계약 뒤 2021만 시작; 2020 재포함·2022 선행 실행 금지 |
| 5 | `prepare_production_year_sample_review.ps1` / `approve_production_year_sample_review.ps1` | 현 연도 기계 QC 뒤 WAV·LAB·6-tier 표본을 준비; 직접 검토 뒤 승인 문장·행 수로 원 pending 보존과 승인 계약을 한 번에 기록; 실현 판정·자동 추론 아님 |
| 6 | `preflight_production_next_year_gate.ps1` / `start_next_mfa_year_after_gate.ps1` | 직전 연도 source·DB·6-tier·동반표·표본 승인과 checkpoint-resume 완료 marker를 결합해 다음 한 연도만 시작 |
| 상태 | `show_mfa_year_queue_status.ps1` | 읽기 전용 큐·lock·D: 상태판 |

`mfa_year_selection.ps1`은 Windows PowerShell 5.1의 `-File` 경계에서 연도 배열이
문자열 하나로 뭉개지는 것을 막는 공용 정규화기다. 외부 wrapper는 `YearsCsv`를
넘기고 내부 runner만 검증된 배열을 사용한다.

2020 생산과 Gate B는 완료됐다. `resume_2020_*`, `start_2020_*`, 2020 검토
wrapper는 재현 근거로 보존하지만 정상 절차에서 다시 실행하지 않는다. 구
3-tier·잔여 재정렬·이행·병목 파일럿 13개는
`archive/pre_2021_legacy_20260803/`로 이동했다.

## 2026-08-01 조합검색 v3 전수 진입

| 스크립트 | 역할 |
|---|---|
| `python/build_morph_search_year_sharded.py` | 동결 pre-MFA search master를 읽기 전용으로 받아 연도·session-file shard별 7개 형태/철자/기호 검색표를 만들고, 성공 shard SHA 재검증·결정적 gzip·연도 승격을 수행한다. 실패 partial은 보존한다. |
| `run_morph_search_year_safe.ps1` | 한 연도만 허용하고 D: 공간·동결 입력 manifest·중복 lock을 검사한 뒤 위 builder를 실행한다. MFA·TextGrid·공통사전은 변경하지 않는다. |
| `prepare_production_year_before_mfa.ps1` | 2021–2025 중 한 연도의 `morph_search.v3`를 생성/재개한 뒤 동결 search master SHA와 연도 manifest를 source contract로 결속한다. 원본·MFA·TextGrid는 바꾸지 않는다. |
| `show_production_year_pre_mfa_status.ps1` | 연도별 shard 진행률·lock PID 생존·annual manifest·source contract·D: 여유를 표시하는 읽기 전용 상태판 | 실행·수정·자동 재개 없음 |
| `show_morph_search_year_status.ps1` | 연도별 shard 진행률, schema, 연도 manifest와 table 행 수를 읽기 전용으로 표시한다. |
| `python/collect_morph_search_regression_evidence.py` | 2020–2025 각 10발화의 두 독립 출력에서 42개 gzip SHA, 어절 좌표 mismatch, 기호 상태와 `2사람이→두` 근거를 감사한다. |


파이프라인 순서대로. 모든 경로 상수는 새 D: 구조 기준 (config/paths.json 참조).
각 코드가 **무슨 자료로·왜·무슨 역할**인지 서술형 해설은
[docs/자료구축_코드해설.md](../docs/자료구축_코드해설.md).

## A단계: 텍스트 레이어 구축
| 스크립트 | 역할 | 상태 |
|---|---|---|
| bareun_dialogue_pilot.py | 바른 API 파일럿 (120발화 검증) | 완료·보존용 |
| bareun_dialogue_full.py | **1차: 전체 형태소 재분석** (510만 발화, 체크포인트) | 실행 완료 |
| repair_empty_tagged.py | 장애 시 오염 파일 탐지·정리 | 유틸 |
| assign_sense_layer.py | **2차: 의미번호 부여** (LS+우리말샘 lexicon) | 실행 완료 |
| supplement_sense_layer.py | 2차 보완 (접사 어간형 색인·다의어 잠정 부여) | 실행 완료 |
| build_freq_dictionaries.py | **3차: 빈도사전** 형태소·어절 2종 (연도별, MP/LS/KoFREN 비교, 어원, IPA). count→merge 2단계 | 실행 완료 |
| build_sense_freq.py | 의미별 빈도표 (02 레이어 기반) | 실행 완료 |
| build_metadata_index.py | 파일 메타데이터 인덱스 (사용역·주제·화자). 파일 stem을 세션 정본으로 쓰고 내부 ID 교차검증, 원자 교체·구판 아카이브 | 2026-07-24 전수 재생성 완료(17,156행, 원본 최상위 ID 오류 4건 추적 보존) |
| build_stratified_freq.py | 층화 빈도 (성별×연령×사용역, per-million, 분산도) | 실행 완료 |

## 2025 음성 파이프라인
| 스크립트 | 역할 | 상태 |
|---|---|---|
| extract_2025_pcm.py | PCM zip 해제 (재개 지원) | 실행 완료 |
| pcm_to_wav_2025.py | PCM→WAV 587,174개 (병렬, 재개) | 실행 완료 |
| `archive/pre_2021_legacy_20260803/python/make_labs_2025.py` | MFA용 형태소 .lab 생성 | archive — 형태소 lab 방식 폐기, 재실행 금지 |
| merge_textgrid_v2.py | **표준 3-tier TextGrid 생성** — MFA 정렬 DB에서 직접 내보내기 (MFA export 교착 우회) | 실행 완료 |

## 인프라
| 스크립트 | 역할 |
|---|---|
| paths.py | config/paths.json 로더 (`from paths import P`) |
| check_python_environment.ps1 | 전역 Python 3.13·py 런처·PATH·프로젝트 `pipeline_python`을 구분 점검하고 샌드박스 접근 거부를 설치 누락과 분리 |
| initialize_common_pron_pilot.ps1 | D: 라벨·여유공간·MFA lock을 검사하고 2020–2025 전체 공통 발음 파일럿 release를 역할별 폴더로 격리 생성. 기존 release 덮어쓰기·원자료 변경·자동 정리 금지 |
| build_common_pron_vocabulary.py | 동결 `pron_reference_form` 6개년 전수에 MFA lab과 같은 토큰화를 적용해 연도별 출현을 포함한 공통 vocabulary와 SHA256 manifest 생성 |
| audit_common_pron_sources.py | enriched `pron_1/2`와 legacy `pron_g2p`를 전수 감사해 행·중복·`urimal_id` fallback을 계측하고 등재 발음과 기계 생성값을 분리 |
| common_pron_ab_pilot.py | 6개년 전체 vocabulary의 exact-word 발음 registry seed→연도별 5화자 stress/control byte-identical A/B corpus→표본 한정 정책 A/B 사전→phone열·경계 비교. 정책 B는 사전 발음을 추가만 하며 자동 채택·canonical 수정 금지 |
| run_common_pron_ab_pilot.ps1 | 공통 발음 정책 A/B end-to-end 안전 실행기. D: 라벨·공간·bulk lock·MFA 패치를 검사하고 current G2P 1-best/strict 계약, 별도 temp/output, 부분 산출 archive, 4-tier QC, 수동 검토 보고서까지 실행 |
| common_pronunciation_contract.py | 공통 발음 자원 v2의 형태소 결합·MFA 활성화 계약. 표면형만 같은 사전 후보를 검색용 `reference_only`로 분리하고 단일형태소 품사 일치·용언 사전형 일치만 occurrence 후보로 허용 |
| audit_common_pron_occurrence_matches.py | A/B stress 발화의 lab 어절과 search master 형태소를 안전하게 왕복 조인하고, 어절 수 불일치는 유일한 표면형 복원 때만 회수하여 사전 후보의 occurrence 적합성 CSV·manifest 생성 |
| build_common_pron_mfa_lexicon.py | 최신 acoustic v3.3.0·Jamo G2P v3.2.0 기준으로 6개년 OOV를 1-best/strict shard화. U+11B3만 같은 모델 입력에서 ㄹ+ㅅ 완전분해하고 원 표층키를 복원한다. 4행 same-model 후보는 불변 증거로 보존하고 별도 연구자 승인 phone만 final에 사용하며, 후보와 다른 수동 교정은 동일 acoustic inventory·근거·notes를 강제한다. 생성기 코드·모델·vocabulary SHA, missing·spn·phone inventory hard gate |
| trace_common_pron_special_occurrences.py | Jamo ㄽ 등 소수 특수 표층형을 공통 vocabulary와 같은 `form_to_lab`로 동결 search-master 전수에서 한 번만 찾아 발화·화자·form/original/pron_reference와 원본 JSON 경로를 연결. 대상 누락·세션/발화 누락·search-master↔JSON 불일치·기존 출력 덮어쓰기를 hard fail하고 CSV·SHA manifest 생성 |
| stage_common_pron_researcher_review.py | no-path·Jamo ㄽ 원본 추적표를 합쳐 연구자 검토용 WAV를 D: release 아래에 복사. 원본을 읽기 전용으로 취급하고 중복 WAV는 한 번만 복사하며 원본/검토본 SHA256 동등성·누락·대상 경계를 manifest로 검증 |
| build_common_pron_researcher_review_xlsx.py | 공통사전 r2 예외 27건의 모델 후보·규범/어휘부 근거·31개 발화·WAV 링크·연구자 결정·재현 계약을 7개 시트 XLSX로 생성. 모든 결정을 pending으로 시작하고 후보 phone과 승인 phone, source correction과 발음 승인을 분리하며 IPA 열은 Noto Sans로 표시 |
| render_xlsx_preview_pil.py | Excel COM이나 artifact renderer를 쓸 수 없는 환경에서 지정 XLSX 범위를 PNG로 읽기 전용 렌더링하는 시각 QA 보조도구. 셀 서식·병합·한글/IPA 폰트를 재현하며 원본 workbook은 수정하지 않음 |
| validate_common_pron_researcher_review_xlsx.py | 연구자가 v5 template을 다른 이름으로 저장해 작성한 사본에서 R·S·U열만 허용하고 나머지 1,860개 셀·수식·링크·병합·표·데이터검증을 template과 대조. 27건 전부 긍정 승인, frozen 107-phone inventory, 수동 결정 notes를 통과할 때만 정규화 결정표 27행과 source/numeric correction registry 2행을 생성하며 D: 원장·shard에는 쓰지 않음 |
| apply_common_pron_researcher_decisions.py | `ready_for_apply` 정규화 결정 27행을 현재 no-path/Jamo 원장 fingerprint·frozen 107-phone과 재대조. 기본은 쓰기 0 dry-run이며 `--apply`에서만 runner와 같은 배타 lock을 잡고 두 원본뿐 아니라 clean/filled workbook, validation/template manifest, model bundle, decision/correction CSV를 SHA archive한 뒤 no-path 23행·Jamo 4행·correction 2행을 원자 승격. 중간 실패 시 두 원장을 모두 archive에서 rollback하고 shard/final/raw corpus는 수정하지 않음 |
| common_pron_no_path_review.py | 동결 Jamo G2P가 exit 0이지만 표층형을 0행으로 누락하는 FST no-path 사례를 관리. 표준 발음 재철자의 same-model 후보는 불변 증거로 보존하고, 별도 연구자 승인 phone만 누락 키에 쓴다. 후보와 다른 phone은 동일 acoustic inventory·근거·notes를 강제하며, 기존 G2P 행 불변·partial SHA 백업·승인행 snapshot·원자 교체·재검증을 유지 |
| finalize_common_pron_no_path_method.py | r2 final 직후 승인 보수 manifest·원 partial backup·승인 snapshot·최종 shard SHA를 재검증하고 G2P cache의 해당 행 `pron_source`를 same-model fallback과 manual same-inventory override로 구분한다. phone·final dictionary는 불변이며 새 production contract ID와 멱등 method supplement를 생성 |
| audit_common_pron_mfa_equivalence.py | r2와 구 2020 TextGrid·부분 DB·2021 완성 DB를 전수 비교해 차이를 결함수정·구조/coverage·기본사전·G2P 변화로 분류. mismatch 0을 채택 조건으로 쓰지 않고 완전한 difference inventory를 생성. 2020 TextGrid는 입력-prefix SHA checkpoint로 중단 뒤 안전 재개 |
| run_common_pron_difference_inventory.ps1 | 완성된 r2 hard gate, D: 라벨·공간, G2P/MFA/자체 lock과 baseline 증거를 확인하고 2020·2021 difference inventory를 전수 실행. 실행 중 Windows 시스템 절전을 억제하고 종료 시 복원한다. 기본 20,000 TextGrid마다 checkpoint를 보존하며 재실행 시 입력 prefix가 불변일 때만 이어서 처리하고 adoption은 자동 승인하지 않음 |
| run_common_pron_mfa_r1.ps1 | 구 acoustic v3.0/음절 G2P r1의 재현·실패 감사용 실행기. 첫 shard의 strict grapheme 누락을 검증기가 차단했으며 최신 Jamo 생산에는 재사용하지 않음 |
| run_common_pron_mfa_r2.ps1 | 동결 acoustic v3.3.0·Jamo G2P v3.2.0·dictionary SHA를 먼저 검증하고 r2를 shard별 생성·재개. U+11B3 정확히 4건 외 미지원·spn·누락을 차단한다. FST no-path는 모델 후보와 별도로 기록된 연구자 승인 phone(동일 acoustic inventory)을 사용해 누락 키만 보수하고, 새 미승인 누락은 partial을 보존한 채 다음 shard 계산을 계속하되 final/연도별 MFA만 금지 |
| build_common_pron_mfa_adoption.py | 연도별 MFA를 허용하는 유일한 adoption v3 contract 생성. r2 실물·동결 모델 pin·2020/2021 difference inventory뿐 아니라 연구자 workbook validation과 원장 적용 transaction, 27개 정규화 결정, no-path 24개 승인 snapshot/repair, ㄽ 4개 최종 phone, source/numeric correction 2개를 행·SHA 수준으로 끝까지 대조한다. no-path 구 repair v1/v2와 현재 review의 필드 배치 차이는 model candidate·approved phone 의미로 정규화한 뒤 비교하며, 최종 연구자 승인 v2가 application·correction SHA를 명시하지 않으면 거부 |
| build_common_pron_researcher_approval.py | 이미 명시 승인된 27건 workbook·결정 적용 transaction·6개년 전면 재정렬 결정문·완료 difference inventory를 다시 검증해 researcher approval v2를 생성. 새 언어학 판단을 자동 생성하지 않고 기존 명시 결정의 SHA 연결만 기계 판독화 |
| validate_mfa_r2_adoption.py | 연도별 실행 직전에 adoption v3가 `passed/allow_yearly_mfa=true`인지 확인하고 공통사전·acoustic·Jamo G2P·model bundle 실물 SHA를 동결 계약과 다시 대조. inline G2P가 아닌 승인 공통사전 경로만 허용 |
| build_mfa_year_phone_inventory.py | 연도별 보존 MFA DB의 실제 phone interval을 집계하고, 동결 acoustic 허용 inventory SHA와 `spn`·inventory 밖 phone을 hard gate로 기록. 코퍼스별 관측 phone 집합 차이는 기술 통계로 보존 |
| audit_mfa_cross_year_contracts.py | 2020–2025 여섯 alignment contract의 acoustic·최종 공통사전·Jamo G2P·런타임·manifest·adoption SHA와 허용 phone inventory SHA가 동일함을 전수 감사해 논문 방법론의 동일 기준 증거 생성 |
| show_common_pron_mfa_status.ps1 | 공통 MFA r2의 검증 shard·ㄽ 후보·모든 미검증 partial·no-path 승인/미등록 대기 shard·현재 출력·lock·D: 공간·final/adoption 상태를 읽기 전용으로 표시. 재개 ETA는 현재 lock 이후 새로 생성된 행만 사용 |
| package_hf_korean_mfa_bundle.py | MFA 내장 downloader의 stale 성공을 우회해 공식 Hugging Face commit에서 acoustic v3.3.0·Jamo G2P v3.2.0·dictionary를 phone inventory·LF symbol·SHA256 gate로 동결 |
| build_jamo_nfkd_g2p_model.py | 구 Jamo v3.0 archive의 누락된 NFKD metadata만 파생 수정하는 진단 도구. 최신 v3.2.0은 공식적으로 `unicode_decomposition=true`이므로 새 생산 기준에는 사용하지 않음 |
| archive_pre_jamo_outputs_to_external.ps1 | **사용 중단·기본 실행 차단.** 수백만 작은 파일의 loose Robocopy 방식이므로 실행 시 압축 스크립트를 안내하고 즉시 중단 |
| archive_pre_jamo_outputs_compressed.ps1 | 수백만 작은 파일의 loose 복사 병목을 피해 항목별 7z로 E:에 보존. CRC 전수검사, 원본/내부 파일 수·바이트, 모든 DB 전후 SHA, archive SHA를 기록하며 원본 삭제 기능 없음 |
| prune_pre_jamo_outputs_after_compressed_archive.ps1 | E: 압축 archive 성공 manifest·현재 archive SHA·D: 원본 파일 수/바이트·모든 DB SHA를 삭제 전에 전수 재검증하고, 명시적 `-Apply`+고정 승인 토큰에서만 정확한 5개 pre-Jamo allowlist를 정리. 기본은 삭제 0 dry-run |
| archive_legacy_d_workspace_20260802.ps1 | 현재 r2·원자료·CSV를 제외한 구 공통사전/파일럿/`06_textgrid_*` exact allowlist를 E: 항목별 7z로 보존. 최초 count/bytes·CRC·archive SHA 뒤 승인 token에서만 항목별 D: prune; PS5 `-PreflightOnly`, symlink `-snl`, 성공 항목 재사용 |
| show_legacy_d_archive_status.ps1 | legacy D: archive manifest의 항목별 상태·원본/압축 GiB·D:/E: 여유를 읽기 전용으로 표시 |
| `archive/pre_2021_cleanup_20260803/archive_pre_2021_active_state_20260803.ps1` | 새 2021 실행 전에 exact allowlist의 구 2021 로그·완료표시·입력계약 9개만 E: 7z로 보관. 7-Zip test·SHA 뒤 활성 사본을 정리하고 2020 완성본·원본 WAV/CSV·기존 LAB·공통사전·검색표는 보호 | 2026-08-03 실행 완료; archive SHA `fb4ccb85…bc39`, 활성 사본 0; 재실행 금지 |
| `archive/pre_2021_legacy_20260803/python/finish_migration.py` | D: 구조 이행 마무리 (archive, 재실행 금지) |
| `archive/pre_2021_legacy_20260803/python/_update_paths.py` | 구 경로 일괄 치환 (archive, 재실행 금지) |

## 검증·연계 (2026-07-14~15 추가)
| 스크립트 | 역할 | 상태 |
|---|---|---|
| coverage_inventory.py | 발화별 wav·TextGrid 전수 인벤토리 (커버리지 99.44% 확정) | 실행 완료 |
| retrofit_textgrid_2020_2024.py | 구 6-tier → 표준 3-tier 소급 재생성 (tier 통일) | 실행 완료 |
| build_multilayer_freq.py | 다층위 2025 빈도표 3종 (2025년판 규준) | 실행 완료 |
| validate_with_multilayer.py | 공식 주석 대비 채점 (형태소 F1 0.929, 의미 76.4%) | 실행 완료 |
| import_multilayer_gold.py | gold 레이어 수입 (구문·의미역·조응, 16,439발화) | 실행 완료 |
| fetch_audio_for_search.py | **검색 결과 → wav+TextGrid 복사/manifest** (A6). 2026-07-19 재작성: locate_utt 일원화, 어절 4-tier 우선(없으면 3-tier 폴백 표기), 격리·ID오류 기록 | 재검증 완료 |

## MFA 정렬 실패분 재정렬 (2020-2025, 2026-07-15)
| 스크립트 | 역할 | 상태 |
|---|---|---|
| `archive/pre_2021_legacy_20260803/python/realign_build_corpus.py` | 구 정렬 실패 발화 코퍼스 구성 | archive, 재실행 금지 |
| `archive/pre_2021_legacy_20260803/python/realign_export_quality.py` | 구 MFA 작업DB 품질통계 | archive |
| `archive/pre_2021_legacy_20260803/python/realign_merge_output.py` | 구 재정렬 결과의 3-tier 병합 | archive |
| `archive/pre_2021_legacy_20260803/python/realign_summary.py` | 구 잔여 재정렬 요약 | archive |
| `archive/pre_2021_legacy_20260803/python/realign_residual_build.py` | 구 잔여 재시도 코퍼스 | archive |
| `archive/pre_2021_legacy_20260803/python/realign_residual_finalize.py` | 구 잔여 재시도 병합 | archive |
| `archive/pre_2021_legacy_20260803/powershell/run_realign_all.ps1` | 구 6개년 잔여 정렬 실행기 | archive, 재실행 금지 |
| `archive/pre_2021_legacy_20260803/python/check_source_pcm.py` | 구 미회수 PCM 실측 | archive |
| build_mfa_missing_textgrid_inventory.py | 연도별 usable lab − 검증된 staging TextGrid 차집합을 발화 ID·세션·lab·WAV 존재 여부 CSV/JSON으로 원자 저장 | 2020 난정렬 3,644건 inventory 생성용 |

절차·명령·최종결과(25,244/26,979=93.6% 회수, 커버리지 99.94%):
`docs/decisions/RUNBOOK_MFA_realign_2020-2025.md`. 남은 미회수 1,735 중
1,296은 원본 wav 깨짐(재추출 필요), 405는 난정렬, 34는 빈 lab.

## 어절 전량 재정렬 — 목적 B: 4-tier (2026-07-16~17)
| 스크립트 | 역할 | 상태 |
|---|---|---|
| realign_eojeol_build_corpus.py | 검증된 pre-MFA search master의 `pron_reference_form`→어절 lab. 세션 coverage·build meta SHA256 입력계약, 기존 lab 내용 전수 대조, 불일치 원자 재작성, 미해결 숫자 추측 금지·발화별 부분 lab inventory. 승인된 `alignment_and_analysis` LAB는 WAV/CSV 불변 상태에서 계약별 가역 archive로 SHA 검증 이동 | 숫자 `1` 원전사 회복·stale lab 재작성·미해결 inventory·승인 LAB 중단 재개 회귀검사 통과 |
| realign_eojeol_merge_output.py | MFA출력+기존 형태소경계 → 검증된 4-tier staging. 기본 출력은 `07_textgrid_eojeol_g2p_staging`, 기존 `06` 보존. 선택적 JSON report | 합성·21,962개 실자료 회귀검사 통과 |
| export_mfa_db_4tier.py | MFA SQLite의 word/phone interval과 기존 형태소경계·동결 form을 직접 4-tier로 병렬 출력. partial 재개·coverage/accounting gate. 정렬 export 성공과 형태소 analysis-ready를 분리하고 원천 누락 전수 ID·개별 예외를 보고. `spn`은 미사용 예약 pronunciation 행이 아니라 실제 phone interval만 센다 | 21,962개 built-in 결과와 라벨·시간 전수 동일; r2 2020 파일럿 10/10·실제 spn 0 |
| compare_textgrid_tiers.py | 두 TextGrid 트리의 파일집합·tier명·라벨·모든 시간경계를 전수 비교 | 3,330개·21,962개 direct 동등성 검증 |
| audit_mfa_year_readiness.py | 연도별 CSV–WAV–lab 수량·내용·빈 입력·source PCM 위험을 원자료 비변경으로 감사. 세션 padding 제거 CSV dur↔WAV header 잔차 0.025초/98% 대응 gate, 전체 행의 극단적 전사량↔duration 물리 불일치 analysis gate, 예상 usable lab의 형태소 원천 존재, strict exit·발화 inventory 포함. post-MFA active 제외는 동일 `direct_db_ready` 계약과 DB 미정렬 exact-ID가 함께 맞을 때만 허용 | 신규 계산은 analysis profile, 동일 계약 temp/DB 재개는 execution profile. 2020 실자료 active 363=DB 미정렬 363, 미허용 0 진단 통과 |
| classify_mfa_input_issues.py | 형태소 원천 누락 inventory를 과거 PCM 근거와 동결 search CSV의 duration·한글 음절 수에 1:1 조인. PCM 결함과 물리적으로 불가능한 전사–segment 대응을 발화별 근거 CSV/요약 JSON으로 분리 | 구 2021 정렬의 역사 진단 1,109/1,109 분류 근거; 새 r2 생산 완료로 간주하지 않음 |
| inventory_mfa_storage.py | 독립 QC·다음 연도 gate 통과 뒤 MFA temp의 보존/정리 후보를 exact file manifest로 산정하는 삭제 없는 dry-run. DB transaction·미분류·symlink·계약 불일치 fail-closed, DB SHA256 선택 지원 | 구 2021 temp의 역사 계측은 E: archive에 보존; 새 2021 r2 temp에는 QC 뒤 별도 실행 |
| build_mfa_alignment_contract.py | lab 입력계약+acoustic/dictionary/G2P SHA256+MFA/Pynini/Python 판본+연구자 승인 제외 계약 SHA로 경로 독립 `alignment_contract_id` 생성 | 전 연도 direct runner 기본 경로에 배선, 모델·입력·승인 snapshot 변화 회귀시험 통과 |
| audit_mfa_4tier_year.py | 연도별 final 4-tier를 lab·WAV와 독립 전수 대조. ID coverage·중복·누락 CSV, tier·0–xmax·gap/overlap·label·WAV duration을 hard gate로 검사. 분류 CSV SHA를 고정해 source unusable만 analysis 분모에서 제외하고 raw 통계는 보존 | 구 2020/2021 4-tier 감사 근거; 현 생산 정본은 6-tier 감사이며 구 결과를 새 완료로 간주하지 않음 |
| verify_mfa_db_4tier_sample.py | 정렬 성공 발화에서 서로 다른 세션의 결정적 표본을 골라 read-only DB에서 별도 scratch 4-tier를 다시 만들고 final과 tier·라벨·시간·SHA256 대조. stale scratch 차단 | 구 2021 24/24 결과는 역사 근거; 새 2021 r2 완료 증거가 아님 |
| preflight_next_year_after_qc.py | 다음 연도 MFA 전에 직전 `direct_db_4tier` 연도의 독립 4-tier 감사·align/merge marker·direct 보고서·temp 입력계약·보존 SQLite DB·누락 CSV뿐 아니라 DB 재수출 표본과 연구자 인프라 승인 보고서를 같은 DB·input/alignment contract로 결합 검증. built-in 연도는 별도 QC 분기 | 계약 불일치·DB/direct/표본/연구자 보고서 누락·다른 DB·미승인·손상 숫자·다른 ID 분류 fail-closed 회귀시험 |
| patch_mfa_export_queue.py | MFA export queue 종료 경쟁을 blocking get+worker별 sentinel로 교정하고 설치 전 소스 archive | 3,330/21,965 실제 MFA 검증 |
| patch_mfa_skip_export.py | 환경변수를 명시한 프로젝트 direct 모드에서만 built-in raw TextGrid export를 생략 | 기본 MFA 동작 보존, 실제 skip probe 통과 |
| run_eojeol_realign.ps1 | `-Year` 한 연도 러너. pre-MFA·모델·승인제외 정렬 계약, marker·archive·PreferD, descendant CPU/working-set/private/process/thread, 시스템 available/commit, alignment-log 및 phone·word interval CSV 증분 처리량 heartbeat. `-UseDirectDbExport`는 partial 출력을 검증 승격하고 DB를 QC 전 보존 | 2020 Jamo r2 완료; 2021 첫 실행은 MFA 전 감사에서 안전 중단. 승인 계약을 LAB builder와 alignment identity 양쪽에 전달하도록 보강 |
| preflight_eojeol_realign.ps1 | 선택 연도의 SSD·공간·모델·세션구조·MFA 패치와 pre-MFA build status·필수 열·세션 coverage·temp 계약을 차단 검사. `-PreferD`이면 선택된 D:의 55/45GB 문턱을 FAIL로 검사하고 C: 용량은 정보로만 기록 | 실환경 MFA 항목 PASS; `PreferD` D: 333.3GB≥55GB 통과; 부분 pilot coverage FAIL 확인 |
| run_pre_mfa_bulk_safe.ps1 | 동결 versioned pre-MFA CSV→한 연도씩 입력계약 lab→MFA→검증 export. r2 manifest/adoption 필수, `-PreferD`, `-UseDirectDbExport`, PID lock, 연도 실패 시 중단, 자동 승격 금지, transcript/summary. 2020·2021 r2 전수 재실행은 상·하위 러너 모두 명시적 `-AllowBaselineCommonPronRerun`을 요구하고 다른 연도에서 플래그를 거부 | 2020 완료; 2021–2025는 Gate B wrapper를 통해서만 시작 |
| verify_mfa_install.py | 프로젝트 밖 MFA 3.4.0 필수 패치의 AST/소스 구조와 SHA256 기록 | 10/10 통과 |
| quarantine_bad_wavs.py | 깨진 WAV(44바이트 header-only 포함) 읽기 전용 inventory/dry-run. 수동 `--apply` 격리 기능은 보존하되 생산 러너는 원자료 이동 없이 승인 계약과 대조 | 44바이트 경계값·상대경로·transaction 회귀검사 통과 |
| copy_hdd_to_ssd.ps1 | HDD→SSD 이전 복사 (robocopy /MT, Tier1 필수분 우선, 재개·검증, MFA 모델 동봉) | 실행 대기(7/20) |
| restructure_wav_sessions.py | 평면 연도 wav/lab → 세션 하위폴더 재구성 (★1화자 사고 근본 해결, dry-run 기본, 멱등) | 합성 검증 완료 |
| locate_utt.py | 발화 ID → 전 레이어 경로·존재 조회. `mfa_state`의 세션형 quarantine 우선·평면 레거시 폴백 (현상별 검색·청취 검증용, import 가능) | 세션형·평면형 격리 회귀검사, 6개년 실검증 완료 |
| build_pilot_corpus.py | 병목 계측용 소표본 코퍼스 (2020 50세션 복사+lab, D: 유지) | 작성 완료 |
| `archive/pre_2021_legacy_20260803/powershell/run_pilot_bottleneck.ps1` | 구 병목 계측 파일럿 | archive, 현 생산에 불필요 |
| setup_mfa_speed_once.ps1 | 1회 시스템 설정 (Defender 제외·절전 해제, ★관리자★) | 실행 대기 |
| build_stratified_mfa_pilot.py | 연도별 실제 `speaker_id` 5명×2발화를 5개 세션에서 선택. 동결 `pron_reference_form` LAB과 `source_eojeol_index→mfa_word_index` 명시 대응표, 선택 세션 CSV의 파일별·aggregate SHA256을 함께 동결하고 WAV 길이 대응이 불량한 세션은 근거와 함께 제외 | r2 schema 3 파일럿 6개년 60발화 입력 구성·검증 완료 |
| finalize_stratified_mfa_pilot.py | 파일럿 MFA 원출력에 기존 형태소 경계를 결합해 4-tier 생성, WAV–TextGrid 및 CSV–WAV 길이 잔차·tier·누락·`spn` 발화별 전수 QC | v2 2020 10/10 통과 |
| run_stratified_mfa_pilot.ps1 | **연도별 10발화·실제 화자 5명 end-to-end 러너** — 입력 QC→G2P align→4-tier→요약, 단계 marker 재개·미완료 출력 보존, MFA exit 0의 부분 export 수량 차단, 정상 대응 난정렬은 기본 결과를 archive한 뒤 beam 100/400 1회 자동 재시도 | v1/v2 2023에서 9/10 차단, v2 자동 확대 beam 회수 후 6개년 60/60 완료 |
| package_mfa_r2_pilot_review.py | 모든 연도 machine marker·DB 재수출 표본과 6개년 방법 감사를 독립 재검증한 뒤 60발화의 WAV/TextGrid/LAB/행별 CSV를 `연도__utt_id` 접두사로 Dropbox 단일 평면 폴더에 원자 구성. 복사 전후 SHA, 입력 계약과 상대경로 v2 manifest를 남기며 Dropbox rename 잠금은 제한 시간 backoff 재시도. 구체적 음운 실현 판정 열은 만들지 않음 | 6개년 payload 240개 생성·검증 완료 |
| recover_mfa_r2_pilot_review_bundle.py | 복사·검증 완료 뒤 Dropbox directory rename만 잠긴 v1 partial을 payload·현재 원본·machine marker·DB 표본·6개년 감사 SHA로 전수 재검증. 목적지 절대경로를 상대경로 v2로 정규화하고 prior manifest SHA·복구 이유를 남긴 뒤에만 최종 이름으로 승격. 원본 삭제·변경 없음 | 2026-07-30 244파일 복구 성공 |
| create_mfa_r2_review_workbook.py | `REVIEW.csv`를 생성 기준 정본으로 유지하면서 사용자가 쉽게 입력하도록 파일 하이퍼링크·결정 dropdown·안내 시트를 갖춘 `REVIEW.xlsx`를 openpyxl로 생성하고 재로딩 검증. CSV/XLSX SHA를 별도 template manifest에 기록 | r2 인프라 수용 파일럿용 |
| prefill_mfa_r2_review_global_issues.py | 연구자 검토에서 확인한 반복 전역 이슈를 2–60번에만 안전 사전입력. 1번 상세 입력과 식별·파일 열을 보존하고, 기존 연구자 판정이 있으면 덮어쓰기 대신 중단하며 240링크·dropdown·검토 table을 재검증 | 2026-07-30 `G-TIER-01/G-CSV-01` 59행 반영 |
| audit_mfa_r2_pilot_review_delivery.py | 최종 Dropbox 평면 묶음 v2, payload·원본·기계 근거 SHA, REVIEW.csv/XLSX/template manifest, 60행·15열·240링크·dropdown·table을 전수 검사하고 연구자 판정 `pending`을 보존 | 최종 전달 246파일 감사 통과 |
| validate_mfa_r2_review_workbook.py | 작성된 `REVIEW.xlsx`에서 여섯 검토 열만 허용하고 원본 CSV의 발화·화자·파일 연결 열을 전수 대조. 기계 gate가 결합된 bundle manifest와 같은 연도·계약인지 확인해 normalized decision CSV와 `approved/changes_required/incomplete/invalid` 연구자 보고서를 생성 | 다음 연도 진입 gate의 연구자 증거 |
| run_mfa_r2_infrastructure_pilot.ps1 | **전수 MFA 전 6개년 r2 인프라 수용 러너** — adoption·모델·공통사전 실물 SHA 검증, 연도당 10발화·5화자·5세션, direct DB 4-tier, 독립 경계 감사, DB 재수출 동등성, 실제 `spn`·phone inventory, 6개년 방법 동일성 감사 뒤에만 Dropbox 평면 검토본·REVIEW.xlsx를 만들고 최종 전달 감사까지 실행 | 2026-07-30 연도 marker 6/6·교차 감사·전달 감사 통과 |

절차·판정 규칙: `docs/decisions/RUNBOOK_MFA_eojeol_realign.md` (가속 결정 2026-07-17 절 참조).

## 검색 마스터 레이어 — 05_search_master (2026-07-23 설계, DESIGN_search_master_layer.md)
| 스크립트 | 역할 | 상태 |
|---|---|---|
| download_gdrive_enriched_1gi.py | 1기 enriched CSV(Drive 4.96GB) → `D:\90_ARCHIVE\1기_enriched\` 백업 (gdown 이어받기, 크기 검증) | 작성 완료·실행 대기 |
| predict_pron.py | 철자열·예측 발음열 생성. form의 숫자·기호가 `∅`로 소실될 때 원전사가 실제 정보를 회복하는 경우만 출처 추적 reference 생성 | 2023 `1층으로`→원전사 `일 층으로` 회복 파일럿 통과 |
| preflight_search_master.py | 경로·헤더·실행기·용량과 형태분석/메타 17,156 세션 ID 집합 전수 검사. `category_norm/discourse_mode` 헤더도 전체 gate에 결합 | 2026-07-24 통과; 정규화 열 누락 거짓 통과 교정 |
| audit_search_master.py | 원본 JSON→Bareun A1→기존 search master의 세션·행·ID·form·tagged·메타·coverage·lexicon 배선을 읽기 전용 전수 감사. 계획 상태와 자료 무결성 gate를 분리하고 무결성 실패는 기본 exit 1 | 17,156세션·5,103,356행 전수 대조, 보완점 보고(2026-07-24); strict 실패 fixture 통과 |
| run_search_master.ps1 | 고정 Python으로 preflight 후 검색 마스터를 실행하고 실패 코드를 전달 | 검증 완료 |
| pipeline_common.py | `.partial`→검증→원자 교체, 구판 archive, run ID·fingerprint 공통 유틸 | 합성 회귀검사 통과 |
| build_search_master.py | 발화 마스터 CSV (bareun+JSON+메타+규칙기반 예측발음). 부분 출력 차단, 기존 CSV 재검증, overwrite archive, run manifest. 원전사 기반 `pron_reference_*`, 미해결 기호 집계, document별 전체·공동 참여 화자 ID 포함 | 2023 목표 세션 371/371 격리 파일럿 통과, 참여자 연결 오류 0. 기존 전량본은 구판이며 lexicon·coverage 보완 후 archive→재생성 대기 |
| measure_spn.py | TextGrid phones tier spn 비율 측정 (G2P 전후 비교) | 완료 (2020 27.5%→G2P 0%) |
| build_g2p_pilot_corpus.py | MFA G2P 파일럿 격리 코퍼스 (form→lab+wav, 화자별) | 완료 |
| stitch_session.py | 후보 주변 발화 클립 온디맨드 이어붙이기. 기본 0.05초 경계 무음, `phones_mfa/morphemes_legacy` 명시, 원 clip↔연결 시간 환산 manifest, padded review TG 입력 차단, 기존 출력 보호 | 합성 2발화·실자료 5발화 검증 |
| build_stratified_mfa_review_bundle.py | 통과한 층화 MFA run을 연도별 평면 점검 묶음으로 재구성. WAV 사본 좌우 0.05초 무음과 TextGrid 동시 이동으로 가시적 양끝 경계를 보장. 기본 v4는 `words/phones_mfa/morph_analysis/utterance_info` 4-tier이며, 마지막 tier에 발화 ID·철자·철자 로마자·규칙 발음 한글/로마자를 표지로 결합. 원본 읽기 전용, 기존 출력 자동 덮어쓰기 금지 | 6개년 60발화·4-tier·양끝 경계·검색표지 60/60 검증 |
| build_mfa_pilot_review_workbook.py | 파일럿 INDEX에서 드롭다운·상대경로 파일 링크·연도별 진행률 수식·원본 보존 시트가 있는 연구자 검토 `.xlsx` 생성. 6/7-tier 구 열과 최소 4-tier v4의 `morph_analysis_align_status/utterance_info_schema`를 모두 허용하고, 워크북이 bundle 밖에 있어도 링크 기준 경로를 계산. partial 검증 후 교체, 기존 출력 보호 | v4 60행·240링크 생성·검증 |
| build_search_parquet.py | 세션 CSV → 연도 Parquet + 전체 단일 Parquet 미러 | 미작성 (전량 CSV 후) |
| extract_actual_pron.py | 4-tier phones 라벨·시간을 검색용 보조 레이어로 추출. **사람의 실현 판정값이 아님** | 미작성(경로명 `06_actual_pron`도 오해 방지를 위해 구현 전 재검토) |

## 형태소 위치 검색·연구 TextGrid v1 (2026-07-31)

| 스크립트 | 역할 | 상태 |
|---|---|---|
| morph_schema.py | `tagged`를 `eojeol_tokens/morph_tokens/morph_units/morph_boundaries/orth_components`로 정규화하고 `tagged_roman.v2`를 결정적으로 생성. 어절 표는 `form/form_roman`의 철자·Roman·형태소 요약을 1행/어절로 보존하며, 완성형 음절·독립 자모·literal·구성 자모를 분리 | 회귀시험 통과; 60발화 전수 재생성은 외부 리뷰 후 최종 schema로 수행 |
| build_morph_position_tables.py | 동결 pre-MFA CSV에서 위 4개 검색 표와 발화별 schema index를 원자 생성. 중복 ID·구조 오류·count 불일치를 차단 | 2020–2025 파일럿 60발화, token 548·unit 809·boundary 488 생성 |
| textgrid_labels.py | `[UTT]/[ORTH_R]/[MORPH]/[MORPH_R]/[NOTE]` label의 예약문자 escape와 왕복 복원 | 회귀시험 통과 |
| research_textgrid.py | `words/phones_mfa/utterance/utterance_search` 4-tier 작성·파싱·연속 interval 검증 | 회귀시험 통과 |
| export_mfa_db_research_4tier.py | 보존 MFA SQLite의 word/phone을 바꾸지 않고 연구 4-tier로 재수출. 기존 exporter와 구 산출물은 보존 | 기존 DB 60발화 재수출·동등성 통과 |
| audit_mfa_research_schema_pilot.py | DB·구 TextGrid·새 TextGrid·검색 CSV를 독립 대조해 coverage, tier, duration, word/phone, 형태소 label을 검사 | `PILOT_AUDIT.json` status passed |
| package_mfa_research_schema_review.py | 연도별 2발화의 WAV/TextGrid/LAB/CSV와 REVIEW.xlsx를 Dropbox에 원자 구성. 네 tier 모두의 정확한 0.05초 endpoint·바깥 빈 label, SHA, 링크·dropdown을 검증하고 이전 연구자 입력을 utt_id로 승계. Dropbox rename lock 복구 지원 | 수동 검토가 잡은 느슨한 경계 gate 교정; v2 12발화·48 payload·명시 경계 12/12 |
| build_morph_combined_search_demo.py | 60발화의 morph master/tokens/units/boundaries를 실제 조합 검색해 현재 12발화 bundle 안 대표 결과로 제한하고, 검색식·전체 적중 수·구조 근거·WAV/TextGrid/CSV 링크와 검토 dropdown을 갖춘 별도 workbook/CSV/manifest 생성 | Q1–Q7 7검색·대표 13행·39링크·SHA 검증 통과 |
| phoneme_roman.py | 동결 acoustic `meta.json`의 107 phone·22 phone group을 읽고 MFA IPA를 검색용 `phone_class_r_auto`로 범주화. 복합 중성 component 전개와 결정적 DP로 철자·예측발음 참조 `phoneme_lexical_r_auto` 대응을 만들되, 삽입/탈락/대체·평격경 차이는 자동 승인하지 않음 | 단위시험과 실제 60발화 inventory hard gate 통과 |
| build_phoneme_roman_pilot.py | `phones_mfa` IPA·시간과 기존 4-tier를 변경하지 않고 interval/correspondence/발화요약 CSV와 선택적 `phoneme_r_auto` 5-tier 사본을 생성. raw 철자와 실제 MFA 입력 resolved 철자를 분리하고 12발화 workbook·Dropbox 복사 SHA를 검증 | 60발화 1,625 phone, 5-tier 60/60, 기존 4-tier 불변 60/60; 연구자 수용 대기 |
| verify_phoneme_roman_pilot.py | 완성 output의 4개 CSV 행수·phone 중복/spn·60개 5-tier·원 4-tier 전 구간·phone/phoneme 경계·D/Dropbox workbook SHA를 독립 재검증하고 rename 전 stale path를 정규화한 v2 verification 생성 | 실자료 60/60·Dropbox 12/12·최종경로 검증 통과 |
| make_phoneme_roman_workbook_portable.py | 원본 workbook을 보존하고 WAV·기존 4-tier·새 5-tier 링크를 같은 Dropbox 폴더의 파일명 상대경로로 바꾸어 원격 컴퓨터에서도 열리는 새 workbook을 생성 | 12행·36링크·36대상 재로딩 검증 통과 |

## 서울 코퍼스 참조 연구 TextGrid v2 (2026-08-01)

| 스크립트 | 역할 | 상태 |
|---|---|---|
| research_textgrid_v2.py | 기존 4-tier를 읽기 전용으로 사용해 `words/phones_mfa/phoneme_r_auto/utterance/utterance_orth_r/morph_analysis_utt` 6-tier를 생성·검증. phone-derived broad Roman만 허용하고 세 발화 수준 tier의 경계를 동기화. 연결 검토본에는 `source_utt_id/speaker`와 원시간 manifest만 추가 | 합성 2발화 및 실자료 최소 파일럿 통과 |
| build_textgrid_v2_mini_pilot.py | 익숙한 2020 단일 발화 1건과 같은 세션·화자의 2022 비인접 2발화 `review` 연결본을 새 평면 root에 생성. 기존 4/5-tier 불변, KOINA 미실행, seam 횡단 운율 해석 금지를 manifest에 기록 | 단일 6-tier·연결 8-tier 생성 성공 |
| verify_textgrid_v2_mini_pilot.py | 입력·출력 SHA, WAV–TextGrid duration, 전 tier 0–xmax 연속성, phone–phoneme 및 세 발화 tier 경계, 연결 `utt_id` 순서와 원시간 역매핑을 독립 재검증 | 실자료 status success |
| export_mfa_db_research_6tier.py | MFA SQLite를 읽기 전용으로 읽어 승인 6-tier와 연도별 `utterance/word/phone/excluded` gzip v2 동반표를 direct partial에 생성. 원 형태소 어절, reference 어절, MFA word 좌표를 분리하고 승인 제외 정확 대사·spn·phone inventory·조인·count·label·원자 승격을 gate함 | 외부 리뷰 HIGH 반영; 실 DB 60/60·결정적 gzip 24/24 통과 |
| repair_mfa_textgrid_terminal_roundoff.py | 실패한 전수 보고서의 완전한 ID 집합만 대상으로 구 float32 종단 writer와의 exact match를 입증하고, 기존 파생 TextGrid를 SHA archive한 뒤 신규 6-tier를 원자 교체·검증. DB/WAV/CSV는 읽기 전용이며 중단 시 파일별 manifest로 재개 | 2021 실제 19건 preflight READY; 적용 전 |
| finalize_mfa_db_research_6tier_repair.py | 실패 전수 checkpoint·표적 repair manifest·현재 DB/모델/계약/ID 집합을 재검증해 통과한 TextGrid 검사를 재사용하고 동반표부터 재개. 성공 뒤 독립 연도 전수 감사는 생략하지 않음 | 단위·통합검사 및 PowerShell 5.1 gate 통과; 2021 적용 전 |
| prepare_post_mfa_alignment_review.py | direct export exact-ID gate에서 발견한 active LAB 미정렬 발화를 DB·보고서 간 전수 대사하고, `mfa_feature_generation_failed`와 `mfa_alignment_missing`을 분리한다. 자동 승인 없이 immutable pending 표, 별도 승인 작업본, 대표 WAV/LAB 대조 표본을 생성하며 DB는 읽기 전용 | 2020 경로 보존; 2021–2025 generic 후보 identity/token 단위시험 고정 |
| build_simple_post_mfa_review_bundle.py | 위 16개 post-MFA 표본을 번호순 단일 폴더로 재구성. WAV·LAB·동결 search-master 1행 CSV·문맥을 붙이고, 대조군만 현행 6-tier를 직접 생성. 검토본 WAV 좌우 0.05초 무음과 모든 tier의 같은 경계를 추가하되 source time을 manifest에 보존하며, 연구자 청취 불가 ID는 정확한 `audio_unusable` 승인 부록으로 기록 | V2 16행·84파일, 13 match+3 audio_unusable, DB 크기·mtime 불변, Dropbox SHA 검증 통과 |
| audit_review_textgrid_boundaries.py | 검토 묶음의 WAV 신호량과 TextGrid 0--xmax·tier별 좌우 빈 경계를 감사하고 각 TextGrid를 Python PNG로 그려 사람과 기계가 같은 구조를 확인 | V2 4/4 TextGrid × 6/6 tier의 0.05초 좌우 경계 통과 |
| audit_mfa_db_tier_edges.py | 전수 6-tier export 전에 보존 MFA DB의 유표 word·phone 바깥 발화 경계를 읽기 전용 집계해 검토본 표시 문제와 생산 시간계약을 분리 | 2020 정렬 성공 868,187/868,187 word-phone 시작·끝 일치 |
| inspect_mfa_db_checkpoint.py | MFA 출력 schema 실패가 비싼 재정렬로 이어지지 않도록 SQLite quick-check·interval 수·coverage·spn을 읽기 전용으로 기록. 계산 재사용 가능과 분석 승인을 분리 | 합성 1시험·실 DB 6/6 success, 60/60 coverage·spn 0 |

## 사전 발음 참조 레이어 (2026-08-05)

| 스크립트 | 역할 | 상태 |
|---|---|---|
| `python/build_dictionary_pronunciation_group_summaries.py` | 1:N registry group을 후보 선택 없이 compact summary로 만들어 occurrence 반복 복제를 줄임 | 564,385 group 생성 완료 |
| `python/verify_dictionary_pronunciation_occurrences.py` | 형태소 입력과 occurrence를 독립 동시 전수 스캔하고 identity·상태·SHA·partial 검증 | 2020·2021 통과 |
| `python/build_eojeol_pronunciation_compare.py` | 원 표기 어절 좌표에서 규칙 예상형·형태소 사전 후보·MFA phone을 기술 비교; 좌표 불일치 추측 금지 | 2020 3,042,451행 완료 |
| `python/verify_eojeol_pronunciation_compare.py` | 원 표기 어절 identity와 구조화 후보·규칙/MFA 비교를 독립 재계산 | 2020 통과 |
| `python/build_pron_reference_utterance_index.py` | 어절 비교를 발화 수준 TextGrid 검색 label과 요약 CSV로 집계 | 2020 870,437행 완료 |
| `python/backfill_pron_reference_textgrid.py` | 기존 6-tier를 바꾸지 않고 7번째 `pron_reference_utt`를 세션 checkpoint 방식으로 파생 | 2020 2세션 914건 구현 파일럿 통과 |
| `python/verify_pron_reference_textgrid_backfill.py` | 앞 6개 tier 불변과 7번째 tier 순서·경계·연속성·label을 독립 전수 감사 | 파일럿 914/914 통과 |
| `run_pronunciation_reference_year.ps1` | 2020–2025 동일 계약의 occurrence→compare→index→선택적 7-tier를 `Tables/Pilot/Full`로 실행·재개 | PS5.1 safety/runtime·2020 pilot 통과 |
| mfa_exclusion_contract.py | input contract에 묶인 연구자 승인 제외 CSV/JSON을 생성·검증. 자동 승인과 목록 밖 누락을 금지하고 quarantine ID 전수 포함을 요구 | 합성 승인/변조/미승인 회귀 통과 |
| finalize_post_mfa_alignment_exclusions.py | 기존 pre-MFA 승인 계약과 보존 DB의 정확한 post-MFA 미정렬 ID를 결합한다. 16표본 결정·원 후보 SHA·DB ID 집합·명시 승인 token을 검증하고 원본을 덮어쓰지 않은 새 계약을 만든다 | 2020: 1,887 + 363(청취 불가 3 + 정렬 실패 360) = 2,250 승인, DB exact match |
| finalize_post_mfa_exact_reconciliation_exclusions.py | 2021–2025 generic post-MFA 경로. pending inventory SHA, export unknown ID, 보존 DB의 feature/정렬 실패 분류, pre-MFA 계약, 모든 행의 명시 승인과 token을 검증해 새 결합 계약을 만든다. DB 수정·자동 승인·full-year rerun 없음 | Python 관련·회귀 30시험 통과 |
| prepare_mfa_exclusion_review.py / prepare_mfa_year_exclusion_review.ps1 | 입력 감사와 불량 WAV dry-run inventory에서 `pending` 검토표를 만들고 전수 lab을 force-verify. CSV duration 0은 `audio_pairing_unresolved` 직접 후보로 보존. 현 6-tier에 쓰지 않는 구 형태소 TextGrid는 제외하고 CSV–WAV 대응 복구 전에는 fail-closed. WAV 이동·자동 승인 없음 | 2021 후속 감사의 14건 후보화 완료 |
| merge_mfa_exclusion_review_candidates.py | 이미 승인된 immutable 후보 snapshot을 덮어쓰지 않고 후속 감사의 새 ID만 합친 새 pending snapshot을 생성. 중복 reason/scope 충돌, SHA·입력계약 불일치, 자동승인을 차단 | 2021 기존 1,488 + 후속 신규 14 = pending v2 1,502 생성 |
| finalize_2020_mfa_review_from_verified_evidence.ps1 | 완료된 2020 LAB/WAV 전수 검증을 반복하지 않고 audit·복구계획·미해결 기호 inventory의 계약 ID·합계·SHA를 결합해 Gate B 전 2020 전용 큐의 최종 승인표를 생성. 1,834 음원 미대응과 빈 LAB 53을 후보로, 부분 LAB 6,158은 경고 보존으로 분리하며 기존 출력 덮어쓰기·자동승인·MFA를 금지 | 2020 최종 승인표 1회 생성용 |
| approve_mfa_exclusion_categories.py | 연구자가 명시한 범주 집합이 후보표의 실제 범주와 정확히 일치할 때만 pending 원본을 보존한 별도 승인 CSV·승인 문구/SHA 기록·input contract 결속 제외 계약을 생성. 일부 범주 누락·후보 변조·기존 출력 덮어쓰기·자동승인·MFA 시작을 차단 | 2020 두 범주 1,887건 명시 승인 기록 완료 |
| build_mfa_exclusion_category_summary.py | 여러 연도의 pending 후보 CSV·manifest·감사 SHA를 다시 검증하고 연도당 1행 범주 요약 JSON/CSV/MD를 생성. 승인·WAV/LAB 변경·MFA 시작 없음 | 현행 safe-body queue: 검색 4,232,919, 안전 본체 4,120,627, 후보 112,292 요약 생성 |
| build_failed_session_quarantine_plan.py | duration session gate 실패 세션의 겉보기 identity까지 전부 `target_unresolved`로 바꾸고, gate 통과 세션은 기존 issue 행만 유지하는 읽기 전용 본체 격리 계획. source orphan 보존·active issue 전수 포함 검증 | 2021–2025 안전 본체 4,120,627, 승인 후보 112,292 정본 생성 |
| plan_wav_duration_recovery.py | 기존 감사의 실제 audio issue ID를 정본으로 삼고, 정상 same-ID 파일을 먼저 보존한 뒤 문제 ID에만 CSV 순서와 WAV 밀리초 길이의 연속 일치로 `identity/remap/ambiguous/unresolved/orphan` 읽기 전용 계획표 생성. issue 누락·정상 발화 오제외·자동 적용 금지 | v2: 2021 issue 1,005, unresolved 1,005, remap 0, 오제외 0 |
| build_wav_recovery_review_bundle.py | 고신뢰 remap을 짧은·중간·긴 연속 일치 구간에서 결정적으로 표본화하고 A=제안 WAV/B=현재 같은 ID WAV 복사본·전사·SHA manifest·단계별 안내를 한 폴더에 생성. 원본 WAV 변경 없음 | 2020 6세션·12건·24 WAV, 복사 SHA 불일치 0 |
| build_wav_recovery_corpus.py / run_2020_wav_id_recovery.ps1 | 12/12 청취 승인과 plan SHA를 결속하고 영향 세션 원음을 E: ZIP+SHA로 먼저 검증한 뒤 D: 별도 2020 MFA 코퍼스를 구성. 원음 폴더 누락 세션은 포함 대상 0건일 때만 `verified_absent` manifest로 명시하고 ZIP을 가장하지 않음. 영향 없는 세션은 hardlink, 영향 세션은 독립 복사, 모호·미해결은 제외 검토로 분리. 세션 checkpoint·lock·stale 보존·최종 전수 count 계약으로 중단 재개 및 fail-closed 보장 | 2020 apply 완료: 870,437→868,603, 제외 검토 1,834, 128 ZIP 세션+누락 manifest 1개, 독립 WAV count 868,603/868,603 |
| mfa_wav_corpus.ps1 / show_2020_wav_id_recovery_status.ps1 | 2020은 passed 복구 계약의 파생 WAV root만 허용하고 2021–2025는 기존 연도 root를 사용. LAB 준비·MFA·독립 감사·생산 표본에서 같은 resolver를 공유하며 계약이 없거나 변조되면 원본으로 fallback하지 않음. 상태판은 진행·lock·계약을 읽기 전용 표시 | PowerShell 5.1 안전검사 통과 |
| audit_mfa_research_6tier_year.py | 연도 전체 LAB↔TextGrid 정확 ID 대사, 6-tier·0–xmax·phone inventory·동반표 SHA/count/key를 스트리밍 독립 감사 | 합성 full-year fixture 통과 |
| verify_mfa_db_research_6tier_sample.py | 보존 DB에서 세션별 결정적 표본을 새 6-tier로 재수출해 final과 의미/바이트 동등성 검사 | 합성 DB 재수출 통과; 연도 gate는 세션 ≥5 요구 |
| preflight_next_year_after_research_qc.py | 6-tier 연도 감사·marker·retained DB·표본 재수출·생산연도 연구자 검토·동반표 contract ID를 결합해 다음 연도 진입 판정 | 생산연도 review schema와 구 파일럿 schema 합성 exact gate 통과; `preflight_2020_gate_b.ps1`에 배선 |
| run_mfa_year_queue_safe.ps1 | 2020–2025를 연도별 독립 staging으로 순회. 승인 계약 없는 연도는 pending 검토표만 만들고, 실패 temp·DB를 보존하며, 성공 연도는 독립 6-tier 감사·DB 표본 재수출까지 수행. full clean retry·연구자 승인·정본 승격은 자동화하지 않음 | 장시간 실행 중 시스템 절전 방지 후 종료 시 복원; PowerShell 정적 안전검사 통과 |
| show_mfa_year_queue_status.ps1 | 연도 큐 JSON·lock·D 여유와 연도별 phase/status를 보여주는 읽기 전용 상태판 | 상태 변경 명령 없음 |
| show_active_mfa_progress.ps1 | 활성/최근 MFA heartbeat를 `FileShare.ReadWrite/Delete`로 공유 읽기하고 phase·정렬 수·오류·watchdog·자원·최신 연도 queue를 표시. 같은 run의 동결 입력감사 `expected_usable_lab`를 분모로 정확한 백분율도 계산하며 활성 JSONL에 `Get-Content`를 사용하지 않음 | heartbeat writer 잠금 비간섭; Windows PowerShell 5.1 안전·호환성 검사 대상 |
| preflight_mfa_year_queue.ps1 | 공통사전·adoption·D 라벨/용량·live lock·기존 MFA preflight·연도별 lab/승인 계약·정적 안전검사·선택적 전체 Python 테스트·Git 추적 변경을 결합해 전수 큐 시작 전 GO/NO-GO JSON 생성 | MFA·승인·정본 승격 수행 안 함 |
| prepare_full_mfa_approval_reviews.ps1 | 지정 연도의 lab 입력을 전수 검증하고 제외 후보 CSV/manifest만 준비하는 내부 공통 진입점. 기존 검토표·승인 계약을 덮어쓰지 않으며 MFA·WAV 이동·자동 승인 없음 | 직접 기본값 사용 금지; 아래 연도 범위 wrapper가 호출 |
| start_full_mfa_after_review.ps1 | 지정 연도의 승인 CSV를 input contract 결합 승인 JSON으로 만들고 전체 테스트 포함 preflight가 정확히 `GO`일 때만 체크포인트형 연도 큐 시작 | 내부 공통 진입점; 직접 기본값 사용 금지, full clean/자동승인/정본승격 없음 |
| resume_2020_export_after_post_mfa_review.ps1 | 2020 결합 2,250건 계약과 보존 DB에서 6-tier·동반표 export를 재개한 이력 wrapper | 2020 완료 근거로 보존; 정상 절차 재실행 금지 |
| prepare_post_mfa_exact_reconciliation_review.ps1 / resume_year_export_after_post_mfa_review.ps1 | 2021–2025 queue가 exact-ID gate에서 멈춘 경우 같은 정렬 계약의 최신 실패 보고서·보존 DB·선행 승인을 묶어 연구자 검토표를 만들고, 명시 승인 뒤 새 queue에서 재정렬 없이 direct export를 재개. 정렬 당시 pre-MFA 계약과 post-MFA 결합 export/QC 계약을 별도 인자로 전달해 `alignment_contract_id`를 소급 변경하지 않음 | Windows PowerShell 5.1 안전 46파일·호환성 55스크립트, Python 340시험 통과; 실제 후보 자동 승인 없음 |
| `python/materialize_post_mfa_exact_approval.py` | 연구자가 채팅에서 승인한 동결 exact-ID 집합을 수백 행 수동 편집 없이 승인 작업본으로 materialize. 원 pending 작업본을 byte-exact archive하고 연도·행 수·scope·candidate SHA·token·승인 문장을 검증한 뒤 `decision`만 변경 | WAV/LAB/DB/TextGrid 무변경, immutable `02_RESEARCHER_DECISIONS.csv` 보존, 자동 승인 0 |
| verify_production_source_contract.ps1 | morph_search와 MFA가 같은 동결 `_build_meta.json` SHA·run ID·연도 입력을 사용했음을 `SOURCE_CONTRACT.json`으로 생성/검증 | 원자료 읽기 전용, 2020 검색·MFA·Gate B wrapper에 강제 |
| resume_2020_morph_search.ps1 | 2020 source contract를 고정하고 성공 shard를 검증 재사용해 shard 2–23만 재개 | 2020 검색표 23/23 완료 |
| prepare_2020_mfa_approval_review.ps1 / start_2020_mfa_after_review.ps1 | 검색표 성공과 source SHA를 확인한 뒤 2020 제외표만 준비하거나 2020 한 연도만 정렬 시작 | 기본 6개년 오실행 차단 |
| mfa_production_year_review.py / prepare_2020_production_sample_review.ps1 / approve_2020_production_sample_review.ps1 | 기계 QC 표본의 WAV/LAB/6-tier 연결·가용성과 수정 불가 identity 승인 JSON 생성 | 2020 24/24 승인 완료; 실제 실현 판정 미수행; 재실행 금지 |
| preflight_2020_gate_b.ps1 | 2020 source·audit·marker·DB·표본·연구자 승인을 결합한 fail-closed gate. 최종 queue `mfa_r2_prod_2020_export_20260803`만 허용하고 구 ID는 canonical 보고서 쓰기 전에 차단 | 2026-08-03 재검증 16/16 통과, 실패 0; stale-ID 무변경 거부 시험 통과 |
| prepare_remaining_mfa_approval_reviews.ps1 / approve_remaining_mfa_exclusion_categories.ps1 / start_remaining_mfa_after_2020_gate.ps1 | Gate B 통과 뒤 2021–2025 제외표를 준비하고, 연구자가 명시 승인한 세 범주를 원본 후보표와 분리된 5개년 계약으로 기록한 뒤, 시작 wrapper는 직전 연도 연구자 gate를 건너뛰지 않도록 현재 2021 한 연도만 허용 | **현재 생산 진입점**; 승인 wrapper는 MFA를 시작하지 않으며 2020 재포함·2022–2025 선행 실행 금지 |
| prepare_production_year_sample_review.ps1 / approve_production_year_sample_review.ps1 | 2021–2025의 단독 연도 queue가 기계 QC를 통과했을 때 DB 표본의 WAV·LAB·6-tier 연결 검토표와 연구자 승인 기록 생성 | 최소 5세션, identity/path·원 pending SHA 불변, 승인 문장·정확 행 수 필수, 재실행 무변경, 자동승인·실현판정 금지 |
| preflight_production_next_year_gate.ps1 / start_next_mfa_year_after_gate.ps1 | 2021→2022부터 2024→2025까지 직전 연도 source·audit·marker·retained DB·DB 표본·연구자 승인을 결합 검증하고 다음 한 연도만 시작 | 표준 6-tier와 checkpoint-resume mode 동등성·`direct_db_ready` 계약 확인; 연도별 독립 queue, gate 우회와 다연도 시작 차단 |
| research_companion_schema.py / research_companion_tables_schema_v2.json | gzip CSV와 Parquet의 열 순서·dtype·nullable·부울·null·BOM·압축 계약을 단일 schema로 동결 | exporter 전 필드 대조 시험 통과 |
| build_research_companion_parquet.py / verify_research_companion_parquet.py | 감사 정본 gzip 4표에서 disposable typed Parquet 검색 미러를 만들고 소규모 QC에서 값·dtype·행 순서를 왕복 검증 | 6개년 60발화 24표 왕복 통과(PyArrow는 별도 분석 환경) |
| benchmark_research_6tier_exporter.py | MFA 없이 합성 SQLite/search CSV로 6-tier 최초 출력·재개 시간과 Python 메모리·partial을 측정 | 10,000발화 최초 87.7초, 재개 38.4초, peak 9.2MiB |
| collect_research_6tier_regression_evidence.py | 로컬 60발화·재출력·Parquet·10k 벤치 결과를 작은 추적 JSON으로 집계 | `outputs/reports/EVIDENCE_research_6tier_post_review_20260801.json` success |

## 2021 checkpoint 국소 복구·QC (2026-08-05)

| 스크립트 | 역할 | 상태 |
|---|---|---|
| repair_mfa_textgrid_phone_only_silence_words.py | 동반표 실패에서 정확히 `LAB N : MFA N+1`인 발화를 선별하고, 추가 word interval에 연결된 phone이 전부 무음임을 DB에서 입증한다. 기존 파생 TextGrid를 SHA archive한 뒤 words 중복 표지만 비우고 검색 tier의 유표 span을 실제 lexical 끝에 맞춘다. phone·시간·텍스트·DB·WAV·LAB·CSV는 불변 | 2021 실자료 preflight 19/19, 적용 19/19 success |
| resume_mfa_year_checkpoint_qc.ps1 | 성공한 direct export를 MFA/LAB/전수 생성 반복 없이 연도 staging으로 승격하고 독립 전수 감사·DB 표본 24건 재수출까지 연결. 정본 채택과 연구자 승인은 자동 수행하지 않음 | Windows PowerShell 5.1 안전·호환 검사 통과; 2021 성공 export 대기 |

## 예정 (미작성)
- inject_tiers.py — morphs/sense/original_form tier 온디맨드 주입
- KOINA 운율 파일럿 노트북 (Colab) — 표본은 06_multilayer_gold에서 추출 권장
- `python/stage_mfa_production_review_bundle.py`: 기계 QC를 통과한 생산 연도의 권위 검토 CSV를 그대로 보존하면서 번호가 붙은 WAV/LAB/6-tier TextGrid를 한 평면 검토 폴더로 복사하고 SHA manifest를 남긴다.

## 2020–2025 대화 음원 품질 감사

| 스크립트 | 역할 |
|---|---|
| `python/audit_dialogue_audio_structure.py` | 원 JSON의 겹침 note·시간구간 중첩·경계 맞닿음·불가능 시간정보를 연도 전수 감사. 원자료 수정·자동 승인 없음 |
| `python/audit_dialogue_audio_sample.py` | 세션 층화 WAV의 헤더·에너지·edge·noise proxy를 측정해 검토 우선순위를 생성. SNR/소음 확정·denoise·자동 제외 없음 |
| `python/profile_dialogue_audio_focus.py` | exact `utt_id` 목록에 구조 근거·직접 WAV edge·세션 noise proxy를 결합해 pending 연구자 검토표 생성 |
| `python/summarize_dialogue_audio_quality.py` | 6개 연도 manifest와 세션 감사표를 결합한 공통 요약 CSV/JSON 생성 |
