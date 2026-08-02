# 통합 CSV·MFA 연구 인프라 전체 계획 (생산 계약 이전 기록)

- 작성일: 2026-07-31
- 상태: **60발화 기계 파일럿 통과, 12발화 연구자 수용 검토 대기**
- 대상: 모두의 말뭉치 2020–2025년
- 목적: 형태소·표기 환경 검색 → WAV/TextGrid 수집 → 선택 후보 KOINA →
  연구자 실현 판정

## 1. 결론

CSV와 MFA를 별도 사업처럼 처리하지 않는다. 다만 둘을 한 파일에 억지로
합치지도 않는다. 다음 네 층을 `utt_id`와 동결된 버전 계약으로 연결한다.

```text
원전 JSON·WAV (읽기 전용)
  ↓
pre-MFA 텍스트·검색 층
  ├─ 발화 1행 master CSV/Parquet
  ├─ morph_tokens
  ├─ morph_units
  ├─ morph_boundaries
  └─ 필요 시 orth_components 파생 view
  ↓
공통발음사전 r2 + 고정 acoustic/G2P + LAB
  ↓
MFA 정렬 DB → 연구용 4-tier TextGrid + 정렬 index/QC
  ↓
post-MFA 보조 층을 발화 master에 연결
  ↓
후보 추출 bundle → KOINA(선택) → 연구자 판정표
```

MFA phone은 청취 위치를 찾는 자동 정렬 보조값이다. 사전 발음, 규칙 발음,
MFA phone, wav2vec2 phone, 연구자 실현 판정은 서로 다른 출처의 열·표로
보존한다.

## 2. 현재 위치

완료:

- 2020–2025 관측 어휘 기반 공통발음사전 r2 생성
- Korean MFA acoustic v3.3.0, Jamo G2P v3.2.0, 공통사전 및 adoption SHA 동결
- adoption v3 `passed`, `allow_yearly_mfa=true`
- 27개 예외 후보 연구자 승인 반영
- 2020/2021 차이 inventory와 구결과 archive
- 2020–2025 연도당 10발화, 5화자, 5세션의 60발화 MFA 기계 검증
- 60발화 WAV/TextGrid/LAB/행별 CSV 검토 묶음
- 외부 형태소·로마자 위치 검색 리뷰 triage 및 필수 정정
- `morph_tokens/morph_units/morph_boundaries/orth_components` 구현
- `tagged_roman.v2`와 연구용 4-tier TextGrid 구현
- 기존 DB 기반 60발화 재수출·자동 동등성 검사 통과
- 연도별 2발화, 총 12발화의 Dropbox 수정본 검토 묶음

미완료:

- 형태소·음절·철자 단위 위치 검색 표의 6개년 전수 생성
- 새 4-tier TextGrid의 연구자 12발화 수용
- r2 기준 2020–2025 전수 MFA
- post-MFA 발음·정렬 보조 층의 전수 생성
- 최종 연구 검색 master와 후보 bundle 자동화

따라서 지금 전수 MFA부터 시작하지 않는다. 검색 스키마와 TextGrid 표시
계약의 기계 검증은 통과했으며, 12발화 수정본을 연구자가 수용하는지가
남았다. 이 파일럿은 보존된 MFA DB를 재사용했으므로 정렬을 다시 돌리지
않았다.

## 3. CSV/Parquet 산출물 계약

### 3.1 발화 1행 master

연도별로 CSV와 Parquet를 모두 만든다. 6개년 통합 검색은 DuckDB view와
partitioned Parquet를 정본으로 삼는다.

필수 정보군:

1. 식별자: `year`, `utt_id`, 원 세션·화자·대화 참여자 ID
2. 원전·전사: `form`, `original_form`, `tagged`
3. 형태 분석 요약: 형태소 수, 어절 수, 분석 상태, `align_warn`
4. 철자 검색 표시: `form_roman`, `tagged_roman_v2`
5. 발음 출처 분리:
   - 규칙 기반 `pron_reference_*`
   - 우리말샘 보조열과 의미 매칭 상태
   - 공통사전 r2 phone 후보
   - post-MFA 정렬 요약
6. 파일 연결: 원 WAV, 연구용 TextGrid, 정렬 DB/index, quarantine 상태
7. provenance: 입력·코드·스키마·사전·모델 버전과 SHA

발화 1행 CSV에 모든 형태소·음절·phone interval을 가로로 펼치지 않는다.
상세 위치는 정규화 표에서 관리한다.

### 3.2 `morph_tokens`

형태소 1개당 1행이다.

핵심 좌표:

