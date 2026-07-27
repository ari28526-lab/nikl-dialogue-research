# 2021 pre-MFA·MFA 완료 및 독립 QC 결과

작성일: 2026-07-28
대상 run: `eojeol_g2p_2021_20260727_082721`
동결 search master: `pre_mfa_v1_20260725`
입력계약:
`ef22e9b38901a3dd0797cd9664cd72c1d04f496e2ad775cbd9b5f3f99292c3fe`
MFA 실행 당시 Git:
`6ef65272e951c0a4b473030a15781f11ad540693`

## 결론

2021 MFA와 direct DB 4-tier 생성은 완료됐고, 최종 TextGrid
1,371,868개 전부가 독립 구조 감사를 통과했다. SQLite DB도 full
`PRAGMA integrity_check`에서 `ok`였으며, 서로 다른 24세션의 결정적 표본을
DB에서 다시 생성한 결과 final TextGrid와 tier·라벨·시간·파일 SHA256이
24/24 완전히 같았다.

최종 4-tier 위치:

```text
D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2021
```

보존 DB:

```text
D:\mfa_tmp\2021\2021.db
12,455,149,568 bytes
SHA256 388540be405ae3be8ae5b933105e00d8d415a2d3454c0c96e4dd64c0e0289872
```

이 완료는 “모든 발화가 정렬됐다”는 뜻이 아니다. 원천 음성 결함과 개별
난정렬 발화를 발화별 inventory로 남긴 상태에서, 분석 가능 분모의
99.9604%가 유효한 4-tier를 가졌다는 뜻이다.

## 연구 파이프라인에서의 위치

현재 결과는 다음 연구 흐름의 인프라다.

```text
동결 CSV에서 형태소·표기/음운형태 환경 후보 검색
  → 해당 WAV·4-tier TextGrid 수집
  → 필요한 후보 구간에 KOINA 운율 분석
  → 연구자가 WAV·TextGrid를 직접 보고 실현 여부 판정
```

`phones`는 MFA가 기준 발음과 음성을 강제정렬한 대략적 phone 시간층이다.
실제 음운현상 실현을 자동 판정하는 정답층이 아니다.

## 실행 결과

### MFA 본 실행

- 시작 heartbeat: 2026-07-27 08:42:30
- MFA process exit: 2026-07-28 01:59:15
- MFA 자체 보고 시간: 62,149.774초, 약 17시간 15분 50초
- 종료코드: 0
- watchdog kill: 없음
- corpus에서 발견한 화자: 4,143
- corpus WAV: 1,416,216
- 정렬 대상 DB 발화: 1,372,438
- first-pass 재시도: 21,885, 정렬 대상의 1.595%
- 최종 개별 정렬 실패: 570, 정렬 대상의 0.0415%
- 정렬 성공: 1,371,868

job별 합은 다음과 같이 전체 정렬 대상을 정확히 설명했다.

| job | 처리 | 재시도 | 성공 | 최종 실패 |
|---:|---:|---:|---:|---:|
| 1 | 343,803 | 5,528 | 343,676 | 127 |
| 2 | 343,102 | 5,402 | 342,915 | 187 |
| 3 | 343,596 | 5,563 | 343,469 | 127 |
| 4 | 341,937 | 5,392 | 341,808 | 129 |
| 합계 | **1,372,438** | **21,885** | **1,371,868** | **570** |

### direct DB 4-tier

- raw 2-tier TextGrid 전량 export: 생략
- DB에서 `words/phones` interval 직접 사용
- 기존 형태소 경계와 동결 `form` 결합
- 생성: 1,371,868
- alignment missing: 570
- form missing: 0
- 파일 생성 실패: 0
- 정렬 성공 집합 안의 morpheme tier missing: 0
- 정렬 대상 기준 coverage: 99.9585%
- 실행시간: 6,360.292초, 약 1시간 46분
- final 이동과 marker 완료: 2026-07-28 03:45:51

direct 보고서에서 형태소 결측이 0인 것은 **정렬 성공 집합**을 분모로 한
결과다. 전체 LAB/source readiness의 형태소 원천 누락 1,109건과 모순되지
않는다. 두 보고서는 분모가 다르다.

