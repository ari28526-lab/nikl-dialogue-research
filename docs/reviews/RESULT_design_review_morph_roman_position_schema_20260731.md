# 설계 리뷰 결과: 형태소·음절·분절 로마자와 위치 검색 스키마 (2026-07-31)

- 요청 문서:
  `docs/reviews/PROMPT_external_review_morph_roman_position_schema_20260731.md`
- 검토 브랜치: `agent/harden-pre-bulk-pipelines`
- 코드·기존 설계 기준 커밋: `bd77bd3` (이후 커밋 2건은 이번 프롬프트 문서
  추가뿐)
- 검토 근거: 저장소의 코드·문서만 사용. D: 코퍼스·Dropbox 실물 미접근.
  저장소로 확인할 수 없는 항목은 `확인 불가`로 명시.
- 검토 범위: 정규형 표현·구분자 문법·정규화 표·검색 API·검증 계약.
  코드 수정·PR 없음.
- 판정 성격: 리뷰 권고안. 연구자 확정 전 구현 금지.

## 0. 직전 리뷰(RESULT 20260731 TextGrid tier)의 정정 3건

이번 프롬프트 지시대로, 직전 리뷰의 결론을 전제하지 않고 재검토한 결과
다음 세 가지를 정정한다.

1. **"동결 pre-MFA 층은 5열뿐" 표현은 오류.** 프롬프트 §4의 읽기 전용
   관측(연도별 표본 48열, `form_roman`·`tagged_roman`·`align_warn` 포함)을
   제공값으로 수용한다. 직전 리뷰가 근거로 삼은
   `WORKFLOW_r2_MFA_research_data_contract_20260730.md` §3.2는 "LAB 생성에
   필요한 열"을 열거한 것이지 파일의 전체 스키마가 아니었다. 단, 표본
   헤더 존재와 전수 값 완전성은 다르므로 전수 preflight 계약은 여전히
   필요하다(§12). 전수 완전성은 저장소만으로 `확인 불가`.
2. **`[MORPH]` 왕복 검증안(` | `→공백 치환 후 raw `tagged` 비교)은 폐기.**
   표시형은 형태소 경계도 `+`→` + `로 바뀌므로 부분 치환은 불완전하다.
   대신 단일 정본 함수 `canonicalize_tagged(tagged)`의 출력과 label
   field를 **바이트 동일 비교**한다(§12). 파생 문자열의 검증은 "파싱해
   되돌리기"가 아니라 "같은 함수로 재생성해 비교"가 맞다.
3. **`morph_tokens`/`morph_boundaries`를 "나중 개선"으로 분류한 판정을
   상향.** 이 구조의 **스키마 동결과 60발화 파일럿 검증은 전수 인프라
   승인 전 필수**다. 근거: 연구자의 핵심 검색 요구(형태소 첫/내부/끝,
   음절 슬롯, 경계 좌우 환경)는 문자열 정규식으로 재현 불가하고(프롬프트
   §5.1), `G-CSV-01`이 이미 재검토 조건으로 명시했다
   (`DECISION_mfa_r2_review_global_issues_20260730.md` §2·§5). 단,
   **전량 생성 자체**는 pre-MFA 텍스트만으로 파생 가능하므로 연도별 MFA와
   병행할 수 있다(§14).

## 1. 한 문단 결론

**대안 B를 권장한다.** 정밀 위치 검색의 정본은 문자열이 아니라 구조화
표(`morph_tokens`·`morph_syllables`·`morph_boundaries`, 연도별 partitioned
Parquet)로 두고, 표시·기초검색용 직렬화는 현행 위계(공백·`_`·`+`·`|`·
`/POS`)를 유지하되 **규격을 동결하고 literal 표시를 추가한
`tagged_roman_v2`**로 세대 교체한다. 현행 구분자 위계 자체는 건전하다 —
문제는 위계가 아니라 (a) 로마자화되지 않은 표면형(숫자·라틴·기호)이 표시
없이 그대로 섞여 분절 토큰과 구별 불가한 점, (b) 무음 초성 `ㅇ`의 비표시,
(c) 규격(공백·NFC·버전)이 코드 관행으로만 존재하는 점이다. (a)는 v2의
`⟨…⟩` literal 표기로, (b)는 표시 문자열이 아니라 구조화 열(`onset_zero`
등)로, (c)는 EBNF 동결과 버전 열로 해결한다. 이 프로젝트의 로마자에서
분절 토큰은 곧 음절 내 슬롯(초성·중성·종성 각 1토큰,
`predict_pron.py::_syl_tokens`)이므로 **별도 `morph_segments` 표는 불필요
하고 `morph_syllables`가 분절 검색까지 담당한다** — 세 표는 과잉 설계가
아니라 위치 기반 환경 검색의 최소 정규화다. 기존 `tagged_roman` v1은
비교·감사용 legacy로 archive하고 최종 연구 CSV에는 싣지 않는다(결정적
재생성 가능). TextGrid `[MORPH_R]`에는 v2 직렬화 한 줄만 복제하고 위치
좌표는 넣지 않는다. 2020 전수 MFA는 이 스키마의 동결과 60발화 파일럿
승인(기존 gate) 후에 시작하되, 구조화 표의 연도별 전량 생성은 MFA와
독립적으로 병행 가능하다.

## 2. 용어와 단위 정의

