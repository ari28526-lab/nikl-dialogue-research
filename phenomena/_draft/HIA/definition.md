# HIA — 모음충돌 회피 — definition draft

> 상태: `literature_seeded_pending_researcher_confirmation`. 이 문서는 Gate 0
> 문헌 시드 초안이며 활음화·축약·탈락 범주나 query 값을 확정하지 않는다.

## 1. 현상

모음 연쇄에서 활음화·활음 첨가·모음 탈락·축약·충돌 유지가 경쟁하는 환경을
검토 대상으로 둔다. 어간말 모음·음절수·발화 속도·어미 구성 및 VH와의 중복을
분리해야 하나 모집단과 표면형 범주는 아직 확정하지 않는다.

## 2. 환경 조작화 후보

- query status: `draft_pv_only`
- 현상 번호·official slug: `pending_f0`
- 활음화/첨가/탈락/축약 범주, 표면형 기준, VH membership: `pending`
- 실제 4단 환경 분류행: 0

## 3. inclusion / exclusion / confound 후보

- inclusion candidate refs: CLM-0123, CLM-0134, CLM-0135, CLM-0136,
  CLM-0140, CLM-0141, CLM-0143, CLM-0147, CLM-0148, CLM-0150,
  CLM-0153, CLM-0154, CLM-0155
- exclusion candidate refs: CLM-0142, CLM-0149
- confound candidate refs: CLM-0138, CLM-0144, CLM-0145, CLM-0147,
  CLM-0151, CLM-0155
- VH/HIA 중복과 동일 토큰 이중 계상 규칙은 `pending`이다.

## 4. 실현 판정 증거

전사 표기·형태소 분석·MFA·G2P는 활음화·유지·첨가를 자동 판정하지 않는다.
필요한 경우 TextGrid 경계와 포먼트 전이를 연구자가 별도로 확인한다.

## 5. 변수·추가 정보 후보

어간말 모음, 어간 음절수·끝음절 유형, 어미·구성, 발화 속도·운율 위치,
화자·연령, 어휘 빈도·음장, VH membership을 sidecar 후보로만 둔다.

## 6. 문헌 근거

- synthesis: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/HIA_현상종합_초안_20260823.md`
- scaffold: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/HIA_착수스캐폴드_20260823.md`
- evidence level: `core_papers_extracted`
- core sources: SRC-071, SRC-072, SRC-075
- definition candidate refs: CLM-0133, CLM-0139, CLM-0146, CLM-0152
- context ref: CLM-0156
- human-check refs: CLM-0145, CLM-0151 (`non_blocking_pending`)
- prosody source-level-only refs: SRC-360, SRC-361, SRC-362, SRC-356

CLM-0145의 용례 쪽수와 CLM-0151의 화자 수 불일치는 Gate 0을 막지 않지만
후속 인용 전 확인해야 한다. 네 운율 SRC는 CLM이 없는 `source_level_only`다.

## 7. 산출 목표와 정지선

Gate 0에서는 query·표면형 분류·membership을 동결하지 않고, 자동 실현 판정·
TextGrid 수정·정식 ledger 쓰기를 하지 않는다.
