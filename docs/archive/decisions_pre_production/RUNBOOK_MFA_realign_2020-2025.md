# 런북: MFA 정렬 실패분 재정렬 (역사 기록)

작성 2026-07-15. 대상: 1차 정렬에서 탈락한 **26,979발화**(wav 있음·TextGrid 없음)
를 빔 확대 재정렬로 회수. 결정 근거·수치는 METHODS 3.5 참조.

## 배경 진단 (2026-07-15 확인)
- 탈락 = wav 있으나 TextGrid 없음. 연도별: 2020 3,440 / 2021 1,709 /
  2022 452 / **2023 19,517** / 2024 629 / 2025 1,232 = **26,979**.
- (별개) 원본 음성 자체 없음 1,463(2020 세션1·2023 세션4)은 재정렬 불가 → 제외.
- **wav은 살아있음**: `D:\20_AUDIO\03_wav\individual\{연도}\{세션}\{발화}.wav`
  (2025만 평면 `individual\2025\{발화}.wav`).
- **.lab은 1차 정렬 후 삭제됨** → 재정렬 시 바른 원자료에서 재생성 필요.
- 실패 원인: 표본 lab 전부 정상(빈 lab 아님). 분포상 대부분 발화 단위
  정렬 실패(빔 협소) + 일부 세션 통째 실패(배치 중단, 2021 4세션) →
  **빔 확대 재정렬로 회수 대상**.

## 결정 (사용자 승인 2026-07-15)
- 범위: **6개년 전체**(26,979) 재정렬.
- 품질: 넓은 빔으로 최대 회수 후 `alignment_analysis.csv`(로그우도·음소길이
  편차 등)로 **사후 필터링** (이상치는 분석 단계에서 표시/제외, 정렬 자체는 유지).

## 코퍼스 구성 완료 (2026-07-15, Claude)
6개년 코퍼스 구성 끝 — **26,945발화**(wav 하드링크 + lab 재생성, 짝 전부 일치).
연도별(세션/발화): 2020 205/3,440 · 2021 443/1,698 · 2022 254/440 ·
2023 411/19,517 · 2024 358/629 · 2025 288/1,221.
빈 lab 34개(2021:11·2022:12·2025:11, 문장부호만) 자동 제외 = 정렬 불가분.
→ **다음은 사용자: 아래 2)~5)를 연도별로 실행** (1) 구성은 이미 완료).

## 파이프라인 (연도별 반복)
경로: 코퍼스 `D:\mfa_realign\corpus\{연도}` · 출력 `D:\mfa_realign\out\{연도}`

### 1) 코퍼스 구성 (lab 재생성 + wav 하드링크)
```powershell
$py = "C:\Users\ari30\Documents\Codex\2026-07-06\d\work\bareun-smoke\.venv\Scripts\python.exe"
& $py scripts\python\realign_build_corpus.py --year 2023
# 파일럿: --pilot-sessions 5  (실패 많은 상위 5세션만)
```

### 2) MFA 재정렬 (빔 100 / retry_beam 400)
> stderr 래핑 문제 회피: `2>&1`·`Tee-Object` 금지. `Start-Process`로 로그를
> 파일에 직접 받는다. `--output_format`은 반드시 **`long_textgrid`**.
```powershell
$conda = "C:\Users\ari30\miniforge3\Scripts\conda.exe"
$args = @('run','-n','mfa','mfa','align',
  'D:\mfa_realign\corpus\2023','korean_mfa','korean_mfa','D:\mfa_realign\out\2023',
  '--num_jobs','4','--no_tokenization','--beam','100','--retry_beam','400',
  '--clean','--output_format','long_textgrid')
Start-Process -FilePath $conda -ArgumentList $args -NoNewWindow -Wait `
  -RedirectStandardOutput "D:\mfa_realign\align_2023_out.log" `
  -RedirectStandardError  "D:\mfa_realign\align_2023_err.log"
```
- 모델·사전: korean_mfa v3.0 (1차와 동일 파일). `--no_tokenization` 유지
  (lab이 이미 바른 형태소 분할).
- 세션 하위폴더 = 화자 단위(1차와 동일 효과). `--speaker_characters` 불필요.

### 3) 품질통계 추출 (사후 필터용) — merge 전에!
```powershell
& $py scripts\python\realign_export_quality.py --year 2023
```
- MFA 3.4는 품질통계를 **작업DB `C:\Users\ari30\Documents\MFA\{연도}\{연도}.db`**
  에만 기록(CSV 자동 내보내기 없음). 이 스크립트가 뽑아
  `05_audio_index\alignment_quality_realign_{연도}.csv` 저장.
- ⚠ **align 재실행(`--clean`) 전에** 뽑아야 함(clean이 DB 초기화).
- `alignment_log_likelihood` NULL = 회수 실패분 → 자동 제외.

