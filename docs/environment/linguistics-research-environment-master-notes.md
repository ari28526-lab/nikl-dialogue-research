# 언어학 연구 환경 마스터 노트

작성일: 2026-07-07  
현재 작업공간: `C:\Users\ari30\Documents\Codex\2026-07-06\d`

이 문서는 Python, R, Quarto, brms/Stan, 바른 형태소 분석기, Praat/음성 분석, R 언어학 패키지, Montreal Forced Aligner(MFA)를 나중에 다른 기기에서 다시 세팅하거나 Codex에게 이어서 작업을 맡길 때 참조하기 위한 마스터 기록이다.

## 빠른 결론

- Python은 전역 설치 후 프로젝트별 `.venv`를 만든다.
- R은 분석 목적별로 전용 라이브러리 경로를 둔다.
- 바른 형태소 분석기는 Python/R 모두 가능하지만, 우선 클라우드 API + API 키 보관 파일 방식으로 쓴다.
- Praat/TextGrid 작업은 Python 전용 가상환경과 R 패키지 둘 다 준비되어 있다.
- MFA는 Miniforge 기반 conda 환경 `mfa`에 설치되어 있고, `korean_mfa` acoustic/dictionary 모델이 다운로드되어 있다.
- 외장하드의 원자료는 그대로 두고, pilot/중간결과/출력은 내장 작업공간에 둔다.

## 핵심 경로

```text
Codex workspace:
C:\Users\ari30\Documents\Codex\2026-07-06\d

Outputs:
C:\Users\ari30\Documents\Codex\2026-07-06\d\outputs

Python:
C:\Users\ari30\AppData\Local\Programs\Python\Python313\python.exe
C:\Users\ari30\AppData\Local\Programs\Python\Launcher\py.exe

R:
C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe

Quarto:
C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd

R linguistics library:
C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\.r-lib

Bareun API key folder:
C:\Users\ari30\Documents\Codex\_secrets\bareun

MFA / Miniforge:
C:\Users\ari30\miniforge3
C:\Users\ari30\miniforge3\envs\mfa
```

다른 기기에서는 `ari30`과 날짜별 workspace 경로가 달라질 수 있으므로, 스크립트 안의 절대경로를 새 경로에 맞게 바꾼다.

## 개별 기록 파일

```text
Python/R/Quarto 기본:
C:\Users\ari30\Documents\Codex\2026-07-06\d\outputs\codex-dev-environment-notes.md

바른:
C:\Users\ari30\Documents\Codex\2026-07-06\d\outputs\bareun-morph-analyzer-setup-plan.md

Praat/음성:
C:\Users\ari30\Documents\Codex\2026-07-06\d\outputs\speech-praat-setup-notes.md

R 언어학/XAI/SHAP:
C:\Users\ari30\Documents\Codex\2026-07-06\d\outputs\r-linguistics-setup-notes.md

MFA:
C:\Users\ari30\Documents\Codex\2026-07-06\d\outputs\mfa-setup-notes.md
```

## Python 세팅

설치된 버전:

```text
Python 3.13.14
```

새 기기 설치 권장:

```powershell
winget install --id Python.Python.3.13 -e --source winget --scope user
```

검증:

```powershell
python --version
py --version
py -0p
```

주의:

- WindowsApps의 0바이트 `python.exe`, `python3.exe` 스텁이 앞에 있으면 실제 Python을 가릴 수 있다.
- Codex 세션의 PATH가 오래된 경우 전체 경로를 사용한다.
- 프로젝트마다 `.venv`를 만든다.

## R / RStudio / Quarto

기준 버전:

```text
R 4.6.1
RStudio installed
Quarto 1.9.38
Rtools 45 available
```

R 실행 기본형:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" -e "sessionInfo()"
```

주의:

- PowerShell에서 `R`은 R 언어가 아니라 `Invoke-History` alias로 잡힐 수 있다.
- 자동화나 Codex에서는 `Rscript.exe` 전체 경로를 쓰는 것이 안전하다.
- Windows R locale 경고가 나면 `LC_ALL`, `LC_CTYPE`, `LANG`을 비우고 실행한다.

Quarto HTML 검증:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Users\ari30\AppData\Local\Programs\Quarto\bin\quarto.cmd" render "report.qmd" --to html
```

