# 계획: 일곱 현상 query 전 형태론 환경·POS 대응 공통 감사

- 작성일: 2026-08-23 KST
- 상태: **설계안 — 코드·query 구현 미승인**
- 계기: NI 동결 v1에서 `편/NNB+이/VCP`가 본모집단 후보로 들어온 사실과
  표면 `요`/분석 `이+요` 보존 예외 확인
- 정지선: 사용자 별도 GO 전에는 query 생성·수정·동결, 후보 재추출, Praat
  작업본 생성, 실현 판정, ledger 기록을 하지 않는다.

## 0. 결론

일곱 현상 모두 문헌 종합 초안과 definition 초안이 실제로 마련되어 있다.
그러나 현재 연구 query까지 동결된 현상은 NI뿐이며, NI에서 학교문법 범주와
말뭉치 POS 태그의 대응 오류가 발견됐다. 따라서 NI Gate 3로 바로 가지 않고,
일곱 현상 모두에 대해 같은 형식의 **현상 범위 카드와 POS·표면형 대응표**를
먼저 만든 뒤 첫 연구 현상을 다시 선택한다.

NI는 이미 구축된 인프라를 시험한 공학적 reference로는 유용하지만, 앞으로도
첫 과학적 분석 현상이어야 한다고 자동 확정하지 않는다.

## 1. 실측한 현재 준비 상태

정본 registry:

```text
config/phenomena_registry.v1.json
```

| 코드 | definition | 현상종합 | 핵심 정독·주장 | query 상태 | 지금 남은 핵심 범위 질문 |
|---|---:|---:|---:|---|---|
| PT | 62행 | 210행 | 5편·33주장 | `draft_pv_only` | 평장애음 집합, ㅎ계열·격음화, 어절 간, NI·사이시옷 중복 |
| NAN | 54행 | 78행 | 1편·3주장 | `draft_pv_only` | ㄴ 앞/ㅁ 앞 범위, 어절 내부·간, 부분 비음화 |
| NAL | 53행 | 110행 | 2편·10주장 | `draft_pv_only` | 장애음+ㄹ 범위, 외래어, NAL/LLN 경계 |
| NI | 75행 | 190행 | 4편·26주장 | v1 `frozen` | 표면 `이` VCP 제외, 표면 `요`/분석 `이+요` 보존, 경계·어원 |
| LLN | 60행 | 179행 | 4편·26주장 | `draft_pv_only` | ㄴㄹ/ㄹㄴ 방향, [ㄹㄹ]/[ㄴㄴ]/중간형, 어종·NAL 중복 |
| VH | 57행 | 209행 | 5편·33주장 | `draft_pv_only` | 표면형/표제어형, 불규칙·방언, 어미 기능, HIA 중복 |
| HIA | 56행 | 142행 | 3편·18주장 | `draft_pv_only` | 활음화·첨가·탈락·축약, 표면형 기준, VH 중복 |

모든 definition·현상종합 경로의 실재를 확인했다. 문헌 정본은 inventory
362행, claim 156행이며 각 현상종합 초안은 정독 범위와 CLM ID를 명시한다.
다만 NI 밖 여섯 definition은 모두
`literature_seeded_pending_researcher_confirmation`이고 실제 환경 분류행은
0이다. 즉, 초안은 준비됐지만 연구자 채택 query는 아직 없다.

## 2. NI에서 드러난 공통 위험

동결 NI v1은 오른쪽 J*/E*를 제외했지만 서술격 `이`가 `VCP`로 태깅되는 점을
포착하지 못했다. 그 결과 다음 두 사례가 NI 표본으로 선택됐다.

```text
PV0015  편/NNB + 이/VCP  → 편인
PV0163  편/NNB + 이/VCP  → 편이에요
```

두 사례는 표면에 `이`가 실제로 나타나므로 NI 본모집단 범위 밖이다. 반대로
표면에는 `요`만 있고 분석기가 `이/VCP+요/...`를 복원한 사례는 제외하면 안
되며, CLM-0002의 별도 `요` 탐색 모집단에 보존해야 한다.

따라서 앞으로는 다음 세 층을 분리한다.

```text
원 표면형·어절 표면형
  ↕ 왕복 확인
형태소 표면·표제어·POS 분석 연쇄
  ↕ 현상별 범위 규칙
후보 포함 / 별도 탐색 / 범위 밖 / 불명 상태
```

POS 하나나 형태소 분석 하나만으로 포함·제외하지 않는다.

## 3. 일곱 현상 공통 범위 카드

각 현상마다 다음 항목을 한 장에 작성한다.

1. 현상의 언어학적 정의와 최소 대조 단위
2. 어절 내부·어절 간·형태소 내부 중 허용 경계
3. 좌우 기저 분절·표면 분절 조건
4. 원 표면형과 형태소 분석 연쇄의 왕복 예
5. 세종/Bareun POS·접사 태그 대응표
6. 본모집단 포함 조건
7. 명시적 제외 조건
8. 별도 탐색 모집단
9. 다른 현상과의 복수 membership·confound
10. 예상 실현 범주와 `not_judgeable` 사유
11. TextGrid·Praat에서 사람이 확인할 항목
12. 필요한 화자·대화·운율·어휘 sidecar
13. 근거 SRC/CLM ID와 근거가 확립하지 않는 것
14. 연구자가 확정해야 할 질문

