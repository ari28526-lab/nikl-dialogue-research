# 자산 대장 (ASSETS LEDGER) — 실측 기반 정본

**규칙**: 이 문서가 "무엇이 어디에 있는가"의 유일한 정본이다.
- 모든 상태는 **실측 근거**(스크립트 보고서·직접 확인)와 날짜를 달아야 한다.
- 이전·삭제·대량 변경 후에는 preflight/인벤토리를 재실행하고 이 문서를 갱신한다.
- "미실측"은 실측 전까지 지우지 않는다. 기억·추정으로 상태를 쓰지 않는다.

최종 실측: **2026-07-23** (`logs/preflight_report.txt` + 이 날 세션의 직접 확인)

## 거점 1 — 외장 SSD (D:, 정본 데이터)

| 자산 | 상태 | 근거 |
|---|---|---|
| `00_RAW\dialogue_json` (전사 JSON 원본) | ✅ 있음, 발화 필드(original_form·start·end·note) 확인 | preflight 7/23 |
| `00_RAW\dialogue_audio` (PCM 원본) | ⚠ 미실측 (7/20 이전 시 제외 가능성 — HDD엔 있음) | — |
| `00_RAW\reference\03_lexicon_1기\01_NIKL_lexicon_full.csv` (어휘목록 **v1**, 발음 컬럼) | ✅ 있음 (Dropbox에서 7/23 복사) | preflight 7/23 |
| `00_RAW\reference\00_DICTIONARY` (어휘목록 **v2** 등) | ❌ **없음 — HDD 유일본** | preflight 7/23 |
| `00_RAW\reference\01_NIKL_MP_v_1_1` | ❌ **없음 — HDD 유일본** | preflight 7/23 |
| `00_RAW\reference\02_NIKL_LS` | ❌ **없음 — HDD 유일본** | preflight 7/23 |
| `00_RAW\reference\NIKL_Multi-layered_2025_v1.0` | ❌ **없음 — HDD 유일본** | preflight 7/23 |
| `10_LAYERS\01_bareun_raw` (형태소, 6개년) | ✅ 연도폴더 6개·2020 세션 2,232·컬럼 확인 | preflight 7/23 |
| `10_LAYERS\02_sense_annotated` | ⚠ 미실측 | — |
| `10_LAYERS\03_freq_dictionaries` (빈도사전 5종) | ✅ IPA표 확인 / 사전 본체 CSV는 미실측 | preflight 7/23(부분) |
| `10_LAYERS\04_metadata_index` (file_meta·speakers_normalized) | ✅ 컬럼까지 확인 | preflight 7/23 |
| `10_LAYERS\06_multilayer_gold` | ⚠ 미실측 | — |
| `10_LAYERS\05_search_master` / `06_actual_pron` | (신규 출력 예정지 — 없음이 정상) | 설계 7/23 |
| `20_AUDIO\03_wav` (wav+lab, 세션 구조) | ✅ 있음 (내용 전수는 인벤토리 99.44% 기준) | preflight 7/23 |
| `20_AUDIO\06_textgrid_merged` (3-tier, 읽기전용) | ✅ 있음 | preflight 7/23 |
| `20_AUDIO\06_textgrid_eojeol` (4-tier) | ✅ 폴더 있음 — 내용은 **2021만 완료**(G2P 미적용 한계) | 7/22 병합 |
| `90_ARCHIVE` | ❌ SSD엔 없음 (HDD 보존 방침) | preflight 7/23 |
| `mfa_eojeol` (마커·로그·격리) | ⚠ 미실측 (7/20 복사 대상 Tier1이었음) | — |

## 거점 2 — 구 외장 HDD (7/20 이전 전의 전체 상)

**★유일본 경고**: 아래 항목은 현재 **HDD에만** 존재한다. HDD 유실 = 영구 손실.

| 자산 | 성격 | 회수 |
|---|---|---|
| `00_RAW\reference` 4종 (00_DICTIONARY·MP·LS·다층위) | **유일본** — A단계 재실행·검증 재현에 필수 | 다음 HDD 연결 시 즉시 (명령 아래) |
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
