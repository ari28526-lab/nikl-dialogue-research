# 프로젝트 현재 상태 정본

최종 갱신: 2026-08-13 KST

> **2026-08-13 2023 r3 정렬·수출·독립 QC 완료:** 2023 exact-ID 입력
> 494,580건을 2020–2022와 같은 `common_pron_mfa_r3_20260809` 계약으로 새로
> 정렬했다. 보존 DB SHA-256은
> `3c6695ac2033612d514e6ca57711d006d2505c6ddb25124b666865df8c315108`이며,
> 성공 494,228건과 기술 미정렬 352건을 exact-ID로 완전 회계했다. 연구자
> `ari30`이 candidate `e6716a369412...eb878b3b`를 명시 승인했고, 6-tier
> 494,228개와 gzip 동반표 4종을 수출했다. 독립 전수 QC는 coverage 100%·hard
> failure 0, 보존 DB 재수출 semantic·byte 24/24로 `passed`다. 2020–2023은
> 재실행하지 않는다. D: 여유가 48.604 GiB뿐이므로 다음 한 단계는 삭제 없는
> **2020–2023 r3 temp 용량 inventory**다. 예상 회수량을 승인·정리해 2024
> capacity Gate를 만족한 뒤, 완료 SHA를 입력으로 2023→2024 전환 Gate를 연다.
>
> **2026-08-12 2022 r3 정렬·수출·독립 QC 완료:** 2020·2021 완료 SHA를
> 변경하지 않고 2022 exact-ID 751,721건을 동일 r3 계약으로 새로 정렬했다.
> `ALIGN_DONE_2022.json`은 2026-08-11 21:41 KST에 `passed`로 생성됐고,
> DB 7,146,942,464 bytes의 SHA-256은
> `610054531403f0ca13292194b13f6e63e509434435864aec9f7118d888bfe5b2`다.
> 정렬 성공 751,383건과 기술 미정렬 338건을 exact-ID로 완전 회계했으며,
> 연구자 `ari30`이 candidate `272bcc134776...3b2357b7a`를 명시 승인했다.
> 2026-08-11 23:36–2026-08-12 01:12 KST에 6-tier 751,383개와 gzip 동반표
> 4종을 수출했다. 독립 QC는 TextGrid coverage 100%·hard failure 0,
> 동반표 계약 오류 0, DB 재수출 semantic·byte 24/24로 완료됐다. 최종
> `QC_STATE.json`은 `passed`다. 2022 r3 MFA·전수 수출·QC는 다시 실행하지
> 않는다. 이 완료 SHA는 통과한 2022→2023 전환 Gate에 결속됐다.

> **2026-08-11 2021 r3 정렬·수출·독립 QC 완료:** 2020 최종 QC state와 정렬
> marker의 SHA를 동결한 채 2020 MFA·전수 수출을 반복하지 않았다. 2021 r3 입력
> 1,207,299건은 4,139세션의 WAV/LAB로 materialize됐고, 같은 exact-ID 수의 보존
> DB가 2026-08-11 00:19 KST에 완료됐다. DB SHA-256은
> `faaef1c2f7c8dd013f7e90dc1694d6514e9b5bdf8fdbe0e60b07d179925a7731`이다.
> word·phone 정렬 성공은 1,206,862건, post-MFA 후보는 437건
> (`mfa_alignment_missing` 413, feature 생성 실패 24)이다. 후보 identity
> `5a4c3de672f...be6a7be35`는 자동 승인하지 않았으며, 연구자가 08:16 KST에 명시
> 승인했다. feature 실패 24와 DB 내 미정렬 413을 분리한 exact-ID preflight가
> 미승인 차이 0으로 통과했다. 08:30–11:00 KST에 6-tier 1,206,862개와 gzip
> 동반표 4개를 수출했다. 동반표는 발화 1,206,862·word 8,926,793·phone
> 32,776,584·제외 437행이며 `spn`은 0이다. 이어 11:05–11:58 KST에 독립 QC를
> 완료했다. 전수 coverage 100%·hard failure 0, 보존 DB 재수출은 semantic·byte
> 24/24이고 최종 `QC_STATE.json`은 `passed`다. 원자료 변경·MFA 재계산·전수
> 수출 반복은 모두 없었다. 이 state의 SHA는 2021→2022 전환 Gate에 고정됐고,
> 이후 2022 완료 결과는 바로 위 최신 state가 대체한다.

