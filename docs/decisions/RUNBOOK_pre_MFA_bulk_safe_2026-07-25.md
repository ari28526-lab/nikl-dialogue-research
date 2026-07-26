# pre-MFA 입력 동결과 전량 MFA 무인 실행 런북

작성: 2026-07-25

대상: 2020–2025 모두의 말뭉치 대화 발화

실행기: `scripts/run_pre_mfa_bulk_safe.ps1`

## 결론

MFA 설치와 데이터 배치는 현재 대량 실행 가능한 상태다. 그러나 기존
`run_eojeol_realign.ps1`을 그대로 실행하면 구 `form`에서 숫자·기호를 제거한
lab을 재사용할 수 있어, 지금 바로 MFA만 시작하는 것은 안전하지 않았다.

따라서 대량 실행은 다음 게이트를 반드시 한 묶음으로 통과한다.

```text
새 pre-MFA search master staging
  → pron_reference_form 기반 lab
  → 기존 lab 내용 전수 대조
  → 입력 계약이 다른 MFA temp 보존 격리
  → 연도별 MFA
  → 수량 검증
  → 4-tier staging 병합
  → 자동 승격 금지
```

## 2026-07-25 실제 사전점검

전체 6개년 preflight 결과는 FAIL 0, WARN 0이었다.

- MFA 3.4.0 프로젝트 패치 7종 통과
- `korean_mfa` acoustic/dictionary/G2P 모델 존재
- D: 볼륨 라벨 `DATA_SSD`
- C: 여유 47.5GB, D: 여유 333.3GB(13:10 재확인)
- 6개년 모두 세션 하위폴더 구조
- 신규 G2P staging에는 아직 연도별 정식 출력 없음
- 2020에 계약 정보가 없는 구 temp 0.68GB가 남아 있음

새 러너는 2020 구 temp를 삭제하지 않고 다음 아래로 옮긴 뒤 clean 시작한다.

```text
D:\mfa_eojeol\archive_stale_temp\<시각>\C\2020
```

## 왜 CSV를 먼저 한 번 더 만드는가

현재 정식 `D:\10_LAYERS\05_search_master`는 2026-07-23 구 schema 전량본이다.
발화 5,103,356행은 있으나 다음 새 열이 없다.

```text
pron_reference_form
pron_reference_source
pron_reference_status
dialogue_speaker_ids
co_speaker_ids
```

새 코드는 숫자·기호가 `form`에서 소실되고 JSON `original_form`이 그 자리를
더 잘 보존하는 경우에만 `pron_reference_form`을 채택한다. 읽기를 임의로
추측하지 않으며 미해결은 `unresolved_symbol`로 남긴다.

이 staging은 **MFA 입력을 동결하기 위한 pre-MFA v1**이다. 우리말샘
`lexicon_enriched + lexicon_legacy_pron`의 형태소별 예외 발음 결합이 아직
끝나지 않았으므로 최종 연구용 CSV라고 부르지 않는다. 다만 MFA의 철자/원전사
입력 계약에는 충분하며, 사전 예외 발음은 이후 CSV/Parquet 검색층에서 별도
출처로 결합한다.

## 실행 명령

전원 연결, 자동 절전 해제, D:를 쓰는 다른 복사·MFA·KOINA 작업 종료 후
프로젝트 루트의 PowerShell에서 다음 한 줄을 실행한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  "C:\Users\ari30\research\2026_summer_research\scripts\run_pre_mfa_bulk_safe.ps1" `
  -RunId "pre_mfa_v1_20260725" -PreferD
```

기본 순서는 2020→2021→2022→2023→2024→2025다. 2020 전량이 첫 확대
게이트다. 한 연도가 실패하면 다음 연도를 실행하지 않는다. 같은 명령을 다시
실행하면 같은 pre-MFA staging과 검증된 marker를 사용해 이어간다. 통과한
`_build_meta.json`이 있으면 동결 CSV를 다시 빌드하거나 meta 시각을 바꾸지
않는다. 입력 코드를 바꿔 새 CSV가 필요하면 기존 RunId를 재사용하지 않고 새
RunId를 쓴다.

2020만 먼저 끝내려면:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  "C:\Users\ari30\research\2026_summer_research\scripts\run_pre_mfa_bulk_safe.ps1" `
  -RunId "pre_mfa_v1_20260725" -Years 2020 -PreferD
```

