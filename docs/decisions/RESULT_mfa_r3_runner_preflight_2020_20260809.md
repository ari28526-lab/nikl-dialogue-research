# 2020 r3 runner·preflight 결과 (2026-08-09)

## 목적

외부 리뷰 체크리스트 5(C1, M1, M5, M6, M7)를 반영해, 기존 r2 DB·marker를
재사용하지 않는 release-scoped r3 MFA 실행 경로를 만들었다. 이 단계는
production Gate를 열거나 MFA를 시작하는 단계가 아니다. 닫힌 Gate를 포함한
실제 2020 계약으로 fail-closed 동작을 확인하는 단계다.

## 실행 이름공간과 불변 조건

- release ID: `common_pron_mfa_r3_20260809`
- release root:
  `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809`
- 2020 corpus:
  `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\corpus\2020`
- temp·DB:
  `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\temp\2020`
- MFA 출력:
  `D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809\mfa_output\2020`
- alignment contract ID:
  `3eff5ae34eb1015c05532140162636609099f1fd1203f561cc06d837039d8e8a`
- expected MFA input: 782,715발화

runner는 r3 경로에 r2 marker·DB가 있으면 중단한다. 기존 r2 marker·DB,
Stage 01–21, 원 WAV·CSV·TextGrid를 읽기 전용 근거로만 취급한다.

## 재시작·실패 정책

1. 2020 exact-ID 입력 목록과 recovered WAV를 대조한 뒤, 같은 D: 볼륨의 r3
   corpus에 WAV hardlink와 r3 전용 LAB만 만든다.
2. 최초 실행은 r3 temp가 없을 때만 MFA `--clean`을 사용한다.
3. 중단 뒤 재개는 같은 alignment contract ID의 `TEMP_CONTRACT_2020.json`이
   있을 때만 같은 temp·DB에서 수행한다.
4. 계약이 없거나 다르면 자동 삭제·자동 clean 재시도 없이 중단한다.
5. MFA 실패 시 temp·DB를 보존한다. heartbeat 쓰기 충돌은 공유 쓰기 재시도 후
   경고만 남기며 MFA 계산을 종료시키지 않는다.
6. runner 본체가 Windows 절전 방지를 설정하고 `finally`에서 복원한다.
7. MFA 단계에서는 TextGrid를 수출하지 않는다. DB 완료와 TextGrid/동반표
   수출을 분리해, 후속 tier·경계 오류가 생겨도 MFA를 다시 계산하지 않는다.

구 실행기의 명시적 full-clean 보존 경로에 있던 `Archive-StaleTemp` 인자 누락도
`($tmpYear, $tmp, $year, $reason)`으로 교정했다. Windows PowerShell 5.1
호환성 검사에서 합성 temp와 checkpoint를 실제 이동·보존하는 시험을 추가했다.

## 실제 2020 PreflightOnly 결과

보고서:

`outputs/reports/PREFLIGHT_mfa_r3_runner_2020_gate_closed_20260809.json`

- D: label `DATA_SSD`: 통과
- lock problem count 0: 통과
- alignment contract·독립 감사: 통과
- acoustic·dictionary·G2P와 exact-ID 목록 SHA: 통과
- 필요 공간 53.726 GiB, 관측 194.869 GiB: 통과
- r3 release 경로의 legacy artifact 0: 통과
- production release Gate: 의도적으로 실패

따라서 상태는 `NO_GO`, 유일한 실패 항목은
`production_release_gate`이다. 이 결과는 runner의 구조적 준비가 끝났지만,
체크리스트 6–7과 연구자 Gate 승인이 끝나기 전에는 MFA를 시작할 수 없다는
의도한 정지점이다.

## 검증과 다음 단계

- Python runner·corpus 합성 회귀: 3/3 통과
- `test_powershell_safety.ps1`: 통과
- `test_powershell_runtime_compat.ps1`: 통과(합성 temp 실제 보존 이동 포함)
- `run_mfa_r3_year_safe_body.ps1`: UTF-8 BOM·PowerShell 5.1 parse 통과

다음 단계는 체크리스트 6의 r3 exporter·독립 감사 확장이다. release Gate는
체크리스트 8 전까지 닫힌 상태로 유지한다.
