# 공통발음 r3 Stage 20 — safe-body 후보 사전 결과

날짜: 2026-08-08 KST
상태: `passed_candidate_only_not_adopted`
독립 감사: `passed_full_projection_and_dictionary_equivalence`

## 목적과 지위

Stage 19 safe body를 실제로 정렬할 수 있는지 검증하기 위해 readiness v4의
candidate만 별도 MFA 사전 형태로 물질화했다. 이 파일은 정렬 가능성·phone
inventory·projection을 검사하는 **비채택 후보**다. canonical 최종 선택,
표준발음 판정, 음성의 실제 실현 판정 또는 프로젝트 release adoption을 뜻하지
않는다.

## 결과

| 항목 | 수 |
|---|---:|
| 후보 표면형 | 795,804 |
| 후보 출현 | 27,043,261 |
| MFA 사전 변이 행 | 796,061 |
| 1변이형 | 795,554 |
| 2변이형 | 245 |
| 3변이형 | 3 |
| 4변이형 | 2 |
| frozen acoustic inventory 밖 phone | 0 |
| lexical `sil`/`spn` | 0 |
| non-candidate 누출 | 0 |

Korean MFA v3.3.0의 동결 acoustic phone 107개를 기준으로 검사했다. `sil`과
`spn`은 acoustic 모델의 특수 심볼이므로 어휘 phone inventory에는 포함하지
않았다. 이 차이를 109개 어휘 phone으로 잘못 해석한 첫 시도는 출력 생성 전에
안전 중단됐고, 동결 raw phone SHA와 107개 inventory를 그대로 사용하도록
교정했다.

## 산출물

- root:
  `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\20_safe_body_candidate`
- 후보 projection: `safe_body_candidate_projection.csv.gz`
- 후보 사전: `common_pron_r3_safe_body_candidate.NOT_ADOPTED.dict`
- manifest: `SAFE_BODY_CANDIDATE_MANIFEST.json`
- 독립 감사:
  `outputs/reports/AUDIT_common_pron_r3_safe_body_candidate_20260808.json`
- candidate contract ID:
  `2c6266b0428a26dad8f3f5ff71f9cf847a170569bda752743623c6a4ba07f95a`

독립 감사기는 readiness 795,804형의 모든 변이·순서·byte projection과 사전
796,061행을 전수 재계산했다. 기존 r2 TextGrid, MFA DB, WAV, LAB와 2020–2022
완성본은 변경하지 않았다.
