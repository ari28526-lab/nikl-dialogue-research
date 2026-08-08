# 공통발음 r3 selection-readiness v4 결과

## 결론

독립 감사된 Stage 17의 14형·200회만 readiness v3의 zero-fallback hold에서
정렬용 candidate-only로 옮겼다. 881,237형 가운데 그 14형 외의 행은 한 필드도
바꾸지 않았다.

| 항목 | readiness v4 |
|---|---:|
| 전체 어절형 | 881,237 |
| 전체 출현 | 27,847,068 |
| candidate 준비 형 | 795,804 |
| candidate 준비 출현 | 27,043,261 |
| zero-fallback hold 형 | 85,398 |
| zero-fallback hold 출현 | 803,644 |
| 기존 정책결정 대기 | 35형·163회 |
| Stage 17 신규 candidate-only | 14형·200회 |

`candidate_attested_rule_exact_full_context_projection`은 사전 등재 `pron_1/2`와
규칙 Roman이 같고 전체 model phone열이 단일 문맥 근거로 재구성됐다는 뜻이다.
최종 발음 선택, 실제 실현 판정 또는 연구자의 음성 판정이 아니다.

## 산출물과 감사

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  18_selection_readiness_v4\
    SELECTION_READINESS_V4_MANIFEST.json
    common_pron_r3_selection_readiness_v4.csv.gz

outputs/reports/AUDIT_common_pron_r3_selection_readiness_v4_20260808.json
```

| 파일 | SHA-256 |
|---|---|
| readiness v4 manifest | `1664c07bb336b9e8a1e150b8733e5df6f949dedc34e1e73533abfcfbba1951c9` |
| 독립 감사 | `a54faf1ec55082f00324e2edcb01fbfaf27006f4547898712c3cd4b869f54acc` |

독립 감사기는 v3와 v4 881,237행을 같은 순서로 전수 비교했다. 14형에서 허용된
planning 필드만 바뀌고, 비대상 행 변화 0, 최종선택 flag 0, TextGrid 변화 0을
확인했다.

## 시행착오와 회계 수정

첫 v4 실행은 기존 `policy_candidate_multiple_rule_dictionary_conflict` 35형·163회를
candidate 또는 hold 합계에 포함하지 않고 전체 출현 기대치를 계산한 오류를 Gate가
잡아 final 승격 전에 중단됐다. Stage 14 정본 총계 27,847,068을 다시 확인하고 이
별도 정책결정 범주를 그대로 보존하도록 계약·회귀 테스트를 수정했다. 실패 partial은
`archive_intermediate`로 보존 이동했다.

## 다음 단계

현재 사용자 검토는 필요 없다. 다음 자동 단계는 readiness v4 전체의 후보·hold·
정책결정 범주를 다시 요약해 canonical selection/adoption에 들어가기 전 남은
결정 단위를 확정하는 것이다. adoption 이전에는 MFA나 TextGrid를 변경하지 않는다.
