# 결정: Stage 2 Gate 1 NI 계약 후보 채택 — 연구자 결정 기록

- 결정일: 2026-08-23 KST
- 결정자: 연구자 `ari30` (Cowork 대화에서 검토 보고서 §8 질문에 직접 답변)
- 상태: `gate1_adopted_pending_freeze_implementation`
- 이 문서는 결정 기록이다. frozen 파일은 아직 만들지 않았고, 이 기록만으로
  자동 승격되지 않는다.

## 1. 근거 검토

- 독립 검토:
  `docs/reviews/incoming/EXTERNAL_REVIEW_stage2_gate1_n_insertion_contracts_claude_code_20260823.md`
  - SHA-256:
    `8ed621ccf75f8ba9044799c96506bb00fbe39f881e6b1f8455b3752a4e495bc0`
  - HTML 동일 내용본 SHA-256:
    `ec9fb90cf6e50f54e4b0e617a7e01342ef50e0620fd5c2b2173d9678331aaaac`
  - 최종 판정: `GO_FREEZE_REVIEW`, P0 0건, P1 0건, 중대 발견사항 없음
- Codex Gate 1 감사:
  `outputs/pilots/stage2_gate1_n_insertion_contracts_20260823/AUDIT_stage2_gate1_n_insertion_contracts_20260823.json`
  (SHA `f08dfe99…8ad15e`, 검토에서 독립 재계산 일치)

## 2. 연구자 답변 원문과 해석

검토 보고서 §8의 질문에 대한 연구자 원문 답변(2026-08-23 Cowork):

> "1번-최대한 환경 다 넣기 2번 채택, 3번 무슨말인지 모름"

| ID | 결정 | 해석·적용 |
|---|---|---|
| D-G1-A | **환경 최대 포함 + CLM-0015 유보** | 환경 유형 7행을 하나도 제외하지 않고 전부 연구 대상으로 보존한다(한자어 공명음·장애음 두 환경 포함, 비실현 비교군도 삭제하지 않음). CLM-0015의 원문 확인은 **명시적 유보**한다 — 유보 사유: CLM-0015(안미진 2008, SRC-287)의 보강 인용 Hwang(2007) 학회 발표문이 수배 목록의 Hwang(2008) SNU 석사논문과 동일 연구 계열인지 원전 대조가 필요하나(CLAIM_EVIDENCE `extraction_note`), 해당 원문이 **미보유·수배 중**(`MISSING_ORIGINALS_WANTED.jsonl`)이라 지금 확인이 불가능하다. 따라서 `NI_ENV_SINO_RESONANT_J`·`NI_ENV_SINO_OBSTRUENT_J` 두 행은 `class_status=pending`을 유지한 채 동결하고, 정본의 `needs_human_check=true` 플래그는 그대로 둔다. 이 유보 기록이 계약 `NI_UNR_001`(`needs_human_check_before_freeze`)의 "확인 결과 또는 유보 사유" 요건을 충족한다. Hwang 원문 입수 시 별도 후속 확인으로 해소한다. |
| D-G1-B | **채택 — freeze 구현 GO** | Gate 1 후보 3종(계약 `n_insertion_contract_candidate_v1_20260823.json`, 환경 유형 `n_insertion_environment_types_candidate_v1_20260823.jsonl`, definition `definition_stage2_candidate_v1_20260823.md`)과 source registry·'요' NOTE를 채택한다. frozen v1 생성을 승인하되, 기존 candidate 파일은 덮어쓰지 않고 **새 frozen 버전 파일 + 채택 감사**를 만든다(§4). |
| D-G1-C | **미결정 — 비차단** | probe 회귀 보강(검토 P2-1)은 연구자에게 설명 후 결정 대기. 이번 채택·동결을 막지 않으며 LLN 착수 전까지만 정하면 된다. 검토자 권고: 감사기를 고치지 않고 단일 목적 probe 스크립트를 커밋하는 방식. |

재질문하지 않는 기결정: 보조사 '요' 처리(본모집단 밖 탐색 후보, D1),
어절 간 실제 검토 시점(후속 Gate로 연기). 이 문서도 이를 변경하지 않는다.

## 3. 이 결정으로 여는 다음 허용 범위

freeze 구현 1회 — 내용은 §4. 여전히 범위 밖: G5/G6 실행, '요' query JSON
생성, 신규 후보 추출·occurrence 파생, 실현 판정, TextGrid 수정, MFA·KOINA·
wav2vec2, 정식 ledger 기록. commit·push는 이 기록에 포함되지 않으며 구현
완료 후 사용자 승인으로 별도 수행한다.

## 4. freeze 구현 지시 초안 (구현 도구 인계용)

1. 신규 파일만 생성한다(기존 파일 수정·삭제·덮어쓰기 금지, `.partial` 완성
   후 원자 승격, 기존 출력 존재 시 `FileExistsError` 중단):
   - `config/phenomenon_contracts/n_insertion_contract_frozen_v1_<date>.json`
     — candidate 내용 유지, `contract_status=frozen`,
     `researcher="ari30"`, `confirmed_at` 기입, `supersedes`에 candidate
     경로·SHA 결속. `NI_UNR_001`은 삭제하지 않고 이 결정 문서의 D-G1-A 유보
     기록으로 해소됨을 상태로 기록(`deferred_by_decision` 등), 한자어 관련
     항목의 pending 성격은 보존.
   - `config/environment_types/n_insertion_environment_types_frozen_v1_<date>.jsonl`
     — 7행 유지. 행 1·2·5는 연구자 확정 반영, 행 3·4는
     `class_status=pending` + D-G1-A 유보 사유 참조, 행 6·7은 기존
     pending/deferred 유지. append-only·`supersedes` 규칙 준수.
   - `phenomena/34_n_insertion/definition_stage2_frozen_v1_<date>.md`
     — candidate 대체가 아니라 새 버전, 상태 어휘는 Gate 0 P2-6 방향(짧은
     enum + 별도 생명주기)을 따른다.
2. 채택 감사: 새 감사기(또는 기존 감사기 확장판)의 신규 AUDIT JSON +
   SHA256SUMS를 `outputs/pilots/stage2_gate1_ni_freeze_<date>/`에 생성.
   manifest는 자기 자신을 해시하지 않는다.
3. 색인 2종 갱신(검토 P2-3): `scripts/SCRIPTS_INDEX.md`에 Gate 1 감사기,
   `docs/decisions/_INDEX.md`에 본 결정·NOTE·검토 보고서 등재.
4. git allowlist 재기준선(검토 P2-2): 채택 커밋 시점의 저장소 상태로 새
   기준선을 만들고, 2026-08-23 Gate 1 감사기는 불변 스냅샷 검사기로 보존
   (Gate 0 채택 문서 §4와 같은 정책).
5. 검증: py_compile → 단위 테스트 → `--check-only` → 산출물 생성 → 재해시
   로그. 대용량 CSV 재해시·전수 스캔 금지, 941,903 zero-drop 등식 재확인.

## 5. CLM-0015 후속 확인 경로 (비차단)

Hwang(2008) SNU 석사논문 입수 시(수배 목록 경유): 안미진 2008 (25a,b)·§3.4의
Hwang(2007) 인용과 대조해 동일 연구 계열 여부를 확인하고, 결과를
CLAIM_EVIDENCE 정본(append-only 원칙)과 후속 결정 문서에 기록한 뒤 한자어 두
환경의 `pending` 해소 여부를 결정한다. 그 전까지 두 환경은 포함·pending으로
유지한다.
