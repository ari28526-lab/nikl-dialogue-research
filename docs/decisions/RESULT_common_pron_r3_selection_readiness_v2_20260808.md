# 공통발음 r3 selection-readiness v2 결과

- 날짜: 2026-08-08 KST
- 범위: canonical 881,237형
- 입력: stage 09 readiness v1 + stage 11 규칙·phone coverage 감사
- 상태: candidate-only 병합·독립 전수 감사 완료
- 미수행: canonical 최종 선택, adoption, MFA, TextGrid 변경, 실제 실현 판정

## 1. 무엇을 바꿨는가

readiness v1의 no-rule zero-fallback 보류 가운데 다음 두 집합만 계획 후보로
추가했다.

1. 모든 r2 변이가 수의적 위치동화로만 다른 36,568형·525,747회
2. 위 집합과 겹치지 않으며 모든 r2 변이가 frozen Korean MFA 기본사전과
   정확히 일치하는 811형·229,177회

총 37,379형·754,924회다. phone열을 새로 만들거나 고치지 않고 기존 r2 변이를
그대로 **MFA 정렬용 lexicon 후보**로 연결했다. `rule_pron_roman`은 의무적
표준발음 참조로 보존했다.

일부 변이만 위치동화인 82형과 나머지 no-rule 미해결 48,043형은 기존 hold를
유지했다. target projection 미해결 43,428형과 정책 결정 35형도 변경하지 않았다.

## 2. 전후 회계

| 항목 | readiness v1 | readiness v2 | 변화 |
|---|---:|---:|---:|
| candidate 준비 유형 | 752,270 | 789,649 | +37,379 |
| candidate 준비 출현 | 26,197,593 | 26,952,517 | +754,924 |
| zero-fallback hold 유형 | 128,932 | 91,553 | -37,379 |
| zero-fallback hold 출현 | 1,649,312 | 894,388 | -754,924 |
| 별도 정책 결정 유형 | 35 | 35 | 0 |

잔여 zero-fallback hold는 다음 두 범주다.

| 범주 | 유형 | 출현 |
|---|---:|---:|
| no-rule 실질 불일치 잔여(82+48,043) | 48,125 | 385,183 |
| target projection 미해결 | 43,428 | 509,205 |
| 합계 | 91,553 | 894,388 |

## 3. 대표 행

### `한번`

```text
rule_pron_roman: H A n _ B EO n
planning_candidate_phones: h ɐ m b ʌ n
planning_candidate_roman: H A M B EO N
planning_status: candidate_r2_optional_place_assimilation_alignment_variant
planning_standard_relation: optional_variant_not_mandatory_standard
```

표준 참조와 정렬용 변이를 같은 값으로 덮어쓰지 않았다.

### `왜`

```text
rule_pron_roman: WAE
planning_candidate_phones: w eː
planning_candidate_roman: W E
planning_status: candidate_r2_exact_frozen_dictionary_alignment_variant
planning_standard_relation: frozen_alignment_variant_standard_relation_not_claimed
```

frozen 기본사전과의 정확 일치는 acoustic model 호환 근거이지 표준발음 또는 실제
실현 판정이 아니다.

### `중에서`

```text
rule_pron_roman: J U ng _ E _ S EO
r2_pron_phones: tɕ uː e sʰ ʌ
planning_candidate: []
planning_status: hold_no_surface_rule_substantive_mismatch
```

분절 누락 가능성이 있으므로 fallback하지 않았다.

### `한국`

두 r2 변이 중 하나만 수의적 위치동화 조건을 충족하므로 전 변이를 일괄 승인하지
않고 `some_variants_optional_place_assimilation` hold로 남겼다.

## 4. 전수 보존 검사

- canonical 881,237행을 v1과 v2에서 같은 순서로 대조했다.
- 새 후보 37,379행에서 허용된 planning 필드만 바뀌었다.
- 그 밖의 795,733행과 계속 hold인 행의 기존 v1 필드는 전부 동일하다.
- 모든 `rule_pron_roman`, r2 phone/roman, 사전·형태소·연도별 출현 정보가
  보존됐다.
- 모든 행의 `planning_is_final_selection=false`,
  `planning_actual_realization_status=not_performed`를 확인했다.
- 독립 감사 상태는 `passed_read_only`다.

## 5. 산출물

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  12_selection_readiness_v2\
    common_pron_r3_selection_readiness_v2.csv.gz
    SELECTION_READINESS_V2_MANIFEST.json

outputs/reports/AUDIT_common_pron_r3_selection_readiness_v2_20260808.json
```

| 산출물 | SHA-256 |
|---|---|
| stage 12 manifest | `92da4e3cd1403b15addbeef5816cf57dc814da74c4011065e6e02c4a622e0801` |
| 독립 감사 | `36cd7f0cd5ce5314834e3e5191930cb68f45f4cf3239505166d809269ff81949` |

## 6. 다음 Gate

다음은 남은 91,553형을 두 hold 계층으로 분리해 기존 계산 근거만으로 회수 가능한
반복 패턴을 찾는 읽기 전용 단계다. 같은 G2P를 다시 실행하거나 r2 전체를 fallback
하지 않는다. 새 근거가 없는 행은 계속 보류한다. canonical selection과 adoption은
잔여 hold 정책, 복수 변이 정책 35형, 최종 lexicon manifest가 명시된 뒤 별도
Gate에서만 수행한다.
