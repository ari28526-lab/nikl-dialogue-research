# 서울 코퍼스 참조 TextGrid tier 결정 및 수용 계획

- 작성일: 2026-08-01
- 상태: **연구자 설계 승인, 최소 수용 파일럿 검토 대기**
- 적용 후보: 2020–2025 r2 MFA 이후 연구용 TextGrid
- 불변 조건: 원 WAV/JSON, MFA DB, `words`, `phones_mfa` 시간·label을
  변경하지 않는다.

## 1. 요청의 정확한 해석

연구자의 신규 요구는 다음과 같다.

1. 한글 발화를 읽는 독립 `utterance` tier가 필요하다.
2. 철자 로마자는 형태소 정보와 합치지 않고, 발화 전체 수준에서
   어절 구분자가 보이도록 두고 싶다.
3. 형태소 정보는 한글 `형태소/POS`로 독립 tier에 두되, 각 형태소의
   음향 시간경계를 주장하지 않는다.
4. `phoneme_r_auto`는 철자·예측발음에서 기저형을 역복원하지 않고,
   `phones_mfa`에 대한 broad Roman phonemic transcription으로 둔다.
5. 세부 형태소·음절·철자 구성성분·형태소 경계 조합 검색의 정본은
   CSV/Parquet 표로 유지한다.

## 2. 서울 코퍼스에서 채택할 원칙

검토 자료:

- `WorkshopLecture1-v4.pdf`, PDF 3–5쪽
- `KCI_FI002007633.pdf`, 논문 105–108쪽(PDF 3–6쪽)

서울 코퍼스는 다음 7개 층위를 사용했다.

- 철자형 utterance 한글
- 발음형 utterance 한글
- 철자형 phrasal-word(어절) 한글
- 발음형 phrasal-word 한글
- 철자형 phrasal-word 로마자
- 발음형 phrasal-word 로마자
- phoneme

논문은 phoneme·phrasal word·utterance 경계를 동기화해 검색과
계산 처리를 쉽게 했다고 명시한다. 철자 및 재음절화 음절 경계는
로마자 표기의 hyphen으로 보존했다. 또한 실제 발음형은 한국인
전사자가 음성을 듣고 먼저 음소 label을 부여한 후, 자동 labeler가 경계를
배치하고 사람이 재조정한 결과이다.

현재 프로젝트가 서울 코퍼스에서 가져올 것은 **층위별 기능 분리,
어절·발화·음소의 병렬 구조, 경계 동기화, 한글·로마자 검색성**이다.

그대로 복제하지 않을 것은 `utterance.prono` 및 `pWord.prono`다. 현재의
규칙/G2P/사전 발음은 사람이 음성을 듣고 확정한 실제 발음형이 아니므로,
서울 코퍼스의 발음형 tier와 같은 지위로 두면 방법론적으로 잘못된다.

## 3. 제안하는 기본 6-tier

```text
words
phones_mfa
phoneme_r_auto
utterance
utterance_orth_r
morph_analysis_utt
```

| # | tier | 정본/출처 | label | 시간의 의미 |
|---|---|---|---|---|
| 1 | `words` | MFA DB word interval | MFA 입력 어절 | MFA 어절 정렬 |
| 2 | `phones_mfa` | MFA DB phone interval | 동결 IPA phone | 사전/G2P phone 강제정렬; 실현 판정 아님 |
| 3 | `phoneme_r_auto` | `phones_mfa` 전용 기계 매핑 | broad Roman phoneme | `phones_mfa`와 같은 경계; 기저형 복원 아님 |
| 4 | `utterance` | frozen master `form` | 한글 발화 | 첫/마지막 유표 word span |
| 5 | `utterance_orth_r` | `form_roman` | 철자 로마자 | `utterance`와 같은 span; 음향 경계 아님 |
| 6 | `morph_analysis_utt` | canonical `tagged` | 한글 `형태소/POS` | `utterance`와 같은 span; 형태소 경계 아님 |

이 구조는 이전 7-tier 실패판과 다르다. 이전판은 legacy 형태소,
`original_form`, 규칙 발음 등을 반복 표시해 Praat 화면이 복잡했다. 새
6-tier는 각 tier가 서로 다른 질문 하나만 담당한다.

## 4. label 문법

### `utterance`

```text
혹시 요즘
```

