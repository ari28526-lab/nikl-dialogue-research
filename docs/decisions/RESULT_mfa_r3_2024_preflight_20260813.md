# 2024 r3 전수 MFA 진입 전 결과

기록일: 2026-08-13 KST

대상 release: `common_pron_mfa_r3_20260809`

상태: `2023→2024 Gate passed_ready_for_researcher_start`

## 연구 목적과 범위

이 단계는 2024년 대화 코퍼스를 2020–2023년과 동일한 r3 공통발음사전·음향모델·G2P provenance·실행 정책으로 새로 강제 정렬하기 위한 입력 인프라를 동결한다. MFA phone은 실제 실현 판정값이 아니라 강제 정렬 결과이며, 실제 음운 현상의 실현 여부는 이후 연구자가 WAV와 TextGrid를 직접 검토한다.

이 단계에서는 원 WAV·원 JSON·원 CSV, 2020–2023 r3 DB와 최종 6-tier TextGrid를 수정하지 않았고 2024 MFA와 TextGrid 생성도 시작하지 않았다.

## 조합검색·CSV 복구와 전수 결과

- 2024 `morph_search.v3` 33/33 shard와 연간 7개 gzip 표가 성공했다.
- source 발화는 728,257개이며 동결 source contract가 `passed`이다.
- CSV 안의 합법적인 따옴표 내부 줄바꿈은 물리적 줄 수가 아니라 `csv.reader`의 논리 레코드로 처리하도록 수정했다.
- Bareun 표면형의 문자 `+`와 형태소 구분자 `+`가 충돌하는 경우는 `/POS` 종결자 기반 무손실 parser로 수정했다.
- 2020–2025 CSV 5,103,356행 전수 감사에서 해당 충돌은 2024년 1건, 2025년 1건뿐이었고 둘 다 무손실로 설명됐다. 2020–2023에는 해당 사례가 0건이므로 기존 완성본을 재실행하지 않았다.
- 실패 당시 raw·보고서는 `archive_failed`에 보존했고, 성공 shard와 체크포인트는 재사용했다.

관련 사건 기록:

- `INCIDENT_morph_search_2024_embedded_newline_20260813.md`
- `INCIDENT_bareun_literal_plus_delimiter_collision_20260813.md`

## 2024 입력·연구 DB·정렬 계약

- source: 728,257
- pronunciation-safe: 595,743
- pronunciation follow-up: 132,514
- safe 집합에 적용된 승인 전 MFA 제외: 1,339
- 최종 r3 MFA 예정 입력: 594,404
- source WAV 누락: 0
- corpus extra WAV: 24 (입력으로 임의 채택하지 않고 inventory에만 보존)
- 발음 연구 DB: 발화 728,257, occurrence 5,141,540, 공통 유형 catalog 881,237
- 연구 DB 독립 감사: `passed`
- alignment contract ID: `d86f490de924cdf92f2fcb16316046558be65f9446ffa0cf325fc661e4b20f9f`
- alignment contract 독립 감사: `passed_independent_identity_audit_pending_runner_and_release_gate`

정렬 계약은 다음을 함께 고정한다.

- 공통발음 release와 pronunciation contract
- 2024 exact-ID 입력·follow-up·제외 inventory
- MFA dictionary SHA-256
- Korean MFA acoustic model SHA-256
- Jamo G2P model provenance SHA-256
- Python·MFA·Pynini runtime identity

따라서 2020–2025년은 연도별 데이터 수와 기술적 제외 수가 다르더라도 같은 발음·phone·모델·실행 기준을 사용했다는 방법론적 근거를 유지한다.

## 최종 runner preflight와 전환 Gate

2024 runner `-PreflightOnly` 결과:

- status: `go`
- 실패 검사: 0
- 예상 입력: 594,404
- 보수적 필요 공간: 44.409 GiB
- 관측 D: 여유 공간: 약 106.9 GiB
- PowerShell safety: 69개 파일 통과
- Windows PowerShell 5.1 runtime compatibility: 69개 script 통과
- Python: 564 tests 통과

2023→2024 Gate는 8/8 항목을 통과했다. 이 Gate는 다음을 확인했다.

- 2023 `ALIGN_DONE` marker, 보존 DB와 독립 QC SHA가 그대로임
- 2023 TextGrid 494,228개 및 표본 semantic/byte 24/24 QC가 동결됨
- 2024 입력·alignment·연구 DB·runner preflight가 서로 같은 contract ID를 참조함
- 2024 완료 marker와 DB가 아직 없어 중복 실행이 아님

## 다음 실행

사용자는 한 개의 일반 PowerShell 창에서 다음 장시간 명령만 실행한다. 동시에 두 번째 runner를 시작하지 않는다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_year_safe_body.ps1" `
  -Year 2024 -NumJobs 4
```

실패 시 corpus·temp·DB를 보존하고 원인에 해당하는 checkpoint/shard만 수정한다. 2020–2023 또는 2024 전체를 근거 없이 처음부터 반복하지 않는다.

## 근거 파일

- `outputs/reports/SOURCE_CONTRACT_morph_search_v3_20260801_2024.json`
- `outputs/reports/AUDIT_mfa_r3_year_input_contract_2024_20260813.json`
- `outputs/reports/AUDIT_mfa_r3_alignment_contract_2024_20260809.json`
- `outputs/reports/GATE_mfa_r3_2023_TO_2024_20260813.json`
- `work/mfa_r3_preflight/PREFLIGHT_common_pron_mfa_r3_20260809_2024.json`
- `D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\05_research_database\2024\AUDIT_RESEARCH_DATABASE_2024.json`
