# 외부 리뷰 처리 결과 — 전수 TextGrid·CSV 생산 계약

- 원 리뷰: `incoming/EXTERNAL_REVIEW_full_production_TextGrid_CSV_20260801.md`
- 원 판정: **GO AFTER FIXES**, BLOCKER 0 / HIGH 2 / MEDIUM 10 / LOW 6
- 처리일: 2026-08-01
- 현재 판정: **코드 수정·회귀 통과, 2020 입력 승인표 생성 전**

## 결론

H-01과 H-02를 모두 구현했다. 다만 이것은 “2020–2025 전수 완료”를 뜻하지
않는다. 2020을 시작하려면 새 helper가 만든 후보표를 연구자가 검토하고,
0건을 포함한 명시적 승인 계약을 만든 뒤 전수 lab force-verify가 통과해야 한다.

## HIGH

### H-01 — 6-tier 연도 QC·다음 연도 gate

처리: **완료**

- `audit_mfa_research_6tier_year.py`: LAB–TextGrid 정확 ID 대사, tier 순서,
  0–xmax 연속성, phone/phoneme와 발화 3-tier 경계, WAV 길이, phone inventory,
  spn, 동반표 manifest/SHA/count/key를 독립 감사한다.
- 연 phone 표를 `list()`로 읽지 않고 스트리밍한다. 메모리는 interval 수가
  아니라 발화 ID 수에 비례한다.
- `verify_mfa_db_research_6tier_sample.py`: 보존 DB에서 세션별 결정적 표본을
  재수출하고 final과 의미·바이트를 비교한다.
- `preflight_next_year_after_research_qc.py`: 동일 input/alignment contract,
  retained DB, direct exporter exact gate, 동반표 manifest, 세션 ≥5 표본,
  연구자 승인 보고서를 결합한다.
- 기존 `preflight_next_year_after_qc.py`는 audit schema를 보고 legacy 4-tier와
  새 6-tier gate를 명시적으로 분기한다.

### H-02 — 승인 제외와 무명 손실 금지

처리: **완료**

- 검토 CSV의 각 행은 `year,input_contract_id,utt_id,reason_code,
  exclusion_scope,evidence_path,decision,notes`를 가진다.
- 자동 생성은 언제나 `decision=pending`이며 자동 승인은 금지된다.
- 승인 JSON은 review CSV SHA-256, 연구자, 승인시각, input contract ID에
  묶인다. CSV가 바뀌면 계약 검증이 실패한다.
- exporter는 승인 제외 전수표 `excluded_utterances.csv.gz`를 만든다.
  목록 밖 결측, stale 승인, 승인 밖 quarantine은 1건도 허용하지 않는다.
- 99% 휴리스틱 대신 active LAB = aligned TextGrid ⊎ 승인 alignment 제외의
  정확 집합 대사를 요구한다.
- 입력 감사도 승인 alignment 제외를 active gate에서 분리하되, ID와 수는
  별도로 기록한다.
- `prepare_mfa_year_exclusion_review.ps1`은 전수 lab force-verify, 입력
  no-strict 후보 감사, 불량 WAV dry-run inventory, pending 검토표 생성까지만
  수행한다. WAV 이동과 승인은 하지 않는다.

## MEDIUM

| 항목 | 처리 | 근거 |
|---|---|---|
| M-01 `n_spn`/`align_status` 상수 | 완료 | DB phone별 실측, `aligned`/`aligned_excluded_approved` 기록 |
| M-02 Windows 상대경로 | 완료 | `textgrid_relative_path` POSIX 고정 |
| M-03 dtype/Parquet 계약 | 완료 | machine-readable schema v2, gzip 4표, 별도 PyArrow builder/roundtrip verifier |
| M-04 `direct_db_ready` 재검증 | 완료 | 재사용 때 DB checkpoint를 다시 실행하고 marker counts와 대조 |
| M-05 lab marker 내용 | 완료 | `-ForceVerifyLabInput`; 승인 후보 준비 helper는 항상 `--force-verify` |
| M-06 동반표 단일 패스 | 실측 수용 | 10k: 최초 87.738초, 재개 38.404초, Python peak 9.214MiB. 연도 단위만 실행하며 동반표 재개 불가는 문서화 |
| M-07 interval 클램프 | 완료 | 허용오차 밖 0–xmax 초과는 예외, 미세 부동소수 오차만 보정 |
| M-08 혼합 어절 `∅` | 완료 | legacy `form_roman` 보존 + `form_roman_v2`/`orth_roman_v2`; literal+한글 동시 보존 |
| M-09 silence 이중 기준 | 완료 | `SILENCE` 단일 상수, `spn`은 silence가 아니라 차단 신호 |
| M-10 gzip 비결정성 | 완료 | `mtime=0`; 독립 재출력 gzip 24개 SHA 불일치 0 |

