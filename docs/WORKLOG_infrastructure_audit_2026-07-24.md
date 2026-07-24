# 연구 인프라 감사 작업일지 — 2026-07-24

## 기록 원칙

- 이 문서는 CSV·MFA 대량 작업 전에 수행하는 점검과 개선을 시간순으로 기록한다.
- 확인한 사실, 해석, 아직 확인하지 못한 사항을 구분한다.
- 원자료는 수정하지 않는다.
- 코드를 바꾸기 전 기존 버전을 보존하고, 변경 이유와 검증 결과를 함께 남긴다.
- 대량 산출물은 재실행 전에 소표본 파일럿과 중단·재개 안전성을 검증한다.
- 커밋·푸시할 때 이 문서에 커밋 ID와 범위를 덧붙인다.

## 연구 작업 흐름 — 사용자 확인본

1. 형태소 분석 CSV에서 특정 형태소가 포함된 발화 또는 표기상 음운 환경을
   충족하는 발화를 추출한다.
2. 추출된 발화에 대응하는 음성 파일과 TextGrid를 모은다.
3. 후보 자료에 KOINA 운율 분석 결과를 결합한다.
4. 연구자가 음성 파일과 TextGrid를 직접 검토해 현상의 실현 여부를 판정한다.
5. 형태소·표기 환경·빈도·사회 변수·운율·수동 판정을 결합해 현상별 분석을
   수행한다.

따라서 이 단계의 핵심은 자동으로 실현 여부를 판정하는 것이 아니라 다음 두
인프라를 신뢰할 수 있게 만드는 것이다.

- **CSV 인프라**: 후보를 빠짐없이 검색할 수 있는 형태소·표기·사전 발음·
  메타데이터
- **MFA 인프라**: 후보 음성에서 연구자가 구간을 찾고 판정하는 데 사용할 수 있는
  안정적인 대략적 분절과 TextGrid

## 개념 정정

### G2P phones의 역할

- `korean_mfa` G2P를 사용한 phones tier는 음성 파일의 대략적 분절 위치를
  TextGrid에 표시하기 위한 정렬 인프라다.
- 이 phones tier를 ㄴ 삽입 등 음운 현상의 최종 실현 판정값으로 사용하지 않는다.
- 최종 실현 여부는 연구자가 음성과 TextGrid를 직접 확인해 판정한다.
- 따라서 G2P 파일럿의 `spn` 감소는 정렬용 발음 항목의 미등록 문제가 줄었다는
  운영 지표이지, 현상 실현을 자동 판정했다는 증거가 아니다.

### lexicon 예외 발음의 역할

- lexicon 예외 발음은 사전의 등재 발음을 조회해 CSV의 기준/예측 발음 층에
  반영하는 것이다.
- 음향 신호로부터 실제 발음을 자동 추정하는 층이 아니다.
- 사전 발음과 규칙 기반 발음을 어떤 우선순위로 결합했는지 출처 열로 추적할 수
  있어야 한다.

## 2026-07-24 작업 시작 상태

### 저장소

- 작업 브랜치: `agent/harden-pre-bulk-pipelines`
- 시작 커밋: `f352668`
- 사용자 소유로 보이는 추적되지 않은 `Microsoft/` 폴더는 건드리지 않는다.

### 이미 확인한 전량 검색 마스터 상태

- `D:\10_LAYERS\05_search_master\_build_meta.json`
  - 세션: 17,156
  - 입력 발화/출력 행: 5,103,356
  - JSON 결측: 0
  - 어절 수 불일치: 0
- 전량 search master는 2026-07-23에 이미 생성되었다.
- 문서 일부에 남은 “전량 대기/미실행” 표기는 최신 상태와 맞지 않아 정정이
  필요하다.

### 확인된 감사 항목

