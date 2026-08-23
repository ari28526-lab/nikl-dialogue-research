# RESULT — Stage 2 2시간 파일럿 reviewer v2 재빌드

- 날짜: 2026-08-23 KST
- 승인 근거:
  `DECISION_stage2_two_hour_pilot_external_review_responses_20260823.md`
- 상태: **v2 빌드·독립 감사·자동 브라우저 스모크 통과, 7개 현상 작업 환경 세팅 완료**
- 연구 Gate: 세팅·커밋·배포는 완료할 수 있다. 실제 첫 연구 세션에서는
  페이지 열림과 오디오 재생만 환경별로 짧게 확인한다.

## 1. 산출물

- v2 패키지:
  `outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/researcher_review_package_v2/`
- v2 패키지 SHA manifest:
  `9a9c0ae7880971c32b16f33f1e3511bdf8d4da64d7560a86b5a3deee313356a1`
- 독립 감사 JSON:
  `outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/reviewer_package_audit_v2/AUDIT_STAGE2_TWO_HOUR_REVIEWER.json`
- 감사 JSON SHA-256:
  `3c0026fbd19d4e11a6627c47eedd9c549eba07fa8546b984016f9f1c597feacf`
- 검증 로그:
  `logs/stage2_two_hour_reviewer_v2_rebuild_20260823/`

## 2. A–H 구현 결과

| 항목 | 구현 |
|---|---|
| A | `START_HERE.html`의 7개 링크를 내장 literature의 `label_ko`에서 생성하고, 이 literature가 scope card의 `label_ko`와 전건 일치하는지 빌드·감사에서 확인한다. 구 `LABELS` 별도 상수는 제거했다. |
| B | 사례 이력을 `reviewRows()`로 개명하고 `window.history.replaceState`를 명시했다. 현상 드롭다운은 목록·본문·진행 표시·URL을 함께 바꾼다. |
| C | 오디오 옆 `표적 구간으로 이동` 버튼을 추가했다. 오디오가 준비됐으면 즉시 `currentTime=target_xmin`, 준비 전이면 `canplay` 뒤 같은 이동을 수행한다. |
| D | 문헌 메모는 입력 즉시 현상별 `_lit_` localStorage 키에 저장하며 사례 폼의 dirty를 세우지 않는다. 현상 요약 버튼은 `stage2_two_hour_phenomenon_summary.v1`·`phenomenon_summary_exploratory_only_not_formal_ledger` 행을 현상별 revision 체인으로 append한다. 현상 행에는 `sample_id`를 넣지 않으며 사례 집계에서 제외한다. import는 현상 행을 수용하고, 메모 복원은 localStorage → import 최신 summary → 최신 사례 행 순서다. |
| E | shuffled에서 최신 사례 행이 grouped 저장분이면 `realization_impression`과 `realization_confidence`만 비운다. 최신 shuffled revision은 그대로 복원하며 선별 재확인 기준 배너를 표시한다. |
| F | 환경·청취 확신도에 5 단서 명확·재청취 불필요 / 4 단서 우세 / 3 단서 있으나 상충 / 2 인상 수준 / 1 추측 앵커를 표시하고 저장값 1–5는 유지했다. |
| G | README·START_HERE에 Praat 기준, 선별 재확인 기준, 절차 규칙 6건을 반영했다. 사례 폼의 `boundary_edit_need`에도 기준 힌트를 추가했다. |
| H | import 전체를 try/catch로 감싸 JSON·ID 오류를 `불러오기 실패 — 행 n`으로 표시한다. 성공 직전까지 `imported`를 대입하지 않으므로 실패 시 기존 import 상태가 유지된다. |

## 3. C:-only 재빌드와 불변성

이번 v2는 `D:` 원자료를 다시 읽지 않았다. 빌더에 C:의 검증된 v1을 입력으로
삼는 `--repackage-from` 경로를 추가했다. 이 경로는 v1 manifest 260건을 먼저
전수 검증한 뒤 자산·내장 데이터를 재사용하고 화면·라벨·패키지 문서·영수증·
manifest만 다시 만든다.

