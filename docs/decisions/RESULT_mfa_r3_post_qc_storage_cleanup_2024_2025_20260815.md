# 2024–2025 r3 post-QC temp exact 정리 결과

작성일: 2026-08-15 KST
상태: 완료·사후 감사 통과

## 목적

연구 원자료와 생산 정본을 D:에 모아 유지하면서, 연구 DB v1 D단계를 위한 최소
작업 공간을 확보했다. 정리 범위는 독립 QC가 끝난 MFA 계산 cache로 제한하고
원 WAV·CSV·r3 DB·최종 6-tier TextGrid·공통발음 자료를 정리 대상으로 삼지 않았다.

## 연구자 승인

승인자: `ari30`

> 2024–2025 r3 QC 완료 MFA temp의 재생성 가능 exact allowlist 126개(35.987
> GiB)를 삭제하고, DB·최종 6-tier·원자료·로그·모델·계약·재현성 파일은
> 보존하는 것을 승인한다.

승인 token `R3_TEMP_CLEANUP_2024_2025_ARI30_20260815`은 다음 범위에만 유효하다.

```text
years          = 2024, 2025
files          = 126
bytes          = 38,640,655,415
release root   = D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809
classification = cleanup_candidate_after_qc
```

## 실행 결과

| 연도 | 삭제 파일 | 삭제 bytes | GiB |
|---|---:|---:|---:|
| 2024 | 63 | 20,533,860,560 | 19.124 |
| 2025 | 63 | 18,106,794,855 | 16.863 |
| 합계 | 126 | 38,640,655,415 | 35.987 |

- preflight: `dry_run_passed`
- apply: `passed`
- 삭제 후보 잔존: 0
- 보호 temp 파일 누락: 0
- D: 여유: 28.197 GiB → 64.184 GiB
- archive: 생성하지 않음. 삭제분은 DB·최종 TextGrid에서 재생성 가능한 계산
  cache이며 exact inventory와 실행 결과 JSON을 재현 근거로 보존한다.

## 보호 자산 사후 감사

- 2024 DB SHA-256:
  `b55d69ded19085d1e97abe13b0a62585a3f638c854cb08dcecf18ddc66cec110`
- 2025 DB SHA-256:
  `5d7eab5a986dd39af2fc163d94bd0d8a378a891d242f984a2e536a24fcd5c0e6`
- 두 DB 모두 연구 DB v1 A–C 정본 SHA와 일치한다.
- 2024·2025 최종 `research_6tier` root와 `TABLES_MANIFEST.json`이 존재하고
  manifest SHA가 동결값과 일치한다.
- 연도 입력 계약·alignment 계약 SHA가 동결값과 일치한다.
- `D:\20_AUDIO` 원자료 root와 공통발음 r3 release root가 존재한다.
- 실행기는 temp 연도 root 밖 경로, `.db`, 모델·tree·log·yaml, 미분류 파일을
  후보로 받지 않으며 symlink와 SQLite transaction이 있으면 중단한다.

대용량 DB 두 개의 통합 사후 해시는 120초 명령 제한에 걸렸으나 파일 변경은
없었다. 연도별로 분리해 다시 계산해 두 DB 모두 동결 SHA와 일치함을 확인했다.

## 증거

- `outputs/reports/mfa_r3_storage_cleanup_review_20260815/SUMMARY.json`
- `outputs/reports/mfa_r3_storage_cleanup_review_20260815/INVENTORY_r3_temp_2024.json`
- `outputs/reports/mfa_r3_storage_cleanup_review_20260815/INVENTORY_r3_temp_2025.json`
- `outputs/reports/mfa_r3_storage_cleanup_review_20260815/APPLY_PREFLIGHT.json`
- `outputs/reports/mfa_r3_storage_cleanup_review_20260815/APPLY_RESULT.json`
- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815/BASE_RELEASE_MANIFEST_2020_2025.json`

## 다음 Gate

D:는 계속 정본 저장소로 유지한다. 다음 단계는 D0에서 A–C 출력 SHA와 저장공간
상태를 입력 계약으로 고정하고, D1에서 후속 817,310건을 reason·year·session별
exact-ID routing 장부로 나누는 일이다. 이 정리 완료는 recovery corpus 생성이나
MFA 재실행을 승인하지 않는다.
