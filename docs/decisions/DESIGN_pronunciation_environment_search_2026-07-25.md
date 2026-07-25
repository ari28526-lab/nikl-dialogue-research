# 음운·형태 환경 검색과 CSV–WAV–TextGrid 연동 설계

작성일: 2026-07-25

상태: 대표 발화 조사 완료, 최소 점검 TextGrid v4 파일럿 구현·검증

대표 점검 발화: `SDRW2200000836.1.1.61`

관련 문서:

- `DESIGN_search_master_layer.md`
- `DESIGN_candidate_infrastructure_layers_2026-07-24.md`
- `STANDARD_textgrid_tiers.md`
- `REVIEW_MFA_pilot_manual_feedback_2026-07-25.md`
- `METHODS_bareun_dialogue_reanalysis.md`

## 1. 연구 목적과 자동화의 경계

이 인프라의 목적은 자동 발음열이나 MFA phone으로 실제 실현을 판정하는 것이
아니다. 연구 흐름은 다음과 같다.

1. CSV에서 특정 형태소 또는 표기·음운·형태 경계 환경을 검색한다.
2. 각 후보의 정확한 좌표와 WAV·TextGrid를 함께 모은다.
3. 필요한 후보에 KOINA 운율 분석을 결합한다.
4. 연구자가 음성과 TextGrid를 직접 검토해 실제 실현을 판정한다.
5. 수동 판정값을 형태소·사전·규칙 발음·화자·사용역·운율 정보와 조인한다.

따라서 다음 세 값은 끝까지 별도 열과 별도 출처로 보존해야 한다.

| 층 | 의미 | 최종 실현 판정에 사용 |
|---|---|---|
| 사전 발음 | 표제어·의미별 독립형 표준 발음 | 기준 자료 |
| 규칙 발음 | 표기와 형태 경계에 규칙을 적용한 문맥 예상형 | 후보 검색·비교 기준 |
| MFA phones | G2P/사전 phone열을 음성에 강제 정렬한 시간 구간 | 위치 탐색·분절 보조 |

최종 실현값은 별도 연구자 판정표에만 기록한다.

### 1.1 처리 순서: pre-MFA와 post-MFA를 섞지 않는다

이 문서에서 말하는 파이프라인 판본과 사전 파일의 과거 `v1/v2` 명칭이
혼동됐으므로 다음 이름으로 고정한다.

```text
pre_mfa_linguistic_master
    ↓
mfa_alignment
    ↓
post_mfa_alignment_index
    ↓
review_bundle + KOINA + human_annotation
```

#### MFA 전: `pre_mfa_linguistic_master`

- `form`, `original_form`, Bareun 형태소, A2 의미번호
- 형태소·어절 철자 로마자
- 사전 독립형 발음과 규칙 문맥 예상 발음
- 음운·형태 경계 환경과 후보 좌표
- 화자·대화·사회 변수
- MFA 입력 WAV·lab manifest

사전·규칙 발음은 실제 실현이 아니라 MFA 전에 준비할 수 있는 언어학적
기준선이다.

#### MFA 실행

- MFA용 작업 WAV·lab
- `words`, `phones` 시간 정렬
- 실패·누락·`spn`·duration·재시도 QC

#### MFA 후: `post_mfa_alignment_index`

- `phones_mfa`와 시작·끝 시간
- TextGrid 스키마와 정렬 상태
- WAV·TextGrid·CSV 경로 및 파일 coverage
- `utt_id + eojeol_idx` 조인 결과

MFA 시간정보는 MFA 전에 존재할 수 없다. 또한 post-MFA 결과를 pre-MFA
언어정보에 덮어쓰지 않고 별도 표로 둔 뒤, 연구용 view에서 조인한다.

#### 수동 검토

- 점검 사본 TextGrid
- KOINA
- 후보별 연구자 실현 판정

사전 예외 발음을 MFA 사전에 직접 투입할지는 별도 소표본 A/B 파일럿으로
결정한다. 우선은 사전 발음을 검색·비교 기준으로 붙이고 기존 G2P MFA를
교란하지 않는다.

## 2. 대표 발화의 원천 추적 결과

### 2.1 원본 JSON

원본:

`D:\00_RAW\dialogue_json\NIKL_DIALOGUE_2022_v1.0_JSON\NIKL_DIALOGUE_2022_v1.0\SDRW2200000836.json`

```text
id            SDRW2200000836.1.1.61
speaker_id    SD2201235
form          꽃에 모양은 어땠어?
original_form 꽃에 모양은 어땠어?
start         201.5325
end           203.1795
note          (빈 값)
```

이 JSON에는 별도의 발음 전사 필드가 없다. `form`과 `original_form`은 이
발화에서 동일하며, `pron_reference`의 출처가 아니다.

