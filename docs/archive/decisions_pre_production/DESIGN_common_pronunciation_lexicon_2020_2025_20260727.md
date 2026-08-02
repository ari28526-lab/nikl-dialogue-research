# 2020–2025 공통 발음 자원·MFA 사전 설계 (r2 이전 역사 기록)

작성일: 2026-07-27  
상태: **방향 채택, 구현·우선순위는 전수 자원 감사와 A/B 파일럿 뒤 동결**

> 2026-07-28 A/B 수동 검토에서 표면형 exact-word 방식이 `수가/NNG`의
> `수까`를 실제 `수/NNB+가/JKS` occurrence에 잘못 적용할 수 있음이
> 확인되었다. 생산 설계와 승격 기준은 형태소 결합 및 어절 type/occurrence
> 분리를 반영한
> `DECISION_common_pronunciation_resource_v2_20260728.md`를 정본으로 삼는다.

2026-07-28 구현 착수:

- 6개년 동결 5,103,356행에서 881,237개 고유 MFA 어절을 전수 확정
- enriched 1,165,157행·legacy 1,296,777행 원천 전수 감사
- 상세 실측과 폴더·용량·phone 체계 gate는
  `PILOT_common_pronunciation_full_corpus_20260728.md` 참조

관련 문서:

- `DESIGN_pronunciation_environment_search_2026-07-25.md`
- `DESIGN_search_master_layer.md`
- `RUNBOOK_pre_MFA_bulk_safe_2026-07-25.md`
- `MONITOR_2021_pre_mfa_v1_20260727.md`
- `PLAN_2022_improved_MFA_after_2020_2021.md`

## 1. 결정

2020–2025를 연도마다 별도의 inline G2P로 처리하지 않고, 여섯 연도의 동결
어휘를 한데 모아 다음을 함께 버전 관리하는 **공통 발음 자원**을 만든다.

- MFA 기본 사전의 기존 발음
- 정확한 버전과 fingerprint가 고정된 G2P 결과
- 우리말샘·표준국어대사전 연계 어휘목록의 `pron_1`, `pron_2`
- 기존 어휘목록의 `pron_g2p`
- 한글 발음→MFA phone 변환 규칙과 판본
- 후보 선택·제외·중복 제거 정책
- 각 발음의 출처, 사전 ID, 품사·의미, 자원 판본, 생성 코드 commit

이는 단순 속도 cache가 아니라 6개년 정렬의 입력을 같은 기준으로 고정하는
방법론적 자원이다. 다만 사전 발음, 규칙 예상 발음, G2P 결과, MFA phones,
연구자의 실제 실현 판정은 서로 다른 층으로 끝까지 분리한다.

현재 2021 실행은 중단하지 않는다. 진행 중인 G2P는 전체 함수가 반환되기
전까지 DB에 부분 사전으로 안전하게 commit되지 않으며, 현재 입력계약에는
사전·G2P·음향모델 fingerprint도 없다. 2021 완주본은 버릴 결과가 아니라
공통 자원의 발음 후보를 회수하고 새 사전과 비교할 **baseline v0**이다.

공통 자원을 채택해 MFA의 허용 발음 집합이 달라지면 2020·2021 재정렬을
꺼리지 않는다. 오히려 6개년 비교 가능성을 위해 같은 사전 release로 다시
정렬하는 편이 방법론적으로 낫다. 단, 기존 결과와 DB를 덮어쓰지 않고 새
`run_id`와 staging으로 재처리한다.

## 2. 하나의 파일이 아니라 세 산출물

“공통 발음사전”을 MFA용 `.dict` 한 파일로 바로 만들면 의미·출처·발음 변이가
사라진다. 정본과 파생물을 다음처럼 분리한다.

```text
pronunciation_registry
    ├── pre_mfa_pronunciation_index
    └── mfa_alignment_lexicon
```

### 2.1 `pronunciation_registry`: 출처 보존 정본

표제어·표층형·품사·의미별 모든 발음 후보와 출처를 long format으로 보존한다.
어떤 후보도 우선순위 적용 전에 덮어쓰거나 삭제하지 않는다.

최소 필드:

