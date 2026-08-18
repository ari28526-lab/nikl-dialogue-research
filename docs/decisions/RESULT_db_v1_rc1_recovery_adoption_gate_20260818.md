# DB v1 RC1 recovery 채택 Gate 결과

## 결과

첫 recovery shard의 exact-ID 55건을 DB v1 RC0 위에 덧붙일 상태 overlay
후보로 통합하고, 독립 감사를 통과했다. 현 상태는
`gate_closed_pending_researcher_approval`이며 실제 DB 채택은 수행하지 않았다.

- D7 연구자 판정: 11건
- D8 0.1초 미만 원 음원 단편: 25건
- D9 통제 재정렬: 19건
- 합계: 중복 없는 55건
- D10 연구자 수동 전사·word 경계 snapshot: 16건

연도별 55건 분포는 2020년 5, 2021년 29, 2022년 5, 2023년 6,
2024년 5, 2025년 5건이다. 모든 ID는 RC0와 D1 recovery 장부에 정확히 한 번씩
존재하며 기존 상태는 모두 `post_mfa_technical_exclusion`이었다.

## 연구 정보의 해석

D10 16건에는 연구자가 확정한 word 경계, 최종 한글 전사, 철자 기반 Roman을
curated 후보로 기록했다. D9 phone은 강제 정렬의 참고 결과일 뿐이므로
`d9_reference_only_not_adopted`로 남겼다. 수정 전사에 맞는 형태소 정보와
phone/phoneme은 추측하여 만들지 않고 후속 재구축 대상으로 명시했다.

이 구분은 수동으로 들은 전사·경계와 자동 정렬 결과를 섞지 않으면서도, 이후
표적 추출에서 `active_annotation_source=curated`를 선택할 수 있게 한다.

## 안전성과 재현성

- RC0 base ledger 변경: 없음
- r3 본체·보존 DB 변경: 없음
- 최종 6-tier 변경: 없음
- TextGrid 교체: 없음
- MFA 재실행: 없음
- 자동 승인: 없음

후보 manifest는 Git 커밋 `645d04e4cd8d9e88eb006e7920aeaead31fa9090`과
builder SHA를 기록한다. 독립 감사 manifest SHA는
`01e4a0eb2762cc80821d0afeeba56f56961ed32a1b0f91c9f130a96f6a0ae3db`이며,
감사 상태는 `passed_gate_closed_pending_researcher_approval`이다.

## 다음 Gate

다음 단계는 새 청취나 전수 MFA가 아니다. 동결된 55건 상태 후보와 16건 수동
snapshot의 SHA 범위를 한 번 승인한 뒤, RC0를 덮어쓰지 않는 RC1 sidecar로
materialize하는 것이다. 승인 전에는 후보 파일만 존재한다.