1. Bareun 완료 기록의 5,103,358행과 search master의 5,103,356행 사이 2행 차이
2. 2026-07-24 메타데이터 수정 전에 생성된 2023년 네 세션 CSV
3. 설계된 lexicon 사전 발음 예외가 현재 코드와 전량 산출물에 실제 반영됐는지
4. `has_wav`, `has_tg_eojeol`, `quarantined` coverage 열의 실제 계산 여부
5. 관련 문서의 오래된 상태와 “실제 발음” 표현 정정

## 작업 기록

### 1. 문서와 코드의 첫 대조

확인한 파일:

- `docs/decisions/DESIGN_search_master_layer.md`
- `docs/HANDOFF_search_master_session2.md`
- `scripts/python/predict_pron.py`
- `scripts/python/build_search_master.py`
- `scripts/SCRIPTS_INDEX.md`
- `outputs/reports/PILOT_pre_bulk_validation_2026-07-24.md`

현재까지 확인한 사실:

- `build_search_master.py`는 `predict_pron.predict_pron()`을 호출한다.
- 현재 `predict_pron.py`에서 lexicon 파일을 읽는 코드는 발견되지 않았다.
- 따라서 lexicon 예외 발음은 설계에는 있으나, 현재 전량 search master의 예측
  발음에는 반영되지 않았을 가능성이 높다. 산출물 열과 표본을 추가로 확인한다.
- `build_search_master.py`는 coverage 세 열을 기본적으로 “미계산” 값으로 채운다.
- `scripts/SCRIPTS_INDEX.md`의 “전량 대기”는 실제 전량 생성 상태와 충돌한다.

### 2. 연구 흐름과 산출물 상태 정정

사용자 확인을 반영해 다음 문서를 정정했다.

- `scripts/SCRIPTS_INDEX.md`
- `outputs/reports/PILOT_pre_bulk_validation_2026-07-24.md`
- `docs/WORK_HISTORY_2026-07.md`
- `docs/decisions/DESIGN_safe_pre_bulk_pipeline_2026-07-24.md`
- `docs/decisions/AUDIT_pre_bulk_MFA_CSV_2026-07-24.md`
- `docs/decisions/DESIGN_search_master_layer.md`
- `docs/decisions/RUNBOOK_MFA_eojeol_realign.md`
- `docs/TODO_A단계.md`
- `docs/ASSETS_LEDGER.md`
- `docs/GUIDE_실행순서_제3자용.md`
- `docs/HANDOFF_search_master_session2.md`
- `docs/HANDOFF_pilot_search_master.md`
- `docs/decisions/METHODS_bareun_dialogue_reanalysis.md`
- `docs/learning/자료구축_단계별_리뷰.md`
- `config/paths.json`
- `scripts/run_eojeol_realign.ps1`
- `scripts/python/predict_pron.py`
- `scripts/python/realign_eojeol_merge_output.py`

정정 내용:

1. search master 전량본은 2026-07-23에 이미 생성됐다고 명시했다.
2. 이 전량본은 7/24 메타 수정 전이며 lexicon 예외 발음과 coverage가
   미반영된 감사 대상이라고 표시했다.
3. G2P phones를 “실제 발음/실현 판정”으로 부르지 않고, 연구자가 후보 위치를
   찾기 위한 대략적 분절·시간정보로 정의했다.
4. 예측/사전 발음, MFA 분절, 연구자의 수동 실현 판정을 서로 다른 층으로
   분리했다.
5. 구 가이드의 완료 마커 와일드카드 삭제 명령을 제거하고 한 연도씩
   파일럿→검증→본실행하도록 바꿨다.

아직 `06_actual_pron`은 경로 설정과 설계 문서에 역사적 이름으로 남아 있다.
실현 판정값과 혼동될 수 있으므로 추출 스크립트를 만들기 전에 보조 레이어의
정확한 이름과 스키마를 다시 정한다.

검증:

- `config/paths.json` JSON 파싱 통과
- `predict_pron.py --selftest` 30/30 통과
- lexicon 색인 헬퍼 자체검사 통과
- `run_eojeol_realign.ps1` PowerShell 파서 통과
- `git diff --check` 통과

