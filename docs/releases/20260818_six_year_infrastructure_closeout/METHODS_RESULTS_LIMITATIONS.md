# 6개년 연구 인프라: 방법, 결과, 검증 및 한계

## 1. 연구 흐름과 인프라 목적

최종 연구 흐름은 다음과 같다.

```text
원 JSON·음성
  → 발화·화자·세션 identity와 형태소 CSV
  → 표기·형태소·발음 참조 결합검색
  → 후보 exact-ID와 WAV·TextGrid 연결
  → 선택 자료의 운율 분석(KOINA 등)
  → 연구자의 청취·음향·TextGrid 기반 실제 실현 판정
  → 수정 이력과 파생 자료 공개
```

MFA는 이 흐름의 가운데에 있는 시간 연결 장치다. G2P나 사전 phone은 MFA가
텍스트와 음성을 정렬하도록 돕는 입력 가설이고, `phones_mfa`는 그 가설과 음향
모델이 선택한 정렬 출력이다. 어느 것도 실제 음운 현상의 실현 여부를 자동으로
판정하지 않는다.

## 2. 입력 정돈

### 2.1 발화 identity

연도·`utt_id`·세션·화자·원 CSV를 기본 조인 키로 유지했다. 대화 자료는 나중에
같은 세션 문맥으로 돌아갈 수 있도록 화자와 세션 정보를 보존했다. WAV 이름과
CSV/JSON 발화 ID가 어긋난 경우에는 문자열을 임의 추정해 덮어쓰지 않고, 원자료
identity와 duration을 대조한 recovery 계획을 만들었다.

### 2.2 형태소와 검색층

형태소 분석은 원 발화 표기와 별도 열로 보존했다. 어절 경계와 형태소 경계를
다른 구분자로 표현하고, 철자 기반 로마자를 검색용 보조 정보로 추가했다. 숫자와
기호는 빈 발음으로 두지 않고 표기 자체와 읽기 후보를 구분해 기록할 수 있게 했다.
의미번호 층은 입력으로 존재하지만 개별 연구 query와의 production join은 다음
연구 단계 Gate로 남아 있다.

6개년 `morph_search.v3` 정본 수량은 다음과 같다.

| 연도 | 발화 | 형태소 token | 형태소 경계 | 기호 읽기 occurrence |
|---:|---:|---:|---:|---:|
| 2020 | 870,437 | 5,767,506 | 4,897,069 | 290,525 |
| 2021 | 1,373,920 | 12,015,453 | 10,641,533 | 537,167 |
| 2022 | 866,359 | 8,192,006 | 7,325,647 | 465,477 |
| 2023 | 677,262 | 6,610,494 | 5,933,232 | 262,115 |
| 2024 | 728,257 | 9,405,308 | 8,677,051 | 436,550 |
| 2025 | 587,121 | 8,965,124 | 8,378,003 | 394,647 |
| **합계** | **5,103,356** | **50,955,891** | **45,852,535** | **2,386,481** |

정본은 `D:\10_LAYERS\09_morph_search_v3_staging\morph_search_v3_20260801`의
연도별 `YEAR_MANIFEST.json`이다.

## 3. 공통발음과 MFA 계약

### 3.1 공통발음 release를 만든 이유

연도별 inline G2P를 따로 실행하면 모델·규칙·사전 상태와 실패 처리가 달라질 수
있었다. 모든 연도에서 같은 phone 기준을 썼다고 방법론에 쓸 수 있도록 관측
어휘를 공통 범위로 모으고, 기본 사전과 동일한 최신 Jamo G2P 기준을 동결했다.
우리말샘 등 사전의 예외 발음 정보는 검색·참조층에 보존할 가치가 있지만, 검토하지
않은 변이를 MFA 사전에 무차별 추가하지 않았다. 사전 변이가 항상 해당 발화에 더
맞는 것은 아니기 때문이다.

최종 release는 `common_pron_mfa_r3_20260809`다. RC0 교차 계약이 동결한 항목은
다음과 같다.

- 공통발음 release와 pronunciation contract
- 최종 MFA dictionary SHA-256
- Korean MFA acoustic model SHA-256
- Jamo G2P provenance SHA-256
- Python 3.13.14, MFA 3.4.0, Pynini 2.1.7 runtime
- `fresh_r3_full_realign=true`
- `research_textgrid.v2` 6-tier schema

모델 이름만 같은 것을 동일 방법으로 간주하지 않고, 실제 파일 SHA와 계약 ID를
연도별 결과에 결속했다.

