# 공통발음 r3 model 표상·문맥 projection 후보 결과

- 날짜: 2026-08-08 KST
- 범위: 2020–2025 공통 규칙 목표형 310,605개와 source 312,410형
- 상태: 후보 생성 및 읽기 전용 독립 감사 완료
- 금지 상태: canonical 선택·adoption·연도별 MFA·TextGrid 변경 모두 미수행

## 1. 왜 이 단계를 수행했는가

앞선 agreement Gate의 mismatch 214,321개를 모두 G2P 오류로 간주할 수 없었다.
동결 acoustic model의 한 phone이 장음이나 활음의 성질을 함께 담는 기술적
단위화 차이가 있는 반면, `있지`의 `SUB:JJ>D`처럼 실제 규칙 목표 단위와 다른
후보도 섞여 있었기 때문이다. 따라서 다음 두 작업을 분리했다.

1. 발음 동등성이나 실제 실현을 주장하지 않는 좁은 **model 단위화 관계**
2. 실질 차이에 대해 exact-agreement 자료에서만 phone을 가져오는 **동일 문맥
   projection 후보**

이 단계의 출력은 최종 공통발음열이 아니다. 최종 선택 전에 사용할 근거층이다.

## 2. 고정한 계약

계약 파일은 `config/common_pron_r3_model_projection_v1.json`이다.

### 2.1 model 단위화 관계

다음만 기술적으로 같은 ordered broad-Roman 목표를 표현할 수 있다고 인정했다.

- comparison key가 처음부터 정확히 같은 경우
- 인접한 동일 규칙 단위 하나가 장음 표지를 가진 phone에 흡수된 경우
- `Y`가 인접한 명시적·고유 구개 phone에 흡수된 경우
- `W`가 인접한 명시적 원순화 phone에 흡수된 경우

substitution, candidate-only, 그 밖의 rule-only 차이는 이 관계로 승인하지
않았다. 이는 언어학적 발음 동등성이나 음성 실현 판정이 아니다.

### 2.2 exact 문맥 donor

실질 차이의 phone 후보는 다음 조건을 모두 만족할 때만 만들었다.

- donor는 `comparison_status=exact_rule_roman`이고 model-input rewrite가 없는
  target만 사용
- 출현 빈도로 다수결하지 않고 서로 다른 target type이 최소 2개 존재
- 같은 문맥의 관측 phone이 하나로 완전히 일치
- 문맥은 `±2단위+음절/어절 경계 → ±1단위+경계 → 해당 단위+경계` 순으로 탐색
- mode, 첫 변이, 수기 phone, 기본사전 membership fallback 금지
- 완성된 전체 phone 열이 model 단위화 관계를 다시 만족해야 후보로 기록

우리말샘 사전 일치는 source 근거 경로를 나누는 데만 사용했으며 최종 phone
선택으로 해석하지 않았다.

## 3. 전수 결과

### 3.1 target 310,605개

| 상태 | target 수 | 출현 수 | 의미 |
|---|---:|---:|---|
| exact 후보 유지 | 96,284 | 1,676,283 | 원 후보 유지 가능, 최종 선택 아님 |
| model 단위화 후보 유지 | 124,564 | 1,686,625 | 장음·활음 기술 관계, 최종 선택 아님 |
| exact 문맥 projection 후보 | 44,058 | 381,335 | 전수 donor 조건을 통과한 새 후보 |
| 동일 문맥 donor 없음 | 45,111 | 725,848 | 자동 선택 보류 |
| candidate-only 삭제 정책 필요 | 588 | 2,801 | 자동 삭제 금지·보류 |

후보가 한 개 이상 만들어진 범위는 target 264,906개(85.287%), 출현
3,744,243회(83.710%)다. 자동으로 해소하지 않은 범위는 target 45,699개
(14.713%), 출현 728,649회(16.290%)다.

### 3.2 source 312,410형

