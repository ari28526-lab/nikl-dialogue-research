# Codex 리밋·새 대화 뒤 프로젝트 연속성

최종 갱신: 2026-08-07 KST

이 절차는 새 계정을 만들기 위한 것이 아니다. 같은 계정에서 Codex 사용 한도가
초기화되기를 기다리거나 새 대화를 열어도, 로컬 계산과 연구 계약을 잃지 않고
이어가기 위한 절차다.

## 가장 중요한 원칙

1. Codex 대화가 멈춰도 별도 PowerShell에서 실행한 작업은 독립적으로 계속된다.
2. 실행 창을 닫거나 같은 명령을 다시 입력하기 전에 반드시 읽기 전용 상태판을
   확인한다.
3. `*.partial`, MFA DB, shard manifest, lock을 임의로 삭제하지 않는다.
4. 채팅 기억이 아니라 현재 파일·manifest·Git commit을 정본으로 사용한다.
5. 2020 완성본과 원본 WAV/CSV는 변경하지 않는다.

## 새 대화에서 가장 먼저 할 일

다음 문서를 순서대로 읽는다.

1. `docs/environment/PROJECT_START_HERE.md`
2. `docs/environment/PROJECT_CURRENT_STATE.md`
3. `docs/RUNBOOK_production_2020_2025.md`
4. 이 문서

그 다음 아래 두 항목을 읽기 전용으로 확인한다.

```powershell
Set-Location "C:\Users\ari30\research\2026_summer_research"
git status --short
git log -3 --oneline
```

현재 단계가 pre-MFA 검색표라면 다음 상태판만 실행한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\show_production_year_pre_mfa_status.ps1" `
  -Year "2021"
```

상태 해석은 다음과 같다.

- `running`: 기존 PowerShell을 그대로 두고 모니터링한다.
- `complete`: annual manifest와 source contract를 독립 재검증한 뒤 다음 gate로
  진행한다.
- `interrupted_or_paused_resumable`: 완료 shard를 보존하고 partial 원인을 먼저
  조사한다. 자동 삭제·처음부터 재실행을 하지 않는다.
- `not_started`: RUNBOOK의 현재 한 단계만 실행한다.

MFA 단계에서는 `show_mfa_year_queue_status.ps1`를 사용하고 같은 원칙을 적용한다.

## 2026-08-07 r3 공통발음 후보 단계

현재 r2 연도 MFA는 차단돼 있다. r3 정본을 만들기 위한 Jamo G2P 후보 실행
상태는 다음 읽기 전용 상태판으로 확인한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\show_common_pron_mfa_r3_g2p_status.ps1"
```

- `prepared_not_started`: 310,605개·13 shard 입력만 준비됐고 G2P는 시작 전이다.
- `g2p_running`: 별도 PowerShell 계산이 진행 중이므로 창과 lock을 그대로 둔다.
- `interrupted_resumable`: 같은 실행 명령을 사용하면 완료 보고서가 있는 shard는
  건너뛰고 중단 shard만 다시 계산한다.
- `success_candidates_not_selected`: 후보 생성만 끝난 상태다. 최종 사전이나 연도별
  MFA가 시작된 것은 아니며, 규칙 Roman 정확 일치 선택 Gate가 다음 단계다.

부분 `.dict`만 보고 완료로 판단하지 않는다. 입력·출력·동결 모델 SHA가 묶인
shard 보고서가 있어야 완료다. r3 실행 명령은
`C:\Users\ari30\research\2026_summer_research\scripts\
run_common_pron_mfa_r3_g2p_candidates.ps1`이며, 새 대화에서는 먼저 상태판을
실행한 뒤에만 재개한다. 사용자에게 주는 명령은 현재 PowerShell 위치와 무관한
절대경로를 사용한다.

## 새 대화에 붙일 최소 프롬프트

```text
C:\Users\ari30\research\2026_summer_research의 작업을 이어가자.
먼저 AGENTS.md와 docs/environment/PROJECT_START_HERE.md,
PROJECT_CURRENT_STATE.md, docs/RUNBOOK_production_2020_2025.md,
CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md를 읽어라.
2020 완성본과 원본 WAV/CSV를 변경하지 말고, 현재 실행 프로세스·lock·manifest를
읽기 전용으로 확인한 뒤 재시작 여부를 판단하라. 완료 checkpoint를 보존하고
현재 Git commit과 실제 D: 상태를 대화 기억보다 우선하라.
```

## 계정 한도에 관한 운영 원칙

OpenAI 안내상 Codex 사용 한도는 플랜에 따라 다르며, 한도 도달 뒤에는 사용
페이지에 표시되는 크레딧·리셋·업그레이드 선택지 또는 한도 초기화를 따른다.
새 계정 생성은 이 프로젝트의 재개 절차가 아니다.

공식 안내:
<https://help.openai.com/en/articles/11369540-codex-in-chatgpt-faq>
