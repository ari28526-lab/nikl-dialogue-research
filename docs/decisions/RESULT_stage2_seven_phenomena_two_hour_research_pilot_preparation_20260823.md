# RESULT — Stage 2 일곱 현상·현상당 2시간 연구 파일럿 준비

- 날짜: 2026-08-23
- 상태: `researcher_ready_no_listening_started`
- 대상: PT·NAN·NAL·NI·LLN·VH·HIA
- 성격: 문헌·범위·후보 환경·청취·수동 TextGrid 후속을 탐색하는 파일럿
- 금지선: 자동 실현 판정, 정식 realization ledger, query 동결, MFA·KOINA·wav2vec2 실행 없음

## 1. 결론

일곱 현상 모두에 대해 현상당 120분, 12사례의 연구 파일럿을 시작할 수 있는
단일 묶음을 만들었다. 각 현상은 2020–2025년에서 연도별 2사례이며, 기본
순서는 같은 형태소 조합·표면 단어순이고 두 번째 확인은 결정적 셔플 순서다.

연구 화면은 한 번에 한 사례만 보여 준다. 화면 안에서 문헌 근거, 형태소 정보,
화자·대화 정보, 전체 대화 전사 검색, 발화 WAV, 읽기 전용 6-tier TextGrid,
범위·실현 확신도 1–5, 연구 메모, Praat 수정 필요성을 함께 기록할 수 있다.
기록은 탐색용 append-only JSONL이며 정식 판정 ledger와 분리된다.

시작 파일:

`outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/researcher_review_package_v1/START_HERE.html`

## 2. 2시간 운영 계약

| 순서 | 시간 | 할 일 | 남기는 것 |
|---|---:|---|---|
| 1 | 20분 | 핵심 문헌 주장·근거 한계 읽기 | 현상 전체 문헌 메모 |
| 2 | 10분 | 중심·주변·탐색·제외·confound 확인 | 범위 메모 |
| 3 | 60분 | 12사례 청취·환경 검토 | 사례별 탐색 기록 |
| 4 | 20분 | 불확실 사례 재확인·Praat 필요 표시 | 후속 작업 표시 |
| 5 | 10분 | 잠정 패턴·질문 정리·JSONL 저장 | 파일럿 요약 |

총계는 7현상 × 120분 = 840분이다. 이는 사용자의 청취 완료를 뜻하지 않으며,
이번 작업에서는 연구자 판정이나 TextGrid 수정을 시작하지 않았다.

## 3. 문헌·범위 근거

- 범위 카드: 7행, SHA-256
  `7f869f0ac3c44a1692b63db4d945314c54973f86c26a7fb048f491b89ed41683`
- 문헌 claim ledger: 156행, SHA-256
  `1e88f5513f4c57387954d6149d922ccfc20ad024cfb8df63d492d96e0924610a`
- source inventory: 362행, SHA-256
  `e8de6907f632a5b64853a6386c7d510ba69852451322630dc43ea201fefa0680`
- reviewer에 포함한 직접 claim 요약: 85행. 각 행은 `CLM-####`·`SRC-###`,
  적용 범위, 확립하지 않는 것, 검토 질문과 페이지를 함께 표시한다.
- 범위 감사:
  `outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/scope_cards/AUDIT_two_hour_scope_cards_20260823.json`

## 4. 후보 실측과 zero-drop

보수적 candidate query 16개를 표·연도별 200,000행, query·연도별 후보 50행
상한으로 probe했다. 최초 결과는 query hit 2,300행 = 후보 회계 2,300행으로
zero-drop이었고, 2,236개 미선택 후보도 상태와 함께 보존했다.

- 최초 선택: 64사례
- 충분: HIA·LLN·NAN·NI·VH 각 12, NAL 3
- 부족: PT 1, NAL 9
- 실측 열: `morph_boundaries` 35열, `orth_eojeol_tokens` 13열
- 실측·manifest 결속:
  `outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/query_probe/P2H_SOURCE_MEASUREMENTS.json`
  — 19,744 bytes, SHA-256
  `50f72f3ba4da6401155ed9cfbd10a987fe1f099cdd7d92569823083ddd67ce7b`
