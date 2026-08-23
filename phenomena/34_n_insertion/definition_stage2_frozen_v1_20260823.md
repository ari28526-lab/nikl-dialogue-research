# ㄴ삽입(NI) — Stage 2 definition frozen v1

> definition_status: `researcher_confirmed`
>
> lifecycle_status: `frozen_v1_adopted_20260823`
>
> 기존 `phenomena/34_n_insertion/definition.md`와 candidate definition, 동결
> query는 읽기 전용으로 유지한다. 이 문서는 연구자가 채택한 Stage 2 NI 계약을
> 기록하지만, 개별 occurrence의 실현 판정·분석·공개 계약은 아니다.

## 1. 현상

선행 요소가 자음으로 끝나고 후행 요소가 /i/ 또는 /j/로 시작하는 형태적·
통사적 경계에서 [n]이 수의적으로 나타나는 현상을 NI로 다룬다. 삽입 뒤 선행
종성이 비음화될 수 있으므로 표면 비음 연쇄만으로 삽입을 자동 판정하지 않는다.

- 현상 코드: `NI`
- 한국어 이름: ㄴ삽입
- 문헌 근거 범위: `CLM-0001~CLM-0026`
- 수의성·변이: 경계·어종·빈도·지역·세대·운율 가능성을 분리해 보존
- 정의 상태: `researcher_confirmed`
- 생명주기 상태: `frozen_v1_adopted_20260823`

## 2. 검색 모집단과 환경 유형

동결 query
`config/target_queries/n_insertion_production_v1_20260818.json`
(SHA-256 `744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6`)
은 다음 두 모집단을 이미 생성했다.

1. `QN1_N_INSERTION_INTRA_EOJEOL_V1`: 어절 내부
2. `QN2_N_INSERTION_INTER_EOJEOL_V1`: 어절 간

Gate 1의 4단 분류는 occurrence가 아니라 환경 유형에 적용한다.

| 환경 유형 | 분류 | 우선순위 | 동결 상태 |
|---|---|---|---|
| 자음 말음 + /j/ | `general_direct` | 핵심 | `researcher_confirmed`; CLM-0001·0004·0014·0023 |
| 자음 말음 + /i/ | `peripheral_reported` | 보조 | `researcher_confirmed`; CLM-0003·0014 |
| 한자어 공명음 + /j/ | `peripheral_reported` | 보조 | `pending`; CLM-0004·0015, D-G1-A 유보 |
| 한자어 장애음 + /j/ | `peripheral_reported` 비교군 | 보조 | `pending`; CLM-0004·0015, D-G1-A 유보 |
| 보조사 ‘요’/JX | `theoretical_underreported` | 별도 탐색 | `researcher_confirmed`; 처리 방침 결정 완료, query 미생성 |
| 어절 간 | 미분류 `pending` | 후속 | AP/IP·실제 검토는 후속 Gate로 기결정 |
| 형태·경계 불명 | `unclear_boundary` | 후속 | 사례별 `pending` |

개별 후보의 환경 유형 자동 배정은 시작하지 않는다. 한자어 두 환경은 최대 포함
원칙에 따라 보존하지만 CLM-0015 확인 전에는 확정 분류로 올리지 않는다.

## 3. inclusion / exclusion / confound

동결 계약:
`config/phenomenon_contracts/n_insertion_contract_frozen_v1_20260823.json`

- inclusion: 두 boundary scope, 양측 한글 unit, 왼쪽 종성, 오른쪽 무초성
  /i·j/ 계열, 왼쪽 POS 무제한.
- exclusion: 본모집단의 오른쪽 J*/E*, 숫자·기호 unit, 동결 nucleus 집합에
  없는 ㅢ.
- retention: 의미번호 불확실성, `etym_unknown`, join 상태는 제외 조건이
  아니며 상태로 보존한다.
- confound: 삽입+비음화 연쇄, ㄴ탈락 이론 관계, NAL·LLN·PT 복수
  membership, 한자어·합성어·사이시옷 경계, 어절 간 운율 경계.

다른 현상과의 복수 membership을 허용하며 한 현상에서 후보를 조용히
삭제하지 않는다. frozen 계약은 candidate의 query 조건 7종을 의미 변경 없이
유지하고 새 occurrence 필터를 추가하지 않는다.

## 4. CLM-0015 명시적 유보

