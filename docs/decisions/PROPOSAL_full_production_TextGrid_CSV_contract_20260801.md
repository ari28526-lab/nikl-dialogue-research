# 2020–2025 전수 MFA 연구 출력 계약 제안

- 작성일: 2026-08-01 KST
- 상태: **구현·60발화 회귀검사 통과, 외부 리뷰 및 최종 GO 대기**
- 적용 대상: 2020–2025 전체 5,103,356발화
- 금지: 외부 리뷰와 필수 수정 전 전수 MFA 시작

## 1. 연구 목적에서 출발한 설계

이 인프라의 목적은 자동 도구로 실제 음운 실현을 판정하는 것이
아니다. 연구자가 형태소 또는 표기상 음운 환경을 재현 가능하게 검색하고,
해당 WAV·TextGrid·CSV를 연결해 직접 듣고 보며 실현을 판정하기 위한
기반을 만드는 것이다.

```text
동결 CSV/Parquet에서 후보 검색
  → utt_id로 WAV·TextGrid·정렬표 수집
  → 선택 후보에만 KOINA·이어붙이기·wav2vec2 보조값 추가
  → 연구자가 실제 실현을 별도 판정
```

따라서 MFA/G2P phone, 규칙 발음, 사전 발음, wav2vec2 phone은 모두
**출처가 다른 자동 참조값**이며 연구자 판정을 대체하지 않는다.

## 2. 연구자가 붙인 정보와 자동 파생 정보의 출처

| 정보 | 출처/생성 주체 | 현재 표현 | 해석 한계 |
|---|---|---|---|
| `original_form`, 시작·종료, `note`, 대화/발화자 ID | 국립국어원 원 JSON | 동결 search master와 동반표 | 원자료로 보존, 자동 수정 금지 |
| `form`, `tagged`, POS, `n_morphs/n_eojeol` | 1차 형태소 분석 레이어 | 발화·어절·형태소 표 | 실제 음향 경계나 실현값이 아님 |
| 6-tier 선택, 형태소 전체-span 표시, 선별 KOINA | 연구자가 직접 확정한 방법 정책 | 계약 문서·tier schema | 자료값이 아니라 분석 설계 결정 |
| `form_roman`, `tagged_roman_v2` | 동결 roman_mfa 코드 | search master·어절/형태소 표 | 철자 전자이며 실제 발음이 아님 |
| `pron_reference_*` | `form`과 JSON `original_form`을 출처 규칙으로 선택 | MFA lab 입력·동반표 | 숫자 등을 근거 없이 추측하지 않음 |
| r2 공통사전 phone | Korean MFA 3.3.0 + Jamo G2P 3.2.0, 동결 SHA | MFA 입력 사전 | 정렬 기준; 음성에서 관찰한 값이 아님 |
| `words`, `phones_mfa`, 시간, score | r2 MFA SQLite DB | TextGrid·interval 표 | 자동 강제정렬 결과 |
| `phoneme_r_auto` | `phones_mfa`만의 결정적 broad Roman 매핑 | TextGrid·phone 표 | 철자/사전으로 기저형을 역복원하지 않음 |
| 우리말샘/표준국어대사전 발음 | 1기 어휘 자료 | **최종 검색 계약 미연결** | 다의어·복수 발음을 1:1 단일값으로 축약 금지 |
| KOINA/wav2vec2 | 선별 후보의 별도 자동 분석 | 후보 bundle 파생표 | 기본 TextGrid/MFA 열 덮어쓰기 금지 |
| 실제 실현·운율 판정 | 연구자의 청취·시각 검토 | 별도 manual judgment 표 | 자동 열로 사전 채우지 않음 |

이 구분은 논문에서 원자료, 연구자 부착/정책, 기계 파생값,
수동 판정의 계층을 별도로 기술하기 위한 추적 계약이다.

## 3. TextGrid 기본 6-tier

