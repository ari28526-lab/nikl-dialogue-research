# 방법론 기록: NIKL 일상대화 말뭉치(2020-2025) 바른 형태소 재분석

작성 시작: 2026-07-09 (진행 중 갱신)
목적: 논문 방법론 절 작성에 필요한 모든 결정·수치·절차의 근거 기록

---

## 1. 자료 (Data)

### 1.1 대상 말뭉치
국립국어원 일상 대화 말뭉치(모두의 말뭉치) 2020-2025, JSON 배포판.
위치: `D:\00_NIKL_DIALOGUE_2020-2025_json\`

| 연도 배포판 | JSON 파일 수 |
|---|---:|
| NIKL_DIALOGUE_2020_v1.4 | 2,232 |
| NIKL_DIALOGUE_2021_v1.1 | 4,143 |
| NIKL_DIALOGUE_2022_v1.0_JSON | 2,654 |
| NIKL_DIALOGUE_2023_v1.1 | 1,973 |
| NIKL_DIALOGUE_2024_v1.0 | 3,227 |
| NIKL_DIALOGUE_2025_v1.0 | 2,927 |
| **합계** | **17,156** |

- 2025 배포판은 2026-07-08 다운로드, 2026-07-09 압축 해제 (zip 내 파일명 ASCII, 인코딩 문제 없음).
- 분석 대상 텍스트: 각 발화(utterance)의 `form` 필드(정제 전사).
  `original_form`(원 전사)이 아닌 `form`을 쓴 이유: 표기 정규화(예: 컨셉→콘셉트)가
  적용되어 사전 조회·형태소 분석 정확도가 높음. 발음 변이 연구 시에는
  `original_form` 및 기존 MFA TextGrid(발음 tier)를 참조.
- 빈 발화(form 공백)는 제외.

### 1.2 참조 자원
| 자원 | 위치 | 역할 |
|---|---|---|
| NIKL 형태 분석 말뭉치 MP v1.1 (2019) | `D:\00_RAW\reference\01_NIKL_MP_v_1_1` | 형태소·어절 빈도 **분포 타당성 규준** (다른 말뭉치 → 발화별 정답 대조 불가, F1 아님). **파생 빈도표(`01~08_*.csv`)는 저자가 R+Quarto로 집계 구축**(가이드 `NIKL_corpus_guide.qmd`, 2026-01-06). 단위 (form,label)=(형태소,태그), 문어(NX)/구어(SX)/전체(ALL) 분리 + 품사빈도 + 발음열(`form_roman_mfa`). 의미번호 없음 |
| NIKL 어휘의미 분석 말뭉치 LS 2020 v2.0 | `D:\00_RAW\reference\02_NIKL_LS` | 우리말샘 sense_id 분포 → 의미번호 부여 근거. **공식: 총 392만 어절(문어 200/구어 100/메신저 92), v2.0 2022-04-01 공개.** 인용: 국립국어원(2022), NIKL Word Sense Tagged Corpus 2020 (v.2.0) |
| **KoFREN** 한국어 빈도 규준 (Kim, Choi & Cho 2024) | `01_frequency_data/final_word_frequency/` (논문 PDF `2024.lrec-main.866.pdf`) | **자유발화(spontaneous speech) 규준, 41M 단어**. AiHub 3개 자유발화 코퍼스(아동 3–10/청년 11–59/노년 60+) 합산, **바른 토크나이저로 lemma 빈도** 집계 → 우리와 동일 태거·레지스터 최적 매칭. LDT·AoA와 상관(심리언어 타당성). 컬럼 WORD/POS_TAG/COUNT(raw)/COUNT_ADJUST(SUBTLEX_US 크기 스케일)/LOG10(**조정값의** log10). ⚠️ 사전엔 raw COUNT+LOG10 조인 → **`KoFREN_log10`≠log10(`freq_KoFREN_all`)**. 파일 `adult_*`=청년(11–59). 인용: Kim, Choi & Cho (2024), LREC-COLING. **외부 규준(우리 코퍼스 아님)** |
| NIKL 다층위 구조 분석 말뭉치 2025 v1.0 | `D:\00_RAW\reference\NIKL_Multi-layered_2025_v1.0` | **최신 형태(MP)·어휘의미(WSD)·구문(DP)·의미역(SRL)·조응(ZA) 주석**. **공식: 총 30만 어절(문어 20만=신문 2024 선별, 구어 10만=일상 대화 말뭉치 2024에서 2인 대화 위주 선별), 2026-06-30 공개.** 구어부가 본 연구 말뭉치의 부분집합 → **동일 발화 직접 대조 검증 가능.** sense 특수코드: 777(고유명사) 등. 인용: 국립국어원(2025), NIKL Korean Multi-layered Structural Analysis Corpus 2025 (v.1.0) |
| NIKL 어휘목록 v2 (저자 구축, 53만 행, Python `NIKL_dictionary_lexicon_v2.py`) | `D:\00_RAW\reference\00_DICTIONARY\01_NIKL_lexicon_full_v2.csv` | `sense_no`(=의미번호)/`urimal_id`(우리말샘 ID)/표준대사전 코드 매핑, 단의어 판정. sense 키로 **표준발음(pron_1/2·G2P·2023판) + 어원·어종(고유어/한자어/외래어/혼종어) + 한자어 분석 + 형태분석 + LS·MP 빈도**를 한 표에 조인 |
| 표준대사전↔우리말샘 대응표 | `D:\00_RAW\reference\00_DICTIONARY\00_stdict_urimal_mapping.csv` | 의미 단위 사전 간 대응 |
| 표준대사전 발음 데이터 (`pron_2023`의 근거) | `D:\00_RAW\reference\00_DICTIONARY\00_2021_2023\` | **원자료 = 국립국어원 표준국어대사전(2020-09, 434,165항목)**. **가공 = 저자(박나영)**: 발음형·형태소경계규칙 적용 전/후·어종·로마자 부여, 일부 발음 자체 교정. **선행 과제 산출물 — 한국연구재단 학술연구교수(B형) 과제번호 2020S1A5B5A17089070**(작성 2021-01, 명사 재가공 스냅샷 2023-10-02). 인용은 표준국어대사전(원자료)+저자 과제(가공) 2층 |
| **NIKL 공식 설명 문서 15종** | `D:\00_RAW\reference\말뭉치설명자료\` | 연도별 전사·PCM 명세, LS/MP/다층위 지침 — 말뭉치 인용·버전 근거 (2026-07-14 등록) |

## 2. 도구 (Tools)

- 형태소 분석기: **바른(Bareun)**, 바이칼AI. 클라우드 API(`api.bareun.ai:443`) 사용.
  - 클라이언트: `bareunpy==2.0.1`, Python 3.13.14 (venv: bareun-smoke)
  - 사용 기능: 형태소 분석 `Tagger.tags()`(배치)/`tag()`(폴백),
    스크립트 `scripts/python/bareun_dialogue_full.py`.
  - ⚠️ **서버 엔진 버전**: 스크립트가 2026-07-09~10 당시 클라우드 서버의
    기본 모델을 사용했으며, API 응답과 당시 로그에는 서버 build ID가
    노출·보존되지 않았다. 따라서 사후에 정확한 엔진 build를 추정해 쓰지 않고,
    논문에는 분석 기간·endpoint·클라이언트(`bareunpy==2.0.1`)와 이 한계를
    명시한다. 현재 동결 A1을 만드는 데 Bareun을 다시 호출하지 않으며, 정확한
    서버 build 확인이 출판 요건이면 바이칼AI 확인 또는 전수 재분석이 별도
    연구자 결정이다(결정 기록: `DECISION_bareun_engine_provenance_20260801.md`).
  - 로컬 Docker 서버 대신 클라우드 API를 택한 이유: 작업 PC(RAM 8GB, Intel N200)
    에서 로컬 AI 서버 상시 구동이 부담(2026-07-06 판단 기록 참조:
    `docs/environment/bareun-morph-analyzer-setup-plan.md`)
  - 라이선스: 연구 목적 형태소 분석 무료 (bareun.ai 안내 기준)
- 태그셋: 바른 출력은 세종 태그셋 확장형. 파일럿에서 관형사 세분(MMD/MMN),
  VCP/VCN, 전 범주 확인 → NIKL MP/다층구조와 동일 계열임을 확인 (5절 검증 예정).

### 2.1 생성형 AI 보조 도구 고지 (AI use disclosure)
논문 보고용 고지 문장(그대로 인용 가능):

> "자료 구축·분석 코드 작성에 생성형 AI 코딩 도구를 보조적으로 사용하였다.
> 모든 산출물(형태소·의미번호·빈도사전·강제정렬·검증)은 저자가 검토하고
> 독립 기준(공식 주석 대비 F1 등)으로 검증하였다. 재현에 필요한 것은 AI 도구가
> 아니라 아래에 명시한 파이프라인 도구·버전·파라미터·공개 코드이다."

모델별 이력(추적 가능한 범위):
- **2026-07-15 이후(이 git 리포 추적 구간)**: 코드·문서 작성 보조에 **Claude
  Opus 4.8**(`claude-opus-4-8`, Anthropic) 사용. 커밋 트레일러
  `Co-Authored-By: Claude Opus 4.8`로 일부 남음.
- **1기(Colab 검색 코드, 2026년 1~3월경) 및 A단계 자료 구축 대부분**: git 이전
  시기로 작업별 AI 모델 이력이 체계적으로 기록되지 않음. **저자 기억으로는
  Claude Opus 4.8(`claude-opus-4-8`)을 사용**한 것으로 추정(당시 최상위 모델).
  - 확증 흔적 1건: MP 파생 빈도표 가이드 `NIKL_corpus_guide.qmd`가
    author "Park Nayoung (**coding with Claude Code**)", **date 2026-01-06** —
    1기 작업이 2026년 1월·Claude Code였음을 실물로 확인(단 모델 버전 문자열까지는
    미기재). 정확한 모델은 저자의 claude.ai 대화 기록으로 확정 가능 — 현재
    "저자 기억 기반, 미확정"으로 표기.
- **방침(이후)**: 이 시점부터 자료·분석 관련 절차에는 사용한 도구·모델을
  METHODS 해당 항목에 병기한다.

## 3. 절차 (Procedure)

### 3.1 파일럿 (2026-07-09)
- 스크립트: `scripts/python/bareun_dialogue_pilot.py`
- 2025년 파일 2개, 발화 120건, 배치 10발화 → 형태소 토큰 2,494개, 오류 0
- 소요 3.9초 (발화당 0.033초). 육안 검토: 구어 축약형 복원 정확
  (예: 섞여→섞이/VV+어/EC, 했습니다→하/VV+았/EP+습니다/EF)

### 3.2 전체 재분석 (1차 레이어: 순수 바른 출력)
- 스크립트: `scripts/python/bareun_dialogue_full.py`
- 실행 환경: 로컬 PC, bareun-smoke venv, 배치 40발화/호출, 파일 단위 체크포인트
  (완료 파일 자동 건너뜀 → 중단·재개 가능)
- 검증 실행(2026-07-09): 2020년 1파일(발화 479) 정상, 약 68발화/초
- **전체 실행 완료 (2026-07-09~10)**: 17,156파일 전부, `form` 비어 있지 않은
  분석대상 **총 5,103,356발화**
  (2020: 870,437 / 2021: 1,373,920 / 2022: 866,359 / 2023: 677,262 /
   2024: 728,257 / 2025: 587,121). 연도별 CSV 파일 수 = 원본 JSON 파일 수
  전부 일치, 빈 분석값 0건 확인 (repair_empty_tagged.py 전수 검사). 원본 JSON
  utterance 5,157,997행 중 `form` 빈 54,641행은 입력 정책상 제외(7/24 전수 감사).
- 실행 기록: 처리 속도 77~104발화/초. 중단 2회(바른 무료 플랜 일일 한도
  초과 → 유료 플랜 전환; 외장하드 일시 분리) 모두 파일 단위 체크포인트로
  손실 없이 재개. 실패 재시도 기록 128건은 모두 재처리로 해소
- 출력: `D:\05_NIKL_DIALOGUE_bareun_2020-2025\01_bareun_raw\{연도}\{파일ID}.csv`
  - 스키마: `utt_id, speaker_id, form, tagged, n_morphs`
  - `tagged` 형식: 어절 간 공백, 어절 내 형태소 `+` 구분, 각 형태소는 `형태/태그`
    (어절-형태소 정렬 보존 → 형태음운론 분석에서 어절 경계 정보 활용 가능)
  - 연도별 `_speakers.csv`: 화자 메타데이터(성별·연령대·출생지·거주지·학력·직업)
  - 로그: `logs/run_log.txt`(타임스탬프·처리량), `logs/failed.csv`(실패 발화 전수 기록)
- 오류 처리: 배치 실패 시 지수 대기 후 3회 재시도 → 단건 폴백 → 그래도 실패 시
  빈 tagged로 기록하고 failed.csv에 남김 (누락의 전수 추적 가능)

### 3.3 의미번호 부여 (2차 레이어: 별도 산출물)

> **⚠️ 신뢰도 경고 (반드시 유의) — 우리 대화 말뭉치(모두의 말뭉치) 기반 의미별
> 빈도는 신뢰도가 낮다.** `sense_freq_dictionary.csv`의 코퍼스 빈도 컬럼
> (`freq_2020…freq_total`)과 `02_sense_annotated`의 다의어 sense 부여는 문맥 없는
> 추정(MFS `ls_*` 또는 사전순 1번 `lex_first`) 결과라, 다의어에서 소수뜻이
> 다수뜻으로 뭉개진다. **실측(내용어 29.2M 토큰): 확정(monosemous+lex_mono)
> 17.2% / 저신뢰 추정(ls_sxls+ls_all+lex_first) 72.6% / 미부여 10.1%** — sense 붙은
> 내용어의 약 4/5가 추정. **뜻별 빈도가 필요하면 코퍼스 값이 아니라 LS 참조 빈도
> (`freq_LS_spoken/all`)를 기준으로 쓰고**, 대상 토큰은 문맥 재판별할 것. 신뢰 구간은
> `method`(monosemous/lex_mono만 확실)·`confidence`(ls_*=숫자, lex_first=공란)로
> 식별. (단의어·기능형태소 태그 등 문맥 무관 정보는 영향 없음.)
> 부여 method 6종: not_target/monosemous/ls_sxls/ls_all(assign) +
> lex_mono/lex_first(supplement 보완 패스, not_found·ambiguous 재판정).

원칙: 1차(순수 바른 출력)와 물리적으로 분리 저장. 바른 분석 자체는 불변으로 보존하고,
의미번호는 파생 레이어로 부여한다 (분석기 출력과 사전 기반 추정의 구분 유지).
- 출력: `D:\10_LAYERS\02_sense_annotated\{연도}\{파일ID}.csv` (형태소 1개=1행, long)
  - 스키마: `utt_id, word_idx, morph_idx, morph, tag, sense_id, confidence, method, candidates`
- 스크립트: `scripts/python/assign_sense_layer.py` (입력자원: LS `08_ALL_morpheme_freq.csv`,
  어휘목록 v2 `01_NIKL_lexicon_full_v2.csv`)
- 부여 규칙 = `decide()`가 형태소마다 위→아래 순서로 판정, `method`로 근거 기록:
  1. `not_target` — 태그가 **J/E/S** 시작(조사·어미·기호) → 의미번호 대상 아님(빈칸)
  2. `monosemous` — 어휘목록 v2에서 (형태소,태그) 뜻이 **1개** → 확정, **confidence=1.00**
  3. `ls_sxls` — 다의어인데 **LS 구어(SXLS)** 출현 → **최빈 sense** 부여
  4. `ls_all` — SXLS 미출현·LS 전체(ALL) 출현 → 최빈 sense 부여
  5. `ambiguous` — 사전엔 다의, **LS 미출현** → 미확정, `candidates`에 후보만
  6. `not_found` — 어떤 자원에도 없음(빈칸)

**★ 신뢰도(confidence) 정의·해석 — 연구용 정본 (헷갈리지 말 것)**
- **계산식**: `monosemous`=1.00(사전상 단의). `ls_sxls`/`ls_all`= **최빈 sense 빈도 ÷
  그 (형태소,태그)의 LS 총빈도** = `dist.most_common(1)[0].freq / sum(dist)`.
- **해석**: 이 값은 **최빈의미(Most-Frequent-Sense, MFS) 기준선의 우세 비율**이며
  **문맥을 보지 않는다**. `confidence 0.80`은 "80% 확률로 정답"이 **아니라**
  "**LS에서 그 뜻이 80% 우세**"라는 뜻. 문맥 기반 WSD가 아님(빈도 기반 추정).
- **confidence(형태소별 우세비율) ≠ 76.4%**: 76.4%는 부여 결과를 **다층위 2025
  정답과 대조한 전체 정확도**(3.3.1/5절, 검증 단계 산출). 성격이 다른 두 수치.
- **연구 시 활용 지침**:
  - `monosemous`(1.00)는 안전. `ls_*`는 **자동 최빈값**이므로, 문맥상 의미가
    중요한 현상에서는 **그대로 신뢰하지 말고 청취/수작업 검증**할 것.
  - `ambiguous`·`not_found`는 sense 없음(강제 부여 안 함) → 분석 시 별도 처리.
  - 보고·필터는 `method`+`confidence` 컬럼으로: 예) "monosemous+ls_sxls(conf≥0.9)만
    사용" 식으로 표본을 통제하고 그 비율을 정량 보고.
- 한계: LS WSD는 내용어 대상(조사·어미 비부여). LS는 2020 자료 → 신어·이후 용법 미반영.

**★★ 연구 설계상 결정적 주의 — 동음이의어 빈도 효과 (2026-07-16, 사용자 확인)**
- **연구 핵심 가설 중 하나**: *동음이의어(같은 표면형·다른 뜻·다른 빈도)*에서도 빈도에
  따라 형태음운 변이가 갈리는가. → 분절형을 통제한 채 빈도만 대비하는 자연 실험.
  **따라서 sense per-토큰 판별이 옵션이 아니라 핵심 변수다.**
- **MFS(ls_*)의 치명적 한계 여기서 발생**: 동음이의어의 모든 토큰에 최빈뜻 하나를
  부여 → **소수뜻 토큰이 다수뜻으로 뭉개져** 보려는 대비 자체가 소멸. 대상
  동음이의어에는 `ls_*` 자동값을 **그대로 쓰면 안 됨.**
- **하위 의존성(중요)**: A3b 의미별 빈도(`build_sense_freq.py`)는 `02_sense_annotated`
  (=MFS)에서 `(morph,tag,sense_id,method)` 집계 → **다의어의 코퍼스 뜻별 빈도
  `freq_YYYY`는 MFS 편향 상속**(소수뜻 과소·다수뜻 과대). 단 **투명 설계로 격리됨**:
  ① `method` 컬럼이 ls_* 여부 표시, ② **LS 참조 뜻별 빈도 `freq_LS_spoken/all`은
  MFS와 독립**(LS 문맥 주석 기반)으로 별도 컬럼 보존.
- **usability 결론(폐기 아님)**: 인덱스 구조·`monosemous`·`freq_LS_*`는 그대로 유효.
  재판별 필요분 = **대상 동음이의어의 (a)토큰 sense (b)코퍼스 뜻별 빈도**뿐이며,
  `method=ls_*`+대상항목으로 **자동 선별**(candidates/confidence가 애매 토큰 표시).
- **권장 경로**: 뜻별 빈도 변수는 `freq_LS_*`(MFS 독립)를 우선 사용. 변이를 겪는
  대상 토큰만 **문맥 판별**(청취/수작업, 또는 LLM 문맥 WSD·LS 연어 규칙) → 소수 범위.

**★★★ 빈도 사용 원칙 + 예외 재판별 프로토콜 (2026-07-16, 사용자 결정)**
- **기본값**: 분석의 빈도 변수는 **형태소(form + 품사) 빈도**를 쓴다
  (`morpheme_freq_dictionary.csv`). 이는 sense 추정과 무관한 순수 카운트라 **완전 신뢰**.
  **다의어 뜻 구분은 기본적으로 하지 않는다**(사용자: 다의어까진 불필요).
- **품사 태그가 동음이의어를 대부분 자동 분리**: 예) 일/NNG(work)·일/NNB(날)·일/NR(하나).
  → 대부분의 "동음이의" 빈도는 (form,품사) 단위로 이미 신뢰 가능하게 갈림.
- **예외 = "품사까지 동일한데 뜻이 갈리는" 소수 형태소**. 특정 현상이 그 뜻 구분을
  실제로 요구할 때만, **그 형태소의 토큰만(전체 코퍼스 아님) 전면 재판별**한다.
  - 재판별 방법 = **LS + 다층위 2025 어절 WSD**를 기준/참조로 문맥 판별. 다층위는
    우리 발화의 부분집합(gold)이라 **재판별기(LLM 등)의 내장 검증셋** 역할.
  - **수동 판정 옵션(항상 열림)**: 정말 애매하면 그 (형태소,태그) 토큰의 **전량 KWIC
    추출**(02 필터→utt_id→01 발화 원문 조인, +A6로 wav·TextGrid 청취) 후 **사용자가
    수동 판정 → override 층**. 규모는 패턴히트/표본으로 조절(수만이면 전량 수동 비현실).
  - 규모 = (타깃 형태소) ∩ (패턴 히트) → 한 줌. **전체 재분석은 결코 아님.**
- **후보 목록(사전 산출)**: `10_LAYERS/03_freq_dictionaries/_polysemous_same_pos_candidates.csv`
  = LS에 뜻 ≥2인 (form,품사) **7,764종(코퍼스 출현)**. 단 이는 외연일 뿐 —
  거/NNB(1:37313,2:4)처럼 **실전 단의**가 많음. **진짜 애매 대상은 `confidence`(우세비율)
  낮은 것**으로 좁힌다(예 일/NNG 0.48, 이/VCP 0.60). 목록×confidence×패턴히트 = 실제 소수.
- **빈도 신뢰 등급**: ✅형태소(품사)빈도 / ✅monosemous·lex_mono / ✅LS 참조 뜻별빈도
  `freq_LS_*`(단 LS 기준) / ⚠️다의어의 코퍼스 뜻별빈도(ls_*·lex_first, 재판별 전).
  "말뭉치 빈도 전체가 저신뢰"가 아니라 **"다의어를 뜻별로 쪼갠 코퍼스 빈도"만** 조심.

### 3.4 빈도사전
- 스크립트 `scripts/python/build_freq_dictionaries.py`. **count(연도별)→merge** 2단계
  (저사양 RAM 대비). 출력 `10_LAYERS/03_freq_dictionaries/`.
- 세는 단위: 형태소=**(형태소,태그)** 전수 / 어절=**(표면형,top분석)**, 단 표면·형태소
  토큰 수가 **정렬될 때만** 어절 카운트(오정렬 발화는 어절 skip, 형태소는 전수).
- 산출: 분석대상 발화 5,103,356 / 형태소 토큰 50,955,889 /
  고유(형태소,태그) 165,920 / 고유 어절 857,443.
- 형태소 사전 컬럼: `morph,tag, freq_2020…freq_total, freq_MP_spoken/written,
  freq_LS_spoken/all, freq_ML2025_spoken/written, freq_KoFREN_all/young/child/elderly,
  KoFREN_log10, sense_id/conf/method, etym_type/origin, roman, roman_mfa, ipa`.
  로마자 폴백순 MP→LS→lexicon. IPA=roman_mfa를 수정가능표 `_roman_mfa_to_ipa.csv`로 변환.

**★ 빈도사전 신뢰도 지도 — 연구용 정본 (어느 열을 믿나, 2026-07-16 사용자 요청)**

| 신뢰 | 파일·열 | 근거 |
|---|---|---|
| ✅✅ **최상** | `morpheme_freq_dictionary`: `morph,tag`, **`freq_2020…freq_total`** | 우리 코퍼스 (형태소,태그) 순수 카운트, sense 무관. **연구 주력 변수** |
| ✅ 믿음 | `eojeol_freq_dictionary`: `eojeol`, `freq_*` | 표면 어절 카운트. 단 정렬 실패 발화 어절은 미세 누락(형태소는 전수) |
| ✅ (외부) | `freq_MP_*`/`freq_LS_*`/`freq_ML2025_*`/`freq_KoFREN_*` | **규준 코퍼스** 빈도 — 우리 게 아님. 비교·규준용 |
| ✅ 대체로 | `etym_type`(어종 고유/한자/외래) | 사전 기반, 안정적 |
| ⚠️ 조건부 | `etym_origin`(한자어 원어) | 자동 재분석(`/?`) 주의 |
| ⚠️ 조건부 | `roman`/`roman_mfa`/`ipa` | **철자 기반=기저형 표기**(음운규칙 미적용). 실현 판정이 아님. MFA TextGrid도 후보 위치 확인용 분절이며 최종 실현은 연구자가 판정. IPA는 변환표 의존 |
| ⚠️⚠️ **조심** | `sense_freq_dictionary`: 코퍼스 `freq_YYYY`(다의어), `morpheme_freq`의 `sense_id/conf/method`(ls_*·lex_first) | 문맥 없는 MFS 추정. **monosemous/lex_mono만 신뢰**. 뜻별빈도는 `freq_LS_*` 사용 |
| ✅ (층화는 메타 의존) | `morph_freq_stratified`(층화 per_million)·`morph_dispersion`(분산도 n_docs) | 우리 코퍼스 형태소 카운트 파생. 분산도=순수 문서카운트 완전신뢰. 층화=**우리 코퍼스(NIKL 일상대화) 화자·사용역 메타** 조인(성별/연령/사용역, `미상` 존재, per_million 정규화 필수). **KoFREN과 무관**(KoFREN은 외부 비교컬럼일 뿐). 일상대화·여성·20대가 큼 |

- **한 문장**: 가장 믿을 열 = `morpheme_freq`·`eojeol_freq`의 **`freq_*`(형태·어절 빈도)**.
  가장 조심할 열 = `sense_freq`의 다의어 **`freq_YYYY`**와 모든 **`sense_*`**.
- **형태음운 유의**: 발음 표기열(roman/ipa)은 **기저형** — 변이 분석은 이 기저 vs MFA 표면 대조.
- **★ 형태소·의미기호 빈도의 조건부 신뢰(사용자 정리 2026-07-16)**: 대화말뭉치에서 뽑은
  형태소·의미 빈도는 **기본적으로 100% 신뢰 불가**. F1 0.929는 **2024/다층위(정제 대화)
  전역 평균**이라, 희귀어·구어특유(축약·간투사·비문)·비표준·비-gold 연도/레지스터는 태거
  오류·체계적 편향 위험(gold 밖이라 F1도 못 잡음). **흔한 형태의 집계는 신뢰**, 타깃 형태는
  **KWIC 태깅 점검 + 외부 규준(KoFREN·MP·LS) 대조**로 보완. 보고 시 F1의 검증 범위(2024/
  다층위 레지스터) 명시. **결론: 코퍼스 빈도는 기준 삼되, 외부 규준을 참고·대조 자원으로.**

### 3.4b 메타데이터 인덱스 (A4) — 사용역 정규화
- `04_metadata_index/file_meta.csv`(문서 단위, `build_metadata_index.py`): file_id·doc_id·
  year·`category`·**`category_norm`**·topic·date·relation·speaker_ids. 화자 메타는 연도별
  `_speakers.csv`(age·sex·occupation·birthplace·residence·education).
- **category 표기 변이 정규화(2026-07-16)**: raw `category`에 마디 내부 공백 변이가 있어
  같은 사용역이 쪼개짐 → `norm_category()`로 공백 제거·정규화한 **`category_norm` 추가**
  (원본 보존). 결과: `구어 > 사적대화 > 일상대화` **14,397**(3표기 통합) / 협력적대화 1,324 /
  공적대화>독백 760 / 비통제대화 417 / 사적대화>독백 258. **분석·검색은 `category_norm` 사용.**
- **담화 유형 컬럼 `discourse_mode`(2026-07-16)**: leaf가 '독백'이면 독백, 아니면 대화.
  → **대화 16,138 / 독백 1,018**. 독백/대화는 순서교대 유무 = 형태음운 변이에 중요한 구분
  (독백이 중간 라벨 "공적대화"에 묻혀 있던 것을 명시화).
- **다층위 연결 표시 `in_ml2025_gold`(2026-07-16)**: file_id가 다층위 2025 gold에 속하면 True.
  = **우리 코퍼스 중 공식 gold로 검증된 부분 = 75문서·16,439발화**(대화 63/독백 12, 전부 2024).
  → "믿을 수 있는 2024 부분"(F1 0.929 검증 대상)을 데이터에서 바로 필터 가능.
- 위 3컬럼은 `build_metadata_index.py`에 반영(재생성 지속). gold 표시는 gold_index 존재 시 자동.
- **세션 좌표 정본과 원자료 오류 보존(2026-07-24)**: 2023 JSON 4개의 최상위 `id`가
  직전 파일 ID로 오기되어 구 인덱스에 중복 4행·세션 메타 누락 4건이 생긴 것을 전수 집합
  대조로 발견했다. 배포 파일명 stem과 내부 document/utterance ID가 일치하므로 stem을
  `file_id` 정본으로 사용하고, 최상위 원값은 `source_top_id`에 보존한다. 새 빌더는 내부 ID,
  17,156개 순서·중복·행수를 검증한 뒤 원자 교체한다. 구판은
  `04_metadata_index/_archive/metadata_fix_top_id_20260724`에 보존했다.

## 3.5 강제정렬 (MFA) — 모델 동일성 확인 (2026-07-11)
- 음향 모델: **korean_mfa v3.0** (GMM-HMM, 2024-02-17 학습, MFA 공식 배포)
- 발음 사전: korean_mfa.dict (모델과 함께 2026-02-18 다운로드)
- **전 연도(2020-2025) 동일 파일 사용 확인**: 모델·사전 파일이 2026-02-18
  다운로드본에서 변경된 적 없음 (파일 타임스탬프 검증). 2020-2024 정렬
  (2026-02~03)과 2025 정렬(2026-07)이 같은 모델·사전으로 수행됨
- 실행: MFA 3.4.0, --num_jobs 4, 화자 단위 = 녹음 세션
  (--speaker_characters 14, 구 파이프라인의 세션 폴더 방식과 동일 효과)
- 텍스트 처리: `--no_tokenization` — 입력 .lab이 이미 바른 형태소 단위로
  분할되어 있어 MFA 내장 한국어 재토큰화(mecab)를 비활성화. 2020-2024
  words tier도 lab 그대로 정렬돼 있어(재토큰화 흔적 없음) 방식 일치.
  (부수 기록: mfa 환경의 soundfile DLL 파손을 재설치로 복구, 2026-07-11)
- TextGrid 산출(2025): MFA 내장 export가 Windows/sqlite 환경에서 교착해
  (database is locked; 작업자 유휴 확인), 정렬 DB(word_interval 1,079만 /
  phone_interval 2,659만 행)에서 **자체 스크립트(merge_textgrid_v2.py)로
  직접 생성**. 분절 시간·라벨은 MFA 계산 결과 그대로이며 표준 3-tier
  (words/phones/utterance)로 기록. 표본 대조로 형식·내용 검증 (2026-07-14)
- **정렬 커버리지 (전수 확정, 2026-07-14 인벤토리)**: 발화 5,103,356 중
  음성+TextGrid 완비 5,074,914 (**99.44%**). 연도별: 2020 99.54% /
  2021 99.88% / 2022 99.95% / 2023 96.98% / 2024 99.91% / 2025 99.79%.
  탈락 유형: 정렬 불가(wav 있음) 26,979 + 음성 원본 없음 1,463(2020 세션
  1개·2023 세션 4개분). 2023의 높은 탈락(19,517)은 재정렬로 대부분 회수
  → **§3.8에서 재정렬 완료(커버리지 99.94%)**. 근거: coverage_{연도}.csv
  근거 파일: D:\10_LAYERS\05_audio_index\coverage_{연도}.csv
  → 모든 음성 분석은 이 인벤토리 기준으로 발화를 필터링한다

## 3.7 TextGrid tier 통일 완료 (2026-07-15)
- 2020-2024 구판(6-tier, 구식 morphs 포함)을 표준 v2(3-tier:
  words/phones/utterance)로 전량 재생성 (retrofit_textgrid_2020_2024.py,
  원천: MFA 원출력 + 바른 form). 실패 0, 연도별 세션 수 원천과 전부 일치
  (2024는 파일 수 727,628로 인벤토리와 정확히 일치 확인)
- 구판은 90_ARCHIVE로 이동 보존. **여섯 연도(2020-2025)가 동일 표준
  TextGrid 체계를 갖춤** — STANDARD_textgrid_tiers.md 기준
- 형태소·의미 정보는 tier가 아닌 레이어(utt_id 조인) 원칙 유지;
  필요시 주입 유틸(inject_tiers, 작성 예정)로 추가

## 3.8 정렬 실패분 재정렬 (2026-07-16)
- 1차에서 탈락한 발화(wav 있음·TextGrid 없음) 26,979개를 대상으로, 실패
  발화만 별도 코퍼스로 재구성(바른 형태소 .lab 재생성 + wav 하드링크)해
  **빔 확대 재정렬**(--beam 100 --retry_beam 400; 잔여는 300/1000). 동일
  모델·사전(korean_mfa v3.0)·`--no_tokenization`. 산출은 기존과 동일 표준
  3-tier로 변환해 06_textgrid_merged에 병합(기존 파일 미덮어씀).
- **회수 25,244 / 26,979 (93.6%)**. 연도별: 2020 3,426 / 2021 589 /
  2022 437 / 2023 18,943 / 2024 628 / 2025 1,221.
  → 전체 정렬 커버리지 **99.44% → 99.94%** (5,100,158 / 5,103,356).
- 미회수 1,735의 확정 분류(원본 PCM 실측, `check_source_pcm.py`):
  - **원본 음성 결함 1,296**: 원본 PCM 자체가 0.1s 토막(대부분 3,196 bytes) —
    NIKL 배포본의 음성 원본이 잘림. 재추출·재정렬 모두 불가. 특히 2021의
    4개 세션(1,017발화, SDRW2100003249/1747/1872/2153)이 세션 통째 결함 →
    **음성분석 제외 대상**.
  - 난정렬 405: 정상 wav이나 빔 1000에도 실패(OOV·소음·중첩 추정).
  - 빈 lab 34: 문장부호만 → 정렬 대상 없음.
- 실행 절차·근거: `RUNBOOK_MFA_realign_2020-2025.md`,
  근거 CSV `05_audio_index\{alignment_quality_realign_*, source_pcm_check}.csv`.
- 정렬 품질통계(로그우도·음소길이편차·SNR)를 발화별로 보존 →
  음성분석 시 이상치 사후 필터 기준으로 사용.

## 3.6 다층위 2025 기준 규준 구축 (2026-07-14)
- 다층위 MP·WSD 레이어에서 2025년판 참조 빈도표 3종 생성
  (`00_RAW\reference\NIKL_Multi-layered_2025_v1.0\freq\ML2025_*.csv`):
  형태소 45,118항 / 어절 112,858항 / 의미 47,372항.
  **어절 토큰 336,955 (문어 227,002 / 구어 109,953)**
- sense_id 표기 정규화: "002"→"2" (LS 2020과 통일; 888 등 특수코드 유지)
- 표본 대조에서 LS 2020과 의미번호 일치 확인 (예: 이/4/VCP) —
  본격 일치율·변동 검증은 5절 계획대로
- 위상: LS 2020(대규모)의 병렬 규준(최신 기준·소규모) — 대체 아님

## 3.8 다층위 gold 레이어 수입 — "프리미엄 표본" (2026-07-15)
- 다층위 구어부 16,439발화(2024 부분집합)의 공식 주석을 utt_id 키 CSV로
  수입: `10_LAYERS\06_multilayer_gold\` — gold_mp(205,295) /
  gold_wsd(86,335) / **gold_dp 구문 의존구조(109,953어절)** /
  gold_srl(49,709) / gold_za(24,871)
- 의의: 이 발화들은 음성·음소정렬·형태소·의미(gold)·구문·의미역을 모두
  갖춘 **완전 적층 표본** — 형태음운 변이의 구문 경계 변수(예: ㄴ삽입과
  구 경계), 운율(추가 시)과 구문의 상호작용 분석에 직접 사용
- 빈도사전에도 다층위 규준 반영: morpheme_freq_dictionary에
  freq_ML2025_spoken/written 컬럼 추가 (2026-07-15 merge 재생성)

## 4. 이전 분석과의 차이 (재분석 사유)
- 기존: `D:\04_00_NIKL_DIALOGUE_MFA\02_csv\nikl_dialogue_corpus_morphs.csv`
  (2020-2024, 이전 분석기) — 2025년 미포함, 의미번호 없음
- 재분석: (1) 2025년 포함 6개년 통일 분석, (2) 바른(최신 상용 수준 분석기) 사용,
  (3) 어절-형태소 정렬 보존 형식, (4) 의미번호 레이어 추가, (5) 전 과정 로그·
  실패 전수 기록으로 재현성 확보

## 5-결과. 다층위 2025 기반 검증 (2026-07-15 완료)
- 방법: 다층위 구어부 16,439문장이 본 말뭉치 2024 발화의 부분집합임을
  확인(ID 100% 일치) → 공식 주석을 gold로 발화 단위 직접 채점
  (validate_with_multilayer.py)
- **형태소** (바른 vs 공식 MP, (형태,태그) 다중집합): 전체 F1 0.909;
  **다층위 정제로 문장이 변형되지 않은 부분집합(12,861문장) F1 0.929**
  (P 0.928 / R 0.930). 문장 완전일치 42.6%
- **의미번호** (우리 레이어 vs 공식 WSD): 전체 76.4%. 방법별 —
  monosemous **100.0%** (9,170/9,170), ls_sxls 72.9%, ls_all 81.3%,
  lex_first 47.8%. → method 컬럼으로 확정/잠정을 구분해 사용하는 설계의
  타당성 입증. monosemous 100%는 우리말샘 번호 체계가 LS 2020↔다층위
  2025 간 실질 변동 없음을 함의 (보정표 불필요 판정)
- 특수코드(777 고유명사 등) 3,845건 제외, 미부여·형태불일치 10,033건
- 불일치 표본: 05_audio_index/validation_{mp,sense}_mismatch_sample.csv

## 5. 검증 계획 (예정, 결과 추가)
- [ ] 태그셋 대조: 바른 출력 태그 전수 목록 ↔ MP/다층구조 태그 목록 대응표
- [ ] 의미번호 최신성 검증 (2026-07-14 추가): 다층위 2025의 어휘의미 주석은
      최신 지침·우리말샘 기준 → 우리 의미번호(LS 2020 분포 기반)와 일치율
      측정 + 번호 체계 변동 항목 대조. 다층위 전체판 배포 여부 확인
- [ ] 일치율: 다층구조 말뭉치(2025) 샘플 문장을 바른으로 분석, NIKL 공식
      형태 분석과 형태소 경계·태그 일치율 측정 (문어 NXML/구어 SXML 각각)
- [ ] 의미번호 커버리지: 방법별(monosemous/ls_sxls/ls_all/unresolved) 비율 보고
- [ ] failed.csv 전수 검토

## 6. 실행 명령 (재현용)

```powershell
# 전체 (중단 후 재실행하면 이어서 진행)
& "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke\.venv\Scripts\python.exe" `
  "C:\Users\ari30\Dropbox\000_2026_summer_research\scripts\python\bareun_dialogue_full.py"

# 특정 연도만
#   ... bareun_dialogue_full.py --year 2025
```

