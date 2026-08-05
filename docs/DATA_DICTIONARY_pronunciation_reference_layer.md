# 사전 발음 참조 레이어 열 사전

최종 갱신: 2026-08-05 KST

## 핵심 구분

| 정보 | 출처 | 의미 | 실제 실현·시간 정답 여부 |
|---|---|---|---|
| 철자·형태소 | 원 JSON, Bareun, `morph_search.v3` | 검색할 표면형·품사·위치 | 아님 |
| `pron_rule_*` | 표기와 규칙기 | 문맥을 반영한 예상 발음 | 아님 |
| `dict_*` | 우리말샘 `pron_1/2`, 명시된 legacy fallback | 표제어·품사·의미별 후보 | 아님 |
| `pron_mfa_*` | 공통 Jamo r2 강제정렬 | MFA 입력 phone의 시간 배치 | 실제 실현 판정 아님 |
| 연구자 판정 | WAV·TextGrid 직접 검토 | 연구 대상 현상의 실현 여부 | 별도 연구 단계 |

## `morph_dictionary_pron_occurrences.csv.gz`

한 행은 형태소 occurrence 하나다.

| 열 묶음 | 주요 열 | 용도 |
|---|---|---|
| 좌표 | `utt_id`, `year`, `eojeol_idx`, `morph_idx_in_eojeol`, `morph_idx_in_utterance` | WAV·TextGrid·다른 검색표와 결합 |
| 형태소 | `morph_surface`, `pos` | 표면형+품사 검색 |
| 사전 연결 | `candidate_group_id`, `dict_match_status`, `match_type` | 사전 후보 group 존재·불일치 이유 |
| 후보 규모 | `candidate_count`, `preferred_candidate_count`, `preferred_pronunciation_count` | 다의·복수 발음 모호성 필터 |
| 후보 성격 | `preferred_source_tier`, `pronunciation_resolution_status`, `sense_match_status` | 등재 발음과 legacy fallback 및 의미 미확정을 구별 |

이 표는 후보 문자열을 occurrence마다 복제하지 않는다. 후보 상세는 registry와
group/member 표에 `candidate_group_id`로 연결한다.

## `eojeol_pronunciation_compare.csv.gz`

한 행은 원 표기의 어절 하나다. `eojeol_idx`는 원 표기 좌표다.

| 열 묶음 | 주요 열 | 용도 |
|---|---|---|
| 좌표 계약 | `source_form_eojeol_count`, `morph_analysis_eojeol_count`, `linked_morph_eojeol_idx`, `morph_link_status` | 원 표기와 형태소 어절 분할 차이를 명시 |
| 표기·형태소 | `eojeol_form`, `eojeol_roman_v2`, `morph_tagged`, `morph_surfaces_pos_json` | 철자·Roman·형태소 조합 검색 |
| 사전 후보 | `morph_candidate_group_ids_json`, `morph_dict_*_json`, `dict_layer_status` | 한 어절 내 형태소별 1:N 사전 후보 보존 |
| 규칙 예상형 | `pron_rule_reference_form_eojeol`, `pron_rule_hangul`, `pron_rule_roman`, `pron_rule_*status` | 표기/기호 해결 및 규칙 예상 발음 검색 |
| MFA | `mfa_available`, `mfa_begin_seconds`, `mfa_end_seconds`, `mfa_word`, `pron_mfa_ipa`, `pron_mfa_r_auto` | 강제정렬 구간과 phone 확인 |
| 비교 flag | `rule_mfa_roman_compare_status`, `single_morph_dict_*`, `pron_audit_status`, `pron_audit_issue_codes` | 후속 검토 대상 선별; 정답 판정 아님 |

`*_json`은 형태소 순서와 1:N 후보를 한 셀에서 구조적으로 보존한다. 단순 문자열
검색보다 Python/R/DuckDB에서 JSON을 풀어 쓰는 것이 안전하다.

## `pron_reference_utterance.csv.gz`

한 행은 발화 하나다. TextGrid 7번째 tier label과 같은 근거를 가진다.

- `pron_reference_hangul/roman/source/status`: 발화 수준 규칙 예상형
- `dict_*_eojeol_count`: 사전 연결·모호·fallback·좌표 미연결 요약
- `rule_mfa_*_eojeol_count`: 규칙 예상형과 MFA phone 비교 요약
- `pron_audit_issue_codes`: 발화에 포함된 기술적 검토 flag
- `pron_reference_utt_label`: Praat에서 읽는 압축 표지
- `textgrid_label_schema_version`: label 해석 버전

## TextGrid `pron_reference_utt`

`utterance`와 정확히 같은 interval 경계를 갖는 발화 수준 검색·참조 tier다.
label에는 규칙 예상형과 사전/MFA 비교 요약만 넣는다. 사전 후보에 음소별 시간
경계를 만들지 않는다. 상세 후보·품사·의미·출처는 동반 CSV가 정본이다.
