# EXTERNAL REVIEW: Stage 2 Gate 0 공통 계약(A1–A6) 구현 독립 검토

- 작성: Claude Code (fable5, 독립 검토), 2026-08-23 KST
- 성격: **검토 보고서 — 구현 아님.** 코드·config·definition·문헌 워크스페이스·
  원자료·TextGrid·DB를 수정하지 않았고, MFA·KOINA·wav2vec2를 실행하지 않았으며,
  git add/commit/push를 하지 않았다. 산출물은 이 MD와 동일 내용 HTML 두 파일뿐이다.
- 검토 대상: Codex가 구현한 Gate 0 공통 계약(A1–A6) — 선언 파일 5종, definition
  템플릿·초안 6종, 독립 감사기·테스트, AUDIT JSON·SHA manifest, 검증 로그 7종.
- 검증 방식: Codex 감사 스크립트와 **별도로 작성한 독립 파서·재해시 스크립트**
  (스크래치패드, 저장소 밖)로 정본 파일을 직접 파싱·재해시했고, 허용된 두 명령
  (`--check-only` 감사, 단위 테스트)을 지정된
  `C:\Users\ari30\miniforge3\envs\mfa\python.exe`로 재실행했다.
  `--check-only` 없는 감사 실행은 하지 않았고 기존 출력을 덮어쓰지 않았다.

## 1. 최종 판정

> ## **GO**
>
> P0(차단 오류) 0건 · P1(지금 고쳐야 하는 오류) 0건. **중대 발견사항 없음.**
> 독립 실측이 Codex 감사 결과와 전 항목 일치했고, 범위 일탈·기존 파일 변경·
> 조용한 확정을 발견하지 못했다. 아래 P2는 전부 "수정 제안·운영 주의"이며
> 구현을 지금 고칠 필요는 없다.
>
> 단, GO는 "Gate 0 후보가 계약대로 만들어졌다"는 검토 판정이다. 산출물 상태는
> 여전히 `candidate_pending_researcher_adoption`이고, **연구자 채택·동결과
> Gate 1 착수는 별도 사용자 GO가 필요하다**(§8).

## 2. 범위 준수 확인 (검토 지시 1·5항)

| 확인 항목 | 결과 | 근거 |
|---|---|---|
| Gate 0 A1–A6 선언·스키마에만 머물렀는가 | **적합** | 신규 파일 = 선언 5종 + 템플릿 1 + 초안 6 + SCHEMA 문서 + 감사기·테스트 + AUDIT/manifest + 로그 7종뿐. git 미추적 목록이 handoff v2 §5 allowlist와 정확히 일치 |
| Gate 1·후보 추출 미착수 | **적합** | `outputs/`에 AUDIT·manifest 외 신규 산출물 없음. 후보 추출·문맥 연결 산출물 0 |
| 자동 실현 판정 없음 | **적합** | AUDIT `scope_assertions.automatic_realization_judgement=false`; 판정값을 만드는 코드·데이터 없음 |
| 정식 ledger 쓰기 없음 | **적합** | 이름에 ledger가 든 파일 전수 확인 — 전부 2026-08-15~18 기존 산출물, 신규 0 |
| 신규 query 생성·동결 없음 | **적합** | `config/target_queries/` 파일 3종 그대로(2026-08-18/19 기존본). '요' 환경은 registry notes에 `pending_exploratory_query_candidate` 참조만 |
| A3 실제 분류행 0 | **적합** | `assignment_rows: []` + 저장소 전체에서 `environment_class` 분류행·`INFO-######` sidecar 데이터 JSONL 탐색 0건 |
| A4 빈 계약 틀 | **적합** | 배열 6종 전부 `[]`, `contract_status=draft`, `query_reference=null` |
| A6 스키마만 존재 | **적합** | JSON Schema 1개 + SCHEMA 문서 예시 1건뿐, 실제 sidecar 행 0 |

## 3. 독립 실측 결과 (검토 지시 2·3·4·8항)

### 3.1 보호 입력 SHA-256 — 7/7 일치