카드는 query 코드가 아니다. 카드가 승인된 뒤에만 해당 현상의 query 후보를
작성한다.

## 4. POS·표면형 대응 probe

일곱 현상 공통 probe는 전수 추출이 아니라 대표 사례 감사다.

- 원천별 최대 200,000행에서 조기 중단
- 실제 gz 헤더와 첫 행을 다시 측정
- `form`·`original_form`·어절 표면형·형태소 surface/lemma/POS를 구분
- J*/E*, VCP/VCN, VX, NNB, XPN/XSN, 숫자·기호 등 고위험 태그를 표본화
- 포함 예뿐 아니라 반드시 제외·별도 탐색·분석 불일치 예를 함께 둠
- 표면형 왕복 실패는 삭제하지 않고 `surface_analysis_mismatch` 상태로 보존
- probe 결과가 없으면 query 값을 확정하지 않음

NI에서는 최소한 다음 네 분기를 따로 확인한다.

1. 표면 `이` + 분석 `이/VCP` → 본모집단 범위 밖
2. 표면 `요` + 분석 `요/JX` → `요` 별도 탐색
3. 표면 `요` + 분석 `이/VCP+요/...` → 제외 금지, `요` 별도 탐색
4. 표면·분석 대응 불명 → 불명 상태 보존

## 5. 첫 연구 현상 재선정

공통 범위 카드와 probe 뒤 다음 기준으로 첫 현상을 다시 고른다.

| 기준 | 질문 |
|---|---|
| 문헌 준비도 | 핵심 환경·변이·제외 근거가 CLM으로 충분한가 |
| 환경 명료도 | 표면형과 형태소/POS를 안정적으로 왕복할 수 있는가 |
| 겹침 관리 | 다른 현상과의 중복을 상태로 분리할 수 있는가 |
| 표본 규모 | 작은 층화 표본으로 기술 Gate를 검증할 수 있는가 |
| 수동 판정 가능성 | Praat에서 사람이 구분할 실현 범주가 명확한가 |
| 재현성 | exact-ID·TextGrid·sidecar로 공개 파생값을 재현할 수 있는가 |

현재 자료만으로는 NI·LLN·PT·VH/HIA 모두 복합적인 범위 문제가 있고, NAN은
분절 조건이 비교적 단순하지만 직접 정독 근거가 가장 얇다. 따라서 지금 특정
현상을 새 1순위로 자동 선택하지 않는다.

## 6. 개정 작업 순서

```text
Gate 0 공통 구조(완료)
  → F0.5 일곱 현상 범위 카드·POS 대응 감사  ← 다음
  → 연구자 현상별 범위 채택
  → 첫 연구 현상 재선정
  → 선택 현상의 소규모 query 후보·negative probe
  → read-only reviewer + 필요한 사례 Praat 왕복
  → 정식 수동 판정 ledger
  → 다음 현상 반복
```

NI의 기존 G1–G4와 Gate 2는 삭제하지 않는다. 역사적·공학적 기준선으로
보존하되, VCP 정정과 유효 NI 대체 표본 없이는 NI 연구 Gate를 통과한 것으로
간주하지 않는다.

## 7. 다음 구현 전 산출물 제안

별도 GO 뒤 다음 문서·검사기만 먼저 만든다.

```text
docs/reviews/incoming/REVIEW_stage2_seven_phenomena_scope_cards_<date>.md
docs/reviews/incoming/REVIEW_stage2_seven_phenomena_scope_cards_<date>.html
config/phenomenon_scope_cards_candidate_v1_<date>.jsonl
scripts/python/audit_stage2_seven_phenomena_scope_cards.py
tests/test_stage2_seven_phenomena_scope_cards.py
outputs/pilots/stage2_seven_phenomena_scope_cards_<date>/
```

후보 JSONL은 현상당 한 행과 상태 필드를 갖고, 실제 occurrence나 query 결과를
만들지 않는다. HTML은 연구자가 한 현상씩 읽고 질문에 답할 수 있는 파생 뷰다.

## 8. 하지 않는 것

- 동결 NI v1·94만 행·Gate 2 출력 수정·삭제
- 표면 `요`/분석 `이+요` 사례의 VCP 일괄 제외
- 일곱 현상 production query 생성·동결
- G5/G6·MFA·KOINA·wav2vec2·대량 음성 처리
- 자동 실현 판정·정식 ledger·Praat 작업본 생성
- 문헌 workspace·원문·r3·6-tier·동반표 수정

## 9. 다음 사용자 결정

이 계획이 채택되면 다음 GO의 의미는 “일곱 현상 범위 카드와 읽기 전용
검토 HTML을 만들고 독립 검사한다”까지다. 첫 연구 현상 선택이나 query 구현은
그 결과를 본 뒤 별도로 결정한다.