> **2026-08-09 r3 2020 정렬 DB 완료·export 직전 상태:** 2020 exact-ID 입력은
> 782,715발화이며 alignment contract ID는
> `3eff5ae34eb1015c05532140162636609099f1fd1203f561cc06d837039d8e8a`다.
> production Gate 승인 뒤, r3 발음 유형표가 연도별 발화·참조 어절 CSV에 직접
> 연결되지 않은 마지막 DB 공백을 MFA 전에 발견했다. 원 형태소 CSV를 덮어쓰지
> 않고 type catalog–utterance scope–reference-eojeol occurrence의 정규화 DB와
> 독립 감사를 추가했다. 보강된 runner는 이 감사가 없으면 NO-GO한다.
> 2020 정규화 DB는 발화 870,437개·참조 어절 3,056,807개를 전수 회계해 독립
> 감사 `passed`를 받았다. r3 MFA DB도 완료되어 782,432건은 word+phone 정렬,
> 283건은 기술적 `mfa_alignment_missing` exact-ID 후속 대상으로 동결됐다.
> 연구자가 2026-08-10에 이 범주를 명시 승인했고, 실제 수출 preflight도 모든
> exact-ID 차이 0·`spn` 0·phone inventory 밖 0으로 통과했다. 이어 보존 DB에서
> 6-tier 782,432개와 gzip 동반표 4개를 수출했다. 완료 감사에서 coverage 100%,
> 실패·누락·partial 0, 동반표 SHA 4/4 일치를 확인했다. MFA DB는 재계산하지
> 않았다. 독립 연도 내용·계약 QC도 2026-08-10에 완료됐다. 782,432개 전수 감사는
> coverage 100%·hard failure 25범주 전부 0이며, 보존 DB 24세션 재수출은
> semantic·byte 24/24 동일하다. 표본 검사 첫 호출의 r3 input-ID 호환 오류는
> source 변경 없이 수정했고, 통과한 25분 전수 감사 checkpoint를 재사용해 표본만
> 55.524초에 재개했다. MFA·전수 수출은 반복하지 않았다. 다음 단계는 2020을
> 동결하고 2021 한 연도만 같은 r3 계약으로 준비하는 것이다.

> **2026-08-07 발음 입력 Gate 보정:** 2022 공식 표본에서 `있지·있는·없는·
> 어쨌든` 등의 MFA 입력 phone이 기존 규칙 예상형과 불일치함을 확인했다. 전수
> 감사 결과 이 문제는 특정 연도나 표본 파일만의 문제가 아니므로 r2 신규 실행을
> 차단했다. 아래 2020–2022의 “완료”는 r2 계산·자료구조·감사 증거의 완료를
> 뜻하며 최종 공통발음 정본 승인을 뜻하지 않는다. 연구자는 2026-08-09에
> 2020–2025 pronunciation-safe pool의 정렬 가능 발화 전체를 동일 r3 계약으로
> 새로 정렬하고, 기술적 제외는 exact-ID로 별도 회계하며 기존 r2 interval은
> 최종 r3에 재사용하지 않는 방안을 승인했다. 718,364 follow-up 발화는 별도
> exact-ID shard로 보존한다.

> 2026-08-07 18:02 보정: 2022 MFA 계산과 보존 DB direct export, 연구용 6-tier
> 864,690개, gzip 동반표 4종, 독립 전수 감사와 DB 재수출 24/24 동등성 검사가
> 완료됐다. 남은 core 단계는 공식 연구자 인프라 표본 24개의 한 번의 Gate뿐이다.
> 연구자가 표본에서 발견한 겹침·잘림 의심·소음 문제는 2020–2025 공통 품질
> 감사로 확장했다. 정렬 가능한 발화는 데이터 구축을 위해 보존하고 승인된 연구
> 주 분석 제외만 `analysis_only`로 붙인다. 이 품질 결정 자체는 유지하되,
> 발음 입력 r3가 채택되면 2020–2025 pronunciation-safe 중 정렬 가능 집합 전체를
> 다시 정렬하고 같은 품질
> Gate를 정렬 전·후에 적용한다. 근거는
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
| 2020 | 완료 | 읽기 전용 증거로 완료 | Gate B 검토를 회귀 근거로 보존 | r3 DB·283 승인·6-tier 782,432·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |
| 2021 | 완료 | 읽기 전용 증거로 완료 | 24/24 검토를 회귀 근거로 보존 | r3 DB·437 승인·6-tier 1,206,862·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |
| 2022 | 완료 | 읽기 전용 증거로 완료 | 기존 24개 검토를 회귀 근거로 보존 | r3 DB·338 승인·6-tier 751,383·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |
| 2023 | 완료 | r2 생산 없음 | 기술 후보 352건 명시 승인 | r3 DB·352 승인·6-tier 494,228·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |
| 2024 | 완료 | r2 생산 없음 | 해당 없음 | pron-safe 595,743; 교집합 산정 대기 |
| 2025 | 완료 | r2 생산 없음 | 해당 없음 | pron-safe 461,643; 교집합 산정 대기 |

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

