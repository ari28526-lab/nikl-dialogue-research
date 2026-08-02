# 2021–2025 MFA 준비도·2020 병목 개선 감사 (역사 기록)

작성: 2026-07-26  
대상: `pre_mfa_v1_20260725`를 입력으로 쓰는 2021–2025 어절 MFA  
원칙: 원 음성·기존 CSV·기존 TextGrid 읽기 전용, 신규 결과는 staging

## 결론

2021은 기술적으로 **GO**다. 다만 2026-07-26 22:17부터 다음 날 09:00까지
연구자가 확인할 수 없는 시간에는 전량 실행을 시작하지 않는다.

이 결정은 실패 가능성이 높아서가 아니라 다음 두 이유 때문이다.

1. 2021은 137만 발화로, 개선 뒤에도 약 18–23시간을 예상한다. 밤사이 끝나지
   않으므로 09:00까지 완결된 QC 결과를 얻을 수 없다.
2. 이번에 새로 연결한 DB 직접 4-tier 경로는 실제 21,965발화에서 기존 경로와
   완전히 같은 결과를 냈지만, 첫 전량 연도는 연구자가 시작 사실과 출력 보존
   정책을 알고 있는 상태에서 실행하는 편이 복구·판단 책임이 명확하다.

따라서 오늘 밤에는 코드 회귀검사, 2021–2025 읽기 전용 감사, 중규모 실자료
성능·동등성 검증, 문서화, 설치 패치 archive, Git 기록까지만 수행한다.
2021 전량은 다음 날 아래 명령으로 한 연도만 시작한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  "C:\Users\ari30\research\2026_summer_research\scripts\run_pre_mfa_bulk_safe.ps1" `
  -RunId "pre_mfa_v1_20260725" -Years 2021 -PreferD -UseDirectDbExport
```

첫 2021 실행에서는 `-CleanupDirectDbAfterMerge`를 붙이지 않는다. 4-tier 전수
검증과 표본 청취 전까지 alignment SQLite DB를 보존한다.

## 연구 흐름에서 이 산출물의 위치

이 작업은 다음 연구 흐름의 기반을 만든다.

```text
pre-MFA CSV
  → 특정 형태소·표기/음운형태 환경 후보 검색
  → 해당 WAV·TextGrid 수집
  → 필요 구간 KOINA 운율 분석
  → 연구자가 WAV·TextGrid를 보고 실현 여부 판정
```

MFA의 `phones`는 음성에 대략적으로 시간 정렬된 G2P 라벨이다. 예컨대 ㄴ 삽입
실현 여부를 자동 판정하는 gold 값이 아니다. 새 내보내기 경로는 이 의미를
바꾸지 않고, MFA DB에 이미 계산된 `words/phones` 시간과 라벨을 기존과 같은
4-tier 파일에 기록하는 I/O 경로만 바꾼다.

pre-MFA CSV의 `pron_reference_form`은 MFA 입력을 안정화하기 위한 층이다.
우리말샘 통합 사전의 예외 발음과 형태소별 철자 로마자·규칙 발음은 검색용
CSV/Parquet 층에서 출처를 분리해 결합한다. MFA가 끝났다고 사전 예외 발음이나
수동 실현 판정이 완성되는 것은 아니다.

## 2020 실측에서 확인한 병목

2020 전 단계는 약 29시간 걸렸다.

| 단계 | 실측 |
|---|---:|
| 전량 pre-MFA CSV | 42분 |
| lab 입력 검증 | 12분 |
| 코퍼스 설정·G2P·MFCC·그래프 | 7시간 27분 |
| 실제 alignment | 1시간 7분 |
| interval 수집 | 1시간 37분 |
| MFA raw TextGrid export | **15시간 57분** |
| 4-tier merge | 1시간 43분 |
| 정리 | 11분 |

2020의 결정적 병목은 정렬 자체가 아니라 raw TextGrid 내보내기였다. MFA는 큰
네 batch를 `multiprocessing.Queue`에 넣고 고정 1초 뒤
`finished_adding`을 설정했다. 큰 Python dict의 feeder 직렬화가 아직 끝나지
않은 동안 worker가 `get(timeout=1)`에서 `Empty`를 받고 종료할 수 있었다.
실제로 네 worker 중 하나만 batch를 받아 약 16시간 동안 사실상 직렬로
866,196개를 썼다.

이를 다음처럼 고쳤다.

- worker: timeout+event 추측 대신 blocking `get()`
- producer: worker 수만큼 `None` sentinel 전송
- direct 모드: MFA가 interval을 DB에 모은 뒤 raw 2-tier 중복 export 생략
- 프로젝트 exporter: DB `words/phones` + 기존 형태소 경계 + 동결 CSV form을
  한 번에 4-tier로 작성
