# 문헌 근거 handoff 감사 — Gate 0 seed map (2026-08-23)

정본(구현 도구용): `docs/reviews/incoming/LITERATURE_HANDOFF_stage2_gate0_seeds_claude_20260823.json`
이 MD와 HTML은 동일 내용의 사람용 파생 보고다. 본 감사는 새 문헌 검색·정독 확대·정본 수정·코드/config/query 수정을 하지 않았다.

## 1. Snapshot 독립 검증 — 통과

- SOURCE_INVENTORY 362행, SHA-256 `e8de6907f632a5b64853a6386c7d510ba69852451322630dc43ea201fefa0680` — 기대값과 일치
- CLAIM_EVIDENCE 156행, SHA-256 `1e88f5513f4c57387954d6149d922ccfc20ad024cfb8df63d492d96e0924610a` — 기대값과 일치
- DECISION_LOG 28행 · 파싱 오류 0 · source_id/source_sha256 결속 오류 0
- needs_human_check 플래그는 정확히 5건: CLM-0008, CLM-0015, CLM-0026, CLM-0145, CLM-0151 (지시 목록과 일치)
- 현상종합 7종이 참조하는 SRC/CLM 누락 0 (아래 §7 ID 재검사)

## 2. 분류·상태 규칙 (결정적·규칙 기반 — 해석 아님)

- **definition_refs**: claim_kind=main_claim (현상 성격·핵심 일반화)
- **inclusion_candidate_refs**: claim_kind∈{environment_condition, data_claim} (적용 환경·실현율 근거)
- **exclusion_candidate_refs**: claim_kind=counterexample (비적용·반례 근거)
- **confound_candidate_refs**: claim_kind∈{methodology, corpus_description} 또는 claim_ko에 속도·과제·위치·빈도·성별·세대·개인·스타일 표지
- **prosody_candidate_refs**: claim_ko에 운율·억양·음운구·경계 성조·휴지 표지인 CLM + 운율 경계 SRC 4종(source_level_only)
- **unresolved_or_human_check_refs**: needs_human_check=true
- **context_prior_work_refs**: (부가 목록) claim_kind=prior_work_summary — 6분류 밖 문맥 근거의 누락 방지용
- **overlap**: 한 CLM이 복수 목록에 들어갈 수 있음(규칙 중복 적용). 최종 4단 분류(general/peripheral/theoretical/unclear)는 Gate 0에서 하지 않음(지시 5).

- evidence_status **claim_verified**: CLM-0001~0026 (NI 파일럿 — 본 세션 직접 정독·추출, 검토 아티팩트 발행)
- evidence_status **pending_researcher_adoption**: CLM-0027~0156 (LD-027 확장 — 병렬 에이전트 초안 + 본 세션 배치별 표본 검증·병합. 연구자 [내 요약·메모] 채택 전)
- evidence_status **needs_human_check**: 플래그 5건
- evidence_status **source_level_only**: CLM 없는 SRC 수준 근거(운율 경계 문헌 등)

주의: Gate 0에서는 4단 환경 분류(general/peripheral/theoretical/unclear)를 하지 않는다 — 위 목록은 근거 **후보 ID**다. 문헌이 직접 확립하지 않는 내용은 추론하지 않았다(claim_kind·본문 표지 기반 기계 분류이며, 중복 등재 허용).

## 3. 현상별 seed map 요약