- `form`만 표시한다.
- ID·로마자·형태소·발음 정보를 합치지 않는다.

### `utterance_orth_r`

원칙상 형태소 구분자 `+`나 POS를 넣지 않는다. 어절은 ` | `로
구분한다. 음절·분절 내부 문법은 `form_roman` 동결 계약을 그대로
사용하되 이 tier에는 형태소 분석을 섞지 않는다.

```text
H O k _ S I | YO _ J EU m
```

정확한 음절·분절 구분자 표시는 현행 `tagged_roman.v2` 계약과의
충돌을 대조한 후 동결한다.

### `morph_analysis_utt`

```text
혹시/MAG | 요즘/NNG
```

복수 형태소 어절의 예:

```text
꽃/NNG + 에/JKB | 모양/NNG + 은/JX | 어떻/VA + 었/EP + 어/EF + ?/SF
```

- 어절 경계: ` | `
- 어절 내 형태소 경계: ` + `
- POS: `/POS`
- 이 구분자는 **문자열의 언어학적 구조**를 나타내지만 TextGrid
  시간경계를 뜻하지 않는다.

## 5. 경계 및 동기화 계약

1. 모든 IntervalTier는 빈 interval을 포함해 `0–xmax`를 gap/overlap 없이
   연속 커버한다.
2. `utterance`, `utterance_orth_r`, `morph_analysis_utt`의 유표 label은 모두
   첫 유표 `words` 시작부터 마지막 유표 `words` 끝까지 같은 span을
   쓴다.
3. `phoneme_r_auto`는 `phones_mfa`의 모든 interval 경계와 완전히 같다.
4. 형태소 문자열을 `words` interval에 자동 분배하지 않는다. 이는
   어절 내 형태소가 어느 시간에 실현됐는지 거짓 정밀성을 만들 수 있다.
5. 점검용 WAV에만 왼쪽/오른쪽 0.05초 padding을 넣고 모든 tier를 함께
   이동한다. 운영 원시간 산출물은 인위적 무음을 추가하지 않는다.

## 6. CSV/Parquet가 정본인 정보

다음은 기본 TextGrid 6-tier에 반복하지 않는다.

- `morph_tokens`, `morph_units`, `morph_boundaries`, `orth_components`
- 형태소 및 음절의 initial/medial/final 좌표
- 철자상 환경 조합검색의 세부 결과
- 규칙 예측발음, 우리말샘 예외발음, 공통발음사전 후보
- `phones_mfa`와 예측발음의 대응 진단
- 실제 실현 판정, KOINA, wav2vec2 보조값
- 화자·대화상대·사회정보·파일경로·QC·provenance

TextGrid는 사람이 음성과 정렬을 보며 바로 필요한 언어학적 문맥을
읽고 간단히 검색하는 표현층으로 사용한다. 정밀한 조합·집계·재현은
CSV/Parquet/DuckDB에서 한다.

## 7. 서울 코퍼스와의 차이를 논문에 밝힐 방법

방법론 서술에서는 다음처럼 구분한다.

```text
서울 코퍼스의 음소·어절·발화 병렬 표시와 경계 동기화 원칙을
참조하여 TextGrid 구조를 설계했다. 다만 서울 코퍼스의 발음형은
사람이 음성을 듣고 전사·수정한 값인 반면, 본 연구의 MFA phone과
규칙/G2P 발음은 자동 참조값이므로 서로 다른 층위로 보존했다.
```

## 8. 기본본에 넣지 않을 tier

- `utterance_prono_auto`: 실제 발음형으로 오인될 수 있어 생성하지 않음
- `morpheme` 시간분할 tier: 실측 경계가 없으므로 생성하지 않음
- `pron_dict`, `pron_rule`: 기본본이 아니라 후보 검토 사본에만 선택적 추가
- `prosody_koina`, `human_judgment`: 해당 분석 단계의 후보만 대상으로
  온디맨드 추가

후속 연구에서 연구자가 음성을 듣고 발음형을 수동 확정한 후에는
`utterance_pron_manual` 또는 별도 판정표를 만들 수 있다. 이 경우에만 서울
코퍼스의 `utt.prono` tier와 비교 가능한 지위를 갖는다.

## 9. 선택적 KOINA 및 연결 발화와의 결합

### 9.1 기본 원칙