### 4) 표준 3-tier 변환·병합 (기존 정렬 보존, 회수분만 채움)
```powershell
& $py scripts\python\realign_merge_output.py --year 2023
```
- MFA 원출력 → `parse_mfa_textgrid` → `write_textgrid`(표준 v2)로
  `06_textgrid_merged\{연도}\{세션}\`에 기입. **기존 파일 미덮어씀**.
- 출력 형식이 기존 코퍼스와 동일함을 파일럿에서 확인(3-tier 일치).

### 5) 커버리지 재측정·기록
```powershell
# coverage_{연도}.csv 삭제 후 재생성(전수 재스캔) 또는 회수분만 반영
& $py scripts\python\coverage_inventory.py
```
- 회수 후 연도별 커버리지·회수량을 METHODS 3.5에 갱신.

## 파일럿 결과 (2023, 상위 5세션 732발화) — 2026-07-15
- **회수 692/732 = 94.5%** (미회수 40 = 정렬점수 NULL, 실제 난정렬 추정).
- 정렬 시간 107초(num_jobs 4, 빔 100/400). 형식·품질통계 전부 정상.
- 소견: 일부 발화 `phone_duration_deviation`가 비정상적으로 큼
  (예 1.12e6) — 넓은 빔이 억지로 맞춘 한계 정렬. **사후 필터로 걸러낼 대상**
  (예: duration_deviation 상위 이상치·낮은 snr·낮은 로그우도).
- 판단: **접근 유효 → 6개년 전체 진행**. 빔 100/400 유지.
- 검증 완료 항목: 코퍼스 구성(wav 하드링크+lab 재생성), 재정렬(94.5% 회수),
  품질통계 추출, 표준 3-tier 변환(기존 형식 일치).

## 최종 결과 (2026-07-16 실행 완료)
전 6개년 재정렬 + 잔여 재시도(빔 300/1000) 완료.

| 연도 | 원래실패 | 회수 | 남은 | 회수율 |
|---|---|---|---|---|
| 2020 | 3,440 | 3,426 | 14 | 99.6% |
| 2021 | 1,709 | 589 | 1,120 | 34.5% |
| 2022 | 452 | 437 | 15 | 96.7% |
| 2023 | 19,517 | 18,943 | 574 | 97.1% |
| 2024 | 629 | 628 | 1 | 99.8% |
| 2025 | 1,232 | 1,221 | 11 | 99.1% |
| **합** | **26,979** | **25,244** | **1,735** | **93.6%** |

→ **전체 커버리지 99.44% → 약 99.94%** (5,100,158 / 5,103,356).

### 남은 미회수 1,735개 분류 (정렬로 더 회수 불가)
- **깨진 wav 1,296** (2021: 1,092 · 2023: 200 등): 원본 개별 wav가 0.1초
  토막(1598 frames)으로 잘려 있음 — 정렬 대상 아님, **원본 재추출 필요**.
  - 특히 2021의 4개 세션이 통째로 깨짐(1,017발화):
    `SDRW2100003249`(260) · `SDRW2100001747`(258) ·
    `SDRW2100001872`(251) · `SDRW2100002153`(248).
  - 원 음성 추출(1기 파이프라인) 단계의 결함으로 추정. 1차 정렬에서도
    이 세션들이 통째로 실패했던 원인.
- **정상 wav 405**: 빔 300/1000에도 실패한 난정렬(OOV·소음·중첩·라벨불일치
  추정). 추가 빔 확대는 효용 낮음.
- **빈 lab / wav없음 34**: 문장부호만 — 회수 불가.

### 잔여 재시도 파이프라인 (이미 실행됨, 재현용)
```powershell
& $py scripts\python\realign_residual_build.py --year all      # 정상wav 미회수만 추출
# 각 연도 residual\{Y} 를 빔 300/1000 으로 align → residual_out\{Y}
& $py scripts\python\realign_residual_finalize.py --year all   # 병합+품질 append
& $py scripts\python\realign_summary.py                        # 최종 요약
```
⚠ 잔여 align은 코퍼스 leaf명이 연도와 같아 MFA 작업DB(Documents\MFA\{연도})가
본 실행 DB를 덮어씀 — 품질은 본 실행에서 이미 CSV로 저장돼 무손실. finalize가
잔여 회수분을 CSV에 append.

## 깨진 wav 1,296 — 원본 실측으로 재추출 불가 **확정** (2026-07-16)
원본 PCM(`00_RAW\dialogue_audio\modu_corpus_dialogue_audio\{year}_pcm\…`)을
발화별로 직접 실측(`check_source_pcm.py` + 연도별 표적 조회):

| 연도 | 깨진wav | 원본도 짧음(<0.3s) | 원본 정상 |
|---|---|---|---|
| 2020 | 3 | 3 (0.14~0.23s) | 0 |
| 2021 | 1,092 | 1,091 (0.1s) +PCM없음1 | 0 |
| 2022 | 1 | 1 (0.1s) | 0 |
| 2023 | 200 | 200 (0.1s) | 0 |
| **합** | **1,296** | **~1,295** | **0** |

- **원본 PCM 자체가 토막**(대부분 정확히 0.1s = 3,196 bytes). 개별 wav은 이
  PCM을 헤더만 씌운 것이라 wav도 0.1s. 즉 **우리 추출 버그가 아니라
  NIKL 배포본의 음성 원본이 잘려 있음.** 재추출해도 동일한 0.1s가 나옴 →
  **회수 불가 확정.**
- 특히 2021의 4개 세션(1,017발화, `SDRW2100003249/1747/1872/2153`)이
  세션 통째로 원본 결함. B단계 음성분석에서 이 발화군은 제외 대상.
- 근거 CSV: `05_audio_index\source_pcm_check.csv` (발화별 원본 길이·분류).

## 최종 회수 한계 (확정)
- 회수 **25,244 / 26,979 (93.6%)** = 정렬로 가능한 상한.
- 남은 1,735 = 원본 깨짐 1,296(재추출 무의미) + 난정렬 405(정상 wav이나
  빔 1000에도 실패, OOV·소음 추정) + 빈 lab 34. **추가 회수 실익 없음.**
- 전체 커버리지 **99.44% → 99.94%**. 잔여 0.06%는 원본·전사 한계.

## 주의
- D: 배치 중 D:를 읽는 다른 작업 금지(경합).
- 저사양 PC: 연도별 분할 실행·재개 가능. 2023(약 2만)이 최대 부하.
- 코퍼스 wav은 하드링크라 추가 용량 거의 없음. 완료 후
  `D:\mfa_realign`는 정리 가능(원본 wav은 individual에 그대로).
