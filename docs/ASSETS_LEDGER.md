# 자산 대장 (ASSETS LEDGER) — 실측 기반 정본

**규칙**: 이 문서가 "무엇이 어디에 있는가"의 유일한 정본이다.
- 모든 상태는 **실측 근거**(스크립트 보고서·직접 확인)와 날짜를 달아야 한다.
- 이전·삭제·대량 변경 후에는 preflight/인벤토리를 재실행하고 이 문서를 갱신한다.
- "미실측"은 실측 전까지 지우지 않는다. 기억·추정으로 상태를 쓰지 않는다.

최종 실측: **2026-07-24** (reference 4종 회수분 — `logs/recover_reference_20260724_150205.log`;
나머지는 2026-07-23 `logs/preflight_report.txt` 기준)

## 거점 1 — 외장 SSD (D:, 정본 데이터)

| 자산 | 상태 | 근거 |
|---|---|---|
| `00_RAW\dialogue_json` (전사 JSON 원본) | ✅ 있음, 발화 필드(original_form·start·end·note) 확인 | preflight 7/23 |
| `00_RAW\dialogue_audio` (PCM 원본) | ⚠ 미실측 (7/20 이전 시 제외 가능성 — HDD엔 있음) | — |
| `00_RAW\reference\03_lexicon_1기\01_NIKL_lexicon_full.csv` (어휘목록 **v1**, 발음 컬럼) | ✅ 있음 (Dropbox에서 7/23 복사) | preflight 7/23 |
| `00_RAW\reference\00_DICTIONARY` (어휘목록 **v2** 등) | ✅ 있음 (HDD H:에서 7/24 회수) | recover_reference 7/24 + preflight [OK] |
| `00_RAW\reference\01_NIKL_MP_v_1_1` | ✅ 있음 (HDD H:에서 7/24 회수) | recover_reference 7/24 + preflight [OK] |
| `00_RAW\reference\02_NIKL_LS` | ✅ 있음 (HDD H:에서 7/24 회수) | recover_reference 7/24 + preflight [OK] |
| `00_RAW\reference\NIKL_Multi-layered_2025_v1.0` | ✅ 있음 (HDD H:에서 7/24 회수) | recover_reference 7/24 + preflight [OK] |
| `10_LAYERS\01_bareun_raw` (형태소, 6개년) | ✅ 연도폴더 6개·2020 세션 2,232·컬럼 확인 | preflight 7/23 |
| `10_LAYERS\02_sense_annotated` | ⚠ 미실측 | — |
| `10_LAYERS\03_freq_dictionaries` (빈도사전 5종) | ✅ IPA표 확인 / 사전 본체 CSV는 미실측 | preflight 7/23(부분) |
| `10_LAYERS\04_metadata_index` (file_meta·speakers_normalized) | ✅ 컬럼까지 확인 | preflight 7/23 |
| `10_LAYERS\06_multilayer_gold` | ⚠ 미실측 | — |
| `10_LAYERS\05_search_master` | ✅ 2026-07-23 전량 17,156세션·5,103,356행. 단, 7/24 메타 수정 전이며 lexicon 예외 발음·coverage 미반영 | `_build_meta.json` + build log 7/23; 7/24 감사 중 |
| `10_LAYERS\06_actual_pron` | 없음. 명칭이 최종 실현 판정으로 오해될 수 있어 구현 전 재검토 | 7/24 사용자 방법론 확인 |
| `20_AUDIO\03_wav` (wav+lab, 세션 구조) | ✅ 있음 (내용 전수는 인벤토리 99.44% 기준) | preflight 7/23 |
| `20_AUDIO\06_textgrid_merged` (3-tier, 읽기전용) | ✅ 있음 | preflight 7/23 |
| `20_AUDIO\06_textgrid_eojeol` (4-tier) | ✅ 폴더 있음 — 2020·2021 비G2P 산출물 존재, G2P 전량 완료 연도는 없음 | 7/22–24 기록 대조; 전수 재실측 예정 |
| `20_AUDIO\07_textgrid_eojeol_g2p_staging` | 신규 G2P 4-tier 연도별 검증용 staging — 아직 본실행 산출물 없음 | 7/24 안전 설계; 기존 `06` 자동 보존 |
| `90_ARCHIVE` | ❌ SSD엔 없음 (HDD 보존 방침) | preflight 7/23 |
| `mfa_eojeol` (마커·로그·격리) | ⚠ 미실측 (7/20 복사 대상 Tier1이었음) | — |