```text
entry_id, normalized_form, headword, word_stem
pos_bareun, pos_lexicon, pos_crosswalk_version
sense_id, sense_method, urimal_id, stdict_target_code
pron_hangul, pron_phones_mfa
pron_source_type, pron_source_field, source_release, source_retrieved_at
is_dictionary_attested, is_machine_generated, variant_rank
hangul_to_phone_version, source_row_fingerprint
selection_status, exclusion_reason
```

### 2.2 `pre_mfa_pronunciation_index`: CSV 검색용

발화·어절·형태소 occurrence에 정본 후보를 조인한다. 다음은 한 칸으로 합치지
않고 병렬 열 또는 별도 정규화 표로 둔다.

- 철자와 형태소별 철자 로마자
- 사전 독립형 대표·대체 발음과 출처
- 규칙 기반 문맥 예상 발음과 적용 규칙
- G2P 후보와 G2P 판본
- 다의·품사 불일치·미조회 상태

이 표에는 MFA 시간경계가 없고, 실제 실현값도 없다.

### 2.3 `mfa_alignment_lexicon`: 정렬용 파생 사전

`pronunciation_registry`에서 명시적 선택 정책을 적용해 만든 MFA 호환
`word phones...` 사전이다. 같은 단어의 복수 발음은 여러 줄로 보존할 수
있다. 이 파일에는 다음 manifest가 동반돼야 한다.

- 전체 파일 SHA256과 행 수·고유 단어 수·복수 발음 단어 수
- 기본 MFA 사전과 acoustic/G2P model fingerprint
- MFA·Python·Pynini 판본
- 발음 후보 선택 정책과 parameter
- 한글→phone 변환표 hash
- 입력 6개년 vocabulary fingerprint
- 생성 코드 git commit과 실행 `run_id`

## 3. 발음 출처를 혼동하지 않는 규칙

| 자원 | 역할 | 주의 |
|---|---|---|
| `korean_mfa.dict` | 현재 정렬 기준의 기본 발음 | 모델 파일과 실제 압축·해제본 hash를 모두 기록 |
| `lexicon_enriched.pron_1/2` | 사전 등재 대표·대체 발음 | 품사·의미·사전 ID를 보존; 예외 발음 근거 |
| `lexicon_legacy_pron.pron_g2p` | 과거 생성된 G2P 보완값 | 우리말샘 등재 발음이라고 부르지 않음 |
| 현재 `korean_mfa` G2P | residual OOV의 기계 생성 후보 | 모델·parameter·top-N·코드 판본 고정 |
| 규칙 발음 엔진 | 발화 문맥의 검색용 예상형 | 사전 독립형 발음을 단순 연결해 대체하지 않음 |
| MFA `phones` | 음성에 정렬된 대략적 분절 | 실제 음운현상 실현 판정값이 아님 |
| 연구자 판정 | 음성·TextGrid 직접 검토 결과 | 별도 annotation 정본 |

특히 `pron_g2p`라는 열 이름만 보고 사전 등재 발음으로 분류하지 않는다.
`pron_1/2`도 자원 생성 과정과 판본을 확인한 뒤에만
`is_dictionary_attested=true`로 둔다.

## 4. 후보 선택 정책: “한 발음으로 덮어쓰기” 금지

최종 우선순위는 자원 전수 감사와 파일럿 전에 고정하지 않는다. 먼저 다음
두 정책을 비교한다.

### 정책 A: 현재 동등 baseline

- 기존 `korean_mfa.dict` 발음 유지
- 사전에 없는 6개년 공통 OOV에 현재와 동일한 G2P 결과를 미리 cache
- inline G2P와 단어별 phone 후보가 완전히 같은지 전수 대조

이는 속도와 재현성만 바꾸고 정렬의 언어학적 입력은 바꾸지 않는 대조군이다.

### 정책 B: 사전 예외·변이 포함

- 정확히 매치된 `pron_1`과 검증된 `pron_2`를 발음 후보로 보존
- 기본 MFA 사전의 기존 변이와의 합집합·대체 정책을 각각 계측
- 사전 근거가 없는 항목에만 고정 G2P를 fallback으로 사용
- 다의어인데 의미를 확정할 수 없으면 가장 작은 의미번호를 임의 선택하지 않고
  서로 다른 후보 집합 또는 `ambiguous` 상태를 유지
