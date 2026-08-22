# PV-A 일곱 현상 미리듣기 구현 결과

작성일: 2026-08-19
상태: **PV-A 생성·독립 감사 통과 / 균형 14개 후속 reviewer 사용성 확인 완료**

## 1. 이 문서가 기록하는 범위

`PLAN_stage2_seven_phenomena_PV_pilot_20260819.md` §5의 작업 1–9만
구현한다. 이 문서는 사용자가 wrapper를 실행한 뒤 실측 결과를 채울 수 있는
RESULT 기록이다. 2026-08-19 실제 wrapper 실행에서 표본 180개를 생성하고 독립
감사를 통과했다. `listening_gate=open`은 청취를 시작해도 된다는 기술적 gate일
뿐이며, 자동 청취나 자동 실현 판정은 수행하지 않았다.

이번 구현에 확정 반영한 연구자 결정은 다음과 같다.

- 2020–2025 각 연도 30개, 합계 180개 물리 패키지
- 현상별·연도별 기본 4개와 순환 추가 2개
- VH/HIA 공유 후보는 물리 자산 하나, 논리 검토 이벤트는 현상별 분리
- 문맥은 같은 `session_id`·`dialogue_id`의 **실제 존재 행 순위 ±2**
- 연속 동일 화자는 정답 `turn`이 아니라 탐색용 조작적 화자 묶음
- 원 타임스탬프 차이는 휴지 또는 turn 증거가 아님
- 원천 표별·연도별 200,000행 고정 상한, 자동 증액 없음
- 2022 NAL의 자산·시간 연결 가능 후보가 상한 안에서 2개뿐이라는 실측에 따라,
  연구자 승인으로 2022 NAL 2개를 PT 1개·NAN 1개로 재배정
- 자동 실현 판정 없음; PV 기록은 정식 판정 ledger와 분리

## 2. 구현 파일

| 작업 | 파일 | 역할 |
|---|---|---|
| 1 | `config/target_queries/pv_preview_boundary_20260819.json` | PV 전용 draft 환경 질의·배분·문맥·안전 계약 |
| 2 | `scripts/python/build_pv_preview_samples.py` | 기존 builder 재사용, 동결 ㄴ삽입 후보 결합, 배분·zero-drop 회계 |
| 3 | `scripts/python/scan_pv_morph_internal_lite.py` | 형태소 내부 인접 자모 D1-lite 상한 스캔 |
| 4 | `scripts/python/build_pv_context_manifest.py` | 기존 행 순위 ±2와 조작적 화자 묶음, 다섯 슬롯 보존 |
| 5 | `scripts/python/build_pv_review_bundle.py` | 대상 자산·직렬화 문맥·HTML·CSV 검토 묶음 |
| 6 | `scripts/python/audit_pv_preview.py` | 생성기와 분리한 조건·배분·문맥·stitch·SHA 감사 |
| 7 | `run_pv_preview_pilot.ps1` | PS 5.1용 preflight와 detached 실행·로그·원자 승격 |
| 8 | 이 문서 | 실행 뒤 실측 RESULT 기록 틀 |
| 9 | `docs/decisions/NOTE_pv_b_environment_preflight_20260819.md` | PV-B 환경의 문서·실물 위치 점검(실행 없음) |

`pv_preview_common.py`는 위 2–6이 함께 쓰는 출력 원자성·헤더 검증·상한·SHA
보조 모듈이다. 기존 ㄴ삽입 builder·linker와 동결 산출물은 수정하지 않았다.

문맥 직렬화는 기존 `stitch_session.py`가 요구하는 전체 세션 입력과 이번
선택 다섯 슬롯 계약이 달라 그 스크립트를 수정하지 않고, 동일한 핵심 원칙
(원 좌표 보존, 합성 seam 명시, 역환산 manifest)을 PV 전용 adapter에 적용했다.

## 3. 실행 전 검증

2026-08-19에 실제 생산 스캔 없이 다음을 검증했다.

- Python `py_compile`: 6개 PV Python 파일, exit 0
- Python import smoke: 6개 모듈 import 성공
- 합성 dry test: 16개 시나리오 통과
  - scanner, 표본 배분, 문맥, bundle, 독립 감사의 성공 경로
  - 의도된 실패 경로
  - 기존 출력 존재 시 `FileExistsError` 중단
  - 180개 물리 표본·205개 논리 이벤트·900개 문맥 행 fixture에 대한 감사 통과
  - 한 표본을 제거한 fixture의 감사 `passed=false`, listening gate 폐쇄
- wrapper `-PreflightOnly`: exit 0; 후보 스캔·출력 생성·음성 처리 없음
- Windows PowerShell 5.1 parser: 오류 0
- `tests/test_powershell_safety.ps1`: 72개 파일 PASS
- `tests/test_powershell_runtime_compat.ps1`: 72개 script PASS
- wrapper 첫 3바이트: `EF BB BF`
- wrapper 기존 출력/없는 Python 실패: 둘 다 exit 1

검증 로그 디렉터리:

```text
logs/pv_preview_pilot_validation_20260819/
```

