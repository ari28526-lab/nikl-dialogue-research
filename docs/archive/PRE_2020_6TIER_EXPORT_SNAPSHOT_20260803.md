# 2020 6-tier export 직전 정리 snapshot

기록일: 2026-08-03 KST

## 목적

2020 공통 Jamo r2 전수 MFA 계산과 post-MFA 검토를 끝낸 뒤, 보존 DB에서 최종
6-tier·동반표를 내보내기 직전의 활성/보관 경계를 고정한다. 이 문서는 현재 실행
정본이 아니라 당시 상태의 archive 기록이다.

## 코드 archive 정책

- 활성 코드를 별도 복제 폴더로 중복하지 않는다.
- 코드·설정·시험·문서의 복구 기준은 Git commit과 GitHub 원격이다.
- 이 정리의 직전 기준 commit은 `056bf2b`다.
- 생성 결과와 검토 사본은 Git 코드와 분리하고, 활성 근거와 대체된 사본만
  폴더명으로 명확히 구분한다.

## 로컬 이동 내역

| 구분 | 이전 경로 | archive 경로 | 검증 |
|---|---|---|---|
| 최초 단순 검토본 V1 | `outputs/reviews/MFA_2020_REVIEW_SIMPLE_20260803` | `outputs/reviews/archive/MFA_2020_REVIEW_SIMPLE_V1_20260803` | 83파일, 1,328,922 bytes 보존 |
| 수정 전 경계 그림 감사 | `outputs/reports/MFA_2020_TIER_BOUNDARY_AUDIT_CURRENT_20260803` | `outputs/reports/archive/MFA_2020_TIER_BOUNDARY_AUDIT_PRE_FIX_20260803` | 5파일, 211,280 bytes 보존 |

활성 근거는 다음과 같다.

- `outputs/reviews/MFA_2020_REVIEW_SIMPLE_V2_20260803`
- `outputs/reports/MFA_2020_TIER_BOUNDARY_AUDIT_FIXED_20260803`
- `outputs/reports/AUDIT_2020_FULL_DB_TIER_EDGES_20260803.json`
- `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_export_20260803/2020`

대형 WAV·TextGrid·DB와 위 로컬 검토 산출물은 Git에 넣지 않는다. 경로·수량·계약
의미만 문서로 커밋한다.

## Dropbox

이 정리에서는 Dropbox 파일을 이동하거나 삭제하지 않았다. Dropbox root의 검토
폴더는 전달·열람용 사본이며, 로컬 V2·manifest·SHA와 결합 승인 계약이 보존된 뒤
연구자가 직접 삭제한다. Dropbox 삭제는 생산 DB나 최종 export에 영향을 주지
않는다.

## 다음 단계

`docs/RUNBOOK_production_2020_2025.md`의 현재 시작점에 따라
`resume_2020_export_after_post_mfa_review.ps1 -PreflightOnly`를 통과시킨 뒤,
같은 wrapper로 보존 DB export를 시작한다. 구 `start_2020_mfa_after_review.ps1`은
재실행하지 않는다.