| 용어 | 정의 | 이 스키마에서의 역할 |
|---|---|---|
| grapheme(음절 글자) | 완성형 한글 음절 문자(U+AC00–D7A3, `predict_pron.py::is_syllable`) | `syllable_surface`의 단위 |
| jamo(자모) | 호환 자모(U+3131–U+3163). 겹받침(ㄺ 등)·쌍자음(ㄲ 등)은 **자모 1개** | `onset/nucleus/coda_jamo` 열의 원자. 코드 표 `CHO/JUNG/JONG`과 동일 문자 집합 |
| roman segment(분절 토큰) | 슬롯당 1개의 프로젝트 로마자 토큰. 초성 대문자(`ONSET_ROMAN`), 중성 대문자(`VOWEL_ROMAN`), 종성 소문자(`SPELL_CODA_ROMAN`). `KK`·`ng`·`lk`처럼 글자 수가 달라도 원자 1개 | 문자열에서 공백 구분; 표에서는 슬롯 열 1칸. **문자 단위 절단 금지** |
| syllable(음절) | 분석 표층형(`morph_surface`)의 완성형 음절 1개. 슬롯 구조 = 초성·중성·종성 | `morph_syllables` 1행 |
| morpheme(형태소) | Bareun `tagged`의 `표면형/POS` 단위 | `morph_tokens` 1행 |
| eojeol(어절) | `tagged`의 공백 구분 단위(**분석 공간**). `form` 어절 수와 다를 수 있음(`align_warn`) | `eojeol_idx` 좌표 축 |
| phone | MFA가 정렬한 phone. **이 스키마에 존재하지 않음** | 철자 로마자와 절대 동일시 금지(프롬프트 §9) |

핵심 발견: 이 로마자 체계에서 **segment = 음절 슬롯 토큰**이다.
`_syl_tokens`는 채워진 슬롯당 정확히 1토큰을 내보내므로, 음절 표의 슬롯
열 3개(`onset/nucleus/coda`)가 분절 단위를 무손실 보존한다. 따라서
`morph_segments` 표나 Parquet list 열은 불필요하다(설계 질문 5·6·10).

좌표계 주의: 모든 음절·분절 좌표는 **분석 공간(tagged 표면형)** 위에
정의한다. `어떻+었+어 → 어땠어` 같은 축약·융합에서는 분석 공간 음절 수와
form 음절 수가 다르며, 이때 문자 대응을 강제하지 않고
`morph_to_form_status=contracted_fused`로 flag한다
(`DESIGN_pronunciation_environment_search_2026-07-25.md` §3.3의 기존 enum
재사용).

## 3. 권장 직렬화 문법 — `tagged_roman_v2`

### 3.1 EBNF (v2)

```ebnf
utterance   = eojeol , { " | " , eojeol } ;
eojeol      = morph , { " + " , morph } ;
morph       = unit , "/" , pos ;
unit        = hangul-run , { literal-run , [ hangul-run ] }
            | literal-run , { hangul-run , [ literal-run ] } ;
hangul-run  = syllable , { " _ " , syllable } ;
syllable    = [ onset , " " ] , nucleus , [ " " , coda ] ;
literal-run = "⟨" , text , "⟩" ;
onset       = "G"|"KK"|"N"|"D"|"TT"|"R"|"M"|"B"|"PP"|"S"|"SS"
            | "J"|"JJ"|"CH"|"K"|"T"|"P"|"H" ;          (* ㅇ은 토큰 없음 *)
nucleus     = "A"|"AE"|"YA"|"YAE"|"EO"|"E"|"YEO"|"YE"|"O"|"WA"|"WAE"
            | "OE"|"YO"|"U"|"WO"|"WE"|"WI"|"YU"|"EU"|"UI"|"I" ;
coda        = "k"|"kk"|"ks"|"n"|"nj"|"nh"|"t"|"l"|"lk"|"lm"|"lp"
            | "ls"|"lt"|"lph"|"lh"|"m"|"p"|"ps"|"s"|"ss"|"ng"
            | "j"|"ch"|"kh"|"th"|"ph"|"h" ;
pos         = Bareun 품사 태그 (대문자 ASCII) ;
```

hangul-run과 literal-run 사이 구분자는 한 칸 공백. 토큰 목록은
`predict_pron.py`의 `ONSET_ROMAN`/`VOWEL_ROMAN`/`SPELL_CODA_ROMAN`을 단일
출처로 하고, 정본 토큰 집합은 기존 원칙대로
`_roman_mfa_to_ipa.csv`와 교차검증한다(`predict_pron.py` 모듈 docstring).

### 3.2 v1 대비 변경점 (이것뿐이다)

| 항목 | v1 (현행) | v2 (권장) | 근거 |
|---|---|---|---|
| 비한글 표면형 | 원문 그대로 삽입 (`?/SF`, `AI/SL`) | `⟨?⟩/SF`, `⟨AI⟩/SL` — literal을 `⟨…⟩`로 감쌈 | `AI` 같은 라틴 표면형이 분절 토큰(`A`+`I`)과 구별 불가한 v1의 실제 결함. `⟨…⟩`는 IPA 변환기의 미정의 토큰 표기(`predict_pron.py::to_ipa_eojeol`)와 동일 관행이라 새 기호가 아님 |
| 혼합 표면형(한글+비한글) | 전체 원문 유지 | 한글 run은 로마자화, 비한글 run은 `⟨…⟩` (예: `⟨1⟩ CH EU ng`) | 혼합 어절·형태소의 한글 부분이 검색 불가능해지는 정보 손실 방지 |
| 규격 문서화 | 코드 관행 | EBNF·공백·NFC·버전 동결 | 장기 재현성 |
| 그 외 전부 | — | **변경 없음** | 위계 자체는 건전. 파괴적 재설계는 이득 없이 재생성·학습 비용만 발생 |

**유지 결정과 이유** (설계 질문 1·3·9):

- **구분자 위계 유지** (질문 1): 공백/`_`/`+`/`|`/`/POS`는 4단 위계를
  구분자 충돌 없이 표현하고, `tagged`·CSV·직전 TextGrid 리뷰와 일관된다.
  기존 표기의 보존에 가산점을 주지 않고 검토해도, 이 위계를 바꿔서 얻는
  검색·검증상 이득이 없다 — 정밀 검색은 어차피 구조화 표가 담당한다.
