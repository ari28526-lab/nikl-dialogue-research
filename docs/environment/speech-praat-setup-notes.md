# Praat / Speech Analysis Setup Notes

Created: 2026-07-07

## Workspace

- Project folder: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat`
- Python virtual environment: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat\.venv`
- R version used: `R 4.6.1`
- R user library: `C:\Users\ari30\AppData\Local\R\win-library\4.6`

## Python Praat / TextGrid Packages

Installed and import-tested:

```text
praat-parselmouth==0.4.7
praatio==6.2.2
tgt==1.5
TextGrid==1.6.1
soundfile==0.14.0
numpy==2.5.1
pandas==3.0.3
```

Full lock file:

`C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat\python-requirements.lock.txt`

Validation command:

```powershell
& "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat\.venv\Scripts\python.exe" "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat\validate_python_praat.py"
```

## R Praat / Speech Packages

Status after recheck on 2026-07-07:

```text
rPraat=MISSING
tuneR=MISSING
seewave=MISSING
wrassp=MISSING
phonTools=MISSING
emuR=MISSING
textgRid=MISSING
```

Earlier installation output reported successful unpacking into `C:\Users\ari30\AppData\Local\R\win-library\4.6`, but a later filesystem and `requireNamespace()` check did not find the installed packages there. Treat the R Praat/speech packages as not currently installed until they are reinstalled and revalidated.

TextGrid work can still be handled with `rPraat` in R and `praatio`, `tgt`, or `TextGrid` in Python.

Validation command:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat\validate_r_praat_packages.R"
```

## Suggested Use

- Use Python `praat-parselmouth` when you need direct Praat-style acoustic extraction from scripts.
- Use Python `praatio` or `tgt` when you mainly need to read/write TextGrid annotation files.
- Use R `rPraat` for TextGrid/formant/pitch-oriented Praat workflows inside R.
- Use R `tuneR`, `seewave`, and `wrassp` for waveform and acoustic signal processing.
- Use `emuR` when working with structured speech corpora and annotation databases.

## Optional Later Additions

`python-requirements-optional.txt` contains broader audio-analysis packages:

```text
librosa
matplotlib
scipy
```

These were prepared but not installed in the first Praat-focused pass.
