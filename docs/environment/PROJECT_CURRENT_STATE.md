# 프로젝트 현재 상태 정본

최종 갱신: 2026-08-07 KST

> **2026-08-07 발음 입력 Gate 보정:** 2022 공식 표본에서 `있지·있는·없는·
> 어쨌든` 등의 MFA 입력 phone이 기존 규칙 예상형과 불일치함을 확인했다. 전수
> 감사 결과 이 문제는 특정 연도나 표본 파일만의 문제가 아니므로 r2 신규 실행을
> 차단했다. 아래 2020–2022의 “완료”는 r2 계산·자료구조·감사 증거의 완료를
> 뜻하며 최종 공통발음 정본 승인을 뜻하지 않는다. r3 채택 뒤 2020–2022는
> 발음이 달라진 화자/세션 단위만 재정렬하고, 동일 단위는 동등성 증명으로
> 재사용한다. 2023–2025는 같은 r3 계약으로 최초 정렬한다.

> 2026-08-07 18:02 보정: 2022 MFA 계산과 보존 DB direct export, 연구용 6-tier
> 864,690개, gzip 동반표 4종, 독립 전수 감사와 DB 재수출 24/24 동등성 검사가
> 완료됐다. 남은 core 단계는 공식 연구자 인프라 표본 24개의 한 번의 Gate뿐이다.
> 연구자가 표본에서 발견한 겹침·잘림 의심·소음 문제는 2020–2025 공통 품질
> 감사로 확장했다. 정렬 가능한 발화는 데이터 구축을 위해 보존하고 승인된 연구
> 주 분석 제외만 `analysis_only`로 붙인다. 이 품질 결정 자체는 유지하되,
> 발음 입력 r3가 채택되면 2020–2022의 영향 세션만 다시 정렬하고 2023–2025는
> 같은 품질 Gate를 정렬 전·후에 적용한다. 근거는
> `docs/decisions/DECISION_dialogue_audio_quality_gate_2020_2025_20260807.md`와
> `outputs/reviews/dialogue_audio_quality_2020_2025_20260807/`에 있다.

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

| 연도 | 검색표 | r2 계산·6-tier 보존 | 연구자 검토 | r3 최종 정렬 |
|---:|---|---|---|---|
| 2020 | 완료 | 읽기 전용 증거로 완료 | Gate B 검토 재사용 | r3 영향 세션만 재정렬 |
| 2021 | 완료 | 읽기 전용 증거로 완료 | 24/24 검토 재사용 | r3 영향 세션만 재정렬 |
| 2022 | 완료 | 읽기 전용 증거로 완료 | 24개 검토·발음 문제 발견 | r3 영향 세션만 재정렬 |
| 2023 | 생성 전 | 시작 금지 | 해당 없음 | r3 채택 뒤 시작 |
| 2024 | 생성 전 | 시작 금지 | 해당 없음 | r3 채택 뒤 시작 |
| 2025 | 생성 전 | 시작 금지 | 해당 없음 | r3 채택 뒤 시작 |

## 2020 — r2 계산·검토 완료, 읽기 전용 보존

- 공통 Jamo r2 신규 MFA, 6-tier 868,187개, 동반표 4개, 독립 전수 감사,
  DB 표본 24/24, 연구자 표본 24/24를 완료했다.
- Gate B는 16/16 core check, 실패 0, `allow_remaining_years=true`다.
- 보존 DB는 `D:\mfa_tmp\2020\2020.db`다.
- r2 MFA·export·광범위 Gate·검토를 같은 조건으로 반복하지 않는다. r3 채택 뒤에는
  같은 사람 검토를 재사용하고 정렬 계산만 새 6개년 계약으로 수행한다.
- 7번째 `pron_reference_utt` 전수 복사는 core 완료 조건이 아니다. 현재
  2세션 914개로 구현 계약이 검증됐으며, 전수 backfill은 다른 MFA와 D: I/O가
  겹치지 않을 때 수행한다.

## 2021 — r2 생산·연구자 Gate 완료, 읽기 전용 보존

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
- r2 산출을 같은 조건으로 반복하지 않는다. r3 채택 뒤 정렬·6-tier·동반표는 새
  release root에 만들고, 기존 7-tier와 검토 결과는 회귀·비교 근거로 보존한다.

## 2022 — r2 MFA·6-tier·기계 QC 완료, 발음 입력 문제 발견

- search master와 source/input/alignment 계약은 완료됐다.
- 활성 LAB 865,128개 중 864,690개가 정렬됐고 438개는 최종 interval이 없는
  `mfa_alignment_missing` exact-ID 집합이다.
- 보존 DB는 `D:\mfa_tmp\2022\2022.db`이며 r2 증거로 변경하지 않는다. r3 채택
  뒤 별도 DB·release root에서 다시 정렬한다.
- 연구자는 20개 연결 표본의 WAV·LAB를 확인했다. 그 과정에서 겹침·잘림 의심·
  심한 소음을 발견해 2020–2025 공통 품질 감사로 확장했다.
- 연구자는 2026-08-07 15:04 KST에 438건을
  `mfa_alignment_missing / alignment_and_analysis`로 명시 승인했다. 원 pending
  작업본은 SHA-256 동일 archive로 보존했고, candidate identity는
  `36912d5d3802...`로 유지됐다.
