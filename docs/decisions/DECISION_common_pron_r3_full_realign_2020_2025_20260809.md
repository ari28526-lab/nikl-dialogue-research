# 공통발음 r3 2020–2025 안전 본체 전수 재정렬 결정

날짜: 2026-08-09 KST
승인자: ari30
상태: 정책 승인, 외부 workflow 검토·runner 구현 전 생산 차단

## 결정

2020–2025의 pronunciation-safe body 4,384,992발화를 하나의 동결 r3 발음
계약의 전수 대상 pool로 삼는다. 이 중 독립 음원·CSV·정렬 가능성 계약을 통과한
발화는 모두 새 r3 DB에서 정렬하고, 기술적으로 정렬 불가능한 exact ID는 이유와
함께 별도 보존한다. 2020–2022의 r2 정렬 interval과 TextGrid는 비교·감사 근거로만 보존하고
최종 r3 산출물에 재사용하지 않는다. 718,364개 follow-up 발화는 삭제하거나 일부
어절을 제거하지 않고 별도 exact-ID shard로 보존한다.

연구자의 원 승인 문장은 다음과 같다.

> 4개 표적 회귀 TextGrid의 경계를 모두 승인한다. 2020–2025에 동일한 기준을
> 적용하는 단계적 safe-body adoption을 승인하며, 718,364개 후속 발화는 별도
> shard로 보존한다. 승인자 ari30.

후속 논의에서 연구자는 2020부터 2025까지 연도별로 같은 r3 기준으로 다시
정렬하는 방향을 확정했다.

승인 계약 ID:
`102a3b1a0641ef28cfe1c6115fc61e392005289ce7dc0c09d188bc6c7c181008`

## 선택 이유

- 여섯 연도 모두 동일한 사전·acoustic phone inventory·정렬 계약을 사용했다는
  방법론 설명이 가장 단순하고 검증 가능하다.
- r2/r3 interval을 최종본에서 섞을 때 필요한 동등성 증명과 provenance 복잡성을
  제거한다.
- 기존 r2 결과를 삭제하지 않아 차이 분석, 회귀 검사와 오류 복구 근거는 남는다.

전수 재정렬은 오류가 날 때 연도 전체를 자동 재시작한다는 뜻이 아니다. 입력,
정렬 DB, TextGrid export, 동반 CSV, 최종 감사 단계를 분리하고 각 단계가 동결
입력 fingerprint와 checkpoint를 갖는다. 국소 오류는 해당 단계·exact ID·완전한
MFA 적응 단위까지만 다시 처리한다.

## 반복하지 않는 것

- r3 canonical/readiness Stage 01–18
- Stage 19 발화 라우팅 전수 계산
- Stage 20 후보사전 projection·독립 감사
- Stage 21 네 발화 표적 회귀 정렬과 연구자 경계 검토
- 기존 2020–2022 r2 광범위 사람 검토
- 같은 입력의 G2P 재생성

## 생산 전 남은 Gate

1. 외부 도구의 workflow·코드 검토와 결과 반영
2. 단계적 r3 release·adoption contract 물질화와 독립 감사
3. 기존 r2 전용 runner를 별도 r3 전수 runner로 분리
4. safe/follow-up exact-ID 회계를 연도 입력 계약에 결속
5. Windows PowerShell 5.1 안전·runtime compatibility 검사
6. 2020 `-PreflightOnly` GO

이 Gate 전에는 생산 MFA를 시작하지 않는다.
