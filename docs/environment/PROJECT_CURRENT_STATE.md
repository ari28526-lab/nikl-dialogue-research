# 프로젝트 현재 상태 정본

최종 갱신: 2026-08-03 KST

이 문서는 append-only 일지가 아니다. 현재 상태가 바뀌면 전체를 교체한다.
이전 전체본은 `docs/archive/PROJECT_CURRENT_STATE_20260801_full.md`에 보존한다.

## 연구 목적

```text
형태소·표기상 음운 환경을 CSV/Parquet에서 검색
  → utt_id로 WAV·TextGrid·메타데이터 수집
  → 선별 후보에만 KOINA·이어붙이기·wav2vec2 보조 분석
  → 연구자가 음성·TextGrid를 보고 실제 실현 여부 판정
```

MFA/G2P phone은 강제정렬을 위한 대략적인 분절 보조값이다. 실제 실현 판정,
음소 전사 정답, 음운론적 분석 결과로 취급하지 않는다.

## 동결된 생산 계약

- 2020–2025를 모두 공통 Jamo r2 기준으로 새로 정렬한다. 구 2020/2021
  정렬은 최종 산출물로 재사용하지 않는다.
- 발음·모델: `common_pron_mfa_r2_20260728`, Korean MFA acoustic v3.3.0,
  Jamo G2P v3.2.0, 연구자 승인 예외 27건. phone 기준은 6개년 동일하다.
- 기본 TextGrid는 6-tier다:
  `words / phones_mfa / phoneme_r_auto / utterance / utterance_orth_r /
  morph_analysis_utt`.
- 모든 tier는 0–xmax를 연속적으로 덮는다. `morph_analysis_utt`는 발화 수준
  형태소 정보이며 형태소 경계를 음향 시간경계라고 주장하지 않는다.
- pre-MFA 검색층은 `morph_search.v3` 연도별 7표, post-MFA 동반층은
  연도별 gzip 4표다. 원자료 좌표, 형태소 좌표, MFA 좌표를 섞지 않는다.
- 우리말샘 1:N 발음은 후속 보조 검색표다. MFA 사전 발음을 자동 교체하지 않는다.
- KOINA, stitch, wav2vec2는 선별 후보에만 추가하며 MFA 열을 덮어쓰지 않는다.
  이어붙인 seam을 가로질러 운율을 해석하지 않는다.
- 이 계약은 최종 점검 슬라이드
  `outputs/presentations/MFA_research_infrastructure_final_prebulk_20260801.pptx`
  및 PDF와 일치해야 한다.

## 실측 완료

- 동결 pre-MFA search master: 2020–2025, 5,103,356발화,
  `_build_meta.status=success`.
- 공통 Jamo r2 release/adoption: `passed`, `allow_yearly_mfa=true`.
- 6-tier exporter, 동반표, DB checkpoint, 독립 연도 감사, DB 표본 재수출,
  승인 제외 계약, 연도 큐 구현.
- 2020 `morph_search.v3`: 23/23 성공, 870,437발화, 7개 연도표 생성,
  중복 0·기호 coverage 일치·현재 lock 없음.
- workflow reset과 음원 대응 gate·복구 코퍼스 계약 반영 뒤 Python 304개 및
  PowerShell 안전검사 34개 파일 통과.
- 2020 공통 Jamo r2 신규 MFA 계산 완료. active 868,550발화 중 868,187발화에
  word+phone interval이 있고 363발화는 post-MFA 미정렬이다. 보존 DB는
  `D:\mfa_tmp\2020\2020.db`, checkpoint marker는
  `D:\mfa_eojeol\done\2020.direct_db_ready`다.
- 2020 결합 제외 계약 2,250건을 확정했다. pre-MFA 1,887건과 보존 DB의 정확한
  post-MFA 미정렬 ID 363건(청취 불가 3 + `mfa_alignment_missing` 360)을
  결합했으며, 전수 MFA 재실행 없이 같은 DB에서 export하도록 동결했다.
- 2020 최종 6-tier 868,187개와 동반표를 보존 DB에서 export했다. 독립 전수 감사와
  DB 재생성 표본 24/24 semantic·byte exact-match를 통과했다.
