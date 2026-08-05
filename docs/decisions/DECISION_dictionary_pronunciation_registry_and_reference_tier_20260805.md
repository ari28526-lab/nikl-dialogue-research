# 사전 발음 registry·조인표·참조 tier 결정 — 2026-08-05

상태: **v2 registry 채택, 2020·2021 occurrence·비교표·발화 index 전수 검증, 2020 7-tier 구현 파일럿 통과**

## 1. 목적

현재 `common_pron_mfa_r2_20260728`은 2020–2025에 같은 MFA 입력 phone열을
공급하는 정렬용 공통사전이다. 우리말샘·표준국어대사전의 표준·예외·복수
발음을 모두 담은 언어학적 사전 정본이 아니다.

연구에서는 다음 값을 끝까지 분리한다.

| 값 | 의미 | 시간 경계 주장 |
|---|---|---|
| `dict_pron_*` | 표제어·품사·의미에 결속된 사전 독립형 발음 후보 | 없음 |
| `pron_reference_*` | 표기·형태 문맥에 필수 규칙을 적용한 예상형 | 없음 |
| `phones_mfa` | 공통사전의 phone열을 음성에 강제정렬한 구간 | MFA 자동 경계 |
| 연구자 실현 판정 | WAV·TextGrid를 보고 별도 판정한 값 | 연구자 증거 구간만 |

Jamo G2P는 일부 음운 패턴을 반영할 수 있지만 완전한 표준발음 규칙기가
아니다. `phones_mfa`를 규칙 발음이나 실제 실현으로 부르지 않는다.

## 2. 2026-08-05 실물 감사 결과

사전 발음 원자료는 다음 두 파일에 확보되어 있다.

- `D:\00_RAW\reference\00_DICTIONARY\01_NIKL_lexicon_full_v2.csv`
  - `pron_1`, `pron_2`, 우리말샘·표준국어대사전 ID와 의미·품사 정보
- `D:\00_RAW\reference\03_lexicon_1기\01_NIKL_lexicon_full.csv`
  - 위 판본의 빈 발음을 같은 `urimal_id`로 보완할 `pron_g2p`

그러나 현재 생산 CSV에는 사전 발음이 아직 배선되지 않았다.

- 동결 search master에는 `pron_pred_*`만 있고 `dict_pron_*`이 없다.
- `morph_search.v3` 7표에는 `pron_reference_*` 규칙 예상형과 형태소·위치
  정보가 있지만 `pron_1/2` 또는 사전 candidate ID가 없다.
- 2020·2021 post-MFA 4표에는 `pron_reference_*`, `pron_mfa_ipa`,
  `pron_mfa_r_auto`가 있지만 사전 발음 열·링크표가 없다.

따라서 현행 `pron_reference_*`가 사전 발음까지 포함한다고 기술하면 안 된다.

## 3. 효율적인 저장 구조

5,103,356개 발화에 긴 사전 문자열을 반복하지 않는다. type 정보와 occurrence
정보를 분리하고 결정적 ID로 조인한다.

### 3.1 `dictionary_pronunciation_registry`

행 단위는 **출처가 하나인 발음 후보 하나**다.

```text
dict_pron_candidate_id
headword, word_stem, pos_tag, pos_group, sense_no
urimal_id, stdict_target_code, stdict_sense_code
pron_hangul, pron_roman
variant_rank, source_name, source_field, source_version
is_primary, is_alternative, is_legacy_fallback
```

- `pron_1`과 `pron_2`를 각각 보존한다.
- enriched 판본에 발음이 없을 때만 같은 `urimal_id`의 legacy `pron_g2p`를
  보완 후보로 두고 출처를 숨기지 않는다.
- 문자열·품사·의미·출처가 같은 중복만 제거한다.
- candidate ID는 위 identity 필드의 canonical hash로 만든다.

### 3.2 `morph_dictionary_pron_links`

행 단위는 **형태소 occurrence와 사전 후보의 연결 하나**다.

```text
utt_id, year, eojeol_idx, morph_idx_in_eojeol
morph_surface, lemma, pos_bareun, sense_id
dict_pron_candidate_id
dict_match_status, dict_match_type, sense_match_status
```

우선순위는 의미·표제어·호환 품사의 정확 일치, 의미 미확정이지만 발음 후보가
유일한 경우, 복수 후보 보존 순이다. 복수 후보 중 하나를 자동으로 대표값으로
선택하지 않는다.