- 품사 대응표가 없으면 품사를 무시해 억지로 결합하지 않음
- 조사·어미·용언 어간은 검증된 별칭·품사 crosswalk만 사용

복수 발음을 무제한으로 넣으면 aligner가 과도한 선택지를 갖게 될 수 있다.
따라서 후보 수, 중복, 사전 간 충돌, 음절·phone 길이 이상치를 계측하고
상한이 필요하면 근거와 제외 목록을 남긴다.

MFA 사전은 표층 word token을 키로 하므로, 같은 철자에 의미별 발음이 다른
경우 occurrence의 의미번호를 직접 조건으로 쓰지 못한다. lab token을
임의로 sense-decorate하지 않고, 우선 복수 변이와 search CSV의 의미별 근거를
분리한다.

## 5. 공통 vocabulary와 버전 계약

공통 vocabulary는 2020–2025 동결 `pron_reference_form`의 MFA tokenizer
출력을 합쳐 만든다. 다음을 별도 집계한다.

- 연도별·전체 고유 token 수와 연도 간 중복률
- 기본 사전 in-vocabulary / OOV
- 숫자·기호·라틴문자·비정상 Unicode·매우 긴 token
- 원전사 회복·미해결 기호 상태
- Bareun 형태소·품사·sense와 연결 가능한 비율
- 사전 발음 0/1/복수 후보 분포

정렬 입력계약은 기존 CSV·lab 계약에 다음을 반드시 더한다.

```text
mfa_version
acoustic_model_sha256
base_dictionary_sha256
g2p_model_sha256
g2p_parameters
pronunciation_registry_release
mfa_alignment_lexicon_sha256
hangul_to_phone_mapping_sha256
tokenizer_and_normalization_version
```

이 중 하나라도 달라지면 기존 temp DB를 그대로 resume하지 않는다. 기존 temp와
DB를 archive하고 새 계약으로 clean 실행한다.

release는 의미가 드러나는 별도 이름을 쓴다. 과거 파일명 `v1/v2`와 섞이는
`lexicon_v1` 같은 이름 대신 예를 들어
`common_pron_r1_20260727`처럼 manifest가 가리키는 release ID를 사용한다.

## 6. A/B 파일럿과 채택 gate

기존 연도별 층화 60발화만으로는 예외 발음이 충분하지 않을 수 있다. 다음 두
표본을 합친다.

1. 기존 6개년·5화자 층화 표본
2. 사전–G2P 불일치, `pron_2`, 다의·품사 충돌, 조사·어미, 숫자·기호,
   장단 token을 의도적으로 포함한 발음 stress 표본

정책 A와 B를 같은 WAV·lab·음향모델·MFA 판본으로 정렬해 다음을 비교한다.

- residual OOV와 G2P 호출 수·시간
- align exit, 입력/출력 수, 누락·부분 성공
- `spn` 수와 비율
- phone set 밖 기호 0건
- 무효 interval, gap/overlap, WAV duration 불일치 0건
- word/phone 경계 이동의 분포와 극단치
- 사전 예외 표본의 사람 청취·TextGrid 점검
- 같은 release 재생성 시 사전·manifest hash 완전 동일
- baseline 대비 전체 벽시계 시간과 peak temp

“`spn`이 줄었다” 또는 “로그우도가 좋아졌다” 하나만으로 정책 B를 채택하지
않는다. 연구자가 예외·충돌·경계 극단치 표본을 확인하고, 정렬 성공률과
재현성도 함께 통과해야 한다.

## 7. 전량 적용과 2020·2021 재실행 정책

1. 현재 2021 baseline v0를 끝까지 완료하고 독립 전수 QC한다.
2. 2020·2021 DB와 실제 word–pronunciation을 읽기 전용으로 추출해 baseline
   후보표와 비교 기준으로 보존한다.
3. 6개년 공통 vocabulary·자원 출처·충돌을 전수 감사한다.
4. 정책 A/B 사전과 manifest를 만들고 파일럿한다.
5. 정책 B를 공통 정본으로 채택하면 2022를 기존 inline 방식으로 먼저 돌리지
   않는다.
