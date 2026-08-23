# EXTERNAL REVIEW: Stage 2 Gate 1 — NI(ㄴ삽입) 계약 후보 구현 독립 검토

- 작성: Claude Code (fable5, 독립 검토), 2026-08-23 KST
- 성격: **검토 보고서 — 구현 아님.** 구현 파일·config·definition·query·문헌
  워크스페이스·원자료·TextGrid·D: 자산을 수정하지 않았고, MFA·KOINA·wav2vec2를
  실행하지 않았으며, git add/commit/push를 하지 않았다. 계약을 frozen으로
  승격하지 않았다. 이 검토가 만든 파일은 본 MD와 동일 내용 HTML 두 개뿐이다.
- 검토 대상: Codex가 구현한 Gate 1 candidate 9종 — source registry, 계약 후보,
  환경 유형 7행, definition candidate, ‘요’ NOTE, 독립 감사기·테스트,
  AUDIT JSON·SHA manifest, 검증 로그 8종.
- 검증 방식: Codex 감사 스크립트와 **별도로 작성한 독립 파서·재해시·probe
  스크립트**(스크래치패드, 저장소 밖)로 정본을 직접 실측했고, 허용된 두 명령
  (`--check-only` 감사, 단위 테스트)을 지정된
  `C:\Users\ari30\miniforge3\envs\mfa\python.exe`로 재실행했다. **모든 감사
  명령은 본 보고서 파일 생성 전에 완료했다**(생성 후에는 감사기의 git
  allowlist 검사가 의도적으로 실패하게 되므로 — §2 P2-2). `--check-only` 없는
  감사 실행과 `--skip-git-check`는 사용하지 않았다. 대용량 CSV 전체 재해시·
  전수 스캔은 하지 않았다(경로·byte·선언 SHA 결속·헤더·기존 passed 감사만
  대조, 지시대로).

## 1. 최종 판정

> ## **GO_FREEZE_REVIEW**
>
> P0(차단 오류) 0건 · P1(frozen 검토 전 반드시 수정할 오류) 0건.
> **중대 발견사항 없음.** 독립 실측(보호 SHA 10종, 6개년 재집계, 35/34/73열
> 실측, match_evidence probe 재현, 문헌 362/156행·결속 0오류, manifest 8항목
> 재해시)이 Codex 감사와 전 항목 일치했고, 범위 일탈·기존 파일 변경·조용한
> 확정·신규 occurrence 파생을 발견하지 못했다.
>
> 단, GO_FREEZE_REVIEW는 “후보가 계약대로 만들어졌으니 연구자 동결 검토로
> 넘어가도 된다”는 뜻이다. 산출물은 여전히 candidate/draft이며, frozen 버전
> 생성 전에 **CLM-0015 확인 또는 명시적 유보**(§7)와 연구자의 환경 유형·계약
> 검토(§8)가 필요하다. 이 검토 자체는 어떤 것도 채택·동결하지 않았다.

## 2. P0 · P1 · P2 발견사항

### P0 (원자료·범위·zero-drop·query 무결성 차단 오류) — 없음

### P1 (frozen 검토 전 반드시 수정할 오류) — 없음

### P2 (선택적 개선·후속 회귀 보강 — 지금 고칠 필요 없음)