```text
words
phones_mfa
phoneme_r_auto
utterance
utterance_orth_r
morph_analysis_utt
```

| tier | label 출처 | 시간의 의미 | 연구 활용 |
|---|---|---|---|
| `words` | MFA DB word interval | MFA 입력 단어 정렬 | 청취 위치·어절 맥락 |
| `phones_mfa` | MFA DB phone interval | 사전/G2P phone의 강제정렬 | 대략적 분절 위치 |
| `phoneme_r_auto` | `phones_mfa`만의 broad Roman | `phones_mfa`와 경계 동일 | 실용적 Roman 검색·표시 |
| `utterance` | frozen `form` | 첫·마지막 유표 word span | 한글 발화 확인 |
| `utterance_orth_r` | frozen `form_roman` | `utterance`와 경계 동일 | 철자 Roman 검색 |
| `morph_analysis_utt` | canonical `tagged` | `utterance`와 경계 동일 | 형태소/POS 문자열 검색 |

모든 tier는 빈 interval을 포함해 `0–xmax`를 연속 커버한다.
`morph_analysis_utt`를 형태소별로 잘게 시간 분할하지 않는 이유는 실측하지
않은 형태소 음향 경계를 주장하지 않기 위해서다. 정밀한 형태소·음절·자모
위치 검색은 정규화 CSV/Parquet에서 한다.

## 4. TextGrid와 같이 생성할 연도별 동반표

5,103,356발화마다 작은 CSV를 하나씩 만들면 파일 수·탐색·복사·
백업 비용이 과도하다. 따라서 전수 정본은 연도별 gzip CSV 세 개로 두고,
후보 검토 bundle에서만 발화별 CSV를 파생한다.

| 파일 | 행 단위 | 주요 키/내용 |
|---|---|---|
| `utterance_alignment.csv.gz` | TextGrid 1개당 1행 | `utt_id`, 화자/대화, 원·reference 표기, 형태소, 정렬 요약, 계약 ID |
| `word_intervals_mfa.csv.gz` | MFA word interval 1개당 1행 | `utt_id+word_interval_idx`, reference 어절·lab word·phone열 |
| `phone_intervals_mfa.csv.gz` | MFA phone interval 1개당 1행 | `utt_id+phone_interval_idx`, DB word 연결, IPA·broad Roman·시간 |

최종 검색용으로는 이 CSV를 동일 schema의 연도별 Parquet으로 재생성하고,
기존 형태소 정규화 표와 `utt_id`로 join한다. gzip CSV는 장기 호환·감사용,
Parquet은 DuckDB/R/Python 검색용이다.

## 5. 위치 번호를 하나로 합치지 않는 이유

모든 공개 `idx`는 1부터 시작하지만 소속 좌표계를 이름으로 분명히 한다.

| 위치 | 좌표계 |
|---|---|
| `eojeol_idx` | `form/tagged`의 형태소 검색용 원 어절 |
| `reference_eojeol_idx` | MFA 입력 `pron_reference_form`의 어절 |
| `mfa_word_idx` | 유표 MFA word interval의 순서 |
| `word_interval_idx` | 무음 interval까지 포함한 word interval 순서 |
| `phone_interval_idx` | phone interval 순서 |

실자료 `SARW2500000414.1.1.2`에서 `form`의 `2사람이`는 한 어절이지만,
원 JSON에서 복원한 MFA 참조 표기는 `두 사람이`라서 두 word다. 이를 같은
`eojeol_idx`로 처리하면 이후의 모든 형태소–phone 연결이 한 칸씩 밀릴 수
있다. 새 계약은 원 형태소 좌표와 MFA 입력 좌표를 분리하고, 두 수가
다른 사실 자체를 출처 정보로 보존한다.

## 6. 재실행·실패 복구 계약