- 결합 승인 preflight는 기존 1,231건 + post-MFA 438건 = 1,669건 exact-ID
  일치, DB 무변경, 출력 생성 0으로 통과했다.
- 보존 DB direct export는 2026-08-07 17:28 KST에 완료됐다. 연구용 6-tier
  864,690개, coverage 100%, `spn` 0, 정확 ID 대사 `passed`이며 1,669개 제외는
  별도 동반표에 보존했다. gzip 동반표는 발화 864,690행, 어절 7,039,920행,
  phone 26,372,701행, 제외 1,669행이다.
- 독립 전수 감사는 hard failure 20범주가 모두 0으로 통과했다. 보존 DB에서 다시
  내보낸 24세션·24발화 표본은 최종 TextGrid와 semantic·byte 모두 24/24
  일치했다. 실행 queue는
  `mfa_r2_prod_safe_body_2022_20260806_postmfa`이며 DB는 계속 보존한다.
- 공식 연구자 표본 24개를
  `outputs/reviews/mfa_production_2022_mfa_r2_prod_safe_body_2022_20260806_postmfa`
  에 준비했고 연구자가 24개 모두의 연결·정렬·6-tier·검색 정보를 확인했다.
  이 검토에서 발견한 공통발음 입력 불일치를 r3 Gate의 회귀 표본으로 재사용한다.
  실제 음운 실현 판정은 이 인프라 Gate의 대상이 아니다.

## 2023–2025 준비 상태

승인 제외 계약과 LAB marker input ID는 각 연도에서 일치한다. 어느 연도도 신규
MFA를 시작하지 않았다. 2022에서 발견한 음원 품질 문제를 반영하기 위해 동일한
구조 감사·음향 표본·`<=44B` 전수 inventory를 이미 2023–2025에도 적용했다.

| 연도 | 승인 제외 | LAB 세션 | LAB 행 | 특기 사항 |
|---:|---:|---:|---:|---|
| 2023 | 103,930 | 1,973 | 677,262 | header-only 75건 모두 기존 승인 포함; 안전 본체 유지 |
| 2024 | 1,610 | 3,227 | 728,257 | 직전 연도 Gate 뒤 시작 |
| 2025 | 4,033 | 2,927 | 587,121 | 직전 연도 Gate 뒤 시작 |

## 발음 참조 레이어의 위치

- 참조 정본:
  `D:\10_LAYERS\10_pronunciation_reference\dictionary_pron_registry_v2_20260805`
- 구 진단 계약: `config/pronunciation_reference_layer_v1.json`
- 사전 후보는 검색·참조용이며 MFA 입력사전을 자동 교체하지 않는다.
- 이 분리가 r2 입력 배선 공백을 만들었으므로 v1 occurrence·비교/index·7-tier를
  더 생성하지 않는다. 이미 만든 2020–2021 자료는 r3 근거로 재사용한다.
- r3 정본은 `config/common_pronunciation_resource_contract_v3_draft.json`을
  채택 계약으로 승격한 뒤 canonical 선택표와 MFA 사전을 같은 projection으로 낸다.

## 현재 안전 정지점

- 실행 중인 장시간 작업 없음
- 2020 완료 자산 변경 없음
- 2021 core 및 파생층 완료
- 2021 공식 연구자 승인·`2021 → 2022` Gate 완료
- 2022 MFA·6-tier·동반표·독립 기계 QC 완료
- 2022 post-MFA 438건과 결합 제외 1,669건의 승인·회계 완료
- 2022 공식 연구자 인프라 표본 24개 검토 완료·발음 입력 불일치 발견
- r2 프로젝트 발음 release Gate 차단 완료
- r3 canonical inventory 881,237형 생성 완료
- exact Roman 표면 donor 후보 346형 생성 완료(아직 최종 선택 아님)
- 규칙 목표형 Jamo G2P 대상 310,605개를 13 shard로 준비 완료
- r3 G2P 장시간 실행은 아직 시작하지 않았고 TextGrid 변경도 없음

현재 허용 작업은 r3 G2P 후보를 재개 가능한 shard로 생성하고, 독립 규칙 Roman과
정확히 일치하는 후보만 canonical 선택표에 승격한 뒤 사전 projection·자동 회귀·
adoption Gate를 구현하는 것이다. G2P 1-best 자체는 정답이나 최종 선택이 아니다.
새 광범위 사람 파일럿과 r2 재실행은 허용하지 않는다.
2023은 r3 release가 채택되고 프로젝트 발음 Gate가 열린 뒤에만 시작한다. 이후
2020–2022는 영향 세션 delta, 2023–2025는 최초 전수 정렬로 순차 진행한다.

## 정본 문서

- 생산 순서: `docs/RUNBOOK_production_2020_2025.md`
- 발음 참조 파생층: `docs/RUNBOOK_pronunciation_reference_layer_2020_2025.md`
- 자산 위치: `docs/ASSETS_LEDGER.md`
- 상세 시행착오: `docs/WORK_HISTORY_2026-08.md`
- r3 후보 선택 결정:
  `docs/decisions/DECISION_common_pron_r3_candidate_resolution_20260807.md`
- 리밋·새 대화 재개: `docs/environment/CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md`
