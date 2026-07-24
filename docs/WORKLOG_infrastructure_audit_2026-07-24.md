# 연구 인프라 감사 작업일지 — 2026-07-24

## 기록 원칙

- 이 문서는 CSV·MFA 대량 작업 전에 수행하는 점검과 개선을 시간순으로 기록한다.
- 확인한 사실, 해석, 아직 확인하지 못한 사항을 구분한다.
- 원자료는 수정하지 않는다.
- 코드를 바꾸기 전 기존 버전을 보존하고, 변경 이유와 검증 결과를 함께 남긴다.
- 대량 산출물은 재실행 전에 소표본 파일럿과 중단·재개 안전성을 검증한다.
- 커밋·푸시할 때 이 문서에 커밋 ID와 범위를 덧붙인다.

## 연구 작업 흐름 — 사용자 확인본

1. 형태소 분석 CSV에서 특정 형태소가 포함된 발화 또는 표기상 음운 환경을
   충족하는 발화를 추출한다.
2. 추출된 발화에 대응하는 음성 파일과 TextGrid를 모은다.
3. 후보 자료에 KOINA 운율 분석 결과를 결합한다.
4. 연구자가 음성 파일과 TextGrid를 직접 검토해 현상의 실현 여부를 판정한다.
5. 형태소·표기 환경·빈도·사회 변수·운율·수동 판정을 결합해 현상별 분석을
   수행한다.

따라서 이 단계의 핵심은 자동으로 실현 여부를 판정하는 것이 아니라 다음 두
인프라를 신뢰할 수 있게 만드는 것이다.

- **CSV 인프라**: 후보를 빠짐없이 검색할 수 있는 형태소·표기·사전 발음·
  메타데이터
- **MFA 인프라**: 후보 음성에서 연구자가 구간을 찾고 판정하는 데 사용할 수 있는
  안정적인 대략적 분절과 TextGrid

## 개념 정정

### G2P phones의 역할

- `korean_mfa` G2P를 사용한 phones tier는 음성 파일의 대략적 분절 위치를
  TextGrid에 표시하기 위한 정렬 인프라다.
- 이 phones tier를 ㄴ 삽입 등 음운 현상의 최종 실현 판정값으로 사용하지 않는다.
- 최종 실현 여부는 연구자가 음성과 TextGrid를 직접 확인해 판정한다.
- 따라서 G2P 파일럿의 `spn` 감소는 정렬용 발음 항목의 미등록 문제가 줄었다는
  운영 지표이지, 현상 실현을 자동 판정했다는 증거가 아니다.

### lexicon 예외 발음의 역할

- lexicon 예외 발음은 사전의 등재 발음을 조회해 CSV의 기준/예측 발음 층에
  반영하는 것이다.
- 음향 신호로부터 실제 발음을 자동 추정하는 층이 아니다.
- 사전 발음과 규칙 기반 발음을 어떤 우선순위로 결합했는지 출처 열로 추적할 수
  있어야 한다.

## 2026-07-24 작업 시작 상태

### 저장소

- 작업 브랜치: `agent/harden-pre-bulk-pipelines`
- 시작 커밋: `f352668`
- 사용자 소유로 보이는 추적되지 않은 `Microsoft/` 폴더는 건드리지 않는다.

### 이미 확인한 전량 검색 마스터 상태

- `D:\10_LAYERS\05_search_master\_build_meta.json`
  - 세션: 17,156
  - 입력 발화/출력 행: 5,103,356
  - JSON 결측: 0
  - 어절 수 불일치: 0
- 전량 search master는 2026-07-23에 이미 생성되었다.
- 문서 일부에 남은 “전량 대기/미실행” 표기는 최신 상태와 맞지 않아 정정이
  필요하다.

### 확인된 감사 항목

1. Bareun 완료 기록의 5,103,358행과 search master의 5,103,356행 사이 2행 차이
2. 2026-07-24 메타데이터 수정 전에 생성된 2023년 네 세션 CSV
3. 설계된 lexicon 사전 발음 예외가 현재 코드와 전량 산출물에 실제 반영됐는지
4. `has_wav`, `has_tg_eojeol`, `quarantined` coverage 열의 실제 계산 여부
5. 관련 문서의 오래된 상태와 “실제 발음” 표현 정정

## 작업 기록

### 1. 문서와 코드의 첫 대조

확인한 파일:

