# 2022 개선 MFA 실행안 — 2020·2021 실측 반영

작성 시작: 2026-07-27
상태: **초안 — 2021 전량 완료·QC 뒤 확정**
원칙: 2022 전량은 사용자 확인 전 시작하지 않음

## 목적

2020에서 발견한 raw TextGrid export 병목과 2021 direct-DB 전량 실측을 함께
반영해, 2022를 처음부터 재현 가능하고 복구 가능한 방식으로 수행한다.

연구 흐름은 변하지 않는다.

```text
동결 CSV에서 형태소·표기/음운형태 환경 후보 검색
  → WAV·4-tier TextGrid 수집
  → 필요한 구간 KOINA
  → 연구자의 음성·TextGrid 수동 실현 판정
```

MFA `phones`는 대략적 G2P 시간정렬이며 실제 실현 판정값이 아니다.

## 2022 입력 기준선

읽기 전용 감사:
`outputs/reports/AUDIT_mfa_year_readiness_2021-2025_20260726.json`

| 항목 | 2022 |
|---|---:|
| pre-MFA CSV 세션 | 2,654 |
| 검색행 | 866,359 |
| WAV | 878,157 |
| 예상 usable lab | 866,106 |
| 현재 lab | 0 |
| 빈 reference form | 253 |
| reference form 변경 | 43,972 |
| 미해결 기호 | 10,106 |
| search master 밖 WAV | 11,798 |
| 과거 source PCM 없음 위험 | 15 |

`search master 밖 WAV`는 주로 빈 form 등으로 검색 입력에 들어가지 않는 원
음성이다. 예상하지 않은 lab이 함께 남아 있지 않으므로 그 자체를 오류로
간주하지 않는다.

## 2020에서 계승할 개선

- 동결 pre-MFA search master와 lab SHA256 입력계약
- 다른 계약의 temp를 삭제하지 않고 archive
- exit 0만 믿지 않는 coverage·실물 수량 gate
- 1분 heartbeat와 watchdog
- 실패 시 다음 연도로 진행하지 않음
- 기존 `06_textgrid_eojeol` 및 원 WAV 비변경
- staging 전수검증 뒤에만 별도 승격

2020의 가장 큰 병목은 raw TextGrid export 15시간 57분과 후속 4-tier merge
1시간 43분이었다. 2022에서는 이 구 경로를 기본으로 사용하지 않는다.

## 2021에서 확정·조정할 개선

현재 2021은 다음 경로를 실제 전량 실행 중이다.

```text
pron_reference_form lab
  → MFA word/phone interval SQLite
  → raw 2-tier 생략
  → DB에서 4-tier partial 병렬 생성
  → coverage·hard-failure gate
  → final staging 이동
  → QC 전 DB 보존
```

2022 확정 전에 2021에서 다음 실측을 가져온다.

1. lab 검증·재작성 시간
2. corpus loading, G2P/MFCC/graph, alignment, interval collect 시간
3. temp peak와 D: 최소 여유
4. direct 4-tier 발화/초와 worker 4의 안정성
5. 난정렬·source 결함·form/morpheme 누락 수
6. heartbeat 단계 판별과 watchdog 오판 여부
7. direct 결과의 tier·양끝 경계·duration 전수검사

2021 완료 전에는 이 항목을 추정치로 확정하지 않는다.

2021의 G2P 교차점검에서 MFA가 주 Python 외에 보조 Python 4개를 사용하고,
보조 작업 각각의 CPU가 지속 증가하는 것이 확인되었다. 기존 heartbeat의
CPU 합계는 이 실행에서는 우연히 실제 트리 합계와 같았지만, 코드를 확인하니
컴퓨터의 모든 `mfa/python` 프로세스를 합산하고 있었다. 별도 Python 분석이
병행되면 진짜 MFA 교착을 정상으로 오판할 수 있다.

2026-07-27 다음 실행용 runner를 Windows Toolhelp 프로세스 스냅샷 기반으로
수정했다. 관리자 권한 없이 `mfa.exe`의 실제 자식·손자만 찾아 heartbeat에
`tree_cpu_seconds`, tree process/Python 수, tree RAM, PID 목록과 집계 범위를
남긴다. 현재 2021 실행 트리(launcher 1, 주 Python 1, worker Python 4)로
동적 검사했고 PowerShell 안전성 회귀시험에도 추가했다. 실행 중인 2021
프로세스에는 소급 적용하지 않으며, 2022 preflight에서 새 필드가 실제 첫
heartbeat에 나타나는지 확인한다.

