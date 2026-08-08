# 공통발음 r3 문맥 보존 frozen 사전 donor 감사 결과

- 날짜: 2026-08-08 KST
- 범위: readiness v2 zero-fallback hold 91,553형·894,388회
- 상태: 단어·음절·국소 분절·이차조음 문맥 inventory와 기존 canonical donor 대조 완료
- 미수행: 후보 발음 생성, canonical selection, adoption, MFA, TextGrid 변경, 실제 실현 판정

## 1. 왜 이 단계가 필요했는가

동결 Korean MFA 사전에서 `pʲ`는 `비`의 B와 `피`의 P 양쪽에 나타나며,
`tʲ`도 D/T 양쪽에 나타난다. 따라서 phone 하나를 음소 하나로 전역 치환하면
후두 대립과 활음 정보를 잘못 복원한다. 이 단계는 phone 자체가 아니라 다음을
함께 보존했다.

- 사전 표제어와 전체 규칙 예상형
- 해당 phone이 놓인 음절 전체와 음절 내 위치
- 앞뒤 규칙 단위와 단어·음절 처음/끝 여부
- `pʲ·tʲ·kʷ·tʷ` 등이 한 phone으로 나타내는 onset+glide 결합
- 기존 canonical exact donor와 frozen 기본사전 donor의 출처별 후보 집합

frozen 사전은 acoustic model과 맞춘 **정렬 근거**일 뿐 표준발음이나 실제
실현의 정답으로 사용하지 않았다.

## 2. frozen 사전 inventory

| 항목 | 수 |
|---|---:|
| 규칙 예상형을 만들 수 있는 표제어 | 17,946 |
| 발음 변이 행 | 20,978 |
| 문맥 mapping이 완전한 변이 | 18,109 |
| 탈락·삽입 등 미지원 mapping이 남은 변이 | 2,869 |
| direct unit mapping | 111,801 |
| 이차조음 onset+glide mapping | 4,601 |

미지원 mapping이 있는 발음 변이는 inventory에는 보존했지만 donor index에는
사용하지 않았다. 동일 단어 근거는 최소 1개 표제어, 단어 밖 일반화는 최소 2개
서로 다른 표제어가 있어야 했다. 출현 빈도로 다수결하지 않았다.

## 3. 91,553형 전수 분류

| 문맥 근거 분류 | 유형 | 출현 | 해석 |
|---|---:|---:|---|
| 단일 문맥 근거 | 10,594 | 162,574 | 모든 미해결 issue의 eligible phone 합집합이 하나 |
| 복수 지지 변이 | 22,171 | 225,511 | 문맥 근거가 둘 이상이며 임의 선택 금지 |
| canonical–frozen 충돌 | 48,780 | 377,518 | 두 출처의 문맥 phone 집합이 서로 겹치지 않음 |
| eligible donor 없음 | 10,008 | 128,785 | 근거 부족 또는 candidate-only 분절 |
| 합계 | 91,553 | 894,388 | — |

이 결과는 전역 `phone→음소` 매핑을 하지 않은 것이 필요했음을 보여준다. 특히
충돌 48,780형을 “가장 흔한 phone”으로 채우면 연구용 규칙 예상형과 정렬용
모델 변이를 혼동한다.

## 4. 대표 사례

- `최근에`: 규칙 `CH W`와 기존 phone `tɕʷ` 관계가 frozen 사전의 같은 음절
  문맥 9개 표제어에서 단일하게 지지됐다.
- `편하게`: 규칙 `P Y`와 기존 phone `pʲ` 관계가 같은 음절 문맥 8개
  표제어에서 단일하게 지지됐다.
- `친구들이`: 규칙 `n` 문맥에 기존 canonical donor는 `n/ɲ`, frozen donor는
  `ŋ`을 제시해 출처 충돌로 남겼다. 수의적 위치동화를 의무 규칙으로 바꾸지 않았다.
- `중에서`: 빠진 `ng` 자리에 canonical donor `ŋ`이 단일하게 나타났지만,
  기존 phone열에 새 분절을 넣어야 하므로 이 감사만으로 후보로 승격하지 않았다.
- `학교`: 종성 `k` 문맥이 복수이고 `KK+Y`에 대한 `cʰː` 문맥 donor도 없어
  계속 보류했다.

## 5. 산출물과 독립 감사

```text
D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  13_contextual_dictionary_donor_audit\
    frozen_dictionary_contextual_donor_inventory.csv.gz
    residual_hold_contextual_donor_evidence.csv.gz
    residual_hold_contextual_donor_classification.csv.gz
    CONTEXTUAL_DICTIONARY_DONOR_AUDIT_MANIFEST.json

outputs/reports/AUDIT_common_pron_r3_contextual_dictionary_donor_20260808.json
```

| 산출물 | SHA-256 |
|---|---|
| Stage 13 manifest | `32cfa44a1f06b99ce9c166c19aa12fa0510ce992f7e07ad232b0f21aaf3d2f31` |
| 독립 감사 | `4c9ecdd586dd75a5d63ed9a2d2492ebec936e18d0b89f40271642b20c2bdfb2d` |

독립 감사기는 frozen 사전 변이 identity, 91,553형 전수 coverage, 172,565개
issue의 출처별 phone 집합과 네 분류, 모든 비채택·비실현 flag를 다시 계산해
`passed_read_only`로 통과했다.
