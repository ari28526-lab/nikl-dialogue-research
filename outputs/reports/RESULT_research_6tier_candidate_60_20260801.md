# 연구 6-tier·동반표 생산 후보 60발화 회귀검사

- 일시: 2026-08-01 KST
- 판정: **회귀검사 통과; 전수 MFA GO는 아님**
- 입력: 기존 2020–2025 r2 수용 파일럿 SQLite DB, 연도당 10발화
- 작업: DB에서 출력만 재생성; MFA 재실행 없음

## 결과

| 연도 | TextGrid/발화행 | word interval | phone interval | DB checkpoint | spn |
|---:|---:|---:|---:|---|---:|
| 2020 | 10/10 | 51 | 211 | success | 0 |
| 2021 | 10/10 | 59 | 187 | success | 0 |
| 2022 | 10/10 | 57 | 227 | success | 0 |
| 2023 | 10/10 | 86 | 363 | success | 0 |
| 2024 | 10/10 | 119 | 419 | success | 0 |
| 2025 | 10/10 | 107 | 394 | success | 0 |
| **합계** | **60/60** | **529** | **1,801** | **6/6** | **0** |

- 기존 4-tier ↔ 새 6-tier duration/word/phone 전수 대조: 60/60, 불일치 0
- 연도별 `utterance_alignment/word_intervals_mfa/phone_intervals_mfa.csv.gz`:
  18개
- 총 회귀 산출물: 669,108 bytes, 활성 `.partial` 0
- 전체 unit test: Python 263건 통과
- PowerShell static safety: 16파일 통과

## 회귀검사가 잡은 실제 문제

`SARW2500000414.1.1.2`의 형태소 원 표기에서 `2사람이`는 1어절이지만,
MFA 입력 reference는 `두 사람이`라서 2 word다. 초안은 둘을 같은
`eojeol_idx`로 취급해 2025를 차단했다. 수정본은 `eojeol_idx`,
`reference_eojeol_idx`, `mfa_word_idx`를 분리해 원 형태소 구조와
정렬 입력 정규화을 모두 보존했다.

또한 count/label gate가 실패했는데도 gzip이 완성 파일명으로 승격되던
순서 문제를 발견했다. 모든 gate 통과 후에만 `.partial`을 최종 이름으로
바꾸도록 수정했고, 실패 시 완성 gzip이 없음을 단위시험으로 고정했다.

## 산출물 위치

```text
C:\Users\ari30\research\2026_summer_research\work\
  research_6tier_candidate_60_20260801
```

이 폴더는 외부 리뷰의 실물 근거이며 정본 승격 대상이 아니다.