## 2021 — r3 신규 정렬·6-tier·독립 QC 완료

- r3 exact-ID 입력 1,207,299건과 DB 발화 1,207,299건이 일치한다.
- 1,206,862건은 word·phone interval이 모두 있고, 437건은 기술적 후속 후보로
  동결됐다. 후보는 정렬 없음 413건과 feature 생성 실패 24건이다.
- `ALIGN_DONE_2021.json`은 `status=passed`이며 DB 경로·bytes·SHA를 고정한다.
- 연구자는 437건을 명시 승인했고, feature 실패 24·DB 내 미정렬 413을 분리한
  preflight가 통과했다. 보존 DB에서 6-tier 1,206,862개와 동반표 4개를 수출했다.
  독립 전수 감사 coverage는 100%, hard failure는 0이고, DB 재수출은
  semantic·byte 24/24다. 최종 `QC_STATE.json`은 `passed`다.
- 2021 r3 MFA·전수 수출·QC는 다시 실행하지 않는다. 2020 변경도 금지한다.
  2021 완료 SHA를 이용한 2021→2022 r3 전환 Gate는 통과했다.
- 상세 근거:
  `docs/decisions/RESULT_mfa_r3_alignment_database_2021_20260811.md`

## 2022 — r3 신규 정렬·6-tier·독립 QC 완료, SHA 동결

- r3 source snapshot·입력 계약·발음 연구 DB·alignment contract와 독립 감사를
  완료했다. source 866,359 = safe 752,591 + follow-up 113,768이며, safe 집합의
  pre-MFA 기술 제외 870을 뺀 exact-ID 751,721건이 새 r3 정렬 대상이다.
- source WAV 누락은 0이다. source 밖 WAV 11,798개는 snapshot에만 기록하고 입력으로
  암묵 선택하지 않는다. 과거 r2 실패 438건 중 조건을 충족한 337건은 새 r3
  정렬에 재진입한다.
- 발음 연구 DB는 866,359발화·4,504,375 occurrence이며 미회계 발화·unknown
  nonempty LAB token은 0이다. alignment contract ID는
  `f53b6c2be25fc4e694796ae123c005258ee9913a4b6bf4cf6625220dec4113cb`다.
- 실제 runner `-PreflightOnly`는 실패 검사 0, 필요 공간 52.193 GiB 대비 D: 여유
  114.028 GiB로 GO였고, 2026-08-11 15:05 KST에 시작해 21:41 KST에 보존 DB와
  `ALIGN_DONE_2022.json`을 완료했다. DB SHA-256은
  `610054531403f0ca13292194b13f6e63e509434435864aec9f7118d888bfe5b2`다.
- DB exact-ID는 입력 751,721 = 정렬 751,383 + 승인 기술 미정렬 338로 닫혔다.
  후보 identity `272bcc134776...3b2357b7a`는 자동 승인하지 않았고 연구자가
  명시 승인했다. r2 미정렬 438과 비교하면 공통 318, r3 회수 120, r3 신규
  미정렬 20이다.
- 6-tier 751,383개와 gzip 동반표 4종을 수출했다. 동반표는 utterance
  751,383, word 5,882,284, phone 21,857,009, excluded 338행이다.
- 독립 QC는 coverage 100%·hard failure 0, 동반표 오류 0, 보존 DB 재수출
  semantic·byte 24/24로 `passed`다. MFA·전수 수출·QC를 다시 실행하지 않는다.
