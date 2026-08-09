# 2020 r3 연도 입력 계약 결과 (2026-08-09)

## 목적

외부 프로세스 리뷰의 H1·H4·H5 지적을 반영하여, 2020년 정렬 대상을
발화 ID 수준에서 재현 가능하게 고정했다. 이 단계는 MFA를 실행하거나 기존
2020 r2 결과를 수정하는 단계가 아니다. 공통발음 r3의 발음상 안전 집합과
정렬 전 기술 제외 집합을 결합해 이후 r3 정렬에 넣을 정확한 우변을 만드는
단계다.

특히 과거 r2에서 정렬에 실패했다는 사실만으로 발화를 다시 제외하지 않았다.
`mfa_alignment_missing`과 `mfa_feature_generation_failed`는 정렬 후 결과이므로,
r3에서 발음상 안전하고 WAV 등 입력 조건을 충족하면 정상 입력으로 되돌린다.

## 고정한 입력

- r3 staged release: `common_pron_mfa_r3_20260809`
- 발음 계약 ID:
  `58226aeded930a5b09985c7a1ad870effbfb39fbbfd7d89229f84578cd3402af`
- Stage 19 blocked-ID SHA-256:
  `59f9d03fb8db25e2030e9cb592b609af1ef7c1308f98ddeab97a3e274f49ed10`
- Stage 19 연도 요약 SHA-256:
  `90ee101fa2b10618d4c04d2e69b2a13706b901b4729864c094d3af981417bd77`
- 2020 회수 WAV corpus contract ID:
  `eb64f80d9106d14c7b2a267811cdf2dc2fe29e890cc335a7029a8cca24a7375f`
- 회수 WAV 위치:
  `D:\20_AUDIO\04_wav_id_recovered_staging\individual\2020`
- 2020 연도 입력 계약 ID:
  `d75fa5bc50cc31c3912220d1cb292eb74ab8e9da4216988926dbaa89c34919ce`

검색 마스터의 `_build_meta.json` SHA와 2020–2025 전체 17,156개 CSV의
경로·크기·수정시각 inventory digest도 계약에 함께 고정했다.

## 전수 결과

| 구분 | 발화 수 | 의미 |
|---|---:|---|
| 검색 마스터 전체 | 870,437 | 2020 분석 분모 |
| 발음상 안전 | 784,390 | Stage 19 candidate 발음만 쓰는 발화 |
| 발음 후속 처리 | 86,047 | hold·policy·빈 발음 참조가 포함된 발화 |
| 승인된 정렬 전 기술 제외 전체 | 1,890 | 발음 후속 처리와 겹치는 ID 포함 |
| 발음상 안전 집합에서 실제 제외 | 1,675 | r3 본체 입력의 우변에서 빼는 ID |
| r3 예상 MFA 입력 | 782,715 | `발음상 안전 - 정렬 전 기술 제외` |
| 회수 WAV | 868,603 | 원 검색 ID에서 audio pairing 미해결 1,834건을 뺀 집합 |
| r2 정렬 후 실패 ID | 360 | 과거 결과이며 정렬 전 제외 사유가 아님 |
| r3 정상 입력으로 재진입 | 284 | 발음상 안전하고 다른 기술 제외가 없는 ID |
| 아직 재진입하지 못한 r2 실패 ID | 76 | 발음 후속 처리 또는 다른 정렬 전 제외와 겹침 |

정렬 전 승인 사유의 원래 전수 수량은
`audio_pairing_unresolved=1,834`,
`empty_reference_unresolved_symbol=53`, `audio_unusable=3`이다.
이 가운데 215개는 이미 발음 후속 처리 집합에 있으므로 중복으로 분모에서
두 번 빼지 않았다.

## 생성 산출물

다음 파일은 새 r3 release 아래에만 생성했다.

`D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\03_year_input_contracts\2020`

- `pronunciation_safe_ids_2020.csv.gz`
- `pronunciation_followup_ids_2020.csv.gz`
- `pre_mfa_exclusion_ids_2020.csv.gz`
- `expected_mfa_input_ids_2020.csv.gz`
- `r2_post_mfa_reentry_ids_2020.csv.gz`
- `YEAR_INPUT_CONTRACT_2020.json`

각 목록은 `year`, `utt_id`, `session_id`, `source_csv`를 포함하며, 계약 JSON에
크기·수정시각·SHA-256을 기록했다. 생성기와 별도의 감사기가 검색 마스터,
blocked 목록, 승인표, 회수 WAV 파일명을 다시 읽어 내용과 행 순서까지 독립
재계산했다.

독립 감사 보고서:

`outputs/reports/AUDIT_mfa_r3_year_input_contract_2020_20260809.json`

감사 상태는
`passed_independent_exact_id_audit_pending_alignment_contract_gate_closed`이다.

## 방법론적 해석

2020 r3의 입력 분모는 편의를 위해 r2 성공분을 재사용한 것이 아니다. 먼저
발음 계약에 따라 전체 870,437개를 안전/후속으로 분할하고, 안전 집합에서
오직 정렬 전에 관측 가능한 기술 제외만 뺐다. 과거 정렬 실패는 새 정렬의
독립변수처럼 사용하지 않았으므로, r2 오류를 r3에 고착시키는 선택 편향을
줄였다.

## 변경하지 않은 것과 현재 Gate

- Stage 01–21: 변경 없음
- D: 원자료: 변경 없음
- 2020 r2 DB·TextGrid·CSV: 변경 없음
- 공통발음 r2 산출물: 변경 없음
- production MFA: 아직 실행 불가
- TextGrid materialization: 아직 실행 불가
- `allowed_release_ids`: 빈 상태 유지

다음 단계는 이 exact-ID 계약과 모델·사전·corpus·runner 설정을 묶는 별도
r3 alignment contract를 만드는 것이다.
