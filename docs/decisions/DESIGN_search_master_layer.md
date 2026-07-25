# 설계: 검색 마스터 레이어 (05_search_master) — 2026-07-23 확정

목적: **CSV 한 층위에서** 사회변수·형태소·철자열·발음열을 함께 검색하고,
매치된 발화의 위치(utt_id → wav·TextGrid)를 즉시 추적하는 것. 현
`01_bareun_raw`(utt_id/speaker_id/form/tagged/n_morphs)에는 사회변수·발음
정보가 없어 이 기능을 못 하므로, **레이어 불변 원칙대로 그 위에 새 층위를
얹는다** (기존 레이어 수정 없음).

관련: DATA_LAYOUT.md(좌표계), 사회변수_코드북.md(정규화 컬럼),
STANDARD_textgrid_tiers.md(tier 표준), RUNBOOK_MFA_eojeol_realign.md(4-tier),
TODO_A단계.md(G2P 트랙).

---

## 확정 결정 4건 (2026-07-23, 사용자)

| # | 결정 | 내용 |
|---|---|---|
| 1 | 로마자 체계 | **기존 roman_mfa 체계 재사용** — 빈도사전·1기 산출물과 일관, `_roman_mfa_to_ipa.csv`로 IPA 병기 가능 |
| 2 | 예측 발음열 | **필수(의무) 규칙만 적용한 단일 기준열** — ㄴ삽입 등 수의적 변이는 미적용 상태로 두고, B단계에서 연구자의 수동 실현 판정과 대조 |
| 3 | 행 단위 | **발화 1행 + 어절 정렬 병기** — 문자열 컬럼은 어절별 공백 구분, i번째 어절끼리 대응 |
| 4 | 저장 형식 | **세션별 CSV(정본) + 연도별 Parquet 미러(검색용)** — DuckDB로 정규식 검색, 미러는 언제든 재생성 가능 |

---

## 1. 레이어 배치

```
D:\10_LAYERS\05_search_master\
   {연도}\{세션ID}.csv          ← 정본 (발화당 1행, 사람이 열람 가능)
   _parquet\{연도}.parquet      ← 검색 미러 (재생성 가능 파생물)
   _parquet\search_master_all.parquet ← ★전 연도 단일 파일 (보관·분석용, 2026-07-23 추가)
   _build_meta.json             ← 생성 일시·입력 레이어 버전·검증 결과
D:\10_LAYERS\06_actual_pron\    ← 역사적 임시명. MFA phones·시간정보 보조 레이어
                                   (사람의 최종 실현 판정값이 아님; 구현 전 명칭 재검토)
   {연도}\{세션ID}.csv
```

**단일 파일 방침(2026-07-23 사용자 요청)**: 세션별 CSV(정본)와 별개로,
6개년 전체를 담은 **단일 파일**을 함께 산출한다. 형식은 Parquet 1개
(`search_master_all.parquet`, 510만 행 — 압축돼 수백 MB 수준, DuckDB·R
arrow에서 그대로 분석 가능). 장기 보관·타 도구 호환용으로 **단일 CSV
내보내기 스크립트 옵션**(`--export-csv`, GB급 1파일)도 두되, 상시 유지는
Parquet만 한다(중복 정본 방지 — CSV 내보내기는 필요 시 재생성).

- v1(마스터)과 MFA phones·시간정보 보조 레이어는 **별도 레이어**로 두고
  `utt_id`로 조인한다. 마스터를 덮어쓰지 않으므로 재정렬이 재작업되어도
  마스터는 불변이다.
- 변이 연구의 분석값은 이 두 층의 단순 차이가 아니라, 연구자가 음성과
  TextGrid를 직접 검토해 만든 수동 실현 판정이다.

## 2. 컬럼 명세 — v1 마스터 (발화당 1행)