## 거점 2 — 구 외장 HDD (7/20 이전 전의 전체 상)

**★유일본 경고**: 아래 항목은 현재 **HDD에만** 존재한다. HDD 유실 = 영구 손실.

| 자산 | 성격 | 회수 |
|---|---|---|
| `00_RAW\reference` 4종 (00_DICTIONARY·MP·LS·다층위) | ~~유일본~~ → D: 사본 확보로 이중화 | ✅ 2026-07-24 회수 완료 (`recover_reference_from_hdd.ps1`, HDD 원본 보존) |
| `90_ARCHIVE` (구판 6-tier TextGrid, 폐기물 보존 등) | 유일본 (재생성 곤란 항목 포함) | 선별 회수 판단 |
| 그 외 전체 | 7/20 시점 사본 (SSD와 중복) | 역방향 백업으로 유지 |

회수 명령 (HDD가 E:로 잡힌 경우, D: 배치 없는 시간에):
```powershell
robocopy "E:\00_RAW\reference\00_DICTIONARY" "D:\00_RAW\reference\00_DICTIONARY" /E
robocopy "E:\00_RAW\reference\01_NIKL_MP_v_1_1" "D:\00_RAW\reference\01_NIKL_MP_v_1_1" /E
robocopy "E:\00_RAW\reference\02_NIKL_LS" "D:\00_RAW\reference\02_NIKL_LS" /E
robocopy "E:\00_RAW\reference\NIKL_Multi-layered_2025_v1.0" "D:\00_RAW\reference\NIKL_Multi-layered_2025_v1.0" /E
```
완료 후: `python scripts\python\preflight_search_master.py` 재실행 → 이 문서 갱신.

## 거점 3 — Google Drive (G:, 이 기기에 연결 확인 2026-07-23)

