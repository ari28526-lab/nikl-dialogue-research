# 설계 리뷰 결과: TextGrid 발화 수준 검색 tier (2026-07-31)

- 요청 문서:
  `docs/reviews/PROMPT_external_review_TextGrid_utterance_search_tier_20260730.md`
- 검토 브랜치: `agent/harden-pre-bulk-pipelines`
- 검토 기준 커밋: `0721bf4` (프롬프트 명시 커밋 `b0f5077`의 직후 커밋으로,
  차이는 프롬프트 문서 추가뿐)
- 검토 근거: 저장소의 코드·문서만 사용. D: 코퍼스·Dropbox 실물은 미접근.
  저장소로 확인 불가한 항목은 본문에 `확인 불가`로 명시.
- 검토 범위: 입출력 형식·방법론 설계. 코드 수정·PR 없음.
- 판정 성격: 이 문서는 리뷰 권고안이며, 연구자 확정 전까지 구현하지 않는다.

## 1. 한 문단 결론

**후보 A의 4-tier(`words / phones_mfa / utterance / utterance_search`)를
권장한다.** 시간 정렬 주장은 MFA DB에서 온 `words`·`phones_mfa` 두 층에만
남기고, 형태소·로마자는 발화 수준 단일 label로 내려 형태소 시간경계 주장을
완전히 제거하는 방향이 연구 목적(검색→수집→청취 판정)과 정확히 맞는다.
다만 현재 저장소는 같은 날짜의 문서끼리 목표 tier 이름이 서로 다르고(아래
충돌표), 실동작 코드는 여전히 legacy `words/phones/morphemes/utterance`를
쓰고 있으므로(`scripts/python/export_mfa_db_4tier.py`의 `tier_provenance`,
`scripts/python/realign_eojeol_merge_output.py::validate_4tier`), 이번
결정에서 이름·순서·label 문법·시간 범위를 한 번에 동결하고 세 문서
(WORKFLOW·DECISION·STANDARD)를 같은 커밋에서 일치시켜야 한다. label 문법은
CSV에서 이미 사용자 확정된 구분자 체계(음소 공백·음절 `_`·형태소 `+`·어절
`|`, `scripts/python/predict_pron.py` 상단 상수)를 TextGrid에 그대로
가져오는 것이 정답이며, 새 구분자를 발명하면 안 된다. 규칙 발음·사전
발음은 전량 TextGrid에 넣지 말고 CSV 정본에 둔다.

### 발견한 문서 간 충돌 (먼저 해소 필요)

| 출처 | 목표 tier |
|---|---|
| `WORKFLOW_r2_MFA_research_data_contract_20260730.md` §6.2, `DECISION_mfa_r2_review_global_issues_20260730.md` §4 | `words/phones_mfa/morph_analysis/utterance_info` |
| 리뷰 프롬프트 후보 A, `PROJECT_CURRENT_STATE.md` "현재 단계" | `words/phones_mfa/utterance/utterance_search` |
| `STANDARD_textgrid_tiers.md` 말미 | 전량 장기 권장 `words/phones_mfa/utterance` 3-tier |
| 실동작 코드 | `words/phones/morphemes/utterance` |

또 `morph_analysis`의 시간 범위도 문서끼리 다르다: DECISION은 "`0–xmax`
단일 구간", `DESIGN_pronunciation_environment_search_2026-07-25.md` §2.7과
실코드 `build_stratified_mfa_review_bundle.py::align_text_to_words`는 "어절
시간 slot 배치"다. 이번 결정으로 발화 수준 단일 label로 통일하면 이 충돌도
함께 해소된다.

## 2. 권장 tier schema

| # | tier 이름 | 출처 | 의미 | 유표 label 시간 범위 |
|---|---|---|---|---|
| 1 | `words` | MFA DB `word_interval` | 어절 시간 정렬 (불변) | MFA가 준 interval 그대로 |
| 2 | `phones_mfa` | MFA DB `phone_interval` | 자동 정렬 phone; **실제 실현 아님** | MFA가 준 interval 그대로 |
| 3 | `utterance` | frozen search master `form` | 사람이 읽는 한글 전사 | **첫 유표 word 시작 ~ 마지막 유표 word 끝** |
| 4 | `utterance_search` | search master의 `form_roman`·`tagged`·`tagged_roman` | 발화 수준 검색 표지; 시간 판정층 아님 | `utterance`와 동일 span |

