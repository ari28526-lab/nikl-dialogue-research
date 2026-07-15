# R Linguistics / XAI / Speech Package Setup

Created: 2026-07-07

## Location

- Project folder: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics`
- Project R library: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\.r-lib`
- R profile: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\.Rprofile`
- Status CSV: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\r-linguistics-package-status.csv`

## How To Use In R

Put this at the top of an R script or qmd if needed:

```r
.libPaths(unique(c(
  "C:/Users/ari30/Documents/Codex/2026-07-06/d/work/r-linguistics/.r-lib",
  "C:/Users/ari30/AppData/Local/R/win-library/4.6",
  .libPaths()
)))
```

If RStudio is opened with `work/r-linguistics` as the working directory, `.Rprofile` sets this automatically.

## Verified Packages

Core tidy/data:

```text
tidyverse=2.0.0
ggplot2=4.0.3
dplyr=1.2.1
stringr=1.6.0
readr=2.2.0
purrr=1.2.2
tidyr=1.3.2
```

Corpus/text/morphology:

```text
quanteda=4.4
readtext=0.92.1
tidytext=0.4.3
tokenizers=0.3.0
tm=0.7.18
topicmodels=0.2.17
text2vec=0.6.6
udpipe=0.8.16
spacyr=1.3.0
koRpus=0.13.9
```

Speech/Praat/phonetics:

```text
rPraat=1.3.2.1
tuneR=1.4.7
seewave=2.2.4
wrassp=1.0.6
phonTools=0.2.2.2
emuR=2.6.0
```

LDA/classification:

```text
MASS=7.3.65
caret=7.0.1
e1071=1.7.17
klaR=1.7.4
mda=0.5.5
discrim=1.1.0
```

XAI/SHAP:

```text
DALEX=2.5.3
iml=0.11.4
shapviz=0.10.3
vip=0.4.6
lime=0.5.4
ingredients=2.3.0
kernelshap=0.9.1
shapr=1.0.8
SHAPforxgboost=0.2.0
shapper=0.1.3
```

Linguistic statistics:

```text
lme4=2.0.1
lmerTest=3.2.1
emmeans=2.0.3
ordinal=2025.12.29
```

## Known Missing Package

```text
fastshap=MISSING
```

`fastshap` was not available in the current CRAN binary or source package list when checked on 2026-07-07. SHAP work can use `kernelshap`, `shapviz`, `shapr`, `SHAPforxgboost`, and `shapper` instead.

## Bareun From R

Bareun can be called from R through its REST API.

- Folder: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r`
- Client: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r\bareun_client.R`
- Smoke test: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r\bareun_r_smoke.R`
- API key file: `C:\Users\ari30\Documents\Codex\_secrets\bareun\bareun.env`

The smoke test currently stops correctly when `BAREUN_API_KEY` is missing. After creating `bareun.env`, run the smoke test command below.

## Validate

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\validate_r_linguistics_packages.R"
```
