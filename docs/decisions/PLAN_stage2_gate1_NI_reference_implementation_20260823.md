# 계획: Stage 2 Gate 1 — NI 기준 구현 설계

- 작성일: 2026-08-23 KST
- 상태: `design_review_pending_researcher_go`
- 선행 Gate: Gate 0 채택 완료
- 대상 현상: NI(ㄴ삽입)만
- 성격: **설계 정본 후보. 아직 구현·실행 승인이 아니다.**

## 0. 결론부터

Gate 1은 기존 6개년 후보 941,903행을 다시 만들거나 복제하지 않는다. 이미
감사된 G1~G4 후보·join 산출물을 읽기 전용 source registry로 연결하고, 작은
계약 파일·환경 유형표·‘요’ 탐색 후보 문서·독립 검사기만 새로 만든다.

환경 4단 분류의 단위는 개별 occurrence가 아니라 **환경 유형**이다. 개별 후보의
실현 여부는 분류하지 않는다. G5/G6 문맥 연결·bundle, TextGrid 검토, 자동
실현 판정, 정식 ledger 기록은 Gate 1 범위가 아니다.

## 1. 목표와 비목표

### 1.1 목표

1. 동결 query와 문헌 근거 사이에 NI inclusion/exclusion/confound 계약을 둔다.
2. NI의 환경 유형을 `general_direct`, `peripheral_reported`,
   `theoretical_underreported`, `unclear_boundary`로 검토 가능하게 정리한다.
3. 각 환경 유형에 `CLM-####`/`SRC-###` 근거 또는 `pending`을 강제한다.
4. 기존 6개년 후보의 경로·SHA·행 수·헤더를 source registry로 결속한다.
5. 입력 후보를 삭제·복제하지 않는 zero-drop 회계를 검증한다.
6. NI에서 이 구조를 검증한 뒤 LLN과 나머지 현상에 재사용할 수 있게 한다.

### 1.2 비목표

- 기존 query·join 계약·후보 CSV·감사 JSON 수정 또는 재생성
- ‘요’ query JSON 생성·동결
- 941,903행 전체의 환경 클래스 자동 배정
- G5 시간 연결, G6 표본 bundle, 전수 음성·TextGrid 스캔
- MFA·KOINA·wav2vec2 실행
- 자동 실현 판정, 수동 판정의 자동 ledger 반영
- 분석모형·공개 파생본 생성

## 2. 실측 입력

### 2.1 동결 계약

| 입력 | SHA-256 | 상태 |
|---|---|---|
| `config/target_queries/n_insertion_production_v1_20260818.json` | `744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6` | frozen, 읽기 전용 |
| `config/join_contracts/n_insertion_variable_join_contract_v1_20260818.json` | `12d811632a9c440e33fd76f814620c65e47113bdfda4ea058581b5e476c44050` | frozen, 읽기 전용 |

동결 query는 QN1 어절 내부와 QN2 어절 간 두 모집단으로 구성된다. 양쪽 unit은
한글, 왼쪽은 종성 존재, 오른쪽은 무초성 ㅇ + 중성 {ㅣ, ㅑ, ㅕ, ㅛ, ㅠ,
ㅖ, ㅒ}, 오른쪽 POS는 `^(?!J|E)`다. 숫자·기호 인접은 unit type 조건으로
제외된다. 왼쪽 POS는 제한하지 않는다.

### 2.2 6개년 manifest 재집계

아래 수치는 RESULT 문서가 아니라 연도별 `TARGET_MANIFEST_BUILD.json`,
`JOIN_MANIFEST.json`, 감사 JSON을 다시 파싱해 얻었다.

| 연도 | 후보 | 어절 내부 | 어절 간 | 고유 발화 | joined 출력 | RC1 curated | 한자어 내부 후보 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 101,638 | 42,604 | 59,034 | 93,360 | 101,638 | 1 | 111 |
| 2021 | 206,037 | 81,865 | 124,172 | 184,328 | 206,037 | 2 | 300 |
| 2022 | 141,966 | 53,759 | 88,207 | 127,107 | 141,966 | 1 | 160 |
| 2023 | 123,381 | 45,570 | 77,811 | 108,785 | 123,381 | 1 | 185 |
| 2024 | 185,401 | 65,109 | 120,292 | 157,565 | 185,401 | 1 | 226 |
| 2025 | 183,480 | 64,719 | 118,761 | 150,459 | 183,480 | 0 | 228 |
| **합계** | **941,903** | **353,626** | **588,277** | **821,604** | **941,903** | **6** | **1,210** |