| ID | 내용 | 위치 | 구분 |
|---|---|---|---|
| P2-1 | **match_evidence 35-key probe가 감사기 밖 일회성 로그로만 존재한다.** 주 감사기는 34열 헤더에 `match_evidence_json` 열이 있는지까지 검사하고([audit_stage2_gate1_n_insertion_contracts.py:305-311](../../scripts/python/audit_stage2_gate1_n_insertion_contracts.py)), JSON 내부 35-key 검사는 별도 로그 08로 수행됐는데 그 probe 스크립트는 저장소에 보존되지 않았다(로그만 존재). **이 분리는 이번 Gate 1 합격에는 충분하다고 판정한다**(근거: ① 대상 CSV는 선언 SHA로 바이트 고정돼 있고 G3/G4 passed 감사에 이미 결속됨 — probe가 검사하는 성질은 입력이 바뀌지 않는 한 변할 수 없고, 입력 변경은 SHA 검사가 먼저 잡는다. ② 본 검토가 로그 08의 명세만으로 probe를 독립 재작성·재실행해 42,605행·35/35 key·key_set SHA까지 동일 재현했다 — §3.5). 다만 LLN 등 다음 현상에 이 구조를 재사용하거나 재기준선 후 회귀 검사를 돌릴 때를 위해, 감사기에 선택 `--probe` 옵션을 넣거나 probe를 단일 목적 스크립트로 커밋할 것을 제안한다 | logs/stage2_gate1_n_insertion_contracts_20260823/08_match_evidence_structural_probe.log | 후속 회귀 보강(P2) |
| P2-2 | **감사기 git allowlist·EXPECTED_INPUTS는 2026-08-23 스냅샷 고정이다**([:73-114](../../scripts/python/audit_stage2_gate1_n_insertion_contracts.py), [:24-35](../../scripts/python/audit_stage2_gate1_n_insertion_contracts.py)). 본 보고서 2개 파일이 `docs/reviews/incoming/`에 생긴 뒤의 `--check-only`는 git 검사에서 의도적으로 exit 1이 된다(정직한 fail-closed, 산출물 손상 아님). 구조만 재확인하려면 `--skip-git-check`, 정식 재검증은 채택 커밋 후 재기준선. Gate 0 채택 문서가 P2-1/P2-2를 “불변 스냅샷 검사기로 보존”으로 이미 정했으므로 같은 정책의 일관 적용이며 수정 불요 | [DECISION_stage2_gate0_common_contracts_adoption_20260823.md](../../docs/decisions/DECISION_stage2_gate0_common_contracts_adoption_20260823.md) §4 | 운영 주의 |
| P2-3 | Gate 1 신규 산출물(감사기·NOTE·definition candidate·config 3종)이 `scripts/SCRIPTS_INDEX.md`·`docs/decisions/_INDEX.md`에 미등재 — 두 색인의 현재 M 상태 diff를 실측한 결과 Gate 0 채택 시점 갱신만 있고 Gate 1 항목은 없다. allowlist가 기존 추적 파일 수정을 금지했으므로 **준수의 귀결**이다(Gate 0 P2-4와 동일 패턴). 채택 커밋 때 색인 2종 갱신을 같이 승인 | scripts/SCRIPTS_INDEX.md, docs/decisions/_INDEX.md | 수정 제안(채택 시) |
| P2-4 | `NI_ENV_INTER_EOJEOL`의 `environment_class=null` 관례가 Gate 0 enum에 명문화돼 있지 않다. enum은 4값만 선언하고 null 허용 여부를 말하지 않으며([stage2_environment_class_enum.v1.json:5-27](../../config/stage2_environment_class_enum.v1.json)), Gate 1 감사기가 “null이면 반드시 `pending`” 결합을 강제해([:417-418](../../scripts/python/audit_stage2_gate1_n_insertion_contracts.py)) 실질 안전장치는 있다. 사용자 지시(어절 간 = null + pending + deferred)에 부합하는 의도된 설계이므로 지금 고칠 것은 없고, Gate 0 P2-6 어휘 통일 때 다음 enum 버전에 null 관례를 같이 명문화할 것을 제안 | [n_insertion_environment_types_candidate_v1_20260823.jsonl:6](../../config/environment_types/n_insertion_environment_types_candidate_v1_20260823.jsonl) | 수정 제안(선택) |

## 3. 독립 실측

### 3.1 허용 명령 재실행 (보고서 작성 전 완료)

| 명령 (mfa python) | 결과 |
|---|---|
| `audit_stage2_gate1_n_insertion_contracts.py --check-only` | exit 0, `passed=true`, `status=passed_candidate_pending_researcher_confirmation`. 941,903/353,626/588,277, 35/34/73열, 환경 7행·occurrence 배정 0·researcher_confirmed 0, query 조건 mismatch 0, 문헌 362/156·결속 0, worktree unexpected 0 — Codex 저장 AUDIT와 동일 값 재현 |
| `tests/test_audit_stage2_gate1_n_insertion_contracts.py -v` | exit 0, **7/7 OK** (성공·registry 필드 누락 실패·manifest SHA 불일치 실패·존재하지 않는 CLM 실패·human check 조용한 확정 실패·기존 출력 FileExistsError·manifest 자기 제외) |
| `-m py_compile` (감사기+테스트) | exit 0 (`__pycache__/`는 .gitignore:10으로 무시되어 worktree 오염 없음) |