- **`/POS` 후치 유지, 공백 없음** (질문 3): `/NNG`가 마지막 분절에 붙어
  보이는 것은 표시 인지 문제일 뿐이고, 기계적으로는 `rpartition('/')`로
  항상 무손실 분리된다(표면형에 `/`가 있어도 마지막 `/`가 POS 구분자,
  `assign_sense_layer.py::iter_morphs`·`predict_pron.py::_parse_morphs`
  동일). ` / POS`로 공백을 넣으면 공백이 분절 구분자와 충돌해 오히려
  문법이 나빠진다. POS가 형태소 전체 속성임은 구조화 표의 `pos_bareun`
  열이 정본으로 보장한다. 510만 행 호환도 유지된다.
- **무음 초성 `ㅇ`은 표시 문자열에 넣지 않음** (질문 9): `Ø`류 명시
  토큰은 삭제·무실현 기호나 phone으로 오해될 위험(프롬프트 §5.3)이
  실익보다 크다. 결정적 근거 두 가지: (1) 표시 수준의 ㅇ 검색은 **한글
  필드(`[MORPH]`·`morph_surface`)가 이미 제공**한다 — `이`·`요` 등
  철자에 ㅇ이 보인다. (2) 정밀 환경 검색(ㄴ삽입 후보의 우측 무음초성
  i/y)은 `morph_syllables.onset_zero`·`nucleus_jamo`로 수행한다(§7).

### 3.3 공백·예약문자·Unicode (질문 2·11·13)

- **exact delimiter 동결**: 어절 `" | "`(SP,U+007C,SP), 형태소
  `" + "`(SP,U+002B,SP), 음절 `" _ "`(SP,U+005F,SP), 분절 사이
  SP(U+0020) 1개, POS `"/"`(U+002F, 앞뒤 공백 없음), literal
  `"⟨"`(U+27E8)·`"⟩"`(U+27E9), placeholder `"∅"`(U+2205, `form_roman`
  어절 수준 전용). 연속 공백·탭·줄바꿈·비ASCII 공백은 생성 필드에서
  금지(gate 검사).
- **escaping**: literal 내부는 원문 보존이 원칙이고 escape 문법을 추가로
  발명하지 않는다. 대신 literal 내부에 정확한 구분자열(`" | "` 등)이나
  `⟨`·`⟩` 자체가 나타나면 **직렬화는 그대로 쓰되 행에
  `serialization_flag=reserved_in_literal`을 기록**하고 QC가 건수를
  보고한다. 문자열은 표시·기초검색용 파생물이므로 무손실 파싱을 문자열
  자체에 요구하지 않고, 검증은 재생성 비교로 한다(§12). 조용한 오분석
  금지 요구는 flag+집계로 충족한다.
- **Unicode**: 모든 한글 필드는 NFC 동결. 입력이 NFD·혼합이면 NFC로
  정규화하되 원문과 달라진 행을 `normalization_changed=true`로 기록(무단
  변경 금지 원칙과 양립). 자모 열은 호환 자모 블록만 허용(코드 표와 동일
  문자, §2). 생성 필드에 U+00A0·U+3000 등 비ASCII 공백 유입 시 hard
  fail.
- **hard fail / flag / literal 보존 구분** (질문 11):
  - hard fail: 중복 `utt_id`, `tagged` 구조 파괴(빈 형태소 단위), 표
    사이 개수 불일치, 비ASCII 공백 유입, 로마자 토큰이 inventory 밖.
  - flag 후 계속: `align_warn`(form–tagged 어절 수 불일치),
    `contracted_fused`, `reserved_in_literal`, `normalization_changed`,
    혼합 표면형(`unit_type=mixed`).
  - literal 보존: 숫자·영문·한자·이모지·문장부호·비언어 표지는 `⟨…⟩`
    원문 보존 + `unit_type=literal`. 읽기 추측 금지(기존 원칙,
    `build_search_master.py` BUILD_PROVENANCE의 숫자·기호 정책).

## 4. 권장 정규화 데이터 모델

정본/파생 구분: **정본 = 아래 표의 좌표·표면형·자모 열. 파생 = 로마자
열(자모에서 결정적 재생성 가능)과 위치 범주(idx+count에서 계산).** 파생
열도 편의상 저장하되 재생성 검증 대상으로 삼는다.

### 4.1 `utterances` (발화 1행 — 기존 검색 마스터 계약의 확장)

기존 `build_search_master.py::BASE_COLS`를 유지하고 다음을 추가한다.

```text
tagged_roman            VARCHAR   v2 직렬화 (v1은 싣지 않음, §11)
roman_system_version    VARCHAR   'roman_mfa.v1'  (토큰 목록 불변)
serialization_version   VARCHAR   'tagged_roman.v2'
position_schema_version VARCHAR   'morph_position.v1'
serialization_flag      VARCHAR   ''|reserved_in_literal|...
```

### 4.2 `morph_tokens` (형태소 1행)

| 열 | 형 | null | 정본/파생 | 비고 |
|---|---|---|---|---|
| `utt_id` | VARCHAR | X | 정본 | join key |
| `year` | SMALLINT | X | 정본 | partition |
| `eojeol_idx` | SMALLINT | X | 정본 | 1-based, `tagged` 공백 분할. `assign_sense_layer.py::iter_morphs`의 `word_idx`와 동일 규칙 |
| `morph_idx_in_eojeol` | SMALLINT | X | 정본 | 1-based |
| `morph_idx_in_utterance` | SMALLINT | X | 파생 | 전 형태소 통산 1-based |
| `morph_count_in_eojeol` | SMALLINT | X | 파생 | |
| `morph_count_in_utterance` | SMALLINT | X | 파생 | |
| `morph_surface` | VARCHAR | X | 정본 | NFC |
| `pos_bareun` | VARCHAR | X | 정본 | |
| `unit_type` | VARCHAR | X | 파생 | `hangul`/`literal`/`mixed` |
| `morph_roman` | VARCHAR | O | 파생 | v2 unit (POS 제외) |
| `syllable_count` | SMALLINT | X | 파생 | 한글 음절 수 |
| `morph_to_form_status` | VARCHAR | X | 파생 | DESIGN §3.3 enum: `exact_concat/normalized/contracted_fused/token_split/token_merge/complex/unknown` |
| `align_warn` | BOOLEAN | X | 정본 복사 | 발화 수준 flag 전파 |

