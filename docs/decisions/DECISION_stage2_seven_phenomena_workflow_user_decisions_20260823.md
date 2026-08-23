# DECISION: 일곱 현상 workflow 설계 검토 — 연구자 결정 기록 (2026-08-23)

근거 검토:
`docs/reviews/incoming/EXTERNAL_REVIEW_stage2_seven_phenomena_workflow_claude_20260823.md`
(§D의 결정 요청 D1~D5). 연구자 `ari30`이 2026-08-23 Cowork 대화에서 선택지
질문에 답해 확정했다. 이 문서는 결정 기록이며 구현 승인 범위는 각 항목에
명시된 대로다.

| ID | 결정 | 내용 |
|---|---|---|
| D1 | **개정안 확정 + '요' 탐색 query 추가** | NI B1 잔여 범위를 개정안대로 확정: 어절 내부/간 2모집단, J*/E*·숫자·기호 제외, 의미번호 불확실성 보존. 동결 query(SHA 744bd8cb…)는 재동결 없이 유지. 보조사 '요' 앞 ㄴ삽입(오미라 2006, 문헌 근거 CLM-0002)은 **별도 탐색 query 후보로 등록**하되 본모집단과 분리 회계한다. |
| D2 | **승인** | NI를 reference implementation으로 공통 시작 체계(검토 §A1–A8)를 검증한 뒤 LLN → 나머지 현상으로 확대(2026-08-19 D2 결정과 정합). |
| D3 | **read-only 패널 + Praat 왕복** | TextGrid 후속 초기 방식은 REQUIREMENT §3 초기 권고 채택: HTML은 read-only TextGrid 패널 즉시 확인만, 수정 필요 사례만 exact-ID 격리 작업본으로 내보내기/가져오기. in-browser 경계 편집은 반복 수요 확인 뒤 별도 파일럿. |
| D4 | **비식별 파생값 + 재현 절차만** | 말뭉치 이용조건·윤리 확인 전까지 현상별 공개 파생본의 기본 출력 계약은 비식별 파생값 + exact-ID 재현 절차. 원문 음성·전사·TextGrid는 공개본에 넣지 않는다. 범위 확대는 별도 결정. |
| D5 | **승인 후 같은 날 개정** | 최초 답: 문헌 확장 없이 NI만 문헌 시드, 6현상 placeholder 시작 승인. **직후 연구자 재지시로 개정**: 구현 도구에 넘기기 전에 나머지 6현상(PT·NAN·NAL·LLN·VH·HIA)도 Cowork에서 문헌정리를 최대한 진행한다 — 현상당 핵심 3~5편은 NI 파일럿과 같은 급(전문 정독 + reference_evidence.v2 주장 추출), 나머지 문헌은 목록·서지 수준으로 두고 정독 범위를 명시 표기. 문헌 산출물은 기존과 같이 Git 밖 `work/literature_evidence_seven_phenomena_20260822`가 정본이며, 이 확장은 query·상한·batch builder를 변경하지 않는다. |

부수 사항:

- pending 보존(질문하지 않음, 검토 §D 하단 목록 그대로): 현상 번호·slug(F0),
  NAN ㅁ 앞 포함, PT 격음화 제외, VH/HIA 질문 4·5·6, sidecar key namespace,
  문맥 창 ±2, 대형 현상 저장 정책, PV-B 보조층 열, NI 600건 층화 세부.
- 이 결정으로 여는 다음 단계: ① Cowork 6현상 문헌 확장(D5 개정, 문헌
  워크스페이스 내부 작업) → ② 완료 뒤 구현 도구에 검토 보고서 §G 인계
  프롬프트(D1~D5 답 기입)로 Gate 0 구현 인계. 코드·config·query 구현은
  여전히 이 기록만으로 승인되지 않는다(각 Gate의 preflight·감사·승인 별도).
