# archive

더 이상 활발히 쓰지 않지만 버리기 애매한 파일을 보관하는 곳입니다.

가능하면 날짜나 이유를 파일명에 남깁니다.

## MFA 설치본 패치

`mfa_install_patches/`는 프로젝트 밖 conda 환경의 MFA 소스를 고치기 직전
원본과 SHA256 manifest를 보존한다.

- `export_queue_pre_20260726_2205/`: 고정 1초 queue 종료 경쟁을 sentinel로
  바꾸기 전 `alignment/base.py`, `alignment/multiprocessing.py`
- `skip_export_pre_20260726_2300/`: 프로젝트 direct-DB 모드용 선택적 raw
  TextGrid export 생략 가드를 넣기 전 `command_line/align.py`

복구할 때는 manifest의 경로·SHA256을 먼저 확인한다. 파일을 무조건 설치
디렉터리에 덮어쓰지 않는다.
