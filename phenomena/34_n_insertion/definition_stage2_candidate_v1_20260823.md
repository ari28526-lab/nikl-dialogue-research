# ㄴ삽입(NI) — Stage 2 definition candidate v1

> 상태: `literature_seeded`, `candidate_pending_researcher_confirmation`.
> 기존 `phenomena/34_n_insertion/definition.md`와 동결 query는 읽기 전용으로
> 유지한다. 이 문서는 CLM 근거와 Gate 1 계약을 연결하는 신규 후보 정의이며,
> 실현 판정·분석·공개 계약으로 아직 동결되지 않았다.

## 1. 현상

선행 요소가 자음으로 끝나고 후행 요소가 /i/ 또는 /j/로 시작하는 형태적·
통사적 경계에서 [n]이 수의적으로 나타나는 현상을 NI로 다룬다. 삽입 뒤 선행
종성이 비음화될 수 있으므로 표면 비음 연쇄만으로 삽입을 자동 판정하지 않는다.

- 현상 코드: `NI`
- 한국어 이름: ㄴ삽입
- 문헌 근거 범위: `CLM-0001~CLM-0026`
- 수의성·변이: 경계·어종·빈도·지역·세대·운율 가능성을 분리해 보존
- 정의 상태: `literature_seeded`

## 2. 검색 모집단과 환경 유형

동결 query
`config/target_queries/n_insertion_production_v1_20260818.json`
(SHA-256 `744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6`)
은 다음 두 모집단을 이미 생성했다.

1. `QN1_N_INSERTION_INTRA_EOJEOL_V1`: 어절 내부
2. `QN2_N_INSERTION_INTER_EOJEOL_V1`: 어절 간

Gate 1의 4단 분류는 occurrence가 아니라 환경 유형에 적용한다.

| 환경 유형 | 분류 후보 | 우선순위 | 근거·상태 |
|---|---|---|---|
| 자음 말음 + /j/ | `general_direct` | 핵심 | CLM-0001·0004·0014·0023 |
| 자음 말음 + /i/ | `peripheral_reported` | 보조 | CLM-0003·0014 |
| 한자어 공명음 + /j/ | `peripheral_reported` | 보조 | CLM-0004·0015, human check |
| 한자어 장애음 + /j/ | `peripheral_reported` 비교군 | 보조 | CLM-0004·0015, human check |
| 보조사 ‘요’/JX | `theoretical_underreported` | 별도 탐색 | CLM-0002, 처리 방침 결정 완료 |
| 어절 간 | 미분류 `pending` | 후속 | SRC-360·362, AP/IP 검토는 나중 |
| 형태·경계 불명 | `unclear_boundary` | 후속 | 사례별 pending |

개별 후보의 환경 유형 자동 배정은 시작하지 않는다.

## 3. inclusion / exclusion / confound

계약 후보:
`config/phenomenon_contracts/n_insertion_contract_candidate_v1_20260823.json`

- inclusion: 두 boundary scope, 양측 한글 unit, 왼쪽 종성, 오른쪽 무초성
  /i·j/ 계열, 왼쪽 POS 무제한.
- exclusion: 본모집단의 오른쪽 J*/E*, 숫자·기호 unit, 동결 nucleus 집합에
  없는 ㅢ.
- retention: 의미번호 불확실성, `etym_unknown`, join 상태는 제외 조건이
  아니며 상태로 보존한다.
- confound: 삽입+비음화 연쇄, ㄴ탈락 이론 관계, NAL·LLN·PT 복수
  membership, 한자어·합성어·사이시옷 경계, 어절 간 운율 경계.

다른 현상과의 복수 membership을 허용하며 한 현상에서 후보를 조용히
삭제하지 않는다.

## 4. ‘요’ 탐색 후보

보조사 ‘요’ 환경은 사용자 결정 완료 항목이다.

- 본모집단과 분리
- CLM-0002 근거
- 기존 query 변경·재동결 없음
- Gate 1에서는 후보 문서만 작성
- 실행 가능한 query JSON과 후보 occurrence는 생성하지 않음

따라서 이후 사용자 결정 목록에 ‘요’를 다시 넣지 않는다.

## 5. 실현 판정 증거

| 증거원 | 역할 | 최종 실현값인가 |
|---|---|---|
| 표기·형태소·동결 query | 가능한 환경 탐색 | 아니오 |
| 의미번호·어원·빈도 join | 층화·해석 보조 | 아니오 |
| MFA·기존 TextGrid | 후속 시간 위치 보조 | 아니오 |
| KOINA·기타 자동 보조층 | 승인된 선별 사례의 보조 정보 | 아니오 |
| 연구자 청취·음향·TextGrid 판정 | 별도 수동 ledger | 예 |

Gate 1은 어떤 실현값도 기록하지 않고 정식 ledger를 쓰지 않는다.

## 6. 문헌 근거

- 현상종합 초안:
  `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NI_현상종합_초안_20260823.md`
- 착수스캐폴드: `null`(NI는 현상종합 초안 §4에서 재개)
- evidence level: `pilot_full`
- core SRC: SRC-297/SRC-288, SRC-287, SRC-293, SRC-294
- definition·환경·confound 후보: CLM-0001~0026
- 추가 교차 주장: CLM-0027~0034 중 NI 태그 행은
  `pending_researcher_adoption`
- 운율 source-level 후보: SRC-360, SRC-362
- human check: CLM-0008, CLM-0015, CLM-0026

CLM-0015는 한자어 내부 환경을 계약에서 동결하기 전에 확인한다. CLM-0008은
이론 confound, CLM-0026은 구체 수치를 쓰지 않는 qualitative 변이 근거로
비차단 유보할 수 있다.

## 7. 기존 후보와 zero-drop

source registry:
`config/candidate_sources/n_insertion_g1_g4_source_registry_v1_20260823.json`

- 2020~2025 후보: 941,903행
- 어절 내부: 353,626행
- 어절 간: 588,277행
- joined 출력: 941,903행
- Gate 1 신규 occurrence 파생표: 0행

환경 유형표는 occurrence 분할표가 아니므로 유형별 개수를 941,903과 직접
합산하지 않는다. 어절 간 후보는 삭제하지 않고 후속 검토 상태로 보존한다.

## 8. 변수·추가 정보 후보

- 공통: 연도, 경계 scope, 좌우 형태소/POS, /i/·/j/, 의미번호 상태,
  어원 상태, 빈도, 화자·대화 맥락
- 후속 sidecar: AP/IP 경계, 정보 요청, TextGrid 검토 필요, 자산 상태,
  수동 작업 상태
- 미확정 값: `pending`, `unavailable`, `not_applicable`을 구분

가변 정보는 append-only sidecar에서 시작하며 반복 사용이 확인되기 전에는
공통 열로 승격하지 않는다.

## 9. 정지선

- 이 definition과 계약은 candidate이며 frozen이 아니다.
- G5/G6, 대량 문맥 연결, 청취, TextGrid 수정, 자동 실현 판정을 시작하지 않는다.
- 연구자가 환경 유형과 계약을 확인한 뒤에만 별도 frozen 버전을 만든다.
- 기존 definition·query·후보·join·감사·문헌 정본을 수정하지 않는다.
