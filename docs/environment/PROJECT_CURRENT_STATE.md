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

## 실제 미완료

- 2021–2025 검색표.
- 2020 미정렬 363건 중 청취 불가 3건은 `audio_unusable`로 승인 기록했다.
  나머지 360건의 범주 결정 뒤 6-tier·동반표·독립 QC를 수행한다.
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

2020 전수 MFA 계산은 완료됐고 DB는 보존됐다. 16표본 WAV·LAB·동결 CSV 연결
QC도 완료됐다. 연구자는 13개를 `match`, 소리가 들리지 않는 3개를
`audio_unusable`로 판정했다. 이 검토는 실제 음운 실현 판정이 아니라
post-MFA 인프라 QC다.

수정 전달본은
`C:\Users\ari30\Dropbox\MFA_2020_REVIEW_SIMPLE_V2_20260803`이다. 검토본에만
WAV 좌우 0.05초 무음을 붙이고 모든 6개 tier에 같은 좌우 경계를 넣었다.
Python 그림 감사에서 4/4 TextGrid × 6/6 tier가 통과했다. 생산 DB와 원음은
변경하지 않았다.

또한 생산 전수 문제 여부를 확인하기 위해 보존 DB의 정렬 성공 868,187발화를
읽기 전용 전수 감사했다. word와 phone의 바깥 발화 시작·끝은
868,187/868,187(100%) 일치했다. 파일마다 자연 무음의 유무가 다른 것은 원음
차이이며, 생산 TextGrid는 source time을 유지한다. 전수 6-tier 실물은 아직
export 전이므로 잘못 생성된 전수본을 고치는 상황도 아니다.

다음 순서만 유지한다.

1. 청취 불가 3건 승인 기록을 유지하고 나머지 미정렬 360건의 범주를 확정한다.
2. 보존 DB에서 2020 6-tier·동반표·독립 QC·생산 표본 확인을 마친다.
3. 2020 Gate B 뒤 2021–2025 연도별 큐를 연다.

검토 묶음과 전수 경계 감사는 DB를 읽기 전용으로 수행했고, 생성 전후 DB 크기와
mtime이 같았다. 2021 gate는 아직 열지 않았다. 상세 과정은
`docs/WORK_HISTORY_2026-08.md`에 보존한다. 실행 명령은
`docs/RUNBOOK_production_2020_2025.md`만 정본으로 사용한다.

## 활성 정본

- 문서 색인: `docs/README.md`
- 현재 상태: 이 문서
- 생산 실행: `docs/RUNBOOK_production_2020_2025.md`
- 자산 위치: `docs/ASSETS_LEDGER.md`
- 결정 색인: `docs/decisions/_INDEX.md`
- 스크립트 색인: `scripts/SCRIPTS_INDEX.md`