존재하지 않는 CLM 실패 테스트가 실제로 있으므로 Gate 0 검토의 P2-3(테스트 추가
요청)은 **이행 확인**됐다([tests/test_audit_stage2_gate1_n_insertion_contracts.py:49-54](../../tests/test_audit_stage2_gate1_n_insertion_contracts.py)).

### 3.2 보호 입력 SHA-256 — 10/10 일치

| 파일 | 독립 재계산 결과 |
|---|---|
| config/target_queries/n_insertion_production_v1_20260818.json | `744bd8cb…3ab6` — 요청 기준값·registry·계약 참조와 일치 |
| config/join_contracts/n_insertion_variable_join_contract_v1_20260818.json | `12d81163…4050` — 요청 기준값과 일치 |
| phenomena/34_n_insertion/definition.md | `aa23b940…3513` — 요청 기준값과 일치(기존 definition 무변경) |
| config/phenomena_registry.v1.json, stage2_environment_class_enum.v1.json, stage2_inclusion_exclusion_confound_contract_template.v1.json | 감사기 pin과 일치(Gate 0 채택본 무변경) |
| docs/decisions/DECISION_…adoption_20260823.md, PLAN_…gate1_NI…20260823.md | 감사기 pin과 일치 |
| work/…/01_inventory/SOURCE_INVENTORY.jsonl, 02_claims/CLAIM_EVIDENCE.jsonl | `e8de6907…0680`, `1e88f551…610a` — Gate 0 기준값과 일치(문헌 정본 무변경) |

기존 G1~G4 산출물(6개년 후보·joined 디렉터리, AUDIT_stage2_g*)도 파일 구성
실측에서 신규·삭제·개명 0건이었고, manifest 선언 SHA 결속이 전부 일치했다.

### 3.3 6개년 행 수 — manifest·감사 JSON에서 독립 재집계

registry 값이 아니라 연도별 `TARGET_MANIFEST_BUILD.json`·`JOIN_MANIFEST.json`·
`AUDIT_stage2_g*.json`(각각 독립 재해시 후 파싱)에서 다시 세었다.

| 연도 | 후보 | 어절 내부 | 어절 간 | 고유 발화 | joined | 등식¹ |
|---:|---:|---:|---:|---:|---:|---|
| 2020 | 101,638 | 42,604 | 59,034 | 93,360 | 101,638 | 성립 |
| 2021 | 206,037 | 81,865 | 124,172 | 184,328 | 206,037 | 성립 |
| 2022 | 141,966 | 53,759 | 88,207 | 127,107 | 141,966 | 성립 |
| 2023 | 123,381 | 45,570 | 77,811 | 108,785 | 123,381 | 성립 |
| 2024 | 185,401 | 65,109 | 120,292 | 157,565 | 185,401 | 성립 |
| 2025 | 183,480 | 64,719 | 118,761 | 150,459 | 183,480 | 성립 |
| **합계** | **941,903** | **353,626** | **588,277** | **821,604** | **941,903** | 6/6 |

¹ `build candidate_rows = join rows_in = join rows_out = audit joined_rows`
(+ 감사 JSON `counts.candidate_rows`·`per_query`까지 동일). 어절 내부+간 =
후보 합도 6개년 모두 성립. 연도별 join `safety.rows_dropped=0`,
`realization_judged=false`, build `realization_judgement_performed=false`,
감사 `failures=[]`·`passed` 전부 실측 확인.

추가 실측(감사기가 검사하지 않는 축): registry의 연도별 `curated_rows`(합 6)·
`sino_internal_candidate`(합 1,210)·`etym_unknown`(합 700,908)도 각 연도 build
counts·join `status_counts`·감사 `distributions`와 전부 일치했다.

### 3.4 실제 헤더 — 35/34/73