### 2.2 Bareun·A2 형태소

```text
꽃/NNG + 에/JKB
모양/NNG + 은/JX
어떻/VA + 었/EP + 어/EF + ?/SF
```

A2 의미 레이어의 내용어:

| word_idx | morph_idx | 형태소 | 품사 | sense_id | 방법 |
|---:|---:|---|---|---|---|
| 1 | 1 | 꽃 | NNG | 1 | ls_sxls |
| 2 | 1 | 모양 | NNG | 2 | ls_sxls |
| 3 | 1 | 어떻 | VA | 1 | ls_sxls |

조사·어미·기호는 A2에서 `not_target`으로 남아 있다. 형태소 자체는 빠지지
않았으므로, 발음 사전 조회에서는 A2 대상 여부와 무관하게 모두 다뤄야 한다.

### 2.3 통합 사전

두 사전 자료의 혼동을 막기 위해 파일명 대신 다음 역할명으로 부른다.

```text
lexicon_enriched
  D:\00_RAW\reference\00_DICTIONARY\01_NIKL_lexicon_full_v2.csv

lexicon_legacy_pron
  D:\00_RAW\reference\03_lexicon_1기\01_NIKL_lexicon_full.csv
```

2026-07-25 전수 실측:

| 항목 | `lexicon_enriched` | `lexicon_legacy_pron` |
|---|---:|---:|
| 행 | 1,165,157 | 1,296,777 |
| `pron_1` 있음 | 500,561 | 613,441 |
| `pron_2` 있음 | 38,340 | 41,237 |
| `pron_g2p` 있음 | **0** | 683,336 |
| 어떤 발음이든 있음 | 500,561 | 1,296,777 |
| 발음 전부 없음 | 664,596 | 0 |

`lexicon_enriched`는 MFA 로마자, 2023 발음, 우리말샘·표준국어대사전 대응
코드, 품사군, 의미번호 등 조회 메타데이터가 더 풍부하지만
`pron_g2p` 열은 전 행이 비어 있다. 따라서 이 파일만으로 발음 색인을 만들면
조사·어미를 포함한 664,596행이 빠진다.

`lexicon_enriched`의 발음 없는 664,596행은 모두 `urimal_id`가 있고,
663,687개 고유 ID 전부가 `lexicon_legacy_pron`의 `pron_g2p` 하나와
일의적으로 대응했다. 미대응·복수 대응은 0이었다. 권장 색인은 다음과 같다.

1. 행 구조·의미·품사·표준사전 대응은 `lexicon_enriched`
2. `pron_1`이 있으면 그대로 사용
3. 없으면 같은 `urimal_id`의 `lexicon_legacy_pron.pron_g2p` 보완
4. 보완 출처를 `legacy_g2p_by_urimal_id`로 기록
5. `lexicon_enriched`에 없는 legacy 전용 항목의 포함 여부는 별도 집합 감사 후
   결정

대표 결과:

- `꽃/NNG`의 독립형 `pron_1`은 `꼳`이다.
- `모양`은 의미에 따라 장음 표시가 달라질 수 있다. A2의 의미번호를 먼저
  적용해야 한다.
- `어떻`은 표제어 `어떻다/VA`의 어간 별칭으로 조회되며 `pron_1=어떠타`다.
- `에/JKB`는 `lexicon_enriched`에 실제로 있다. 과거 `lexicon_legacy_pron`의
  같은 `urimal_id` 행은 `JX`로 되어 있어 판본 사이 품사 정규화가 일어났다.
- `었`은 Bareun에서 `EP`지만 사전 행은 `EF`로 보이는 경우가 있다.

따라서 `에`에 대한 초기 “JKB 항목 없음” 판단은 정정한다. 그러나 `었/EP`처럼
실제 품사 불일치는 남으므로 `(표층형, Bareun 품사)` 완전일치만 쓰면 일부
조사·어미가 누락된다. 반대로 품사를 무시하면 동형이의 형태소가 잘못 결합될
수 있다. `urimal_id` 판본 조인과 검증된 품사 대응표를 각각 분리해야 한다.

사전 파일은 의미·빈도원 병합 때문에 동일 항목이 여러 행으로 반복된다.
CSV를 발화 자료에 직접 조인하면 행 수가 폭증할 수 있으므로, 먼저 발음이 같은
중복을 제거한 작은 색인을 만들어야 한다.

### 2.4 규칙 예상 발음

현재 규칙기는 다음을 산출한다.

```text
pron_reference_hangul  꼬체 모양은 어때써
pron_reference_roman   KK O _ CH E | M O _ YA ng _ EU n | EO _ TT AE _ SS EO
source                 form_rule_prediction
```

