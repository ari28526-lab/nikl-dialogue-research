# 공통발음 r3 v3.1 단계적 채택 계약 개정

날짜: 2026-08-09 KST

상태: 계약 개정 확정, release 물질화·독립 감사 전, production Gate 닫힘

## 결정

공통발음 r3의 첫 생산 범위는 881,237개 관측 표면형 전체가 아니라,
Stage 19에서 분리한 pronunciation-safe 발화에 사용할 수 있도록 Stage 20에서
전수 projection한 795,804개 candidate-ready 표면형으로 한정한다. 이
795,804형의 796,061개 발음 변이 행은 새 staged release에서 byte 동일하게
물질화되고 독립 감사를 통과할 때에만 `selected`로 승격된다.

85,398개 zero-fallback hold형과 35개 명시적 policy형은 첫 staged release의
선택 대상이 아니다. 이 형들이 들어 있는 718,364개 발화는 삭제하거나 임의의
G2P 1-best로 채우지 않고 exact-ID follow-up shard로 보존한다. 따라서 첫
release는 4,384,992개 pronunciation-safe 발화의 신규 r3 정렬을 위한 것이며,
전체 코퍼스 발음 해결 또는 실제 음성 실현 판정을 주장하지 않는다.

## 개정 이유

기존 v3 draft에는 다음 두 기준이 동시에 들어 있었다.

- candidate는 selection이 아니다.
- 채택 전에 881,237형 전부가 selected phone을 가져야 한다.

하지만 연구자가 승인한 실행 범위는 candidate-ready형을 쓰는 safe-body 단계
채택이고, 나머지 형은 의도적으로 follow-up에 남기는 방식이다. 기존 문구를
그대로 두면 정상적인 staged release도 영구적으로 실패하거나, 구현 코드가
candidate를 근거 없이 selection으로 간주하게 된다. v3.1은 승인 범위를
바꾸는 새 연구자 판단이 아니라 이미 승인된 범위를 기계 검증 가능한 계약으로
정확히 표현하는 개정이다.

## 수량 계약

| 단위 | 수 | 지위 |
|---|---:|---|
| canonical 관측 표면형 | 881,237 | 전체 장기 범위 |
| staged release 승격 대상 표면형 | 795,804 | Step 2 물질화·감사 후 selected |
| staged dictionary 변이 행 | 796,061 | projection byte 동등성 대상 |
| zero-fallback hold형 | 85,398 | 후속 release 대상 |
| 명시적 policy형 | 35 | 후속 결정 대상 |
| pronunciation-safe 발화 | 4,384,992 | 연도별 입력 계약과 교집합 후 신규 r3 정렬 |
| follow-up 발화 | 718,364 | exact-ID 별도 보존 |

표면형 분할은 `881,237 = 795,804 + 85,398 + 35`이다. 발화 분할은
`5,103,356 = 4,384,992 + 718,364`이다. 표면형 수와 발화 수는 단위가
다르므로 서로 대체해 보고하지 않는다.

## 승인 기록 불변성

기존
`outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json`
은 최초 승인 결정의 기록으로서 앞으로 byte 불변으로 취급한다. 구현 문서나
입력 provenance의 SHA가 바뀌어도 승인 JSON을 제자리 갱신하지 않는다.

새 관측 provenance는 같은 폴더의
`RESEARCHER_APPROVAL.provenance.v2.json`에 내용 SHA가 달라질 때만 새 레코드로
추가한다. sidecar는 승인 범위를 확장하지 않으며, 기존 레코드를 삭제하거나
수정하지 않는다. 현재 승인 파일에 과거 `provenance_refreshed_at`이 남아 있는
것은 외부 리뷰 전 이력으로 보존하고 다시 고쳐 쓰지 않는다.

## 변하지 않는 사항

- Stage 01–21 산출물은 재생성하지 않는다.
- D: 원자료, r2 DB, r2 TextGrid와 r2 완성본은 수정하지 않는다.
- Stage 20 `NOT_ADOPTED` 후보 사전 자체는 계속 비채택 증거다.
- candidate를 selected로 승격하는 실물은 별도의 release ID로 만든다.
- r2 interval을 최종 r3에 재사용하거나 phone label만 바꾸지 않는다.
- production release Gate는 체크리스트 1–7 동안 계속 닫아 둔다.

## 논문 방법론 기록용 요지

전체 관측 어휘형 중 자동·사전·형태론적 근거가 합치되어 발음 후보가 확정된
표면형만 1차 공통발음 자원으로 물질화하였다. 미해결형을 임의의 G2P 출력으로
대체하지 않고 해당 발화를 후속 처리 집합으로 분리했으며, 1차 자원의 사전
projection과 MFA 입력 사전은 byte 수준 동등성 및 동결 phone inventory
검사를 거치도록 설계하였다. 이 단계의 phone은 강제 정렬 입력 발음이며 실제
음성 실현의 판정값이 아니다.

## 다음 단계

체크리스트 2에서 새 staged release builder와 독립 adoption 감사기를 구현한다.
그 감사가 통과하기 전에는 이 결정만으로 MFA, TextGrid 물질화 또는 Production
Gate 개방을 허용하지 않는다.