| 파일 | 실측 열 수 | 정규화 헤더 SHA | 6개년 동일성 |
|---|---:|---|---|
| 2020 원천 `morph_boundaries.csv.gz` (D:) | **35** | `9a9899f5…39a1` — registry 계약과 일치 | (2020 원천만 계약 대상) |
| `TARGET_CANDIDATES.csv` | **34** | `7c2e32dd…0cad9` | 6개년 모두 동일(고유 SHA 1개) |
| `CANDIDATES_WITH_VARIABLES.csv` | **73** | `e3e5cff0…38f8` | 6개년 모두 동일(고유 SHA 1개) |

`required_occurrence_fields` 6종(`year, utt_id, target_occurrence_id,
occurrence_index, query_id, match_evidence_json`)은 34열 후보 헤더에 전부
존재했고(감사기 검사 범위), 추가 실측으로 **73열 joined 헤더에도 6개년 모두
존재**함을 확인했다. 형태·경계 35열이 상위 열이 아니라
`match_evidence_json` 안에 있다는 설계는 실제 파일과 일치한다(§3.5).

### 3.5 match_evidence_json 독립 probe — Codex 로그 08 완전 재현

로그 08을 참조하지 않은 독립 구현으로 2020 `TARGET_CANDIDATES.csv`를 상한
200,000행으로 읽고 QN1·QN2를 모두 만나는 즉시 중단했다.

| 항목 | 실측 |
|---|---|
| 중단 행 | **42,605행** — Codex 로그 08의 42,605와 동일 |
| QN1/QN2 `match_evidence_json` 파싱 | 둘 다 유효 JSON |
| key 수·집합 | 각 35개, **원천 morph_boundaries 35 header key 집합과 정확히 동일** |
| 값 형 | 전부 문자열 |
| 상위 열 `year·utt_id·target_occurrence_id·occurrence_index` | 존재 |
| key_set_sha256 | 정렬 정규화 기준 `2f29f866…38b8` — **Codex 로그 08 값과 일치**(즉 로그 08의 해시는 sorted-key 정규화임을 역확인) |
| 원문 값·발화 내용 | 보고서·로그에 복사하지 않음 |

### 3.6 문헌 362/156행과 결속

- SOURCE_INVENTORY: **362행**, 공백행 0, `SRC-001`~`SRC-362` 연속.
- CLAIM_EVIDENCE: **156행**, 공백행 0, `CLM-0001`~`CLM-0156` 연속.
- CLM→SRC 결속(`source_id`·`source_file`·`source_sha256` 3중 대조): **오류 0건**.
- `needs_human_check=true`: 정확히 **CLM-0008·0015·0026·0145·0151** 5건.
  CLM-0015의 플래그는 정본에 그대로 남아 있다(조용한 해제·확정 없음).
- Gate 1 산출물 전체(계약 JSON·환경 JSONL의 구조적 `evidence_refs` + definition·
  NOTE MD 본문의 CLM/SRC 언급 정규식 수집)에서 참조된 모든 ID가 정본에
  실재하며, **HIA 유보 대상 CLM-0145·0151의 사용은 0건**이다.
- 참조 정합성 표본: NOTE의 근거 CLM-0002는 SRC-297(오미라 2006), 한자어
  환경의 CLM-0015는 SRC-287(안미진 2008)에 결속 — 현상종합 초안의 서지와 일치.

### 3.7 감사 산출물·manifest 재해시 — Codex 보고값과 일치

| 항목 | 독립 재계산 |
|---|---|
| AUDIT JSON SHA-256 | `f08dfe99ad94bc47a66ac3302c3c483a810946e20551441c81291425228ad15e` — Codex 보고값과 일치 |
| SHA manifest SHA-256 | `ea7e160f9cea3be1db6487e87bab33d65dc5c2778906cfacaf59c6101deb25d5` — Codex 보고값과 일치 |
| manifest 항목 | **8항목**(신규 산출물 7종 + AUDIT JSON) 전부 독립 재해시 일치, **manifest 자기 자신 미포함** |
| AUDIT 내부 `artifact_sha256` 7종 | 실측 재해시와 전부 일치 |
| Gate 1 대응 `.partial` 잔존 | 0건. 출력 폴더에 AUDIT·manifest 외 파일 없음 |
| Codex 검증 로그 8종(01~08) | 전부 통독 — py_compile·7/7 테스트·check-only·최초 생성·기존 출력 거부(의도된 exit 1)·최종 재해시·사후 check-only·probe가 모두 주장과 일치, 본 검토 실측과도 일치 |

