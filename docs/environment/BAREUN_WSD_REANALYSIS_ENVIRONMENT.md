# 바른 동형이의어·의미번호 전면 재분석 환경

작성일: 2026-08-28

현재 상태: **P1 통과, CSV 전수 사용자 PowerShell 실행 대기**

## 이 환경의 목적

바른 형태소분석기의 `with_sense=true` 응답을 2020–2025 대화 말뭉치 전체에
새로 받아, 형태소 분석과 동형이의어 의미번호 후보를 재현 가능한 별도 레이어로
보존한다. 기존 형태소 결과를 제자리에서 갱신하지 않는다.

## 절대 보호 입력

외장하드에 남아 있는 다음 자료는 이미 완결된 정본이다.

- 2020–2025 원 CSV와 기존 Bareun CSV
- 완결된 MFA 결과와 6-tier TextGrid
- 원 WAV와 MFA에 사용한 WAV

이 환경은 위 자료를 **읽기 전용 입력**으로만 사용한다. 삭제, 이동, 이름 변경,
덮어쓰기, tier 수정, 재정렬은 허용하지 않는다. 새 대용량 산출물도 외장하드의
`D:/10_LAYERS/11_bareun_wsd/bareun_wsd_full_20260828` 아래에서만 만들고,
기존 경로가 있으면 실패하도록 설계한다. 작업 중에는 그 아래 `.building`,
검증 통과 뒤에는 `final`로 원자 승격한다. 프로젝트/GitHub에는 코드·문서·작은
manifest만 두고 CSV 본체나 TextGrid·WAV를 넣지 않는다.

## 고정한 클라이언트

- `bareunpy` 2.1.0
- 공식 저장소 commit `8107424892d76ac855918c20a0fb82faa877e530`
- 설치 목록: `config/bareun_wsd_requirements_20260828.txt`
- 실행 계약: `config/bareun_wsd_reanalysis_v1.json`
- 로컬 가상환경: `work/bareun_wsd_full_20260828/.venv`

PyPI의 과거 배포판 대신 동형이의어 분석을 포함한 공식 Git commit을 고정한다.
가상환경 자체는 Git에 올리지 않고, 요구사항과 검증 결과만 버전 관리한다.

## API 키 취급

키는 프로젝트와 Git 바깥에 둔다. 사전점검기는 다음 순서로 읽되 값은 화면,
보고서, 로그에 출력하지 않는다.

1. `BAREUN_API_KEY` 환경 변수
2. `%USERPROFILE%/Documents/Codex/_secrets/bareun/bareun.env`
3. `%USERPROFILE%/Documents/Codex/_secrets/bareun/bareun_api.txt`

## 환경 재구성

일반 PowerShell에서 다음처럼 프로젝트 파이프라인 Python으로 만든다.

```powershell
& "$env:USERPROFILE\miniforge3\envs\mfa\python.exe" -m venv `
  "work\bareun_wsd_full_20260828\.venv"
& "work\bareun_wsd_full_20260828\.venv\Scripts\python.exe" -m pip install `
  -r "config\bareun_wsd_requirements_20260828.txt"
```

설치에 사용하는 Python의 정본 경로는 `config/paths.json`의
`pipeline_python`을 우선한다.

## 사전점검

API를 부르지 않는 환경·입력 전수 점검:

```powershell
& "work\bareun_wsd_full_20260828\.venv\Scripts\python.exe" `
  "scripts\python\preflight_bareun_wsd_environment.py" `
  --full-input-scan
```

명시적으로 한 문장만 보내는 연결·응답 스모크 테스트:

```powershell
& "work\bareun_wsd_full_20260828\.venv\Scripts\python.exe" `
  "scripts\python\preflight_bareun_wsd_environment.py" `
  --full-input-scan --live-api
```

`--live-api`도 전수 호출은 하지 않으며 `다리를 건넜다.` 한 문장만 전송한다.
`--require-bulk-ready`는 저장공간, 입력 전수검사, 라이브 스모크, 문서의 명시
승인이 모두 충족되지 않으면 실패한다.

## 현재 안전 정지점

- P1은 240/240과 독립 감사를 통과했다.
- 전수 실행기·상태판·완료 감사기는 준비됐으나 API 전수 호출은 시작하지 않았다.
- 새 전수 결과의 최종 저장소도 외장하드이며 로컬 SSD는 결과 저장소가 아니다.
- CSV-only 예상은 gzip 약 2.00 GiB이며 15 GiB gate를 통과했다.
- TextGrid 등 추가 파생은 80 GiB gate가 계속 닫혀 있다.
- 의미번호는 자동 정답이 아니라 검토할 WSD 후보로 저장한다.
- TextGrid 연결은 별도 sidecar가 기본이며 원 TextGrid는 불변이다.

전수 실행 전 최종 확인:

```powershell
& .\run_bareun_wsd_csv_full.ps1 -PreflightOnly
```

전수 시작은 사용자가 직접 다음 명령을 실행해야 한다.

```powershell
& .\run_bareun_wsd_csv_full.ps1 `
  -Execute `
  -ApprovedBy ari30 `
  -ApprovalToken BAREUN_WSD_CSV_FULL_20260828
```

중단 뒤 재개:

```powershell
& .\run_bareun_wsd_csv_full.ps1 `
  -Execute -Resume `
  -ApprovedBy ari30 `
  -ApprovalToken BAREUN_WSD_CSV_FULL_20260828
```

다른 PowerShell 창에서 상태 확인:

```powershell
& .\show_bareun_wsd_csv_status.ps1
```

관련 결정 기록:

- `../decisions/PLAN_bareun_WSD_full_reanalysis_20260828.md`
- `../decisions/RESULT_bareun_WSD_environment_gate_20260828.md`
- `../decisions/RESULT_bareun_WSD_csv_pilot_P1_20260828.md`
