# 외부 설계 리뷰 요청: 형태소·음절·분절 단위 로마자와 위치 검색 스키마

아래 `복사용 프롬프트` 전체를 다른 도구에 전달한다. 저장소 주소는 이미
기입돼 있다. 이번 요청은 코드 구현이 아니라 **대량 구축 전에 검색 표현과
자료 스키마를 동결하기 위한 독립 설계 리뷰**다.

---

## 복사용 프롬프트

당신은 한국어 음운론·형태론, 말뭉치 언어학, 음성 코퍼스 인프라,
Praat TextGrid, 형태소 분석, 대규모 CSV/Parquet 자료 모델링 경험이 있는
독립 방법론·코드 리뷰어다.

다음 GitHub 저장소의 **코드와 문서만 읽고**, 형태소·음절·분절 단위의
철자 로마자 표현과 위치 기반 검색 스키마를 비판적으로 설계해 달라.

```text
저장소: https://github.com/ari28526-lab/nikl-dialogue-research
검토 브랜치: agent/harden-pre-bulk-pipelines
코드·기존 설계 기준 커밋: bd77bd3
이번 요청 문서:
docs/reviews/PROMPT_external_review_morph_roman_position_schema_20260731.md
```

로컬 D: 코퍼스와 Dropbox 실물에는 접근할 수 없다고 가정하라. 저장소에 없는
실측값은 추정하지 말고 `확인 불가`라고 써 달라. 코드를 수정하거나 PR을
만들지 말고, 이번에는 **정규형 표현·구분자 문법·정규화 표·검색 API·검증
계약**에 집중해 달라.

### 1. 연구의 실제 목적

이 프로젝트의 흐름은 다음과 같다.

```text
CSV/Parquet에서 특정 형태소 또는 표기상 음운·형태 환경 검색
→ 해당 발화의 WAV와 TextGrid를 utt_id로 수집
→ 필요한 후보에 KOINA 또는 보조 분석 추가
→ 연구자가 음성과 TextGrid를 보고 실제 실현 여부 판정
```

따라서 지금 만드는 것은 실제 실현 자동 판정기가 아니라, 이후 연구자가
후보를 빠짐없이 찾고 관련 파일을 검토할 수 있게 하는 **연구 인프라**다.

다음 층은 끝까지 구분해야 한다.

- 한글 철자와 철자에서 분해한 자모·로마자
- Bareun 형태소 표면형·품사 분석
- 규칙 기반 문맥 예상 발음
- 우리말샘 등 사전 독립형 발음
- MFA가 자동 정렬한 phone
- 향후 선택 후보에만 추가할 wav2vec2 phone
- 연구자의 실제 실현 판정

이 요청의 `roman`은 기본적으로 **철자 구조 검색을 위한 프로젝트 로마자
전자**다. 개정 로마자 표기, 실제 발음, MFA phone과 동일하지 않다.

### 2. 이미 완료된 관련 리뷰와 새 쟁점

직전 외부 리뷰 결과는 다음 문서에 있다.

```text
docs/reviews/RESULT_design_review_TextGrid_utterance_search_tier_20260731.md
```

그 리뷰는 기본 TextGrid에 다음 4-tier를 권장했다.

```text
words
phones_mfa
utterance
utterance_search
```

`utterance_search`는 발화 수준 단일 label에 다음을 두는 안이다.

```text
[UTT] ...
[ORTH_R] ...
[MORPH] ...
[MORPH_R] ...
```

이 방향은 형태소마다 근거 없는 음향 시간경계를 만들지 않고, TextGrid 안의
표시·기초 검색을 가능하게 한다는 점에서 유력하다.

그러나 직전 리뷰는 정밀 환경 검색용 `morph_tokens`·`morph_boundaries`를
“나중 개선”으로 분류했다. 연구자는 형태소의 시작·내부·끝, 음절 내
초성·중성·종성, 형태소 및 어절 경계의 좌우 로마자 환경을 안정적으로
검색하는 것이 핵심이라고 판단한다. 따라서 이번 리뷰에서는 이 구조를
**전수 인프라 이전 필수 계약으로 올려야 하는지** 다시 판정해야 한다.

### 3. 현재 직렬화 규칙

현행 `tagged_roman`은 다음 위계를 사용한다.

```text
분절 토큰 사이  ASCII 한 칸 공백
음절 경계       " _ "
형태소 경계     " + "
어절 경계       " | "
품사            형태소 표현 뒤 "/POS"
```

이를 형식 문법으로 쓰면 대략 다음과 같다.

