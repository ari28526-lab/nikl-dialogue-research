# Stage 2 PV reviewer v2 구현 결과

- 날짜: 2026-08-22
- 상태: **구현·독립 감사 통과 / v2.1 보완본의 사용자 최소 화면 Gate 통과로 종료**
- 승인 근거:
  `docs/reviews/incoming/EXTERNAL_REVIEW_pv_reviewer_v2_design_codex_20260822.md`
- 구현 범위: 승인된 균형 14개 표본의 reviewer v2 파생출력만

## 1. 결과

새 파생출력 root를 만들었다.

```text
outputs/pilots/pv_seven_phenomena_reviewer_v2_20260822/
```

핵심 HTML은 한 화면에 후보 하나를 표시하고, 후보 검색·핵심/탐색 우선순위,
이전/다음 이동, 형태소 카드, 기존 대상/±2 문맥 음성, 조작적 동일화자 묶음,
전체 대화 텍스트 검색, 화자·대화 상황, 규칙 예상형·사전 참조형, 원유권(2022)
공통 방법론 패널, revision 보존·JSONL 내보내기를 포함한다.

자동 실현 판정, 정식 판정 ledger 쓰기, 전체 대화 음성 포함, MFA·KOINA·
wav2vec2 실행, 음성 변환은 하지 않았다.

## 2. 실측 계수

| 항목 | 결과 |
|---|---:|
| 표본 / 세션 / 현상×연도 셀 | 14 / 14 / 14 |
| 전체 대화 텍스트 행 | 4,060 |
| 대화에 exact target이 1개 있는 표본 | 14/14 |
| 사용자 원기록 행 / 최신 view / 의미상 중복 보존 | 15 / 14 / 1 |
| 기존 근거에서 직접 표시한 형태소 | 12 |
| HIA 상태 기록 | 2 |
| HIA exact linked | 1 (`PV0177`) |
| HIA 원천 불일치 zero-drop | 1 (`PV0027`) |
| WAV source SHA 일치 | 28/28 |
| 원유권 evidence 원행 / 공통 방법 긍정 표시 | 40 / 29 |
| 문헌 `not_found` / 원문 미확인 재인용 제외 | 1 / 10 |

`PV0027`은 후보 삭제나 자동 보정 대상이 아니다. 동결된
`match_evidence_json`의 `morph_link_status=form_tagged_count_mismatch`와 빈
`linked_morph_eojeol_idx`를 그대로 보존하고, reviewer에는 형태소 연결 불가
zero-drop 상태로 표시한다.

## 3. 무손실·상한 확인

- 사용자 JSONL 15행을 byte-for-byte 보존했다.
- 원본 SHA-256:
  `8a7d913af97ef903be941f726dbe73d78271384c6add246cdc52fe8df7de6133`
- 기존 15행 가운데 `PV0177`의 의미상 중복 1행을 삭제하지 않았다.
- `utterance_master_v2`와 `morph_units`는 연도·표별 200,000행에서 멈췄다.
- 자동 상한 증가는 하지 않았다.
- D:\ 원자료·동결층과 기존 PV root는 수정하지 않았다.

## 4. 독립 감사

감사 결과는 `passed=true`, `errors=[]`이다.

- 감사 JSON:
  `outputs/pilots/pv_seven_phenomena_reviewer_v2_20260822/audit/PV_REVIEWER_V2_AUDIT.json`
- SHA manifest:
  `outputs/pilots/pv_seven_phenomena_reviewer_v2_20260822/PV_REVIEWER_V2_SHA256_MANIFEST.csv`
- 검증 로그:
  `logs/pv_reviewer_v2_validation_20260822/VALIDATION_pv_reviewer_v2_20260822.log`

주요 SHA-256은 다음과 같다.

| 파일 | bytes | SHA-256 |
|---|---:|---|
| `PV_REVIEWER_V2.html` | 19,456,165 | `37c152d73069bfc7dc3e31684fdc99303916bb4acb72f986aab335541a1228f6` |
| `PV_REVIEWER_V2_BUILD.json` | 21,279 | `c22bd1734543792b1ff2c2aa7b54c5e22a33cbc335daf29481a4e1af8c35ec93` |
| `PV_REVIEWER_V1_IMPORTED.jsonl` | 12,028 | `8a7d913af97ef903be941f726dbe73d78271384c6add246cdc52fe8df7de6133` |
| `PV_REVIEWER_V2_DIALOGUES.jsonl` | 7,792,634 | `990c1098448d58107e375d868eb4e8593e14ea150fdc2e73938e22c0919b39ae` |
| `PV_REVIEWER_V2_AUDIT.json` | 1,937 | `13d42f8728be20ae0d97cacc9dab3a76b84fea1aef109b8dbdbbf44547c4b7bb` |

Python 두 파일은 `py_compile`을 통과했다. 성공·입력 실패·기존 출력
비덮어쓰기 시나리오를 시험했다. HTML 런타임 시험은 검색·우선순위·import
실패 네 종류·revision·내보내기·문헌 제외 규칙을 통과했다.

인앱 브라우저 자동 시각 검사는 브라우저 연결의 trusted-path 오류 때문에
실행하지 못했다. 이는 정적·런타임·독립 감사 통과와 분리한다. iPad/노트북
폭의 실제 사용성은 다음 사용자 Gate에서 확인한다.

## 5. 후속 Gate와 종료 상태

전체 14개를 다시 판정하지 않고 다음 세 표본만 화면 사용성을 확인하는 Gate를
제안했다.

1. `PV0001`: 표적 강조, 뒤 문맥 확장, 한 후보 화면
2. `PV0163`: 형태소 카드, 긴 화자 묶음 검색·접기
3. `PV0177`: HIA 형태소 연결, 기존 중복 기록 보존, 새 revision 내보내기

사용자가 확인할 질문은 네 가지다.

1. 어디를 들어야 하는지 즉시 알 수 있는가?
2. 더 긴 맥락을 필요할 때 찾을 수 있는가?
3. 메모 필드가 연구자의 생각을 방해하지 않고 돕는가?
4. JSONL로 내보냈을 때 기존 15행과 새 revision이 모두 남는가?

이 Gate의 안전·사용성 보완은 v2.1에서 구현했고 사용자 최소 화면 확인을
통과했다. 따라서 v2는 역사적 입력으로 보존하며 실제 후속 검토에는 v2.1을
사용한다. 연도별 30개 batch는 별도 문헌·환경 정리와 설계 승인 전에는
구현하지 않는다.

## 6. 저장소 상태

19MB HTML·전체 대화 JSONL·embedded audio를 포함한 생성 payload는 로컬에
보존하고 Git에는 올리지 않는다. 재현에 필요한 builder·auditor·runtime test와
이 결과 문서는 Git 추적 대상으로 둔다.