### 3.3.1 의미번호 부여 검증 (2026-07-09)
- 스크립트: `scripts/python/assign_sense_layer.py`
- 검증: 2020년 1파일(형태소 토큰 2,987개)
  - not_target(조사·어미·기호) 46.3% / ls_sxls 34.2% / monosemous 8.0% /
    ambiguous 6.6% / not_found 4.1% / ls_all 0.7%
  - **내용어 기준 부여율 80.1%** (1,285/1,604)
- 자원 규모: LS (형태소,태그) 94,068개 / lexicon v2 (word,pos) 564,387개
- **전체 실행 완료 (2026-07-10)**: 17,156파일, 형태소 토큰 50,952,902개
  - not_target(조사·어미·기호) 42.7% / ls_sxls 34.2% / monosemous 9.8% /
    ambiguous 6.5% / not_found 6.1% (ls_all ~0.7%)
  - **내용어 기준 의미번호 부여율 약 78%** — 파일럿(80.1%)과 일관
- **보완 패스 (2026-07-10, supplement_sense_layer.py)**: not_found/ambiguous
  재판정. XSV/XSA 접미사는 lexicon 표제어의 '-다' 제거형으로 색인해 매칭.
  결과: lex_mono(신규 확정) 61,300 / lex_first(다의어 첫 의미 잠정, 후보
  보존) 3,436,036 / not_found 잔여 2,948,444 (우리말샘 미수록 고유명사·
  신어·비표준형 — 의도적으로 미부여).
  **최종 내용어 커버리지 약 90%** (확정·LS 78% + 잠정 lex_first 12%).
  method 컬럼으로 확정/잠정 구분 가능 — 분석 시 선택적 사용

## 7. 변경 이력
- 2026-07-09: 문서 생성. 파일럿·검증 실행 완료, 전체 실행 대기.
- 2026-07-09: 의미번호 부여 스크립트 작성·검증 (3.3.1절). 빈도사전에
  로마자(word_roman/word_roman_mfa) 및 IPA 변환 컬럼 추가 예정.
