# 공통 MFA 발음사전 r1 실시간 점검대장 — 2026-07-28

대상 release:
`D:\mfa_common_pron\releases\common_pron_mfa_r1_20260728`

목표:

1. 866,691개 OOV의 G2P shard 35개를 전부 생성·검증한다.
2. 기본사전 보존, attested variant 0, `spn` 0, acoustic inventory 이탈
   0인 최종 공통사전을 만든다.
3. 2020 최종 TextGrid, 2020 부분 DB 내부 후보, 2021 완성 DB의 세 전수
   동등성 gate를 mismatch 0으로 통과한다.

## 시간순 기록

| 시각 | 상태 | 증거와 판정 |
|---|---|---|
| 13:38 | 첫 사용자 실행이 shard 시작 전에 중단 | 빈 incomplete 목록이 StrictMode에서 `$null.Count`가 된 runner 오류. lock 0, output shard 0, log 0, work 0으로 G2P 미시작·무손상 확인 |
| 13:41 | 수정 commit `e0f4c77`로 재시작 | release lock PID 26900, `mfa.exe`와 parent Python 및 worker Python 4개 생성 |
| 13:42 | shard 1 계산 시작 확인 | `oov_00001.dict`가 5초 동안 12,906→14,680 bytes로 증가. D: 263.71GiB |
| 13:43 | worker·출력 재확인 | `mfa.exe` PID 7916, Python PID 10996 및 worker 10976/10284/26116/14660 활성. worker CPU 각각 약 76초. 출력이 6초 동안 35,480→37,486 bytes로 증가. 완료·검증 report는 아직 0/35 |
| 14:15 | 읽기 전용 상태판 검증 | `show_common_pron_mfa_status.ps1`가 shard 행 수·평균 처리율·ETA, lock PID 생존, DriveInfo 여유 공간, manifest·동등성 gate를 한 번에 표시. release 자료를 쓰거나 프로세스를 제어하는 명령이 없음을 PowerShell 안전성 검사에 추가 |
| 14:21 | shard 1 완주 뒤 전수 coverage gate 실패 | MFA는 25,000개 중 24,966개만 생성하고 정상 exit했으나, strict grapheme 미지원 어절 34개가 누락됨. 검증기가 누락을 차단하고 output·log·temp를 `archive_failed\20260728_142132\shard_00001_verification_failed`에 보존한 뒤 runner가 lock을 해제하고 중단. 원자료·기존 결과 손상 없음 |
| 14:25 | 6개년 OOV grapheme 전수 감사 | 866,691개 중 5,176개(0.597%)가 음절형 `korean_mfa` G2P의 2,112개 grapheme inventory 밖이며, 미지원 음절은 654종. `랩·챗·팠·텀·쭤·깻` 등 정상 어휘·활용형을 포함하므로 삭제·제외·비엄격 G2P는 불가 |
| 14:27 | 공식 Jamo 모델 확보 | 공식 `korean_jamo_mfa` v3.0.0을 fallback 후보로 추가. 파일 SHA256 `d866389d2d29f9b8dec6be84132182cd3527a354926479958b9193d26377511f`. 기존 음절형 모델을 주 모델로 보존하고 미지원 어절에만 쓸 수 있는지 별도 검증하기 전에는 채택하지 않음 |
| 14:30 | 2021 완성 DB의 숨은 `spn` 확인 | `갭·깻잎·랩을·쏴·아팠던·얜·여쭤보고·쪘어·텀이·힘듦이` 10개를 read-only 조회한 결과 전부 `word_type=oov`, `pronunciation=spn`. 과거 실행에서 문제가 새로 생긴 것이 아니라 strict G2P 누락을 MFA가 `spn`으로 흡수해 실행 성공처럼 보였음을 코드와 DB 양쪽으로 확인 |
| 14:55 | 최신 공식 모델 재검토 | sunk cost를 배제하고 공식 Hugging Face `MontrealCorpusTools/korean_mfa` commit `0091ffa...`의 acoustic v3.3.0·Jamo G2P v3.2.0·dictionary를 6개년 새 기준으로 선택. 구 2020·2021과 r1은 baseline으로만 보존 |
| 14:56 | MFA 내장 downloader의 거짓 갱신 차단 | `model download --force`가 exit 0이었지만 세 파일 SHA256이 구버전과 동일했음. 최신 확보 판정을 exit code가 아니라 upstream commit·version·SHA로 바꿈 |
| 14:58 | 첫 최신 clone의 CRLF 실패 | Windows Git 변환으로 `phones.sym` label이 `0\r`이 되어 OpenFST가 거부. `core.autocrlf=false` LF clone을 별도 생성하고 실패 clone은 증거로 보존 |
| 15:02 | 최신 묶음 동결·표준 로드 성공 | acoustic v3.3.0·Jamo G2P v3.2.0·dictionary를 D:에 deterministic archive로 동결. acoustic–G2P 107 phones 동일, G2P 표준 10단어 10/10, directory와 zip 출력 SHA 동일 |
| 15:04 | 최신 Jamo grapheme 전수 gate | 구 OOV 866,691개 중 4개만 미지원. 모두 종성 `ᆳ`이며 `ᆳ→ᆯ+ᆺ` Jamo 완전분해 후 같은 rewriter로 처리하고, 그 외 미지원은 중단하기로 결정 |

## 2020·2021 재실행 판단

- 기존 2020·2021은 같은 음절형 G2P를 사용했지만, 모델 미지원 어절에는
  실제 phone 대신 `spn`이 들어갔다.
- 따라서 수정된 공통사전이 이 어절들에 실제 phone을 부여하면 기존 DB·TextGrid와
  mismatch 0일 수 없다. 이는 새 사전 오류가 아니라 의도적인 결함 수정이다.
- 2020–2025에 동일한 phone 생성·정렬 방법을 적용했다고 연구 방법에 쓰려면,
  공통사전 계약을 동결한 뒤 2020·2021 MFA DB·TextGrid를 새 계약으로 재생성한다.
- CSV, 형태소 분석, 원 wav, 원 lab은 재생성 대상이 아니다. 기존 MFA 결과는
  구 기준 baseline과 차이 감사 자료로 archive·보존한다.
- 기존 2020·2021 동등성 검사는 “채택을 위한 mismatch 0 gate”에서 “구 기준과
  새 기준의 전수 차이 inventory”로 역할을 바꾸고, 새로 재실행한 2020·2021
  결과에 대해 공통사전 계약 일치와 전수 coverage를 다시 gate한다.

## 판정 규칙

- output 파일이 존재한다는 것만으로 shard 완료로 세지 않는다.
- `_state\shard_reports\oov_XXXXX.json`이 `status=success`이고 입력·출력
  word coverage, `spn`, phone inventory gate가 모두 0이어야 완료다.
- PowerShell이 MFA의 정상 stderr를 `NativeCommandError`로 포장한 문자열은
  단독 실패 신호가 아니다. 실제 process 생존, output 증가, MFA exit code,
  shard verification을 함께 본다.
- lock PID가 사라지고 lock만 남으면 stale lock으로 판정하되 수동 삭제하지
  않는다. 같은 runner가 archive한 뒤 재개하게 한다.
- source vocabulary, 기본사전, 모델, 기존 2020·2021 결과는 수정하지 않는다.

현재 판정: **r1은 SAFELY STOPPED·폐기된 생산 후보다. 최신 acoustic
v3.3.0 + Jamo G2P v3.2.0 단일 기준으로 r2를 새로 만들며, 공통사전의
missing=0·spn=0 전에는 연도별 MFA를 시작하지 않는다.**
