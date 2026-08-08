# 공통발음 r3 G2P 불일치 전수 진단 결과

- 날짜: 2026-08-08 KST
- 입력: r3 G2P–규칙 Roman agreement Gate의 mismatch 전부
- 상태: `passed_read_only` 진단 완료, canonical 선택·adoption 전
- 적용 범위: 2020–2025 공통 target·source

## 1. 왜 이 진단을 했는가

agreement Gate에서 310,605개 target 중 214,321개(69.001%)가 exact가 아니었다.
그러나 이 숫자를 그대로 ‘잘못된 발음’으로 해석할 수는 없다. 고정 Korean MFA
acoustic model의 한 phone이 장음 또는 활음의 성질을 함께 표상할 수 있고, 반대로
같아 보이는 broad group 안에서도 연구상 보존해야 할 대조가 있을 수 있기
때문이다. 따라서 최종 r3 발음을 고르기 전에 다음을 분리했다.

1. acoustic-model phone 표상과 Roman 단위화의 차이일 가능성
2. 표상 차이 같지만 근거가 충분하지 않아 추가 검토가 필요한 경우
3. 같은 acoustic-model group 안의 대조
4. 실제 규칙 예상형과 다른 후보로 보아야 할 경우

이 단계는 G2P를 정답으로 승인하는 단계가 아니다. 실현 발음 판정도 아니며,
MFA·TextGrid·기존 DB를 변경하지 않는다.

## 2. 방법

후보 phone을 동결 acoustic-model broad Roman으로 변환한 순서열과 규칙 예상
Roman 순서열 사이에서 unit-cost Levenshtein 편집을 계산했다. 각 source에는
원래의 형태소·사전·연도별 출현 근거를 다시 연결했다. 편집은 `SUB`,
`RULE_ONLY`, `CANDIDATE_ONLY`로 기록했으며, 동일 편집 signature를 반복
패턴으로 집계했다.

표상 동등성 후보는 다음의 좁은 조건에서만 분류했다.

- 같은 Roman 단위의 연속 반복 중 하나가 acoustic phone의 장음 표지로
  나타난 경우
- 규칙 Roman의 `Y`가 인접 phone의 구개화 또는 고유 구개 조음에 포함된 경우
- 규칙 Roman의 `W`가 인접 phone의 원순화에 포함된 경우

이 조건을 만족해도 `automatic_equivalence_approved=false`로 유지했다. 즉,
자동 진단은 검토 경로를 정할 뿐 최종 발음 동등성을 선언하지 않는다.

## 3. 전수 결과

### 3.1 target 214,321개

| 진단층 | target 수 | 비율 |
|---|---:|---:|
| 표상 동등성 후보 | 124,564 | 58.120% |
| 표상 추가 검토 | 30 | 0.014% |
| model 내부 대조 검토 | 5,988 | 2.794% |
| 실질 차이 후보 | 83,739 | 39.071% |

### 3.2 source 불일치 출현 2,796,609회

| 진단층 | 출현 수 | 비율 |
|---|---:|---:|
| 표상 동등성 후보 | 1,686,625 | 60.310% |
| 표상 추가 검토 | 106 | 0.004% |
| model 내부 대조 검토 | 34,667 | 1.240% |
| 실질 차이 후보 | 1,075,211 | 38.447% |

가장 큰 패턴은 `RULE_ONLY:Y` 729,818회, `RULE_ONLY:N` 442,081회,
`RULE_ONLY:W` 226,915회였다. 앞의 `Y/W`는 인접 phone의 이차조음으로,
`N` 등 동일 단위 반복은 장음 phone으로 합쳐졌을 가능성을 표시한다. 반면
`SUB:JJ>D` 223,132회와 `SUB:NG>N` 109,479회 등은 자동 G2P 선택을 거부하고
다른 규칙·사전 projection을 찾아야 할 실질 차이 후보로 남겼다.

### 3.3 연도 일관성

