# wav2vec2 한국어 phone 인식 모델의 연구 보조층 검토

작성일: 2026-07-27
상태: **후속 소표본 채택 — CSV 검색 인프라 완성 뒤 표적 구간만 실행**

## 결론

`slplab/wav2vec2-xls-r-300m_phone-mfa_korean`은 딥러닝 모델을 새로 학습하지
않아도 추론에 사용할 수 있다. 그러나 현재 MFA를 대체하거나 실제 음운
실현의 정답으로 사용하지 않는다.

연구 파이프라인에서의 적절한 위치는 다음과 같다.

```text
동결 CSV·형태소/표기 환경으로 후보 추출
  → MFA 기준 발음 강제정렬
  → wav2vec2의 독립적인 음향 기반 phone 후보열
  → 두 결과의 불일치 구간을 검토 우선순위로 표시
  → 연구자가 WAV·TextGrid를 보고 최종 실현 판정
```

즉, MFA `phones`와 마찬가지로 모델 출력도 연구자의 실현 판정값이 아니다.
canonical 4-tier `words/phones/morphemes/utterance`에는 바로 합치지 않고,
필요하면 연구자 점검 사본에만 `wav2vec_phone_candidate` tier로 추가한다.

## 확인한 모델 정보

모델 카드:
<https://huggingface.co/slplab/wav2vec2-xls-r-300m_phone-mfa_korean>

파일 목록:
<https://huggingface.co/slplab/wav2vec2-xls-r-300m_phone-mfa_korean/tree/main>

- 기반: `facebook/wav2vec2-xls-r-300m`
- 과제: CTC 기반 한국어 phone 인식
- 학습: 한국어 모어 화자 낭독 음성 108시간, 54,000표본, 540화자
- 평가: 같은 자료 계열 12시간, 6,000표본, 60화자
- 모델 카드 보고 Phone Error Rate: 3.88%
- 저장소 총량: 약 1.26GB
- 공개 환경 표기: Transformers 4.21.3, PyTorch 1.12.1
- 라이선스: Apache-2.0

Hugging Face의 CTC pipeline은 token/character offset을 시간으로 바꾸는
기능을 제공하므로 phone 후보의 대략적인 시간층을 만들 수 있다.

문서:
<https://huggingface.co/docs/transformers/main_classes/pipelines>

## 연구상 장점

1. 기준 발음에 구속된 MFA와 달리 음성에서 phone열을 독립적으로 추정한다.
2. 예상 phone과 다른 발화를 자동 확정하지 않고 검토 대상으로 선별할 수 있다.
3. ㄴ 삽입처럼 삽입·삭제·대치 후보의 수동 검토 우선순위를 만들 가능성이 있다.
4. 전체 음성을 전량 판정할 필요 없이 CSV로 추출한 연구 후보에만 적용할 수 있다.

## 한계와 방법론적 위험

1. 낭독체 학습 결과를 현재 대화 음성에 그대로 일반화할 수 없다. 카드의
   3.88%는 현재 코퍼스의 기대 오류율이 아니다.
2. 모델 이름과 phone표가 MFA 계열 label을 사용하므로 MFA와 완전히 독립된
   인간 음성학 정답으로 볼 수 없다. MFA의 phone inventory와 label 편향을
   학습했을 가능성을 별도로 평가해야 한다.
3. 자유 phone 인식 결과는 reference text를 강제한 정렬이 아니므로 어절·
   형태소 대응과 연속적인 TextGrid 경계를 자동 보장하지 않는다.
4. CTC timestamp는 후보 시간값이지 수동 분절의 정답이 아니다.
5. 현재 Intel N200에서 2020–2025 전량을 돌릴 효율은 실측 전 보장할 수 없다.
   먼저 연구 후보 수십 건의 CPU 처리율을 재고, 이후에도 전체 코퍼스가 아니라
   검색 후보 subset에 한정하는 것을 기본으로 한다.

## 안전한 파일럿

30–50개 발화를 다음처럼 균형 표집한다.

- ㄴ 삽입 예상 환경이면서 수동 실현
- 같은 환경이지만 수동 비실현
- 유사 음향의 비대상 대조군
- 여러 연도·화자·성별·발화 길이
- 조용한 음성과 중첩·잡음·축약 음성

세 결과를 분리 보존한다.

1. 사전·규칙에서 나온 예상 phone
2. MFA 강제정렬 phone과 시간
3. wav2vec2가 인식한 phone 후보와 CTC 시간

평가는 최소한 다음을 포함한다.

- 수동 판정 대비 ㄴ 삽입 후보 precision·recall
- 전체 phone error 및 삽입·삭제·대치별 오류
- MFA·수동 경계 대비 CTC timestamp 오차
- 화자·연도·잡음·발화 길이별 실패율
- CPU/GPU별 음성 1시간당 처리시간과 peak RAM
- 모르는 phone·빈 출력·모델 load 실패 inventory

GO 조건은 모델이 실현을 대신 판정하는 것이 아니라, 사람이 검토할 표본을
줄이면서 대상 현상의 recall을 충분히 보존한다는 증거가 생기는 것이다.

## 실행 환경 원칙

- 현재 `mfa` conda 환경과 분리한 Python 3.10/3.11 전용 환경을 만든다.
- 모델 revision과 모든 다운로드 파일 SHA256을 manifest에 고정한다.
- `trust_remote_code=False`를 유지한다.
- 저장소 가중치는 `safetensors`가 아닌 `pytorch_model.bin`이므로 출처·
  revision을 검증하고 기존 연구 환경에 임의로 로드하지 않는다.
- 원 WAV와 canonical TextGrid는 읽기 전용이다.
- 출력은 별도 `work`/`outputs` 경로와 별도 run ID에 저장한다.
- 파일럿 통과 전 canonical CSV·MFA 결과·4-tier에 새 column/tier를 넣지 않는다.

## 현재 결정

2021 MFA 실행과 전수 QC를 우선한다. 이 모델은 현재 대량 작업의 가속책이나
MFA 오류 수정책으로 투입하지 않는다. 이후 ㄴ 삽입 등 표적 현상 추출
인프라가 완성되면, CSV 검색 결과에서 해당 부분만 별도 소표본으로 뽑아
음향 후보 탐지층으로 검증한다. 이 순서는 2026-07-27 사용자 결정으로
채택했고 2026-07-28 다시 확인했다. 전 코퍼스 일괄 추론은 현재 범위가
아니다.
