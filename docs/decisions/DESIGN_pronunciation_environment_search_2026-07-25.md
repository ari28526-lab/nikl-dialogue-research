# 음운·형태 환경 검색과 CSV–WAV–TextGrid 연동 설계

작성일: 2026-07-25

상태: 구현 전 조사·설계안

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

정본 후보:

`D:\00_RAW\reference\00_DICTIONARY\01_NIKL_lexicon_full_v2.csv`

v2에는 `pron_1`, `pron_2`, `pron_g2p`와 각 MFA 로마자 열, 2023 발음,
우리말샘·표준국어대사전 대응 코드, 품사군, 의미번호가 함께 있다. v1보다
조회용 정보가 많으므로 새 색인은 v2를 우선 검증한다. v1은 원천 대조용으로
보존한다.

대표 결과:

- `꽃/NNG`의 독립형 `pron_1`은 `꼳`이다.
- `모양`은 의미에 따라 장음 표시가 달라질 수 있다. A2의 의미번호를 먼저
  적용해야 한다.
- `어떻`은 표제어 `어떻다/VA`의 어간 별칭으로 조회되며 `pron_1=어떠타`다.
- `에`는 Bareun에서 `JKB`지만 사전에는 주로 `JX`로 보인다.
- `었`은 Bareun에서 `EP`지만 사전 행은 `EF`로 보이는 경우가 있다.

즉 `(표층형, Bareun 품사)` 완전일치만 쓰면 조사·어미가 누락된다. 반대로
품사를 무시하면 동형이의 형태소가 잘못 결합될 수 있다. 검증된 품사 대응표와
조회 상태가 필요하다.

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

점검용 6-tier에는 `original_form`, `pron_reference`가 추가돼 있다.

문제:

- Bareun/A2는 문장부호까지 8형태소인데 `morphemes` tier는 5개 라벨이다.
- `어떻+었+어`가 `어땠어` 한 구간으로 합쳐져 있다.
- 이 tier는 기존 `06_textgrid_merged`의 `words`를 재사용한 것으로, 현재
  Bareun 형태소 토큰을 새로 정렬한 결과가 아니다.
- `phones`에서 `꽃에`가 대략 `k͈-o-n-e`로 정렬돼 규칙 기준 `꼬체`와도
  다르다. 실제 실현 또는 정답 발음으로 해석할 수 없다.

따라서 현재 `morphemes`라는 이름만 보고 A2 `morph_idx`와 1:1 대응한다고
가정하면 안 된다.

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

1. A2 `sense_id` + 표제어 + 호환 품사가 정확히 대응하는 항목
2. 의미번호가 없어도 후보들의 서로 다른 `pron_1`이 하나인 항목
3. `pron_1`이 없을 때 `pron_g2p`
4. 서로 다른 발음이 둘 이상이면 `multiple`
5. 항목이 없으면 `not_found`

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
| 2 | `phones` | MFA/G2P phone과 시간 | MFA; 실제 실현 아님 |
| 3 | `morphs_aligned` 또는 기존 `morphemes` | 검증된 범위의 형태소/구형 분절 | 출처·상태 필수 |
| 4 | `utterance` | `form` | 원본 JSON/Bareun |

기존 도구 호환 때문에 당장 `phones` 이름을 바꾸지 않더라도 manifest와 문서에는
`phones_mfa` 의미라고 명시한다.

현재 `morphemes` tier는 Bareun 8형태소와 일치하지 않을 수 있다. 다음 중 하나를
선택해야 한다.

1. 새 정본에서는 검증된 Bareun 형태소 경계를 만들고 `morphs_aligned`로 명명
2. 구형 경계를 유지할 때 `morphemes_legacy`로 명명
3. 호환 때문에 이름을 유지하면 파일별 `morph_tier_source`,
   `morph_tier_map_status`를 manifest에 반드시 기록

근거 없는 비례 분할로 `어떻/었/어`의 정확한 음향 경계를 만든 것처럼 보이게
해서는 안 된다. 융합 활용형은 어절 전체 구간과 `contracted_fused` 상태를
사용한다.

모든 IntervalTier는 `0–xmax`를 빈 interval까지 연속적으로 덮는다. 유표
발화 앞뒤의 빈 interval을 제거하지 않는다.

### 6.2 연구자 점검 사본

선택 후보에만 다음 tier를 온디맨드로 추가한다.

| tier | 내용 |
|---|---|
| `original_form` | 원전사 어절 |
| `pron_rule` | 어절별 규칙 예상 발음 |
| `candidate` | 후보 어절 또는 경계와 `candidate_id` |
| `pron_dict` | 형태소 시간 매핑이 검증된 경우에만 독립형 사전 발음 |
| `prosody_koina` | KOINA 결과 |
| `human_judgment` | 연구자 판정; 자동 재생성에서 보호 |

로마자·IPA·사전 대체 발음을 모두 전량 TextGrid에 넣지 않는다. CSV/Parquet을
정본으로 두고, 현재 검토에 필요한 열만 주입한다.

`pron_dict`는 문맥 실제 발음처럼 보이지 않도록 예를 들어
`꽃{dict:꼳}`처럼 출처가 드러나는 라벨을 사용한다. 다중 발음은
`[multiple]`을 표시하고 하나를 임의 선택하지 않는다.

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

### 단계 0: 기준선 동결

- 관련 코드 SHA256과 git commit 기록
- 현재 search master·TextGrid 판본과 경로 기록
- 기존 산출물 수정 금지, 새 `run_id` staging 사용

### 단계 1: lexicon v2 색인 파일럿

- 대표 발화와 수동 선정 예외·다의·조사·어미 표본
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

한 연도 파일럿 통과 후 해당 연도 전량, 전수 QC 통과 후 다음 연도로 간다.
부분 성공은 성공으로 승격하지 않는다.

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
| D:, 프로젝트, Dropbox 경로 혼재 | `paths.py` 단일 경로 설정 + 실행별 root snapshot |
| 사전 다의어에서 첫 의미를 임의 선택 | A2 sense 우선, 미해결 multiple 보존 |
| lexicon 중복 직접 조인으로 행 폭증 위험 | 사전 전용 dedup index 후 many-to-one 검증 |

## 10. 구현 전 확정할 결정

1. 운영 TextGrid의 기존 `morphemes`를 호환 유지할지,
   `morphemes_legacy`/`morphs_aligned`로 구분할지
2. Bareun–lexicon 품사 대응표를 어느 범위까지 허용할지
3. `sense_method=ls_sxls/lex_first` 등 추정 의미를 사전 발음 대표 선택에
   허용할 신뢰도 기준
4. `contracted_fused` 형태소의 TextGrid 표시는 어절 전체 중첩 라벨로 할지,
   연구자 점검 사본에서만 표시할지
5. 첫 end-to-end 현상과 자동 후보 조건

현재 권고는 1–3단계 인프라를 먼저 파일럿하고, 현상별 탐지기는 그 위에 얹는
것이다. 이렇게 해야 ㄴ 삽입을 포함한 여러 음운 현상에 같은 파일·좌표·출처
체계를 재사용할 수 있다.