## 입력·원천 자료 독립 감사

보고서:

```text
outputs/reports/AUDIT_mfa_year_readiness_2021_post_mfa_20260728.json
outputs/reports/CLASSIFY_morph_source_missing_2021_post_mfa_20260728.csv
outputs/reports/CLASSIFY_morph_source_missing_2021_post_mfa_20260728.json
```

주요 결과:

- search rows: 1,373,920
- 예상 usable LAB: 1,373,521
- 실제 LAB: 1,373,521
- 동결 CSV와 LAB 내용 일치: 1,373,521/1,373,521
- 빈 reference form: 399
- 미해결 기호 inventory: 17,394
- 원전사 회복으로 reference form이 달라진 행: 38,529
- 형태소 원천 checked: 1,373,521
- 형태소 원천 nonzero: 1,372,412
- 형태소 원천 missing: 1,109
- 분류 완료: 1,109/1,109
- 미분류: 0

1,109건의 최종 분류:

| 원인 | 건수 | 처리 |
|---|---:|---|
| source PCM이 지나치게 짧음 | 1,091 | 원천 음성 사용 불가 제외 |
| source PCM 없음 | 1 | 원천 음성 사용 불가 제외 |
| 짧은 segment에 물리적으로 불가능한 긴 전사 연결 | 17 | 원천 segment–text 불일치 제외 |
| 합계 | **1,109** | **발화 ID·근거 보존** |

duration 감사에서는 4개 세션의 offset 대응 실패, residual mismatch 966행,
읽을 수 없는 WAV 39건, CSV duration invalid 14건이 남았다. 이 값은
MFA TextGrid 구조 실패와 분리한 source QC inventory이며, 원자료를
자동 수정하거나 실제 발음 판정에 쓰지 않는다.

## final 4-tier 전수 감사

보고서:

```text
outputs/reports/AUDIT_mfa_4tier_2021_pre_mfa_v1_20260728.json
outputs/reports/MISSING_mfa_4tier_2021_pre_mfa_v1_20260728.csv
logs/audit_4tier_2021_pre_mfa_v1_20260728_heartbeat.jsonl
```

실행:

- 시작: 2026-07-28 04:16:33
- 종료: 2026-07-28 04:52:52
- 소요: 2,178.632초, 약 36분 19초
- worker: 4
- WAV duration tolerance: 1ms

결과:

| 항목 | 수량 |
|---|---:|
| 전체 LAB | 1,373,521 |
| 원천 결함 제외 | 1,109 |
| 분석 가능 LAB | 1,372,412 |
| final TextGrid | 1,371,868 |
| 유효 TextGrid | 1,371,868 |
| 구조·duration invalid | 0 |
| 분석 가능 LAB 중 TextGrid 없음 | 544 |
| TextGrid without LAB | 0 |
| 중복 LAB/TextGrid | 0 |
| 0바이트 LAB | 0 |
| 분석 가능 coverage | **99.9604%** |
| raw LAB coverage | 99.8797% |

누락 수량은 다음처럼 정확히 조정된다.

```text
전체 LAB 누락 1,653
  = 원천 음성 사용 불가 1,109
  + 분석 가능하지만 정렬 실패 544

MFA DB의 alignment missing 570
  = 분석 가능 정렬 실패 544
  + 원천 제외 중 DB 정렬 대상에 포함됐으나 실패한 26
```

따라서 570, 1,653, 544는 서로 충돌하는 수치가 아니라 서로 다른 분모에서
같은 발화를 설명하는 수치다.

## tier 경계 해석

1,371,868개 모두 정확한 tier 순서를 가졌다.

```text
words
phones
morphemes
utterance
```

모든 tier는 interval의 gap·overlap 없이 0초부터 WAV `xmax`까지 연속으로
덮었다. 즉 처음이나 끝에 tier 자체가 비는 구조적 경계 누락은 0건이다.

다만 운영본 WAV에 실제 50ms 이상의 무음이 없는 발화까지 억지로 시간을
추가하지 않았으므로, “양끝에 최소 0.05초의 빈 interval이 눈에 보이는가”는
별도 진단값이다.

