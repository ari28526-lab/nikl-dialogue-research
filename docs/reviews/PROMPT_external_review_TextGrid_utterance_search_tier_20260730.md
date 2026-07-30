# 외부 설계 리뷰 요청: TextGrid 발화 수준 로마자·형태소 검색 tier

아래 프롬프트에서 `[저장소 URL]`만 실제 GitHub 주소로 바꾸어 사용한다.

---

## 복사용 프롬프트

당신은 한국어 음성학·음운론 연구 인프라, Praat TextGrid, 형태소 분석,
Montreal Forced Aligner(MFA), 대규모 코퍼스 자료 설계 경험이 있는
독립 코드·방법론 리뷰어다.

다음 GitHub 저장소의 **코드와 문서만 읽고**, 아래 TextGrid 출력 설계를
비판적으로 검토해 달라.

```text
저장소: [저장소 URL]
검토 브랜치: agent/harden-pre-bulk-pipelines
검토 기준 커밋: b0f5077
```

로컬 D: 코퍼스나 Dropbox 파일은 접근할 수 없다고 가정하라. 저장소에 없는
실측값을 추정하지 말고, 코드·문서만으로 확인할 수 없는 것은 명시적으로
`확인 불가`라고 써 달라. 코드를 직접 수정하거나 PR을 만들지 말고,
이번에는 **입출력 형식과 방법론 설계 리뷰**에 집중해 달라.

### 1. 연구의 실제 흐름

이 프로젝트의 목적은 MFA phone으로 음운현상의 실제 실현 여부를 자동
판정하는 것이 아니다.

```text
형태소·표기 환경을 CSV/Parquet에서 검색
→ 해당 WAV와 TextGrid 수집
→ 필요한 후보에 KOINA 운율 분석
→ 연구자가 WAV와 TextGrid를 보고 실제 실현 여부 판정
```

다음 자료는 끝까지 구분한다.

- 철자와 철자 기반 로마자
- Bareun 형태소 분석
- 규칙 기반 문맥 예상 발음
- 우리말샘 등 사전 독립형 발음
- MFA가 정렬한 phone
- 향후 선택 후보에만 추가할 wav2vec2 phone
- 연구자의 실제 실현 판정

MFA phone은 대략적인 정렬·탐색 보조층이며 실제 실현 판정값이 아니다.

### 2. 현재 r2 파일럿

- 2020–2025, 연도당 10발화·5화자·5세션, 총 60발화
- 같은 acoustic model, Jamo G2P, 공통 발음사전, phone inventory 사용
- 실제 `spn=0`, 허용 phone 밖 값 0
- MFA DB의 word·phone interval과 직접 내보낸 TextGrid 표본 동등성 통과
- 전수 MFA는 아직 시작하지 않음

현재 운영 파일럿 TextGrid는 다음 4-tier다.

```text
words
phones
morphemes
utterance
```

문제는 `morphemes`다. 이 tier는 현재 Bareun 형태소 분석을 시간 정렬한
것이 아니라 과거 `06_textgrid_merged`의 `words` 경계를 복사한 legacy
자료다. 연구자 첫 검토에서는 `words`와 시작·끝이 달라 형태소의 실제
음향경계처럼 오해될 수 있음이 확인됐다.

저장소에 기록된 60발화 읽기 전용 대조 결과:

- legacy 4-tier 구성: 60/60
- `words`와 `morphemes`의 유표 라벨 순서까지 직접 비교 가능한 파일: 6
- 그 6개 중 시간경계까지 완전히 같은 파일: 0
- 구조 또는 시간이 다른 파일: 60
- 비교 가능한 최대 경계 차이: 0.245초

따라서 연구자는 **형태소별 시간 분절 tier를 원하지 않는다**.

### 3. 사용자가 원하는 핵심

TextGrid 자체를 열었을 때 다음 정보를 발화 수준에서 검색하고 싶다.

1. 발화 한글 표기
2. 발화 철자 기반 `roman_mfa` 표기
3. Bareun 형태소 표기(`surface/POS`, 형태소·어절 경계 포함)
4. 가능하면 형태소 철자 로마자 표기

즉, 형태소마다 임의의 시간경계를 만드는 대신 **발화 전체 구간에 하나의
검색용 label**을 두려는 것이다.

