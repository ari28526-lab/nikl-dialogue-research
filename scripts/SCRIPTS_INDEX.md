# 스크립트 색인 (scripts/python) — 2026-07-14

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
| make_labs_2025.py | MFA용 .lab 생성 (바른 형태소 분할, S태그 제외) | ⚠구식 — 형태소 lab 방식 폐기(어절 재정렬로 대체), 재실행 금지 |
| merge_textgrid_v2.py | **표준 3-tier TextGrid 생성** — MFA 정렬 DB에서 직접 내보내기 (MFA export 교착 우회) | 실행 완료 |

## 인프라
| 스크립트 | 역할 |
|---|---|
| paths.py | config/paths.json 로더 (`from paths import P`) |
| finish_migration.py | D: 구조 이행 마무리 (1회용, 보존) |
| _update_paths.py | 이행 시 경로 일괄 치환 (1회용, 보존) |

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
| realign_build_corpus.py | 정렬 실패 발화만 코퍼스 구성 (lab 재생성 + wav 하드링크) | ⚠구식 — 어절 전량 재정렬로 대체(잔여분 회수 불필요), 재실행 금지 |
| realign_export_quality.py | MFA 작업DB → 품질통계 CSV (사후 필터용, merge 전 실행) | 파일럿 검증 |
| realign_merge_output.py | 재정렬 원출력 → 표준 3-tier → 06_textgrid_merged (기존 보존) | 검증 |
| realign_summary.py | 연도별 원래실패/회수/미회수 요약표 | 실행 완료 |
| realign_residual_build.py | 1차 후 잔여(정상wav 미회수)만 재시도 코퍼스 구성 | 실행 완료 |
| realign_residual_finalize.py | 잔여 재시도(빔 300/1000) 산출 병합+품질 append | 실행 완료 |
| run_realign_all.ps1 | 6개년 일괄 실행기(align→품질→병합→요약), 한 줄 실행 | 실행 완료 |
| check_source_pcm.py | 미회수 발화의 원본 PCM 실측 → 재추출 가능/불가 확정 | 실행 완료 |

절차·명령·최종결과(25,244/26,979=93.6% 회수, 커버리지 99.94%):
`docs/decisions/RUNBOOK_MFA_realign_2020-2025.md`. 남은 미회수 1,735 중
1,296은 원본 wav 깨짐(재추출 필요), 405는 난정렬, 34는 빈 lab.

## 어절 전량 재정렬 — 목적 B: 4-tier (2026-07-16~17)
| 스크립트 | 역할 | 상태 |
|---|---|---|
| realign_eojeol_build_corpus.py | form→어절 lab을 wav 폴더에 제자리 생성 (세션당 scandir 1회 최적화, lab 원자 기록·구조화 marker) | 합성 회귀검사 통과, 본실행 대기 |
| realign_eojeol_merge_output.py | MFA출력+기존 형태소경계 → 검증된 4-tier staging. 기본 출력은 `07_textgrid_eojeol_g2p_staging`, 기존 `06` 보존 | 합성 TextGrid 회귀검사 통과, 본실행 대기 |
| run_eojeol_realign.ps1 | `-Year` 한 연도 러너 (preflight→lab→align→검증→staging merge, JSON marker 재개, 실패 temp 보존) | 2020 선택 preflight 통과, 대량 실행 대기 |
| preflight_eojeol_realign.ps1 | 선택 연도의 SSD·공간·모델·세션구조·marker·MFA 설치 패치 7종을 차단 검사 | `-Year 2020` FAIL 0/WARN 0 |
| verify_mfa_install.py | 프로젝트 밖 MFA 3.4.0 수동 패치의 AST/소스 구조와 SHA256 기록 | 7/7 통과 |
| quarantine_bad_wavs.py | 깨진 wav(0바이트 등) 격리 — 상대경로 보존, planned/complete transaction JSON, dry-run 기본 | 합성 회귀검사 통과 |
| copy_hdd_to_ssd.ps1 | HDD→SSD 이전 복사 (robocopy /MT, Tier1 필수분 우선, 재개·검증, MFA 모델 동봉) | 실행 대기(7/20) |
| restructure_wav_sessions.py | 평면 연도 wav/lab → 세션 하위폴더 재구성 (★1화자 사고 근본 해결, dry-run 기본, 멱등) | 합성 검증 완료 |
| locate_utt.py | 발화 ID → 전 레이어 경로·존재 조회 (현상별 검색·청취 검증용, import 가능) | 6개년 실검증 완료 |
| build_pilot_corpus.py | 병목 계측용 소표본 코퍼스 (2020 50세션 복사+lab, D: 유지) | 작성 완료 |
| run_pilot_bottleneck.ps1 | **병목 계측 파일럿** — CPU%·디스크 샘플러 + 소표본 MFA, 발화/s·ETA 실측 | 실행 대기 |
| setup_mfa_speed_once.ps1 | 1회 시스템 설정 (Defender 제외·절전 해제, ★관리자★) | 실행 대기 |

