# 프로젝트 현재 상태 정본

최종 갱신: 2026-08-01 KST

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
- 2020 `morph_search.v3`: shard 1/23 성공, 41,803발화, 현재 lock 없음.
- workflow reset 반영 뒤 Python 293개 및 PowerShell 안전검사 31개 파일 통과.

## 실제 미완료

- 2020 검색표 shard 2–23과 2021–2025 검색표.
- 2020–2025 신규 r2 MFA 전량.
- 연도별 승인 제외 계약과 2020 생산 표본 연구자 확인.
- 7표+4표 최종 join/Parquet·DuckDB view.
- 우리말샘 1:N 보조표 연결. reference 4종은 2026-07-24 D: 회수 기록이
  있으므로 사용 직전 실물·SHA를 다시 확인한다.

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
contract 생성·검증을 완료했고, 2026-08-01 17:14 KST에 2020
`morph_search.v3` shard 2–23 재개 작업을 시작했다. lock PID 25716,
Python worker PID 13480, 시작 직후 manifest는 `running`, 1/23 재사용 상태다.
이는 MFA 대체가 아니라 2020 MFA 직전 필수 검색·입력 인프라 단계다.

다음 작업은 다음 순서로만 진행한다.

1. 실행 중인 2020 `morph_search.v3` shard 2–23을 완주한다.
2. 2020 승인 제외표만 만들고 연구자가 확인한다.
3. **필수** 2020 MFA→6-tier→4 동반표→독립 QC→생산 표본 검토를 완료한다.
4. 2020 Gate B가 통과한 뒤 **필수** 2021–2025 전 연도 MFA 큐를 연다.

실행 명령은 `docs/RUNBOOK_production_2020_2025.md`만 정본으로 사용한다.

## 활성 정본

- 문서 색인: `docs/README.md`
- 현재 상태: 이 문서
- 생산 실행: `docs/RUNBOOK_production_2020_2025.md`
- 자산 위치: `docs/ASSETS_LEDGER.md`
- 결정 색인: `docs/decisions/_INDEX.md`
- 스크립트 색인: `scripts/SCRIPTS_INDEX.md`
