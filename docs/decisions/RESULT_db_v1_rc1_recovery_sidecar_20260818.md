# DB v1 RC1 recovery sidecar 채택 결과

## 완료 상태

연구자 승인에 따라 첫 recovery shard 55건과 D10 수동 전사·word 경계 16건을
RC0 불변 append-only sidecar로 채택했다. release 상태는
`internal_rc1_recovery_sidecar_adopted`, 독립 감사 상태는
`passed_internal_rc1_append_only_sidecar`다.

산출물:

```text
outputs/releases/nikl_dialogue_research_db_v1_0_0_rc1_20260818
```

## 채택된 내용

- recovery 상태 55건
  - 기술 제외 30
  - 전사 회수 후보 2
  - 부분 정렬 보존 6
  - curated 수동 복구 16
  - D9 정렬 성공·6-tier 보완 대기 1
- 수동 annotation snapshot 16건
- `active_annotation_source=curated` pointer 16건
- 연구자 승인 원문과 후보 SHA의 release 내부 사본

D10 수동 TextGrid는 word 경계와 최종 한글 전사·철자 Roman만 활성화했다.
D9 phone은 `d9_reference_only_not_adopted`, 수정 전사 형태소는
`pending_rebuild_from_curated_transcript`, phoneme은
`pending_curated_alignment`로 유지했다.

## 회계

RC0의 5,103,356발화와 4,286,046개 정렬 성공 6-tier는 변하지 않았다. D0의
recovery 장부 817,310건 중 첫 55건에 후속 상태가 생겼고 817,255건은 기존
recovery 장부에 그대로 남는다. D9 1건과 curated 16건을 본체 정렬 성공 수에
더하지 않은 이유는 수정 전사에 맞는 6-tier·형태소·phone 보완이 아직 별도
Gate이기 때문이다.

## 안전·재현성

- RC0 수정 0
- r3·보존 MFA DB 수정 0
- 최종 6-tier·TextGrid 수정 0
- MFA 실행 0
- phone 자동 채택 0
- 형태소 자동 재구축 0

materializer는 먼저 Git 커밋 `bf3e51731f13a2187362387a9169e31cf591d4e9`로
고정했다. RC1 manifest SHA는
`0b3288fb7c2f2b1b750072b6facc6c13faaed7018651fa2e11670b8a7c9be48e`,
승인 SHA는
`1de47c47acf7eb733ff1083997775a799e0de4dfc8a3ce0273d89f9530a49b1e`다.

## 다음 단계

다음은 전수 MFA나 D7–D10 검토 반복이 아니다. 2026-08-18 방향 재점검에 따라
curated 16건의 형태소·phone/phoneme enrichment는 실제 표적 포함 시 exact-ID로
지연 처리한다. 우선 RC0 기본값과 RC1 curated pointer의 precedence를 범용 target
query·검토 bundle·세션 JSON이 공통으로 사용하게 한다. 기존 D9 phone을
기계적으로 복사해 최종 phone으로 만들지 않는다. 상세 결정은
`DECISION_post_RC1_priority_reset_20260818.md`에 기록했다.