lexicon 관련 추가 확인:

- `predict_pron.py`에는 `(word, pos_tag)` 조회용 색인 헬퍼가 이미 있다.
- 그러나 `build_search_master.py`는 실제 lexicon 파일을 열거나 이 색인을
  `predict_pron()` 호출에 전달하지 않는다.
- 따라서 “준비 코드가 전혀 없음”이 아니라 “조회 헬퍼는 있으나 전량 빌드에
  배선되지 않음”이 정확한 상태다.

### 3. Search master 전수 감사

추가한 재현 스크립트:

- `scripts/python/audit_search_master.py`
- 합성 회귀검사: `tests/test_audit_search_master.py`

실행 원칙:

- 원본 JSON, Bareun A1, D: search master를 읽기만 한다.
- 세션 단위로 스트리밍해 510만 ID를 메모리에 한꺼번에 올리지 않는다.
- 상세판은 `work/pre_bulk_pilot`에 보존하고, Git에 넣을 보고서는 합계와
  제한된 예시만 남겨 8.9MB에서 약 59KB로 축약했다.

실행 결과:

- 감사 세션: 17,156/17,156
- Bareun A1: 5,103,356행
- search master: 5,103,356행
- 세션 누락/추가: 0/0
- ID 순서·값, `form`, `tagged` 불일치: 모두 0
- 중복 ID: 0
- 원본 JSON utterance: 5,157,997행
- `form`이 비어 A1에서 제외된 utterance: 54,641행
  - `original_form` 비어 있지 않음: 44,440
  - `original_form`도 비어 있음: 10,201
  - 영향 세션: 4,386

2행 차이 판정:

- 2024 A1 전수: 728,257
- `03_freq_dictionaries/_partials/meta_2024.txt`: 728,257
- `D:\10_LAYERS\_merge_rerun.txt`: 합계 5,103,356
- search master build log: 합계 5,103,356
- 과거 문서의 2024 728,259와 총 5,103,358은 기계 산출물로 뒷받침되지 않는다.
  따라서 search master에서 두 행이 빠진 것이 아니라 과거 서술 수치의 오기로
  판정하고 활성 문서를 5,103,356으로 정정했다. archive 핸드오프 원문은 당시
  기록으로 보존했다.

메타데이터:

- 2023년 네 세션의 기존 전량본 1,090행은 `category_norm`과 `topic`이 모두
  `미상`이다.
- 수정된 메타데이터로 격리 재생성한 한 세션은 결측 0을 이미 확인했다.

lexicon:

- 1,296,777행 전부 `pron_1` 우선, 없으면 `pron_g2p` 폴백으로 발음 가용
- `pron_1` 613,441행, `pron_2` 41,237행, `pron_g2p` 683,336행
- builder에는 아직 미배선, 전량 CSV에 출처 열도 없음

coverage:

- `has_wav`, `has_tg_eojeol`, `quarantined`는 5,103,356행 전부 빈 문자열
- 현재 강화판 builder는 `미계산`으로 구분하지만 실제 계산은 미구현

어절 매핑 경고:

- `align_warn` 508,153행(9.957%)
- Bareun token 경계와 `form` 공백 어절 수의 불일치
- 발화 단위 형태소 포함 검색과 표기 환경 검색은 각각 가능하지만, 경고 행에서
  형태소를 TextGrid words의 정확한 어절 번호로 자동 대응시키면 안 된다.
- Bareun protobuf의 `Token.text`에는 `content`, `begin_offset`, `length`가
  있으나 현재 A1은 span을 저장하지 않았다. 후속 재분석·보완 시 저장한다.

사람이 읽는 상세 판정:

- `outputs/reports/AUDIT_search_master_full_2026-07-24.md`

기계 판독 요약:

- `outputs/reports/search_master_audit_20260724.json`

### 4. 후보 추출 인프라와 2020 파일럿 설계

설계 문서:

- `docs/decisions/DESIGN_candidate_infrastructure_layers_2026-07-24.md`

