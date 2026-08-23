# 결정: Stage 2 일곱 현상 Gate 0 공통 계약 채택

- 결정일: 2026-08-23 KST
- 결정자: 연구자 ari30
- 상태: `gate0_adopted_snapshot`
- 다음 허용 범위: **NI Gate 1 설계 문서화만**
- 아직 허용하지 않은 범위: Gate 1 코드 구현, G5/G6 실행, 신규 query 생성·동결,
  실현 판정, TextGrid 수정, 정식 ledger 기록

## 1. 결정

연구자는 Codex가 작성하고 Claude Code가 독립 검토한 Stage 2 Gate 0 공통
계약(A1~A6)을 채택한다. 이 채택은 공통 구조·enum·상태 사전·빈 계약 틀·
sidecar 스키마의 연구 워크플로우 사용 승인이며, 개별 현상의 환경값·실현값·
문헌 주장을 자동으로 확정한다는 뜻이 아니다.

Gate 0 파일 안의 `candidate_pending_researcher_adoption`은 감사 당시의 불변
스냅샷 상태값으로 남긴다. 감사된 파일의 바이트와 SHA를 바꾸지 않고, 현재의
채택 상태는 이 결정 문서가 기록한다.

## 2. 채택 근거

- 독립 검토:
  `docs/reviews/incoming/EXTERNAL_REVIEW_stage2_gate0_common_contracts_claude_code_20260823.md`
  - SHA-256:
    `a63848230815d30a869043adbb714c0d04e3c6d98a3e508bcd34b61614af62a9`
  - 최종 판정: `GO`
  - P0 0건, P1 0건, 중대 발견사항 없음
- 감사 JSON:
  `outputs/pilots/stage2_gate0_common_contracts_20260823/AUDIT_stage2_gate0_common_contracts_20260823.json`
  - SHA-256:
    `62d7221b65c862baeea5e1b85809b385e173ecdbd98e53f70b2587f1f5d85671`
  - `passed=true`
- 채택 대상 15종과 감사 JSON의 SHA 목록:
  `outputs/pilots/stage2_gate0_common_contracts_20260823/SHA256SUMS_stage2_gate0_common_contracts_20260823.txt`
  - SHA-256:
    `3b5716ac024dcdfbe3a685ca36dccc5be0907e5915e0508afd960fe967e0112a`
- 문헌 실측: inventory 362행, claim 156행, source 결속 오류 0건,
  `needs_human_check` 5건 보존.
- 선언 실측: 7현상 registry 완결, 실제 환경 배정 0행, 계약값 0행,
  sidecar 데이터 0행, 자동 실현 판정 0건.

## 3. 보조사 ‘요’의 상태

보조사 ‘요’ 앞 ㄴ삽입은 **사용자 결정 완료 항목**이다.

1. 본모집단과 분리한 탐색 query 후보로 등록한다.
2. 기존 동결 query(SHA `744bd8cb…`)를 변경하거나 재동결하지 않는다.
3. Gate 1에서는 후보 문서만 작성하고 실제 query JSON 생성·동결은 별도 승인
   전까지 하지 않는다.
4. 따라서 이후 계획의 “사용자 결정 필요” 목록에 ‘요’를 다시 넣지 않는다.

Gate 0 registry의 `pending_exploratory_query_candidate`는 결정 대기가 아니라
실제 query 산출물이 아직 없는 구현 생명주기 상태다.

## 4. Claude Code P2 처리

| 항목 | 처리 |
|---|---|
| P2-1 git allowlist 시점 고정 | Gate 0 감사기는 2026-08-23 불변 스냅샷 검사기로 보존. 외부 검토 추가 뒤의 worktree 차이를 숨기도록 고치지 않음 |
| P2-2 문헌 CURRENT_STATE·DECISION_LOG SHA 고정 | 역사적 Gate 0 입력 pin으로 유지. 후속 문헌 갱신은 새 Gate 감사 버전에서 새 기준선 사용 |
| P2-3 존재하지 않는 SRC/CLM 실패 테스트 | Gate 1 독립 검사기 테스트에 추가 |
| P2-4 문서·스크립트 색인 | 이 채택 문서와 함께 갱신 |
| P2-5 CLM 범위 표기 명료화 | 감사된 Gate 0 초안은 불변. NI Gate 1 새 definition에서 명료화 |
| P2-6 `definition_status` 어휘 통일 | 감사된 Gate 0 초안은 불변. 다음 registry/definition 버전에서 단일 enum으로 통일 |
| P2-7 감사 JSON의 출력 전 worktree 시점 | 정상 동작으로 기록, 조치 없음 |

## 5. 사람 확인 문헌의 시점

- NI 관련 `CLM-0008`, `CLM-0015`, `CLM-0026`은 Gate 1 계약 근거로 사용할
  때 검토하거나 명시적으로 유보한다.
- 특히 inclusion 환경에 직접 영향을 줄 수 있는 `CLM-0015`는 NI 계약 동결
  전에 우선 확인한다.
- HIA 관련 `CLM-0145`, `CLM-0151`은 HIA 착수 Gate까지 유보한다.
- 미확정 상태를 빈값·행 삭제·자동 확정으로 바꾸지 않는다.

## 6. 다음 Gate

다음 작업은
`docs/decisions/PLAN_stage2_gate1_NI_reference_implementation_20260823.md`의
설계 검토다. 이 계획의 작성·검토는 승인되었으나, 그 계획에 적힌 코드를
구현하는 것은 별도의 `Gate 1 구현 GO`를 요구한다.

commit·push는 이 결정에 포함되지 않는다.