| 현상 | evidence_level | core 논문 | core claim | 전체 태깅 | A_direct | def | incl | excl | conf | pros | unresolved |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PT 합성어 경음화(사잇소리 관련 포함) | core_papers_extracted | 5 | 33 | 37 | 23 | 9 | 19 | 3 | 12 | 4 | 0 |
| NAN ㄴ 앞 비음화 | core_papers_extracted | 1 | 3 | 9 | 13 | 2 | 6 | 0 | 2 | 5 | 0 |
| NAL ㄹ 앞 비음화 | core_papers_extracted | 2 | 10 | 15 | 14 | 4 | 6 | 2 | 3 | 4 | 0 |
| NI ㄴ삽입 | pilot_full | 4 | 26 | 32 | 32 | 15 | 11 | 0 | 6 | 7 | 3 |
| LLN ㄴㄹ·ㄹㄴ 연쇄(유음화·비음화 복합형) | core_papers_extracted | 4 | 26 | 34 | 16 | 5 | 18 | 3 | 15 | 6 | 0 |
| VH 모음조화 | core_papers_extracted | 5 | 33 | 34 | 15 | 5 | 21 | 1 | 9 | 4 | 0 |
| HIA 모음충돌 회피 | core_papers_extracted | 3 | 18 | 24 | 6 | 4 | 13 | 2 | 6 | 4 | 2 |

교차 태깅 claim은 core paper 수와 별개다(예: NI 전체 32 = 파일럿 26 + Zuraw 교차 6; §5).

### PT (합성어 경음화(사잇소리 관련 포함))

- core 논문: SRC-338(7건), SRC-305(8건), SRC-311(6건), SRC-337(7건), SRC-321(5건)
- definition_refs (9): CLM-0022 CLM-0024 CLM-0025 CLM-0028 CLM-0035 CLM-0043 CLM-0049 CLM-0056 CLM-0060
- inclusion_candidate_refs (19): CLM-0023 CLM-0029 CLM-0030 CLM-0032 CLM-0033 CLM-0034 CLM-0036 CLM-0037 CLM-0038 CLM-0039 CLM-0040 CLM-0044 CLM-0045 CLM-0046 CLM-0047 CLM-0050 CLM-0051 CLM-0053 CLM-0054
- exclusion_candidate_refs (3): CLM-0041 CLM-0052 CLM-0059
- confound_candidate_refs (12): CLM-0027 CLM-0028 CLM-0029 CLM-0035 CLM-0037 CLM-0040 CLM-0041 CLM-0042 CLM-0044 CLM-0048 CLM-0055 CLM-0058
- prosody_candidate_refs (4): SRC-360 SRC-361 SRC-362 SRC-356
- context_prior_work_refs (2): CLM-0042 CLM-0057
- 문서: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/PT_현상종합_초안_20260823.md` · `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/PT_착수스캐폴드_20260823.md`

### NAN (ㄴ 앞 비음화)

- core 논문: SRC-057(3건)
- definition_refs (2): CLM-0061 CLM-0075
- inclusion_candidate_refs (6): CLM-0064 CLM-0069 CLM-0071 CLM-0072 CLM-0074 CLM-0077
- confound_candidate_refs (2): CLM-0067 CLM-0071
- prosody_candidate_refs (5): CLM-0074 SRC-360 SRC-361 SRC-362 SRC-356
- 문서: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAN_현상종합_초안_20260823.md` · `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAN_착수스캐폴드_20260823.md`

### NAL (ㄹ 앞 비음화)

