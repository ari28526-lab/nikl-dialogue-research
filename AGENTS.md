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
C:\Users\ari30\Dropbox\000_2026_summer_research
```

## Important Existing Environment

```text
Python:
C:\Users\ari30\AppData\Local\Programs\Python\Python313\python.exe

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

## Safety And Data Rules

- Do not print API keys or copy secret values into chat, logs, scripts, notebooks, or Quarto documents.
- Keep Bareun secrets outside this Dropbox project folder.
- Treat external-drive corpus data as source data. Do not modify raw corpus files unless explicitly asked.
- For Modu corpus and MFA work, always build and validate a small pilot subset before bulk processing.
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

