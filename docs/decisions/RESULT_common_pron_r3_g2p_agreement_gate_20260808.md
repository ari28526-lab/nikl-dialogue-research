# 공통발음 r3 G2P–규칙 발음 전수 비교 Gate 결과

- 실행일: 2026-08-08 KST
- 실행 ID: `common_pron_mfa_r3_20260807`
- 상태: `success_candidates_not_selected`
- 범위: G2P 후보와 독립 규칙 목표의 ordered broad-Roman exact 비교
- 비범위: canonical 최종 선택, 사전 adoption, 연도별 MFA, TextGrid 변경, 실제 실현 발음 판정

## 1. 왜 이 Gate가 필요한가

Jamo G2P가 310,605개 입력 모두에 1-best phone을 생성했고 no-path와 `spn`이
0이었다는 사실은 계산이 완결됐다는 뜻일 뿐, 그 phone이 연구용 규칙 목표 발음과
같거나 최종 공통발음으로 채택할 수 있다는 뜻이 아니다. 따라서 각 후보 phone을
고정 acoustic-model broad-Roman 단위로 바꾼 뒤, 별도로 계산해 둔 규칙 목표 Roman과
단위 순서와 길이를 포함해 정확히 비교했다.

대상 발음형과 원천 표면형을 구분했다. 여러 원천 어휘가 같은 규칙 목표 한글형을
공유할 수 있기 때문이다. 대상 수준은 기술적 exact 여부를 기록하고, 원천 수준은
우리말샘 근거·사전 충돌·형태음운 환경 보류를 보존한다.

## 2. 전수 결과

### 규칙 목표 대상형 310,605개

| 결과 | 대상형 | 비율 |
|---|---:|---:|
| exact | 96,284 | 30.999% |
| mismatch | 214,321 | 69.001% |

편집거리 분포는 0이 96,284개, 1이 144,848개, 2가 52,806개, 3이
13,594개, 4가 2,567개, 5가 439개, 6이 66개, 7이 1개다. mismatch의
대부분이 작은 차이이더라도 이를 임의로 같다고 간주하지 않았다.

### 원천 표면형 312,410개·4,472,892회

| source Gate | 원천형 | 출현 수 | 의미 |
|---|---:|---:|---|
| `exact_candidate_dictionary_agree` | 3,078 | 184,103 | exact이며 사전 근거도 일치하는 후속 선택 후보 |
| `hold_exact_dictionary_conflict` | 14 | 57 | exact이나 사전 후보와 충돌하여 보류 |
| `hold_exact_no_attested_agreement` | 94,134 | 1,492,123 | exact이나 독립 사전 일치 근거가 없어 보류 |
| `mismatch_not_eligible` | 215,184 | 2,796,609 | 규칙 목표와 달라 자동 선택 불가 |

출현 기준 exact는 1,676,283회(37.476%), mismatch는
2,796,609회(62.524%)다. `exact`는 최종 채택이 아니라 다음 canonical 선택
단계에 들어갈 수 있다는 기술적 자격만 뜻한다.

## 3. 연도별 동일 기준 결과

| 연도 | exact 출현 | mismatch 출현 | 합계 | exact 비율 |
|---:|---:|---:|---:|---:|
| 2020 | 191,245 | 325,314 | 516,559 | 37.023% |
| 2021 | 392,339 | 632,563 | 1,024,902 | 38.281% |
| 2022 | 264,241 | 432,004 | 696,245 | 37.952% |
| 2023 | 218,709 | 369,751 | 588,460 | 37.166% |
| 2024 | 315,998 | 522,546 | 838,544 | 37.684% |
| 2025 | 293,751 | 514,431 | 808,182 | 36.347% |

여섯 연도 모두 같은 target inventory, acoustic/G2P model, broad-Roman mapping,
exact 비교 함수와 source evidence routing을 사용했다. 연도는 선택 기준을 바꾸는
분기점이 아니라 출현 회계를 나누는 열이다.

## 4. 기존 문제 예시 회귀검사

| 표면형 | 규칙 목표 | 비교 | 처리 |
|---|---|---|---|
| `놨던` | `놛떤` | exact | 사전 독립 근거 보류 |
| `어쨌든` | `어짿뜬` | exact | 사전 일치 후속 후보 |
| `없는` | `엄는` | exact | 사전 독립 근거 보류 |
| `있는` | `인는` | mismatch | 자동 선택 불가 |
| `있지` | `읻찌` | mismatch | 자동 선택 불가 |

`있는`과 `있지`는 G2P가 정상 종료돼 phone을 만들었더라도 규칙 목표의 단위열과
같지 않음을 보여 준다. 이 예시는 향후 코드 변경 때 다시 검사한다.

## 5. 산출물과 독립 감사

전수 Gate:

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
04_g2p_rule_agreement_gate
```

Gate manifest:

```text
G2P_AGREEMENT_GATE_MANIFEST.json
SHA-256 8e4252885db93cd9abf47b2265fcb1cee699f3c4a5c63db475a371b8854df516
```

별도 감사기는 target 310,605행과 source 312,410행을 다시 읽어 phone→Roman,
exact/mismatch, 편집거리, source routing, 연도 합계, target–source 집계, 다섯 회귀
예시와 모든 SHA를 재계산했다. 결과는 `passed_read_only`다.

```text
outputs/reports/AUDIT_common_pron_r3_g2p_agreement_gate_20260808.json
SHA-256 19957d63f2ef4f627b28b74dfcad80ffe800e63a33ecd09cd6abac6bab14245c
```

사람이 결과의 성격을 파악할 수 있도록 75행 소형 증거표를 만들었지만 승인표는
아니다. 이 단계에서 사용자가 검토하거나 승인할 일은 없다.

```text
outputs/reviews/common_pron_r3_g2p_agreement_gate_20260808/EVIDENCE_SAMPLE.csv
SHA-256 516bbbb8a3e3281de106c0846d351ba95bc4de61c9b4a6669cbf30c027a228e2
```

## 6. 다음 단계와 금지 사항

다음 별도 단계에서는 exact 후보 중 사전 근거 일치 3,078형을 우선 대상으로 삼고,
사전 충돌 14형과 독립 근거 없는 94,134형은 서로 다른 보류 경로로 처리한다.
mismatch 215,184형은 G2P 후보를 자동 채택하지 않는다. 그 단계의 결과도 canonical
선택표와 provenance를 생성하고 독립 adoption Gate를 통과하기 전에는 MFA 사전이
아니다.

현재까지 다음 값은 모두 `false`다.

- `candidate_is_final_selection`
- `canonical_selection_performed`
- `adoption_performed`
- `annual_mfa_started`
- `textgrids_modified`
- `actual_realization_claimed`
