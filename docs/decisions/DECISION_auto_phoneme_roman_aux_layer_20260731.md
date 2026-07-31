# MFA phone의 검색용 로마자 음소 보조층 결정

기록일: 2026-07-31
상태: **60발화 기계 파일럿 통과, 12발화 연구자 수용 검토 대기**
적용 범위: 2020–2025 r2 MFA의 post-MFA 파생 인프라

## 결론

MFA의 IPA phone 원값과 시간은 `phones_mfa`로 그대로 보존한다. 그 위에
다음 두 로마자 보조값을 별도 CSV로 생성할 수 있다.

1. `phone_class_r_auto`: MFA IPA phone의 기계적인 프로젝트 로마자 범주
2. `phoneme_lexical_r_auto`: 철자 로마자와 규칙 예측발음 로마자를 참조해
   MFA phone 시간에 투영한 자동 어휘 음소 후보

사용자가 실제 연구에서 검색하기 쉽도록 두 파생값은 IPA가 아니라
`roman_mfa.v1` 계열의 프로젝트 로마자를 사용한다. 개정 로마자 표기가
아니며, 실제 음성 실현 판정도 아니다.

기본 운영 TextGrid는 계속
`words/phones_mfa/utterance/utterance_search` 4-tier다. 파일럿에서는
기존 네 tier를 의미·시간·label 수준에서 그대로 복제하고
`phoneme_r_auto`만 덧붙인 선택적 5-tier 사본을 만들었다. 연구자 수용 전에는
전수 기본 tier로 승격하지 않는다.

## 먼저 바로잡을 개념

MFA의 `phones_mfa`는 음성을 독립적으로 인식해 실제 변이음을 전사한 결과가
아니다. 공통 발음사전/G2P가 제시한 phone열 가운데 정렬 경로를 선택하고
그 열을 음성 시간에 강제정렬한 결과다. 따라서 새 보조층의 해석은 다음과
같아야 한다.

```text
철자·형태소
  → 규칙 예측발음 및 공통사전/G2P 후보
  → MFA가 선택·정렬한 IPA phone과 시간
  → 검색용 로마자 범주·자동 어휘 음소 후보
  → 연구자가 WAV/TextGrid로 실제 실현을 별도 판정
```

마지막 연구자 판정은 앞의 어느 자동 열로도 대체하지 않는다.

## phone inventory 수의 정확한 구분

최신 동결 Korean MFA acoustic v3.3.0의 계약은 다음 세 수를 구분한다.

| 범위 | 수 | 의미 |
|---|---:|---|
| `meta.json phones` | 107 | acoustic/G2P의 비침묵 phone |
| release 허용 interval inventory | 109 | 위 107 + `sil` + `spn` |
| 내부 numeric mapping | 110 | 위 109 + `<eps>` |

따라서 107·109·110은 모순이 아니라 포함 범위가 다른 값이다. 논문과
manifest에는 어느 범위를 센 것인지 함께 쓴다. `<eps>`는 연구 phone interval로
해석하지 않으며 `sil/spn`에도 음소 로마자를 부여하지 않는다.

## 두 파생값의 근거와 차이

### `phone_class_r_auto`

- 입력: `phones_mfa` IPA 한 구간
- 1차 근거: 동결 acoustic zip `meta.json`의 107 phone과 22
  `phone_groups`
- 2차 규칙: 한국어 검색에 필요한 평음/격음/경음 대립을 보존하는 명시 매핑
- 예: `ɡ/k/c/ɟ → G`, `kʰ/cʰ → K`, `k͈/c͈ → KK`,
  `s/ɕʰ → S`, `s͈/ɕ͈ → SS`, `ɾ → R`, `ɭ/ʎ → l`
- 장음 `ː`, 구개음화 `ʲ`, 원순화 `ʷ`, 미방출 `◌̚`는 별도 feature 열에
  보존한다.

22개 model group은 acoustic decision-tree 묶음이지 한국어 음소 inventory
그 자체가 아니다. 예를 들어 평음·격음·경음이 같은 group에 있을 수 있다.
그러므로 group ID만 로마자로 바꾸지 않고 phone 기호의 대립을 함께 본다.

