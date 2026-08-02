# 프로젝트 현재 상태 정본

최종 갱신: 2026-08-02 KST

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

## 실제 미완료

- 2021–2025 검색표.
- 2020–2025 신규 r2 MFA 전량.
- 연도별 승인 제외 계약과 2020 생산 표본 연구자 확인.
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

신규 전수 MFA는 아직 시작하지 않았다. workflow 수정, 전체 시험, 2020 source
contract와 2020 `morph_search.v3` 23/23을 완료했다. 검색은 2026-08-01
17:47 KST에 `status=success`로 끝났고 lock은 정상 해제됐다. 연도 manifest에는
7개 표의 SHA와 row 수, 중복 0, 기호 coverage 일치가 기록됐다.

다음 작업은 다음 순서로만 진행한다.

1. 2020 CSV–WAV 발화 ID 밀림 복구와 전수 재감사: **완료**.
2. 복구 불가·모호 발화만 2020 승인 제외표에 넣고 연구자가 확인한다: **다음**.
3. **필수** 2020 MFA→6-tier→4 동반표→독립 QC→생산 표본 검토를 완료한다.
4. 2020 Gate B가 통과한 뒤 **필수** 2021–2025 전 연도 MFA 큐를 연다.

최초 생성된 14행 검토표는 구형 형태소 TextGrid 누락에 근거해 현행 6-tier와
맞지 않으므로 자동 승인 없이 archive했다. 읽기 전용 음원 복구 계획은 영향
129세션에서 고신뢰 remap 14,221건, 자동판정 보류 92건, 대응 원음 미확인
1,742건을 분리했다. 고신뢰 remap은 짧은·중간·긴 연속 일치 블록에서 서로
다른 6세션의 시작/끝 12건을 뽑아 A=제안 WAV, B=현재 같은 ID WAV로 묶었고,
복사본 24개의 원본 대비 SHA-256을 검증했다. 연구자 청취 결과는 12/12 모두
A 제안 음원이 대상 전사와 일치했다. 이는 층화 표본이 고신뢰 규칙을 지지한다는
근거이며 14,221건 전수 수동 확인으로 표현하지 않는다.

복구 transaction·재개·rollback 계약과 2020 MFA 입력 전용 경로를 구현했다.
실자료 dry-run은 검색 870,437건, 파생 코퍼스 868,603건, 제외 검토 1,834건,
영향 archive 50,777 WAV/3.148 GiB를 확인해 `dry_run_passed`였다. 원 D: WAV는
바뀌지 않았다. 첫 apply는 아래 누락 세션에서 안전 중단됐지만 수정 계약 apply는
완료됐다. 이 계약이 `passed`가 되지 않으면 2020 LAB/제외 후보/MFA 경로가
원본 WAV로 조용히 되돌아가지 않고 fail-closed한다.

첫 apply는 10/129세션 archive 뒤 원음 폴더가 배포본에 없는
`SDRW2000000176`에서 안전 중단됐다. 이 세션 513건은 전부 미해결·제외 대상이며
포함 WAV는 0건이다. 누락 자체를 `verified_absent` manifest로 보존하고 포함
대상이 있으면 중단하는 새 계약으로 수정·시험했다. 구 계약의 E: ZIP 10개는
실패 근거로 보존하며, D: 원본과 최종 파생 코퍼스에는 변경이 없다.

수정 apply는 contract ID `eb64f80d9106…`로 완료됐다. 독립 파일 계수도
868,603/868,603이었고 lock은 해제됐다. 2020 MFA resolver는 원 `03_wav`가
아니라 복구 파생 root를 선택한다. 현재 다음 단계는 복구 불가·모호 1,834건의
2020 승인 제외 후보표를 생성하는 것이다. 아직 MFA 정렬은 시작하지 않았다.

검토 묶음:
`outputs/2020_wav_id_recovery_review_20260802/00_READ_ME_FIRST.md`

실행 명령은 `docs/RUNBOOK_production_2020_2025.md`만 정본으로 사용한다.

## 활성 정본

- 문서 색인: `docs/README.md`
- 현재 상태: 이 문서
- 생산 실행: `docs/RUNBOOK_production_2020_2025.md`
- 자산 위치: `docs/ASSETS_LEDGER.md`
- 결정 색인: `docs/decisions/_INDEX.md`
- 스크립트 색인: `scripts/SCRIPTS_INDEX.md`