- 상세 근거:
  `docs/decisions/RESULT_mfa_r3_2022_preflight_20260811.md`,
  `docs/decisions/RESULT_mfa_r3_alignment_database_2022_20260812.md`

## 2023 — r3 신규 정렬·6-tier·독립 QC 완료, SHA 동결

- source 677,262 = pronunciation-safe 582,389 + follow-up 94,873이며, safe 집합의
  pre-MFA 기술 제외 87,809를 뺀 exact-ID 494,580건을 새 r3 DB에 정렬했다.
- 입력 494,580 = 정렬 성공 494,228 + 승인 기술 미정렬 352로 완전 회계했다.
  후보는 `mfa_alignment_missing` 351건과 feature 생성 실패 1건이다.
- `ALIGN_DONE_2023.json`은 `status=passed`다. 보존 DB SHA-256은
  `3c6695ac2033612d514e6ca57711d006d2505c6ddb25124b666865df8c315108`이다.
- 연구자 명시 승인 뒤 보존 DB에서 6-tier 494,228개와 동반표 utterance
  494,228·word 3,832,921·phone 14,781,191·excluded 352행을 수출했다.
- 독립 QC는 coverage 100%·hard failure 0, 동반표·contract 오류 0, 보존 DB
  재수출 semantic·byte 24/24로 `passed`다. `QC_STATE.json` SHA-256은
  `115b81f539d87eb30892df2ffb0052e5d569884569aa4ff9f30c0b39db91d958`이다.
- 2023 MFA·전수 수출·QC를 다시 실행하지 않는다. 다음은 이 완료 SHA를 사용하는
  2023→2024 전환 Gate다.
- 상세 근거:
  `docs/decisions/RESULT_mfa_r3_alignment_database_2023_20260813.md`

### 2022 r2 역사적 비교 증거 — 현행 생산 입력 아님

아래 항목은 r3 채택 이전의 r2 결과와 문제 발견 경위를 보존한 기록이다. 현재
TextGrid·동반표·분석 범위에는 바로 위 r3 완료본만 사용하며, 아래 r2 DB·수출물은
재실행하거나 r3와 섞지 않는다.

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

승인 제외 계약과 LAB marker input ID는 각 연도에서 일치한다. 2023은 전수
MFA 직전 GO이며 아직 계산을 시작하지 않았다. 2022에서 발견한 음원 품질 문제를
반영하기 위해 동일한 구조 감사·음향 표본·`<=44B` 전수 inventory를 이미
2023–2025에도 적용했다.

| 연도 | 승인 제외 | LAB 세션 | LAB 행 | 특기 사항 |
|---:|---:|---:|---:|---|
| 2023 | 103,930 | 1,973 | 677,262 | r3 입력 494,580; 조합검색·연구 DB·runner preflight·전환 Gate 통과 |
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
- 2020–2023 r3 MFA·6-tier·동반표·독립 QC 완료 SHA 동결
- 2023 exact-ID 494,580 = 정렬 494,228 + 승인 기술 후속 352
- 2023 독립 QC coverage 100%·hard failure 0·DB 재수출 24/24
- D: 48.604 GiB·E: 1,834.453 GiB 확인; 실제 정리 전 temp inventory 대기
- 다음 단일 작업은 삭제 없는 2020–2023 r3 temp inventory
- inventory·승인·정리 뒤 2023→2024 전환 Gate
- 2022 post-MFA 438건과 결합 제외 1,669건의 승인·회계 완료
- 2022 공식 연구자 인프라 표본 24개 검토 완료·발음 입력 불일치 발견
- r2 프로젝트 발음 release Gate 차단 완료
- r3 canonical inventory 881,237형 생성 완료
- exact Roman 표면 donor 후보 346형 생성 완료(아직 최종 선택 아님)
- 규칙 목표형 Jamo G2P 310,605개·13 shard 후보 생성 및 읽기 전용 독립 감사 완료
- no-path·`spn`·중복·입력 밖 key·acoustic inventory 밖 phone 모두 0
- G2P 후보–독립 규칙 Roman 전수 exact Gate와 별도 읽기 전용 감사 완료
- 대상형 exact 96,284개(30.999%), mismatch 214,321개(69.001%)
- source 출현 exact 1,676,283회(37.476%), mismatch 2,796,609회(62.524%)
- 사전 근거 일치 exact 3,078형은 후속 선택 후보, 사전 충돌 14형과 독립 근거 없는
  exact 94,134형은 각각 보류, mismatch 215,184형은 자동 선택 불가