| 묶음 | 컬럼 | 출처 |
|---|---|---|
| 추적 | `utt_id, year, session_id, utt_seq` | 좌표계 규약 (utt_id에서 유도) |
| 대화 문맥 | `dialogue_id, dialogue_speaker_ids, n_dialogue_speakers` | 원본 JSON document ID와 그 document의 발화자 집합 |
| | `co_speaker_ids, n_co_speakers` | 현재 `speaker_id`를 제외한 공동 참여자 ID. 직접 수신자 표지는 아님 |
| | `has_wav, has_tg_eojeol, quarantined` | coverage 인벤토리 + mfa_eojeol/quarantine |
| 문서 | `category_norm, discourse_mode, topic, relation, date, in_ml2025_gold` | 04_metadata_index/file_meta.csv |
| 화자 | `speaker_id, sex, age_norm, occupation_norm, education_ord, birthplace_norm, current_residence_norm` | speakers_normalized.csv (utt의 speaker_id로 조인) |
| 텍스트 | `form, tagged, n_morphs, n_eojeol` | 01_bareun_raw |
| | `original_form` — 원전사(축약·수 표기·모음변이 등 실발화 표기. 1기 표본에서 form과 **31.2% 상이**) | ★원본 JSON (1기 대조로 추가, 2026-07-23) |
| | `start, end, dur` — 세션 오디오 내 발화 시간(초)·지속시간 (발화속도 공변량) | ★원본 JSON (〃) |
| | `note` — 전사 비고(예: `발화겹침` ≈7.9% — 음향 분석 제외 필터) | ★원본 JSON (〃) |
| 철자열 | `form_roman` — 표기 자모의 전자(轉字), roman_mfa 기호 | 신규 생성 |
| | `tagged_roman`(선택) — 형태소 경계(+)·태그 보존 roman (1기 morphs_roman 상당 — 형태소 경계 환경 검색용) | 신규 생성 (사용자 승인 시) |
| 예측발음 | `pron_pred_hangul` — 규칙 적용 후 한글 표면형 (예: 것을→거슬) | 신규 생성 |
| | `pron_pred_roman` — 위의 roman_mfa 표기 | 신규 생성 |
| | `pron_pred_ipa` — `_roman_mfa_to_ipa.csv` 변환 | 신규 생성 |

### 숫자·혼합표기 reference 열 — 2026-07-25 수동 검토 반영

기존 form 기반 열은 재현성과 감사 때문에 덮어쓰지 않는다. 숫자·기호가 포함된
어절 전체가 `∅`가 되어 한글 부분까지 소실되는 경우에만 `original_form`을
대체 입력으로 시험하고, placeholder 수가 실제로 줄어들 때 다음 열에 채택한다.

| 열 | 내용 |
|---|---|
| `pron_reference_form` | reference 계산에 실제 사용한 form 또는 original_form |
| `pron_reference_form_roman` | 위 입력의 철자 전자 |
| `pron_reference_hangul` | 위 입력의 규칙 기반 한글 기준 발음 |
| `pron_reference_roman` | roman_mfa 기준 발음 |
| `pron_reference_ipa` | IPA 기준 발음 |
| `pron_reference_source` | `form_rule_prediction` / `original_form_placeholder_resolution` |
| `pron_reference_status` | `resolved_form` / `resolved_original_form` / `unresolved_symbol` |
| `pron_reference_n_eojeol` | reference 입력의 어절 수 |

숫자 읽기를 기계적으로 추측하지 않는다. 원전사에도 근거가 없으면
`unresolved_symbol`로 남긴다. 이 열은 lexicon 사전 발음 층과 실제 실현 판정
층을 대체하지 않는다.

### 어절 정렬 규약 (문자열 컬럼 공통) — 2026-07-23 개정(A3 정합 검토 반영)
- **모든 문자열 컬럼의 어절 수 = n_eojeol** (생성 시 전수 검증).
- 한글 컬럼(form·original_form·pron_pred_hangul): 어절 구분 = 공백 (원문 그대로).
- **로마자·IPA 컬럼: 기존 빈도사전 표기 관행을 그대로 따른다** —
  음소 구분 = 공백, 음절 경계 = ` - `, 초성 대문자/종성 소문자
  (`_roman_mfa_to_ipa.csv` 관행). 음소가 공백을 쓰므로 **어절 구분은 ` | `**.
  예: 것을 → 예측발음 `G EO - S EU L`, 두 어절 "먹은 것" → `M EO - G EU N | G EO t`.
  (초안의 `GEOS.EUL`식 붙여쓰기·`.` 음절 표기는 **폐기** — 기존 산출물·IPA
  변환표와 어긋남.)
