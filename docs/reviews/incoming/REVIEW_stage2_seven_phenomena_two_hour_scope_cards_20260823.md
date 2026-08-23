# 일곱 형태음운 현상 — 현상당 2시간 연구 파일럿 범위 카드

- 작성일: 2026-08-23 KST
- 상태: `candidate_pending_researcher_adoption`
- 총 연구자 시간: 현상당 120분 × 7 = 840분(14시간)
- 표본 목표: 현상당 12개(중심 10, 주변·탐색 최대 2; 2020–2025 연도당 최대 2)
- 정지선: 이 문서는 query 동결·실현 판정·Praat 수정을 수행하지 않는다.

## 먼저 읽는 법

각 현상에서 `중심 모집단`을 먼저 보고, `주변·탐색`은 최대 2개만 본다. 같은 형태소 조합과 단어를 붙여 보는 순서와 지각 편향을 확인하기 위한 결정적 혼합 순서를 모두 준비한다. `불명`은 삭제가 아니라 보존 상태다.

## 공통 120분 시간표

| 단계 | 시간 | 활동 |
|---|---:|---|
| 문헌 | 20분 | 핵심 주장·근거 한계 읽기 |
| 범위 | 10분 | 중심/주변/탐색/범위 밖 확인 |
| 사례 | 60분 | 중심 10개 + 주변·탐색 최대 2개 |
| 재확인 | 20분 | 불확실·경계 사례와 향후 Praat 필요 표시 |
| 정리 | 10분 | 잠정 패턴·질문·JSONL 저장 |

## 준비 상태 요약

| 코드 | 현상 | 문헌 수준 | 시작 query 상태 | 현재 막힘 |
|---|---|---|---|---|
| PT | 합성어 경음화(사잇소리 관련 포함) | `core_papers_extracted` | `draft_pv_only` | 합성어성 판별과 자동 경음화 제외 probe 필요 |
| NAN | ㄴ 앞 비음화 | `core_papers_extracted` | `draft_pv_only` | ㅁ 앞 범위와 어절 간 층의 probe 필요 |
| NAL | ㄹ 앞 비음화 | `core_papers_extracted` | `draft_pv_only` | NAL·LLN 경계와 외래어 층 probe 필요 |
| NI | ㄴ삽입 | `pilot_full` | `frozen_v1_requires_scope_correction` | VCP overt 이 제외와 표면 요 보존을 구현한 v2 후보 probe 필요 |
| LLN | ㄴㄹ·ㄹㄴ 연쇄(유음화·비음화 복합형) | `core_papers_extracted` | `draft_pv_only` | 방향별 층화와 NAL 배제 probe 필요 |
| VH | 모음조화 | `core_papers_extracted` | `draft_pv_only` | 표면형·표제어형 대응과 VH/HIA membership probe 필요 |
| HIA | 모음충돌 회피 | `core_papers_extracted` | `draft_pv_only` | 회피 전략별 판정 가능성과 VH 중복 probe 필요 |

## PT — 합성어 경음화(사잇소리 관련 포함)

합성어 또는 그에 준하는 형태론적 경계 뒤의 평장애음이 경음으로 실현될 수 있는 변이를 다룬다. 단순한 장애음 뒤 자동 경음화와 분리한다.