- 순서는 시간층(1·2)을 위에, 읽기용(3)을 그 아래, 긴 검색 label(4)을 맨
  아래에 둔다. Praat에서 스펙트로그램–`words`–`phones_mfa` 대응을 가리지
  않기 위함(7-tier v3를 축소한 이유와 동일, DESIGN §2.7).
- **시간 범위는 `0–xmax` 전체가 아니라 "첫 유표 word 시작~마지막 유표 word
  끝"을 권장.** 근거:
  1. 이 두 경계는 MFA `words`에서 파생된 실측 경계라 새 시간 주장을 만들지
     않는다(설계 질문 6의 해법). 이미 구현·검증된
     `build_stratified_mfa_review_bundle.py::labeled_word_span`과 기존
     `utterance` 관행(`realign_eojeol_merge_output.py::write_4tier`,
     STANDARD 2026-07-25 보완)과 일치한다.
  2. `0–xmax` 단일 유표 구간은 tier 안에 경계가 하나도 없어, 연구자가
     반복 요구한 "처음·끝 경계 가시성"(GUIDE §7.3 `boundary_status`)을
     앞뒤 빈 interval로 충족할 수 없다.
  3. 발화가 0 또는 xmax에 붙은 경우의 가시성은 기존 정책대로 운영본이
     아니라 점검 사본의 0.05초 padding으로 해결한다(무padding 원칙 유지,
     WORKFLOW §6.2).
- 유표 word가 하나도 없는 발화는 `0–xmax`로 폴백하고 manifest에 flag를
  남긴다(현 코드의 폴백과 동일).
- 모든 tier는 지금처럼 `0–xmax`를 빈 interval 포함 연속으로 덮는다
  (`merge_textgrid_v2.py::interval_tier`가 gap을 자동 충전).
- 새 스키마는 tier 이름 자체(`phones_mfa`, `utterance_search`)가 legacy
  파일과 구별되므로 스키마 판별자 역할을 겸한다.

## 3. 권장 label 문법

원칙: **새 문법을 만들지 말고, CSV에서 이미 확정된 구분자 위계를 그대로
복제한다.** 그래야 연구자가 CSV용으로 익힌 정규식이 TextGrid에서 1:1로
재사용된다(`predict_pron.py` 구분자 상수,
`build_search_master.py::tagged_to_roman`).

- **field marker**: `[이름] ` (대괄호+대문자+공백). 기존 v4
  `utterance_info`와 동일 문법
  (`build_stratified_mfa_review_bundle.py::utterance_info_label`).
- **field 구성(전량 운영본)**: `[UTT]` `[ORTH_R]` `[MORPH]` `[MORPH_R]`
  4개 고정 + 이상 시에만 `[NOTE]`. `[FORM]`은 `utterance` tier와 중복이라
  넣지 않는다.
- **field separator**: 한 칸 공백 + 다음 `[이름]`.
  파싱 정규식: `\[([A-Z_]+)\] (.*?)(?= \[[A-Z_]+\] |$)`
- **어절 separator**: `[MORPH]`·`[MORPH_R]` 모두 ` | `.
  **`tagged`의 공백 어절 경계는 label에서 ` | `로 정규화해도 된다
  (설계 질문 8: 예).** raw `tagged`는 CSV 정본에 이미 있으므로 TextGrid에
  중복 보존하지 않는다.
- **형태소 separator**: ` + ` (tagged_roman과 동일). POS는 `/POS` 후치.
- **escaping**: `"`는 이미 `""`로 이중화되고 파서가 복원한다
  (`merge_textgrid_v2.py::esc`,
  `retrofit_textgrid_2020_2024.py::parse_mfa_textgrid`) — 추가 조치 불필요.
  `|`·`+`·`/`·대괄호가 실전사에 나타나는 경우는 escape 문법을 발명하지
  말고, (a) 검증 gate가 `form`/`tagged`에서 예약 패턴(` [A-Z_]+] `, `|`)을
  스캔해 건수·목록을 보고하고, (b) 걸린 발화는 `[NOTE] reserved_char`
  flag만 남긴다. TextGrid label은 검색용이지 무손실 파싱 대상이 아니며
  (정본은 CSV), escape 계층은 510만 건 재생성 비용만 키운다.
