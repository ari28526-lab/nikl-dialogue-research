# 런북: 어절 전량 재정렬 — 2026-07-16 역사 기록

## 왜 (문제 진단)
기존 정렬은 `.lab`을 **형태소 단위**로 넣어(make_labs), MFA가 형태소마다 따로 G2P →
phone 라벨이 **고립형**이 됨. 실측: 발화 `저는 여행 다니는 것을`의 `것을`이
`k ʌ t̚ ɨ ɭ`=**[걷을]**로 정렬됨(어절 G2P 입력 [거슬]과 다름). 이 구조는
형태소 경계 주변의 음성 구간을 연구자가 찾고 검토하기에 부적합했다.

원인: "words tier를 형태소로" 하려고 형태소를 MFA에 그대로 먹였는데, 그러면 분절뿐
아니라 **발음(음소정보)까지 형태소 고립형**이 됨. 의도는 "어절 연결발음 + 형태소 정보".

## 무엇 (목적 B — 사용자 확정)
**한 파일에 4-tier**로 재생성:
| tier | 내용 | 출처 |
|---|---|---|
| words | **어절** | 신규 어절 MFA |
| phones | G2P 사전으로 정렬된 대략적 음소 라벨·시간(것을→거슬) | 신규 어절 MFA |
| morphemes | **형태소 경계** | 기존 `06_textgrid_merged` words tier 재사용 |
| utterance | form | 01_bareun_raw |
- 신규 결과는 먼저
  `D:\20_AUDIO\07_textgrid_eojeol_g2p_staging`에 쓴다. 기존 비G2P
  `06_textgrid_eojeol`과 `06_textgrid_merged`는 **읽기 전용 보존**한다.
  staging 전수 검증 뒤 기존 연도 폴더를 archive하고 별도 승격한다.

## 어떻게 (파이프라인, 재사용)
`.lab`만 형태소→**어절**(form 표층, 어절별 한글만)로 바꾸고 나머지는 기존 파이프라인 재사용.
**★ lab은 원래 make_labs처럼 wav 옆에 '제자리' 생성(하드링크 없음)** — 하드링크 코퍼스는
USB에서 느려 폐기(원래 정렬이 <3일이던 비결이 제자리 lab이었음).
스크립트(리포):
- `scripts/python/realign_eojeol_build_corpus.py` — form→어절 lab을 **wav 폴더에 제자리** 생성
  (코퍼스 = `03_wav/individual/{y}` 그대로)
- MFA: `mfa align D:\20_AUDIO\03_wav\individual\{y} korean_mfa korean_mfa out --num_jobs 4 --no_tokenization --clean --temporary_directory C:\mfa_tmp --output_format long_textgrid` (모델·사전=1차와 동일 korean_mfa v3.0; **temp는 C: SSD** — 아래 가속 결정 참조)
- `scripts/python/realign_eojeol_merge_output.py` — MFA출력+기존 형태소경계 →
  staging 4-tier
- 러너: `scripts/run_eojeol_realign.ps1 -Year 2020`
  (선택 연도 lab→align→검증→staging merge, JSON 완료 마커로 재개)
- 2020 전량 실측에서 주 병목은 정렬 자체가 아니라 MFA raw TextGrid export
  15시간 57분이었다. 2026-07-26 DB 직독 4-tier 경로를 3,330개와
  21,962개 실자료로 전수 대조해 라벨·시간 불일치 0을 확인했으며, 2021부터
  `-UseDirectDbExport`를 권장한다. 보수적 long_textgrid 경로도 fallback으로 유지한다.

## 실행 (밤샘)

> 2026-07-26 현재는 아래 단독 명령보다
> `RUNBOOK_pre_MFA_bulk_safe_2026-07-25.md`의
> `run_pre_mfa_bulk_safe.ps1`을 사용한다. 새 실행기는
> `pron_reference_form`이 포함된 pre-MFA CSV를 먼저 동결하고 lab·temp의
> 입력 계약을 검증한 뒤 이 연도별 러너를 호출한다.

```powershell
# 리포 루트에서
powershell -ExecutionPolicy Bypass -File scripts\run_eojeol_realign.ps1 `
  -Year 2021 -SearchMasterRoot `
  "D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725" `
  -PreferD -UseDirectDbExport
