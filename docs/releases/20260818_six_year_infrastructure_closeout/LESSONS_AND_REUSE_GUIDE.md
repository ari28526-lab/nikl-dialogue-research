# 시행착오와 재사용 안내

이 문서는 코드를 잘 모르는 연구자도 같은 종류의 자료 구축을 시작할 때 무엇을
먼저 결정하고, 어디서 멈추며, 어떤 결과를 믿지 말아야 하는지 설명한다. 특정
PowerShell 한 줄을 복사하는 것보다 계약과 순서를 재사용하는 것이 목적이다.

## 1. 가장 중요한 교훈

### 1.1 먼저 연구 흐름을 고정한다

“MFA를 돌린다”가 연구 목적이 아니다. 어떤 형태소·표기 환경을 검색할지, WAV와
TextGrid를 어떻게 돌아볼지, 실제 실현을 누가 판단할지부터 문장으로 쓴다. 자동
phone은 후보 탐색과 시간 접근을 돕지만 최종 실현값이 아니다.

### 1.2 원본, 파생, 수동 보정을 분리한다

- 원본: JSON, WAV/PCM, 원 전사
- 파생: 형태소 CSV, 검색표, MFA DB, TextGrid
- 수동 보정: exact-ID overlay, 연구자 decision ledger

수동 보정 때문에 원본이나 수백만 건의 기본 파생본을 덮어쓰지 않는다. 기본 release
위에 작은 sidecar를 적용하면 수정 이유와 이전 상태를 모두 설명할 수 있다.

### 1.3 연도보다 계약을 먼저 고정한다

연도별로 즉석 G2P나 다른 모델을 쓰면 “같은 기준”이라고 말하기 어렵다. 발음
release, 사전, G2P, 음향모델, phone inventory, runtime, tier schema를 먼저
동결하고 hash로 기록한다. 2020 Gate가 통과해 계약이 변하지 않으면 2021–2025에
같은 파일럿을 반복하지 않는다.

### 1.4 일부 성공을 성공으로 처리하지 않는다

입력 10건 중 TextGrid 9건은 90% 성공이 아니라 “1건의 상태가 설명되지 않은
부분 성공”이다. 입력 = 성공 + 이유가 있는 후속이라는 회계가 성립해야 단계가
끝난다.

### 1.5 실패를 버리지 말고 exact-ID로 라우팅한다

실패 1건 때문에 연도 전체를 다시 돌리지 않는다. 실패 ID, 이유, 입력 계약,
시도한 설정, 보존 자산과 다음 Gate를 장부에 남기고 별도 shard로 보낸다. 같은
입력과 같은 설정의 무한 재시도는 금지한다.

## 2. 실제로 겪은 오류와 바뀐 설계

| 시행착오 | 위험 | 채택한 대응 |
|---|---|---|
| 한 화자 중심 파일럿 | 화자·세션 편향을 놓침 | 연도·복수 화자·복수 세션 층화 표본 |
| TextGrid 9/10 생성인데 성공처럼 보임 | 누락 은폐 | 입력-출력 완전성 fail-closed |
| CSV/코퍼스/TextGrid에 없는 발화 ID | 잘못된 pairing | 원 JSON·WAV·duration·exact-ID 재감사 |
| 일부 tier만 앞뒤 경계 보유 | 이어붙이기·검색 좌표 혼동 | 전체 시간축 coverage와 tier 계약 검사 |
| 형태소를 억지로 시간 분할 | 경계가 음성학적 사실처럼 보임 | 형태소/POS를 발화 검색 문자열 tier로 전환 |
| 숫자·기호의 발음열이 빈칸 | 검색·MFA 입력 손실 | 표기와 읽기 후보를 별도 정보로 보존 |
| 기본 beam 실패를 조용히 재시도 | 방법 불명·성공 과장 | 설정과 결과를 기록한 exact-ID controlled retry |
| 연도별 inline G2P | 기준 불일치·중복 계산 | 6개년 공통발음 release와 model hash 동결 |
| grapheme/음절 모델의 inventory 누락 | `spn`·생성 실패 | 최신 Jamo G2P 기준, no-path를 별도 queue로 보존 |
| 사전 변이를 전부 추가하려는 유혹 | 해당 발화와 다른 발음 강제 | 사전 발음은 참조층, MFA 변이는 검토·계약된 것만 |
| PowerShell `Count` scalar 해제 | 대량 job 중단 | `@(...)` 정규화와 typed List, PS 5.1 runtime test |
| UInt32 seed 범위 오류 | 실행 전/중단 | signed/unsigned 범위 명시와 preflight 회귀검사 |
| heartbeat 동시 쓰기 충돌 | 계산은 정상인데 wrapper 종료 | FileShare.ReadWrite·재시도·heartbeat 비치명화 |
| gzip CSV 줄 수 off-by-one | shard 생성 중단 | CSV parser 기반 row count와 newline 회귀검사 |
| WAV ID·길이·CSV 시간 불일치 | 잘못된 음성에 전사 연결 | raw 불변, recovery staging, source snapshot과 SHA |
| MFA 완료 뒤 word/phone 없는 ID | 거짓 전수 완료 | post-MFA exact-ID 제외 장부와 연구자 승인 |
| 2024 export의 실패·성공 보고서 공존 | 최신 파일 오판 | QC state가 가리키는 SHA의 보고서만 정본 채택 |
| `있지/있는/없는/어쨌든` phone 기준 문제 | 6개년 방법 불일치 | r3 계약으로 6개년 fresh realign |
| 수동 전사 후 기존 형태소·phone 유지 | 층간 모순 | RC1 pointer만 채택하고 enrichment는 별도 Gate |
| 검토 폴더가 너무 세분됨 | 연구자 검토 비용 증가 | 번호순 flat bundle, WAV/LAB/TextGrid/CSV 동봉 |
| 검수만 반복하고 반영 지연 | 진도 정체 | 검수 결과를 계약·코드·release에 반영한 뒤 다음 Gate |