2021 G2P에서 보조 worker 하나가 다른 셋보다 먼저 정상 종료하자 기존
live-process CPU 합계가 14,050.94초에서 11,343.92초로 역행하는 현상도
관측했다. 계산이 되돌아간 것이 아니라 종료 worker의 누적 CPU가 합계에서
빠진 것이다. 다음 실행용 runner는 PID별 마지막 CPU를 보존해
`tree_live_cpu_seconds`, `tree_retired_cpu_seconds`, 둘의 단조 증가 합인
`tree_cpu_seconds`를 따로 기록한다. worker 종료와 PID 재사용을 재현한
동적 시험을 추가했다. 2022 preflight에서는 첫 heartbeat의 세 필드뿐 아니라,
worker 수가 줄어든 뒤에도 `tree_cpu_seconds`가 감소하지 않는지 확인한다.

## 실행 위치 판단: Colab보다 외장 SSD를 연결한 강한 로컬 컴퓨터

2026-07-27 현재 실행 컴퓨터는 Intel N200, 논리 프로세서 4개이며 MFA도
`-j 4`를 사용한다. 2021 G2P에서는 남은 worker 3개의 CPU가 계속 증가하고
D: 사용량은 거의 변하지 않아 이 구간의 주 병목은 저장장치보다 CPU 계산이다.
현 컴퓨터 안에서 job 수만 늘리는 가속 여지는 거의 없다.

Google Colab hosted runtime은 사용자 컴퓨터에 꽂힌 외장 SSD를 직접 마운트하지
못한다. 자료를 hosted VM으로 업로드·동기화하지 않는 조건에서는 계산 노드가
원자료에 접근할 수 없다. Colab local runtime은 외장 SSD를 읽을 수 있지만
코드는 현재 컴퓨터의 CPU·RAM·디스크에서 실행되므로 Colab 화면만 바뀌고 MFA
속도는 빨라지지 않는다. 또한 MFA의 공식 가속 축은 `num_jobs`와
multiprocessing이며, hosted runtime에서 GPU를 선택하는 것만으로 현재
Kaldi/OpenFST·SQLite 중심 정렬이 자동 GPU 가속되지는 않는다.

공식 근거:

- Colab local runtime은 로컬 하드웨어에서 코드를 실행:
  <https://research.google.com/colaboratory/local-runtimes.html>
- Colab hosted 자원은 보장·무제한이 아니며 중단 가능:
  <https://research.google.com/colaboratory/faq.html>
- MFA는 `--num_jobs`와 multiprocessing을 실행 가속 옵션으로 제공:
  <https://montreal-forced-aligner.readthedocs.io/en/v3.3.3/user_guide/data_validation.html>

따라서 2021 실행은 현재 컴퓨터에서 그대로 보존·완료한다. 2022 이후 시간을
의미 있게 줄이려면 외장 `DATA_SSD`를 성능이 더 높은 로컬 컴퓨터에 물리적으로
연결하고, 같은 Git commit·MFA 3.4.0 패치 10/10·모델·입력계약으로 소표본
benchmark를 먼저 한다. 가능하다면 원자료는 외장 SSD에서 읽기 전용으로 두고
MFA temp/SQLite만 후보 컴퓨터의 빠른 내부 NVMe에 두는 조합도 비교한다.
전량 이전 판단은 동일 표본의 벽시계 시간, 산출 수량, tier/시간경계 동등성,
temp peak가 모두 확인된 뒤에 한다.

### 기기 변경 없이 남은 가속 우선순위

기기 변경이 부담스럽다는 사용자 조건을 반영하면, “더 이상 방법이 없음”은
아니다. 다만 현재 Intel N200의 논리 프로세서 4개를 `-j 4`로 이미 사용하므로
job 수만 늘려 전체 MFA를 몇 배 빠르게 할 수는 없다. 남은 방법은 반복 계산과
운영체제 오버헤드를 줄이는 것이다.

