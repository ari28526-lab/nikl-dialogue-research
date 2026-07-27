# 외부 CSV·MFA 코드리뷰 수신 및 판정 기록

- 수신일: 2026-07-27
- 검토 대상 커밋: `ce421dbe8c6b7f5bb50202b69f3ff1785508ba5f`
- 외부 리뷰 원문:
  `docs/reviews/incoming/EXTERNAL_REVIEW_CSV_MFA_ce421db_20260727.md`
- 원문 행 수: 336
- 줄바꿈 정규화 후 원문 SHA256:
  `90b55a98e340d97b6d2a3831b62bfad7ee6749f37f5c2c2303f4ce92fcad6175`
- 판정 주체: 현재 프로젝트 작업 세션에서 코드·로컬 MFA 설치본·실행 상태를
  다시 대조함

## 1. 결론

외부 리뷰의 큰 결론은 타당하다.

1. 현재 진행 중인 2021 `pre_mfa_v1` 실행은 중단하지 않는다.
2. 2022 전량 실행은 아래 세 항목을 구현·검증하기 전 시작하지 않는다.
   - CSV 주석 길이와 동일 ID WAV 길이의 세션 단위 대응 검사(P1-01)
   - 예상 MFA 입력 중 형태소 원천 TextGrid 누락 사전 집계(P1-02)
   - 음향모델·기본 사전·G2P 모델의 SHA256 계약 고정(P2-05)
3. P1-02의 외부 권고인 “빈 형태소 tier도 연도 성공으로 처리”는 그대로
   채택하지 않는다. 이 연구는 형태소/표기 환경 검색을 출발점으로 삼으므로,
   `정렬 완료`와 `분석 준비 완료`를 구분하고 형태소 누락은 전수 inventory와
   명시적 보완·제외 판정 없이는 analysis-ready로 승격하지 않는다.
4. 2020·2021은 위 검사를 소급 적용한다. 문제가 발견되더라도 우선
   세션 단위 오염/누락 범위를 확정하고, 무조건 연도 전체를 다시 돌리지 않는다.

## 2. 현재 2021을 중단하지 않는 근거

2021 G2P 실행은 외부 리뷰 수신 뒤에도 세 작업자의 CPU가 계속 증가하고
하트비트가 갱신되는 정상 계산 상태였다. 오류나 watchdog 종료 조건은 없었다.

설치된 MFA 3.4.0 소스도 직접 확인했다.

- `montreal_forced_aligner/corpus/base.py:2007-2022`
  - `PyniniGenerator(... num_pronunciations=1, strict_graphemes=True)` 생성
  - `generate_dict_pronunciations()`가 먼저 전체 결과를 반환
- 같은 파일 `2063-2072`
  - 반환된 발음을 `pronunciation_insert_mappings`에 메모리상 구성
- 같은 파일 `2115-2135`
  - `Word`와 `Pronunciation`을 bulk insert한 뒤 마지막에 `session.commit()`

따라서 현재 G2P 계산을 중단하면 아직 DB에 반영되지 않은 장시간 계산을 잃을
가능성이 높다. 또한 현재 실행은 direct exporter의 fail-closed 검사로 마지막
누락을 차단하므로, 실행을 살려 baseline을 확보하는 편이 안전하다.

## 3. 모델 baseline 증빙

외부 리뷰의 P2-05를 즉시 수용해 실행 중 설치본을 읽기 전용으로 해시했다.

기계 판독 보고서:
`outputs/reports/MFA_MODEL_FINGERPRINT_baseline_20260727.json`

| 자원 | SHA256 |
|---|---|
| `korean_mfa` acoustic | `46f7a73ab46828c679562b160e0577beecfb4a9a827efe5ab392aee947451a4d` |
| `korean_mfa.dict` | `75683f4dc2a7dd95295a068206d248a30bd2f4f2231fd4449210c91d1e78150b` |
| `korean_mfa` G2P | `6938db05d83fa92c5c80681bf76fd7dd7af7f3ea8c7d7df1093790c641ad0344` |

세 파일의 수정 시각은 현재 2021 실행 시작보다 앞선다. 다만 기존 2020·2021
input contract/marker 안에 해시가 들어 있지는 않으므로, 기존 marker를 소급
변조하지 않고 이 별도 baseline 보고서로 연결한다.

## 4. Finding별 판정

