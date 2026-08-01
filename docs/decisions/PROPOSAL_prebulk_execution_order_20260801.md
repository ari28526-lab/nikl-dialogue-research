# 전수 작업 전 최종 실행 순서 제안

- 작성일: 2026-08-01 KST
- 상태: 외부 workflow 리뷰 요청 전 제안
- 범위: 2020–2025 조합검색 CSV, 신규 MFA, 6-tier TextGrid, 동반표
- 현재 정지점: 2020 `morph_search.v3` 실제 첫 shard 1/23 성공 후 정상 정지

## 1. 최종 연구 목적

이 작업의 목적은 자동 phone으로 음운 현상의 실현 여부를 판정하는 것이 아니다.

```text
형태소·POS·철자·음운형태 환경을 CSV/Parquet에서 검색
  → utt_id로 WAV·TextGrid·메타데이터를 수집
  → 필요한 후보만 이어붙이기·KOINA·wav2vec2 보조 분석
  → 연구자가 음성과 TextGrid를 보고 실제 실현 여부 판정
```

따라서 전수 생산물은 다음 두 축을 함께 만족해야 한다.

1. **검색 축**: 형태소, 철자 Roman, 형태소 경계, 숫자·기호, 화자·대화 정보
2. **음성 접근 축**: 동일 기준의 MFA word/phone, 6-tier TextGrid, WAV 연결

MFA phone은 자동 강제정렬의 보조값이며 실제 음성 실현 판정값이 아니다.

## 2. 먼저 구분해야 할 두 종류의 작업

### 2.1 MFA 전에 반드시 동결할 것

다음 항목이 바뀌면 phone 또는 시간 정렬이 달라질 수 있으므로 2020 신규 MFA
전에 확정·fingerprint해야 한다.

| 항목 | 현재 기준 | 변경 시 영향 |
|---|---|---|
| 원 발화 집합과 `utt_id` | 동결 pre-MFA search master | 입력 coverage·조인 변경 |
| `pron_reference_form`과 LAB 생성 규칙 | 원 전사 근거 우선, 근거 없는 기호 읽기 자동 확정 금지 | MFA word·phone 변경 |
| 공통 발음사전 | `common_pron_mfa_r2_20260728` | phone sequence 변경 |
| acoustic model | Korean MFA v3.3.0 | 시간 정렬 변경 |
| G2P/model policy | Jamo v3.2.0, 공통사전 기본 | OOV phone 변경 |
| researcher exception 27건 | r2 adoption v3 승인본 | 해당 어휘 phone 변경 |
| 허용 phone inventory | r2 manifest 기준 | 연도 간 방법 일관성 변경 |

이 계약이 확정된 뒤에는 2020–2025 모두 같은 기준을 사용한다. 이 입력을 바꾸는
결정은 영향 inventory와 명시적 새 버전 없이는 하지 않는다.

### 2.2 정렬 뒤에도 재생성·결합할 수 있는 것

다음 항목은 기존 MFA phone을 덮어쓰지 않으며, 동일 동결 입력과 `utt_id`가
보존되면 정렬 뒤에도 독립적으로 다시 만들 수 있다.

- `morph_tokens`, `morph_units`, `morph_boundaries`
- `orth_eojeol_tokens`, 철자 기반 `form_roman_v2`
- 숫자·기호 `symbol_readings` 보조표
- 우리말샘 1:N 센스·사전 발음 후보표
- `phones_mfa`의 기계적 broad Roman인 `phoneme_r_auto`
- 최종 joined Parquet와 검색 view
- 선별 KOINA, 이어붙이기, wav2vec2 보조열, manual judgment

그러므로 **6개년 조합검색 표 전부가 끝날 때까지 MFA를 무조건 기다릴 필요는
없다**. 다만 첫 생산 연도인 2020은 조합검색 전수가 약 1시간 내외로 예상되고
원 입력·기호·좌표 문제를 조기에 발견할 수 있으므로, 2020 검색표를 먼저
완료·검증한 뒤 2020 MFA로 가는 것을 권장한다. 2021–2025는 연도별로 같은
순서를 적용하거나, 장치 I/O가 충돌하지 않는 시간에 독립 생성할 수 있다.

## 3. 현재 완료된 것

