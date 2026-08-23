# PT — 합성어 경음화(사잇소리 관련 포함) — definition draft

> 상태: `literature_seeded_pending_researcher_confirmation`. 이 문서는 문헌
> 근거 ID를 연결한 Gate 0 초안이다. query·환경 분류·실현 판정값을 확정하지
> 않으며 연구자 확인 전 분석 계약으로 쓰지 않는다.

## 1. 현상

합성어·형태론적 경계에서 후행 평장애음이 경음으로 실현될 수 있는 현상을
검토 대상으로 둔다. 문헌은 어종·빈도·길이·경계 강도·구성요소의 분절 특성에
따른 확률적 변이를 보고하지만, 정확한 모집단과 의무층/수의층의 분리는 아직
확정하지 않는다.

## 2. 환경 조작화 후보

- query status: `draft_pv_only`
- 현상 번호·official slug: `pending_f0`
- 좌우 분절 집합, ㅎ·ㄶ·ㅀ 환경 처리, 어절 간 포함 범위: `pending`
- 실제 4단 환경 분류행: 0

## 3. inclusion / exclusion / confound 후보

- inclusion candidate refs: CLM-0023, CLM-0029, CLM-0030, CLM-0032,
  CLM-0033, CLM-0034, CLM-0036, CLM-0037, CLM-0038, CLM-0039,
  CLM-0040, CLM-0044, CLM-0045, CLM-0046, CLM-0047, CLM-0050,
  CLM-0051, CLM-0053, CLM-0054
- exclusion candidate refs: CLM-0041, CLM-0052, CLM-0059
- confound candidate refs: CLM-0027, CLM-0028, CLM-0029, CLM-0035,
  CLM-0037, CLM-0040, CLM-0041, CLM-0042, CLM-0044, CLM-0048,
  CLM-0055, CLM-0058
- PT/NI 경계와 사이시옷·ㄴ삽입 교차 태깅은 `pending`이며 토큰 배타/중복
  규칙을 여기서 정하지 않는다.

## 4. 실현 판정 증거

표기·형태소 검색, 사전·G2P, MFA·기존 TextGrid는 후보와 시간 위치의 보조
정보다. 최종 실현값은 별도 승인 ledger의 연구자 수동 판정만 사용한다.

## 5. 변수·추가 정보 후보

어종, 구성요소 빈도, 전체 합성어 빈도, 길이, 경계 유형, 화자, 발화 속도,
운율 경계, 어휘화·친숙도는 sidecar 후보일 뿐 정식 열이 아니다.

## 6. 문헌 근거

- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/PT_현상종합_초안_20260823.md`
- scaffold: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/PT_착수스캐폴드_20260823.md`
- evidence level: `core_papers_extracted`
- core sources: SRC-338, SRC-305, SRC-311, SRC-337, SRC-321
- definition candidate refs: CLM-0022, CLM-0024, CLM-0025, CLM-0028,
  CLM-0035, CLM-0043, CLM-0049, CLM-0056, CLM-0060
- prosody source-level-only refs: SRC-360, SRC-361, SRC-362, SRC-356
- context refs: CLM-0042, CLM-0057

`SRC-360·361·362·356`은 아직 CLM이 없는 `source_level_only` 자료이며 확정
주장으로 취급하지 않는다. CLM-0027~0060은 `pending_researcher_adoption`이다.

## 7. 산출 목표와 정지선

Gate 1 이후 현상별 inclusion/exclusion/confound 계약과 환경 분류를 별도
승인으로 만든다. Gate 0에서는 query 생성·수정, 자동 실현 판정, TextGrid 수정,
정식 ledger 쓰기를 하지 않는다.