실자료 규모에서는 occurrence마다 1:N candidate 행을 폭발시키지 않는다. 다음
정규화 구조를 사용한다.

```text
dictionary_pronunciation_match_groups
  (morph_surface, corpus_pos) -> candidate_group_id + 후보 수·해결 상태

dictionary_pronunciation_match_group_members
  candidate_group_id -> dict_pron_candidate_id + preferred/retained_fallback

morph_dictionary_pron_occurrences
  utt_id + 형태소 위치 -> candidate_group_id + match status
```

용언은 `word_stem + 정확 품사`, 그 밖의 품사는 `headword + 정확 품사`로
그룹화한다. 사전 품사가 없는 388,405후보는 삭제하지 않고 registry에 보존하되
자동 occurrence 조인에서는 제외한다. 등재 후보가 하나라도 있으면 legacy
fallback은 `retained_fallback`으로 남기고 대표 후보 경쟁에서는 제외한다.

### 3.3 `eojeol_pronunciation_compare`

연구자가 바로 필터·조인할 수 있는 occurrence 비교표를 별도로 만든다.

```text
utt_id, year, eojeol_idx, eojeol_form, morph_analysis
pron_rule_hangul, pron_rule_roman, pron_rule_status
dict_pron_candidate_ids, dict_match_status
pron_mfa_ipa, pron_mfa_r_auto
pron_audit_status, pron_audit_issue_codes
```

정본은 작은 registry와 link 표다. 비교표는 재생성 가능한 view이며, 교환용
`csv.gz`와 분석용 Parquet/DuckDB view를 함께 제공한다.

## 4. TextGrid 7번째 tier

기존 6-tier를 원본으로 보존하고 다음 발화 수준 파생 tier를 추가한다.

```text
pron_reference_utt
```

예시:

```text
[RULE_H] 읻짜나
[RULE_R] I t _ JJ A _ N A
[SOURCE] standard_rule_prediction
[DICT_STATUS] linked_unique | multiple | not_found
```

- 유표 span은 `utterance`와 같은 첫 lexical word 시작–마지막 lexical word
  끝이다.
- 사전 발음에는 음향 시간이 없으므로 음소별 가짜 경계를 만들지 않는다.
- 1:N 사전 후보의 실제 문자열·의미·출처는 동반표에서 확인한다.
- `multiple`을 임의로 한 값으로 축약하지 않는다.

최종 7-tier 순서는 다음과 같다.

1. `words`
2. `phones_mfa`
3. `phoneme_r_auto`
4. `utterance`
5. `utterance_orth_r`
6. `morph_analysis_utt`
7. `pron_reference_utt`

## 5. 공통발음열 감사와 기존 연도 처리

1. 현재 공통사전·모델·규칙기·사전 원자료 SHA를 먼저 동결한다.
2. Jamo G2P phone을 사전 발음·문맥 규칙 예상형과 전수 비교한다.
3. 단순 표기 차이, 해석 경고, 경계 위험, 모호 후보를 분리한다.
4. 후보를 2020·2021의 `utt_id + eojeol_idx` occurrence에 조인한다.
5. 기존 2020·2021 MFA·DB·6-tier 정본은 감사만으로 무효화하거나
   덮어쓰지 않는다.
6. 7번째 tier와 사전 조인표는 MFA 재실행 없이 파생 backfill한다.
7. 실제 경계 문제까지 확인된 소수 발화만 별도 국소 shard에서 재정렬하고
   기존 결과와 병렬 보존한다.
8. 사전 발음을 공통 MFA 사전에 자동 변이로 넣지 않는다. 전역 변경은 빈도·
   occurrence·경계 영향 감사와 새 생산 계약을 거친 뒤에만 가능하다.

## 6. wav2vec2의 위치

wav2vec2 phone 후보는 전수 사전 감사의 기준이 아니다. 사전·규칙·Jamo G2P의
차이가 크고 빈도가 높은 선택 occurrence에만 음향 교차검증으로 사용하며,
`phones_mfa`나 사전·연구자 판정 열을 덮어쓰지 않는다.

## 7. 구현·실행 경계

- 생성기:
  `scripts/python/build_dictionary_pronunciation_registry.py`
- Windows PowerShell 5.1 실행기:
  `scripts/build_dictionary_pronunciation_registry.ps1`
