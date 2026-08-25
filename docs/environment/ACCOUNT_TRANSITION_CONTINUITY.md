# 개인 계정에서 학교 계정으로 전환할 때의 연구 연속성

최초 작성: 2026-08-25 KST
상태: 계정 비종속 저장소 기록 체계 사용

## 목적

개인 ChatGPT/Codex 계정을 갑자기 더 사용할 수 없게 되더라도 같은 로컬 저장소나
Git 원격에서 연구를 재개할 수 있게 한다. 채팅 기억이나 계정별 memory는 정본으로
간주하지 않는다.

## 정본과 보조 기록

1. 연구 계약·결정·완료 결과: 기존 `docs/decisions`, `docs/environment`, manifest
2. Git 기준선: 현재 branch, commit, upstream
3. 작업 경계 기록: `docs/environment/CONTINUITY_CHECKPOINTS.jsonl`
4. 로컬 미승인 자료: `work/`와 아직 commit하지 않은 working tree

`CONTINUITY_CHECKPOINTS.jsonl`은 한 작업 경계당 한 행을 추가하는 append-only
장부다. 각 행은 작업 요약, 다음 한 단계, 사용자 결정 필요 항목, Git 상태만
보존한다. 파일 내용, 절대경로, 비밀값은 기록하지 않는다.

## 자동 기록 규칙

저장소의 `AGENTS.md`는 실질적인 작업을 마치거나 안전 정지점에 도달하기 전에
다음 스크립트로 체크포인트를 남기도록 요구한다.

```powershell
& ".\scripts\write_continuity_checkpoint.ps1" `
  -Status "paused" `
  -Summary "이번 작업에서 확인하거나 변경한 내용" `
  -NextStep "새 계정에서 가장 먼저 할 한 단계" `
  -DecisionNeeded "사용자 승인이 필요한 항목"
```

이 스크립트는 commit이나 push를 실행하지 않는다. 미승인 문헌 후보, 원자료,
음성, TextGrid가 자동으로 GitHub에 올라가는 것을 막기 위한 의도적인 경계다.

## 학교 계정에서 첫 재개 순서

1. 같은 프로젝트 루트를 연다. 다른 컴퓨터라면 승인된 최신 Git commit을 받는다.
2. `AGENTS.md`와 `docs/environment/PROJECT_START_HERE.md`를 읽는다.
3. 이 문서와 `docs/environment/CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md`를 읽는다.
4. 체크포인트 마지막 행과 실제 Git 상태를 대조한다.

```powershell
Get-Content ".\docs\environment\CONTINUITY_CHECKPOINTS.jsonl" -Tail 1
git status --short --branch
git log -3 --oneline
```

5. 마지막 행의 `next_step`을 수행하기 전에 관련 manifest·감사 결과·사용자 승인
   상태를 다시 확인한다.

## 현재 인수인계 요약 — 2026-08-25

- 2020–2025 r3 MFA·6-tier·동반표·독립 QC는 완료 상태이며 다시 실행하지 않는다.
- 현재 전면 작업은 일곱 음운현상의 문헌 검토와 stage2 연구 설계다.
- D2-P0 문헌 후보·다음 검토 패키지는 local candidate이며 정본 반영 전이다.
- KOINA·wav2vec2는 PV-B의 소량 보조층이다. 대량 실행이나 자동 실현 판정은 하지
  않는다.
- 개강 전 권장 구현은 KOINA 재현성 보강, wav2vec2 소표본 실행 골격, 공통
  sidecar 감사기까지다.
- 현재 Git branch는 `agent/harden-pre-bulk-pipelines`이며, 이 문서 작성 직전
  HEAD는 `978ddfd8e7f76c542eed3f006ad943de563110bb`였다. 새 계정에서는 실제 값을
  다시 확인한다.
- 자동 commit/push는 없다. 다른 컴퓨터에서도 이어가려면 공개-safe allowlist를
  검토해 사람이 commit/push해야 한다.

## 학교 계정에 붙일 최소 프롬프트

```text
현재 열린 프로젝트 저장소 루트의 작업을 이어가자.
먼저 AGENTS.md, docs/environment/PROJECT_START_HERE.md,
docs/environment/ACCOUNT_TRANSITION_CONTINUITY.md,
docs/environment/CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md를 읽어라.
그다음 docs/environment/CONTINUITY_CHECKPOINTS.jsonl의 마지막 행과 실제
git status/log를 대조하라. 채팅 기억보다 저장소 문서·manifest·Git commit을
우선하고, 미승인 문헌 후보나 KOINA/wav2vec2 결과를 정본 판정으로 승격하지 마라.
현재 상태, 미결정 사항, 다음 한 단계만 먼저 보고하라.
```

## 한계

- 아직 commit하지 않은 로컬 변경은 다른 컴퓨터에 자동으로 복제되지 않는다.
- 계정별 채팅, memory, 연결 권한, 예약 작업의 이전 여부를 이 기록이 보장하지
  않는다.
- 따라서 중요한 안전 정지점에서는 checkpoint 생성 후 public-safe diff를 검토하고
  별도 승인된 commit/push를 하는 것이 최종 보존 단계다.
