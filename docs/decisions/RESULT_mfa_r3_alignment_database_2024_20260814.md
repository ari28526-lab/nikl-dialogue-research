# 2024 r3 정렬 DB·post-MFA 회계·분석 수출 진입 결과

작성일: 2026-08-14
상태: 정렬·6-tier·동반표·독립 QC 완료
적용 release: `common_pron_mfa_r3_20260809`

## 결정 요약

2024년은 동결한 r3 입력·공통발음사전·음향모델로 전수 MFA를 새로 실행했다.
보존 DB와 완료 marker를 기준으로 exact-ID를 회계했으며, 성공한 정렬은 보존하고
기술 미정렬만 별도 후속 범위로 이관한다. 2020–2023 완성본은 수정하거나
재실행하지 않는다.

## 정렬 완료 근거

- alignment contract ID:
  `d86f490de924cdf92f2fcb16316046558be65f9446ffa0cf325fc661e4b20f9f`
- 완료 시각: `2026-08-14T01:24:30.7684016+09:00`
- 동결 MFA 입력: 594,404건
- 보존 DB: `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\temp\2024\2024.db`
- DB bytes: 7,538,421,760
- DB SHA-256:
  `b55d69ded19085d1e97abe13b0a62585a3f638c854cb08dcecf18ddc66cec110`
- 완료 marker SHA-256:
  `6b49f1018d65588cec26c9d48c4922ac272ca6e9336d5ad6fdd8ba07f0d79a06`
- marker 불변조건: `status=passed`, `r3_full_realign=true`,
  `textgrid_materialized=false`, DB·temp 보존

## post-MFA exact-ID 회계

```text
expected MFA input      594,404
database utterances     594,404
aligned utterances      593,530
technical unaligned         874
unknown/unapproved gap        0
```

874건은 모두 `mfa_alignment_missing`이며 500세션에 분포한다. 후보 identity는
`792b78220ca4a6377f0aea309fc6696e957f08f1ca3423bf62f2d03985e11f2a`다.
이 회계는 실제 음운 실현 판정이 아니라 정렬 산출물 존재 여부에 대한 기술적
exact-ID 분류다. 후보를 만들 때 자동 승인은 수행하지 않았고 원자료·DB·성공한
정렬은 수정하지 않았다.

## 연구자 승인

연구자 `ari30`은 2026-08-14 10:33 KST에 다음 범위를 명시 승인했다.

> 2024 r3 post-MFA 미정렬 874건(candidate 792b78220ca4)을
> alignment_and_analysis 범위의 후속 exact-ID로 이관하고, 성공한 593,530건은
> 보존 DB에서 6-tier로 수출한다.

- 승인문 SHA-256:
  `7b03892433b046f177cdae6365a85cc1c7335f5e7dfd896d91b0534cf01f7eb3`
- 승인 CSV SHA-256:
  `c2c7455bc217dda06188acf5de44eaf0f10c9440a31d3587f1a6bd0357a5c316`
- 승인 제외 계약 SHA-256:
  `cd561dff8632027b925c5d26e71b1316beb448ed2ed74451d13a343c4bba347e`

## 수출 중 안전 중단과 표적 복구

수출 preflight는 `594,404 = 593,530 + 874`, `spn=0`, acoustic inventory 밖
phone 0, 미승인 차이 0을 확인했다. 실제 수출은 2026-08-14 10:42 KST에 한 번
시작했으나 검색 원문 `form` 안에 포함된 U+000A 줄바꿈 두 건을 TextGrid 표시
label로 쓰는 단계에서 안전 중단됐다.

대상은 다음 두 발화뿐이었다.

- `SDRW2400001393.1.1.156`
- `SDRW2400002782.1.1.226`

원 CSV에서는 줄바꿈을 포함한 quoted field가 유효하므로 원문과 동반표 값은
변경하지 않았다. TextGrid 표시 tier를 만들 때에만 LF·CR·NEL·U+2028·U+2029를
ASCII 공백 하나로 정규화한다. TAB 등 그 밖의 제어문자는 계속 hard failure다.
이미 생성된 593,528개 TextGrid, MFA DB, WAV, LAB, 원 CSV는 다시 만들거나
수정하지 않았고, 누락된 두 TextGrid만 exact-ID와 원문 fingerprint를 확인한 뒤
생성했다. 그 후 동반표 생성을 checkpoint에서 재개했다.

- 최초 실패 보고서:
  `outputs/reports/EXPORT_mfa_r3_research_6tier_2024_20260814_104221.json`
- 표적 복구 manifest:
  `outputs/reports/REPAIR_label_controls_EXPORT_mfa_r3_research_6tier_2024_20260814_104221.json`
- 최종 복구 수출 보고서:
  `outputs/reports/EXPORT_RECOVERED_mfa_r3_research_6tier_2024_20260814_124518.json`

## 최종 산출물과 독립 QC

```text
research 6-tier TextGrid      593,530
approved exclusions              874
unapproved difference               0
coverage                         100%
hard-failure categories           0/25
DB re-export sample semantic      24/24
DB re-export sample byte          24/24
```

동반표는 `utterance_alignment`, `word_intervals_mfa`, `phone_intervals_mfa`,
`excluded_utterances` 네 종류이며 `TABLES_MANIFEST.json`이 각 행 수와 SHA-256을
동결한다. 최종 독립 QC 상태는 다음과 같다.

- state:
  `outputs/reports/mfa_r3_research_qc_common_pron_mfa_r3_20260809/2024/QC_STATE.json`
- status: `passed`
- QC state SHA-256:
  `2321d5cc3914404b6d067250265e0f0d4887ffbf5ab5c49245809f631f785549`
- source mutation: 없음
- MFA recomputation: 없음
- full export repetition: 없음

따라서 2024 r3 MFA·6-tier·동반표·독립 QC는 완료 상태로 동결한다. 2024를 다시
실행하지 않고, 다음 생산 단계는 이 QC state를 입력 증거로 삼는 2024→2025
단일 연도 Gate다.
