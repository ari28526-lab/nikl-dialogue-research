# 2단계 G1 결과: ㄴ 삽입 생산 query v1 동결

작성일: 2026-08-18 KST
전제: `PLAN_stage2_target_query_and_realization_design_20260818.md` G1,
연구자 G1 착수 승인(같은 날 세션).

## 결과

`config/target_queries/n_insertion_production_v1_20260818.json`을 동결했다.

- query SHA-256:
  `744bd8cb45769074b7299a8b553784b7cc9a436ac70f2479f1f674a98edb3ab6`
- 승인: `outputs/approvals/APPROVAL_n_insertion_query_v1_freeze_20260818.json`
  (approver ari30, 정의서·B1 계획 SHA에 결속)
- 두 질의: `QN1_N_INSERTION_INTRA_EOJEOL_V1` / `QN2_N_INSERTION_INTER_EOJEOL_V1`
  — 동일 분절 조건에 `boundary_scope`만 상이, 상한 없음, 6개년 대상.

## 조건 요약

포함: 좌·우 unit 한글(`left/right_unit_type=hangul`, 숫자·기호 인접 자동
제외), 왼쪽 마지막 음절 종성 존재(`left_coda_jamo` nonempty), 오른쪽 초성
ㅇ(`right_onset_zero`) + 중성 {ㅣㅑㅕㅛㅠㅖㅒ}, 오른쪽 품사 정규식
`^(?!J|E)`(J*/E* 제외). 왼쪽 품사는 무제한(넓은 추출 — 연구자 확인 사항:
"는#여행" 유형 포함). ㅢ 제외. 경계유형·`etym_check_needed`는 필터가 아니라
추출 후 `left_pos/right_pos` 증거로 파생(연구자 3결정 반영).

## 검증 (실측)

- 열 실재: 2020 `morph_boundaries.csv.gz` 헤더 실측 — `boundary_scope`,
  `left/right_pos`, `left/right_unit_type`, 자모 분해 열 존재 확인.
  **builder 코드 수정 없이** 선언형 조건만으로 B1 환경 표현 가능.
- 케이스 검증: builder의 `condition_matches/row_matches`를 그대로 import해
  23케이스(포함 12·제외 11) 전부 기대 일치. `validate_query_set` 통과.

## 다음 Gate (별도 GO 필요)

1. **G2**: 의미번호·A3 `etym_type` join 계약 — A3 정본 위치는
   `docs/ASSETS_LEDGER.md`에서 확인 후 진행.
2. **G3**: 2020 단일 연도 생산 감사 — builder에 `--years` 런타임 필터(config
   불변, 실행 연도만 제한) 최소 추가가 선행 조건. 수량·열·상태만 감사하고
   새 청취 파일럿은 하지 않는다.
3. G4 이후는 G3 통과·연구자 GO 후.

## 안전 확인

MFA 실행 0, D: 쓰기 0(읽기 전용 헤더 확인만), 원자료·RC0/RC1·6-tier 수정 0.
production query 실행은 여전히 미승인 상태로 유지된다.
