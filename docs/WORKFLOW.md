# 연구 워크플로우 v2 (2026-07-09 확정)

> 상태: **historical**. 연구의 큰 흐름은 유효하지만 현재 생산 순서는 `RUNBOOK_production_2020_2025.md`가 우선한다.

## 연구 목표

한국어 일상대화 말뭉치(NIKL 2020-2025)의 **형태음운 변이**를
**빈도 효과**(형태소·어절·의미 빈도, 화자·사용역 변수)와의 관계에서 분석.
필요 정보: 형태소 분석, 의미번호, IPA/로마자 발음형, 운율(IP/AP), 빈도.
음성은 전량 처리하지 않고 **JSON 기반 레이어로 검색 → 필요 발화만
wav/TextGrid 호출**하는 포인터 방식.

**범위 (2026-07-09 확정)**: 직접 분석 대상은 **일상대화 말뭉치만**.
서울코퍼스(50번, G: 03_Seoul_Corpus)는 이번 작업의 직접 분석에서 **제외** —
기존 검색 결과·빈도의 참조/비교 자료로만 활용. MP·LS·다층구조·KoFREN도
동일하게 참조 전용.

## 대원칙: 두 단계 분리

```
A단계 [자료 구축]  현상 중립적 인프라. 한 번 구축, 전 현상이 공유.
B단계 [현상 분석]  현상마다 독립 폴더·독립 워크플로우. 동일 템플릿 반복.
```

---

## A단계: 자료 구축 (현상 중립)

| # | 레이어 | 산출물 위치 (D:\05_NIKL_DIALOGUE_bareun_2020-2025\) | 상태 |
|---|---|---|---|
| A1 | 형태소 (바른) | 01_bareun_raw/ | 🔄 실행 중 |
| A2 | 의미번호 (우리말샘) | 02_sense_annotated/ | 스크립트 ✅ |
| A3 | 빈도사전 (통합+KoFREN) | 03_freq_dictionaries/ | 스크립트 ✅, KoFREN 예정 |
| A4 | 메타데이터 인덱스 (사용역·주제·화자) | 04_metadata_index/ | 예정 |
| A5 | 층화 빈도 (성별×연령×사용역) | 03_freq_dictionaries/ | 예정 |
| A6 | 음성 포인터 (utt_id→wav/TextGrid) | 05_audio_index/ (G: file_index 이관) | 예정 |
| A7 | 운율 표본 (KOINA IP/AP) | 06_prosody/ | 파일럿 예정 (Colab) |

**A단계 완료 기준**: 각 레이어 산출물 + 검증 수치가
`docs/decisions/METHODS_bareun_dialogue_reanalysis.md`에 기록되어 있을 것.

## B단계: 현상별 워크플로우 (동일 템플릿)

현상마다 Dropbox에 폴더 하나: `phenomena/{번호}_{현상}/`
(예: `phenomena/34_n_insertion/`)

```
B1 환경 정의   definition.md — 음운·형태 조건 명세
               (예: ㄴ삽입 = 선행 형태소 자음 말음 + 후행 i/j 시작,
                합성어/파생어/구 경계 구분, 어휘 목록 조건)
B2 환경 검색   search_env.py — A레이어에서 가능 환경 전수 추출
               → candidates.csv (utt_id, 어절, 분석, 환경 변수들)
B3 실현 판정   현상별 방법 선택:
               (a) 전사 대조: original_form vs form
               (b) 음성 확인: A6 포인터로 wav/TextGrid 호출 (표본)
               (c) 운율 결합: A7 IP/AP 경계와 교차
B4 변수 결합   candidates + A3/A5 빈도 + A2 의미 + 화자·사용역 + (운율)
               → analysis_ready.csv
B5 통계·보고   R (scripts/R/), Quarto (qmd/) → outputs/
```

- 현상별 폴더는 서로 독립 — 병렬 진행/중단 가능
- B2까지는 완전 자동화 목표: 새 현상 추가 시 definition.md 작성만으로
  후보 추출까지 1일 내
