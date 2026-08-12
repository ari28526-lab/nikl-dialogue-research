# 2023 r3 전수 MFA 직전 입력·연구 DB·전환 Gate 결과

작성일: 2026-08-12 KST

상태: `passed_ready_for_researcher_start`

대상 release: `common_pron_mfa_r3_20260809`

## 결론

2020–2022의 완료 산출물은 다시 계산하거나 수정하지 않았다. 2022 완료 marker,
보존 DB와 독립 QC SHA를 동결한 상태에서 2023년만 준비했으며, 2023 r3 전수 MFA
입력은 exact-ID 494,580발화로 확정됐다. 형태소 조합검색 7표, 발음 연구 DB,
연도 입력 계약, 정렬 계약, 실행 환경·용량 preflight와 2022→2023 전환 Gate가
모두 통과했다. 2023 corpus·MFA DB·TextGrid는 아직 생성하지 않았다.

다음 단일 작업은 연구자가 장시간 PowerShell에서 2023 runner를 한 번 시작하는
것이다. 이 명령은 2020–2022를 재실행하지 않으며 동시 중복 실행을 금지한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_year_safe_body.ps1" `
  -Year 2023 -NumJobs 4
```

## 입력 범위와 제외 회계

- 동결 source 발화: 677,262
- 공통 발음 r3 pronunciation-safe: 582,389
- 발음 후속 shard: 94,873
- 연구자가 이미 승인한 2023 기술 범주 후보: 103,930
- 위 승인 집합 중 pronunciation-safe와 교차해 본체에서 실제 제외: 87,809
- 나머지 승인 16,121은 이미 발음 후속 shard에 있으므로 이중 제외하지 않음
- 최종 MFA 입력: 494,580
- 과거 r2 post-MFA 재진입: 0 — 2023 r2 생산 정렬이 없으므로 재사용하지 않음

2023 WAV source snapshot은 677,397개다. source 발화 중 WAV 미대응 923건은 모두
pronunciation follow-up 또는 승인 제외 범위에 있어 최종 494,580 입력의 WAV
결손은 0이다. source 밖 WAV 1,058개는 존재하지만 자동 포함하지 않았다. 원 WAV,
원 CSV와 JSON은 읽기 전용으로 유지했다.

연도 입력 계약 ID는
`04d82d422460341ea853fa06767237bbfb823896814381caacc2c7fb5134bfa0`, 정렬
계약 ID는
`2b16d0309aa11731b6d1e520850c359aa67783004fbd5dea80758b416a7d61eb`다.
MFA 입력 exact-ID 파일 SHA-256은
`f065ccfd36d446b2f847ef4be5741a5eb9172a077fb4bed57956780bc1d0b16d`다.

## 형태소 조합검색 CSV와 발음 연구 DB

2023 발음 연구 DB를 처음 실행했을 때, 기존 `-PreflightOnly`가 당해 연도
`morph_search.v3` shard의 부재를 발견하지 못하고 실제 builder에서 안전 중단됐다.
이때 MFA·corpus·DB·TextGrid는 시작하지 않았고 원자료 변경도 없었다. 이 공백을
수정해 연구 DB preflight가 다음을 실행 전에 강제하도록 했다.

1. 당해 `YEAR_PROGRESS.json`과 `YEAR_MANIFEST.json`의 success 상태
2. 기대 shard 수와 실제 shard manifest 수의 일치
3. 모든 `SHARD_MANIFEST.json`의 success 상태

동시에 형태소 연도 wrapper에 `-PreflightOnly`를 추가하고, Windows PowerShell
5.1에서 D: 여유가 0으로 오인되지 않도록 `DriveInfo` 기반 검사로 통일했다. 이
보강은 2024·2025에도 같은 누락이 반복되는 것을 막는다.

이후 2023 형태소 조합검색 20/20 shard를 완료했다. 주요 표는 발화 master
677,262행, 어절 token 3,586,726행, 형태소 token 6,610,494행, 형태소 unit
9,802,117행, 형태소 경계 5,933,232행, 철자 어절 token 3,592,988행, 기호 읽기
262,115행이다. 중복 발화 0, 기호 coverage 일치, 결정적 gzip 검사를 통과했다.

발음 연구 DB는 20/20 checkpoint를 완료해 발화 677,262행과 참조 어절 occurrence
3,629,250행을 만들었다. scope는 MFA 본체 494,580, 발음 후속 94,873, pre-MFA
제외 87,809로 완전 분할된다. post-MFA 결합 키는
`(year, utt_id, reference_eojeol_idx)`이며 비어 있지 않은 LAB의 미등록 발음 유형은
0이다. 이 DB는 규칙·사전·형태소 근거와 향후 MFA phone/TextGrid를 같은 발화·어절
좌표에 연결하기 위한 연구용 정규화층이며, 원 형태소 CSV를 대체하지 않는다.

## 실행 전 검증과 용량

장시간 runner의 실제 `-PreflightOnly`는 다음을 통과했다.

- PowerShell 안전검사 68개
- Windows PowerShell 5.1 runtime 호환검사 68개
- Python 전체 시험 558개
- r3 acoustic/dictionary/G2P SHA와 release Gate
- exact-ID 입력·follow-up·제외 파일 SHA
- 발음 연구 DB 독립 감사
- active lock 없음, legacy 산출물 재사용 없음
- D: 관측 여유 72.174 GiB, 보수적 필요량 39.470 GiB

preflight 보고서는
`work/mfa_r3_preflight/PREFLIGHT_common_pron_mfa_r3_20260809_2023.json`이고
SHA-256은
`8e12da362e2b6384f517a2525340799e707996f470cc52b4855f32b1a844f24c`다.

## 전환 Gate와 재개 원칙

`outputs/reports/GATE_mfa_r3_2022_TO_2023_20260812.json`은 8/8 검사를 통과했다.
보고서 SHA-256은
`f5268010fa72cf4f09f7ff6a12ce4a1a2242731e8afef63c3f9056801e9132d8`다.
Gate는 2022 정렬 marker·DB·QC가 그대로인지, 2023 입력·정렬·연구 DB·runner
preflight가 통과했는지, 2023 marker와 DB가 아직 없는지를 동시에 확인한다.

장시간 실행이 중단되거나 post-MFA 미정렬이 생겨도 2023 전체를 임의 삭제하거나
2020–2022로 돌아가지 않는다. corpus·temp·DB를 보존하고 exact-ID checkpoint와
후속 shard로 재개한다. 새로운 승인 필요성이 생기기 전에는 기존 103,930건의
승인을 반복하지 않는다.

## 논문 방법론에 남길 핵심

연도별 정렬은 동일한 r3 발음 release와 동결 acoustic/dictionary/G2P SHA를
사용하되, 당해 발화의 pronunciation-safe 집합과 명시 승인된 기술 제외의 교집합만
본체 입력에서 제외했다. 형태소 조합검색 CSV와 발음 연구 DB를 MFA 전에 완성해
표기·형태소·규칙/사전 발음·후속 MFA phone을 안정된 발화/어절 키로 연결했다.
연도 전환은 직전 연도 marker·보존 DB·독립 QC SHA와 다음 연도 입력·정렬·연구 DB
감사를 결속한 fail-closed Gate로 수행했다. 따라서 연도별 자료 규모와 기술 제외는
달라도 phone 기준, release, 처리 순서와 검증 기준은 2020–2025에 동일하다.
