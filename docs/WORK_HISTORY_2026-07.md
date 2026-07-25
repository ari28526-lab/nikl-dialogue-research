# 작업 내역 (2026-07-08 ~ 07-15) — Claude와의 협업 기록

앞선 1기(겨울~3월: 어휘목록 53만·MFA 정렬 449만·검색 시스템)는
`PROJECT_SUMMARY.md` 참조. 아래는 2기(7월) 상세.

## 7/8-9 — 재가동·형태소 재분석 착수
- 중단된 프로젝트 상태 파악 (문서 기반), 2025년 JSON 압축 해제 (2,927파일)
- 바른(Bareun) 클라우드 API 환경 확인, 파일럿 120발화 검증 (품질 우수)
- **1차 전체 재분석 시작**: `bareun_dialogue_full.py` — 발화별 형태소
  (어절 경계 보존 형식), 파일 단위 체크포인트
- A2 의미번호(`assign_sense_layer.py`)·A3 빈도사전 스크립트 작성·검증
- 연구 설계 확정: **A단계(자료 구축)/B단계(현상별 분석) 분리**,
  D: 재편 계획, 경로 중앙관리(config/paths.json) 도입

## 7/9-10 — 텍스트 레이어 완성
- 바른 무료 일일한도 초과 → 유료 플랜(월 300만 어절) 1개월 전환
- **1차 완료: 17,156파일·분석대상 5,103,356발화·형태소 토큰 5,096만** —
  후속 전수 감사에서 원본 JSON 5,157,997행 중 `form` 빈 54,641행은
  `iter_utterances()` 입력 정책으로 제외됐음을 확인
- A2 의미번호 전체 부여 (내용어 78%→보완 후 90%; 방법·신뢰도 기록)
- A3 빈도사전 (RAM 대비 연도분할 count→merge): 형태소 165,920항·어절
  857,443항 + MP/LS 비교·로마자·IPA·어원(우리말샘)·KoFREN 통합
- A3b 의미별 빈도표, A4 메타데이터 인덱스(사용역·주제·화자),
  A5 층화 빈도(성별×연령×사용역, 층 합계 교차검증 통과)
- **D: 전면 이행**: 00_RAW/10_LAYERS/20_AUDIO/90_ARCHIVE (생애주기 구조),
  전 스크립트 경로 일괄 갱신

## 7/10-14 — 2025 음성 파이프라인
- PCM 59.6GB 해제 → 발화별 WAV 587,174 변환·검증 → 바른 분할 기준
  .lab 587,110 생성
- MFA 정렬 트러블슈팅 연쇄 해결: soundfile DLL 파손(재설치),
  한국어 재토큰화 요구(→ --no_tokenization, 방법론상으로도 타당),
  sqlite 잠금(→ WAL 전환+패치), **MFA export 교착(→ 정렬 DB에서
  직접 생성하는 자체 스크립트 merge_textgrid_v2.py로 우회)**
- 화자 설정을 기존 연도와 통일(세션=화자), 모델 동일성 검증
  (전 연도 korean_mfa v3.0 같은 파일 — 논문 기재 가능)
- **2025 표준 TextGrid 585,889개 생성** (정렬 커버리지 99.79%)

## 7/14 — 인벤토리·다층위 발견
- **전수 커버리지 인벤토리**: 6개년 발화별 wav·TextGrid 대조 —
  전체 99.44% (2023만 96.98%, 재정렬 여부 보류 결정 대기)
- 다층위 2025의 실체 확인: 문어 13,907+구어 16,439문장, MP·WSD·DP·
  SRL·ZA 레이어 — **구어부가 우리 2024 발화의 부분집합**(ID 100% 일치)
- 다층위 빈도표 3종(2025년판 규준, 어절 33.7만 토큰) 구축
- NIKL 공식 설명 PDF 15종 등록, 공식 수치·인용 확보

## 7/15 — 통일·검증·연계·운율·GitHub
- **tier 통일 완결**: 2020-2024 구판(6-tier)을 표준 3-tier로 전량
  재생성(retrofit) 후 스왑 — 여섯 연도 동일 체계, 구판 아카이브
- **공식 주석 대비 검증**: 형태소 F1 0.929(동일문장 기준), 의미번호
  76.4%(단의어 100% — 우리말샘 체계 변동 없음 판정)
