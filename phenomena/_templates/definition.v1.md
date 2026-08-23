# <현상명> — Stage 2 definition template v1

> 상태: `draft_template`. 이 템플릿은 Gate 0의 구조 선언이며 query·환경 분류·
> 실현 판정값을 확정하지 않는다. 실제 값 채택은 현상별 후속 Gate와 연구자
> 승인을 요구한다.

## 1. 현상

- 현상 코드:
- 한국어 이름:
- 기술적 정의 후보:
- 수의성·변이 가능성:
- 이 절의 상태: `pending | literature_seeded | researcher_confirmed`

## 2. 환경 조작화 후보

- 환경 유형 ID:
- 형태론적 경계 후보:
- 분절 환경 후보:
- query 참조(있을 때만 경로·SHA):
- 미확정 항목:

Gate 0에서는 조건값을 동결하지 않는다. 환경 분류는 occurrence가 아니라 환경
유형 단위의 append-only 기록으로 후속 Gate에서 수행한다.

## 3. inclusion / exclusion / confound 후보

- inclusion evidence refs:
- exclusion evidence refs:
- confound evidence refs:
- 교차 현상·중복 가능성:

여기의 ID는 계약값이 아니라 검토 후보 근거다.

## 4. 실현 판정 증거

| 증거원 | 역할 | 최종 실현값인가 |
|---|---|---|
| 표기·형태소 검색층 | 후보 환경 탐색 | 아니오 |
| 사전·G2P | 가능한 발음 참조 | 아니오 |
| MFA·기존 TextGrid | 검토 시간 위치 보조 | 아니오 |
| KOINA·기타 자동 보조층 | 선별 사례의 보조 정보 | 아니오 |
| 연구자 청취·음향·TextGrid 판정 | 별도 승인 ledger의 수동 판정 | 예 |

자동 실현 판정과 정식 ledger 자동 쓰기를 금지한다.

## 5. 변수·추가 정보 후보

- 공통 변수 후보:
- 현상별 정보 요청 후보:
- TextGrid 검토 필요성:
- 미확정 값의 상태:

가변 정보는 append-only sidecar로 시작하고 반복 사용이 확인된 뒤에만 코드북
검토를 거쳐 정식 열로 승격한다.

## 6. 문헌 근거

- 현상종합 초안:
- 착수스캐폴드(없으면 `null`):
- evidence level:
- core SRC IDs:
- definition candidate CLM IDs:
- inclusion candidate CLM IDs:
- exclusion candidate CLM IDs:
- confound candidate CLM IDs:
- prosody candidate SRC/CLM IDs:
- unresolved/human-check IDs:

모든 참조는 `SRC-###`·`CLM-####`와 저장소 상대경로로 기록한다. 요약문을
원문 주장처럼 복사하지 않는다.

## 7. 산출 목표와 정지선

- 후보 추출·검토 목표:
- 수동 후속 목표:
- 공개 파생본 기본 원칙:
- 다음 Gate 전 결정할 항목:

Gate 0 definition은 연구자 확인 전 분석·실행·공개 계약으로 사용하지 않는다.