```
- 한 연도씩 실행한다. 중단 시 같은 명령을 재실행하면 검증된 JSON 완료 마커와
  temp 상태를 확인해 이어간다.
- 로그: `D:\mfa_eojeol\logs\`. **도는 동안 D: 읽는 다른 작업 금지(경합).**
- 완료 후에도 신규 파일은 staging에 있으며 기존 `06_textgrid_eojeol`은
  바뀌지 않는다. 전수 검증·archive·승격은 별도 단계다.
- direct 경로의 첫 전량 연도는 alignment DB를 기본 보존한다. QC 전에
  `-CleanupDirectDbAfterMerge`를 붙이지 않는다.

## 2026-07-26 export 병목 교정과 DB direct 경로 확정

2020에서 네 export worker 중 하나만 살아 866,196개 raw TextGrid 쓰기에
15시간 57분이 걸린 원인은 큰 queue batch의 feeder 직렬화와 고정 1초
`finished_adding` 종료 조건의 경쟁이었다. worker를 blocking `get()`으로,
producer를 worker별 `None` sentinel로 바꿨다.

더 큰 절감은 이미 MFA SQLite에 수집된 word/phone interval을 직접 읽는
경로다. 이 경로는 기존 `write_4tier`를 그대로 사용하고, partial staging을
99% coverage·hard failure 0으로 검증한 뒤에만 연도 폴더를 이동한다.
3,330개 및 21,962개 실자료에서 기존 built-in export+merge와 모든 tier
라벨·interval 시간이 같았다. 세션별 CSV 로딩과 4 worker 적용 뒤
21,962개 생성은 73.983초였다.

실패 시 SQLite DB와 partial은 보존되고 다음 연도로 진행하지 않는다.
상세 근거는
`AUDIT_remaining_MFA_years_and_direct_DB_export_2026-07-26.md`에 있다.

## 사전검증 (2026-07-16, 통과)
문법·임포트 OK / form_to_lab 어절 정상(것을 한 토큰) / 기존 형태소경계 파싱 OK.
한계: 숫자·외국어 어절은 lab에서 제외(기존 make_labs와 동일 동작, 회귀 아님).

## 아카이브 재활용 검토 — 재활용 불가 확정 (2026-07-16 아침)
"2020~2024는 예전에 어절로 정렬했으니 재활용하면 되지 않나?"를 실물로 검토한 결과:
- **실제 정렬 산출물 2개 모두 phones가 형태소 고립형**:
  - 현재 `20_AUDIO/05_mfa_output/2020` : 것을 phones = `k ʌ t̚ ɨ ɭ` = **[걷을]**
  - 아카이브 `90_ARCHIVE/06_textgrid_merged_구판_2020`(6-tier: words/phones/form/
    pronunciation/morphs/speaker) : 것을 phones = **[걷을]** (동일)
- **구판의 `pronunciation` tier엔 연결발음이 텍스트로 존재**: 것을 = `G EO S EU L`
  = **[거슬]**. 즉 어절 연결발음을 *계산은* 했으나(사용자 기억의 근거), **시간정렬은
  안 된 텍스트**일 뿐. 시간정렬된 phones는 2020~2024도 형태소 고립형.
- 옛 lab(`04_00_04_mfa_input_구식`)·`00_이전시도`는 USB에서 파일 접근조차 타임아웃날
  만큼 느려 전수 확인 불가했으나, **실제 정렬 산출물 2종이 모두 고립형**이므로 결론 불변.
- **결론**: 시간정렬된 연결 phones를 가진 재활용 가능 산출물은 없음 → **재정렬 불가피.**
  (재활용으로 시간 절약 불가. USB+585만 파일로 인해 전량은 multi-day, 하드웨어 한계.)
- 근본 가속은 **wav을 빠른 디스크로 이전(~290GB 필요)**뿐 — 별도 판단 대기.

## 가속 결정 (2026-07-17)
**SSD 구매 안 함**(사용자 결정, 비용) → 무료 가속만 적용 + 병목 실측 후 추가 판단:
1. **MFA temp → `C:\mfa_tmp`(SSD)**: MFA는 정렬 반복 중 wav이 아니라 temp의
   특징값(MFCC)·PostgreSQL DB를 계속 읽음 — USB에 두면 그게 병목. wav은 특징
   추출 때 1회만 읽음. 연도당 temp ~20-35GB, `--clean`으로 연도마다 비워짐.
   러너에 C: 여유 30GB 가드 추가(부족 시 중단).
2. **lab 생성 scandir 최적화**: 발화별 `exists()` 2-3회(각 USB 왕복, "12발화/s"의
   유력 주범) → 세션당 폴더 목록 1회. 510만 발화 기준 메타데이터 왕복 수백만 회 제거.
3. **Defender 제외 + 절전 해제**: `scripts/setup_mfa_speed_once.ps1` (관리자 1회).
   D:\20_AUDIO·D:\10_LAYERS·D:\mfa_eojeol·C:\mfa_tmp·miniforge3 제외.
4. **병목 계측 파일럿**: `scripts/run_pilot_bottleneck.ps1` — 2020 50세션(~5천 발화)
   복사본(D: 유지)으로 본 배치와 동일 설정 MFA를 돌리며 5초 간격 CPU%·디스크
   사용률 CSV 기록. **판정 규칙**: 정렬 구간 CPU ≥85% 지속 = CPU 병목(디스크
   대책 무의미, 남는 카드는 SAT off뿐 — 품질 대가라 비권장) / CPU 낮고 D: 바쁨
   = I/O 병목(→ C: 분기 청크 스테이징 검토). 발화/s 실측으로 본 배치 ETA 재계산.
- 검토했으나 보류: SAT(화자적응) off(~절반 절감이나 경계 정밀도 하락 — 길이 연구라
  비채택), 병합 MFA DB 직독(~1일 절감, 미검증 리스크), C: 스테이징(파일럿 결과 대기).

## 파일럿 1차 실패에서 나온 발견·교정 (2026-07-17 오전)
파일럿 1차: MFA가 시작 6초에 빈 코퍼스 에러 → conda run 래퍼가 안 죽고 78분 매달림.
원인 추적에서 나온 **사실 3건** (전부 실물 확인):
1. **wav 폴더 구조는 연도별 상이**: 평면=2020·2021·2025(확인) / 세션 하위폴더=2023(확인).
   문서·코드의 "2020-2024 세션 하위폴더" 가정은 틀렸음. lab 생성기·파일럿 구성기
   모두 양쪽 지원으로 교정(세션 우선→평면 폴백).
2. **★2025에 구판 make_labs_2025의 '형태소' lab이 제자리 존재**(예: "보 시 게 되 면 은").
   "이미 있으면 건너뜀" 로직이 이를 그대로 써서 **2025(58.7만)가 구판 lab으로 정렬될
   뻔함**(교정 대상 버그 재생산). → 2025만 1회 전량 덮어쓰기 + `.eojeol_labs_v2` 연도
   마커로 재개 보존. 2020-2024 구판 lab은 별도 폴더(04_00_04_mfa_input_구식)라 안전
   (2020 제자리 lab은 신판 어절식 실측 확인 — 사용자의 이전 lab 생성 실행분).
3. **conda run 래퍼 문제**: 출력 버퍼링(진행바 안 보임) + MFA 에러 시 래퍼가 안 죽고
   매달림. → 러너 2종 모두 `mfa.exe` 직접 호출로 전환(버전 3.4.0 직접 실행 확인).
부수 확인: Windows 디스크 성능 카운터 정상 작동(파일럿 CSV에 C: 활동 기록됨).

## 파일럿 판정 (2026-07-17 낮) — I/O 병목 확정
2차 시도(mfa.exe 직접 호출)는 OpenFST(`fstcompile`) PATH 미비로 즉사 → 러너가
env 경로(root/Library\bin/Scripts/bin)를 PATH에 프리펜드하도록 수정 후 3차 성공.
- **실측**: 21,965발화 / 1,542초 = **14.2발화/s** → 510만 발화 MFA만 **~4.2일**.
- **판정: USB I/O 병목** — 대부분 구간 D: 디스크 90~130% 포화(2~3MB/s = 소형파일
  랜덤 접근 특성), CPU 40~55%. 순수 정렬 연산 구간만 짧게 CPU 92% (temp=C: 덕에
  연산 자체는 빠름). temp 실측: 22K발화당 0.47GB → 연간 ~20-26GB(C: 감당 가능).
- **개선(적용)**: 필수 I/O(wav 1회 읽기 + 최종 4-tier 쓰기)만 D:에 남기고 **중간
  산출을 전부 C:로** — MFA 원출력 TextGrid를 `C:\mfa_eojeol_out`에 쓰고 병합이
  거기서 읽음(`--mfa-out`), 병합 성공 후 연도별 삭제. 완료 마커는
  `D:\mfa_eojeol\done\{y}.align_done/.merge_done`(영구, C: 정리와 무관하게 재개).
  기대: MFA 단계 ~20-25% 절감 + 병합 단계 대폭 단축 → **총 4일 안팎**.
- **불채택**: C: 청크 스테이징(로테이션) — 필수 wav 1회 읽기가 지배적이라
  한계효용 작고 복잡도·공간 곡예 큼. SSD 구매 없이는 이 이상 단축 수단 없음.
- **병합 평면 대응(중대 교정)**: MFA 출력도 평면 연도(2020·2021·2025)는 평면으로
  나옴 — 기존 병합은 세션 폴더만 훑어 **3개 연도가 조용히 0건**이 될 뻔.
  평면/세션 모두 지원 + 처리 0건이면 실패 종료로 교정(단위테스트 통과).

## 본실행 1차 실패 (2026-07-17 밤) — 원인 유실, 재발 방지 조치
- 경과: 2020 lab 생성 9h31m 완료(12:24→21:55, ~29발화/s) → MFA "Loading corpus from
  source files" 1h52m 만에 exit 1(23:47). 정렬 연산 진입 전. done 마커·출력 0.
  2020 어절 lab은 전량 확보(재실행 시 스킵 — 재개는 분 단위).
- 원인 분석(소스 대조): Ctrl+C 아님("Detected ctrl-c" 로그 없음). 코퍼스 파싱 **워커의
  실제 예외**가 `error_dict`로 수집돼 로딩 말미에 raise됨(acoustic_corpus.py). 단 MFA
  3.4는 traceback을 **자기 로그 파일이 닫힌 뒤 콘솔(stderr)에만** 출력 + command_history의
  exception 필드도 빈 값 → **콘솔이 닫히면 원인 복구 불가**(실제로 유실됨).
- **★백신 발견(중대)**: 이 PC의 실제 백신은 **AhnLab V3 365 Clinic**(활성)이고 Windows
  Defender는 비활성(수동) — `setup_mfa_speed_once.ps1`의 Defender 제외는 **무효였음**.
  수백만 소형 파일 I/O마다 V3 실시간 검사가 걸렸고, 게다가 로딩 도중(22:06) V3가 자체
  업데이트로 필터 드라이버를 재시작함(파일 I/O 오류 유발 가능 — 실패 용의 1순위.
  용의 2순위: MFA 로딩이 연도 전체를 RAM에 누적하는 구조 + 8GB).
- 조치: ① 러너 MFA 단계를 stderr 파일 캡처(`D:\mfa_eojeol\logs\mfa_{y}_stderr.log`)로
  전환 — 실패 traceback 영구 보존, 진행은 1분 하트비트(파일 끝 진행바 요약)로 표시.
  ② V3 검사 예외 등록은 사용자 액션(아래) — Defender 제외와 같은 6개 경로.

## 본실행 2차 실패 (2026-07-18 13:46) — 원인 확정: 0바이트 wav
stderr 캡처(1차 실패 조치)가 작동해 원인 즉시 확보:
`soundfile.LibsndfileError: SDRW2000000521.1.1.175.wav Format not recognised`
— 실물 확인 **0바이트**(2026-01-10 PCM→wav 변환 산물). MFA 3.4는 로딩 워커가
soundfile로 못 여는 wav를 만나면 그 파일만 건너뛰지 않고 **로딩 말미에 전체
raise**(파싱은 끝까지 진행 후 실패 — 5.5h 낭비 구조). 1차(7/17) 실패도 동일
원인으로 추정(당시 traceback 유실).
- V3 제외 효과 실측: lab 스킵 패스 9.5h→12분, MFA 로딩 파싱 5.5h에 완주
  (전날은 1h52m 시점 중단).
- 조치: ① `quarantine_bad_wavs.py` 신설 — 연도 wav 전수 크기 스캔(<44B 불량),
  `D:\mfa_eojeol\quarantine\{y}\`로 이동(짝 lab 동반, CSV 기록, 복원 가능).
  기본 dry-run, `--apply` 이동. 크기는 scandir 열거로 얻어 추가 I/O 없음.
  ② 러너 ExitCode 함정 수정(PS5.1 `-NoNewWindow -PassThru`는 핸들 미참조 시
  ExitCode 빈 값 → `$null=$p.Handle`+`WaitForExit()`). ③ 격리 후 재실행 —
  같은 유형 재발 시 stderr 로그가 파일명을 지목하므로 개별 격리로 대응.
- 주의: 격리된 발화는 TextGrid 미생성(기존에도 커버리지 99.44%였음 — 전수
  아님). 2021~2025도 각 연도 MFA 전에 동일 스캔 필요(러너 진입 전 1회 권장).

## 본실행 3차 중단 (2026-07-19) — ★1화자 사고 발견, SSD 이전과 통합 해결
3차(7/18 17:08~)는 로딩 9.4h 완주·MFCC 진입까지 갔으나, 로그에서
`Found 1 speaker across 870158 files` / `MFA will only use 1 jobs` 확인 —
**평면 코퍼스라 MFA가 연도 전체를 화자 1명으로 오인** → SAT·CMVN 무력화(품질)
+ 1job 강등(4배 느림). 파일럿은 세션 폴더 구조 복사본이라 못 잡았던 함정.
사용자 결정(7/19): 현 기기에서 2020 무리하지 않고, **SSD 이전 시 평면 연도를
세션 하위폴더로 물리 재구성**하여 근본 해결. 상세 절차·근거는
`RUNBOOK_SSD_migration.md`(정본). 러너에는 평면 가드 추가(재구성 없인 MFA 진입
불가). 구 기기 C:\mfa_tmp·C:\mfa_eojeol_out의 1화자 정의 산출물은 폐기.

## 본실행 4차 (2026-07-21, SSD+미니PC) — 로딩 극적 단축 + 신규 교착 사고
SSD 이전 후 2020 재실행: 코퍼스 로딩 **14분**(HDD 9.4h 대비 40배), 화자
2,231명 정상 인식(1화자 사고 완전 해소 확인), 실제 정렬(Viterbi) 2시간에
완주. 그런데 이후 **품질분석(analyze_alignments) 단계에서 교착상태** —
CPU 0·디스크 idle·로그 무갱신이 1.5시간+ 지속(job별 상세 로그로 실측 확인:
4개 워커 스레드가 동일 시각에 동시 정지). 원인: 이 파일에 있던 2026-07-12
패치(`try/except`로 품질분석 실패 시 건너뜀)는 **예외만 잡지 hang은 못
잡아** 무력화됨(7/19 "패치 없음" 판정은 확인 오류 — TODO 정정).
- **조치**: `align.py`의 `analyze_alignments()` **호출 자체를 제거**
  (align_corpus_cli·align_corpus_hf_cli 양쪽). 이 산출물(로그우도 등 품질
  지표)은 `realign_eojeol_merge_output.py`가 안 씀(TextGrid만 읽음) → 제거
  안전. **이 패치는 conda env 재설치 시 사라지므로 새 기기 셋업마다 재적용
  필수**(아래 "새 기기 셋업" 절 참조).
- **러너에 일반 교착 워치독 추가**: mfa/python 프로세스 누적 CPU가
  15분간 1초도 안 늘면 자동 강제종료 → 이어가기/--clean 재시도로 자동 복구.
  (stderr 텍스트 무변화만으론 오판 위험 확인됨 — 품질분석 단계는 "일하면서도
  몇 분씩 새 줄 없음"이 정상이라 CPU 실측 방식으로 설계.) 사람이 매번 붙어서
  확인할 필요 없이 자동 복구되도록 하는 것이 목적.
- 진단 순서(향후 유사 정지 의심 시 참고): ①stderr 하트비트 텍스트만 보지 말 것
  ②`Get-Process mfa,python`의 CPU 누적을 10초 이상 간격으로 두 번 재서 변화
  있는지 확인 ③의심되면 `C:\mfa_tmp\{year}\alignment\log\*.job.log`류 개별
  워커 로그의 최종 타임스탬프 대조(집계 로그보다 신뢰도 높음).

## ★2020 MFA 정렬 완주 + 병합 버그 발견·수정 (2026-07-21, SSD+C:workDrive)
analyze_alignments 제거 패치 적용 후 2020 재실행: 로딩 14분 → 정렬 준비
72분 → 그래프 컴파일 6분 → **실제 정렬(Viterbi) 57분 완주**(869,132/869,733,
오류 601건=0.07%, WinError 1314 심볼릭링크 권한 경고는 무해·정렬에 영향
없음) → alignments 수집 → **export까지 전부 통과, MFA align 최초 완주**.
- **병합(3/3) 단계에서 신규 버그 발견**: `realign_eojeol_merge_output.py`의
  `load_forms` 호출이 세션 CSV를 모을 때 `_`로 시작하는 파일을 안 걸러서
  `_speakers.csv`(화자 메타데이터: id/age/sex/...— form 컬럼 없음)를 세션
  파일로 오인 → `KeyError: 'form'`. **6개년 전부에 `_speakers.csv` 존재
  확인** — 미수정 시 2021~2025 병합도 전부 같은 지점에서 실패했을 구조적
  버그. 조치: glob에 `if not p.name.startswith("_")` 필터 추가(다른
  스크립트들의 기존 관례와 통일). 실데이터 재검증 통과(870,437 form 로드,
  세션당 ~200/s로 TextGrid 생성).

## ★G2P 부재 발견 (2026-07-23) — 2020·2021 산출물 핵심 목적 달성 여부 의심
2020·2021 완료 후 QC 표본 4건(wav+TextGrid+CSV 원본) 사람 검토 요청 → phones
tier 열어보니 어절의 **30~75%가 실제 음소 없이 "spn"**(placeholder)로 채워짐.
- **원인**: `korean_mfa.dict`가 고정 21,009단어뿐. 실측: "여행"(사전 있음)은
  정상 음소, "것을"·"다니는"(활용형, 사전 없음)은 전부 spn. 한국어 교착어
  특성상 활용형이 무한히 많아 고정 사전 커버리지가 근본적으로 부족 — G2P
  모델 없이 `mfa align`을 돌리면 OOV는 그냥 버려짐(형태소 고립형 문제를
  고치려던 이 프로젝트의 핵심 대상인 활용형이 하필 가장 취약함).
- **확인된 해결책**: `mfa model download g2p korean_mfa`(v3.0.0, 사전·음향모델과
  버전 일치) + `mfa align ... --g2p_model_path korean_mfa` 추가.
- **합의된 절차**: 전체 재작업 전 소표본(몇백 발화) 파일럿으로 ① spn 비율
  감소 확인 ② 활용형 연음 품질(것을→거슬 등) 확인 → 검증 후 2020·2021 포함
  전체 재작업 여부 결정. **아직 파일럿 미실행**(발견 직후 발화단위 발음정보
  이슈로 전환, 아래 참조).
- 교훈: 이번 주 내내 확인한 "성공"은 전부 실행 완료(exit 0·파일 수·구조)
  기준이었고 **음운론적 내용 검증은 이번이 처음** — 앞으로 방법론 전환 시
  소표본 **내용** 검토를 먼저 하는 것으로 원칙 변경(TODO_A단계.md 참조).

## 발화 단위 발음정보 레이어 부재 + 1기 산출물 재발견 (2026-07-23)
G2P 조사 중 사용자가 "발화별 CSV에 발음도 있는 줄 알았다"고 문제 제기 →
확인 결과 `01_bareun_raw`는 형태소 분석뿐, `morpheme_freq_dictionary.csv`의
roman/roman_mfa/ipa는 형태소 타입별 1행(토큰 검색 불가). **1기(작년 겨울)
`01_nikl_dialogue_enriched.csv`(4.7GB, Google Drive)에 발화단위 pronunciation·
form_roman·morphs_roman·화자정보 전부 있었음을 1기 노트북
(`reference/colab_search/60_search_dialogue_corpus/61_dialogue_context.ipynb`)
분석으로 확인** — 이 기기는 G: 미연결이라 실물 미확인(클라우드라 안전 추정).
한계: 2025 미포함(1기는 겨울~3월), 구버전 바른, 발음이 1기 449만 발화 정렬
산출물이라 동일 G2P 검증 필요. 1기 워크플로우 구조 참고: 30(사전 규칙기반
후보 예측)→40(빈도)→50(서울코퍼스 실현 대조)→60(대화코퍼스, 사람이 청취
판정) — `utils_phonology.py`가 핵심 규칙 엔진, B2 검색 스크립트 설계에 참고 가능.
당시 결정 기록: 2025+최신 바른 재분석 검토, "예측 발음열"+"MFA phones·시간정보" 이원
구축, Google Drive CSV를 SSD로 백업 예정. 바른 유료 해지는 보류.

## 사전 점검 (2026-07-21, 2020 완주 직후 — 남은 2021-2025 리스크 선제 확인)
`_speakers.csv` 사고 계기로 나머지 연도에서 재발할 만한 것들을 미리 훑음:
- **다른 CSV glob 코드 전수 감사**: 리포 내 `RAW.glob("*.csv")` 유형 호출
  13곳 전수 확인 — `realign_eojeol_merge_output.py` 외 **전부 이미
  `if not p.name.startswith("_")` 필터 보유**(build_pilot_corpus·
  build_freq_dictionaries·merge_textgrid_v2·retrofit_textgrid_2020_2024·
  validate_with_multilayer 등). 딱 이 파일 하나만 예외였고 이제 수정 완료
  — 동일 유형 재발 없음 확정.
- **WinError 1314(심볼릭링크 권한) 무해 확인**: MFA 소스
  (`alignment/multiprocessing.py` symlink_to 호출부)에 이미
  `except OSError: shutil.copyfile(...)` 폴백이 있어 실패해도 파일 복사로
  대체됨 — 데이터 손실 아님, 조치 불필요(매년 반복돼도 무시 가능).
- **연도별 규모 격차 확인**(wav 실측, 세션 재구성 후):
  2020 870,158 · **2021 1,416,216(2020의 1.63배, 최대)** · 2022 878,157 ·
  2023 677,397 · 2024 728,281 · 2025 587,174 (합 515만대 — 문서상 "585만"과
  약간 차이, 계수 기준 차이로 추정·중요하지 않음). **2021은 로딩·정렬 시간이
  2020(로딩 14분+정렬 57분) 대비 비례해 더 걸릴 것으로 예상**(로딩 ~23분,
  정렬 ~1.5h 안팎 추산) — 실패 아니니 오래 걸려도 정상. temp 용량은 C: 여유
  50GB 기준 여유(연도당 정리되므로 누적 없음, 2021도 30GB 미만 하강 없이
  안전할 것으로 추산).
- **★2020 최초 완주 확정**: MFA align 869,132/869,733 성공(오류 601=0.07%),
  병합 생성 869,132 / 건너뜀 0 / 실패 0 / 형태소tier없음 2. 목적지
  `D:\20_AUDIO\06_textgrid_eojeol\2020`에 TextGrid 869,132개 실물 확인,
  표본 파일 4-tier(words/phones/morphemes/utterance) 구조 정상. 어절 전량
  재정렬 파이프라인이 처음으로 연도 하나를 끝까지 완주(2020~2025 중 1/6).

## 2021 export 교착 + 워치독 오판 (2026-07-22)
2021 정렬(Viterbi)은 3.26시간 만에 완주(1,372,068/1,372,252, 오류 184=0.01%),
이후 **export_files 단계에서 4.5시간+ 무응답**. 원인 규명(job 로그+소스 대조):
- **진짜 원인**: `alignment/multiprocessing.py`의 export 워커가
  `construct_textgrid_output()`에서 예외 발생 시 `AlignmentExportError(
  output_path, ...)`로 보고하려는데, 예외가 **첫 yield 전**에 나면
  `output_path`가 아직 할당 전이라 `UnboundLocalError`로 **그 핸들러 자체가
  다시 죽음**. 스레드(USE_THREADING) 기반이라 이 죽음이 프로세스 전체를
  안 죽이고, 그 워커의 `finished_processing`만 영원히 안 켜져 메인 수집
  루프가 무한 대기(다른 3개 워커는 몫을 다 마쳐도 전체 종료 조건은 "4개 다
  끝남"이라 못 빠져나옴). **실제로 그 원인 파일 batch에서 무엇이 실패했는지는
  이 버그 때문에 한 번도 기록된 적이 없었음** — 패치 후 재실행에서 확인 예정.
- **패치**: `output_path = None`을 `try:` 직전에 초기화 — 이제 예외가 나도
  핸들러가 안 죽고 `AlignmentExportError`를 정상 기록(→`output_errors.txt`)
  하며 나머지 배치 처리를 계속함. 새 기기 셋업 시 이 패치도 함께 재적용 필요.
- **워치독 1차 설계(CPU 완전 무변화)도 이번에 무력화됨 확인**: 다른 스레드의
  미세한 폴링 때문에 60초마다 CPU가 1~2초씩 계속 늘어 "무변화"가 한 번도
  안 걸림(4.5시간 방치). → **누적 증가량 기준**(최근 15분간 CPU 증가 10초
  미만이면 교착)으로 교체. 노이즈보다 확실히 큰 문턱이라 오판 가능성 낮음.
- **작업드라이브를 연도별 재평가로 전환**: 기존엔 스크립트 시작 시 1회
  결정이라 2021처럼 큰 연도 도중 C: 여유가 40GB 밑으로 떨어지는 사례 발생
  (2021 temp 실측 33.3GB). 이제 연도마다 "기존 temp가 어느 드라이브에
  있는지"부터 확인(재개 우선), 없으면 그때 C:/D: 여유로 판단. 사고 조치로
  C:\mfa_tmp\2021(완주된 정렬 DB 포함, 33.3GB)을 D:\mfa_tmp\2021로 이동해
  재계산 3시간+ 손실 방지.

## 추가 예방 점검 (2026-07-22, 사용자 요청 — 재발 가능한 버그 선제 확인)
같은 유형(대용량 IN 쿼리, 워커 스레드가 예외로 죽어 메인이 무한 대기)이
다른 데도 있는지 MFA 전체 소스 훑음:
- **`.in_(` 전수 검색**(70곳+): 우리 파이프라인(`mfa align`, --subset 미사용)이
  실제로 타는 코드 중 코퍼스 크기에 비례해 커지는 건 `construct_textgrid_output`
  뿐(이미 수정). 나머지는 ①서브쿼리(파라미터 안 씀, 안전) ②사전/음소타입 등
  **크기 고정** 목록(어휘·enum, 안전) ③`--subset`·화자분리·전사 등 우리가 안 쓰는
  기능 전용 코드(도달 안 함) — 추가 조치 불필요.
- **export 워커 구조 강화**: `ExportTextGridProcessWorker.run()` 전체를
  try/finally로 감싸 **어떤 예외로 죽어도 `finished_processing`이 반드시
  찍히게** 함 — 특정 버그(output_path) 하나만 막는 대증치료가 아니라 "이
  워커가 죽으면 메인이 무한 대기"라는 구조적 약점 자체를 제거. 코퍼스 로딩
  워커(`corpus/multiprocessing.py`)는 원래부터 이 패턴이라 안전했음(대조 확인).
- `collect_alignments`(2021에서 2082초 걸린 벌크 삽입)는 별개의 공용 실행기
  `run_kaldi_function`을 씀 — 여러 기능이 공유하는 더 성숙한 코드경로라
  자체 조사는 낮은 우선순위로 보류(이미 2021 규모에서 실제로 성공 확인됨).

## 새 기기 셋업 시 필수 반영 사항 (2026-07-21 추가)
새 미니PC/노트북에 MFA를 새로 설치할 때 반드시 아래를 재적용:
1. `command_line/align.py`의 `align_corpus_cli`·`align_corpus_hf_cli` 두 곳
   에서 `aligner.analyze_alignments()` 호출을 제거(위 패치, 이유 상동).
2. `alignment/multiprocessing.py`의 `ExportTextGridProcessWorker.run()` —
   `output_path = None` 초기화 + **전체를 try/finally로 감싸
   `finished_processing.set()`을 finally에서 보장**(2026-07-22 패치 2건,
   이유 상동 섹션 참조).
3. `textgrid.py`의 `construct_textgrid_output`을 청크 래퍼로 분리
   (`_construct_textgrid_output_impl`로 원본 로직 이동, 50,000개씩 처리) —
   SQLite "too many SQL variables" 방지.
   순정 설치 직후엔 셋 다 diff 0 상태이므로 **매번 수동 재적용 필요** — 자동화
   스크립트 미작성(코드 몇 줄이라 저비용, 필요시 요청).

## 기기 이전 결정 (2026-07-18) — 외장 SSD + 상위 기기로 이전 예정
사용자 결정: 외장 SSD(1TB, USB 10Gbps급)를 구매해 **다른 노트북(삼성,
i5-1240P 12코어/16스레드, 16GB RAM, 내장 238GB)**에서 남은 배치를 잇는다.
- 근거: 현 병목은 USB HDD 소형파일 랜덤 I/O(2~3MB/s 포화, CPU 40~55% 유휴).
  SSD로 I/O 병목 제거 + CPU 4~6배 + `--num_jobs` 4→8 + RAM 16GB(로딩 RAM
  적재 여유) → 남은 전체 예상 4~5일 → **1~1.5일 수준** 기대.
- 복사 비용은 1회 반나절~하루(robocopy 멀티스레드): 이전 대상은 파이프라인
  필요분만 — `03_wav`(+제자리 lab 포함) · `06_textgrid_merged`(병합 형태소
  출처) · `01_bareun_raw` CSV · `mfa_eojeol`(done 마커·로그). 500GB 미만.
- **경로 무수정 이전**: 새 기기에서 SSD에 드라이브 문자 **D:** 부여 + 폴더
  구조 그대로 복사 → `config/paths.json`·스크립트 수정 불필요. lab·마커가
  함께 가므로 완료 연도는 자동 건너뜀(재개 보존).
- 되돌림 복사 없음: SSD를 데이터 정본으로 승격, 기존 USB HDD는 백업 강등.
- 절차: ① SSD 도착 전까지 현 기기 배치 계속 ② 도착 시 **연도 경계에서**
  중단(연도 도중 중단 시 그 연도 정렬 재시작) ③ 복사(중엔 D: 배치 금지)
  ④ 새 기기 셋업: 리포 clone·miniforge+mfa env+korean_mfa 모델·바른 venv·
  **그 기기 백신 검사 예외 등록** ⑤ num_jobs 8로 재실행.

## 남은 것
- [x] **V3 365 Clinic 검사 예외 등록(사용자)** — 2026-07-18 완료. 효과 실측:
  lab 스킵 패스 9.5h→12분, MFA 로딩 진행 가시화(~24발화/s 파싱).
  (가능하면 배치 중 V3 자동 업데이트도 꺼두기.)
- [ ] 외장 SSD 1TB 구매(사용자) → 도착 시 이전 절차 실행(위 결정 참조).
  Claude가 robocopy 복사 스크립트(검증·재개 가능)·셋업 체크리스트 작성 예정.
- [ ] `setup_mfa_speed_once.ps1` 관리자 실행(사용자, 1회) → 파일럿 실행 → 병목 판정.
- [ ] 배치 실행(사용자, 밤샘, 여러 날) → 커버리지 재확인.
- [ ] 완료 후 A6(fetch_audio)·검색이 `textgrid_eojeol`을 쓰도록 점검.
- [ ] METHODS 3.5에 이 교정 반영(1차=형태소 고립형 결함 → 어절 재정렬로 교정).
- [ ] (선택) wav 빠른 디스크 이전 검토(전량 재정렬 가속 유일 수단).
