# 후보 추출·분절·수동 판정을 위한 인프라 층 설계

상태: 2026-07-24 사용자 연구 흐름 확인 후 작성

관련 감사: `outputs/reports/AUDIT_search_master_full_2026-07-24.md`

## 1. 목적

이 프로젝트의 자동화 목표는 음운 현상의 실현 여부를 기계가 최종 판정하게 하는
것이 아니다. 자동화는 연구자가 검토할 후보를 정확히 찾고, 해당 음성·TextGrid·
운율 정보를 빠짐없이 모으는 데 집중한다.

전체 흐름:

1. CSV에서 특정 형태소 포함 여부 또는 표기상 음운 환경을 검색한다.
2. 후보 `utt_id`의 음성 파일과 TextGrid를 모은다.
3. KOINA 운율 분석 결과를 결합한다.
4. 연구자가 음성과 TextGrid를 직접 보고 실현 여부를 판정한다.
5. 수동 판정과 형태소·사전 발음·빈도·사회 변수·운율을 결합해 분석한다.

## 2. 서로 섞지 않을 세 층

### A. 언어·검색 층

- 원문 표기 `form`
- Bareun 형태소 `tagged`
- A2 의미번호
- lexicon 사전 등재 발음
- 규칙 기반 기준 발음
- 사용역·화자·빈도 변수

이 층의 발음은 후보 검색과 표준/기준선 구성용이다. 음향에서 자동 추정한
실현값이 아니다.

### B. 파일·분절 층

- WAV 존재·경로
- 어절 4-tier TextGrid 존재·경로
- 구 3-tier TextGrid 존재·경로
- 격리 여부와 사유
- MFA phones 라벨·시간
- tier·시간 경계·정렬 상태

MFA phones는 G2P/사전 후보를 음성에 강제정렬한 대략적 분절이다. 연구자가
음성 구간을 찾고 TextGrid를 검토하기 위한 인프라로 사용한다.

### C. 연구자 판정 층

- 현상명과 후보 환경
- 실현/비실현/판정불가
- 판정 신뢰도
- 판정자·판정일
- 근거 구간·메모
- KOINA 운율 변수

이 층만이 ㄴ 삽입 등 현상의 최종 실현값을 가진다. A·B층을 덮어쓰지 않고
`utt_id`와 후보 위치 키로 조인한다.

## 3. Search master 보완 원칙

기존 `05_search_master` 전량본은 2026-07-23 기준선으로 보존한다. 새판은
격리 파일럿에서 스키마를 검증한 뒤 실행 ID archive를 만들고 승격한다.

### 3.1 사전 발음

현재 규칙 기반 `pron_pred_*`는 그대로 보존한다. lexicon 결과를 여기에
덮어쓰지 않고 별도 열로 추가한다.

권장 열:

| 열 | 내용 |
|---|---|
| `morph_pron_dict_hangul` | 형태소별 대표 사전 발음, `tagged`의 `+`·어절/token 경계 보존 |
| `morph_pron_dict_alt_hangul` | `pron_2` 및 복수 발음 |
| `morph_pron_dict_source` | `pron_1` / `pron_g2p_fallback` / `not_found` / `ambiguous` |
| `morph_pron_dict_key` | 실제 조회한 표제어·품사·의미번호 |
| `morph_pron_dict_status` | unique / sense_resolved / multiple / not_found |

조회 원칙:

1. A2의 `sense_id`가 있고 lexicon의 같은 표제어·품사·의미번호와 대응되면 이를
   먼저 사용한다.
2. 의미번호가 없을 때 `(표제어, 품사)`의 서로 다른 발음이 하나뿐이면 사용한다.
3. 발음이 여러 개면 첫 의미번호를 임의로 고르지 않고 `multiple`로 보존한다.
4. 용언·파생접사는 사전형 `-다`/표제어 규칙을 명시적으로 적용한다.
5. `pron_1`을 우선하고 없을 때만 `pron_g2p`를 폴백으로 사용한다.
6. `pron_2`는 대체 인정형이므로 대표값에 덮어쓰지 않는다.
7. 사전의 기존 roman 열은 체계가 다르므로 한글 발음을 프로젝트
   `roman_mfa` 매핑으로 다시 변환한다.

사전 형태소 발음과 경계 규칙을 합성한 단일 열은 별도 파일럿에서 검증하기 전
만들지 않는다. 먼저 원자료와 출처를 손실 없이 보존한다.

### 3.2 파일 coverage

권장 열:

| 열 | 내용 |
|---|---|
| `has_wav` | 사용 가능한 WAV 존재 |
| `has_tg_eojeol` | 어절 4-tier TextGrid 존재 |
| `has_tg_merged` | 구 3-tier TextGrid 존재 |
| `quarantined` | WAV 격리 여부 |
| `quarantine_reason` | 0바이트·손상 등 사유 |
| `tg_preferred` | `eojeol_4tier` / `merged_3tier` / `none` |
| `candidate_files_ready` | 연구자 검토용 WAV와 최소 한 TextGrid가 함께 존재 |