| 영역 | 상태 | 근거 |
|---|---|---|
| 6개년 동결 pre-MFA search master | 완료 | 5,103,356발화, 17,156 session CSV |
| 공통 Jamo r2 사전 | 완료 | 866,692 OOV, `spn=0`, missing=0 |
| 모델·adoption 동결 | 완료 | acoustic 3.3.0, Jamo G2P 3.2.0, adoption v3 |
| 6-tier TextGrid 계약 | 확정·파일럿 통과 | 60발화 및 외부 리뷰 수정 |
| post-MFA 동반표 4종 | 구현·회귀 통과 | gzip/Parquet 소규모 왕복 검증 |
| 조합검색 v3 schema | 구현·60발화 회귀 통과 | 42 gzip SHA 불일치 0 |
| 2020 실제 검색 첫 shard | 성공 | 41,803발화, 7표, SHA 불일치 0 |
| 2020–2025 신규 MFA | 미시작 | 구 정렬은 재사용하지 않음 |

## 4. 전수 진입 전에 아직 확정·연결할 것

### Blocker 후보

1. **workflow 의존성 연결**
   - 현재 `morph_search.v3` 연도 runner와 MFA 연도 큐는 별도다.
   - 최소한 두 산출물이 같은 동결 source inventory와 `utt_id` 계약을 사용했음을
     preflight에서 확인해야 한다.
   - 검색표 연도 `YEAR_MANIFEST=success` 자체를 MFA 시작의 hard gate로 할지,
     동일 source/input contract 확인만 hard gate로 할지는 외부 리뷰가 필요하다.

2. **LAB·기호 읽기 계약 최종 확인**
   - `symbol_readings` 후보값을 LAB에 자동 주입하지 않는다.
   - `pron_reference_form`에 원 JSON 전사 근거가 이미 있을 때만 그 값을 사용한다.
   - 근거 없는 기호는 누락시키지 말고 unresolved inventory로 남긴다.

3. **연도별 입력 예외 처리의 최소 범위**
   - 구 2020 TextGrid나 전체 발화를 다시 검토하지 않는다.
   - 새 LAB/WAV 입력에서 실제로 사용할 수 없는 후보만 자동 inventory한다.
   - 사람이 확인해야 한다면 그 소수 후보의 제외 여부뿐이다. 후보가 0이면 검토도 0이다.

4. **저장공간 수명주기**
   - D:는 실행 정본, E:/추가 HDD는 검증된 archive 원칙을 유지한다.
   - 검색 builder는 shard raw와 gzip을 함께 보존하므로, 연도 manifest·SHA 검증 뒤
     raw shard를 압축 archive할지 삭제할지 명시적 정책이 필요하다.
   - 원 JSON/WAV와 검증 전 partial은 자동 삭제하지 않는다.

### MFA를 막지 않는 후속 과제

- 우리말샘 1:N 발음 후보를 최종 검색 DB에 결합하는 정책과 코드
- pre-MFA 7표와 post-MFA 4표를 묶는 최종 DuckDB/Parquet 검색 view
- KOINA·이어붙이기·wav2vec2·manual judgment schema
- HTK/kfaligner 비교 실행: 현재는 참고사항이며 생산 blocker가 아님

## 5. 권장 생산 순서

### Gate A — 외부 workflow 리뷰와 계약 동결

1. 이 문서의 연구 목적·선행 필수/후행 가능 구분을 외부 리뷰한다.
2. BLOCKER/HIGH를 반영한다.
3. 코드 commit, model/dictionary/schema SHA, D: 경로와 run ID를 기록한다.
4. `2020 GO`를 먼저 판정한다. 이때 2021–2025 전체 실행은 아직 허가하지 않는다.

### Stage 1 — 2020 pre-MFA 검색층 완성

1. `morph_search.v3` shard 2–23을 이어 실행한다.
2. 성공 shard를 재사용하고 실패 partial은 보존한다.
3. 연도 7표, 행 수, 중복 `utt_id=0`, symbol coverage, SHA를 검사한다.
4. `YEAR_MANIFEST=success` 뒤에만 2020 검색 정본 후보로 인정한다.

이것은 구 2020 MFA/TextGrid 검토가 아니다.

### Stage 2 — 2020 신규 MFA 입력 계약