확정한 구조:

1. 언어·검색 층, 파일·MFA 분절 층, 연구자의 수동 실현 판정 층을 분리한다.
2. lexicon 사전 발음은 기존 규칙 기반 예측을 덮어쓰지 않고 출처와 함께 별도
   열에 둔다.
3. A2 의미번호로 해소할 수 있는 사전 항목만 의미를 확정하고, 여러 발음은
   임의로 첫 항목을 고르지 않는다.
4. coverage는 연도별 파일 목록을 한 번 스캔해 채우고 기존 audio index와
   교차검증한다.
5. `align_warn` 행은 발화 단위 후보 검색에는 포함하되 정확한 TextGrid 어절
   번호 자동 연결에서는 제외하거나 수동 대상으로 보낸다.
6. MFA 2020 파일럿은 현상 자동 판정이 아니라 파일 대응·4-tier·시간 경계·
   실패 기록·재개·연구자 구간 찾기 용이성을 검증한다.

### 5. 연도별 MFA 실행과 기존본 보존 보완

코드 재대조에서 찾은 위험:

- 기존 병합기는 `06_textgrid_eojeol/{연도}`에 유효한 4-tier가 있으면
  G2P 여부와 무관하게 건너뛴다.
- 따라서 새 G2P MFA가 성공해도 2020·2021의 기존 비G2P 최종본을 그대로
  “완료”로 오인할 수 있었다.

개선:

1. `run_eojeol_realign.ps1 -Year 2020`처럼 한 연도만 선택하도록 했다.
2. preflight도 같은 `-Year`만 검사한다.
3. 신규 G2P 4-tier의 기본 출력은
   `D:\20_AUDIO\07_textgrid_eojeol_g2p_staging`으로 분리했다.
4. 기존 `D:\20_AUDIO\06_textgrid_eojeol`은 자동 덮어쓰기·자동 skip 대상에서
   분리되어 그대로 보존된다.
5. 완료 마커는 연도·단계·G2P 모델뿐 아니라 staging 경로까지 일치해야
   유효한 것으로 인정한다.
6. staging 전수 검증과 archive 계획 확인 전에는 자동 승격하지 않는다.

검증:

- 전체 Python 회귀검사 21/21 통과
- PowerShell 정적 안전검사 3/3 파일 통과
- 4-tier Python 회귀검사 3/3은 위 전체 검사에 포함
- `config/paths.json` staging 키 파싱 통과
- `preflight_eojeol_realign.ps1 -Year 2020`: FAIL 0 / WARN 0
- 확인된 이어가기 상태: 2020은 `C:\mfa_tmp\2020` temp가 남아 있고
  align/merge 완료 마커와 MFA 원출력은 없음. 실행 시 먼저 temp 이어가기를
  시도하고 실패하면 안전한 `--clean` 폴백을 사용한다.

이 시점에는 2020 전량 MFA를 시작하지 않았다. 아래의 10발화 격리 파일럿은
전량 실행과 별개다.

### 6. 연도별 10발화·실제 화자 5명 end-to-end 파일럿

사용자 추가 조건:

- 연도별 10발화를 한 화자에서 고르지 않는다.
- CSV의 실제 `speaker_id` 기준 화자 약 5명을 포함한다.
- 선택 발화와 관련 CSV도 같은 파일럿 폴더에 모은다.

구현:

1. 정확히 5명의 실제 화자, 화자당 2발화를 선택했다.
2. 대화 맥락도 퍼지도록 서로 다른 원 세션 5개에서 화자 한 명씩 골랐다.
3. MFA 코퍼스 하위폴더 이름을 `speaker_id`로 만들어, 세션 폴더와 실제 화자를
   혼동하지 않게 했다.
4. 각 연도에 바른 선택행 10개, search master 선택행 10개, 화자 메타 5개를
   함께 저장했다.