현재 search master에는 최소한 다음 값이 있다.

```text
form
original_form
tagged
form_roman
tagged_roman
pron_reference_hangul
pron_reference_roman
utt_id
```

현재 `tagged_roman` 구분자는 다음과 같다.

```text
phone token   공백
syllable      _
morpheme      +
eojeol        |
POS           /POS
```

예:

```text
form:
혹시 요즘

form_roman:
H O k _ S I | YO _ J EU m

tagged:
혹시/MAG 요즘/NNG

tagged_roman:
H O k _ S I/MAG | YO _ J EU m/NNG
```

이 로마자는 철자 전자이며 개정 로마자 표기가 아니다. 실제 발음이나
MFA phone도 아니다.

### 4. 현재 고려 중인 선택지

다음은 확정안이 아니라 검토를 위한 후보안이다.

#### 후보 A: 4-tier

```text
words
phones_mfa
utterance
utterance_search
```

- `words`: MFA DB의 어절 시간 정렬
- `phones_mfa`: MFA DB의 phone 시간 정렬
- `utterance`: 한글 `form`
- `utterance_search`: 발화 수준의 철자 로마자·형태소·형태소 로마자

`utterance_search` label 예:

```text
[ORTH_R] H O k _ S I | YO _ J EU m
[MORPH] 혹시/MAG | 요즘/NNG
[MORPH_R] H O k _ S I/MAG | YO _ J EU m/NNG
```

실제 TextGrid에서는 줄바꿈 대신 안전한 한 줄 field marker를 사용할 수 있다.

이 안의 장점은 일반 한글 발화를 읽는 tier와 긴 검색 표지를 분리하면서도
tier 수를 4개로 유지하는 것이다.

#### 후보 B: 3-tier

```text
words
phones_mfa
utterance_search
```

한 label 안에 `[FORM]`, `[ORTH_R]`, `[MORPH]`, `[MORPH_R]`를 모두 넣는다.
가장 작지만 Praat에서 label이 길어지고 일반 전사 가독성이 낮아질 수 있다.

#### 후보 C: 5-tier

```text
words
phones_mfa
utterance
utterance_orth_roman
utterance_morph
```

검색 자료를 나눠 가독성은 높이지만 tier 수가 다시 늘고 형태소 로마자를
어디에 둘지 불분명하다.

### 5. 반드시 검토할 설계 질문

1. 위 연구 목적에는 3/4/5-tier 중 무엇이 가장 타당한가?
2. 정확한 tier 이름과 순서는 무엇으로 고정해야 하는가?
3. `utterance_search`를 하나로 합치는 것이 Praat 검색·가독성·장기
   호환성 측면에서 안전한가?
4. label의 정확한 한 줄 문법을 어떻게 정해야 하는가?
   - field marker
   - field separator
   - 어절·형태소 separator
   - 따옴표, 괄호, `|`, `+`, `/`가 실제 전사에 있을 때 escaping
5. 발화 수준 tier의 유표 label은 어느 시간 범위가 적절한가?
   - `0–xmax` 전체
   - 첫 유표 word 시작부터 마지막 유표 word 끝까지
   - 다른 방식
6. 연구자가 이전부터 요구한 “각 tier의 처음·끝 경계”와
   “형태소 시간경계를 주장하지 않음”을 동시에 만족시키는 방법은 무엇인가?
7. 규칙 발음 `[RULE_H/R]`과 사전 발음도 기본 TextGrid에 넣어야 하는가,
   아니면 CSV/Parquet에만 두는 것이 나은가?
8. `tagged`의 공백 어절 경계를 label에서 명시적 `|`로 정규화해도 되는가?
   raw `tagged`도 별도로 보존해야 하는가?
9. 한 label이 매우 길어지는 발화, 문장부호, 인용부호, 비언어 표지,
   숫자·외국어·분석 불일치를 어떻게 처리해야 하는가?
10. 2020–2025 약 510만 발화에 적용할 때 TextGrid 크기, 쓰기 I/O,
    Praat 검색 속도, 중복 저장 비용이 현실적인가?
11. 모든 검색 정보를 TextGrid에 복제하는 대신 CSV를 정본으로 유지하면서
    TextGrid에는 어느 최소 정보만 넣어야 하는가?
