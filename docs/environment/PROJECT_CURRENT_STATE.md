# 프로젝트 현재 상태 정본

최종 갱신: 2026-08-06 KST

이 문서는 지금 유효한 완료·미완료·다음 단계만 기록한다. 2026-08-06 이전의
상세 누적본은
`docs/archive/pre_2022_refresh_20260806/PROJECT_CURRENT_STATE_pre_2022_20260806.md`에
보존한다.

## 연구 목적

```text
형태소·표기상 음운 환경을 CSV/Parquet에서 검색
  → utt_id로 WAV·TextGrid·메타데이터 수집
  → 선별 후보에 KOINA·이어붙이기·wav2vec2 보조 분석
  → 연구자가 음성·TextGrid를 보고 실제 실현 여부 판정
```

MFA/G2P phone은 강제정렬용 분절 보조값이다. 규칙 예상 발음, 사전 발음,
음성에서 실현된 발음과 동일시하지 않는다.

## 현재 연도별 상태

| 연도 | 검색표 | 공통 Jamo r2 MFA·6-tier | 연구자 Gate | 발음 참조 파생층 |
|---:|---|---|---|---|
| 2020 | 완료 | 완료 | Gate B 통과 | occurrence·비교/index 완료, 7-tier 914건 구현 검증 |
| 2021 | 완료 | 완료 | 24/24 승인·다음 연도 Gate 통과 | occurrence·비교/index·7-tier 전수 완료 |
| 2022 | 생성 전 | 시작 전 | 해당 없음 | MFA 뒤 생성 |
| 2023 | 생성 전 | 시작 전 | 해당 없음 | MFA 뒤 생성 |
| 2024 | 생성 전 | 시작 전 | 해당 없음 | MFA 뒤 생성 |
| 2025 | 생성 전 | 시작 전 | 해당 없음 | MFA 뒤 생성 |

## 2020 — 동결 완료

- 공통 Jamo r2 신규 MFA, 6-tier 868,187개, 동반표 4개, 독립 전수 감사,
  DB 표본 24/24, 연구자 표본 24/24를 완료했다.
- Gate B는 16/16 core check, 실패 0, `allow_remaining_years=true`다.
- 보존 DB는 `D:\mfa_tmp\2020\2020.db`다.
- 2020 MFA·export·Gate·검토를 다시 실행하지 않는다.
- 7번째 `pron_reference_utt` 전수 복사는 core 완료 조건이 아니다. 현재
  2세션 914개로 구현 계약이 검증됐으며, 전수 backfill은 다른 MFA와 D: I/O가
  겹치지 않을 때 수행한다.

## 2021 — 생산·연구자 Gate 완료

- `morph_search.v3` 7표와 frozen source contract가 완료됐다.
- MFA 정렬은 2026-08-04 20:53:45 KST에 exit 0으로 끝났다.
- 보존 DB는 `D:\mfa_tmp\2021\2021.db`, checkpoint marker는
  `D:\mfa_eojeol\done\2021.direct_db_ready`다.
- 정렬 당시 pre-MFA 승인 제외는 1,502건이다. post-MFA exact-ID 기술 제외
  535건을 더한 export/QC 회계는 2,037건이다. 삭제가 아니라 후속 회수 대상으로
  보존한다.
- 6-tier·동반표는 1,371,883발화다. 독립 감사 coverage 100%, hard failure 0,
  `spn` 0이며 DB 재수출 표본은 semantic·byte 24/24 일치했다.
- 19개 후행 무음 word 표지는 시간·phone을 유지하고 빈 word label로 국소
  정규화했다. MFA DB·WAV·LAB·원 CSV는 변경하지 않았다.
- 연구자는 1–20번과 21–24번, 총 24개 표본의 WAV·LAB·TextGrid 연결,
  6-tier, 정렬, 검색 정보가 대체로 적절하다고 확인했다. 원 pending CSV를
  바이트 동일 보존한 뒤 명시 승인 문장을 24/24에 기록했다.
- 승인 보고서는 `automatic_approval_performed=false`,
  `materialized_from_explicit_researcher_statement=true`,
  `allow_next_year_mfa=true`다.
- checkpoint-resume mode와 별도 `direct_db_ready` marker를 같은 6-tier 생산
  계약으로 검증한 `2021 → 2022` Gate는 2026-08-06에 실패 검사 0으로 통과했다.
- 우리말샘 occurrence 12,015,453행, 원 표기 어절 비교표 6,610,698행,
  발화 index 1,373,920행을 독립 검증했다.
- 7-tier 파생본은 4,139세션·1,371,883개다. 기존 6개 tier 변경 0,
  `pron_reference_utt` 경계·label 오류 0으로 2026-08-05 21:20 KST에
  독립 전수 검증을 통과했다.
- 2021 MFA·DB·6-tier·7-tier 전수를 다시 실행하지 않는다.

## 2022 — 다음 생산 연도

읽기 전용 준비 inventory의 현재 값은 다음과 같다.

- 승인 제외 1,231건
- LAB marker `passed`
- LAB 2,654세션·866,359행
- alignment contract 없음
- MFA DB 없음

따라서 2022 생산은 아직 시작되지 않았다. 다음 순서는 다음과 같다.

1. 2022 `morph_search.v3`와 source contract를 생성·검증한다.
2. 승인 제외 1,231건과 LAB marker의 input contract를 대조한다.
3. PowerShell 안전·5.1 검사와 해당 wrapper preflight를 통과시킨다.
4. 2022 한 연도만 checkpoint 방식으로 시작한다.

## 2023–2025 준비 상태

승인 제외 계약과 LAB marker input ID는 각 연도에서 일치한다. 어느 연도도 신규
MFA를 시작하지 않았다.

| 연도 | 승인 제외 | LAB 세션 | LAB 행 | 특기 사항 |
|---:|---:|---:|---:|---|
| 2023 | 103,930 | 1,973 | 677,262 | 안전 본체와 후속 회수 shard 분리 유지 |
| 2024 | 1,610 | 3,227 | 728,257 | 직전 연도 Gate 뒤 시작 |
| 2025 | 4,033 | 2,927 | 587,121 | 직전 연도 Gate 뒤 시작 |

## 발음 참조 레이어의 위치

- 참조 정본:
  `D:\10_LAYERS\10_pronunciation_reference\dictionary_pron_registry_v2_20260805`
- 공통 계약: `config/pronunciation_reference_layer_v1.json`
- 사전 후보는 검색·참조용이며 MFA 입력사전을 자동 교체하지 않는다.
- occurrence·비교/index는 각 연도 6-tier 뒤 생성한다.
- 물리적 7-tier backfill은 파생 작업이며 다음 연도 MFA의 새 gate로 만들지 않는다.

## 현재 안전 정지점

- 실행 중인 장시간 작업 없음
- 2020 완료 자산 변경 없음
- 2021 core 및 파생층 완료
- 2021 공식 연구자 승인·`2021 → 2022` Gate 완료
- 2022 MFA 시작 전

현재 허용 작업은 2022 검색표·source contract와 preflight 준비다. 2020·2021
정렬 재실행, 새 발음사전 설계, 새 파일럿, 검증 전 2022 MFA 시작은 허용하지
않는다.

## 정본 문서

- 생산 순서: `docs/RUNBOOK_production_2020_2025.md`
- 발음 참조 파생층: `docs/RUNBOOK_pronunciation_reference_layer_2020_2025.md`
- 자산 위치: `docs/ASSETS_LEDGER.md`
- 상세 시행착오: `docs/WORK_HISTORY_2026-08.md`
- 리밋·새 대화 재개: `docs/environment/CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md`