- 기존 G: 30-60번 검색 로직(utils_phonology.py, 61_34 노트북 등)은
  B2 작성 시 재사용

## 첫 적용: ㄴ삽입 (잠정)

- 기존 자산: 34번 사전검색 CSV, 서울코퍼스 구 경계 ㄴ삽입(50번),
  61_34_dialogue_n_insertion.ipynb (G:)
- A단계 완료 후 `phenomena/34_n_insertion/`부터 시작
- 실현 판정: 1차는 전사 대조(a), 표본 검증은 음성(b), IP/AP 경계
  효과는 (c) — ㄴ삽입은 운율 경계 민감 현상이므로 A7과 연결 가치 큼

## 폴더 정리 계획 (2026-07-09 확정)

### 거점별 역할 (겹침 없이)

| 거점 | 역할 | 규칙 |
|---|---|---|
| **D:** | 데이터 전부 (원본+산출물) | 유일한 데이터 원본 |
| **Dropbox** | 코드·문서·phenomena·config | 기계 간 동기화, 대용량 금지 |
| **G:** | Colab **셔틀** (미러 아님) | 필요 파일만 업로드, 결과 D: 회수 후 삭제 |
| **C:** | 실행환경 (venv·conda·API 키) | 데이터 두지 않음 |

### 경로 중앙 관리 (이행보다 먼저 도입 — ✅ 완료)

- `config/paths.json` — 모든 경로의 단일 출처. 폴더 이동·기계 변경 시 여기만 수정
- `scripts/python/paths.py` — 로더 (`from paths import P; P("layers")`)
- 신규 스크립트는 반드시 paths 사용. 기존 스크립트는 이행(Phase 3) 때 일괄 수정

### D: 목표 트리 (이동은 같은 드라이브라 즉시)

```
D:\
├── 00_RAW\                       원본 · 불변
│   ├── dialogue_json\            ← 00_NIKL_DIALOGUE_2020-2025_json
│   ├── dialogue_audio\           ← 04_00\00_source (+ 2025 PCM 예정)
│   └── reference\                ← DATA_2026 (MP·LS·다층구조·사전 원자료)
├── 10_LAYERS\                    A단계 산출물 ← 05_NIKL_DIALOGUE_bareun_2020-2025
├── 20_AUDIO\                     음성 자산 ← 04_00\03_wav, 05_mfa_output,
│                                   06_textgrid_merged, 04_mfa_input
├── 30_PHENOMENA\                 B단계 대용량 중간산출물 (현상별 하위폴더)
└── 90_ARCHIVE\                   ← 00_이전시도, 00_YOON_workshop, temp, tmp,
                                    nul, 기타, 04_00 루트 임시파일·구식 CSV
```

결정 사항: **04_00은 해체·재배치**, **DATA_2026은 00_RAW\reference로 이동**.

### 이행 단계

1. **Phase 1 (지금)**: 아무것도 옮기지 않음 (1차 분석 실행 중).
   paths.json 도입 ✅, 신규 산출물은 규칙대로 D:에 생성
2. **Phase 2 (1차 분석 완료 직후)**: A2·A3 실행은 현 경로로 그대로 진행
3. **Phase 3 (A단계 산출물 확정 후, 디스크 한가할 때)**:
   D: 내부 이동 실행(즉시) → paths.json 갱신 → 기존 스크립트 상수를
   paths.py 참조로 일괄 수정 → 문서 내 경로 갱신 (HANDOFF, PLAN들)
4. **Phase 4**: 90_ARCHIVE 정리·중복 삭제로 D: 여유 확보 (294GB → 2025
   음성 수용 대비), G: 셔틀 규칙 적용 시작

## 관련 문서

- 총정리·재개: `000_HANDOFF_2026-07-09.md`
- 방법론(논문용): `docs/decisions/METHODS_bareun_dialogue_reanalysis.md`
- 억양: `docs/decisions/PLAN_KOINA_intonation_IP_AP.md`
- 음성 연계·2025 PCM: `D:\04_00_NIKL_DIALOGUE_MFA\PLAN_2026-07-09_점검_및_음성연계.md`