- gold 레이어 수입(구문·의미역·조응, 16,439발화) → "프리미엄 표본"
- 빈도사전에 freq_ML2025 컬럼 통합 (규준 5종 체제 완성)
- A6 fetch 유틸(검색→wav+TextGrid), 정렬 품질통계 587,174행 구출
- **운율 파일럿**: 500발화 Colab 실행 성공 — IP/AP·경계성조·F0·
  Momel 목표점 + prosody tier TextGrid (청취 검증 대기, 규칙 v0)
- 프리미엄 16,439 운율 표본 준비 (premium_all.zip → G:)
- ㄴ삽입 환경 정의 초안 (phenomena/34_n_insertion — 검토 대기)
- 파일 정돈(임시파일 아카이브, mfa_temp 삭제) 및 **GitHub 이행**:
  리포 생성(private, ari28526-lab/nikl-dialogue-research), 정본을
  research 폴더로 이사, 초기 커밋 60파일

## 7/16-17 — 어절 전량 재정렬 착수 (목적 B: 4-tier)
- **1차 정렬의 구조적 결함 확정**: phones가 형태소 고립형(것을=[걷을], 연음
  미반영) → 형태음운 변이 분석 불가. 아카이브 전수 검토로 재활용 불가 판정
  → **어절 lab 전량 재정렬 결정** (RUNBOOK_MFA_eojeol_realign)
- 파이프라인 작성: 어절 lab 제자리 생성 → MFA → 4-tier 병합(기존 형태소
  경계 재사용). 파일럿 3차 성공: 14.2발화/s, **USB I/O 병목 판정** →
  temp·중간산출 C: 이전, conda run→mfa.exe 직접 호출 교정
- 본실행 1차(7/17): lab 9.5h + MFA 로딩 1h52m 만에 원인불명 실패 —
  traceback 유실 사고

## 7/18 — 3연속 실패의 원인 규명 (각각 다른 층위)
- **stderr 캡처 도입**: MFA는 traceback을 로그 닫힌 뒤 콘솔에만 출력 →
  러너를 Start-Process 리다이렉트+1분 하트비트로 전환 (원인 영구 보존)
- **★백신 착오 발견**: 실백신은 AhnLab V3(Defender 비활성) — Defender
  제외가 무효였음. V3 예외 등록 → lab 스킵 9.5h→12분 실증
- **2차 실패 원인 확정**: 0바이트 wav 4개(SDRW2000000521 연속 구간, 변환
  산물) — MFA는 로딩 말미에 전체 raise. `quarantine_bad_wavs.py` 신설
  (전수 크기 스캔·격리), 러너에 연도별 자동 격리 단계 추가
- MFA 이어가기(재시도 시 temp 재사용→실패 시 --clean 폴백) 도입
- **기기 이전 결정**: 외장 SSD 1TB + i5-1240P 노트북 (근거·절차 런북 기록)

## 7/19 — ★1화자 사고 → 구조 재정비로 전환 (사용자 방침)
- 3차 실행: 로딩 9.4h 완주 후 로그에서 **`Found 1 speaker across 870158
  files` 발견** — 평면 코퍼스라 MFA가 연도 전체를 화자 1명으로 오인
  (SAT·CMVN 무력화 + 1job 강등). 파일럿(세션 구조 복사본)이 못 잡던 함정
- 사용자 결정: 2020 무리하지 않고 **HDD를 최종 구조로 정돈 후 SSD 이전**
- **세션 재구성 완료**(사용자 콘솔, 밤): 평면 4개년(2020·21·22·25) →
  세션 하위폴더. 6개년 감사 통과(루트 잔여 0, 세션 17,155개)
- 체계 정비: `DATA_LAYOUT.md`(전 폴더 실측 지도+발화 좌표계),
  `locate_utt.py`(발화 ID→전 레이어 경로), fetch_audio 재작성(locate 일원화·
  4-tier 우선), 복사 러너(`copy_hdd_to_ssd.ps1`, 역방향 백업 겸용),
  러너 이식성(홈 기준 경로·num_jobs 자동·평면 가드)
- A단계 전반 점검: align.py 패치 의혹 종결(원본과 diff 0), 1차는 세션=화자
  였음 확인(morphemes tier 1화자 우려 해소), 운율 파일럿·검색은 4-tier 후
  재실행/신규 작성으로 순번 확정
- 다음: 7/20 오후 HDD→SSD 복사 → SSD를 D:로 → 미니 PC에서 재정렬 재개
  (기기 이전은 열린 카드)