## 3. 재사용자가 먼저 준비할 것

### 3.1 최소 입력

1. 발화별 고유 ID
2. WAV 또는 변환 가능한 원 음성
3. 발화 전사
4. 세션·화자 연결 정보
5. 형태소/POS 또는 이를 생성할 명시적 도구·버전
6. 원자료를 다시 찾을 수 있는 source pointer

ID가 불안정하면 MFA 전에 멈춘다. 파일명 유사도로 대량 pairing하지 않는다.

### 3.2 세 가지 계약

- **input contract**: 어떤 ID와 파일이 입력인지
- **method contract**: 모델·사전·G2P·runtime·tier가 무엇인지
- **output contract**: 성공 조건, 파일 수, tier, 실패 장부가 무엇인지

각 계약에는 사람이 읽는 설명과 기계가 읽는 JSON, SHA-256이 함께 있어야 한다.

## 4. 권장 실행 순서

### 단계 A — 읽기 전용 감사

- 원자료 수, ID 중복, WAV/LAB pairing, duration 가능성 확인
- 결과를 바꾸지 말고 문제 범주와 수량만 만든다.

### 단계 B — 검색층

- 원 전사, 정규화 전사, 형태소/POS, 철자 로마자, 기호 읽기, 세션/화자 정보를
  분리된 열로 만든다.
- 발화 수가 원 범위와 정확히 같은지 감사한다.

### 단계 C — 공통발음·모델 동결

- 전체 범위 어휘를 관측하고 기본 사전 OOV를 계산한다.
- G2P no-path를 숨기지 않는다.
- 사용한 파일과 runtime을 hash로 동결한다.

### 단계 D — 층화 pilot/Gate

- 여러 연도, 최소 여러 화자·세션, 짧고 긴 발화, 기호·잡음·OOV·연결 발화를
  포함한다.
- TextGrid 수량, tier, 앞뒤 coverage, WAV·LAB identity, 사람이 읽을 수 있는
  검색 문자열을 확인한다.
- 계약이 그대로면 다음 연도에 같은 pilot을 반복하지 않는다.

### 단계 E — 연도별 안전 본체

- 한 연도씩 materialize → MFA → post-MFA accounting → 6-tier export → 독립 QC.
- 완료 marker와 DB를 보존한다.
- 오류 ID만 별도 후속으로 보내고 성공 본체를 다시 계산하지 않는다.

### 단계 F — 교차연도 release

- 공통 method hash와 연도별 ID 범위 차이를 구분한다.
- 원천 = 정렬 + 기술 후속 + 발음 후속 + 연구 제외의 회계식을 검사한다.

### 단계 G — 실제 연구

- 선언형 query로 형태소·표기 환경 후보를 뽑는다.
- 후보 occurrence를 WAV·TextGrid와 연결한다.
- MFA 경계를 연구자 판정 문맥으로만 사용한다.
- KOINA·wav2vec/HuBERT 등은 원 열을 덮지 않는 보조 sidecar로 추가한다.
- 최종 실현·제외·수동 경계는 연구자 decision ledger에 기록한다.