6. 새 release로 2020·2021을 먼저 재정렬·전수 QC해 baseline과 차이를
   설명한 뒤, 같은 release로 2022–2025를 순차 실행한다.

재실행은 실패의 인정이 아니라 정렬 입력을 6개년에 통일하기 위한 판본
갱신이다. 기존 `pre_mfa_v1` CSV, SQLite DB, TextGrid, marker, 보고서는
baseline archive로 보존하고 새 결과와 혼합하지 않는다.

공통 release가 정책 A처럼 현재 phone 후보와 완전히 동일한 cache에 그친다면
2020·2021 정렬 재실행은 계산상 필요하지 않다. 그러나 정책 B처럼 예외·대체
발음 후보가 실제로 달라지면 6개년 비교 가능성을 위해 재정렬하는 것을 기본
권고로 한다.

## 8. 연구 해석의 경계

공통 사전은 정렬 입력의 재현성과 분절 보조 품질을 높이기 위한 것이다.
ㄴ 삽입 등 실제 실현 여부를 자동 판정하는 gold가 아니다.

```text
공통 발음 자원
    → 동일 기준 MFA 정렬
    → CSV 후보 검색 + WAV/TextGrid/KOINA 수집
    → 연구자 직접 청취·분절 확인
    → 별도 실제 실현 annotation
```

따라서 search CSV에는 사전·규칙·G2P 출처를 보존하고, post-MFA 표에는
정렬된 phones와 시간만 붙이며, 사람 판정값은 자동 재생성 코드가 덮어쓰지
못하는 별도 정본에 둔다.

## 9. 구현 전 열어 둔 질문

1. `pron_1/2`와 2023판 발음 필드 각각의 생성 출처·판본·라이선스
2. 기본 MFA 변이와 사전 변이가 충돌할 때 합집합·대체 중 어느 정책이
   정렬 안정성이 높은지
3. 다의어 발음 변이를 MFA word-level 사전에 어느 범위까지 허용할지
4. 장음·방언·비표준·옛말 표지를 정렬용 발음에서 제외할 기준
5. 한글 발음의 장음·경계 표지를 MFA phone set으로 변환하는 규칙
6. G2P top-N과 확률 threshold를 한 개로 고정할지 복수 후보로 둘지
7. 공통 vocabulary에 원전사 미해결 숫자·기호를 포함/격리하는 정책
8. 검색용 규칙 발음 엔진의 `-히-` 구개음화·겹받침+ㅎ 규칙을 어느
   `rule_version`에서 교정하고 사전 예외와 어떤 순서로 결합할지

이 질문은 코드가 임의로 결정하지 않는다. 전수 분포와 대표 예를 보고
방법론 결정표에 답을 기록한 뒤 release를 동결한다.

## 10. 규칙 발음 기준선의 확정된 결손

외부 리뷰 뒤 현재 환경에서 `predict_pron.py`를 다시 실행해 다음을 재현했다.

```text
굳히다 → 구티다
닫히다 → 다티다
묻히다 → 무티다
앉히다 → 안히다
넓히다 → 널히다
밝히다 → 박히다
읽히다 → 익히다
```

현재 selftest 30/30은 통과하지만 이 부류가 시험표에 없기 때문에 결손을
검출하지 못한다. 원인은 ㄷ+히에서 격음화가 먼저 적용돼 뒤의 구개음화 환경이
사라지고, ㄵ·ㄼ·ㄺ+ㅎ의 격음화가 구현되지 않은 데 있다.

이 값은 검색 후보의 규칙 기반 기준선 오류이며 MFA의 한글 lab이나 사람의
실현 판정값은 아니다. 따라서 진행 중인 2021 MFA를 다시 시작할 사유는
아니다. 수정할 때는 다음을 한 변경 단위로 묶는다.

1. 새 `rule_version`을 부여한다.
2. 위 7개와 `좋다/많다/싫어` 대조군을 회귀표에 추가한다.
3. 기존 6개년 검색 CSV를 조용히 덮어쓰지 않고 새 staging에 재생성한다.
4. 우리말샘 `pron_1/2` 예외와 규칙 예측을 별도 출처 열로 유지한다.
5. 변경 전후 후보 수·현상별 검색 결과 차이를 보고서로 남긴다.
