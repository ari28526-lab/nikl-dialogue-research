# 연구 DB v1 recovery D0–D4 완료와 pre-MFA 정지

최종 갱신: 2026-08-15 KST

## 결론

2020–2025 r3 안전 본체 밖에 보존한 817,310발화를 이유·연도·세션·exact ID로
완전 회계하고, 기술적 회수 가능성 감사와 발음 유형 축약, 첫 진단 shard를
완료했다. 기존 r3 코퍼스·DB·6-tier TextGrid·원 WAV는 모두 읽기 전용으로
유지했다. recovery 파일 생성과 MFA는 수행하지 않았고, 검증된 Windows
PowerShell 5.1 preflight가 `passed_gate_closed`로 끝나는 지점에서 정지했다.

정본 package는 다음과 같다.

```text
outputs/releases/nikl_dialogue_research_db_v1_recovery_d0_d4_20260815
```

## D0 — 입력·저장공간·불변성 계약

`D0_INPUT_CONTRACT.json`은 A–C `OUTPUT_MANIFEST.json`, base release, QA,
발음 type catalog, 2024–2025 temp 정리 결과를 SHA-256으로 결속한다. D:는
계속 active 정본 저장소이고 E:는 별도 승인 뒤의 read-only archive 역할만
가진다. 계약 시 D: 여유는 64.184 GiB였다.

다음 불변성을 명시했다.

- r3 안전 본체 4,286,046발화, 보존 DB, 6-tier TextGrid를 수정하지 않는다.
- recovery는 whole-year 재실행이 아니라 exact-ID append-only shard로 한다.
- 사전·규칙·G2P·MFA phone은 발음 참고 근거이지 실제 실현 판정이 아니다.
- 모호한 발음이나 음원 identity를 자동 승인하지 않는다.
- `D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809`는 아직 만들지 않았다.

과거 계획 문서의 단계 글자와 충돌하지 않도록 현재 `D0–D4`는
**이유별 recovery 계획과 pre-execution Gate**로 고정했다. 표적 추출·수동
overlay·세션 JSON은 이 회계가 끝난 다음 단계다.

## D1 — 817,310건 이유별 recovery 장부

`D1_recovery_ledger/YYYY_recovery_routing.csv.gz`에 각 발화를 한 번만 기록했다.
주요 열은 `year`, `utt_id`, `session_id`, `source_csv`, `primary_status`,
`reason_codes_json`, `recovery_family`, `recovery_shard_id`, `priority`,
`action`, 두 r3 계약 ID다. `D1_SHARD_MANIFEST.json`은 이를 43개 routing
단위로 축약하며, 이는 자동 승인이나 최종 제외표가 아니다.

| 상태 | 발화 수 |
|---|---:|
| pre-MFA 기술 후속 | 95,860 |
| post-MFA 기술 후속 | 3,086 |
| 발음 후속 | 718,364 |
| 합계 | 817,310 |

기술 사유의 exact count는 다음과 같다.

| 사유 | 발화 수 |
|---|---:|
| `audio_pairing_unresolved` | 95,798 |
| `text_duration_impossible` | 60 |
| `audio_unusable` | 2 |
| `mfa_alignment_missing` | 3,061 |
| `mfa_feature_generation_failed` | 25 |

## D2 — 기술 후속 98,946건 회수 가능성 감사

각 행을 frozen search-master CSV에 다시 연결하고, 연도 input contract의 WAV
root와 post-MFA r3 corpus WAV/LAB를 읽기 전용으로 확인했다. 같은 파일명이
있다는 사실만으로 음성 identity가 맞다고 판단하지 않았다.

| 회수 가능성 분류 | 발화 수 | 의미 |
|---|---:|---|
| `requires_audio_identity_review` | 93,361 | exact-name WAV는 있으나 내용 identity 검토 필요 |
| `requires_session_audio_remap` | 2,437 | exact-name WAV가 없어 세션 한정 remap 필요 |
| `requires_timing_metadata_review` | 60 | WAV는 있으나 CSV 시간정보 조정 필요 |
| `preserve_audio_unusable_research_decision` | 2 | 음원 불량 결정을 자동 복구하지 않음 |
| `ready_for_alignment_diagnostic` | 3,061 | 기존 r3 WAV/LAB 쌍으로 제한 진단 가능 |
| `ready_for_feature_failure_diagnostic` | 25 | 기존 r3 WAV/LAB 쌍으로 feature 진단 가능 |

