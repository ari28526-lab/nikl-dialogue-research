# 실행 순서 가이드 (제3자용) — 검색 마스터 완성 + 발음 레이어

작성 2026-07-23. **이 문서만 보고 순서대로 실행**하도록 정리(명령·확인·주의).
상세 배경·사고 이력은 `docs/decisions/RUNBOOK_MFA_eojeol_realign.md`.

## 전제·환경
- 리포: `C:\Users\ari30\research\2026_summer_research` (여기서 명령 실행).
- 데이터: **D:** (외장 SSD, 볼륨 라벨 `DATA_SSD`). Python 3.13 시스템,
  MFA는 conda env `mfa`(`%USERPROFILE%\miniforge3\envs\mfa`).
- **★황금률 1 — D: 배치는 한 번에 하나만.** CSV 생성·MFA·robocopy는 모두 D:를
  크게 읽는다. 둘을 동시에 돌리면 몇 배 느려지고 실패 위험(과거 실측).
- **★황금률 2 — 상태는 실측으로만.** 각 단계 뒤 로그/preflight로 확인.
  "됐을 것"으로 다음 단계 넘어가지 말 것.

## 0. 사전 점검 (약 1분)
```
python scripts\python\preflight_search_master.py
```
→ `logs\preflight_report.txt`에 **✅ 파일럿 진행 가능**이면 OK.
- reference 4종이 `[없음]`인 건 정상(1·3단계와 무관). 그 외 경로는 `[OK]`여야 함.

## 1. v1 검색 마스터 CSV 전량 생성 — 예측 발음열 (약 하룻밤, D: 단독)
```
python scripts\python\build_search_master.py
```
- 6개년 전량. 출력 `D:\10_LAYERS\05_search_master\{연도}\{세션}.csv`.
- 진행이 콘솔에 실시간(세션별 줄). 끝에 **판정: ✅ 검증 통과** 확인.
- **재개**: 중단돼도 같은 명령 다시 실행하면 이미 만든 CSV는 건너뛰고 이어감.
- **확인**: `logs\build_search_master_*.txt` — 행수=발화수, `어절수 불일치 0`.
- ⚠ 도는 동안 MFA·robocopy 등 **D: 읽는 다른 작업 금지**.

## 2. MFA G2P 전량 재정렬 — 실제 발음(v2) 레이어 (약 4일, D: 단독)

### 사전 준비(기기당 한 번씩 확인)
- **D: 볼륨 라벨이 `DATA_SSD`인지** 확인(HDD를 D:로 오인 방지). 러너가 자동 가드.
- **백신(AhnLab V3 등) 검사 예외**에 아래 6경로 등록(안 하면 수십 배 느림, 과거 실측):
  `D:\20_AUDIO` `D:\10_LAYERS` `D:\mfa_eojeol` `C:\mfa_tmp` `C:\mfa_eojeol_out` `%USERPROFILE%\miniforge3`.
- **MFA align.py 패치 4종**(conda env 재설치하면 사라짐 → 새 기기면 재적용):
  ① `analyze_alignments()` 호출 제거(교착 방지) ② export 워커 `try/finally`+`output_path=None`
  ③ `construct_textgrid_output` 5만개씩 청크(SQLite 변수 한도) ④ 패치 print의 em-dash `—`→`--`
  (cp949 콘솔 crash 방지, 2026-07-23). 절차: RUNBOOK '새 기기 셋업' 절.

### 실행
2020·2021도 **G2P로 다시** 하려면 완료 마커부터 삭제(안 하면 그 두 해는 건너뜀):
```
Remove-Item D:\mfa_eojeol\done\*.align_done, D:\mfa_eojeol\done\*.merge_done -Force
powershell -ExecutionPolicy Bypass -File scripts\run_eojeol_realign.ps1
```
(2022–2025만 새로 하려면 마커 삭제 없이 러너만 실행 — 미완료분만 처리.)

### 러너가 자동으로 하는 것 (사람 개입 불필요)
- 깨진(0바이트) wav 격리 · 평면 코퍼스 가드(뜨면 아래 조치) · temp C:/D: 자동 선택 ·
  교착 워치독(최근 15분 CPU 정체 시 자동 강제종료·재시도) · 거짓 성공(exit 0인데
  출력 0건) 가드 · 완주("Done!") 직후 오살 방지.

### 확인·주의
- 진행: 1분마다 하트비트(현재 MFA 단계). 연도 하나 수 시간(2021 최대=2020의 1.63배).
- ⚠ 도는 동안 **D: 다른 작업 금지**.
- 평면 구조 경고가 뜨면: `python scripts\python\restructure_wav_sessions.py --root D:\20_AUDIO\03_wav\individual --year {연도} --apply` 먼저.
- 실패 시 원인: `D:\mfa_eojeol\logs\mfa_{연도}_stderr.log`의 traceback.
- 완료 확인: `python scripts\python\measure_spn.py "D:\20_AUDIO\06_textgrid_eojeol\{연도}"` →
  spn 비율 매우 낮아야(G2P 전 20~30%대 → 후 0%대).
- 다음(스크립트 미작성): `extract_actual_pron.py`로 phones→`06_actual_pron`(v2), utt_id로 v1과 조인.

## 3. reference 4종 회수 (HDD 연결 시, 독립·수 분)
- HDD 연결(문자 예: E:). **D: 배치 안 도는 시간에.**
- `docs/ASSETS_LEDGER.md`의 robocopy 4줄 실행 → `D:\00_RAW\reference\`.
- `python scripts\python\preflight_search_master.py` 재실행 → reference `[OK]` → ASSETS_LEDGER ✅ 갱신.
- **HDD 원본은 삭제 금지**(유일본 역백업 유지).
- 용도: 빈도사전 재생성·A단계 검증·lexicon 발음 예외층(1·2단계엔 불필요).

## 실수하기 쉬운 곳 (과거 시행착오 압축)
1. **두 D: 배치 동시 실행** → 경합. 반드시 하나씩.
2. **MFA 코퍼스 평면 구조**(세션 폴더 아님) → 연도 전체를 화자 1명으로 오인, 품질·속도 붕괴. 러너 가드가 막음.
3. **0바이트 wav 1개**가 MFA 로딩 전체를 실패시킴(로딩 5시간 뒤에야). 러너가 사전 격리.
4. **MFA exit 0인데 TextGrid 0개**(거짓 성공). 러너가 잡음 — temp 함부로 삭제 금지(완주 정렬이 날아감).
5. **.ps1은 UTF-8 BOM 필수**(없으면 PS5.1이 한글 주석 다음 줄을 삼켜 사고).
6. **상태 선언은 실측으로만** — preflight/로그 근거 없이 "완료"라 하지 말 것.
7. **콘솔 인코딩** — 한글/특수문자 출력이 crash 유발 가능. 스크립트는 utf-8 reconfigure,
   MFA는 align.py em-dash 수정으로 해결(위 패치 ④).
