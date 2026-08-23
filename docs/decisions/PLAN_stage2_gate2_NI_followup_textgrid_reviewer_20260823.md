# 계획: Stage 2 Gate 2 NI 후속 TextGrid 검토 필요성 reviewer

- 작성일: 2026-08-23 KST
- 상태: **설계안 — 구현 미승인**
- 적용 순서: Gate 0 채택 → Gate 1 NI frozen v1 완료 → **현재 Gate 2 설계**
- 구현 정지선: 사용자가 `Gate 2 구현 GO`를 주기 전에는 코드·출력 reviewer를 만들지 않는다.

## 0. 먼저 읽을 결론

이번 단계는 ㄴ삽입의 실제 발음을 판정하는 단계가 아니다. 각 후보를 들은 뒤
**“기존 TextGrid를 더 확인하거나 나중에 Praat에서 손볼 필요가 있는가?”**만
기록하는 연구 전 준비 단계다.

가장 단순하고 안전한 방법은 이미 화면 검증을 마친 reviewer v2.1의 14개 표본을
그대로 재사용해 read-only TextGrid 패널과 후속 요청 필드만 붙이는 것이다.
14개 중 NI는 2개이며, 나머지 12개는 공통 화면의 기술 회귀 시험에만 사용한다.
나머지 현상의 연구 계약이나 query를 채택하는 근거로 사용하지 않는다.

구현 뒤 연구자가 먼저 할 일도 많지 않다. NI 두 표본에서 다음 세 동작만
확인하면 된다.

1. `필요` 또는 `불확실`을 누르면 같은 화면의 TextGrid 패널이 자동으로 열린다.
2. 저장한 뒤 JSONL을 내보내고 다시 가져오면 같은 후보에 복원된다.
3. 필요한 사례만 “Gate 3 작업 후보 queue”로 별도 내보내진다.

## 1. 왜 이것이 다음 단계인가

승인된 일곱 현상 workflow의 순서는 다음과 같다.

```text
Gate 0 공통 구조
  → Gate 1 NI 계약 동결
  → Gate 2 후속 TextGrid 검토 필요성 표시·read-only 확인  ← 지금 여기
  → Gate 3 필요한 사례만 Praat 작업본·overlay·가변 sidecar 왕복
  → Gate 4 승인 ledger·공개 파생본
  → Gate 5 LLN부터 다른 현상 확대
```

따라서 LLN이나 NI 어절 간 대규모 후보로 바로 넘어가지 않는다. Gate 2에서
연구자가 후보를 보며 필요한 후속 작업을 잃지 않고 기록할 수 있는지를 먼저
검증한다. `D-G1-C`의 probe 보강은 LLN 착수 전까지 결정하면 되는 비차단 항목이라
Gate 2를 막지 않는다. 보조사 `요`도 이미 “본모집단 밖 별도 탐색 query 후보”로
결정됐으므로 이 단계에서 다시 묻지 않는다.

## 2. 용어를 쉬운 말로

| 용어 | 이 계획에서 뜻하는 것 |
|---|---|
| Gate | 다음 연구 단계로 넘어가기 전에 통과해야 하는 작은 검문소 |
| candidate/후보 | 현상이 나타날 형태·표기 환경을 만족해 검토 대상으로 뽑힌 한 사례 |
| occurrence/exact-ID | 같은 발화 안에서도 어느 위치의 후보인지 다시 찾을 수 있는 정확한 식별자 |
| TextGrid | 발화의 단어·음소·형태소 정보와 시간 경계를 여러 줄(tier)로 표시한 파일 |
| read-only | 화면에서 볼 수만 있고 원본 경계·label은 바꿀 수 없음 |
| queue | 다음 Gate에서 실제 수동 작업본을 만들 후보 목록. 작업본 자체는 아님 |
| sidecar | 원자료를 바꾸지 않고 추가 정보·상태를 옆의 별도 파일에 기록하는 방식 |
| zero-drop | 후보를 조용히 지우지 않고, 미검토·필요·불필요·자산 부재 등의 상태로 전부 회계하는 원칙 |
| SHA-256 | 파일 내용이 같은지 확인하는 64자리 지문. 경로나 파일명이 같아도 내용이 바뀌면 달라짐 |

## 3. 시작 전 실측 근거

### 3.1 재사용할 reviewer와 표본

| 실측 항목 | 결과 |
|---|---:|
| PV-A `PV_SAMPLES.csv` 데이터 행 | 180 |
| PV-A bundle의 `.TextGrid` 파일 | 180 |
| reviewer v2.1 표본 | 14 |
| 현상별 구성 | PT·NAN·NAL·NI·LLN·VH·HIA 각 2 |
| 연도별 구성 | 각 현상 2020년 1 + 2025년 1 |
| reviewer v2.1 기존 기록 | 15행 / 고유 review event 14 |
| NI 표본 | `PV0015`(2020), `PV0163`(2025) |
| 선택 14개 TextGrid 존재 | 14/14 |
| package 선언 SHA = bundle 실파일 SHA | 14/14 |
| bundle SHA = `active_textgrid_sha256` | 14/14 |
| 6-tier 이름·순서 일치 | 14/14 |

