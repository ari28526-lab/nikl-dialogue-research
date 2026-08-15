# D0–D4 runbook

Current state: **STOP before recovery corpus materialization and MFA**.

Read-only preflight command:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\ari30\research\2026_summer_research\scripts\run_db_v1_recovery_first_shard.ps1" `
  -PreflightOnly
```

Do not replace `-PreflightOnly` until a separate, scope-bound researcher
approval contract exists for `D4_POST_MFA_DIAGNOSTIC_0001`. The frozen r3 body
must not be reused as a writable output and no whole-year rerun is authorized.