`morph_position_in_eojeol` 같은 범주 열은 **저장하지 않는다**(질문 7,
프롬프트 §6.2의 자체 우려에 동의). `single/initial/medial/final`은
`idx`+`count`에서 항상 파생 가능하고, 범주만 저장하면 `single`(1/1)과
`initial`(1/n)의 구분·재검증이 불가능해진다.

### 4.3 `morph_syllables` (분석 표층형의 음절 또는 literal 단위 1행)

| 열 | 형 | null | 정본/파생 | 비고 |
|---|---|---|---|---|
| `utt_id`, `year`, `eojeol_idx`, `morph_idx_in_eojeol` | 위와 동일 | X | 정본 | 부모 좌표 |
| `syllable_idx_in_morph` | SMALLINT | X | 정본 | 1-based |
| `syllable_count_in_morph` | SMALLINT | X | 파생 | |
| `syllable_idx_in_eojeol` | SMALLINT | X | 파생 | 분석 공간 통산. `contracted_fused` 어절에서는 form 음절과 대응하지 않음(§2 좌표계 주의) |
| `syllable_count_in_eojeol` | SMALLINT | X | 파생 | |
| `unit_type` | VARCHAR | X | 정본 | `hangul`/`literal` |
| `syllable_surface` | VARCHAR | X | 정본 | 음절 1자 또는 literal run 원문 |
| `onset_jamo` | VARCHAR | O | 정본 | ㅇ 포함. literal이면 NULL |
| `onset_roman` | VARCHAR | O | 파생 | ㅇ이면 `''`(빈 문자열) |
| `onset_zero` | BOOLEAN | O | 파생 | `onset_jamo = 'ㅇ'` |
| `nucleus_jamo` / `nucleus_roman` | VARCHAR | O | 정본/파생 | |
| `coda_jamo` / `coda_roman` | VARCHAR | O | 정본/파생 | 종성 없음 = NULL(빈 종성과 구분) |
| `parse_status` | VARCHAR | X | 파생 | `ok`/`not_hangul` |

NULL 규약: "슬롯이 없음"(개음절 coda)=NULL, "슬롯은 있으나 무음"(ㅇ
onset)=`onset_jamo='ㅇ'`+`onset_roman=''`+`onset_zero=true`. 이 구분이
질문 9의 구조화 해법이다.

**이 표가 분절 표를 겸한다** (질문 5·6·10): 슬롯당 로마자 토큰이 정확히
1개이므로(§2) `KK`·`ng`·`lk` 같은 가변 길이 토큰은 슬롯 열 1칸에 원자로
보존되고, 문자 단위 절단 문제가 원천적으로 없다. Parquet list 열 대안은
저사양 환경(8GB, DuckDB/pandas)에서 질의가 복잡해지고 Excel 추출도
어려워 기각한다. 별도 `morph_segments` 표는 중복이므로 기각한다.

### 4.4 `morph_boundaries` (인접 형태소 경계 1행 — 물질화된 파생 표)

발화 내 인접 형태소 쌍마다 1행(어절 내부 경계 + 어절 사이 경계 모두;
행 수 = 발화별 `n_morphs − 1`). **이 표 전체가 `morph_tokens`+
`morph_syllables`에서 결정적으로 파생**되므로 단일 builder로 물질화하고
재생성 검증한다. ㄴ삽입 등 후보 환경 검색의 중심 표이며 실현 판정 표가
아니다(프롬프트 §6.4 명시 유지).

```text
utt_id, year, boundary_idx                    정본 좌표 (1-based, 발화 통산)
boundary_scope                                'within_eojeol'/'between_eojeol'
left_eojeol_idx,  left_morph_idx_in_eojeol    좌 형태소 좌표
right_eojeol_idx, right_morph_idx_in_eojeol   우 형태소 좌표
left_surface, left_pos, left_unit_type
right_surface, right_pos, right_unit_type
left_final_syllable, left_final_jamo_underlying(=말음절 coda_jamo, NULL 가능)
left_final_roman
right_initial_syllable
right_initial_jamo_underlying(=첫음절 onset_jamo)
right_initial_roman
right_initial_onset_zero, right_initial_nucleus_jamo
within_same_eojeol, crosses_eojeol            BOOLEAN (파생)
map_status                                    좌우 morph_to_form_status 요약
align_warn                                    발화 flag 전파
```

`punctuation` scope는 별도 값으로 두지 않고 `left/right_unit_type=
literal`로 판별한다(scope 축과 단위 축을 섞지 않음 —
`DESIGN` §3.4의 `boundary_scope` 예시보다 직교적).

## 5. 위치 좌표 설계 (질문 7·8)

정본은 **각 층위의 `idx`(1-based) + `count` 쌍**이고, 위치 범주는 전부
파생이다.

```text
발화 내 어절:   eojeol_idx            / n_eojeol
어절 내 형태소: morph_idx_in_eojeol   / morph_count_in_eojeol
발화 내 형태소: morph_idx_in_utterance/ morph_count_in_utterance
형태소 내 음절: syllable_idx_in_morph / syllable_count_in_morph
어절 내 음절:   syllable_idx_in_eojeol/ syllable_count_in_eojeol
음절 내 분절:   슬롯 열 이름 자체(onset/nucleus/coda)가 좌표
```