## 4. query–계약 대조표

동결 query([n_insertion_production_v1_20260818.json](../../config/target_queries/n_insertion_production_v1_20260818.json))의
QN1(:21-33)·QN2(:44-56) 조건을 직접 읽고, 계약
([n_insertion_contract_candidate_v1_20260823.json:18-33](../../config/phenomenon_contracts/n_insertion_contract_candidate_v1_20260823.json))의
scope + 공통 6조건으로 재구성해 대조했다. 감사기는 조건 리스트의 **완전
동일성**(`[scope, *공통6] == query conditions`, [:368-373](../../scripts/python/audit_stage2_gate1_n_insertion_contracts.py))을
검사하며, 독립 재구성에서도 **mismatch 0**이었다.

| # | 동결 query 실측 조건 | 계약 후보 | 판정 |
|---|---|---|---|
| 1 | `boundary_scope`: QN1=`intra_eojeol`, QN2=`inter_eojeol` | scope_conditions 동일 | 일치 |
| 2 | `left_unit_type = hangul` | 공통 조건 1 | 일치 |
| 3 | `right_unit_type = hangul` | 공통 조건 2 | 일치(숫자·기호 인접 제외는 이 두 조건의 귀결 — NI_EXC_02 서술과 부합) |
| 4 | `left_coda_jamo nonempty` | 공통 조건 3 | 일치 |
| 5 | `right_onset_zero truthy` | 공통 조건 4 | 일치 |
| 6 | `right_nucleus_jamo ∈ {ㅣ,ㅑ,ㅕ,ㅛ,ㅠ,ㅖ,ㅒ}` | 공통 조건 5 — 동일 7원소, **ㅢ 없음**(NI_EXC_03과 부합) | 일치 |
| 7 | `right_pos regex ^(?!J\|E)` | 공통 조건 6 — 패턴 문자열 동일(NI_EXC_01과 부합; ‘요’/JX는 별도 탐색 후보로만 기록) | 일치 |

- **왼쪽 POS 필터**: query에 없음 — 계약도 `left_pos_filter: null`,
  `new_occurrence_filter_added: false`(:30-32). **몰래 추가된 occurrence 필터
  없음.**
- **의미번호 불확실성·etym_unknown·join 상태**: 계약 retention_rules
  NI_RET_01/02(:83-96)가 “제외 조건이 아니라 상태 보존”으로 명시 — 제외
  조건 3종(:60-82)은 위 query 조건의 거울일 뿐 새 제외가 없다.
- include 4·exclude 3·confound 5·membership 3·unresolved 5 — 전부 candidate/
  pending 상태이며 `contract_status=draft`, `researcher=null`,
  `confirmed_at=null`, safety 5항목 전부 false(:164-170).

## 5. 환경 유형 7행 검토표

[n_insertion_environment_types_candidate_v1_20260823.jsonl](../../config/environment_types/n_insertion_environment_types_candidate_v1_20260823.jsonl)
(행 번호 = 파일 줄 번호). 전 행 `occurrence_assignment_status=not_started`
(**occurrence 배정 0행**), `researcher_confirmed` **0행**, 근거 없는 행은
`pending` — 전부 실측 확인. 분류값은 Gate 0 enum 4값 안에 있다(어절 간 null은
P2-4 참조).

