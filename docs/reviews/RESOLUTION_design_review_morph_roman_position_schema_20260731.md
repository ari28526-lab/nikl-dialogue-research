# 형태소·철자 로마자 위치 검색 설계 리뷰 반영 결과

- 일자: 2026-07-31
- 외부 리뷰:
  `RESULT_design_review_morph_roman_position_schema_20260731.md`
- 판정: **필수 정정 반영 뒤 60발화 기계 파일럿 통과**
- 연구자 수용 상태: **12발화 수정본 검토 대기**
- 전수 MFA: **아직 시작하지 않음**

## 1. 연구 목적에 따른 최종 판단

이 스키마의 목적은 자동으로 음운 현상의 실현 여부를 판정하는 것이 아니다.
형태소·표기 환경으로 후보를 정확히 검색하고, 해당 WAV·TextGrid·CSV를
연결해 연구자가 실제 실현을 판단할 수 있게 하는 인프라를 만드는 것이다.

따라서 다음을 분리한다.

- 형태소·철자·위치 정보: pre-MFA 구조화 검색 표
- MFA word/phone: 청취 위치를 찾는 자동 정렬 보조값
- 규칙·사전 발음: 출처가 분명한 별도 보조열
- KOINA·wav2vec2: 선택 후보에만 추가하는 독립 보조 산출물
- 실제 실현 판정: 연구자가 별도 판정표에 기록

## 2. 외부 리뷰에서 채택한 사항

1. 정밀 검색 정본은 긴 직렬화 문자열이 아니라 정규화 표로 둔다.
2. 위치는 `idx`와 `count`를 함께 저장해 첫·가운데·끝을 재현한다.
3. 표시·기초 검색용 로마자는 `tagged_roman.v2`로 versioning한다.
4. 숫자·영문·기호 등은 `⟨…⟩` literal로 명시해 로마자 토큰과 구분한다.
5. 모든 생성 한글 필드는 NFC로 정규화하고 변경 여부를 기록한다.
6. TextGrid는 `words/phones_mfa/utterance/utterance_search` 4-tier로 줄인다.
7. 기존 60발화 DB를 재사용해 출력만 다시 만들고 MFA는 재실행하지 않는다.

## 3. 리뷰안을 그대로 채택하지 않고 정정한 사항

### 3.1 음절 슬롯과 분절을 동일시하지 않음

리뷰는 `segment = 음절 슬롯 토큰`으로 보았지만 연구 언어학의 정본으로는
지나치게 강한 동일시다. 예를 들어 겹받침 `ㄺ`은 음절의 종성 슬롯 하나를
차지하지만 구성 자모 `ㄹ+ㄱ`을 가진다. 복합 모음도 같은 문제가 있다.

따라서 구현은 다음을 함께 보존한다.

- `morph_units`: 순서가 있는 표층 단위와 초성·중성·종성 슬롯
- `orth_components`: 슬롯의 구성 자모를 순서대로 나타내는 파생 표

문자열 `lk`를 두 글자로 잘라 분절이라고 추측하지 않는다. slot 로마자와
구성 자모는 출처와 단위가 다른 정보로 유지한다.

### 3.2 `morph_syllables` 대신 `morph_units`

형태소 표면에는 완성형 음절뿐 아니라 독립 자모와 기호가 나타난다. 이를
음절 표에 억지로 넣으면 단위명이 거짓이 되거나 검색 대상이 사라진다.

`morph_units`는 다음 세 종류를 명시한다.

- `hangul`: 완성형 한글 음절
- `jamo`: 독립 자모
- `literal`: 숫자·영문·문장부호 등 비한글 run

독립 `ㄴ`, `ㄹ` 등도 각각 검색 가능한 단위와 로마자 `n`, `l`을 가진다.
literal은 원문을 보존하고 읽는 법을 추측하지 않는다.

### 3.3 큰 중복 열과 QC 기호를 정본에 넣지 않음

- 전체 `morph_struct`, `morph_display`를 발화 master의 필수 대형 열로
  중복하지 않는다. 정규화 표에서 결정적으로 재생성할 수 있다.
- `!`, `~` 같은 QC 상태를 로마자 직렬화 안에 삽입하지 않는다. 검색
  문자열과 품질 상태가 섞이지 않도록 `align_warn` 등 별도 열로 둔다.
- 구 `tagged_roman` v1은 비교 감사에는 쓸 수 있지만 새 전수 빌드의
  필수 입력 gate로 삼지 않는다.

