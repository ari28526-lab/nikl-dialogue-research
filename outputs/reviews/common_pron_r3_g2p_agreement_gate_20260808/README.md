# r3 G2P–규칙 발음 Gate 소형 증거표

`EVIDENCE_SAMPLE.csv`는 승인 후보표가 아니다. 2026-08-08 전수 Gate 결과의 범주가
무엇인지 확인할 수 있도록 만든 75행 진단 표본이다.

- 사전 일치 exact 고빈도 12행
- 사전 충돌 exact 전부 14행
- 독립 사전 근거 없는 exact 고빈도 24행
- 규칙 목표 mismatch 고빈도 24행
- 위 고빈도 표본에 포함되지 않은 기존 회귀 예시 1행

각 행은 규칙 목표, G2P phone과 broad Roman, 편집거리, 우리말샘 후보·출처,
형태음운 근거 범주를 함께 보존한다. `candidate_is_final_selection=false`이며 이 파일을
수정해도 canonical 사전이나 MFA 입력은 바뀌지 않는다. 현재 연구자 승인 작업은
필요하지 않다.