- definition: `phenomena/_draft/PT/definition.md`
- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/PT_현상종합_초안_20260823.md`
- 근거: `CLM-0022`, `CLM-0023`, `CLM-0027`, `CLM-0029`, `CLM-0035`, `CLM-0037`, `CLM-0040`, `CLM-0041`, `CLM-0043`, `CLM-0052`, `CLM-0059`, `SRC-360`, `SRC-362`

### 최소 대조

- 동일하거나 유사한 합성어 경계에서 후행 평장애음의 평음 실현
- 동일하거나 유사한 합성어 경계에서 후행 평장애음의 경음 실현

### 경계 범위

- **primary** — 어절 내부의 확인 가능한 합성어·어근 경계 (`CLM-0023`, `CLM-0029`, `CLM-0035`)
- **separate_population** — 어절 간 또는 합성어성이 불명확한 경계 (`CLM-0037`, `SRC-360`, `SRC-362`)
- **excluded** — 형태소 내부의 단순 분절 연쇄 (`CLM-0041`)

### 표면형–형태소–POS 왕복

- 표면형: 후행 음절의 표면 초성이 평장애음 철자인지 확인하되 표기만으로 실제 경음 실현을 판정하지 않는다.
- 형태소: 좌우 구성요소가 합성어 또는 생산적인 명사 결합으로 분석되는지 형태소열과 어절 표면형을 함께 확인한다.
- POS: NNG/NNP 등 명사성 좌우 요소를 중심으로 우선하되 POS만으로 합성어성을 자동 확정하지 않는다.
- 고위험 예:
  - NNG+JKB처럼 합성어가 아닌 경계를 PT로 오인
  - 장애음 종성 뒤 평장애음의 일반적 자동 경음화
  - ㅎ·ㄶ·ㅀ 관련 격음화

### 중심 모집단

- `PT_PRI_COMPOUND_LENIS` — 확인 가능한 합성어·명사 결합 경계와 후행 평장애음 ㄱ·ㄷ·ㅂ·ㅅ·ㅈ (우선순위 1; `CLM-0023`, `CLM-0029`, `CLM-0035`, `CLM-0043`; `literature_seeded_candidate`)

### 주변 모집단

- `PT_PER_LEXICALIZED` — 어휘화 정도나 합성어성 판단이 흔들리지만 직접 보고된 어휘 (우선순위 2; `CLM-0037`, `CLM-0040`, `CLM-0052`; `literature_seeded_candidate`)

### 탐색 모집단

- `PT_EXP_INTER_EOJEOL` — 어절 간 평장애음 연쇄로 운율 경계와 후어휘 경음화가 개입할 수 있는 환경 (우선순위 3; `SRC-360`, `SRC-362`; `pending_probe`)

### 범위 밖

- `PT_OUT_AUTOMATIC_POST_OBSTRUENT` — 합성어성과 무관한 장애음 뒤 자동 경음화 또는 조사·어미 경계 (우선순위 4; `CLM-0041`, `CLM-0059`; `pending_probe`)
- `PT_OUT_UNDERLYING_TENSE` — 후행 자음이 기저적으로 경음인 어휘 (우선순위 4; 없음; `pending_probe`)

### 불명 보존

- `PT_UNC_COMPOUNDNESS` — 형태소 분석만으로 합성어 경계를 확인할 수 없는 단일 NNG 내부 (우선순위 4; `CLM-0041`; `pending_probe`)

### 후보 실현 범주

- `plain_like`
- `tense_like`
- `intermediate_or_mixed`
- `not_judgeable`

### 사람이 볼 항목

- 합성어성·좌우 구성요소
- 후행 폐쇄·VOT·F0 등 경음 단서
- 운율 경계와 휴지
- 같은 형태소 조합·단어 반복

### 근거의 한계

- 핵심 문헌은 합성어 정의와 자료 구성이 서로 달라 단일 검색식이 확립되지 않았다.
- 운율 자료 SRC는 현상별 occurrence 판정 기준을 직접 확립하지 않는다.

### 아직 열린 질문

- 합성어 경계를 말뭉치 형태소열에서 어디까지 신뢰할 것인가?
- 장애음 뒤 자동 경음화를 비교군으로 몇 건 둘 것인가?
- 사이시옷·NI 중복을 복수 membership으로 둘 것인가?

## NAN — ㄴ 앞 비음화

장애음 종성과 후행 /ㄴ/의 연쇄에서 선행 장애음이 비음으로 실현되는 현상과 그 변이를 다룬다.

- definition: `phenomena/_draft/NAN/definition.md`
- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAN_현상종합_초안_20260823.md`
- 근거: `CLM-0061`, `CLM-0064`, `CLM-0067`, `CLM-0069`, `CLM-0071`, `CLM-0074`, `CLM-0075`, `CLM-0077`, `SRC-360`, `SRC-362`

### 최소 대조

- 장애음성이 유지되는 C+ㄴ 실현
- 선행 장애음이 조음 위치를 유지한 비음으로 실현되는 C+ㄴ 실현

### 경계 범위

- **primary** — 형태소 내부와 어절 내부 장애음+ㄴ (`CLM-0064`, `CLM-0069`, `CLM-0071`)
- **separate_population** — 어절 간 장애음#ㄴ (`CLM-0074`, `SRC-360`, `SRC-362`)
- **pending** — ㅁ 앞 환경 (`CLM-0061`)

### 표면형–형태소–POS 왕복