- **줄바꿈 금지, 한 줄 고정**: 현 파서 `parse_mfa_textgrid`는 regex
  기반이라 여러 줄 label을 읽지 못한다.

### 예시 1 — 일반 발화 (`혹시 요즘`)

```text
[UTT] SDRW2000000510.1.1.98 [ORTH_R] H O k _ S I | YO _ J EU m [MORPH] 혹시/MAG | 요즘/NNG [MORPH_R] H O k _ S I/MAG | YO _ J EU m/NNG
```

### 예시 2 — 복수 형태소 어절·문장부호 (`꽃에 모양은 어땠어?`, DESIGN §2 대표 발화)

```text
[UTT] SDRW2200000836.1.1.61 [ORTH_R] KK O ch _ E | M O _ YA ng _ EU n | EO _ TT AE ss _ EO [MORPH] 꽃/NNG + 에/JKB | 모양/NNG + 은/JX | 어떻/VA + 었/EP + 어/EF + ?/SF [MORPH_R] KK O ch/NNG + E/JKB | M O _ YA ng/NNG + EU n/JX | EO _ TT EO h/VA + EO ss/EP + EO/EF + ?/SF
```

(문장부호 형태소 `?/SF`는 `tagged_to_roman`의 현행 동작대로 비음절
표면형을 원문 유지.)

### 예시 3 — 숫자·분석 불일치 (`무조건 1층으로`, 테스트 픽스처 기반)

```text
[UTT] U1 [ORTH_R] M U _ J O _ G EO n | ∅ [MORPH] 무조건/MAG | 1/SN + 층/NNG + 으로/JKB [MORPH_R] M U _ J O _ G EO n/MAG | 1/SN + CH EU ng/NNG + EU _ R O/JKB [NOTE] orth_r_placeholder=1
```

`form`–`tagged` 어절 수 불일치(align_warn) 발화는 `[MORPH]`를 그대로 쓰되
`[NOTE] eojeol_tag_mismatch(3!=2)`를 덧붙인다(형식은
`predict_pron.py`의 warn 문자열 재사용). 이때 `[ORTH_R]`와 `[MORPH]`의
`|` 개수가 다를 수 있음이 NOTE로 명시된다.

## 4. 3/4/5-tier 대안 비교

| 기준 | B: 3-tier | **A: 4-tier (권장)** | C: 5-tier |
|---|---|---|---|
| 한글 전사 가독성 | 나쁨 — `[FORM]`이 긴 label에 묻힘 | 좋음 — `utterance` 독립 | 좋음 |
| 검색 편의 | 가능 | 가능 (한 tier에 3필드) | 가능하나 필드가 tier에 분산 |
| 형태소 로마자 위치 | label 내 필드 | label 내 필드 | 불명확(프롬프트 §4 자인) |
| Praat 화면 부담 | 최소 | 낮음 | v3 7-tier에서 이미 실패한 방향(DESIGN §2.7) |
| 기존 결정과 정합 | STANDARD 장기 3-tier와 일치하나 검색 요구 미충족 | G-TIER-01의 "시간층 2 + 비시간층" 구조 유지 | tier 축소 요청(GUIDE §2)에 역행 |
| 510만 건 비용 | 최소 | +약간(필드 3개) | +tier 오버헤드(각 tier가 header·빈 interval 추가) |

B는 연구자가 Praat에서 발화를 "읽는" 기본 동작을 훼손하고, C는 5-tier로
되돌아가면서 형태소 로마자의 자리가 없어 결국 6-tier로 팽창할 위험이
있다. A가 유일하게 "읽기 층과 검색 층의 분리 + tier 수 유지"를 동시에
만족한다.

## 5. CSV 정본과 TextGrid 복제 범위