KOINA는 전수 기본 6-tier를 늘리는 기능이 아니라, 검색으로 선별한 후보에
붙이는 **독립 파생 분석**으로 둔다. 따라서 KOINA를 실행하지 않은 발화와
실행한 발화의 기본 TextGrid 계약은 동일하게 유지된다.

```text
전수 정본: CSV/Parquet + MFA DB + 기본 6-tier TextGrid
    ↓ utt_id로 후보 선택
선택 산출물: WAV + 기본 6-tier 사본 + KOINA 원출력 + KOINA 표 + 검토표
```

KOINA 자체가 다시 만든 word/phoneme 정렬은 본 프로젝트의 `words`와
`phones_mfa`를 덮어쓰지 않는다. 두 정렬을 비교할 필요가 있으면 반드시
`koina_word_auto`, `koina_phone_auto`처럼 출처가 드러나는 별도 이름을
쓴다. KOINA의 Momel/F0 결과도 자동값이며, 연구자의 AP/IP 확정 판정과
구분한다.

선택 산출물의 권장 구분은 다음과 같다.

| 산출물/tier | 지위 | 용도 |
|---|---|---|
| `koina_raw.TextGrid` | KOINA 원출력, 불변 | 재현 및 오류 추적 |
| `koina_targets_auto` | PointTier 또는 별도 표 | Momel/F0 자동 목표점 표시 |
| `prosody_candidate_auto` | 선택적 파생 tier/표 | 규칙 기반 AP/IP 후보; 확정값 아님 |
| `prosody_manual` | 연구자 검토 뒤에만 생성 | 최종 AP/IP 등 수동 판정 |

기본 TextGrid에 위 네 층위를 빈 tier로 미리 만들지 않는다. 필요한 후보의
**분석용 사본**에만 존재하게 한다.

### 9.2 여러 발화 파일을 이어 붙일 때

연결 TextGrid에서는 기본 6-tier의 발화 수준 세 tier를 원 발화마다 하나의
유표 interval로 반복한다.

- `utterance`: 각 원 발화의 한글 `form`
- `utterance_orth_r`: 각 원 발화의 철자 로마자
- `morph_analysis_utt`: 각 원 발화의 형태소/POS 문자열

연결본에만 `source_utt_id` IntervalTier를 추가해 각 구간의 `utt_id`를
표시한다. 화자가 바뀔 수 있으면 `speaker`도 연결본 전용 tier로 둔다.
이 두 tier 때문에 단일 발화의 기본 계약을 7/8-tier로 늘리지는 않는다.

좌표 변환 정본은 TextGrid label이 아니라 별도 manifest다. 최소한 다음
필드를 보존한다.

```text
stitched_id, order, utt_id, session_id, speaker_id,
source_wav, source_textgrid, source_sha256,
source_start_seconds, source_end_seconds,
stitched_start_seconds, stitched_end_seconds,
gap_before_seconds, gap_after_seconds,
stitch_mode, alignment_contract_id, selection_query_id
```

모든 KOINA point/interval에는 `stitched_id`와 함께 원 `utt_id` 및 원시간으로
역변환한 좌표를 표에도 저장한다. 그러면 연결본에서 찾은 운율 후보를 원래
WAV·TextGrid·CSV 행으로 되돌릴 수 있다.

### 9.3 인공 연결 경계의 방법론적 제한

발화별 클립을 붙인 WAV는 원래의 연속 녹음이 아니다. 클립 사이에 0.05초
무음을 넣거나 무음 없이 맞붙여도 자연 발화의 실제 쉼·F0 연속성은
복원되지 않는다. 따라서 다음 세 모드를 구분한다.

| mode | 목적 | 경계 횡단 운율 해석 |
|---|---|---|
| `review` | 앞뒤 맥락 청취·Praat 검토 | 금지; 인공 gap 허용 |
| `koina_batch` | 여러 독립 클립을 한 묶음으로 운반·처리 | 원 발화별 결과로 다시 분리; seam 횡단 판정 금지 |
| `continuous_source` | 실제 연속 원녹음에서 시간구간 추출 | 원시간·자연 쉼이 검증된 경우에만 허용 |

현재 `scripts/python/stitch_session.py`는 기본 0.05초 무음을 넣고 구형
`morphemes_legacy`를 옮기는 `review` 도구다. 새 6-tier를 운반하고 위 mode를
manifest에 기록하도록 고치기 전에는 KOINA 분석 입력으로 사용하지 않는다.

