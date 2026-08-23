# CROSSCHECK — Stage 2 2시간 파일럿 워크플로 외부 검토 교차확인

- 날짜: 2026-08-23 KST
- 작업 성격: 확인 전용. 코드·config·outputs·기존 HTML을 수정하지 않았고, git
  commit·push, query 변경, 자동 실현 판정·MFA·KOINA·wav2vec2를 수행하지 않았다.
- 교차확인 대상:
  `docs/reviews/incoming/EXTERNAL_REVIEW_stage2_two_hour_pilot_workflow_claude_cowork_20260823.md`
  및 같은 이름 `.jsonl`(제안 22행: M 3 · S 10 · D 4 · K 5)
- 검증물:
  `outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/researcher_review_package_v1/`
  (START_HERE.html, STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html, README.md,
  open_praat_sample.ps1, PRAAT_TASKS.csv),
  `config/phenomenon_scope_cards_candidate_v1_20260823.jsonl`,
  `config/stage2_two_hour_phenomenon_pilot_schema.v1.json`,
  `docs/decisions/RESULT_stage2_seven_phenomena_two_hour_research_pilot_preparation_20260823.md`,
  `reviewer_package_audit_v1/AUDIT_STAGE2_TWO_HOUR_REVIEWER.json`,
  `tests/test_stage2_two_hour_seven_phenomena_reviewer_runtime.js`
- 방법: (1) 내장 JS 전문·본문 HTML·데이터 블록의 정적 정독(스크래치패드에
  정형화 사본을 만들어 읽음, 원본 무수정), (2) 로컬 읽기 전용 정적 서버
  (127.0.0.1:8137, GET 전용)로 실제 브라우저에서 시나리오 재현. 실측 후 서버
  종료, 테스트가 만든 localStorage 키 2건 삭제를 확인했다. 저장소 파일은
  변경되지 않았다.

## 1. 판정 요약

22개 제안의 "현재 관찰"을 코드·문서·실측으로 대조했다. **22건 전부
confirmed**이며, not_reproduced·needs_more_evidence는 없다. 다만 §4의 정밀화
노트 4건(서술과 실물의 사소한 차이)과, 외부 검토에 **없는 신규 결함 1건**(§5,
현상 드롭다운 전환이 TypeError로 중단)을 확인 과정에서 발견했다.

| 제안 | 판정 | 핵심 근거(요약) |
|---|---|---|
| WF-M1 | confirmed | START_HERE 라벨 4건 불일치 재현(§2.1). 본 화면 label_ko 7건은 카드와 완전 일치 |
| WF-M2 | confirmed | 문헌 메모 쓰기 경로는 submit 핸들러 내부뿐, 이동 확인창 승인 시 유실 실측 재현(§2.2) |
| WF-M3 | confirmed | restoreForm()이 순서 모드 무관하게 최신 행 복원, 셔플 재방문 시 1차 판정 노출 실측 재현(§2.3) |
| WF-S1 | confirmed | scope-contract `<details open>`·claims `<details>`(접힘) 기본, 접힘 상태는 innerHTML 교체 범위 밖이라 유지, 폼 순서 규칙 문서 없음 |
| WF-S2 | confirmed | JS 전체에 currentTime 조작 없음(점프 버튼 부재), 인용 사례 실측치 일치(§3) |
| WF-S3 | confirmed | import 핸들러 try/catch 부재, 실패 2종 화면 무표시 실측 재현(§2.4) |
| WF-S4 | confirmed | 두 확신도 셀렉트는 맨 옵션 1–5뿐, 화면·README·RESULT 어디에도 앵커 정의 없음 |
| WF-S5 | confirmed | 메모 textarea 정확히 4개, 데이터/도구 문제 전용 필드 없음 |
| WF-S6 | confirmed | boundary_edit_need(불필요/필요/불확실)·Praat 명령·복사 버튼 존재, '필요' 기준 문장은 4개 문서 모두 부재 |
| WF-S7 | confirmed | RESULT §2 4단계 "불확실 사례 재확인·Praat 필요 표시 20분" 대 셔플이 12사례 전체 적용, 문턱 기준 문서 부재 |
| WF-S8 | confirmed | 저장 행에 build SHA 없음, SHA는 STORAGE_KEY에만(8043eb25… 일치), 청취 조건 필드 없음. 필드명 정밀화는 §4.2 |
| WF-S9 | confirmed | a.download 고정 파일명, import는 event_uuid dedupe 없이 imported 통째 대입 → local과 이중 축적 경로 성립(§2.5) |
| WF-S10 | confirmed | 단계 수준 표지 UI 없음(사례 카운터·position뿐), RESULT §9에 현상 종료 조건 명문화 없음 |
| WF-D1 | confirmed | 화면에 운율·동음이의어·의미번호·어원·빈도 표시 없음, 카드 7행 전부 sidecar_candidates 보유(prosodic_boundary·word_origin·lexical_frequency 등) |
| WF-D2 | confirmed | 타이머 UI 없음, schedule은 pilot_schedule 텍스트 배너 렌더링뿐 |
| WF-D3 | confirmed | 카드 7행 전부 not_judgeable_reasons 정의, 폼에는 사유 선택지 없음(들린 실현의 not_judgeable 값만 존재, 사유는 자유 메모뿐) |
| WF-D4 | confirmed | target-audio에 이벤트 리스너·재생 로그 없음 |
| WF-K1 | confirmed | environment_confidence·realization_confidence 분리 존재 |
| WF-K2 | confirmed | grouped 기본·shuffled 2차, shuffled_order는 빌드 시 고정값(런타임 난수 없음), 스키마 sampling_contract const 일치 |
| WF-K3 | confirmed | claims 기본 접힘, renderCurrent에 사례별 claim 매칭·필터 없음 |
| WF-K4 | confirmed | append-only push·revision 체인 필드·record_role 고정·읽기 전용 TextGrid·PT probe 경고·derived turn 경고·PT 전용 합성어성 필드·AUDIT checks 기대값 전부 일치 |
| WF-K5 | confirmed | 한 사례 한 화면, ✓·"저장된 청취 n/12"·localStorage 복원 실측, AUDIT one_case_per_screen_contract=true |