실측한 6-tier는 다음과 같다.

```text
words / phones_mfa / phoneme_r_auto / utterance /
utterance_orth_r / morph_analysis_utt
```

NI 두 표본은 모두 `intra_eojeol`이며 연결 시간은 다음과 같다.

| pv_id | 연도 | target span(초) | timing_status |
|---|---:|---:|---|
| PV0015 | 2020 | 1.26–1.59 | linked_single_eojeol_context_span |
| PV0163 | 2025 | 3.93–4.36 | linked_single_eojeol_context_span |

즉, 이번 2건으로 **화면과 저장 방식**은 시험할 수 있지만 NI 어절 간 환경의
연구 표본성을 평가할 수는 없다. 어절 간 모집단은 삭제된 것이 아니라 후속
G5/G6 층화 표본 단계에 남아 있다.

### 3.2 파일 지문

| 파일 | SHA-256 |
|---|---|
| `outputs/pilots/pv_seven_phenomena_20260819/samples/PV_SAMPLES.csv` | `31bea32b1cd44f5e9e77baa84259a6fa3566a192f866a5b006371700fa1fe93f` |
| `outputs/pilots/pv_seven_phenomena_20260819/PV_MANIFEST.json` | `acb8772e1f4ab8860ebc0631517f616eeb2b2e0f5eeb8e1d890abf462248ad51` |
| `outputs/pilots/pv_seven_phenomena_reviewer_v2_1_20260822/PV_REVIEWER_V2_1.html` | `4ac9edd77fd8889aaeb73b8c15afc6c2ee1a3c0eb5cca1e4d2b24e862da98a7e` |
| `outputs/pilots/pv_seven_phenomena_reviewer_v2_1_20260822/PV_REVIEWER_V2_1_BUILD.json` | `3db5b74367a43a2f79babfdc67f6700e0e5a06105da112321823dcb631955a7c` |
| `outputs/pilots/pv_seven_phenomena_reviewer_v2_1_20260822/audit/PV_REVIEWER_V2_1_AUDIT.json` | `3a47c2e3509dae16852ff90dcf295ddc602c89f6773e0198a9e9e700b242fc78` |
| `config/stage2_zero_drop_status_dictionary.v1.json` | `f87a5684d4c7f21752ad9c4c023c28264471436eae9885a93cbd7a34e601c173` |
| `config/stage2_additional_information_sidecar_schema.v1.json` | `b1992e21f9431e5d066e396264eb61b89dff652d950f4e6fa7a6bb9d1b14c3f3` |

## 4. 승인 요청 구현 범위

### 4.1 표본 범위

- 새 후보를 추출하지 않는다.
- v2.1의 14개를 모두 보존한다.
- NI 2개는 Gate 2 방법론 기준 표본이다.
- 나머지 12개는 공통 UI·자산 처리 회귀 표본일 뿐, 해당 현상의 query·환경
  분류·연구 우선순위를 동결하지 않는다.
- 실제 사용자 최소 확인은 NI 필터를 켜고 두 건만 해도 된다.

이 선택은 새 NI 층화 표본을 만들기 위해 G5/G6를 앞당기지 않으면서도, 이미
사용자가 확인한 14개 화면과 저장 기록을 그대로 회귀 시험할 수 있다는 장점이
있다.

### 4.2 새 입력 필드

| 필드 | 화면 문구·값 | 역할 |
|---|---|---|
| `textgrid_review_need` | 불필요 `not_needed` / 필요 `required` / 불확실 `unsure` | TextGrid 후속 확인 필요성 |
| `textgrid_review_reasons_json` | 경계 / label / 전사 / 표적 span / 기타(복수 선택) | 왜 필요한지 |
| `additional_information_requests_json` | 정보명·필요 이유를 여러 행 추가 | 운율·의미번호·화자 정보 등 나중에 확인할 것 |
| `followup_note` | 자유 메모 | 위 구조로 담기 어려운 내용 |
| `followup_need_confidence` | 1–5 | **후속 검토 필요성 판단**의 확신도 |

기존 `judgement_confidence`는 “들린 형식·실현 인상”의 높음/중간/낮음이다.
새 1–5 척도와 의미가 다르므로 덮어쓰거나 재사용하지 않는다.