```text
utterance := eojeol (" | " eojeol)*
eojeol    := morph (" + " morph)*
morph     := syllable (" _ " syllable)* "/" POS
syllable  := segment (" " segment)*
```

대표 실자료:

```text
utt_id:
SDRW2200000836.1.1.61

form:
꽃에 모양은 어땠어?

tagged:
꽃/NNG+에/JKB 모양/NNG+은/JX 어떻/VA+었/EP+어/EF+?/SF

form_roman:
KK O ch _ E | M O _ YA ng _ EU n | EO _ TT AE ss _ EO

tagged_roman:
KK O ch/NNG + E/JKB | M O _ YA ng/NNG + EU n/JX | EO _ TT EO h/VA + EO ss/EP + EO/EF + ?/SF
```

이 값은 2026-07-31 읽기 전용 로컬 확인에서 동결 pre-MFA CSV의 실제 행과
일치했다. 저장소 밖 실물 확인이므로 외부 리뷰어는 독립 재검증할 수 없으며,
제공된 관측값으로만 다뤄 달라.

### 4. 로컬에서 추가 확인한 입력 계약

동결 pre-MFA root는 문서에 열거된 LAB 필수 5열만 가진 파일이 아니었다.
2020–2025 각 연도 표본 CSV는 모두 48열이었고 다음 열을 포함했다.

```text
utt_id
form
original_form
tagged
n_eojeol
form_roman
tagged_roman
align_warn
```

따라서 새 구조화 색인은 원 JSON이나 Bareun API를 다시 실행하지 않고도
이 동결 CSV에서 파생할 수 있을 가능성이 높다. 다만 표본 헤더 확인과
전수 값 완전성은 다르므로, 구현 전 전수 preflight 계약은 별도로 필요하다.

직전 리뷰 문서의 “동결 pre-MFA 층은 5열뿐”이라는 표현은 실제 표본 헤더와
맞지 않는다. 이 오류가 새 설계 판단에 영향을 주지 않도록 바로잡아 달라.

### 5. 현재 문자열만으로 생기는 문제

#### 5.1 위치 단위가 모호함

“어두·어중·어말” 또는 “처음·중간·끝”만으로는 다음을 구분할 수 없다.

- 발화의 처음·중간·끝
- 어절의 처음·중간·끝
- 어절 안에서 형태소가 처음·중간·끝인지
- 형태소 안에서 음절이 처음·중간·끝인지
- 음절 안의 초성·중성·종성
- 로마자 분절 토큰이 형태소 안에서 몇 번째인지

예를 들어 어떤 형태소는 어절의 두 번째 형태소이지만, 그 형태소 자체의 첫
음절과 첫 분절은 각각 형태소 시작 위치다. 하나의 `is_initial` 열로는
연구 환경을 재현할 수 없다.

#### 5.2 가변 길이 로마자 토큰

`KK`, `EO`, `ng`, `ch` 등은 문자열 글자 수가 서로 다르다. 로마자 문자열을
문자 단위로 자르면 분절 토큰을 잘못 해석한다. 공백으로 분리된 원자적
`segment` 토큰과 음절 내 역할을 보존해야 한다.

#### 5.3 무음 초성 `ㅇ`

현행 표시 로마자에서 음절 초성 `ㅇ`은 별도 토큰으로 나타나지 않는다.

```text
요즘 → YO _ J EU m
에   → E
```

따라서 문자열만 보면 해당 음절이 철자상 초성 `ㅇ`을 가졌는지 직접 검색하기
어렵다. ㄴ 삽입 후보처럼 우측의 표기상 무음 초성과 i/y 계열 모음을 함께
봐야 하는 환경에는 `onset_jamo=ㅇ`, `onset_zero=true` 같은 구조화 정보가
필요할 수 있다.

단, 표시 문자열에 `Ø` 같은 새 토큰을 넣으면 연구자가 삭제·무실현 기호나
MFA phone으로 오해할 위험이 있다. 명시 토큰을 도입할지, 구조화 열에만
보존할지를 검토해 달라.

#### 5.4 품사 표지와 마지막 분절

현행 `morph_roman`은 품사를 마지막 로마자 토큰 바로 뒤에 붙인다.

```text
KK O ch/NNG
YO _ J EU m/NNG
```

문법상 `/NNG`는 형태소 전체의 품사지만, 육안이나 단순 검색에서는 마지막
분절 `ch`, `m`에 붙은 것처럼 보인다. 현행 `/POS`를 유지할지, 공백을 둔
` / POS`, 별도 구조화 열, 다른 안정적인 표지를 사용할지 검토가 필요하다.

#### 5.5 예약문자와 왕복 복원