행마다 디스크를 세 번 조회하지 않는다. 연도별 파일 stem 집합을 한 번 스캔하고
메모리 set membership으로 채워 D: I/O를 줄인다. 결과 합계는 기존
`05_audio_index`와 교차검증한다.

### 3.3 형태소 token과 표기 어절

`align_warn` 508,153행은 삭제하거나 억지로 1:1 정렬하지 않는다.

권장 열:

- `eojeol_map_status`: exact / token_split / token_merge / complex / unknown
- `bareun_token_count`
- `form_eojeol_count`
- 향후 재분석 시 `token_begin_offset`, `token_length`, `token_content`

발화 단위 후보 추출에서는 다음을 독립적으로 수행한다.

- 형태소 조건: `tagged`/A2에서 검색
- 표기 환경: `form`에서 검색

정확한 TextGrid 어절 번호가 필요한 작업은 `eojeol_map_status=exact`만 자동
처리하고, 나머지는 발화 전체를 연구자 검토 묶음으로 보낸다.

## 4. 후보와 수동 판정 스키마

현상별 후보표는 search master를 덮어쓰지 않는다.

최소 열:

| 열 | 내용 |
|---|---|
| `candidate_id` | 현상·발화·후보순번으로 만든 고유 키 |
| `phenomenon` | 예: `34_n_insertion` |
| `utt_id` | 모든 층의 조인 키 |
| `candidate_index` | 발화 안의 후보 순번 |
| `form_context` | 표기 환경 |
| `morph_context` | 형태소 환경 |
| `eojeol_index` | exact일 때만 자동값, 아니면 빈 값 |
| `wav_path`, `textgrid_path` | 검토 파일 |
| `koina_status` | 운율 분석 조인 상태 |
| `realization` | realized / not_realized / uncertain / excluded |
| `annotator`, `annotated_at` | 판정 출처 |
| `confidence`, `note` | 신뢰도와 근거 |

같은 발화에 후보가 둘 이상 있을 수 있으므로 행 단위는 발화가 아니라 후보
토큰이다.

## 5. 2020 MFA 파일럿 게이트

### 5.1 목적

G2P가 현상을 자동 판정하는지 시험하는 것이 아니다. 다음을 시험한다.

- 올바른 WAV와 lab이 대응되는가
- 세션=화자 구조가 유지되는가
- TextGrid가 누락 없이 생성되는가
- words/phones/morphemes/utterance 네 tier가 있는가
- 시간 경계가 음성 길이 안에 있고 역전·음수가 없는가
- 연구자가 후보 어절과 음성 구간을 찾을 수 있는가
- 실패·격리·`spn`이 manifest에 남는가
- 중단 후 재개와 기존 산출물 보존이 되는가

### 5.2 단계

1. 2020 소표본을 본 산출물과 분리된 경로에 구성한다.
2. 짧음/보통/김, 여러 세션, `align_warn` 있음/없음, 사전 OOV 가능성이 있는
   표본을 포함한다.
3. hardened preflight와 같은 runner 경로로 G2P MFA를 실행한다.
4. 출력 수·tier·시간·WAV 대응을 자동 검사한다.
5. `fetch_audio_for_search.py`로 WAV+TextGrid manifest를 실제 생성한다.
6. 연구자가 20–30건을 Praat에서 열어 구간 찾기 용이성을 확인한다.
7. 통과하면 2020 전량을 새 실행 ID로 시작한다.

### 5.3 자동 통과 기준

- 대상 세션과 발화 목록이 manifest에 고정됨
- 사용 가능 입력 대비 출력 누락 0 또는 모든 누락에 명시적 실패 사유 존재
- 잘못된 tier 이름 0
- 음수·역전·duration 초과 interval 0
- 0바이트·손상 WAV가 실행 전에 격리됨
- 정렬 종료코드와 산출물 수가 모두 성공을 지시함
- `spn`은 합계·연도·세션 분포가 기록됨
- 기존 2020 비G2P 산출물은 archive 또는 별도 경로에 보존됨

`spn=0` 자체를 음운론적 정답의 기준으로 사용하지 않는다.

## 6. 실행 순서

1. search master 보완 열을 격리된 2020 소표본으로 구현·검증
2. 2020 CSV 한 연도 archive→재생성→전수 감사
3. 2020 MFA 소표본 파일럿과 연구자 사용성 확인
4. 2020 MFA 전량 실행·검증
5. 후보 추출→WAV/TextGrid 수집→KOINA 조인→연구자 수동 판정의 한 현상
   end-to-end 파일럿
6. 통과 뒤 2021부터 같은 게이트를 연도별 반복