- core 논문: SRC-069(6건), SRC-062(4건)
- definition_refs (4): CLM-0061 CLM-0075 CLM-0093 CLM-0098
- inclusion_candidate_refs (6): CLM-0062 CLM-0065 CLM-0076 CLM-0077 CLM-0095 CLM-0096
- exclusion_candidate_refs (2): CLM-0066 CLM-0097
- confound_candidate_refs (3): CLM-0065 CLM-0067 CLM-0094
- prosody_candidate_refs (4): SRC-360 SRC-361 SRC-362 SRC-356
- context_prior_work_refs (1): CLM-0080
- 문서: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAL_현상종합_초안_20260823.md` · `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NAL_착수스캐폴드_20260823.md`

### NI (ㄴ삽입)

- core 논문: SRC-297(10건), SRC-287(6건), SRC-293(5건), SRC-294(5건)
- definition_refs (15): CLM-0001 CLM-0003 CLM-0007 CLM-0008 CLM-0009 CLM-0010 CLM-0011 CLM-0012 CLM-0014 CLM-0017 CLM-0021 CLM-0022 CLM-0024 CLM-0025 CLM-0028
- inclusion_candidate_refs (11): CLM-0002 CLM-0004 CLM-0005 CLM-0006 CLM-0013 CLM-0015 CLM-0023 CLM-0029 CLM-0031 CLM-0032 CLM-0034
- confound_candidate_refs (6): CLM-0010 CLM-0015 CLM-0026 CLM-0027 CLM-0028 CLM-0029
- prosody_candidate_refs (7): CLM-0009 CLM-0010 CLM-0016 SRC-360 SRC-361 SRC-362 SRC-356
- unresolved_or_human_check_refs (3): CLM-0008 CLM-0015 CLM-0026
- context_prior_work_refs (4): CLM-0016 CLM-0018 CLM-0019 CLM-0020
- 문서: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NI_현상종합_초안_20260823.md` · `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/NI_착수스캐폴드_20260823.md`

### LLN (ㄴㄹ·ㄹㄴ 연쇄(유음화·비음화 복합형))

- core 논문: SRC-212(7건), SRC-065(6건), SRC-063(6건), SRC-058(7건)
- definition_refs (5): CLM-0061 CLM-0068 CLM-0075 CLM-0087 CLM-0099
- inclusion_candidate_refs (18): CLM-0063 CLM-0064 CLM-0065 CLM-0069 CLM-0070 CLM-0071 CLM-0072 CLM-0074 CLM-0079 CLM-0082 CLM-0083 CLM-0084 CLM-0089 CLM-0090 CLM-0091 CLM-0092 CLM-0102 CLM-0103
- exclusion_candidate_refs (3): CLM-0078 CLM-0085 CLM-0104
- confound_candidate_refs (15): CLM-0065 CLM-0067 CLM-0071 CLM-0081 CLM-0082 CLM-0086 CLM-0087 CLM-0088 CLM-0090 CLM-0091 CLM-0099 CLM-0100 CLM-0101 CLM-0104 CLM-0105
- prosody_candidate_refs (6): CLM-0068 CLM-0074 SRC-360 SRC-361 SRC-362 SRC-356
- context_prior_work_refs (2): CLM-0073 CLM-0086
- 문서: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/LLN_현상종합_초안_20260823.md` · `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/LLN_착수스캐폴드_20260823.md`

### VH (모음조화)

- core 논문: SRC-214(7건), SRC-139(7건), SRC-126(7건), SRC-122(6건), SRC-134(6건)
- definition_refs (5): CLM-0106 CLM-0113 CLM-0120 CLM-0127 CLM-0133
- inclusion_candidate_refs (21): CLM-0109 CLM-0110 CLM-0112 CLM-0115 CLM-0116 CLM-0117 CLM-0118 CLM-0119 CLM-0121 CLM-0122 CLM-0123 CLM-0124 CLM-0125 CLM-0128 CLM-0129 CLM-0130 CLM-0131 CLM-0134 CLM-0135 CLM-0136 CLM-0143
- exclusion_candidate_refs (1): CLM-0111
- confound_candidate_refs (9): CLM-0107 CLM-0108 CLM-0109 CLM-0114 CLM-0116 CLM-0127 CLM-0129 CLM-0131 CLM-0138
- prosody_candidate_refs (4): SRC-360 SRC-361 SRC-362 SRC-356
- context_prior_work_refs (3): CLM-0126 CLM-0132 CLM-0137
- 문서: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/VH_현상종합_초안_20260823.md` · `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/VH_착수스캐폴드_20260823.md`

### HIA (모음충돌 회피)

