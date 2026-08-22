# Stage 2 PV reviewer v2.1 사용성·안전 보완 결과

- 날짜: 2026-08-22
- 상태: **구현·독립 감사·사용자 최소 화면 확인 통과**
- 사용자 승인: Claude Work 검토에 대한 Codex 재검토 권고대로 진행
- 새 파생 root:
  `outputs/pilots/pv_seven_phenomena_reviewer_v2_1_20260822/`

## 1. 구현 범위

다음 다섯 항목만 구현했다.

1. R01: 미저장 입력이 있을 때 후보 이동·가져오기 경고
2. R06: 동결 `target_word_indices_json`에 따른 표적 어절 강조
3. R07: 최신 revision을 배열 끝이 아니라 `reviewed_at` 기준으로 선택
4. R08: 내부 형태소 상태 코드에 한국어 설명 병기, HIA는 `경계` 대신
   `축약 음절`로 표시
5. R09: `판단 확신도`를 `들린 형식·실현 인상에 대한 확신도`로 명확화

R03의 30개 batch builder와 R04의 200,000행 스캔 계약 변경은 구현하지 않았다.
R05의 batch/device 필드도 이번 14개 v2.1 범위에서는 추가하지 않았다.

## 2. 파생 방식

감사 통과한 v2 HTML을 입력으로 하는 UI-only 파생 builder를 새로 만들었다.
D: 말뭉치와 연도별 표를 다시 스캔하지 않았고, 음성·대화·기존 사용자 기록
payload를 변경하지 않았다.

- source v2 HTML SHA-256:
  `37c152d73069bfc7dc3e31684fdc99303916bb4acb72f986aab335541a1228f6`
- v2.1 HTML SHA-256:
  `4ac9edd77fd8889aaeb73b8c15afc6c2ee1a3c0eb5cca1e4d2b24e862da98a7e`
- 강조 정보 source `PV_SAMPLES.csv` SHA-256:
  `31bea32b1cd44f5e9e77baa84259a6fa3566a192f866a5b006371700fa1fe93f`

## 3. 독립 감사 결과

감사 결과는 `passed=true`, `errors=[]`이다.

| 항목 | 결과 |
|---|---:|
| 표본 / 강조 정보가 있는 표본 | 14 / 14 |
| 강조되는 표적 어절 | 15 |
| 기존 사용자 기록 | 15행 / 14 event |
| 전체 대화 텍스트 | 4,060행 |
| 기존 v2와 동일한 WAV SHA | 28/28 |
| 외부 자원 | 0 |
| R03 구현 | 0 |
| R04 계약 변경 | 0 |

PV0151의 연속 두 어절 `떡 벌어질`도 11·12번째 어절로 각각 강조되는지 runtime
시험했다. 최신값은 `Date.parse(reviewed_at)`로 비교하고, 시각이 같거나 유효하지
않을 때만 배열 순서를 tie-break로 쓴다.

## 4. 안전 동작

- 폼을 수정한 뒤 다른 후보로 이동하면 버리고 이동할지 묻는다.
- 취소하면 현재 입력을 유지한다.
- 저장하면 dirty 상태가 해제된다.
- 미저장 입력이 있는 채 JSONL 가져오기를 시작해도 같은 경고를 적용한다.
- 탭을 닫거나 새로고침할 때도 브라우저의 기본 미저장 경고를 요청한다.
- 후보 검색은 미저장 상태에서 자동으로 다른 후보로 전환하지 않는다.

## 5. 산출물

- HTML:
  `outputs/pilots/pv_seven_phenomena_reviewer_v2_1_20260822/PV_REVIEWER_V2_1.html`
- build receipt:
  `outputs/pilots/pv_seven_phenomena_reviewer_v2_1_20260822/PV_REVIEWER_V2_1_BUILD.json`
- audit JSON:
  `outputs/pilots/pv_seven_phenomena_reviewer_v2_1_20260822/audit/PV_REVIEWER_V2_1_AUDIT.json`
- SHA manifest:
  `outputs/pilots/pv_seven_phenomena_reviewer_v2_1_20260822/PV_REVIEWER_V2_1_SHA256_MANIFEST.csv`
- 검증 로그:
  `logs/pv_reviewer_v2_1_validation_20260822/VALIDATION_pv_reviewer_v2_1_20260822.log`

## 6. 사용자 최소 확인 결과

사용자가 다른 노트북의 Dropbox 사본에서 다음을 직접 확인했다.

1. `PV0151`의 복수 표적 `떡`과 `벌어질`이 모두 강조됐다.
2. 시험 글자를 입력한 뒤 후보 검색 필터를 해제하고 `다음`을 누르자 미저장
   입력 경고가 나타났다.
3. 경고에서 취소한 뒤에도 현재 표본과 시험 글자가 그대로 보존됐다.
4. 시험 글자는 실제 revision으로 저장하지 않았다.

처음에는 검색창이 `PV0151` 한 후보로 제한된 상태여서 `다음`이 같은 후보를
가리켰고 경고가 나타나지 않았다. 검색 필터를 해제해 실제 후보 이동을 시도하자
경고가 정상 작동했다. 이는 자료 손실이 아니라 한 후보 필터 상태의 no-op이었다.

따라서 v2.1 사용자 최소 화면 Gate는 **통과**다. 후속 연구자 결정에 따라
연도별 30개 batch 구현보다 먼저 일곱 현상 전체의 직접 선행연구와 일반적·
주변적·탐색적 형태론 환경을 정리한다. 이 정리가 끝나기 전에는 현재의
`핵심/탐색` 표시를 생산 우선순위로 해석하지 않고, 200,000행 계약도 실제 30개
후보 위치를 측정하기 전에는 바꾸지 않는다.

## 7. 저장소 상태

기존 v2 root와 스크립트는 수정하지 않았다. 19MB HTML·전체 대화 JSONL·
embedded audio를 포함한 생성 payload는 로컬에 보존하고 Git에는 올리지
않는다. v2.1 builder·auditor·runtime test와 이 결과 문서만 재현 근거로 Git
추적 대상으로 둔다.
