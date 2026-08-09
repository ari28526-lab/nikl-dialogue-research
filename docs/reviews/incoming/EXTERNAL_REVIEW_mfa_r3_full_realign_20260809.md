# 외부 검토 보고서 — 공통발음 r3 2020–2025 전수 재정렬 workflow

- 날짜: 2026-08-09 KST
- 검토 대상: branch `agent/harden-pre-bulk-pipelines`, commit `abd8d45`
- 검토자: 외부 도구 (읽기 전용 검토; 코드·D: 자료·release Gate 무변경)
- 검토 방법: 지정 문서 9종 정독 후, runner·validator·alignment contract·
  TextGrid/CSV exporter·독립 감사기·PowerShell 5.1 테스트를 실제 코드
  행 수준으로 대조. Stage 19–21 산출물과 감사 보고서(D: manifest 포함)의
  수량·SHA 회계를 재검산.

## 0. 총평

정책 층위는 견고하다. 6개년 동일 r3 계약·r2 interval 비재사용·follow-up
exact-ID 보존·fail-closed release Gate라는 골격은 방법론적으로 옳고, Stage
19–21 산출물의 수량 회계(5,103,356 = 4,384,992 + 718,364, 연도별 합계,
어절 회계 27,847,068 = 27,043,261 + 803,644 + 163)는 코드와 감사 보고서에서
모두 일치함을 재확인했다.

그러나 **현재 코드 기준으로 r3를 시작하면 안 되는 이유도 그대로 확인됐다.**
기존 r2 코드는 이름만 바꿔 재사용할 수 없도록 여러 겹으로 fail-closed로
잠겨 있으나(이는 유지할 강점), 반대로 r3 구현이 물려받으면 안 되는 함정
— 연도 단위로만 구분되는 DB·marker 이름공간, 발음 release identity가
불완전한 alignment contract, safe-body ID 목록의 미실물화, r3 필수 manifest
필드의 전면 부재 — 이 코드에 실재한다. 아래 Critical 2건과 High 6건이
2020 실행 전 반드시 해소돼야 한다.

심각도 분포: **Critical 2, High 6, Medium 9, Low 3.**

## 1. 유지할 점 (바꾸지 말 것)

1. **fail-closed release Gate.** `validate_mfa_r2_adoption.py:45-69`는
   `status == "adopted"` **그리고** `allowed_release_ids` 멤버십을 요구한다.
   현재 `allowed_release_ids: []`이므로 r2든 미지의 r3 ID든 모두 차단된다.
   blocklist가 아니라 allowlist+status로 잠근 설계는 그대로 유지할 것.
2. **checkpoint 보존 규율.** `run_eojeol_realign.ps1:2010-2026, 2412-2435`의
   `--clean` 가드(최초 실행 또는 명시적 `-AllowFullCleanRetry`에서만),
   `Archive-StaleTemp`의 이동-후-보존(1416-1445), 실패 시 temp·DB 보존은
   전 경로에서 확인됐다. `done` marker·input/alignment contract를 삭제하는
   코드는 `scripts\*.ps1` 어디에도 없다.
3. **heartbeat 비간섭 계약.** 쓰기(`Write-JsonLine`, 1491-1527: FileStream
   Append + `FileShare.ReadWrite`, 10회 재시도, 실패해도 MFA 비중단)와
   읽기(962-967, 1183-1187: `FileShare.ReadWrite|Delete` 공유 읽기)가 모두
   AGENTS.md 규칙대로 구현돼 있고 동적 시험(test_powershell_safety.ps1:
   1342-1378)이 경합 시나리오를 실제로 검증한다.
