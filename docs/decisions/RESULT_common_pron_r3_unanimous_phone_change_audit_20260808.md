# 공통발음 r3 단일 문맥 근거·phone 변경 필요형 감사 결과

최종 갱신: 2026-08-08 KST

## 결론

readiness v3에서 문맥 donor가 단일하게 합의됐지만 기존 r2 phone을 그대로
유지할 수 없어 보류한 4,453형·72,030회를 전수 분류했다. 이 집합에는 단순한
표기 차이뿐 아니라 phone 삽입 2,826 issue, 직접 치환 2,047 issue, 이차조음
결합 치환 27 issue가 섞여 있었다. 단일 donor는 phone 편집의 자동 승인 근거가
아니므로 후보 생성은 0형이며, 4,453형 모두 zero-fallback hold를 유지한다.

이 단계는 사전·규칙·음향모델의 관계를 다음 감사 단위로 나눈 읽기 전용
inventory다. 표준발음·실제 실현 판정, canonical 선택, adoption, MFA,
TextGrid 변경은 수행하지 않았다.

## 전수 분류

| 다음 감사 경로 | 형 | 출현 회수 |
|---|---:|---:|
| ㅢ `EU_G` 성분 삽입 | 964 | 15,134 |
| 복합모음 `Y/W` 활음 삽입 | 589 | 15,627 |
| 연구용 `ng` 분절 삽입 | 536 | 15,868 |
| 종성·공명음 분절 삽입 | 212 | 7,397 |
| 그 밖의 분절 삽입 | 250 | 2,919 |
| 초성 후두 대립·조음 방법 치환 | 919 | 9,453 |
| 비음·종성 치환 | 455 | 1,626 |
| 모음 질·길이 치환 | 144 | 2,938 |
| 이차조음 결합 치환 | 16 | 29 |
| 그 밖의 단일 치환 | 35 | 134 |
| 둘 이상의 편집이 섞인 형 | 333 | 905 |

합계는 4,453형·72,030회다. 출현 빈도는 다음 감사의 우선순위일 뿐 발음의
진실값이나 채택 기준으로 사용하지 않는다.

## 방법론적 해석

- `저희·너희`류의 `EU_G`는 규칙 참조열과 acoustic phone 단위화가 서로 다른
  것인지 먼저 감사한다. ㅢ의 표준발음 규칙을 빈도만으로 결정하지 않는다.
- `걔`류 `Y/W`와 `중에서`류 `ng`는 현재 phone열에 없는 분절을 새로 넣어야
  한다. donor가 하나여도 기존 r2 후보를 바이트 동일하게 유지할 수 없으므로
  자동 승격하지 않는다.
- 후두 대립, 종성, 비음, 모음 길이·질 치환은 우리말샘 발음·규칙 참조·동결
  MFA 사전·acoustic model phone 관계를 함께 보아야 한다. MFA phone을 곧바로
  실제 발음 전사나 표준발음으로 해석하지 않는다.
- 여러 편집이 섞인 333형은 전역 phone 치환으로 처리하지 않고 token 수준
  분석을 거친다.

## 산출물

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  15_unanimous_phone_change_audit\
    UNANIMOUS_PHONE_CHANGE_AUDIT_MANIFEST.json
    unanimous_phone_change_token_inventory.csv.gz
    unanimous_phone_change_issue_inventory.csv.gz
    unanimous_phone_change_route_summary.csv

outputs/reports/AUDIT_common_pron_r3_unanimous_phone_change_20260808.json
```

| 산출물 | SHA-256 |
|---|---|
| Stage 15 manifest | `c23267a1ca0dcdc881fab1b8c59ad05266819ce6f6d3f2b84f094a71066788f5` |
| token inventory | `3bf8b8ccd718894ae298bc9328ed46d90ab8387a2146c723ef353f2f8d9e60d4` |
| issue inventory | `5f3c59d0cecfc2dbc2a94b681c574da34e8f48c67647cadfd41759b91acf82a5` |
| route summary | `6ba652d84f85d2af0a74898fcd5e1863836ae0107f59687cde15f575c0d8dec5` |
| 독립 감사 | `398a4db7177013065caac625e90c69a02e6da38adfb22f636c9662c887a8f84b` |

독립 감사기는 readiness v3에서 목표 4,453형을 다시 추출하고, Stage 13의
미지지 issue 4,900행과 Stage 15 issue·token·요약표를 전수 대조했다. donor
집합의 단일성, 분류 회계, 모든 비채택·비변경 flag를 재계산해
`passed_read_only`로 통과했다.
