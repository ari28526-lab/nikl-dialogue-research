# 공통발음 r3 readiness v2 잔여 hold 우선순위

- 날짜: 2026-08-08 KST
- 범위: zero-fallback hold 91,553형·894,388회
- 상태: 감사된 입력의 읽기 전용 반복 패턴 요약 완료
- 미수행: 후보 생성, canonical selection, adoption, G2P 재실행, MFA, TextGrid 변경

## 1. 잔여 hold 두 계층

| 계층 | 유형 | 출현 | 성격 |
|---|---:|---:|---|
| target projection 미해결 | 43,428 | 509,205 | 의무 규칙형은 있으나 exact-context phone donor가 합의되지 않거나 탈락 포함 |
| no-rule 실질 불일치 잔여 | 48,125 | 385,183 | 수의 위치동화·기본사전 안전 집합을 뺀 뒤의 G2P/단위화/매핑 문제 |
| 합계 | 91,553 | 894,388 | — |

두 계층은 원인이 다르므로 한 fallback 정책으로 합치지 않는다.

## 2. target projection 잔여

43,428형 중 42,839형·506,404회는 `hold_no_unanimous_exact_context_donor`다.
나머지 589형·2,801회는 candidate-only deletion이 포함돼 별도 정책이 필요하다.

합의되지 않은 donor의 주요 의무 규칙 조합은 다음과 같다.

| 규칙 조합 | 유형 | 출현 | 고빈도 예 |
|---|---:|---:|---|
| fortis | 9,341 | 152,315 | 먹고, 학교, 고등학교 |
| liaison | 15,111 | 125,794 | 최근에, 친구들이, 친구들이랑 |
| neutralize + fortis | 3,279 | 64,380 | 있다고, 있다, 있다는 |
| aspiration | 2,585 | 55,079 | 않고, 많고, 않게 |
| h-deletion + liaison | 587 | 18,332 | 괜찮은, 괜찮을, 괜찮아 |
| cluster + fortis | 171 | 18,003 | 없고, 읽고, 없고요 |

이 집합은 규칙을 새로 발견하지 못해서 생긴 것이 아니라, 같은 규칙 목표에 대한
frozen phone donor가 하나로 합의되지 않았기 때문에 보류된 것이다. 다음 단계는
첫 donor를 고르는 것이 아니라 frozen 기본사전을 추가 문맥 donor로 넣고, 변이
집합의 합의·충돌·출처를 함께 보존하는 감사다.

## 3. no-rule 잔여

48,125형 중 48,043형·368,912회는 Jamo G2P 1-best 출처다. frozen 기본사전
출처 82형·16,271회는 일부 변이만 수의적 위치동화인 경우라 전 변이를 채택하지
않았다.

상위 반복 signature는 다음과 같다.

| signature | 유형 | 출현 | 해석 우선순위 |
|---|---:|---:|---|
| `RULE_ONLY:P;SUB:B>Y` | 2,911 | 41,301 | `pʲ`의 격음+활음 단위화와 현재 B 표시의 비일대일성 |
| `SUB:D>T` | 3,992 | 36,579 | `tʲ` 등 phone의 D/T 비일대일성 |
| `SUB:B>P` | 4,449 | 33,734 | `pʲ`의 B/P 비일대일성 |
| `RULE_ONLY:Y;SUB:N>NG` | 2,339 | 16,005 | 활음 단위화와 비음 위치 차이의 결합 |
| `RULE_ONLY:EU_G` | 814 | 14,709 | `저희·너희`류 ㅢ 발음 규칙/단위화 별도 감사 |
| `RULE_ONLY:CH;SUB:J>W` | 1,540 | 14,684 | `취·최`류 이차조음·활음 단위화 |
| `RULE_ONLY:Y` | 407 | 14,669 | `걔`류 활음 단위화 |
| `RULE_ONLY:NG` | 337 | 13,271 | `중에서`류 분절 누락 가능성; fail-closed 유지 |
| `RULE_ONLY:L;SUB:N>Y` | 1,340 | 11,851 | `종류·대통령`류 ㄹ/활음·규칙 결합 |

상위 세 signature만 11,352형·111,614회다. 그러나 이를 단순 `B→P`, `D→T`
전역 치환으로 해결하면 안 된다. frozen 기본사전에서 `pʲ`가 B와 P 양쪽에,
`tʲ`가 D와 T 양쪽에 쓰이기 때문이다. raw phone의 이차조음과 목표 규칙 문맥을
함께 보는 다대다 compatibility가 필요하다.

`RULE_ONLY:EU_G`는 model 표상 문제와 한국어 ㅢ 발음 규칙을 분리해 점검한다.
`RULE_ONLY:NG`처럼 phone 한 분절이 사라진 집합은 기술적 동등성으로 복구하지
않고 계속 hold한다.

## 4. 다음 구현 순서

1. frozen 기본사전의 **단어·음절·이차조음 문맥을 보존한 donor inventory**를
   만든다. phone 하나를 음소 하나에 전역 매핑하지 않는다.
2. target projection 42,839형에는 기존 canonical donor와 frozen 기본사전 donor를
   합쳐 unanimous·multiple-supported·conflict·no-donor를 다시 구분한다.
3. no-rule 잔여에는 `pʲ/tʲ/kʷ/tʷ` 같은 phone이 목표 onset+glide 단위를 함께
   나타내는지 문맥별로 검증한다. 충분한 frozen donor가 있는 관계만
   candidate-only로 제안한다.
4. ㅢ 관련 규칙은 표준발음 근거와 형태소·음절 위치를 별도 감사한 뒤 규칙 엔진
   보강 여부를 결정한다.
5. 분절 탈락·삽입과 donor 충돌은 자동 fallback하지 않는다.

이 작업도 후보 감사 단계다. canonical selection·adoption·MFA·TextGrid보다
앞에 위치한다.

## 5. 산출물

```text
outputs/reports/REPORT_common_pron_r3_readiness_v2_residual_priorities_20260808.json
```

SHA-256:
`98a9fe63f13d9f1422e5bef4a796c9697befeade0f6f51ef57b290ddb65394e5`

보고서는 readiness v2와 stage 11의 fingerprint를 검증하고, zero-fallback
91,553형·894,388회를 모두 두 계층에 포함해 회계를 검증했다. 저장소 보고서는
대용량 중간표를 중복하지 않도록 각 계층의 상위 50패턴·패턴당 상위 10예만 담고,
전수 원행은 D:의 감사된 readiness·coverage에 둔다. mutation flag는 모두
`false`다.