`rows_in=rows_out`는 6개년 모두 성립하고 연도별 감사 상태는 모두 `passed`,
failures는 0건이다. `etym_unknown`은 6개년 합계 700,908행이며 값 추정이나
삭제 없이 상태로 보존되어 있다.

### 2.3 실제 헤더

| 실측 파일 | 열 수 | 정규화 헤더 SHA-256 |
|---|---:|---|
| 2020 `morph_boundaries.csv.gz` | 35 | `9a9899f55c81656dd902ade14fdbc588cb9855ad24d06464f155e0050fa039a1` |
| 2020~2025 `TARGET_CANDIDATES.csv` | 34 | `7c2e32dd00f270011f02ddcaa3fe44356b5a21511ad8c78f8556e26bf190cad9` |
| 2020~2025 `CANDIDATES_WITH_VARIABLES.csv` | 73 | `e3e5cff018516e22331c3bf2b9fbc611f55ec60d6604ac87e48c7f7a5d8738f8` |

6개년 후보·joined 헤더는 각각 완전 동일하다. 형태소 경계의 `left_pos`,
`right_pos`, unit·자모·어절/형태소 index 35열은 후보 표의 상위 열이 아니라
`match_evidence_json`에 문자열 값으로 보존된다. Gate 1 검사기는 이 JSON을
명시적으로 파싱해야 하며, 상위 열에 해당 필드가 있다고 가정해서는 안 된다.

QN1과 QN2의 실제 evidence key 집합을 확인하기 위해 2020 후보를 최대
200,000행으로 제한해 읽었고 두 query를 모두 만난 42,605행에서 중단했다.
두 query 모두 source 35열과 같은 evidence key 집합을 가졌고,
`year`, `utt_id`, `target_occurrence_id`, `occurrence_index`가 존재했다.

## 3. 단순화 원칙

### 3.1 94만 행 파생표를 만들지 않는다

Gate 1의 계약은 기존 후보를 변경하지 않는다. 따라서 occurrence별 새 CSV를
복제하는 대신, 연도별 원본·joined·manifest·audit의 경로·SHA·행 수를 담은
작은 source registry를 만든다. 이후 표본이 필요한 Gate에서만 exact-ID로
선택한다.

이 방식은 5GB 이상 중복 저장, 새 행 누락, SHA 재생성, 의미 없는 전수 재검사를
피하면서도 기존 후보로 재현 가능하다.

### 3.2 환경 유형과 occurrence를 분리한다

4단 분류는 문헌·형태론적 환경 **유형**의 지식 표다. 아직 각 후보 occurrence를
그 유형에 자동 배정하지 않는다. 따라서 Gate 1에서는 “환경 클래스별 후보 수의
합 = 941,903” 같은 허위 회계를 만들지 않는다.

### 3.3 query 조건과 연구 분류를 분리한다

- query: 가능한 환경을 넓게 찾는 동결된 기계 조건
- 환경 유형: 문헌 근거와 연구 우선순위를 표시하는 검토 단위
- 실현 판정: 추후 연구자 청취·음향·TextGrid 검토로만 기록

환경 유형이나 어원 분류는 실현값이 아니며 후보 삭제 필터로 사용하지 않는다.

## 4. NI 환경 유형 seed 제안

아래는 Gate 1 구현 때 사용자가 검토할 초기 seed다. `seeded`는 문헌 연결이
있다는 뜻이지 연구자 최종 확정을 뜻하지 않는다.

