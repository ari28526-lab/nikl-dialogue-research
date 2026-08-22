# REQUIREMENT: Stage 2 수동 TextGrid·가변 정보 보강·현상별 공개

기록일: 2026-08-22 KST
상태: **후속 설계 필수 요구사항 기록 완료, 구현 미승인**

## 1. 기록 목적

현재 PV reviewer는 후보 탐색·청취·메모를 위한 도구이며 정식 실현 판정이나
TextGrid 수정 도구가 아니다. 그러나 실제 연구에서는 후보마다 다음 작업이
달라질 수 있다.

- 기존 TextGrid만으로 판정 가능
- word/phone 경계, label 또는 전사 수동 조정 필요
- 더 긴 대화 문맥이나 다른 session 파일 확인 필요
- 형태소·의미번호·동음이의어·운율·발화속도·화자/상황 등 추가 정보 필요
- 자산 부재·음질 문제로 보류 또는 제외 검토 필요

이 작업층을 일곱 현상 workflow에서 빠뜨리지 않고, 나중에 현상별 연구 결과를
재현 가능하게 공개할 수 있도록 처음부터 provenance를 보존한다.

## 2. 연구자 요구사항

### R1. 후보별 후속 필요성은 독립된 정식 단계다

문헌·형태론 환경 정리와 청취 뒤에 다음 순서를 둔다.

```text
문헌·환경 근거
  → 후보 추출·HTML 청취
  → 후보별 후속 필요성 분류
  → 필요한 사례만 수동 작업 묶음 생성
  → TextGrid overlay·가변 정보 보강
  → 독립 감사
  → 정식 실현 판정 ledger
  → 현상별 공개용 파생본
```

모든 후보를 조정하지 않는다. 수동 조정이나 정보 보강이 필요하지 않은 후보도
`not_needed` 상태로 보존해 zero-drop 회계를 유지한다.

### R2. HTML에서 TextGrid 검토 필요를 표시하고 바로 이어서 볼 수 있어야 한다

후속 reviewer에는 최소한 다음 입력을 둔다.

- `textgrid_review_need`: `not_needed | required | unsure`
- `textgrid_review_reasons`: 경계·label·전사·표적 span·기타의 복수 선택
- `additional_information_requests`: 필요한 정보명·이유를 복수 기록
- 자유 메모와 1–5 확신도

연구자가 `required` 또는 `unsure`를 선택했거나 기존 수동 작업 상태가 있으면,
같은 후보 화면에서 TextGrid 검토 패널이 **자동으로 펼쳐지는 것**을 목표
사용성으로 둔다. 패널은 다음을 보여야 한다.

- 대상 시간 span과 파형/재생 위치
- 기존 6-tier TextGrid의 read-only tier·label·경계
- target 어절·형태소 근거와 원 시간 좌표
- TextGrid 존재 여부, source 경로 식별자와 SHA-256
- 수동 작업본/overlay 상태와 마지막 revision
- 자산이 없을 때의 명시적 `unavailable` 상태

`필요` 표시만으로 TextGrid를 자동 수정하거나 실현값을 자동 판정해서는 안 된다.

### R3. 원본 불변과 overlay 원칙

`D:\00_RAW`, `D:\10_LAYERS`, r3 DB, 최종 6-tier와 동반표는 수정하지 않는다.
수동 작업은 exact-ID에 결속한 격리 사본 또는 overlay로 수행한다.

각 작업 묶음은 최소한 다음 provenance를 가진다.

```text
task_id, phenomenon_id, occurrence_id, utt_id,
source_textgrid_sha256, source_wav_sha256, source_span,
requested_actions, working_asset_status,
revision_id, supersedes, reviewer, reviewed_at
```

수정된 경계·label·전사는 원본과 diff 가능한 patch/sidecar 및 versioned 작업본으로
보존한다. 정식 ledger 반영은 별도 감사와 연구자 승인을 거친다.

### R4. 현상마다 달라지는 추가 정보는 가변 sidecar로 시작한다

공통 핵심 열과 현상별·사례별 정보 요청을 분리한다. 처음부터 모든 가능성을 넓은
CSV 열로 만들지 않고, 다음과 같은 append-only long-form 기록을 우선한다.

