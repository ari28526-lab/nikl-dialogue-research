# r2 공통발음사전 기반 MFA 연구 데이터 계약과 전 과정

확정일: 2026-07-30

적용 범위: 모두의 말뭉치 2020–2025년 전수 재정렬

상태: 외부 방법론·코드 리뷰 전 동결 초안

## 1. 연구 목적

이 파이프라인의 최종 목적은 자동 phone 자체를 분석값으로 쓰는 것이 아니다.

1. CSV/Parquet에서 특정 형태소 또는 표기상 음운 환경을 검색한다.
2. 해당 발화의 WAV와 TextGrid를 같은 `utt_id`로 모은다.
3. 선택된 발화에만 KOINA 운율 분석과 필요 시 이어붙이기를 수행한다.
4. 연구자가 음성과 TextGrid를 함께 보고 목표 현상의 실제 실현 여부를
   별도 판정한다.

따라서 MFA의 G2P/phone은 청취 위치를 찾게 해 주는 **대략적인 자동 정렬
보조 정보**이다. 사전 발음, 규칙 발음, MFA phone, wav2vec2 phone, 연구자
실현 판정은 서로 다른 자료이며 어느 열이나 tier도 다른 것을 덮어쓰지 않는다.

## 2. 자료 층위와 불변 원칙

| 층위 | 정본 또는 출처 | 핵심 역할 | 금지 사항 |
|---|---|---|---|
| 원시 말뭉치 | 외장 저장장치의 NIKL JSON/WAV | 원문·메타데이터·음성 증거 | 제자리 수정 금지 |
| 형태소·화자 메타데이터 | Bareun 결과, NIKL 화자/대화 메타데이터 | 형태소 및 사회·대화 검색 | 직접 상대자를 근거 없이 추정 금지 |
| 동결 pre-MFA 입력 | `D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725` | LAB 생성과 MFA 입력 | 최종 연구 검색 CSV라고 부르지 않음 |
| 공통 발음 계약 | `D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728` | 6개년 동일 사전·모델·phone 기준 | 연도별 inline G2P, phone 기준 변경 금지 |
| 연도별 MFA 산출물 | D: staging의 DB·interval CSV·4-tier TextGrid·QC | 시간 정렬과 실패 추적 | QC 전 정본 승격·삭제 금지 |
| 연구 검색 마스터 | 최종 CSV + 연도별/전연도 Parquet | 형태·표기·발음·화자·파일 연결 검색 | 자동 phone을 실제 실현으로 해석 금지 |
| 후보 점검 묶음 | 선택 발화의 WAV/TextGrid/CSV/manifest | 연구자 청취·시각 판정 | 원본 경로와 시간 대응을 잃지 않음 |
| 연구자 판정 | 별도 decision table | 실제 실현 여부의 유일한 판정값 | MFA/wav2vec2 결과로 자동 대체 금지 |