```text
pre-MFA 입력 계약
  → r2 MFA 정렬
  → direct_db_ready (정렬 계산 재사용 가능, 분석 승인 아님)
  → DB 직독 6-tier + 동반표 partial 생성
  → 수량·tier·경계·phone inventory·spn·조인 검증
  → 연도 staging 승격
  → 독립 QC·연구자 표본 검토
  → 다음 연도
```

`direct_db_ready`는 출력 코드와 CSV schema가 실패해도 이미 끝난 수십 시간의
MFA 정렬을 다시 시작하지 않게 하는 중간 체크포인트다. 이 표시는 TextGrid
출력 성공이나 분석 준비 승인이 아니다. 완성 gzip 표도 모든 gate를 통과한
뒤에만 `.partial`에서 최종 파일명으로 승격한다.

## 7. 논문 방법론 기술의 골격

최종 실행 후에는 다음 근거를 실제 버전·SHA·수치로 채운다.

> 2020–2025 자료에 동일한 Korean MFA acoustic model, Jamo G2P,
> 공통 발음사전 및 phone inventory를 적용하였다. 원 전사·형태소
> 분석, MFA 입력용 reference 표기, 사전/G2P phone, MFA 정렬 phone,
> 자동 Roman 매핑을 별도 출처로 보존하였다. MFA phone은 청취
> 위치를 찾기 위한 자동 강제정렬 보조값으로 사용했으며, 음운 현상의
> 실제 실현 여부는 선별 발화의 음성과 TextGrid를 연구자가 검토해
> 별도로 판정하였다.

논문에는 다음 표를 보조자료로 남긴다.

- 연도별 발화·정렬·누락·격리 수
- acoustic/G2P/사전/adoption/alignment contract SHA-256
- 연도별 관찰 phone이 공통 허용 inventory의 부분집합임을 보이는 감사
- `spn`, 누락, count/label 불일치의 전수 inventory와 처리 규칙
- 전수 출력 schema·코드 commit·실행 manifest

## 8. 60발화 회귀검사 결과

기존 r2 인프라 파일럿 DB를 읽기 전용으로 재사용했다. 새 MFA는 돌리지
않았다.

- 2020–2025 각 10발화, 총 60/60 출력 성공
- 기존 4-tier의 duration·`words`·`phones`와 새 `words/phones_mfa`
  전수 동일: 60/60, 불일치 0
- 새 6-tier 순서·`0–xmax`·phone–Roman 경계·발화 수준 경계 통과
- 연도별 gzip 3개, 총 18개 생성; 발화 행 60
- DB computation checkpoint 6/6 `success`, coverage 100%, actual `spn=0`
- 전체 회귀 산출물 669,108 bytes, 활성 `.partial` 0
- 위 `2사람이 → 두 사람이` 사례로 좌표 혼동을 발견·수정
- 실패한 동반표가 완성 gzip으로 남던 순서를 수정하고 회귀시험 추가

검증본:
`work/research_6tier_candidate_60_20260801`.

## 9. 외부 리뷰에서 반드시 결정할 사항

1. 5.1백만 TextGrid에 6-tier 모두를 물리적으로 저장할지, 일부 발화
   수준 tier를 후보 추출 시 파생할지
2. 대량 gzip CSV 생성 후 Parquet 미러 계약·toolchain·schema를 어떻게
   동결할지
3. 예상된 MFA 미정렬/원 WAV 사용 불가 항목을 어떻게 분류·승인해
   연도 staging을 완료할지
4. 우리말샘 복수 센스·복수 발음을 별도 1:N 후보 표로 연결할
   키와 중복 정책
5. 형태소 표, MFA word/phone 표, 사전 후보 표, manual judgment 표의
   최종 조인 계약
6. 독립 연도 QC가 새 6-tier·동반표·DB checkpoint와 같은
   계약 ID를 확인하는지

이 운영 미정 사항을 해결하기 전에는 코드 단위시험이 통과해도 전수
실행에 `GO`하지 않는다.
