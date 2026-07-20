# 런북: HDD→외장 SSD 이전 + 세션 구조 재구성 (2026-07-19 확정, 7/20 오후 실행)

## 왜 (두 결정의 통합)
1. **기기 이전** (7/18 결정): USB HDD 랜덤 I/O 병목 + N200 저사양 → 외장 SSD(1TB,
   10Gbps) + i5-1240P 노트북(16GB)으로. 남은 재정렬 예상 4~5일 → 1~1.5일.
2. **★1화자 사고** (7/19 발견): MFA는 화자를 **폴더 구조로 추론**(하위폴더 1개=화자
   1명). 평면 연도(2020 실측 87만 파일)는 연도 전체가 화자 1명으로 잡혀
   ① SAT·CMVN 무력화(경계 정밀도 하락 — "SAT off 기각" 결정과 모순)
   ② num_jobs 무관 1job 강등(4배 느림). 로그 증거:
   `Found 1 speaker across 870158 files` / `MFA will only use 1 jobs`.
   파일럿(50세션, 세션 폴더 구조 복사본)은 화자 50으로 정상 인식돼 못 잡았음.
   → 3차 시도(7/18 17:08 시작, 로딩 9.4h 완료·MFCC 초입) 7/19 중단.
3. **해법 = 물리 재구성**: `--speaker_characters` 우회 대신 **복사하는 김에 평면
   연도를 세션 하위폴더로 재구성**. 근거: ① 06_textgrid_merged가 6개년 모두 세션
   구조(7/19 실측)라 레이아웃 통일 ② 파일럿·2023과 동일 조건(세션=화자) ③ 연도별
   접두사 길이 차이 무관 ④ 영구적(옵션 실수 여지 없음). 세션 안에 실제 화자 2명
   안팎이 섞이는 한계는 있으나(파일명만으론 개인 분리 불가) 1그룹 vs 세션수천
   그룹의 차이가 결정적. 러너에 평면 가드 추가 — 재구성 없인 MFA 진입 불가.

## 무엇을 (스크립트, 전부 리포에 있음)
| 스크립트 | 역할 |
|---|---|
| `scripts/copy_hdd_to_ssd.ps1` | robocopy 복사(Tier1 필수분 우선, 재개 가능, 로그·검증) |
| `scripts/python/restructure_wav_sessions.py` | 평면 연도 wav/lab → 세션 폴더 이동(SSD에서 수 분, dry-run 기본, 멱등) — 합성 데이터 검증 통과 |
| `scripts/run_eojeol_realign.ps1` | 기기 무관 실행(홈 기준 miniforge, num_jobs 자동 4/8, 작업드라이브 자동 C:/D:, 평면 가드) |

Tier1(필수, ~350GB): `10_LAYERS` `20_AUDIO\03_wav` `20_AUDIO\06_textgrid_merged`
`20_AUDIO\06_textgrid_eojeol` `mfa_eojeol`(마커·로그·격리). MFA 모델
(`Documents\MFA\pretrained_models`)도 동봉. Tier2(선택, `-Tier2`): `00_RAW`
`05_mfa_output` `30_PHENOMENA` `90_ARCHIVE` — 안 옮기면 HDD가 백업으로 보존.

## 절차 A-0 — HDD 사전 정리 (7/19, 복사 전날 — 사용자 방침: "HDD를 최종 상태로
## 깔끔히 만들고 그대로 복사")
- [x] `03_wav\merged` 빈 폴더(구식 잔재) 삭제 (7/19).
- [x] **세션 재구성 HDD에서 완료** (7/19 밤, 사용자 콘솔 실행): 6개년 전부
  루트 잔여 0 감사 통과. 세션 수는 DATA_LAYOUT.md 참조값 표 참조.