여기서 `꽃`의 독립형 사전 발음 `꼳`을 그대로 `에`와 이어 붙여서는
`꼬체`를 만들 수 없다. 문맥 규칙은 `꽃+에`의 철자 기저 종성 `ㅊ`을 보존한
상태에서 적용해야 한다. 따라서 다음과 같은 단순 결합은 금지한다.

```text
사전 독립형 발음들을 연결 → 경계 규칙
```

안전한 구조는 다음 두 결과를 병렬로 보존하는 것이다.

```text
형태소별 사전 발음(독립형 기준)
표기·형태 경계 기반 문맥 규칙 발음
```

향후 사전 예외를 문맥 규칙기의 입력에 반영할 때도, 독립형 표면 발음 전체를
덮어쓰지 말고 어떤 음운표현 또는 예외 규칙을 대체했는지 사건 단위로 기록해야
한다.

### 2.5 현재 TextGrid

현재 파일럿 4-tier:

1. `words`: `꽃에 | 모양은 | 어땠어`
2. `phones`: MFA/G2P 정렬
3. `morphemes`: `꽃 | 에 | 모양 | 은 | 어땠어`
4. `utterance`: `꽃에 모양은 어땠어?`

기존 점검용 6-tier에는 `original_form`, `pron_reference`가 추가돼 있다.

문제:

- Bareun/A2는 문장부호까지 8형태소인데 `morphemes` tier는 5개 라벨이다.
- `어떻+었+어`가 `어땠어` 한 구간으로 합쳐져 있다.
- 이 tier는 기존 `06_textgrid_merged`의 `words`를 재사용한 것으로, 현재
  Bareun 형태소 토큰을 새로 정렬한 결과가 아니다.
- `phones`에서 `꽃에`가 대략 `k͈-o-n-e`로 정렬돼 규칙 기준 `꼬체`와도
  다르다. 실제 실현 또는 정답 발음으로 해석할 수 없다.

따라서 현재 `morphemes`라는 이름만 보고 A2 `morph_idx`와 1:1 대응한다고
가정하면 안 된다.

### 2.6 2026-07-25 점검 TextGrid v3 검증

기존 6개 수동 검토본과 새 60개 점검본을 전수 검사했다.

| 점검본 | 왼쪽 가시적 빈 구간 없음 | 오른쪽 가시적 빈 구간 없음 |
|---|---:|---:|
| 구 `6_review` 6개 | tier별 다수 | tier별 다수 |
| 새 60개 6-tier | 10발화 | 3발화 |

모든 tier가 구조적으로 `0–xmax`를 덮더라도, 정렬 라벨이 실제로 0 또는
`xmax`에 붙으면 Praat에서 앞뒤 빈 구간 경계가 보이지 않는다. 라벨 시간을
임의로 잘라 빈 interval을 만드는 대신 점검 **사본**에만 다음을 적용했다.

1. 원 WAV를 수정하지 않고 점검 WAV 앞뒤에 각각 0.05초 0 진폭 무음 추가
2. 모든 TextGrid 구간을 정확히 +0.05초 이동
3. 새 `xmax = 원 xmax + 0.10초`
4. 모든 tier의 첫·끝에 최소 0.05초 빈 interval 강제 검사
5. 원시간 환산은 `source_time = review_time - 0.05`

실자료 60개는 전부 16 kHz, mono, 16-bit PCM이었다. 중앙 PCM frame이 원본과
완전히 같은지, 양끝이 0인지 전수 검증했다.

점검 v3 tier:

1. `words`
2. `phones_mfa`
3. `morphemes_legacy`
4. `morph_analysis`
5. `original_form`
6. `pron_reference`
7. `utterance`

60개 모든 tier에서 좌우 가시적 빈 구간 60/60, `0–xmax` 연속 coverage
60/60을 통과했다. `morph_analysis`는 현재 Bareun 형태소열을 **어절 시간**에
표시하며 형태소 내부의 새 음향 경계를 주장하지 않는다.

대표 발화 v3:

```text
words:
  꽃에 | 모양은 | 어땠어

morphemes_legacy:
  꽃 | 에 | 모양 | 은 | 어땠어

morph_analysis:
  꽃/NNG+에/JKB
  모양/NNG+은/JX
  어떻/VA+었/EP+어/EF+?/SF
```

이 구성은 구형 시간 분절과 현재 형태소 분석을 동시에 보여 주되 둘을 같은
것으로 오해하지 않게 한다.

### 2.7 7-tier 검증판에서 최소 4-tier v4로 축소

v3의 7개 tier는 출처 분리와 경계 검증에는 유용했지만, 연구자가 실제로
Praat에서 검토할 때 같은 발화 수준 문자열이 여러 줄을 차지하고 핵심
`words`–`phones_mfa` 대응을 가렸다. 기술적으로 통과한 v3는 시행착오와
provenance 확인용 중간 산출물로 보존하되, 기본 점검본으로 승격하지 않는다.