`_`, `+`, `|`, `/`, 대괄호가 실제 문장부호·외국어·비언어 표지에 나타날
가능성이 있다. TextGrid label은 CSV 정본의 표시 사본이므로 반드시 무손실
파서여야 하는지는 논쟁적이지만, CSV/Parquet 파생 과정과 자동 검증은
조용한 오분석을 허용하면 안 된다.

직전 리뷰의 검증안은 `[MORPH]`에서 ` | `만 공백으로 복원해 raw `tagged`와
비교한다고 했지만, 표시형은 형태소 경계도 `+`에서 ` + `로 바뀔 수 있다.
단순 부분 치환보다 `canonicalize_tagged(tagged)`의 출력과 label field를
직접 비교하는 편이 안전한지 검토해 달라.

### 6. 내부 잠정 데이터 모델

아래는 확정안이 아니라 외부 검토를 위한 출발점이다.

#### 6.1 `utterances`

행 단위: 발화 1개. 기존 세션별 CSV와 전연도 검색 마스터 역할을 유지한다.

```text
utt_id, year, session_id, speaker_id
form, original_form, tagged
form_roman, tagged_roman
roman_system_version, serialization_version
align_warn, n_eojeol
```

#### 6.2 `morph_tokens`

행 단위: 형태소 1개.

```text
utt_id
eojeol_idx
morph_idx_in_eojeol
morph_idx_in_utterance
morph_count_in_eojeol
morph_count_in_utterance
morph_surface
pos_bareun
morph_roman
morph_position_in_eojeol
morph_to_form_status
```

`morph_position_in_eojeol` 같은 편의 범주보다 인덱스와 전체 개수를 정본으로
두고 `single/initial/medial/final`을 파생하는 것이 더 안전할 수 있다.

#### 6.3 `morph_syllables`

행 단위: 형태소를 이루는 한글 음절 또는 비한글 단위 1개.

```text
utt_id
eojeol_idx
morph_idx_in_eojeol
syllable_idx_in_morph
syllable_count_in_morph
syllable_idx_in_eojeol
syllable_count_in_eojeol
syllable_surface
syllable_roman
onset_jamo
onset_roman
onset_zero
nucleus_jamo
nucleus_roman
coda_jamo
coda_roman
unit_type
parse_status
```

이 표가 필요한지, 아니면 `morph_tokens`의 list 열 또는 더 작은
`morph_segments` 표가 나은지 비교해 달라.

#### 6.4 `morph_boundaries`

행 단위: 인접한 형태소 또는 어절 경계 1개.

```text
boundary_id
utt_id
boundary_idx
boundary_scope
left_eojeol_idx, left_morph_idx
right_eojeol_idx, right_morph_idx
left_surface, left_pos
right_surface, right_pos
left_final_jamo_underlying
left_final_roman
right_initial_jamo_underlying
right_initial_roman
right_initial_onset_zero
right_initial_nucleus_jamo
within_same_eojeol
crosses_eojeol
map_status
```

이 표는 후보 환경을 찾는 인프라다. ㄴ 삽입 등 특정 현상의 실제 실현을
자동 판정하거나 확정하는 표가 아니다.

### 7. 반드시 검토할 설계 질문

1. 현행 `공백 / _ / + / | / /POS` 위계는 사람 가독성, 기계 파싱,
   Praat 검색, 장기 호환성 측면에서 유지할 만한가?
2. exact delimiter는 주변 ASCII 공백까지 포함해 어떻게 동결해야 하는가?
3. POS는 현행 `/POS` 후치를 유지해야 하는가? 형태소 전체의 속성임을 더
   명확히 하면서 기존 510만 행과 호환되는 방법은 무엇인가?
4. 표시용 문자열과 정밀 검색 정본을 분리해야 하는가?
   - 기존 `tagged_roman`을 표시·기초 검색용으로 보존
   - 구조화 Parquet을 위치 검색 정본으로 신설
   - 새 `tagged_roman_v2`도 함께 만들기
   위 선택지의 장단점을 비교하라.
5. `segment`의 정확한 정의는 무엇이어야 하는가?
   - 프로젝트 로마자 원자 토큰
   - 한글 자모
   - 음절 내 초성·중성·종성 슬롯
   - MFA phone
   이들을 어떤 이름과 열로 분리해야 오해가 없는가?
6. 형태소별 어두·어중·어말 검색에는 `morph_syllables`가 필요한가?
   `morph_segments` 또는 Parquet list 열이 더 효율적인가?
7. 위치 정본은 `initial/medial/final` 문자열보다
   `idx + count`로 두고 위치 범주를 파생하는 것이 나은가?
