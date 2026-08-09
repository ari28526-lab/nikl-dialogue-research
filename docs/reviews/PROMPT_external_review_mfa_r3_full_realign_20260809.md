# 외부 도구에 전달할 프롬프트

아래 내용을 그대로 전달한다. 외부 도구는 같은 로컬 저장소에서 작업한다.

```text
C:\Users\ari30\research\2026_summer_research 저장소의 공통발음 r3 및
2020–2025 MFA 전수 재정렬 workflow를 독립적으로 검토해 주세요.

먼저 AGENTS.md를 준수하고 다음 파일을 순서대로 읽으세요.
- docs/environment/PROJECT_START_HERE.md
- docs/environment/PROJECT_CURRENT_STATE.md
- docs/WORKFLOW_mfa_r3_full_realign_2020_2025.md
- docs/decisions/DECISION_common_pron_r3_full_realign_2020_2025_20260809.md
- config/mfa_r3_full_realign_workflow_v1.json
- config/common_pronunciation_resource_contract_v3_draft.json
- config/mfa_pronunciation_release_gate.json
- docs/reviews/BRIEF_external_review_mfa_r3_full_realign_20260809.md
- outputs/reports/AUDIT_mfa_r3_full_realign_policy_20260809.json

관련 runner, validator, alignment contract, TextGrid·CSV exporter와 테스트도 실제로
읽고 문서 주장과 코드가 일치하는지 확인하세요. 특히 기존 r2 전용 hard-code를
r3 후보 파일 이름만 바꿔 우회하면 안 됩니다.

연구 목적은 형태소·표기상 음운 환경을 검색해 WAV·TextGrid를 모으고, KOINA와
연구자 청취로 실제 실현을 판정할 수 있는 6개년 인프라를 만드는 것입니다.
MFA/G2P phone은 실제 실현 정답이 아닙니다.

연구자가 승인한 정책은 다음과 같습니다.
- 2022 표적 회귀 4개 TextGrid 경계 승인
- safe body 4,384,992발화 단계 채택
- follow-up 718,364발화 exact-ID 별도 shard 보존
- 2020부터 2025까지 pronunciation-safe pool 중 정렬 가능 발화를 동일 r3
  계약으로 모두 새로 정렬하고 기술적 제외는 exact-ID 별도 회계
- r2 interval/TextGrid는 최종 r3에 재사용하지 않고 비교 증거로만 보존
- 국소 오류 때문에 연도 전체를 자동 clean 재시작하지 않음

다음을 비판적으로 검토하세요.
1. 거시·미시 workflow의 연구방법론 타당성
2. 화자 적응과 safe-body 발화 선별의 상호작용
3. 오류 유형별 재처리 범위와 checkpoint/DB 재개 안전성
4. 사전·입력·정렬·TextGrid·CSV 계약 분리
5. 2020 연도 Gate와 2021–2025 자동 진행 조건
6. follow-up 비율과 selection bias 보고
7. 기존 코드의 r2 hard-code, marker, path, schema, PowerShell 5.1 문제
8. 반복 계산·반복 사람 검토를 줄이면서 놓치면 안 되는 검사
9. 2020 실행 전 최소 구현 순서와 GO/NO-GO 조건
10. 발음 coverage safe-body 4,384,992와 과거 음원·CSV·승인제외 safe-body
    4,120,627의 정의·분모 차이 및 실제 MFA 입력 exact-ID 교집합 계약

코드나 release Gate, D: 자료는 변경하지 말고 검토 보고서만 다음 경로에 작성하세요.
docs/reviews/incoming/EXTERNAL_REVIEW_mfa_r3_full_realign_20260809.md

보고서는 Critical/High/Medium/Low로 분류하고, 각 지적에 파일·행/함수 근거,
연구방법론 영향, 데이터 무결성 영향, 구체적 수정안을 포함하세요. 마지막에는
“2020 실행 전 최소 체크리스트”와 “재실행 범위 결정표”를 별도로 제시하세요.
```