1. **2020–2025 공통 발음 자원·versioned MFA 사전 — 최우선 파일럿**
   - 설치된 MFA 3.4.0 소스를 확인하면 `normalize_text()`가 사전에 없는
     **고유 OOV 집합**을 만든 뒤 Pynini G2P worker queue에 넣는다. 같은 단어가
     한 연도 안에서 반복돼도 한 번만 계산하지만, 새 연도 DB에서는 다시
     계산한다.
   - 2021에서는 이 단계가 09:16 시작해 11:15에도 계속됐고, worker 하나가
     먼저 끝난 뒤 셋이 오래 계산했다. 남은 셋이 CPU를 계속 사용하므로
     교착은 아니며, queue 끝의 계산비용이 큰 단어들이 장기 꼬리를 만드는
     것으로 추정한다.
   - 동결 pre-MFA CSV에서 **2020–2025 전체** 고유 어절을 모아 기본
     `korean_mfa` 사전의 OOV와 사전–G2P 불일치 항목을 추출한다.
   - G2P 결과만 cache하는 대조 정책 A와, 우리말샘·표준국어대사전 연계
     `pron_1/2` 예외·대체 발음을 출처와 함께 보존하는 정책 B를 분리해 만든다.
     두 정책 모두 기본 사전을 직접 덮어쓰지 않는 별도 versioned 파생사전이며,
     예상 밖 residual OOV용 fallback도 별도 집계한다.
   - 공식 MFA도 `mfa find_oovs` 결과를 `mfa g2p` 입력으로 사용하고 생성
     발음을 기존 사전에 보완하는 절차를 제공한다:
     <https://montreal-forced-aligner.readthedocs.io/en/latest/user_guide/workflows/dictionary_generating.html>
   - 우리말샘 등재 `pron_1/2`, 과거 기계 생성 `pron_g2p`, 현재 G2P를 같은
     “사전 발음”으로 뭉개지 않는다. 출처·품사·의미·사전 ID·model hash를
     long-format 정본에 보존하고, search CSV와 MFA `.dict`를 각각 파생한다.
   - GO 조건은 파일럿 OOV 0 또는 설명 가능한 residual, phone set 완전 호환,
     사전·manifest 재생성 hash 동일, TextGrid 수량·tier·시간경계 정상,
     예외 stress 표본의 연구자 검토, 실제 G2P 단계 시간 감소다.
   - 정책 B가 채택돼 허용 phone 후보가 달라지면 2020·2021도 같은 공통
     release로 재정렬하는 것을 기본 권고한다. 기존 결과는 baseline으로
     archive하고 새 `run_id`와 섞지 않는다.

2. **이미 적용한 direct DB 4-tier 경로 유지**
   - 2020에서 raw export 15시간 57분과 별도 merge 1시간 43분이 걸렸다.
     이를 생략하는 direct 경로가 가장 큰 코드 수준 가속이며 2021에 실제
     적용 중이다. 이 이득을 되돌리는 built-in export 경로는 사용하지 않는다.

3. **전원 모드와 냉각 — 2021 뒤 동일 표본 비교**
   - 현재 Windows 전원 계획은 `균형 조정`이다. 2021 실행 중에는 환경을
     바꾸지 않는다. 완료 뒤 AC 전원·충분한 냉각에서 `최고 성능`을 적용한
     동일 표본과 비교한다. 효과는 CPU 단계에 한정된 중간 폭 개선으로 보고,
     결과 동등성과 온도·안정성을 함께 본다.

4. **Defender 제외는 좁게, 명시 승인 뒤**
   - 수백만 소형파일을 읽고 쓰는 corpus loading·MFCC·TextGrid 출력에서
     실시간 검사가 비용을 만들 수 있다. 현재 권한으로 exclusion 현황은
     조회되지 않았다.
   - 기존 `setup_mfa_speed_once.ps1`은 원자료와 전체 miniforge까지 넓게
     제외하므로 그대로 실행하지 않는다. 필요하면 generated temp·DB·staging
     경로만 대상으로 좁힌 가역 설정을 만들고, 보안상 시스템 변경이므로
     사용자 명시 승인 후 파일럿한다. 현재 CPU 중심 G2P에는 직접 효과가 작다.

5. **C: temp 전환은 현재 금지**
   - 2026-07-27 C: 여유는 47.85GB뿐이다. 2021 실측 DB·temp와 다음 연도
     안전 문턱을 고려하면 내부 드라이브 가속을 기대해 C:로 옮길 여유가
     부족하다. D: `DATA_SSD` 317.84GB를 계속 사용한다.

