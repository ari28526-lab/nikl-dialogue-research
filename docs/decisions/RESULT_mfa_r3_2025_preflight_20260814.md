# 2025 r3 전수 MFA 진입 전 최종 결과

기록일: 2026-08-14 KST

상태: `2024→2025 Gate passed_ready_for_researcher_start`

## 목적

2025를 2020–2024와 동일한 공통발음사전·음향모델·phone inventory·runtime 기준으로
새로 정렬하기 전에 검색 source, 발음 라우팅, 기술 제외, WAV와 연구 DB를 exact-ID와
SHA-256으로 결속했다. 이 단계는 실제 음운 실현을 판정하지 않으며 MFA phone은 강제
정렬 결과라는 기존 연구 해석을 유지한다.

## 동결된 회계

- source 발화: 587,121
- pronunciation-safe: 461,643
- pronunciation follow-up: 125,478
- 승인된 pre-MFA 기술 제외 전체: 4,033
- safe body와 교차해 실제 입력에서 제외: 3,230
- 최종 r3 MFA 입력: 458,413
- WAV snapshot: 587,174
- source WAV 누락: 0
- source 밖 WAV: 53 (보존하되 자동 선택하지 않음)
- 연구 DB: 587,121발화, 4,888,815 occurrence, 공통 유형 881,237

승인 기술 제외 4,033건 중 803건은 이미 발음 follow-up에 있으므로 다시 빼지 않았다.
따라서 `461,643 - 3,230 = 458,413`이며 후속 발음과 기술 제외를 중복 회계하지 않는다.

## 계약·감사 결과

- WAV corpus contract ID:
  `c1e3fad1634b488e496b3bcd6f276ca99e96a186db65e50538cfd470ceed3991`
- year input contract ID:
  `57e6ca0b42a6d2d5daa49505a63295e1a15016dde39d1ee7f99cbca28dada64a`
- alignment contract ID:
  `1b739d22d56c9ce91ce17486b89355558e17acc8364f88bb68a27acd16ba5f35`
- year input independent audit: passed
- research DB independent audit: passed
- alignment identity audit: passed
- runner preflight: GO, failed checks 0
- 필요 공간: 37.681 GiB
- preflight 관측 D: 여유: 60.491 GiB
- 2024→2025 Gate: 8/8 passed

## 시행착오와 재발 방지

첫 runner preflight는 제한된 Codex 셸에서 AppData의 conda 실행 환경 접근이 달라
`mfa_runtime_dependencies`만 NO-GO로 기록됐다. 별도 읽기 전용 직접 검사에서
`mfa.exe`, Python, `fstcompile.exe`가 존재하고 MFA `check_third_party()`가 exit 0임을
확인했다. 정상 Windows 권한으로 같은 preflight를 다시 실행해 모든 검사가 GO인
정본 보고서를 만들고 그 SHA만 전환 Gate에 결속했다.

앞으로 제한 셸의 runtime 실패만으로 MFA 설치 부재나 환경 손상을 진단하지 않는다.
장시간 명령 전에는 정상 Windows PowerShell 5.1 조건에서 safety/runtime tests와
대상 runner의 `-PreflightOnly`를 통과시킨다.

## 반복하지 않는 범위

- 2020–2024 MFA·6-tier export·독립 QC
- 2025 morph_search.v3 30/30과 frozen source contract
- 2025 WAV snapshot·입력 계약·연구 DB·정렬 계약·runner preflight
- 공통발음 r3 Stage 01–21와 연구자 승인

실패 시 2025 해당 checkpoint만 보존·복구하며 앞 연도나 공통사전부터 다시 시작하지
않는다.

## 다음 실행

사용자가 일반 PowerShell 한 창에서 `run_mfa_r3_year_safe_body.ps1 -Year 2025
-NumJobs 4`를 한 번 실행한다. 두 번째 runner를 동시에 실행하지 않는다. MFA 완료 뒤
post-MFA 미정렬 exact-ID reconciliation, 6-tier export, 독립 QC 순으로 진행한다.

## 근거 파일

- `outputs/reports/AUDIT_mfa_r3_year_input_contract_2025_20260814.json`
- `outputs/reports/AUDIT_mfa_r3_alignment_contract_2025_20260809.json`
- `outputs/reports/GATE_mfa_r3_2024_TO_2025_20260814.json`
- `work/mfa_r3_preflight/PREFLIGHT_common_pron_mfa_r3_20260809_2025.json`
- `D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\03_year_input_contracts\2025`
- `D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\05_research_database\2025`
