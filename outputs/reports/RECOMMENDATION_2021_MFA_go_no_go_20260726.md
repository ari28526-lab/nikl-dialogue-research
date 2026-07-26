# 2021 MFA 오전 실행 판정

판정: **GO — 단, 2021 한 연도만 실행하고 첫 결과 QC 전에는 DB를 보존**

2026-07-26 23:23 preflight는 FAIL 0 / WARN 0이다. D: 여유 319GB,
2021 세션 4,143/4,143, MFA 설치 패치 10/10, 세 모델, 신규 상태를 확인했다.

오늘 밤 22:17부터 다음 날 09:00까지는 전량을 시작하지 않았다. 개선 후에도
2021 예상 시간이 약 18–23시간이라 오전까지 끝나지 않고, 새 direct 경로의
첫 전량 실행은 연구자가 시작 사실을 알고 있는 상태가 더 안전하기 때문이다.

오전 명령:

```powershell
cd "C:\Users\ari30\research\2026_summer_research"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  ".\scripts\run_pre_mfa_bulk_safe.ps1" `
  -RunId "pre_mfa_v1_20260725" -Years 2021 -PreferD -UseDirectDbExport
```

시작 전에는 D:의 Dropbox 복사·다른 MFA·KOINA를 끝내고, 전원 연결·절전
해제·SSD 연결을 확인한다. `-CleanupDirectDbAfterMerge`는 첫 2021에 붙이지
않는다.

실증 근거:

- 3,330개 파일럿: 기존 경로와 direct 4-tier 불일치 0
- 21,962개 실자료: tier 라벨·모든 경계시간 불일치 0
- 병렬 direct 출력: 21,962개 73.983초
- Python 50개 + PowerShell 실행기 5개 파일 안전성 검사 통과

상세 기록:
`docs/decisions/AUDIT_remaining_MFA_years_and_direct_DB_export_2026-07-26.md`