1. 동결 `pron_reference_form`으로 LAB을 생성·전수 기계 감사한다.
2. LAB 발화 집합, WAV 발화 집합, search master 발화 집합을 exact ID 대사한다.
3. 빈 LAB, 읽을 수 없는 WAV, 미해결 기호 등 실제 예외 후보만 inventory한다.
4. 예외 후보가 있으면 연구자는 **제외 여부만** 확인한다.
5. input contract ID와 승인 예외표를 고정한다.

### Stage 3 — 2020 신규 MFA

1. r2 공통사전·동결 모델 SHA·input contract를 preflight한다.
2. 신규 MFA를 실행한다. 구 2020 정렬은 재사용하지 않는다.
3. temp·SQLite·로그를 보존하고 자동 full-clean retry를 금지한다.
4. 정렬 계산 완료 시 `direct_db_ready`를 남겨 출력 실패와 정렬 재계산을 분리한다.

### Stage 4 — 2020 연구 산출물과 QC

1. DB에서 기본 6-tier TextGrid를 생성한다.
2. post-MFA 동반표 4종을 연도 gzip으로 생성한다.
3. duration, word/phone coverage, tier 경계, phone inventory, `spn`, 누락,
   `utt_id` join을 전수 감사한다.
4. schema나 입력을 바꾸는 검토가 아니라, 실제 파일 접근성과 자동 정렬 산출물이
   계약대로 생성됐는지를 작은 층화 표본으로 확인한다.
5. 문제가 출력 코드에 있으면 DB부터 재수출하고 MFA를 다시 돌리지 않는다.

### Gate B — 2020 생산 결과로 2021–2025 허가

1. 2020의 입력·정렬·출력·QC manifest가 모두 같은 계약을 가리키는지 확인한다.
2. 방법 변경이 없으면 2021–2025를 같은 연도별 pipeline으로 순차 실행한다.
3. 한 연도 실패는 해당 연도만 막고, 성공한 연도와 shard는 재사용한다.
4. 연도마다 D: 공간을 확인하고 검증된 중간물만 archive/정리한다.

### Stage 5 — 6개년 최종 검색 인프라

1. pre-MFA 7표, post-MFA 4표, 메타데이터, 파일 경로를 명시적 key로 연결한다.
2. 우리말샘 복수 센스·복수 발음은 별도 1:N 후보표로 연결한다.
3. gzip CSV를 감사·보존 정본으로 두고 Parquet/DuckDB를 검색 미러로 만든다.
4. 형태소/POS/어두·어중·어말/경계/철자 Roman/기호 조합 질의를 회귀시험한다.
5. 후보 bundle에서만 발화별 WAV·TextGrid·CSV를 모은다.

### Stage 6 — 실제 연구

선별 후보에만 KOINA, 이어붙이기, wav2vec2 보조 phone을 추가한다. 기존
`phones_mfa`나 공통사전 열을 덮어쓰지 않는다. 연구자가 음성과 TextGrid를 보고
실현 여부를 별도 manual judgment 표에 기록한다.

## 6. 지금은 무엇을 하지 않는가

- 2020 구 MFA/TextGrid 전수 재검토
- 2020–2025 MFA 동시 실행
- 근거 없는 숫자·기호 읽기의 LAB 자동 확정
- 우리말샘 복수 발음을 MFA용 단일 발음으로 자동 채택
- KOINA·wav2vec2를 전수 실행
- 검증 전 partial, 원 JSON/WAV, 실패 증거 자동 삭제
- 외부 workflow 리뷰가 끝나기 전 2020 shard 2 이후 전수 재개

## 7. 외부 리뷰가 내려야 할 최종 판정

리뷰 결과는 다음을 명시해야 한다.

1. `GO`, `GO AFTER FIXES`, `NO_GO` 중 하나
2. 2020 신규 MFA 전에 반드시 끝내야 할 항목
3. 정렬 뒤로 미뤄도 되는 항목
4. `morph_search.v3 YEAR_MANIFEST`를 MFA hard gate로 할지 여부와 이유
5. 2020 생산 결과 뒤 2021–2025로 넘어가는 최소 Gate B
6. 불필요하게 반복되는 사람 검토가 있는지
7. 논문 방법론에서 동일 기준·출처 분리를 주장하기에 부족한 증거가 있는지
