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

현재 판정: **RUNNING — shard 1/35 계산 중**