- 동결 samples SHA-256:
  `8043eb2564e041881051cad4c8f92370b061b363572ad8a4afb21c2e33eaca9f`
- v1 manifest SHA-256은 빌드 전후
  `08af27c2b48a822fe96a7745d2b4e40ab983a5c1410d21ab6f271c7c530bffad`로 같다.
- v1 BUILD_RECEIPT SHA-256은 빌드 전후
  `c403b94f447e64b9d6e6b1b57db2f9d549551193b0fe47c8d8bf190561c05771`로 같다.
- v1 대 v2의 samples·dialogues·metadata·literature·textgrids 내장 JSON은
  의미적으로 전부 같다.
- `ASSET_MANIFEST.csv`, `PRAAT_TASKS.csv`,
  `DIALOGUE_SOURCE_RECEIPTS.json`, `open_praat_sample.ps1`은 v1과 바이트가 같다.
- query 16종·probe·표본 84행·문헌 claim·config 기존 파일은 수정하지 않았다.
- MFA·KOINA·wav2vec2·자동 실현 판정·연구자 청취·Praat 수정은 0건이다.

## 4. 검증 결과

- Python `py_compile`: builder·auditor·Python test 통과
- Python test: 7/7 통과
- Node runtime: 구문 컴파일 + 정적 회귀 + 최소 DOM 실행 스모크 통과
  (`domSmoke=true`)
- 독립 감사: `passed=true`, manifest 260, 자산 84, Praat 작업 84,
  표본 84, 대화·메타 82, 문헌 코드 7, TextGrid projection 84
- 감사 신규 검사: A·B·C·D·E·F·H와 v1 데이터/자산 불변성 전부 통과
- 실제 브라우저:
  - START_HERE 7개 라벨이 scope card와 일치
  - PT → NAN 드롭다운 전환 뒤 URL `?phenomenon=NAN`, 본문 `1/12 · NAN`,
    진행 표시 `ㄴ 앞 비음화 · 저장된 청취 0/12`, 콘솔 오류 0
  - 표적 점프 3건:
    `P2H-PT-2022-02` 2.070초,
    `P2H-PT-2024-01` 0.430초,
    `P2H-PT-2024-02` 1.910초
  - shuffled 재확인 배너 표시 확인

Python 기본 정적 서버는 WAV HTTP Range를 지원하지 않아 첫 브라우저 점검에서
`seekable=0`이 재현됐다. C: 작업 폴더의 표준 라이브러리 Range 테스트 서버로
실사용 가능한 seek 범위를 제공한 뒤 위 3건을 확인했다. 중간 패키지·감사·로그는
실패 증거로 이름을 바꾸거나 후보 이름 그대로 보존했고 자동 삭제하지 않았다.

## 5. 2026-08-24 사용자 운영 방식 확인

사용자가 준비하려는 것은 지금 일곱 현상을 모두 깊이 검토하는 것이 아니라,
나중에 시간이 날 때 바로 시작할 수 있도록 **일곱 현상의 작업 환경을 전부
미리 세팅하는 것**이다.

- PT·NAN·NAL·NI·LLN·VH·HIA 각각 12건, 총 84건과 현상별 문헌 패널 7개가
  정식 v2에 들어 있다.
- 기존의 '수동 게이트 7항'은 프로그램의 기술 QA 목록이지 현상 7개의 연구
  판정 목록이 아니다. 해당 동작은 Python·Node·독립 감사·실브라우저 스모크로
  검증했으며, 사용자가 지금 반복 수행할 필요가 없다.
- 실제 검토는 나중에 시간이 날 때 한 현상씩 진행해도 다른 여섯 현상의 세팅은
  그대로 유지된다.
- 첫 실제 사용 때는 해당 컴퓨터에서 페이지가 열리는지와 오디오가 재생되는지만
  짧게 확인한다. 문제가 있을 때만 기술 QA 항목을 다시 좁혀 점검한다.
- 현상 정의·포함/제외 기준·문헌 해석은 연구자 판단에 따라 바꿀 수 있도록
  `candidate` 상태를 유지한다.
