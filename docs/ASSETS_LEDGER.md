# 자산 대장 — 현재 생산 기준

최종 갱신: 2026-08-07 KST

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
| `D:\10_LAYERS\09_morph_search_v3_staging` | pre-MFA 연도별 7개 조합검색표 | 2020·2021 연도 manifest success; 나머지는 각 생산 연도 직전 checkpoint 생성 |
| `D:\10_LAYERS\10_pronunciation_reference\dictionary_pron_registry_v2_20260805` | 우리말샘 1:N·예외 발음, occurrence와 규칙/사전/MFA 비교표 | registry 1,192,729행 채택; 2020·2021 occurrence 5,767,506/12,015,453행, 비교표 3,042,451/6,610,698행, index 870,437/1,373,920행 전수 검증 |
| `D:\20_AUDIO\03_wav` | 원 WAV·LAB 코퍼스 | 원자료, 수정 금지 |
| `D:\20_AUDIO\04_wav_id_recovered_staging\individual\2020` | 2020 MFA 전용 파생 WAV | 868,603건, 계약 passed |
| `D:\20_AUDIO\08_textgrid_research_v2_staging\2020` | 2020 신규 r2 6-tier·동반표 출력 | TextGrid 868,187개·독립 감사 성공·Gate B 통과 |
| `D:\20_AUDIO\08_textgrid_research_v2_staging\2021` | 2021 신규 r2 6-tier·동반표 출력 | TextGrid·동반표 1,371,883발화 완료; 후행 무음 word 표지 19건 국소 정규화 |
| `D:\20_AUDIO\09_textgrid_pron_reference_v1_pilot_20260805` | 7번째 `pron_reference_utt` 구현 파일럿 | 2020 2세션 914개; 기존 6-tier 변경 0, 독립 감사 통과 |
| `D:\20_AUDIO\09_textgrid_pron_reference_v1_staging\2021` | 세션 checkpoint형 7-tier 파생 생산본 | 4,139세션·1,371,883개; 기존 6-tier 변경 0, 독립 감사 오류 0 |
| `D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728` | 구 공통 Jamo r2 사전·감사 증거 | 읽기 전용 보존, 신규 MFA 사용 금지 |
| `D:\mfa_eojeol` | 입력·정렬 계약, marker, log, lock | 2020–2022 r2 marker·계약 보존; r2 신규 실행 Gate 차단, r3 준비 중 |
| `D:\mfa_tmp\2020\2020.db` | 2020 공통 Jamo r2 보존 정렬 DB | 868,187 정렬 성공·363 승인 미정렬; Gate B 근거로 보존 |
| `D:\mfa_tmp\2021\2021.db` | 2021 공통 Jamo r2 보존 정렬 DB | 1,371,883 정렬 산출; 읽기 전용 비교 증거 |
| `D:\mfa_tmp\2022\2022.db` | 2022 공통 Jamo r2 보존 정렬 DB | 864,690 정렬 산출; 발음 입력 문제 발견 근거로 읽기 전용 보존 |
| `D:\mfa_eojeol_out` | 용량 폴백 작업경로 | 현재 연도 실행 중에만 사용 |

CSV는 정리 대상이 아니다. 형태소 CSV, 조합검색 7표, post-MFA 동반표 4개,
WAV–TextGrid–metadata 연결표, 승인·제외·미해결 기호표는 모두 연구 인프라의
필수 산출물로 유지한다.

사전 발음 registry v2는 공통 MFA 입력 phone 사전이 아니다. `pron_1/2`와
fallback의 표제어·품사·의미·출처를 occurrence에 조인하고 규칙 예상형·MFA
phone과 비교하기 위한 참조 자산이다. 비채택 v1은 감사 근거로만 보존한다.

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
| `pre_2021_active_state_20260803` | D:에 남았던 구 2021 로그·LAB 완료표시·입력계약 9개 | 4,208,271 bytes → 458,443-byte 7z; CRC·SHA 검증 성공, 활성 사본 0 |
| `pronunciation_reference_pre_adoption_20260805` | 비채택 registry v1과 폐기된 2020 비교 좌표 파일럿 2종 | 6파일·84,513,545 bytes; 84,504,963-byte 7z, SHA-256·7-Zip 검사 통과; 채택 v2는 D: 유지 |

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
- MFA 상태: 2020 신규 r2 계산 완료; 보존 DB 868,187 정렬 성공·363 미정렬
- post-MFA 연결 QC: 16표본 완료, 13 match + 3 `audio_unusable`
- 결합 승인 계약:
  `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_export_20260803/2020/`
  — pre-MFA 1,887 + post-MFA 363(청취 불가 3 + 정렬 실패 360) = 2,250;
  보존 DB의 실제 미정렬 ID와 exact match
- TextGrid·동반표: `D:\20_AUDIO\08_textgrid_research_v2_staging\2020`에
  868,187개 export 완료. utterance 868,187, word 4,973,795,
  phone 19,101,192, excluded 2,250행이며 독립 감사 하드 실패 0
- TextGrid 경계: 2020 DB 868,187/868,187 word-phone 바깥 경계 일치;
  모든 tier가 0–xmax를 연속적으로 덮음
- 생산 표본: 24/24 연구자 승인, 실제 실현 판정은 수행하지 않음
- Gate B: 16/16 core check 통과, 실패 0, `allow_remaining_years=true`

2021–2025 LAB·pending 제외 후보표와 safe-body 5행 요약은 완료됐다. 저장소의
현행 검토 root는
`outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_safe_body_2021_2025_20260803`이며,
검색 4,232,919 중 안전 본체 4,120,627, 후보 112,292다. 이 승인·제외 계약은
r3 재정렬에서도 재사용하되 r2 MFA를 새로 시작하는 근거로 쓰지 않는다. 다음
생산 단계는 r3 발음 release 채택이며 실행 순서는
[RUNBOOK_production_2020_2025.md](RUNBOOK_production_2020_2025.md)만 따른다.

2021 기존 `.lab`은 동결 CSV 기반의 재사용 입력이라 보존했다. r3 재정렬 시에도
LAB 자체는 전수 재생성하지 않고 frozen source contract를 재검증해 불일치만
재작성한다.
