# Codex Instructions For This Project

This folder is the main project workspace for 2026 summer linguistics research.

Use Korean for user-facing explanations unless the user asks otherwise.

Before starting any substantial task in this folder, read:

```text
docs/environment/PROJECT_START_HERE.md
docs/environment/linguistics-research-environment-master-notes.md
```

If those files mention paths from an older Codex setup folder, treat them as environment reference notes, not necessarily as the current project root.

## Project Root

```text
C:\Users\ari30\research\2026_summer_research
```

## Important Existing Environment

```text
Python:
C:\Users\ari30\AppData\Local\Programs\Python\Python313\python.exe

Project pipeline Python:
C:\Users\ari30\miniforge3\envs\mfa\python.exe

R:
C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe

Quarto:
C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd

Bareun API key folder:
C:\Users\ari30\Documents\Codex\_secrets\bareun

MFA conda:
C:\Users\ari30\miniforge3\Scripts\conda.exe

MFA environment:
C:\Users\ari30\miniforge3\envs\mfa
```

Python verification rule:

- In the user's normal PowerShell, `python`, `py`, and the absolute Python 3.13
  path are valid.
- A restricted Codex shell can report `AccessDenied`, `Test-Path=False`, or
  command-not-found for the AppData Python even when the file exists. Do not
  diagnose an absent installation from that result alone.
- Run `scripts\check_python_environment.ps1` with read-only permission when
  global Python must be verified.
- Prefer `config/paths.json` key `pipeline_python` for reproducible project
  helper scripts. Use the MFA conda command for MFA itself.

Windows PowerShell 5.1 compatibility rule:

- Save every `.ps1` as UTF-8 with BOM; `.editorconfig` is authoritative.
- Do not use `+=` for JSON/pipeline values that can unwrap to a scalar
  `PSCustomObject`; normalize with `@(...)` and accumulate in a typed List.
- Do not poll an actively written `*_heartbeat.jsonl` with `Get-Content`.
  Open it through `FileStream` with `FileShare.ReadWrite`, and keep polling
  intervals conservative. Heartbeat append conflicts must be retried and must
  never terminate MFA computation.
- Before giving the user a long-running PowerShell command, run both
  `tests/test_powershell_safety.ps1` and
  `tests/test_powershell_runtime_compat.ps1` under Windows PowerShell 5.1,
  then run the target script's `-PreflightOnly` mode when it exists.

## Safety And Data Rules

- Do not print API keys or copy secret values into chat, logs, scripts, notebooks, or Quarto documents.
- Keep Bareun secrets outside this Dropbox project folder.
- Treat external-drive corpus data as source data. Do not modify raw corpus files unless explicitly asked.
- For Modu corpus and MFA work, require a validated pilot or a passed prior-year production gate before bulk processing. Do not repeat a pilot when the frozen contract is unchanged; 2020 Gate B is the pilot/production gate for 2021–2025.
- Keep large generated files out of Dropbox when practical; store only scripts, notes, small samples, final reports, and selected outputs here.
- Put transient files in `work`, reusable scripts in `scripts`, final results in `outputs`, and logs in `logs`.

## Preferred Commands

R:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" "scripts\R\SCRIPT.R"
```

MFA:

```powershell
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa version
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa model list acoustic
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa model list dictionary
```

Quarto:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd" render "qmd\report.qmd" --to html
```

## Expected Workflow

1. Read the project notes.
2. Confirm the relevant environment with a small validation command.
3. Work on a small pilot sample.
4. Save scripts and reproducible notes.
5. Record important decisions in `docs/decisions`.
6. Put final user-facing outputs in `outputs`.
