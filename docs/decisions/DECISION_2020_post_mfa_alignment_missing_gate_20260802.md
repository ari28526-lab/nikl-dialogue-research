# 2020 post-MFA alignment-missing gate 결정

날짜: 2026-08-02

## 결론

2020년 공통 Jamo r2 전수 MFA의 음향 정렬 계산은 성공했다. 그러나 연구용
6-tier 내보내기의 exact-ID gate에서 363개 active LAB가 word/phone interval을
갖지 않는 것이 확인되어 자동 중단했다. DB와 계산 결과를 보존하며, 363건을
연구자 확인 없이 자동 제외하지 않는다.

## 확인된 전수 수치

- search master 원천 발화: 870,437
- 연구자 승인 pre-MFA 제외: 1,887
  - WAV pairing 미해결: 1,834
  - 빈 기준 발음/미해결 기호: 53
- active LAB 및 MFA DB 발화: 868,550
- word와 phone interval이 모두 있는 발화: 868,187
- MFA 기본 beam과 retry beam 모두에서 실패: 363
- 방정식: `870,437 = 868,550 + 1,887`
- 정렬 job별 최종 오류: `33 + 54 + 39 + 237 = 363`

따라서 기존 1,887건은 stale 승인이 아니라 MFA 입력 전에 적용된 승인 제외다.
기존 exporter가 active LAB 밖의 승인을 모두 stale로 해석한 것은 입력 단계와
post-MFA 단계를 혼합한 게이트 오류였다.

## 코드 수정 원칙

exact-ID gate는 다음 두 방정식을 분리한다.

1. `source_search_ids = active_lab_ids ∪ approved_upstream_alignment_exclusions`
2. `active_lab_ids = aligned_database_ids ∪ approved_active_alignment_exclusions`

승인 ID가 source search master 밖에 있거나, 승인 없이 source에서 active LAB가
사라지거나, active LAB가 source 밖에 있으면 계속 hard failure다. 따라서 안전
게이트를 약화하지 않고 단계 의미만 바로잡았다.

## 363건 판단 보류 이유

363건 모두 feature와 정규화 text가 있고 OOV는 없지만, alignment likelihood와
word/phone interval이 없다. 특히 다음과 같이 세션 집중이 크다.

- `SDRW2000000257`: 200/464 실패
- `SDRW2000000514`: 28/427 실패
- `SDRW2000002165`: 17/434 실패
- 나머지: 79개 세션에 분산

한 세션에서 43.1%가 실패한 것은 단순 희귀 음향 실패로 단정하기 어렵다.
대표 실패 12개와 같은 세션 정상 대조 4개의 WAV/LAB를 먼저 들어서 입력 매핑
문제와 실제 MFA beam 실패를 구분한다.

추가로 2026-07-26 구방식의 실패 inventory와 대사했다. 구방식 실패는
3,644건이었고 이번에는 363건으로 줄었다. 구방식 실패 중 3,332건은 이번
공통 Jamo r2에서 회수됐으며, 이번 363건 중 312건은 구방식에서도 실패한
지속 난정렬이고 51건은 새 실패다. `SDRW2000000257`은 구방식 205건, 이번
200건이며 193 ID가 겹친다. 이 세션은 WAV ID 복구 계획 대상이 아니므로 새
복구 매핑이 집중 실패를 만든 가능성은 낮다. 다만 원자료 자체의 WAV/LAB
대응 문제까지 배제하는 근거는 아니므로 대표 청취 gate는 유지한다.

## 재개 계약

- 보존 DB: `D:\mfa_tmp\2020\2020.db`
- DB 크기: 6,348,247,040 bytes
- 보존 marker: `D:\mfa_eojeol\done\2020.direct_db_ready`
- 연도 전체 MFA 재실행: 필요 없음
- 다음 실행: DB checkpoint를 재검증한 뒤 6-tier 내보내기부터 재개
- 자동 승인·정본 승격·2021 진입: 금지

검토 결과 WAV/LAB가 맞으면 표적 재정렬 가능성과 명시적 제외를 비교한다.
매핑 불일치가 확인되면 영향 세션만 입력 복구하고 보존 DB/부분 결과를 근거로
해당 범위만 다시 계산한다.

## 2026-08-03 검토 완료와 재개 판정

- 연결 표본 16건: 13 `match`, 3 `audio_unusable`
- 보존 DB 재조회 미정렬 ID와 원 post-MFA 후보표: 363/363 exact match
- post-MFA 승인: `audio_unusable` 3 + `mfa_alignment_missing` 360 = 363
- 최종 결합 승인: pre-MFA 1,887 + post-MFA 363 = 2,250
- 계약 위치:
  `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_export_20260803/2020`

표본 13건이 360건 각각의 음질을 대표한다고 주장한 것이 아니다. 363건 전체는
동일한 기계적 상태, 즉 승인된 입력에는 존재하지만 기본·retry 정렬 뒤에도
word/phone interval이 없는 발화로 전수 확인했다. 연구자가 인프라 구축을
계속하도록 명시 결정했으므로 이 범주를 결과에서 투명하게 제외하고, 실패 ID와
사유는 동반 제외표에 모두 남긴다. 정렬 성공 868,187건은 같은 DB에서 내보내며
연도 전체 MFA를 다시 계산하지 않는다.