8. 형태소·어절·발화 위치를 한 열로 합치지 않고 어떤 최소 좌표 집합으로
   분리해야 하는가?
9. 무음 초성 `ㅇ`은 표시 로마자에 명시 토큰으로 넣어야 하는가, 아니면
   `onset_zero` 구조화 열에만 두어야 하는가?
10. 복합 종성·겹자음·이중모음과 `KK/TT/PP/SS/JJ`, `ng/ch` 같은 가변 길이
    토큰을 어떻게 원자 단위로 보존해야 하는가?
11. 숫자, 영문, 한자, 이모지, 비언어 표지, 문장부호, `/ + | _ [ ]`,
    분석 실패를 어떻게 표현하고 어떤 경우 hard fail·flag·literal 보존을
    해야 하는가?
12. raw `tagged`와 정규화 표시형의 왕복 또는 동등성 검증은 정확히 어떤
    함수·규칙으로 해야 하는가?
13. NFC/NFD, ASCII/비ASCII 공백, 연속 공백, 줄바꿈에 대한 정규화 정책은
    무엇이어야 하는가?
14. 약 510만 발화에서 `morph_tokens`, `morph_syllables`,
    `morph_boundaries`를 전량 만들 때 현실적인 저장 형식과 partition은
    무엇인가?
    - 세션별 CSV
    - 연도별/partitioned Parquet
    - DuckDB 색인
    - 다른 방식
15. Excel·Praat에서 사람이 확인할 작은 CSV와 대규모 정본 Parquet의 역할을
    어떻게 나눠야 하는가?
16. TextGrid `[MORPH_R]`에는 구조화 정보를 어디까지 복제해야 하는가?
    위치 좌표 전체를 넣지 않고 기존 직렬화 한 줄만 표시하는 것이 타당한가?
17. 형태소 분석 오류, `form`–`tagged` 어절 불일치, 축약·융합
    (`어떻+었+어 → 어땠어`)을 어떻게 flag하면서 형태소 정보를 보존할까?
18. 어떤 60발화 파일럿 표본과 edge case를 거쳐야 이 문법과 스키마를
    전수에 적용해도 되는가?
19. 기존 `tagged_roman`을 보존하면서 새 구조를 도입하는 migration 및
    schema/version 계약은 무엇인가?
20. 이 구조가 완성되기 전에 2020 전수 MFA를 시작해도 되는가?
    정렬 DB를 보존하면 검색층과 TextGrid를 나중에 재수출할 수 있다는 점과,
    대량 재작업 위험을 함께 고려해 단계 순서를 제안하라.

### 8. 반드시 비교할 세 가지 대안

#### 대안 A: 기존 문자열 유지 + 구조화 표 신설

```text
tagged_roman v1은 표시·호환용으로 보존
morph_tokens/morph_syllables/morph_boundaries를 정밀 검색 정본으로 신설
TextGrid는 v1 직렬화를 [MORPH_R]에 복제
```

#### 대안 B: 직렬화 v2도 신설

```text
기존 tagged_roman은 legacy로 보존
POS·무음 초성·escaping을 보완한 tagged_roman_v2 추가
구조화 표도 함께 생성
TextGrid에는 v1 또는 v2 중 하나를 명시적으로 선택
```

#### 대안 C: 복합 문자열 최소화

```text
기존 tagged_roman은 과거 자산으로만 보존
정밀 검색은 구조화 표에서만 수행
TextGrid에는 한글 형태소 또는 최소 검색 키만 둠
```

단순히 “정규식을 잘 쓰면 된다”라고 결론 내리지 말고, 연구 재현성,
표시 가독성, 대량 저장·재생성 비용, 위치 검색의 정확성을 함께 비교하라.

### 9. 변경해서는 안 되는 기준

- 원 WAV·JSON·기존 CSV의 제자리 수정 금지
- 기존 `tagged_roman` 값을 설명 없이 덮어쓰지 않음
- MFA DB의 word·phone interval 불변
- 2020–2025 공통 acoustic·Jamo G2P·공통 발음사전·phone inventory 불변
- 철자 로마자와 MFA phone을 같은 값으로 취급하지 않음
- 규칙 발음·사전 발음·MFA phone·wav2vec2·연구자 판정을 별도 출처로 보존
- 형태소 경계에 근거 없는 음향 시간경계를 만들지 않음
- `utt_id` 기반 WAV/TextGrid/CSV/LAB 연결 유지
- 새 출력은 별도 staging/schema version으로 만들고 기존 결과를 덮어쓰지 않음