`D:\`는 실행과 대용량 산출물의 메인 드라이브이다. E:는 검증된 archive에만
사용하며 실행 root로 쓰지 않는다.

## 3. 입력 계약

### 3.1 원시·정규화 입력

모든 입력 행은 최소한 다음 연결 좌표를 보존해야 한다.

| 구분 | 필수 값 | 출처·의미 |
|---|---|---|
| 발화 좌표 | `utt_id`, `year`, `session_id`, `utt_seq` | JSON·파일명에서 검증한 전역 조인 키 |
| 음성 | 원 WAV 경로, 크기, duration, 선택적으로 SHA256 | 읽기 전용 음향 증거 |
| 텍스트 | `form`, `original_form`, 필요 시 `reference_form` | 원전 필드를 보존하고 정규화·보완값을 분리 |
| 형태소 | `tagged`, 형태소 표면형·품사·어절 번호 | Bareun 분석과 어절 대응 상태 포함 |
| 화자 | 발화 화자 ID와 정규화 사회변수 | NIKL 메타데이터 |
| 대화 | `dialogue_id`, 대화 참여자 ID 목록, `co_speaker_ids` | 같은 대화의 다른 참여자이며 직접 상대자 단정 아님 |
| 품질 | WAV/JSON/CSV 존재, quarantine, overlap/note | 누락과 분석 제외 근거 |

### 3.2 동결 pre-MFA 입력

현재 `pre_mfa_v1_20260725`는 LAB을 만들기에 필요한 `utt_id`, `year`,
`session_id`, `form`, `pron_reference_form`과 build meta를 동결한 입력층이다.
공통사전의 6개년 관측 어휘도 이 정확한 root에서 만들었다. 그러므로 다음은
전수 일치해야 한다.

- 연도별 발화 수와 WAV 수
- `utt_id` 유일성 및 WAV basename과의 일치
- `pron_reference_form`의 공백 기준 어절 수
- LAB 내용과 `pron_reference_form`의 전수 동등성
- 공통사전 vocabulary contract의 search root·SHA

이 층은 **MFA 입력으로 충분하지만 연구용 최종 CSV는 아니다**. 형태소별
철자 로마자, 어절별 철자 로마자, 우리말샘 발음, 대화 참여자, 파일 coverage
등의 최종 검색 계약을 별도로 완성·검증해야 한다.

### 3.3 공통 발음·모델 입력

연도별 MFA는 아래 고정 실물만 사용한다.

- acoustic: Korean MFA v3.3.0
- G2P: Jamo v3.2.0, `unicode_decomposition=true`
- dictionary:
  `common_pron_mfa_r2.dict`
- release manifest:
  `00_contract\release_manifest.json`
- adoption:
  `00_contract\adoption_contract.json`
- dictionary SHA256:
  `24c406604c86a5df833a7e47d809f252d6fc39dc566a6d3818b3d3ffeb04fb86`

adoption은 `schema_version=common_pron_mfa_adoption.v3`, `status=passed`,
`allow_yearly_mfa=true`여야 한다. 연도별 inline G2P는 기본 경로가 아니며
6개년 생산 실행에서는 허용하지 않는다.

## 4. 발음 정보의 의미와 저장 위치

| 이름 | 단위·위치 | 의미 | 실제 실현 여부 |
|---|---|---|---|
| `form` | 발화 CSV | 말뭉치의 기본 전사 | 아님 |
| `original_form` | 발화 CSV | JSON 원전 표기 | 아님 |
| 형태소/어절 철자 로마자 | 연구 검색 CSV/Parquet | 표기 기반 환경 검색 | 아님 |
| `pron_reference_*` | 연구 검색 CSV/Parquet | 규칙 기반 예상 발음과 MFA 입력 보조 | 아님 |
| 우리말샘 발음 | 연구 검색 CSV/Parquet의 보조열 | 표제어·의미번호에 따른 사전 예외 발음 | 아님 |
| r2 사전 phone | 공통사전·계약 | MFA가 정렬에 사용한 phone 후보 | 아님 |
| `phones`/의미 별칭 `phones_mfa` | TextGrid·정렬 index | MFA의 시간 정렬 phone | 아님 |
| wav2vec2 phone | 별도 보조열·별도 tier | 선택 후보의 독립적인 음향 phone 추정 | 아님 |
| `human_judgment` | 별도 판정표 | 연구자가 듣고 본 실현 판정 | **맞음** |

우리말샘 발음은 검색·비교용 어휘부 정보다. 공통 MFA 사전에 임의의 다중
변이로 전부 넣지 않으며, 발화가 사전형과 다르거나 의미번호가 불확실하면
그 상태를 명시한다.

## 5. 연도별 처리 상태 기계

연도는 항상 하나씩 처리한다.

```text
frozen input
  → preflight
  → LAB contract
  → MFA alignment DB
  → direct DB interval export
  → operational 4-tier TextGrid
  → coverage/integrity/analysis-ready QC
  → 연구자 표본 검토
  → 해당 연도 승인
  → 다음 연도