## 5. 다른 사람이 이 저장소를 사용할 때

배포판은 두 경로를 먼저 구분한다. 허가 대상 데이터와 완성 파생층이 들어 있는
D: 동결본을 인계하는 경우는 `DISTRIBUTION_D_DRIVE.md`, 원자료를 각자 확보하고
코드로 재현하는 경우는 `DISTRIBUTION_CODE_ONLY.md`를 따른다. 두 경로 모두
특정 현상 검색과 실현 판정은 A단계 배포에 포함하지 않는다.

### 5.1 같은 원 말뭉치를 재현하는 경우

1. `docs/environment/PROJECT_START_HERE.md`와 `config/paths.json`을 읽는다.
2. 원자료는 이용권한에 따라 별도로 확보한다. GitHub에 WAV가 있다고 가정하지
   않는다.
3. `docs/RUNBOOK_production_2020_2025.md`의 현행 runner만 사용한다.
4. archive 문서의 명령은 실행하지 않는다.
5. `-PreflightOnly`가 있는 장시간 PowerShell은 먼저 preflight한다.
6. `tests/test_powershell_safety.ps1`과
   `tests/test_powershell_runtime_compat.ps1`를 Windows PowerShell 5.1에서 통과한다.
7. release manifest의 수량·hash가 다르면 자동으로 계속하지 않는다.

동일 폴더명이더라도 제공기관의 갱신으로 byte가 달라질 수 있다. 입력 SHA가
다르면 기존 수량을 강제로 맞추지 않고 새 input release로 기록한다.

### 5.2 다른 한국어 말뭉치에 적용하는 경우

그대로 재사용할 것은 checkpoint, exact-ID 회계, fail-closed, overlay와 독립 감사
패턴이다. 그대로 복사하면 안 되는 것은 ID parser, JSON schema, 세션·화자 필드,
형태소 tagset, 기호 읽기, 음성 포맷과 licensing이다. 새 corpus adapter와 새 input
contract를 먼저 만든다.

### 5.3 코드를 잘 모르는 연구자의 확인 질문

각 단계에서 아래 다섯 문장에 답할 수 있어야 한다.

1. 지금 입력은 정확히 몇 건이고 어디에 있는가?
2. 성공은 무엇이며 몇 건인가?
3. 실패·보류는 몇 건이고 exact-ID가 남아 있는가?
4. 원본과 이전 release를 덮어썼는가?
5. 같은 결과를 다시 만들 모델·버전·명령·hash가 있는가?

하나라도 답할 수 없으면 다음 대량 단계로 넘어가지 않는다.

## 6. 공개 저장소의 권장 구조

현재 GitHub 공개는 확정되지 않았다. 공개한다면 전체 작업 저장소를 그대로
복제하지 않고 `PUBLIC_CODE_RELEASE_CANDIDATE.md`의 allowlist Gate를 통과한
A단계 코드 재현 package만 사용한다. 코드 라이선스 결정도 공개 전 필수다.

```text
README.md                    # 목적, 범위, 라이선스, 빠른 길잡이
docs/
  methods/                   # 연구 인프라 방법
  tutorials/                 # 작은 비식별 예시
  decisions/                 # 중요한 변경과 이유
  archive/                   # 과거 기록, 실행 금지 표지
config/                      # 경로·query·schema 예시(비밀 제외)
scripts/                     # 재사용 코드
tests/                       # 회귀·안전 검사
outputs/examples/            # 작은 manifest와 가상/허용 예시
```

원 음성, 개인 Dropbox 경로, API key, 대형 MFA DB와 licensed corpus는 Git에 넣지
않는다. 대신 사용자가 직접 배치해야 할 위치, 예상 수량, checksum 생성법을 쓴다.

## 7. 재실행하지 않아야 할 것

- 현재 2020–2025 r3 MFA와 전수 6-tier export/QC
- 완료 계약이 바뀌지 않은 pilot
- 같은 입력·같은 설정으로 이미 실패한 exact-ID의 무한 재시도
- RC0/RC1 기본 회계를 수정하는 즉석 수동 편집

새 연구 질문의 query와 연구자 판정은 앞으로 진행할 일이지만, 그것을 이유로
6개년 안전 본체를 다시 만들 필요는 없다.
