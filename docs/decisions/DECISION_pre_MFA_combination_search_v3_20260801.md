# pre-MFA 조합검색 v3와 2020 신규 정렬 진입 결정

- 결정일: 2026-08-01 KST
- 상태: 확정
- 적용 범위: 2020–2025 전체 자료

## 결론

2020의 **기존 MFA 정렬 결과를 다시 전수 검토하거나 재사용하지 않는다**.
2020–2025는 모두 공통 Jamo 발음사전 r2, Korean MFA acoustic model
v3.3.0, Jamo G2P v3.2.0과 같은 phone inventory로 새로 정렬한다.

새 정렬 전 2020에서 먼저 만드는 것은 구 TextGrid 검토표가 아니라 다음 두
종류의 새 입력 인프라다.

1. 형태소·철자·Roman·기호를 조합 검색할 `morph_search.v3` 표
2. 같은 입력 계약으로 새 MFA에 넣을 LAB과 예외 입력 inventory

두 번째 단계에서 사람이 볼 수 있는 것은 전수 발화가 아니라 자동으로 정렬
입력 불가라고 분류된 **예외 후보만**이다. 후보가 없으면 별도 검토도 없다.
이는 구 정렬의 품질을 승인하는 절차가 아니라, 새 정렬 입력에서 자료가 말없이
누락되지 않았음을 기록하는 절차다.

## 연구 흐름

```text
동결 pre-MFA search master (읽기 전용)
  → 연도·shard별 morph_search.v3 생성·기계검증
  → 같은 발화 ID로 LAB 생성·입력 예외 inventory
  → 공통 r2 사전으로 해당 연도 신규 MFA
  → 승인된 6-tier TextGrid와 post-MFA 동반표 생성
  → 연도 전수 QC
  → 다음 연도
```

2020을 먼저 하는 이유는 구결과와 비교하거나 승인하기 위해서가 아니라, 전수
파이프라인의 첫 신규 생산 연도로 삼기 위해서다. 2020 성공 뒤 같은 계약을
2021–2025에 적용한다.

## pre-MFA 검색 표

연도별 gzip CSV 정본은 다음 7표다.

| 표 | 행 단위 | 목적 |
|---|---|---|
| `utterance_master_v2` | 발화 | 원문·형태소·Roman·출처·상태의 발화 인덱스 |
| `orth_eojeol_tokens` | `form`의 철자 어절 | 철자 어절·철자 Roman 검색 |
| `eojeol_tokens` | `tagged`의 분석 어절 | 형태소 분석 어절·Roman 검색 |
| `morph_tokens` | 형태소 | 표면형·POS·어두/어중/어말 위치 검색 |
| `morph_units` | 형태소 내부 음절/기호 unit | 음절·자모·문자 위치 검색 |
| `morph_boundaries` | 형태소 경계 | 좌우 형태소·POS·철자 환경 조합 검색 |
| `symbol_readings` | 숫자·기호 occurrence | 표기, 출처 근거 발음, 후보, 미해결 상태 분리 |

`form` 어절과 `tagged` 분석 어절의 수가 다를 수 있으므로 하나의 좌표로 억지로
맞추지 않는다.

- `orth_eojeol_idx`: 철자 `form` 좌표
- `eojeol_idx`: 형태소 분석 `tagged` 좌표
- `reference_eojeol_idx`: MFA 입력 `pron_reference_form` 좌표
- `mfa_word_idx`: 실제 새 MFA word interval 좌표

어절 수가 다르면 오류를 감추거나 전체 발화를 버리지 않고 mismatch 상태와 두
표를 모두 남긴다. 자동으로 형태소 경계를 음향 시간경계라고 해석하지 않는다.

## 숫자·기호 정책

`2=둘` 같은 대응은 문맥에 따라 `이/둘/두` 등이 가능하므로 전역 치환하지 않는다.

- 원 JSON의 전사나 이미 확정된 `pron_reference_form`이 정확한 대응 근거를 주면
  `reference_reading`에 선택값을 기록한다.
- 근거가 없으면 선택값은 비워 두고 `reading_candidates_json`에 후보만 둔다.
- 문장부호 보존/생략, 비한글 치환, 정렬 모호성을 서로 다른 상태로 기록한다.
- 이 보조표는 사전 phone이나 실제 음성 실현 판정을 덮어쓰지 않는다.

실자료 `SARW2500000414.1.1.2`의 `2사람이`는 원 전사 근거가 있어 `두`가 선택되고,
후보 `이/둘/두`도 별도로 보존된다.

## 재실행과 실패 복구

- 기본 shard는 session CSV 100개다.
- 성공 shard는 manifest·행 수·SHA-256을 재검증한 뒤 재사용한다.
- 실패한 `.partial`은 자동 삭제하지 않고 근거로 보존한다.
- 모든 shard 성공 전에는 연도 정본을 승격하지 않는다.
- 연도 정본은 결정적 gzip(`mtime=0`)으로 생성한다.
- MFA·TextGrid·공통발음사전은 이 단계에서 실행하거나 변경하지 않는다.

따라서 일부 파일의 오류 때문에 2020 전체 CSV나 이미 끝난 MFA를 처음부터 다시
돌리는 경로를 기본값으로 두지 않는다.

## 회귀검증 근거

기존 r2 파일럿에서 연도별 10발화, 총 60발화를 두 번 독립 생성했다.

- 2020–2025 모두 성공
- 7표 × 6년 = gzip 42개 SHA-256 불일치 0
- 철자/형태소 어절 수 불일치 7발화는 두 좌표로 보존
- 기호 26 occurrence 전부 표에 수록
- `2사람이 → 두 사람이` 출처 근거 복원 확인
- 이 검사에서는 MFA를 실행하지 않음

기계 근거:
`outputs/reports/EVIDENCE_morph_search_v3_regression_60_20260801.json`

## 다음 생산 단계

다음 계산은 2020의 `morph_search.v3` 신규 전수 생성이다. 첫 shard를 기계
preflight로 완성한 뒤 같은 명령을 재실행하면 성공 shard를 재사용하며 나머지를
계속한다. 이것은 2020 구 정렬 전수 검토가 아니다.
