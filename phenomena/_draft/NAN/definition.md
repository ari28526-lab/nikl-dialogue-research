# NAN — ㄴ 앞 비음화 — definition draft

> 상태: `literature_seeded_pending_researcher_confirmation`. 이 문서는 Gate 0
> 문헌 시드 초안이며 query·환경 분류·실현 판정값을 확정하지 않는다.

## 1. 현상

장애음 종성과 후행 ㄴ의 연쇄에서 선행 종성이 비음으로 실현되는 환경을 검토
대상으로 둔다. 필수 현상으로 기술되는 층과 운율 경계·과제·화자에 따른 변이
가능성을 분리해야 하나, 모집단은 아직 확정하지 않는다.

## 2. 환경 조작화 후보

- query status: `draft_pv_only`
- 현상 번호·official slug: `pending_f0`
- ㅁ 앞 환경 포함 여부, 어절 내부/간 모집단, 부분 비음화 코딩: `pending`
- 실제 4단 환경 분류행: 0

## 3. inclusion / exclusion / confound 후보

- inclusion candidate refs: CLM-0064, CLM-0069, CLM-0071, CLM-0072,
  CLM-0074, CLM-0077
- exclusion candidate refs: 없음(확정값이 아니라 후보 부재)
- confound candidate refs: CLM-0067, CLM-0071
- NAN/NAL/LLN 경계와 삽입 후 연쇄는 `pending`이며 모집단 분리 규칙을 여기서
  정하지 않는다.

## 4. 실현 판정 증거

MFA·G2P·기존 TextGrid는 위치 보조일 뿐 실현값이 아니다. 완전/부분 비음화와
판정 불가능 상태는 후속 연구자 수동 판정 계약에서 분리한다.

## 5. 변수·추가 정보 후보

어절 내부/간, 운율 경계, 발화 속도, 과제·대화 맥락, 화자·어휘, 음향적
부분 비음화 정도를 추가 정보 후보로만 둔다.

## 6. 문헌 근거

- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAN_현상종합_초안_20260823.md`
- scaffold: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAN_착수스캐폴드_20260823.md`
- evidence level: `core_papers_extracted`
- core source: SRC-057
- definition candidate refs: CLM-0061, CLM-0075
- prosody refs: CLM-0074; source-level-only SRC-360, SRC-361, SRC-362,
  SRC-356

CLM-0027 이후 주장은 `pending_researcher_adoption`이다. 네 운율 SRC는 CLM이
없는 `source_level_only`로만 보존한다.

## 7. 산출 목표와 정지선

Gate 0에서는 query·환경값을 동결하지 않고, 자동 실현 판정·TextGrid 수정·
정식 ledger 쓰기를 하지 않는다.
