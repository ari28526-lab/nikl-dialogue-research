# 자산 대장 — 현재 생산 기준

최종 갱신: 2026-08-02 KST

이 문서는 현재 필요한 자산의 위치만 기록한다. 2026-07-24 전체 인벤토리는
[archive/ASSETS_LEDGER_20260724_full.md](archive/ASSETS_LEDGER_20260724_full.md)에
보존한다. 추정으로 완료를 선언하지 않고, 대량 이동 뒤에는 manifest 또는 보고서로
갱신한다.

## D: DATA_SSD — 원자료와 현재 생산 자산

| 자산 | 현재 역할 | 상태 |
|---|---|---|
| `D:\00_RAW\dialogue_json` | 전사 JSON 원본 | 보존, 수정 금지 |
| `D:\00_RAW\reference\*` | 우리말샘·MP·LS·다층위 reference | 4종 D: 확보 기록 있음; 사용 직전 실물·SHA 재확인 |
| `D:\10_LAYERS\01_bareun_raw` | 연도별 형태소 분석 CSV | 보존 |
| `D:\10_LAYERS\05_search_master` | 동결 5,103,356발화 search master | 보존, `_build_meta` SHA 계약 |
| `D:\10_LAYERS\09_morph_search_v3_staging` | pre-MFA 연도별 7개 조합검색표 | 2020 23/23 완료; 2021–2025 미완료 |
| `D:\20_AUDIO\03_wav` | 원 WAV·LAB 코퍼스 | 원자료, 수정 금지 |
| `D:\20_AUDIO\04_wav_id_recovered_staging\individual\2020` | 2020 MFA 전용 파생 WAV | 868,603건, 계약 passed |
| `D:\20_AUDIO\08_textgrid_research_v2_staging` | 신규 r2 6-tier·동반표 출력 | 생산 전/미생성 |
| `D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728` | 현재 공통 Jamo r2 사전 | 보존, 연도별 MFA 필수 |
| `D:\mfa_eojeol` | 입력·정렬 계약, marker, log, lock | 현재 생산 상태, 보존 |
| `D:\mfa_tmp`, `D:\mfa_eojeol_out` | 용량 폴백 작업경로 | 현재 연도 실행 중에만 사용 |

CSV는 정리 대상이 아니다. 형태소 CSV, 조합검색 7표, post-MFA 동반표 4개,
WAV–TextGrid–metadata 연결표, 승인·제외·미해결 기호표는 모두 연구 인프라의
필수 산출물로 유지한다.

## E: — 읽기 전용 archive

archive root:

```text
E:\READ_ONLY_ARCHIVE\2026_summer_research
```

| 묶음 | 내용 | 상태 |
|---|---|---|
| `pre_jamo_compressed_20260728` | 구 2020/2021 TextGrid, 구 2021 MFA DB/temp, stale temp, 실패 모델 clone | 검증 성공; D: 55.883GiB 정리 완료 |
| `wav_id_recovery_2020_eb64f80d9106` | 2020 WAV ID 복구 전 영향 세션 | 128 ZIP + 129 manifest, 계약 passed |
| `wav_id_recovery_2020_eba4f3c7debf` | 첫 복구 계약의 안전 중단 증거 | 역사·실패 근거로 보존 |
| `legacy_d_workspace_20260802` | 구 공통사전 r1/A-B/파일럿과 구 `06_textgrid_*` | 2026-08-02 완료; TextGrid 8항목 7,341,358파일/33.297GiB를 2.226GiB로 검증 보존 후 D: 정리 |

archive는 원자료 정본이 아니라 과거 산출물의 재현·감사 근거다. E: archive가
검증되기 전에는 대응하는 D: 경로를 제거하지 않는다.

## H: SAMSUNG — 과거 전체 백업

2026-08-02 여유가 약 93GiB여서 새 archive 대상으로 사용하지 않는다. D:와 E:의
현재 생산 경로와 혼동하지 않도록 읽기 전용 비교·비상 복구용으로만 취급한다.

## 저장소와 GitHub

```text
C:\Users\ari30\research\2026_summer_research
```

코드·설정·작은 CSV/보고서·방법론 문서의 정본이다. 대형 WAV/TextGrid/DB는 Git에
넣지 않는다. 현재 작업 브랜치는 `agent/harden-pre-bulk-pipelines`이며, 정리 기록은
검증 완료 뒤 커밋·푸시한다.

## 2020 현재 계약

- source contract: `morph_search_v3_20260801/2020/SOURCE_CONTRACT.json`
- WAV recovery contract ID:
  `eb64f80d9106d14c7b2a267811cdf2dc2fe29e890cc335a7029a8cca24a7375f`
- 승인 제외: 음원 미대응 1,834 + 빈 LAB 미해결 기호 53 = 1,887
- 부분 LAB 미해결 기호 6,158: 제외하지 않고 동반 CSV 경고로 보존
- 연구자 승인: 2026-08-02 `ari30`, 두 범주 모두 승인
- MFA 상태: 아직 미시작

다음 생산 명령은 [RUNBOOK_production_2020_2025.md](RUNBOOK_production_2020_2025.md)의
2020 단일 시작 wrapper다. archive I/O와 MFA를 동시에 실행하지 않는다.