최종 기본 점검본 v4는 다음 4개 tier만 사용한다.

1. `words`: MFA 어절 정렬
2. `phones_mfa`: MFA/G2P phone 정렬; 실제 실현 판정값이 아님
3. `morph_analysis`: 현재 Bareun 형태소열을 어절 시간에 표시
4. `utterance_info`: 발화 수준 검색·판독 정보

`utterance_info`는 별도 tier를 늘리는 대신 한 label 안에 출처가 드러나는
고정 표지를 사용한다.

```text
[UTT] ...
[FORM] ...
[ORTH_R] ...
[ORIG] ...                 # form과 다를 때만
[REF_FORM] ...             # 숫자·기호 보완 입력이 다를 때만
[REF_ORTH_R] ...           # 위 경우에만
[RULE_H] ...
[RULE_R] ...
```

따라서 Praat에서도 발화 ID, 철자, 철자 기반 로마자, 규칙 예상 발음 한글·
로마자를 검색할 수 있다. `RULE_H/R`은 사전 발음이나 실제 실현이 아니라
규칙 기반 기준선이다. 사전 예외 발음, 형태소별 철자 로마자, 경계별 환경,
구형 분절은 CSV/Parquet을 정본으로 두고 필요한 후보에만 주입한다.

실자료 60발화 재생성·전수 검증 결과:

- 6개년 각 10발화, 총 60발화
- 정확히 4-tier: 60/60
- 모든 tier 좌우 0.05초 이상 빈 interval: 60/60
- `UTT/FORM/ORTH_R/RULE_H/RULE_R` 표지 존재: 각 60/60
- 원 `words/phones` 의미를 padding 제거 후 재대조: 120/120
- 원 WAV 중앙 PCM frame 보존, 좌우 0값: 60/60
- 형태소 어절 매핑: `all_lexical_slots` 24,
  `labeled_word_slots` 28, `utterance_fallback` 8

fallback 8건은 잘못된 1:1 대응을 만들지 않고 발화 전체에 `[align≠]`로
표시하며 `tier_warning`에 토큰 수 불일치를 남긴다.

## 3. 권장 데이터 구조

발화 한 행짜리 CSV에 모든 정보를 긴 문자열로만 넣으면 형태 경계 검색과
한 발화 안의 복수 후보를 안정적으로 표현할 수 없다. 사람이 보는 세션별 CSV는
유지하되, 검색용 Parquet은 다음 정규화 표를 함께 만든다.

### 3.1 `utterances`

행 단위: 발화 1개.

주요 열:

```text
utt_id, year, session_id, dialogue_id, speaker_id
form, original_form, tagged
start, end, dur, note
category_norm, discourse_mode, topic
sex, age_norm, occupation_norm, ...
form_roman
pron_rule_hangul, pron_rule_roman, pron_rule_ipa
pron_rule_source, pron_rule_status, rule_version
eojeol_map_status
```

기존 search master의 역할을 보존한다. `pron_pred_*` 구열을 즉시 삭제하거나
덮어쓰지 않고, 새 이름으로 승격할 때 명시적인 스키마 버전을 둔다.

### 3.2 `eojeol_tokens`

행 단위: 표기 어절 1개.

```text
utt_id, eojeol_idx
eojeol_form, eojeol_original
eojeol_form_roman
eojeol_pron_rule_hangul, eojeol_pron_rule_roman
char_start_form, char_end_form
word_tg_start, word_tg_end
word_tg_label
word_alignment_status
```

`eojeol_idx`는 1부터 시작하고 A2 `word_idx`, TextGrid의 유표 `words`
interval 순서와 교차검증한다. 공백 interval의 물리 인덱스를 어절 번호로
사용하지 않는다.

### 3.3 `morph_tokens`

행 단위: 형태소 1개.

```text
utt_id, eojeol_idx, morph_idx, morph_global_idx
morph_surface, lemma, pos_bareun, pos_lexicon
sense_id, sense_confidence, sense_method
morph_roman
dict_headword, dict_sense_no
dict_pron_primary_hangul, dict_pron_primary_roman
dict_pron_alt_hangul, dict_pron_alt_roman
dict_pron_source, dict_lookup_status, dict_match_type
morph_to_form_status
morph_tg_start, morph_tg_end, morph_tg_status
```

`morph_to_form_status` 권장값:

- `exact_concat`: 형태소 표층 연결이 해당 form 어절과 정확히 일치
- `normalized`: 문장부호·공백 정규화 뒤 일치
- `contracted_fused`: 축약·융합으로 단순 문자 위치를 줄 수 없음
- `token_split`
- `token_merge`
- `complex`
- `unknown`

