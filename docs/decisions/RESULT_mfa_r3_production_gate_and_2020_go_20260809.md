# r3 production Gate 채택과 2020 실행 GO 결과

날짜: 2026-08-09 KST

## 연구자 승인

연구자 `ari30`은 다음 문장을 명시 승인했다.

> 체크리스트 1–7 결과를 확인했다. common_pron_mfa_r3_20260809의 production release Gate 개방과 2020 안전 본체 782,715발화의 r3 preflight 진행을 승인한다. 승인자 ari30.

원문·승인자·범위는
`outputs/reviews/common_pron_r3_production_gate_20260809/RESEARCHER_APPROVAL_PRODUCTION_GATE.json`에
불변 기록했다. 이 승인은 2020 preflight와 채택된 r3 release 사용을 허용하지만,
발음의 실제 실현 여부를 자동 판정하거나 follow-up 발화를 폐기하는 승인이 아니다.

## Gate와 검사 결과

- production Gate가 허용하는 release는
  `common_pron_mfa_r3_20260809` 하나다.
- `common_pron_mfa_r2_20260728`은 계속 차단하며 기존 r2 DB·TextGrid는 읽기 전용
  비교·회귀 증거로만 보존한다.
- 정책 감사 v2는 Stage 19 실제 연도 routing summary, v3.1 범위, 두 연구자 승인,
  Gate 증거, r3 실행 경로의 legacy token을 검사해 `failures=0`, `gaps=0`,
  `production_allowed=true`로 통과했다.
- 2020 final preflight는 18/18 `GO`다. PowerShell safety/runtime 대상 65개와
  Python 전체 suite 542시험이 통과했다. 검사한 실행 코드 commit은
  `c48a8016cbe308b8602abfb2a5f7b25fb41a45bc`다.
- 2020 입력은 exact-ID 782,715발화이며 alignment contract ID는
  `3eff5ae34eb1015c05532140162636609099f1fd1203f561cc06d837039d8e8a`다.
- preflight 관측 D: 여유 공간은 약 194.869 GiB로, 계산된 필요량 약
  53.726 GiB보다 크다.

정본 보고서는 다음 두 파일이다.

- `outputs/reports/AUDIT_mfa_r3_full_realign_policy_v2_gate_adopted_20260809.json`
- `outputs/reports/PREFLIGHT_mfa_r3_runner_2020_gate_adopted_go_20260809.json`

## 현재 상태와 실행 경계

현재 상태는 `ready_not_started`다. 이 결과를 기록한 시점에는 r3 production
corpus, MFA DB, TextGrid를 생성하지 않았다. 장시간 명령을 시작하면 runner가
`D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809` 아래에 release 전용 corpus,
contract, temp/DB, log, marker, lock을 만든다.

처음에는 원 WAV를 수정하지 않는 hardlink와 생성 LAB를 exact-ID 순서로
물질화한다. 중단 시 `.building` 계약, temp, DB를 삭제하지 않고 같은 명령을
한 번 다시 실행한다. 동시에 두 runner를 실행하거나 legacy `D:\mfa_tmp` DB를
재사용하지 않는다. 본 명령의 완료 기준은 `ALIGN_DONE_2020.json`이며, 6-tier
TextGrid와 동반표 export는 보존 DB 완료 뒤 별도 단계로 진행한다.

## 방법론적 해석

이 Gate는 동일한 r3 사전·acoustic phone inventory·실행 계약으로 2020 안전
본체를 강제정렬할 수 있다는 인프라 승인이다. `phones_mfa`는 강제정렬 입력과
분절 결과이며 실제 음성 실현의 정답이 아니다. 연구자는 이후 검색으로 선별한
WAV·TextGrid를 직접 보고 실현 여부를 판단한다. follow-up 718,364발화는 정확
ID와 사유를 유지한 별도 shard로 보존하며 안전 본체 완료와 혼동하지 않는다.