- 연구자가 24개 생산 표본에서 WAV·LAB·TextGrid 동일 발화, 정렬의 전반적 타당성,
  6개 tier 및 검색 정보의 이해 가능성을 확인했다. 이는 인프라 QC이며 실제 음운
  실현 판정은 수행하지 않았다.
- 2020 Gate B는 2026-08-03에 16/16 core check, 실패 0으로 `passed`였으며
  `allow_remaining_years=true`다.

## 실제 미완료

- 2021–2025 검색표.
- 2021–2025 신규 r2 MFA와 연도별 승인 제외 계약.
- 7표+4표 최종 join/Parquet·DuckDB view.
- 우리말샘 1:N 보조표 연결. reference 4종은 2026-07-24 D: 회수 기록이
  있으므로 사용 직전 실물·SHA를 다시 확인한다.

2020 CSV–WAV 복구는 더 이상 미완료 항목이 아니다. 2026-08-02 10:24 KST에
파생 WAV 868,603건, E: ZIP 128개+누락 manifest 1개, 제외 이월 1,834건으로
최종 계약이 `passed`였다.

## workflow reset 판정

- 외부 리뷰 원문은 보존했다.
- 최종 판정은 `GO AFTER SMALL WORKFLOW FIXES`다. 원문 리뷰의
  “코드 수정 없이 GO”는 2020-only 범위와 Gate B가 기본 큐에 연결되지 않은
  사실 때문에 수정했다.
- 폐지: 구 4-tier 60행 잔여 검토, 12발화 utterance_search 재검토,
  5-tier phoneme 수용 검토, difference inventory 반복.
- 통합: 6-tier mini pilot 육안 검토는 2020 첫 생산 표본 검토에 흡수한다.
- 새 파일럿·설계 리뷰는 생산 계약이 실제로 바뀔 때만 다시 연다.

## 현재 안전 정지점

2020 신규 정렬·6-tier export·동반표·독립 감사·24개 생산 표본 연구자 확인·
Gate B가 모두 완료됐다. 최종 TextGrid는
`D:\20_AUDIO\08_textgrid_research_v2_staging\2020`의 868,187개다. 동반표는
utterance 868,187, word 4,973,795, phone 19,101,192, excluded 2,250행이며,
독립 감사의 하드 실패는 0이다. Gate B 보고서는
`outputs/reports/GATE_B_2020_TO_2021.json`, core 보고서는
`outputs/reports/GATE_B_2020_core.json`이다.

연구자는 공식 24개 표본을 모두 검토해 같은 발화, 정렬 대체로 맞음, 6개 tier
정상, 검색 정보 이해 가능으로 승인했다. 승인 기록은
`outputs/reviews/mfa_production_2020_mfa_r2_prod_2020_export_20260803/04_RESEARCHER_APPROVAL.json`이며
`allow_next_year_mfa=true`, `realization_judgment_performed=false`다.

육안상 일부 경계가 없어 보인 네 표본도 실제 TextGrid 값을 확인했다. 모든 tier는
빈 interval을 포함해 0–xmax를 연속적으로 덮고, 세 검색 tier의 유표 span은
`words`의 유표 span과 정확히 같다. 발화 시작·끝이 파일의 0초 또는 xmax와
일치하면 Praat에서 별도 내부 세로선이 보이지 않을 뿐이다. 이는 시간정보 손실이나
검색 결함이 아니다. 생산 source time과 파일 가장자리 경계를 유지하며 인공 내부
경계를 추가하지 않는다.

현재 안전 정지점은 **2020 Gate B 통과, 2021 미시작**이다. 다음 실행은 별도 사용자
지시 뒤 2021의 연도별 입력·제외 계약 preflight부터 시작한다. 상세 과정은
`docs/WORK_HISTORY_2026-08.md`, 실행 명령은
`docs/RUNBOOK_production_2020_2025.md`만 정본으로 사용한다.

## 활성 정본

- 문서 색인: `docs/README.md`
- 현재 상태: 이 문서
- 생산 실행: `docs/RUNBOOK_production_2020_2025.md`
- 자산 위치: `docs/ASSETS_LEDGER.md`
- 결정 색인: `docs/decisions/_INDEX.md`
- 스크립트 색인: `scripts/SCRIPTS_INDEX.md`