### `phoneme_lexical_r_auto`

- 입력 근거:
  - raw `form_roman`
  - 실제 LAB/MFA 입력과 같은 `pron_reference_form_roman`
  - 규칙 예측 `pron_reference_roman`
  - 선택된 `phones_mfa`와 시간
- 복합 중성은 대응을 위해 glide+vowel component로 펼치되 원 토큰과
  component index를 보존한다. 예: `WA → W+A`, `YA → Y+A`,
  `UI → EU_G+I`.
- 초성/종성 위치만 다른 `G/k`, `D/t`, `B/p`, `R/l`, `N/n`, `M/m`,
  `NG/ng`는 `position_compatible`로 기록한다.
- 평음/격음/경음처럼 같은 model group이지만 중요한 대립이 다른 경우는
  `model_group_only`로 낮춰 자동 승인하지 않는다.
- 삽입·탈락·대체는 각각 `phone_only/reference_only/substitution`으로
  노출한다. 조용히 길이를 맞추지 않는다.

`phoneme_lexical_r_auto`는 음운론적 기저형의 확정 전사가 아니다. 예를 들어
표면 [ŋ]만 보고 기저 /ㄴ/과 /ㅇ/을 항상 복원할 수 없고, 종성 중화·동화·
삽입·탈락에는 다대다 대응이 있다. 이 열은 철자·예측발음·MFA를 잇는
검색 후보다.

## 산출 스키마

전수용 정규화 표:

- `PHONE_ROMAN_INVENTORY.csv`: 동결 107 phone과 `sil/spn`, 로마자·group·feature
- `PHONE_ROMAN_INTERVALS.csv`: MFA phone interval 1행당 1행
- `PHONEME_ROMAN_CORRESPONDENCE.csv`: phone과 참조 토큰의 대응 operation 1행
- `UTTERANCE_PHONEME_ROMAN_SUMMARY.csv`: 발화별 검색·QC 요약

핵심 interval 열:

```text
year, utt_id, word_index, begin, end
phone_mfa
phone_class_r_auto
phoneme_lexical_r_auto
mapping_status, automatic_use
orth_roman_eojeol, pron_reference_roman_eojeol
orth_reference_source_field
has_length, secondary_articulation, unreleased
realization_judgment=not_performed
```

시간 interval 전체를 긴 CSV 셀 하나에만 넣지 않는다. 발화 master에는
요약·join key만 두고 실제 interval은 별도 정규화 표로 유지한다.

## 60발화 파일럿 결과

입력은 r2 인프라 수용 파일럿의 2020–2025 연도별 10발화, 총 60발화다.

| 항목 | 결과 |
|---|---:|
| 동결 비침묵 phone inventory | 107 |
| 파일럿 관측 phone 종류 | 74 |
| 유표 phone interval | 1,625 |
| correspondence 행 | 1,683 |
| exact | 1,421 |
| position compatible | 151 |
| model group only | 29 |
| substitution | 16 |
| phone only | 8 |
| reference only | 58 |
| 선택적 5-tier TextGrid | 60/60 |
| 기존 네 tier 의미·시간·label 불변 | 60/60 |

유표 phone 중 exact 또는 position-compatible은 1,572/1,625다. 나머지를
실패로 숨기거나 억지 치환하지 않고 `?` 표시와 상태열로 연구자 검토에
남겼다. 이는 실현 정확도 점수가 아니라 자동 대응 coverage다.

실물:

```text
D:\mfa_eojeol\pilots\r2_infrastructure\mfa_r2_infra_pilot_20260730\
  phoneme_roman_aux_v1_20260731
```

검토본:

```text
C:\Users\ari30\Dropbox\MFA_RESEARCH_SCHEMA_REVIEW_12_20260731\
  PHONEME_ROMAN_PILOT.xlsx
  연도__utt_id__phoneme_r_auto.TextGrid  (12개)
```

## 시행착오와 안전중단

### 1. 기존 tier를 다시 쓰면서 1 μs 빈 구간이 생길 뻔한 문제