| 행 | ID | 분류 | class_status | priority | 근거 | 검토 소견 |
|---|---|---|---|---|---|---|
| 1 | NI_ENV_CORE_C_J | `general_direct` | seeded | **core** | CLM-0001·0004·0014·0023 | /j/ 핵심 환경 — PLAN §4 seed와 동일, 근거 4건 전부 실재 |
| 2 | NI_ENV_CORE_C_I | `peripheral_reported` | seeded | **secondary** | CLM-0003·0014 | /i/ 분리 집계 — /j/>/i/ 비대칭 문헌과 부합 |
| 3 | NI_ENV_SINO_RESONANT_J | `peripheral_reported` | **pending** | secondary | CLM-0004·0015 | pending_reason: “CLM-0015 needs_human_check before contract freeze” — 조용한 승격 없음 |
| 4 | NI_ENV_SINO_OBSTRUENT_J | `peripheral_reported` | **pending** | secondary_comparator | CLM-0004·0015 | 비실현 비교군을 후보에서 삭제하지 않음(설명문 명시), 동일 pending 사유 |
| 5 | NI_ENV_YO_JX | `theoretical_underreported` | seeded | exploratory_separate | CLM-0002 | **[별도] ‘요’**: `decision_status=treatment_decided_query_not_created` — 처리 방침 결정 완료·query 미생성. 재결정 요청 아님 |
| 6 | NI_ENV_INTER_EOJEOL | **null** | **pending** | deferred_review | SRC-360·362 | **[별도] 어절 간**: 모집단 보존 + 실제 문맥·운율·청취 검토는 후속 Gate로 미룸(결정대로). pending_reason 명시 |
| 7 | NI_ENV_UNCLEAR_BOUNDARY | `unclear_boundary` | **pending** | deferred_review | (없음) | 근거 없는 행 → pending 규칙 준수, “삭제하지 않고 보존” 명시 |

- 감사기 강제 사항 실측: 7 ID 정확·순서 일치, enum 필수 8필드 전 행 존재,
  존재하지 않는 SRC/CLM 참조 0, `researcher_confirmed` 등장 시 실패
  ([:435](../../scripts/python/audit_stage2_gate1_n_insertion_contracts.py), 테스트 5번이 실제로 검증).
- 분류·priority는 PLAN §4의 seed 제안과 1:1로 일치하며, 어느 행도 연구자
  확정으로 표시되지 않았다. **행 5·6의 최종 분류명 확정은 연구자 검토
  몫으로 남아 있다(§8).**

## 6. Codex 감사와 독립 검사 결과의 차이

**수치·판정 차이 0건.** 행 수·헤더·SHA·probe 중단 행(42,605)·환경 7행 통계·
문헌 5건 human check까지 전부 동일하게 재현됐다.

독립 검사가 Codex 감사보다 **더 깊이 본 부분**(모두 통과):

1. registry의 `curated_rows`·`sino_internal_candidate`·`etym_unknown` 연도별
   값을 build counts·join status_counts·감사 distributions와 3중 대조(감사기는
   이 세 축을 검사하지 않음).
2. `required_occurrence_fields`의 **73열 joined 헤더** 포함 여부(감사기는
   34열 후보 헤더만 검사).
3. AUDIT JSON 내부 `artifact_sha256` 7종의 재해시 대조와 manifest 8항목
   완전 재해시.
4. definition·NOTE 산문의 CLM/SRC 언급 전수 수집으로 HIA CLM-0145·0151
   오용 0건 확인(감사기 `validate_refs`는 구조적 `evidence_refs`만 수집).
5. 색인 2종 M 상태의 diff 실측 — Gate 0 채택 시점 갱신만 있고 Gate 1의 추적
   파일 수정 0건(§2 P2-3).
6. probe의 완전 독립 재구현(§3.5) — key_set 해시의 정규화 방식까지 역확인.

관찰 1건(조치 불요): 저장된 AUDIT JSON의 `worktree.status_lines`에
`?? outputs/pilots/stage2_gate1_…` 줄이 없다 — 감사가 출력을 쓰기 **전** 실측한
스냅샷이라 정상이며(Gate 0 P2-7과 동일 패턴), 로그 07과 본 검토의 사후
`--check-only`가 outputs 포함 상태로 통과함을 확인했다.

## 7. frozen 전 실제 차단 항목

**CLM-0015 하나뿐이다.** 그 외 차단 항목은 발견되지 않았고, 억지로 만들지
않는다.

- 내용: 한자어 2음절 공명음/장애음 말음 비대칭(안미진 2008, SRC-287) —
  `NI_ENV_SINO_RESONANT_J`·`NI_ENV_SINO_OBSTRUENT_J` 두 환경 유형과 계약
  confound `SINO_COMPOUND_BOUNDARY`의 근거.