- 표면형: 표면 철자의 선행 종성과 후행 ㄴ을 확인하되 실제 비음화 여부는 청취·음향 판정 전까지 비워 둔다.
- 형태소: 형태소 내부·형태소 경계·어절 경계를 분리하고 삽입된 ㄴ인지 기저 ㄴ인지 보존한다.
- POS: POS 제한으로 모집단을 좁히지 않되 조사·어미 때문에 생긴 경계는 별도 층으로 기록한다.
- 고위험 예:
  - NI가 먼저 적용된 뒤 생긴 비음 연쇄
  - 기저 비음 종성을 장애음 비음화로 오인
  - 어절 간 IP 경계 개입

### 중심 모집단

- `NAN_PRI_OBS_N` — 한글 장애음 종성 뒤 기저 /ㄴ/이 오는 형태소 내부·어절 내부 환경 (우선순위 1; `CLM-0064`, `CLM-0069`, `CLM-0071`, `CLM-0077`; `literature_seeded_candidate`)

### 주변 모집단

- `NAN_PER_INTER_EOJEOL` — 어절 간 장애음#ㄴ이며 운율 경계를 별도 기록하는 환경 (우선순위 2; `CLM-0074`, `SRC-360`, `SRC-362`; `literature_seeded_candidate`)

### 탐색 모집단

- `NAN_EXP_BEFORE_M` — 후행 /ㅁ/까지 같은 파일럿에 포함할지 확인하는 별도 탐색 (우선순위 3; `CLM-0061`; `pending_probe`)

### 범위 밖

- `NAN_OUT_UNDERLYING_NASAL` — 선행 종성이 기저 비음인 연쇄 (우선순위 4; 없음; `pending_probe`)
- `NAN_OUT_INSERTION_ONLY` — NI 여부만을 묻는 사례이며 NAN 환경이 별도로 성립하지 않는 행 (우선순위 4; `CLM-0067`; `pending_probe`)

### 불명 보존

- `NAN_UNC_PARTIAL` — 부분 비음화 또는 기저·삽입 ㄴ 구분이 불명확한 사례 (우선순위 4; `CLM-0071`; `pending_probe`)

### 후보 실현 범주

- `oral_obstruent_like`
- `fully_nasalized`
- `partially_nasalized`
- `not_judgeable`

### 사람이 볼 항목

- 선행 종성의 구강 폐쇄·비음 공명
- 후행 ㄴ과의 경계
- 어절 내부·간
- 운율 경계와 발화 속도

### 근거의 한계

- 직접 정독 핵심 문헌이 한 편이므로 형태론적 하위 환경 근거가 얇다.
- 필수 현상 기술이 자연대화 모든 운율 경계에서 100% 적용됨을 확립하지 않는다.

### 아직 열린 질문

- 후행 ㅁ을 NAN 본모집단에 넣을 것인가 별도 현상으로 둘 것인가?
- 어절 간 표본을 중심 12개에 포함할 것인가?
- 부분 비음화를 3단계로 기록할 수 있는가?

## NAL — ㄹ 앞 비음화

장애음과 후행 /ㄹ/의 연쇄에서 후행 유음과 선행 장애음이 비음 계열로 바뀌거나 유음이 유지되는 변이를 다룬다.