첫 실행은 2024년 한 원본 tier의 `xmax`와 마지막 interval 끝 사이에 허용
범위 1 μs 차이가 있는 것을 발견했다. 네 tier를 재직렬화하면 이 차이가 새
빈 interval로 물질화돼 “기존 네 tier 불변” gate가 실패했다.

해결:

- 기존 네 tier 원문을 byte 그대로 보존한다.
- top-level tier count만 4→5로 바꾼다.
- `phones_mfa`와 정확히 같은 interval 경계의 다섯 번째 tier만 append한다.
- 출력 재파싱 뒤 기존 네 tier의 모든 경계·label 동등성을 다시 검사한다.

실패 준비본은 D:의 `.partial` 폴더에 남겨 원인을 추적할 수 있게 했으며,
정본·Dropbox는 수정되지 않았다.

### 2. `2사람이`와 `두 사람이`의 어절 수 차이

2025 `SARW2500000414.1.1.2`의 raw `form`은 `2사람이` 한 어절이고
`form_roman`은 그 혼합 어절을 `∅`로 표시한다. 원전사 회복 뒤 실제 MFA
입력은 `두 사람이` 두 어절이므로 `pron_reference_form_roman`은 한 어절 더
많다. raw `form_roman`을 MFA word index에 직접 붙이려는 두 번째 실행은
12대 13 불일치를 발견하고 중단했다.

해결:

- raw 철자 검색용 `form_roman`은 그대로 보존한다.
- 시간 투영의 철자 근거는 실제 LAB과 같은
  `pron_reference_form_roman`으로 고정한다.
- 두 열을 workbook과 정규화 표에서 구분한다.
- source field를 행마다 기록한다.

이는 숫자·기호 원전사 회복으로 어절 수가 달라질 수 있다는 기존 시행착오를
후속 보조층에서도 명시적으로 처리한 것이다.

### 3. rename 전 `.partial` 경로가 manifest에 남은 문제

최종 성공 실물의 SHA와 bytes는 정상이었지만 첫 `PILOT_MANIFEST.json`의
네 CSV 및 D: workbook 경로가 directory 원자 rename 전 `.partial` 주소를
기록했다. 생성기는 fingerprint의 경로를 최종 예상주소로 투영하도록 고쳤다.
기존 manifest를 덮어쓰지 않고 독립 verifier가 최종 실물 경로·SHA와 60개
TextGrid를 다시 확인한 `PILOT_VERIFICATION_V2.json`을 추가했다. 이 v2가
최종 경로 확인의 정본이고 v1은 실패 원인 추적용으로 보존한다.

## 연구 활용

가능한 활용:

- 특정 MFA phone 또는 넓은 로마자 범주로 후보 검색
- 철자 환경과 규칙 예측발음, MFA 정렬열이 다른 후보 우선 검토
- 장음·이차조음·미방출 phone의 표본 수집
- 형태소/어절 검색 결과를 같은 `utt_id`, word index, 시간과 조인
- 후보 WAV/TextGrid/KOINA/연구자 판정 묶음 생성

금지하는 해석:

- `phoneme_lexical_r_auto`를 실제 실현 전사로 사용
- `?` 후보를 오류 없이 확정된 음소로 사용
- MFA phone과 wav2vec2 phone 또는 연구자 판정을 같은 열로 덮어쓰기
- 로마자 보조층 때문에 `phones_mfa` IPA나 시간을 삭제

## 다음 gate

1. 12발화에서 WAV, 기존 4-tier, 새 5-tier를 비교한다.
2. `phone_class_r_auto`가 검색 표기로 이해되는지 확인한다.
3. 철자·예측발음 참조가 자동 음소 후보를 해석하는 데 도움이 되는지 본다.
4. `?` 사례는 오류인지, 허용할 다대다 관계인지 대응_세부에서 확인한다.
5. 수용 후에만 연도별 post-MFA 보조층으로 runner에 배선한다.

2020 전수 MFA 시작 여부와 이 보조층의 수용은 분리한다. 보조층은 정렬 뒤
생성 가능한 파생물이므로 정렬 기준을 바꾸지 않는다. 그러나 대량 정렬 전에
스키마를 수용하면 6개년 후처리의 재작업을 줄일 수 있다.