- 현재 상태: 정본 `needs_human_check=true` 보존, 환경 2행 `pending`, 계약
  `NI_UNR_001`이 **`needs_human_check_before_freeze`로 스스로 동결을 막고
  있다**([계약:155](../../config/phenomenon_contracts/n_insertion_contract_candidate_v1_20260823.json)).
  즉 이것은 구현 오류가 아니라 계약이 설계대로 요구하는 연구자 절차다.
- 처리: frozen 버전 생성 전에 CLM-0015 원문 확인 결과를 기록하거나, 한자어
  두 환경을 명시적 유보 상태로 두는 결정을 채택 문서에 남긴다. CLM-0008·
  0026은 `non_blocking_pending`으로 보존돼 있어 차단이 아니다(계약
  NI_UNR_002/003 실측 확인).

## 8. 지금 연구자가 결정할 것

‘요’ 처리 방침(결정 완료)과 어절 간 실제 검토 시점(후속 Gate로 확정)은
재질문하지 않는다. 정말 필요한 새 결정은 다음뿐이다.

1. **Gate 1 후보 채택·동결 여부** — 계약 후보, 환경 유형 7행(특히 행 1~4의
   분류·priority가 연구 의도와 맞는지), definition candidate를 검토하고
   frozen 버전 생성을 승인할지. 승인 시 §7의 CLM-0015 확인/유보 기록이
   선행돼야 하며, 같은 채택 커밋에서 색인 2종 갱신(P2-3)과 감사 재기준선
   정책(P2-2)을 함께 처리하는 것을 권고한다.
2. **(선택) probe 회귀 보강 방식(P2-1)** — LLN 등 다음 현상에 Gate 1 구조를
   재사용하기 전에, 감사기 `--probe` 옵션 추가와 단일 목적 스크립트 커밋 중
   택일. 지금 결정하지 않아도 이번 채택을 막지 않는다.

## 9. 수정 제안과 지금 반드시 고칠 오류의 구분

- **지금 반드시 고칠 오류: 없음.** P0·P1 0건이며, 구현 파일을 하나도 고치지
  않고 그대로 연구자 동결 검토에 올릴 수 있다.
- **수정 제안(전부 P2, 채택 시점 이후 처리 가능)**: P2-1 probe 코드
  보존(후속 회귀 보강), P2-2 재기준선 정책 확인(운영 주의, Gate 0 정책의
  일관 적용), P2-3 색인 2종 갱신(채택 커밋), P2-4 enum null 관례
  명문화(다음 enum 버전).

## 재현 명령 (읽기 전용)

```powershell
& 'C:\Users\ari30\miniforge3\envs\mfa\python.exe' `
  'scripts/python/audit_stage2_gate1_n_insertion_contracts.py' --check-only
```

```powershell
& 'C:\Users\ari30\miniforge3\envs\mfa\python.exe' `
  'tests/test_audit_stage2_gate1_n_insertion_contracts.py' -v
```

주의: 본 보고서 2개 파일 생성 이후에는 첫 명령이 git allowlist 검사에서
의도적으로 exit 1이 된다(§2 P2-2, 산출물 손상 아님). 이때는
`--skip-git-check`로 구조·SHA 검사만 재확인하거나 채택 커밋 후 실행한다.
본 검토의 모든 감사 명령은 보고서 생성 전에 완료했고 `--skip-git-check`는
사용하지 않았다.

## 결론

Gate 1 NI 구현은 PLAN §7의 신규 파일 범위에 정확히 머물렀고, 941,903행
zero-drop 회계·동결 query 거울 계약·환경 유형 7행·‘요’ 분리·문헌 결속이
독립 실측과 전 항목 일치했다. 기존 query·join 계약·definition·G1~G4 후보·
문헌 정본은 SHA로 무변경이 입증됐다. **지금 고칠 오류는 없다.** 다음 행동은
구현이 아니라 §7~§8의 연구자 동결 검토다. 본 검토는 이 보고서 MD·HTML 두
파일 외에 어떤 파일도 만들거나 수정하지 않았다.
