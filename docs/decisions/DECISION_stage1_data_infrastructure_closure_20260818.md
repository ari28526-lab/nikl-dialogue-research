# 자료구축 1단계 공식 종료 결정

작성일: 2026-08-18 KST
기록 근거: 연구자 `ari30`의 세션 지시("자료구축 단계를 체계적·완결적으로
마무리하고 다음 단계를 설계해 기록하라", 2026-08-18)에 따라 기록한다.

## 결정

2020–2025년 6개년 자료구축 인프라 단계(1단계)를 **공식 종료**한다. 이후
저장소의 신규 작업은 본 결정과 같은 날 채택된
`PLAN_stage2_target_query_and_realization_design_20260818.md`(2단계 설계)의
Gate 순서만 따른다. 1단계 산출물(RC0/RC1/active view/6-tier/검색층)은 동결
정본이며, 2단계에서 이를 수정하지 않고 참조·파생만 한다.

## 종료 범위 (완료된 것)

closeout 정본과 독립 감사(전부 `passed`)가 확인한 다음 7건이다.

1. 원천 5,103,356발화의 누락·중복·미분류 0 exact-ID 상태 회계 (RC0)
2. 동일 `common_pron_mfa_r3_20260809` 계약의 2020–2025 fresh realign
3. 4,286,046발화 6-tier TextGrid 수출과 독립 QC
4. 기술 98,946 + 발음 718,364 후속의 삭제 없는 이유별 장부 (합 817,310)
5. 6개년 검색층 5,103,356발화·50,955,891 형태소 token (`morph_search.v3`)
6. RC1 append-only 수동 보정(55행 상태·16행 curated pointer)과
   active view 계약 (본체 정렬 delta 0)
7. 후보→WAV/TextGrid→어절 문맥 시간 연결의 소표본 검증
   (manifest 22행·link 19건, 독립 감사 통과)

문서화 산출물로 closeout 해설 6종
(`docs/releases/20260818_six_year_infrastructure_closeout/`)과 외부 공개용
HTML 보고서(`qmd/six_year_infrastructure_report_20260818.qmd` →
`outputs/reports/six_year_infrastructure_report_20260818.html`, 커밋
`8ff42a8`, 수량 20항목 프로그램 재검증 통과)가 본선에 반영됐다.

## 결속 근거 (machine-readable)

- `outputs/reports/SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json`
  (sha256 `53a9af1d…f054beb3`)
- `outputs/reports/AUDIT_six_year_infrastructure_closeout_20260818.json`
  (status `passed`, 12검사 전부 통과)
- RC0 `QA_REPORT.json` (hard failure 9종 전부 0)
- RC1 `ACCOUNTING.json` (`passed_append_only_no_base_category_delta`)
- `AUDIT_db_v1_active_view_contract_20260818.json`
- `AUDIT_db_v1_target_manifest_pilot_20260818.json` ·
  `AUDIT_db_v1_target_interval_link_pilot_20260818.json`

## 이 종료가 승인하지 않는 것

1단계 종료는 다음의 실행 승인이 아니다. 각각 2단계의 별도 Gate에서만 연다.

- 6개년 production target query 실행
  (`APPROVAL_n_insertion_B1_revision_20260818.json`의 `not_authorized` 유지)
- 잔여 recovery inventory 817,255건의 대량 회수·MFA 재실행
- RC1 16건의 전면 형태소·phone enrichment
- KOINA·wav2vec2/HuBERT 전수 실행
- 원자료·RC0·RC1·6-tier·보존 DB의 어떤 수정

## 잔여 항목의 라우팅 (미해결로 남기되 소속을 확정)

| 잔여 항목 | 라우팅 |
|---|---|
| recovery 817,255건 | 2단계 G8: 실제 후보에 포함된 exact-ID만 표적 회수 |
| RC1 16건 형태소·phone pending | 2단계 G8: 표적 포함 시 exact-ID 단위 enrichment Gate |
| 의미번호 production join | 2단계 G2 계약으로 승격 |
| `work/` 대형 정리 후보 (~1.5 GiB) | `CLEANUP_LEDGER.md`의 별도 cleanup Gate (2단계 아님) |
| `main` 브랜치 동기화 (agent 본선과 약 300커밋 차이) | 운영 결정, 공개(GitHub Pages 등) 시점에 별도 처리 |
| 문헌 폴더 정비 (중복·미상 14건 등) | 별개 문헌 관리 트랙 (`claude/GitHub_Dropbox_연동_지침.md`) |

## 재실행 금지 재확인

1단계 종료 후에도 다음은 재실행하지 않는다: 2020–2025 r3 MFA와 전수 6-tier
export/QC, 계약 불변 파일럿의 반복, 같은 입력·설정의 실패 exact-ID 무한
재시도, RC0/RC1 기본 회계의 즉석 수동 편집.
