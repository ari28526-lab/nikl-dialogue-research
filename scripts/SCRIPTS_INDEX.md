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
| build_metadata_index.py | 파일 메타데이터 인덱스 (사용역·주제·화자) | 실행 완료 |
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
| realign_eojeol_build_corpus.py | form→어절 lab을 wav 폴더에 제자리 생성 (세션당 scandir 1회 최적화) | 검증 완료 |
| realign_eojeol_merge_output.py | MFA출력+기존 형태소경계 → 4-tier → 06_textgrid_eojeol | 2026-07-21: `_speakers.csv`(화자 메타, form 없음) 오인 KeyError 수정 — glob에 `_`제외 필터 추가(6개년 전부 해당 파일 존재, 안 고쳤으면 전 연도 실패) |
| run_eojeol_realign.ps1 | 연도별 일괄 러너 (lab→align→merge, .done 재개, **temp=C:\mfa_tmp**+공간 가드, MFA stderr 파일 캡처+1분 하트비트) | 실행 중 |
| quarantine_bad_wavs.py | 깨진 wav(0바이트 등) 격리 — MFA 로딩 전체 실패 방지. dry-run 기본, --apply 이동(짝 lab 동반, CSV 기록) | 검증 완료 |
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
| build_search_master.py | 발화 마스터 CSV (bareun+JSON+메타+예측발음, 세션별, 검증 내장, 체크포인트) | 파일럿 2020 3세션 통과 — 전량 대기 |
| measure_spn.py | TextGrid phones tier spn 비율 측정 (G2P 전후 비교) | 완료 (2020 27.5%→G2P 0%) |
| build_g2p_pilot_corpus.py | MFA G2P 파일럿 격리 코퍼스 (form→lab+wav, 화자별) | 완료 |
| stitch_session.py | 발화 클립 이어붙이기 → 연속 wav+정렬 TextGrid (원본 연속본 부재 대비) | 검증 완료 |
| build_search_parquet.py | 세션 CSV → 연도 Parquet + 전체 단일 Parquet 미러 | 미작성 (전량 CSV 후) |
| extract_actual_pron.py | 4-tier phones → v2 실발음 레이어 (G2P 재정렬 후) | 미작성 |

## 예정 (미작성)
- inject_tiers.py — morphs/sense/original_form tier 온디맨드 주입
- KOINA 운율 파일럿 노트북 (Colab) — 표본은 06_multilayer_gold에서 추출 권장