대표 발화의 `어떻+었+어 → 어땠어`는 `contracted_fused`에 해당한다. 이때
형태소 정보를 삭제하지 않되, 근거 없는 세부 시간 경계를 만들어서는 안 된다.

### 3.4 `morph_boundaries`

행 단위: 인접한 형태소 또는 어절 사이 경계 1개. 음운·형태 환경 검색의 핵심
테이블이다.

```text
boundary_id
utt_id, boundary_idx
left_eojeol_idx, left_morph_idx
right_eojeol_idx, right_morph_idx
boundary_scope
left_surface, left_lemma, left_pos, left_sense_id
right_surface, right_lemma, right_pos, right_sense_id
left_final_jamo_underlying, right_initial_jamo_underlying
left_final_phone_class, right_initial_phone_class
left_dict_pron_final, right_dict_pron_initial
left_rule_pron_final, right_rule_pron_initial
within_same_eojeol, crosses_eojeol
map_status, time_status
boundary_time_start, boundary_time_end
```

`boundary_scope` 예:

- `within_eojeol_morph`
- `between_eojeol`
- `punctuation`
- `unknown`

검색은 `tagged` 문자열 정규식만 쓰지 않고 이 테이블의 구조화된 좌우 열을
사용한다. 예를 들어 특정 형태소 뒤, 특정 품사 결합, 종성 자음 뒤 i/y 계열
환경, 동일 어절 내부와 어절 경계의 대조를 각각 명시적으로 조회할 수 있다.

### 3.5 `file_index`

행 단위: 발화 1개.

```text
utt_id
wav_path, wav_exists, wav_size, wav_duration
lab_path, lab_exists
textgrid_path, textgrid_exists, textgrid_schema_version
search_master_path, sense_path
quarantined, quarantine_reason
preferred_review_textgrid
files_ready
index_run_id, indexed_at
```

경로 계산은 `paths.py`와 `locate_utt.py` 한 곳에서 한다. 데이터 표마다 서로
다른 경로 규칙을 다시 구현하지 않는다.

전량 WAV에 매번 SHA256을 계산하면 I/O 비용이 크다. 전량 인덱스에는
크기·duration·수정시각을 기록하고, 연구자에게 복사하는 선택 후보 묶음에는
원본과 사본 SHA256을 계산해 복사 무결성을 보증한다.

### 3.6 `candidates`

행 단위: 현상 후보 1개. 같은 발화에 후보가 여러 개면 여러 행이다.

```text
candidate_id, phenomenon, detector_version
utt_id, candidate_idx, boundary_id
eojeol_idx, morph_idx
orthographic_context, morphological_context
rule_pron_context, dictionary_pron_context
candidate_reason, exclusion_flag
wav_path, textgrid_path
bundle_relpath, bundle_status
```

`candidate_id`는 최소한
`phenomenon + utt_id + boundary_idx + detector_version`으로 재현 가능하게
만든다.

### 3.7 `annotations`와 `koina`

자동 파생층과 연구자 판단층을 분리한다.

```text
annotations:
candidate_id, realization, confidence, annotator, annotated_at
evidence_start, evidence_end, exclusion_reason, note

koina:
candidate_id 또는 utt_id+time
analysis_version, ip_ap_label, prosody_features, qc_status
```

자동 재생성은 `annotations`를 절대 덮어쓰지 않는다.

## 4. 사전 발음 색인 규칙

### 4.1 중복 제거

원본 lexicon 행을 search master에 직접 조인하지 않는다. 다음 키와 발음
집합으로 작은 색인을 먼저 만든다.

```text
headword, word_stem, pos_tag, pos_group, sense_no
urimal_id, stdict_target_code, stdict_sense_code
pron_1, pron_2, pron_g2p
```

빈도원만 다른 완전 중복은 하나로 합치고 빈도는 합계가 아니라 원본 정의에
맞는 대표/최댓값 정책을 별도로 기록한다.

### 4.2 조회 우선순위

1. `lexicon_enriched`에서 A2 `sense_id` + 표제어 + 호환 품사가 정확히
   대응하는 항목
2. 의미번호가 없어도 후보들의 서로 다른 `pron_1`이 하나인 항목
3. enriched `pron_1`이 없을 때 같은 `urimal_id`의
   `lexicon_legacy_pron.pron_g2p`
4. 조사·어미처럼 여러 의미 후보가 있어도 서로 다른 발음이 하나뿐이면
   `unique_pron_across_senses`
5. 서로 다른 발음이 둘 이상이면 `multiple`
6. 항목이 없으면 `not_found`

`pron_2`는 대체 인정형으로 별도 보존한다. 대표 발음을 덮어쓰지 않는다.

기존 `predict_pron.py::build_lexicon_index()`처럼 가장 작은 `sense_no`를
자동 선택하는 방식은 최종 인프라에 사용하지 않는다.

