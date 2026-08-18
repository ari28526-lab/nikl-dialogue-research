# 2단계 설계: 표적 질의에서 연구자 실현 판정까지

작성일: 2026-08-18 KST
전제: `DECISION_stage1_data_infrastructure_closure_20260818.md`(1단계 공식
종료). 이 문서는 2단계의 전체 구조·Gate 순서·출력 계약을 정본으로 고정한다.
개별 Gate의 실행은 각 Gate의 preflight·감사·연구자 승인을 별도로 통과해야
한다. 이 문서 자체는 어떤 대량 실행도 승인하지 않는다.

## 1. 목적과 계승 원칙

2단계의 목적은 형태음운 환경 후보를 재현 가능하게 추출하고, 연구자가
WAV·TextGrid를 근거로 실제 실현을 판정하며, 그 판정을 provenance와 함께
축적하는 것이다. 1단계에서 확립한 원칙을 그대로 계승한다.

- exact-ID 회계: 입력 = 산출 + 이유 있는 잔여가 모든 Gate에서 성립
- fail-closed: 부분 성공을 성공으로 처리하지 않음
- append-only: 원본·RC0·RC1·6-tier를 덮어쓰지 않고 파생·overlay만 추가
- 독립 감사: 생성기와 별도 코드의 재계산 검증
- 연구자 Gate: 범위·hash에 결속된 명시 승인 없이 다음 대량 단계 없음
- MFA phone ≠ 실현: 자동 phone은 후보 탐색·시간 접근 보조일 뿐

## 2. Gate 순서 (G0–G8)

### G0. 전제 동결 확인 (읽기 전용)

1단계 종료 결정, B1 개정 승인(`APPROVAL_n_insertion_B1_revision_20260818.json`,
bound SHA 2건), active view 계약이 유효한지 확인만 한다.

### G1. 생산 query v1 동결

- `PLAN_n_insertion_B1_to_production_query_20260818.md`의 두 모집단
  (`intra_eojeol` / `inter_eojeol`)을 **선언형 JSON config**로 작성한다.
  형식은 파일럿에서 검증된
  `config/target_queries/db_v1_target_manifest_pilot_20260818.json`을
  확장하며, builder는 `scripts/python/build_db_v1_target_manifest.py` 계열을
  재사용한다(신규 엔진을 만들지 않는다).
- J*/E* 앞 전부 제외, 숫자·기호 unit 인접 제외, 경계유형(N+N/접두+어근/
  어근결합/기타) 거친 분류 후 사람 세분류, 한자어 내부 후보는
  `etym_check_needed` 표시 후 G2에서 확정 — 연구자가 2026-08-18 확정한
  3결정을 그대로 반영한다.
- 두 모집단은 서로 다른 query ID로 분리하고, query SHA를 기록해 이후 모든
  산출물에 결속한다.
- 참고: 세션 초안 `search_env.py`(definition.md 예시 7건 통과)는 환경
  조작화의 참고 구현이다. 저장소 반영 전 실제 세션 CSV의 `tagged` 포맷
  실측 대조가 필요하며, 생산 경로는 위 builder 확장을 우선한다.

### G2. 의미번호·어원 join 계약

- `sense_id/source/status/candidates/confidence`를 분석 변수로 보존하는
  join 계약을 동결한다. 의미번호는 후보 필터가 아니다.
- A3 빈도사전 `etym_type` 컬럼과의 조인으로 `etym_check_needed` 후보의
  한자어 내부/고유어 결합을 확정한다.
- join 커버리지(부여/다의/미부여 비율)를 감사하고, 미부여를 삭제하지 않고
  상태로 보존한다.

### G3. 2020 단일 연도 생산 감사

- G1 query를 2020에만 실행해 **수량·열·상태만** 감사한다. 새 청취 파일럿은
  하지 않는다(승인 문서의 지시).
- 검사 항목: 의미번호 join 누락, occurrence ID 중복,
  `primary_status`/`textgrid_available`/`followup_required` 등 자산 상태
  은폐 여부, 두 모집단의 분리 유지.

### G4. 2020–2025 후보 전수 생성

- 같은 query SHA로 6개년을 연도 checkpoint형으로 생성한다. 검색층
  (`morph_search.v3`) 기반이므로 MFA·음성 자산과 무관하게 실행 가능하다.