파생 규칙: `initial := idx=1 ∧ count>1`, `final := idx=count ∧ count>1`,
`single := count=1`, `medial := 그 외`. 발화 처음 = `eojeol_idx=1 ∧
morph_idx_in_eojeol=1`처럼 상위 좌표의 합성으로 표현하므로 층위를 합친
단일 위치 열은 만들지 않는다(프롬프트 §5.1의 요구와 일치). 1-based는
기존 `assign_sense_layer.py::iter_morphs`(word_idx·morph_idx 1-based),
`DESIGN` §3.2(`eojeol_idx` 1부터)와 정합 — **의미번호 레이어
`02_sense_annotated`(utt_id, word_idx, morph_idx)와 좌표가 그대로
조인된다**는 것이 이 선택의 실질 이득이다.

## 6. 대표 예시 5개

아래 표기는 `morph_tokens`(MT)·`morph_syllables`(MS) 행을 축약 표기한
것이다. 좌표는 (eojeol_idx, morph_idx_in_eojeol[, syllable_idx_in_morph]).

### 예시 1 — `혹시 요즘` (일반 발화, 무음 초성 포함)

```text
tagged:           혹시/MAG 요즘/NNG
tagged_roman_v2:  H O k _ S I/MAG | YO _ J EU m/NNG        (v1과 동일 문자열)

MT (1,1) 혹시/MAG hangul  roman="H O k _ S I"  syll=2
MT (2,1) 요즘/NNG hangul  roman="YO _ J EU m"  syll=2
MS (1,1,1) 혹: onset ㅎ/H, nucleus ㅗ/O, coda ㄱ/k
MS (1,1,2) 시: onset ㅅ/S, nucleus ㅣ/I, coda NULL
MS (2,1,1) 요: onset ㅇ/'' zero=true, nucleus ㅛ/YO, coda NULL
MS (2,1,2) 즘: onset ㅈ/J, nucleus ㅡ/EU, coda ㅁ/m
```

`요`의 문자열 표기는 `YO` 하나지만 표에서는 `onset_zero=true`가 보존된다
— 프롬프트 §5.3의 요구를 문자열 변경 없이 충족.

### 예시 2 — `꽃에 모양은 어땠어?` (복수 형태소 어절·축약·문장부호)

```text
tagged: 꽃/NNG+에/JKB 모양/NNG+은/JX 어떻/VA+었/EP+어/EF+?/SF
v2:     KK O ch/NNG + E/JKB | M O _ YA ng/NNG + EU n/JX
        | EO _ TT EO h/VA + EO ss/EP + EO/EF + ⟨?⟩/SF

MT (1,1) 꽃/NNG   status=exact_concat
MT (1,2) 에/JKB   status=exact_concat        MS (1,2,1) 에: ㅇ zero, ㅔ/E
MT (3,1) 어떻/VA  status=contracted_fused    MS 어(ㅇ zero,ㅓ)·떻(ㄸ/TT,ㅓ,ㅎ/h)
MT (3,2) 었/EP    status=contracted_fused
MT (3,3) 어/EF    status=contracted_fused
MT (3,4) ?/SF     unit_type=literal, roman="⟨?⟩", MS 1행 parse_status=not_hangul
```

v1과의 차이는 `?/SF` → `⟨?⟩/SF`뿐. 어절 3의 분석 공간 음절 수(5)와 form
음절 수(어땠어, 3)가 달라 `syllable_idx_in_eojeol`은 분석 공간 좌표임이
flag로 드러난다.

### 예시 3 — 한 형태소 안의 여러 음절 (`모양/NNG`)

```text
MS (2,1,1) 모: idx_in_morph=1/2 → initial. onset ㅁ/M, ㅗ/O
MS (2,1,2) 양: idx_in_morph=2/2 → final.  onset ㅇ/'' zero, ㅑ/YA, ㅇ/ng
```

같은 음절 `양`이 "형태소 끝 음절"이면서 "onset은 무음, coda는 ㅇ(ng)"임이
슬롯 열로 분리된다 — coda의 ㅇ(=ng 발음 표기)과 onset의 무음 ㅇ이 다른
슬롯이므로 혼동이 없다.

### 예시 4 — 복수 형태소 어절의 경계 (`꽃+에`, morph_boundaries)

```text
boundary (utt, idx=1) scope=within_eojeol
  left  = (1,1) 꽃/NNG  final_syll=꽃  final_jamo=ㅊ  final_roman=ch
  right = (1,2) 에/JKB  init_syll=에  init_jamo=ㅇ  onset_zero=true
                         init_nucleus=ㅔ
boundary (utt, idx=2) scope=between_eojeol
  left  = (1,2) 에/JKB  final_jamo=NULL (개음절)
  right = (2,1) 모양/NNG init_jamo=ㅁ  init_roman=M
```

좌측 기저 종성 `ㅊ`이 중화 없이 보존된다 — 규칙·사전 발음 열과 별도의
철자 기저 층이라는 원칙(`WORKFLOW` §4) 그대로.

### 예시 5 — 숫자·비한글·불일치 (`무조건 1층으로`)

```text
tagged: 무조건/MAG 1/SN+층/NNG+으로/JKB
v2:     M U _ J O _ G EO n/MAG | ⟨1⟩/SN + CH EU ng/NNG + EU _ R O/JKB

MT (2,1) 1/SN  unit_type=literal  roman="⟨1⟩"
MT (2,2) 층/NNG hangul
boundary(1): left=1/SN(literal), right=층/NNG → 환경 검색에서
  left_unit_type=literal로 자동 제외/포함 선택 가능
```

form–tagged 어절 수가 불일치하는 발화(`align_warn`)도 표는 분석 공간
좌표로 생성하되 모든 행에 `align_warn=true`가 전파되어, 환경 검색 시
포함·제외를 질의자가 결정한다. v1이 이 어절을 form_roman에서 `∅`로
지웠던 것과 달리(혼합 어절 정보 손실), v2 형태소 로마자는 `층`을
검색 가능하게 남긴다.