- 후보 회계:
  `outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/query_probe/P2H_CANDIDATE_ACCOUNTING.csv`
  — 2,300행, SHA-256
  `bac1ca3f802f7b39225132e0039dda1b5e13f25a2132f3aafe79b94126993e70`

PT 부족분은 `morph_units`의 실제 39열 헤더를 확인한 뒤 연도별 조기 중단으로
300개 명사 내부 probe를 회계했다. 연도별 스캔 행 수는 856·1,092·914·
1,337·705·692이며 어느 연도도 200,000행 상한에 닿지 않았다. 300행 가운데
12행을 사용하고 288행은 미선택 상태로 보존했다. 이 12행은 합성어성이 확인된
중심 PT가 아니라 모두 `pending_manual_compound_boundary`다.

NAL은 기존 PV-A의 exact-ID·시간 연결 완료 환경을 재사용했다. 최초 보충본에서
2022년 동일 물리 발생을 두 번 고르는 선택기 결함을 발견했다. 기존 보충본은
증거로 보존하고, 연도 내 `used_refs`를 다시 검사하도록 고친 v2를 별도 생성했다.
v2의 현상 내부 중복은 0이다.

## 5. NI 범위 정정

최초 84행에는 NI의 VCP branch 두 행이 포함돼 있었다.

- `모습이에요`: 표면 접미부 `이에요`
- `전용이라서`: 표면 접미부 `이라서`

둘 다 표면에 실제 `이`가 나타나므로 사용자의 확정 규칙에 따라 NI에서 제외하고
각각 같은 연도(2024·2025)의 중심 NI 후보로 교체했다. 입력 84행은 82 retained +
2 explicit excluded로 모두 회계했으며 교체 2행을 별도 기록했다.

표면 `요`+분석 `이/VCP+요`는 계속 별도 탐색 모집단에 보존하는 규칙이다. 이번
VCP 후보 상한 300행에서는 이 유형으로 확정할 수 있는 행이 0개였고, 표면 `이`
확정 163행·왕복 불확실 137행은 후보 회계에서 삭제하지 않았다.
미래의 깨끗한 재실행에서는 VCP 행을 모두 회계하되 표면 `왼쪽 형태소+요`가
확인된 행만 표본 선택에 들어가도록 selector도 같은 규칙으로 보강했다.

최종 표본:

`outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/ni_scope_correction_v2/P2H_SAMPLES_FINAL_V2.csv`

- 84행
- 현상별 12행
- 현상×연도별 2행
- 고유 발화 82개(현상 간 중복 membership 2건 허용)
- NI 선택 VCP branch 0행
- SHA-256
  `8043eb2564e041881051cad4c8f92370b061b363572ad8a4afb21c2e33eaca9f`

정정 감사:

`outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/ni_scope_correction_v2/P2H_NI_SCOPE_CORRECTION_RECEIPT.json`

SHA-256 `8ceaadc717989f131dea6abf8d437c327cbd010deed7e1e51a0bd6ec241c259d`.

## 6. 연구자 검토 묶음

묶음 경로:

`outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/researcher_review_package_v1/`

| 항목 | 실측 |
|---|---:|
| 사례 | 84 |
| 현상 | 7 |
| 고유 발화·전체 대화 key | 82 |
| 포함 대화 전사 행 | 26,311 |
| 문헌 claim 요약 | 85 |
| 발화 WAV exact copy | 84 |
| source TextGrid 보존 copy | 84 |
| Praat 수정 작업본 | 84 |
| SHA manifest 기록 | 260 |
| WAV 합계 | 8,497,972 bytes |
| 묶음 전체 | 24,719,256 bytes |

WAV는 자르거나 재인코딩하지 않았다. source·bundle WAV SHA와 source·보존
TextGrid·초기 Praat 작업본 SHA는 모두 일치했다. `praat_work`의 TextGrid만
연구자가 수정하며 WAV는 수정하지 않는다.