```

2020·2021도 구결과와 차이가 작더라도 r2로 전수 재실행한다. difference
inventory는 구결과 재사용 승인이 아니라 변경 원인과 규모를 남긴 전환 감사다.
상위 실행기와 하위 러너 모두 `-AllowBaselineCommonPronRerun`을 명시해야만
2020·2021을 시작하도록 한다.

완료 marker는 이름만으로 재사용하지 않는다. search master, LAB 입력,
공통사전, acoustic/G2P, alignment contract SHA가 다르면 구 marker나 temp를
성공으로 인정하지 않고 stale archive로 격리한다.

## 6. 연도별 출력 계약

### 6.1 실행·복구 산출물

한 연도마다 최소한 다음을 보존한다.

- MFA alignment SQLite DB
- `phone_intervals.csv`, `word_intervals.csv`
- 실행 transcript, heartbeat, 완료/실패 marker
- LAB input contract와 alignment contract
- 누락·quarantine·재시도·부분 성공 inventory
- direct DB export manifest
- 4-tier QC JSON/CSV

대용량 raw 2-tier TextGrid를 먼저 전량 썼다가 다시 읽는 이중 I/O 대신,
MFA DB에서 연구용 4-tier를 직접 내보낸다. 단, direct export가 MFA의 word와
phone interval을 바꾸지 않았다는 표본·전수 계약 검증을 유지한다.

DB와 temp는 해당 연도 QC 및 복구 가능성 확인 전 삭제하지 않는다.
`-CleanupDirectDbAfterMerge`는 첫 전수 실행 명령에 넣지 않는다.

### 6.2 운영 4-tier TextGrid

현재 대량 파이프라인의 호환 표준은 다음 순서와 이름이다.

```text
words
phones
morphemes
utterance
```

- `words`: 공통사전과 LAB을 사용해 정렬한 어절
- `phones`: 의미상 `phones_mfa`; 자동 정렬 phone이며 실제 실현 아님
- `morphemes`: 기존 형태소 TextGrid의 `words` 경계를 복사한 legacy 출처;
  형태소 내부의 새 음향 경계를 추정한 것이 아님
- `utterance`: 발화 전사

모든 IntervalTier는 `0–xmax`를 연속적으로 덮고, 라벨 없는 구간도 명시적
빈 interval로 가져야 한다. 운영본에는 시간 padding을 넣지 않는다.

점검 사본은 필요할 때만 WAV 양끝에 0.05초 무음을 넣고
`words/phones_mfa/morph_analysis/utterance_info`로 만든다. 이 경우
`source_time = review_time - left_padding` 환산값을 manifest에 남긴다.
운영 4-tier를 3-tier로 줄이거나 tier 이름을 바꾸는 일은 호환성 전수 검증
전에는 하지 않는다.

### 6.3 연구 검색 마스터와 MFA 보조 레이어

최종 검색 자료는 발화 1행 정본 CSV와 연도별/전연도 Parquet 미러로 구성한다.
최소 컬럼군은 다음과 같다.

- 조인: `utt_id`, `year`, `session_id`, `utt_seq`
- 화자·대화: speaker ID, 사회변수, dialogue ID, 참여자/co-speaker 목록
- 텍스트: `form`, `original_form`, `reference_form`
- 형태: 형태소 표면형·품사·어절 번호, 정렬 상태
- 철자 검색: 형태소별·어절별 철자 로마자
- 발음 참고: 규칙 발음과 우리말샘 발음의 한글·로마자·IPA·출처·status
- 파일 연결: WAV/TextGrid 경로와 존재·quarantine 상태
- MFA 보조: `pron_mfa`, `pron_mfa_ipa`, `n_spn`, `spn_ratio`,
  `align_status`, alignment contract ID

`pron_mfa`는 `words` 경계로 phone을 어절별로 묶어 생성해야 하며,
`utt_id + eojeol_index`를 통해 형태소·철자·사전 발음과 연결한다.
이 MFA 보조 레이어를 전수 생성하는 구현은 아직 최종 완료되지 않았으므로,
6개년 TextGrid 완성만으로 연구 CSV까지 완성되었다고 보고하지 않는다.

## 7. 후보 추출 이후 출력

검색 결과를 실제 검토 대상으로 옮길 때는 다음 구조를 기본으로 한다.

```text
candidate_bundle/
  README.md
  manifest.csv
  checksums.json
  candidates.csv
  by_year/<year>/
    <utt_id>.wav
    <utt_id>.TextGrid
    <utt_id>.utterance.csv
    <utt_id>.candidates.csv