- definition: `phenomena/_draft/NAL/definition.md`
- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAL_현상종합_초안_20260823.md`
- 근거: `CLM-0061`, `CLM-0062`, `CLM-0065`, `CLM-0066`, `CLM-0067`, `CLM-0075`, `CLM-0076`, `CLM-0077`, `CLM-0093`, `CLM-0094`, `CLM-0095`, `CLM-0096`, `CLM-0097`, `CLM-0098`, `SRC-360`, `SRC-362`

### 최소 대조

- 후행 /ㄹ/이 유음으로 유지되는 장애음+ㄹ 실현
- 후행 /ㄹ/과 선행 장애음이 비음화되는 실현

### 경계 범위

- **primary** — 형태소 내부와 어절 내부 장애음+ㄹ (`CLM-0076`, `CLM-0095`, `CLM-0096`)
- **separate_population** — 외래어·어절 간 장애음+ㄹ (`CLM-0094`, `SRC-360`, `SRC-362`)
- **excluded** — 비음+ㄹ 또는 ㄹ+ㄴ (`CLM-0065`)

### 표면형–형태소–POS 왕복

- 표면형: 선행 종성과 후행 ㄹ의 표면 철자를 확인하고 표면 음성 방향은 자동 추정하지 않는다.
- 형태소: 장애음+ㄹ을 NAL로, 비음+ㄹ·ㄹ+ㄴ을 LLN 후보로 구분하되 중간형은 복수 membership으로 보존한다.
- POS: 외래어·고유명사·일반어를 POS만으로 삭제하지 않고 어종 sidecar로 분리한다.
- 고위험 예:
  - 비음+ㄹ을 NAL로 오분류
  - 외래어 철자와 형태소 분석 불일치
  - 후행 ㄹ이 실제 형태소 초성인지 불명

### 중심 모집단

- `NAL_PRI_OBS_L` — 한글 장애음 종성 뒤 기저 /ㄹ/이 오는 형태소 내부·어절 내부 환경 (우선순위 1; `CLM-0076`, `CLM-0095`, `CLM-0096`; `literature_seeded_candidate`)

### 주변 모집단

- `NAL_PER_LOANWORD` — 외래어의 장애음+ㄹ 연쇄 (우선순위 2; `CLM-0094`, `CLM-0097`; `literature_seeded_candidate`)

### 탐색 모집단

- `NAL_EXP_INTER_EOJEOL` — 어절 간 장애음#ㄹ로 운율 경계를 별도 기록하는 환경 (우선순위 3; `SRC-360`, `SRC-362`; `pending_probe`)

### 범위 밖

- `NAL_OUT_NASAL_L` — 선행 분절이 기저 비음인 비음+ㄹ 연쇄는 LLN 모집단 (우선순위 4; `CLM-0065`; `pending_probe`)
- `NAL_OUT_L_N` — ㄹ+ㄴ 방향 연쇄는 LLN 모집단 (우선순위 4; `CLM-0065`; `pending_probe`)

### 불명 보존

- `NAL_UNC_INTERMEDIATE` — [비음+유음] 중간형 또는 어종·경계 해석이 불명확한 사례 (우선순위 4; `CLM-0093`, `CLM-0098`; `pending_probe`)

### 후보 실현 범주

- `liquid_retained`
- `full_nasal_sequence`
- `nasal_plus_liquid_intermediate`
- `not_judgeable`

### 사람이 볼 항목

- C1 비음화 여부
- C2 ㄹ 유지·비음화 여부
- 중간형의 설측·비음 단서
- 어종·경계·운율

### 근거의 한계

- 직접 문헌은 이론·실험 자료가 중심이라 자연대화의 어절 간 분포를 확립하지 않는다.
- 외래어와 고유어를 같은 모집단으로 합칠 근거는 아직 없다.

### 아직 열린 질문

- 외래어를 주변 모집단으로 몇 건 포함할 것인가?
- [비음+유음] 중간형을 독립 범주로 판정할 수 있는가?
- 어절 간 연쇄는 운율 주석 전까지 탐색으로만 둘 것인가?

## NI — ㄴ삽입

자음으로 끝나는 요소 뒤 /i/ 또는 /j/ 시작 요소가 결합할 때 [n]이 수의적으로 나타날 수 있는 현상을 다룬다.

- definition: `phenomena/34_n_insertion/definition_stage2_frozen_v1_20260823.md`
- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NI_현상종합_초안_20260823.md`
- 근거: `CLM-0001`, `CLM-0002`, `CLM-0003`, `CLM-0004`, `CLM-0008`, `CLM-0014`, `CLM-0015`, `CLM-0022`, `CLM-0023`, `CLM-0026`, `SRC-360`, `SRC-362`

### 최소 대조

- 경계에 삽입 [n]이 들리지 않는 실현
- 경계에 삽입 [n]이 나타나는 실현

### 경계 범위

- **primary** — 어절 내부 자음 말음+/i·j/ 경계 (`CLM-0001`, `CLM-0004`, `CLM-0014`)
- **separate_population** — 어절 간 자음 말음#/i·j/ (`CLM-0023`, `SRC-360`, `SRC-362`)
- **separate_population** — 보조사 표면 요 (`CLM-0002`)
- **excluded** — 표면 서술격 이 (`CLM-0001`)

### 표면형–형태소–POS 왕복

