# 공통발음 r3 전수 selection-readiness 결과

- 날짜: 2026-08-08 KST
- 범위: 2020–2025 관측 표면형 881,237개·27,847,068회
- 상태: planning candidate 전수 연결·독립 감사 완료
- 미수행: canonical 최종 선택, adoption, MFA, TextGrid 변경

## 1. 목적

앞 단계의 G2P projection은 규칙 민감 source 312,410형만 다뤘다. 그러나 최종
공통사전은 881,237개 표면형 전체를 한 계약으로 설명해야 한다. 따라서 canonical
inventory, surface donor, 감사된 target projection, 사전 후보, r2 phone을 한
행씩 연결하고 다음을 분리했다.

- 현재 근거만으로 candidate를 만들 수 있는 형
- 복수 변이 정책 한 줄만 확정하면 되는 형
- silent fallback 없이 추가 후보 생성이 필요한 형

이 행렬은 최종 선택표가 아니라 final selection 직전의 전수 회계표다.

## 2. 적용한 계획 정책

`config/common_pron_r3_selection_readiness_v1.json`에 다음 우선순위를 기록했다.

1. r2 phone이 어절 내부 의무 규칙 목표와 정확히 같은 경우
2. 같은 규칙 목표의 exact surface donor가 있는 경우
3. r2가 plain 목표와 다르지만 우리말샘 계열 사전 후보와 일치하는 예외
4. 전수 감사된 exact 문맥 projection이 의무 규칙 목표를 만족하는 경우
5. 규칙 변화가 없고 r2 차이가 장음·활음 model 단위화뿐인 경우

현행 규칙기는 aspiration, h-deletion, palatalization, liaison, neutralization,
cluster simplification, nasal assimilation, fortition의 어절 내부 의무 규칙만
사용한다. 수의적 ㄴ삽입, 어절 간 동화, 미구현 ㄹ비음화, 실제 실현 판정은 단일
정답 후보로 넣지 않았다.

규칙 후보와 사전 지지 r2가 충돌하는 24형은 둘 중 하나를 임의로 고르지 않고
명시적 복수 변이 planning candidate로 보존했다. 어떤 candidate도 아직 final
selection으로 표시하지 않았다.

## 3. 결과

| 범주 | 유형 수 | 출현 수 |
|---|---:|---:|
| candidate 준비 | 749,779 (85.083%) | 25,978,186 (93.289%) |
| 복수 변이 정책 결정 필요 | 24 | 126 |
| zero-fallback 보류 | 131,434 | 1,868,756 |

candidate 준비 749,779형의 근거별 구성은 다음과 같다.

| 근거 | 유형 수 | 출현 수 |
|---|---:|---:|
| r2 exact 의무 규칙 | 382,891 | 19,765,802 |
| no-rule model 단위화 동등 | 99,660 | 2,176,473 |
| 의무 규칙 projection·사전 비충돌 | 260,508 | 3,394,428 |
| 의무 규칙 projection·사전 일치 | 5,948 | 349,689 |
| surface donor exact | 346 | 245,597 |
| 사전 지지 r2 예외 | 426 | 46,197 |

보류는 다음 두 범주다.

- target projection 미해결: 45,930형·728,649회
- 규칙 변화가 없지만 r2와 plain 목표가 실질적으로 다르고 사전 지지가 없음:
  85,504형·1,140,107회

## 4. 중복 계산을 피하기 위해 확인한 사항

no-rule 실질 불일치 85,504형 중 83,922형은 이미
`korean_mfa_jamo_g2p_v3.2.0_1best_strict`에서 온 결과다. 같은 모델과 같은 입력을
다시 G2P해도 새 근거가 생기지 않는다. base dictionary 보존 출처는 1,582형뿐이다.

또한 85,504형의 목표 한글 중 기존 310,605 target과 겹치는 것은 241형이었다.
그중 기존 audited projection을 즉시 재사용할 수 있는 것은 132형뿐이고, 109형은
기존에도 donor 부재 또는 candidate-only 문제로 보류됐다. 나머지 85,263형은 새
target이다.

