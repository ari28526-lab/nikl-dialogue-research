# 공통발음 r3 Stage 16 형태소·문맥 근거 연결 결과

## 목적

Stage 15에서 phone 삽입·치환이 필요해 계속 보류한 4,453형·72,030회를
2020–2025 동결 검색 master와 연결했다. 목적은 발음을 자동 결정하는 것이 아니라,
같은 표면 어절이 어떤 자동 형태소 분석 문맥에서 실제로 나타났는지 확인하고 이후
우리말샘·표준발음 규칙·MFA model phone 근거 감사를 더 좁게 만드는 것이다.

이 단계의 Bareun 분석은 연구자의 정답 형태소 분석이 아니다. 또한 출현 빈도나
품사 signature는 표준발음 또는 실제 음성 실현의 증거로 사용하지 않는다.

## 입력과 연결 원칙

- Stage 15의 보류형 4,453개와 출현 기대치 72,030회를 고정했다.
- `D:\10_LAYERS\05_search_master`의 17,156개 세션 CSV, 5,103,356개 발화를
  전수 순회했다.
- `form`의 공백 분리 표면 어절과 목표형이 정확히 같을 때만 표면 출현으로
  연결했다.
- Bareun `tagged` group 수가 `form` 어절 수 및 `n_eojeol`과 모두 같을 때만
  같은 위치의 형태소·품사 signature를 연결했다.
- `그래가지고` 대 `그렇/VA+어/EC 가지/VX+고/EC`처럼 Bareun group 수가 표면
  어절 수와 다른 행은 표면 출현은 보존하되 형태소 위치를 억지로 맞추지 않았다.
- 후보 생성, canonical 선택, adoption, MFA, TextGrid 수정은 모두 금지했다.

## 결과

| 항목 | 결과 |
|---|---:|
| 목표 표면형 | 4,453 |
| 기대 출현 | 72,030 |
| 표면 어절 exact 연결 | 68,285 |
| 형태소·품사 안전 연결 | 60,292 |
| 표면 출현 전부 연결된 형 | 3,661 |
| 표면 출현 일부 연결된 형 | 306 |
| 표면 출현 미연결 형 | 486 |
| 형태소 출현 전부 연결된 형 | 2,502 |
| 형태소 출현 일부 연결된 형 | 839 |
| 형태소 미연결 형 | 1,112 |
| 단일 형태소 signature 형 | 3,025 |
| 복수 형태소 signature 형 | 316 |
| 형태소 signature 행 | 3,792 |
| 우리말샘 계열 사전 참조가 있는 형 | 179 |
| 표면 발음 규칙 참조가 있는 형 | 742 |
| 자동 후보 | 0 |
| 보존한 zero-fallback hold | 4,453 |

표면 연결 수가 기대 출현보다 적다고 해서 원자료가 유실됐다고 판단하지 않는다.
기대치는 공통 어휘 inventory의 연도별 집계이고, Stage 16은 현재 동결된 검색
master에서 exact 표면 어절만 센 값이다. 차이는 후속 provenance 감사 대상으로
남겼다. 형태소 연결 수가 더 작은 것은 위의 1:1 안전 조건을 적용한 의도된 결과다.

## 산출물

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  16_morph_context_evidence\
    MORPH_CONTEXT_EVIDENCE_MANIFEST.json
    unanimous_phone_change_evidence_coverage.csv.gz
    unanimous_phone_change_morph_signatures.csv.gz
    unanimous_phone_change_evidence_route_summary.csv

outputs/reports/AUDIT_common_pron_r3_morph_context_evidence_20260808.json
```

| 파일 | SHA-256 |
|---|---|
| Stage 16 manifest | `7539be36cc69b02bff0028501db3400206aa284fb34cfeb0f09566c0231ce6f0` |
| 독립 감사 보고서 | `3235c24a73b65d1ec69e7948b6f8b0815f3b6a7e9e87d1ec038048486a82640e` |

독립 감사기는 5,103,356개 검색 master 행을 다시 순회해 표면 위치와 안전한
형태소 위치를 별도로 재계산하고, token coverage·signature·route summary·모든
비채택 flag를 대조해 통과했다.

## 시행착오와 안전 중단

- 첫 호출은 장시간 실행에 비해 관찰 timeout을 너무 짧게 설정해 산출물 없이
  종료됐다. 데이터나 기존 단계는 바뀌지 않았다.
- 두 번째 호출은 Bareun group 수와 표면 어절 수가 항상 같다는 잘못된 가정을
  `그래가지고` 사례에서 잡고 출력 전에 안전 중단됐다.
- 이후 표면 연결과 형태소 연결을 분리하고 1:1이 아닌 행은 형태소 미연결로
  보존하도록 수정한 뒤 전수 생성과 독립 감사를 통과했다.

## 다음 허용 범위

사전·규칙 Roman이 정확히 일치하는 소수형도 기존 r2 phone의 문제 분절만
기계적으로 바꿔 바로 채택하지 않는다. 주변 변이음이 남아 부자연스러운 phone열이
될 수 있기 때문이다. 다음 단계는 해당 좁은 집합에 대해 전체 rule unit sequence를
acoustic-model 호환 문맥 donor로 완전 재구성할 수 있는지 읽기 전용으로 감사하는
것이다. 완전하고 단일하며 독립적으로 재검증된 경우에만 candidate-only 계획표를
만들 수 있고, canonical 선택·adoption·MFA·TextGrid는 여전히 별도 Gate 뒤다.