| 파일 | 독립 재계산 SHA-256 | 판정 |
|---|---|---|
| config/target_queries/n_insertion_production_v1_20260818.json | `744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6` | 요청 기준값과 일치 |
| phenomena/34_n_insertion/definition.md | `aa23b940d1e556df98cee5f332e8757f886ab098f468620fe084b93e90983513` | 요청 기준값과 일치 |
| docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json | `938353d719e1ddc57c8ba96ca4694310f6570a4b4ca944f684a5a66961bdebae` | handoff v2 §2 일치 |
| work/…/01_inventory/SOURCE_INVENTORY.jsonl | `e8de6907f632a5b64853a6386c7d510ba69852451322630dc43ea201fefa0680` | handoff v2 §2 일치 |
| work/…/02_claims/CLAIM_EVIDENCE.jsonl | `1e88f5513f4c57387954d6149d922ccfc20ad024cfb8df63d492d96e0924610a` | handoff v2 §2 일치 |
| work/…/00_admin/CURRENT_STATE.md | `a2de36342a29cc143a56e887b525c37acbd27eca028d37c92bac37cb6a76506c` | 감사기 pin과 일치 |
| work/…/00_admin/DECISION_LOG.jsonl | `be2235e5f9cbc20bdff4265be634d23f5ac4a71ca364c792c86451d9f6b90253` | 감사기 pin과 일치 |

### 3.2 문헌 정본 직접 파싱 — 전 항목 일치

- SOURCE_INVENTORY: **362행**, 공백행 0, `SRC-001`~`SRC-362` 연속·순서 정확.
- CLAIM_EVIDENCE: **156행**, 공백행 0, `CLM-0001`~`CLM-0156` 연속·순서 정확.
- CLM→SRC 결속(`source_id`·`source_file`·`source_sha256` 3중 대조): **오류 0건**.
- `needs_human_check=true`: 정확히 **CLM-0008·0015·0026·0145·0151** 5건, 전 행
  bool 형. **조용한 확정 없음** — 5건 모두 정본에 플래그가 그대로 남아 있고,
  handoff는 각각 `non_blocking_pending` 사유를 명시하며, HIA 초안도
  `non_blocking_pending`으로 표기한다. 어떤 Gate 0 산출물도 이 5건의 값을
  확정 인용하지 않는다.
- 운율 4종 SRC-360·361·362·356: 인벤토리 존재 + CLM 0건(`source_level_only`)
  독립 확인. 초안 6종 전부 "확정 주장으로 취급하지 않는다"로 표기.
- DECISION_LOG: 28행(CURRENT_STATE 표기와 일치).

### 3.3 handoff 참조 무결성 — 전 항목 일치

- handoff의 모든 SRC/CLM 참조가 정본에 존재하고 source 결속이 일치: **오류 0**.
- CLM 참조 포괄: **156/156**. 고유 SRC 참조: **28종**.
- 추가 심층 확인(감사기가 하지 않는 검사): **28종 SRC의 원문 파일을 실제로
  열어 재해시 — 인벤토리 `sha256`과 28/28 일치.** handoff의
  `core_extracted_*`·`total_phenomenon_claim_mentions`·`a_direct_count`
  수치도 정본에서 독립 재집계해 전부 일치(§3.4).
- NI 26/32 구분: `ni_pilot_split`이 파일럿 26건(CLM-0001~0026, 전부 NI 태그
  독립 확인)과 NI 태깅 총 32건(교차 태깅 Zuraw 6건 명시)을 분리 보존.

### 3.4 registry 수치 독립 재집계 — 7현상 전부 일치

| 현상 | core SRC (실측/registry) | core CLM (실측/registry) | 총 태깅 (실측/registry) | A_direct (실측/registry) |
|---|---|---|---|---|
| PT | 5 / 5 | 33 / 33 | 37 / 37 | 23 / 23 |
| NAN | 1 / 1 | 3 / 3 | 9 / 9 | 13 / 13 |
| NAL | 2 / 2 | 10 / 10 | 15 / 15 | 14 / 14 |
| NI | 4 / 4 | 26 / 26 | 32 / 32 | 32 / 32 |
| LLN | 4 / 4 | 26 / 26 | 34 / 34 | 16 / 16 |
| VH | 5 / 5 | 33 / 33 | 34 / 34 | 15 / 15 |
| HIA | 3 / 3 | 18 / 18 | 24 / 24 | 6 / 6 |

registry는 정확히 PT·NAN·NAL·NI·LLN·VH·HIA 7현상(중복·누락 0)이며 요구된
필수 필드 17종을 전부 갖췄다. NI 특수 규칙(slug `34_n_insertion`·
`assigned_existing`·`researcher_confirmed`·`frozen`·전체 64자리 query SHA·
scaffold `null`)과 6현상 placeholder 규칙(`pending_f0`·`draft_pv_only`·
`frozen_query_sha256=null`) 모두 준수. `generated_from` 4종 경로·SHA 실측 일치.
`NI_착수스캐폴드_20260823.md` 비존재(정합 상태) 확인.

