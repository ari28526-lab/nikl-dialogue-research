# Codex 작업용 Windows 개발 환경 기록

작성일: 2026-07-06

이 문서는 Codex와 함께 Python, R, RStudio, Quarto/qmd 작업을 할 때 참조하기 위한 환경 기록이다. 새 기기로 옮기거나 Windows를 다시 세팅하거나, Codex가 실행 파일을 못 찾을 때 이 문서를 기준으로 확인한다.

## 핵심 원칙

- Python 작업은 프로젝트마다 `.venv`를 만든다.
- R/qmd 작업은 R 4.6.1을 기준으로 한다.
- Codex 세션의 PATH가 오래된 경우가 있으므로, 자동화나 검증에는 절대경로를 우선 사용한다.
- Windows PowerShell에서 `R`은 R 언어가 아니라 `Invoke-History` 별칭일 수 있으므로 `Rscript.exe` 전체 경로를 쓰는 편이 안전하다.
- Windows R에서 `LC_ALL=C.UTF-8`, `LC_CTYPE=C.UTF-8`, `LANG=C.UTF-8` 때문에 locale 경고가 날 수 있다. R/Quarto 실행 전 이 변수들을 비우면 경고가 사라진다.

## Python

설치 상태:

- Python: `3.13.14`
- 설치 방식: `winget install --id Python.Python.3.13`
- 실제 Python 경로: `C:\Users\ari30\AppData\Local\Programs\Python\Python313\python.exe`
- Python launcher 경로: `C:\Users\ari30\AppData\Local\Programs\Python\Launcher\py.exe`
- pip 확인됨: Python 3.13용 `pip 26.1.2`
- PowerShell 실행 정책: `CurrentUser RemoteSigned`

정리한 문제:

- `C:\Users\ari30\AppData\Local\Microsoft\WindowsApps\python.exe`
- `C:\Users\ari30\AppData\Local\Microsoft\WindowsApps\python3.exe`

위 두 파일은 0바이트 WindowsApps 별칭 파일이었고 삭제했다. 이 파일들이 남아 있으면 `python` 명령이 실제 Python 대신 Store 별칭을 잡을 수 있다.

일반 사용 명령:

```powershell
python --version
py --version
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install <package>
```

Codex가 PATH를 못 믿을 때 쓸 안전한 명령:

```powershell
& "C:\Users\ari30\AppData\Local\Programs\Python\Python313\python.exe" --version
& "C:\Users\ari30\AppData\Local\Programs\Python\Launcher\py.exe" -0p
```

프로젝트 실행 시 가장 안전한 방식:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## R

설치 상태:

- R 4.6.1: `C:\Program Files\R\R-4.6.1`
- R 4.5.1: `C:\Program Files\R\R-4.5.1`
- 기준 버전: R 4.6.1
- Rscript 안전 경로: `C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe`
- R 사용자 라이브러리: `C:\Users\ari30\AppData\Local\R\win-library\4.6`
- Rtools 경로 확인됨: `C:\rtools45\usr\bin`, `C:\rtools45\mingw64\bin`
- R source package 빌드 확인됨: `rlang`, `Rcpp` 빌드 성공

PowerShell에서 주의:

```powershell
Get-Command R -All
```

위 명령에서 `R`이 `Invoke-History` 별칭으로 나올 수 있다. 그러면 `R --version`은 R을 실행하는 것이 아니다. R 자동화는 아래처럼 전체 경로로 실행한다.

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" -e "print(1+1)"
```

설치한 주요 R 패키지:

```text
knitr=1.51
rmarkdown=2.31
quarto=1.5.1
languageserver=0.3.18
reticulate=1.46.0
tinytex=0.60
ggplot2=4.0.3
tidyverse=2.0.0
```

패키지 재설치가 필요할 때:

```r
options(repos = c(CRAN = "https://cloud.r-project.org"))
install.packages(c(
  "rmarkdown",
  "quarto",
  "languageserver",
  "reticulate",
  "tinytex",
  "ggplot2",
  "tidyverse"
))
```

## RStudio

설치 상태:

- RStudio 실행 파일: `C:\Program Files\RStudio\rstudio.exe`

Codex가 GUI 앱을 직접 여는 작업은 승인/UAC/샌드박스 영향을 받을 수 있다. RStudio에서 편집하고 Codex에서 CLI 렌더링을 검증하는 흐름이 안정적이다.

## Quarto / qmd

설치 상태:

- Quarto CLI: `1.9.38`
- Quarto 경로:
  - `C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd`
  - `C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.exe`
  - `C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.js`
- Chrome 감지됨
- 기본 Markdown 렌더링 통과
- R 4.6.1 감지됨
- R 청크가 들어간 `.qmd` HTML 렌더링 통과

HTML 렌더링 안전 명령:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd" render "report.qmd" --to html
```

검증에 사용한 테스트 파일:

- `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-quarto-setup\smoke.qmd`
- 생성 결과: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-quarto-setup\smoke.html`

테스트 내용:

- R 코드 청크 실행
- `summary(cars)` 출력
- `plot(cars)` 그래픽 출력
- Quarto HTML 생성

## TinyTeX / PDF

현재 상태:

- R 패키지 `tinytex`는 설치됨
- 실제 TinyTeX 배포판은 아직 설치되지 않음
- 확인 결과: `tinytex::is_tinytex()` -> `FALSE`

따라서 현재 안정적으로 확인된 출력은 HTML이다. PDF 렌더링까지 필요하면 다음을 별도로 실행한다.

```r
tinytex::install_tinytex()
```

그 다음 PDF 검증:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd" render "report.qmd" --to pdf
```