### 4.3 표제어·품사 대응

- 용언 어간은 `word_stem`과 `-다` 표제어를 모두 조회하되 실제 사용 키를
  기록한다.
- 조사·어미는 Bareun–lexicon 품사 대응표를 별도 CSV로 버전 관리한다.
- 대응표가 없는 태그는 품사를 무시해 억지로 매치하지 않고
  `pos_crosswalk_missing`으로 남긴다.
- `sense_id`가 MFS 추정인 경우 `sense_method`와 `confidence`를 발음 조회
  결과에 함께 전파한다.

### 4.4 로마자

사전의 한글 `pron_1/pron_2/pron_g2p`를 프로젝트의 단일 `roman_mfa`
변환기로 다시 변환한다. 기존 lexicon roman과 새 `*_roman_mfa` 열은 감사용
대조에만 쓰고, 체계가 일치한다고 검증되기 전에는 그대로 복사하지 않는다.

## 5. 규칙 발음 엔진 보완

현재 `predict_pron.py`는 어절 철자 전체를 처리하므로 대표 발화의 `꼬체`,
`어때써`를 만들 수 있다. 다음 버전에서는 최종 문자열만 주지 말고 적용 사건을
함께 남긴다.

```text
rule_event_id, utt_id, eojeol_idx
rule_name, rule_version
input_span, output_span
left_morph_idx, right_morph_idx
boundary_scope
input_repr, output_repr
applied, blocked_reason
```

이 기록이 있어야 “왜 이 발음을 예상했는가”를 연구 방법에 설명하고, 특정
규칙을 끈 대조판을 재현할 수 있다.

형태소 표층 연결과 form이 일치하지 않는 활용·축약은 별도 상태로 둔다.
현재 코드도 음절 수가 다르면 일부 형태 경계 규칙을 보수적으로 건너뛰지만,
그 사실을 발화 수준 `align_warn` 한 칸에만 남기지 말고 해당 어절·경계 행에
기록해야 한다.

## 6. TextGrid vNext 제안

### 6.1 전량 운영 정본

전량 TextGrid는 가볍게 유지한다.

| 순서 | tier | 내용 | 출처 |
|---:|---|---|---|
| 1 | `words` | 표기 어절과 MFA 시간 | 신규 어절 MFA |
| 2 | `phones_mfa` | MFA/G2P phone과 시간 | MFA; 실제 실현 아님 |
| 3 | `utterance` | `form` | 원본 JSON/Bareun |

형태소·철자 로마자·사전/규칙 발음 검색의 정본은 CSV/Parquet이다. 전량
TextGrid 수백만 개에 같은 문자열을 중복하면 파일 크기, 열기 속도, 스키마
변경 비용이 커지므로 넣지 않는다.

현재 파일럿과 기존 도구가 쓰는 4-tier는 이번 대량 run 중에는 그대로
보존한다. 다음 정본 승격에서 3-tier로 이행하되, 기존 `phones`는 manifest에
`phones_mfa` 의미라고 명시하고 기존 `morphemes`는
`morph_tier_source=morphemes_legacy`로 기록한다. 호환성 검증 전에는 기존
tier를 삭제하거나 이름만 일괄 변경하지 않는다.

근거 없는 비례 분할로 `어떻/었/어`의 정확한 음향 경계를 만든 것처럼 보이게
해서는 안 된다. 융합 활용형은 어절 전체 구간과 `contracted_fused` 상태를
사용한다.

모든 IntervalTier는 `0–xmax`를 빈 interval까지 연속적으로 덮는다. 유표
발화 앞뒤의 빈 interval을 제거하지 않는다. 다만 원 발화가 0 또는 `xmax`에
붙은 운영본에는 근거 없는 빈 시간을 만들지 않는다. 가시적 양끝 경계는 아래
점검 사본 export에서 보장한다.

### 6.2 연구자 점검 사본

선택 후보의 기본 점검 사본은 다음 4-tier다. 점검 사본 WAV와 TextGrid는
원본을 수정하지 않고 좌우 0.05초 무음을 더한 시간축을 사용한다.

| tier | 내용 |
|---|---|
| `words` | MFA 어절 정렬 |
| `phones_mfa` | MFA/G2P 대략적 분절임을 이름에 명시 |
| `morph_analysis` | 현재 Bareun 형태소열을 어절 구간에 표시 |
| `utterance_info` | ID·form·철자 로마자·규칙 발음 한글/로마자 |

다음 tier는 기본본에 넣지 않고 현상별 분석 사본에만 온디맨드로 추가한다.

| 선택 tier | 내용 |
|---|---|
| `morphemes_legacy` | 구형 분절의 출처 비교가 필요한 경우 |
| `candidate` | 후보 어절 또는 경계와 `candidate_id` |
| `pron_dict` | 형태소 시간 매핑이 검증된 경우에만 독립형 사전 발음 |
| `prosody_koina` | KOINA 결과 |
| `human_judgment` | 연구자 판정; 자동 재생성에서 보호 |

