# 결정: 연도별 독립 실행 큐와 직전 연도 생산 gate

날짜: 2026-08-03 KST

## 문제

2021 시작 진입점은 2020 Gate B를 강제하지만, 2021 완료 뒤 2022–2025에 같은
절차를 적용하는 공용 PowerShell 진입점은 2020 전용 경로에 묶여 있었다. 또한
여러 연도를 같은 실행 queue ID로 차례로 호출하면 `queue_state.json`을 덮어써
직전 실행의 실패 원인과 재개 근거를 잃을 수 있었다.

## 결정

1. 제외 승인은 5개년 공용 approval queue에 둔다.
   `mfa_r2_prod_safe_body_2021_2025_20260803`
2. 실제 MFA 실행은 연도별 독립 queue ID를 쓴다.
   `mfa_r2_prod_safe_body_<YEAR>_20260803`
3. 각 실행은 정확히 한 연도만 받는다. 2022–2025 시작기는 직전 연도의 다음
   자료를 모두 같은 input/alignment/DB 계약으로 검증해야 한다.
   - 원자료·morph search source contract
   - align/merge marker와 보존 SQLite DB
   - 6-tier 및 동반표 독립 전수 감사
   - DB 표본 재수출 동등성
   - 최소 5세션 연구자 인프라 표본 승인
   각 현 연도의 MFA를 시작하기 전에는 그 연도 `morph_search.v3` 7표와 동결
   source contract도 먼저 성공해야 한다.
4. 연구자 표본 승인은 WAV/LAB/TextGrid 연결과 6-tier 사용 가능성에 대한
   인프라 승인이다. 실제 음운 실현 판정은 수행하지 않는다.
5. 동일 실행 queue를 재개할 때 기존 `queue_state.json`은 SHA-256이 같은 history
   사본으로 먼저 보존한다. 같은 queue ID에 다른 연도를 넣으면 중단한다.
   이미 기계 QC까지 통과한 queue도 다시 실행하지 않고 연구자 표본 검토로
   넘긴다.
6. 정본 승격은 자동 수행하지 않는다. 기계 QC 성공 뒤에도 연구자 표본 승인과
   다음 연도 gate 전까지 현 연도는 `complete_not_promoted` 상태다.

## 진입점

- 첫 연도: `start_remaining_mfa_after_2020_gate.ps1` — 2021만 허용
- 연도 입력 준비: `prepare_production_year_before_mfa.ps1`
- 표본 준비: `prepare_production_year_sample_review.ps1`
- 표본 승인 기록: `approve_production_year_sample_review.ps1`
- 다음 연도 gate: `preflight_production_next_year_gate.ps1`
- 다음 한 연도 시작: `start_next_mfa_year_after_gate.ps1`

## 연구 방법론상의 의미

모든 연도는 같은 Jamo r2·음향모델·6-tier 계약을 사용하되, 완료 판정은 연도별
독립 증거에 근거한다. 한 연도의 성공이나 구 산출물을 다른 연도의 완료 근거로
대체하지 않으며, 실패 뒤 재개도 완료된 정렬 DB와 export checkpoint를 보존한
상태에서 수행한다.
