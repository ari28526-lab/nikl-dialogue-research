# RESULT — Stage2 실제 연구 안내서 7현상 사전 작성

- 날짜: 2026-08-24 KST
- 상태: **공통 안내서·현상별 7개 안내서·세션 체크시트 빌드 및 독립 감사 통과**
- 연구 상태: 범위·문헌 해석·실현 범주는 전부 `candidate`; 연구자 실제 판정 0건

## 산출물

- 안내서 묶음:
  `outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/actual_research_guides_v1/`
- 독립 감사:
  `outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823/actual_research_guides_audit_v1/AUDIT_STAGE2_ACTUAL_RESEARCH_GUIDES.json`
- 안내서 파일: 25개, 137,838 bytes
- 안내서 SHA manifest SHA-256:
  `03dc14bf756d0d880a881d3cd28c766ae8dba09da9457db77b51ef5b1fb6cb32`
- `START_HERE.html` SHA-256:
  `ba848151077830257bffec635a07c134963267e0a46555e38f4ee0525dee68e7`
- 감사 JSON SHA-256:
  `4ec00488499cabec7b8c1135e21778a33eb260cd80e728e55463bee17b5c570e`

## 구성

- 공통 실제 연구 안내서 HTML·Markdown
- 세션 체크시트 HTML·Markdown
- 화면 재설계 관찰 양식 HTML·Markdown
- PT·NAN·NAL·NI·LLN·VH·HIA별 HTML·Markdown 14개
- 현상 선택 시작 화면과 현상별 색인
- 연구 JSONL 보관 규칙
- 빌드 영수증과 SHA-256 manifest

각 현상 안내서는 동결 범위 카드의 잠정 정의, 최소 대조, 120분 일정,
primary/peripheral/exploratory/out_of_scope/unclear 모집단, 경계 범위,
표면형·형태론·품사 계약, 고위험 오인, 사람 확인 항목, 실현 후보 범주,
판단 불가 사유, 혼란변수, 근거 한계와 열린 질문을 그대로 투영한다.

## 연구 우선·화면 재설계 원칙

- 안내서는 판단을 대신하지 않고 무엇을 관찰·기록할지 안내한다.
- 범위 판정과 실현 판정을 분리하고 MFA phone·형태소·TextGrid를 자동 정답으로
  사용하지 않는다.
- 화면 `Blocker`만 즉시 수정하고, 반복 `Friction`은 현상 종료 뒤 모아 다음
  화면 버전에 반영한다.
- 같은 불편이 둘 이상의 세션이나 현상에서 반복되기 전에는 검증된 reviewer v2를
  기준본으로 유지한다.

## 검증

- Python `py_compile`: builder·auditor·test 통과
- Python unittest: 4/4 통과
- 독립 감사: `passed=true`
- 현상별 HTML 7·Markdown 7, 각 12건·총 84건
- manifest 24건 전부 SHA 일치
- 로컬 링크 81개 확인
- candidate 상태 보존, 원자료 읽기 0, 자동 실현 판정 0
- 브라우저: 시작 화면 7개 카드, NI 현상 안내서의 범위표·열린 질문·candidate
  표시, `NI 1/12` reviewer 연결 확인
- 브라우저 콘솔 오류 0건, localStorage·연구 기록 작성 0건

## 실제 사용

`actual_research_guides_v1/START_HERE.html`에서 현상을 고르고, 먼저 현상별
안내서를 읽은 뒤 같은 카드의 reviewer 링크로 이동한다. 2시간을 한 번에 확보하지
못하면 완료 지점을 문헌 메모에 남기고 JSONL을 export한 뒤 다음 세션에 현상별
최신 정본 하나만 불러온다.
