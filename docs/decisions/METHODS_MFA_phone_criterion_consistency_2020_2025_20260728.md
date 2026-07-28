# 2020–2025 MFA phone 기준 동일성 — 방법론 계약과 증거 계획

기록일: 2026-07-28  
상태: **방법론 계약 고정, 공통 G2P 계산 및 전수 동등성 실행 전**  
적용 범위: 2020–2025 어절 MFA 4-tier 인프라

## 결론

논문에서 주장하려는 동일성은 다음이다.

> 2020–2025년 자료에 동일한 phone 기호 inventory, 동일한 MFA
> acoustic/G2P 모델 판본, 동일한 기본 발음사전과 OOV 생성 규칙, 동일한
> 어절 입력 정규화 및 4-tier 생성 규칙을 적용하였다.

이 주장은 모든 발화의 실제 음성 실현이나 시간 경계가 동일하다는 뜻이 아니다.
MFA phone은 연구자의 실제 실현 판정을 대신하지 않는 정렬용 예측 분절이다.
따라서 논문에는 **동일한 방법론적 phone 표기·생성·forced-alignment 기준**을
사용했다고 기술하고, 실제 실현은 WAV와 TextGrid를 연구자가 별도로 판정했다고
구분한다.

이 문서의 gate가 모두 통과하기 전에는 위 문장을 완료 사실로 쓰지 않는다.

## 동일 기준의 조작적 정의

| 구성요소 | 6개년 동일성 기준 |
|---|---|
| phone 기호 | 동일 acoustic model의 110개 정렬용 inventory와 동일 해시 |
| MFA | 동일 MFA 3.4.0 환경과 같은 핵심 정렬 옵션 |
| acoustic model | 같은 `korean_mfa.zip` 내용 SHA-256 |
| 기본 사전 | 같은 `korean_mfa.dict` 21,009행 내용 SHA-256 |
| OOV | 같은 `korean_mfa` G2P, 1-best, strict graphemes |
| 공통사전 | 기본 사전 행을 원문·순서 그대로 보존하고 관측 OOV 1-best만 추가 |
| 예외 발음 | 우리말샘·형태소 조건 후보는 검색 CSV용이며 MFA r1에는 0개 추가 |
| 입력 단위 | 동결 `pron_reference_form`의 공백 어절, 한글 음절 유지 정책 |
| TextGrid | `words/phones/morphemes/utterance` 4-tier와 동일 경계/QC 계약 |

공통사전은 새로운 phone 기준이 아니다. 연도마다 되풀이하던 같은 G2P 계산을
2020–2025 전체 고유 표면 어절에 한 번 수행해 재사용하는 속도용 cache이다.

## 고정한 모델과 원천

2026-07-28 최신 prepare manifest에서 확인한 값이다.

| 자원 | SHA-256 |
|---|---|
| acoustic `korean_mfa.zip` | `46f7a73ab46828c679562b160e0577beecfb4a9a827efe5ab392aee947451a4d` |
| 기본 `korean_mfa.dict` | `75683f4dc2a7dd95295a068206d248a30bd2f4f2231fd4449210c91d1e78150b` |
| G2P `korean_mfa.zip` | `6938db05d83fa92c5c80681bf76fd7dd7af7f3ea8c7d7df1093790c641ad0344` |
| 6개년 vocabulary | `3a6ecbe3a18508dd6807e6d5c8b3ced2179420e2e9fa93967a085daecce25319` |
| 정렬 phone inventory | 110개, 정렬된 목록 SHA `9b66a3b6a3b698b188adcc35bc30909b7550cc7a1ff48be931f1d47c217b493e` |

vocabulary는
`D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725`의
5,103,356발화, 27,847,068어절, 881,237개 고유 표면 어절을 대상으로 한다.
기본 사전에 이미 있는 것은 14,546개이고 관측 OOV는 866,691개이다.

## 2020·2021 소급 증거

2020·2021을 즉시 다시 정렬하지 않는다. 먼저 기존 결과가 위 공통 기준에
부합하는지 전수 확인한다.

완료 marker가 가리키는 2020 Git commit
`195d71f377993dedd6dab4fae4133682b74fb576`과 2021 Git commit
`6ef65272e951c0a4b473030a15781f11ad540693`의 실행 코드는 모두
`mfa align ... korean_mfa korean_mfa --g2p_model_path korean_mfa`를
사용한다. acoustic model과 기본 사전 파일의 생성 시각은 2026-02-20,
G2P 파일은 2026-07-23 12:36으로 두 최종 실행보다 앞선다. 2020 보존
MFA 로그와 2021 완성 로그에는 MFA 3.4.0이 기록돼 있다.

### 2020

완성 정렬 DB는 남아 있지 않다. 발견된 archive DB
`D:\mfa_eojeol\archive_stale_temp\20260725_141701\C\2020\2020.db`는
SQLite `quick_check=ok`이지만 `word_interval=0`, `phone_interval=0`인
정렬 전 부분본이다. 그러므로 다음 두 증거를 결합한다.

1. 독립 QC를 통과한 최종 4-tier TextGrid 866,196개에서 모든 비어 있지 않은
   word 구간과 그 안의 phone열을 복원한다. 모든 실제 출력열이 공통사전의
   해당 어절 후보에 포함되어야 한다.
2. 부분 DB 안에 존재하는 모든 speech/OOV 단어–발음 후보를 공통사전과
   집합 동등 비교한다. 이는 DB 내부 전수 감사이지만 2020 전체 vocabulary
   전수라고 표현하지 않는다.