- mismatch 214,321 target·215,184 source형 전수 편집 진단과 독립 감사 완료
- mismatch 출현 중 표상 동등성 후보 1,686,625회(60.310%), 실질 차이 후보
  1,075,211회(38.447%), model 내부 대조 34,667회(1.240%), 표상 추가 검토
  106회(0.004%)
- 전체 2,625개 패턴 중 56행이 2,590,212회(92.620%)를 포괄하는 결정표 생성;
  자동 동등성 승인과 연구자 즉시 검토 요구는 모두 없음
- 후보 비교는 최종 선택이 아니며 canonical selection·adoption·TextGrid 변경 없음
- 좁은 model 단위화 관계와 exact 문맥 donor projection 계약·전수 생성·독립
  감사 완료: target 후보 가능 264,906개(85.287%)·3,744,243회(83.710%)
- 자동 보류 45,699개·728,649회; 잔여 1,799패턴은 95.136% 출현과 각 범주
  대표를 포괄하는 56행 handoff로 축약
- source 중 projection과 독립 사전 근거가 함께 일치한 것은 5,948형·349,689회;
  이 또한 canonical 최종 선택 전 후보
- canonical exact donor 382,891형 전역 projection·독립 감사 완료: 기존과 동일
  286,556 target, 후보 획득 13,172, 후보 상실 10,799, phone 변경 78
- 전역 결과를 반영한 09 readiness·독립 감사 완료: candidate 준비 752,270형
  (26,197,593회), 복수 변이 정책 35형·163회, zero-fallback 보류
  128,932형·1,649,312회
- 잔여 보류: target projection 미해결 43,428형, 아직 target이 아닌 no-rule
  실질 불일치 85,504형. 후자의 83,922형은 이미 동일 Jamo G2P 1-best 출처다.

no-rule 85,504형·1,140,107회의 전수 특성화와 독립 감사가 완료됐다. 모두
완성형 한글 음절이며, 숫자·기호·라틴 문자·낱자 자모는 없다. 주요 비배타적
진단 표지는 비음 조음 위치·경계 54,073형, 분절 수·탈락 35,703형,
활음·모음 단위화 22,168형, 후두 대립·phone 매핑 13,550형이다. 이는 규칙
정답이 아니라 현재 규칙 엔진·phone 매핑의 coverage를 점검할 우선순위다.

후속 읽기 전용 coverage 감사에서 모든 변이가 수의적 위치동화로만 다른
36,568형·525,747회, 위치동화와 겹치지 않으면서 모든 변이가 frozen 기본사전에
정확히 있는 811형·229,177회를 분리했다. 일부 변이만 위치동화인 82형·16,271회와
나머지 48,043형·368,912회는 보류한다. 107 acoustic phone 중 33개는 frozen
사전의 동일 길이 위치 대조에서 둘 이상의 규칙키와 반복 공존하므로, phone만으로
기저·표면 음소를 일대일 복원하지 않는다. 특히 `pʲ`는 B/P 양쪽에 쓰인다.

stage 12 readiness v2는 검증된 37,379형을 **정렬용 candidate-only**로 추가했고
독립 전수 감사를 통과했다. 이어 Stage 13에서 frozen 기본사전의 단어·음절·
국소 분절·이차조음 문맥 inventory를 만들고 zero-fallback 91,553형을 기존
canonical donor와 전수 대조했다. 단일 근거 10,594형, 복수 근거 22,171형,
출처 충돌 48,780형, 근거 없음 10,008형이며 독립 감사가 통과했다.

Stage 14 readiness v3는 단일 근거 중 기존 r2 phone·Roman을 바이트 그대로
유지하고 모든 issue가 frozen 사전의 onset+glide 이차조음 문맥으로 지지되는
6,141형·90,544회만 정렬용 candidate-only로 추가했다. candidate 준비는
795,790형·27,043,061회, zero-fallback hold는 85,412형·803,844회다. 881,237행
전수 v2 대조에서 비대상 필드 변화 0, phone·Roman 변화 0을 확인했다.

