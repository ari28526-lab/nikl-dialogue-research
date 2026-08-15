# 연구 DB v1 recovery D5 실행 후보 축소와 승인 Gate

기록일: 2026-08-15 KST

## 결론

D0–D4의 첫 진단 후보 55건을 실제 MFA에 그대로 반복 투입하지 않았다. WAV
헤더·지속시간, LAB UTF-8 코드포인트, LAB 바이트 해시, 고정 r3 공통사전 어휘
coverage를 전수 감사한 뒤 다음처럼 분리했다.

| 처리 | 건수 | 근거 |
|---|---:|---|
| D5 fresh subset MFA 후보 | 30 | 과거 `mfa_alignment_missing`, WAV 0.7–6.853초, LAB 정상, 공통사전 OOV 0 |
| 동일 입력 MFA 금지·원 음원 길이 회수 | 25 | 과거 `mfa_feature_generation_failed`이며 현재 WAV가 모두 0.01–0.099875초 |

25건은 연구 제외나 발음 실현 판정이 아니다. 현재 잘못 짧은 음원으로 같은 MFA를
반복하지 않고, 원 음원 segment/duration 회수 대상으로 계속 보존한다. 실제 MFA
후보 30건은 각 연도 5건이며 한 개의 exact-ID shard
`D5_ALIGNMENT_DIAGNOSTIC_0001`로 고정했다.

## 입력과 방법론 일관성

- LAB 55건은 모두 정상 UTF-8 한글이다. 제한 셸의 화면 표시가 깨져 보였으나
  실제 바이트와 Unicode code point를 검사해 파일 손상과 구분했다.
- D5 실행 30건의 LAB 어휘 214유형은 고정 공통사전에서 모두 확인됐다.
- 사전·acoustic model·G2P provenance는 2020–2025 본체와 같은
  `common_pron_mfa_r3_20260809` 계약의 SHA로 고정했다.
- 원 WAV/LAB는 읽기 전용이며 D5 전용 namespace에는 hardlink가 아닌 바이트
  복사본을 만든다. 따라서 D5 MFA가 복사본을 다루더라도 원본 inode를 공유하지
  않는다.
- 결과는 진단 자료다. r3 본체, 연구 6-tier, DB v1에는 자동 병합하지 않는다.
  병합 또는 추가 회수는 결과 검토 뒤 별도 exact-ID Gate를 거친다.

## Gate 자산

정본 package:

```text
outputs/releases/nikl_dialogue_research_db_v1_recovery_d5_gate_20260815
```

주요 파일:

- `D5_INPUT_AUDIT.csv`: 55건 WAV/LAB·duration·사전 coverage 전수 감사
- `D5_NO_RUN_AUDIO_DURATION_RECOVERY.csv`: 25건 길이 회수 장부
- `D5_RUN_SHARD.csv.gz`: MFA 실행 후보 30건
- `D5_EXECUTION_CONTRACT.json`: 출력 root·모델·실행 범위 고정
- `RESEARCHER_APPROVAL_PENDING.json`: 승인 후보이며 승인 자체가 아님
- `OUTPUT_MANIFEST.json`: package와 실행 구현 SHA

예정 출력 root는 아래와 같지만 현재 존재하지 않는다.

```text
D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D5_ALIGNMENT_DIAGNOSTIC_0001
```

## 안전장치

`run_db_v1_recovery_d5_shard.ps1`은 다음을 강제한다.

1. 승인 없이 실행하면 D: 파일 생성 전에 fail-closed한다.
2. 승인은 실행 계약 SHA, shard SHA, 30건, 출력 root, 자동 병합 금지를 함께
   묶어야 한다.
3. `.partial` contract가 같은 경우만 복사를 재개한다.
4. WAV/LAB는 복사 전후 SHA를 확인하고 원본 fingerprint도 다시 확인한다.
5. MFA 실패 시 temp·DB·로그를 삭제하지 않는다.
6. 성공 뒤에도 TextGrid present/missing을 별도 감사하고 자동 병합하지 않는다.

PowerShell 5.1 safety/runtime 71개 파일과 관련 Python 단위검사 7개가 통과했다.
실자료 읽기 전용 preflight 결과는 다음과 같다.

```text
outputs/reports/PREFLIGHT_db_v1_recovery_D5_20260815.json
status = passed_gate_closed
rows = 30
files_materialized_by_this_preflight = false
mfa_run_by_this_preflight = false
```

## 현재 정지점과 다음 승인

현재 D5 출력 root·partial root는 모두 없고 활성 MFA도 0이다. 다음 승인은 단순히
“55건 재실행”이 아니라 아래 범위를 이해한 승인이어야 한다.

> `D5_ALIGNMENT_DIAGNOSTIC_0001`의 alignment-missing 30건을 격리된 복사본으로
> MFA 진단 실행하는 것을 승인한다. 0.1초 미만 feature-failure 25건은 같은 입력으로
> 재실행하지 않고 원 음원 길이 회수 장부에 보존하며, 결과의 r3 본체·DB v1 자동
> 병합은 승인하지 않는다. 승인자 ari30.

이 승인이 기록된 뒤에만 approved contract를 만들고 장시간 명령을 제공한다.

## 2026-08-15 연구자 승인 기록

연구자 `ari30`이 위 문구 그대로 승인했다. 승인은 다음 파일에 기록했으며
execution contract SHA, run shard SHA, 30건, 격리 출력 root, 원본·r3 본체 변경
금지, 자동 병합 금지를 함께 고정한다.

```text
outputs/reviews/db_v1_recovery_d5_20260815/RESEARCHER_APPROVAL.json
```

이 승인은 D5 30건 진단 실행만 허용한다. 25건의 현재 짧은 음원을 같은 입력으로
다시 MFA하거나, D5 결과를 r3 본체·DB v1에 자동 병합하는 권한은 포함하지 않는다.

승인 결합 Windows PowerShell 5.1 preflight는 `passed_ready_to_execute`,
`approval_verified=true`로 통과했다. 이 검사 뒤에도 D5 output/partial root는 없고
활성 MFA는 0이므로, 실제 상태 변경은 연구자가 다음 실행 명령을 시작할 때 발생한다.