전체 대화의 `derived turn`은 같은 화자의 연속 전사 단위를 묶은 탐색 표지다.
원자료의 금표준 turn annotation으로 해석하지 않으며, 화면에서 끊겨 보이는
현상은 원 전사 단위 분절 때문일 수 있음을 명시했다.

## 7. 독립 검증

독립 감사 결과:

`outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/reviewer_package_audit_v1/AUDIT_STAGE2_TWO_HOUR_REVIEWER.json`

- `passed=true`
- 감사 JSON SHA-256
  `72a02430b212b8e31d6b4a8014bc4340667c977dbb486d1ee2ceae15c9c8a40d`
- package SHA manifest 260건 전수 일치
- package manifest SHA-256
  `08af27c2b48a822fe96a7745d2b4e40ab983a5c1410d21ab6f271c7c530bffad`
- reviewer HTML SHA-256
  `2ef29c79cb676cbf71efb1859ac38ab5e4d43ad5df4e1c62f4b364d02fc2992f`
- `.ps1` 첫 3바이트 `EF BB BF`, Windows PowerShell 5.1 parse 통과
- 프로젝트 PowerShell safety/runtime 73개 통과
- Python `py_compile` 7개 통과
- Python unittest 24개 통과
- 실제 Node JavaScript 구문·내장 데이터 왕복 통과
- 기존 출력 존재 시 중단 7시나리오 통과

검증 로그:

`outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/validation_logs_v2/`

| 로그 | bytes | SHA-256 |
|---|---:|---|
| `PYTHON_VALIDATION.log` | 39,274 | `e00ea021176ed01d4b527d62ca66d21e292f4d3b9225006b9d82bbaa693b0c00` |
| `RUNTIME_AND_POWERSHELL_VALIDATION.log` | 329 | `f6c64dc6fb7be630c78d46c485708a1728f8ac449b7b792a82370bf64de93068` |
| `EXISTING_OUTPUT_REFUSAL.log` | 2,520 | `f6cb30219cd5934679c5febe3e958d427baf8ec7b805cde7b638bf04e4a49ad6` |

## 8. 안전 확인

- D: 원자료·검색 표·r3 6-tier·RC0/RC1·동결 query·기존 G1–G4를 수정하지 않았다.
- MFA·KOINA·wav2vec2·대량 음성 변환을 실행하지 않았다.
- 원천 표 스캔은 연도·표별 200,000행 상한을 넘기지 않았다.
- 자동 실현 판정과 정식 ledger 쓰기를 하지 않았다.
- 후보·표본 누락과 제외는 모두 상태·감사 행으로 보존했다.
- 기존 산출물을 덮어쓰지 않고 `.partial` 디렉터리 승격과 SHA manifest를 썼다.
- git commit·push는 하지 않았다.

## 9. 남은 연구자 작업과 한계

1. `START_HERE.html`을 열고 한 현상만 선택한다.
2. 화면의 20→10→60→20→10분 순서를 따른다.
3. 세션마다 `P2H_EXPLORATORY_REVIEWS.jsonl`을 저장한다.
4. 경계 수정 필요 사례만 `open_praat_sample.ps1 -SampleId <ID>`로 열어
   `praat_work` TextGrid를 수정한다. 이 컴퓨터에서는 `praat.exe`가 PATH에서
   발견되지 않았으므로 필요하면 `-PraatExe 'C:\...\Praat.exe'`를 지정한다.
5. PT 12건은 합성어성 확인 전 모두 probe다. 이를 중심 PT 실현 자료로 해석하면
   안 된다.
6. 이번 상한 안에서 표면 `요`/분석 `이+요` NI 사례는 선택되지 않았다. 규칙은
   보존되어 있지만 별도 탐색 확장은 이후 사용자 승인 사항이다.
7. 앱 브라우저 자동 시각 점검은 로컬 신뢰 경로 오류로 수행하지 못했다. 독립
   HTML 구조 감사와 실제 Node 런타임 검사는 통과했으나, 사용자의 첫 화면 확인은
   여전히 필요하다.

이 단계의 완료는 연구 실행 준비 완료다. 사용자의 청취·Praat 수정·해석이 끝난
뒤에만 현상별 RESULT와 후속 exact-ID queue를 작성한다.