따라서 다음 작업은 85,504형 전체에 같은 Jamo G2P를 반복하는 것이 아니다.
현행 06 projection이 donor로 사용한 96,284 target exact pool을, canonical 전체의
382,891 exact-rule 형으로 확장해 동일 문맥 projection을 다시 계산하는 것이
방법론적으로 우선이다. 이 과정에서 기존 06 후보가 더 넓은 donor pool에서도
유지되는지 함께 비교해야 한다.

## 5. 회귀 예시

- `놨던`, `없는`, `있는`: 사전 미등재만으로 버리지 않고, 어절 내부 의무 규칙과
  감사된 phone 후보가 일치하므로 planning candidate로 연결됐다.
- `어쨌든`: 의무 규칙·projection·사전 근거가 함께 일치하는 candidate다.
- `있지`: exact donor 지지가 없어 zero-fallback 보류를 유지했다.

이는 MFA 입력 후보를 실제 음성 실현 판정과 분리한다. planning candidate가
준비됐다는 것은 강제정렬 사전 후보를 구성할 기술·규칙 근거가 있다는 뜻이지,
해당 발화에서 그 발음이 실현됐다고 판정했다는 뜻이 아니다.

## 6. 시행착오와 국소 복구

첫 실행은 projection source가 기존 열을 `original_selection_status`로 이름 붙인
것을 조인기가 `selection_status`로 참조해 첫 행에서 안전 중단됐다. 1KB partial은
삭제하지 않고 다음 위치에 보존했다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\archive_intermediate\
  07_selection_readiness_failed_schema_link_20260808_1207
```

열 매핑을 고친 전수 실행은 881,237행 gzip을 완전히 썼지만, 출력 stream을 닫은
뒤 iterator를 한 번 더 읽는 종료검사 버그 때문에 manifest 작성 직전에
중단됐다. 이미 계산된 44.5MB 결과를 버리고 8분 계산을 반복하지 않았다.
복구 경로가 다음을 전수 검증한 뒤 같은 partial에 manifest를 쓰고 원자 승격했다.

- gzip EOF와 881,237행 coverage
- donor 원행 byte field 동등성
- projection source 312,410형 exact link
- JSON variant 수, hold flag, phone inventory, 의무 규칙 집합
- 상태·연도 출현 집계

manifest에는 `recovery.performed=true`,
`full_recomputation_avoided=true`를 기록했다. 종료검사는 닫힌 iterator를 다시
읽지 않도록 수정했다.

## 7. 독립 감사와 실물

복구 검증과 별도로 감사기는 model 단위화 관계, 사전 지지 r2 변이, 각 planning
route, candidate phone inventory, source/target 연결과 회귀 예시를 처음부터 다시
계산했다. 결과는 `passed_read_only`다.

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  07_canonical_selection_readiness

outputs/reports/AUDIT_common_pron_r3_selection_readiness_20260808.json
outputs/reports/REPORT_common_pron_r3_selection_readiness_20260808.json
```

| 실물 | SHA-256 |
|---|---|
| readiness manifest | `d11bd4e74b3c3cefba22745788f0e74aa5406efa0e96f6bbfd1bc82e76b54e8a` |
| 독립 감사 | `1a9f296db6db15a044f9394b478db9716dced0a7e3964539299f09ec0033f577` |
| 요약 보고서 | `57cbbed10a2f885caed54851a83e5f023c3ddcb9e3674cf8e42e78eec8ab8306` |

## 8. 다음 단계

canonical 전역 exact-rule donor 382,891형을 사용하는 projection v2를 후보
단계로 만든다. 기존 06의 264,906 target 후보가 더 넓은 donor에서도 유지되는지,
현재 보류 131,434형 중 얼마나 새로 해소되는지를 비교한다. 결과가 독립 감사를
통과한 뒤에만 final selection·zero-fallback·adoption Gate로 간다.

현재 사용자 청취 검토나 PowerShell 장시간 MFA는 필요하지 않다.