### 3.2 왜 6개년을 다시 정렬했는가

초기 정렬에서 `있지`, `있는`, `없는`, `어쨌든` 같은 사례의 입력 phone이 기대한
규칙형과 일치하지 않는 것을 표본 검토에서 발견했다. 일부 TextGrid만 후처리하면
연도별 phone 생성 근거가 달라지므로, 과거 계산 시간보다 방법론적 일관성을
우선해 r3 계약으로 2020–2025를 모두 새로 정렬했다. 이후 오류는 연도 전체를
반복하지 않고 exact-ID 후속 shard로 분리했다.

### 3.3 안전 본체와 후속 분리

원천 발화는 다음 상태 중 하나만 가진다.

- `aligned_safe_body`: 완전한 word+phone 정렬과 독립 QC를 통과
- `pre_mfa_technical_exclusion`: 음원 pairing, duration, 기호 등 MFA 전 기술 문제
- `post_mfa_technical_exclusion`: MFA 입력에는 있었으나 완전한 interval 부재
- `pronunciation_followup`: 발음 입력 근거 확정 뒤 별도 정렬할 대상

이 분리는 실패를 성공으로 숨기지 않으면서 안전한 본체가 진행되게 했다. 기술
실패와 방법론적 연구 제외는 섞지 않았다.

안전 본체 밖 817,310건은 검색 대상에서 삭제한 자료가 아니다. 전 발화가
`morph_search.v3`에 있으므로 표기·형태소 환경으로 먼저 검색할 수 있다. 검색 뒤
`aligned_safe_body`는 즉시 WAV·TextGrid 문맥 검토로 보내고,
`pronunciation_followup`과 기술 후속은 실제 연구 후보로 뽑힌 exact-ID부터
발음·음원 recovery를 수행한다. 후속 자료에는 최종 `phones_mfa`와 6-tier가
없으므로 phone·시간 검색 결과처럼 표시해서는 안 된다.

발음 후속 718,364건이 큰 이유는 발화 안에 확정하지 않은 어절이 하나라도 있으면
발화 전체를 안전 본체에서 보류한 보수적 규칙 때문이다. 내부 분류는 hold
717,354, policy 136, empty reference 848, hold+policy 26이다. 이들은 “사용할 수
없는 발화”가 아니라 불확실한 발음을 억지로 사전에 넣지 않은 발화다.

## 4. 연구용 TextGrid

최종 schema는 다음 6-tier다.

| tier | 내용 | 주의 |
|---|---|---|
| `words` | MFA가 정렬한 어절 | 실제 형태소 경계가 아님 |
| `phones_mfa` | MFA phone interval | 실제 발음 정답이 아님 |
| `phoneme_r_auto` | MFA phone의 기계적 넓은 로마자 범주 | 기저형·수동 음운전사가 아님 |
| `utterance` | 한글 발화 전사 | 원/정규화 provenance 확인 필요 |
| `utterance_orth_r` | 어절 구분을 보존한 철자 로마자 검색 문자열 | 발음 로마자와 구별 |
| `morph_analysis_utt` | 한글 형태소/POS 검색 문자열 | 시간 정렬된 형태소 tier가 아님 |

빈 앞뒤 구간은 모든 tier가 TextGrid 전체 길이를 덮도록 interval로 유지하되,
검색 정보 tier의 내용은 발화가 있는 시간 문맥에만 둔다. 여러 발화를 이어붙일 때
source utterance ID와 speaker tier가 추가될 수 있지만, 단일 발화 정본의 6-tier
계약과 혼동하지 않는다.

## 5. 검증 체계

검증은 같은 프로그램의 성공 메시지만 믿지 않는 방식으로 구성했다.

1. 입력 contract: 정확한 ID, 파일 수, SHA, 모델·runtime 고정
2. preflight: 용량, Windows PowerShell 5.1 호환, 입력 pairing 검사
3. checkpoint: shard/연도 완료 marker와 재개 가능한 namespace
4. fail-closed: TextGrid가 일부만 생성되면 성공으로 처리하지 않음
5. post-MFA 회계: 완전 정렬과 미정렬 exact-ID를 합쳐 입력과 일치
6. 독립 QC: 생성기와 별도 코드가 coverage, tier, duration, companion table,
   DB 표본 재수출을 재검사
7. 교차연도 감사: 6개년 발음·모델·runtime·schema 동일성 검증
8. researcher Gate: 자동 승인하지 않고 범위와 candidate hash에 결속한 승인