따라서 2021은 건드리지 않고 완주한다. 완료 뒤 첫 추가 작업은 2022 전량이
아니라 6개년 공통 vocabulary·연도 간 중복률·길이/문자 이상치·사전 후보
충돌을 읽기 전용으로 감사하고, 소표본에서 현재 baseline과 공통 발음사전
정책 A/B를 비교하는 것이다. 정책 B를 채택하면 2020·2021을 먼저 새 release로
재정렬·전수 QC한 뒤 2022–2025에 같은 사전을 적용한다. 세부 정본·파생물·
fingerprint 계약은
`DESIGN_common_pronunciation_lexicon_2020_2025_20260727.md`를 따른다.

## 2022 고유 병목과 대응

### lab 866,106개 신규 생성

2021은 기존 lab 133만 개를 검증하면서 38,320개만 재작성했지만, 2022는 현재
lab이 0개다. 따라서 정렬 이전의 소형파일 쓰기 비용이 2021보다 상대적으로
커질 수 있다.

대응:

- 세션당 디렉터리 목록 1회 캐시 유지
- 발화별 존재확인 왕복 금지
- 원자적 `.lab` 쓰기
- 세션·발화 처리율과 ETA를 로그에 즉시 출력
- lab marker는 입력계약이 정확히 같을 때만 재사용

2026-07-27 다음 실행용 빌더에 append-only lab heartbeat를 구현했다.
연도·입력계약별 파일에 `lab_started`, `lab_progress`, `lab_completed`,
`lab_reused`를 기록하며, 세션 진도·전체 조회 행·usable lab·신규·재작성·
검증·WAV 누락·빈 reference·행/초·ETA·경과시간을 보존한다. invalid 행이
많아도 heartbeat가 멈추지 않도록 기존 usable lab 기준 대신 `rows_seen`
1,000행 단위로 기록한다. 작은 임시 코퍼스에서 이벤트 순서와 marker 재사용
경로까지 회귀시험을 통과했다.

이 과정에서 기존 빌더가 usable lab 0건일 때 `passed` marker를 먼저 기록하고
나중에 예외를 내는 거짓 성공 순서를 발견했다. 성공 marker·최신 보고서는
0건 gate 통과 뒤에만 쓰도록 순서를 바꾸고, 실패 시 `lab_failed`와
`reason=usable_lab_zero`를 남긴다. 0건 임시 코퍼스에서 성공 marker와 성공
보고서가 생성되지 않는 것도 회귀시험으로 고정했다.

2021 완료 뒤 실제 SSD 쓰기율을 반영해 2022 ETA를 계산한다. lab 생성이
느리다고 MFA temp를 삭제하거나 runner를 중복 실행하지 않는다.

### known source 위험 15건

과거 PCM 감사의 `PCM 없음` 15건은 사후 미정렬 inventory에서 먼저 source
결함 후보로 분류한다. 현재 감사에서는 44 byte 미만 WAV가 없었으므로 전량
시작 자체를 막지 않되, 난정렬과 같은 범주로 합치지 않는다.

### 2021 DB 보존과 용량

첫 2021 direct 실행의 SQLite DB는 QC 전까지 보존한다. 2022 preflight에서는
다음을 다시 계산한다.

- 2021 retained temp 실제 크기
- 2021 final 4-tier 실제 크기
- D: 남은 여유
- 2022 예상 temp peak

공간이 충분하더라도 2021 QC와 기록이 끝나기 전에는 2022를 자동 시작하지
않는다.

## 2022 GO/NO-GO

다음이 모두 충족돼야 GO다.

- 2021 final 4-tier 전수검증 통과
- 2021 align/merge marker가 같은 입력계약을 가리킴
- 2021 누락 inventory와 source/난정렬 분류 저장
- 2021 DB 보존 또는 검증 후 정리 결정 기록
- MFA 설치 패치 10/10
- 2022 세션 coverage 2,654/2,654
- D: `DATA_SSD` 및 실측 기반 여유 공간 통과
- 2022 temp/output/staging/marker 충돌 없음
- 다른 MFA·KOINA·Dropbox 대량 복사 없음

2021부터 `audit_mfa_4tier_year.py`를 final 승격 후 독립 gate로 사용한다.
lab↔TextGrid ID coverage·중복·누락 inventory, 네 tier 순서, 0–xmax 연속성,
interval gap/overlap, 핵심 label, WAV header duration을 전수 검사한다.
운영본의 원시간을 바꾸지 않으므로 0.05초 가시적 양끝 빈 경계는 hard gate가
아니라 tier별 진단값이며, 패딩된 연구자 점검 사본에서 별도로 보장한다.

### 2021 완료 증거를 2022 preflight에 결합