## 7/22-23 — 2021 완주 + ★G2P 부재 발견(방법론 재검토)
- 2021 정렬 완주(3.26h, 137만 발화 중 오류 184건=0.01%) → export 단계에서
  진짜 완료("Done!") 직후 워치독이 CPU 저하를 교착으로 오판해 강제종료(temp만
  소실, 실제 출력 1,372,068건 무사 확인 → 수동 병합으로 복구). 워치독을
  "Done!" 신호 감지 시 안 죽이게 수정
- 병합 스크립트 재검증 중 새 발견: `realign_eojeol_merge_output.py`가
  `_speakers.csv`(화자 메타)를 세션 파일로 오인해 6개년 공통 KeyError —
  필터 추가로 수정(2021 병합 성공, 형태소tier없음 1건)
- 사용자 요청으로 QC 표본(2020·2021 각 2건, wav+TextGrid+원본CSV) 추출 →
  **phones tier의 30~75%가 "spn"(음소 없음)** 발견. 원인: MFA 발음사전
  고정 21,009단어, G2P 미사용으로 활용형(교착어 특성상 무한) 전부 OOV.
  하필 이 프로젝트가 되살리려던 활용형 연음이 핵심 피해 대상 — 2020·2021
  산출물의 핵심 목적 달성 여부 의심. korean_mfa G2P 모델(v3.0.0) 존재 확인,
  파일럿 검증 후 재작업 여부 결정하기로 합의(미실행)
- 발음정보 CSV 부재 문제 추가 발견: 발화단위 발음이 있는 줄 알았던 게 실제로는
  형태소타입별 사전(조인 안 됨)뿐이었음 → 1기(작년 겨울)
  `01_nikl_dialogue_enriched.csv`(4.7GB, 발화단위 pronunciation·roman 포함)를
  1기 노트북 분석으로 재발견, Google Drive에 위치(이 기기 미연결, 클라우드라
  안전 추정) — 2025 미포함·구버전 바른·자체 G2P 검증 필요라는 한계 확인
- 당시 사용자 결정 기록: 2025+최신 바른 재분석 검토(유료 플랜 해지 보류),
  예측 발음열+MFA phones·시간정보 이원 구축, 1기 CSV를 SSD로 백업 예정.
  최종 실현 여부는 사람의 수동 판정으로 별도 구축. 2022~2025 재정렬은 보류
  (G2P 파일럿 검증 후 진행 방향 재결정)

## 7/23 — 검색 마스터 설계 확정 + ★reference 미이전 발견(체계 교정)
- **검색 마스터 레이어 설계 확정** (`DESIGN_search_master_layer.md`): 발화 1행
  CSV에 사회변수+형태소+철자열+예측발음열, 어절 정렬(` | `), roman_mfa 체계,
  세션 CSV+연도/전체 Parquet. 결정 4건(사용자) + A3 빈도사전 정합 검토
  (IPA 변환표=정본 토큰집합, 로마자 3종 혼재 실측→정규화 방침)
- **1기 산출물 실측 대조**: Drive enriched CSV(4.96GB, 표본 3k 분석) —
  original_form(form과 31.2% 상이)·start/end·note가 기존 레이어에 누락이었음
  → 마스터에 추가. 어휘목록 v1(Dropbox→D: 복사, 130만 행) 발음 100% 보유
  확인 → 예측발음 조회부 원천으로 채택
- **★reference 4종(사전 v2·MP·LS·다층위) SSD 미이전 발견** — 7/20 이전이
  Tier1 우선이었는데 '전량 이전'으로 인식 불일치, 문서도 이를 소리내어
  알리지 않음. HDD 유일본 상태. → **예방 체계 수립**: `ASSETS_LEDGER.md`
  (실측 기반 자산 정본) 신설, CLAUDE.md 규칙 8~10 추가(전량 기본·실측 선언·
  한줄명령 금지), `preflight_search_master.py` 신설(파일럿 차단 요소 없음 판정)
- G: 연결 실측 확인 → 1기 CSV 백업은 robocopy 한 줄로 (gdown 불필요)
- 다음: 새 세션에서 파일럿 (`HANDOFF_pilot_search_master.md` 참조)

## 핵심 수치 총괄
| 항목 | 값 |
|---|---|
| 분석대상 발화 / 형태소 토큰 | 5,103,356 / 50,955,889 |
| 표준 TextGrid | 585만 (6개년, 커버리지 99.44%) |
| 빈도사전 | 형태소 165,920항·어절 857,443항 (+의미별·층화·분산도) |
| 검증 | 형태소 F1 0.929, 의미번호 76.4% (단의어 100%) |
| 프리미엄 표본 | 16,439발화 (구문·의미역 gold + 운율 진행 중) |

