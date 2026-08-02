# MFA r2 인프라 파일럿 전역 이슈와 반복 검토 정책 (역사 기록)

## 1. 상태

- 결정일: 2026-07-30
- 범위: 2020–2025 r2 인프라 수용 파일럿 60발화
- 판정: **전역 수정 후 재검토**
- 전수 MFA: **아직 시작하지 않음**
- 실제 음운 실현 판정: 수행하지 않음

이 결정은 MFA phone의 기준이나 공통 발음사전을 바꾸는 결정이 아니다.
파일럿에서 발견한 TextGrid 표시 계층과 연구 검색 CSV 구조를 고친 뒤 같은
60발화로 다시 확인하기 위한 인프라 결정이다.

## 2. 연구자 검토에서 발견한 문제

첫 검토 발화 `SDRW2000000510.1.1.98`은 WAV, LAB, CSV, TextGrid가 같은
발화이며 기본 word·phone 정렬과 양끝 경계도 대체로 사용할 수 있었다.
그러나 다음 두 문제는 이 한 발화에 국한되지 않는 설계 문제였다.

### G-TIER-01: 시간 분할된 legacy `morphemes` tier

현재 `morphemes` tier는 Bareun 형태소 분석을 표시한 층이 아니라 기존
`06_textgrid_merged`의 `words` 경계를 복사한 legacy 층이다. 따라서
`words`와 시작·끝이 다르면서도 마치 형태소의 음향 시간경계를 판정한 것처럼
보일 수 있다.

읽기 전용으로 60개 TextGrid를 전수 대조한 결과는 다음과 같다.

- tier 구성 `words/phones/morphemes/utterance`: 60/60
- `words`와 `morphemes`의 라벨 순서까지 비교 가능한 파일: 6/60
- 그 6개 중 시간경계까지 완전히 같은 파일: 0/6
- 두 tier의 구조 또는 시간이 다른 파일: 60/60
- 비교 가능한 파일의 최대 경계 차이: 0.245초

이 tier는 후속 연구에서 형태소 포함 발화를 찾는 데는 도움이 될 수 있지만,
형태소의 실제 시작·끝 시간을 제공한다는 근거는 없다. 특히 형태소 첫소리
환경을 시간경계에서 바로 읽으려 하면 잘못된 정밀성을 부여한다.

결정:

- 후속 TextGrid의 셋째 tier는 `morph_analysis`로 이름을 바꾼다.
- `0–xmax` 단일 구간에 CSV의 형태소 표면형·품사 tagging을 표시한다.
- 형태소의 음향 경계를 새로 추정하지 않는다.
- `words`와 `phones_mfa`만 MFA의 시간 정렬층으로 해석한다.

### G-CSV-01: 형태소 경계 환경의 구조화 열 부재

60개 행별 CSV는 모두 같은 헤더를 가지며 `search__tagged`와
`search__tagged_roman`은 60/60 존재한다. 그러나 다음 구조화 자료는
60/60 부재했다.

- 형태소별 token 표
- 형태소 시작·끝 철자 단위
- 형태소 경계의 왼쪽·오른쪽 단위
- 규칙 발음·사전 발음과 결합한 형태소 경계 환경 표

`tagged_roman`은 음소 사이 공백, 음절 `_`, 형태소 `+`, 어절 `|`, 형태소
끝 POS 표지를 사용하므로 표시와 단순 검색에는 보존 가치가 있다. 하지만
`요즘/NNG`의 `YO`처럼 형태소 첫 음절의 활음·모음이 묶이고 onsetless `ㅇ`이
직접 표시되지 않는 사례에서는 연구자가 정규식과 표기 규약을 매번 해석해야
한다.

결정:

- `tagged`와 `tagged_roman`은 표시·기초검색용으로 보존한다.
- 최종 검색 CSV/Parquet에는 정규화한 `morph_tokens`와
  `morph_boundaries` 파생표를 추가한다.
- 각 형태소의 표면형, POS, 어절·형태소 순번, 철자 첫/끝 단위와 좌우 경계를
  명시한다.
- 규칙 발음과 우리말샘 발음은 별도 보조열로 연결하고 실제 발화의 실현값으로
  덮어쓰지 않는다.

## 3. 반복 입력을 줄이는 검토 정책

같은 전역 문제를 60행에 긴 문장으로 반복하지 않는다.

