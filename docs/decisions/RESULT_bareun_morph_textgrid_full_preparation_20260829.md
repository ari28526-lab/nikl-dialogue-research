# 바른 v3.1 형태소 TextGrid 전수 실행환경 준비 결과

작성일: 2026-08-29 KST

상태: **준비·검사 완료 — 사용자 PowerShell 실행 필요**

## 결론

기존 r3 6-tier TextGrid 4,286,046건의 시간축과 앞의 5개 tier를 그대로
보존하면서 `morph_analysis_utt` label만 바른 v3.1 형태소 final로 갱신하는
전수 실행환경을 준비했다. 전수 생성은 아직 시작하지 않았다.

원본 TextGrid·WAV·바른 CSV final은 읽기 전용이다. 새 파생본은 D:를 먼저
사용하고, 다음 바른 receipt가 D: 18 GiB 안전선을 넘길 것으로 예상될 때 해당
receipt 전체를 C: 임시 저장소로 보낸다. C:도 20 GiB 안전선을 넘으면 파일을
채우지 않고 `paused_storage_safety`로 멈춘다.

## 실제 preflight 결과

2026-08-29 실행 직전과 같은 Windows PowerShell 5.1 진입점에서 다음을
확인했다.

| 항목 | 확인값 | 판정 |
|---|---:|---:|
| 바른 final receipt | 17,156 / 17,156 | 통과 |
| 예상 전체 발화 | 5,103,356 | 계약 고정 |
| 예상 파생 TextGrid | 4,286,046 | 계약 고정 |
| MFA 미대응 발화 | 817,310 | 누락하지 않고 별도 기록 |
| D: 여유 / 하한 | 56.199 / 18 GiB | 통과 |
| C: 여유 / 하한 | 37.752 / 20 GiB | 통과 |
| 하한 제외 합산 가용량 | 55.951 GiB | 통과 |
| 파일럿 추정 + 추가 headroom | 47.928 GiB | 통과 |
| 파일럿 기계 감사 | 12 / 12 | 통과 |
| 사용자 대표 검토 | 3 / 3 | 통과 |

공간값은 전수 실행 직전에 자동으로 다시 측정한다. 위 값이 변해 계약을
충족하지 않으면 실행은 시작되지 않는다.

## 중단·재개 및 감사

- 파일은 목적지와 같은 볼륨의 고유 `.partial`에 먼저 쓴 뒤, 6-tier 구조·앞의
  5개 tier·형태소 경계·새 label을 검증하고 원자적으로 확정한다.
- SQLite checkpoint와 receipt별 압축 inventory에 저장소 ID, 상대경로,
  원본·파생본 바이트와 SHA-256을 기록한다.
- 완료 receipt는 바른 receipt와 output inventory SHA를 확인하고 건너뛴다.
- 생성이 끝나면 자동으로 독립 전수 감사를 시작한다. 감사도 receipt 단위로
  체크포인트를 남겨 재개할 수 있다.
- 분산 결과는 즉시 final로 승격하지 않는다. 생성·감사 통과 뒤에도
  `passed_pending_external_consolidation`으로 두고, 새 외장하드에 복사→전수
  확인→사용자 승인 순서로 합친다.

## 검증 결과

- Python compile: 통과
- 전용 회귀 검사: 6 / 6 통과
  - D: 우선 배치
  - D: 하한 보호 후 C: spill
  - 두 저장소 부족 시 쓰기 전 안전 정지
  - 앞의 5개 tier 불변과 형태소 label 교체
  - receipt 생성·SHA 감사·완료 receipt 재채택
- 프로젝트 PowerShell safety: 74 / 74 통과
- Windows PowerShell 5.1 runtime compatibility: 74 / 74 통과
- 실제 PowerShell `-PreflightOnly`: `ready=true`
- 상태판 초기값: `phase=not_started`, `state=none`

## 실행 및 상태 확인

전수 실행 명령은 사용자에게 대화에서 한 번에 복사할 수 있는 형태로 제공한다.
실행 뒤 다른 PowerShell 창에서 다음 읽기 전용 명령으로 확인한다.

```powershell
cd C:\Users\ari30\research\2026_summer_research
.\show_bareun_morph_textgrid_status.ps1
```

중단 뒤에는 최초 실행 명령에 `-Resume`만 추가한다. 결과 폴더를 지우거나 같은
이름으로 새로 시작하지 않는다.