## 미해결 (2026-07-15 기준)
TODO_A단계.md 참조 — 사용자 필수: 운율 청취 검증, ㄴ삽입 definition
검토, 바른 구독 해지. 결정 대기: 2023 재정렬(보류 권고), 산출물 G: 백업(승인 대기).

## 2026-07-23 (오후) — 검색 마스터 v1 파일럿 + MFA G2P 검증 (Claude 세션)

- **검색 마스터 v1 구현·파일럿**: `predict_pron.py`(필수 규칙 G2P, 단위테스트 30/30),
  `build_search_master.py`(세션 CSV·검증 내장). 2020 3세션·1,297발화 검증 통과.
- **사용자 결정 확정 반영**: 용언 어간+어미 경음화 ON, ㄹ비음화 OFF(보류), 표기 4단
  위계(음소 공백/음절 `_`/형태소 `+`/어절 `|`), 자리표시 `∅`, tagged_roman 정본 on
  (ㄴ삽입 검색용 `[자음]/N… + (I|Y)`).
- **MFA G2P 파일럿 성공**: g2p korean_mfa 다운로드. `mfa align --g2p_model_path korean_mfa`
  로 2020 SDRW2000000001(479발화) 재정렬 → **phones spn 27.5%→0.0%**, 것을=[거슬]
  (k ʌ sʰ ɨ ɭ) 시간정렬 확인. `measure_spn.py`·`build_g2p_pilot_corpus.py`.
- **align.py 버그 수정**: 7/21 패치 print의 em-dash(—)가 cp949 콘솔서 UnicodeEncodeError
  로 export 직전 crash → `—`→`--` 2곳 수정. `run_eojeol_realign.ps1`에 `--g2p_model_path
  korean_mfa` 추가(전량 재정렬 대비).
- **stitch_session.py**: 원본 연속 녹음 부재 대비 — 발화 클립을 utt_id 순 이어붙여
  연속 wav+정렬 TextGrid 재구성. 9발화 데모 검증.
- 다음 세션용 핸드오프: `docs/HANDOFF_search_master_session2.md`. 남은 것: v1 CSV 전량
  생성(밤샘, HDD 불필요) → MFA G2P 전량 재정렬(~4일). HDD는 7/24 13:00, reference 회수용(독립).

### 2026-07-23 14:20–14:47 — search master 전량 생성

- `D:\10_LAYERS\05_search_master`에 2020–2025 전량 생성 완료:
  17,156세션·5,103,356행, JSON 결측 0, 어절 수 불일치 0.
- 이 산출물은 2026-07-24 메타 ID 수정 전 버전이므로 2023년 네 세션의 문서
  메타가 `미상`이다.
- `predict_pron.py`가 규칙 기반만 구현되어 lexicon 예외 발음은 미반영이고,
  coverage 세 열도 계산되지 않았다. 따라서 파일 존재와 구조적 완결은 확인됐지만
  연구용 최종 정본으로 승격하기 전 감사·보완이 필요하다.

## 2026-07-24 — 대량 MFA·CSV 전 안전성 감사와 파이프라인 강화

- 사용자 요청에 따라 MFA G2P 전량 재정렬과 search master **전량 재생성**은
  시작하지 않고, 먼저 기존 코드·오류 이력·D:/프로젝트 역할을 전수 감사.
  수정 전 핵심
  코드 11개를 `archive/code_pre_bulk_20260724`에 SHA256 manifest와 함께 보존.
- 누적 시행착오를 F01–F27로 정리. 과거의 traceback 유실·V3 착오·0바이트
  WAV·1화자 사고·MFA export/SQLite/거짓 성공·워치독 오살·G2P 부재뿐 아니라
  이번 감사에서 exit 0, 부분 CSV skip, overwrite 유실, 경로 혼재를 추가 확인.
- 공통 원자 출력 계층 도입: `.partial` 기록→fsync→스키마·ID·행수 검증→
  `os.replace`; 기존 정식 파일은 `_archive/<run_id>`에 먼저 보존. Git commit,
  Python·OS·옵션·경로·합계를 JSON manifest에 기록.