- 표면형: 원 표면형과 어절 표면형에 서술격 이가 실제 나타나는지, 또는 요만 나타나는지 먼저 구분한다.
- 형태소: 표면 요를 분석기가 이/VCP+요로 복원한 경우 VCP만 보고 삭제하지 않고 요 탐색 모집단에 보존한다.
- POS: 오른쪽 J*/E*는 본모집단에서 제외하되 VCP는 표면형과 형태소 연쇄를 함께 확인해 overt 이와 restored 이+요를 구분한다.
- 고위험 예:
  - 편/NNB+이/VCP→편인·편이에요는 표면 이가 있어 범위 밖
  - 표면 요+분석 이/VCP+요는 제외 금지
  - 형태소 분석만으로 /i/·/j/ 경계를 확정

### 중심 모집단

- `NI_PRI_C_J` — 어절 내부 자음 말음 뒤 /j/ 시작 자립 형태소·합성어 환경 (우선순위 1; `CLM-0001`, `CLM-0004`, `CLM-0014`, `CLM-0023`; `researcher_confirmed`)
- `NI_PRI_C_I` — 어절 내부 자음 말음 뒤 /i/ 시작 환경을 /j/와 분리한 보조 중심층 (우선순위 1; `CLM-0003`, `CLM-0014`; `researcher_confirmed`)

### 주변 모집단

- `NI_PER_SINO` — 한자어 공명음·장애음+/j/를 구분해 보존하는 환경 (우선순위 2; `CLM-0004`, `CLM-0015`; `pending_probe`)

### 탐색 모집단

- `NI_EXP_YO` — 표면 요/JX 또는 표면 요+분석 이/VCP+요 계열의 별도 탐색 모집단 (우선순위 3; `CLM-0002`; `researcher_confirmed`)
- `NI_EXP_INTER_EOJEOL` — 어절 간 자음#/i·j/ 환경 (우선순위 3; `CLM-0023`, `SRC-360`, `SRC-362`; `pending_probe`)

### 범위 밖

- `NI_OUT_OVERT_COPULA_I` — 표면형에 서술격 이가 실제 나타나는 VCP 환경 (우선순위 4; `CLM-0001`; `researcher_confirmed`)
- `NI_OUT_J_E_MAIN` — 본모집단의 오른쪽 J*/E*와 숫자·기호 unit (우선순위 4; `CLM-0001`; `researcher_confirmed`)

### 불명 보존

- `NI_UNC_SURFACE_ANALYSIS` — 표면 이·요와 분석 이/VCP+요의 대응을 확정할 수 없는 사례 (우선순위 4; `CLM-0002`; `pending_probe`)

### 후보 실현 범주

- `no_insertion`
- `n_insertion`
- `insertion_plus_nasalization`
- `uncertain_or_mixed`
- `not_judgeable`

### 사람이 볼 항목

- 표면 이 대 표면 요
- 삽입 [n] 유무
- 선행 종성 비음화
- 경계 scope·어원·같은 형태소 조합

### 근거의 한계

- 동결 v1은 VCP 표면형 분기를 구현하지 않아 연구 query로 그대로 재사용할 수 없다.
- CLM-0015의 한자어 하위 환경은 원전 확인이 남아 있다.

### 아직 열린 질문

- 동결 v1에서 표면형 정본으로 사용할 열은 무엇인가?
- /i/와 /j/를 10개 중심 표본 안에서 어떻게 배분할 것인가?
- 한자어 하위층은 pilot에서 몇 건만 둘 것인가?

## LLN — ㄴㄹ·ㄹㄴ 연쇄(유음화·비음화 복합형)

/ㄴ+ㄹ/과 /ㄹ+ㄴ/ 연쇄에서 [ㄹㄹ], [ㄴㄴ], 분절 유지와 중간형이 경쟁하는 변이를 방향별로 다룬다.