## 7. 실제 검색 예시 (DuckDB SQL, 연도별 Parquet 대상)

```sql
-- 1) 형태소 첫 음절의 초성이 ㄴ인 후보
SELECT utt_id, eojeol_idx, morph_idx_in_eojeol
FROM morph_syllables
WHERE syllable_idx_in_morph = 1 AND onset_jamo = 'ㄴ';

-- 2) 형태소 내부(첫 음절 제외)에 종성 ㄺ(roman 'lk')을 가진 형태소
SELECT DISTINCT utt_id, eojeol_idx, morph_idx_in_eojeol
FROM morph_syllables
WHERE syllable_idx_in_morph > 1 AND coda_jamo = 'ㄺ';

-- 3) 어절 내부 형태소 경계: 좌 종성 있음 + 우 무음초성 i/y (ㄴ삽입류 후보)
SELECT b.*
FROM morph_boundaries b
WHERE b.within_same_eojeol
  AND b.left_final_jamo_underlying IS NOT NULL
  AND b.right_initial_onset_zero
  AND b.right_initial_nucleus_jamo IN ('ㅣ','ㅑ','ㅕ','ㅛ','ㅠ','ㅒ','ㅖ');

-- 4) 어절 사이 경계: 좌 어절이 NNG로 끝나고 우 어절이 경음화 가능 평음 시작
SELECT b.*
FROM morph_boundaries b
WHERE b.crosses_eojeol AND b.left_pos = 'NNG'
  AND b.right_initial_jamo_underlying IN ('ㄱ','ㄷ','ㅂ','ㅅ','ㅈ');

-- 5) 무음 초성 환경: 발화 어디든 onset_zero 음절과 그 좌측 문맥 join
SELECT s.utt_id, s.eojeol_idx, s.morph_idx_in_eojeol,
       s.syllable_idx_in_morph, s.syllable_surface
FROM morph_syllables s
WHERE s.onset_zero AND s.unit_type = 'hangul';
```

같은 질의를 v1/v2 문자열 정규식으로 재현하려면 무음 초성(표기 부재),
가변 길이 토큰, `/POS` 인접, literal 혼입을 모두 정규식으로 방어해야
한다 — 이것이 구조화 표가 "정규식을 잘 쓰면 된다"의 대안이 아니라
정본이어야 하는 이유다(프롬프트 §8 말미 요구에 대한 답).

## 8. 대안 A/B/C 비교와 최종 선택

| 기준 | A: v1 유지 + 구조화 표 | **B: v2 신설 + 구조화 표 (선택)** | C: 문자열 최소화 |
|---|---|---|---|
| 정밀 위치 검색 | 구조화 표 (동일) | 구조화 표 (동일) | 구조화 표 (동일) |
| 표시 문자열의 결함 | literal 무표시·혼합 어절 손실 잔존 | `⟨…⟩`·혼합 run 처리로 해소 | 표시 문자열 자체 부재 |
| TextGrid `[MORPH_R]` | v1 복제 | v2 복제 | 한글 `[MORPH]`만 → 연구자의 로마자 표시 요구(직전 리뷰 §3, 프롬프트 §2) 미충족 |
| 추가 비용 | 0 | v2 생성기 + 문서. 최종 연구 CSV는 어차피 신규 구축(`DESIGN` §8.0 "기준선 판본")이므로 한계 비용 미미 | 문자열 생성 비용 절약, 그러나 Praat·Excel 사용성 손실 |
| 재현성·감사 | v1 규격이 코드 관행으로만 존재 | EBNF·버전 동결, v1은 archive+결정적 재생성 | 버전 관리 단순 |
| 위험 | 결함이 "정본 표기"로 굳음 | v1/v2 혼용 기간의 혼동(버전 열로 통제) | 표시 검색 요구 회귀 |

**선택: B.** 이유 요약: (1) 정밀 검색 정본이 구조화 표라는 점은 세 안이
동일하므로, 차이는 표시 문자열의 품질이다. (2) v1의 literal 무표시는
실제 결함이고, 수정 비용은 최종 CSV 신규 구축에 흡수된다. (3) C는
TextGrid 내 로마자 표시·검색이라는 연구자의 명시 요구를 버린다. 기존
표기 보존에 가산점을 주지 않아도 B가 우월하며, v1→v2는 "최대한 유지"가
아니라 "위계는 검증 결과 건전하므로 유지, 결함부만 교정"이라는 판정이다.

TextGrid에는 **v2 하나만** 명시적으로 선택해 복제한다(v1/v2 병기 금지 —
파일당 문자열 중복과 혼동만 늘림).

## 9. TextGrid와 CSV/Parquet 역할 분담 (질문 15·16)

| 매체 | 역할 | 내용 |
|---|---|---|
| TextGrid `utterance_search` | 열린 파일 안의 표시·기초 검색 | `[MORPH]`(한글 정규화형)·`[MORPH_R]`(v2 직렬화 한 줄). **위치 좌표·구조화 정보 복제 금지** |
| 연도별 partitioned Parquet | 전량 정밀 검색 정본 | `morph_tokens`/`morph_syllables`/`morph_boundaries` + 발화 1행 마스터 |
| 작은 CSV | 사람 확인 | 파일럿 60발화 표 전체, 후보 추출 결과, QC 표본만 CSV로 추출. 전량 표의 CSV 미러는 만들지 않음 |

직전 리뷰의 결론(라벨은 검색용 파생물, 정본은 CSV)을 유지하되, `[MORPH_R]`
필드의 내용만 v1→v2로 교체한다. 좌표 전체를 label에 넣지 않는 것이
타당하다(질문 16: 예) — label은 재생성 비교로만 검증하므로 정보를 더
넣을수록 재생성 결합만 커진다.