- 출력 root:
  `D:\10_LAYERS\10_pronunciation_reference`
- 채택 예정 release:
  `dictionary_pron_registry_v2_20260805`

2026-08-05 실자료 `-PreflightOnly`는 enriched 46열, legacy 27열과 기존
SHA-256 감사 fingerprint의 경로·크기·수정시각 일치를 확인했다. preflight는
D:에 산출물을 만들지 않았다.

registry는 `pron_1`, `pron_2`, 빈 등재 발음의 legacy `pron_g2p` fallback을
long 형식으로 저장한다. source record 순서와 무관한 semantic hash ID를 쓰고,
동일한 의미·출처 후보만 중복 제거한다. gzip CSV와 manifest는 완전히 닫아
검증 가능한 상태가 된 뒤 최종 이름으로 승격하며 기존 release를 덮어쓰지 않는다.

### 7.1 Roman 열 분리

최초 `dictionary_pron_registry_v1_20260805` 실물은 1,192,729행, gzip 전수 읽기,
SHA 재계산, 출처 flag 검증을 통과했다. 그러나 독립 표본 감사에서 enriched의
Roman-MFA와 legacy `pron_g2p_roman` 구형 convention이 같은
`pron_roman_mfa` 열에 들어간 것을 발견했다. 발음·출처 후보 자체의 오류는
아니지만 조합검색에서 같은 체계로 오해할 수 있으므로 v1은 채택하지 않는다.

v2는 다음을 분리한다.

```text
pron_roman_source       원자료 Roman 문자열
pron_roman_source_mfa   원자료에 실제로 존재할 때만 보존한 기존 Roman-MFA
pron_roman_search       pron_hangul을 현재 roman_mfa.v1로 동일 변환
roman_search_system_version
```

따라서 구형 표기를 버리거나 고쳐 쓰지 않으면서도 검색에는 한 체계만 사용한다.
v1은 덮어쓰지 않고 비채택 검증 근거로 보존한다.

2026-08-05 v2 실물은 1,192,729행을 gzip으로 끝까지 다시 읽었고, 출력 SHA,
필수 열, 사전/fallback flag, 모든 현대 한글 발음의 `roman_mfa.v1` 검색열을
독립 검증했다. 오류와 partial은 0이다. v2는 **사전 참조·검색용 registry**로
채택하며 공통 MFA 입력사전으로 채택한 것은 아니다.

### 7.2 형태소·품사 match index 검증

v2에서 804,324후보를 564,385개 `(형태소 표면형, 품사)` 그룹으로 정규화했다.
group/member gzip 전수 읽기와 SHA를 확인했고 중복 key·고아 member·후보 중복·
우선순위 오류·partial은 모두 0이다. 2020 첫 5,000형태소 pilot은 입력과 출력이
1:1이며 3,866건이 정확 표면형+품사로 연결됐다. 불일치·미등재·문장부호·비표준
표면형은 서로 다른 상태로 보존했다.

## 8. 왜 2020 생산 검토 때 이 층을 잡지 못했는가

2020 Gate B의 검토 대상은 다음이었다.

- 공통 Jamo r2 phone 기준과 MFA 계산의 완주 여부
- WAV–LAB–DB–TextGrid 발화 동일성
- 6개 tier의 시간 경계·연속성·검색 정보 가독성
- 제외 발화와 미정렬 발화의 정확한 회계

당시 `pron_reference_*`는 표기와 규칙기에서 만든 예상형이었고, 우리말샘
`pron_1/2` 후보를 형태소의 표면형·표제어·품사·의미에 연결하는 occurrence
계약은 아직 없었다. 따라서 연구자가 2020 표본을 잘못 보거나 검토를 누락해서가
아니라, **검토표에 사전 후보가 아직 배선되지 않은 설계 공백**이었다. 2021 표본의
`있잖아`에서 `phones_mfa`와 규칙 예상형·사전 후보의 역할 차이가 눈에 띄면서 이
공백이 확인됐다.

이후 보완은 2021 예외처리로 두지 않는다. 2020–2025 모두
`config/pronunciation_reference_layer_v1.json`의 같은 schema·좌표·출처 계약을
사용한다. 기존 2020 정렬 검토의 효력은 유지하고, 새 참조층만 파생 backfill한다.

## 9. 전수 산출과 좌표 계약

