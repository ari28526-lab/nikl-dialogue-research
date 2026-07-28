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

## 10:54–11:04 재개와 기본 사전 확률열 오류

로깅 수정 뒤 같은 RunId로 재개했다.

- 이전 G2P temp는
  `archive_failed\20260728_105423\sample_words_g2p_temp`로 이동했다.
- 표본 어절 G2P: 317/317, 완료 marker 생성
- 사전 한글 발음 phone 변환: 24/24 입력 처리, 완료 marker 생성
- 5단계 파생사전 phone gate에서 숫자 `0.01`–`52.64` 등을 acoustic
  inventory 밖 phone으로 탐지하고 중단했다.

실제 `korean_mfa.dict`는 단순한 `단어 + phone` 파일이 아니라 다음
형식이었다.

```text
단어  발음확률  뒤침묵확률  앞침묵보정  앞비침묵보정  phone...
```

최초 parser는 선택적 확률 4열을 phone으로 잘못 읽었다. 그 결과 구
registry의 exact-word 포함 여부와 OOV 집합은 맞았지만,
`base_mfa_dictionary` 후보의 `pron_phones_mfa`에는 확률 숫자가 섞였다.
따라서 구 registry와 그 hash를 사용하는 표본·G2P·결과는 새 실행에서
의존 산출물과 함께 `archive_failed`로 보존한 뒤 재구축한다.

### 수정된 사전 계약

- MFA 3.4의 `parse_dictionary_file`과 같은 선택적 확률열 인식 순서를
  사용한다.
- 정책 A와 B 모두 기본 사전 21,009행의 순서·phone·확률 4열을
  의미적으로 그대로 보존한다.
- 정책 A의 표본 OOV G2P만 새 무확률 행으로 덧붙인다.
- 정책 B는 정책 A에 exact-word 우리말샘 변이를 무확률 행으로
  추가한다. MFA 3.4에서 무확률 행의 발음 가중치는 기본값 1.0이다.
- 이는 등재 변이의 **사용 가능성 availability** 파일럿이지 발음확률
  추정이 아니다. 정책 B 채택 뒤 확률 보정은 별도 연구 결정이다.

실제 자료 smoke test:

| 항목 | A | B |
|---|---:|---:|
| 기본 사전 보존 행 | 21,009 | 21,009 |
| 표본 OOV 추가 행 | 190 | 190 |
| 우리말샘 변이 추가 행 | 0 | 15 |
| 최종 행 | 21,199 | 21,214 |
| acoustic inventory 밖 phone | 0 | 0 |

MFA 3.4 자체 parser로 두 파일을 다시 읽어 행 수, 기본 21,009행의
line-for-line 동일성, 추가 행의 무확률 계약, phone inventory를 모두
확인했다. `궹장히`는 현재 G2P grapheme 범위에서 phone으로 변환되지 않아
`attested_pron_g2p_missing` 2행으로 명시적으로 제외했다. 조용한 `spn`
대체나 정책 B 삽입은 하지 않았다.

