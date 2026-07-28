# 2020–2025 공통 발음사전 A/B MFA 파일럿 결과

## 결론

자동 파이프라인은 완료됐고 결과는 **수동 검토 필요** 상태다. 정책 B를
채택하거나 기존 2020·2021을 재실행하라는 결론은 아직 내리지 않는다.

- 모집단: 2020–2025 동결 코퍼스 전체 vocabulary 881,237개
- 정렬 표본: 6개년 × 실제 화자 5명 × stress/control 2발화 = 60발화
- 정책 A: 기존 `korean_mfa.dict` + 표본 OOV current G2P 1-best
- 정책 B: A + exact-word 우리말샘 `pron_1/2` 변이
- A/B WAV·lab: 120파일쌍 SHA256 불일치 0
- 기존 2020·2021 canonical CSV/TextGrid와 원자료: 비변경

정본 실행:

```text
release = common_pron_pilot_full6y_20260728
run     = ab_stress_control_20260728_01
commit  = e4a69ad42c441076ddc7ea0f23edca05592c296f
```

## 사전과 registry

| 항목 | 값 |
|---|---:|
| registry | 199,119행 |
| 우리말샘 policy B eligible 원천 | 25,988행 |
| 기본 사전 | 17,968단어 / 21,009행 |
| 정책 A | 18,158단어 / 21,199행 |
| 정책 A 표본 OOV 추가 | 190행 |
| 정책 B | 18,158단어 / 21,214행 |
| 정책 B 고유 추가 변이 | 15행 / 15단어 |
| 표본 G2P 실패→`spn` | 0 |
| acoustic inventory 밖 phone | 0 |

기본 MFA 사전의 선택적 확률 4열을 phone과 분리했다. 정책 A/B 모두
기본 21,009행의 순서·phone·확률을 line-for-line 보존한다. 새 G2P와
사전 변이는 확률을 임의 추정하지 않고 MFA 기본 발음 가중치 1.0인
무확률 행으로만 추가했다. 따라서 이 결과는 변이 **availability**
파일럿이며 발음확률 추정 결과가 아니다.

`궹장히` 한 발음형은 current G2P에서 phone으로 변환되지 않아
`attested_pron_g2p_missing`으로 명시적으로 제외했다.

## MFA와 4-tier QC

| 정책 | 정렬 | 오류 | 경과 | `spn` | 4-tier QC |
|---|---:|---:|---:|---:|---:|
| A | 60/60 | 0 | 38.165초 | 0 | 60/60 |
| B | 60/60 | 0 | 34.464초 | 0 | 60/60 |

두 정책 모두 default beam에서 끝났고 확대 beam은 필요 없었다.
최종 TextGrid 120개는 모두 다음 네 tier를 가지며, 각 tier가 0초부터
파일 끝까지 domain을 덮는다.

```text
words
phones
morphemes
utterance
```

## A/B 자동 비교

사전 원천 기준 stress 30개를 current phone 변환 뒤 다시 분류했다.

| 비교 집단 | 발화 |
|---|---:|
| `stress_effective` | 20 |
| `stress_screened_no_effect` | 10 |
| `control` | 30 |

실제 B 변이 stress는 모든 연도에 남았다.

```text
2020=3, 2021=3, 2022=4, 2023=3, 2024=3, 2025=4
```

phone열이 달라진 것은 3발화이며 모두 `stress_effective`다.

| 연도 | 발화 ID | token | phone edit distance |
|---|---|---|---:|
| 2020 | `SDRW2000001214.1.1.95` | 있다 | 2 |
| 2023 | `SDRW2300000171.1.1.108` | 그것 | 2 |
| 2024 | `SDRW2400002901.1.1.111` | 수가 | 1 |

word label 변화는 0/60, control phone열 변화도 0/30이다.

## 경계 차이의 주의점

phone열이 같은 별도 A/B 실행에서도 동일-index 경계가 움직였다.

| 집단 | 비영 경계 차이 | 최대 |
|---|---:|---:|
| effective stress | 6/20 | 0.060초 |
| screened no-effect stress | 3/10 | 0.010초 |
| control | 7/30 | 0.070초 |

control의 최대 70ms는 이 파일럿의 경험적 run-to-run 잡음 기준이다.
경계 이동만으로 정책 B가 개선됐다고 판단하지 않는다.

## 연구자가 먼저 볼 파일

요약:

```text
D:\mfa_common_pron\releases\common_pron_pilot_full6y_20260728\
  06_ab_results\ab_stress_control_20260728_01\comparison\RESULTS.md
```

발화별 A/B WAV·TextGrid 경로와 비교값:

```text
...\comparison\ab_utterance_comparison.csv
```

사전 추가 후보와 출처:

```text
...\04_mfa_lexicons\pilots\ab_stress_control_20260728_01\
  policy_B_added_variants.csv
```

검토 순서:

1. 위 3개 phone열 변화 발화를 먼저 듣고 A/B TextGrid를 나란히 본다.
2. 나머지 `stress_effective` 17개에서 B 변이가 선택되지 않은 이유를 본다.
3. `stress_screened_no_effect`와 control의 경계 차이를 잡음 기준으로 본다.
4. 수동 판단 뒤 정책 A 유지, B 보완 후 재파일럿, B 채택 중 하나를 결정한다.

## 2026-07-28 수동 검토와 후속 결정

첫 3발화의 사용자 검토 결과:

| token | 판정 | 메모 |
|---|---|---|
| 있다 | B가 더 나음 | 경음 phone이 더 적절; `t͈` 해석 필요 |
| 그것 | 둘 다 무난 | A가 유성음을 조금 더 반영 |
| 수가 | A가 더 나음 | B의 `수까`가 이 발화에는 부적절 |

후속 형태소 감사에서 `수가`의 사전 후보는 `수가/NNG`, 실제 발화는
`수/NNB+가/JKS`로 확인됐다. exact-word policy B는 서로 다른 형태소 구조를
구분하지 못했으므로 production 정책으로 채택하지 않는다. 이는 사전 발음을
버린다는 뜻이 아니라 다음처럼 역할을 분리한다는 뜻이다.

- 모든 사전 발음과 출처는 공통 registry·검색 CSV에 보존
- 어절 occurrence의 형태소 구조와 호환되는 후보만 정렬 후보로 분류
- 같은 plain word의 전 occurrence 감사 전에는 MFA 전역 활성화 금지
- wav2vec2 phone은 검색 뒤 선택 발화의 별도 보조열로만 추가

30 stress 발화 형태소 감사와 새 계약은 다음을 참조한다.

- `PILOT_common_pron_occurrence_match_20260728.csv`
- `PILOT_common_pron_occurrence_match_20260728.manifest.json`
- `docs/decisions/DECISION_common_pronunciation_resource_v2_20260728.md`

## 검증과 이력

- Python unittest 100개 통과
- PowerShell 안전검사 7개 파일 통과
- MFA 3.4 자체 dictionary parser 재검증 통과
- A/B 실제 사전 기본 21,009행 prefix 동일
- registry base 후보 17,082행의 숫자 phone 0, inventory 밖 phone 0
- TextGrid 120개 parse 실패 0, tier domain 실패 0
- 비교표 60행의 WAV/TextGrid 링크 누락 0
- 같은 RunId 재실행: 7단계 marker/hash 전부 재사용, exit 0
- D: `DATA_SSD` 최종 여유 263.821GiB

시행착오·원인·archive 위치와 수정 근거는
[`MONITOR_common_pron_AB_pilot_20260728.md`](../../docs/decisions/MONITOR_common_pron_AB_pilot_20260728.md)에
시간순으로 기록했다.