| 자산 | 상태 |
|---|---|
| `DATA_2026\00_raw_data\04_nikl_dialogue\02_csv\01_nikl_dialogue_enriched.csv` (1기 발화단위 발음 CSV, 4.96GB) | ✅ 있음 (+`NIKL_dialogue\`에 동일 크기 중복 1부, 표본 3k 2부) |
| `DATA_2026\prosody_pilot` 등 1기 Colab 산출 | ⚠ 미실측 |

1기 CSV → SSD 백업 (G: 연결 확인됐으므로 **이 한 줄이 최선**, gdown 불필요):
```powershell
robocopy "G:\내 드라이브\DATA_2026\00_raw_data\04_nikl_dialogue\02_csv" "D:\90_ARCHIVE\1기_enriched" 01_nikl_dialogue_enriched.csv /J
```
(완료 확인: 크기 4,957,188,915 bytes. `download_gdrive_enriched_1gi.py`는 G: 미연결 기기용 예비로 유지)

## 거점 4 — Dropbox (`C:\Users\ari30\Dropbox\000_NIKL_2026`)

| 자산 | 상태 |
|---|---|
| `00_01_1차_archive\02_DICTIONARY\01_NIKL_lexicon_full.csv` (v1, 130만 행·발음 100%) | ✅ 실측 7/23 → D:로 복사 완료 |
| 1차 archive 나머지 (R 프로젝트·스크립트 등) | ⚠ 미실측 (원천 보존용) |

## 거점 5 — 리포 (`C:\Users\ari30\research\2026_summer_research` + GitHub private)

코드·문서·설정 정본. GitHub `ari28526-lab/nikl-dialogue-research` (푸시가 밀리면
GitHub·claude.ai 프로젝트 지식은 구버전 — **커밋·푸시 후 최신**).

---
*이 대장의 갱신 없이 "이전 완료" 같은 상태 선언을 하지 않는다 (CLAUDE.md 규칙 9).*

---

## reference 4종 — 활용처와 D: 확보 계획 (★잊지 말 것, 2026-07-23)

**현재(2026-07-24 갱신)**: ✅ **4종 모두 D: 회수 완료** — preflight 4종 [OK] 실측
(`recover_reference_from_hdd.ps1`, HDD 원본 보존·역백업 유지). `config/paths.json`의
키(`reference_dictionary/mp/ls/multilayer`)는 이미 **D:\00_RAW\reference\ 하위**를
가리키므로, HDD에서 그 위치로 회수하면 **스크립트 무수정**으로 바로 쓰인다.

| reference | 실제 파일(핵심) | 무엇에 쓰이나 | 쓰는 스크립트 |
|---|---|---|---|
| `00_DICTIONARY` (어휘목록 **v2**) | `01_NIKL_lexicon_full_v2.csv` (word_roman_mfa) | 빈도사전의 로마자 폴백·어원(etym)·의미(sense) 조회 | build_freq_dictionaries.py, assign/supplement_sense_layer.py |
| `01_NIKL_MP_v_1_1` (형태분석 말뭉치) | `05_ALL_word_freq.csv`·`06_ALL_morpheme_freq.csv` | 비교빈도 **freq_MP**(구어/문어) + 로마자 1순위 | build_freq_dictionaries.py |
| `02_NIKL_LS` (어휘의미 말뭉치) | `07_ALL_word_freq.csv`·`08_ALL_morpheme_freq.csv` | 비교빈도 **freq_LS**(SXLS/전체) + **sense_id 결정** + 로마자 | build_freq_dictionaries.py, decide_sense |
| `NIKL_Multi-layered_2025_v1.0` | `freq\ML2025_morpheme_freq.csv` | 2025 규준 비교빈도 **freq_ML2025** | build_freq_dictionaries.py, build_multilayer_freq.py, import_multilayer_gold.py |

**언제 필요**: A3 빈도사전 재생성·A단계 검증·검색 마스터의 lexicon 발음 예외층 확장 시.
**언제 불필요**(회수 전에도 진행 가능): 검색 마스터 v1(예측 발음열)·MFA G2P 재정렬은
이 4종과 무관 — v1은 이미 D:에 있는 lexicon **v1**(`03_lexicon_1기`)만 쓴다.

**D: 확보 절차(HDD 연결 시, 위 '거점 2'의 robocopy 4줄)**:
1. HDD 연결(문자 예: E:). D: 배치 안 도는 시간.
2. robocopy E:\00_RAW\reference\{4종} → D:\00_RAW\reference\{4종} /E  (거점 2 참조)
3. `python scripts\python\preflight_search_master.py` 재실행 → reference [OK] 확인.
4. 이 문서 표(거점 1) ✅로 갱신. **HDD 원본은 삭제하지 말 것**(역백업 유지, 유일본 보호).
- 안전: 회수 후에도 D: 라벨은 DATA_SSD 유지(러너·파이프라인이 HDD 오인 방지에 씀).

## 2026-08-01 생산 source contract

2020 `morph_search.v3`와 신규 r2 MFA가 같은 동결 search master를 사용한다는
근거를 다음 실물로 고정했다. `D:\00_RAW`와 동결 search master는 수정하지 않았다.

```text
D:\10_LAYERS\09_morph_search_v3_staging\morph_search_v3_20260801\2020\SOURCE_CONTRACT.json
```

- source `_build_meta.json` SHA256:
  `1649d60a302de44a772460ba9f64d3cfb9307a56d53f1fa578bcd0494264ea79`
- contract schema: `production_frozen_source_contract.v1`
- 검증 보고서:
  `outputs/reports/SOURCE_CONTRACT_morph_search_v3_20260801_2020.json`
- 상태: `passed`

## 2026-08-02 2020 MFA 제외 최종 회계

- 활성 검토 root:
  `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_20260801/2020`
- 추적 집계:
  `outputs/reports/EVIDENCE_2020_mfa_exclusion_final_20260802.json`
- 후보: `audio_pairing_unresolved` 1,834 +
  `empty_reference_unresolved_symbol` 53 = 1,887
- 제외하지 않고 경고 보존: 부분 LAB `unresolved_symbol` 6,158
- 구 1,834건 표:
  `outputs/reviews/archive/mfa_exclusions_queue_mfa_r2_prod_2020_20260801_pre_symbol_accounting_20260802`
- 승인 기록:
  `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_20260801/2020/04_RESEARCHER_APPROVAL.json`
- 승인 계약:
  `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_20260801/2020/approved_exclusions.json`
- 상태: 연구자 두 범주 승인 완료, MFA 미시작