## 10. 510만 발화 규모 추정과 확인 불가 항목

기지수: 발화 5,103,356 · 세션 17,156(`build_search_master.py`
BUILD_PROVENANCE). 발화당 평균 형태소·음절 수는 저장소에 없음 →
`확인 불가`. 아래는 가정 표기한 추정이다.

| 표 | 행 수 추정 (발화당 8–12형태소, 형태소당 1.6–1.9음절 가정) | Parquet(zstd) 추정 |
|---|---|---|
| `morph_tokens` | 4,100–6,100만 | 1–2 GB |
| `morph_syllables` | 7,000–1억 1,000만 | 2–4 GB |
| `morph_boundaries` | 3,600–5,600만 | 1–2 GB |

- **저장 형식** (질문 14): 연도별 partitioned Parquet(표당
  `year=YYYY/part-*.parquet`, 세션 묶음 단위 row group)를 정본으로,
  DuckDB로 질의. 세션별 CSV 전량 미러는 기각(수십 GB·질의 불가).
  별도 DuckDB 파일 색인은 선택 사항이며 Parquet+즉석 질의로 충분하다.
  8GB RAM에서도 DuckDB의 out-of-core 스캔으로 동작한다(단 실측 필요).
- **생성 비용**: 순수 텍스트 파생(자모 분해·좌표 계산)이라 CPU 경량.
  N200에서도 연도별 밤샘 배치 1회 내 완료를 예상하되 실측치는
  `확인 불가` — 2020 파일럿에서 처리율을 기록할 것.
- **재생성 결합**: 표가 전부 `tagged`의 결정적 함수이므로 스키마 변경 시
  재생성은 MFA와 무관하게 텍스트만으로 가능. 이것이 문자열에 정보를 덜
  넣는(§9) 설계의 보상이다.
- `확인 불가` 목록: 형태소·음절 총수와 분포, 예약문자·혼합 표면형 실제
  빈도, 동결 pre-MFA 48열의 전수 값 완전성, D: 환경의
  pyarrow/duckdb 설치 여부, 실제 처리율·최종 파일 크기.

## 11. 마이그레이션·schema version·archive 정책 (질문 19)

1. **버전 식별자 3축**: `roman_system=roman_mfa.v1`(토큰 목록 불변) ·
   `serialization=tagged_roman.v2` · `position_schema=morph_position.v1`.
   발화 1행 마스터와 각 Parquet 표의 메타(_build manifest)에 기록.
2. **v1 archive**: 기존 `tagged_roman` v1 값은 기준선 CSV의 archive
   절차(기존 `_archive`/`run_id` 규칙, `build_search_master.py::
   build_session`)로 보존한다. **최종 연구 CSV에는 v1 열을 싣지 않는다**
   — v1은 `tagged`에서 현행 코드(`tagged_to_roman`, git commit 고정)로
   언제든 결정적으로 재생성 가능하므로, 이중 문자열로 510만 행을 무겁게
   할 이유가 없다. manifest에 v1 생성 함수·commit·재생성 절차를 기록.
3. **제자리 덮어쓰기 금지**: 새 표·새 CSV는 별도 staging root + 새
   `run_id`로 만들고 전수 감사 후 승격(프롬프트 §9, 기존 원칙).
4. **변환 manifest**: v2 채택 시 60발화에 대해 v1↔v2 diff 목록(변경은
   literal 표기뿐이어야 함)을 만들어 교체 근거로 남긴다.

## 12. 자동 검증 gate와 연구자 파일럿 (질문 12·18)

**전수 preflight (구현 전, 연도별):**

1. 동결 pre-MFA CSV 전 세션에서 48열 헤더 존재 + `utt_id`·`form`·
   `tagged` 비결측 + `tagged_roman`(v1)·`form_roman` 존재 전수 확인
   (§0-1의 표본↔전수 간극 해소).
2. NFC·공백·중복 utt_id 스캔.

**빌드 gate (표 생성 시, 전수):**

1. **결정성**: 같은 입력으로 2회 생성 → Parquet 논리 내용 동일.
2. **3중 동등성**: (a) `canonicalize_tagged(tagged)`(공백→` | `, `+`→
   ` + `, NFC)와 저장된 정규화 한글형 바이트 동일, (b) `morph_tokens`를
   직렬화하면 `tagged_roman_v2`와 바이트 동일, (c) `morph_tokens`의
   surface/POS를 재조립하면 raw `tagged`(NFC)와 동일.
3. **음절 재조립**: `parse_status=ok` 행에서
   `compose(onset,nucleus,coda) == syllable_surface`
   (`predict_pron.py::compose` 재사용) — 전수.
4. **inventory**: 모든 roman 토큰이 `ONSET/VOWEL/SPELL_CODA` 표와
   `_roman_mfa_to_ipa.csv` 집합 안에 있고 대소문자 규칙(초성·중성 대문자,
   종성 소문자)을 지킴.
5. **개수 정합**: 발화별 `Σ형태소 == n_morphs`(bareun 열),
   어절 수 == `tagged` 분할 수, `boundary 행 수 == n_morphs − 1`,
   `morph_syllables`의 한글 행 수 == `Σ syllable_count`.
6. **레이어 교차**: 표본 세션에서 `02_sense_annotated`의
   (utt_id, word_idx, morph_idx) 집합과 `morph_tokens` 좌표 집합 일치 —
   분해 규칙이 어긋나면 의미번호 조인이 조용히 깨지므로 필수. (전수
   교차는 D: 접근·비용 문제로 표본 gate로 두되 분해 함수 자체를 공유
   모듈로 단일화해 원천 차단, §13-1.)
7. flag 집계 보고: `align_warn`·`contracted_fused`·`literal`·`mixed`·
   `reserved_in_literal`·`normalization_changed` 건수와 예시.