코드 인용은 `STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html`의 원본(압축) 행
번호다: STORAGE_KEY·상수 35행, latest()·history() 36행, renderList 38행,
requestOpen(confirm) 39행, renderLiterature 41행, restoreForm 46행,
renderCurrent 47행, submit 핸들러 49행, input 리스너·현상 onchange·순서
onchange 50행, export·import·beforeunload 51행.

## 2. 지목 항목 상세 재현

### 2.1 WF-M1 — START_HERE 라벨 대 scope card label_ko

`START_HERE.html`(단일 행) 시작 링크 7건 대
`config/phenomenon_scope_cards_candidate_v1_20260823.jsonl`의 label_ko:

| 코드 | START_HERE 링크 | 카드 label_ko | 대조 |
|---|---|---|---|
| PT | 합성어 경음화 | 합성어 경음화(사잇소리 관련 포함) | 괄호 부연만 생략(외부 검토와 동일하게 불일치로 세지 않음, §4.1) |
| NAN | 비음 동화 | ㄴ 앞 비음화 | **불일치** |
| NAL | 유음화 | ㄹ 앞 비음화 | **불일치**(방향이 반대인 별개 현상명) |
| NI | ㄴ삽입 | ㄴ삽입 | 일치 |
| LLN | 유음의 비음화 | ㄴㄹ·ㄹㄴ 연쇄(유음화·비음화 복합형) | **불일치**(복합형의 한쪽만 지칭) |
| VH | 모음조화 | 모음조화 | 일치 |
| HIA | ㅎ 관련 축약·탈락 | 모음충돌 회피 | **불일치**(완전히 다른 현상) |

불일치 4건(NAN·NAL·LLN·HIA)이 외부 검토 관찰 문구 그대로 재현된다. 본 화면
literature-data의 label_ko 7건은 카드와 문자열 단위로 완전 일치함도
확인했다(진행 표시·드롭다운·문헌 제목이 모두 이 값을 쓴다). 즉 불일치는
START_HERE에만 있다.

### 2.2 WF-M2 — 문헌 메모·잠정 패턴 정리의 기록 경로

정적 확인(코드 사실):

1. `phenomenon-lit-note`를 localStorage(`STORAGE_KEY+'_lit_'+현상코드`)나 행
   필드(`phenomenon_literature_note`)에 쓰는 코드는 **submit 핸들러(49행) 안
   두 곳뿐**이다.