Stage 15는 남은 단일 근거 4,453형·72,030회의 4,900 issue를 ㅢ 규칙, 활음·
`ng`·종성 삽입, 후두 대립·비음/종성·모음·이차조음 치환, 혼합 편집으로 전수
분류하고 독립 감사를 통과했다. 자동 후보는 0형이고 4,453형 모두 기존 hold를
유지한다. `중에서`처럼 donor `ŋ`가 하나여도 기존 phone열에 분절을 새로 넣는
경우는 자동 승격하지 않는다.

Stage 16은 이 4,453형을 6개년 동결 검색 master 5,103,356발화와 연결했다.
exact 표면 어절은 68,285회, Bareun group과 표면 어절이 1:1일 때의 안전한
형태소·품사 문맥은 60,292회 연결됐다. 비1:1 분석은 억지로 맞추지 않았다.
자동 후보는 0형이며 4,453형 hold, MFA·TextGrid 미변경을 유지했고 독립 감사가
통과했다.

Stage 17은 사전·규칙 Roman exact 141형을 실제 등재 `pron_1/2` 65형과 legacy
기계 `pron_g2p` 76형으로 분리했다. 등재 65형의 전체 phone열을 동결 문맥 donor로
재구성해 14형·200회만 candidate-only로 준비하고 51형·2,851회는 복수·충돌로
hold했다. Stage 18 readiness v4는 이 14형만 병합했다. candidate 준비는
795,804형·27,043,261회, zero-fallback hold는 85,398형·803,644회다. v3/v4
881,237행 전수 감사에서 비대상 변화 0을 확인했다.

Stage 19는 동결 pre-MFA `pron_reference_form`과 실제 LAB tokenizer로
5,103,356발화를 전수 다시 읽었다. candidate만 포함한 safe body는
4,384,992발화(85.923694%), hold·policy·빈 LAB가 하나라도 있는 follow-up은
718,364발화다. unknown 어절은 0이며, 여섯 연도에 같은 발화 단위 라우팅 규칙을
적용했다. 부분 어절 삭제·대체는 하지 않았다. 독립 전수 감사가 통과했다.

Stage 20은 795,804형·796,061변이의 safe-body MFA 후보 사전을 물질화하고
107-phone 동결 acoustic inventory와 전수 byte projection을 독립 감사했다.
inventory 밖 phone, lexical `spn`/`sil`, non-candidate 누출은 모두 0이다. 파일명과
manifest의 `NOT_ADOPTED`는 당시 Stage 20 후보 상태를 보존한다. 이 후보를
byte-exact selected projection으로 물질화한 별도
`common_pron_mfa_r3_20260809` release는 2026-08-09 production Gate에서
채택됐다. Stage 폴더 자체를 production release로 사용하지 않는다.

Stage 21은 기존 연구자 지적 표본 `있지·놨던·슬프겠지만·없는` 네 발화만 새
후보 사전으로 표적 정렬했다. 입력 phone exact 4/4, interval 연속 4/4,
word–phone 바깥 경계 4/4, `spn` 0으로 자동 검사를 통과했다. 연구자는 네 경계를
모두 승인했다. 승인 계약은
`outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json`
이다.

연구자는 같은 승인에서 2020–2025 pronunciation-safe 4,384,992발화를 r3 대상
pool로 삼고, 독립 정렬 가능성 Gate를 통과한 발화를 모두 동일 r3 계약으로 새로
정렬하며 follow-up 718,364발화를 별도 shard로 보존하도록 결정했다.
따라서 더 이상 full-coverage/단계 채택이나 r2 interval 재사용을 다시 선택하지
않는다. 외부 workflow 리뷰, r3 전용 release/adoption, 연도별 checkpoint runner,
정책 감사와 2020 preflight는 완료됐다. 현재는 2020 장시간 runner를 사용자가
시작하기 직전이며, DB 완료 전 TextGrid materialization은 시작하지 않는다.

## 정본 문서

- 생산 순서: `docs/RUNBOOK_production_2020_2025.md`
- 발음 참조 파생층: `docs/RUNBOOK_pronunciation_reference_layer_2020_2025.md`
- 자산 위치: `docs/ASSETS_LEDGER.md`
- 상세 시행착오: `docs/WORK_HISTORY_2026-08.md`
- r3 후보 선택 결정:
  `docs/decisions/DECISION_common_pron_r3_candidate_resolution_20260807.md`