여러 연도를 요청하되 특정 연도 완료 경계에서 정상 일시정지하려면:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  "C:\Users\ari30\research\2026_summer_research\scripts\run_pre_mfa_bulk_safe.ps1" `
  -RunId "새_RUN_ID" -PreferD -PauseAfterYear 2020
```

`-PauseAfterYear`는 지정 연도의 align·4-tier merge·marker·중간출력 정리를
모두 끝낸 뒤 멈춘다. summary는 실패가 아니라 `status=paused`,
`paused_after_year`, `paused_before_year`를 기록한다. 실행 중 새로 멈춰야
할 때는 run별 emergency pause 요청이 다음 연도의 config·temp 접근 전에
exit 75를 내고, wrapper가 이를 정상 pause로 해석한다.

## 생성 위치

새 pre-MFA CSV:

```text
D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725
```

MFA 상태·로그:

```text
D:\mfa_eojeol\done
D:\mfa_eojeol\logs
D:\mfa_eojeol\input_contracts
D:\mfa_eojeol\archive_stale_temp
```

새 4-tier TextGrid:

```text
D:\20_AUDIO\07_textgrid_eojeol_g2p_staging
```

통합 실행 기록:

```text
logs\pre_mfa_bulk_pre_mfa_v1_20260725_<시각>.log
logs\pre_mfa_bulk_pre_mfa_v1_20260725_latest.json
```

## 자동 차단 조건

- pre-MFA build status가 `success`가 아님
- 연도별 Bareun 세션 수와 pre-MFA CSV 수가 다름
- `pron_reference_form/source/status` 필수 열 누락
- D:가 `DATA_SSD`가 아님
- MFA 필수 패치나 모델 누락
- 연도 루트에 WAV가 직접 있어 전체를 한 화자로 오인할 위험
- 같은 입력 계약이 아닌 temp·완료 marker
- C:/D: 시작 여유 공간 부족
- MFA exit 0이지만 TextGrid 0건
- TextGrid/lab 정렬 coverage 99% 미만
- 4-tier 병합 한 건이라도 실패
- 같은 이름의 다른 배치가 이미 실행 중

2021은 temp 실측 최대 33.3GB였으므로 신규 작업 문턱을 55GB로 높였다.
다른 연도는 45GB를 요구하고, 검증된 resume temp는 남은 10GB를 하한으로
둔다.

현재 C: 47.5GB는 일반 연도 45GB 문턱을 통과하더라도 Windows·Dropbox·임시
파일을 위한 여유가 2.5GB밖에 남지 않는다. 이틀 무인 실행에는 충분히 보수적이지
않으므로 정식 명령은 `-PreferD`를 사용한다. 이 옵션은 다음처럼 작동한다.

- 신규 연도의 MFA temp와 MFA 원출력은 D:에 둔다.
- D:는 2021 포함 실행이면 55GB, 그 밖에는 45GB 미만일 때 preflight에서 FAIL한다.
- 같은 입력계약으로 검증된 resume temp가 이미 있으면 수시간 계산을 버리지 않도록
  그 temp의 원래 드라이브에서만 이어간다.
- 연도 정렬이 끝나면 해당 연도의 temp를, 4-tier 병합이 끝나면 MFA 원출력을
  정리하므로 여섯 연도의 중간산출이 누적되지 않는다.

용량 추정 근거는 기존 search master 4.19GB, 기존 TextGrid 5,000개 표본의
평균 3.03–4.38KB, 전량 5,103,356발화다. 새 언어층·4-tier staging과 한 연도
중간 peak를 보수적으로 합쳐도 D: 추가 사용량은 약 100GB 이내로 예상한다.
현재 D: 여유 333.3GB에는 200GB 이상의 완충 공간이 있다.

2026-07-25 13:10 실제 `-PreferD -Year 2021` 읽기 전용 점검에서
`D: 333.3GB >= 55GB`가 통과했다. 사용한 search master는 의도적으로 2020
파일럿만 있는 부분본이어서 2021 coverage 단계는 FAIL했다. 즉 이 실행은 D:
정책 검증만을 위한 음성·CSV 비변경 점검이며, 전량 입력 통과를 가장하지 않는다.

## 2020 전 단계 실측 결과 (2026-07-26)

`pre_mfa_v1_20260725`는 2020 한 연도의 CSV→lab→MFA→4-tier merge를
완주한 뒤 사용자 요청에 따라 2021 시작 전 일시정지했다.

