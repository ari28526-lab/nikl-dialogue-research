# DB v1 RC1 recovery sidecar 채택 결정

## 승인

2026-08-18 연구자 `ari30`은 동결 후보 SHA에 결속된 다음 범위를 명시 승인했다.

- D7–D10 exact-ID 55건의 recovery 상태 overlay
- D10 수동 전사·word 경계 16건의 append-only curated snapshot
- RC0·r3·최종 6-tier 불변
- D9 phone 참고 전용
- 수정 전사의 형태소·phone 재구축은 별도 후속 Gate

승인 원문과 candidate hash는
`outputs/approvals/APPROVAL_db_v1_rc1_recovery_adoption_20260818.json`에 기록한다.

## 채택 방식

RC1은 RC0의 5,103,356행 ledger를 다시 쓰지 않는 sidecar release다. 55건의
기존 `post_mfa_technical_exclusion` 행에 후속 상태를 덧붙이고, 16건에는
`active_annotation_source=curated` pointer를 추가한다. 원본과 수동 수정본을
모두 보존하며 active pointer만 연구용 선택을 안내한다.

1건의 D9 정렬과 16건의 수동 word·전사는 아직 공통 6-tier와 수정 전사 기반
형태소·phone 보완 전이다. 따라서 이 단계에서 정렬 성공 본체 수와 RC0 범주
회계를 바꾸지 않는다. 이는 복구 증거가 생겼다는 사실과 최종 분석 가능 상태를
구분하기 위한 것이다.

## 다음 단계

RC1 sidecar 독립 감사 뒤에는 수정 전사 16건의 형태소·철자 Roman 재구축과
phone/phoneme 처리 범위를 설계한다. D9 phone을 그대로 최종값으로 승격하거나
전수 MFA를 반복하지 않는다.