4. **lock의 PID 생존 검사 + stale archive**(삭제가 아니라
   `locks\archive_stale\`로 이동), 교차 파이프라인 lock 스캔
   (`run_eojeol_realign.ps1:305-347` ↔ `run_common_pron_*` 양방향).
5. **Stage 19 blocked 목록의 byte 단위 독립 감사**
   (`audit_common_pron_r3_pre_adoption_routing.py:159-174`): 17,156개 CSV를
   재스캔해 blocked 행을 스트림 순서까지 대조한다. 이 감사 패턴은 r3 연도
   입력 계약 감사의 본보기로 재사용할 것.
6. **후보≠선택 분리.** Stage 20 사전의 NOT_ADOPTED 표시가 파일명·manifest
   scope·행 단위 열·정책 gate 4중으로 걸려 있고(`build_common_pron_r3_safe_
   body_candidate.py:27,134,182-184,207-215`), 감사가 사전을 projection과
   행 단위로 재대조한다.
7. **승인의 명시성.** 자동 승인 0, 승인 문장·행 수·identity 검증, 원 pending
   byte-exact 보존 패턴(approve/materialize 계열)은 r3에서도 그대로 쓸 것.
8. **어절 부분 삭제 금지·발화 단위 라우팅**(Stage 19), follow-up의
   exact-ID·사유 보존. 방법론적으로 올바른 결정이다.

## 2. Critical

### C1. r2 DB·marker 이름공간을 r3가 물려받으면 r2 interval이 r3로 수출될 수 있다

**근거:**
- `run_eojeol_realign.ps1:2438` — DB 경로가 `D:\mfa_tmp\<year>\<year>.db`로
  **연도 단위**다. release·queue 차원이 없다. 보존 중인 r2 DB
  `D:\mfa_tmp\2020\2020.db`, `2021.db`, `2022.db`가 정확히 이 자리에 있다.
- `run_eojeol_realign.ps1:1368,1726,2643` — done marker가
  `done\<year>.direct_db_ready` 등 연도 단위이고, `export_mode =
  'direct_db_research_6tier_v1'`로 r2 당시와 같은 schema ID를 쓴다.
- `run_eojeol_realign.ps1:2010` — `-UseDirectDbExport`이고 `direct_db_ready`
  marker가 유효하면 **MFA 정렬을 완전히 건너뛰고** 보존 DB에서 export만
  수행한다.
- `run_mfa_year_queue_safe.ps1:114-139` — `Set-YearStateFromDirectDbCheckpoint`
  는 marker의 `stage`·`computation_complete`·DB 존재만 보고 **release ID·
  발음 mode·현재 alignment contract를 비교하지 않은 채** marker의 contract
  ID들을 queue 상태로 복사한다.
- 완화 장치: `run_eojeol_realign.ps1:1734-1742`의 `Read-DoneMarker` 대조는
  contract ID 불일치 시 exit 1로 막는다(fail-closed). 그러나 이 방어는
  alignment_contract_id가 r2/r3에서 반드시 달라진다는 가정에 의존하는데,
  그 가정이 C2·H2에서 보듯 구조적으로 보장되지 않는다.

**연구방법론 영향:** 승인 정책의 핵심 금지사항("r2 interval을 최종 r3에
재사용하지 않는다")이 코드 경로 하나로 위반될 수 있다. 위반이 일어나면
6개년 동일 계약 주장 전체가 무효가 된다.

**데이터 무결성 영향:** r3 산출물에 r2 시간값이 섞여도 TextGrid 자체에는
계약 ID가 없으므로(H3) 사후 판별이 어렵다.

**수정안:**
1. r3 전용 runner는 **모든** 경로에 release ID를 넣는다:
   `D:\mfa_r3\<release_id>\tmp\<year>\<year>.db`,
   `done\<release_id>.<year>.direct_db_ready`,
   `input_contracts\<release_id>.<year>.json`. workflow Y04가 이미 요구하는
   사항이며, 기존 `config/paths.json`의 `mfa_state`/`mfa_temp_*` 평면 키를
   r3에서 그대로 참조하지 않는다.
2. marker 신뢰 로직(신규 queue runner)은 `stage` 외에 `release_id`,
   `pronunciation_release_id`, `alignment_contract_id` 3중 일치를 요구하고,
   불일치 시 재정렬이 아니라 **정지+보고**한다(자동 삭제 금지 유지).
3. r3 preflight에 "r3 이름공간 안에 r2 유래 marker/DB 없음" 검사를 추가한다.

### C2. v3 draft 계약이 승인된 단계적 채택과 모순 — 이대로면 adoption Gate가 열릴 수 없다

**근거:**
- `config/common_pronunciation_resource_contract_v3_draft.json:54` —
  `selected_phone_coverage_required_before_adoption: 881237`. 그러나
  연구자가 승인한 것은 candidate 795,804형만으로의 safe-body 단계적
  채택이고, zero-fallback hold 85,398형·policy 35형은 의도적으로 follow-up에
  남는다(`AUDIT_common_pron_r3_adoption_readiness_20260808.json` gates
  `full_final_selected_phone_coverage`·`explicit_policy_decisions` 실패가
  정상 상태).
- 같은 파일 `variant_policy.candidate_is_not_selection: true`와
  `canonical_type_table`의 `selection_*` 열 요구 — Stage 20 사전은 전 행이
  `candidate_only=true, final_selection=false`다
  (`build_common_pron_r3_safe_body_candidate.py:182-184`). 즉 현재 자료
  상태로는 "selected" 열 기준 coverage가 0이다.

**연구방법론 영향:** 계약을 문자 그대로 구현하면 생산이 영원히 차단되고,
현실적으로는 구현자가 계약을 비공식적으로 우회("candidate를 selection으로
간주")할 유인이 생긴다. 후자는 candidate≠selection 원칙의 붕괴다.

**데이터 무결성 영향:** 직접 영향은 없으나, 우회가 일어나면 어떤 phone이
"명시적 선택"인지의 provenance가 소실된다.

**수정안:** draft를 v3.1 "staged adoption amendment"로 개정한 뒤 승격한다.
1. selection의 정의를 명시: "safe-body LAB에서 실제 사용되는 token(795,804형)
   에 한해 candidate 변이를 명시적 절차로 selected로 승격한다. hold·policy
   형은 selected 대상이 아니며 해당 발화는 follow-up에 있다."
2. `selected_phone_coverage_required_before_adoption`를 "safe-body 사용 token
   전수(= Stage 20 후보 사전과 byte 동일 projection)"로 재정의하고, 881,237
   전수 coverage는 후속 full-corpus release의 Gate로 이관한다.
3. 이 개정은 승인 범위 자체의 변경이 아니라 승인 범위의 계약화이므로 새
   연구자 승인이 아니라 개정 사유 기록으로 충분하다(단, M3의 승인 재작성
   문제를 먼저 고칠 것).

## 3. High

### H1. safe-body 4,384,992의 ID 목록이 실물로 존재하지 않는다

**근거:** `build_common_pron_r3_pre_adoption_routing.py:333-336` — safe 발화는
`continue`로 건너뛰고 blocked 행만 기록한다(:350-365). Stage 19 출력 폴더에
safe ID 목록 파일이 없음을 확인했다. 연도별 수치는 manifest가 아니라
`year_routing_summary.csv`에만 있고, 승인 계약
(`build_common_pron_r3_staged_approval.py:128-142,168-175`)은 blocked 목록
SHA도, safe 목록 SHA도 직접 결속하지 않는다(감사 보고서 JSON만 결속).
`source = safe + follow-up, 교집합 0`을 **ID 수준**에서 검사하는 코드는 없고
`audit_mfa_r3_full_realign_policy.py:44-61`이 config의 정적 정수만 대조한다.

**연구방법론 영향:** workflow Y01의 "Stage 19 blocked 집합을 빼서 safe ID
목록을 만든다"가 유일한 유도 경로인데, 유도 결과를 고정·감사할 기준물이
없으면 연도 입력 계약마다 분모가 재유도되고 검증 불가가 된다.

**데이터 무결성 영향:** 라우팅 감사(byte 대조)는 통과했으므로 현재 자료는
건전하다. 위험은 미래의 유도 불일치다.

**수정안:** Y01 연도 입력 계약 builder가 (a) 동결 search master fingerprint와
`blocked_utterance_routing.csv.gz` SHA(`59f9d03f…`)를 입력으로 명시, (b)
연도별 safe ID 목록을 실물 CSV(.gz)로 물질화하고 SHA 기록, (c)
`|safe| + |blocked| = |source|`, `safe ∩ blocked = ∅`, unknown 0을 ID 수준에서
재검사, (d) 연도별 수량이 `year_routing_summary.csv`와 일치함을 확인한다.
독립 감사기는 blocked 감사와 같은 방식으로 재유도-대조한다.

### H2. alignment_contract_id에 발음 release identity가 불완전하게 들어간다

**근거:** `build_mfa_alignment_contract.py:326-378` identity 구성 요소 중
발음 관련은 adoption 계약 파일 SHA(:343-349)와
`models["dictionary"]["sha256"]`뿐이다. `pronunciation_mode`는 release
비구분 리터럴 `"common_pronunciation"`(:338-342)이고, release manifest
SHA는 감사 본문에만 기록되며 identity 밖이다(:386-392). release ID는
`--dictionary-model-name`을 통해서만 간접 유입되는데 기본값이
`"korean_mfa"`(:185-187)라 호출자가 빠뜨리면 identity에서 release 이름이
사라진다. 또한 r2 전용 hard gate — release ID `common_pron_mfa_r2_` 접두
강제(:249-253), `g2p_jamo_ls_rewrite_words != 4` 같은 r2 release 고유 상수
(:254-257) — 가 identity 계산 앞단에 있다.

**연구방법론 영향:** "연도마다 하나의 동결 alignment contract ID"(Y04)가
6개년 방법론 동일성의 증명 수단인데, ID가 발음 계약을 완전히 pin하지
않으면 증명력이 약해진다.

**데이터 무결성 영향:** contract ID가 우연히 r2와 충돌하면
`write_alignment_contract_if_changed`(:118-141)가 기존 r2 계약 파일을
무변경 보존하고, 모든 marker 대조가 r2 marker와 일치해 버린다(C1과 결합
시 최악 경로).

**수정안:** r3 전용 `build_mfa_r3_alignment_contract.py`(새 schema
`mfa_alignment_contract.v2` 또는 `r3.v1`)를 만들고 identity에
`pronunciation_release_id`, release manifest SHA, adoption 계약 SHA,
`safe_body_routing_contract_id`(Stage 19 manifest SHA), 사전 SHA를 명시
포함한다. r2 접두 검사·magic 4 같은 release 고유 상수는 r3 계약 파일에서
데이터로 받는다(코드 상수 금지).

### H3. exporter·독립 감사가 r3 필수 manifest 필드와 검사를 갖고 있지 않다

**근거:** v3 draft `textgrid_materialization_gate.required_manifest_fields`
10종 중 현재 `export_mfa_db_research_6tier.py`가 기록하는 것은
`alignment_contract_id` 하나뿐이다(companion manifest :1178-1216, export
보고서 :1939-2010). `pronunciation_release_id`, `pronunciation_contract_id`,
`mfa_dictionary_sha256`(명명 필드), `source_db_sha256`(DB는 경로 문자열만,
:1950), `alignment_origin`, `r3_full_realign`, `safe_body_routing_contract_id`,
`followup_inventory_sha256` 전부 부재. 독립 감사
`audit_mfa_research_6tier_year.py`는 tier 구조·연속성·spn·inventory·표
SHA를 훌륭히 재검하지만(:56-121, :354-385) **`phoneme_r_auto`가
`phones_mfa`의 결정론적 함수임을 label 수준에서 검증하지 않고**(경계만
비교, :97-102) 동반표의 `alignment_contract_id` 열 값도 행 수준으로 읽지
않는다(:124-184). `preflight_next_year_after_research_qc.py`에는 사전
SHA·release ID·routing 계약 검사가 전혀 없다.

**연구방법론 영향:** draft의 adoption_gates 중 "phoneme_r_auto 결정론적
재생성·검증", "모든 산출물이 같은 r3 contract ID·사전 SHA를 pin" 두 조항이
현재 검사 체계로는 증명되지 않는다.

**데이터 무결성 영향:** r2/r3 산출물이 파일 시스템에서 섞였을 때 manifest
만으로 계보를 판별할 수 없다.

**수정안:** exporter에 위 10필드 기록(+DB SHA256 계산)을 추가하고, 독립
감사에 (a) `phone_class` 매핑을 실제 적용한 `phoneme_r_auto` label 전수
재계산 대조, (b) 동반표 contract ID 열의 전수(또는 스트림) 값 검사, (c)
manifest 10필드 존재·값 일치 검사를 추가한다. 차기 연도 preflight r3판은
사전 SHA와 `safe_body_routing_contract_id` 일치를 gate에 포함한다.

### H4. "정렬 가능성 교집합"이 전면 미구현이고, 우변 피연산자 선택에 함정이 있다

**근거:** `pron_safe_body`·`year_input_contract`·
`safe_body_corpus_materialization`의 구현 스크립트는 저장소에 없다(grep
전수 확인; `run_mfa_r3_year_safe_body.ps1` 부재는 정책 감사도 명시).
r2 시대의 정렬 가능성 연산은 `audit_mfa_4tier_year.py:340`
(`eligible_lab_ids = lab_ids - excluded_ids`)이 유일한 유사물이다.
한편 승인 제외 계약에는 **pre-MFA 계약과 post-MFA 결합 계약이 연도별로
공존**한다: 2021 `1,488` vs 결합 `2,037`(post-MFA 535 포함), 2022 `1,231`
vs 결합 `1,669`(post-MFA 438 포함), 2020 `2,250`(r2 정렬 실패 360 포함).

**연구방법론 영향:** r3 교집합의 우변에 **결합(post-MFA 포함) 계약을 쓰면
안 된다.** post-MFA 미정렬은 r2 사전·모델에서의 정렬 결과이므로, 새 r3
사전에서는 정렬될 수 있다. workflow의 식
"pronunciation-safe pool = MFA 입력 + **pre-MFA** 기술 제외"도 이를
전제한다. 결합 계약을 재사용하면 r2의 실패를 r3에 선험적으로 각인해
회수 가능 발화를 잃고, r2/r3 비교 분석도 오염된다.

**데이터 무결성 영향:** 교집합 계약이 없으면 Y05 post-MFA 회계의 분모가
연도마다 임의로 재구성될 수 있다.

**수정안:** Y01 builder는 교집합 우변을 "pre-MFA 승인 제외(audio/CSV
pairing·empty reference·불가능 시간)만"으로 제한하고, r2 post-MFA ID
(2020 360, 2021 535, 2022 438)는 **r3 정규 입력으로 복귀**시키되 별도
열(`r2_post_mfa_unaligned=true`)로 표지해 r3 결과와 비교 보고한다.
연도 계약에는 `pron_safe_body / pre_mfa_exclusion / expected_mfa_input`
수량과 exact-ID 목록 SHA를 분리 기록한다.

### H5. 2020 복구 WAV corpus 계약이 preflight 체계에서 검증되지 않는다

**근거:** `mfa_wav_corpus.ps1:25-58`은 2020에 대해 복구 corpus 계약
(`04_wav_id_recovered_staging`, 868,603 WAV)을 fail-closed로 강제하지만,
GO/NO-GO를 판정하는 `preflight_mfa_year_queue.ps1`은 이 resolver를 아예
호출하지 않고(dot-source 없음), `preflight_eojeol_realign.ps1` 호출도
`-Year` 없이 기본 `03_wav\individual` 트리 기준으로 수행한다(:178-182).
`start_full_mfa_after_review.ps1`에도 corpus resolver 참조가 없다.
또한 Stage 19 라우팅 분모는 동결 master 870,437이므로 2020 safe 784,390에는
음원 미대응 1,834건 등 corpus 밖 ID가 포함될 수 있다.

**연구방법론 영향:** 2020이 r3 첫 생산 연도이므로, 교집합 계약이 복구
corpus의 `corpus_contract_id`에 결속되지 않으면 첫 연도부터 분모 불일치로
시작한다.

**수정안:** r3 preflight는 연도별로 `Resolve-MfaWavCorpusForYear`를 호출해
2020 계약 유효성을 GO 조건에 포함하고, Y01 계약에 `corpus_contract_id`와
corpus WAV 수(868,603)를 기록한다. 2020 교집합은
`safe(784,390) ∩ corpus(868,603) ∩ pre-MFA 승인 제외 여집합`으로 명시한다.

### H6. Stage 21 표적 회귀는 생산 문맥에서 재현되지 않는다 — Gate 판정 기준이 미정의

**근거:** Stage 21은 네 발화(`있지·놨던·슬프겠지만·없는`)만 격리 정렬했다.
MFA는 화자·세션 단위 적응(SAT)을 쓰므로, 2022 전수 r3 정렬에서 같은 네
발화의 경계는 격리 정렬과 수치적으로 동일하지 않다. draft adoption_gates의
"2022 reviewed regression IDs 08, 09, 15, 24 pass the intended boundary and
label checks"에는 판정 기준(입력 phone 동일성? 경계 허용 오차? 재승인?)이
없다.

**연구방법론 영향:** 기준이 없으면 이 Gate는 (a) 검사 불능이 되거나 (b)
"대충 비슷하면 통과"가 되어 회귀 표본의 의미가 사라진다.

**수정안:** Gate를 두 층으로 정의한다. (1) **결정론 층**: 네 발화의 MFA
입력 phone열이 승인 당시와 byte 동일(사전 projection 검증) — 자동, 통과
필수. (2) **경계 층**: 생산 DB에서 재수출한 TextGrid의 word/phone 경계가
승인본 대비 허용 오차(예: ±20ms) 이내면 자동 통과, 초과 시에만 연구자
재확인. 오차 값은 구현 전에 문서로 고정한다. 음운현상별 층화 자동 회귀
(비음화·경음화 등 8현상)도 같은 2층 구조로 구현한다.

## 4. Medium

### M1. `Archive-StaleTemp` 호출 인자 버그 — 명시적 clean 재시도 경로가 항상 실패

**근거:** `run_eojeol_realign.ps1:2416-2417`이 4-파라미터 함수
(`:1416` `($path, $allowedRoot, $year, $reason)`)를 3인자로 호출한다.
`$allowedRoot`에 연도 문자열이 들어가 `:1419` 경계 검사가 throw하고,
`-AllowFullCleanRetry`를 명시해도 archive 대신 중단된다(올바른 4인자 호출
형태는 `:1885-1886`에 있음). 실패 방향이 안전(fail-safe)이라 Critical은
아니나, 의도된 국소 복구 경로가 죽어 있다.

**수정안:** r3 runner 구현 시 이 함수·호출을 이식하면서 인자를 교정하고,
안전검사 토큰이 아니라 **실제 호출 시험**(합성 temp 디렉터리)을 추가한다.

### M2. 정책 감사의 r2 hard-code 탐지가 표식 수준이다

**근거:** `audit_mfa_r3_full_realign_policy.py:131-160` — `"r2"` 대소문자
무시 부분 문자열 매칭이라 주석 한 줄로도 hit이고, 스캔 대상이 3개 파일뿐
이다. 이번 검토에서 확인된 실제 hard-code 지점(`preflight_eojeol_realign.
ps1:12` ValidateSet, `run_eojeol_realign.ps1:465-479,546-548`,
`start_full_mfa_after_review.ps1:27-34`, `preflight_mfa_year_queue.ps1:7,
178-182` 등)의 대부분이 스캔 밖이다. 또 `production_mfa_allowed_now`가
리터럴 `False`(:191)이고, 연도 회계는 config 정수의 산술 자기일관성만
검사하며 Stage 19 실물과 잇지 않는다.

**수정안:** r3 runner 완성 후 이 감사를 v2로: (a) 스캔 대상을 r3 실행
경로의 전 스크립트로 확장, (b) 토큰을 `common_pron_mfa_r2_`·
`direct_db_research_6tier_v1`·`mfa_r2_` 등 구체 패턴으로 교체, (c)
`year_accounting`을 `year_routing_summary.csv` SHA·값과 대조.

### M3. 승인 계약이 제자리 갱신된다

**근거:** `build_common_pron_r3_staged_approval.py:164-167` — `review_csv`·
`workflow_policy` SHA를 identity에서 의도적으로 제외하고, :201-215에서
workflow 파일이 바뀌면 기존 승인 JSON을 같은 자리에서 다시 쓴다
(`provenance_refreshed_at`만 갱신; 실물에서 `recorded_at 09:50:33` vs
`refreshed 09:59:17` 확인). "사소한 문서 수정이 새 승인을 만들지 않게"
하려는 의도는 이해되나, 승인 **파일 자체**가 변형되는 것은 감사 추적상
바람직하지 않다.

**수정안:** 승인 JSON은 최초 기록 후 불변으로 두고, provenance 갱신은
별도 sidecar(`RESEARCHER_APPROVAL.provenance.v2.json`)에 append-only로
기록한다. C2의 v3.1 개정을 승인 파일 재작성 없이 처리하려면 이 분리가
선행돼야 한다.

### M4. PowerShell 안전검사의 구조적 공백 — 새 r3 스크립트는 자동으로 검사 밖

**근거:** `test_powershell_safety.ps1:4-61`은 50개 고정 allowlist다. 현재도
11개 스크립트가 미포함이고, `show_active_mfa_progress.ps1` 검사 블록
(:1158-1179, heartbeat `Get-Content` 금지 규칙 포함)은 대상 배열에 그 파일이
없어 **한 번도 실행되지 않는 dead code**다. 전수 glob 검사를 하는
`test_powershell_runtime_compat.ps1`은 어떤 preflight에서도 호출되지 않는다
(`preflight_mfa_year_queue.ps1:246-251`은 safety만 실행). 검사 자체도
`String.Contains` 토큰 매칭이라 주석으로 충족될 수 있다.

**수정안:** (a) BOM·ParseFile 검사는 `scripts\*.ps1` 전수 glob으로 승격,
(b) 신규 `run_mfa_r3_year_safe_body.ps1`·r3 preflight를 allowlist에 추가하는
일을 구현 체크리스트에 명문화, (c) dead block에 파일 추가, (d) r3 preflight
가 safety+runtime_compat 둘 다 실행하도록 배선.

### M5. checkpoint QC 재개기가 lock·D: 라벨 가드 없이 돈다

**근거:** `resume_mfa_year_checkpoint_qc.ps1`은 identity 재검증(:139-158)은
훌륭하나 `pre_mfa_bulk.lock`/`mfa_year_queue.lock`을 잡지도 검사하지도
않고 D: 라벨 가드도 없다. 연도 queue와 동시 실행되면 "D: 대량 I/O 비중복"
규칙(불변 규칙 6)을 위반한다.

**수정안:** r3 상당 스크립트에는 lock 획득(또는 최소한 live lock 검사)과
`DATA_SSD` 라벨 가드를 넣는다.

### M6. 절전 방지가 wrapper 경유에만 있다

**근거:** `SetThreadExecutionState`는 `run_mfa_year_queue_safe.ps1:59-83` 등
7개 스크립트에 있으나 `run_eojeol_realign.ps1`·`run_pre_mfa_bulk_safe.ps1`
직접 호출 경로에는 없다(0건 확인). 직접 실행 시 장시간 MFA 중 절전 위험.

**수정안:** r3 runner 본체에 enable/restore 쌍을 내장한다(기존 7개 구현
중 하나 이식).

### M7. 용량 문턱이 r2 단일 연도 기준이다

**근거:** `preflight_mfa_year_queue.ps1:116-118` 55GiB 고정,
`run_eojeol_realign.ps1:567` 45/55GB. r3는 r2 증거(DB 3개 등)를 보존한 채
새 release root를 추가하므로 소요가 다르다.

**수정안:** r3 preflight는 연도별 예상 소요(corpus 사본 + temp + DB +
staging)를 계약에서 계산해 문턱을 산출하고, r2 보존분을 지우지 않는 것을
전제로 검사한다.

### M8. follow-up 비율의 연도 추세는 우연이 아니다 — selection bias 보고 계약 필요

**근거:** `year_routing_summary.csv` — follow-up 비율이 2020 9.89% → 2021
12.06% → 2022 13.13% → 2023 14.01% → 2024 18.20% → 2025 21.37%로 단조
증가한다. 블록 사유의 99.9%가 어휘 hold(717,354/718,364)이므로, follow-up은
"드문·비표준·미해결 발음형을 포함한 발화"라는 어휘 조건화 집합이다. 연도별
말뭉치의 어휘 분포 차이(신어·고유명 증가 추정)가 그대로 반영된 것이다.

**연구방법론 영향:** 정렬본만으로 연도 간 비교를 하면 해당 어휘를 포함한
발화 환경이 연도별로 다른 비율로 빠진다. 음운 환경 검색의 분모가 연도마다
다르게 축소된다.

**수정안:** (a) 논문·보고 표준 표에 연도별 safe/follow-up 비율과 블록 사유
분포를 고정 포함, (b) 검색층(pre-MFA 7표)은 전체 5,103,356 기준을 유지하고
"정렬층 존재 여부"를 열로 표시해 환경 검색 자체는 전수에서 수행 가능하게,
(c) 음운현상별로 safe/follow-up 출현 비율을 산출하는 coverage 표를 Y08
감사에 추가(현상별 손실률이 큰 경우 해석 제한 명시), (d) hold 최빈 상위
형태의 회수를 follow-up 1차 release 우선순위로 삼는다.

### M9. 화자 적응과 부분 세션 정렬 — 세션 제외는 불필요하나 기록 계약이 필요

**분석:** 세션 일부 발화가 follow-up이어도 세션 전체를 뺄 필요는 없다.
근거: (a) follow-up 비율은 발화 단위이고 세션 내 무작위에 가깝게 분산되며,
(b) 적응 통계는 나머지 safe 발화만으로도 대개 충분하고, (c) 세션 제외는
손실을 어휘 조건화에서 세션 조건화로 확대해 bias를 오히려 키운다. 단,
r2와 r3의 같은 발화 경계 차이에는 "사전 차이" 외에 "적응 데이터 차이(세션
내 발화 구성 변화)"가 섞이므로 r2/r3 비교 분석 시 이를 명시해야 한다.

**수정안:** Y07 동반표에 세션 단위 `session_utt_total / session_safe_count /
session_safe_speech_seconds`를 기록하고, 적응 지지가 약한 세션(예: safe
발화 10개 미만 또는 발화 총 길이 임계 미만)을 **제외가 아니라 flag**로
표시한다. follow-up 후속 정렬 시 같은 세션 safe 발화를 함께 넣어 적응
문맥을 재현할지, follow-up만 별도 정렬할지를 후속 release 계약에서 명시한다.

## 5. Low

### L1. validator 보고서가 발음 mode를 리터럴로 오표기

`validate_mfa_r2_adoption.py:145` — 검증한 release와 무관하게
`"pronunciation_mode": "common_pron_mfa_r2_latest_jamo"`를 기록한다. r3
validator에서는 manifest에서 유도할 것.

### L2. 존재하지 않는 lock 파일 참조

`archive_legacy_mfa_markers_for_r2.ps1:102-105`가 현재 없는
`locks\eojeol_realign.lock`을 검사 목록에 두고 있다. 무해하나 lock 목록의
단일 정본(공용 함수 또는 config 키)을 두면 재발을 막는다.

### L3. temp 우선순위의 잠재 혼동

`run_eojeol_realign.ps1:566-587` — 기존 `D:\mfa_tmp\<year>`가 있으면
우선하고 없으면 `C:\mfa_tmp` 검사로 넘어간다. r3에서 release-scoped 경로로
가면 자연 해소되지만, C: temp로의 조용한 전환은 r3에서 금지(명시 인자
없이는 D: 고정)로 단순화할 것.

## 6. 중점 검토 질문에 대한 답

프롬프트의 10개 질문 순서대로 요약한다.

1. **거시·미시 workflow의 방법론 타당성** — 타당하다. 단일 동결 계약·연도
   직렬 Gate·단계 분리(Y01–Y10)·국소 복구 원칙은 corpus 인프라 표준에
   부합한다. 결함은 방향이 아니라 결속력이다: C2(계약 모순)·H1(safe 목록
   미실물)·H4(교집합 미구현)를 해소해야 설계가 코드로 강제된다.
2. **화자 적응 × safe-body 선별** — M9 참조. 세션 유지+flag가 정답이며,
   세션 제외는 bias를 키운다. r2/r3 경계 비교 시 적응 문맥 차이를 명시할 것.
3. **오류 유형별 재처리·checkpoint 재개 안전성** — 원칙(§5 workflow 표)은
   옳고 r2 코드의 실증 이력도 좋다. 다만 M1 버그, C1 이름공간, M5 lock
   공백이 r3 이식 시 교정 대상이다. 재실행 범위는 §8 결정표를 따를 것.
4. **사전·입력·정렬·TextGrid·CSV 계약 분리** — 분리는 이미 잘 돼 있다
   (Y06 export가 DB와 분리, Y07 CSV만 재생성 가능). 부족한 것은 각 층이
   같은 r3 identity를 pin하는 것(H2·H3).
5. **2020 Gate와 2021–2025 자동 진행** — 2020 1회 deterministic 표본 + 사람
   검토, 이후 연도는 자동 전수 감사 무결 + 회귀(2층 기준, H6) 통과 시
   자동 진행하되, (a) hard failure, (b) 회귀 경계층 초과, (c) 연도 분포
   지표(미정렬률·spn·평균 경계 통계)가 직전 연도 대비 임계 이탈 — 셋 중
   하나면 사람 표본을 요구하는 조건부 설계를 권한다. 무조건 매년 24표본
   재검토는 이미 축적된 r2 검토·회귀 증거와 중복이다.
6. **follow-up 비율과 selection bias** — M8 참조. 연도별 비율 표준 보고 +
   검색층 전수 유지 + 현상별 coverage 감사 + hold 상위형 우선 회수.
7. **r2 hard-code·marker·path·schema·PS5.1 위험** — C1·H2·H4·H5·M4의
   목록이 실측 전수다. 요지: **기존 runner의 fail-closed 잠금은 우회하지
   말고, r3는 이름공간·schema·계약 builder를 전부 새로 판다.** PS5.1
   측면은 BOM·배열 정규화·heartbeat 규칙이 이미 테스트로 존재하므로 신규
   스크립트를 allowlist에 넣는 절차만 강제하면 된다(M4).
8. **반복을 줄이되 놓치면 안 되는 검사** — 반복 불필요: Stage 01–21 재실행,
   광범위 파일럿, r2 연도 재감사, 동일 G2P 재생성(모두 manifest+SHA로
   skip). 반드시 유지: 연도별 독립 전수 감사(Y08), DB 표본 재수출 동등성,
   ID 수준 회계 등식, phoneme_r_auto 결정론(신규, H3), 회귀 2층 검사(H6),
   release identity 대조. 즉 "사람 반복"은 줄이고 "기계 전수"는 유지한다.
9. **최소 구현 순서와 GO/NO-GO** — §7 체크리스트 참조.
10. **safe-body 4,384,992 vs 4,120,627** — 혼용 금지가 옳으며 정의 차이를
    코드로 확정했다: 4,120,627은 **2021–2025 5개년**(4,232,919 − 112,292)
    의 음원·CSV pairing 기준이고 2020(870,437; 별도 제외 2,250)이 아예
    분모에 없다. 4,384,992는 6개년 발음 coverage 기준이다. 두 수는 어떤
    산식으로도 서로 유도되지 않으므로 문서·계약에서 나란히 쓰지 말고,
    연도 입력 계약의 `pron_safe_body / pre_mfa_exclusion /
    expected_mfa_input` 3열(+ID 목록 SHA)로만 보고한다(H4 수정안).
    교집합의 우변은 pre-MFA 제외만 사용한다(H4의 post-MFA 함정 주의).

## 7. 2020 실행 전 최소 체크리스트

순서대로 수행하며, 각 항목은 산출물(파일)과 통과 조건을 가진다. 이
목록 밖의 작업(새 파일럿, Stage 재실행, r2 재감사)은 하지 않는다.

| # | 작업 | 산출물 | 통과 조건 |
|---:|---|---|---|
| 1 | C2: v3.1 staged adoption 개정 (M3의 승인 sidecar 분리 포함) | `common_pronunciation_resource_contract_v3_1.json`, 개정 사유 결정문 | selection 정의·coverage 분모가 승인 범위와 일치 |
| 2 | staged r3 release builder + 독립 adoption 감사 | release manifest(`common_pron_mfa_r3_<date>`), 사전 byte-projection 감사 | 사전=canonical projection byte 동일, inventory 밖 phone 0, Stage 19/20 실물 SHA pin |
| 3 | H1·H4·H5: 연도 입력 계약 builder + 독립 감사 | 연도별 safe ID 목록(.csv.gz+SHA), `YEAR_INPUT_CONTRACT_2020.json` | source=safe+followup(ID 수준), ∩=0, unknown=0, 연도 수량=`year_routing_summary.csv`, 2020 `corpus_contract_id` 결속, 우변=pre-MFA 제외만 |
| 4 | H2: r3 alignment contract builder | `mfa_r3_alignment_contract.v1` schema | identity에 release ID·manifest SHA·routing 계약 ID·사전 SHA 포함, r2 상수 0 |
| 5 | C1: r3 runner + preflight (`run_mfa_r3_year_safe_body.ps1` 등) | release-scoped 경로·marker, M1 교정, M5 lock, M6 절전, M7 용량 산식 | `-PreflightOnly` GO, r3 이름공간에 r2 marker/DB 0 |
| 6 | H3: exporter·감사 확장 | manifest 10필드, DB SHA, phoneme_r_auto label 검사 | 합성 fixture 회귀 통과 |
| 7 | M4: 테스트 배선 | safety allowlist에 신규 스크립트 추가, glob BOM/parse, dead block 수정 | `test_powershell_safety` + `test_powershell_runtime_compat` PS5.1 통과, Python 전체 suite 통과 |
| 8 | release Gate 개방(단일 편집) | `mfa_pronunciation_release_gate.json`: `status=adopted`, `allowed_release_ids=[r3 ID]`, r2는 blocked 유지 | 정책 감사 v2 통과 |
| 9 | 2020 `-PreflightOnly` GO | GO/NO-GO JSON | 아래 GO 조건 전부 충족 |

**2020 GO 조건(모두 hard):** D: 라벨 `DATA_SSD`; 산식 기반 여유 공간;
live lock 0; r3 이름공간 청정(r2 marker/DB 미검출); 2020 복구 corpus 계약
`passed`; 연도 입력 계약 감사 통과; adoption 감사 통과; release Gate가
정확히 r3 ID 하나만 허용; Stage 19/20 실물 SHA 불변; PS5.1 테스트 2종 +
Python suite 통과. — 하나라도 실패하면 MFA를 시작하지 않는다(수정 후
preflight만 재실행).

## 8. 재실행 범위 결정표

workflow §5를 기반으로 이번 검토 결과를 반영해 확정한 표다. "안 하는 것"
열이 더 중요하다.

| 오류/변경 | 다시 하는 범위 | 다시 하지 않는 것 |
|---|---|---|
| v3.1 계약 문구 수정(수량·정책 불변) | 정책 감사 재실행만 | 승인 재취득, Stage 19–21, 어떤 계산도 |
| 사전·phone inventory·acoustic 변경 | 새 release ID + 영향 연도 Y02–Y09 전체 | 원 CSV, 형태소 분석, Stage 19 라우팅(입력 불변 시) |
| Stage 19 라우팅 오류 발견 | Stage 19 재계산 + 전 연도 Y01부터 | Stage 01–18(readiness 불변 시), r2 증거 |
| 연도 입력 계약(Y01) 버그 | 해당 연도 Y01–(진행된 지점)만 | 다른 연도, Stage 19 실물 |
| WAV 누락·손상·ID 불일치(개별) | 해당 exact ID/세션의 corpus 준비 + follow-up 이관 | 같은 연도 다른 세션의 MFA |
| MFA process 중단(전원·리밋 등) | 같은 DB·checkpoint에서 Y04 재개 (`inspect_mfa_db_checkpoint` 통과 확인 후) | `--clean` 재시작, temp/DB 삭제 |
| DB checkpoint 수량 불일치(:2471-2483 유형) | 원인 조사 후 **그 연도만** 새 release-scoped temp에서 재정렬 | 다른 연도, 불일치 DB 삭제(보존·격리) |
| 일부 발화 정렬 미생성 | Y05 exact-ID 회계로 follow-up 이관 | 성공 DB 폐기, 연도 재정렬 |
| TextGrid tier·경계·label 버그 | Y06–Y09 재수출·재감사 | Y04 MFA·DB |
| 동반 CSV 열·조인·Roman 버그 | Y07–Y09만 | MFA·TextGrid·시간값 |
| phoneme_r_auto 매핑 버그 | 매핑 수정 + Y06–Y09 (phones_mfa 불변이므로) | MFA·DB |
| 국소 발음형 오류(채택 후) | point release 계약 + token→세션 영향 inventory + 영향 적응 단위만 새 DB 재정렬 | 무관 세션, 기존 TextGrid label 제자리 수정(절대 금지) |
| 회귀 경계층 허용 오차 초과(H6) | 해당 발화 연구자 확인; 원인이 사전이면 point release 경로 | 연도 자동 재정렬 |
| heartbeat/dashboard 잠금 | sidecar 재시도(자동) | MFA 중단 |
| 용량 부족 | 안전 정지 → archive 검증 → 같은 checkpoint 재개 | 검증 결과 삭제, 자동 clean |
| 직전 연도 Gate 실패 | 실패 항목만 수정 후 Gate 재실행 | 통과 항목 재검토, 연도 재계산 |

---

*본 보고서는 읽기 전용 검토이며 코드·D: 자료·release Gate를 변경하지
않았다. 근거 행 번호는 commit `abd8d45` 기준이다.*
