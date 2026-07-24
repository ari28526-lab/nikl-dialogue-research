# 대량 MFA·CSV 전 검증 결과

검증일: 2026-07-24

브랜치: `agent/harden-pre-bulk-pipelines`

범위: 코드·환경·전수 입력 좌표·합성 실패·검색 CSV 1세션 파일럿

이번 감사에서 대량 MFA는 **미실행**했다. 510만 발화 search master 전량본은
이 감사 전인 2026-07-23에 이미 생성되어 있었으며, 이번에는 재생성하지 않고
격리된 1세션만 새 코드로 검증했다.

## 판정

코드의 부분 출력·거짓 성공·구판 유실 위험은 자동 검사로 방어되었다. MFA 설치,
필수 패치, 모델, 저장공간과 6개년 코퍼스 구조는 preflight를 통과했다. 검색
마스터 입력에서는 2023년 메타 ID 충돌 4건을 발견하여, 원본을 바꾸지 않고 파생
인덱스를 복구했다. 복구 뒤 17,156개 세션 ID가 완전히 일치했고 대표 세션 CSV
파일럿이 통과했다.

**현재 상태는 “기존 전량 search master 감사 중, MFA는 구조·복구 안전성
통과 후 연도별 파일럿 대기”다.**

## 1. 코드 기준선과 커밋

| 커밋 | 내용 |
|---|---|
| `5587604` | 수정 전 코드 아카이브와 실패 이력 감사 |
| `f49eeef` | 검색 CSV 원자적 작성·검증·구판 보존 |
| `69babb4` | MFA preflight·패치 검증·복구 가능한 실행기 |
| `d77474a` | 메타 ID 충돌 검출·복구와 검색 파일럿 |

기준선은 `archive/code_pre_bulk_20260724`에 상대경로 그대로 보존했고,
`MANIFEST.sha256`의 모든 항목을 실제 파일 hash와 대조했다. PowerShell 원본은
UTF-8 BOM을 포함한 바이트 단위로 보존했다.

## 2. 자동 검사

실행기: `C:\Users\ari30\miniforge3\envs\mfa\python.exe`

버전: Python 3.13.14, MFA 3.4.0

| 검사 | 결과 |
|---|---:|
| Python unittest | 18/18 통과 |
| PowerShell 파서·BOM·치명 종료 검사 | 3/3 파일 통과 |
| MFA 설치 소스 필수 패치 | 7/7 통과 |
| `predict_pron.py --selftest` | 30/30 통과 |
| Git whitespace 검사 | 통과 |

실패 주입 범위:

- 임시파일 쓰기 실패 시 기존 정식 파일 불변
- 유효한 CSV 재사용, 부분 CSV 자동 보존·재생성
- overwrite 전 구판 아카이브
- 잘못된 TextGrid tier 이름·duration 불일치 차단
- 0바이트 WAV dry-run과 상대경로 보존 격리
- MFA `analyze_alignments` 호출·export `finally` 누락 탐지
- 원본 최상위 ID와 내부 좌표 불일치 탐지
- 형태분석 세션과 메타 ID의 중복·누락 탐지

## 3. MFA preflight

2026-07-24 19:53 KST 실행 결과:

- D: 볼륨 레이블 `DATA_SSD`
- C: 여유 49.9GB, D: 여유 334.4GB
- acoustic `korean_mfa`, dictionary `korean_mfa`, G2P `korean_mfa` 확인
- MFA 필수 패치 7종 확인
- 2020–2025 세션 하위폴더 구조 확인
- FAIL 0, WARN 0

설치 소스 hash와 검사 상세는
`outputs/reports/mfa_install_baseline_20260724.json`에 기록했다. 이 검사는
설치 환경과 구조를 확인한 것이며, 대량 정렬이나 새 TextGrid를 생성하지 않았다.

## 4. 메타 ID 결함의 재현과 복구

### 교체 전 재현

형태분석 세션 17,156개, 메타 행 17,156개였지만 메타 ID 중복이 4개였고 다음
세션이 누락되어 preflight가 실패했다.

```text
SDRW2300000445
SDRW2300000457
SDRW2300000473
SDRW2300001337
```

네 JSON의 파일명 stem·내부 문서 ID·내부 발화 ID는 서로 일치했다. 최상위
`id`만 각각 직전 세션을 가리켰다. 따라서 파일 stem을 조인 좌표로 사용하고
잘못된 최상위 값은 `source_top_id`에 보존했다.

### 격리 전수 검증

- 입력 JSON: 17,156
- 출력 행: 17,156
- 최상위 ID 불일치: 4
- JSON parse 오류: 0
- 내부 ID 오류: 0
- 다중 document 오류: 0
- 출력 스키마·순서·중복 검증: 통과

### D: 파생 레이어 교체

기존 CSV를 아카이브한 다음 새 CSV를 원자적으로 승격했다.

| 파일 | SHA256 |
|---|---|
| 구판 archive | `1AFF90B35A3E839C15085C450330BCCA5C65C073A15A58D7EA92FE81132BE244` |
| 새 `file_meta.csv` | `6C9FF0342A2552D20FCBF73C481717FE30A065287C128CD4B4DB3729CD0ED753` |

구판 위치:
`D:\10_LAYERS\04_metadata_index\_archive\metadata_fix_top_id_20260724\file_meta.csv`

실행 manifest:
`D:\10_LAYERS\04_metadata_index\_runs\metadata_metadata_fix_top_id_20260724.json`

교체 뒤 preflight는 형태분석·메타 ID 집합 17,156개 일치, 중복·누락 0으로
통과했다. `D:\00_RAW` 파일은 수정하지 않았다.

## 5. 검색 마스터 파일럿

메타가 누락됐던 `SDRW2300000445`를 의도적으로 선택했다.

| 지표 | 값 |
|---|---:|
| 입력 발화 | 216 |
| 출력 행 | 216 |
| 문서 메타 결측 | 0 |
| 화자 결측 | 0 |
| JSON 발화 결측 | 0 |
| 어절수 불일치 | 0 |
| form–tagged 정렬 경고 | 31 |
| 판정 | 통과 |

정렬 경고 31건은 숨기지 않고 실행 manifest에 남겼다. 이 값은 새 메타 복구
실패가 아니라 기존 형태소 분석의 form–tagged 정합 QC 신호다.

파일럿 출력은 프로젝트 `work\pre_bulk_pilot\search_master`에 두어 본 산출물과
분리했다. 사람이 읽는 로그는
`logs/build_search_master_recovered_meta_20260724.txt`에 남겼다.

## 6. 아직 하지 않은 일과 다음 게이트

- 대량 MFA G2P 재정렬: 미실행
- 검색 마스터 전량 CSV: 2026-07-23 생성 완료. 다만 7/24 메타데이터 수정 전
  산출물이고 lexicon 사전 발음 예외와 coverage는 아직 반영되지 않음
- 이번 감사에서 전량 search master 재생성: 미실행
- Parquet 미러: 미실행
- 원본 JSON 직접 교정: 미실행

다음에는 먼저 기존 전량 search master의 행·세션·메타·사전 발음·coverage를
감사한다. MFA는 연도별 소표본에서 TextGrid의 파일 대응, tier, 시간 경계,
어절 위치 찾기 용이성, `spn`과 실패 분포를 확인한다. phones는 ㄴ 삽입 등
현상의 최종 실현 판정값이 아니며, 최종 판정은 연구자가 음성과 TextGrid를
직접 검토해 기록한다.