- [x] 코드 사전 정비 (7/19): fetch_audio_for_search를 locate_utt 일원화로
  재작성(4-tier 우선·격리 표시, 3케이스 실검증) / 구식 스크립트 2종
  (make_labs_2025·realign_build_corpus) 재실행 금지 표기 / 복사 스크립트에
  `-Src` 추가 — **추후 SSD→HDD 역방향 백업에 동일 스크립트 사용**
  (`-Src D:\ -Dst {HDD문자}:\`, 추가/갱신만·삭제 미러링 없음).
- 참고: `D:\mfa_realign`(구 잔여분 재정렬 작업물)은 어절 전량 재정렬로 사실상
  대체된 중간물 — SSD 복사 대상 아님(HDD에만 남음). 삭제는 사용자 판단.
- HDD의 향후 역할: ① 원자료(00_RAW 등) 보존 백업 ② SSD 산출물의 주기적
  역복사 대상. 양방향 모두 `copy_hdd_to_ssd.ps1` 하나로 수행.

## 절차 A — 구 기기(N200)에서 (7/20 오후 1~2시 시작)
1. SSD 연결, 탐색기에서 드라이브 문자 확인(예: E:). NTFS 아니면 NTFS로 포맷.
2. V3 검사 예외에 SSD 드라이브(또는 E:\ 전체) 추가 — HDD 때 교훈.
3. 복사 (Tier1 반나절~하루, robocopy /MT:16; 재구성은 A-0에서 이미 끝났으므로
   순수 복사 — 말미의 자동 재구성 단계는 멱등 안전망으로 몇 초 만에 통과):
   `powershell -ExecutionPolicy Bypass -File scripts\copy_hdd_to_ssd.ps1 -Dst E:\`
   (여유 확인 후 원본까지: `... -Dst E:\ -Tier2`) — 끊기면 같은 명령 재실행(이어짐).
4. 복사 후 검증 출력(파일 수 대조)과 재구성 안전망 출력("루트에 wav/lab 없음")
   확인. 2020 기준 참조값: wav 870,158(원 870,162 − 0바이트 격리 4), 세션 ~2,232.
   전체 배치 규약·열람 요령은 `docs/DATA_LAYOUT.md` 참조 (00_RAW는 불변 —
   재구성 대상 아님, 원본 PCM은 연도별 폴더라 이미 열람 가능).
5. **드라이브 문자 고정 (7/20 사용자 지시 — HDD 상시 연결 대비 엉킴 방지)**:
   디스크 관리(diskmgmt.msc)에서 ① HDD(라벨 SAMSUNG)를 **H:** 로 변경
   ② SSD(라벨 DATA_SSD)를 **D:** 로 변경. 이후 체계:
   - **D: = SSD(정본, 라벨 DATA_SSD)** — 모든 파이프라인·경로의 기준
   - **H: = HDD(백업 전용, 라벨 SAMSUNG)** — 00_RAW 원본 보존 + 역복사 대상
   - 러너에 라벨 가드 있음: D:의 라벨이 DATA_SSD가 아니면 실행 거부(HDD 오인 방지)
   - 역복사(백업): `copy_hdd_to_ssd.ps1 -Src D:\ -Dst H:\` (추가/갱신만)
6. 복사 목록 참고: Tier1에 **00_RAW\dialogue_json 포함**(사용자 지시 7/20 —
   전사 JSON 원본은 SSD에도 동봉). 첫 복사가 json 추가 전에 시작됐으므로,
   완료 후 같은 명령 1회 재실행(기존 파일 스킵, json만 추가 복사).

## 절차 B — 새 기기(i5-1240P 노트북)에서
1. **OneDrive 함정 주의**: 문서·바탕화면이 OneDrive로 리디렉션돼 있으면 MFA 모델
   경로가 꼬임 — `docs/SETUP_다른기기_작업가이드.md`(A5) 참조.
2. SSD 연결 → 디스크 관리(diskmgmt.msc)에서 드라이브 문자를 **D:로 변경**
   → `config/paths.json`·스크립트 무수정 사용 가능.
3. 리포 clone: `git clone https://github.com/ari28526-lab/nikl-dialogue-research.git`
4. Python 3.13 설치(파이프라인 스크립트는 표준 라이브러리만 사용 — 바른 venv는
   이번 작업엔 불요. paths.json의 kofren·bareun 경로는 구 기기 전용이므로
   재정렬에는 무관, A단계 재작업 시에만 갱신).
5. miniforge 설치(기본 위치 `%USERPROFILE%\miniforge3`) 후:
   `conda create -n mfa -c conda-forge montreal-forced-aligner=3.4.0`
   MFA 모델: SSD의 `_migration\mfa_pretrained_models`를
   `%USERPROFILE%\Documents\MFA\pretrained_models`로 복사(버전 완전 일치 보장).
6. **이 기기 백신에 검사 예외 등록**(Defender든 타사든 — V3 교훈):
   `D:\20_AUDIO` `D:\10_LAYERS` `D:\mfa_eojeol` `D:\mfa_tmp` `D:\mfa_eojeol_out`
   `%USERPROFILE%\miniforge3`. 절전 해제(`scripts\setup_mfa_speed_once.ps1`의
   powercfg 부분 참조).
7. 실행: `powershell -ExecutionPolicy Bypass -File <리포>\scripts\run_eojeol_realign.ps1`
   → 자동으로 num_jobs 8, 작업드라이브 D:(SSD), 세션=화자. 평면 가드가 뜨면
   재구성 누락이니 4번(절차 A-4)을 SSD에서 재확인.

## 검증 체크리스트 (새 기기 첫 실행에서)
- [ ] 러너 로그에 `Found ~2,232 speakers`(2020, 연도별 세션 수) — **1 speaker면 중단**
- [ ] `num_jobs 8` 강등 경고 없음
- [ ] 로딩 시간이 HDD 대비 대폭 단축(참조: HDD 9.4h)
- [ ] 첫 연도 완료 후 `06_textgrid_eojeol\{y}` 표본 열어 4-tier·연결발음(것을→거슬) 확인

## 상태
- [x] 스크립트 3종 작성·구문 검증·재구성 합성 테스트 (7/19)
- [x] 구 기기 C:\mfa_tmp·C:\mfa_eojeol_out 옛 산출(1화자 정의 DB) 정리
- [ ] 7/20 오후: 절차 A (사용자)
- [ ] 절차 B → 배치 재개 (사용자, Claude 셋업 지원)