- core 논문: SRC-071(6건), SRC-072(6건), SRC-075(6건)
- definition_refs (4): CLM-0133 CLM-0139 CLM-0146 CLM-0152
- inclusion_candidate_refs (13): CLM-0123 CLM-0134 CLM-0135 CLM-0136 CLM-0140 CLM-0141 CLM-0143 CLM-0147 CLM-0148 CLM-0150 CLM-0153 CLM-0154 CLM-0155
- exclusion_candidate_refs (2): CLM-0142 CLM-0149
- confound_candidate_refs (6): CLM-0138 CLM-0144 CLM-0145 CLM-0147 CLM-0151 CLM-0155
- prosody_candidate_refs (4): SRC-360 SRC-361 SRC-362 SRC-356
- unresolved_or_human_check_refs (2): CLM-0145 CLM-0151
- context_prior_work_refs (1): CLM-0156
- 문서: `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/HIA_현상종합_초안_20260823.md` · `work/literature_evidence_seven_phenomena_20260822/03_phenomenon_synthesis/HIA_착수스캐폴드_20260823.md`

## 4. needs_human_check 5건 — Gate 0 영향 판정

| CLM | SRC | 현상 | 판정 | 이유 |
|---|---|---|---|---|
| CLM-0008 | SRC-297 | NI | **non_blocking_pending** | 전도규칙 반박(이론사)의 인용 서지 연도 확인(고광모 1991 vs Ko 1992) 문제. Gate 0 산출물(registry·템플릿)은 CLM ID 인용만 하고 서지 값을 동결하지 않으므로 차단 아님. 채택(adoption) 시 원전 대조 필요. |
| CLM-0015 | SRC-287 | NI | **non_blocking_pending** | 2음절어 공명음/장애음 말음 비대칭은 Gate 1 inclusion 계약의 후보 근거이나, Gate 0에서는 후보 ID 등재만 한다. Hwang 2007/2008 동일성은 근거 강도 문제이지 스키마 구조 문제가 아님. |
| CLM-0026 | SRC-294 | NI | **non_blocking_pending** | prior_work_summary(문맥 근거). Cho 2020 수배 추가 여부는 문헌 확장 결정이며 Gate 0의 어떤 선언 값에도 들어가지 않는다. Go & Kwon 2021은 SRC-272 보유 확인 완료. |
| CLM-0145 | SRC-072 | HIA | **non_blocking_pending** | w 활음화 총 용례 수(약 31만)의 출전 쪽수 재확인 필요. Gate 0 산출물은 수치를 인용하지 않는다. HIA 착수(문헌 채택) 시 쪽수 확인 후 인용. |
| CLM-0151 | SRC-075 | HIA | **non_blocking_pending** | 화자 수 5(p.60) vs 10(p.61, 영문초록) 불일치는 원문 자체 문제로 기록됨. Gate 0 영향 없음. 인용 시 두 수치 병기 또는 저자 확인 필요. |

5건 모두 non_blocking_pending — Gate 0(스키마·registry·템플릿 동결)은 어떤 문헌 수치·서지 값도 동결하지 않기 때문. 단, Gate 1(NI inclusion 계약)에서 CLM-0015, 현상 착수 시 CLM-0145·0151의 해소가 필요하다.

## 5. NI 파일럿/전체 분리 (지시 9)

- 최초 파일럿: SRC-297, SRC-287, SRC-293, SRC-294 — CLM-0001~CLM-0026 (26건, claim_verified)
- NI 태그 전체: 32건 = 파일럿 26 + 교차 태깅 6 (SRC-338: CLM-0027, CLM-0028, CLM-0029, CLM-0031, CLM-0032, CLM-0034, pending_researcher_adoption)

## 6. 운율 경계 SRC — CLM 부재 확인 (지시 7)