- partial staging 전수 검증 뒤 연도 디렉터리 단위 승격
- 기본은 DB 보존, 명시적 옵션이 있을 때만 성공 후 정리
- 1분 heartbeat JSONL에 단계·PID·CPU·카운터·D: 여유·stderr 끝줄 기록

순정 동작이 필요한 경우에는 direct 옵션을 빼면 sentinel로 고친 기존
`MFA raw export → 기존 merge` 경로가 그대로 남는다.

## 2021–2025 입력 읽기 전용 감사

동결 입력:
`D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725`

| 연도 | 검색행 | 세션 | WAV | 예상 usable lab | 현재 lab | 실행 전 자동 조치·주의 |
|---|---:|---:|---:|---:|---:|---|
| 2021 | 1,373,920 | 4,143 | 1,416,216 | 1,373,521 | 1,373,335 | 누락 186 생성, 내용 불일치 38,320 원자 재작성 |
| 2022 | 866,359 | 2,654 | 878,157 | 866,106 | 0 | 전량 lab 생성 |
| 2023 | 677,262 | 1,973 | 677,397 | 676,232 | 0 | WAV 누락 923은 입력 제외·추적 |
| 2024 | 728,257 | 3,227 | 728,281 | 728,235 | 0 | 전량 lab 생성 |
| 2025 | 587,121 | 2,927 | 587,174 | 587,107 | 587,110 | 누락 6 생성, 빈 입력의 stale lab 9개 archive |

공통으로 세션 하위폴더 구조가 존재하고 44 byte 미만의 치명적 WAV는 감사에서
발견되지 않았다. `wav_not_in_search_master`는 주로 빈 form 등으로 검색 입력에
들지 않는 원 음성의 존재를 뜻하며, lab이 함께 남아 있지 않으면 그 자체가
오류는 아니다.

과거 PCM 감사에서 추적할 source 위험은 다음과 같다.

| 연도 | 알려진 source 위험 |
|---|---|
| 2021 | PCM 없음 1, 원본 짧음 1,091, 과거 hard-align이었으나 원본 정상 28 |
| 2022 | PCM 없음 15 |
| 2023 | PCM 없음 574 |
| 2024 | PCM 없음 1 |
| 2025 | PCM 없음 11 |

이 수치는 전량 실행을 막을 이유는 아니지만, 사후 `lab − TextGrid` 누락
inventory를 만들 때 source 결함과 난정렬을 분리하는 근거다.

### 2021 lab 전수 내용 비교

- 동결 CSV 기준 usable lab: 1,373,521
- 현재 nonzero lab: 1,373,335
- 내용 일치: 1,335,015
- 내용 불일치: 38,320
- 누락: 186
- `pron_reference_form`이 구 form과 달라진 행: 38,529

불일치는 대부분 새 reference-form 계약 도입에 따른 예상 변경이다.
`realign_eojeol_build_corpus.py`가 이를 검사하고 원자 재작성한다. 현재 lab을
무조건 신뢰하거나 수동으로 먼저 지우지 않는다.

### 연도별 특이점

- 2023: 검색행에 해당하는 WAV 누락 923개가 있어, 완료율 분모와 누락 원인을
  별도 기록해야 한다. PCM 없음의 세션 집중도도 다른 연도보다 높다.
- 2025: 현재 입력이 빈 9개 발화에 구형 lab이 남아 있다. 실행기가
  `archive_stale_labs/<input-contract>/...`로 옮긴 뒤 MFA 입력에서 제외한다.
- 2025 `speaker_missing` 1,082는 검색 메타데이터의 화자 정보 문제이며 음성
  정렬 자체의 차단 조건은 아니다. 후보 검색·대화상대 분석 전에는 보완 대상이다.

## 실자료 파일럿 결과

### 3,330발화

- 8개 세션, MFA exit 0
- TextGrid 3,330/3,330
- sentinel 적용 raw export 파일 쓰기 약 4초
- 기존 merge와 DB 직접 4-tier를 전수 비교
- tier 이름·라벨·모든 interval 시작/끝 불일치 0

### 21,965발화

- 50개 세션, 실제 MFA 24분 46초
- 정렬 성공 TextGrid 21,962, 난정렬 3, coverage 99.9863%
- sentinel 적용 raw export 쓰기 약 27초
- 기존 built-in export+merge와 DB 직접 4-tier 21,962개 전수 비교
- 누락 차이 0, tier/라벨/시간 불일치 **0**

병렬 direct exporter의 새 출력 폴더 실측은 다음과 같다.

| 방식 | 21,962개 4-tier 생성 |
|---|---:|
| 초기 direct exporter | 약 220초 |
| 세션별 CSV 로딩 + 4 worker | **73.983초** |

