# ㄴ삽입 — 환경 정의 (B1) — 2026-08-18 개정 제안

> 상태: **연구자 B1 확정 전 개정안**. 2026-07-15 초안은
> `archive/definition_20260715.md`에 보존한다. 후보 검색 코드와 TextGrid 연결은
> 검증됐지만, 이 정의의 전수 추출은 연구자가 B1 범위를 확정한 뒤 시작한다.

## 현상
선행 요소가 자음으로 끝나고 후행 요소가 /i/ 또는 활음 /j/로 시작하는
형태론적·통사적 경계에서 [n]이 수의적으로 삽입되는 현상.
예: 솜+이불→[솜니불], 색+연필→[생년필](삽입+비음화 연쇄),
꽃+잎→[꼰닙], 한+여름→[한녀름]; 구 경계: 옷 입다→[온닙따].
**수의적(variable)** — 실현율이 경계 유형·빈도·운율·화자 변수에 민감
(본 연구의 핵심 질문).

## 환경 조작화 (B2 검색 조건)
후보 = 아래 두 위치에서 (선행요소 자음 종성) + (후행요소 i/j 시작):

1. **어절 내부 경계**: tagged의 어절 내 인접 형태소 쌍 (m1+m2)
   - m1: 마지막 음절에 종성 존재 (한글 분해로 판정)
   - m2: 첫 음절이 {이 야 여 요 유 예 얘} 계열 (i/j 시작)
   - 경계 유형 분류: N+N(합성), 접두(XPN)+N, 어근 결합, 한자어 내부 등
     — m1·m2의 태그 조합으로 자동 분류
2. **어절 간 경계 (구 경계)**: 인접 어절 w1(자음 말음)+w2(i/j 시작)
   - 구문 조건: 프리미엄 표본은 gold_dp로 정확히 (w1이 w2의 의존소인지,
     구 성분 경계인지), 일반 발화는 근사(태그 열)

제외: m2가 조사·어미(J*, E*)인 경우 (ㄴ삽입 환경 아님 — 연음 환경),
숫자·기호 인접, 한 음절 미만 요소.

## 실현 판정 (B3) — 증거원을 섞지 않는 현행 원칙

| 증거 | 출처 | 역할 | 최종 실현값인가 |
|---|---|---|---|
| 표기 반영 | `original_form`·`form` 대조 | 전사자가 표기에 반영한 보수적 보조 신호 | 아니오 |
| 규칙·사전 발음 | G2P·우리말샘 발음 | 가능한 발음과 예외의 참조 | 아니오 |
| 강제 정렬 | MFA `words/phones_mfa` | 후보 어절·분절의 대략적 시간 위치 | 아니오 |
| 연구자 판정 | WAV·spectrogram·TextGrid 직접 검토 | 삽입/비삽입/불확실 및 근거 기록 | **예** |
| 운율 | 선별 KOINA·수동 AP/IP | 경계·운율 변수 | 실현값과 별도 |

MFA phone에 [n]이 있거나 없다는 사실만으로 ㄴ 삽입 실현을 자동 판정하지 않는다.
MFA phone은 공통발음사전의 입력 후보와 음향모델에 의존한 정렬 결과다. 보조
wav2vec2/Hubert 모델을 사용할 경우에도 새 보조열로만 추가하고 수동 판정이나
기존 MFA 열을 덮어쓰지 않는다.

수동 판정표는 최소 다음을 분리한다.

```text
study_id, target_occurrence_id, year, utt_id,
review_context_xmin, review_context_xmax,
realization_decision, confidence, reviewer, reviewed_at,
audio_quality, boundary_adjustment_revision, notes
```

`realization_decision`은 적어도 `realized`, `not_realized`, `uncertain`,
`not_judgeable`을 구분한다.

## 변수 (B4 결합)
- 빈도: m1·m2·전체 어절 빈도 (대화/MP/LS/ML2025/KoFREN), 의미번호별 빈도
- 경계 유형: 형태소/단어/구 (+gold 구문 깊이, 프리미엄)
- 운율: IP/AP 경계 여부·경계성조 (프리미엄, prosody 레이어)
- 사회변수: 성별·연령·사용역 / 화자 무선효과
- 어원: 고유어/한자어/외래어 (etym_type)

## 산출 목표

1. `query_set.json`: 어절 내부·어절 간 조건과 버전을 동결
2. `candidates.csv`: RC0+RC1 active 전사, 형태소/POS, 의미번호·출처,
   WAV·TextGrid pointer, 검토용 어절 문맥 시간
3. `manual_realization.csv`: 실제 실현의 append-only 연구자 판정
4. `analysis_ready.csv`: 후보·판정·빈도·경계유형·운율·사회변수 결합
5. R(brms, 혼합효과 로지스틱): 실현 여부 ~ 빈도 + 경계유형 + 운율 + 사회변수

의미번호가 불확실한 후보를 임의의 최소 의미번호로 확정하거나 검색에서 조용히
삭제하지 않는다. `sense_id/source/status/candidates/confidence`를 별도 열로
보존한다.