- 철자 전자(form_roman)에는 발음 표기에 없는 종성 토큰(ㅅ·ㅈ·ㅊ·ㅋ·ㅌ·ㅍ·ㅎ·
  겹받침 등 미중화형)이 필요 → `_roman_mfa_to_ipa.csv`에 '철자 전용' 표시로
  토큰 추가 등록(표가 수동 편집 전제로 설계돼 있어 그대로 활용).
- 숫자·외국어·비언어 어절은 자리 표시자 `_`(어절 수 정렬 보존) —
  lab 생성기의 제외 대상과 동일 기준.
- 매치 위치 → 어절 번호(| 개수) → TextGrid words tier(어절)와 직결.

### 예측 발음의 이원 구성: 사전 발음 + 경계 규칙 (2026-07-23 추가)
규칙만으로는 어휘부 예외를 못 잡는다 — 예: 한자어 경음화(성과[성꽈]류),
표준발음 복수 인정형, 관용 발음. 따라서 **예측 발음열 = ① 형태소별 사전
발음(1기 어휘목록 `01_NIKL_lexicon_full.csv`, 53만 항 — 우리말샘·표준대사전
발음, roman 두 체계) 우선 조회 + ② 형태소·어절 경계에서 필수 규칙 적용**의
이원 구성으로 한다. 사전에 없는 항목(신조어 등)만 전면 규칙 폴백.
- **어휘목록 실측 (2026-07-23, 1,296,777행·280MB 전수 스캔)**:
  - 발음 커버리지: `pron_1`(사전 표준발음) 47.3% + `pron_g2p`(1기 자체 G2P
    보완) 52.7% = **전 항목 발음 보유**. `pron_2`(복수 인정형) 3.2%.
  - `pron_1`에 어휘부 예외가 실려 있음 확인 (예: ㄱㄴㄷ순→[…쑨] 합성어 경음화).
  - `morph_dict`/`morph_analysis` = **표제어 내부 형태 경계**(ㄱㄴㄷ-순/NNG 등)
    → 어절 내부 합성어 경계 판별 자료 (ㄴ삽입·사잇소리 B단계에 직결).
  - `origin`/`origin_lang`(어원), `freq_MXLS/NXLS/SXLS`, `in_stdict`, `urimal_id`.
  - ⚠ 이 파일의 roman(`word_roman`·`pron_*_roman`)은 **서울코퍼스식 소문자
    체계**(k0·xx·vv)로 roman_mfa(대문자)와 다름 → 체계 혼용 방지 위해
    **한글 발음(pron_1)을 자모 매핑으로 roman_mfa에 직접 변환**해 쓰고,
    lexicon roman 컬럼은 참조 전용.
  - 조회 키: (word, pos_tag, sense_no) — sense·빈도원 중복행 dedup 필요.
    표제어(사전형) 수준이므로 활용형은 어간·어미 발음 + 경계 규칙으로 결합.