### 3.5 SHA manifest·AUDIT 독립 재해시 — 전 항목 일치

- manifest 16항목(선언 15 + AUDIT JSON 1) **전부 독립 재해시 일치**.
- manifest는 **자기 자신을 포함하지 않음**(선언 목록·항목 어디에도 없음).
- AUDIT JSON 재해시:
  `62d7221b65c862baeea5e1b85809b385e173ecdbd98e53f70b2587f1f5d85671` — 보고값 일치.
- manifest 재해시:
  `3b5716ac024dcdfbe3a685ca36dccc5be0907e5915e0508afd960fe967e0112a` — 보고값 일치.
- AUDIT 내부 `artifact_sha256` 15항목도 실측 일치. Gate 0 대응 `.partial` 잔존 0.

### 3.6 zero-drop 상태 사전 축 독립성 (검토 지시 6항)

`config/stage2_zero_drop_status_dictionary.v1.json`은 여섯 독립 축을 선언한다:

| 축 | 값 |
|---|---|
| candidate_availability_status | candidate_ready… / candidate_metadata_only… |
| selection_status | not_selected_quota_or_duplicate / selected_primary / selected_shared_membership |
| timing_status | not_linked… / linked_single… / linked_inter… / pending_textgrid_asset_unavailable / pending_textgrid_word_mapping_review |
| textgrid_review_need | not_needed / required / unsure |
| textgrid_asset_status | available / unavailable / blocked |
| manual_task_status | not_created / queued / exported / returned / audited |

- 후보 가용성·선정·시점 / 검토 필요 / 자산 상태 / 수동 작업 상태가 **서로 다른
  축으로 분리**되어 있고, handoff v2 §8이 요구한 최소 3축의 값 집합과 정확히
  일치한다. **축 간 상태값 중복 0건**(복합 enum으로 합친 흔적 없음),
  `forbidden_combinations` 빈 배열(교차 제약 선제 고정 없음).
- 불변식이 "required+unavailable 동시 성립 가능"과 "서로 다른 축의 상태 수를
  한 합계식으로 더하지 않는다"를 명문화 — 검토 §A5·REQUIREMENT R1·R2의 축
  분리 요구를 정확히 구현했다.

### 3.7 definition 초안의 문헌 연결 방식 (검토 지시 7항)

- 초안 6종의 문헌 근거는 **SRC-###/CLM-#### ID와 저장소 상대경로로만** 연결된다.
  참조된 CLM/SRC 전부 정본 존재, 언급된 `work/…` 경로 전부 실재.
- **문헌 본문 복사 없음**: 각 초안의 산문은 일반적 현상 기술이며, 정본의
  `claim_ko`·쪽수(`printed_page`/`pdf_page`)·인용문을 옮긴 흔적이 없다(기계
  탐지 + 6종 전문 통독).
- 참조 CLM의 현상 태그 교차 대조(감사기가 하지 않는 검사): 불일치처럼 보이는
  4건은 전부 NAN·NAL·LLN·VH 초안의 **"CLM-0027 이후 주장은
  pending_researcher_adoption" 경계 표기 문장**에서 나온 CLM-0027(PT·NI 태그)
  언급이다. 근거 오용이 아니다(§7 P2-5 표기 제안 참조).

## 4. 허용 명령 재실행 결과

| 명령 | 결과 |
|---|---|
| `audit_stage2_gate0_common_contracts.py --check-only` (mfa python) | exit 0, `passed=true`, `status=passed_candidate_pending_researcher_adoption`, 362/156행·결속 오류 0·handoff CLM 156/SRC 28·분류행 0·계약값 0·sidecar 행 0·tracked 변경 0 — Codex 저장 AUDIT와 동일 값 재현 |
| `tests/test_audit_stage2_gate0_common_contracts.py -v` (mfa python) | exit 0, **5/5 OK** (성공·필드 누락 실패·SHA 실패·기존 출력 쓰기 거부·manifest 자기해시 배제) |

Codex 검증 로그 7종(01~07)도 통독했다: py_compile·테스트·check-only·최초
생성·기존 출력 거부(의도된 exit 1)·최종 재해시·사후 check-only가 모두 주장과
일치하며, 06 로그의 "기존 `.partial` 6개는 work/ 아래 무관 유물" 주장도 전수
탐색으로 재확인했다(6건 전부 2026-08-01 이전 파이프라인 잔재, Gate 0 대응 0건).

