# NAL — ㄹ 앞 비음화 — definition draft

> 상태: `literature_seeded_pending_researcher_confirmation`. 이 문서는 Gate 0
> 문헌 시드 초안이며 연구자 확인 전 분석 계약이 아니다.

## 1. 현상

장애음과 후행 ㄹ의 연쇄에서 후행 유음의 비음화 및 선행 장애음 비음화가
관련되는 환경을 검토 대상으로 둔다. 후행 유음이 표면에서 유지되는 변이와
LLN 연쇄의 방향 경쟁을 분리할 필요가 있으나 아직 확정하지 않는다.

## 2. 환경 조작화 후보

- query status: `draft_pv_only`
- 현상 번호·official slug: `pending_f0`
- 장애음+ㄹ 범위, 어절 내부/간, 외래어 처리, NAL/LLN 경계: `pending`
- 실제 4단 환경 분류행: 0

## 3. inclusion / exclusion / confound 후보

- inclusion candidate refs: CLM-0062, CLM-0065, CLM-0076, CLM-0077,
  CLM-0095, CLM-0096
- exclusion candidate refs: CLM-0066, CLM-0097
- confound candidate refs: CLM-0065, CLM-0067, CLM-0094
- NAN/NAL/LLN 모집단과 [비음+유음] 중간형은 `pending`이다.

## 4. 실현 판정 증거

MFA·G2P phone은 표면 방향을 자동 판정하지 않는다. 유음 유지, 완전 비음화,
부분 비음화·비음화 설측음은 후속 수동·음향 판정에서 구분한다.

## 5. 변수·추가 정보 후보

어휘·어종, 경계 유형, 운율 단위, 발화 속도, 세대·방언, 표면 C1/C2의 음향
지표를 sidecar 후보로만 둔다.

## 6. 문헌 근거

- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAL_현상종합_초안_20260823.md`
- scaffold: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAL_착수스캐폴드_20260823.md`
- evidence level: `core_papers_extracted`
- core sources: SRC-069, SRC-062
- definition candidate refs: CLM-0061, CLM-0075, CLM-0093, CLM-0098
- context ref: CLM-0080
- prosody source-level-only refs: SRC-360, SRC-361, SRC-362, SRC-356

CLM-0027 이후 주장은 `pending_researcher_adoption`이다. 운율 SRC는 확정 CLM
근거가 아니다.

## 7. 산출 목표와 정지선

Gate 0에서는 query·환경값을 동결하지 않고, 자동 실현 판정·TextGrid 수정·
정식 ledger 쓰기를 하지 않는다.