RC0 `QA_REPORT.json`의 hard failure는 모두 0이다. 큰 자산의 SHA도 release 작성
시 다시 확인했다.

## 6. RC1과 수동 보정

첫 recovery inventory는 817,310건이다. 이 가운데 55건을 진단했고, 연구자
검토로 수동 word·전사 16건을 만들었다. RC1은 RC0를 복사하거나 수정하지 않고
55행 상태 sidecar와 16행 curated pointer만 추가한다.

- base source: 5,103,356
- base aligned 6-tier: 4,286,046
- first shard status: 55
- curated recovery: 16
- remaining recovery inventory: 817,255
- main body alignment delta: 0

D9 phone은 진단 참고 전용이다. 수동 전사가 바뀌었는데 기존 자동 형태소·phone을
그대로 최종값으로 채택하면 서로 모순되므로, 형태소와 phone/phoneme 재구축은
별도 Gate로 남겼다.

## 7. 후보 검색 연결 검증

RC0 기본값 위에 RC1 exact-ID 예외만 우선 적용하는 active-view 계약을 만들었다.
파일럿 22 occurrence에서 실제 환경 후보 20건을 확인했고, TextGrid가 있는 19건을
형태소 어절 index와 `words` interval에 연결했다. 이 시간은 청취할 어절 문맥일
뿐 실제 음운 현상의 시작·끝이나 실현 판정이 아니다.

ㄴ 삽입 B1 개정안은 어절 내부와 어절 간 환경을 분리하고 J*/E* 및 숫자·기호
인접을 제외하며 연구자가 실현을 판정하도록 설계했다. 이는 승인된 다음 연구
단계의 query 규칙이지, 현재 closeout에서 얻은 ㄴ 삽입 연구 결과가 아니다.

## 8. AI 보조와 인간 검증

본 구축은 연구자와 생성형 AI 도구의 반복적 협업으로 진행됐다.

- 연구자: 연구 목적·언어학적 구분·포함 범위 결정, 청취와 TextGrid 검토,
  예외 해석, 단계별 명시 승인, 최종 책임
- Claude Code와 Codex: 저장소 조사, 코드 초안·수정, manifest·감사·문서 생성,
  오류 재현과 진단, 명령어와 checkpoint 제안

AI가 만든 코드와 설명은 곧바로 자료의 정답으로 취급하지 않았다. 코드 결과는
입력 contract, 수량 회계, SHA-256, 독립 감사와 연구자 검토를 통과해야 했고,
음운 실현 판단은 자동 phone이 아니라 연구자에게 남겼다. 공개 문서에는 AI가
보조했다는 사실과 인간 검증 절차를 함께 밝히되, 확인하지 못한 모델 버전이나
“AI가 연구를 자율 수행했다”는 표현은 쓰지 않는다.

권장 공개 문구:

> 자료 구축 과정에서 Claude Code와 OpenAI Codex를 코드 작성·검토, 오류 진단,
> 재현성 문서와 검증 절차의 초안 작성에 보조적으로 사용하였다. 연구 질문,
> 언어학적 분류, 청취·TextGrid 판정, 단계별 채택 결정은 연구자가 수행하였다.
> AI가 제안한 산출물은 고정 입력, 수량·해시 회계, 독립 감사 및 연구자 검토를
> 통과한 경우에만 채택하였다.

## 9. 한계와 공개 시 주의

1. 정렬 성공은 음운 현상 실현 성공이 아니다.
2. 강제정렬 경계는 수동 음성학 분절의 대체물이 아니다.
3. 자동 형태소 분석·로마자·기호 읽기·사전 발음은 보조 정보이며 오류 가능성이
   있다.
4. 후속 817,255건이 남아 있으므로 RC1은 전체 회수 완료본이 아니다.
5. 6개년 분모는 인프라 범위이며 개별 연구의 분석 분모는 별도 decision ledger로
   만들어야 한다.
6. 원 음성·전사 재배포는 말뭉치 이용조건과 개인정보·저작권을 별도로 확인해야
   한다. GitHub에는 코드, 작은 manifest, 비식별 예시와 설명만 둔다.
7. 절대 로컬 경로는 내부 재현성 근거다. 외부 공개본에는 환경변수나 설정 파일
   기반의 상대적 예시로 바꾸고 원자료 경로를 그대로 공개하지 않는다.
8. KOINA, wav2vec2/HuBERT 등은 선별 후속 분석 도구이며 MFA 본체 열을
   덮어쓰지 않는 보조열/sidecar로만 추가한다.