표상 동등성 후보의 연도별 출현 비율은 2020 60.591%, 2021 60.612%,
2022 60.618%, 2023 60.388%, 2024 60.357%, 2025 59.397%였다. 실질 차이
후보는 각각 38.508%, 38.329%, 38.059%, 38.254%, 38.143%, 39.325%였다.
한 연도에만 치우친 임시 규칙이 아니라 같은 target·model·mapping으로 여섯
연도를 처리해야 한다는 기존 방법론과 일치한다.

## 4. 회귀 예시

- `있는`: `RULE_ONLY:N`; 장음/중복 단위 병합 표상 후보. 승인 아님.
- `있지`: `SUB:JJ>D`; 실질 차이 후보로 자동 G2P 선택 금지.
- `놨던`, `어쨌든`, `없는`: 앞선 exact Gate에 남아 있어 mismatch 진단 대상이
  아니며 이 사실을 회귀검사로 확인했다.

이는 `phones_mfa`가 실제 발음을 새로 판정한 층이 아니라 사전 후보를 기준으로
강제 정렬한 acoustic phone 층이라는 해석과도 일치한다.

## 5. 반복 검토 축약

전체 2,625개 편집 패턴을 사람이 모두 보게 하지 않고, 빈도 상위·각 class 대표·
불완전 표상 후보·회귀 패턴을 합친 56행 결정표를 만들었다. 이 표는 불일치
출현 2,590,212회(92.620%)를 포괄한다.

```text
outputs/reviews/common_pron_r3_g2p_mismatch_diagnostics_20260808/
  README.md
  PATTERN_DECISION_TABLE.csv
```

결정표는 adoption 승인표가 아니다. 최종 canonical 선택 직전에 반복 패턴별
정책을 명시적으로 고정하는 handoff다.

## 6. 독립 감사와 시행착오

첫 감사 실행은 agreement target 파일과 진단 파일의 행 순서가 같다고 가정해
즉시 안전 중단됐다. 산출물 오류가 아니라 감사기의 잘못된 순서 가정이었다.
감사기를 target ID 기반 exact join으로 고친 뒤 다시 실행했다.

수정 후 감사기는 다음을 독립 재계산해 `passed_read_only`로 통과했다.

- 입력·출력 fingerprint와 false scope
- 편집 경로의 index·순서·연산 의미와 Levenshtein 거리
- 길이·활음 표상 근거와 진단 class
- source–target 연결 및 연도별 출현
- 2,625개 패턴 집계와 대표 예시
- 기존 문제 예시 회귀분류

초기 진단본은 삭제하지 않고 다음 위치에 보존했다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  archive_intermediate\05_g2p_mismatch_diagnostics_initial_20260808_1053
```

## 7. 실물과 무결성

최종 진단 root:

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  05_g2p_mismatch_diagnostics
```

| 실물 | SHA-256 |
|---|---|
| `G2P_MISMATCH_DIAGNOSTICS_MANIFEST.json` | `dbeae47ba2a7bf3da0784441195cd55ce15fa0fe6aa9817a4cc866dfd2f499da` |
| 독립 감사 보고서 | `552b09e944dd31c959909b31aa4c55d61d9a337821d7018eeee542c269c4f3ae` |
| 요약 보고서 | `04204bc2ec1f71efdf31bd7ed1545c6e68ff8ba8d787b8a08167f3d6031061d4` |
| 56행 결정표 | `49c416b97f4c7daae29aeaaccd9b0a4eb98fdf98dba25a53011c25e38cd78114` |

## 8. 이 결과가 허용하지 않는 것

- 표상 동등성 자동 승인
- canonical r3 최종 발음 선택
- r3 사전 adoption
- 2020–2025 MFA 실행
- 기존 DB·TextGrid·동반표 변경
- 음성 실현 여부 판정

다음 단계는 56행을 처음부터 모두 청취하는 것이 아니라, 코드로 확정 가능한
model 표상 계약과 사전·규칙 projection 정책을 먼저 작성하고 정말 연구자 판단이
필요한 잔여 패턴만 소형 표본으로 올리는 것이다.