```

manifest에는 원본·사본 경로, 크기/SHA256, year/session/speaker, 원시간과
점검시간 대응, alignment contract ID를 둔다. 파일 basename은 `utt_id`로
통일한다.

KOINA는 선택된 후보에만 수행하고 별도 표/온디맨드 tier로 추가한다.
인접 발화 이어붙이기도 선택 후보에만 수행하며, 각 원발화의 source time과
stitched time 대응 manifest를 만든다. wav2vec2 phone도 선택 후보의 독립
보조열로만 추가한다.

## 8. 연도별 QC와 다음 연도 게이트

다음 연도로 넘어가기 전에 최소한 다음을 확인한다.

1. 입력 발화·WAV·LAB 수와 산출물 coverage
2. 누락·quarantine·부분 성공·재시도 사유 전수 inventory
3. TextGrid 4-tier 이름·순서·`0–xmax` 연속성·duration
4. `spn` 수와 비율, 빈 word/phone/morpheme/utterance
5. DB interval과 direct 4-tier 표본 동등성
6. 공통사전·acoustic·G2P·adoption·input contract SHA
7. 최소 5명 이상 화자와 문제 유형을 포함한 연구자 표본 검토
8. 처리 시간, words/sec, 세션별 outlier와 D: 공간

QC 실행 순서와 기계가독 증거는 다음으로 고정한다.

1. `audit_mfa_4tier_year.py`: 연도 전수 coverage·tier·경계·duration
2. `verify_mfa_db_4tier_sample.py`: 서로 다른 세션 최소 5개의 보존 DB
   재수출 동등성. `--input-contract-id`를 반드시 기록한다.
3. `build_mfa_year_phone_inventory.py`: 실제 phone interval 전수 집계,
   `spn=0`, acoustic 허용 inventory 밖 phone 0
4. 연구자 표본 검토: 최소 5화자의 WAV/TextGrid/LAB/CSV 연결, tier 경계,
   검색 편의성만 판정한다. 구체적인 음운 실현은 이 단계의 판정값이 아니다.
5. `validate_mfa_r2_review_workbook.py`: 원본 `REVIEW.csv`의 불변 연결 열과
   작성된 XLSX를 전수 대조하고 승인 보고서를 만든다.
6. `preflight_next_year_after_qc.py`: 위 감사·marker·보존 DB뿐 아니라
   `--sample-equivalence-report`와 `--researcher-review-report`를 필수로
   받아 동일 DB·input contract·alignment contract와 결합한다.

따라서 콘솔 성공이나 연구자 구두 확인만으로 다음 연도로 넘어가지 않는다.
연구자 보고서가 `status=approved`, `allow_bulk_mfa=true`이고 표본 보고서가
같은 DB와 input contract를 가리킬 때만 전환 gate가 열린다.

6개년 완료 뒤에는 `audit_mfa_cross_year_contracts.py`로 모든 방법 계약과
허용 phone inventory SHA가 동일한지 전수 감사한다. 연도별 관측 phone
집합은 실제 어휘가 달라 서로 다를 수 있으므로 동일성을 강제하지 않는다.
대신 모든 관측 phone이 동일 허용 inventory의 부분집합이고 각 연도의 실제
`spn` interval이 0인지 증명한다. 논문에는 “같은 기준”이라는 추상적
표현만 쓰지 않고, 모델 버전·설정·사전 SHA·adoption SHA·alignment contract,
허용 inventory SHA를 함께 기록한다.

## 9. 실패·복구·저장장치 정책

- 한 연도가 실패하면 다음 연도를 자동 시작하지 않는다.
- 프로세스 종료, 최종 manifest 부재, coverage 부족은 성공으로 간주하지 않는다.
- 재개는 checkpoint/input contract가 동일할 때만 한다.
- raw corpus와 통과한 이전 정본은 덮어쓰지 않는다.
- 삭제 전에는 E: archive의 CRC, 파일 수·원 bytes, DB SHA, archive SHA를
  검증한다.
- D: 용량은 연도별로 QC·archive·정리한 뒤 다음 연도를 시작해 관리한다.
- MFA와 D: 대량 archive, KOINA, stitch, 다른 대규모 검색 빌드를 동시에
  실행하지 않는다.

## 10. 현재 완료와 미완료

완료:

- r2 공통사전 생성·연구자 27건 승인·적용
- 2020/2021 difference inventory
- adoption v3 `passed`, `allow_yearly_mfa=true`
- 구 pre-Jamo 2020/2021 결과·DB의 E: 압축 archive와 검증
- 검증 후 D:의 정확한 구 산출물 5개 경로 정리

아직 시작하지 않은 것:

- r2 기준 2020–2025 전수 MFA
- 최종 연구 검색 CSV/Parquet 계약의 전수 완성
- post-MFA 발음·정렬 보조 레이어의 전수 생성
- 연구 주제별 후보 bundle, KOINA, 실제 실현 판정

## 11. 외부 리뷰 후 첫 실행 명령

외부 리뷰가 `GO` 또는 필수 수정 반영 뒤 `GO`일 때만 2020을 시작한다.

```powershell
Set-Location "C:\Users\ari30\research\2026_summer_research"

$release = "D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728"

& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\run_pre_mfa_bulk_safe.ps1" `
  -Years 2020 `
  -PreferD `
  -UseDirectDbExport `
  -SkipSearchMasterBuild `
  -CommonPronManifest "$release\00_contract\release_manifest.json" `
  -CommonPronAdoptionContract "$release\00_contract\adoption_contract.json" `
  -AllowBaselineCommonPronRerun
```

이 명령에는 cleanup이나 자동 정본 승격을 넣지 않는다.
