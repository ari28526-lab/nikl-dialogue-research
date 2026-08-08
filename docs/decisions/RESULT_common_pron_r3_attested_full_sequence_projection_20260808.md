# 공통발음 r3 Stage 17 사전 등재 발음 전체 phone열 projection 결과

## 결론

Stage 15 보류 4,453형 중 사전 Roman과 규칙 Roman이 같은 141형을 다시 감사했다.
그중 76형은 우리말샘 등재 발음이 아니라 과거 기계 생성 `pron_g2p`만 가진
경우이므로 사전 근거에서 제외했다. 실제 어휘목록 v2의 `pron_1` 또는 `pron_2`가
규칙과 일치하는 65형만 전체 model-phone sequence projection 대상으로 삼았다.

65형 중 모든 rule unit이 canonical exact donor와 동결 MFA 사전 문맥에서 하나의
상호 호환 phone으로 완전히 재구성된 것은 14형·200회다. 이 14형은 정렬용
candidate-only 계획이며 최종 canonical 선택, 표준발음 주장, 실제 실현 판정이
아니다. 나머지 51형·2,851회는 하나 이상의 unit에서 복수 phone 또는 출처 충돌이
있어 계속 hold한다.

## 왜 기존 phone 일부만 고치지 않았는가

사전·규칙 Roman이 같아도 기존 r2 phone에서 문제 분절만 삽입·치환하면 주변
변이음이 잘못 남을 수 있다. 예를 들어 glide가 빠진 형에서 glide 하나만 넣는
방식은 기존 onset의 이차조음이 같은 문맥에 적합한지 보장하지 않는다. 따라서
Stage 17은 기존 phone을 부분 편집하지 않고 모든 rule unit을 처음부터 문맥 donor로
재구성했다.

## 결과

| 범주 | 형 | 출현 | 처리 |
|---|---:|---:|---|
| `pron_1/2` exact + 전체 sequence 단일 | 14 | 200 | candidate-only 계획 |
| `pron_1/2` exact + 전체 sequence 불완전/충돌 | 51 | 2,851 | hold |
| legacy 기계 `pron_g2p`만 exact | 76 | 923 | 사전 등재 근거에서 제외·hold |
| 합계 | 141 | 3,974 | 최종 선택 없음 |

14형은 `깔짝깔짝`, `깜짝깜짝`, `꼬르륵꼬르륵`, `떡꼬치`, `맏딸`, `뽕뽕`,
`식칼`, `쏴`, `입추`, `입춘`, `입출금`, `제택`, `징표`, `합판`이다.

51형의 보류는 연구자가 음성을 들어 발음을 판정할 문제가 아니다. 같은 rule unit에
복수 acoustic-model phone이 지지되는 model allophone 선택 문제이므로, 빈도
다수결이나 임의 phone 선택을 하지 않고 후속 기술 감사로 남긴다.

## 산출물과 감사

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  17_attested_full_sequence_projection\
    ATTESTED_FULL_SEQUENCE_PROJECTION_MANIFEST.json
    attested_full_sequence_projection_inventory.csv.gz
    attested_full_sequence_projection_summary.csv

outputs/reports/AUDIT_common_pron_r3_attested_full_sequence_projection_20260808.json
```

| 파일 | SHA-256 |
|---|---|
| Stage 17 manifest | `7ffb5ccfd59c2f48902cf924d2578d11058da1b1036bb7fa46b9a23b6d914ad7` |
| 독립 감사 | `5bf92072f5f596112b9dd7fe2dc434e95f06d8ac3ee1d27c1ddd852ccc485e2c` |

독립 감사기는 141형의 사전 출처를 다시 구분하고, 65형의 모든 rule unit에 대해
canonical/frozen 문맥 index를 다시 구성해 14형·200회를 동일하게 재현했다.

## 시행착오

- 첫 실행은 도구 관찰 시간이 짧아 manifest 작성 전 종료됐다.
- 다음 실행은 결과 CSV를 만든 뒤 `runtime_snapshot`에 프로젝트 root 인수가 빠진
  오류를 잡고 final 승격 전에 안전 중단됐다.
- 함수 인수를 명시하고 회귀 테스트를 추가한 뒤 재실행·독립 감사를 통과했다.
- 두 실패 partial은 성공본과 혼동되지 않도록 같은 release의
  `archive_intermediate`로 보존 이동했다.

MFA, TextGrid, 기존 r2, 2020–2022 완성본은 이 단계에서 변경하지 않았다.
