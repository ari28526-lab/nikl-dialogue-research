# 2020 r3 발음 연구 DB 구축·감사 결과

기록일: 2026-08-09
상태: `passed`, 2020 장시간 MFA 전 필수 Gate 충족

## 목적

채택된 `common_pron_mfa_r3_20260809` 발음사전과 기존 형태소·철자 검색 CSV,
연도별 MFA 입력, 이후 word/phone interval을 같은 좌표로 연결한다. 기존 원 CSV를
새 발음값으로 덮어쓰지 않고 각 정보의 출처와 해석을 분리한다.

## 실자료 결과

| 항목 | 수량 |
|---|---:|
| 관측 발음 유형 | 881,237 |
| 채택 유형 | 795,804 |
| 채택 발음 변이행 | 796,061 |
| 2020 전체 발화 | 870,437 |
| 2020 참조 어절 occurrence | 3,056,807 |
| r3 안전 본체 입력 | 782,715 |
| pre-MFA 기술 제외 | 1,675 |
| 발음 follow-up | 86,047 |
| 미등록 nonempty LAB token | 0 |

정본 결합 키는 `(year, utt_id, reference_eojeol_idx)`다. 참조·철자·형태소의
어절 수가 다를 때 좌표를 자동으로 밀거나 추정하지 않는다.

## 정본과 감사

정본 root:

```text
D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\05_research_database
```

주요 파일:

- `pronunciation_type_catalog.csv.gz`
- `TYPE_CATALOG_MANIFEST.json`
- `TYPE_CATALOG_AUDIT.json`
- `2020\utterance_pronunciation_scope.csv.gz`
- `2020\pronunciation_occurrences.csv.gz`
- `2020\YEAR_DATABASE_MANIFEST_2020.json`
- `2020\AUDIT_RESEARCH_DATABASE_2020.json`

연도 감사의 `status=passed`, `failures=[]`,
`ready_for_mfa_preflight=true`를 확인했다. occurrence SHA-256은
`9739c3fee29e5e87f66d8a92315dc854bbb401c22065428f85201bc39a8a35df`,
발화 scope SHA-256은
`84c9033b07ba1474d1f52d819610b53b346ef1ea10e6cf2dc72923e1e165f229`다.

## 재개와 실패 격리

2020은 기존 형태소 검색 23 shard를 단위로 생성한다. 첫 실행 제어 채널이 shard
1 뒤 끊겼지만, 같은 명령을 재실행하자 type catalog와 shard 1의 SHA를 확인해
재사용하고 나머지만 생성해 23/23을 완료했다. 남은 `.partial` 파일은 0개다.
따라서 중단은 이미 검증된 shard나 원자료를 훼손하지 않으며 연도 전체 재계산을
요구하지 않는다.

## MFA·후속 DB 결합 Gate

보강된 2020 runner preflight는 19/19 `GO`다. 그중
`research_database_occurrence_contract`가 위 감사·manifest·두 정본표의 SHA와
결합 키를 검사한다. post-MFA exporter와 독립 감사도 동일 SHA를 결과 manifest에
고정하므로, CSV 재생성은 보존 MFA DB에서 수행할 수 있고 정렬을 반복할 필요가
없다.

gzip CSV는 재현·감사의 정본이다. 반복 조합 검색용 Parquet/DuckDB 미러는 이후
정본 SHA에 종속된 재생성 가능 파생층으로 만들며 MFA 시작 Gate에는 넣지 않는다.
