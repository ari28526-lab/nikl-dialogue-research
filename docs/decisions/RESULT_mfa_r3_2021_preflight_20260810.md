# 2021 r3 장시간 MFA 직전 GO 결과

기록일: 2026-08-10 KST

## 결론

2020 r3 완료본을 다시 계산하지 않고 동결한 상태에서, 2021 한 연도의 WAV 원천
snapshot, exact-ID 입력 계약, 발음 연구 DB, alignment contract, 독립 감사와
장시간 runner preflight를 모두 통과했다. 실제 2021 MFA·corpus 물질화·TextGrid
수출은 아직 시작하지 않았다.

## 2020 동결 근거

- `QC_STATE.json`: `passed`, SHA-256
  `fb92b2d22a1f238acebbe226cf3fc347c301c72052cecb4803c1121b30d10146`
- `ALIGN_DONE_2020.json`: SHA-256
  `8cececf38fd9488a95d4512009378be972a4467dc9db6a1afc67058c97c63d3e`
- 최종 6-tier 782,432개, 승인 후속 283개, DB 재수출 표본 semantic·byte
  24/24 동일
- 이번 단계에서 `source_mutation_performed=false`, `mfa_recomputed=false`,
  `full_export_repeated=false`

## 2021 입력 계약

- 검색 원천 발화: 1,373,920
- recovered WAV snapshot: 1,416,216
- pronunciation-safe: 1,208,236
- pronunciation follow-up: 165,684
- pre-MFA 기술 제외: 937
- 장시간 MFA exact-ID 입력: 1,207,299
- source WAV 누락: 0
- source 밖 추가 WAV 42,296개는 snapshot에는 기록하되 MFA 입력으로 암묵 선택하지 않음
- year input contract ID:
  `1b6e767631bc047735aba192d3964470fcee93f61c49d28fad7618362aa9cd91`

최초 WAV snapshot 구현은 각 파일의 개별 stat을 반복하여 약 184초 뒤 제한 시간에
도달했고 결과 파일을 승격하지 않았다. 상대경로 inventory 중심으로 바꾼 뒤 약
90.8초에 완료했다. 원 WAV는 읽기 전용이며 이동·수정·삭제하지 않았다.

## 발음 연구 DB와 정렬 계약

- 연구 DB: 발화 1,373,920행, reference-eojeol occurrence 6,648,515행
- 안전 본체 1,207,299 + follow-up 165,684 + pre-MFA 제외 937 = 전체 발화
- unknown nonempty LAB token: 0
- 연구 DB 독립 감사: `passed`, SHA-256
  `7ee6b03bf2f749ee3fa5eaac4bc21f6d87ac56c14db6b352ccce8ca1c12feb01`
- alignment contract ID:
  `e072d4a74ce1ade7d175e4988b6113977711852d491b8b72438744400bea3f95`
- alignment contract SHA-256:
  `291ff4d1c18c19ec3250ea4d1206f425449bade395c3b9a84743fbd40a37e8aa`
- acoustic v3.3.0, Jamo G2P v3.2.0, r3 공통사전의 경로·크기·SHA가 2020과 같은
  단일 release 계약으로 고정됨
- 구 r2 marker·DB·interval 재사용: 금지

## 검증 결과

- 표적 Python 테스트 11개 통과
- Python 전체 suite 555개 통과
- Windows PowerShell 안전 검사 68개 파일 통과
- Windows PowerShell 5.1 runtime 호환 검사 68개 스크립트 통과
- 실제 2021 `-PreflightOnly`: `status=go`, `failed_checks=[]`
- 공간 산식: 필요 74.733 GiB, 관측 D: 여유 167.081 GiB
- preflight SHA-256:
  `7b3c4c5aad249aaed4feb75ee51dd3e3f192c5c3133bee4f249c205d892524d3`

## 다음 허용 동작

연구자가 장시간 PowerShell 창에서 아래 명령을 한 번만 실행한다.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_mfa_r3_year_safe_body.ps1" `
  -Year 2021 -NumJobs 4
```

동시에 같은 명령을 두 번 실행하지 않는다. 중단·실패 시 corpus·temp·DB를 삭제하지
않고 상태판과 로그를 먼저 확인한다. 2020은 재실행하지 않는다.