5. seed+SHA256 순서로 표본을 고정해 재현 가능하게 했다.
6. 원본 WAV·CSV·형태소 TextGrid는 읽기만 하고 별도 run 폴더에 복사했다.
7. 미완료 출력은 삭제하지 않고 run 내부 `archive_failed`로 옮긴 뒤 재시도하며,
   단계별 JSON marker가 일치하는 경우에만 건너뛴다.

추가 코드:

- `scripts/python/build_stratified_mfa_pilot.py`
- `scripts/python/finalize_stratified_mfa_pilot.py`
- `scripts/run_stratified_mfa_pilot.ps1`
- `tests/test_build_stratified_mfa_pilot.py`

실제 입력 구성 결과:

- 2020–2025 각 연도 10발화·5화자·5세션·화자당 2발화
- 바른 CSV 10행/년, search master CSV 10행/년, 화자 메타 5행/년
- 총 파일 140개, 약 6.1MB, `.partial` 잔여 0
- 실행 폴더:
  `D:\mfa_eojeol\pilots\year10_speaker5\pilot_year10_speaker5_20260724`

첫 2020 실제 시도에서 발견한 시행착오:

- `mfa validate`가 `python-mecab-ko`를 요구하며 실패했다.
- MFA 3.4의 `validate`에는 본 정렬에서 사용하는 `--no_tokenization` 옵션이
  없다.
- 새 토크나이저 의존성을 설치하면 파일럿과 본 정렬의 전처리 경로가 달라지므로
  설치하지 않았다.
- 대신 표본 구성기의 WAV 헤더·lab·CSV·형태소 TextGrid 전수 검사와 실행기의
  화자/발화 수 검사를 입력 QC로 사용한 뒤, 본 경로와 동일한
  `align --no_tokenization --g2p_model_path korean_mfa`를 실행하도록 수정했다.
- 실패 로그는 run 폴더의 `logs\2020.validate.log`에 보존했다.

수정 후 2020 실제 결과:

- MFA 보고: `Found 5 speakers across 10 files`
- G2P MFA 원 TextGrid 10/10
- 표준 4-tier 10/10
- WAV 길이·tier·시간 경계·누락 전수 QC 10/10 통과
- 누락 0, 추가 0, `spn` interval 0
- MFA align 34.249초
- 기존 D: 전량 레이어 변경 0
- 같은 RunId 재실행 시 입력 QC·align·finalize 세 단계가 모두 완료 마커를
  검증하고 재계산 없이 4.3초에 종료함

자동검증:

- Python 전체 회귀검사 23/23 통과
- PowerShell 파서·UTF-8 BOM·필수 안전장치 검사 4/4 파일 통과
- `git diff --check` 통과

상세 실행서:

- `docs/decisions/RUNBOOK_MFA_stratified_year10_pilot_2026-07-24.md`

참고:

- 동봉한 search master 선택행은 현재 2026-07-23 전량본의 스냅숏이다.
- lexicon 예외 발음과 coverage는 아직 미반영이므로 최종 교정 CSV로 부르지
  않는다.
- MFA phones와 `spn`은 분절 인프라 지표이지 연구 현상의 실현 판정이 아니다.

### 7. 2023 MFA 9/10 부분 성공에서 발견한 CSV–WAV 대응 결함

v1 실행 중 2023에서 러너가 다음 오류로 중단했다.

```text
2023 MFA 거짓/부분 성공 차단: TextGrid=9/10
```

안전장치가 완료 마커와 병합을 차단했으며 9개 원출력·temp·로그를 보존했다.
누락 ID는 `SDRW2300000130.1.1.235`였다. MFA 내부 로그는 alignment 단계
`Done 1, errors on 1`, 전체 `Aligned 9, errors on 1, total 10`을 기록했지만
프로세스는 exit 0으로 종료했다.

원인 감사:

- 누락 발화 CSV: 12어절, 3.622초
- 같은 ID WAV: 2.333초
- 같은 세션의 `...273` CSV: `대용량.` 0.613초
- 같은 ID WAV: 4.610초
- `SDRW2300000130` 전체: CSV 428행, WAV 436개
- CSV–동일 ID WAV 길이 차이 0.02초 초과: 363/428
- WAV에만 있는 ID: `.429`–`.436`

이는 단일 난정렬이나 beam 부족이 아니라 발화 ID와 음성 clip 대응 결함이다.
과거 음성 분절 시 사용한 말뭉치 판본 또는 발화 번호 부여가 현재 JSON/CSV와
다를 가능성이 있다. v1의 2020 통과 표본에서도 같은 유형의 길이 이상 2건을
뒤늦게 확인했으므로 v1 전체는 성공 근거로 사용하지 않고 보존만 한다.

개선:

1. 표본 선정 전 후보 세션 전체의 CSV `dur`와 WAV 실측 길이를 대조한다.
2. 2024–2025에서 관찰되는 일관된 약 +0.4초 padding은 세션 중앙값으로
   분리한다.
3. padding 제거 후 잔차 0.025초 이내 대응률이 98% 미만인 세션은 통째로
   제외한다.
4. 실제 선택 발화도 잔차 0.025초를 다시 통과해야 한다.
5. manifest에 CSV 길이, WAV 길이, delta, 세션 padding, 대응률을 기록한다.
6. 최종 4-tier QC에서도 CSV–WAV 잔차를 재검사한다.

v2 실행 ID:

```text
pilot_year10_speaker5_v2_20260724
```

v2 입력 및 최종 검증:

- 2020–2025 각 10발화·5화자·5세션
- 선택 세션 duration 대응률 최저 99.5%
- 선택 발화 잔차 실패 0
- 2024 세션 padding 약 +0.4초, 2025 약 +0.4초로 일관
- v2 실제 MFA/4-tier/QC 전 연도 60/60 통과, `spn=0`
- Python 전체 회귀검사 25/25와 PowerShell 안전검사 4/4 통과

v1 폴더는 삭제·수정하지 않았다. 문제 세션이 얼마나 넓게 분포하는지는 대량
MFA 개선 전에 6개년 전수 자산 대응 감사로 확장해야 한다.

### 8. v2 정상 대응 발화의 기본 beam 난정렬과 자동 재시도

v2 실행에서도 2023이 9/10에서 중단됐다. 누락 발화는
`SDRW2300001955.1.1.164`였다.

- CSV 길이: 3.025초
- WAV 길이: 3.025초
- 세션 padding: 0초
- 세션 duration 대응률: 99.5868%
- 전사: `어 접근하려고 좀 노력을 하고 있습니다.`
- MFA DB: `alignment_log_likelihood=NULL`
- 기본 align worker: `Done 1, errors on 1`

따라서 이 사례는 v1의 WAV 매핑 결함과 달리 기본 beam 10/retry_beam 40에서
정렬되지 않은 난정렬 발화로 분류했다. 같은 2023 표본 10개를 별도
`retry_probe` 출력에서 beam 100/retry_beam 400으로 실행한 결과 10/10
TextGrid를 생성했다.

러너 개선:

1. 기본 정렬이 exit 0이어도 TextGrid 수가 부족하면 부분 성공으로 판정한다.
2. 기본 원출력·temp·로그를 `archive_failed`에 이동해 증거를 보존한다.
3. duration 대응 검증을 통과한 표본만 beam 100/400으로 1회 자동 재시도한다.
4. 확대 beam에서도 수량이 부족하면 실패 종료하고 원출력·temp를 보존한다.
5. 완료 marker에는 `align_mode=default_beam_10_40` 또는
   `retry_beam_100_400`을 기록한다.

이 분리는 중요하다. 잘못 연결된 WAV는 확대 beam으로 억지 정렬하면 안 되고,
정상 대응이 확인된 난정렬만 beam 확대 회수 대상이다.

### 9. v2 6개년 완료

개선한 러너로 같은 v2 run을 재개해 2020–2025 전체를 완료했다.