## Codex에서 우선 사용할 실행 방식

Python:

```powershell
& "C:\Users\ari30\AppData\Local\Programs\Python\Python313\python.exe"
```

Python 프로젝트:

```powershell
.\.venv\Scripts\python.exe
```

R:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe"
```

Quarto:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd"
```

## 새 기기 또는 재설치 체크리스트

1. Python 3.13 설치
2. `py --version`, `python --version` 확인
3. WindowsApps의 0바이트 `python.exe`, `python3.exe` 별칭이 앞서 잡히지 않는지 확인
4. PowerShell 실행 정책을 사용자 범위에서 `RemoteSigned`로 설정
5. R 4.6.1 설치
6. RStudio 설치
7. Quarto CLI 설치
8. Rtools 설치 또는 확인
9. R 사용자 라이브러리에 `rmarkdown`, `knitr`, `quarto`, `languageserver`, `reticulate`, `tinytex` 설치
10. HTML qmd 렌더링 테스트
11. PDF가 필요하면 TinyTeX 설치 후 PDF 렌더링 테스트

## 빠른 검증 명령 모음

```powershell
python --version
py --version
where.exe python
where.exe py
where.exe quarto
quarto --version
where.exe Rscript
```

PATH가 불안정하면:

```powershell
& "C:\Users\ari30\AppData\Local\Programs\Python\Python313\python.exe" --version
& "C:\Users\ari30\AppData\Local\Programs\Python\Launcher\py.exe" -0p

$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" -e "sessionInfo()"

$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd" --version
```

R 패키지 검증:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" -e "pkgs <- c('knitr','rmarkdown','quarto','languageserver','reticulate','tinytex','ggplot2','tidyverse'); info <- sapply(pkgs, function(p) if (requireNamespace(p, quietly=TRUE)) as.character(packageVersion(p)) else 'MISSING'); cat(paste(names(info), info, sep='=', collapse='\n'))"
```

## 남은 주의점

- 현재 기록 기준으로 HTML qmd 렌더링은 검증됨.
- PDF qmd 렌더링은 TinyTeX 배포판이 없어 아직 검증하지 않음.
- Codex의 현재 실행 세션은 PATH를 오래된 상태로 들고 있을 수 있다. 이 경우 새 세션을 열거나 절대경로를 쓴다.
- R locale 경고가 보이면 `LC_ALL`, `LC_CTYPE`, `LANG`를 비우고 다시 실행한다.
- `R` 명령 자체는 PowerShell 별칭과 충돌할 수 있으므로 자동화에서는 `Rscript.exe` 절대경로를 쓴다.

## brms / Stan

설치 상태:

- brms: `2.23.0`
- cmdstanr: `0.9.0`
- CmdStan: `2.39.0`
- CmdStan 설치 경로: `C:\Users\ari30\.cmdstan\cmdstan-2.39.0`
- RStan도 설치됨: `rstan=2.36.0.9000`
- StanHeaders: `2.36.0.9000`
- loo: `2.10.0.9000`
- posterior: `1.7.1`
- bayesplot: `1.15.0.9000`
- bridgesampling: `1.2.1`

설치 방식:

- `brms`는 CRAN에서 설치
- `cmdstanr`, Stan 계열 패키지는 Stan R-universe와 CRAN을 함께 사용
- CmdStan 본체는 `cmdstanr::install_cmdstan(cores = 2)`로 설치

검증 완료:

- `cmdstanr::check_cmdstan_toolchain()` 통과
- CmdStan 예제 `bernoulli.stan` 컴파일 성공
- CmdStan 예제 짧은 MCMC 샘플링 성공
- `brms`에서 `backend = "cmdstanr"`로 작은 선형 모델 컴파일 및 샘플링 성공
- 검증 결과 `fit$backend`가 `"cmdstanr"`로 확인됨

brms 실행 시 안전한 기본 형태:

```r
library(cmdstanr)
library(brms)

cmdstan_dir <- "C:/Users/ari30/.cmdstan/cmdstan-2.39.0"
cmdstanr::set_cmdstan_path(cmdstan_dir)

tbb_dir <- file.path(cmdstan_dir, "stan", "lib", "stan_math", "lib", "tbb")
Sys.setenv(PATH = paste(tbb_dir, Sys.getenv("PATH"), sep = .Platform$path.sep))

fit <- brm(
  y ~ x,
  data = dat,
  family = gaussian(),
  backend = "cmdstanr",
  chains = 4,
  cores = 4,
  seed = 123
)
```

Codex에서 brms 검증에 사용한 실행 방식:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-quarto-setup\validate_brms_cmdstanr.R"
```

주의:

- CmdStan 설치 중 `NOTE: Please add .../tbb to your PATH variable` 메시지가 나왔다. 검증 스크립트에서는 실행 전에 TBB 경로를 `PATH` 앞에 추가했다.
- CmdStan/TBB 컴파일 중 많은 C++ 경고가 출력됐지만 설치와 실행은 성공했다.
- 실제 분석에서는 설치 검증용처럼 아주 작은 `iter` 값을 쓰지 말고, 모델에 맞는 충분한 반복 수와 체인을 사용한다.