| ID | 판정 | 처리 원칙 |
|---|---|---|
| P1-01 | 수용, 2022 차단 | 파일 존재/구조 검사만으로 잡을 수 없는 F29형 오염이다. 파일럿과 같은 세션 중앙 padding 제거 후 잔차 `≤0.025초`, 대응률 `≥98%`를 대량 preflight에 추가하고 2020·2021을 소급 감사한다. |
| P1-02 | 위험 진단 수용, 권고안 수정 | MFA 전에 예상 usable lab과 형태소 원천 TextGrid를 대조한다. 누락을 빈 tier로 조용히 성공시키지 않는다. 정렬 산출은 보존할 수 있지만 analysis-ready 판정은 실패시키고 누락 inventory를 보완/제외 결정에 사용한다. direct/built-in의 최종 의미론도 통일한다. |
| P2-03 | 수용, 언어학 승인 후 | `-히-` 구개음화 및 겹받침+ㅎ 규칙 결손을 새 `rule_version`과 회귀표본으로 수정한다. MFA 입력과 독립이므로 현재 2021은 재실행하지 않는다. 공통 발음 자원/검색 CSV 재생성 때 반영한다. |
| P2-04 | 수용, A/B 필요 | 숫자·라틴 혼합 발화를 모두 삭제하거나 현재처럼 한글만 남기는 정책 중 어느 쪽도 자동 정답으로 두지 않는다. 발화 ID inventory와 경고를 먼저 추가하고 소표본 정렬 품질 A/B 뒤 확정한다. |
| P2-05 | 수용, 1단계 완료 | 현 설치본 3종 해시는 별도 기록 완료. 다음 실행부터 alignment contract와 marker에 해시·MFA/Pynini 판본을 넣고 모델 변화 시 stale temp로 분리한다. |
| P2-06 | 수용 | 동결 CSV 밖 고아 lab을 preflight에서 hard fail하고, 향후 build 단계에서 계약별 archive 대상으로 만든다. 2021 실측 보고서는 0건이다. |
| P2-07 | 수용 | 한 번에 여러 연도를 자동 연쇄하지 않는다. 기본은 단일 연도이며, 다음 연도는 직전 연도의 독립 4-tier 감사·P1 감사·marker identity를 통과해야 한다. |
| P2-08 | 수용 | preflight의 필수 정규화 열 검사 반환값을 실제 gate에 포함하고 fresh/resume 결측 정의를 일치시킨다. |
| P2-09 | 수용 | quarantine 조회를 `paths.json`의 `mfa_state`와 세션 하위 구조 기준으로 고치고 평면 레거시를 폴백으로 둔다. |
| P3-10 | 수용 | 감사 스크립트에 명시적 strict exit를 추가한다. 자동 배선 전에 실패 fixture의 exit 1을 고정한다. |
| P3-11 | 수용 | `Done!` 이후에도 `phase=finalizing` heartbeat를 계속 기록하되 kill만 억제한다. 현재 실행에는 소급 적용하지 않는다. |
| P3-12 | 수용 | direct marker 복구 분기와 built-in 분기를 구분한다. 가능하면 direct 완료 marker를 원자화한다. |
| P3-13 | 수용, 2021 export 뒤 수정 | direct exporter의 `failed_examples`를 추가한다. 현재 2021이 나중에 이 파일을 새 프로세스로 읽을 수 있으므로 실행 완료 전 해당 파일을 바꾸지 않는다. |
| P3-14 | 수용 | 최소 sense 번호 선택 helper를 deprecated로 표시하고 새 공통 발음 registry에서는 사용하지 않는다. |
| P3-15 | 현행 유지+문서화 | 정상 경로 실측은 통과했고 watchdog이 producer 조기 사망 hang을 회수한다. 설치 패치 재변경은 별도 재현시험 없이 하지 않는다. |
| P3-16 | 수용 | `preflight_next_year_after_qc.py`가 direct 전용임을 문서와 실패 사유에 명시하고 built-in 완료 연도는 별도 QC 분기를 둔다. |
| P3-17 | 분할 수용 | 연구 재현성/게이트에 영향을 주는 경로·엔진 판본·missing JSON부터 고친다. 단순 표기 정리는 기능 수정과 분리한다. |

## 5. 구현 순서와 실행 간섭 방지

### 현재 2021 G2P/정렬과 병행해도 되는 작업

1. 외부 리뷰 원문·판정·모델 fingerprint 보존
2. 읽기 전용 readiness audit와 그 단위시험 보강
3. 2022 계획/게이트 문서 보강

### 현재 2021이 끝날 때까지 미루는 작업

1. `export_mfa_db_4tier.py`와 merge 의미론 변경
2. 현재 실행이 후속 단계에서 새 Python 프로세스로 읽을 수 있는 exporter 변경
3. MFA 설치 패치 변경

### 2021 완료 직후

1. lab–CSV 전수 일치 재확인
2. CSV–WAV duration 대응 전수 감사
3. 형태소 원천 TextGrid 누락 전수 감사
4. direct 4-tier 수량·tier·시간·경계·라벨 전수 감사
5. 문제 세션/발화 inventory 확정
6. 2020 동일 감사 소급 실행

### 2022 전량 실행 전

1. alignment contract에 모델/런타임 fingerprint 배선
2. P1 두 사전 게이트를 runner/wrapper에 fail-closed로 배선
3. 직전 연도 QC 강제
4. preflight와 PowerShell 안전성 회귀시험 통과
5. 사용자에게 보고한 뒤 2022 실행 여부 확인

## 6. 재실행 판단

이 리뷰만으로 2020·2021 전량 재실행을 결정하지 않는다.

- duration 오염 세션 발견: 해당 세션 제외 또는 원자료 재분절 뒤 세션 단위 재정렬
- 형태소 원천 누락: 정렬 DB/TextGrid는 보존하고 형태소 보완 가능성부터 판단
- 새 공통 발음 release 채택: baseline v0를 archive한 뒤 동일 release로
  2020–2025를 재정렬하는 방법론적 재실행을 별도 결정
- 규칙 발음 CSV 수정만 발생: MFA 재실행 없이 검색층만 새 version으로 재생성

이렇게 해야 “문제가 생겼으니 전부 다시 실행”과 “결과가 있으니 그냥 통과”라는
두 극단을 모두 피하고, 연구 자료의 변경 이유와 범위를 재현 가능하게 남길 수 있다.