| 제안 ID | 환경 | 4단 분류 제안 | 근거·상태 | 처리 |
|---|---|---|---|---|
| `NI_ENV_CORE_C_J` | 자음 말음 + /j/ 시작, 형태 경계 | `general_direct` | CLM-0001·0004·0014·0023, seeded | 본모집단 핵심 |
| `NI_ENV_CORE_C_I` | 자음 말음 + /i/ 시작 | `peripheral_reported` | CLM-0003·0014, seeded | /j/와 분리 집계 |
| `NI_ENV_SINO_RESONANT_J` | 한자어 내부, 공명음 말음 + /j/ | `peripheral_reported` | CLM-0004·0015; CLM-0015 human check | 계약 동결 전 확인 |
| `NI_ENV_SINO_OBSTRUENT_J` | 한자어 내부, 장애음 말음 + /j/ 비교군 | `peripheral_reported` | CLM-0004·0015; 비실현 비교 보고 | 후보를 삭제하지 않음 |
| `NI_ENV_YO_JX` | 보조사 ‘요’ 앞 | `theoretical_underreported` | CLM-0002, 사용자 결정 완료 | 본모집단 밖 탐색 후보 문서만 |
| `NI_ENV_INTER_EOJEOL` | 어절 간 인접 경계 | `pending` | 기존 query QN2·NI definition, 운율 근거 보완 필요 | AP/IP 개입은 추후 sidecar |
| `NI_ENV_UNCLEAR_BOUNDARY` | 형태·어원·경계 해석 불명 | `unclear_boundary` | evidence 또는 pending | 조용히 삭제하지 않음 |

이 표는 최종 분류가 아니다. 특히 `NI_ENV_CORE_C_I`, 한자어 내부 두 유형,
어절 간 환경의 분류명은 Gate 1 구현 보고서에서 근거와 함께 연구자가 확인한다.

## 5. inclusion/exclusion/confound 계약 설계

### 5.1 포함 조건

동결 query의 실제 7조건을 한 항목씩 참조하고, QN1/QN2의 차이는
`boundary_scope`뿐임을 검사한다. 계약은 query보다 후보를 좁히는 새 필터를
몰래 추가하지 않는다.

### 5.2 제외 조건

- 오른쪽 J*/E*: 기존 본모집단 query에서 제외
- 숫자·기호 unit: 기존 query에서 제외
- `ㅢ`: 동결 nucleus 집합에 없으므로 제외
- 의미번호 불확실성·어원 불명·join 상태: **제외 사유가 아님**. 상태로 보존

### 5.3 confound와 membership

- 삽입 뒤 비음화 연쇄: 표면 [ŋn]/[nn]만으로 NI를 자동 판정하지 않음
- ㄴ탈락과의 이론 관계: CLM-0008 human check, 결정 필터가 아니라 이론
  confound로 유보 가능
- NAL·LLN·PT 접면: 복수 membership 허용, 한 현상에서 조용히 삭제 금지
- 한자어 내부·사이시옷·합성어 경계: 근거와 판정 축을 분리
- 어절 간 AP/IP 경계: 실현값이 아니라 추가 정보 요청 후보

### 5.4 ‘요’

‘요’는 본 계약의 include 조건에 넣지 않는다. 사용자 결정대로 별도 탐색 후보
문서에 CLM-0002, JX 환경, 본모집단 분리 회계, 비동결 상태를 기록한다. ‘요’를
처리할지 다시 묻지 않는다.

## 6. 문헌 사람 확인 처리

| CLM | Gate 1 역할 | 계획 |
|---|---|---|
| CLM-0008 | ㄴ삽입↔ㄴ탈락 이론 관계 | inclusion 조건에 쓰지 않고 confound 설명으로 유보 가능. 사용 시 원문 확인 |
| CLM-0015 | 한자어 2음절 공명음/장애음 비대칭 | 환경 유형·inclusion에 직접 영향을 주므로 계약 동결 전 우선 확인 |
| CLM-0026 | 연령·지역 변이 | 구체 수치를 쓰지 않는 한 qualitative confound로 `non_blocking_pending` 유지 가능 |
| CLM-0145 | HIA 코퍼스 연구 | HIA 착수까지 유보 |
| CLM-0151 | HIA 음향 연구 화자 수 불일치 | HIA 착수까지 유보 |

NI Gate 1 전체를 세 건 때문에 정지시키지 않는다. 다만 CLM-0015에 기대는
환경 유형을 `researcher_confirmed` 또는 계약 `frozen`으로 올리기 전에는
확인 결과나 유보 사유가 있어야 한다.

## 7. Gate 1 구현 산출물 제안

사용자 구현 GO 뒤 다음 신규 파일만 만든다. 날짜·버전은 실제 착수일에 확정한다.