2. lit-note의 input 리스너(50행)는 `dirty=true`만 설정하고 저장하지 않는다.
3. 사례 이동 `requestOpen()`(39행)은 confirm 승인 시
   `renderCurrent()→renderLiterature()`(41행)를 거쳐 textarea를 localStorage
   값으로 되돌린다.
4. `phenomenon_summary`류 현상 수준 행은 없다. 모든 행은
   `record_role:'exploratory_pilot_only_not_formal_realization_ledger'`인 사례
   행이고, export(51행)는 `history()` 행만 내보내므로 마지막 사례 저장 이후의
   메모 수정분은 JSONL에 들어가지 않는다.
5. import(51행)는 renderLiterature를 호출하지 않고, renderLiterature는
   imported 행의 phenomenon_literature_note를 읽지 않으므로, 다른
   기기·브라우저에서 JSONL을 불러와도 문헌 메모는 화면에 복원되지 않는다.

브라우저 실측(127.0.0.1:8137, PT 화면):

- 메모 입력 → 다른 사례 클릭 → confirm("저장하지 않은 입력이 있습니다. 버리고
  이동할까요?") 호출 확인 → 승인 → 이동 직후 textarea 값 `""`,
  `_lit_` localStorage 키 부재. **작성 중 메모 완전 유실 재현.**
- 부기: lit-note만 편집한 상태에서는 "저장하지 않은 변경" 표시도 뜨지
  않는다(§4.3). 현상 "전환" 경로의 세부는 신규 결함(§5) 때문에 검토 서술과
  다르게 진행되나 유실 결론은 같다(§4.4).

### 2.3 WF-M3 — 셔플 재확인에서 1차 판정 사전 노출

정적 확인: `restoreForm()`(46행)은 `latest()[sample_id]`(36행: reviewed_at
최신, 동률 시 후행 인덱스)를 폼 전 필드(체크박스·셀렉트·textarea)와
realization_impression에 복원하며 **order-mode 분기가 없다**. 순서 전환
(50행 `order-mode.onchange=applyFilter`)도 같은 restoreForm 경로를 지난다.

브라우저 실측: grouped에서 P2H-PT-2024-01에 listened✓·들린 실현
tense_like·청취 확신도 2를 저장(행 1건 append) → shuffled 전환(해당 사례
11/12 위치로 이동) → 다른 사례를 들렀다가 재방문 → **세 값이 모두 미리 채워져
표시되고 "마지막 저장 …" 문구가 노출**. 셔플 2차의 차폐 부재 재현.

부기(검토의 검증 방법 항목과 일치): 저장 행에는 `review_order_mode`와
`revision_seq`가 기록되므로 2차 저장의 사후 구분 자체는 가능하다. 문제는
사전 노출뿐이다.

### 2.4 WF-S3 — JSONL 불러오기 무표시 실패

정적 확인: import onchange(51행)는 async 함수로 try/catch가 없다.
`JSON.parse` 실패·미지 sample_id의 `throw`는 unhandled promise rejection이
되고, `import-status`는 성공 경로에서만 갱신된다. `imported` 대입이 루프
완료 후라 실패 시 이전 값(초기 빈 배열)이 유지되고, 이후 submit(49행)의
`revision_seq=prior.length+1`이 1부터, `supersedes_event_uuid=''`로 시작해
체인이 끊긴다.

브라우저 실측(DataTransfer로 파일 선택 모사):

| 입력 | import-status | 관찰 |
|---|---|---|
| 깨진 JSON 1행 | ""(무표시) | unhandledrejection: `SyntaxError: Unterminated string in JSON …` |
| 미지 sample_id 1행 | ""(무표시) | unhandledrejection: `Error: 알 수 없는 sample_id NOPE-999 at 1` |
| 정상 1행 | "1행 불러옴" | 정상 표시 |

실패 신호는 개발자 콘솔에만 남고 연구자 화면에는 아무 표시가 없다 — 검토의
"불러오기 후 'n행 불러옴' 확인" 절차 권고의 전제가 그대로 성립한다.

### 2.5 WF-S9 — export 고정 파일명·import 중복 미제거

정적 확인: export(51행) `a.download='P2H_EXPLORATORY_REVIEWS.jsonl'` 고정
(중복 다운로드 시 "(1), (2)" 접미는 브라우저 표준 동작). import는
event_uuid 대조 없이 `imported=rows`로 통째 대입하고
`history()=[...imported,...parseLocal()]`(36행)는 단순 연결이므로, 같은
브라우저에서 이전 export를 불러온 뒤 다시 export하면 localStorage 원본 행과
imported 사본이 이중으로 파일에 들어간다. `latest()`가 reviewed_at 기준
최신(동률 시 후행)을 고르므로 화면 표시는 안전하다는 부가 서술도 코드와
일치한다. RESULT §9-3("세션마다 같은 파일명 저장")이 반복 세션 전제를
뒷받침한다.

## 3. 나머지 17건 근거 상세

- **WF-S1**: 본문 HTML에서 literature-panel이 main 첫 패널. "이 파일럿의
  범위·제외·혼란변수"는 `<details open>`, "문헌 주장과 한계 — 20분 읽기"는
  `<details>`(기본 접힘). renderLiterature(41행)는 details 내부 div의
  innerHTML만 교체하므로 접힘/펼침 상태는 사례 이동 간 유지된다. 폼 작성 순서
  규칙은 화면·README·RESULT 어디에도 없다.
- **WF-S2**: `<audio id="target-audio" controls preload="metadata">` + "발화
  전체 exact copy입니다. 잘라낸 표적 음성이 아닙니다" 문구. JS 전문에
  currentTime 조작 없음. textgrid-meta가 표적 시각을 문자로 표시.
  인용 사례 P2H-PT-2022-02 실측: 2022년, active_form "분야를 하나 정해서 뭐
  전문적으로 공부를 하고 있는데", 표적 '공부를', TextGrid 전체 0–3.120초 중
  표적 2.070–2.450초 — 검토 수치와 전부 일치.
- **WF-S4**: environment_confidence·realization_confidence 셀렉트 옵션은 빈
  값+1~5뿐. '앵커' 관련 서술은 RESULT에서 grep 0건, README·화면에도 없음.
- **WF-S5**: 메모 textarea는 morph_environment_note, phonological_note,
  literature_connection_note, uncertainty_and_question 4개가 전부.
- **WF-S6**: boundary_edit_need(no/yes/unclear) 셀렉트, praat-command
  표시(47행)와 copy-praat 버튼(50행), `open_praat_sample.ps1`·
  `PRAAT_TASKS.csv`(84행) 존재. '필요' 판단 기준 문장은
  화면·README·START_HERE·RESULT 모두 부재.
- **WF-S7**: RESULT §2 표 4행 "20분 | 불확실 사례 재확인·Praat 필요 표시";
  화면 pilot_schedule(literature-data)도 동일. orderedSamples(37행)는 현상
  12사례 전체를 shuffled_order로 정렬하므로 셔플은 전체에 적용된다. 재확인
  대상 문턱 기준은 어떤 문서에도 없다.
- **WF-S8**: submit 행 필드 전체 열거 — schema_version, event_uuid,
  revision_seq, supersedes_event_uuid, sample_id, phenomenon_code, year,
  utt_id, physical_occurrence_ref, query_id, population_role_at_selection,
  review_order_mode, (폼 필드 일체), phenomenon_literature_note, record_role,
  reviewed_at. build SHA 필드 없음.
  `STORAGE_KEY='stage2_two_hour_seven_phenomena_reviews_v1_'+samples_sha256.slice(0,12)`
  (35행). build-data의 samples_sha256은
  `8043eb2564e041881051cad4c8f92370b061b363572ad8a4afb21c2e33eaca9f`로 검토가
  인용한 "8043eb25…"와 일치. 청취 조건 기록 필드 없음.
- **WF-S10**: 단계 수준 표지는 UI에 없음 — progress(38행)는 "저장된 청취
  n/12", position(47행)은 사례 위치뿐. RESULT §9는 절차 나열이며 "다음
  현상으로 넘어가는 조건" 명문화가 없다.
- **WF-D1**: 렌더링 항목(발화·형태소·화자 메타·TextGrid·대화·폼)에
  운율·동음이의어·의미번호·어원·빈도 없음. 카드 7행 전부 sidecar_candidates
  보유 — prosodic_boundary(1–5행)·prosodic_position(7행), word_origin
  (1·3·4·5행), lexical_frequency(1·6행) 등.
- **WF-D2**: 타이머·단계 추적 UI 없음. schedule(41행)은 pilot_schedule 텍스트
  배너.
- **WF-D3**: 카드 7행 전부 not_judgeable_reasons 정의(예: PT "표적 자음이
  겹침발화·잡음에 가림" 등 3건씩). 폼에는 사유 선택지가 없고, 들린 실현
  옵션에 not_judgeable 값만 있으며 사유는 자유 메모로만 남긴다.
- **WF-D4**: target-audio에 재생 이벤트 리스너·횟수 기록 없음(JS 전문 확인).
- **WF-K1**: 두 확신도 필드가 폼에 분리 존재.
- **WF-K2**: order-mode 첫 옵션 grouped("같은 형태소 조합·단어순"), 둘째
  shuffled("고정 셔플(두 번째 확인)"). shuffled_order는 84사례 전부에 빌드 시
  부여된 고정값(예: P2H-PT-2022-02 grouped 1·shuffled 51)이고 런타임 난수가
  없어 결정적. 스키마 sampling_contract의 const
  "same_morpheme_combination_then_word"/"deterministic_second_pass_order"와
  일치.
- **WF-K3**: claims details 기본 접힘(§WF-S1), renderCurrent(47행)에 사례별
  claim 매칭·필터 없음 — 문헌은 현상 수준 전체만 렌더링. 현상별 claim 수
  실측: PT 11 · NAN 8 · NAL 14 · NI 10 · LLN 18 · VH 12 · HIA 12(검토 본문의
  "8–18개, LLN 18개"와 일치).
- **WF-K4**: submit은 `local.push(row)` append-only, event_uuid·revision_seq·
  supersedes_event_uuid 체인, record_role 고정 문자열. 읽기 전용 TextGrid
  패널 + 원본 보존 복사본/Praat 작업본 링크 분리, 헤더 "음성은 발화 WAV의
  SHA 동일 복사본… TextGrid 수정은 praat_work 복사본에서만". PT 경고(47행:
  "합성어성을 확인하기 전에는 중심 PT 사례가 아닙니다") 및 PT 12건 전원
  compoundness_probe 실측. derived turn 경고 문구(대화 패널·README 5항).
  compoundness_decision은 PT에서만 표시(46행). AUDIT passed=true,
  automatic_realization_judgement=false, formal_ledger_written=false 등 checks
  전 항목 기대값 일치.
- **WF-K5**: 한 사례 한 화면(renderCurrent 단일 렌더), 목록 ✓(listened)·
  "저장된 청취 n/12"·localStorage 복원 실측(§2.3에서 ✓·카운터·복원 동작
  확인). AUDIT one_case_per_screen_contract=true.

## 4. 정밀화 노트 (판정을 바꾸지 않는 서술 차이)

1. **PT 라벨**: START_HERE의 "합성어 경음화"는 카드 label_ko의 괄호
   부연("(사잇소리 관련 포함)")을 생략한 축약형이다. 외부 검토처럼 불일치로
   세지 않는 것이 타당하나, 재빌드 시 label_ko 단일 소스로 생성하면 이 축약도
   함께 사라진다는 점만 기록한다.
2. **WF-S8 필드명**: 검토 관찰은 "population_role"이라 했으나 실제 행 필드는
   `population_role_at_selection`이다(실질 동일 정보).
3. **lit-note의 미저장 표시**: 폼 필드 편집은 "저장하지 않은 변경" 문구를
   띄우지만(50행), lit-note 편집은 dirty만 세팅하고 표시를 바꾸지 않는다.
   연구자가 미저장 상태를 알 수 있는 시점이 이동 확인창뿐이라 WF-M2 위험을
   약간 더 키운다.
4. **WF-M2의 "현상 전환" 경로**: 검토는 사례 이동과 현상 전환 모두
   "renderLiterature()가 즉시 되돌린다"고 서술했다. 사례 이동은 그대로
   재현되지만, 현상 전환은 §5의 신규 결함 때문에 renderLiterature까지 도달하지
   못하고 중단된다 — 메모는 textarea에 잠시 남지만, 이후 아무 컨트롤이나
   건드려 applyFilter가 돌면 확인창 없이 새 현상 메모로 덮여 유실된다. 유실
   결론은 같고 경로만 다르다.

## 5. 신규 관찰 — 현상 드롭다운 전환이 TypeError로 중단 (외부 검토 미포착)

**관찰**: 화면 상단 "현상" 드롭다운으로 현상을 바꾸면 아무 화면 변화가 없다.
콘솔에만 `Uncaught TypeError: history.replaceState is not a function`이 남는다.

**원인(정적)**: 최상위 스크립트의 `const history=()=>[...imported,
...parseLocal()]`(36행)가 전역 어휘 환경에서 `window.history`를 가린다. 현상
onchange 핸들러(50행)는 `currentCode`를 새 값으로 바꾼 직후
`history.replaceState(null,'',…)`를 호출하는데, 이 `history`는 화살표 함수라
replaceState가 없어 TypeError가 나고, 그 뒤의 `currentId=''`·`applyFilter()`가
실행되지 않는다.

**실측 재현(127.0.0.1:8137)**:

1. PT 화면에서 드롭다운을 NAN으로 변경 → `Uncaught TypeError:
   history.replaceState is not a function`. 셀렉트 표시만 NAN이고
   position("1/12 · PT")·진행 표시·사례 목록·본문은 전부 PT에 정지. URL도
   `?phenomenon=PT` 유지.
2. **잠복 전환**: 내부 `currentCode`는 이미 NAN이므로, 이후 무관한 컨트롤
   (빈 검색창 input 등)만 건드려도 화면이 갑자기 NAN으로 전환된다. 저장하지
   않은 폼 입력·문헌 메모는 이 시점에 확인창 없이 사라진다(§4.4).
3. 전역 상태 실측: `typeof history === "function"`,
   `history !== window.history`, `history.replaceState === undefined`.

**기존 검사망이 못 잡은 이유**:
`tests/test_stage2_two_hour_seven_phenomena_reviewer_runtime.js`는
`new vm.Script(...)`(23행)로 **구문 컴파일만** 하고 실행하지 않으므로 실행기
오류는 통과한다. RESULT §9-7도 "앱 브라우저 자동 시각 점검은 … 수행하지
못했다"고 명시하고 있어, 이 경로를 실제로 눌러 본 검사가 없었다.

**영향 한정**: START_HERE 링크(URL 파라미터) 진입과 새로고침 진입은 로드 시
`URLSearchParams`로 읽으므로 정상이다. 한 세션에서 한 현상만 다루는 운영
(README 2항)이라면 실사용 빈도는 낮지만, 현상 간 이동 시 무경고 데이터 유실
경로가 있으므로 파일럿 전 처리 결정이 필요하다.

**처리 제안(수정은 지시 대기)**: WF-M1 재빌드(외부 검토 질문 1)가 승인되면
같은 빌드에서 `window.history.replaceState`로의 정정(또는 해당 호출 제거)을
묶는 것이 자연스럽다. 재빌드 없이 절차로만 간다면 "현상 전환은 드롭다운이
아니라 START_HERE 링크나 URL 파라미터 변경으로만 한다"는 규칙이 필요하다.
빌더 스크립트(`scripts/python/build_stage2_two_hour_seven_phenomena_reviewer.py`)와
산출 HTML 어느 쪽도 이번 작업에서는 수정하지 않았다.

## 6. 검증·안전 확인

- 수정한 기존 파일: 없음. 생성: 이 문서 1건(`docs/reviews/incoming/`, 기존에
  없던 이름)과 스크래치패드 임시 파일(저장소 밖).
- 실측용 로컬 정적 서버(127.0.0.1:8137, GET 전용)는 검증 후 종료했다. 인앱
  브라우저 테스트가 만든 localStorage 키 2건
  (`…_8043eb2564e0`, `…_8043eb2564e0_lit_PT`)은 삭제를 확인했다. export
  다운로드는 수행하지 않았다.
- git commit·push 없음. query·config·outputs·문헌 workspace 무변경. 자동 실현
  판정·MFA·KOINA·wav2vec2 없음.
- 후속 처리(재빌드 여부, §5 결함 처리, decisions/_INDEX·WORK_HISTORY 기록)는
  외부 검토 §6의 질문 5개에 대한 사용자 답변 뒤 별도 지시를 따른다.