- MFA 러너를 preflight 기본 실행, JSON marker, 실패 temp 보존, 검증 후 정리,
  치명 분기 `exit 1`로 강화. MFA 3.4.0 설치본의 필수 수동 패치 7종을
  AST/소스 hash로 검증하는 `verify_mfa_install.py` 추가. 실제 preflight는
  모델·패치·세션구조·디스크 포함 FAIL 0/WARN 0.
- **★메타 ID 충돌 발견·복구**: `file_meta.csv`가 17,156행이라 정상처럼
  보였으나 2023 JSON 4개의 최상위 `id`가 직전 세션으로 잘못 기입되어 중복 4,
  실제 메타 누락 4였음. 원본 파일명 stem과 내부 doc/utterance ID는 일치하므로
  stem을 조인 정본으로 채택하고 잘못된 값은 `source_top_id`에 보존.
- D: 원본 JSON은 수정하지 않고 구 `file_meta.csv`를
  `_archive/metadata_fix_top_id_20260724`에 보존한 뒤 17,156행을 원자 재생성.
  형태분석–메타 ID 집합 17,156개 완전 일치 확인. 누락됐던
  `SDRW2300000445` 216발화 검색 CSV 파일럿에서 메타/화자/JSON 결측 0,
  어절 불일치 0으로 통과.
- 자동 검사: Python unittest 18/18, PowerShell BOM·AST 안전 검사 3/3,
  MFA 패치 7/7, 예측발음 selftest 30/30 통과. 세부 결과는
  `outputs/reports/PILOT_pre_bulk_validation_2026-07-24.md`.
- 중간 커밋과 원격 푸시:
  `5587604`(기준선), `f49eeef`(CSV 안전화), `69babb4`(MFA 안전화),
  `d77474a`(메타 복구). 작업 브랜치 `agent/harden-pre-bulk-pipelines`.
- 다음 게이트: 기존 전량 CSV의 행·메타·lexicon·coverage 감사와 연도별 MFA
  소표본. G2P phones는 연구자가 음성 구간을 찾기 위한 대략적 분절이며 현상의
  자동 실현 판정값이 아니다. 실패·`spn`·시간 경계·파일 대응을 확인한 뒤
  연도별 실행 여부를 결정한다.

## 2026-07-25 — 층화 MFA 수동 검토 반영

- 사용자가 Dropbox 점검본에서 연도별 핵심 발화 7개를 Praat로 검토하고
  TextGrid 외곽 경계 가시성, 숫자 `1`의 발음 정보 소실, 파일 탐색성 문제를
  보고했다. 스크린샷과 메모는 `6_review`에 보존.
- 회수 발화 `SDRW2300001955.1.1.164`는 누락이 아니라
  `2023\SD2302149` 화자 폴더와 연도별 통합 CSV에 존재함을 확인했다.
- TextGrid tier의 구조적 0/xmax 경계와 화면의 빈 interval 경계를 구분했다.
  원 MFA 라벨·시간은 유지하고, 이후 생성본의 `utterance`만 첫–마지막 유표
  어절 범위에 놓아 근거 있는 앞뒤 padding이 보이도록 수정했다.
- 기존 `1층으로`의 form 기반 `∅` 열은 감사용으로 보존하면서,
  원전사 `일 층으로`가 placeholder를 실제로 줄일 때만 채택하는
  `pron_reference_*` 출처 추적 열을 추가했다. 근거 없는 기호는
  `unresolved_symbol`로 명시한다.
- 2023 목표 세션 371/371행 격리 재생성 통과. 목표 발화는 한글·roman·IPA
  reference를 회복했고, 특수 전사 1행만 미해결로 명시됐다.
- 연도별로 같은 basename의 WAV·lab·6-tier TextGrid·발화 CSV를 한 폴더에
  모으는 점검 bundle 빌더를 추가했다. 60발화 실자료 검증 통과.
- 발화자뿐 아니라 같은 원본 JSON document의 전체 화자와 현재 화자를 제외한
  공동 참여자 ID를 `dialogue_speaker_ids`·`co_speaker_ids`로 추가했다.
  직접 수신자 정보는 원자료에 없으므로 상대 후보로만 해석한다. 2023 목표 세션
  371행에서 연결 오류 0.
- Dropbox 정식 bundle의 디렉터리 원자 rename이 WinError 5로 차단된 사례를
  기록하고, `.INCOMPLETE`→전 파일 SHA256 대조→완료 표지 제거의 검증 복사
  fallback을 추가했다. 검증 후 staging 디렉터리 정리만 동기화 lock으로
  실패하는 경우는 완료본을 실패로 되돌리지 않고 비치명 정리 경고로 분리했다.