- `utt_id`
- `eojeol_idx`
- `morph_idx_in_eojeol`
- `morph_idx_in_utterance`
- 각 축의 `count`

핵심 값:

- `morph_surface`
- `pos`
- `unit_count`
- 형태소 철자 로마자
- parse/QC 상태

`initial/medial/final/single`은 저장 정본이 아니라 `idx + count`에서 파생한다.

### 3.3 `morph_units`

분석 표면형의 완성형 한글 음절 또는 비한글 literal run 1개당 1행이다.
외부 리뷰의 `morph_syllables`를 그대로 확정하지 않고 다음을 보완한다.

- `unit_idx_in_morph`, `unit_count_in_morph`
- 원 문자열의 `char_start`, `char_end`
- 한글 행에만 nullable `syllable_idx_in_morph`
- `unit_type = hangul | literal`
- 한글 행의 초성·중성·종성 호환 자모 및 각 로마자
- 무음 초성 ㅇ은 `onset_zero=true`로 구조화
- 겹받침은 `coda_jamo=ㄺ`, `coda_roman=lk`만 두고 끝내지 않고
  구성 성분 목록도 별도로 보존

이 구조는 `1층`, 라틴 문자, 기호와 한글이 섞인 형태소의 원래 순서를
잃지 않게 한다.

호환용으로 `unit_type='hangul'`만 거른 `morph_syllables` view를 제공할 수
있다.

### 3.4 철자 구성 성분과 “분절” 용어

외부 리뷰의 “분절 = 음절 슬롯 1토큰”은 그대로 채택하지 않는다.

- ㄺ은 Unicode 호환 자모로는 한 글자이고 종성 슬롯으로는 하나지만,
  철자 구성상 ㄹ+ㄱ을 포함한다.
- ㅘ·ㄲ 등도 연구 질문에 따라 한 슬롯과 구성 성분을 구분해야 한다.
- 이 층을 실제 음성 분절이나 MFA phone으로 부르지 않는다.

정본 `morph_units`에는 슬롯 값과 구성 성분 list를 보존한다. 개별 성분
위치 검색이 필요할 때 `orth_components`를 결정적으로 펼친 파생 view 또는
Parquet 표로 만든다. 60발화에서 저장 크기와 질의 편의성을 비교한 뒤 전수
물질화 여부를 결정한다.

### 3.5 `morph_boundaries`

인접 형태소 쌍 1개당 1행이다. 어절 내부 경계와 어절 사이 경계를 모두
표시하며, 다음 검색에 사용한다.

- 좌·우 형태소/POS
- 좌 마지막 unit의 종성·구성 성분
- 우 첫 unit의 초성·중성·무음 초성 상태
- 동일 어절 여부
- 분석 불일치·축약·literal 관련 상태

이 표는 ㄴ 삽입 등 음운 환경의 **후보**를 찾는 도구다. 실제 실현 여부를
자동 판정하지 않는다.

### 3.6 표시 문자열

`tagged_roman_v2`는 사람 확인과 간단 검색을 위한 파생 표시다. 정본 좌표는
구조화 표에 둔다.

동결할 계층:

```text
분절/슬롯 토큰: `" "`
음절:            `" _ "`
형태소:          `" + "`
어절:            `" | "`
품사:            /POS
literal:         ⟨...⟩
```

정확한 ASCII 공백, NFC, 버전 값을 계약으로 검사한다. 기존 v1은 archive하고
재현 가능성만 보존한다.

외부 리뷰가 추가한 `morph_struct`와 `morph_display`는 전수 master의 필수
중복 열로 바로 채택하지 않는다.

- `morph_struct`: 후보 snapshot에서 JSON으로 생성하거나 DuckDB view로 제공
- `morph_display`: 60발화와 후보 검토 CSV/XLSX에서 가독성 시험
- `!`, `~` 같은 경고 기호를 형태 표기 안에 삽입하지 않고 QC 열로 분리
- 전수 저장은 크기·Excel 길이·실제 검색 이득을 측정한 뒤 결정

## 4. TextGrid 계약

전수 운영 TextGrid는 4개 tier로 제한한다.

1. `words`: MFA word interval
2. `phones_mfa`: MFA phone interval, 실제 실현 판정 아님
3. `utterance`: 사람이 읽는 `form`
4. `utterance_search`: 발화 수준 검색 정보 한 줄

`utterance_search`의 기본 field:

```text
[UTT] <utt_id>
[ORTH_R] <form_roman>
[MORPH] <canonical tagged>
[MORPH_R] <tagged_roman_v2>
[NOTE] <필요한 경우에만 QC 상태>
```

