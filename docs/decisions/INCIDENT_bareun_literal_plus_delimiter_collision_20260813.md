# Bareun literal `+`와 형태소 구분자 충돌 복구

## 결론

2026-08-13 16:02 KST, 2024 `morph_search.v3`는 31/33 shard를 보존한 채
shard 32에서 안전 중단됐다. 원인은 Bareun 형태소 표면형 안의 실제 `+`와
1차 CSV 직렬화의 형태소 구분자 `+`가 escape 없이 같은 문자로 저장된 것이었다.

문제 기호를 삭제하거나 임의 POS로 바꾸지 않았다. POS 종결점을 기준으로 원
Bareun 구조를 무손실 복원했고, 2020–2025 전체 입력을 전수 감사해 같은 유형이
두 발화뿐이며 모두 설명 가능함을 확인했다.

## 2024 실제 사례

- 원 JSON 발화: `SDRW2400003024.1.1.216`
- `form`: `어 저도 나중에 한번 전주를 가 봐야 될 거 같아요.+`
- 1차 Bareun `tagged` 끝:
  `같/VA+아요/EF+.+/SW`
- Bareun 표면형: `.+`
- POS: `SW`

1차 serializer는 각 형태소를 `surface/POS`로 쓰고 형태소 사이를 `+`로
연결했지만 surface 안의 plus를 escape하지 않았다. 기존 parser의
`split('+')`는 이를 `.`와 빈 surface `/SW`로 잘못 나눴다.

`n_morphs=18`도 Bareun API가 준 독립 원계수가 아니다. 저장 코드가 직렬화된
문자열의 모든 plus를 세어 만든 값이어서 literal plus 한 개를 경계로 과대계상한
것이다. 실제 구조화 형태소 수는 17이다.

## 원자료 대조

다음을 교차 확인했다.

1. 원 NIKL JSON에는 발화 표기 `같아요.+`가 존재한다.
2. `01_bareun_raw`에는 `.+/SW`가 존재한다.
3. `02_sense_annotated`는 기호 형태소를 의미 분석 대상에서 제외했으므로 lexical
   16행만 있으며, 이것을 기호 삭제 근거로 사용하지 않는다.
4. pre-MFA search master는 원 `tagged`와 `n_morphs=18`을 그대로 보존한다.

따라서 표면형 `.+/SW`를 한 기호 형태소로 보존하는 것이 원 분석에 가장 충실하다.

## 코드 수정

`scripts/python/morph_schema.py`는 이제 단순 plus 분할 대신 `/POS` 종결점 뒤의
plus만 형태소 경계로 해석한다. 그 결과 `.+/SW`, `+/SW` 같은 literal plus
surface를 보존한다. 다음 안전장치는 유지한다.

- 빈 surface/POS는 실패
- POS 동결 문법 밖 값은 실패
- 한글·독립 자모가 섞인 surface 안의 모호한 plus는 실패
- 재조립한 raw tagged가 입력과 다르면 실패
- source `n_morphs` 차이는 `legacy plus count = structured count + surface의
  literal plus 수`로 완전히 설명될 때만 허용

설명된 행의 master에는 다음 상태를 기록한다.

```text
morph_parse_status=ok_legacy_literal_plus_n_morphs_overcount
```

원 `n_morphs` 열은 provenance를 위해 바꾸지 않고, 정본 구조 수는
`morph_count_structured`에 둔다.

향후 Bareun 전수 재분석 코드 `bareun_dialogue_full.py`의 `n_morphs` 계산도
문자 plus 수가 아니라 POS 종결점 수를 사용하도록 바꿨다. 기존 원 CSV는
수정하지 않는다.

## 6개년 전수 감사

동결 pre-MFA CSV 전 행에서 legacy plus count와 POS 종결점 수를 비교했다.

| 연도 | 행 | 충돌 후보 | 무손실 설명 | 미설명 |
|---:|---:|---:|---:|---:|
| 2020 | 870,437 | 0 | 0 | 0 |
| 2021 | 1,373,920 | 0 | 0 | 0 |
| 2022 | 866,359 | 0 | 0 | 0 |
| 2023 | 677,262 | 0 | 0 | 0 |
| 2024 | 728,257 | 1 | 1 | 0 |
| 2025 | 587,121 | 1 | 1 | 0 |

2025 후보는 `SDRW2500001064.1.1.189`이며 surface `+`, POS `SW`, source
`n_morphs=25`, 구조화 수 24다. 따라서 2025 실행 전에 이미 같은 중단을
예방했다.

2020–2023 후보가 0이므로 새 parser를 적용해도 해당 완성본의 형태소 구조가
바뀔 입력은 없다. 2020–2023 조합검색·MFA·TextGrid를 재실행하지 않는다.

감사 보고서:

```text
outputs/reports/AUDIT_bareun_tagged_delimiter_collisions_2020_2023_20260813.json
outputs/reports/AUDIT_bareun_tagged_delimiter_collisions_2024_20260813.json
outputs/reports/AUDIT_bareun_tagged_delimiter_collisions_2025_20260813.json
```

## 실패 증거와 감사기 시행착오

shard 32 실패 raw 7표·`BUILD_FAILED.json`·당시 progress는 삭제하지 않고 다음에
격리했다.

```text
D:\10_LAYERS\09_morph_search_v3_staging\morph_search_v3_20260801\2024\
  shards\shard_00032\archive_failed\
  bareun_literal_plus_surface_20260813_160205\
```

첫 전수 감사기는 어절 단위 정규식을 발화 전체 문자열에 적용해 어절 끝 POS를
누락하고 대량 false positive를 냈다. 이 잘못된 보고서는 성공 보고서와 섞지 않고
`outputs/reports/archive_failed/`에 보존했다. 감사기는 CSV 전체 48열 dict 생성을
피하고 필요한 열만 읽으며, 연도별 progress checkpoint를 남기도록 고쳤다.

Codex 실행기의 5분 제한으로 shard 32 단일 회귀 wrapper가 먼저 종료되고 Python
자식이 잠시 orphan 상태로 계산을 계속한 일도 있었다. 새 실행을 겹치지 않고
PID·CPU·partial 승격을 감시했다. raw → tables → manifest가 순서대로 원자
완료되고 Python이 정상 종료한 뒤에만 성공으로 판정했다.

## shard 32 실제 회귀

- shard manifest: `success`
- utterances: 27,812
- 문제 발화 structured morph: 17
- 마지막 morph: `.+/SW`
- `tagged_regeneration_equal=True`
- `morph_parse_status=ok_legacy_literal_plus_n_morphs_overcount`
- 진행 상태: `paused_after_max_shards`, 32/33

성공한 shard 1–31은 다시 생성하지 않았다. 다음 단계는 shard 33과 annual 7표
병합·source contract 검증이며, 그 뒤에도 별도 입력·정렬·전환 Gate 전에는 MFA나
TextGrid를 시작하지 않는다.
