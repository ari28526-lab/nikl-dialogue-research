# 연구 DB v1 recovery D9 통제 beam 재시도 Gate

기록일: 2026-08-17 KST

## 결론

D8에서 원자료 identity와 음성 길이가 확인된 계속 미정렬 19건만 별도
`D9_CONTROLLED_BEAM_RETRY_0001` 실행 후보로 동결했다. D5와 같은 입력을 기본
설정으로 반복하지 않고, MFA가 정렬 0건 오류에서 안내하는 한 단계 확장값을 따라
다음 한 번의 통제 비교만 허용하도록 설계했다.

| 항목 | D5 | D9 고정값 |
|---|---:|---:|
| beam | 10 (MFA 기본값) | 100 |
| retry beam | 40 (MFA 기본값) | 400 |
| 입력 | alignment-missing 30건 | D8 identity 확인 잔여 19건 |
| 자동 병합 | 없음 | 없음 |

D9 후보의 연도별 수는 2020 2, 2021 5, 2022 3, 2023 5, 2024 3, 2025
1건이다. 4개 겹침 표지 발화는 정렬 인프라 후보에 남지만, 성공하더라도 단일 화자
음향분석에 자동 포함하지 않는다.

## 하지 않는 일

- 0.1초 미만 25건은 D9에 넣지 않는다.
- 2020–2025 전체연도나 D5의 성공 11건을 다시 정렬하지 않는다.
- 음향모델, 공통발음 r3 사전, G2P provenance, LAB를 바꾸지 않는다.
- 성공 TextGrid를 r3 본체, 연구용 6-tier 또는 DB v1에 자동 병합하지 않는다.
- 실패하면 같은 계약으로 두 번째 자동 재실행을 하지 않는다.

창 종료처럼 정상 완료 marker가 생기기 전 끊긴 실행은 동일 temp·계약을 확인한 뒤
재개할 수 있다. 반대로 MFA가 명시적으로 실패 marker를 남기면 새 계약 없이는 다시
실행할 수 없다. 완전한 TextGrid 19개가 이미 존재하면 재실행하지 않고 감사만 한다.

## 동결 계약

정본 package:

```text
outputs/releases/nikl_dialogue_research_db_v1_recovery_d9_gate_20260817
```

주요 해시:

```text
D9_RUN_SHARD.json       73b65ca9892133da3c84bb71f9d2a17521b2314c682006b6a66f367921563157
D9_MFA_CONFIG.json      a9b184843a8e3c1763f195c910f25c946313068887e46928babfd52d53502923
D9_EXECUTION_CONTRACT   fbfa88151de78b580a7987f159eceb7fdb689c199409cffd778021dfb840a830
```

예정 D: 격리 출력은 다음이며 현재는 존재하지 않는다.

```text
D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D9_CONTROLLED_BEAM_RETRY_0001
```

## 검증 결과와 현재 Gate

- `mfa align` 설치본의 `PretrainedAligner.parse_parameters`가 동결 JSON을 실제
  `beam=100`, `retry_beam=400`으로 읽는 것을 확인했다.
- Windows PowerShell 5.1 safety/runtime 회귀검사 72개 스크립트가 통과했다.
- 실제 `-PreflightOnly`는 19건, 위 연도별 수, 모델·사전·LAB/WAV 해시,
  D: 여유 63.4 GiB를 확인하고 `passed_gate_closed`로 끝났다.
- preflight는 D: 파일 복사와 MFA 실행을 모두 0건으로 유지했다.

현재는 연구자 승인 전이다. 승인은 run shard·설정·execution contract 세 해시,
19건, 100/400, 단 한 번 실행, 무병합 조건에 결속한다. 승인 후에도 결과는
`words`·`phones` tier와 exact-ID coverage를 감사한 뒤 별도 채택 Gate에서만
6-tier/DB v1에 반영할 수 있다.

## 논문 방법론에 남길 요지

기본 정렬에서 결과가 생성되지 않은 발화를 무제한 반복하지 않았다. 먼저 원 JSON,
분석 CSV, 전사와 복수 음원 사본의 exact-ID·해시·길이를 대조하고, 충분한 음성이
있는 19건만 동일 모델·사전·전사를 유지한 채 탐색 폭을 10/40에서 100/400으로
한 차례 확장했다. 0.1초 미만 원 조각 25건은 알고리즘 실패와 분리해 기술 제외로
기록했으며, 재시도 결과 역시 본체에 자동 편입하지 않았다.