주요 로그 receipt:

| 로그 | bytes | SHA-256 |
|---|---:|---|
| `01_python_py_compile.log` | 59 | `753F12972121AB7C9DC6915824F6C4D28FE0E3E3E00E479EB424F6EF9D123A3F` |
| `02_powershell_parse.log` | 53 | `367560D50720B66B5F036FC9AD50FCA371507EB046A06D8E568DBB82A372B885` |
| `03_wrapper_preflight.log` | 48,256 | `1E5D294DB3DBB74B3BCE14015162D9354C02DC08F48D239A880561529C090BFB` |
| `04_test_powershell_safety.log` | 42 | `FB029E845DA9E2E476AA9445F075977A8E68BCBE1A3920686169E5608AF01E9C` |
| `05_test_powershell_runtime_compat.log` | 64 | `6711CBBC2D5421C3B00217D1EA10E74904DCC35D55DB5F340DD78ABE580D54B4` |
| `06_python_imports.log` | 14 | `F07CBBE7EAD977CF2AE6B0B5D8B304F1D2996BCF3E66A86FE162F0425BB7EB63` |
| `07_synthetic_dry_tests.log` | 2,753 | `6554641CFFCB492D082B99251BD591BB05071924000F93D3A24377FAB4A97851` |
| `08_wrapper_existing_output.log` | 678 | `7DC596C1019DBC23B66F3CA4AFC405A631C1D708D4EC25122EDD8316064A36B6` |
| `09_wrapper_failure.log` | 546 | `6964051EE8FB4ACC60EBEF9E1B1B3E6E61DAE3A335EE657E46971F5DCC0FD911` |

합성 fixture는 결과 확인 뒤 검증 전용 경로만 확인하여 제거했다. 실제
`pv_seven_phenomena_20260819` final 또는 `.partial`은 만들지 않았다.

### 3.1 구현 receipt

| 파일 | 행 수 | SHA-256 |
|---|---:|---|
| `config/target_queries/pv_preview_boundary_20260819.json` | 378 | `68d0b8cc0bc97019817d779341fa734324eea5467d80d92fa3f90726fa64f736` |
| `scripts/python/pv_preview_common.py` | 483 | `56488739bb0d5c21081275b7d194f148f660f194287e06ea70b4ef926a384bdd` |
| `scripts/python/scan_pv_morph_internal_lite.py` | 304 | `f9ff315e70df7ae104705593fad7b7e043b6203851de2acbf7b5199387efc6e4` |
| `scripts/python/build_pv_preview_samples.py` | 1,061 | `e92f61024b490a4b8587ae36641e790be990eda6e954836ac413a38d45840228` |
| `scripts/python/build_pv_context_manifest.py` | 602 | `505766bae1ef2c2b6032287407cd2fd21e1c2a6e56f735a8dfdaf8bd4a30ccf1` |
| `scripts/python/build_pv_review_bundle.py` | 615 | `b1f603f441702ecec0099e922a11a000fdc8f7cb0aae0e5aa7a6cda93c691dbe` |
| `scripts/python/audit_pv_preview.py` | 713 | `86ba9c77ab7f61e8544487f992c7fb3a03515232aa0cf621daf5e3edf362344c` |
| `run_pv_preview_pilot.ps1` | 256 | `3dc7940ec53d7b587277f06d97098f723702310acb10ad1b4295d45532668f35` |

실행 중 보정과 최종 독립 확인의 추가 로그 receipt:

| 로그 | bytes | SHA-256 |
|---|---:|---|
| `13_approved_2022_quota_exception.log` | 218 | `b1bc2d2e0e43da121452627ef4ca4271d23bb5c636c18213cab33cfb884ed46c` |
| `14_post_reallocation_py_compile.log` | 15 | `155b3cf483721fa13c70ae89d1940707b98b9cab30affcbbc4f8a60f4fd48fcd` |
| `15_context_ledger_zero_drop.log` | 235 | `816c596647afe3e1adb568c5eb0dbb552637f384d16b256c36bb9c8899c264cb` |
| `16_interpretation_limit_audit_regression.log` | 6,820 | `f851ac46379906a623094e7b4d356224890cd3ba0c221b1855a06ce01c8f563f` |
| `17_universal_interpretation_limit.log` | 526 | `5a9524ee40fda01220de6fa1d97c6c9686a0742ef18433fae9169b28016733ed` |
| `18_final_sha_verification.log` | 1,020 | `d5b67cf9e48b1ad5b6ba517064846c2b2a2a080e068f04d7404d687b7ce829c0` |

## 4. 실행 명령 기록

재현 시 먼저 출력 없이 경로·manifest·실측 헤더를 확인한다.

```powershell
Set-Location 'C:\Users\ari30\research\2026_summer_research'
& '.\run_pv_preview_pilot.ps1' -PreflightOnly
```

preflight 통과 뒤 실제 생성 작업은 다음 단일 명령으로 시작한다. 이번 결과는 이
명령으로 숨은 worker를 시작해 만들었다. 현재 final이 존재하므로 같은 경로에서
재실행하면 비덮어쓰기 규칙에 따라 중단한다. 청취는 감사 통과 후에도 자동으로
시작되지 않는다.