1. `config/candidate_sources/n_insertion_g1_g4_source_registry_v1_<date>.json`
2. `config/phenomenon_contracts/n_insertion_contract_candidate_v1_<date>.json`
3. `config/environment_types/n_insertion_environment_types_candidate_v1_<date>.jsonl`
4. `phenomena/34_n_insertion/definition_stage2_candidate_v1_<date>.md`
5. `docs/decisions/NOTE_n_insertion_yo_exploratory_query_candidate_<date>.md`
6. `scripts/python/audit_stage2_gate1_n_insertion_contracts.py`
7. `tests/test_audit_stage2_gate1_n_insertion_contracts.py`
8. `outputs/pilots/stage2_gate1_n_insertion_contracts_<date>/AUDIT_*.json`
9. 같은 출력 폴더의 `SHA256SUMS_*.txt`와 `logs/stage2_gate1_.../`

후보 계약은 `draft`/`candidate`로 생성한다. 연구자 검토 전 `frozen` 값을 쓰지
않는다. 승인 시 기존 파일을 덮어쓰지 않고 새 frozen 버전과 채택 문서를 만든다.

## 8. zero-drop 계약

### 8.1 Gate 1 기준선

- 입력 후보: 941,903
- 기존 joined 출력: 941,903
- join에서 삭제된 행: 0
- Gate 1이 새로 복제·변형하는 occurrence 행: 0

따라서 Gate 1 source registry의 핵심 회계는 연도별
`manifest candidate_rows = join rows_in = join rows_out = audit joined_rows`다.

### 8.2 독립 축

후속 표본 상태는 다음을 독립적으로 유지한다.

- 후보 가용성
- 선정 상태
- 시간 연결 상태
- TextGrid 검토 필요
- TextGrid 자산 상태
- 수동 작업 상태

서로 다른 축의 개수를 하나의 합계식으로 더하지 않는다. 환경 유형표 역시
occurrence 분할표가 아니므로 941,903과 직접 합산하지 않는다.

## 9. 검사와 대표 실패 시나리오

Gate 1 검사기는 다음을 독립 확인한다.

1. 동결 query·join 계약 SHA 일치
2. 연도별 manifest·audit 6종 경로·SHA·행 수 결속
3. 후보 34열·joined 73열 헤더의 6개년 동일성
4. `match_evidence_json`의 필수 35 key 존재와 파싱 가능성
5. 계약 조건과 동결 query 7조건의 모순 0
6. 환경 유형별 evidence ref 또는 `pending` 존재
7. 존재하지 않는 SRC/CLM 참조의 명시적 실패(Claude P2-3 반영)
8. `needs_human_check`를 researcher-confirmed로 조용히 승격하면 실패
9. source registry의 zero-drop 등식
10. 기존 출력 존재 시 `FileExistsError`
11. `.partial` 원자 승격과 manifest 자기해시 제외

실측용 CSV 읽기는 `max_occurrences=200000` 상한을 갖고 필요한 헤더·대표
query·JSON 구조를 확인한 뒤 조기 중단한다. 기존 G3/G4 전수 감사를 반복하지
않는다.

## 10. 구현 순서와 정지선

1. 모든 예정 출력 경로 부재 확인
2. 보호 입력 SHA·manifest·헤더 preflight
3. source registry 생성
4. NI 계약 candidate 생성
5. 환경 유형 candidate 생성
6. 새 NI definition과 ‘요’ 후보 문서 생성
7. 독립 검사기·테스트 작성
8. py_compile + 성공/필드누락/잘못된 ref/SHA 불일치/기존 출력 거부 테스트
9. 감사 JSON·SHA manifest 생성 후 정지

합격 뒤에도 G5/G6를 실행하지 않는다. 연구자가 계약과 환경 유형을 검토하고
별도 승인해야 frozen 버전을 만든다.

## 11. 구현 GO 전에 사용자가 확인할 것

다시 결정할 필요가 없는 항목:

- ‘요’는 본모집단 밖 탐색 후보
- 기존 query 재동결 없음
- 환경 분류 단위는 occurrence가 아니라 환경 유형
- NI 후 LLN 순서
- TextGrid는 추후 read-only 패널 + Praat 왕복

구현 GO 때 확인할 것은 다음 두 가지뿐이다.

1. §4의 환경 유형 seed를 candidate 상태로 만드는 데 동의하는가.
2. §7의 신규 파일 9종 범위로 구현하는 데 동의하는가.

동의 전에는 이 문서와 HTML 검토본만 보존하고 구현하지 않는다.