- SRC-360 · `00_참고문헌/03_운율_초점_음성변이/Jun_1998_The Accentual Phrase in the Korean prosodic hierarchy.pdf` — CLM 0건 확인, evidence_status=source_level_only, claim_status=pending_claim_extraction (새 CLM 생성하지 않음)
- SRC-361 · `00_참고문헌/03_운율_초점_음성변이/Jun_2000_K-ToBI Labelling Conventions v3.pdf` — CLM 0건 확인, evidence_status=source_level_only, claim_status=pending_claim_extraction (새 CLM 생성하지 않음)
- SRC-362 · `00_참고문헌/03_운율_초점_음성변이/신지영_2011_한국어의운율.pdf` — CLM 0건 확인, evidence_status=source_level_only, claim_status=pending_claim_extraction (새 CLM 생성하지 않음)
- SRC-356 · `00_참고문헌/03_운율_초점_음성변이/이향원_2021_운율 단위 경계에 위치한 음운의 음성적 변이.pdf` — CLM 0건 확인, evidence_status=source_level_only, claim_status=pending_claim_extraction (새 CLM 생성하지 않음)

지시는 SRC-360·SRC-362였으나 같은 지위의 SRC-361(K-ToBI)·SRC-356(이향원 2021)도 CLM 부재이므로 동일하게 기록했다.

## 7. 현상 간 경계·confound 충돌 후보 (지시 10 — 해석 미확정, ID만)

### PT/NI 경계

- IDs: CLM-0022 CLM-0023 CLM-0024 CLM-0025 CLM-0026 CLM-0027 CLM-0028 CLM-0029 CLM-0031 CLM-0032 CLM-0034
- 쟁점: 이세창 2024(SRC-294)는 ㄴ삽입과 사잇소리를 동일 합성 경계 실현(상보 분포)으로 주장; Zuraw 2011(SRC-338)의 사이시옷 예측 요인 6건이 NI에 교차 태깅됨. registry가 PT·NI를 별개 현상으로 유지하는 것과의 관계는 해석 미확정 — ID만 기록.

### NAN/NAL/LLN 경계·모집단

- IDs: CLM-0064 CLM-0099 CLM-0068 CLM-0069 CLM-0070 CLM-0071 CLM-0072 CLM-0073 CLM-0074 CLM-0087 CLM-0088 CLM-0089 CLM-0090 CLM-0091 CLM-0092 CLM-0081 CLM-0082 CLM-0083 CLM-0084 CLM-0085 CLM-0086
- 쟁점: /ㄴㄹ/ 연쇄의 우세 표면형 보고가 자료 종류에 따라 갈림: 김지유 2026(자유 발화 한자어, [ㄹㄹ] 95.89%) vs Sohn 2008(외래어, 젊은 세대 [nn] 지배형) vs Sim et al 2023(낭독, [ll]~[nn] 변이) vs 서윤정 2022(실험 산출, 유음화 87.2%·비음화 10.8%). 모순이 아니라 어종·과제 조건 차이일 수 있으나 해석 미확정 — 계약 설계 시 모집단 분리 필요성만 기록.

### VH/HIA 환경 중복

- IDs: CLM-0133 CLM-0134 CLM-0135 CLM-0136 CLM-0138 CLM-0123 CLM-0143 CLM-0139 CLM-0140 CLM-0141 CLM-0142 CLM-0144
- 쟁점: 어간말 모음 + /어/계 어미의 모음충돌 문맥이 VH(조화형 선택)와 HIA(활음화·축약·탈락) 양쪽에 걸침(Han 2009 이중 태깅 5건, Jo 2023 1건, 박나영 1건). 동일 토큰의 이중 계상 위험 — 현상 간 토큰 배타/중복 규칙은 미확정, ID만 기록.

## 8. ID 독립 재검사

- JSON에 등장하는 SRC 28종·CLM 156종 전수를 정본 JSONL과 대조 — 누락 0 (all_ids_exist=True).
- CLM 156건 전부가 최소 1개 목록에 포함됨(누락된 claim 없음).

## 9. 정지 선언

산출물 3파일 작성과 ID 감사로 본 작업을 종료한다. 구현(Gate 0)은 시작하지 않았다. 정본·00_참고문헌·코드·config·query·원자료는 수정하지 않았고, git 커밋도 하지 않았다.