| 코드 | 일괄 기록 | 개별 행에서 다시 적을 때 |
|---|---|---|
| `G-TIER-01` | `tier_structure_status=문제있음` | 특정 파일에서 tier 누락·깨짐 등 추가 문제가 있을 때 |
| `G-CSV-01` | `csv_searchability_status=문제있음` | 특정 발화의 형태소 분석·로마자·파일 연결에 별도 문제가 있을 때 |
| 두 코드 공통 | `overall_infrastructure_decision=수정 후 재검토`, notes에 `[전역 G-TIER-01, G-CSV-01]` | 전역 코드만으로 설명되지 않는 국소 문제를 뒤에 추가 |

2–60번 행에는 위 값을 일괄 사전입력했다. 1번 행의 연구자 입력은 보존했다.
따라서 남은 59행에서 연구자가 직접 확인할 핵심은 다음 두 가지다.

1. `linkage_status`: WAV·LAB·CSV·TextGrid가 같은 발화인가
2. `boundary_status`: word 정렬과 발화 양끝 경계에 심각한 국소 문제가 없는가

전역 이슈가 이미 기록됐으므로 정상 행에는 notes를 반복해 쓰지 않는다.

## 4. 다음 수정의 범위

### TextGrid 출력

- 목표 4-tier:
  `words / phones_mfa / morph_analysis / utterance_info`
- `morph_analysis`: `0–xmax` 단일 구간, 형태소 tagging과 출처 표지
- `utterance_info`: 발화 철자와 검색용 참조값, 시간경계 판정층 아님
- 모든 tier는 `0–xmax`를 명시적으로 덮는다.

이는 정렬 DB의 word·phone interval을 바꾸는 작업이 아니다. 보존한 pilot
DB와 CSV에서 TextGrid만 다시 내보낼 수 있으므로 60발화 MFA 정렬을 처음부터
다시 계산할 필요가 없다.

### 검색 자료

- 발화 1행 CSV의 기존 열은 보존한다.
- 형태소별 자료와 경계별 자료는 별도 정규화 CSV/Parquet로 파생한다.
- 모든 파생행은 `utt_id`, `eojeol_index`, `morph_index`로 WAV·TextGrid·
  발화 1행 정본에 다시 조인할 수 있어야 한다.
- 실제 실현 여부는 이 단계에서 만들지 않는다.

## 5. 재검토와 전수 진입 조건

1. 위 두 수정의 코드·스키마·출처 표지를 구현한다.
2. 보존한 60발화 DB·CSV로 새 TextGrid와 행별 CSV를 재생성한다.
3. 기존 WAV·LAB과의 식별자·duration·word/phone interval 동등성을 검사한다.
4. 연도별 첫 사례 6개를 우선 재검토하고, 문제가 없으면 나머지 표본을 본다.
5. 연구자 검토 보고서가 `approved`가 된 뒤에만 2020 r2 전수 MFA를 시작한다.

개선 효과가 드라마틱한 정렬 성능 향상인지가 이 gate의 기준은 아니다. 연구자가
후속 후보 검색, 파일 수집, KOINA, 수동 실현 판정을 할 때 각 층의 의미가
일관되고 추적 가능한지가 기준이다.

## 6. 파일 보존과 작업 기록

- 수정 전 workbook:
  `archive/mfa_r2_review/REVIEW_before_global_prefill_20260730_173905.xlsx`
- 수정 전 SHA-256:
  `232f55bad13734e3fa7808fb7a7ac384974ec3b995f8f5d652421cf7bef64798`
- 일괄 입력 검증본:
  `outputs/019f9337-013e-7933-97a6-fdf8f1b6f31f/REVIEW.xlsx`
- 수정 후 SHA-256:
  `0802b6a0d5c590d8d5f818dfcac23ad4bb6b506cc8004746322ad69196d75d9a`
- Dropbox 반영 위치:
  `C:\Users\ari30\Dropbox\MFA_R2_INFRA_PILOT_20260730\REVIEW.xlsx`

일괄 입력 전후에 1번 행, 불변 식별·파일 열, 240개 하이퍼링크, 2개
dropdown, `A1:O61` 검토 table을 다시 열어 대조했다. 원자료, D: 정렬 DB,
WAV, TextGrid, LAB, CSV 산출물은 이 작업에서 수정하지 않았다.