- 어휘목록 이동: Dropbox `000_NIKL_2026/00_01_1차_archive/02_DICTIONARY/` →
  `D:\00_RAW\reference\03_lexicon_1기\` 복사, paths.json `lexicon_full` 키 등록.
  기존 `reference_dictionary`(00_DICTIONARY)와의 판본 관계 확인.
- 부수 효과: 사전 발음은 후보 검색과 표준발음 기준선 구성에 쓸 수 있다.
  단, MFA phones와의 차이를 곧바로 변이의 실현값으로 해석하지 않는다.
  실현 여부는 연구자가 음성과 TextGrid를 직접 검토해 별도 층에 판정한다.

### 예측 발음 규칙 인벤토리 (★사용자 검토 대상 — 음운론적 판단)
필수(의무) 규칙만 적용한다는 원칙 하에, 적용 후보 목록 초안:
음절말 평폐쇄음화(중화), 연음(재음절화), 장애음 비음화(국물→궁물),
유음화(신라→실라), ㄹ비음화(담력→담녁), 장애음 뒤 경음화(국밥→국빱),
구개음화(굳이→구지), ㅎ축약·탈락, 겹받침 단순화.
**미적용(수의적 — 연구 대상)**: ㄴ삽입, 사잇소리/합성어 경음화, 수의적
위치동화(신문→심문류), 모음 관련 수의 현상.
→ 각 규칙의 필수/수의 판정과 적용 순서(feeding 관계 포함)는 **파일럿 출력
표본으로 사용자가 확정** 후 METHODS에 기록. 1기 `utils_phonology.py`(참고:
reference/colab_search)를 출발점으로 재작성.

## 3. 컬럼 명세 — MFA 분절 보조 레이어 (재정렬 완료 연도부터)

| 컬럼 | 내용 |
|---|---|
| `utt_id` | 조인 키 |
| `pron_mfa` | 4-tier phones tier의 음소열, **어절 정렬(공백 구분)** — words tier 경계로 어절 분할 |
| `pron_mfa_ipa` | 위의 IPA 표기 |
| `n_spn, spn_ratio` | spn 구간 수·비율 (G2P 품질 지표 — 검색 시 필터) |
| `align_status` | ok / partial / missing / quarantined |

- 입력: `06_textgrid_eojeol`(어절 4-tier, **G2P 적용 재정렬본**).
- G2P 파일럿 → 재정렬 트랙(TODO 최우선 항목)과 병행하되, **v1 생성은 MFA와
  완전 독립**이므로 먼저 진행 가능.

## 4. TextGrid 쪽 결정 (변경 없음 — 재확인)

- **어절 4-tier 유지**: words(어절)/phones(G2P 사전으로 정렬된 대략적
  음소 라벨·시간)/morphemes/utterance. phones는 자동 실현 판정값이 아니다.
- 예측 발음열·로마자·사회변수는 tier로 넣지 않음 — 슬림 표준 원칙("시간
  정렬이 본질인 정보만 tier로") 유지. 검색은 CSV, 시간·소리는 TextGrid,
  다리는 utt_id + 어절 번호.
- 운율(IP/AP)은 기존 계획대로 분석 대상 발화에만 5번째 tier 온디맨드.
- STANDARD_textgrid_tiers.md의 "words=형태소" 기술은 목적 B(words=어절,
  morphemes tier 신설) 반영해 갱신 필요.

## 5. 생성 파이프라인 (신규 스크립트)

| 순서 | 스크립트(안) | 역할 |
|---|---|---|
| ① | `build_search_master.py` | 01_bareun_raw + file_meta + speakers_normalized + 인벤토리 → 세션별 CSV. 연도·세션 체크포인트 재개, paths.json 사용 |
| ② | (①에 내장) 발음열 생성 모듈 `predict_pron.py` | form(+tagged 어절 경계) → 철자열·예측 발음열. 규칙별 on/off 플래그로 구현(검증·규칙 확정에 활용) |
| ③ | `build_search_parquet.py` | 세션 CSV → 연도 Parquet 미러 (DuckDB/pyarrow) |
| ④ | `extract_actual_pron.py` | 06_textgrid_eojeol → v2 레이어 (재정렬 완료 연도부터) |

검증(①에 내장): 행 수 = 01_bareun_raw 발화 수 전수 일치 / 문자열 컬럼 어절
수 = n_eojeol 전수 일치 / 사회변수 조인 무결(결측은 `미상`) / 표본 30발화
발음열 사용자 육안 검토.

### 검색 사용 예 (DuckDB, 8GB RAM에서 초 단위)
```sql
-- 어절 경계 ㄴ삽입 후보: 자음 종성 어절 + i/j 시작 어절 (예시 골격)
SELECT utt_id, form, pron_pred_roman, category_norm, sex, age_norm
FROM '05_search_master/_parquet/*.parquet'
WHERE regexp_matches(pron_pred_roman, '[A-Z]+(C종성패턴) (I|Y)')
  AND discourse_mode = '대화';