형태소별 로마자·IPA·사전 대체 발음을 모두 TextGrid에 넣지 않는다.
CSV/Parquet을 정본으로 두고, 발화 수준의 철자·규칙 발음 로마자만
`utterance_info`에 넣는다.

`pron_dict`는 문맥 실제 발음처럼 보이지 않도록 예를 들어
`꽃{dict:꼳}`처럼 출처가 드러나는 라벨을 사용한다. 다중 발음은
`[multiple]`을 표시하고 하나를 임의 선택하지 않는다.

점검 CSV에는 다음 시간 provenance를 반드시 둔다.

```text
source_wav_duration_seconds
review_wav_duration_seconds
review_textgrid_duration_seconds
review_edge_padding_left_seconds
review_edge_padding_right_seconds
review_time_to_source
```

## 7. 검색 결과와 파일 묶음

연구자가 파일을 일일이 찾지 않도록 후보 추출 결과마다 다음 구조를 만든다.

```text
{phenomenon}_{run_id}/
  manifest.csv
  candidates.csv
  by_year/
    2022/
      SDRW2200000836.1.1.61.wav
      SDRW2200000836.1.1.61.TextGrid
      SDRW2200000836.1.1.61.utterance.csv
      SDRW2200000836.1.1.61.candidates.csv
  logs/
  checksums.csv
  README.md
```

같은 basename을 사용하고 `manifest.csv`에 원본 경로·사본 경로·크기·SHA256·
TextGrid 스키마·복사 검증 상태를 남긴다. 원본 D: 파일은 읽기만 한다.

## 8. 구현 순서와 승격 게이트

### 8.0 현재 상태 판정

#### CSV

기존 전량 search master는 17,156세션·5,103,356행의 ID·form·tagged가 A1과
완전히 일치하므로 삭제할 대상이 아니다. 그러나 다음이 빠진 **기준선 판본**이다.

- 복구된 2023 네 세션 메타
- dialogue/co-speaker 열의 전량 반영
- `pron_reference_*`
- enriched+legacy 결합 사전 발음
- WAV/TextGrid/quarantine coverage
- 정규화된 어절·형태소·경계 표

따라서 “CSV 전량 생성 완료”와 “연구용 최종 CSV 완료”를 구분한다. 기존본을
archive한 뒤 새 schema를 별도 staging에서 만들어야 한다.

#### MFA

- 층화 파일럿 60발화 MFA 자체는 수량·duration·tier QC를 통과했다.
- `phones`는 MFA/G2P 분절이며 실제 실현이 아니다.
- `morphemes`는 현재 Bareun과 1:1이 보장되지 않는 legacy 분절이다.
- 전량 정본 경로와 파일럿 run 경로가 분리돼 있어 `locate_utt.py`가 파일럿
  TextGrid를 자동 선택하지 않는다.
- 점검 v4에서 가시적 edge padding과 최소 4-tier·형태소 표시가 정돈됐다.

#### 원칙

CSV 언어층을 먼저 확정하고 MFA 시간층은 나중에 조인한다. 단, MFA 입력 사전의
변경은 CSV 사전 발음 열을 만든 것과 별도 실험으로 취급한다.

### 단계 0: 기준선 동결

- 관련 코드 SHA256과 git commit 기록
- 현재 search master·TextGrid 판본과 경로 기록
- 기존 산출물 수정 금지, 새 `run_id` staging 사용

### 단계 1: enriched+legacy lexicon 색인 파일럿

- 대표 발화와 수동 선정 예외·다의·조사·어미 표본
- enriched 664,596 무발음행의 `urimal_id` fallback 전수 검증
- 중복 제거 전후 행 수
- sense 정확 일치, 단일 발음, multiple, not_found 분포
- Bareun–lexicon 품사 대응표 검토
- 가장 작은 의미번호 임의 선택 0건

### 단계 2: 정규화 검색표 파일럿

- 기존 층화 파일럿 60개를 우선 사용
- `utterances`, `eojeol_tokens`, `morph_tokens`, `morph_boundaries`,
  `file_index` 생성
- 원본 발화 수·어절 수·형태소 수와 전수 대조
- `exact/contracted_fused/complex` 사례를 연구자가 확인

### 단계 3: TextGrid 연동 파일럿

- `words` 유표 구간과 `eojeol_idx` 1:1 대조
- 형태소 tier의 실제 의미와 원천 검사
- 모든 tier 0–xmax 연속성
- 점검 사본 모든 tier 좌우 0.05초 가시적 빈 interval
- review 시간을 source 시간으로 되돌리는 식 검증
- WAV/TextGrid duration, stem, speaker, session 일치
- 후보 tier와 `candidate_id` 왕복 조인