- definition: `phenomena/_draft/LLN/definition.md`
- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/LLN_현상종합_초안_20260823.md`
- 근거: `CLM-0061`, `CLM-0063`, `CLM-0065`, `CLM-0068`, `CLM-0069`, `CLM-0070`, `CLM-0071`, `CLM-0074`, `CLM-0078`, `CLM-0079`, `CLM-0081`, `CLM-0082`, `CLM-0085`, `CLM-0087`, `CLM-0090`, `CLM-0099`, `CLM-0102`, `CLM-0104`, `SRC-360`, `SRC-362`

### 최소 대조

- /ㄴㄹ/ 또는 /ㄹㄴ/이 [ㄹㄹ] 계열로 실현
- 같은 기저 연쇄가 [ㄴㄴ] 또는 분절 유지 계열로 실현

### 경계 범위

- **primary** — 어절 내부 ㄴ+ㄹ과 ㄹ+ㄴ (`CLM-0082`, `CLM-0083`, `CLM-0090`, `CLM-0102`)
- **separate_population** — 어절 간 ㄴ#ㄹ과 ㄹ#ㄴ (`CLM-0074`, `SRC-360`, `SRC-362`)
- **excluded** — 장애음+ㄹ (`CLM-0065`)

### 표면형–형태소–POS 왕복

- 표면형: 표면 철자의 ㄴㄹ·ㄹㄴ 방향을 구분하고 실제 [ll]/[nn]은 자동 판정하지 않는다.
- 형태소: 형태소 내부·어기+접사·합성어·어절 간을 분리하고 같은 형태소 조합을 묶는다.
- POS: 일반어·외래어·고유명사를 POS로 삭제하지 않고 어종과 형태론 경계를 별도 기록한다.
- 고위험 예:
  - 장애음+ㄹ NAL을 LLN으로 오분류
  - 형태소 분석이 ㄴ/ㄹ 경계를 복원하거나 소실
  - 어절 간 연쇄와 단어 내부 연쇄 혼합

### 중심 모집단

- `LLN_PRI_NL_INTRA` — 어절 내부 /ㄴ+ㄹ/ 연쇄 (우선순위 1; `CLM-0082`, `CLM-0083`, `CLM-0090`, `CLM-0102`; `literature_seeded_candidate`)
- `LLN_PRI_LN_INTRA` — 어절 내부 /ㄹ+ㄴ/ 연쇄를 방향별로 분리 (우선순위 1; `CLM-0069`, `CLM-0070`, `CLM-0079`; `literature_seeded_candidate`)

### 주변 모집단

- `LLN_PER_LOANWORD` — 외래어 ㄴㄹ·ㄹㄴ 연쇄 (우선순위 2; `CLM-0068`, `CLM-0074`; `literature_seeded_candidate`)

### 탐색 모집단

- `LLN_EXP_INTER_EOJEOL` — 어절 간 연쇄를 운율 경계와 함께 보는 별도 탐색 (우선순위 3; `CLM-0074`, `SRC-360`, `SRC-362`; `pending_probe`)

### 범위 밖

- `LLN_OUT_OBS_L` — 장애음+ㄹ 연쇄는 NAL 모집단 (우선순위 4; `CLM-0065`; `pending_probe`)
- `LLN_OUT_NONADJACENT` — ㄴ과 ㄹ이 동일 경계에서 인접하지 않는 사례 (우선순위 4; 없음; `pending_probe`)

### 불명 보존

- `LLN_UNC_DIRECTION_OR_BOUNDARY` — 방향·형태소 경계·중간형을 확정할 수 없는 사례 (우선순위 4; `CLM-0087`, `CLM-0099`; `pending_probe`)

### 후보 실현 범주

- `ll_like`
- `nn_like`
- `segment_sequence_retained`
- `intermediate_or_mixed`
- `not_judgeable`

### 사람이 볼 항목

- 기저 방향 ㄴㄹ 대 ㄹㄴ
- [ll]/[nn]/유지/중간형
- 형태소·어절 경계
- 어종·세대·운율

### 근거의 한계

- 방향·어종·과제별 문헌 모집단이 달라 하나의 우세 실현형으로 합칠 수 없다.
- 어절 간 연쇄는 핵심 직접 문헌에서 제외된 경우가 있어 별도 모집단이어야 한다.

### 아직 열린 질문

- 중심 10개에서 ㄴㄹ·ㄹㄴ을 5개씩 강제할 것인가?
- 외래어를 별도 2개에 우선 배치할 것인가?
- 중간형을 별도 범주로 유지할 수 있는가?

## VH — 모음조화

용언 어간과 아/어 계열 어미의 결합에서 나타나는 조화형·비조화형 선택을 일반 활용과 불규칙·방언·축약 환경으로 나누어 다룬다.

- definition: `phenomena/_draft/VH/definition.md`
- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/VH_현상종합_초안_20260823.md`
- 근거: `CLM-0106`, `CLM-0109`, `CLM-0111`, `CLM-0112`, `CLM-0113`, `CLM-0114`, `CLM-0120`, `CLM-0123`, `CLM-0127`, `CLM-0133`, `CLM-0134`, `CLM-0138`, `SRC-362`

### 최소 대조