2023의 `audio_pairing_unresolved` 87,808건은 다른 연도와 합쳐 자동 처리하지
않고, 세션 topology 문제로 별도 routing한다. D2는 회수 가능성 감사이며 실제
WAV remap·복사·교체는 0건이다.

## D3 — 발음 유형 축약표

발음 후속 718,364발화의 `hold/policy/unknown` token을 token-role·연도 빈도로
축약하고 frozen `pronunciation_type_catalog.csv.gz`의 철자 Roman, 규칙 발음,
사전 발음, 계획 후보와 release 상태를 연결했다.

- role-token 행: 85,433
- type catalog 연결: 85,433/85,433
- `zero_fallback_hold`: 80,912유형
- `dictionary_evidence_review`: 4,486유형
- `policy_decision_required`: 35유형
- 자동 발음 선택·실현 판정: 0건

정본은 `D3_pronunciation_types/pronunciation_type_summary.csv.gz`, 빠른 검토용은
빈도 상위 1,000행 `PRIORITY_TOP_1000.csv.gz`다. 사전 정보가 있다는 이유로
그 발음을 alignment 입력이나 실제 실현값으로 자동 채택하지 않는다.

## D4 — 첫 실행 shard와 정지 Gate

`D4_POST_MFA_DIAGNOSTIC_0001`은 generic pilot 반복이 아니라 recovery 경로의
표적 회귀검사다.

- `mfa_feature_generation_failed` 25건 전수
- `mfa_alignment_missing`에서 연도별 서로 다른 세션 5건씩, 합계 30건
- 전체 55건, WAV 약 2.62 MiB, LAB 2,589 bytes
- 보수적 working budget 4 GiB, 실행 전 D: 최소 여유 20 GiB

`FIRST_SHARD.csv.gz`에는 기존 materialized WAV/LAB의 정확한 경로·크기와 선택
규칙을 기록했다. `PRE_MFA_GATE.json` 상태는
`hold_before_materialization_and_mfa`다.

검증한 읽기 전용 명령은 다음과 같다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_db_v1_recovery_first_shard.ps1" `
  -PreflightOnly
```

결과는 `outputs/reports/PREFLIGHT_db_v1_recovery_D4_20260815.json`의
`passed_gate_closed`다. 별도 scope-bound 연구자 승인 계약 없이 옵션을 빼면
fail-closed한다. D0–D4 구현은 승인 계약을 검증하더라도 이 단계에서 실제
materializer나 MFA를 호출하지 않도록 정지한다.

## 독립 감사와 연구 방법 서술

별도 감사기가 A–C 장부와 D1의 817,310 exact ID를 다시 전수 비교했고, 정렬
본체 ID 혼입·누락·중복·사유 변형이 모두 0임을 확인했다. D2의 현재 파일
존재·크기, D3 token 빈도, D4 25+30 선택 규칙도 독립 재계산했다.

논문 방법·각주에는 다음처럼 서술할 수 있다.

> 6개년 강제정렬 본체는 동일한 동결 r3 발음·음향·phone·TextGrid 계약으로
> 보존하고, 미처리 발화는 원인별 exact-ID 장부로 분리하였다. 기술적 후속은
> 원 CSV와 WAV/LAB 존재·크기 및 세션 결속을 읽기 전용 감사해 회수 경로를
> 분류했으며, 발음 후속은 사전·규칙·G2P 정보를 참고 근거로만 유형 축약하였다.
> 자동 발음 실현 판정이나 filename-only 음원 재매핑은 하지 않았고, 별도 승인된
> 소규모 진단 shard 전 단계에서 본체와 후속 처리를 분리하였다.

## 다음 Gate

다음 행동은 D2·D3 요약과 55건 D4 shard를 검토한 뒤, 그 exact shard에만
적용되는 별도 승인 계약을 만드는 것이다. 그 전에는 사용자가 실행할 대량
PowerShell 명령이 없고, r3 전 연도 재정렬도 하지 않는다.