부분 DB와 2021 완성 DB 모두 사전 이름과 경로가 `korean_mfa` 및 같은
`korean_mfa.dict` 경로이다. 두 DB의 non-silence 109개, `sil`, `spn`은
동일하다. 2021에만 더 있는 `#11`, `#12`는 코퍼스별 FST disambiguation
symbol이며 연구 phone이 아니다.

2020 완료 marker에는 당시 모델 SHA가 직접 기록되지 않았다는 소급
provenance 한계가 있다. 따라서 Git 실행코드·파일 시각·MFA 로그·DB 내부
phone/사전 정보·최종 TextGrid 전수 결과를 결합한다. 이는 일반적인
방법론 동일성 주장을 뒷받침하지만 “2020 실행 순간의 세 파일을 별도
cryptographic snapshot으로 보존했다”는 더 강한 주장은 하지 않는다.
그 수준의 엄격한 chain of custody가 연구 요건이 되면 2020·2021을 새
공통 release로 재실행해야 한다.

### 2021

완성 DB `D:\mfa_tmp\2021\2021.db`의 모든 2021 관측 어절에 대해
speech/OOV pronunciation 후보 집합을 공통사전과 정확히 비교한다.
단 하나의 후보 추가·삭제·phone 변화도 허용하지 않는다.

### 소급 gate

다음을 모두 만족해야 2022 공통사전 사용을 허용한다.

- 2020 TextGrid 전수 mismatch 0
- 2020 부분 DB 내부 전수 mismatch 0
- 2021 완성 DB 전수 mismatch 0
- acoustic/G2P/기본사전/공통사전 fingerprint 일치
- 공통사전의 우리말샘·attested variant 추가 0
- acoustic inventory 밖 phone 0, `spn` G2P 결과 0

소급 검사는 기존 결과를 수정하지 않는 읽기 전용 검사다. 어느 하나라도
실패하면 2022 실행을 차단하고 원인과 영향 발화 목록을 먼저 만든다.

## 2022–2025 전향적 강제

2022–2025는 같은 공통사전 파일을 직접 입력한다. `run_eojeol_realign.ps1`은
다음이 모두 일치하지 않으면 시작 전에 종료한다.

- 공통 release manifest와 전수 동등성 보고서 SHA-256
- 현재 acoustic/G2P/기본사전 SHA-256
- 최종 공통사전 SHA-256
- 2020, 2020 부분 DB, 2021의 세 동등성 status
- 6개년 vocabulary의 search-master root

공통사전 모드에서는 `--g2p_model_path`를 정렬 단계에 넘기지 않는다.
관측 OOV가 이미 모두 cache에 있으므로 연도별 G2P를 반복하지 않는다.
그러나 G2P 모델 해시는 release provenance로 계속 고정한다.

각 연도 alignment contract에는 acoustic/dictionary/G2P 해시, MFA/Pynini/
Python 판본, lab 입력계약을 기록한다. 2022–2025의 acoustic·G2P·공통사전
해시는 모두 같아야 한다. 연도별 `alignment_contract_id`는 연도와 lab
입력계약을 포함하므로 서로 달라도 정상이다.

## 논문용 최종 증거 묶음

공통사전과 2022–2025가 모두 끝나면 다음을 함께 보존한다.

1. 공통 release manifest
2. 2020 TextGrid·부분 DB 및 2021 DB 전수 동등성 JSON/CSV
3. 2022–2025 alignment contract 4개
4. 연도별 독립 4-tier QC 보고서
5. 6개년 모델·사전 해시 비교표와 mismatch 0 요약
6. Git commit과 실행 transcript

권장 한국어 방법론 문장:

> 6개년 자료에는 동일한 Montreal Forced Aligner 3.4.0 한국어 음향모델,
> phone inventory, 기본 발음사전 및 G2P 규칙을 적용하였다. 2020·2021의
> 기존 산출물은 공통 발음자원과의 전수 동등성 검사를 통과한 경우에만
> 보존하였고, 2022–2025에는 동일 SHA-256의 공통 발음사전을 직접 사용하였다.
> MFA phone과 시간 경계는 후보 탐색을 위한 정렬 정보이며, 실제 음운현상의
> 실현 여부는 음성과 TextGrid를 연구자가 별도로 판정하였다.

최종 보고서가 통과하기 전에는 “통과하였다”를 미래형 계획으로 바꿔 쓴다.

## 시행착오 기록

최초 phone inventory gate에서 기본 사전의 세 번째·네 번째 보정값
`1.77`, `1.4` 등을 phone으로 오인해 prepare가 중단됐다. 장시간 G2P는
시작되지 않았고 output shard는 0개였다.

원인은 자체 parser가 네 숫자 열을 모두 0–1 확률로 가정한 것이었다. 설치된
MFA 3.4.0의 `utils.parse_dictionary_file`은 발음확률, 뒤침묵확률,
앞침묵 보정, 앞비침묵 보정의 최대 네 숫자 열을 허용하며 뒤의 두 보정값은
1보다 클 수 있다. 실제 MFA parser 규칙에 맞춰 수정한 뒤 기본 사전
21,009행·17,968단어의 phone이 acoustic inventory 밖으로 나가는 사례가
0임을 확인했다. 실패 준비본은 다음에 보존했다.

`D:\mfa_common_pron\archive\common_pron_mfa_r1_20260728_pre_method_contract_20260728_132528`

최신 PrepareOnly는 2026-07-28 13:27에 성공했고 G2P output shard는 아직
0개다.
