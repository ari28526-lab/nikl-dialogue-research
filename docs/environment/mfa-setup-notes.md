# Montreal Forced Aligner Setup Notes

Created: 2026-07-07

## Installed Components

- Miniforge: `C:\Users\ari30\miniforge3`
- Conda executable: `C:\Users\ari30\miniforge3\Scripts\conda.exe`
- MFA conda environment: `C:\Users\ari30\miniforge3\envs\mfa`
- MFA version: `3.4.0`

## Korean MFA Models

Installed and listed by MFA:

```text
acoustic: korean_mfa
dictionary: korean_mfa
```

Model files:

```text
C:\Users\ari30\Documents\MFA\pretrained_models\acoustic\korean_mfa.zip
C:\Users\ari30\Documents\MFA\pretrained_models\dictionary\korean_mfa.dict
```

## Verification Commands

```powershell
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa version
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa model list acoustic
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa model list dictionary
```

Expected:

```text
3.4.0
['korean_mfa']
['korean_mfa']
```

## Recommended First Pilot

Use a tiny subset first, not the whole corpus.

Suggested local structure:

```text
External drive:
E:\modu-corpus\...

Working/output folder:
C:\Users\ari30\Documents\Codex\2026-07-06\d\work\mfa-pilot
```

Run validation first:

```powershell
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa validate "E:\path\to\pilot_corpus" korean_mfa korean_mfa --clean --num_jobs 1
```

Then align:

```powershell
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa align "E:\path\to\pilot_corpus" korean_mfa korean_mfa "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\mfa-pilot\aligned" --clean --num_jobs 1
```

Use `--num_jobs 1` first on this PC. If the pilot is stable, try `--num_jobs 2`.

## Notes

- MFA is installed and runs locally.
- Korean acoustic and dictionary models are downloaded and registered.
- The PC is modest, so run small batches by session/speaker rather than the whole corpus at once.
- Keep raw audio/transcripts on the external drive and write alignment outputs to the internal workspace.
- MFA does forced alignment from existing transcripts. It does not create a fully corrected precision transcript by itself.
