# 2026-08-02 문서·D: legacy 정리 manifest

## 목적

생산 정본과 과거 파일럿·검토·구 실행 지침이 함께 노출되어 다음 단계가 반복되는
문제를 줄인다. 연구의 시행착오와 방법론 근거는 삭제하지 않고 archive한다.

## 문서 정리

- `docs` 최상위의 구 `WORKFLOW/TODO/HANDOFF/GUIDE/PROJECT_SUMMARY/WORKLOG`
  7개를 `archive/pre_production_legacy/`로 이동했다.
- 2026-07 작업 내역을 `archive/work_history/`로 이동했다.
- 종료된 감사·파일럿·구 RUNBOOK·MONITOR·과거 계획 33개를
  `archive/decisions_pre_production/`으로 이동했다.
- 현행 결정 24개만 `docs/decisions/`에 남기고 `_INDEX.md`를 다시 작성했다.
- 낡은 시작 안내와 전체 자산 대장은 각각
  `PROJECT_START_HERE_pre_20260802.md`, `ASSETS_LEDGER_20260724_full.md`로
  보존하고 현재 정본을 짧게 다시 작성했다.
- 원문 삭제 없음. Git 이력과 위 archive 경로에서 추적 가능하다.

현재 문서 읽기 순서는 다음 다섯 개뿐이다.

1. `docs/environment/PROJECT_START_HERE.md`
2. `docs/environment/PROJECT_CURRENT_STATE.md`
3. `docs/RUNBOOK_production_2020_2025.md`
4. `docs/ASSETS_LEDGER.md`
5. `docs/decisions/_INDEX.md`

## D: 대용량 정리

기존 완료분:

- `pre_jamo_compressed_20260728`의 5항목을 E:에서 CRC·count/bytes·SHA로
  검증한 뒤 2026-07-30 D: 55.883GiB를 정리했다.

2026-08-02 신규 묶음:

```text
E:\READ_ONLY_ARCHIVE\2026_summer_research\legacy_d_workspace_20260802
```

- 현재 공통사전 r2는 allowlist에서 제외해 D:에 유지한다.
- 구 r1, A/B 검토, 대체 release, `mfa_eojeol` 구 pilot/pilots를 먼저 archive한다.
- 구 `D:\20_AUDIO\06_textgrid_eojeol\2020–2021`과
  `06_textgrid_merged\2020–2025`는 별도 장시간 단계다.
- 각 원본은 최초 archive의 파일 수·바이트, 7z CRC, archive SHA가 통과한
  항목만 D:에서 제거한다. 성공 항목은 재압축하지 않는다.
- symlink는 `7z -snl`로 링크 자체를 보존한다.

상태·최종 수량의 기계 정본:

```text
outputs/reports/ARCHIVE_legacy_d_workspace_20260802.json
```

## 이동하지 않는 자료

- 모든 형태소·검색·동반 CSV/Parquet
- 원 WAV·JSON·reference
- 2020 WAV ID 복구 파생 코퍼스와 계약
- 공통 Jamo r2 release와 model/adoption manifest
- 승인·제외·미해결 기호 기록
- 현재 MFA state·lock·input/alignment contract
- 신규 6-tier·동반표 생산 경로

archive I/O와 MFA는 동시에 실행하지 않는다.
