# 공통 발음사전 A/B 파일럿과 연도별 재정렬 순서

작성일: 2026-07-28
상태: **파일럿 우선 결정 — 2022 전량 및 2020·2021 재실행 보류**

관련 문서:

- `DESIGN_common_pronunciation_lexicon_2020_2025_20260727.md`
- `PILOT_common_pronunciation_full_corpus_20260728.md`
- `NOTE_wav2vec2_phone_candidate_layer_20260727.md`
- `AUDIT_2020_2021_MFA_comparison_and_2022_gate_20260728.md`

## 1. 현재 상태를 정확히 구분한다

완료된 것은 다음과 같다.

- 2020·2021 기존 공통 조건 이전 baseline 전수 MFA와 독립 QC
- 2020–2025 동결 CSV 5,103,356행의 공통 vocabulary 구축
- 881,237개 고유 MFA 어절 확정
- enriched `pron_1/2`와 legacy `pron_g2p` 원천 전수 감사
- 기존 결과를 덮어쓰지 않는 D: 격리 release 구조

아직 완료되지 않은 것은 다음과 같다.

- 출처 보존 `pronunciation_registry`
- 사전 한글 발음을 현재 MFA 3.4.0 phone alphabet으로 옮기는 검증된 변환
- 정책 A baseline-cache 사전과 정책 B 사전 예외·변이 포함 사전
- 두 사전의 manifest와 fingerprint
- 동일 WAV·lab A/B 정렬 파일럿과 연구자 검토

따라서 현재 상태를 “공통 MFA 사전 완성”으로 부르지 않는다. 정확히는
**공통 사전 구축을 위한 전수 모집단·원천 감사 완료**다.

## 2. 지금 선택: 연도 전량보다 파일럿이 먼저다

지금 2020을 새 조건으로 다시 돌릴 수는 없다. 아직 채택할 공통 사전 release가
없기 때문이다. 2022를 기존 inline G2P 조건으로 먼저 진행하면, 곧 정책 B를
채택했을 때 2022도 다시 돌려야 하고 6개년 입력 기준이 잠시 혼재한다.

따라서 실행 순서를 다음처럼 고정한다.

1. 현재 MFA acoustic/dictionary phone inventory와 hash 동결
2. 전체 881,237어절의 출처 보존 registry 생성
3. 한글 사전 발음→현재 MFA phone 변환 동등성 파일럿
4. 정책 A·B 파생사전과 재현 manifest 생성
5. 기존 층화 표본과 발음 stress 표본을 합친 A/B MFA 파일럿
6. 자동 QC와 연구자 WAV·TextGrid 검토
7. 정책 채택 뒤에만 연도 전량 순서 확정

이 gate 동안 2022 전량은 방법론 HOLD를 유지한다.

## 3. A/B 결과에 따른 연도별 결정

### 정책 A가 현재 baseline과 phone 후보까지 동등한 경우

정책 A가 inline G2P를 미리 계산한 cache일 뿐이고, 2020·2021에서 실제 사용한
단어별 발음 후보와 전수 동등하면 2020·2021 재정렬의 계산상 이득이 없다.

```text
A 동등성 통과
  → 2020·2021 baseline을 공통 release와 연결해 보존
  → 2022 전량
  → 2023 → 2024 → 2025
```

전수 동등성은 파일명이나 모델 이름이 아니라 word–phones 집합, tokenizer,
모델·사전 hash와 parameter로 증명한다.

### 정책 B가 사전 예외·대체 발음을 실제로 추가하거나 바꾸는 경우

정책 B를 채택하면 6개년 비교 가능성을 위해 2020·2021부터 같은 새 release로
다시 정렬하는 것을 기본 순서로 한다.

```text
B 파일럿 채택
  → 2020 새 run_id 재정렬·전수 QC
  → 2021 새 run_id 재정렬·전수 QC
  → 2022 → 2023 → 2024 → 2025
```

기존 2020·2021 CSV·TextGrid·DB·marker·보고서는 baseline archive로 유지한다.
새 결과는 별도 staging과 run ID를 사용하며 기존 final을 자동 덮어쓰거나
canonical로 자동 승격하지 않는다.

2022를 먼저 진행했다가 2020·2021로 돌아오는 순서는 정책 B 가능성이 남아
있는 현재에는 권하지 않는다. 계산 중복과 release 혼재를 늘리기 때문이다.

## 4. wav2vec2 보조층의 확정 계약

사용자 결정에 따라
`slplab/wav2vec2-xls-r-300m_phone-mfa_korean`을 보조적으로 사용한다.

- MFA의 기존 `words`·`phones` interval을 수정·대체하지 않는다.
- canonical 4-tier TextGrid와 동결 CSV를 덮어쓰지 않는다.
- 모델 phone열·CTC 시간·신뢰도·MFA와의 차이는 별도 append-only 산출물에
  `utterance_id`, `run_id`, `model_revision`으로 연결한다.
- TextGrid가 필요하면 `07_review`의 연구자 점검 사본에만
  `wav2vec_phone_candidate` tier를 추가한다.
- 정렬 실패·경계 극단치·사전 후보 충돌의 검토 우선순위와 발음 후보 비교에
  사용하되 실제 음운 실현의 판정값으로 사용하지 않는다.
- 모델을 사용한 CTC 정렬을 만들더라도 MFA phone 경계를 고쳐 쓰지 않고
  두 시간열을 병렬 보존한다.

첫 적용은 A/B stress 표본 중 30–50개 발화다. 별도 Python 환경, 고정된 모델
revision/hash, `trust_remote_code=False`, 원 WAV 읽기 전용을 지킨다.

## 5. 다음 구현 단위와 완료 gate

다음 코드 변경은 한 번에 전량 MFA를 시작하는 러너가 아니라 아래의 작은
재현 가능한 단위로 나눈다.

1. phone inventory·모델 fingerprint 추출기
2. registry builder와 출처·중복·충돌 감사기
3. 한글 발음→현재 MFA phone 변환기와 회귀표
4. 정책 A/B `.dict` builder와 manifest 검증기
5. 결정적 A/B 표본 builder
6. A/B MFA 실행·자동 QC·연구자 검토 묶음
7. 별도 wav2vec2 소표본 runner와 MFA 불일치 보고서

전량 GO에는 최소한 다음이 필요하다.

- phone set 밖 기호 0
- residual OOV 0 또는 발화별 설명 가능한 inventory
- 같은 입력에서 사전·manifest hash 재생성 일치
- A/B 모두 출력 수량·tier·시간 연속성 hard failure 0
- 사전 변이 표본의 연구자 청취 검토
- baseline 대비 경계 극단치·`spn`·실패율·벽시계·temp 사용량 비교
- wav2vec2 결과가 기존 MFA 또는 canonical 파일을 변경하지 않았다는 감사

## 6. 용량과 보존

현재 공통 발음 준비 release는 약 28MiB이므로 파일럿 자체의 용량 문제는
없다. 2021 temp의 재계산 가능 31.365GiB는 실제 전량 재정렬 직전까지
명시 승인 없이 삭제하지 않는다.

정책 B 채택 뒤에는 연도별로 하나씩 실행하고, 각 연도 독립 QC와 보존
manifest가 끝난 뒤 재계산 가능 temp만 별도 승인으로 정리한다. 여러 연도
full temp를 동시에 누적하지 않는다.