`preflight_next_year_after_qc.py`를 다음 연도 선행 gate로 추가했다. 콘솔의
완료 문구나 MFA exit 0만으로는 통과하지 않으며 다음을 서로 대조한다.

- 2021 독립 4-tier 전수 감사 `status=success`, coverage 99% 이상,
  hard failure 0
- audit·align marker·merge marker·temp contract의 입력계약 ID 일치
- 세 기록의 동결 pre-MFA search master 경로 일치
- direct-DB 보고서 성공, form/morpheme/출력 실패 0
- audit·marker·direct 보고서의 lab/TextGrid 수량 일치
- 2021 SQLite DB가 temp 계약 경로에 실제로 남아 있고 0바이트가 아님
- audit의 final 연도 폴더와 merge marker의 staging base 일치
- 누락 발화 CSV가 실제로 존재

계약 불일치, DB 누락, direct 보고서 누락, 손상된 숫자 필드를 합성 fixture로
재현해 모두 실패 보고서를 남기고 fail-closed임을 확인했다. 이 gate가
통과한 뒤에만 기존
`preflight_eojeol_realign.ps1 -Year 2022`로 모델·MFA 패치·SSD 라벨·공간·
2022 세션 coverage·temp 충돌을 확인한다.

## 준비된 실행 명령

아래 1·2는 2021 전수 QC 완료 뒤 실행할 읽기 전용 preflight다. 3은
**사용자 확인 전 실행하지 않는다**.

1. 2021 완료 증거 결합 gate:

```powershell
cd "C:\Users\ari30\research\2026_summer_research"

& "C:\Users\ari30\miniforge3\envs\mfa\python.exe" `
  ".\scripts\python\preflight_next_year_after_qc.py" `
  --prior-year 2021 `
  --next-year 2022 `
  --audit-report `
    ".\outputs\reports\AUDIT_mfa_4tier_2021_pre_mfa_v1_20260727.json" `
  --align-marker "D:\mfa_eojeol\done\2021.align_done" `
  --merge-marker "D:\mfa_eojeol\done\2021.merge_done" `
  --temp-contract "D:\mfa_eojeol\input_contracts\2021.json" `
  --expected-search-master-root `
    "D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725" `
  --expected-final-year-root `
    "D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2021" `
  --report `
    ".\outputs\reports\PREFLIGHT_2022_after_2021_QC_20260727.json"

if ($LASTEXITCODE -ne 0) {
  throw "2021 완료 증거 gate 실패 — 2022 실행 금지"
}
```

2. 2022 자체 입력·환경 preflight:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  ".\scripts\preflight_eojeol_realign.ps1" `
  -Year 2022 `
  -SearchMasterRoot `
    "D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725" `
  -PreferD

if ($LASTEXITCODE -ne 0) {
  throw "2022 환경·입력 preflight 실패 — 실행 금지"
}
```

3. 두 preflight 통과와 사용자 확인 뒤의 실제 한 연도 실행:

```powershell
cd "C:\Users\ari30\research\2026_summer_research"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  ".\scripts\run_pre_mfa_bulk_safe.ps1" `
  -RunId "pre_mfa_v1_20260725" `
  -Years 2022 `
  -PreferD `
  -UseDirectDbExport
```

첫 2022 direct 결과도 QC 전에는 `-CleanupDirectDbAfterMerge`를 붙이지 않는다.

## 완료 후 채울 실측 표

| 지표 | 2020 | 2021 | 2022 실행 결정 |
|---|---:|---:|---|
| usable lab | 869,840 | 1,373,521 | 866,106 |
| lab 단계 | 12분 | 실행 후 입력 | 실행 후 예측 |
| corpus loading | 약 14분 | **30분 실측** | 잠정 15–20분, 전체 완료 뒤 확정 |
| setup/G2P/MFCC/graph | 7시간 27분 | 실행 후 입력 | 비례·보정 |
| alignment | 1시간 7분 | 실행 후 입력 | 비례·보정 |
| interval collect | 1시간 37분 | 실행 후 입력 | 비례·보정 |
| raw export | 15시간 57분 | direct면 생략 | 생략 |
| 4-tier 출력 | 1시간 43분 별도 merge | 실행 후 입력 | direct 예상 |
| temp peak | 약 33GB 미만 | 실행 후 입력 | 실측 기반 |
| 난정렬/누락 | 3,644 | 실행 후 입력 | source 위험과 분리 |
