# 연구 진행 현황 (2026-08-18 기준)

**기계적 분석·MFA 정렬 완결층의 D: 고정 상태와, 그 다음 연구 단계의 진행
위치를 한 장으로 요약한 현황 문서.** 정본 수치는 각 절의 근거 파일에서
가져왔으며 모두 독립 감사를 통과한 값이다.

## 1. 완결·고정된 층: 기계적 분석 + MFA 정렬

아래 전부가 **완료 상태로 D: 드라이브에 고정**돼 있다(2026-08-18 12개 자산
실측 확인). 이 층은 동결 정본이며 이후 연구는 참조만 한다.

| 층 | 내용 | 수량 | D: 위치 |
|---|---|---|---|
| 원자료 | JSON 전사·WAV (2020–2025) | 5,103,356발화 | `00_RAW`, `20_AUDIO\03_wav` |
| 형태소 분석 | 바른 재분석 CSV | 6개년 전량 | `10_LAYERS\01_bareun_raw` |
| 검색층 | morph_search.v3 조합검색 7표 | 5,103,356발화 · 50,955,891 token | `10_LAYERS\09_morph_search_v3_staging` |
| A2 의미번호 | 형태소 단위 sense_id/method/candidates | 6개년 전량 | `10_LAYERS\02_sense_annotated` |
| A3 빈도사전 | 형태소·어절·의미별·층화·분산도 + 어원 | 형태소 165,920항 · 어절 857,443항 | `10_LAYERS\03_freq_dictionaries` |
| 발음 참조 | 우리말샘 registry v2 + 비교표 | registry 1,192,729행 | `10_LAYERS\10_pronunciation_reference` |
| 공통발음 | r3 release (사전·모델·runtime hash 동결) | 796,061변이 사전 | `mfa_common_pron\releases\common_pron_mfa_r3_20260809` |
| MFA 정렬 | r3 fresh realign + 6-tier TextGrid | **4,286,046발화** (독립 QC 통과) | `mfa_eojeol\r3\...\research_6tier` |
| 상태 회계 | RC0/RC1/active view (누락·중복 0) | 후속 817,310 이유별 장부 | `30_RELEASES\stage1_...` 패키지 |

회계식(전수 검증 완료):

```text
5,103,356 = 4,286,046 정렬 안전본체 + 95,860 MFA전 기술후속
          + 3,086 MFA후 기술후속 + 718,364 발음후속 + 0 연구제외
```

**주의**: 전체 510만 발화는 검색 가능하지만 6-tier 정렬 본체는 428만이다.
MFA phone은 실제 발음 판정이 아니다.

### 공유 방식 (D:\30_RELEASES\00_공유안내_20260818.md)

- **방식 A** — D: 드라이브 인수인계: 수령자가 NIKL 이용 허가 보유 시.
  원자료+전 파생층 포함, 즉시 연구 가능.
- **방식 B** — 각자 모두의말뭉치 다운로드 + 재현: GitHub 저장소(또는
  `repo_snapshot_f48f5e1_*.zip`)의 코드·계약·manifest로 같은 수량을 재현.
  RUNBOOK과 재사용 가이드 준수, SHA·수량 회계로 동일성 검증.

2026-08-19 배포 범위는 위 두 방식 모두 **자료구축 1단계(A단계)**로 제한한다.
범용 `morph_search.v3` 인프라는 포함하지만 G1–G8 특정 현상 query·후보·검토·
실현 판정은 제외한다. 방식 B의 GitHub 공개는 가능성을 고려한 선별 공개 후보이며
아직 확정되지 않았다. 현행 진입점은 저장소 루트 `RELEASE.md`다. A단계 전용
D: package는 `D:\30_RELEASES\stage1_infrastructure_distribution_20260819`이며,
비전공자용 단일 HTML을 포함한 56개 payload의 SHA·누락·금지 범주 독립 감사가
`passed`다.

## 2. 그 다음 단계(2단계 연구)의 현재 위치

2단계 설계(G0–G8)는 `PLAN_stage2_target_query_and_realization_design_20260818.md`가
정본이다. 현재 **G1–G4 완료, G5부터 남음**.

| Gate | 내용 | 상태 |
|---|---|---|
| G1 | ㄴ삽입 생산 query v1 동결 (intra/inter, SHA `744bd8cb…`) | ✅ 완료 (연구자 승인) |
| G2 | 의미번호·어원·빈도 join 계약 동결 (SHA `12d81163…`) | ✅ 완료 |
| G3 | 2020 단일 연도 생산 감사 | ✅ 통과 (13/13) |
| G4 | 2021–2025 후보 전수 생성 | ✅ 완료 (감사 6/6) |
| G5 | 후보→TextGrid 문맥 시간 연결 | ⬜ 미착수 |
| G6 | 검토 bundle·workbook | ⬜ **표본 전략 결정 대기** |
| G7 | 연구자 실현 판정 (append-only ledger) | ⬜ 미착수 |
| G8 | 표적 후속 (recovery 회수·RC1 enrichment·KOINA·wav2vec2) | ⬜ 미착수 |

### G4까지의 산출 (6개년 후보)

| 연도 | 후보 행 | 어절 내부 | 어절 간 | 고유 발화 |
|---:|---:|---:|---:|---:|
| 2020 | 101,638 | 42,604 | 59,034 | 93,360 |
| 2021 | 206,037 | 81,865 | 124,172 | 184,328 |
| 2022 | 141,966 | 53,759 | 88,207 | 127,107 |
| 2023 | 123,381 | 45,570 | 77,811 | 108,785 |
| 2024 | 185,401 | 65,109 | 120,292 | 157,565 |
| 2025 | 183,480 | 64,719 | 118,761 | 150,459 |
| **합계** | **941,903** | **353,626** | **588,277** | **821,604** |

- 6개년 94만 행 전수에서 변수 join 이상 0 (의미번호 층과 토큰화 완전 일치).
- 한자어 내부 후보 1,210건, RC1 수동 보정 발화 6건 포함.
- 이 후보는 "가능 환경의 넓은 후보"이며 실현 판정 전 단계다.
- 산출물: C: `outputs\candidates\`(정본) + D:
  `30_RELEASES\stage2_n_insertion_candidates_20260818`(SHA 검증 미러).

### 남은 결정 1건

**G6 검토 표본 전략** — 94만 행 전수 청취는 비현실적이므로 층화 표본
(경계유형×어원분류×빈도대×연도) 우선 청취를 권장. 층화 세부 설계는 연구자
승인 후 확정한다.

## 3. 근거 파일

```text
docs/environment/PROJECT_CURRENT_STATE.md               (최상단 진입점)
docs/decisions/DECISION_stage1_data_infrastructure_closure_20260818.md
docs/decisions/PLAN_stage2_target_query_and_realization_design_20260818.md
docs/decisions/RESULT_stage2_G1_query_freeze_20260818.md
docs/decisions/RESULT_stage2_G2_variable_join_contract_20260818.md
docs/decisions/RESULT_stage2_G3_2020_production_audit_20260818.md
docs/decisions/RESULT_stage2_G4_full_six_year_candidates_20260818.md
docs/decisions/RESULT_stage2_candidates_D_mirror_20260818.md
outputs/reports/SIX_YEAR_INFRASTRUCTURE_CLOSEOUT_20260818.json
outputs/reports/AUDIT_stage2_g3|g4_n_insertion_<연도>_20260818.json
D:\30_RELEASES\00_공유안내_20260818.md
```