규칙 발음, 우리말샘 발음, KOINA, wav2vec2, 연구자 판정은 기본 4-tier에
넣지 않는다. 선택 후보에서만 온디맨드 tier 또는 동반 CSV로 제공한다.

모든 tier는 `0–xmax`를 빈 interval까지 포함해 연속적으로 덮는다. `utterance`
와 `utterance_search`의 실제 label은 첫 유효 word 시작부터 마지막 유효
word 끝까지 놓고, 앞뒤에는 가시적인 빈 interval을 둔다. 이로써 연구자가
지적한 “처음·끝 경계가 보이지 않는 문제”를 해결한다.

## 5. 단계별 실행 계획

### 단계 0 — 외부 리뷰 정리와 설계 동결 전 수정

목표:

- 채택할 제안과 수정할 제안을 decision 문서에 명시
- “음절 슬롯”과 “철자 구성 성분/분절”을 구분
- 혼합 문자 위치 좌표를 보완
- `morph_struct`, `morph_display`, 경고 기호를 선택 사항으로 되돌림
- preflight가 legacy `tagged_roman` 존재 때문에 불필요하게 막히지 않게 함

완료 gate:

- 예시 5종 + 겹받침 + 숫자/기호 혼합 예시의 기대 출력 확정
- schema/serialization/version 이름 확정
- 코드 변경 전 문서끼리 모순 없음

### 단계 1 — 60발화 텍스트·검색 스키마 파일럿

MFA를 다시 돌리지 않고 기존 60발화 CSV에서 다음을 생성한다.

- 발화 master v2
- `morph_tokens`
- `morph_units`
- `morph_boundaries`
- 선택적 `orth_components`
- 사람이 보는 작은 CSV/XLSX snapshot

자동 gate:

- raw `tagged` 재조립 byte equality
- `tagged_roman_v2` 결정적 재생성
- 음절 compose equality
- 형태소·unit·경계 개수 정합
- NFC·공백·예약문자 검사
- `utt_id` 중복·누락 0
- 의미 layer 좌표와 형태소 좌표 교차 검증

### 단계 2 — 기존 DB에서 60발화 TextGrid 재수출

- MFA 재정렬 없음
- 기존 word/phone interval byte/semantic 동등성 확인
- 새 4-tier와 `utterance_search`만 신규 root에 생성
- legacy 결과는 이름 변경·덮어쓰기 없이 보존

자동 gate:

- 60/60 파일 생성
- tier 이름·순서 4개 정확 일치
- word/phone 시간·라벨 불변
- 모든 tier `0–xmax` 연속
- 앞뒤 빈 경계 존재
- TextGrid 검색 label과 CSV 파생값 byte equality

### 단계 3 — 연구자 수용 검토

전체 60개에 동일 지적을 반복 입력하게 하지 않는다.

- 전역 구조 문제는 `GLOBAL` 결정 1건으로 기록
- 변경된 핵심 예시와 자동 flag 사례를 중심으로 10–12개 확인
- 연도별·화자별 다양성 유지
- WAV/TextGrid/LAB/CSV 연결, 검색성, 가독성만 판단
- 구체적 음운 현상의 실제 실현 여부는 이 단계에서 판정하지 않음

수용되면 schema와 exporter를 동결하고 커밋·푸시한다. 수용 전에는 2020
전수를 시작하지 않는다.

### 단계 4 — 연도별 전수 텍스트 인프라와 MFA

같은 코드 commit과 계약 SHA로 2020부터 2025까지 한 연도씩 진행한다.

```text
연도 N 텍스트 preflight
  → 연도 N master/morph tables 생성·검증
  → LAB 및 공통사전 계약 검증
  → MFA 정렬
  → DB에서 4-tier 직접 export
  → 기계 QC
  → 층화 표본 검토
  → post-MFA 보조 층 생성
  → manifest·archive·공간 정리
  → 다음 연도
```

순서:

```text
2020 → 2021 → 2022 → 2023 → 2024 → 2025
```

2020과 2021도 구결과와 비슷하더라도 r2로 전수 재정렬한다. 구결과는
전환 감사 자료일 뿐 재사용 결과가 아니다.

MFA와 같은 D: 대량 I/O 작업 중에는 다른 연도의 morph 전수 build, archive
압축, KOINA, stitch를 동시에 실행하지 않는다.

연도별 중단 gate:

- 입력·사전·모델·adoption·코드 SHA 불일치
- 허용 phone inventory 밖의 phone
- 실제 `spn` phone 발생
- 설명되지 않은 WAV/LAB/TextGrid 개수 불일치
- DB↔TextGrid word/phone 동등성 실패
- tier 구조·duration·파일명/`utt_id` 불일치
- runner가 정한 D: 여유 공간 기준 미달

개별 불량 원본은 원인을 기록해 quarantine할 수 있지만, 분류되지 않은 실패를
성공으로 처리하지 않는다.

### 단계 5 — post-MFA 보조 층

연도별 정렬 후 다음을 별도 표로 생성한다.

- `mfa_alignment_summary`: 발화 1행
- word interval index
- phone interval index
- `pron_mfa`, 관측 phone 수, `n_spn`, `spn_ratio`
- `align_status`, 누락·난정렬·quarantine 이유
- TextGrid와 DB 경로·SHA
- `phone_class_r_auto`: 원 MFA IPA를 보존한 검색용 로마자 phone 범주
- `phoneme_lexical_r_auto`: raw 철자, 실제 MFA 입력 resolved 철자,
  규칙 예측발음을 참조한 자동 음소 후보와 대응 상태

발화 master에는 요약과 조인 키만 붙인다. 전체 interval을 긴 셀 하나에
밀어 넣지 않는다.

로마자 음소 보조층은 60발화 파일럿에서 구현·기계 검증했다. 기본 4-tier에
상시 넣지 않고 정규화 interval/correspondence 표를 정본으로 하며, 선택
후보에만 `phoneme_r_auto` 5-tier 사본을 만든다. `model_group_only`,
`substitution`, `phone_only`, `reference_only`는 자동 승인하지 않는다.

### 단계 6 — 6개년 통합과 재현성 감사

- 6개년 partitioned Parquet와 DuckDB union view 생성
- 연도별 발화 master CSV도 별도 보존
- 같은 schema/roman/model/dictionary/adoption 계약 사용 여부 전수 감사
- 연도별 관측 phone 집합 차이는 자료 차이로 보고하되 방법 계약 동일성을
  SHA와 manifest로 증명
- 논문 방법론에 사용할 버전·SHA·제외 기준·QC 수치 표 생성

### 단계 7 — 실제 연구 후보와 보조 분석

1. 형태소/표기 환경 SQL로 후보 추출
2. `utt_id`로 WAV/TextGrid/행별 CSV를 한 폴더에 수집
3. 필요 후보에만 이어붙이기와 KOINA 실행
4. 필요 후보에만 wav2vec2 phone을 **추가 보조열/tier**로 생성
5. 연구자가 음성과 TextGrid를 보고 실제 실현 여부를 별도 판정

MFA 또는 wav2vec2가 연구자 판정 열을 덮어쓰지 않는다.

## 6. 저장·archive·배포 원칙

- `C:\...\2026_summer_research`: 코드, 테스트, 문서, 작은 보고서
- `D:\`: 현재 전수 실행, staging, 대형 Parquet/DB/TextGrid
- `E:\`: 검증된 구결과와 중간 대형 산출물의 압축 archive
- Dropbox: 60발화·후보 등 사람이 확인할 작은 묶음
- 원전 corpus: 항상 읽기 전용

새 schema와 새 TextGrid는 새 version root에 만든다. 기존 결과를 덮어쓰거나
이름만 바꾸지 않는다. 삭제·용량 회수는 archive manifest, CRC/SHA, 파일 수,
복원 시험을 통과한 뒤 별도 승인으로 한다.

## 7. 바로 다음 작업

1. Dropbox의 12발화 수정본에서 연결·경계·검색 가독성을 검토한다.
2. `COMBINED_SEARCH_DEMO.xlsx`에서 구조화 조건 → 후보 → WAV/TextGrid/CSV
   연결이 실제로 재현되는지 Q1–Q7 대표 결과를 검토한다.
3. 반복 문제는 행마다 장문으로 쓰지 않고 공통 코드와 예외 메모로 기록한다.
4. 연구자 수용 결과를 machine gate와 결합해 인프라 승인 보고서를 만든다.
5. 승인 뒤 2020 전수 MFA를 시작하고, 연도별 QC 뒤에만 다음 연도로 간다.

현재 연구자가 실행할 PowerShell 대량 명령은 없다. 먼저 같은 Dropbox
폴더의 `REVIEW.xlsx`와 `COMBINED_SEARCH_DEMO.xlsx`를 검토한다. 연구자
수용 전에 전수 MFA를 시작하면 수정본의 표시·조합 검색 문제가 해결됐는지
확인하지 않은 채 6개년에 복제할 위험이 있다.