| 정보 | CSV/Parquet (정본) | 전량 TextGrid | 점검 사본 TextGrid |
|---|---|---|---|
| `form` | O | O (`utterance`) | O |
| 철자 로마자(발화) `form_roman` | O | O (`[ORTH_R]`) | O |
| `tagged`(raw, 공백 경계) | O | X (정규화판 `[MORPH]`만) | X |
| `tagged_roman` | O | O (`[MORPH_R]`) | O |
| 규칙 발음 `pron_reference_*` | O | **X (설계 질문 7: CSV만)** | 온디맨드 `[RULE_H][RULE_R]` |
| 사전(우리말샘) 발음 | O | X | 온디맨드 `pron_dict` tier |
| `original_form` | O | X | 다를 때만 `[ORIG]` |
| 형태소별 구조화 환경(`morph_tokens`/`morph_boundaries`, G-CSV-01) | O | X | X |
| 화자·대화·사회변수, coverage, `pron_mfa`·`n_spn` 등 post-MFA 보조 | O | X | X |

규칙 발음을 전량본에서 빼는 이유: 연구자의 새 요구 4항목(프롬프트 §3)에
없고, "실제 발음으로 오해" 위험이 가장 큰 필드이며(WORKFLOW §4 표),
규칙기 버전이 바뀔 때마다 510만 TextGrid를 재생성해야 하는 결합을 만들기
때문이다. `tagged_roman`은 Bareun 결과가 동결 자산이라 이 위험이 없다.
이 권고는 DESIGN §6.1의 "전량본에 검색 문자열 중복 금지"보다 한 걸음
완화된 것인데, 연구자가 "TextGrid 자체를 열었을 때 검색"을 명시
요구했으므로 **4개 필드에 한해** 중복을 승인하고 그 근거를 STANDARD에
결정으로 남긴다.

## 6. 방법론적 위험

1. **거짓 시간 정밀성** — 핵심 위험은 제거된다(형태소 시간층 소멸). 잔여
   위험: (a) `utterance_search` span의 양끝이 word 경계에서 파생됐음을
   manifest에 명시하지 않으면 "발화 경계 판정값"으로 오해될 수 있음 →
   `tier_provenance`에 `utterance_search: word_span_derived` 기록.
   (b) `align_text_to_words`의 어절 slot 배치는 60발화 중 8건이
   `utterance_fallback`으로 빠질 만큼 취약하고(DESIGN §2.7 실측) 새
   의도와 어긋나므로 기본 경로에서 제거한다(설계 질문 12: word slot
   배치는 새 의도와 어긋남 — 단, 함수는 온디맨드 주입용으로 보존).
2. **실제 발음 오해** — `[ORTH_R]`·`[MORPH_R]`는 대문자 로마자라 phone처럼
   보일 수 있다. 완화: 필드명이 철자임을 README·GUIDE에 못 박고,
   `phones_mfa` tier명 대비를 유지하며, 규칙·사전 발음을 전량본에서
   배제한다. 이 로마자가 개정 로마자도 발음도 아니라는 문구를 번들 README
   템플릿(`build_stratified_mfa_review_bundle.py`,
   `package_mfa_r2_pilot_review.py`)에 반영한다.
3. **형태소 분석 오류 전파** — Bareun F1 0.929이므로 `[MORPH]` 검색 결과는
   후보군일 뿐이다. align_warn 발화는 `[ORTH_R]`와 `[MORPH]`의 `|` 위치가
   대응하지 않으므로 `[NOTE]` flag가 없으면 어절 위치 기반 검색이 조용히
   틀린다 — flag 필수. 또 `혹시`의 `H O k`처럼 onsetless `ㅇ`이 로마자에
   표기되지 않는 규약 한계(G-CSV-01에서 확인)는 label 검색으로 해결하지
   말고 구조화 `morph_tokens`/`morph_boundaries`(CSV 트랙)로 해결한다.
   label은 표시·기초검색, 환경 정밀 검색은 CSV — 역할 구분을 흐리지
   않는다.

## 7. 대량 처리 위험과 예상 병목