절차·판정 규칙: `docs/decisions/RUNBOOK_MFA_eojeol_realign.md` (가속 결정 2026-07-17 절 참조).

## 검색 마스터 레이어 — 05_search_master (2026-07-23 설계, DESIGN_search_master_layer.md)
| 스크립트 | 역할 | 상태 |
|---|---|---|
| download_gdrive_enriched_1gi.py | 1기 enriched CSV(Drive 4.96GB) → `D:\90_ARCHIVE\1기_enriched\` 백업 (gdown 이어받기, 크기 검증) | 작성 완료·실행 대기 |
| predict_pron.py | 철자열·예측 발음열 생성 (필수 규칙 G2P; 용언경음화 on·ㄹ비음화 off; roman_mfa·IPA·tagged_roman) | 파일럿 검증·테스트 30/30 (2026-07-23) |
| preflight_search_master.py | 경로·헤더·실행기·용량과 형태분석/메타 17,156 세션 ID 집합 전수 검사 | 2026-07-24 통과 |
| audit_search_master.py | 원본 JSON→Bareun A1→기존 search master의 세션·행·ID·form·tagged·메타·coverage·lexicon 배선을 읽기 전용 전수 감사 | 17,156세션·5,103,356행 전수 통과, 보완점 보고(2026-07-24) |
| run_search_master.ps1 | 고정 Python으로 preflight 후 검색 마스터를 실행하고 실패 코드를 전달 | 검증 완료 |
| pipeline_common.py | `.partial`→검증→원자 교체, 구판 archive, run ID·fingerprint 공통 유틸 | 합성 회귀검사 통과 |
| build_search_master.py | 발화 마스터 CSV (bareun+JSON+메타+규칙기반 예측발음). 부분 출력 차단, 기존 CSV 재검증, overwrite archive, run manifest | 2026-07-23 전량 5,103,356행 생성. 단, 7/24 메타 수정 전 산출물이며 lexicon 예외 발음·coverage 미반영 — 감사·선별 재생성 대기 |
| measure_spn.py | TextGrid phones tier spn 비율 측정 (G2P 전후 비교) | 완료 (2020 27.5%→G2P 0%) |
| build_g2p_pilot_corpus.py | MFA G2P 파일럿 격리 코퍼스 (form→lab+wav, 화자별) | 완료 |
| stitch_session.py | 발화 클립 이어붙이기 → 연속 wav+정렬 TextGrid (원본 연속본 부재 대비) | 검증 완료 |
| build_search_parquet.py | 세션 CSV → 연도 Parquet + 전체 단일 Parquet 미러 | 미작성 (전량 CSV 후) |
| extract_actual_pron.py | 4-tier phones 라벨·시간을 검색용 보조 레이어로 추출. **사람의 실현 판정값이 아님** | 미작성(경로명 `06_actual_pron`도 오해 방지를 위해 구현 전 재검토) |

## 예정 (미작성)
- inject_tiers.py — morphs/sense/original_form tier 온디맨드 주입
- KOINA 운율 파일럿 노트북 (Colab) — 표본은 06_multilayer_gold에서 추출 권장
