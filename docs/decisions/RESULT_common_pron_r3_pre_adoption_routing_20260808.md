# 공통발음 r3 Stage 19 — adoption 전 발화 라우팅 결과

날짜: 2026-08-08 KST
상태: `passed_independent_full_scan`
범위: 2020–2025 동결 pre-MFA 입력 전수
MFA·TextGrid·원 WAV/CSV 변경: 없음

## 목적

readiness v4의 발음 후보가 준비됐더라도, 한 발화 안에 발음 후보가 없는 어절을
남긴 채 일부 어절만 바꿔 정렬하면 같은 6개년 발음 기준이라고 말할 수 없다.
따라서 실제 MFA LAB 생성과 동일한 tokenizer로 모든 발화를 다시 읽고 다음 두
집합으로 나눴다.

- `safe body`: 발화의 모든 LAB 어절이 readiness v4 candidate인 경우
- `follow-up`: hold, 미결 policy, unknown 또는 빈 LAB가 하나라도 있는 경우

어절을 발화에서 삭제하거나 부분 발음으로 대체하지 않았다. 후속 발화도 삭제하지
않고 정확한 `utt_id`, 원 CSV 행, 문제 어절과 사유를 보존했다.

## 입력 계약

- 동결 pre-MFA root:
  `D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725`
- 발음 입력 열: `pron_reference_form`
- 실제 LAB tokenizer: `realign_eojeol_build_corpus.form_to_lab`
- readiness:
  `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\18_selection_readiness_v4`

구 `D:\10_LAYERS\05_search_master`의 `form`은 연구 검색용 역사 자산이지 동결
pre-MFA 발음 입력이 아니다. 두 root를 혼용하지 않는다.

## 전수 결과

| 항목 | 수 |
|---|---:|
| CSV | 17,156 |
| 발화 | 5,103,356 |
| `pron_reference_form` 어절 | 27,869,302 |
| 실제 LAB 어절 | 27,847,068 |
| tokenizer가 제거한 기호 어절 | 22,234 |
| safe body 발화 | 4,384,992 (85.923694%) |
| follow-up 발화 | 718,364 (14.076306%) |
| unknown LAB 어절 | 0 |

readiness 상태 출현 회계도 전수 입력과 정확히 일치했다.

- candidate: 27,043,261회
- zero-fallback hold: 803,644회
- 미결 policy: 163회

follow-up 사유는 hold 717,354발화, policy 136발화, hold+policy 26발화,
빈 LAB 848발화다. 부분 unresolved symbol은 기존 승인 정책대로 제거 뒤 남은
LAB가 안전하면 본체에 유지하고, 전체가 비어 버린 경우만 `empty_reference`로
후속 이관했다.

## 연도별 동일 기준 회계

| 연도 | 전체 발화 | safe body | follow-up | safe 비율 |
|---:|---:|---:|---:|---:|
| 2020 | 870,437 | 784,390 | 86,047 | 90.114506% |
| 2021 | 1,373,920 | 1,208,236 | 165,684 | 87.940783% |
| 2022 | 866,359 | 752,591 | 113,768 | 86.868261% |
| 2023 | 677,262 | 582,389 | 94,873 | 85.991684% |
| 2024 | 728,257 | 595,743 | 132,514 | 81.803951% |
| 2025 | 587,121 | 461,643 | 125,478 | 78.628256% |

이는 연도별로 다른 발음 기준을 적용한 결과가 아니라, 같은 r3 readiness와 같은
발화 단위 보수적 라우팅 규칙을 여섯 연도에 전수 적용한 결과다.

## 독립 감사와 시행착오

독립 감사기는 5,103,356발화를 원 CSV부터 다시 스캔해 blocked 행 identity,
사유 집합, 연도 회계, 85,433개 follow-up 어절형의 연도별 출현 수를 재계산했다.
safe body에 hold/policy/unknown/empty가 섞인 경우는 0건이었다.

첫 시도는 구 검색 root를 사용해 전수 합계가 맞지 않아 final 승격 전에 중단됐다.
두 번째 시도는 `pron_reference_n_eojeol`과 실제 LAB tokenizer 결과를 같다고
가정해, 기호 제거가 있는 첫 사례에서 중단됐다. 입력 root와 실제 tokenizer
계약을 바로잡은 뒤 성공했다. 실패 중간물은 삭제하지 않고 다음에 보존했다.

- `...\archive_intermediate\19_pre_adoption_routing_failed_legacy_search_master_a5e9ca31319e46deae1d43c7f89c1320`
- `...\archive_intermediate\19_pre_adoption_routing_failed_pron_reference_count_contract_5123eb65523e4ecfb128e3407ec936be`

정본 manifest는
`D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\19_pre_adoption_routing\PRE_ADOPTION_ROUTING_MANIFEST.json`,
독립 감사 보고서는
`outputs/reports/AUDIT_common_pron_r3_pre_adoption_routing_20260808.json`이다.