| tier | 왼쪽 빈 경계 ≥50ms | 오른쪽 빈 경계 ≥50ms |
|---|---:|---:|
| words | 1,267,866 | 1,339,207 |
| phones | 1,267,866 | 1,339,220 |
| morphemes | 1,268,092 | 1,341,724 |
| utterance | 1,267,866 | 1,339,212 |

운영본에서 모든 발화에 50ms 빈 경계를 강제하면 WAV 시간축과 불일치한다.
연결 청취나 연구자 점검에는 WAV와 TextGrid를 함께 좌우 padding한 review
bundle을 만들고, canonical 운영본은 원 WAV 시간을 보존하는 현재 정책이
적절하다.

## DB 무결성과 재생성 증거

### SQLite full integrity

보고서:

```text
outputs/reports/SQLITE_integrity_2021_pre_mfa_v1_20260728.json
```

- SQLite: 3.53.3, 64-bit
- 실행: `sqlite3 -readonly ... "PRAGMA integrity_check;"`
- 결과: `ok`
- 소요: 4,255.2초, 약 70분 55초
- DB 수정시각 변화: 없음
- journal/WAL/SHM: 없음

full integrity는 최종 보존 결정에 유용하지만 큰 DB에서는 사후 병목이다.
다음 연도에는 즉시 이상을 찾는 `quick_check`와 최종 보존용
`integrity_check`를 서로 다른 단계로 운영한다.

### 결정적 24세션 재추출

보고서:

```text
outputs/reports/VERIFY_db_4tier_sample_2021_20260728.json
outputs/reports/VERIFY_db_4tier_sample_2021_20260728.csv
```

- 정렬 성공 발화: 1,371,868
- 정렬 성공 세션: 4,139
- 서로 다른 결정적 표본 세션: 24
- DB 재생성 성공: 24/24
- tier·라벨·모든 시간값 동일: 24/24
- 파일 SHA256 동일: 24/24
- 소요: 106.628초

## 저장공간 dry-run

보고서:

```text
outputs/reports/PLAN_2021_cleanup_dry_run_20260728.json
```

- 상태: `ready_for_user_review`
- 삭제 수행: false
- apply 기능: false
- 2021 temp 총량: 47,119,546,244바이트, 43.883GiB
- 정리 후보: 33,677,552,748바이트, 31.365GiB
- 보존: 13,441,993,496바이트, 12.519GiB
- 후보 파일: 63
- 보존 파일: 42
- 현재 D: 여유: 약 264.146GiB
- 후보 정리 뒤 예상 여유: 약 295.511GiB

보존 대상은 DB 1개와 실행 재현 로그·모델·dictionary/FST·Kaldi tree다.
정리 후보는 DB와 final TextGrid에서 재계산 가능한 `.ark`, `.scp`,
`phone_intervals.csv`, `word_intervals.csv`다.

사용자 승인 전 실제 삭제·이동은 하지 않는다.

## 2022 진입 상태

직전 연도 QC 결합 gate:

```text
outputs/reports/PREFLIGHT_2022_after_2021_QC_20260728.json
```

- 상태: passed
- 검사: 20/20 passed
- contract·marker·direct report·DB·final 수량 일치

2022 자체 PowerShell preflight:

```text
logs/preflight_20260728_070125.log
```

- FAIL: 0
- WARN: 0
- D: `DATA_SSD` 확인
- D: 여유 264.1GB
- 2022 session 구조 확인
- search master session coverage 2,654/2,654
- 2022 temp/output/marker 없음

기술적으로는 실행 가능하지만 2022 전량은 아직 시작하지 않았다. 6개년 공통
G2P cache/우리말샘 예외 발음 파생사전을 먼저 파일럿할지 방법론 결정을 한 뒤,
사용자 확인을 받아 별도 한 연도 실행으로 시작한다.

최종 코드 검증:

- Python unittest: 88개 통과
- PowerShell safety: 실행기 5개 통과
- `git diff --check`: 통과
- 20260728 QC JSON 10개 parse: 통과