## 2026-07-25 — MFA 파일럿 연구자 검토 Excel

- 사용자가 60개 파일럿을 쉽게 판정할 수 있는 시트를 요청했다.
- `Spreadsheets` 전용 artifact runtime이 현재 세션에 로드되지 않아 사용자가
  `openpyxl` 우회를 명시적으로 승인했다. MFA Python 환경에 openpyxl 3.1.5와
  et-xmlfile 2.0.0을 설치했다.
- `build_mfa_pilot_review_workbook.py`를 추가했다. 원본 INDEX를 별도 시트로
  보존하고, 검토입력 드롭다운·WAV/TextGrid/CSV/LAB 상대경로 링크·연도별
  진행률 수식·두 우선 사례 표시를 생성한다.
- 필수 열·고유 발화·관련 파일 존재를 먼저 검사하고 `.partial.xlsx`를 다시
  열어 시트·행·수식·드롭다운·링크를 확인한 뒤에만 최종 파일로 교체한다.
- 설계와 해석 제한은
  `docs/decisions/DESIGN_mfa_pilot_review_workbook_2026-07-25.md`에 기록했다.
- 생성본을 다시 열어 60행·240개 링크·4종 드롭다운·2개 우선 사례·수식을
  검사하고 프로젝트 보존본과 Dropbox 공식본의 SHA256 일치를 확인했다.
- Excel 16.0 COM 자동 렌더링은 `Workbooks.Open`에서 실패했다. 검증용으로
  시작된 제목 없는 Excel 프로세스는 종료했으며, 첫 수동 열기에서 화면 배치와
  상대경로 링크를 확인하도록 제한을 기록했다.

## 2026-07-25 — 발음 원천 추적과 음운·형태 환경 검색 설계

- 대표 발화 `SDRW2200000836.1.1.61`을 원본 JSON, search master, Bareun,
  A2 의미 레이어, 통합 사전 v1/v2, 규칙 발음, MFA 2-tier, 4-tier 및
  점검용 6-tier까지 역추적했다.
- 원본 JSON의 `form`과 `original_form`은 모두 `꽃에 모양은 어땠어?`이며
  별도 발음 전사 필드는 없다. 점검 TextGrid의 `pron_reference`는 JSON
  전사가 아니라 `predict_pron.py`의 규칙 기반 파생값이다.
- A2에는 8형태소가 있으나 현재 TextGrid `morphemes`에는
  `꽃|에|모양|은|어땠어` 5라벨만 있어, 구형 words tier를 현재 Bareun
  형태소와 1:1 대응하는 것으로 해석할 수 없음을 확인했다.
- 통합 사전 v2가 `pron_1/pron_2/pron_g2p`와 MFA 로마자·표준사전 대응 열을
  모두 가진 것을 확인했다. 다만 중복행, 다의 발음, Bareun–사전 품사 불일치,
  활용형 합성 문제가 있어 단순 CSV 조인이나 최소 의미번호 자동 선택은
  부적합하다.
- 발화·어절·형태소·형태경계·파일 인덱스·후보·수동 판정을 분리하고
  `utt_id/eojeol_idx/morph_idx/boundary_id/candidate_id`로 연결하는 설계를
  `docs/decisions/DESIGN_pronunciation_environment_search_2026-07-25.md`에
  기록했다. D: 원자료나 기존 CSV/TextGrid는 변경하지 않았다.

## 2026-07-25 — Python 경로 오진 정정과 환경 점검 고정

- 제한된 Codex shell에서 AppData의 Python 3.13 절대경로가
  `Test-Path=False`·명령 없음으로 보여 설치가 없다고 잘못 보고했다.
- 읽기 전용 권한으로 재검증한 결과 전역 Python 3.13.14, py launcher,
  사용자 PATH, MFA 환경의 pipeline Python 3.13.14가 모두 정상임을 확인했다.
  설치·PATH 변경은 하지 않았다.
- `scripts/check_python_environment.ps1`을 추가해 전역 Python, launcher,
  PATH, `config/paths.json`의 `pipeline_python`을 한 번에 검사하고,
  `access_denied`를 `missing`과 구분하도록 했다.
- `AGENTS.md`의 오래된 Dropbox 프로젝트 root를 현재 research root로 고치고,
  제한된 Codex shell의 거짓 음성을 Python 삭제로 판단하지 않는 규칙과
  프로젝트 helper의 `pipeline_python` 우선 원칙을 기록했다.