- projection과 독립 사전 근거가 함께 일치한 후속 후보: 5,948형·349,689회
- 사전 충돌: 24형·126회 보류
- 독립 사전 근거 없음: 260,508형·3,394,428회 보류
- target projection 미해결: 45,930형·728,649회 보류

따라서 target phone 후보를 만들 수 있다는 사실과 canonical source를 최종
선택할 수 있다는 사실을 분리했다.

## 4. 회귀 예시

- `놨던`, `어쨌든`, `없는`: exact 후보를 유지했다.
- `있는`: `i nː ɨ n`이 규칙 Roman의 중복 `N`을 장음 phone 하나가 담는
  기술적 단위화 후보로 유지됐다. 실제 발음 승인이나 최종 선택은 아니다.
- `있지`: 전수 exact donor가 현 정책의 최소 지지를 충족하지 않아 자동
  projection하지 않고 보류했다. 합성 단위시험의 임의 donor와 전수 자료의 실제
  지지를 구분함으로써 시험 예시를 곧바로 생산 선택으로 오인하지 않았다.

## 5. 독립 감사

감사기는 생성기 집계를 재사용하지 않고 다음을 다시 계산했다.

- 입력·출력·동결 acoustic model fingerprint와 false scope
- 310,605 target 및 312,410 source의 원 입력 열 불변성
- 9,347/810/44개 query context와 exact donor 96,284 target·1,000,388 unit
- 사용한 798개 evidence의 문맥, 최소 target type 수, unanimity, 예시와 ID
- 모든 projection phone의 acoustic inventory membership와 전체열 관계
- 보류 사유, source 사전 경로, 연도별 출현 집계
- `있는·있지·놨던·어쨌든·없는` 회귀 결과

결과는 `passed_read_only`다. 대량 결과는 D:에 원자적으로 확정했고, 요약·감사
보고서만 저장소에 둔다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  06_model_projection_candidates

outputs/reports/AUDIT_common_pron_r3_projection_candidates_20260808.json
outputs/reports/REPORT_common_pron_r3_projection_residuals_20260808.json
outputs/reports/common_pron_r3_target_residual_patterns_20260808.csv
outputs/reports/common_pron_r3_source_route_patterns_20260808.csv
outputs/reviews/common_pron_r3_projection_residual_handoff_20260808.csv
```

무결성 핵심값:

| 실물 | SHA-256 |
|---|---|
| projection manifest | `992bc1f8af30a4b6d1c4aec7cc1ee6eace1854b59f263e09605eed12c17a7dc9` |
| 독립 감사 보고서 | `dafad41614827bb13bd57f4e09e72fb7c02d2c6abe639765907723d6883de3b5` |
| 잔여 요약 보고서 | `76cfde01e9b50ad7a00debc959f7432b534c90ea0a641060ab4ff9c3187d8e97` |
| 56행 잔여 handoff | `273ee16e53057b7c24aff29d4df3cbfc158e7b3b2b1d425acd8c7a4b147865e1` |

## 6. 다음 단계

잔여 pattern 1,799개를 전부 사람에게 넘기지 않았다. 출현의 95.136%와 각
범주 대표를 포괄하는 56행 handoff로 축약했다. 이 표 역시 승인표가 아니다.

다음 단계는 다음 순서다.

1. 기존 canonical inventory·donor·G2P·projection 근거의 우선순위를 명시한
   최종 선택 계약 작성
2. 선택 phone 누락 0, `spn` 0, inventory 밖 phone 0을 만족하는 canonical 표와
   MFA 사전 projection 생성
3. 기존 문제 발화와 음운현상별 표적 회귀 및 단일 adoption Gate
4. adoption 뒤에만 2020–2022 영향 세션 delta와 2023–2025 최초 MFA 시작

새 광범위 청취 검토, r2 재실행, 기존 TextGrid phone 문자열의 제자리 변경은
허용하지 않는다.