## 4. 동결한 버전과 직렬화 계약

```text
roman_system_version       = roman_mfa.v1
serialization_version      = tagged_roman.v2
position_schema_version    = morph_position.v1
search_schema_version      = morph_search.v1
utterance_search_version   = utterance_search.v1
```

`tagged_roman.v2`의 정확한 계층 구분자는 다음과 같다.

```text
분절 토큰: " "
음절/단위: " _ "
형태소:   " + "
어절:     " | "
품사:     "/POS"
literal:  "⟨원문⟩"
```

정밀 위치 검색은 이 문자열을 다시 파싱하지 않고 `morph_tokens`,
`morph_units`, `morph_boundaries`, 필요 시 `orth_components`를 질의한다.
직렬화는 같은 정본 함수로 다시 생성해 바이트 동일성을 검사한다.

## 5. TextGrid 동결 계약

전수 운영용 연구 TextGrid:

```text
words
phones_mfa
utterance
utterance_search
```

`utterance_search`에는 다음 필드만 둔다.

```text
[UTT]
[ORTH_R]
[MORPH]
[MORPH_R]
[NOTE]   # align_warn가 있을 때만
```

형태소별 음향 시간을 주장하는 tier는 두지 않는다. 위치 정본은 CSV/Parquet
표이고, TextGrid의 발화 수준 문자열은 Praat에서 찾아보기 위한 복제본이다.
`phones_mfa`는 실제 실현 판정이 아니다.

## 6. 60발화 파일럿 실측

보존한 2020–2025 파일럿 DB·CSV를 읽어 출력만 새로 만들었다. 연도당
10발화이며 MFA 정렬은 다시 실행하지 않았다.

```text
D:\mfa_eojeol\pilots\r2_infrastructure\
  mfa_r2_infra_pilot_20260730\
  research_schema_v1_20260731
```

구조화 표:

- 발화: 60
- `morph_tokens`: 548
- `morph_units`: 809
  - hangul 757
  - jamo 25
  - literal 27
- `morph_boundaries`: 488
- `orth_components`: 1,847

자동 gate:

- 중복 `utt_id`: 0
- tagged parse error: 0
- v2 재생성 불일치: 0
- 한글 음절 재조합 불일치: 0
- 경계 수 `n_morphs-1` 불일치: 0
- 새 TextGrid 유효성: 60/60
- 기존 DB word/phone과 새 `words/phones_mfa` 의미 동등성: 60/60
- CSV와 TextGrid `[MORPH]`, `[MORPH_R]` 동등성: 60/60

자연 원시간 TextGrid에서는 발화가 파일 시작·끝에 닿으면 빈 interval이
없을 수 있다. 이는 없는 무음을 만들어내지 않는 운영 원칙이다. 연구자
점검 사본은 WAV 좌우에 0.05초 무음을 추가하고 모든 tier를 함께 이동해
12/12에서 양끝 경계를 가시화했다.

## 7. 연구자 검토 묶음

```text
C:\Users\ari30\Dropbox\MFA_RESEARCH_SCHEMA_REVIEW_12_20260731
```

- 2020–2025 연도별 2발화, 총 12발화
- WAV/TextGrid/LAB/행별 CSV 4종 연결
- 구조화 검색 표 4종 동봉
- `REVIEW.xlsx`, `REVIEW.csv`, 열 안내와 변경 요약 포함
- 48개 상대경로 링크, dropdown, 파일 크기·SHA-256 검증
- WAV/TextGrid duration 및 좌우 0.05초 경계 검증

Dropbox 동기화가 폴더 rename을 잠근 1회 실패는 부분 폴더의 manifest,
파일별 크기·SHA-256, workbook 링크를 전수 재검증한 뒤 승격했다. payload를
다시 복사하거나 원본을 변경하지 않았다.

## 8. 다음 gate

연구자는 12발화에서 다음만 확인한다.

1. WAV와 LAB가 같은 발화인지
2. 기존 `words/phones_mfa`가 보존됐는지
3. 점검 사본의 좌우 빈 경계가 보이는지
4. `[MORPH]`가 사람이 읽기 쉬운지
5. `[MORPH_R]`로 형태소·단위 검색이 가능한지

구체적 음운 실현 여부는 이 인프라 검토에서 판정하지 않는다. 연구자
수용 뒤에만 2020 r2 전수 MFA 명령을 확정한다.