**60발화 파일럿 표본 구성** (질문 18): 기존 60발화(연도당 10) 전체 +
의도 표집한 edge case를 추가한다 — `align_warn` 행, `∅`/숫자 행,
비한글(라틴·기호) 형태소 행, `contracted_fused`(어땠어형), 겹받침
종성(ㄺ·ㅄ 등), 최장 발화. 실코퍼스에서 각 유형의 존재 여부·표본
추출은 D: 접근 필요 → `확인 불가`, preflight 보고서로 선정한다.

**연구자 확인 항목**: (1) §7류의 실환경 질의 2–3개(예: ㄴ삽입 후보,
어절 경계 경음화 환경)를 직접 실행해 hit가 의도한 환경인지 표본 청취
없이 표만으로 판독 가능한지, (2) hit에서 `utt_id`로 WAV/TextGrid 회수,
(3) TextGrid `[MORPH_R]` v2 표기의 가독성(특히 `⟨…⟩`가 오해 없는지),
(4) `∅`·`⟨…⟩`·`onset_zero`의 의미 구분이 README 설명으로 충분한지.
판정 회수는 기존 workbook 검증 경로를 재사용한다.

## 13. 코드 변경 지점과 구현 순서

1. **신규 `scripts/python/morph_schema.py`** (직전 리뷰의
   `textgrid_labels.py` 계획과 통합·확장): `iter_morphs()`(현행
   `assign_sense_layer.py::iter_morphs`·`predict_pron.py::_parse_morphs`
   의 중복 로직을 단일 출처로 승격), `canonicalize_tagged()`,
   `tagged_roman_v2()`, `decompose_syllable_slots()`, 버전 상수,
   inventory 검사. 로마자 표는 `predict_pron.py`에서 import(단일 출처
   유지).
2. **신규 `scripts/python/build_morph_position_tables.py`**: 동결
   pre-MFA CSV → 연도별 Parquet 3표. 세션 단위 checkpoint·재개, 실행
   보고서(JSON)·flag 집계. 입력은 읽기 전용.
3. **신규 preflight**: §12의 전수 preflight를 독립 스크립트로 만들어
   `logs/` 보고서를 남긴다(콘솔 한 줄 지시 금지 원칙).
4. **직전 리뷰 구현 계획의 수정**: TextGrid `[MORPH]`는
   `canonicalize_tagged`, `[MORPH_R]`는 `tagged_roman_v2` 출력을 사용.
   gate의 치환 비교를 재생성 비교로 교체(§0-2).
5. **테스트**: `morph_schema` 단위테스트(예시 5종 golden + 겹받침·혼합·
   NFD 입력·예약문자), 표 builder의 개수·재조립·3중 동등성 테스트,
   `test_build_search_master.py`에 v2 열·버전 열 검증 추가.
6. **이후(별도 트랙)**: 최종 연구 CSV(`utterances` 확장)에 v2·버전 열
   통합, 사전 발음·경계 환경 결합(`DESIGN` §3.4의 발음 열은 이번 스키마
   확정 뒤 후속).

구현 순서: 1 → 5(모듈 테스트) → 3(preflight) → 2(60발화 파일럿 생성)
→ §12 gate → 연구자 확인 → 문서 동결(STANDARD·WORKFLOW·DECISION 갱신)
→ 연도별 전량 생성.

## 14. 2020 전수 MFA 전 필수 vs 병행 가능 (질문 20)

**전수 MFA 시작 전 필수:**

1. 이 스키마(직렬화 v2 + 3표 + 좌표)의 연구자 확정과 문서 동결.
2. TextGrid `utterance_search` label 문법 확정(직전 리뷰 + 본 리뷰 §9)
   — label은 전수 export 산출물이므로 미동결 상태로 전수를 시작하면
   585만 파일 재작성 위험이 있다.
3. 60발화 재수출 + 3표 파일럿 + §12 gate + 연구자 승인(기존
   `PROJECT_CURRENT_STATE.md` "바로 다음 작업" gate와 동일 지점).

**전수 MFA와 병행 가능(순서 무관):**

- `morph_tokens`/`morph_syllables`/`morph_boundaries`의 연도별 전량 생성
  — 입력이 동결 pre-MFA 텍스트뿐이라 MFA 산출물과 무관하다. 단 D: 경합
  금지 원칙(CLAUDE.md 규칙 7)에 따라 MFA 배치와 동시 실행하지 않고 연도
  사이 틈에 돌린다.
- 사전 발음 색인, KOINA, post-MFA 보조 레이어(기존 계획 그대로).

**정렬 DB 보존 논거의 한계**: DB·interval CSV를 보존하면 TextGrid와
검색층은 나중에 재수출할 수 있으므로 이론상 MFA를 먼저 시작해도 복구
가능하다. 그러나 현행 연도 상태 기계는 4-tier export·QC·연구자 표본
검토를 연도 gate에 포함하므로(`WORKFLOW` §5·§8), label 미동결 상태로
시작하면 gate 산출물 전체가 재작업 대상이 된다. 순서를 바꿔 얻는 시간
이득이 없으므로 **기존 gate 순서 유지를 권고**한다.

## 부록: 설계 질문 1–20 답 위치

1 §3.2(유지) · 2 §3.3 · 3 §3.2(`/POS` 유지) · 4 §8(B) · 5 §2(슬롯 토큰)
· 6 §4.3(syllables가 겸함) · 7 §5(idx+count 정본) · 8 §5 · 9 §3.2(구조화
열만) · 10 §4.3(슬롯 열 원자 보존) · 11 §3.3 · 12 §12(3중 동등성) ·
13 §3.3(NFC·ASCII SP) · 14 §10(연도별 Parquet+DuckDB) · 15 §9 ·
16 §9(한 줄만) · 17 §4.2·§6 예시 2(enum+flag) · 18 §12 · 19 §11 ·
20 §14.