- **재생성 결합이 최대 위험**: label 문법을 바꾸면 510만 발화(약 585만
  TextGrid) 전체 재작성이다. 8GB/N200 + USB SSD에서는 밤샘 배치 수일 규모
  → 문법을 60발화 재수출 전에 동결하고, 스키마 버전을 연도별 export
  report에 기록해 부분 재생성이 가능하게 한다. (510만 건 실제 크기·시간
  분포는 저장소만으로는 `확인 불가` — 2020 첫 연도 실행에서 실측해 기록.)
- **크기 자체는 수용 가능 추정**: 필드 4개는 발화당 대략 수백 바이트,
  전체 수 GB 수준 추정(실측 필요). 파일 수는 불변이므로 I/O 병목의 지배
  요인(파일 생성 횟수)은 그대로다.
- **Praat로 코퍼스 검색 금지**: 수백만 파일 대상 검색은 Praat의 용도가
  아니다. `utterance_search`는 열어 놓은 파일 안에서의 검색·판독용이고,
  후보 추출은 CSV/Parquet에서 한다(설계 질문 10·11의 답).
- **resume 오염**: 현재 resume는 `validate_4tier`의 하드코딩된 legacy
  tier 이름으로 기존 파일을 valid로 skip한다
  (`export_mfa_db_4tier.py::export_session`). 새 스키마 export가 구
  output root 위에서 돌면 legacy 파일이 전부 재생성되거나, validator만
  바꾸면 구 파일이 새 파일로 오인된다 → 새 output root 필수(§10).
- **search master 열 계약**: 현 `load_session_forms`는 `utt_id`·`form`만
  읽는다. 새 exporter는 `form_roman`·`tagged`·`tagged_roman`이 필요한데,
  동결 pre-MFA 층은 5열뿐이므로(WORKFLOW §3.2) 연도별 실행 전 preflight
  에서 대상 search master CSV의 필수 열 존재를 하드 검증해야 한다
  (파일럿 run에는 `search__tagged_roman`이 60/60 존재했지만 전량 경로의
  연도별 CSV는 저장소만으로 `확인 불가`). 결측 시 빈 label로 조용히
  진행하지 말고 export 실패 처리.
- 기존 안전장치(연도 1개씩, spn gate, ThreadPool+read-only SQLite, D:
  경합 금지)는 그대로 유효하며 바꿀 필요 없다.

## 8. 필수 수정 / 나중 개선

**필수 (60발화 재수출 전):**

1. tier 이름·순서·label 문법·시간 범위 동결 + WORKFLOW §6.2·DECISION §4·
   STANDARD·GUIDE §7.2 표·번들 README 템플릿을 같은 커밋에서 일치.
2. label 생성·파싱을 단일 모듈로 구현(§10-1) — exporter와 점검 사본이
   같은 함수를 쓰게 한다.
3. exporter의 search-row 로더 확장 + 필수 열 하드 검증.
4. 새 스키마 전용 validator(레거시 이름 하드코딩 제거)와 테스트 갱신
   (`tests/test_export_mfa_db_4tier.py`의 tier 이름 단언 등).
5. 새 output root 정책(§10-6).

**나중 개선 (재수출을 막지 않음):**

- `morph_tokens`/`morph_boundaries` 파생표(G-CSV-01) — CSV 트랙이라 병행
  가능, TextGrid 스키마와 독립.
- 온디맨드 주입 tier(`pron_dict`·`candidate`·`prosody_koina` 등,
  DESIGN §6.2).
- `align_text_to_words`의 공식 deprecate 및 어절 slot 표시 사본 옵션화.
- label 길이·예약문자 통계의 전연도 집계.

## 9. 검증 gate

**자동 (60발화 재수출 시 전수):**

1. word·phone interval이 보존 DB 재수출과 의미상 동일(기존
   `intervals_semantically_equal`·`verify_mfa_db_4tier_sample.py` 재사용)
   — 60/60.
2. tier 이름·순서 정확히 `words/phones_mfa/utterance/utterance_search`,
   4개, `0–xmax` 연속, duration=원본, 파일 수 60, legacy `morphemes`
   tier 0건.