```text
D:\mfa_eojeol\pilots\year10_speaker5\
  pilot_year10_speaker5_v2_20260724
```

최종 결과:

| 연도 | 실제 화자 | 원 세션 | 입력 | QC 통과 | spn | 정렬 |
|---:|---:|---:|---:|---:|---:|---|
| 2020 | 5 | 5 | 10 | 10 | 0 | 기본 beam으로 완료한 기존 marker |
| 2021 | 5 | 5 | 10 | 10 | 0 | 기본 beam으로 완료한 기존 marker |
| 2022 | 5 | 5 | 10 | 10 | 0 | 기본 beam으로 완료한 기존 marker |
| 2023 | 5 | 5 | 10 | 10 | 0 | `retry_beam_100_400` |
| 2024 | 5 | 5 | 10 | 10 | 0 | `default_beam_10_40` |
| 2025 | 5 | 5 | 10 | 10 | 0 | `default_beam_10_40` |

- 완료 시각: 2026-07-24 22:42:34 KST
- 전체 판정: `PASSED`
- 전체 QC: 60/60
- 전체 `spn` interval: 0
- 관련 CSV: run 내부 `csv\{year}`
- 원 MFA 출력: `mfa_raw\{year}`
- 최종 4-tier: `textgrid_4tier\{year}`
- 발화별 QC: `qc\{year}_utterance_qc.csv`
- 사람이 읽는 요약: `RESULTS.md`
- 기계 판독 요약: `pilot_summary.json`

2020–2022 marker는 자동 `align_mode` 기록 기능을 추가하기 전에 이미 완료되어
해당 필드가 없다. 그러나 각 연도 원출력 10개와 최종 QC 10/10은 완료 marker와
최종 요약에서 다시 검증됐다. 재현 근거를 임의로 고쳐 쓰지 않기 위해 기존
marker는 그대로 보존했다.

2023의 이전 9/10 원출력·temp·로그와 자동 재시도 직전의 기본 beam 실패 자료는
run 내부 `archive_failed`에 보존했다. v1도 별도 폴더에 그대로 남아 있다.

대량 MFA 전에 이 파일럿에서 확인된 다음 두 게이트를 6개년 전수로 확장해야 한다.

1. 세션별 CSV–WAV 대응률 및 발화별 duration 잔차 전수 감사
2. MFA exit code와 별개인 기대 입력–TextGrid 수량 비교 및 제한적 확대 beam 회수

## 커밋·푸시 기록

| 커밋 | 범위 | 원격 푸시 |
|---|---|---|
| `2660232` | 연구 흐름·MFA 역할·기존 전량 CSV 상태 정정, 작업일지 신설 | 완료 |
| `c4777f4` | 원본 JSON→Bareun A1→search master 17,156세션 전수 감사 | 완료 |
| `f0e2582` | 후보 검색·파일 수집·KOINA·수동 판정 층 설계와 2020 파일럿 게이트 | 완료 |
| `d35ec5c` | MFA `-Year` 실행, G2P staging 분리, 기존 4-tier 자동 보존 | 완료 |
| `c8f4938` | 연도별 실제 화자 5명×2발화 MFA 파일럿·관련 CSV·4-tier/QC·실행서 | 완료 |
| `3daef12` | 2023 부분 성공 원인 규명, CSV–WAV duration 대응 가드와 v2 파일럿 | 완료 |
| `1596f92` | 정상 대응 난정렬 자동 확대 beam 회수, 실패 증거 archive, v2 6개년 60/60 완료 기록 | 푸시 예정 |

## 다음 기록 예정

- 연도별 Bareun/search master 파일 수와 행 수 재계산
- 2행 차이의 정확한 파일·발화 ID
- 네 메타데이터 수정 세션의 수정 전/후 값
- lexicon 발음 파일의 실제 열과 조회 키
- 대표 예외 발음 표본에서 현재 CSV와 사전 발음 비교
- 수정 파일, 테스트 결과, 커밋 ID