- pre-MFA CSV: 5,103,356발화·17,156세션, build success
- usable lab 869,840 / MFA TextGrid 866,196 = 99.58%
- 기본+retry beam 난정렬 3,644
- 난정렬 차집합 3,644 ID를 CSV/JSON으로 고정; 215세션, WAV 3,644/3,644
- 4-tier created 866,196 / failed 0 / form·morpheme 누락 0
- 독립 전수 열거 866,196, 0바이트 0
- 네 tier 좌우 경계 표본 15/15 통과
- 2021 temp/output/staging/marker 모두 없음
- 기존 `06_textgrid_eojeol` 자동 승격·덮어쓰기 없음

가장 큰 병목은 worker 1개로 사실상 직렬 처리된 TextGrid export 약
15시간 57분이었다. 2021 전에 queue 종료 경쟁 조건, 영구 heartbeat,
원 MFA output 보존 정책, 3,644 실패 ID 부분 재시도를 먼저 다룬다.

상세 감사:
`AUDIT_2020_pre_mfa_full_pipeline_2026-07-26.md`.

## 오류·병목과 대응

| 위험 | 대응 |
|---|---|
| 숫자 `1` 등이 lab에서 사라짐 | `pron_reference_form` 우선, 미해결은 추측 금지 |
| 기존 nonzero lab을 무조건 신뢰 | 첫 계약 생성 때 실제 내용 전수 대조·불일치 원자 재작성 |
| 현재 입력이 한글 0자인데 과거 lab이 남음 | MFA가 stale 문장을 읽지 않도록 구 lab을 삭제 대신 `archive_stale_labs`로 이동 |
| 새 lab인데 과거 MFA temp 재사용 | SHA256 입력 계약 비교, 불일치 temp 보존 격리 |
| 부분 export를 성공으로 오인 | exit code와 실제 TextGrid 수를 함께 검사 |
| C: 여유 47.5GB가 실행 중 줄어듦 | 정식 명령은 `-PreferD`; 신규 6개년 temp/output 모두 D: |
| 워커 교착 | 단계·진행카운터·CPU 기반 watchdog, 실패 로그 영구 보존 |
| 0바이트 WAV가 로딩 말미에 전체 실패 | MFA 전 연도별 스캔·복원 가능한 quarantine |
| 병합 일부 실패 후 원출력 삭제 | 실패 1건이면 종료, 원 MFA 출력 보존 |
| 실행 중 두 번째 배치 시작 | PID lock |
| 새 결과가 기존 정본을 덮음 | 05/07 staging만 사용, 자동 승격 없음 |

## 발화를 이어 붙이는 분석

MFA 전량 정렬은 발화 단위로 유지한다. 세션 전체를 미리 이어 붙이면 중복 WAV,
좌표계 두 개, 겹침발화 직렬화, 원 세션 침묵 소실 때문에 검색 정본이 복잡해진다.

이어붙이기는 후보 추출 후 다음 용도로만 온디맨드 생성한다.

- 특정 발화 앞뒤 맥락 청취
- 같은 대화 참여자의 교대 확인
- KOINA/수동 검토용 짧은 연속 구간

새 G2P staging을 명시하는 예:

```powershell
& "C:\Users\ari30\miniforge3\envs\mfa\python.exe" `
  ".\scripts\python\stitch_session.py" `
  --around "SDRW2200000836.1.1.61" --window 8 `
  --tg-dir "D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2022" `
  --out "D:\mfa_eojeol\stitched_review"
```

이어붙인 시간은 원 세션 시간이 아니라 클립 연결 시간이다. 연구표에는 반드시
각 발화의 원 `utt_id`, 연결 시작·끝, 원 클립 길이를 manifest로 남겨야 한다.
발화 경계에 검토용 무음을 넣으면 그 길이도 좌표 환산 정보로 기록한다.

## 이틀 뒤 우선 확인

```powershell
Get-Content ".\logs\pre_mfa_bulk_pre_mfa_v1_20260725_latest.json"
Get-ChildItem "D:\mfa_eojeol\done" | Sort-Object Name
Get-Content "D:\mfa_eojeol\logs\mfa_2020_stderr.log" -Tail 80
```

`latest.json`이 `failed`면 다음 연도로 진행하지 않은 것이 정상이다. 실패 로그를
확인하기 전 marker나 temp를 수동 삭제하지 않는다. `passed`여도
`07_textgrid_eojeol_g2p_staging`을 정본으로 자동 승격하지 않고, 연도별
coverage·tier·duration·표본 청취를 먼저 수행한다.