```
→ 결과 utt_id를 `locate_utt.py` / `fetch_audio_for_search.py`에 넘겨
wav+TextGrid 청취·판정.

## 6. 실행 순서

1. **파일럿**: 2020 세션 2~3개 → CSV 실물 표본을 사용자 검토(기호·구분자·
   규칙 인벤토리 확정) ← 대량 작업 전 파일럿 원칙
2. **전량 생성**(밤샘, 연도별 체크포인트): 510만 발화 — 텍스트 연산이라
   MFA와 무관, SSD에서 수 시간~하룻밤 예상
3. **Parquet 미러** 생성 + 검색 쿼리 템플릿 정비
4. (병행 트랙) **G2P 파일럿 → 재정렬** — 완료 연도부터 MFA 분절 보조 레이어 ④
5. B단계 검색은 이 레이어 기준으로 재작성 (구 Colab 검색 대체)

## A3 빈도사전 구축 시 확정 사항과의 정합 검토 (2026-07-23)

`build_freq_dictionaries.py` 정독 결과 — 그때 함께 정한 것들을 마스터
설계에 그대로 승계/재사용한다:

1. **IPA 변환표가 정본 토큰 집합**: `03_freq_dictionaries/_roman_mfa_to_ipa.csv`
   (수동 수정 가능하게 설계됨, 초성 대문자·종성 소문자·음절 `-`). predict_pron
   출력 토큰을 **이 표의 집합으로 강제**하고, 미정의 토큰은 빈도사전과 같은
   방식(`⟨기호⟩` 표시)으로 드러나게 한다 — 표기 체계가 사전·마스터에서 단일화.
2. **로마자 조회 우선순위 재사용**: MP → LS → lexicon 폴백 (freq dict와 동일).
   단 마스터의 예측발음은 타입 사전값이 아니라 발화별 생성이므로, 이 우선순위는
   형태소 단위 발음 조회부에 적용.
3. **⚠ 로마자 체계 3종 혼재 실측** — 통일 필요:
   | 산출물 | 체계 | 예 |
   |---|---|---|
   | 빈도사전·MP·LS (`roman_mfa`) | 초성대문자·종성소문자·`-`음절, 활음 YA/YEO/WA | `G EO t` |
   | 1기 enriched CSV (`form_roman` 등) | 유사하나 **활음 표기 상이** (iO·uEO·oE) | `I iO NG` (이용) |
   | 어휘목록 v1 (`word_roman`·`pron_*_roman`) | 서울코퍼스식 소문자 (k0·xx·vv) | `k0 ii - yv k0` |
   → 마스터 정본은 **빈도사전식**. 1기 CSV·lexicon 발음을 쓸 때는 정규화 매핑
   1회 통과(활음 iO→YO 등 / 서울식→대문자식). 매핑표는 `_roman_mfa_to_ipa.csv`
   옆에 `_roman_normalize.csv`로 관리.
4. **어절-분석 정렬 가드 재사용**: freq dict의 `len(form.split())==len(tagged.split())`
   검증과 동일한 same-length 가드 → 불일치 발화는 로마자·발음열을 `_`로 채우고
   `align_warn` 플래그 (조용한 오정렬 방지).
5. **사전형 어간 처리 승계**: XSV/XSA `-다` 제거 색인(freq dict 방식)을 확장 —
   용언(VV/VA/VX/VCP/VCN) 표제어 `-다` → 어간 매핑을 predict_pron 조회부에 내장.
6. **★어휘목록 판본**: A2·A3가 쓰는 정본은 이미 D:에 있는
   `00_DICTIONARY/01_NIKL_lexicon_full_v2.csv` (**v2**, `word_roman_mfa` 컬럼
   보유). Dropbox 것은 **v1**. → v2에 `pron_1/pron_2/pron_g2p` 발음 컬럼이
   있는지 확인 후: 있으면 v2 단독 사용, 없으면 v2(형태·roman_mfa) + v1(발음
   컬럼)을 urimal_id/word 키로 병용. v1 복사본은 어느 쪽이든 원천 보존용으로 유지.

## 1기 enriched CSV 대조 결과 (2026-07-23, Drive 표본 3k 실측)

Google Drive의 1기 `01_nikl_dialogue_enriched.csv`(4.96GB, 2020–2024)와
컬럼 대조. 표본 `_sample3k.csv`(2,999행) 전수 분석 기준.

| 1기 컬럼(28종) | 새 마스터에서 |
|---|---|
| file_id·doc_id·utterance_id·year | ✅ utt_id·session_id·year (좌표계) |
| category·topic·doc_date·relation | ✅ file_meta (category는 `_norm`으로 개선) |
| speaker_* 7종 | ✅ speakers_normalized (`_norm`·순서형으로 개선) |
| form / morphs | ✅ form / tagged (바른 재분석 — 구 분석기보다 상위) |
| form_roman | ✅ 동일 roman_mfa 체계 확인 (결정 1 정합) |
| **original_form** | ❌ 누락이었음 → **v1에 추가** (form과 31.2% 상이 — "좋아하구요"류 모음변이·축약이 전사에 이미 존재, 변이 연구 직결) |
| **start·end** | ❌ 누락이었음 → **v1에 추가** (발화 지속시간·발화속도) |
| **note** | ❌ 누락이었음 → **v1에 추가** (`발화겹침` 7.9% — 음향 QC 필터) |
| pronunciation (1기 정렬 유래, form_roman과 96.9% 상이) | v2 성격. 참고용 `pron_mfa_v1` 컬럼으로 수입 가능하나 **1기 한계(구버전 바른·G2P 미적용·spn) 검증 전 참고 전용** |
| morphs_v7_ids | 대체됨 — A2 의미번호 레이어가 상위 호환 |
| morphs_v7_origins | 대체됨 — 빈도사전 어원 컬럼(타입 수준) |
| doc_title | 미채택 (정보량 낮음 — n_speakers로 충분) |

- original_form·start·end·note는 **원본 JSON**(D:\00_RAW\dialogue_json)에서
  직접 읽는다(2025 포함·신뢰원천) — build_search_master.py에 JSON 패스 추가.
- Drive에는 동일 크기(4,957,188,915B) 전체본이 **2곳에 중복** 존재:
  `…/04_nikl_dialogue/02_csv/`(2026-02-24 원본)·`NIKL_dialogue/`(2026-05-11 사본).
  SSD 백업은 한 부만 (`D:\90_ARCHIVE\1기_enriched\`).

## 미결(사용자 판단 대기)
- [ ] 예측 발음 규칙 인벤토리·적용 순서 확정 (파일럿 표본 검토로)
- [ ] 철자열·발음열 기호 세부(음절 경계 `.`, 자리 표시자 `_`) 승인
- [ ] v2의 spn_ratio 필터 임계값 (G2P 파일럿 결과 후)
- [ ] `tagged_roman`(형태소 경계 보존 roman) 포함 여부
- [ ] 1기 `pron_mfa_v1` 참고 컬럼 수입 여부 (1기 CSV SSD 백업 후)
- [ ] **lexicon v2에 발음 컬럼(pron_1/pron_2/pron_g2p) 유무 확인** (아래 명령):
      `powershell "Get-Content 'D:\00_RAW\reference\00_DICTIONARY\01_NIKL_lexicon_full_v2.csv' -TotalCount 1"`

*작성 2026-07-23 (Claude 협업). 확정·변경 시 METHODS·TODO·SCRIPTS_INDEX 갱신.*