## 2026-07-25 — 점검 TextGrid 양끝 경계·형태소 tier v3

- 구 수동 검토본과 새 60개 점검본을 tier별로 전수 재검사했다. 새 점검본도
  유표 정렬이 시간축 끝에 붙어 10발화는 왼쪽, 3발화는 오른쪽 가시적 빈
  경계가 없음을 확인했다.
- 원 MFA 라벨 시간을 임의로 줄이지 않고, 점검 WAV 사본 좌우에 0.05초 PCM
  무음을 추가한 뒤 모든 TextGrid 시간을 같은 양만큼 이동하도록 review bundle
  builder를 보완했다. 원 D: WAV·TextGrid는 변경하지 않았다.
- `phones`를 `phones_mfa`, 구 형태소 분절을 `morphemes_legacy`로 명시하고,
  현재 Bareun 형태소열을 어절 구간에 표시하는 `morph_analysis`를 추가했다.
- 60개 WAV가 16 kHz·mono·16-bit PCM임을 확인하고 중앙 frame 원본 일치,
  양끝 0값, 7-tier, 전 tier 좌우 0.05초 빈 interval을 전수 검증했다.
- `morph_analysis`는 24개 all-slot, 28개 labeled-slot 정렬, 복잡 사례 8개는
  근거 없는 오정렬 대신 발화 전체 fallback과 경고로 처리했다.
- 발음·검색 설계 문서를 pre-MFA 언어 마스터→MFA→post-MFA 시간 인덱스→
  KOINA·수동 판정 순서로 바로잡고, enriched lexicon의 무발음 664,596행을
  legacy G2P와 `urimal_id`로 100% 일의 보완할 수 있음을 기록했다.

## 2026-07-25 — 점검 TextGrid 최소 4-tier v4

- 사용자가 7-tier가 기본 수동 검토에 과도하다고 지적해, 기술적으로 검증된
  v3는 중간 실험 기록으로 보존하고 기본 점검본을 4-tier로 축소했다.
- 기본 tier를 `words / phones_mfa / morph_analysis / utterance_info`로
  확정했다. `utterance_info` 한 label에 발화 ID, form, 철자 로마자, 규칙
  발음 한글·로마자를 출처 표지와 함께 넣었다.
- `original_form`과 숫자·기호 보완 reference는 form과 다를 때만 같은 label에
  추가한다. 형태소별 철자 로마자와 사전 예외 발음은 CSV/Parquet 정본에
  보존하고 TextGrid tier를 늘리지 않는다.
- 새 로컬 경로에서 6개년 각 10개, 총 60발화를 재생성했다. 4-tier·좌우
  0.05초 빈 경계·원 WAV 중앙 PCM·`UTT/FORM/ORTH_R/RULE_H/RULE_R`
  검색 표지를 전수 통과했다.
- 원 `words/phones` 120개 tier의 의미를 padding 제거 뒤 재대조했다.
  형태소 어절 매핑은 all-slot 24, labeled-slot 28, 안전 fallback 8이었다.
- 원 D: run, 기존 CSV/TextGrid, v3 묶음은 수정하거나 덮어쓰지 않았다.
- 첫 v4 검토 엑셀 생성은 작성기가 제거된 구식
  `original_form_align_status/pron_reference_align_status`를 필수로 요구해
  중단됐다. v4의 `morph_analysis_align_status/utterance_info_schema`를
  인식하고 워크북 위치에서 bundle까지의 상대 링크를 계산하도록 고쳤다.
- Dropbox에 새 `9_review_by_year_minimal_v4_20260725` 묶음과
  `MFA_pilot_review_v4_20260725.xlsx`를 만들었다. 엑셀은 60행, 5개 시트,
  240개 파일 링크, 4개 드롭다운 규칙을 재열기 검증했다.

## 2026-07-25 — 대량 MFA 직전 입력계약·무인 실행 안전장치

- 실환경 6개년 MFA preflight를 다시 실행해 설치 패치 7종, 세 모델, D:
  `DATA_SSD`, 세션 폴더, C: 47.8GB·D: 333.3GB를 확인했다. 최초 결과는
  FAIL 0/WARN 0이었다.
- 기존 전량 러너가 Bareun `form`만 lab에 써 숫자·기호를 제거할 수 있고,
  C:\mfa_tmp\2020의 0.68GB 중간 DB에는 어떤 입력으로 만들었는지 계약이
  없음을 발견했다. 이 상태의 즉시 재개는 금지했다.
