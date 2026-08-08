# 공통발음 r3 selection-readiness v3 결과

- 날짜: 2026-08-08 KST
- 입력: readiness v2 881,237형 + Stage 13 문맥 donor 독립 감사
- 상태: phone 불변 이차조음 후보 6,141형만 candidate-only 병합 완료
- 미수행: canonical selection, adoption, MFA, TextGrid 변경, 실제 실현 판정

## 1. v3에서 허용한 유일한 추가

다음 조건을 **모두** 만족한 6,141형·90,544회만 새 정렬용 계획 후보로
추가했다.

1. Stage 13 분류가 `unanimous_contextual_support`다.
2. r2 발음 변이가 하나다.
3. 모든 미해결 issue가 `secondary_articulation_cluster`다.
4. 기존 r2 phone 자체가 frozen 사전의 단어·음절 문맥에서 지지된다.
5. direct-unit 치환·분절 삽입·분절 삭제가 하나도 없다.
6. 기존 `r2_pron_phones_json`과 `r2_pron_roman_json`을 바이트 그대로 유지한다.

따라서 `최근에`의 `CH W ↔ tɕʷ`, `편하게`의 `P Y ↔ pʲ` 같은 경우는
MFA 모델의 onset+glide 단위화 근거로만 후보가 됐다. 표준발음이나 실제 음성
실현을 선언한 것이 아니다.

## 2. 전수 회계

| 항목 | readiness v2 | readiness v3 | 변화 |
|---|---:|---:|---:|
| candidate 준비 유형 | 789,649 | 795,790 | +6,141 |
| candidate 준비 출현 | 26,952,517 | 27,043,061 | +90,544 |
| zero-fallback hold 유형 | 91,553 | 85,412 | −6,141 |
| zero-fallback hold 출현 | 894,388 | 803,844 | −90,544 |
| 별도 정책 결정 | 35형·163회 | 35형·163회 | 변화 없음 |

새 planning status는 다음이다.

```text
candidate_r2_contextual_secondary_articulation_equivalent
```

후보 역할은 `mfa_alignment_lexicon_candidate`, 표준발음 관계는
`contextual_model_unitization_not_standard_pronunciation_claim`, 실제 실현
상태는 `not_performed`다.

## 3. 계속 보류한 85,412형

| 근거 범주 | 유형 | 출현 | 다음 처리 |
|---|---:|---:|---|
| canonical–frozen 충돌 | 48,780 | 377,518 | 자동 선택 금지 |
| 복수 지지 변이 | 22,171 | 225,511 | 변이 정책 전까지 보류 |
| eligible donor 없음 | 10,008 | 128,785 | 근거 추가 전 보류 |
| 단일 근거지만 phone 변경 필요 | 4,453 | 72,030 | 규칙별 별도 감사 |
| 합계 | 85,412 | 803,844 | — |

마지막 4,453형에는 `중에서`의 `ng` 삽입, `걔가`의 glide 삽입,
`저희가·너희가`의 ㅢ 관련 `EU_G`, 경음·종성 phone 교체가 섞여 있다. 단일
donor가 있다는 이유만으로 기존 phone을 바꾸지 않는다. 다음 단계는 이 집합을
ㅢ 규칙, 분절 삽입/삭제, 후두 대립·종성 교체로 분리하는 좁은 정책 감사다.
사람이 85,412형을 전수 청취하는 단계는 아니다.

## 4. 실패 안전 기록

Stage 14 첫 실행은 issue 행이 0개인 특수 hold도 분류표에는 존재한다는 점을
엄격한 두 표 token 동등성 검사에서 잡아 출력 전 중단됐다. issue 0개 행은 빈
근거로 명시하고 계속 보류하도록 고친 뒤 재실행했다. 기존 Stage 13, readiness
v2, MFA, TextGrid는 변경되지 않았다.

## 5. 산출물과 독립 감사

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  14_selection_readiness_v3\
    common_pron_r3_selection_readiness_v3.csv.gz
    SELECTION_READINESS_V3_MANIFEST.json

outputs/reports/AUDIT_common_pron_r3_selection_readiness_v3_20260808.json
```

| 산출물 | SHA-256 |
|---|---|
| Stage 14 manifest | `78303fe23feadafe4c9263dfc056ff5e4cbb4d5feab9547bca476079fc41debd` |
| readiness v3 | `b38e5200702e9a71e9976801e9080bb017ed215cd98330a1eb70a9d96e1cf5fa` |
| 독립 감사 | `6a551a7d50640be8bd321325e092c75fa004807c68e61d7e383c08a9f7f4bd56` |

독립 감사기는 881,237행을 v2와 전수 비교해 6,141행의 phone·Roman JSON이
바이트 동일함을 확인했고, 나머지 행의 v2 필드 변화 0, 후보 채택·MFA·TextGrid
변경 0을 확인해 `passed_read_only`로 통과했다.
