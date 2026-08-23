# LLN — ㄴㄹ·ㄹㄴ 연쇄(유음화·비음화 복합형) — definition draft

> 상태: `literature_seeded_pending_researcher_confirmation`. NI 다음 reference
> implementation 후보이나, 이 문서는 Gate 0의 구조·문헌 시드 초안뿐이다.

## 1. 현상

ㄴ+ㄹ 또는 ㄹ+ㄴ 연쇄에서 [ㄹㄹ], [ㄴㄴ], 분절 유지 및 중간형이 경쟁하는
변이를 검토 대상으로 둔다. 문헌 간 우세 표면형 차이는 어종·과제·경계·세대가
다른 모집단에서 나온 것일 수 있으므로 하나의 규칙으로 합치지 않는다.

## 2. 환경 조작화 후보

- query status: `draft_pv_only`
- gate position: `next_after_ni`
- 현상 번호·official slug: `pending_f0`
- 방향별·어절 내부/간·어종별 모집단과 NAL 경계: `pending`
- 실제 4단 환경 분류행: 0

## 3. inclusion / exclusion / confound 후보

- inclusion candidate refs: CLM-0063, CLM-0064, CLM-0065, CLM-0069,
  CLM-0070, CLM-0071, CLM-0072, CLM-0074, CLM-0079, CLM-0082,
  CLM-0083, CLM-0084, CLM-0089, CLM-0090, CLM-0091, CLM-0092,
  CLM-0102, CLM-0103
- exclusion candidate refs: CLM-0078, CLM-0085, CLM-0104
- confound candidate refs: CLM-0065, CLM-0067, CLM-0071, CLM-0081,
  CLM-0082, CLM-0086, CLM-0087, CLM-0088, CLM-0090, CLM-0091,
  CLM-0099, CLM-0100, CLM-0101, CLM-0104, CLM-0105
- NAN/NAL/LLN 경계·모집단 충돌 후보는 해석 미확정 상태로 둔다.

## 4. 실현 판정 증거

MFA·G2P phone은 [ㄹㄹ]/[ㄴㄴ]을 자동 확정하지 않는다. 연구자 수동 판정과
필요한 음향 근거를 별도 승인 ledger에 기록한다.

## 5. 변수·추가 정보 후보

방향, 어종, 형태소·단어·어절 경계, 음절수, 빈도·친숙도, 연령·성별·방언,
과제·대화 맥락, 운율 경계를 sidecar 후보로만 둔다.

## 6. 문헌 근거

- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/LLN_현상종합_초안_20260823.md`
- scaffold: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/LLN_착수스캐폴드_20260823.md`
- evidence level: `core_papers_extracted`
- core sources: SRC-212, SRC-065, SRC-063, SRC-058
- definition candidate refs: CLM-0061, CLM-0068, CLM-0075, CLM-0087,
  CLM-0099
- context refs: CLM-0073, CLM-0086
- prosody refs: CLM-0068, CLM-0074; source-level-only SRC-360, SRC-361,
  SRC-362, SRC-356

CLM-0027 이후 주장은 `pending_researcher_adoption`이며 네 운율 SRC는
`source_level_only`다.

## 7. 산출 목표와 정지선

Gate 0에서는 query·표면형 분류를 동결하지 않고, 자동 실현 판정·TextGrid 수정·
정식 ledger 쓰기를 하지 않는다.