## 5. Codex 감사 결과와 독립 검사 결과의 차이

**수치·판정 차이 0건.** 행수·ID 연속성·결속 오류 0·human-check 5건·SRC 28/CLM
156·manifest 16항목·모든 SHA가 동일하게 재현됐다.

독립 검사가 Codex 감사보다 **더 깊이 본 부분**(모두 통과):

1. handoff 참조 SRC 28종의 **원문 파일 실물 재해시**(인벤토리 sha256 대조 28/28).
2. registry·handoff의 core/총 태깅/A_direct **수치를 정본에서 재집계**(감사기는
   registry↔handoff 일치만 검사하고 handoff 수치 자체는 재집계하지 않음 —
   [audit_stage2_gate0_common_contracts.py:208](../../scripts/python/audit_stage2_gate0_common_contracts.py) 부근).
3. 초안 참조 CLM의 현상 태그 교차 대조(§3.7)와 zero-drop 축 간 값 중복 검사.
4. 저장소 전체 `.partial`·sidecar 데이터·환경 분류행·신규 ledger·신규 query 탐색.

## 6. 기존 파일 변경 여부

**변경 0건으로 판정한다.** 근거:

- `git status --short` 실측: 추적 파일 변경(M/D/R) 0, 미추적 목록은 Gate 0
  allowlist + 구현 전부터 있던 결정·리뷰·handoff 문서뿐.
- 보호 입력 7종의 재계산 SHA가 **구현 이전에 작성된 문서**(HANDOFF v2 §2,
  SCHEMA §1, 외부 검토 §0)에 기록된 값과 동일 — 구현 과정에서 문헌 정본·NI
  definition·동결 query가 바뀌지 않았음을 SHA로 입증.
- 문헌 워크스페이스·`00_참고문헌`·`docs/reviews/incoming/_to_delete/` 접근·수정
  없음(본 검토도 `_to_delete/`를 열지 않았다).

## 7. 발견사항 — P0·P1·P2

### P0 (차단 오류) — 없음

### P1 (지금 반드시 고쳐야 하는 오류) — 없음

### P2 (수정 제안·운영 주의 — 지금 고칠 필요 없음)

| ID | 내용 | 위치 | 구분 |
|---|---|---|---|
| P2-1 | **감사기 git allowlist는 "그날의 저장소 상태"에 고정되어 있다.** 본 검토 보고서 2개 파일이 `docs/reviews/incoming/`에 생기는 순간, 이후의 `--check-only`는 `unexpected untracked paths`로 exit 1이 된다(정직한 fail-closed 동작이며 산출물 손상 아님). 재검증이 필요하면 ① 보고서·Gate 0 산출물을 커밋한 뒤 실행하거나 ② `--skip-git-check`를 붙이거나 ③ 채택 시 `PREEXISTING_UNTRACKED` 갱신을 함께 승인한다 | [audit_stage2_gate0_common_contracts.py:74](../../scripts/python/audit_stage2_gate0_common_contracts.py) (PREEXISTING_UNTRACKED), :330-354 (check_worktree) | 운영 주의 |
| P2-2 | 감사기 `EXPECTED_INPUTS`가 handoff 요구 4종 외에 **CURRENT_STATE.md·DECISION_LOG.jsonl SHA까지 고정** — 스냅샷 무결성엔 더 강해서 좋으나, 문헌 워크스페이스의 정당한 후속 갱신(예: LD-029 추가)만으로도 감사가 실패하게 된다. 채택 시 "이 감사는 2026-08-23 후보 상태 검증기이며 재기준선 없이는 재실행 보증이 없다"를 결정 문서에 명시 권고 | [audit_stage2_gate0_common_contracts.py:52-55](../../scripts/python/audit_stage2_gate0_common_contracts.py) | 운영 주의 |
| P2-3 | 단위 테스트에 '존재하지 않는 CLM/SRC 참조' 실패 시나리오가 없다(필드 누락·SHA 불일치·쓰기 거부·자기해시 배제는 있음). 성공 경로가 간접 커버하므로 차단 아님 — 후속 Gate에서 테스트 1개 추가 제안 | [tests/test_audit_stage2_gate0_common_contracts.py:22-59](../../tests/test_audit_stage2_gate0_common_contracts.py) | 수정 제안 |
| P2-4 | `scripts/SCRIPTS_INDEX.md`·`docs/decisions/_INDEX.md`에 신규 감사기·SCHEMA 문서가 미등재 — allowlist가 기존 파일 수정을 금지했으므로 **준수의 귀결**이다. 채택 커밋 때 색인 2종 갱신을 같이 승인 | scripts/SCRIPTS_INDEX.md, docs/decisions/_INDEX.md | 수정 제안(채택 시) |
| P2-5 | NAN·NAL·LLN·VH 초안의 "CLM-0027 이후 주장은 pending_researcher_adoption" 문장이 경계 표지로 CLM-0027(PT·NI 태그)을 언급 — 근거 오용은 아니나, 기계 대조 시 태그 불일치로 보일 수 있으니 채택 시 "CLM-0027~0156"처럼 범위 표기 제안 | phenomena/_draft/{NAN,NAL,LLN,VH}/definition.md §6 | 수정 제안(선택) |
| P2-6 | definition_status 어휘: 템플릿 §1 힌트는 `pending \| literature_seeded \| researcher_confirmed`, 초안·registry 실제값은 `literature_seeded_pending_researcher_confirmation` — 의미는 더 정확하나 어휘가 이원화됨. 채택 시 한쪽으로 통일 제안 | [phenomena/_templates/definition.v1.md:13](../../phenomena/_templates/definition.v1.md), registry `definition_status` | 수정 제안(선택) |
| P2-7 | AUDIT JSON의 `worktree.status_lines`에 `outputs/pilots/...`가 없다 — 감사가 출력 파일을 쓰기 **전에** 실측한 스냅샷이라 정상이며, 07 로그의 사후 `--check-only`가 outputs 포함 상태로 통과함을 확인했다. 정보 제공용 | AUDIT JSON `worktree` | 관찰(조치 불요) |

