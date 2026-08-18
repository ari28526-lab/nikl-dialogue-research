# 6개년 closeout 정리 장부

기준일: 2026-08-18 KST

## 원칙

- 원자료, 보존 MFA DB, 최종 6-tier, 공통발음 모델·사전, contract, manifest,
  독립 감사, 연구자 decision ledger는 삭제하지 않는다.
- 역사 문서는 현재 지침과 분리하되 시행착오의 증거이므로 일괄 삭제하지 않는다.
- 삭제는 정확한 경로와 재생성 가능성을 확인한 항목만 수행한다.
- 대형 `work` 디렉터리는 이름만 보고 삭제하지 않고, 정본 대체물과 생성 명령을
  확인한 다음 별도 cleanup Gate로 처리한다.

## 이번 closeout에서 삭제한 재생성 캐시

| exact path | 파일 | bytes | 근거 |
|---|---:|---:|---|
| `scripts/colab/__pycache__` | 1 | 13,710 | Python 실행 시 재생성되는 bytecode |
| `scripts/python/__pycache__` | 261 | 4,698,198 | Python 실행 시 재생성되는 bytecode |
| `tests/__pycache__` | 156 | 1,226,758 | test 실행 시 재생성되는 bytecode |
| `work/__pycache__` | 1 | 11,759 | 임시 helper bytecode |
| **합계** | **419** | **5,950,425** | 정본·소스·결과에 영향 없음 |

네 경로의 419파일·5,950,425 bytes를 삭제했고 잔존 경로 0을 확인했다. Git 추적
파일은 포함되지 않았다.

`work/MFA_RESEARCH_SCHEMA_REVIEW_12_20260731.partial`은 이름상 미완성이고 같은
계열의 v2/v3 완료 디렉터리가 있지만, 내부에 WAV·TextGrid·CSV/LAB 55개가 있어
자동 안전 검사가 삭제를 차단했다. 이 항목은 단순 캐시가 아니므로 **보존**하며,
내용·정본 대체·archive 여부를 확인한 별도 exact-path 승인 전에는 삭제하지 않는다.

## 보존 확정

- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815`
- `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc1_20260818`
- `outputs/releases/nikl_dialogue_research_db_v1_active_view_contract_v1_20260818`
- `outputs/reports/mfa_r3_research_qc_common_pron_mfa_r3_20260809`
- `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809`의 보존 DB와 최종 `research_6tier`
- `D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809`
- `D:\10_LAYERS\09_morph_search_v3_staging\morph_search_v3_20260801`
- recovery D0–D10 release·감사·연구자 판단
- `docs/archive`: 현재 지침이 아닌 역사·실패 증거

## 별도 Gate 전 삭제하지 않을 대형 후보

현재 `work`에는 과거 pilot·export 검토 복사본이 약 1.5 GiB 이상 남아 있다.
특히 다음은 용량이 크지만, 생성 코드·정본 대체물·허용 표본 보존 여부를 따로
검사하기 전에는 삭제하지 않는다.

| 경로 | 약 크기 | 현재 판단 |
|---|---:|---|
| `work/mfa_export_queue_pilot_21965_20260726` | 1001.56 MiB | 정본 대체 확인 뒤 archive/delete 후보 |
| `work/mfa_export_queue_pilot_20260726` | 410.26 MiB | 정본 대체 확인 뒤 archive/delete 후보 |
| `work/venv_parquet_qc` | 92.05 MiB | 재생성 가능하지만 환경 재현 비용 검토 |
| `work/venv_pdf` | 64.76 MiB | 문서 렌더링 의존성 확인 뒤 처리 |
| `work/common_pron_prepare_revalidation_20260729` | 36.78 MiB | 과거 검증 증거와 중복 여부 확인 |
| `work/benchmark_research_exporter_10k_20260801` | 31.04 MiB | benchmark 보고서 존재 여부 확인 |
| `work/MFA_RESEARCH_SCHEMA_REVIEW_12_20260731.partial` | 1.58 MiB | 연구 검토 파일 55개; 별도 확인 전 보존 |

이 목록은 삭제 승인이 아니라 다음 정리 후보 inventory다.

## 문서 정리 상태

현행 문서는 `docs/environment/PROJECT_CURRENT_STATE.md`,
`docs/RUNBOOK_production_2020_2025.md`, 이 closeout 폴더를 진입점으로 한다.
`docs/archive` 61개 Markdown은 역사 자료로 보존한다. 외부 HTML 작성자는
`SOURCE_MAP_FOR_HTML.md`의 우선순위를 따라야 한다.
