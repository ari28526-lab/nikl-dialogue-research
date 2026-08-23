# SCHEMA: Stage 2 일곱 현상 Gate 0 공통 계약

기록일: 2026-08-23 KST  
상태: **후보 — 독립 감사 통과 후에도 연구자 채택·동결 전**

## 1. 범위

이 문서는 일곱 현상(PT·NAN·NAL·NI·LLN·VH·HIA)의 Gate 0에서 A1~A6의
구조만 선언한다. 현상별 query 값, 실제 4단 환경 분류, inclusion/exclusion/
confound 값, 실현 판정, TextGrid 작업 queue, 공개 파생본은 범위 밖이다.

정본 입력:

- 문헌 handoff:
  `docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json`
- SOURCE_INVENTORY 362행, SHA
  `e8de6907f632a5b64853a6386c7d510ba69852451322630dc43ea201fefa0680`
- CLAIM_EVIDENCE 156행, SHA
  `1e88f5513f4c57387954d6149d922ccfc20ad024cfb8df63d492d96e0924610a`
- NI query SHA
  `744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6`

## 2. A1 definition

공통 템플릿은 `phenomena/_templates/definition.v1.md`다. 기존 NI definition은
`phenomena/34_n_insertion/definition.md`를 그대로 참조하고 수정하지 않는다.
나머지 6현상은 `phenomena/_draft/<CODE>/definition.md`에 문헌 seed ID만 연결한
초안을 둔다.

NI는 별도 착수스캐폴드가 없으므로 registry의 `literature_scaffold_path`가
`null`이다. 이는 누락이 아니라 NI 현상종합 문서 §4가 재개 지점인 현재 문헌
계약을 반영한다.

## 3. A2 registry

`config/phenomena_registry.v1.json`의 최상위 필드는 다음과 같다.

- `schema_version`
- `status`
- `generated_from`: 입력 경로·행 수·SHA
- `phenomena`: 정확히 7개 객체

현상 객체 필수 필드:

```text
phenomenon_code, label_ko, official_slug, slug_status,
definition_path, definition_status,
literature_synthesis_path, literature_scaffold_path,
literature_evidence_level,
core_extracted_source_count, core_extracted_claim_count,
total_phenomenon_claim_mentions, a_direct_count,
query_status, frozen_query_sha256, gate_position, notes
```

NI만 기존 slug·동결 query SHA가 있으며, 나머지 6현상의 query는
`draft_pv_only`다. draft 조건을 frozen으로 해석하지 않는다.

## 4. A3 환경 분류 enum

환경 유형 단위의 허용값은 다음 네 가지다.

```text
general_direct
peripheral_reported
theoretical_underreported
unclear_boundary
```

`config/stage2_environment_class_enum.v1.json`은 enum과 필드만 선언한다.
Gate 0의 `assignment_rows`는 빈 배열이다. 미확정 환경에 특정 값을 자동으로
채우지 않으며, occurrence 단위 분류로 오용하지 않는다.

## 5. A4 inclusion/exclusion/confound 템플릿

`config/stage2_inclusion_exclusion_confound_contract_template.v1.json`은 빈
계약 틀이다. include/exclude/confound/membership 배열은 모두 비어 있고
`contract_status=draft`, `query_reference=null`이다. 현상별 조건값은 Gate 1
이후 연구자 승인으로만 생성한다.

## 6. A5 zero-drop 상태

`config/stage2_zero_drop_status_dictionary.v1.json`은 상태를 독립 축으로 둔다.
특히 다음 세 축을 하나의 enum으로 합치지 않는다.

```text
textgrid_review_need = not_needed | required | unsure
textgrid_asset_status = available | unavailable | blocked
manual_task_status = not_created | queued | exported | returned | audited
```

따라서 `required + unavailable`은 모순이 아니다. zero-drop은 각 적용 축에서
입력 행 수가 상태별 행 수 합과 일치하는지 별도로 검사한다. 서로 다른 축의
상태 수를 한 식으로 더하지 않는다.

## 7. A6 추가 정보 sidecar

`config/stage2_additional_information_sidecar_schema.v1.json`은 JSONL 한 행의
JSON Schema다. Gate 0에서는 실제 JSONL 데이터 파일을 만들지 않는다.

예시(문서 예시이며 실제 데이터 행이 아님):

```json
{
  "schema_version": "stage2_additional_information_sidecar.v1",
  "request_id": "INFO-000001",
  "phenomenon_id": "NI",
  "occurrence_id": "<exact occurrence id>",
  "key_namespace": "unregistered",
  "information_key": "prosodic_boundary_review",
  "requested_reason": "어절 간 후보의 AP/IP 경계 확인 필요",
  "value_status": "pending",
  "value_text_or_ref": null,
  "evidence_source": null,
  "evidence_sha256": null,
  "reviewer": null,
  "recorded_at": "2026-08-23T00:00:00+09:00",
  "supersedes": null
}
```

수정은 기존 행 덮어쓰기가 아니라 새 `request_id`와 `supersedes` 연결로 한다.
`pending`, `unavailable`, `not_applicable`을 빈값이나 행 삭제로 숨기지 않는다.

## 8. 문헌 근거 상태

- `claim_verified`: CLM-0001~0026 NI 파일럿
- `pending_researcher_adoption`: CLM-0027~0156 확장 추출
- `needs_human_check`: CLM-0008, CLM-0015, CLM-0026, CLM-0145,
  CLM-0151
- `source_level_only`: CLM이 없는 SRC-360, SRC-361, SRC-362, SRC-356

사람확인 5건은 Gate 0에서 `non_blocking_pending`이지만 후속 인용·계약 채택
전에 해소하거나 유보 상태를 명시해야 한다.

## 9. 불변 안전 규칙

- 원자료·r3 DB·동결 6-tier·동반표·문헌 워크스페이스·기존 NI definition·
  query를 수정하지 않는다.
- MFA·KOINA·wav2vec2를 실행하지 않는다.
- 자동 실현 판정과 정식 ledger 자동 쓰기를 금지한다.
- 신규 파일은 `.partial` 완성 뒤 원자 승격하고 기존 파일을 덮어쓰지 않는다.
- audit manifest는 자신을 해시하지 않는다.

## 10. 채택 상태

독립 감사의 `passed=true`는 구조·경로·SHA 무결성만 뜻한다. 이 문서와 선언
파일은 연구자가 별도로 채택하기 전까지 `candidate_pending_researcher_adoption`
상태이며 Gate 1을 열지 않는다.