```text
request_id, phenomenon_id, occurrence_id,
information_key, requested_reason, value_status,
value_text_or_ref, evidence_source, evidence_sha256,
reviewer, recorded_at, supersedes
```

여러 현상·사례에서 반복되고 분석에 실제 쓰이는 항목만 코드북 검토 뒤 versioned
정식 열로 승격한다. 미확인 값은 행 삭제나 빈값 은폐 대신 `pending`,
`unavailable`, `not_applicable` 등 상태로 남긴다.

### R5. 현상별 공개용 파생본을 만들 수 있어야 한다

정식 공개용 자료는 reviewer의 localStorage나 임시 HTML을 정본으로 삼지 않는다.
현상별로 승인된 ledger, TextGrid overlay provenance, 정보 코드북과 감사 manifest를
결합해 재생성한다. 최소 구성 후보는 다음과 같다.

- 현상 정의·query와 버전/SHA
- 공개 가능한 후보·판정·확신도·근거 표
- 수동 수정 이력과 원본 대비 patch/요약
- 변수 코드북과 결측·보류 상태 설명
- 표본 선택·제외·zero-drop 회계
- 독립 감사 JSON과 SHA manifest

말뭉치 음성·전사·TextGrid 원문 자체의 외부 배포 범위는 모두의 말뭉치 이용조건,
개인정보·연구윤리와 재배포 허용 범위를 별도 확인한 뒤 확정한다. 허용되지 않는
자산은 공개본에 넣지 않고 exact-ID 기반 재현 절차나 비식별 파생값만 제공한다.

## 3. 구현 전 결정할 사항

다음은 아직 확정하지 않는다.

1. HTML 안에서 경계를 직접 편집할지, read-only 시각화와 Praat 작업본
   내보내기/가져오기를 결합할지
2. 파형·TextGrid를 단일 HTML에 내장할 범위와 대용량 batch의 지연 로딩 방식
3. 현상별 필수 tier와 수정 가능 tier
4. 정보 요청 key의 공통 사전과 현상별 namespace
5. 공개 가능한 원자료·파생자료의 범위와 배포 위치

초기 권고는 **HTML에서 즉시 read-only 확인 + 필요한 사례만 격리 작업본으로
내보내기/가져오기**다. 실제 수동 조정이 반복적으로 많고 브라우저 편집의 이점이
확인된 뒤에만 in-browser 경계 편집을 별도 파일럿한다.

## 4. 후속 reviewer 합격 기준 초안

- `required/unsure` 선택 즉시 같은 화면의 TextGrid 패널이 열린다.
- 후보 이동·검색·가져오기 전에 미저장 변경 경고가 유지된다.
- 저장·재가져오기 뒤 필요 상태와 요청 정보가 같은 occurrence에 복원된다.
- TextGrid 부재 후보가 삭제되지 않고 `unavailable`로 표시된다.
- `not_needed + required + unsure + unavailable/blocked`가 입력 후보 전체를
  zero-drop으로 회계한다.
- 수동 작업본은 원본 SHA와 exact-ID에 결속되고 원본 파일 변경은 0건이다.
- 자동 실현 판정과 자동 ledger 쓰기는 0건이다.
- 현상별 공개 파생본을 정식 ledger와 audit manifest에서 재생성할 수 있다.

## 5. 적용 시점과 현재 정지선

현재 Cowork의 일곱 현상 문헌·형태론 환경 정리를 먼저 마친다. 그 결과를 승인한
뒤, 연도별 30개 후속 batch를 확대하기 전에 이 요구사항을 포함한 reviewer·수동
annotation Gate를 설계한다. 이 문서는 query, 200,000행 상한, TextGrid, 정식
ledger 또는 공개 범위를 바꾸는 구현 승인이 아니다.

참고할 선행 구현은 다음이다.

- `PLAN_db_v1_recovery_D10_manual_overlay_20260818.md`
- `RESULT_db_v1_recovery_D10_materialization_20260818.md`
- `PLAN_post_production_recovery_target_manual_session_json_20260814.md`
- `PLAN_stage2_target_query_and_realization_design_20260818.md`
- `PLAN_stage2_seven_phenomena_PV_pilot_20260819.md`