- 동일 어간·어미 기능에서 기대되는 조화형 아/어 선택
- 동일하거나 비교 가능한 환경에서 비조화형 선택

### 경계 범위

- **primary** — 용언 어간+아/어 계열 어미의 어절 내부 경계 (`CLM-0109`, `CLM-0110`, `CLM-0112`, `CLM-0115`)
- **separate_population** — 불규칙·방언·메신저 표기·축약 환경 (`CLM-0114`, `CLM-0127`, `CLM-0133`)
- **excluded** — 비용언 또는 아/어 교체와 무관한 모음 연쇄 (`CLM-0111`)

### 표면형–형태소–POS 왕복

- 표면형: 실제 어절 표면형의 아/어·축약형을 보존하고 표기만으로 음성적 모음 질을 확정하지 않는다.
- 형태소: 어간 표면형·표제어형·어미 표면형을 함께 보며 불규칙·ㅡ탈락·축약을 별도 유형으로 둔다.
- POS: 왼쪽 V*와 오른쪽 E*를 출발점으로 삼되 VX·VCP·분석 오류는 표면형과 함께 확인한다.
- 고위험 예:
  - 표면 축약형에서 어미 아/어가 분석상 복원
  - VCP·보조용언을 일반 용언 활용으로 오인
  - VH와 HIA 동일 토큰 중복

### 중심 모집단

- `VH_PRI_REGULAR_A_EO` — 일반 용언 어간과 아/어 계열 어미의 생산적 결합 (우선순위 1; `CLM-0109`, `CLM-0110`, `CLM-0112`, `CLM-0115`, `CLM-0116`; `literature_seeded_candidate`)

### 주변 모집단

- `VH_PER_IRREGULAR` — ㅡ탈락·불규칙 활용을 유형별로 분리한 환경 (우선순위 2; `CLM-0127`, `CLM-0133`, `CLM-0134`; `literature_seeded_candidate`)

### 탐색 모집단

- `VH_EXP_DIALECT_NONSTANDARD` — 보고되지 않았거나 비일반적인 방언·비표준·희귀 활용 환경 (우선순위 3; `CLM-0114`, `CLM-0129`; `pending_probe`)

### 범위 밖

- `VH_OUT_NONVERBAL` — 용언 활용이 아니며 아/어 선택 대조가 성립하지 않는 연쇄 (우선순위 4; `CLM-0111`; `pending_probe`)
- `VH_OUT_HIA_ONLY` — 모음충돌 회피만 성립하고 아/어 이형태 선택 질문이 성립하지 않는 사례 (우선순위 4; `CLM-0138`; `pending_probe`)

### 불명 보존

- `VH_UNC_STEM_SURFACE` — 표면형·표제어형·불규칙 분석 대응이 불명확한 사례 (우선순위 4; `CLM-0127`, `CLM-0133`; `pending_probe`)

### 후보 실현 범주

- `harmonic_a`
- `harmonic_eo`
- `disharmonic_variant`
- `contracted_or_deleted`
- `not_judgeable`

### 사람이 볼 항목

- 어간 표면형·표제어형
- 아/어 이형태와 어미 기능
- 불규칙·방언 여부
- HIA membership·발화 속도

### 근거의 한계

- 메신저·실험·자연구어 문헌의 표기와 과제가 달라 표면형 비율을 직접 합칠 수 없다.
- 일반 활용과 방언·비표준 탐색을 같은 우선순위로 두지 않는다.

### 아직 열린 질문

- 어간 표제어 정본은 어느 sidecar에서 연결할 것인가?
- 일반 활용 10개에서 어미 기능을 어떻게 층화할 것인가?
- VH/HIA 중복은 같은 음성을 두 논리 사건으로 볼 것인가?

## HIA — 모음충돌 회피

모음 연쇄에서 활음화·활음 첨가·모음 탈락·축약·충돌 유지가 경쟁하는 양상을 일반 용언 활용과 주변 환경으로 나누어 다룬다.