연구자 결정 `D-G1-A`에 따라 `NI_ENV_SINO_RESONANT_J`와
`NI_ENV_SINO_OBSTRUENT_J`를 모두 포함하되 `class_status=pending`으로 유지한다.
CLM-0015의 `needs_human_check=true`를 해제하지 않는다. Hwang(2007/2008) 원전
대조가 필요하지만 원문을 보유하지 않아 수배 중이므로, 입수 후 별도 후속
결정으로 해소한다. 계약의 `NI_UNR_001`도 같은 사유로
`deferred_by_decision_d_g1_a` 상태를 보존한다.

## 5. ‘요’ 탐색 후보

보조사 ‘요’ 환경은 사용자 결정 완료 항목이다.

- 본모집단과 분리
- CLM-0002 근거
- 기존 query 변경·재동결 없음
- `decision_status=treatment_decided_query_not_created`
- 실행 가능한 query JSON과 후보 occurrence를 생성하지 않음

따라서 이후 사용자 결정 목록에 ‘요’를 다시 넣지 않는다.

## 6. 어절 간 환경

어절 간 후보는 588,277행 모집단으로 보존한다. `environment_class=null`,
`class_status=pending`을 유지하며, 실제 문맥·AP/IP·청취 검토는 후속 Gate로
미룬다는 기존 결정을 변경하지 않는다.

## 7. 실현 판정 증거

| 증거원 | 역할 | 최종 실현값인가 |
|---|---|---|
| 표기·형태소·동결 query | 가능한 환경 탐색 | 아니오 |
| 의미번호·어원·빈도 join | 층화·해석 보조 | 아니오 |
| MFA·기존 TextGrid | 후속 시간 위치 보조 | 아니오 |
| KOINA·기타 자동 보조층 | 승인된 선별 사례의 보조 정보 | 아니오 |
| 연구자 청취·음향·TextGrid 판정 | 별도 수동 ledger | 예 |

이 freeze는 어떤 실현값도 기록하지 않고 정식 ledger를 쓰지 않는다.

## 8. 문헌 근거

- 현상종합 초안:
  `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NI_현상종합_초안_20260823.md`
- evidence level: `pilot_full`
- core SRC: SRC-297/SRC-288, SRC-287, SRC-293, SRC-294
- definition·환경·confound: CLM-0001~0026
- 운율 source-level 후보: SRC-360, SRC-362
- human check: CLM-0008, CLM-0015, CLM-0026

CLM-0008은 이론 confound, CLM-0026은 구체 수치를 쓰지 않는 qualitative 변이
근거로 비차단 유보한다. CLM-0015는 위 §4의 명시적 유보를 따른다.

## 9. 기존 후보와 zero-drop

source registry:
`config/candidate_sources/n_insertion_g1_g4_source_registry_v1_20260823.json`

- 2020~2025 후보: 941,903행
- 어절 내부: 353,626행
- 어절 간: 588,277행
- joined 출력: 941,903행
- freeze 신규 occurrence 파생표: 0행

환경 유형표는 occurrence 분할표가 아니므로 유형별 개수를 941,903과 직접
합산하지 않는다. 후보 행은 삭제·복제·재분류하지 않았다.

## 10. 변수·추가 정보 후보

- 공통: 연도, 경계 scope, 좌우 형태소/POS, /i/·/j/, 의미번호 상태,
  어원 상태, 빈도, 화자·대화 맥락
- 후속 sidecar: AP/IP 경계, 정보 요청, TextGrid 검토 필요, 자산 상태,
  수동 작업 상태
- 미확정 값: `pending`, `unavailable`, `not_applicable`을 구분

가변 정보는 append-only sidecar에서 시작하며 반복 사용이 확인되기 전에는
공통 열로 승격하지 않는다.

## 11. 정지선

- frozen v1은 환경 유형·계약의 연구자 채택 기록이지 occurrence 실현 판정이 아니다.
- G5/G6, 신규 후보 추출, 대량 문맥 연결, 청취, TextGrid 수정, 자동 실현 판정,
  정식 ledger를 시작하지 않는다.
- ‘요’ query 설계와 probe 회귀 보강 D-G1-C도 별도 GO 전에는 시작하지 않는다.
- 기존 definition·candidate·query·후보·join·감사·문헌 정본을 수정하지 않는다.
