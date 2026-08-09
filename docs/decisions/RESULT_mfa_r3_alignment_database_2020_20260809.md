# 결과: 2020 r3 안전 본체 MFA 정렬 DB 완료

날짜: 2026-08-09 KST

release: `common_pron_mfa_r3_20260809`

alignment contract: `3eff5ae34eb1015c05532140162636609099f1fd1203f561cc06d837039d8e8a`

## 결론

2020년 r3 안전 본체 782,715발화를 단일 r3 발음사전과 동결 Korean acoustic
model 기준으로 새로 강제 정렬했다. 계산은 2026-08-09 17:28에 재개되어
21:20에 정상 완료됐고, 2021은 자동 시작하지 않았다.

완료 marker는 다음과 같다.

```text
D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\markers\ALIGN_DONE_2020.json
```

marker의 `status=passed`, `r3_full_realign=true`,
`expected_mfa_input=782715`, `textgrid_materialized=false`를 확인했다. 이 결과는
MFA 계산 DB의 재사용 가능성을 뜻하며 6-tier TextGrid·동반표·연구 분석 준비가
완료됐다는 뜻은 아니다.

## 보존 DB와 독립 감사

```text
DB: D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\temp\2020\2020.db
bytes: 5,534,134,272
SHA-256: e2fec7300f9a70a6553f0f9d81d9c7a3c5cdfbc514b77cc7b6de87f933d7f991
```

완료 marker가 기록한 bytes·SHA-256과 실제 파일을 독립 재계산한 값이 정확히
일치했다. SQLite `PRAGMA quick_check`는 `ok`다.

| 항목 | 수량 |
|---|---:|
| MFA 입력 발화 | 782,715 |
| word와 phone interval이 모두 있는 발화 | 782,432 |
| post-MFA 미정렬 발화 | 283 |
| coverage | 99.9638% |
| word interval | 4,315,723 |
| phone interval | 16,458,699 |
| `spn` interval | 0 |

독립 감사 실물은
`outputs/reports/AUDIT_mfa_r3_alignment_checkpoint_2020_20260809.json`이다.
283건은 전체 연도 계산 실패가 아니다. 다음 export 직전에 DB와 입력 계약을
exact-ID로 대사해 후속 회계하고, 성공한 782,432건의 DB를 버리거나 2020년
전체를 다시 정렬하지 않는다.

## 최초 실패와 재개 의미

14:56 최초 실행에서는 release 전용 hardlink+LAB 코퍼스 782,715쌍을 완성한 뒤,
MFA 자식이 conda `Library\\bin`의 `fstcompile`을 찾지 못해 즉시 종료됐다. 이는
발음사전·음향모델·코퍼스 자료의 실패가 아니라 실행기 PATH 전달 결함이었다.
완료 marker를 만들지 않고 corpus·temp·DB를 보존했으며, runner에 conda runtime
PATH와 MFA `check_third_party()` hard Gate를 추가한 뒤 같은 계약으로 재개했다.

이 시행착오는 다음 원칙의 근거다.

1. 코퍼스 물질화, MFA 계산, TextGrid/export를 분리한다.
2. 실행 환경 의존성은 대량 파일 생성 전에 hard Gate로 검사한다.
3. 실패하면 성공 checkpoint와 DB를 삭제하지 않고 같은 계약에서 재개한다.
4. 정상 보고는 한 시간 간격이어도 실패 감지는 1분 이하로 분리한다.
5. post-MFA 일부 미정렬은 exact-ID 후속 shard로 관리하고 전년 재정렬 사유로
   사용하지 않는다.

## 연구 방법론에서의 의미

이번 작업은 단순히 TextGrid 수를 늘린 것이 아니다. 2020–2025에 동일하게 쓸
발음 선택 release, acoustic phone inventory, 입력·제외 좌표, 발화별 발음 occurrence,
정렬 계약을 SHA로 고정한 첫 연도 생산 결과다. 따라서 논문에는 “2020년 자료를
채택된 단일 r3 발음·음향모델 계약으로 전수 강제 정렬했고, 기술적 미정렬은
exact-ID로 별도 회계했다”고 쓸 수 있다.

`phones_mfa`는 음향과 사전 후보 사이의 강제 정렬 결과이지 실제 음운 실현의
연구자 판정값이 아니다. 철자 Roman, 규칙 예상 발음, 우리말샘 발음, 형태소 정보,
MFA phone과 추후 실제 실현 판정은 서로 다른 열·층으로 유지한다.

## 다음 정지점

- 2021을 시작하지 않는다.
- 먼저 283건 exact-ID 회계와 보존 DB 기반 6-tier/export preflight를 수행한다.
- exporter·tier·CSV 문제는 이 DB에서 다시 생성하며 MFA를 다시 계산하지 않는다.
- 2020 export·독립 QC·최소 인프라 표본 Gate가 끝난 뒤에만 2021을 연다.