이번 스키마 검토는 phone 기준을 바꾸거나 MFA 정렬 결과를 폐기하는 문제가
아니다. 보존된 60발화 pilot DB에서는 TextGrid와 검색 파생표만 재수출할 수
있어야 한다. 향후 2020–2025 전수 r2 MFA는 여전히 같은 공통 기준으로 새로
실행할 계획이다.

### 10. 반드시 읽을 저장소 파일

다음 순서로 읽어 달라.

```text
docs/environment/PROJECT_CURRENT_STATE.md
docs/reviews/RESULT_design_review_TextGrid_utterance_search_tier_20260731.md
docs/reviews/PROMPT_external_review_TextGrid_utterance_search_tier_20260730.md
docs/decisions/DESIGN_pronunciation_environment_search_2026-07-25.md
docs/decisions/DECISION_mfa_r2_review_global_issues_20260730.md
docs/decisions/WORKFLOW_r2_MFA_research_data_contract_20260730.md
docs/decisions/STANDARD_textgrid_tiers.md

scripts/python/build_search_master.py
scripts/python/predict_pron.py
scripts/python/assign_sense_layer.py
scripts/python/build_stratified_mfa_review_bundle.py
scripts/python/export_mfa_db_4tier.py

tests/test_build_search_master.py
tests/test_build_stratified_mfa_review_bundle.py
tests/test_export_mfa_db_4tier.py
```

과거 문서의 결론을 현재 확정안으로 전제하지 말라. 문서 간 충돌과 실동작
코드의 차이를 파일·함수 근거와 함께 지적하라.

### 11. 요구하는 답변 형식

다음 순서로 답해 달라.

1. **한 문단 결론**
2. **용어와 단위 정의**
   - grapheme/jamo/roman segment/syllable/morpheme/eojeol/phone
3. **권장 직렬화 문법**
   - EBNF 또는 동등한 형식 문법
   - exact separator와 whitespace
   - POS·escaping·Unicode normalization
4. **권장 정규화 데이터 모델**
   - 표별 한 행의 단위
   - 정확한 열·형·nullable/flag
   - 정본과 파생 열 구분
5. **위치 좌표 설계**
   - 형태소·어절·발화 시작/내부/끝을 구분하는 방법
6. **대표 예시 최소 5개**
   - `혹시 요즘`
   - `꽃에 모양은 어땠어?`
   - 한 형태소 안의 여러 음절
   - 복수 형태소 어절
   - 숫자·문장부호·비한글·불일치
7. **실제 검색 예시**
   - 형태소 첫 음절의 특정 초성/모음/종성
   - 형태소 내부의 특정 로마자 분절
   - 어절 내부 형태소 경계
   - 어절 사이 경계
   - 무음 초성 `ㅇ` 환경
8. **대안 A/B/C 비교표와 최종 선택**
9. **TextGrid와 CSV/Parquet 역할 분담**
10. **510만 발화 규모 저장·성능 추정과 확인 불가 항목**
11. **마이그레이션·schema version·archive 정책**
12. **자동 검증 gate와 연구자 파일럿 확인 항목**
13. **코드 변경 지점과 구현 순서**
14. **2020 전수 MFA 시작 전 반드시 완료할 것과 병행 가능한 것**

각 판단에는 가능한 한 저장소 파일·함수·문서 절을 근거로 달라. 특히
`morph_tokens/morph_syllables/morph_boundaries`를 실제 연구 질문과 무관한
과잉 설계로 볼지, 위치 기반 환경 검색에 필요한 최소 정규화로 볼지를
분명히 판정해 달라.

---

## 현재 내부 잠정 판단

외부 리뷰를 강제하지 않되 현재 내부 판단은 다음과 같다.

1. 현행 `tagged_roman`은 삭제·덮어쓰기 없이 표시·호환용으로 보존한다.
2. 정확한 위치 검색은 긴 문자열 정규식이 아니라 구조화
   `morph_tokens/morph_syllables/morph_boundaries`에서 수행한다.
3. 위치 정본은 `initial/medial/final`만 저장하지 않고 `idx + count`로
   보존하며 편의 범주를 파생한다.
4. 무음 초성 `ㅇ`은 우선 구조화 열에 명시하고, 표시 문자열에 새 `Ø` 토큰을
   넣는 것은 오해 가능성을 검토한 뒤 결정한다.
5. TextGrid의 `[MORPH_R]`은 표시·개별 파일 검색용이며 전량 후보 추출의
   정본은 CSV/Parquet이다.
6. 이 구조의 설계와 60발화 파일럿 검증은 전수 인프라 승인 전에 필요하다.