## 8. Gate 1 전 사용자 결정 필요 항목

1. **Gate 0 후보 채택·동결 여부** — registry·선언 5종·템플릿·초안 6종·SCHEMA
   문서를 `candidate_pending_researcher_adoption`에서 채택 상태로 올릴지.
   채택 없이는 Gate 1을 열지 않는 것이 현 계약이다.
2. **채택 시 감사 재기준선 정책**(P2-1·P2-2) — 보고서·산출물 커밋 시점,
   `PREEXISTING_UNTRACKED`/`EXPECTED_INPUTS` 갱신 또는 "1회성 검증기로 동결"
   중 택일. 색인 2종 갱신(P2-4)도 같은 커밋에서 처리 권고.
3. **needs_human_check 5건 처리 시점** — Gate 0에서는 `non_blocking_pending`
   유지가 계약대로다. Gate 1에서 해당 CLM을 계약 근거로 승격하기 전에 해소
   또는 유보 명시가 필요하다(특히 CLM-0015는 NI inclusion 후보 근거).
4. **D1 '요' 탐색 query 후보 문서화** — Gate 0에서는 pending 표지만 있는 것이
   맞다. Gate 1 산출물(후보 문서, 동결 아님)로 만들 시점 결정.
5. **pending 보존 항목 재확인(결정 불요)** — F0 slug 부여, NAN ㅁ 앞, PT 격음화
   제외, VH/HIA 질문 4·5·6, sidecar key namespace 등은 결정 기록대로 pending
   유지가 확인됐다. 지금 답할 필요 없음.

## 9. 재현 명령 (읽기 전용)

```powershell
& 'C:\Users\ari30\miniforge3\envs\mfa\python.exe' `
  'scripts/python/audit_stage2_gate0_common_contracts.py' --check-only
```

```powershell
& 'C:\Users\ari30\miniforge3\envs\mfa\python.exe' `
  'tests/test_audit_stage2_gate0_common_contracts.py' -v
```

주의: 본 보고서 2개 파일 생성 이후에는 첫 명령이 P2-1의 git allowlist 검사에서
의도적으로 exit 1이 된다(산출물 손상 아님). 이때는 `--skip-git-check`를 붙여
구조·SHA 검사만 재확인하거나, 채택 커밋 후 실행한다.

## 결론

Gate 0 공통 계약 구현은 handoff v2의 범위·allowlist·특수 규칙을 정확히 지켰고,
독립 실측(행수·ID·결속·수치 재집계·원문 재해시·manifest 재해시)이 Codex 감사와
전 항목 일치했다. **지금 고쳐야 하는 오류는 없다.** 산출물은 연구자 채택 전
후보 상태로 정지해 있으며, 다음 행동은 구현이 아니라 §8의 사용자 결정이다.
본 검토는 이 보고서 작성 외에 어떤 파일도 만들거나 수정하지 않았다.