추가 정보 요청은 Gate 2 기록 안에서는 JSON 배열로 보존한다. Gate 3가 열릴 때
독립 검사를 거쳐 `stage2_additional_information_sidecar.v1`의 append-only 행으로
변환한다. reviewer가 정식 sidecar나 ledger에 자동으로 쓰지 않는다.

### 4.3 TextGrid 패널

`required` 또는 `unsure`를 선택하면 같은 후보 화면에서 패널을 자동으로 연다.
저장 기록을 복원했을 때도 같은 조건이면 열린 상태로 복원한다.

패널에는 다음만 표시한다.

- 표적 WAV의 파형과 현재 재생 위치
- `target_xmin`–`target_xmax` 강조
- 기존 6개 tier의 label·경계 read-only 표시
- target 어절·형태소 검색 근거와 원 시간 좌표
- source TextGrid 식별자·SHA-256
- `textgrid_asset_status`와 `manual_task_status`
- 작업본이 생긴 뒤에는 마지막 revision 상태(현재는 `not_created`)

파형은 14개 bundle의 기존 `target.wav`에서 작은 표시용 peak 배열만 계산해
HTML에 넣는다. 원 WAV나 TextGrid를 수정하지 않고, 외부 라이브러리·모델·대량
음성 처리를 사용하지 않는다. tier를 클릭하면 음성 재생 위치만 이동하며 경계나
label은 편집할 수 없다.

### 4.4 자산 부재와 zero-drop

두 상태 축을 섞지 않는다.

```text
연구자 판단 축: textgrid_review_need = not_needed | required | unsure
자산 상태 축:   textgrid_asset_status = available | unavailable | blocked
작업 상태 축:   manual_task_status = not_created | queued | exported | returned | audited
```

예를 들어 연구자는 TextGrid 확인이 `required`라고 판단했지만 파일이 없어서
자산 상태가 `unavailable`일 수 있다. 이는 모순이 아니다.

아직 저장하지 않은 후보는 `textgrid_review_need`를 억지 기본값으로 채우지 않고
화면 회계에서 `not_reviewed`로 센다. 따라서 진행률은 다음처럼 축별로 검사한다.

```text
reviewed decision 3종 합 + not_reviewed = 입력 14
asset status 3종 합 = 입력 14
manual task status 5종 합 = 입력 14
```

실자료 14개는 현재 모두 `available`이다. `unavailable`/`blocked` 화면 분기는
실제 표본 상태를 거짓으로 바꾸지 않고 runtime test의 합성 fixture로 검증한다.
파일 부재·SHA 불일치·TextGrid parse 실패가 생겨도 후보를 삭제하지 않는다.

### 4.5 저장·가져오기와 queue

- 기존 15행 JSONL은 바이트 그대로 보존한다.
- schema가 없던 기존 행도 가져올 수 있다.
- 새 revision만 `pv_reviewer_event.v3`로 저장한다.
- 최신 revision은 v2.1과 같이 `reviewed_at`을 우선하고 동률일 때만 행 순서를
  tie-break로 사용한다.
- 미저장 변경 경고를 후보 이동·검색에 따른 자동 이동·JSONL 가져오기·창 닫기에
  모두 유지한다.
- 전체 history JSONL과 별도로, 최신값이 `required`/`unsure`인 사례만
  `Gate 3 queue candidate` JSONL로 내보낼 수 있게 한다.
- Gate 2 queue 행은 `record_role=exploratory_queue_candidate_not_manual_task`로
  명시한다. Gate 3 검증기가 이를 받아 정식 `task_id`를 부여하기 전에는 수동
  작업 묶음이나 ledger가 아니다.

## 5. 기존 “우선순위” 표시는 어떻게 처리하는가

현재 v2.1의 `priority_tier`는 14개 중 `core` 10, `exploratory` 4다. 이는
2026-08-19 PV-A 기술 표본을 만들 때의 태그이며, 사용자가 말한
“일반적인 형태론 환경을 먼저 보고 주변·저보고 환경을 줄이는 연구 우선순위”와
같지 않다.

따라서 Gate 2에서는 다음처럼 처리한다.

- `핵심/탐색`이라는 큰 배지와 정렬 필터로 사용하지 않는다.
- 필요하면 감사 패널에 `이전 PV-A 표본 태그(연구 우선순위 아님)`으로만 남긴다.
- 새 연구 우선순위는 Gate 1의 환경 유형이 실제 occurrence에 배정된 뒤 만든다.
- 같은 형태소 조합·단어별 묶기와 불확실 사례 재검토 정렬도 그때 구현한다.

NI 두 표본에 지금 임의로 `general_direct` 등을 붙이면 Gate 1의
`occurrence_assignment_status=not_started`를 조용히 우회하게 되므로 하지 않는다.

## 6. 구현 파일 allowlist 초안

