# 프로젝트 현재 상태 정본 (교체 초안)

최종 갱신: 2026-08-01 KST · 이전 판은 `docs/archive/`의 동명 파일 참조

## 연구 목적

```text
형태소·표기상 음운 환경을 CSV/Parquet에서 검색
  → utt_id로 WAV·TextGrid·메타데이터 수집
  → 선별 후보에만 KOINA·이어붙이기·wav2vec2 보조 분석
  → 연구자가 음성·TextGrid를 보고 실제 실현 여부 판정
```

MFA/G2P phone은 강제정렬 보조값이며 실현 판정이 아니다.

## 확정 방법 (동결)

- 정렬: 2020–2025 전부 신규 MFA. 공통사전 `common_pron_mfa_r2_20260728`,
  acoustic Korean MFA v3.3.0, G2P Jamo v3.2.0, 승인 예외 27건, adoption v3
  `passed/allow_yearly_mfa=true`. 구 2020/2021 정렬 재사용 금지.
- TextGrid 6-tier: `words/phones_mfa/phoneme_r_auto/utterance/
  utterance_orth_r/morph_analysis_utt`, 전 tier 0–xmax. 형태소 시간경계 미주장.
- pre-MFA 조합검색: `morph_search.v3` 연도별 7표 (좌표계 3종 분리, 기호 후보 분리).
- post-MFA 동반표: 연도별 gzip 4표 (`config/research_companion_tables_schema_v2.json`).
- KOINA/stitch/wav2vec2는 선별 후속층, MFA 값 비덮어쓰기, seam 횡단 해석 금지.

## 실제 완료 (실물 근거 있음)

- 동결 pre-MFA search master 6개년 5,103,356발화 (`_build_meta=success`)
- r2 공통사전 release/adoption/승인 (D: `00_contract\*.json` 전부 통과)
- 생산 코드: 6-tier exporter·동반표·연도 QC·연도 큐·preflight 전부 기본 경로에
  배선 (Python 287/287, PowerShell 정적검사 통과)
- 2020 `morph_search.v3` shard 1/23 성공 (41,803발화, SHA 불일치 0, lock 해제)
- 회귀 증거: `outputs/reports/EVIDENCE_morph_search_v3_regression_60_20260801.json`,
  `outputs/reports/EVIDENCE_research_6tier_post_review_20260801.json`

## 실제 미완료

- 2020 검색표 shard 2–23, 2021–2025 검색표 전체
- 2020–2025 신규 r2 MFA 전체 (D:에 시작 흔적 없음 — 실측 확인)
- 승인 제외 계약 (전 연도; preflight `NO_GO`의 유일 사유)
- 최종 joined 검색층(7표+4표)·우리말샘 1:N — **의도적 후행**, 6개년 정렬 후 작성
- reference 어휘부 4종 HDD 회수 (우리말샘 1:N의 물리적 선행조건)

## 현재 실행 상태

계산 중인 것 없음. lock 없음. D: 여유 약 318 GiB.
2026-08-01 workflow reset 외부 리뷰 완료 — 결과는
`docs/reviews/incoming/EXTERNAL_REVIEW_workflow_reset_20260801.md`.
구 4-tier/5-tier 검토 적체 3건(REVIEW.xlsx 59행·12발화·phoneme 파일럿)은
6-tier 확정으로 **폐지 판정** — 더 이상 검토하지 않는다.

## 다음 명령 (순서대로, 각 1줄)

1. `scripts\run_morph_search_year_safe.ps1 -Year 2020` — shard 2–23 재개(자동 재사용)
2. `scripts\prepare_full_mfa_approval_reviews.ps1` — 6개년 제외 후보표 생성
3. **[사람]** 후보표 승인/기각 (0건 연도는 0행 계약 서명만)
4. `scripts\start_full_mfa_after_review.ps1 -ApprovedBy <연구자>` — preflight `GO`면 큐 시작

완료 판정 manifest: 1번 `YEAR_MANIFEST=success` / 4번 연도별
`machine_qc_passed_human_review_pending` (`show_mfa_year_queue_status.ps1`로 확인).
실패 시 재개: 같은 명령 재실행 (shard/temp/DB checkpoint 자동 재사용, full-clean 금지).

## 운영 규칙 (2026-08-01 사용자 확정)

- 6개년 신규 정렬이 기본 축이다 — 검색 선완주를 이유로 MFA를 미루지 않는다.
- 사람 승인은 **2일 1회 승인 창구**로 일괄 처리(제외 승인·표본 검토·파괴적
  작업). 슬롯 사이 기계 작업은 무인 계속.
- 문서 상태기계화 채택: 활성 문서는 README·CURRENT_STATE·RUNBOOK·
  ASSETS_LEDGER 4개로 축소, 전환 작업은 전수 MFA 무인 실행 기간에 수행.

## 금지사항

- 구 2020/2021 정렬 재검토·재사용, MFA phone의 실현 판정 취급
- 근거 없는 기호 읽기 자동 확정, 후보 자동 승인, 검증 전 partial 삭제
- 전수 중 새 파일럿·새 설계 리뷰 개시 (방법 계약 변경 시에만)
- D:\00_RAW 수정, MFA 실행 중 D: 경합 작업

## 정본 링크

- 실행 순서: `docs/decisions/PROPOSAL_prebulk_execution_order_20260801.md` (+본 리뷰 §7)
- 출력 계약: `docs/decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md`
- 검색표 계약: `docs/decisions/DECISION_pre_MFA_combination_search_v3_20260801.md`
- 연도 큐: `docs/decisions/DECISION_incremental_unattended_year_MFA_20260801.md`
- 자산 위치: `docs/ASSETS_LEDGER.md` / 스크립트: `scripts/SCRIPTS_INDEX.md`
