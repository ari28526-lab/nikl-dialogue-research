# 바른 형태소 분석기 설치/운영 메모

작성일: 2026-07-06

## 현재 PC 기준 판단

- C: 드라이브: 약 236.56GB 중 약 59.86GB 여유
- Docker: 설치되어 있지 않음
- WSL: 설치되어 있지 않음
- 바른 로컬 서버: 설치되어 있지 않음
- `C:\Program Files\bareun`: 없음
- `BAREUN_ROOT`: 설정되어 있지 않음
- 5656 포트: 현재 충돌 흔적 없음
- RAM/CPU: 약 8GB RAM, Intel N200 계열로 확인됨

## 결론

이 기기에서는 처음부터 Docker/WSL까지 깔아서 바른 서버를 로컬로 운영하기보다는, 우선 바른 클라우드 API와 Python 클라이언트 `bareunpy`를 쓰는 방식이 가장 안정적이다.

이유:

- 바른은 단순 Python 패키지가 아니라 서버형 분석기와 클라이언트가 통신하는 구조이다.
- 현재 Docker/WSL이 없어서 Docker 방식은 준비 비용이 크다.
- RAM 8GB 환경에서는 로컬 AI 서버를 상시 서비스로 띄우는 것보다 클라우드 API가 덜 부담스럽다.
- 이미 Python 3.13.14가 설치되어 있고, `bareunpy`는 Python 3.10 이상을 지원하므로 클라이언트 설치 조건은 충족한다.

## 추천 순서

1. 클라우드 API + `bareunpy`로 먼저 분석 워크플로우를 만든다.
2. 대량 자료 처리, 폐쇄망, 데이터 외부 전송 제한이 필요해지면 Windows MSI 설치 방식으로 로컬 서버를 설치한다.
3. Docker는 Docker Desktop/WSL2를 다른 작업에서도 계속 쓸 계획이 있을 때만 선택한다.

## Python 클라이언트 방식

프로젝트별 가상환경에서 설치한다.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install bareunpy
```

현재 테스트 가상환경:

- 경로: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke\.venv`
- 설치 완료: `bareunpy==2.0.1`
- lock 파일: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke\requirements.lock.txt`
- API 키 없는 상태에서 `smoke_bareun.py`가 키 누락을 정상 감지함

API 키는 코드에 직접 적지 않고 환경변수로 둔다.

```powershell
$env:BAREUN_API_KEY="YOUR-API-KEY"
```

또는 로컬 전용 보관 폴더에 둔다.

- 보관 폴더: `C:\Users\ari30\Documents\Codex\_secrets\bareun`
- 키 파일: `C:\Users\ari30\Documents\Codex\_secrets\bareun\bareun.env`
- 예시 파일: `C:\Users\ari30\Documents\Codex\_secrets\bareun\bareun.env.example`

`bareun.env` 내용:

```text
BAREUN_API_KEY=koba-발급받은키
```

`smoke_bareun.py`는 이 보관 폴더의 `bareun.env`를 자동으로 읽도록 설정되어 있다.

테스트 코드 예시:

```python
import os
from bareunpy import Tagger

tagger = Tagger(os.environ["BAREUN_API_KEY"], "api.bareun.ai", 443)
result = tagger.pos("햇빛이 선명하게 나뭇잎을 핥고 있었다.")
print(result)
```

## R 클라이언트 방식

R에서는 REST API를 직접 호출하는 작은 래퍼를 준비해 두었다.

- R 작업 폴더: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r`
- R 클라이언트 함수: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r\bareun_client.R`
- R smoke test: `C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r\bareun_r_smoke.R`
- API 키 파일: `C:\Users\ari30\Documents\Codex\_secrets\bareun\bareun.env`

현재 상태:

- `httr2`, `jsonlite`, `tibble`, `dplyr` 등 REST 호출과 결과 정리에 필요한 R 패키지는 `work\r-linguistics\.r-lib`에서 사용 가능하다.
- `bareun_r_smoke.R`는 API 키가 없으면 실제 호출 전에 정상적으로 멈춘다.

실행 명령:

```powershell
$env:LC_ALL=''
$env:LC_CTYPE=''
$env:LANG=''
& "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\r-linguistics\bareun-r\bareun_r_smoke.R"
```

로컬 바른 서버를 쓸 때는 R 함수의 `host`를 바꾼다.

```r
bareun_analyze("문장", host = "http://localhost:5656")
```

## Windows 로컬 서버 방식

로컬 설치가 필요하면 Windows MSI 설치를 우선한다.

- 기본 설치 경로: `C:\Program Files\bareun`
- 설치 후 `BAREUN_ROOT`가 자동 설정됨
- 관리 페이지: `http://localhost:5656`
- API 키 등록:

```powershell
cd "C:\Program Files\bareun"
.\bareun.exe -reg YOUR-API-KEY
```

Python에서 로컬 서버에 붙을 때:

```python
from bareunpy import Tagger

tagger = Tagger("YOUR-API-KEY", "localhost", 5656)
```

## Docker 방식

현재 이 PC에는 Docker/WSL이 없으므로 1순위로 권하지 않는다. Docker까지 설치할 계획이 있으면 다음 공식 흐름을 쓴다.

```powershell
docker pull bareunai/bareun:latest
docker run `
  -d `
  --restart unless-stopped `
  --name bareun `
  -p 5656:5656 `
  -v ~/bareun/var:/bareun/var `
  bareunai/bareun:latest
docker exec bareun /bareun/bin/bareun -reg YOUR-API-KEY
```

## 라이선스 주의

- 형태소 분석은 연구 목적 사용의 경우 무료로 안내되어 있다.
- 상용 서비스, 상시 운영 서비스, 상업적 목적 연구에는 유료 라이선스가 필요할 수 있다.
- 맞춤법 검사 기능은 유료 서비스로 안내되어 있다.

## 참고 링크

- 바른 소개: https://bareun.ai/docs/intro/
- 바른 클라우드 API: https://bareun.ai/docs/howtouse/cloud-api/
- 바른 Windows 설치: https://bareun.ai/docs/install/windows/
- 바른 Docker 설치: https://bareun.ai/docs/install/docker/
- bareunpy PyPI: https://pypi.org/project/bareunpy/
