# 2025 morph_search.v3와 frozen source contract 완료 결과

작성일: 2026-08-14
상태: 완료·독립 검증 통과

## 범위

2025 pre-MFA search master CSV 2,927개를 읽어 조합검색 30개 shard, 연간 7표,
frozen source contract를 생성했다. 이 단계는 MFA·TextGrid·WAV·원 CSV와
2020–2024 완성본을 변경하지 않았다.

## 완료 상태

```text
shards                         30/30
utterance_master_v2 rows      587,121
eojeol_tokens rows          4,816,887
orth_eojeol_tokens rows     4,839,305
morph_tokens rows           8,965,124
morph_units rows           13,436,041
morph_boundaries rows       8,378,003
symbol_readings rows          394,647
duplicate_utt_id                    0
```

- output root:
  `D:\10_LAYERS\09_morph_search_v3_staging\morph_search_v3_20260801\2025`
- input inventory SHA-256:
  `e794979883d16d1e80de0c1d233b31c219ba6fdad1b6e07292f2b2746abae4e1`
- 연간 manifest status: `success`
- 연간 manifest SHA-256:
  `798896ef2988c642978b77bf33ce1cd05a887c0d1d6e20c1b0e579e6777a846e`
- source contract status: `frozen`
- source contract SHA-256:
  `48f0a5e7d8e094988f384192f681f38236b2f4e645bbddd929ef522cc8e6959f`
- raw source modified: `false`
- 완료 뒤 D: 여유: 60.66 GiB

연간 manifest의 gate는 `all_shards_success=true`, `duplicate_utt_id=0`,
`orth_symbol_coverage_equal=true`, deterministic gzip mtime 0이다.

## 독립 검증

`verify_production_source_contract.ps1`을 `-RequireMorphYearSuccess`로 다시 실행해
12개 검사를 모두 통과했다. 연간 7개 gzip 파일의 SHA-256을 manifest와 독립적으로
재계산했고 7/7 일치했다.

- 검증 보고서:
  `outputs/reports/SOURCE_CONTRACT_morph_search_v3_20260801_2025.json`
- 보고서 status: `passed`
- failed checks: 0/12
- 보고서 SHA-256:
  `197028eb3b32a5ea3b4b0b0dbc63f4cb537f08d66f61ccc7921d2e2bd937089d`

## 정지점과 다음 단계

2025 조합검색·source contract는 재생성하지 않는다. 다음 단계는 이 manifest와
contract를 입력으로 2025 발음 연구 DB를 preflight한 뒤 생성·독립 감사하는
것이다. 그 결과와 2024 QC state를 결속한 2024→2025 Gate가 통과하기 전에는
2025 MFA runner를 시작하지 않는다.

후속 MFA 제외분 재처리, 표적 추출, 수동 TextGrid overlay, 세션 JSON, HTML
매뉴얼과 공유 release는 `PLAN_post_production_recovery_target_manual_session_json_20260814.md`에
별도 계획으로 보존하며 현재 생산 단계에 섞지 않는다.