```powershell
& '.\run_pv_preview_pilot.ps1'
```

진행 로그 예정 경로:

```text
outputs/pilots/pv_seven_phenomena_20260819.partial/logs/runner.log
```

완료 판정 파일 예정 경로:

```text
outputs/pilots/pv_seven_phenomena_20260819/PV_MANIFEST.json
outputs/pilots/pv_seven_phenomena_20260819/audit/PV_AUDIT.json
outputs/pilots/pv_seven_phenomena_20260819/PV_SHA256_MANIFEST.csv
```

`PV_AUDIT.json`의 `passed=true`, `listening_gate=open`을 확인하기 전에는
`bundle/INDEX.html` 청취를 시작하지 않는다. 기존 final 또는 `.partial` 경로가
있으면 wrapper는 덮어쓰지 않고 중단한다.

## 5. 실행 실측 결과

| 항목 | 실측값 |
|---|---|
| 실행 시작/종료 시각 | 2026-08-19 18:07:52 / 18:11:38 KST |
| query config SHA-256 | `68d0b8cc0bc97019817d779341fa734324eea5467d80d92fa3f90726fa64f736` |
| 후보 회계 행 수 | 18,339 |
| 물리 패키지 수 | 180 (연도별 각 30) |
| 논리 검토 이벤트 수 | 214 |
| 문맥 행 수 | 900 (표본당 5행) |
| 누락 edge 슬롯 수 | 9 |
| ledger 상한 안에서 조회되지 않은 문맥 이웃 ID | 116 (행 삭제 없이 상태 보존) |
| target WAV/TextGrid 누락 | 0 / 0 |
| 감사 `passed` / 실패 검사 수 | `true` / 0 |
| root / bundle SHA manifest 행 수 | 1,456 / 1,443 |
| `PV_AUDIT.json` SHA-256 | `628cb01692c28e14b9cfe00271fc3aa6e9c33267aafe34895c95c6f7d6896db2` |
| 최종 파일 수 / bytes | 1,463 / 133,426,435 |

2022년 최종 주현상 배분은 PT 5, NAN 5, NAL 2, NI 4, LLN 5, VH 5,
HIA 4로 합계 30이다. 나머지 연도도 각각 30개다.

독립 재검산 로그:

```text
logs/pv_preview_pilot_validation_20260819/18_final_sha_verification.log
```

이 재검산은 root manifest 1,456행과 bundle manifest 1,443행의 실제 bytes·SHA를
모두 다시 계산했으며, 누락 경로·여분 경로·해시 불일치가 각각 0이었다.

### 5.1 실행 중 중단과 zero-drop 보정 기록

실패 실행은 삭제하지 않고 다음 경로에 보존했다.

- `pv_seven_phenomena_20260819_failed_20260819T165731`: capped release lookup
  밖 후보를 조용히 버리지 않도록 metadata-only 상태를 추가
- `pv_seven_phenomena_20260819_failed_20260819T170530`: 선택 전에 WAV·6-tier·
  연결 시간을 검증하도록 보정
- `pv_seven_phenomena_20260819_failed_20260819T171057`: 2022 NAL 실측 2개 확인,
  연구자 승인 재배정의 근거
- `pv_seven_phenomena_20260819_failed_20260819T175735`: 문맥 이웃의 capped ledger
  결측을 행 삭제 없이 명시 상태로 보존하도록 보정
- `pv_seven_phenomena_20260819_failed_20260819T180503`: 모든 표본에 자동 실현
  판정 금지 문장을 동일하게 명시하고 독립 감사 조건을 강화

## 6. 해석 경계와 후속 설계

PV-A는 “어떤 환경을 얼마나 안정적으로 뽑아 들을 수 있는가”를 점검한다.
음운변이 선행연구에서 유용한 동음이의어·형태 분석 통제, 화자·발화양식 층화,
음향·청각 다중 단서, 제외 사유 회계는 후속 정식 판정 설계의 입력으로 보존하되
이번 구현에 새 판정 규칙으로 넣지 않았다. 근거 문헌별 적용 시점은
`docs/reviews/incoming/LITERATURE_REVIEW_modu_corpus_pv_design_20260819.html`에
분리해 두었다.

## 7. RESULT 확정 상태

1. `-PreflightOnly`와 실제 wrapper 실행: 완료
2. 감사 JSON `passed=true`, `listening_gate=open`: 완료
3. 실측 행 수와 SHA 기록: 완료
4. 전체 180개 청취: 아직 미실행. 2020·2025×7현상 균형 14개는 후속
   reviewer v2.1에서 최소 화면·안전 동작을 확인했다.

2026-08-22 후속 결정에 따라 전체 청취나 새 연도별 batch를 바로 시작하지
않는다. 일곱 현상별 직접 선행연구와 일반적·주변적·탐색적 형태론 환경을 먼저
정리한 뒤 표본 우선순위와 묶음·재검토 방식을 별도 승인한다.