- `realign_eojeol_build_corpus.py`를 새 pre-MFA search master의
  `pron_reference_form` 기반으로 바꿨다. build meta SHA256·세션 coverage·
  source field를 입력 계약으로 묶고, 첫 실행은 기존 nonzero lab도 실제
  내용을 읽어 전수 비교한다.
- 현재 reference에서 한글이 0자인데 구 lab이 남아 있으면 stale 전사를
  MFA가 재사용하지 않도록 `archive_stale_labs/<contract>/...`로 복원 가능하게
  옮긴다.
- 숫자 `1`이 원전사 `일`로 안전하게 회복된 합성 사례에서 구 lab을 원자
  재작성하고, 같은 계약 재실행은 marker로 재개하는 회귀검사를 추가했다.
- 3세션 pilot search master를 전량 입력처럼 넘긴 실험은
  `search=3/source=2232` coverage FAIL로 정확히 차단됐다.
- `run_eojeol_realign.ps1`은 다른 입력의 temp를 삭제하지 않고
  `archive_stale_temp`로 옮기며, 완료 marker에도 input contract를 요구한다.
  2021은 C: 55GB, 다른 신규 연도는 45GB 문턱을 적용한다.
- `run_pre_mfa_bulk_safe.ps1`을 추가했다. versioned pre-MFA CSV staging을
  전량 생성한 뒤 2020부터 연도별로 실행하고, 실패 시 다음 연도를 중단한다.
  PID lock·transcript·요약 JSON을 남기며 기존 CSV/TextGrid를 자동 승격하지
  않는다.
- 이어붙이기는 전량 정렬 입력이 아니라 후보 추출 뒤의 온디맨드 검토 산출물로
  유지한다. 연결 시간은 원 세션 시간이 아니므로 발화별 offset manifest가
  필요하다는 점을 새 런북에 명시했다.
- `stitch_session.py`가 실제로 offset manifest를 쓰도록 보완했다. 기본
  0.05초 경계 무음, `phones_mfa/morphemes_legacy` 명칭, padded review
  TextGrid 길이 불일치 차단, 기존 출력 보호를 추가했다. 대표 발화
  `SDRW2200000836.1.1.61` 앞뒤 2개씩 총 5발화를 연결해 WAV/TextGrid
  10.89초 일치와 발화별 환산 좌표를 확인했다.

## 2026-07-25 — 대량 MFA D: 우선 용량 정책

- 대량 실행 직전 용량을 재확인했다. C: 47.5GB는 일반 연도 시작 문턱
  45GB보다 2.5GB만 많아 Windows·Dropbox 변동을 감당할 무인 실행 여유로는
  부족하다고 판정했다. D:는 `DATA_SSD`, 여유 333.3GB였다.
- 기존 search master는 4.19GB이고, 기존 TextGrid 각 5,000개 표본은 평균
  3.03KB(2020)·4.38KB(2021)였다. 510만 발화 신규 staging과 연도별 temp
  peak를 합쳐도 D: 추가량은 보수적으로 약 100GB 이내로 보아 200GB 이상
  완충 공간을 확보했다.
- `run_pre_mfa_bulk_safe.ps1`, `run_eojeol_realign.ps1`,
  `preflight_eojeol_realign.ps1`에 `-PreferD`를 연결했다. 신규 MFA temp와
  원출력은 D:에서 시작하고, 2021 55GB/그 밖 45GB 미만이면 실행 전에
  차단한다.
- 동일 입력계약으로 이미 계산된 resume temp는 무조건 다른 드라이브로 옮기지
  않는다. MFA DB의 절대경로 의존 가능성과 수시간 재계산을 피하기 위해 원래
  드라이브에서만 이어가며, 계약이 없거나 다른 temp는 기존 원칙대로 삭제하지
  않고 `archive_stale_temp`에 보존한다.
- 실제 `-PreferD -Year 2021` preflight에서
  `D: 333.3GB >= 55GB`를 확인했다. 2020 파일럿 search master를 일부러
  지정했으므로 2021 입력 coverage는 FAIL했고, 이를 전량 통과로 기록하지
  않았다.
- PowerShell BOM·AST·필수 D 우선 전달 검사 5/5와 Python unittest 41/41을
  통과했다. 정식 무인 명령은 기존 RunId에 `-PreferD`를 붙인다.