- r3 G2P 후보 실행 결과:
  `docs/decisions/RESULT_common_pron_r3_g2p_candidate_phase_20260808.md`
- r3 G2P–규칙 Roman 전수 Gate 결과:
  `docs/decisions/RESULT_common_pron_r3_g2p_agreement_gate_20260808.md`
- r3 G2P mismatch 전수 진단 결과:
  `docs/decisions/RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md`
- r3 model 표상·문맥 projection 후보 결과:
  `docs/decisions/RESULT_common_pron_r3_model_projection_candidates_20260808.md`
- r3 881,237형 selection-readiness 결과:
  `docs/decisions/RESULT_common_pron_r3_selection_readiness_20260808.md`
- r3 전역 donor projection·09 readiness 결과:
  `docs/decisions/RESULT_common_pron_r3_global_projection_v2_20260808.md`
- r3 no-rule 보류형 전수 특성화 결과:
  `docs/decisions/RESULT_common_pron_r3_no_rule_hold_characterization_20260808.md`
- r3 규칙·MFA phone coverage 감사 결과:
  `docs/decisions/RESULT_common_pron_r3_rule_phone_coverage_audit_20260808.md`
- r3 selection-readiness v2 결과:
  `docs/decisions/RESULT_common_pron_r3_selection_readiness_v2_20260808.md`
- r3 readiness v2 잔여 hold 우선순위:
  `docs/decisions/RESULT_common_pron_r3_readiness_v2_residual_priorities_20260808.md`
- r3 문맥 보존 frozen 사전 donor 감사:
  `docs/decisions/RESULT_common_pron_r3_contextual_dictionary_donor_audit_20260808.md`
- r3 selection-readiness v3 결과:
  `docs/decisions/RESULT_common_pron_r3_selection_readiness_v3_20260808.md`
- r3 단일 문맥 근거·phone 변경 필요형 감사:
  `docs/decisions/RESULT_common_pron_r3_unanimous_phone_change_audit_20260808.md`
- r3 pre-adoption 발화 라우팅:
  `docs/decisions/RESULT_common_pron_r3_pre_adoption_routing_20260808.md`
- r3 safe-body 후보 사전:
  `docs/decisions/RESULT_common_pron_r3_safe_body_candidate_20260808.md`
- r3 2022 표적 회귀 정렬:
  `docs/decisions/RESULT_common_pron_r3_targeted_regression_20260808.md`
- r3 adoption 선택 Gate:
  `docs/decisions/DECISION_common_pron_r3_full_realign_2020_2025_20260809.md`
- r3 전수 재정렬 workflow:
  `docs/WORKFLOW_mfa_r3_full_realign_2020_2025.md`
- 리밋·새 대화 재개: `docs/environment/CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md`

## 2026-08-09 21:30 현재: 2020 r3 정렬 DB 완료·export 전 정지

- 2020 r3 코퍼스는 2,231세션·782,715 WAV/LAB 쌍으로 완료됐고, 같은 계약의
  재개 실행이 17:28–21:20에 정상 종료됐다.
- `ALIGN_DONE_2020.json`은 `status=passed`다. 보존 DB는 5,534,134,272 bytes이며
  marker와 실제 SHA-256이 일치하고 SQLite `quick_check=ok`다.
- 782,715발화 중 782,432발화에 word·phone interval이 모두 있고 post-MFA
  미정렬은 283건이다. `spn` interval은 0이며 coverage는 99.9638%다.
- 최초 `fstcompile` PATH 실패는 runner의 conda runtime 상속과
  `check_third_party()` preflight hard Gate로 보정했다. 실패 당시 코퍼스·DB를
  삭제하지 않고 같은 계약에서 재개했다.
- 2021 corpus·temp·marker는 생성되지 않았다. 현재 허용 작업은 283건 exact-ID
  회계와 보존 DB 기반 6-tier/export preflight이며, TextGrid·CSV·tier 수정 때문에
  2020 MFA 전체를 다시 계산하지 않는다.
- 완료 기록:
  `docs/decisions/RESULT_mfa_r3_alignment_database_2020_20260809.md`