KOINA가 연결 파일에서 계산되더라도 인공 seam 주변의 F0·pause 기반 값은
자동으로 제외하거나 `seam_contaminated=true`로 표시해야 한다. 자연스러운
대화 연속성 자체가 연구 대상이면 발화 클립 연결본이 아니라 실제 연속
원녹음을 확보해야 한다.

### 9.4 파일 배치 원칙

후보별 분석 묶음은 다음처럼 분리한다.

```text
candidate_bundle/
  base/                 # 원 WAV와 기본 6-tier 사본
  stitched/             # 선택한 경우에만 연결 WAV/TG/manifest
  koina_raw/            # KOINA 원출력, 변경 금지
  koina_derived/        # 자동 후보 tier와 분석표
  review/               # 연구자 판정표와 수동 주석 사본
```

KOINA는 D:의 전수 MFA와 동시에 돌리지 않고, 선별 묶음만 Colab/Linux 실행용
전송본으로 만든다. 전송·회수 때 manifest와 SHA256으로 동일성을 확인한다.

## 10. 승인 전 파일럿

이 제안이 승인되면 MFA를 다시 돌리지 않고 보존된 60발화 DB/CSV에서
새 버전 사본만 생성한다.

1. 현행 v1/v2 결과는 덮어쓰지 않는다.
2. 2020–2025 연도별 10발화·5화자 60발화를 새 root에 재수출한다.
3. `words/phones_mfa` 모든 label·경계가 보존 DB와 동등한지 전수 검증한다.
4. `phoneme_r_auto`가 `phones_mfa`만으로 결정되고 경계가 1:1로 같은지
   검증한다.
5. 세 발화 tier의 label span과 앞뒤 빈 interval이 같은지 검증한다.
6. `utterance_orth_r` 어절 수와 `words`/정본 CSV 어절 수가 다를 때는
   조용히 정렬하지 않고 QC flag와 발화 ID를 남긴다.
7. 60발화의 파일 크기를 현행 4-tier와 비교해 6개년 전수 저장량을
   추정한다.
8. 전역 구조 문제는 한 번만 판정하고, 12발화에서 연도별 2개씩
   가독성·검색성·경계를 검토한다.

파일럿 검토에서는 특히 다음을 분리한다.

- TextGrid 구조가 읽기·검색에 유용한가?
- 자동 음소 로마자가 `phones_mfa`를 정직하게 넓게 전사하는가?
- 형태소 문자열을 형태소의 실측 시간경계로 오해할 위험이 없는가?

구체적 음운현상의 실제 실현은 이 파일럿에서 판정하지 않는다.

## 11. 승인으로 확정된 점과 파일럿 후 운영 결정

2026-08-01 연구자 승인으로 다음을 확정했다.

1. `utterance_orth_r`는 기존 검색표와 호환되는 현행 `form_roman` 문법과
   ` | ` 어절 구분자를 쓴다. 서울 코퍼스의 hyphen을 모양만 복제하지 않는다.
2. `morph_analysis_utt`에는 한글 형태소와 POS를 함께 넣는다.
3. 단일 발화의 기본 연구 표시 계약은 6-tier로 한다.
4. KOINA는 기본 6-tier에 빈 tier를 미리 만들지 않고 선별 분석 사본에만
   추가한다.

최소 파일럿 뒤 결정할 운영 항목은 다음 두 가지다.

1. 6-tier를 6개년 전수 상시본으로 저장할지, 보존 정렬본에서 필요할 때
   재생성할지. 파일럿 크기로 전수 저장량을 추정한 뒤 결정한다.
2. 실제 KOINA 연구에서 `koina_targets_auto`와
   `prosody_candidate_auto`를 모두 표시할지, 연구 질문에 필요한 것만
   선택할지.

최소 파일럿 실물은 다음에 생성했다.

```text
outputs/textgrid_6tier_mini_pilot_20260801
```

단일 6-tier 1건과 같은 세션·같은 화자의 비인접 2발화를 붙인 `review`
연결본 1건이다. KOINA는 실행하지 않았으며 연결 seam 횡단 운율 해석은
금지했다. 이 파일럿을 연구자가 수용하기 전에는 새 TextGrid를 전수
생성하지 않는다.