12. 현재 코드의 `morph_analysis`를 word slot에 배치하는 방식도 사용자의
    새 의도와 어긋나는가? 어긋난다면 완전히 제거해야 하는가?

### 6. 변경해서는 안 되는 기준

- MFA DB의 기존 word·phone interval
- 2020–2025 공통 phone 기준
- 공통 발음사전과 Jamo G2P 기준
- 원 WAV, 원 JSON, 기존 CSV
- MFA phone과 실제 실현 판정의 분리
- 사전 발음·규칙 발음·철자 로마자 간 출처 분리
- `utt_id` 기반 WAV/TextGrid/CSV/LAB 연결

새 TextGrid는 보존한 pilot DB와 CSV에서 재수출해야 하며 MFA 정렬을 다시
실행할 필요가 없어야 한다.

### 7. 반드시 읽을 저장소 파일

다음 순서로 읽어 달라.

```text
docs/environment/PROJECT_CURRENT_STATE.md
docs/decisions/WORKFLOW_r2_MFA_research_data_contract_20260730.md
docs/decisions/DECISION_mfa_r2_review_global_issues_20260730.md
docs/decisions/GUIDE_mfa_r2_infrastructure_review_columns_20260730.md
docs/decisions/DESIGN_pronunciation_environment_search_2026-07-25.md
docs/decisions/STANDARD_textgrid_tiers.md

scripts/python/export_mfa_db_4tier.py
scripts/python/realign_eojeol_merge_output.py
scripts/python/build_stratified_mfa_review_bundle.py
scripts/python/package_mfa_r2_pilot_review.py
scripts/python/build_search_master.py
scripts/python/predict_pron.py

tests/test_export_mfa_db_4tier.py
tests/test_audit_mfa_4tier_year.py
tests/test_build_stratified_mfa_review_bundle.py
```

문서끼리 또는 문서와 코드가 충돌하면 어느 쪽이 현재 실동작인지 근거와
함께 지적하라. 특히 과거 `morphemes`/`morph_analysis` 설계를 그대로
정답으로 전제하지 말라.

### 8. 요구하는 답변 형식

다음 순서로 답해 달라.

1. **한 문단 결론**
2. **권장 tier schema**
   - 정확한 이름·순서
   - 각 tier의 출처와 의미
   - 각 tier의 label 시간 범위
3. **권장 label 문법**
   - 실제 한 줄 예시 3개
   - 일반 발화
   - 복수 형태소 어절
   - 문장부호·숫자·불일치가 있는 발화
4. **3/4/5-tier 대안 비교표**
5. **CSV 정본과 TextGrid 복제 범위**
6. **방법론적 위험**
   - 거짓 시간 정밀성
   - 실제 발음으로 오해할 위험
   - 형태소 분석 오류 전파
7. **대량 처리 위험과 예상 병목**
8. **필수 수정과 나중 개선을 분리한 목록**
9. **검증 gate**
   - 60발화 재수출에서 반드시 확인할 자동 검증
   - 연구자가 직접 확인할 최소 표본과 항목
10. **코드 변경 지점**
    - 파일·함수 단위
    - 구현 순서
    - 기존 결과를 덮어쓰지 않는 archive/새 output 정책

각 지적에는 가능하면 저장소의 파일과 함수 또는 문서 절을 근거로 달라.
단순히 “더 많은 tier를 추가하라”거나 “딥러닝 모델을 써라”라고 하지 말고,
이 연구에서 실제 검색·검토 효율과 방법론적 해석 가능성을 기준으로 판단해
달라.

---

## 현재 내부 잠정안

외부 리뷰에 강제하지 않되, 현재 내부적으로는 후보 A를 가장 유력하게 본다.

```text
words
phones_mfa
utterance
utterance_search
```

이유:

- 시간 정렬층은 `words/phones_mfa` 두 개만 남긴다.
- 한글 발화는 짧고 읽기 쉬운 `utterance`에 둔다.
- 철자 로마자·형태소·형태소 로마자는 하나의 발화 수준 검색 tier로 모은다.
- 형태소별 시간경계를 만들지 않는다.
- 7-tier로 다시 늘리지 않고 4-tier를 유지한다.

다만 `utterance_search`의 정확한 label 문법, label 시간 범위, 규칙·사전
발음 포함 여부는 외부 리뷰를 받은 뒤 확정한다.
