# 외부 검토 brief — 공통발음 r3 6개년 전수 재정렬 workflow

날짜: 2026-08-09 KST
저장소: `https://github.com/ari28526-lab/nikl-dialogue-research`
브랜치: `agent/harden-pre-bulk-pipelines`

## 검토 목적

이 프로젝트는 형태소·표기상 음운 환경을 CSV/Parquet에서 검색하고 해당 WAV와
TextGrid를 모은 뒤, 선별 자료에 KOINA와 연구자 청취 판정을 적용하기 위한
2020–2025 연구 인프라를 구축한다. MFA phone은 실제 실현 정답이 아니라 분절
인프라다.

r2 표본 검토에서 규칙 예상 발음이 MFA 입력에 일관되게 연결되지 않은 문제를
찾아 신규 생산을 중단했다. 881,237형 전수 감사와 r3 후보 설계, 5,103,356발화
safe/follow-up 라우팅, 네 문제 발화 표적 회귀까지 완료했다. 연구자는 네 경계와
단계적 safe-body adoption을 승인했고, 최종 r3에는 r2 interval을 섞지 않고
2020–2025 pronunciation-safe 4,384,992발화를 대상 pool로 삼고, 독립 음원·CSV·
정렬 가능성 Gate를 통과한 발화를 모두 새로 정렬하기로 결정했다. 기술적 제외는
exact-ID로 별도 회계한다.

## 반드시 먼저 읽을 파일

1. `AGENTS.md`
2. `docs/environment/PROJECT_START_HERE.md`
3. `docs/environment/PROJECT_CURRENT_STATE.md`
4. `docs/WORKFLOW_mfa_r3_full_realign_2020_2025.md`
5. `docs/decisions/DECISION_common_pron_r3_full_realign_2020_2025_20260809.md`
6. `config/mfa_r3_full_realign_workflow_v1.json`
7. `config/common_pronunciation_resource_contract_v3_draft.json`
8. `config/mfa_pronunciation_release_gate.json`
9. `docs/RUNBOOK_production_2020_2025.md`

증거 manifest와 감사 보고서:

- `outputs/reports/AUDIT_common_pron_r3_pre_adoption_routing_20260808.json`
- `outputs/reports/AUDIT_common_pron_r3_safe_body_candidate_20260808.json`
- `outputs/reports/AUDIT_common_pron_r3_policy_decision_reuse_20260808.json`
- `outputs/reports/AUDIT_common_pron_r3_adoption_readiness_20260808.json`
- `outputs/reports/AUDIT_mfa_r3_full_realign_policy_20260809.json`
- `outputs/reviews/common_pron_r3_targeted_regression_20260808/`

## 현재 의도적 차단

기존 `start_full_mfa_after_review.ps1`, `run_mfa_year_queue_safe.ps1`,
`run_eojeol_realign.ps1`, `preflight_mfa_year_queue.ps1`,
`build_mfa_alignment_contract.py`, `validate_mfa_r2_adoption.py`는 r2 전용 계약을
가정한다. r3 후보를 r2 manifest로 가장하지 않기 위해 release Gate를 닫아 둔
상태다. 이 검토 뒤 r3 전용 adoption·runner를 구현한다.

## 중점 검토 질문

1. safe body 전수 재정렬과 follow-up 분리가 6개년 방법론 일관성을 충분히
   보장하는가?
2. 14.076% follow-up이 연도별로 다른 비율인 점을 논문·분석에서 어떻게
   보고하고 selection bias를 어떻게 관리해야 하는가?
3. MFA의 화자 적응을 고려할 때, 일부 발화가 follow-up이면 세션 전체를 빼야
   하는가, 아니면 같은 세션의 safe 발화만 정렬해도 되는가?
4. MFA 중단 뒤 같은 DB를 재개하는 현재 전략과 세션/연도 checkpoint의 경계가
   안전한가?
5. 어떤 오류가 DB 재정렬을 요구하고, 어떤 오류는 TextGrid/CSV export만 다시
   하면 되는가?
6. 국소 발음 수정 때 token→session 영향 inventory로 완전 적응 단위만 다시
   정렬하는 정책이 충분한가?
7. 2020 첫 r3 연도 뒤 사람 표본을 한 번 요구하고 2021–2025는 전수 자동 감사의
   flag가 있을 때만 요구하는 안이 타당한가?
8. 6-tier TextGrid와 동반 CSV/Parquet가 연구 목적, KOINA, 이어붙이기와 형태소·
   음운 환경 검색에 충분한가?
9. 기존 r2 전용 코드에서 r3 runner 구현 시 빠뜨리기 쉬운 hard-code, marker,
   path, schema, checkpoint 위험은 무엇인가?
10. 처음부터 다시 해야 하는 사고를 막기 위해 추가할 계약·테스트·독립 감사는
    무엇인가?
11. Stage 19 발음 coverage safe-body 4,384,992와 과거 음원·CSV·승인제외 기준
    safe-body 4,120,627를 혼용하지 않고 실제 연도 MFA 입력 교집합을 계산·보고하는
    설계가 충분한가?

## 원하는 결과 형식

- `Critical / High / Medium / Low` 심각도
- 각 지적마다 파일·행 또는 함수 근거
- 연구방법론 영향과 소프트웨어/자료 무결성 영향을 분리
- 현재 설계에서 유지할 점과 반드시 바꿀 점 구분
- 2020 PowerShell을 실행하기 전 필요한 최소 구현 순서
- 의미 없는 반복 검토·중복 계산을 명시적으로 지적

검토 중 생산 MFA, D: 원자료·기존 r2 DB/TextGrid, release Gate를 변경하지 않는다.
