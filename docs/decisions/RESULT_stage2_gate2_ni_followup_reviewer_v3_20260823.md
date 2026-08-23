# 결과: Stage 2 Gate 2 NI 후속 TextGrid reviewer v3 구현

- 기록일: 2026-08-23 KST
- 사용자 승인: `Gate 2 구현 GO`
- 구현 상태: **완료**
- 독립 감사 상태: **통과**
- 연구자 화면 Gate: **미실시 — Gate 3 전 확인 필요**
- Gate 3·실제 청취·정식 판정: **시작하지 않음**

> **2026-08-23 사후 정정:** NI 두 표본 `PV0015`, `PV0163`은 모두
> `편/NNB + 이/VCP`로 확인되었다. 사용자 결정에 따라 VCP 서술격 `이`는
> NI 본모집단에서 제외한다. 따라서 아래 두 건의 화면 시험은 UI 기능 검증으로만
> 유효하며 NI 연구 내용 표본 검증으로는 무효다. 근거와 후속 정지선은
> `docs/decisions/DECISION_stage2_NI_VCP_copula_exclusion_20260823.md`를 따른다.
> 단, 표면에는 `요`만 있고 형태소 분석에서만 `이+요`가 복원되는 사례는 이
> 제외 규칙의 예외이며 별도 `요` 탐색 모집단에 보존한다. 현재 두 표본은 표면에
> `이`가 실제로 나타나므로 이 예외에 해당하지 않는다.

## 1. 결론

승인된 Gate 2 범위 안에서 reviewer v3를 만들었다. 기존 v2.1 표본 14개를
zero-drop으로 모두 보존했으며, 빌드 당시 NI 2개를 방법론 기준 표본으로
표시했다. 사후 형태소 확인에서 이 두 건이 모두 VCP 범위 밖 사례임이 밝혀졌기
때문에 현재는 14개 전부를 UI 회귀 증거로만 취급한다.

연구자는 각 사례에서 `TextGrid 후속 검토 필요성`, 복수 이유, 추가 정보 요청,
자유 메모, 1–5 확신도를 기록할 수 있다. `필요` 또는 `불확실`을 고르면 현재
6-tier TextGrid와 파형 패널이 자동으로 열린다. 패널은 read-only이며 원
TextGrid·WAV·경계·label을 수정하지 않는다.

## 2. 구현 파일

- `scripts/python/build_stage2_gate2_ni_followup_reviewer_v3.py`
- `scripts/python/audit_stage2_gate2_ni_followup_reviewer_v3.py`
- `tests/test_stage2_gate2_ni_followup_reviewer_v3.py`
- `tests/test_stage2_gate2_ni_followup_reviewer_v3_runtime.js`
- `scripts/run_stage2_gate2_ni_followup_reviewer_v3.ps1`

Wrapper는 Windows PowerShell 5.1 호환, CRLF, UTF-8 BOM(`EF BB BF`)으로
검증했다. `-PreflightOnly`는 출력과 연구 기록을 만들지 않는다.

| 구현 파일 | 행 수 | SHA-256 |
|---|---:|---|
| `build_stage2_gate2_ni_followup_reviewer_v3.py` | 775 | `e7aea491e916f1b732aa698b9b3a8a406d27a3b5808da50232384c1bf103a832` |
| `audit_stage2_gate2_ni_followup_reviewer_v3.py` | 456 | `4aa5d5dd61ae0dd3020793cc0c76a575a155d96841c8e1636f6ae49f733f21c5` |
| `test_stage2_gate2_ni_followup_reviewer_v3.py` | 146 | `a0f2b919805f16ac29831984881303704bc9a37213f27d5f40d786d8dae09741` |
| `test_stage2_gate2_ni_followup_reviewer_v3_runtime.js` | 121 | `53d4f9fe6bf198b06904085a561b6f1f1d573af690fa569a5f6100d7cdeaeaa4` |
| `run_stage2_gate2_ni_followup_reviewer_v3.ps1` | 47 | `1130a0d33dfdcbcc2ec6fe8bc9829ddaedf2b424954b5d56e17ff709d4f0ebf5` |

## 3. 산출물과 SHA-256

출력 디렉터리:

```text
outputs/pilots/stage2_gate2_ni_followup_reviewer_v3_20260823/
```