사용자 GO 뒤 다음 범위만 만든다. 이름은 구현일이 바뀌면 실제 날짜를 사용한다.

```text
scripts/python/build_stage2_gate2_ni_followup_reviewer_v3.py
scripts/python/audit_stage2_gate2_ni_followup_reviewer_v3.py
tests/test_stage2_gate2_ni_followup_reviewer_v3.py
tests/test_stage2_gate2_ni_followup_reviewer_v3_runtime.js
scripts/run_stage2_gate2_ni_followup_reviewer_v3.ps1

outputs/pilots/stage2_gate2_ni_followup_reviewer_v3_20260823/
  STAGE2_GATE2_NI_REVIEWER_V3.html
  STAGE2_GATE2_NI_REVIEWER_V3_BUILD.json
  audit/STAGE2_GATE2_NI_REVIEWER_V3_AUDIT.json
  SHA256SUMS_stage2_gate2_ni_followup_reviewer_v3_20260823.txt

logs/stage2_gate2_ni_followup_reviewer_v3_20260823/
docs/decisions/RESULT_stage2_gate2_ni_followup_reviewer_v3_20260823.md
```

PowerShell wrapper는 Windows PowerShell 5.1 호환·UTF-8 BOM으로 만들고
`-PreflightOnly`를 제공한다. Python은 pipeline Python을 사용하고 기존 동명
출력이 있으면 `FileExistsError`로 중단한다. 모든 산출은 `.partial`에서 완성한
뒤 원자 승격한다.

## 7. 독립 검증과 합격 기준

### 7.1 정적·단위 시험

- 신규 Python `py_compile`
- Python 단위 시험: 성공, source SHA 불일치 실패, manifest 불일치 실패,
  TextGrid parse 실패의 `blocked` 보존, 기존 출력 존재 시 중단, manifest 자기 제외
- JavaScript runtime 시험: 자동 펼침, 1–5 복원, 복수 이유·정보 요청 왕복,
  queue 필터, legacy 15행 보존, 최신 revision 선택, 미저장 경고
- Windows PowerShell 5.1 안전·runtime compatibility 시험과 wrapper
  `-PreflightOnly`

### 7.2 실자료 감사

- 입력 표본 14 = 출력 표본 14
- NI 2 + 비NI 회귀 표본 12를 역할별로 명시
- TextGrid 14/14 존재·SHA 일치·6-tier 순서 일치
- target span이 WAV·TextGrid 시간 범위 안에 있음
- 기존 v2.1 WAV·대화·기존 기록 payload 불변
- 다른 현상 query·환경 계약 채택 0건
- 원본·bundle 자산 수정 0건
- 자동 실현 판정 0건, 정식 ledger 쓰기 0건
- `.partial` 잔존 0, SHA manifest 자기해시 0

### 7.3 사용자 최소 화면 Gate

구현·독립 감사 뒤 연구자가 NI 두 건으로 확인한다.

1. 한 건을 `required`, 다른 한 건을 `not_needed` 또는 `unsure`로 시험한다.
2. `required/unsure`에서 패널 자동 열림과 6-tier·표적 span을 확인한다.
3. 새 정보 요청 1개를 임시로 추가하고 1–5 확신도를 넣는다.
4. 저장 → JSONL 내보내기 → 재가져오기 복원을 확인한다.
5. queue candidate 내보내기에 `required/unsure` 최신 사례만 들어가는지 확인한다.

이는 도구 동작 시험이며 실제 실현 판정이나 정식 연구 ledger 기록이 아니다.

## 8. 이번 Gate에서 하지 않는 것

- G5/G6 실행이나 94만 후보 전수 스캔
- NI 새 층화 표본·어절 간 표본 생성
- 보조사 `요` query JSON 생성·동결
- 같은 형태소 조합·단어 기준 생산 정렬
- 다른 여섯 현상의 query·환경값 채택
- TextGrid 경계·label의 브라우저 편집
- Praat 작업본 실제 생성·반입(Gate 3)
- KOINA·MFA·wav2vec2 또는 자동 실현 판정
- 정식 ledger 쓰기·공개 파생본 생성
- 원자료·r3·6-tier·동반표·문헌 workspace 수정

## 9. 구현 전에 연구자가 정할 것

새로운 방법론 선택은 한 가지뿐이다.

> **기존 14개를 공통 UI 회귀 표본으로 유지하되, NI 2개만 Gate 2 방법론
> 기준으로 채택하는 이 설계에 동의하는가?**

권고 답은 `Gate 2 구현 GO`다. 이 답을 받은 뒤에만 §6 allowlist를 구현한다.
구현 후에는 독립 감사 결과와 HTML 경로를 보고하고, 실제 연구 청취나 Gate 3는
다시 별도 지시를 기다린다.
