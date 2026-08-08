# 공통발음 r3 adoption 선택 Gate — 연구자 결정 대기

날짜: 2026-08-08 KST
상태: `blocked_as_expected_at_explicit_method_choice_and_manual_targeted_review`

## 자동으로 확정된 것

- 881,237개 관측 표면형을 readiness v4에서 정확히 한 번씩 회계했다.
- candidate 795,804형·27,043,261회는 107-phone 동결 acoustic inventory 안에서
  전수 projection·사전 동등성 감사를 통과했다.
- 5,103,356발화를 같은 tokenizer와 같은 라우팅 규칙으로 전수 검사했다.
- safe body는 4,384,992발화, follow-up은 718,364발화다.
- 35개 policy형·163회에 재사용 가능한 과거 연구자 결정은 없었다. r2 생성
  phone을 연구자 승인으로 소급 해석하지 않았다.
- 기존 MFA·TextGrid·원자료는 변경하지 않았다.

## 자동으로 정할 수 없는 선택

### A. 전 유형 완결 뒤 adoption

zero-fallback hold 85,398형·803,644회와 policy 35형·163회의 최종 phone을 모두
해결할 때까지 생산 MFA를 시작하지 않는다. “전체 관측 어휘가 하나의 최종 r3
사전으로 완결됐다”는 가장 강한 주장에 적합하지만, 다음 정렬 진입이 크게 늦어진다.

### B. 단계적 safe-body adoption

4개 표적 TextGrid의 최소 경계 검토가 통과하면 safe body 4,384,992발화에만
candidate 사전을 명시 채택한다. 718,364발화는 정확 ID와 문제 어절을 보존한
follow-up shard로 유지하며, 전체 코퍼스 완료라고 주장하지 않는다. 여섯 연도에
동일한 발음 기준과 동일한 라우팅 규칙을 적용하므로 연도 간 방법론 일관성은
유지된다.

현 단계의 권고는 **B**다. 연구 목적은 전수 정렬 인프라를 실제로 진전시키면서도
근거 없는 발음을 억지로 채우지 않는 것이기 때문이다. 다만 이는 기존
`blocked_pending_r3` release Gate를 연구자의 명시 승인으로 고치는 방법론 선택이며,
자동화가 대신 결정할 수 없다.

## 승인 전 금지 사항

- 생산 MFA와 6-tier TextGrid materialization
- r2 TextGrid phone label의 제자리 치환
- follow-up 발화 삭제 또는 일부 어절만 제거한 정렬
- 후보 phone을 표준발음이나 실제 실현으로 서술

종합 보고서는
`outputs/reports/AUDIT_common_pron_r3_adoption_readiness_20260808.json`이다.