| 파일 | 바이트 | SHA-256 |
|---|---:|---|
| `STAGE2_GATE2_NI_REVIEWER_V3.html` | 19,637,021 | `f361c1c8559315399af2f368ebfcff9b99d83b8c14fa726e6e7a40fea435f057` |
| `STAGE2_GATE2_NI_REVIEWER_V3_BUILD.json` | 15,399 | `aa605d2dc7c0da37107854251bef0bdefddf1d8344babe8d88cc5b94857281d7` |
| `STAGE2_GATE2_NI_REVIEWER_V3_IMPORTED_BASE.jsonl` | 12,028 | `8a7d913af97ef903be941f726dbe73d78271384c6add246cdc52fe8df7de6133` |
| `STAGE2_GATE2_NI_REVIEWER_V3_DIALOGUES.jsonl` | 7,792,634 | `990c1098448d58107e375d868eb4e8593e14ea150fdc2e73938e22c0919b39ae` |
| `audit/STAGE2_GATE2_NI_REVIEWER_V3_AUDIT.json` | 2,360 | `0a565bb109734f08a9250f568518662f4d32ba910390f406e5f541c7ed0f499e` |

SHA manifest:

```text
outputs/pilots/stage2_gate2_ni_followup_reviewer_v3_20260823/SHA256SUMS_stage2_gate2_ni_followup_reviewer_v3_20260823.txt
```

Manifest 5행을 다시 해시해 SHA·바이트 불일치 0건, 자기 자신 포함 0건,
`.partial` 잔존 0건을 확인했다.

## 4. 독립 감사 결과

감사 JSON:

```text
outputs/pilots/stage2_gate2_ni_followup_reviewer_v3_20260823/audit/STAGE2_GATE2_NI_REVIEWER_V3_AUDIT.json
```

`passed=true`, `errors=[]`이다.

| 감사 항목 | 결과 |
|---|---:|
| 입력 = 출력 | 14 = 14 |
| 빌드 당시 NI 방법론 기준 역할 | 2 (`PV0015`, `PV0163`) — 사후 VCP 범위 밖 판정 |
| 비NI 공통 UI 회귀 전용 | 12 |
| TextGrid available / unavailable / blocked | 14 / 0 / 0 |
| 독립 자산 검증 | 14/14 |
| tier 수·순서 | 각 6, 전부 일치 |
| 기존 기록 | 15행 / 고유 event 14 |
| 대화 행 | 4,060 |
| 내장 WAV / 원본 SHA 일치 | 28 / 28 |
| 새 후보 추출 | 0 |
| G5/G6 실행 | 0 |
| 정식 수동 task 생성 | 0 |
| 자동 실현 판정 | 0 |
| 정식 ledger 쓰기 | 0 |

## 5. 검증 결과

- Python `py_compile`: 통과
- Python 단위 시험: 7/7 통과
- JavaScript runtime 시험: 통과
- Windows PowerShell 5.1 안전 시험: 73개 파일 통과
- Windows PowerShell 5.1 runtime compatibility: 73개 script 통과
- wrapper `-PreflightOnly`: 통과
- 실제 생성 뒤 같은 경로 재실행: `FileExistsError`로 예상대로 중단
- `git diff --check`: 통과
- 보호 원자료·r3·6-tier·동반표·문헌 workspace 수정: 0건

검증 로그 디렉터리:

```text
logs/stage2_gate2_ni_followup_reviewer_v3_20260823/
```

앱 내 브라우저 자동 DOM 점검은 설치된 browser plugin의 trusted-code-path
연결 오류로 실행하지 못했다. 이는 reviewer 런타임 실패와 구분했다. 동일 내장
JavaScript는 독립 runtime 시험을 통과했으며, 실제 기록을 자동 저장하지 않았다.

## 6. 연구자가 지금 확인할 것

아래 HTML을 열고 상단 현상 필터에서 `NI`만 선택한다.

```text
outputs/pilots/stage2_gate2_ni_followup_reviewer_v3_20260823/STAGE2_GATE2_NI_REVIEWER_V3.html
```

NI 두 건에서 다음만 시험한다.

1. 한 건은 `필요`, 다른 한 건은 `불필요` 또는 `불확실`로 고른다.
2. `필요/불확실`에서 패널이 자동으로 열리고 파형·표적 span·6개 tier가
   보이는지 확인한다.
3. 추가 정보 요청 1개와 1–5 확신도를 임시로 넣는다.
4. 저장한 전체 history JSONL을 내보낸 뒤 다시 가져와 같은 후보에 복원되는지
   확인한다.
5. `Gate 3 queue candidate` 내보내기에 최신값이 `필요/불확실`인 사례만
   들어가는지 확인한다.

이 다섯 동작은 도구 시험이다. 실제 발음 실현 판정이나 정식 연구 ledger
기록으로 사용하지 않는다.

## 7. 정지선

Gate 2 UI 구현과 독립 기술 감사까지만 완료했다. 유효한 NI 내용 표본 Gate는
VCP 제외를 반영한 대체 표본으로 다시 확인해야 한다. NI 어절 간 새 표본, G5/G6, 보조사
`요` query, Praat 작업본 생성·반입, 다른 여섯 현상 계약, Gate 3 정식 task,
실제 청취 및 공개 파생본은 시작하지 않았다. 연구자 화면 Gate 결과를 받은 뒤
다음 단계를 별도로 결정한다.
