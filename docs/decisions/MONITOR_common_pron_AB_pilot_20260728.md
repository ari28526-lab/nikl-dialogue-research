# 공통 발음 A/B 파일럿 점검대장 — 2026-07-28

## 목적

`ab_stress_control_20260728_01`을 끝까지 점검해 뒤늦은 전면 재실행을
막는다. 단계별 완료 marker, 입력·출력 수, 오류 로그, 부분 성공,
A/B 동일 입력, 원자료·기존 결과 비변경을 확인한다.

대상은 다음 격리 release뿐이다.

```text
D:\mfa_common_pron\releases\
  common_pron_pilot_full6y_20260728
```

기존 2020·2021 canonical CSV/TextGrid와 원자료는 수정 대상이 아니다.

## 10:37–10:42 최초 실행 점검

- 10:37:44 PowerShell 실행 시작을 확인했다.
- MFA 3.4.0 설치 검증 10항목은 모두 통과했다.
- 2020–2025 동결 vocabulary `881,237`개를 모집단으로 registry seed를
  만들었다.
- registry는 `199,119`행이며 전체 vocabulary OOV는 `866,691`개다.
- 6개년 × 실제 화자 5명 × stress/control 2발화인 60발화 A/B 입력을
  만들었다.
- 10:39:30 표본 어절 G2P가 `Generating pronunciations...`까지 간 뒤
  실행 자식 프로세스가 사라졌다.
- `sample_words_g2p_done.json`, 파생 lexicon, A/B align marker는 없었다.
  따라서 lexicon 생성과 MFA 정렬은 시작되지 않았다.
- 남은 것은 0바이트 최종 산출물이 아니라
  `g2p_temp\words\sample_words\`의 DB·내부 로그뿐이다. 같은 RunId
  재개 시 `Archive-Incomplete`가 이 부분을 `archive_failed`로 옮긴다.

### 무손상 판정

- 원자료 수정: 없음
- 기존 2020·2021 canonical 결과 수정: 없음
- A/B TextGrid 부분 성공을 완성으로 오인할 위험: 없음
- 재사용 가능한 완료 단계: registry와 byte-hash 검증된 A/B 표본
- 재실행해야 하는 최초 단계: 표본 어절 G2P

## 원인 재현

동일한 `sample_words.txt` 317개를 격리된 프로젝트 진단 폴더에서
실행했다.

| 설정 | 결과 | 경과 | 출력 |
|---|---:|---:|---:|
| `num_jobs=1` | 성공 | 63.93초 | 317/317행 |
| `num_jobs=4` | 성공 | 63.16초 | 317/317행 |

따라서 G2P 모델·317개 어절·4개 병렬 작업 자체는 실패 원인이 아니다.

원인은 Windows PowerShell 5.1의 네이티브 stderr 처리였다.
새 러너는 전역 `$ErrorActionPreference='Stop'` 상태에서 MFA의 stdout과
stderr를 합쳐 `Tee-Object`로 보냈다. Windows PowerShell 5.1은 정상적인
MFA 진행 표시도 `ErrorRecord`로 바꾸므로 첫 진행 출력에서 파이프라인과
MFA를 중단했다.

## 수정

`Invoke-MfaLogged`의 네이티브 MFA 호출 경계에서만
`$ErrorActionPreference='Continue'`를 사용한다. 호출 직후 실제
`$LASTEXITCODE`를 별도 변수에 보존하고 `finally`에서 기존 preference를
복구한다. 실패 판정은 stderr 유무가 아니라 process exit code와 출력
marker 검증으로 한다.

이 방식은 정상 진행 표시를 허용하지만 실제 MFA 실패를 숨기지 않는다.
각 단계의 non-zero exit, 출력 누락·0바이트, TextGrid 수 불일치 검사는
그대로 유지된다.

검증:

- PowerShell 안전검사: 7개 파일 통과
- Python `unittest`: 96개 통과
- `git diff --check`: 통과
- 참고 시행착오: MFA 환경에는 `pytest`가 없어 설치를 추가하지 않고
  프로젝트 표준인 `unittest`로 검증했다.

## 재개 원칙

- 새 RunId를 만들지 않고 `ab_stress_control_20260728_01`로 재개한다.
- registry와 A/B 표본은 manifest·hash가 맞을 때만 재사용한다.
- marker 없는 G2P temp는 보존 archive 뒤 새로 만든다.
- A와 B는 별도 temp·출력·marker를 사용한다.
- 60/60 TextGrid, A/B 입력 SHA256 동일, 4-tier 경계, phone inventory,
  `spn`과 phone 변화 비교가 끝나기 전에는 정책 B를 채택하지 않는다.