PDF 렌더링은 TinyTeX 배포판 설치가 아직 별도 확인 필요하다.

## brms / Stan

준비된 상태:

```text
brms=2.23.0
cmdstanr=0.9.0
CmdStan=2.39.0
CmdStan path: C:\Users\ari30\.cmdstan\cmdstan-2.39.0
```

검증 스크립트:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-quarto-setup\validate_brms_cmdstanr.R"
```

실제 brms 스크립트에서는 TBB 경로를 PATH 앞에 추가한다.

```r
cmdstan_dir <- "C:/Users/ari30/.cmdstan/cmdstan-2.39.0"
cmdstanr::set_cmdstan_path(cmdstan_dir)

tbb_dir <- file.path(cmdstan_dir, "stan", "lib", "stan_math", "lib", "tbb")
Sys.setenv(PATH = paste(tbb_dir, Sys.getenv("PATH"), sep = .Platform$path.sep))
```

## 바른 형태소 분석기

권장 사용 방식:

1. 클라우드 API + Python `bareunpy`
2. R에서는 REST API 래퍼 사용
3. 민감자료/폐쇄망/대량 처리 필요 시 Windows 로컬 바른 서버 고려

API 키 보관:

```text
C:\Users\ari30\Documents\Codex\_secrets\bareun\bareun.env
```

파일 내용:

```text
BAREUN_API_KEY=koba-발급받은키
```

채팅에 API 키를 붙이지 않는다.

Python 바른 환경:

```text
C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke
C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke\.venv
```

Python 검증:

```powershell
cd "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke"
.\.venv\Scripts\python.exe smoke_bareun.py
```

R 바른 래퍼:

```text
C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r\bareun_client.R
C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r\bareun_r_smoke.R
```

R 검증:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r\bareun_r_smoke.R"
```

## Praat / 음성 / TextGrid

Python 전용 환경:

```text
C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat
C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat\.venv
```

설치/검증된 주요 Python 패키지:

```text
praat-parselmouth==0.4.7
praatio==6.2.2
tgt==1.5
TextGrid==1.6.1
soundfile==0.14.0
numpy==2.5.1
pandas==3.0.3
```

검증:

```powershell
& "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat\.venv\Scripts\python.exe" "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\speech-praat\validate_python_praat.py"
```

R 쪽 음성/Praat 패키지는 R 언어학 전용 라이브러리에서도 검증됨:

```text
rPraat
tuneR
seewave
wrassp
phonTools
emuR
phonR
```

## R 언어학 / 텍스트 / XAI / 분류

전용 라이브러리:

```text
C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\.r-lib
```

RStudio나 qmd 상단에 필요하면 다음을 넣는다.

```r
.libPaths(unique(c(
  "C:/Users/ari30/Documents/Codex/2026-07-06/d/work/r-linguistics/.r-lib",
  "C:/Users/ari30/AppData/Local/R/win-library/4.6",
  .libPaths()
)))
```

