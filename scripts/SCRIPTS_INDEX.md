# 스크립트 색인 (scripts/python) — 2026-07-14

파이프라인 순서대로. 모든 경로 상수는 새 D: 구조 기준 (config/paths.json 참조).

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
| make_labs_2025.py | MFA용 .lab 생성 (바른 형태소 분할, S태그 제외) | 실행 완료 |
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
| fetch_audio_for_search.py | **검색 결과 → wav+TextGrid 복사/manifest** (A6) | 완료 |

## 예정 (미작성)
- inject_tiers.py — morphs/sense/original_form tier 온디맨드 주입
- KOINA 운율 파일럿 노트북 (Colab) — 표본은 06_multilayer_gold에서 추출 권장