### 단계 4: 한 현상 end-to-end

- 구조화 환경 검색
- 후보 CSV 생성
- WAV·review TextGrid·발화 CSV 복사
- KOINA 결합
- 연구자 판정 시트 입력
- 판정표를 원 후보표와 재조인

### 단계 5: 연도별 확대

1. 2020 pre-MFA CSV 새 schema 파일럿
2. 2020 CSV archive→staging 전량 생성→전수 감사→승격
3. 2020 MFA 소표본
4. 2020 MFA 전량→post-MFA alignment index
5. 한 현상 end-to-end 연구자 판정
6. 2021부터 같은 게이트 반복

부분 성공은 성공으로 승격하지 않는다. CSV와 MFA는 각각 독립적인 완료 marker와
보고서를 갖고, 둘이 모두 통과한 연도만 analysis-ready view를 만든다.

## 9. 과거 오류·시행착오를 반영한 방지책

| 과거 문제 | 설계상 방지책 |
|---|---|
| 10개 중 TextGrid 9개인데 성공처럼 진행 | 기대 수·출력 수·실패 목록·종료코드를 함께 검사 |
| manifest의 발화가 corpus/CSV/TextGrid에서 안 보임 | `utt_id`를 각 입력에서 역조회하고 bundle 전 존재 검증 |
| 한 화자 표본으로 오인 | 선정 단계에서 화자 수·세션 수 최소조건과 manifest 고정 |
| Dropbox 복사 중단·원본 손상 우려 | D: 원본 읽기 전용, 사본 SHA256 대조 후 완료 표지 |
| 숫자 `1` 때문에 발음열 전체가 빈 값 | form/original_form 출처 폴백과 `unresolved_symbol`; 읽기 추측 금지 |
| original_form을 실제 발음 전사로 오해 | 원전사·규칙 발음·사전 발음·실현 판정을 별도 열로 분리 |
| MFA phones를 실제 판정값으로 오해 | `phones_mfa` 의미와 provenance를 manifest·README에 표시 |
| `morphemes` tier 이름이 실제 1:1 형태소를 과장 | legacy/verified 상태와 토큰 수 일치 검사 |
| 0–xmax coverage는 있지만 Praat에서 양끝 경계가 안 보임 | 점검 WAV 사본 좌우 0.05초 무음 + TextGrid 동시 이동 + source 환산식 |
| D:, 프로젝트, Dropbox 경로 혼재 | `paths.py` 단일 경로 설정 + 실행별 root snapshot |
| 사전 다의어에서 첫 의미를 임의 선택 | A2 sense 우선, 미해결 multiple 보존 |
| lexicon 중복 직접 조인으로 행 폭증 위험 | 사전 전용 dedup index 후 many-to-one 검증 |
| enriched lexicon의 `pron_g2p`가 전부 빈데 단독 사용 가정 | legacy 발음을 `urimal_id`로 보완하고 출처 기록 |

## 10. 확정 사항과 남은 결정

확정:

1. pre-MFA 언어 마스터와 post-MFA 시간 인덱스를 분리한다.
2. 기본 점검 사본은
   `words/phones_mfa/morph_analysis/utterance_info` 4-tier를 쓴다.
3. 점검 WAV/TextGrid 사본은 좌우 0.05초 padding과 원시간 환산식을 기록한다.
4. enriched 사전의 무발음행은 같은 `urimal_id`의 legacy G2P로 보완한다.
5. 기존 전량 CSV와 원 MFA/TextGrid는 자동 덮어쓰지 않는다.
6. 형태소·철자 기반 로마자 검색은 CSV/Parquet 정본에서 보장하고, 점검
   TextGrid에는 발화 수준 `ORTH_R`와 `RULE_R`만 중복한다.

남은 결정:

1. 전량 운영 TextGrid의 기존 `morphemes` 이름을 호환 유지할지, 다음 전량
   판본에서 `morphemes_legacy`로 이행할지
2. Bareun–lexicon 품사 대응표를 어느 범위까지 허용할지
3. `sense_method=ls_sxls/lex_first` 등 추정 의미를 사전 발음 대표 선택에
   허용할 신뢰도 기준
4. `contracted_fused` 형태소의 TextGrid 표시는 어절 전체 중첩 라벨로 할지,
   연구자 점검 사본에서만 표시할지
5. 첫 end-to-end 현상과 자동 후보 조건

현재 권고는 1–3단계 인프라를 먼저 파일럿하고, 현상별 탐지기는 그 위에 얹는
것이다. 이렇게 해야 ㄴ 삽입을 포함한 여러 음운 현상에 같은 파일·좌표·출처
체계를 재사용할 수 있다.