검증:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\validate_r_linguistics_packages.R"
```

검증된 주요 묶음:

```text
tidyverse / ggplot2 / dplyr / stringr / readr / purrr / tidyr
quanteda / readtext / tidytext / tokenizers / tm / topicmodels / text2vec / udpipe / spacyr / koRpus
rPraat / tuneR / seewave / wrassp / phonTools / emuR
MASS / caret / e1071 / klaR / mda / discrim
DALEX / iml / shapviz / vip / lime / ingredients / kernelshap / shapr / SHAPforxgboost / shapper
lme4 / lmerTest / emmeans / ordinal
```

현재 `fastshap`은 CRAN 목록에서 확인되지 않아 설치하지 못했다. SHAP 작업은 `kernelshap`, `shapviz`, `shapr`, `SHAPforxgboost`, `shapper`를 우선 사용한다.

## Montreal Forced Aligner

설치 방식:

```text
Miniforge + conda-forge + mfa environment
```

설치된 경로:

```text
C:\Users\ari30\miniforge3
C:\Users\ari30\miniforge3\envs\mfa
```

검증:

```powershell
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa version
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa model list acoustic
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa model list dictionary
```

확인된 결과:

```text
MFA 3.4.0
acoustic: korean_mfa
dictionary: korean_mfa
```

모델 파일:

```text
C:\Users\ari30\Documents\MFA\pretrained_models\acoustic\korean_mfa.zip
C:\Users\ari30\Documents\MFA\pretrained_models\dictionary\korean_mfa.dict
```

모두의 말뭉치 대화 코퍼스 pilot 흐름:

```powershell
& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa validate "E:\path\to\pilot_corpus" korean_mfa korean_mfa --clean --num_jobs 1

& "C:\Users\ari30\miniforge3\Scripts\conda.exe" run -n mfa mfa align "E:\path\to\pilot_corpus" korean_mfa korean_mfa "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\mfa-pilot\aligned" --clean --num_jobs 1
```

이 PC에서는 처음에 `--num_jobs 1`, 안정적이면 `--num_jobs 2`까지만 권장한다.

## 모두의 말뭉치 / 외장하드 운용 원칙

- 원자료는 외장하드에 둔다.
- 작은 pilot subset만 먼저 만든다.
- 결과물, 로그, 정규화 전사, TextGrid 출력은 내장 작업공간에 둔다.
- MFA에는 같은 basename의 오디오와 전사 파일 구조가 필요하다.
- 기본 전사와 정규화 전사를 모두 보존한다.
- 대화체 특수표지, 웃음, 중복, 끊김, 방언, 고유명사는 OOV 점검 후 사용자 사전 보강이 필요하다.
- MFA는 전사 자체를 정밀하게 고쳐주는 도구가 아니라, 주어진 전사를 음성에 정렬하는 도구다.
- 겹침발화와 품질 낮은 구간은 자동 정렬 후 Praat에서 수동 검수한다.

## 새 기기에서 다시 세팅할 때 순서

1. Python 3.13 설치
2. R 4.6.x, Rtools, RStudio 설치
3. Quarto 설치
4. Miniforge 설치
5. MFA conda 환경 생성
6. Korean MFA acoustic/dictionary 모델 다운로드
7. 바른 API 키 보관 폴더 생성
8. Python 바른 `.venv` 재생성
9. Python Praat `.venv` 재생성
10. R 언어학 전용 `.r-lib` 설치 스크립트 실행
11. brms/CmdStan 검증
12. Quarto HTML smoke test
13. MFA `validate` pilot 실행

## 나중에 Codex에게 맡길 때 첫 요청 예시

```text
이 컴퓨터에 언어학 연구 환경을 다시 세팅하려고 해.
먼저 outputs/linguistics-research-environment-master-notes.md를 읽고,
Python/R/Quarto/MFA/바른/Praat/R 언어학 패키지 설치 상태를 점검한 뒤
빠진 것만 보완해줘.
```

외장하드 코퍼스 작업 요청 예시:

```text
외장하드에 모두의 말뭉치 대화 코퍼스를 연결했어.
MFA용 pilot subset을 만들고,
전사 정규화 -> mfa validate -> OOV 목록 -> align -> TextGrid 후처리까지
작은 샘플로 먼저 진행해줘.
```

## 주의할 점

- API 키, 개인정보, 연구대상 원자료는 채팅에 붙이지 않는다.
- 외장하드 드라이브 문자는 바뀔 수 있으므로 스크립트에서 경로를 매번 확인한다.
- Codex 일반 실행과 권한 승인 실행에서 PATH나 라이브러리 탐색 결과가 다르게 보일 수 있다.
- Windows에서는 R/Python/conda 실행 시 전체 경로를 쓰는 편이 가장 안정적이다.
- 설치 기록은 성공 로그보다 검증 명령 결과를 기준으로 판단한다.