## LOW

| 항목 | 처리 |
|---|---|
| L-01 회귀 증거 휘발 | 작은 집계 증거 JSON을 `outputs/reports`에 추적. 대형 work 실물은 로컬 QC 자산 |
| L-02 gzip fsync | raw gzip을 flush/fsync한 뒤에만 승격 |
| L-03 Roman 대소문자 | 방법 계약에 `k/K`, `p/P`, `t/T`, `R/l` 의미와 case-sensitive 검색 명시 |
| L-04 제어문자 | TextGrid label C0 제어문자 사전 차단 |
| L-05 final staging/marker 창 | preflight에서 final staging만 있고 marker 전무한 상태를 별도 hard fail |
| L-06 전량 ID set | 형태소 위치표는 연도 단위만 실행하도록 운영 계약 명시 |

## 추가로 발견·수정한 사항

1. 원 60발화 보고서의 word interval 합계 `529`는 단순 합산 오류였다.
   연도별 manifest를 다시 더한 정확한 값은 `479`다. 원 실물과 연도별 수치는
   변하지 않았다.
2. Parquet 첫 실물 실행에서 Windows 읽기 전용 descriptor의 `fsync`가
   `Bad file descriptor`로 실패했다. `rb+` descriptor로 고치고 실패 root에는
   success manifest가 생기지 않음을 확인했다.
3. 60발화 최종 회귀에서 legacy 대비 혼합 표기 2건의
   `utterance_orth_r`만 의도적으로 바뀌었다. 다른 tier 불일치 0,
   최종 재출력끼리 TextGrid·gzip SHA 불일치 0이다.
4. Bareun 클라우드 서버 build ID는 당시 API/로그에 보존되지 않아 정확한
   사후 복원이 불가능하다. 현재 버전을 과거 버전으로 허위 소급하지 않고,
   분석일·endpoint·`bareunpy==2.0.1`과 한계를 논문에 기록한다.

## 회귀 증거

- 60발화: 6개년 60 utterance / 479 word / 1,801 phone / spn 0
- 출력: 96파일, 673,456 bytes, active partial 0
- deterministic gzip: 24/24, SHA mismatch 0
- Parquet roundtrip: 6개년 × 4표 = 24/24 logical/schema equal
- 합성 10k: 최초 87.738초, 재개 38.404초, Python peak 9.214MiB
- 집계: `outputs/reports/EVIDENCE_research_6tier_post_review_20260801.json`

## 전수 전 남은 연구자 작업

1. 2020 pending 제외 후보표의 각 행 사유·범위를 승인하거나 기각한다.
2. 후보 0건이어도 연구자·승인시각이 있는 0행 계약을 만든다.
3. 2020 완료 후 화자 ≥5 표본을 검토하고, 독립 6-tier 감사·DB 재수출 gate가
   모두 통과한 뒤에만 2021로 넘어간다.

우리말샘 1:N 후보표, KOINA, wav2vec2, 실제 음운 실현 판정은 후속 검색·연구
레이어이며 이 MFA 인프라 gate와 분리한다.

## 최종 회귀 검증

- Python 전체 단위·통합 테스트: **287/287 통과**
- PowerShell 정적 안전 검사: **17/17 파일 통과**
- 신규 격리 회귀 시나리오: 승인 없는 quarantine ID는 차단되고, 같은 input
  contract에 묶인 연구자 승인 뒤에만 `excluded_utterances.csv.gz`로 기록됨을 확인
- 신규·변경 Python 엔트리포인트 `py_compile` 통과
- `git diff --check` 통과(공백 오류 없음)
