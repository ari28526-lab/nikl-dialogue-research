# 2021 진입 전 저장소 정리 archive manifest

작성일: 2026-08-03 KST

## 범위와 보호 계약

2020 Gate B 통과 뒤 2021을 시작하기 전에 구 문서·구 코드·완료 파일럿과
2021–2025 구 실행 상태를 현재 정본에서 분리했다. 저장소 안의 문서·코드·파일럿은
삭제하지 않고 archive 경로로 이동했다. D:의 구 2021 활성 상태 9개는 E: 압축본의
CRC와 SHA-256을 검증한 뒤 활성 위치에서 제거했다. 다음 2020 완성 자산은 모든
이동·정리 대상에서 명시적으로 제외했고, 각 단계 뒤에도 존재를 재확인했다.

- `D:\20_AUDIO\08_textgrid_research_v2_staging\2020`
- `D:\mfa_tmp\2020\2020.db`
- `outputs/reports/GATE_B_2020_*.json`
- `outputs/reports/mfa_year_queue_mfa_r2_prod_2020_export_20260803/`
- `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_export_20260803/`
- `outputs/reviews/mfa_production_2020_mfa_r2_prod_2020_export_20260803/`

## 로컬 산출물 이동

트리 SHA-256은 `relative_path|bytes|file_sha256`을 상대경로순으로 LF 결합한
문자열의 SHA-256이다. 이동 전후 파일 수·바이트·트리 SHA가 모두 같았다.

| archive 경로 | 파일 | bytes | tree SHA-256 |
|---|---:|---:|---|
| `outputs/archive/pre_2021_local_20260803/mfa_r2_review_workbook_20260725` | 3 | 60,955 | `eae8e4a308c6a4b4bd8dcc69c8212f108a27765d11a2a24c078f4b95914fc4dc` |
| `outputs/archive/pre_2021_local_20260803/phoneme_roman_pilot_20260731` | 5 | 2,542,535 | `7b53e96b0ffb0d621ce799d28be073af62a2d5025a12f9e11862691492183481` |
| `outputs/archive/pre_2021_local_20260803/phoneme_roman_portable_20260801` | 6 | 436,084 | `5d01ebbe4c7bf054b6aa0a557d0f8ac0907430e94d7d20351741f791af9081ee` |
| `outputs/archive/pre_2021_local_20260803/textgrid_6tier_mini_pilot_20260801` | 12 | 308,428 | `bd2dd9d3d3949b86a833aa7db20885ead10b089fbdd8e0af63ec71fdd3b163be` |
| `outputs/archive/pre_2021_local_20260803/textgrid_6tier_mini_pilot_pre_repro_fix_20260801` | 11 | 306,992 | `18d05b694bc5d47222c59908624419f474b6d65c07356af7126482874c14d6cb` |

## 구 문서·코드 이동

- 구 기기 설정 문서, 반복 검토 학습노트, 구 Dropbox 구조 결정문 3개를
  `docs/archive/pre_2021_cleanup_20260803/`로 이동했다. 학습노트 SHA-256은
  `a445764f3352f9005c6107f77a1136d8c0d3266f746b1831e936bf3652b16efe`,
  구 구조 결정문 SHA-256은
  `a0d00fb00380e713082dbbe217495846c4b3aeabe7b1a298ba9a27986782bb97`다.
- 일회성 이행·구 형태소 LAB·구 잔여분 재정렬·병목 파일럿 코드 13개를
  `scripts/archive/pre_2021_legacy_20260803/`로 이동했다.
- 원문 내용과 Git 이력은 보존했다. 현행 production wrapper, 공통 Jamo r2,
  6-tier exporter, 연도 큐, 감사 및 Gate B 코드는 이동하지 않았다.

개별 파일의 이동 전 SHA-256은 Git의 archive 커밋과 함께 보존하며, 실행 가능
정본 목록은 `scripts/SCRIPTS_INDEX.md`가 유일한 기준이다.

## 2021–2025 구 외부 작업 정리

새 2021 정렬 전에 D:의 생산·임시·상태 경로를 읽기 전용으로 조사했다.

- `D:\20_AUDIO\06_textgrid_merged`, `06_textgrid_eojeol`,
  `07_textgrid_eojeol_g2p_staging`, `08_textgrid_research_v2_staging`,
  `D:\mfa_tmp`, `D:\mfa_eojeol_out`에는 2021–2025 연도 결과 폴더가 0개였다.
- 구 2021 TextGrid와 MFA DB/temp는 기존
  `E:\READ_ONLY_ARCHIVE\2026_summer_research\pre_jamo_compressed_20260728`에
  CRC 검증된 상태로 보존되어 있고 대응 D: 원본은 이미 정리됐다.
- 구 `06_textgrid_merged`의 2021–2025와 구 `06_textgrid_eojeol`의 2021은
  `E:\READ_ONLY_ARCHIVE\2026_summer_research\legacy_d_workspace_20260802`에
  항목별 검증 보관된 뒤 D:에서 정리됐다.
- D: 활성 위치에 남은 구 2021 로그·LAB 완료표시·낡은 입력계약 9개,
  4,208,271 bytes는 다음 묶음에 보관했다.

```text
E:\READ_ONLY_ARCHIVE\2026_summer_research\pre_2021_active_state_20260803
```

압축본은 458,443 bytes이며 7-Zip 전수 test가 통과했다. SHA-256은
`fb4ccb859a60b9833960d38ba97330a530fbd89be0b820e08e32ebf004edbc39`다.
외부 manifest와 저장소 보고서
`outputs/reports/ARCHIVE_pre_2021_active_state_20260803.json`은
`status=success`, `active_sources_remaining=0`,
`production_2020_rechecked=true`를 기록한다.

2021의 기존 `.lab`은 동결 CSV에서 만든 재사용 가능한 MFA 입력이므로 삭제하거나
압축 이동하지 않았다. 대신 구 `2021.lab_input_done.json`을 archive했으므로 새
2021 실행은 기존 LAB을 무조건 신뢰해 건너뛰지 않고 내용 계약을 전수 재검증하며,
CSV와 다른 파일만 다시 쓴다. 2021 구 align/merge marker 2개는 2026-07-30에 이미
`D:\mfa_eojeol\done\archive_stale\r2_transition_20260730_legacy_markers`로
격리됐으므로 역사 증거로 그대로 유지했다.

`D:\10_LAYERS\09_morph_search_v3_staging`, 공통 Jamo r2 사전, 원본 WAV/CSV와
2020 완성 TextGrid·DB·Gate B 자료는 이번 외부 정리에서 변경하지 않았다.