2020·2021 morphology occurrence를 각각 5,767,506행과 12,015,453행으로
1:1 생성했고, 독립 동시 전수 스캔에서 identity·link state·manifest SHA·partial
오류가 모두 0이었다.

최초 비교표 파일럿은 형태소 분석 어절을 중심 좌표로 삼았다. 그러나
`그래가지고`처럼 원 표기 어절 1개가 형태소 분석 어절 2개가 되는 경우 규칙 예상형과
MFA 어절을 잃을 수 있었다. 이 파일럿은 비채택 근거로 보존하고, 생산 v2는 다음처럼
고쳤다.

- 1행 단위는 `orth_eojeol_tokens`의 **원 표기 어절**이다.
- 규칙 예상형과 MFA word/phone 비교는 원 표기 좌표에서 계속 보존한다.
- 형태소 사전 후보는 `linked_morph_eojeol_idx`가 명시될 때만 결합한다.
- 어절 수가 다르면 후보를 추측해서 붙이지 않고 `morph_coordinate_not_linked`로
  기록한다. 후보 원문은 occurrence 표에서 사라지지 않는다.

2020 생산 비교표 v2는 원 표기 어절 3,042,451행, 2021은 6,610,698행이다.
각각의 발화 index는 870,437행과 1,373,920행이다. 두 연도 모두 독립 전수
감사에서 좌표·구조화 JSON·규칙/MFA 재계산·SHA·partial 오류가 0이었다. 차이
flag는 오류나 실현 판정이 아니라 후속 검토 대상을 기술하는 값이다.

## 10. 7번째 tier와 재개 단위 검증

`pron_reference_utt`는 기존 6-tier를 복사한 새 파생 root에만 추가한다.
`utterance` tier의 interval 경계를 정확히 재사용하며, 사전 후보에 음소별 가짜
시간을 부여하지 않는다. 상세 1:N 후보는 CSV가 정본이다.

2020 실제 2세션 914개 TextGrid 파일럿에서 다음을 독립 전수 확인했다.

- 기존 6개 tier의 시간·라벨 변경: 0
- 7번째 tier 순서·0–xmax 연속성·`utterance` 경계 일치: 914/914
- 발화 label과 동반표 불일치: 0
- partial: 0

TextGrid backfill은 세션별 임시 폴더→검증→승격→checkpoint 순서다. 중단되면
완료 세션은 건너뛰고 실패 세션만 다시 만든다. `--max-sessions N`은 재실행마다
N개를 더 만드는 뜻이 아니라 연도 첫 N세션이라는 안정된 파일럿 범위다.

실행기는 `scripts/run_pronunciation_reference_year.ps1` 하나이며 `Tables`,
`Pilot`, `Full` 모드를 제공한다. 2022–2025도 당해 `morph_search.v3`와 6-tier
동반표 manifest가 성공한 뒤 동일 실행기를 사용한다.

## 11. 정리·보관과 다음 단계

채택되지 않은 registry v1과 좌표 설계 중 폐기된 1,000발화 비교 파일럿 2종은
현재 생산 root에서 제거하기 전에 다음 읽기 전용 archive로 검증 보관했다.

```text
E:\READ_ONLY_ARCHIVE\2026_summer_research\pronunciation_reference_pre_adoption_20260805\
  pronunciation_reference_pre_adoption_20260805.7z
```

6개 파일, 84,513,545바이트를 SHA-256 목록화했고 7-Zip 무결성 검사를 통과한
뒤 정확히 세 구경로만 D:에서 제거했다. 채택된 v2 registry, 2020·2021 전수표,
2020 7-tier 파일럿, 기존 MFA·6-tier는 정리 대상이 아니었다. 복구 근거는
`outputs/reports/ARCHIVE_pronunciation_reference_pre_adoption_20260805.json`이다.

다음 순서는 다음과 같이 동결한다.

1. 이 결정문·RUNBOOK·자산 대장·검증 보고서를 Git에 커밋·푸시한다.
2. 같은 코드·계약의 2020 구현 파일럿을 다시 반복하지 않는다.
3. 2021 7-tier를 세션 checkpoint 방식으로 전수 파생하고 독립 검증한다.
4. 2021 인프라 Gate의 남은 연구자 확인을 끝낸 뒤에만 2022 MFA preflight로
   넘어간다.
5. 2022–2025의 발음 참조표는 각 연도 6-tier가 완료된 후 같은 실행기로 만든다.