3. `utterance`·`utterance_search` 유표 span == 첫/마지막 유표 word 경계
   (±1e-6); 유표 word 없는 발화는 폴백 flag와 함께 집계.
4. **label 왕복 검증**: label에서 `[MORPH]`를 추출해 ` | `→공백 복원 시
   CSV `tagged`와 일치, `[ORTH_R]`==`form_roman`,
   `[MORPH_R]`==`tagged_roman` (바이트 동일) — 60/60.
5. `[MORPH]` 어절 수==`n_eojeol` 또는 `[NOTE] eojeol_tag_mismatch` 존재;
   `∅` 포함 발화는 `[NOTE]` 필수.
6. 예약 패턴 스캔(`form`/`tagged` 안의 ` [A-Z_]+] `·`|`) 건수 보고
   (기대 0).
7. 기존 gate 유지: `spn=0`, utt_id–파일명 일치, WAV duration 대조.

**연구자 최소 표본:** 연도별 첫 사례 6개(1·11·21·31·41·51번, GUIDE §12)
+ 자동 gate에서 flag된 전 건. 확인 항목: (a) `utterance`가 읽기 편한가,
(b) Praat 검색으로 형태소 하나(예: `요즘/NNG`)를 실제로 찾는 시연,
(c) 처음·끝 경계 가시성, (d) 어떤 tier도 발음 판정처럼 읽히지 않는가.
판정 회수는 기존 `validate_mfa_r2_review_workbook.py` 경로 그대로.

## 10. 코드 변경 지점 (구현 순서)

1. **신규 `scripts/python/textgrid_labels.py`**:
   `utterance_search_label()`, `tagged_to_morph_label()`(공백→` | `
   정규화), `parse_search_label()`(gate용), 예약문자 스캔.
   `build_search_master.py::tagged_to_roman`과
   `build_stratified_mfa_review_bundle.py::utterance_info_label`을 이
   모듈로 수렴. 단위테스트 동시 작성.
2. **`scripts/python/export_mfa_db_4tier.py`**: `schema_version` 2→3;
   `morpheme_tier` import·호출 제거; `load_session_forms`를 다열 로더로
   확장 + 필수 열 검증; 새 `write_research_4tier`/
   `validate_research_4tier` 사용; `tier_provenance` 갱신. legacy
   `realign_eojeol_merge_output.py`의 `write_4tier`/`validate_4tier`는
   수정하지 않고(pilot v1 증거·구 경로 보존) 새 함수를 별도로 둔다.
3. **audit·verify 계열**(`audit_mfa_4tier_year.py`,
   `verify_mfa_db_4tier_sample.py`): 기대 tier 이름을 스키마 인자로 받게
   하고, 새 root에서 legacy 이름 발견 시 하드 실패.
4. **`build_stratified_mfa_review_bundle.py`**: 점검 사본도 같은 label
   모듈 사용, `REVIEW_TIERS`를 새 스키마로, 점검 사본에서만
   `[RULE_H][RULE_R]` 추가 필드 허용; `verify_existing_bundle`의 기대
   tier 목록 분기 갱신.
5. **테스트**: `tests/test_export_mfa_db_4tier.py`·
   `tests/test_audit_mfa_4tier_year.py`의 tier 이름 단언 갱신 + label
   왕복 테스트 추가.
6. **출력 정책**: pilot v1 `textgrid_4tier`는 그대로 두고 새 스키마는 새
   root(예: `textgrid_research_v3_<date>`)에 생성. 기존 결과 덮어쓰기·
   이름 일괄 변경 금지(DESIGN §6.1 기존 원칙). 보존 pilot DB·CSV에서
   60발화 재수출 → §9 gate → 연구자 재검토 → 승인 후 2020 전수.

## 불변 기준 확인

MFA 재정렬 불필요(보존 DB에서 재수출만). 기존 word·phone interval, 2020–
2025 공통 phone 기준, 공통 발음사전·Jamo G2P, 원 WAV/JSON/CSV, MFA phone과
실현 판정의 분리, 발음 출처 분리, `utt_id` 연결 — 위 어느 권고도 이들을
건드리지 않는다(프롬프트 §6 준수).
