# 런북: 어절(語節) 전량 재정렬 — phones 연결발음 교정 + 형태소 tier (2026-07-16)

## 왜 (문제 진단)
기존 정렬은 `.lab`을 **형태소 단위**로 넣어(make_labs), MFA가 형태소마다 따로 G2P →
phone 라벨이 **고립형**이 됨. 실측: 발화 `저는 여행 다니는 것을`의 `것을`이
`k ʌ t̚ ɨ ɭ`=**[걷을]**로 정렬됨(연음 [거슬] 아님). **형태소 경계를 넘는 음운현상
(연음·경음화·ㄴ첨가)이 phone 라벨에 안 담김** → 형태음운 변이(특히 ㄴ삽입) 분석 불가.

원인: "words tier를 형태소로" 하려고 형태소를 MFA에 그대로 먹였는데, 그러면 분절뿐
아니라 **발음(음소정보)까지 형태소 고립형**이 됨. 의도는 "어절 연결발음 + 형태소 정보".

## 무엇 (목적 B — 사용자 확정)
**한 파일에 4-tier**로 재생성:
| tier | 내용 | 출처 |
|---|---|---|
| words | **어절** | 신규 어절 MFA |
| phones | **연결 실제 발음**(것을→거슬) | 신규 어절 MFA |
| morphemes | **형태소 경계** | 기존 `06_textgrid_merged` words tier 재사용 |
| utterance | form | 01_bareun_raw |
- 결과: `D:\20_AUDIO\06_textgrid_eojeol`. 기존 `06_textgrid_merged`(형태소·구)는 **읽기
  전용 보존**(morphemes tier 소스 겸 "형태소 길이" 부차 레이어).

## 어떻게 (파이프라인, 재사용)
`.lab`만 형태소→**어절**(form 표층, 어절별 한글만)로 바꾸고 나머지는 기존 파이프라인 재사용.
**★ lab은 원래 make_labs처럼 wav 옆에 '제자리' 생성(하드링크 없음)** — 하드링크 코퍼스는
USB에서 느려 폐기(원래 정렬이 <3일이던 비결이 제자리 lab이었음).
스크립트(리포):
- `scripts/python/realign_eojeol_build_corpus.py` — form→어절 lab을 **wav 폴더에 제자리** 생성
  (코퍼스 = `03_wav/individual/{y}` 그대로)
- MFA: `mfa align D:\20_AUDIO\03_wav\individual\{y} korean_mfa korean_mfa out --num_jobs 4 --no_tokenization --clean --temporary_directory C:\mfa_tmp --output_format long_textgrid` (모델·사전=1차와 동일 korean_mfa v3.0; **temp는 C: SSD** — 아래 가속 결정 참조)
- `scripts/python/realign_eojeol_merge_output.py` — MFA출력+기존 형태소경계 → 4-tier → `06_textgrid_eojeol`
- 러너: `scripts/run_eojeol_realign.ps1` (연도별 lab→align→merge, 재개 가능: 연도 `.done` 마커)
- ETA: ~3~4일(제자리 lab). 병목=MFA 정렬 자체(줄일 수 없음). 추가 최적화 여지=병합을 MFA
  DB 직독으로(≈1일 절감, 단 리스크) — 현재는 검증된 long_textgrid 경로 사용.

## 실행 (밤샘)
```powershell
# 리포 루트에서
powershell -ExecutionPolicy Bypass -File scripts\run_eojeol_realign.ps1
```
- 연도별 순차. 중단 시 재실행하면 완료 연도(.done)·기존 산출 파일 건너뜀.
- 로그: `D:\mfa_eojeol\logs\`. **도는 동안 D: 읽는 다른 작업 금지(경합).**
- 완료 후: `06_textgrid_eojeol`가 음운변이 분석 주 레이어. paths.json `textgrid_eojeol`.

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