- definition: `phenomena/_draft/HIA/definition.md`
- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/HIA_현상종합_초안_20260823.md`
- 근거: `CLM-0133`, `CLM-0139`, `CLM-0140`, `CLM-0142`, `CLM-0145`, `CLM-0146`, `CLM-0147`, `CLM-0149`, `CLM-0151`, `CLM-0152`, `CLM-0155`, `CLM-0156`, `SRC-360`, `SRC-362`

### 최소 대조

- 모음충돌이 유지되는 두 모음 연쇄
- 같은 형태론 환경에서 활음화·첨가·탈락·축약 중 하나로 회피된 실현

### 경계 범위

- **primary** — 모음말 용언 어간+모음 시작 어미의 어절 내부 경계 (`CLM-0140`, `CLM-0141`, `CLM-0147`, `CLM-0153`)
- **separate_population** — 어절 간 모음 연쇄·희귀 형태론 환경 (`CLM-0155`, `SRC-360`, `SRC-362`)
- **excluded** — 형태소 경계 없는 단순 철자 모음 연쇄 (`CLM-0142`)

### 표면형–형태소–POS 왕복

- 표면형: 어절 표면형의 연속 모음·축약 철자를 보존하되 표기만으로 활음화·첨가를 판정하지 않는다.
- 형태소: 모음말 어간과 모음 시작 어미의 형태소열, 복원된 아/어, 축약 표면형을 함께 기록한다.
- POS: 왼쪽 V*·오른쪽 E*를 중심으로 하되 일반적 활용을 우선하고 비일반·희귀 조합은 탐색층으로 낮춘다.
- 고위험 예:
  - 전사 기어 대 기여가 실제 음성과 불일치
  - 축약형에서 분석기가 두 형태소를 복원
  - VH 토큰을 HIA 단독으로 또는 그 반대로 계상

### 중심 모집단

- `HIA_PRI_VOWEL_STEM_ENDING` — 모음말 용언 어간과 모음 시작 아/어 계열 어미의 생산적 결합 (우선순위 1; `CLM-0140`, `CLM-0141`, `CLM-0147`, `CLM-0153`, `CLM-0154`; `literature_seeded_candidate`)

### 주변 모집단

- `HIA_PER_CONTRACTION_TYPE` — 활음화·탈락·축약 유형이 어휘·형태론적으로 제한된 환경 (우선순위 2; `CLM-0134`, `CLM-0135`, `CLM-0147`, `CLM-0155`; `literature_seeded_candidate`)

### 탐색 모집단

- `HIA_EXP_GLIDE_INSERTION` — 활음 첨가 또는 일반적 활용이 아닌 저보고 환경 (우선순위 3; `CLM-0150`, `CLM-0155`, `CLM-0156`; `literature_seeded_candidate`)
- `HIA_EXP_INTER_EOJEOL` — 어절 간 모음충돌을 운율 경계와 함께 보는 별도 탐색 (우선순위 3; `SRC-360`, `SRC-362`; `pending_probe`)

### 범위 밖

- `HIA_OUT_NO_MORPH_BOUNDARY` — 형태소 경계가 없고 회피 선택 대조가 성립하지 않는 철자 연쇄 (우선순위 4; `CLM-0142`; `pending_probe`)
- `HIA_OUT_VH_ONLY` — 아/어 선택은 있으나 모음충돌 환경이 성립하지 않는 사례 (우선순위 4; `CLM-0133`; `pending_probe`)

### 불명 보존

- `HIA_UNC_SURFACE_REALIZATION` — 표면 전사·형태소 복원·실제 활음 구간의 대응이 불명확한 사례 (우선순위 4; `CLM-0145`, `CLM-0151`; `pending_probe`)

### 후보 실현 범주

- `hiatus_retained`
- `glide_formation`
- `glide_insertion`
- `vowel_deletion`
- `coalescence_or_contraction`
- `not_judgeable`

### 사람이 볼 항목

- 어간말 모음과 어미 시작 모음
- 활음·포먼트 전이·모음 수
- 표기 축약 대 음성 실현
- VH membership·발화 속도·운율

### 근거의 한계

- 활음화·첨가·탈락·축약은 동일한 음향 기준으로 자동 구분할 수 없다.
- CLM-0145와 CLM-0151은 사람 확인이 남아 있어 수치 인용 근거로 쓰지 않는다.

### 아직 열린 질문

- 12개 안에서 활음화·첨가·탈락·축약을 모두 넣을 것인가?
- VH와 겹치는 사례를 동일 음성의 별도 논리 사건으로 둘 것인가?
- 표기 축약 probe를 중심 표본에 포함할 것인가?

## 범위 밖

- 자동 실현 판정
- MFA·KOINA·wav2vec2 실행
- production query 동결
- 원자료·r3·6-tier·기존 PV 출력 수정
- 연구자 검토를 했다고 자동 기록