- 후속 817,310건 발화도 후보에 포함될 수 있으며, 삭제하지 않고 상태 열로
  구분한다. 연도별 회계식(입력 발화 대비 후보·비후보·오류)을 보고서에
  남긴다.

### G5. 문맥 시간 연결 전수 적용

- `scripts/python/link_db_v1_target_intervals.py` 계열로 후보 occurrence를
  `words` interval의 review context span에 연결한다.
- TextGrid가 없는 후보(후속 발화)는 `pending_textgrid_asset_unavailable`
  상태로 보존한다. 연결 실패는 후보 삭제 사유가 아니다.
- `target_xmin/xmax`는 검토 문맥이며 음운 경계·실현이 아니라는 계약 문구를
  산출물 schema에 포함한다.

### G6. 검토 bundle·workbook 생성

- 확정 질의에 대해서만 WAV·TextGrid·CSV를 복사한 번호순 flat bundle과
  판정 workbook을 만든다(1단계 검토 비용 교훈 반영).
- 표본 순서·크기(예: 층화 표본 우선 청취 후 전수)는 연구자가 이 Gate에서
  결정한다.

### G7. 연구자 실현 판정 ledger

- `realization_decision`은 연구자만 append-only로 기록한다. 최소 schema:

```text
target_occurrence_id, year, utt_id, query_sha,
decision ∈ {realized, not_realized, uncertain,
            excluded_noise, excluded_overlap, excluded_other},
decision_basis(자유 기술), boundary_note(수동 경계 필요 여부),
reviewed_at, reviewer
```

- 이 ledger가 개별 연구의 **분석 분모**를 정의한다. 인프라 분모(510만/
  428만)와 혼동하지 않도록 분모 결정을 별도 decision ledger로 남긴다.
- 자동 phone·G2P·보조모델 출력은 decision 열에 들어갈 수 없고 참고 열로만
  동반한다.

### G8. 표적 후속 (선별 실행)

실제 후보에 포함된 exact-ID에 한해서만 연다.

- 후속 발화(recovery inventory)의 표적 회수: 이유별 장부에서 해당 ID만
  꺼내 별도 shard·용량 Gate로 처리. 전수 회수를 열지 않는다.
- RC1 16건 중 표적 포함 ID의 형태소·phone enrichment Gate.
- 선별 자료의 KOINA 운율 분석(원 발화 ID·source interval provenance 유지).
- wav2vec2/HuBERT phone 후보는 MFA 열을 덮지 않는 sidecar 보조열로만 추가
  (`NOTE_wav2vec2_phone_candidate_layer_20260727.md` 원칙 유지).
- 수동 경계 수정은 D10과 같은 격리 overlay → 채택 Gate 패턴을 재사용한다.

## 3. 산출물 계약 요약

| 산출물 | 계약 |
|---|---|
| query config | 선언형 JSON, query SHA, 모집단 분리 |
| candidate manifest | occurrence 단위 행, active precedence(RC0+RC1), 자산 상태 열 필수 |
| context link 표 | review context span, SHA 결속, 실패 상태 보존 |
| review bundle | 번호순 flat, WAV/LAB/TextGrid/CSV 동봉, 생성 manifest |
| realization ledger | append-only, 연구자 전용, 분석 분모의 유일한 근거 |
| 후속 실행 기록 | exact-ID shard, preflight, 독립 감사, 승인 JSON |

## 4. 이 설계가 지금 실행하지 않는 것

- 6개년 production query 실행 (G1–G3 통과와 연구자 GO 전까지)
- 전 연도 MFA 재실행, 자동 실현 판정
- recovery 817,255건의 전수 회수
- KOINA·보조 음성모델 전수 실행
- RC1 전면 enrichment

## 5. 다음 실행 순서 (사용자 결정 대기)

1. G1 착수 승인: query config 초안 작성·query SHA 동결을 시작할지.
2. G2의 A3 `etym_type` join 대상 정본 위치 확인(ASSETS_LEDGER 기준).
3. G6 표본 전략(전수 청취 vs 층화 우선 청취)의 사전 선호.

이 세 가지가 정해지면 G1–G3는 power-cube에서 기존 builder 확장으로 진행할
수 있으며, 장시간 배치는 아니다(검색층 기반). G4 전수 생성부터 연도
checkpoint·preflight 절차를 적용한다.