병렬 결과를 다시 기존 built-in 경로와 비교해 21,962/21,962가 동일했다.
이는 direct 경로가 새로운 발음 판정을 만들지 않고 기존 정렬 결과를 같은
TextGrid 구조로 직렬화한다는 실증이다.

## 예상 시간과 절감 범위

2021은 2020 usable 입력의 약 1.58배다. 2020 실측을 단순 비례시키되 새
내보내기의 대규모 D: I/O 변동을 보수적으로 반영하면 다음과 같다.

| 구간 | 2021 예상 |
|---|---:|
| lab 확인·재작성 | 20–40분 |
| 설정·G2P·MFCC·그래프 | 11–13시간 |
| alignment | 1.5–2.5시간 |
| interval 수집 | 2–3시간 |
| direct 4-tier 출력·전수 gate | 1.5–3시간 |
| 합계 | **약 18–23시간** |

기존 2020 방식의 16시간 raw export와 별도 merge를 2021에 그대로 비례시키면
내보내기 이후만 25시간 이상이 될 수 있다. direct 경로는 raw 2-tier 수백만
파일을 먼저 쓰고 다시 읽는 중복 I/O를 제거하므로 2021에서 대략 20시간 이상의
낭비를 피할 가능성이 있다. 다만 전량 실측 전의 ETA이므로 범위를 좁혀
보고하지 않는다.

## 안전·복구 정책

1. `-UseDirectDbExport`를 쓸 때만 설치 패치의 skip flag를 자식 MFA 프로세스에
   전달한다. 기본 MFA 동작은 유지된다.
2. DB direct 출력은
   `07_textgrid_eojeol_g2p_staging\_partial_direct_db\<contract>\<year>`에 쓴다.
3. 99% coverage, hard failure 0, 모든 source utterance accounting을 통과해야
   최종 staging 연도 폴더로 이동한다.
4. 실패하면 DB와 partial을 보존하고 다음 연도로 진행하지 않는다.
5. 첫 2021은 DB를 보존한다. QC 후 용량을 회수할 때만
   `-CleanupDirectDbAfterMerge`를 다음 실행 정책에 채택한다.
6. 기존 `06_textgrid_eojeol`, 원 WAV, 동결 CSV는 덮어쓰지 않는다.
7. 설치본 수정 전 소스는
   `archive/mfa_install_patches/`에 SHA256 manifest와 함께 보존한다.

## 2021 GO/NO-GO 게이트

2026-07-26 23:23 최종 preflight:

- FAIL 0 / WARN 0
- MFA 3.4.0 패치 검사 10/10
- acoustic/dictionary/G2P 모델 존재
- D: `DATA_SSD`, 여유 319GB ≥ 55GB
- C: 48.5GB, direct 신규 작업에는 사용하지 않음
- search master build success
- 2021 세션 coverage 4,143/4,143
- 2021 temp/output/staging/marker 없음

따라서 오전 시작 판정은 GO다. 다음 조건이면 시작하지 않는다.

- D:를 쓰는 복사·Dropbox 대량 이동·다른 MFA·KOINA가 실행 중
- D: 여유가 55GB 미만
- 노트북 절전 또는 SSD 연결 해제 가능성
- preflight가 하나라도 FAIL

## 실행 중 확인

```powershell
# wrapper 요약
Get-Content `
  "C:\Users\ari30\research\2026_summer_research\logs\pre_mfa_bulk_pre_mfa_v1_20260725_latest.json"

# 1분 단위 구조화 하트비트(가장 최근 2021 실행)
$hb = Get-ChildItem "D:\mfa_eojeol\logs\mfa_2021_*_heartbeat.jsonl" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content $hb.FullName -Tail 5

# MFA stderr
Get-Content "D:\mfa_eojeol\logs\mfa_2021_stderr.log" -Tail 80
```

하트비트가 보이지 않는다고 원본·temp·marker를 수동 삭제하지 않는다. 실패 시
로그와 DB/partial 보존 상태를 먼저 확인하고 같은 입력계약으로 재개한다.

## 근거 산출물

- `outputs/reports/AUDIT_mfa_year_readiness_2021-2025_20260726.json`
- `outputs/reports/AUDIT_mfa_year_readiness_2021_content_20260726.json`
- `outputs/reports/COMPARE_mfa_builtin_vs_db_4tier_3330_20260726.json`
- `outputs/reports/COMPARE_mfa_builtin_vs_db_4tier_21962_20260726.json`
- `outputs/reports/COMPARE_mfa_builtin_vs_db_parallel4_21962_20260726.json`
- `outputs/reports/BENCH_mfa_db_direct_parallel4_fresh_21965_20260726.json`
- `outputs/reports/VERIFY_mfa_install_after_direct_db_patch_20260726.json`
- `logs/preflight_20260726_232316.log`
