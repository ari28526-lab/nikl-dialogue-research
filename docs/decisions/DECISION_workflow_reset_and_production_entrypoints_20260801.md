# 결정: workflow reset과 연도 범위가 고정된 생산 진입점

- 결정일: 2026-08-01 KST
- 상태: canonical active
- 근거 리뷰: `../reviews/incoming/EXTERNAL_REVIEW_workflow_reset_20260801.md`
- 조치 판정: `../reviews/RESOLUTION_external_review_workflow_reset_20260801.md`

## 문제

기술적 검증은 쌓였지만 서로 다른 세대의 파일럿 검토와 기본 6개년 실행기가
동시에 남아 있었다. 그 결과 이미 6-tier로 대체된 검토를 계속 보게 되었고,
2020만 먼저 완결하려는 운영 방침과 달리 기본 명령은 2021–2025까지 계속할 수
있었다. 또한 morph_search와 MFA가 같은 search master를 읽는다고 가정했지만
동일 `_build_meta` SHA를 대조하는 계약은 없었다.

## 결정

1. 구 4-tier/12발화/5-tier 검토와 difference inventory 반복을 종료한다.
2. 활성 문서는 README, CURRENT_STATE, production RUNBOOK, ASSETS_LEDGER로
   축소한다. CURRENT_STATE는 누적 추가하지 않고 전체 교체한다.
3. 사용자는 범위가 고정된 wrapper만 실행한다.
   - 2020 검색: `resume_2020_morph_search.ps1`
   - 2020 제외표: `prepare_2020_mfa_approval_review.ps1`
   - 2020 정렬: `start_2020_mfa_after_review.ps1`
   - Gate B 뒤 남은 연도: `prepare_remaining_*`, `start_remaining_*`
4. `SOURCE_CONTRACT.json`에 연도·run ID·동결 `_build_meta` SHA를 기록하고
   2020 MFA와 Gate B가 이를 재검증한다.
5. 2020 기계 QC 뒤 최소 5세션 생산 표본에서 파일 연결·6-tier·검색 가용성만
   연구자가 확인한다. 실제 음운 실현을 판정하지 않는다.
6. 2020 Gate B는 source/input/alignment contract, audit, retained DB, 재수출
   표본, 연구자 승인 보고서를 모두 결합한다. 통과 전 2021을 시작하지 않는다.
7. 2021–2025에서는 연도별 checkpoint와 실패 산출물을 보존한다. 한 연도의
   국소 실패가 다른 성공 연도의 처음부터 재계산을 요구하지 않게 한다.

## 연구 형식 보존

이 reset은 형식을 바꾸지 않는다. TextGrid 6-tier, pre-MFA 7표, post-MFA
4표, Roman 대소문자·구분자, 공통 Jamo r2와 phone 기준, KOINA/stitch의 선별
사용은 최종 점검 슬라이드와 동일하게 유지한다.

## 논문 방법론에서의 의미

6개년 자료가 단지 같은 이름의 모델을 사용했다고 주장하는 데 그치지 않고,
동일한 동결 입력 SHA, 모델/사전 계약, exporter, QC gate를 거쳤다는 기계 판독
근거를 남긴다. 동시에 MFA phone은 강제정렬 보조값일 뿐 실제 실현 판정은
후속 연구자 판단이라는 층 분리를 유지한다.