- `docs/decisions/DESIGN_search_master_layer.md`
- `docs/HANDOFF_search_master_session2.md`
- `scripts/python/predict_pron.py`
- `scripts/python/build_search_master.py`
- `scripts/SCRIPTS_INDEX.md`
- `outputs/reports/PILOT_pre_bulk_validation_2026-07-24.md`

현재까지 확인한 사실:

- `build_search_master.py`는 `predict_pron.predict_pron()`을 호출한다.
- 현재 `predict_pron.py`에서 lexicon 파일을 읽는 코드는 발견되지 않았다.
- 따라서 lexicon 예외 발음은 설계에는 있으나, 현재 전량 search master의 예측
  발음에는 반영되지 않았을 가능성이 높다. 산출물 열과 표본을 추가로 확인한다.
- `build_search_master.py`는 coverage 세 열을 기본적으로 “미계산” 값으로 채운다.
- `scripts/SCRIPTS_INDEX.md`의 “전량 대기”는 실제 전량 생성 상태와 충돌한다.

### 2. 연구 흐름과 산출물 상태 정정

사용자 확인을 반영해 다음 문서를 정정했다.

- `scripts/SCRIPTS_INDEX.md`
- `outputs/reports/PILOT_pre_bulk_validation_2026-07-24.md`
- `docs/WORK_HISTORY_2026-07.md`
- `docs/decisions/DESIGN_safe_pre_bulk_pipeline_2026-07-24.md`
- `docs/decisions/AUDIT_pre_bulk_MFA_CSV_2026-07-24.md`
- `docs/decisions/DESIGN_search_master_layer.md`
- `docs/decisions/RUNBOOK_MFA_eojeol_realign.md`
- `docs/TODO_A단계.md`
- `docs/ASSETS_LEDGER.md`
- `docs/GUIDE_실행순서_제3자용.md`
- `docs/HANDOFF_search_master_session2.md`
- `docs/HANDOFF_pilot_search_master.md`
- `docs/decisions/METHODS_bareun_dialogue_reanalysis.md`
- `docs/learning/자료구축_단계별_리뷰.md`
- `config/paths.json`
- `scripts/run_eojeol_realign.ps1`
- `scripts/python/predict_pron.py`
- `scripts/python/realign_eojeol_merge_output.py`

정정 내용:

1. search master 전량본은 2026-07-23에 이미 생성됐다고 명시했다.
2. 이 전량본은 7/24 메타 수정 전이며 lexicon 예외 발음과 coverage가
   미반영된 감사 대상이라고 표시했다.
3. G2P phones를 “실제 발음/실현 판정”으로 부르지 않고, 연구자가 후보 위치를
   찾기 위한 대략적 분절·시간정보로 정의했다.
4. 예측/사전 발음, MFA 분절, 연구자의 수동 실현 판정을 서로 다른 층으로
   분리했다.
5. 구 가이드의 완료 마커 와일드카드 삭제 명령을 제거하고 한 연도씩
   파일럿→검증→본실행하도록 바꿨다.

아직 `06_actual_pron`은 경로 설정과 설계 문서에 역사적 이름으로 남아 있다.
실현 판정값과 혼동될 수 있으므로 추출 스크립트를 만들기 전에 보조 레이어의
정확한 이름과 스키마를 다시 정한다.

검증:

- `config/paths.json` JSON 파싱 통과
- `predict_pron.py --selftest` 30/30 통과
- lexicon 색인 헬퍼 자체검사 통과
- `run_eojeol_realign.ps1` PowerShell 파서 통과
- `git diff --check` 통과

lexicon 관련 추가 확인:

- `predict_pron.py`에는 `(word, pos_tag)` 조회용 색인 헬퍼가 이미 있다.
- 그러나 `build_search_master.py`는 실제 lexicon 파일을 열거나 이 색인을
  `predict_pron()` 호출에 전달하지 않는다.
- 따라서 “준비 코드가 전혀 없음”이 아니라 “조회 헬퍼는 있으나 전량 빌드에
  배선되지 않음”이 정확한 상태다.

## 다음 기록 예정

- 연도별 Bareun/search master 파일 수와 행 수 재계산
- 2행 차이의 정확한 파일·발화 ID
- 네 메타데이터 수정 세션의 수정 전/후 값
- lexicon 발음 파일의 실제 열과 조회 키
- 대표 예외 발음 표본에서 현재 CSV와 사전 발음 비교
- 수정 파일, 테스트 결과, 커밋 ID
