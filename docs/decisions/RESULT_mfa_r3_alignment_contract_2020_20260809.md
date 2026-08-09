# 2020 r3 alignment contract 결과 (2026-08-09)

## 목적

외부 리뷰 H2를 반영하여, 2020 r3 정렬의 방법론적 동일성을 하나의 불변
alignment contract ID로 증명할 수 있게 했다. 기존 `mfa_alignment_contract.v1`
은 r3 release ID와 release manifest SHA가 identity에 완전하게 들어가지 않고
발음 release 고유 조건도 코드 상수에 의존했다. 새 계약은 r3 전용 schema로
분리했으며 MFA를 실행하거나 Gate를 여는 기능은 갖지 않는다.

## 결과

- schema: `mfa_r3_alignment_contract.v1`
- status: `materialized_pending_runner_preflight_and_release_gate`
- year: `2020`
- pronunciation release: `common_pron_mfa_r3_20260809`
- pronunciation contract ID:
  `58226aeded930a5b09985c7a1ad870effbfb39fbbfd7d89229f84578cd3402af`
- year input contract ID:
  `d75fa5bc50cc31c3912220d1cb292eb74ab8e9da4216988926dbaa89c34919ce`
- alignment contract ID:
  `3eff5ae34eb1015c05532140162636609099f1fd1203f561cc06d837039d8e8a`
- expected MFA input: 782,715 발화
- alignment origin: `fresh_r3_full_realign`
- `r3_full_realign=true`

계약 파일:

`D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\04_alignment_contracts\2020\ALIGNMENT_CONTRACT_2020.json`

독립 감사 보고서:

`outputs/reports/AUDIT_mfa_r3_alignment_contract_2020_20260809.json`

## contract ID에 직접 포함한 항목

1. pronunciation release ID
2. pronunciation contract ID
3. pronunciation release manifest SHA-256
4. staged adoption contract SHA-256
5. staged adoption 독립 감사 SHA-256
6. 연구자 승인 SHA-256
7. Stage 19 manifest SHA-256(`safe_body_routing_contract_id`)
8. 2020 year input contract ID와 SHA-256
9. expected MFA input exact-ID 목록 SHA-256
10. pronunciation follow-up 목록 SHA-256
11. 2020 recovered corpus contract ID
12. frozen model pin SHA-256
13. r3 MFA 사전 SHA-256
14. acoustic model SHA-256
15. G2P model SHA-256
16. Python·MFA·Pynini 판본
17. `pronunciation_mode`, `alignment_origin`, `r3_full_realign`

경로와 mtime은 감사 본문에는 기록하지만 contract ID에는 넣지 않았다. 같은
내용을 다른 경로로 옮겨도 방법론적 identity는 같고, 내용 SHA가 바뀌면
contract ID는 달라진다.

## 독립 감사

별도 감사기는 contract ID를 자체 구현으로 재계산하고, release·연도 입력
계약·사전·음향모델·G2P·model pin의 실제 바이트 SHA를 다시 대조했다. 또한
Gate의 `allowed_release_ids=[]`, 기존 marker/DB 재사용 금지,
`r3_full_realign=true`를 확인했다.

감사 상태는
`passed_independent_identity_audit_pending_runner_and_release_gate`이다.

## 변경하지 않은 것과 다음 단계

- Stage 01–21, 원자료, 모든 r2 DB·TextGrid·CSV: 변경 없음
- production MFA, TextGrid materialization: 실행 안 함
- release Gate: 닫힘 유지

다음 단계는 이 alignment contract만 허용하는 release-scoped r3 runner와
fail-closed `-PreflightOnly`를 구현하는 것이다.
