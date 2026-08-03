# 2026년 8월 작업 기록

## 2026-08-01 — 로마자 음소 보조층 원격 검토 링크 보정

### 문제 발견

사용자가 외부 컴퓨터에서 Dropbox 동기화 본을 열었을 때 새 5-tier
TextGrid 링크를 열 수 없었다. 12발화의 WAV·기존 4-tier·새 5-tier
파일은 모두 Dropbox 검토 폴더에 있었으나, workbook 하이퍼링크가
생성 컴퓨터의 `D:\...` 절대경로를 담고 있었다.

### 조치

- 기존 `PHONEME_ROMAN_PILOT.xlsx`는 덮어쓰지 않았다.
- `PHONEME_ROMAN_PILOT_PORTABLE_20260801.xlsx`를 새로 생성했다.
- 12행의 WAV·기존 4-tier·새 5-tier, 총 36개 hyperlink를 같은 폴더의
  파일명만 사용하는 상대경로로 변경했다.
- workbook 재로딩, 36개 링크의 상대경로·대상 존재, 원본 미변경,
  네 시트 렌더링을 검증했다.
- Dropbox 전달본과 프로젝트 검증본의 SHA-256은
  `2d21408ed215c8778e1b2a530753eb6486794e596a7ed2301df9c8c7ba0fb714`로
  일치했다.
- 이후 `build_phoneme_roman_pilot.py`도 최초 생성부터 상대링크만 허용하도록
  바꾸어 재발을 차단했다.

### 연구 및 데이터 영향

- D: 원본/파일럿 정렬 산출물은 변경하지 않았다.
- `phones_mfa`, 음성, TextGrid 경계, 로마자 대응값은 변경하지 않았다.
- 검토 접근성만 보정했으며 어떤 연구자 실현 판정도 추가하지 않았다.

## 2026-08-01 — 서울 코퍼스 참조 tier 재설계 검토

- 사용자가 `phoneme_r_auto`를 철자·예측발음에서 기저형을 역복원하는
  층이 아니라 `phones_mfa`의 broad Roman 음운전사로 재정의했다.
- 이 수정을 구현하던 중 사용자가 tier 전체 구성을 먼저 재검토하도록
  요청해, 코드는 미완성 초안 상태에서 중지하고 산출물·커밋·푸시를
  하지 않았다.
- `WorkshopLecture1-v4.pdf` 45쪽과 `KCI_FI002007633.pdf` 7쪽을 전체 텍스트
  추출하고, tier 예시·음소 기호표·검색 예시가 있는 페이지를 PNG로
  렌더링해 시각 확인했다.
- 서울 코퍼스의 7-tier는 철자형/발음형 utterance·phrasal-word,
  두 phrasal-word 로마자, phoneme로 구성된다. 음소·어절·발화
  경계를 동기화했으며 실제 발음형은 사람 전사·수정을 거친 값이다.
- 현재 프로젝트는 이 원칙을 참조하되 G2P/사전 예측발음을 서울 코퍼스의
  수동 발음형과 같게 취급하지 않는 6-tier 적용안을 작성했다.
- 제안 tier는 `words / phones_mfa / phoneme_r_auto / utterance /
  utterance_orth_r / morph_analysis_utt`이다. 세 발화 수준 tier는 같은
  word-derived span을 쓰고, 형태소 문자열은 실측 시간경계를 주장하지
  않는다.
- 제안 정본:
  `docs/decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md`.

### KOINA 및 연결 발화 호환성 추가 검토

- 연구자가 추후 KOINA를 선별 적용하고 여러 발화 파일을 이어 붙일 수
  있다고 명시했다.
- KOINA는 전수 기본 6-tier가 아니라 `utt_id`로 결합하는 독립 파생
  산출물로 유지하는 안을 설계 문서에 추가했다.
- KOINA가 자체 생성한 word/phoneme 정렬은 공통 MFA의 `words`와
  `phones_mfa`를 덮어쓰지 않고, 필요할 때 `koina_*_auto`로 분리한다.
- 연결 TextGrid에서는 세 발화 수준 tier를 원 발화마다 반복하고,
  연결본 전용 `source_utt_id`와 필요 시 `speaker` tier를 둔다.
- 현재 `stitch_session.py`는 0.05초 인공 무음과 구형
  `morphemes_legacy`를 사용하는 맥락 검토용이다. 인공 seam을 자연스러운
  AP/IP 경계로 오인할 위험이 있어, 새 tier와 `review/koina_batch/
  continuous_source` mode 계약을 구현하기 전에는 KOINA 분석 입력으로
  사용하지 않기로 했다.
- 연결 좌표는 `stitched_id/order/utt_id/source time/stitched time/gap/
  contract SHA` manifest로 원 발화에 역매핑할 수 있게 한다.

## 2026-08-01 — 서울 코퍼스 참조 6-tier 확정 및 최소 파일럿

### 연구자 결정

- 차기 기본 연구 표시를 `words / phones_mfa / phoneme_r_auto /
  utterance / utterance_orth_r / morph_analysis_utt` 6-tier로 확정했다.
- 철자 로마자는 현행 `form_roman`, 형태소 tier는 한글 `형태소/POS`를
  사용한다. 두 tier 모두 형태소 음향 시간경계를 주장하지 않는다.
- KOINA는 선별 파생 산출물이며 기본본에 빈 tier를 만들지 않는다.

### 구현과 구버전 보존

- 기존 `research_textgrid.py`와 4/5-tier 출력은 수정·삭제하지 않았다.
- 새 `research_textgrid_v2.py`에 6-tier 작성·검증과 연결 검토본 생성을
  분리했다.
- 연결본은 기본 6-tier에 `source_utt_id/speaker`를 추가하고, 각 원발화의
  source time과 stitched time을 manifest로 기록한다.
- 기존 `stitch_session.py`는 구형 맥락 검토 도구로 보존했다. 새 코드에서
  `stitch_mode=review`, `koina_cross_seam_allowed=false`를 강제했다.

### 최소 파일럿 결과

- 프로젝트 보존본:
  `outputs/textgrid_6tier_mini_pilot_20260801`
- 단일 발화: `SDRW2000000510.1.1.98` (`혹시 요즘`), 6-tier 1건
- 연결본: 같은 세션·같은 화자
  `SDRW2200001103.1.1.67 → SDRW2200001103.1.1.269`, 0.05초 인공 gap,
  8-tier 1건
- 두 연결 발화는 비인접하므로 자연스러운 대화 연속 자료가 아니다.
  연결 구조·좌표 검토에만 사용하며 seam 횡단 운율 해석을 금지했다.
- 단위시험 13건 통과. 실자료 독립 검증에서 입력 9개·출력 9개의 SHA,
  모든 tier의 0–xmax 연속성, 기존 word/phone 보존, phone–phoneme 경계,
  발화 수준 세 tier 경계, 연결 원시간 역매핑이 모두 통과했다.
- KOINA는 실행하지 않았고 KOINA 빈 tier도 생성하지 않았다.

### 재현성 메타데이터 보정

- 첫 최소본은 미완성 v2 초안의 `phoneme_roman_aux.v2`를 manifest에
  기록했다. 구 5-tier 코드를 그대로 보존하고 새 6-tier를 별도 모듈로
  분리하기로 했으므로 현재 재현 가능한 의존성은 기존 phone mapping
  `phoneme_roman_aux.v1`과 새 표시 계약 `research_textgrid.v2`의 조합이다.
- 첫 실물은 삭제하지 않고
  `outputs/textgrid_6tier_mini_pilot_20260801_pre_repro_fix_ARCHIVE`로 옮겼다.
- 현재 코드로 동일 최소본을 새 최종 root에 다시 생성하고 독립 검증을
  재실행했다. 최종 `PILOT_VERIFICATION.json`은 `status=success`다.

### Dropbox 전달

- 전달 위치:
  `C:\Users\ari30\Dropbox\TEXTGRID_6TIER_MINI_PILOT_20260801`
- 첫 복사 명령은 `Copy-Item -LiteralPath`에 wildcard를 사용해 대상 폴더만
  만들고 파일 0개 상태에서 안전 중단됐다. 프로젝트 보존본과 원 입력에는
  변화가 없었다.
- 비어 있는 대상임을 확인한 뒤 검증된 11개 파일을 절대경로로 개별 복사했고,
  프로젝트 보존본과 파일별 SHA-256이 전부 일치했다.
- 생성 직후의 dirty worktree commit 표시를 보완하기 위해 최종 구현 commit
  `fb275b7`과 세 스크립트·시험·파일럿 manifest SHA를 묶은
  `CODE_PROVENANCE.json`을 추가했다. 이 파일도 복사 SHA가 일치한다.
- 최종 전달본은 12파일·308,428 bytes다.

## 2026-08-01 — 전수 6-tier·동반표 생산 후보 정리

### 시작 점검에서 확인한 불일치

- 연구자가 최종 6-tier와 TextGrid 연결 CSV를 승인했지만,
  실제 전수 runner의 direct 출력은 여전히 구
  `export_mfa_db_4tier.py`를 호출하고 있었다.
- 최종 search Parquet/post-MFA 추출 스크립트도 실물이 없었다.
  이 상태로 전수 MFA를 시작하면 새 r2 정렬 후에도 구 4-tier와
  미완성 CSV만 남을 수 있어 전수 실행을 계속 차단했다.

### 생산 코드 수정

- MFA SQLite에서 승인된
  `words/phones_mfa/phoneme_r_auto/utterance/utterance_orth_r/
  morph_analysis_utt` 6-tier를 직접 쓰는
  `export_mfa_db_research_6tier.py`를 추가했다.
- 연도별 logical sidecar로
  `utterance_alignment/word_intervals_mfa/phone_intervals_mfa/
  excluded_utterances.csv.gz` 4종을
  생성했다. 510만 발화별 개별 CSV는 만들지 않고, 선별
  후보 bundle에서만 파생하도록 했다.
- 형태소 표에 발화당 1행/어절 `eojeol_tokens`를 추가해 어절
  철자·Roman·형태소 tagging을 검색할 수 있게 했다.
- r2 공통사전 전수 runner는 새 6-tier direct export를 생략하면
  중단하고, legacy 4-tier로 조용히 폴백하지 않도록 바꿘었다.

### 실자료가 잡은 좌표 혼동

- 첫 회귀에서 2020–2024는 통과했지만 2025의
  `SARW2500000414.1.1.2`가 어절 수 불일치로 차단됐다.
- 형태소 원 `form`은 `2사람이` 1어절이고 MFA 입력용
  `pron_reference_form`은 원 JSON에서 복원한 `두 사람이` 2 word였다.
- 초안의 단일 `eojeol_idx`는 다음 항목을 모두 혼동했다. 이를
  `eojeol_idx`(원 form/tagged), `reference_eojeol_idx`(MFA reference),
  `mfa_word_idx`(유표 MFA word)로 분리했다.
- 이 분리는 형태소–phone의 자동 직결을 주장하지 않고,
  `utt_id`를 중심으로 검색 후보와 정렬 참조값을 안전하게 결합한다.

### 원자적 승격과 비싼 재실행 방지

- 초안은 count gate 실패를 확인하기 전 gzip `.partial`을 완성 이름으로
  승격했다. 모든 조인·개수·label gate 통과 후에만 승격하도록
  순서를 바꾸고 실패 시 완성 gzip 0개임을 회귀시험으로 고정했다.
- 출력 schema 실패 때 이미 끝난 MFA를 다시 돌리지 않도록
  `inspect_mfa_db_checkpoint.py`와 `direct_db_ready` marker를 추가했다.
  이 marker는 정렬 계산 재사용 가능만 뜻하며 분석 승인은 별도다.
- direct align marker만 있고 merge marker가 없을 때 legacy 4-tier 병합으로
  떨어지는 경로도 명시적으로 차단했다.

### 60발화 회귀 결과와 현재 gate

- 2020–2025 각 10발화, 총 60/60 6-tier·동반표 출력 성공
- 기존 4-tier 대비 duration·word·phone 불일치 0
- DB checkpoint 6/6 `success`, coverage 100%, actual `spn=0`
- 전체 Python 263시험, PowerShell 16파일 정적 안전 검사 통과
- 전수 MFA는 시작하지 않았다. 미정렬 분류·Parquet·우말샘
  1:N 후보·독립 6-tier QC·510만 파일 운영을 외부 리뷰한 뒤만
  2020 전수에 `GO`한다.

정본 제안:
`docs/decisions/PROPOSAL_full_production_TextGrid_CSV_contract_20260801.md`.

외부 리뷰 프롬프트:
`docs/reviews/PROMPT_external_review_full_production_TextGrid_CSV_20260801.md`.

## 2026-08-01 — 전수 6-tier·동반표 외부 리뷰 수정

### 외부 판정과 작업 경계

- 외부 리뷰는 BLOCKER 0, HIGH 2, MEDIUM 10, LOW 6으로
  `GO AFTER FIXES`를 판정했다.
- HIGH는 (1) 새 6-tier 연도 QC/다음 연도 gate 부재, (2) 예상 미정렬·
  사용 불가 자료의 연구자 승인 제외 계약 부재였다.
- 이 수정 중에는 기존 D: 파일럿 SQLite를 읽기만 했고 MFA·KOINA·wav2vec2를
  실행하지 않았다. 2020–2025 전수 MFA도 시작하지 않았다.

### 승인 제외와 정확 대사

- input contract에 묶인 승인 CSV/JSON 계약을 신설했다. 자동 후보는
  `pending`만 쓰며, 연구자·승인시각·review CSV SHA가 없으면 계약이 아니다.
- exporter에 네 번째 동반표 `excluded_utterances.csv.gz`를 추가했다.
- 99% 휴리스틱을 폐기하고 active LAB, 정렬 성공, 승인 제외, quarantine의
  정확 ID 대사를 요구한다. 목록 밖 누락·stale 승인·승인 밖 quarantine은
  한 건도 통과하지 못한다.
- `prepare_mfa_year_exclusion_review.ps1`은 lab 전수 force-verify, 입력 후보
  감사, 불량 WAV dry-run inventory, pending 검토표까지만 만들며 WAV 이동과
  자동 승인을 하지 않는다.

### 독립 연도 QC와 재현성

- 6-tier 연도 감사, 보존 DB 세션 표본 재수출, 다음 연도 gate를 구현했다.
- 연 phone 표 감사가 수천만 행을 메모리에 올리지 않도록 스트리밍 key/count
  검증으로 바꿨다.
- DB checkpoint 재사용 때 DB를 다시 quick-check하고 marker count와 대조한다.
- TextGrid 구간은 허용오차 밖 0–xmax 초과를 조용히 clamp하지 않고 실패한다.
- gzip은 `mtime=0`, 소문자 부울, fsync 후 승격으로 고정했다.

### 검색 표기와 Parquet

- machine-readable companion schema v2에 네 표의 열 순서·dtype·nullable·
  null·부울·BOM·gzip 계약을 동결했다.
- legacy `form_roman`은 보존하되, 혼합 어절 전체가 `∅`가 되는 문제를
  `form_roman_v2`/`orth_roman_v2`로 해결했다. 비한글은 `⟨literal⟩`,
  한글은 철자 Roman으로 남는다. 발음 규칙이나 실현 판정은 추가하지 않았다.
- 별도 임시 분석 venv에만 `pyarrow==21.0.0`을 설치했다. 동결 MFA conda
  환경은 변경하지 않았다.
- Windows에서 Parquet partial의 읽기 전용 fd `fsync`가 실패한 것을 실물로
  발견해 `rb+` fd로 수정했다. 실패 root에는 success manifest가 없다.

### 실측 결과와 정정

- 최종 60발화: utterance 60, word 479, phone 1,801, spn 0,
  96파일 673,456 bytes, active partial 0.
- 기존 문서의 word 합계 529는 연도별 수치를 잘못 더한 오기였다. 정확한
  합계 479로 정정했고 원 실물·연도별 값은 변하지 않았다.
- legacy 대비 혼합 표기 2건의 `utterance_orth_r`만 의도적으로 변경,
  다른 tier 불일치 0. 최종 독립 재출력 TextGrid SHA 불일치 0.
- 결정적 gzip 24/24 SHA 불일치 0, Parquet 24/24 값·dtype·행 순서 왕복 통과.
- 10,000 합성 발화 exporter: 최초 87.738초, 재개 38.404초,
  Python 추적 메모리 peak 9.214MiB, partial 0.

### Bareun provenance

- 2026-07-09~10 사용한 클라우드 서버 build ID가 당시 API·로그에
  보존되지 않아 사후 정확 복원이 불가능함을 확인했다.
- 현재 버전을 과거 버전으로 허위 소급하지 않고 분석일, endpoint,
  `bareunpy==2.0.1`, 검증 결과와 이 한계를 논문에 명시하기로 했다.
- 현재 MFA/CSV는 동결 A1을 읽을 뿐 Bareun을 다시 호출하지 않는다.

처리표:
`docs/reviews/RESOLUTION_external_review_full_production_TextGrid_CSV_20260801.md`.

기계 증거:
`outputs/reports/EVIDENCE_research_6tier_post_review_20260801.json`.

### 외부 리뷰 수정 최종 회귀 검사

- Python 전체 테스트 287개 전부 통과.
- PowerShell 대량 작업 안전 정적 검사 대상 17개 파일 전부 통과.
- quarantine된 발화가 연구자 승인 계약 없이 빠질 수 없고, 승인된 경우에도
  별도 제외표로 남는 직접 회귀 테스트를 추가했다.
- 변경된 Python 실행 파일의 문법 컴파일과 Git 공백 검사를 통과했다.
- 이 결과는 코드·소형 표본 수준의 생산 준비 판정이다. 2020년 전수 시작 전에
  연구자가 pending 제외 후보를 확인하고 승인 계약을 만드는 단계는 여전히 필요하다.

## 2026-08-01 무인 연도 큐와 연도 내부 재계산 방지

- 연구자가 며칠간 계속 확인하지 못해도 2020–2025를 연도별 독립 작업으로
  순회하는 `run_mfa_year_queue_safe.ps1`을 추가했다.
- 기존 러너에서 temp 재개 실패 뒤 자동으로 temp를 지우고 연도 전체를 `--clean`
  재계산하던 폴백을 기본 금지했다. 명시적 `-AllowFullCleanRetry`가 없으면
  temp·SQLite DB·로그를 보존하고 해당 연도만 차단한다.
- 무인 큐는 full-clean 스위치를 전달하지 않는다. 승인 제외 계약이 없으면
  pending 후보표만 만들고 MFA를 시작하지 않으며, 다른 연도의 준비는 계속한다.
- 성공 연도는 독립 6-tier 전수 감사와 보존 DB 표본 재수출까지 자동 수행하지만,
  연구자 검토와 정본 승격은 `human_review_pending`으로 남긴다.
- 읽기 전용 상태판 `show_mfa_year_queue_status.ps1`을 추가했다.
- 전수 시작 전 공통사전·저장공간·lock·입력/승인 계약·staging 충돌·테스트·Git
  상태를 합쳐 `GO/NO_GO`로 판정하는 `preflight_mfa_year_queue.ps1`을 추가했다.
- PowerShell 안전 검사 대상 20개 파일이 모두 통과했다.

결정 문서:
`docs/decisions/DECISION_incremental_unattended_year_MFA_20260801.md`.

## 2026-08-01 전수 직전 최종 preflight와 연구 설계 슬라이드

### 최종 preflight 실측

- 첫 실행에서 Windows PowerShell 5.1의 CP949 출력과 Generic.List JSON 직렬화
  문제를 발견했다. `PYTHONUTF8=1`, 평탄화 배열, 명시적 최종 상태 계산으로 고쳤고
  PowerShell 정적 검사에 회귀 조건을 추가했다.
- 수정 후 최종 preflight는 공통 Jamo 사전/adoption SHA, D: `DATA_SSD`,
  318.5 GiB 여유, lock/staging 충돌, 2020–2025 원 세션 exact coverage,
  Python 287/287, PowerShell 20/20을 모두 통과했다.
- 현재 `NO_GO`의 유일한 이유는 2020–2021 승인 제외 계약 부재와
  2022–2025 lab 입력·승인 계약 생성 전 상태다. 이는 전수 계산을 섣불리 시작하지
  않게 하는 의도된 안전 중단이다.
- 다음 단계는 `run_mfa_year_queue_safe.ps1 -PrepareMissingReviews`로 6개 연도의
  lab 입력을 전수 검증하고 pending 연구자 검토표를 만드는 것이다. 이 단계는
  MFA·WAV 이동·자동 승인·정본 승격을 하지 않는다.

근거:

- `outputs/reports/PREFLIGHT_mfa_year_queue_mfa_r2_full6y_20260801.json`
- `outputs/reports/PREFLIGHT_mfa_adoption_mfa_r2_full6y_20260801.json`
- `outputs/reports/FINAL_PREBULK_MFA_CHECKLIST_20260801.md`

### 서울코퍼스 참고형 최종 슬라이드

- 서울코퍼스의 레이블·WAV/TextGrid pair·경계 검색·후속 통계 활용 흐름을 참고하되,
  이번 연구의 역할 분리를 중심으로 15장 편집 가능한 PPTX와 PDF를 만들었다.
- 원자료, 연구자 정책, 기계 파생값, 수동 판정을 구분하고, 6-tier TextGrid,
  연도별 gzip/Parquet 동반표, Roman/형태소 검색 좌표, MFA phone의 한계,
  KOINA/이어붙이기/wav2vec2의 선별 사용, 체크포인트 복구, 현재 `NO_GO`와
  다음 명령을 한 흐름으로 설명한다.
- 모든 슬라이드에 `[Sources]` 노트를 넣었다. PowerPoint 렌더를 15/15 육안
  확인했고, 도형 범위·텍스트 넘침·출처 블록 기계 QA도 issue 0으로 통과했다.
- PowerPoint COM 생성 과정에서 BOM 없는 UTF-8을 Windows PowerShell 5.1이
  잘못 읽는 문제와 텍스트 입력 뒤 도형 높이를 최소값으로 되돌리는 문제를 실물로
  발견했다. 생성 스크립트는 UTF-8 BOM과 최종 도형 치수 재고정으로 해결했다.

산출물:

- `outputs/presentations/MFA_research_infrastructure_final_prebulk_20260801.pptx`
- `outputs/presentations/MFA_research_infrastructure_final_prebulk_20260801.pdf`
- `outputs/reports/QA_MFA_research_infrastructure_final_prebulk_20260801.json`

### 사용자가 전수 실행까지 갈 수 있는 2단계 진입점

- 승인 작업은 MFA phone이나 실제 음운 실현을 승인하는 절차가 아니다. 입력에서
  제외할 발화를 자동 누락하지 않도록, 제외 사유·범위·증거를 정확한
  `input_contract_id`에 묶어 연구자가 확인하는 절차다.
- `prepare_full_mfa_approval_reviews.ps1`은 6개년 입력을 검증하고 pending 제외
  후보표만 만든다. MFA·WAV 이동·자동 승인·정본 승격은 하지 않으며 기존 검토
  입력을 덮어쓰지 않는다.
- 사용자가 각 후보의 제외에 동의할 때만 `decision=approved`로 바꾼다. 동의하지
  않는 후보는 승인하지 않고 원자료/분류 원인을 수정한 뒤 검토표를 재생성한다.
- `start_full_mfa_after_review.ps1 -ApprovedBy <연구자>`는 승인된 CSV만 계약화하고
  전체 테스트 포함 preflight가 정확히 `GO`일 때만 연도 큐를 시작한다.
  full clean retry, 자동 승인, 정본 자동 승격은 전달하지 않는다.

## 2026-08-01 — 구 2020 정렬 검토 중단과 조합검색 v3 생산 준비

### 범위 정정

- 2020–2025는 공통 Jamo r2 기준으로 모두 새로 정렬하므로 구 2020 정렬을
  전수 검토·승인·재사용하지 않기로 다시 명시했다.
- 중단된 `mfa_exclusions_queue_mfa_r2_full6y_20260801/2020`에는 검토 CSV가
  생성되지 않았고, 이를 재개하지 않았다.
- 현재 2020 작업은 구 TextGrid 검토가 아니라 새 정렬 전 조합검색 CSV/LAB
  인프라 생성이다. 사람 확인은 새 입력에서 실제 예외 후보가 있을 때 그
  후보에만 한정한다.

### 구현

- `morph_search.v3`에서 `form` 철자 어절과 `tagged` 분석 어절을
  `orth_eojeol_tokens`/`eojeol_tokens`로 분리했다. 수가 다르면 hard fail하거나
  zip으로 유실하지 않고 mismatch 상태를 남긴다.
- `form_roman_v2`, 형태소·음절·경계 검색표와 `symbol_readings`를 함께 생성한다.
- 숫자·기호는 occurrence별 표기, 좌우 문맥, 출처 근거 발음, 후보 목록,
  해결 상태를 분리했다. 근거가 없으면 후보를 선택값으로 승격하지 않는다.
- 연도·session-file shard checkpoint runner와 읽기 전용 상태판을 추가했다.
  성공 shard는 SHA를 재검증해 재사용하고 실패 partial은 자동 삭제하지 않는다.
- 실제 전수 경로와 run ID는 `morph_search_v3`로 통일했다.

### 실자료 회귀 중 발견·보존한 시행착오

1. 첫 시도는 2020에서 `form` 5어절과 `tagged` 4어절을 동일 좌표로 강제해
   안전 중단됐다. 실패본은
   `work/morph_search_v2_regression_60_pre_coordinate_fix_ARCHIVE_20260801`에
   남겼고, 두 좌표계 분리로 수정했다.
2. 두 번째 시도는 2024에서 형태소 literal 수와 원표기 symbol 수를 잘못
   비교하는 gate 때문에 중단됐다. 실패본은
   `work/morph_search_v2_regression_60_pre_orth_symbol_gate_ARCHIVE_20260801`에
   남겼고, 원표기 기대 symbol 수와 실제 symbol 표 행 수를 비교하도록 고쳤다.

### 검증 결과

- 2020–2025 각 10발화, 총 60발화를 두 번 독립 생성했다.
- 7표×6년 gzip 42개 SHA-256 불일치 0, 발화 60, 기호 occurrence 26,
  철자/분석 어절 수 mismatch 7발화를 보존했다.
- `SARW2500000414.1.1.2`의 `2사람이`는 원 전사 근거로 `두`를 선택하고
  `이/둘/두` 후보를 별도 보존했다.
- 전체 Python 292시험과 PowerShell 안전 검사 22파일이 통과했다.
- 이 작업에서는 MFA·TextGrid·공통발음사전을 실행하거나 변경하지 않았다.

### 2020 실제 전수 경로 첫 shard

- 실제 동결 2020 입력은 session CSV 2,232개이며 100파일씩 총 23 shard로
  계약됐다.
- `morph_search_v3_20260801`의 shard 1만 실행해 41,803발화를 처리했다.
- 압축 7표 28,540,035 bytes, SHA-256 재검사 불일치 0이었다.
- 철자 어절 141,931행, 형태소 분석 어절 140,807행, 형태소 269,827행,
  형태소 unit 402,110행, 경계 228,024행, 기호 13,560행을 보존했다.
- `paused_after_max_shards`, 1/23으로 정상 중단했고 lock은 해제됐다. 다음 실행은
  shard 1을 SHA 검증한 뒤 shard 2부터 이어간다.
- 이 실측에서도 MFA·TextGrid·구 2020 정렬은 실행하거나 읽지 않았다.

결정:
`docs/decisions/DECISION_pre_MFA_combination_search_v3_20260801.md`

근거:
`outputs/reports/EVIDENCE_morph_search_v3_regression_60_20260801.json`

실제 첫 shard 근거:
`outputs/reports/PREFLIGHT_morph_search_v3_2020_shard1_20260801.json`

## 2026-08-01 — 전수 실행 전 workflow 순서 재정돈

- 사용자가 코드보다 연구 목적에 맞는 입력·출력·작업 순서를 외부 도구에 먼저
  리뷰받기로 했다. 2020 검색 shard 2 이후 계산은 시작하지 않았다.
- MFA 전에 반드시 동결할 LAB/reference·공통사전·모델·phone inventory와,
  정렬 후 재생성 가능한 형태소/Roman/우리말샘 1:N/Parquet/KOINA 레이어를
  구분했다.
- 6개년 검색표 전부를 MFA의 무조건적 선행조건으로 두지 않고, 2020 검색 전수는
  첫 생산 연도의 원 입력 검증을 위해 먼저 완료하는 권장안을 제시했다.
- 현재 별도 runner인 `morph_search.v3`와 MFA 연도 큐 사이에서 연도 manifest를
  hard gate로 할지 동일 source/input contract만 gate로 할지를 외부 리뷰의 핵심
  질문으로 남겼다.
- 구 2020 정렬 재검토, 근거 없는 기호 읽기 자동 확정, KOINA/wav2vec2 전수,
  검증 전 자료 삭제는 실행 순서에서 명시적으로 제외했다.

제안서:
`docs/decisions/PROPOSAL_prebulk_execution_order_20260801.md`

외부 리뷰 프롬프트:
`docs/reviews/PROMPT_external_review_prebulk_execution_order_20260801.md`

## 2026-08-01 — 전체 workflow·검수 가치·archive 구조 리뷰로 확대

- 사용자는 계속 검수에 머물면서 반영 누락, 의미 없는 반복 검수, 다음 생산 단계
  지연이 생겼을 가능성을 전체적으로 점검해 달라고 요청했다.
- 현재 문서 104개, decision 53개, review 21개이며 과거와 최신 `GO/완료/대기`
  상태가 함께 노출되는 구조 자체를 위험으로 기록했다.
- 새 외부 리뷰는 문서의 완료 표현을 믿지 않고 결정→문서→config/schema→runner→
  test→실물 artifact를 대조하게 했다.
- 모든 검수를 `유지/통합/기계화/조건부/폐지`로 판정하고, 사람이 해야 하는 것은
  언어학적 선택·자료 제외·파괴적 작업 승인으로 제한하게 했다.
- 정본/현재 증거/역사자료/대체됨/실패근거/검토산출물 archive 후보표와 50–120줄의
  새 현재상태 초안을 결과물로 요구했다.
- 이번 리뷰에서는 실제 파일 이동·삭제·코드 수정·전수 계산을 금지했다. 결과 반영
  뒤 manifest와 `git mv`로 archive 및 구조 refresh를 별도 시행한다.

브리프:
`docs/reviews/BRIEF_external_review_workflow_reset_20260801.md`

새 외부 리뷰 프롬프트:
`docs/reviews/PROMPT_external_review_workflow_reset_20260801.md`

## 2026-08-01 — workflow reset 반영과 2020 생산 진입점 고정

- Claude Code 외부 리뷰 원문·결정 추적표·검수 가치표·archive 후보표를 보존하고
  저장소 코드 및 D: 실물과 다시 대조했다.
- 외부 리뷰의 방향은 수용했지만, `코드 수정 없이 GO`, Gate B 배선 완료,
  5주 경과, Python 287개, reference 4종 HDD 유일본 주장은 실제 상태와 달라
  최종 판정을 `GO AFTER SMALL WORKFLOW FIXES`로 수정했다.
- 구 4-tier 60행 잔여 검토, 12발화 검토, 5-tier 수용 검토, difference
  inventory 반복을 종료했다. mini pilot 확인은 2020 생산 표본 검토에 통합했다.
- 누적형 `PROJECT_CURRENT_STATE.md`를 archive하고 89줄 교체형 정본으로 바꿨다.
  README/CLAUDE 진입점, production RUNBOOK, decision index, archive manifest를
  새로 만들고 구 TODO/WORKFLOW/HANDOFF에는 역사·대체 상태를 표시했다.
- 슬라이드가 고정한 6-tier, pre-MFA 7표, post-MFA 4표, Jamo r2, phone 기준,
  선택적 KOINA/stitch/wav2vec2 설계는 바꾸지 않았다.
- 2020-only 검색·승인표·정렬 wrapper와 2020 Gate B 뒤 2021–2025 wrapper를
  추가해 기본 6개년 오실행을 막았다.
- `SOURCE_CONTRACT.json`을 생성해 동결 `_build_meta.json` SHA
  `1649d60a302de44a772460ba9f64d3cfb9307a56d53f1fa578bcd0494264ea79`를
  2020 morph_search와 MFA 사이의 공통 입력 근거로 고정했다. 원자료 수정은 없다.
- 생산연도 표본 검토 schema를 추가했다. 최소 5세션의 WAV/LAB/6-tier/CSV
  연결과 연구 가용성만 확인하며 실제 음운 실현은 판정하지 않는다.
- 새 생산연도 review schema를 다음 연도 QC gate에 배선했다. Gate B는 source,
  input, alignment, DB, 6-tier audit, 재수출 표본, 연구자 승인을 모두 요구한다.
- 회귀시험: Python 293/293, PowerShell 안전검사 31개 파일, source contract
  실물 검증 `passed`.

다음 계산은 커밋·푸시 뒤 `scripts/resume_2020_morph_search.ps1` 하나로 2020
shard 2–23을 재개하는 것이다.

### 17:14 KST — 2020 검색표 재개

- 커밋 `cbfd299`를 GitHub에 푸시한 뒤 2020 전용 wrapper를 백그라운드로
  시작했다.
- 시작 실측: source contract `passed`, 충돌 lock 0, 기존 progress 1/23,
  새 lock PID 25716, Python worker PID 13480, manifest `running`.
- 이 계산은 MFA를 대신하지 않는다. 완료 뒤 2020 제외 후보 승인과 2020 신규
  r2 전수 정렬이 필수 후속 단계이며, Gate B 뒤 2021–2025도 전부 정렬한다.
- 로그: `logs/morph_search_2020_20260801_171441.out.log` 및 `.err.log`.

### 17:47 KST — 2020 검색표 23/23 완료

- `YEAR_PROGRESS.status=success`, 23/23 shard, lock 정상 해제를 확인했다.
- 2020 발화 870,437행을 기준으로 7개 gzip 표를 생성했다.
  `eojeol_tokens` 3,030,081행, `orth_eojeol_tokens` 3,042,451행,
  `morph_tokens` 5,767,506행, `morph_units` 8,581,967행,
  `morph_boundaries` 4,897,069행, `symbol_readings` 290,525행이다.
- `all_shards_success=true`, `duplicate_utt_id=0`, deterministic gzip,
  `orth_symbol_coverage_equal=true`를 확인했다.
- 완료 연도 manifest와 동결 `_build_meta` SHA를 다시 대조해 source contract
  검증이 `passed`였다.
- 다음 사용자 PowerShell 단계는 `prepare_2020_mfa_approval_review.ps1`이다.
  이는 2020 LAB 입력 전수 검증과 제외 후보표만 만들며 MFA는 아직 시작하지 않는다.

### 18:59 KST 이후 — 승인표 요약 오류와 2020 음원 ID 밀림 차단

- 최초 후보표 14행 생성은 끝났지만 Windows PowerShell 5.1이 `[ordered]`
  dictionary의 `candidate_count`를 `Measure-Object -Property`로 읽지 못해 마지막
  요약만 실패했다. 명시적 정수 합산으로 고치고 안전검사 31개 파일을 통과했다.
- 후보 14행은 모두 구형 `06_textgrid_merged`의 형태소 TextGrid 누락이었다.
  확정 6-tier의 `morph_analysis_utt`는 search CSV에서 생성되므로 현행 제외
  사유가 아니다. 자동 승인 없이 검토 root 전체를 이유문과 함께 archive했다.
- 같은 입력 감사의 실제 차단 사유는 길이 잔차 불일치 15,074발화/126세션,
  WAV 누락 544발화, 세션 폴더 누락 1개였다. `SDRW2000000108`에서 JSON과
  H: 배포 PCM을 직접 대조해 발화 번호 밀림을 확인했다. D:/H: JSON SHA는 같다.
- 세션 통과율 98%만으로는 소수의 잘못 짝지어진 발화를 허용하므로, 승인 제외 후
  남은 모든 발화의 잔차·누락·깨진 header가 0이어야 gate가 통과하도록 강화했다.
- 읽기 전용 복구 계획은 영향 129세션 52,519행을 분류했다. 고신뢰 remap
  14,221, identity 35,210, 짧은 모호 일치 92, target unresolved 1,742,
  source orphan 1,254다. 아직 WAV 적용·MFA·자동 승인은 수행하지 않았다.
- 승인 제외가 감사에서만 빠지고 실제 MFA 입력 WAV+LAB에는 남는 경로도
  차단했다. `alignment_and_analysis` 승인 입력은 실제 격리 전까지 실행 gate를
  통과하지 않는다. 전체 Python 298개와 PowerShell 31개 파일 검사가 통과했다.

결정:
`docs/decisions/DECISION_2020_CSV_WAV_ID_recovery_20260801.md`

## 2026-08-02 — 2020 WAV ID 복구 최소 청취 묶음

- 길이 연속열만으로 고신뢰 remap 14,221건을 곧바로 적용하지 않고, 실제
  음성–전사 일치를 확인할 최소 사람 검토를 만들었다.
- 연속 일치 길이 `3–10 / 11–80 / 81+`에서 각각 2블록, 블록별 재매핑 구간
  시작·끝을 선택해 6세션 12건으로 제한했다.
- 각 건은 `A_PROPOSED`와 `B_CURRENT` WAV를 함께 제공한다. A는 대상 전사에
  대응한다고 제안된 음원이고, B는 현재 같은 ID의 음원이다.
- D: 원본은 읽기 전용으로 유지했고, 24개 복사본은 복사 전후 SHA-256을
  대조해 불일치 0을 확인했다. 묶음 전체는 약 1.51 MiB다.
- 최초 자동 선정은 현재 같은 ID WAV가 없는 구간 끝을 포함해 안전 중단됐다.
  비교 WAV 두 개가 모두 존재하는 블록만 선정하도록 수정하고, 중간에 생긴
  미완료 복사본만 정리한 뒤 새 묶음을 완성했다.
- 현재 사용자 작업은 1번부터 대상 전사와 A 음성의 일치만 답하는 것이다.
  PowerShell 실행, 승인 CSV 편집, MFA 시작은 아직 필요하지 않다.

검토 묶음:
`outputs/2020_wav_id_recovery_review_20260802/00_READ_ME_FIRST.md`

재현 스크립트:
`scripts/python/build_wav_recovery_review_bundle.py`

### 연구자 청취 결과

- 1–2번은 개별 응답, 3–12번은 일괄 응답으로 확인했다.
- 12/12 모두 A 제안 음원이 대상 전사와 일치했다.
- 판정은 `REVIEW_DECISIONS.json/.md`에 기록하고 Dropbox 검토 폴더에도
  SHA 동일 사본으로 동기화했다.
- 이 결과는 3개 길이대의 6블록 양끝 표본이 복구 규칙을 지지한다는 뜻이다.
  14,221건을 사람이 전수 확인한 것으로 해석하거나 기록하지 않는다.
- 다음 단계는 원본 변경 전 영향 세션 archive manifest·복구 적용 transaction·
  rollback 계약을 구현하고 dry-run으로 검증하는 것이다. 사용자가 새로 실행할
  PowerShell 명령은 아직 없다.

### 복구 transaction 구현과 실제 전수 dry-run

- 원 `D:\20_AUDIO\03_wav\individual`을 직접 재명명·덮어쓰기하지 않고
  `D:\20_AUDIO\04_wav_id_recovered_staging\individual\2020`에 MFA 전용
  파생 코퍼스를 만드는 방식으로 확정했다.
- 영향 129세션의 원음은 apply 전에
  `E:\READ_ONLY_ARCHIVE\2026_summer_research`에 세션별 ZIP과 WAV SHA-256
  manifest로 보존한다. 초기 용량 계산에서 source orphan을 빼 3.0 GiB보다 작게
  셌던 오류를 고쳐, 50,777 WAV/비압축 3.148 GiB를 archive 대상으로 확정했다.
- 영향 없는 세션은 같은 D: 볼륨의 NTFS hardlink, 영향 세션은 독립 검증 복사로
  만든다. 모호 92건과 미해결 1,742건은 파생 코퍼스에서 빼고 다음 제외 검토로
  보낸다. 원본은 계속 불변이다.
- 세션별 archive/build checkpoint, live PID lock, 불완전 partial의 stale 보존,
  복사·ZIP 재읽기 SHA 검증, 최종 exact count 계약을 구현했다. 중단 후 재실행은
  검증된 세션을 재사용하며 연도 전체를 처음부터 자동 재처리하지 않는다.
- 무인 실행 중 Windows system sleep을 억제하고 apply 종료 시 정상 상태로
  복원한다. 화면 끄기는 막지 않는다.
- 첫 실자료 dry-run은 세션별 파일 조회가 느려 120초에 250/2,232세션만
  진행됐다. 세션 단위 `scandir` inventory로 바꾼 뒤 60–63초에 전수 완료했다.
- 최종 dry-run: 검색 870,437건, 출력 예정 868,603건, 제외 검토 1,834건,
  파생 코퍼스 논리 53.96 GiB, archive 3.148 GiB, 사용자 승인 12/12,
  `status=dry_run_passed`.
- 2020 LAB 준비·MFA·정렬 감사·생산 표본은 passed 복구 계약의 WAV root만
  사용하도록 공통 resolver에 연결했다. 계약 누락/변조 시 원 `03_wav`로
  fallback하지 않는다. 2021–2025 경로는 기존 원자료를 유지한다.
- 합성 apply 시험은 원본 SHA 불변, 영향 없는 hardlink, remap 독립 복사,
  archive 전수 포함, 모호·미해결 누락, 재실행 재사용을 확인했다. 전체 Python
  304개와 PowerShell 안전검사 34개 파일이 통과했다.
- 실제 D:/E: apply와 MFA는 아직 시작하지 않았다. 다음 사용자 단계는 코드
  커밋·푸시 뒤 RUNBOOK의 `run_2020_wav_id_recovery.ps1 -Apply` 한 줄이다.

### 첫 apply 안전 중단 — 원음 폴더 누락 1세션 계약 보완

- 첫 apply는 E: archive 10/129세션을 검증한 뒤
  `D:\20_AUDIO\03_wav\individual\2020\SDRW2000000176` 폴더가 없어 중단됐다.
  원 D: 삭제·변경은 없고 lock과 절전 guard는 정상 해제됐다.
- 해당 세션의 search 513행은 모두 이미 `target_unresolved`라 파생 코퍼스 포함
  대상은 0건이다. dry-run은 이 513행을 제외했지만 archive 단계가 물리 폴더가
  없는 세션에도 ZIP을 요구한 것이 직접 원인이었다.
- E:에 완료된 구 계약 ZIP 10개(약 176 MiB)와 manifest 10개는 실패 증거로
  보존했다. 새 builder SHA/contract ID에 무근거 재사용하거나 자동 삭제하지 않는다.
- 수정본은 원음이 존재하는 128세션은 ZIP+SHA로, 누락 1세션은
  `verified_absent`/0파일/ZIP 없음 manifest로 기록한다. 누락 세션에 포함 대상이
  있으면 여전히 즉시 중단한다.
- 진행 JSONL의 모든 사건에 contract ID를 넣고 상태판이 현재 dry-run 계약의
  사건만 표시하게 해 구 실패 진행률 10/129가 새 실행 상태처럼 보이지 않게 했다.
- 합성 누락 세션 apply·재개, 전체 Python 304개, PowerShell 34개 검사를 통과했고
  실자료 재-dry-run은 128 ZIP 세션+누락 manifest 1개, corpus 868,603,
  제외 1,834, archive 3.148 GiB로 통과했다.

### 수정 계약 apply 완료

- 2026-08-02 09:58:09–10:24:46 KST에 수정 계약 apply가 완료됐다.
- contract ID `eb64f80d9106d14c7b2a267811cdf2dc2fe29e890cc335a7029a8cca24a7375f`,
  final contract와 APPLY 보고서 ID가 일치하고 status는 모두 `passed`다.
- D: 파생 코퍼스 계약 WAV 868,603건을 별도 directory enumeration으로 다시
  세어 868,603건과 정확히 일치했다. 세션 디렉터리는 2,232개다.
- E:에는 128 ZIP, 129 manifest가 있으며 차이 1개는
  `SDRW2000000176`의 `verified_absent` 증거다. ZIP 합계는 약 2.18 GiB이며
  원음 비압축 기준은 3.148 GiB다.
- 최종 lock은 해제됐고 source tree untouched=true다. 2020 corpus resolver도
  새 root와 같은 contract ID를 반환했다.
- 복구 단계는 완료됐다. 다음 단계는 1,834건의 승인 제외 후보표 생성·연구자
  확인이며, MFA 자체는 아직 시작하지 않았다.

### 2020 제외 후보의 미해결 기호 회계 보완 — 전수 계산 반복 없음

- 첫 후보표 1,834건은 음원 복구 불가·모호 발화만 포함했으나, 완료된 LAB
  보고서에는 WAV가 있으면서 정렬 문자열이 완전히 빈 미해결 기호 발화 53건이
  별도로 있었다. 이를 승인표에 넣지 않으면 MFA 입력과 승인 제외 양쪽에서
  암묵적으로 빠지는 결함을 승인 전에 발견했다.
- 기존 전수 LAB/WAV 검사를 다시 실행하지 않았다. audit·복구계획·LAB 보고서·
  미해결 기호 인벤토리의 계약 ID·합계·SHA-256을 읽기 전용으로 검증해 결합했다.
- 최종 후보는 `audio_pairing_unresolved` 1,834건과
  `empty_reference_unresolved_symbol` 53건, 합계 1,887건이다.
- 미해결 기호 6,211건 중 부분 한글 LAB이 있는 6,158건은 제외하지 않았다.
  `pron_reference_status=unresolved_symbol`이 post-MFA
  `utterance_alignment.csv.gz`로 그대로 전달되는 회귀시험을 추가했다.
- 첫 1,834건 검토 root 5개 파일/896,389 bytes는 삭제하지 않고
  `outputs/reviews/archive/..._pre_symbol_accounting_20260802`로 이동했다.
- Gate B 전 2020 전용 큐의 `...mfa_r2_prod_2020_20260801/2020`만 활성본으로
  고정했다. 이는 `start_2020_mfa_after_review.ps1`의 기본 큐 ID와 일치한다.
  새 finalize 스크립트는 출력이 있으면 덮어쓰지 않으므로 후보표 반복 생성을
  막는다. 자동 승인과 MFA는 수행하지 않았다.
- 결정 근거:
  `docs/decisions/DECISION_2020_MFA_exclusion_symbol_accounting_20260802.md`

### 2020 제외 두 범주 연구자 명시 승인

- 2026-08-02 13:27 KST에 사용자 `ari30`이 “두 범주 모두 승인”이라고 답했다.
- 1,834건 `audio_pairing_unresolved`와 53건
  `empty_reference_unresolved_symbol`, 합계 1,887건을 승인했다.
- 원 `03_RESEARCHER_REVIEW.csv`는 1,887행 모두 `pending`인 생성 증거로
  바꾸지 않았다. 별도 `04_RESEARCHER_APPROVED.csv`의 동일 1,887 ID만
  `approved`로 기록했다.
- 승인 문구·시각·범주별 수·pending/approved SHA는
  `04_RESEARCHER_APPROVAL.json`에, 실제 실행 제외는 입력 계약 ID에 결속된
  `approved_exclusions.json`에 기록했다.
- 독립 계약 validate는 approved 1,887, ID 차이 0, pending SHA 보존을 확인했다.
  승인 기록 생성은 MFA·WAV·LAB·정본을 변경하지 않았다.
- 승인 뒤 `PreflightOnly`를 별도 필수 단계로 안내한 것은 workflow reset의
  단일 진입점 원칙과 달라 즉시 수정했다. `start_2020_mfa_after_review.ps1`가
  내부에서 같은 preflight를 수행하고 `GO`일 때만 시작하므로 정상 사용자 단계는
  한 줄이며, `PreflightOnly`는 문제 진단용 선택 옵션으로만 남긴다.
## 2026-08-02 — 생산 전 문서·D: legacy 정리

- 사용자는 D:에 원자료·CSV·현재 공통사전·앞으로 필요한 생산 자산만 남기고
  과거 산출물을 다른 드라이브에 과감히 archive하도록 승인했다.
- D: 309.08GiB, E: 1.84TiB, H: 93.04GiB 여유를 확인해 E:를 archive 대상으로
  선택하고 H:는 제외했다. 활성 MFA/Python/7z 작업과 lock은 없었다.
- 7월 말 E: 압축 archive 5항목과 D: prune 보고서를 재확인했다. 파일
  2,238,237개, 55.883GiB가 이미 검증·정리돼 같은 작업을 반복하지 않았다.
- 현재 `common_pron_mfa_r2_20260728`, 원 WAV/CSV/search master, 2020 복구
  코퍼스·승인 계약은 정리 allowlist에서 제외했다.
- 구 공통사전 r1/A-B/pilot과 `mfa_eojeol` pilot을 항목별 E: archive로 옮기는
  재개형 스크립트와 상태판을 추가했다. archive 검증은 삭제 전 최초 1회로
  제한하고 생산 MFA/CSV gate와 구분했다.
- 첫 실행은 Windows PowerShell 5.1이 BOM 없는 UTF-8을 잘못 읽어 archive 생성
  전에 파싱 실패했다. D:/E: 변경 0건을 확인하고 UTF-8 BOM·구문검사를 추가했다.
- 공통발음 full6y pilot에는 MFA가 만든 symlink가 있어 7z의 비압축 바이트가
  원본 Length 합보다 커졌다. 파일 수·CRC와 reparse 근거를 기록하는 방식으로
  수정했다. `mfa_eojeol\pilots`에는 끊어진 임시 `.ark` symlink 12개가 있어
  링크 자체를 보존하는 `-snl`로 수정했다. 실패 시 원본은 남고 성공 항목만
  정리됐다.
- 문서 정본 혼동을 줄이기 위해 `docs`의 구 진입문서 7개와 7월 작업일지,
  종료된 decision/RUNBOOK/MONITOR/PILOT 33개를 `docs/archive`로 이동했다.
  현행 decision 24개와 정본 5개만 활성 색인에 남겼다.
- 상세 이동표: `docs/archive/ARCHIVE_MANIFEST_20260802.md`.
- 수백만 개 TextGrid를 사용자 PowerShell에서 장시간 archive할 때 화면 꺼짐은
  허용하되 시스템 절전으로 작업이 중단되지 않도록 Windows execution-state
  guard를 추가했다. 성공·실패 어느 경우에도 `finally`에서 정상 전원 정책으로
  복원한다.

### 구 TextGrid 8항목 archive·D: 정리 완료

- 2026-08-02 14:32–18:29 KST에 `06_textgrid_eojeol` 2020–2021과
  `06_textgrid_merged` 2020–2025, 총 8항목을 순차 처리했다.
- 항목마다 파일 수·비압축 바이트 일치, 7-Zip CRC 전수검사, 최종 archive
  SHA-256 기록을 통과한 뒤에만 해당 D: 원본을 정리했다.
- 최종 manifest는 `selection_completed`, 8항목은 모두 `pruned`다.
- 합계 7,341,358파일/33.297GiB를 E: 2.226GiB의 8개 archive로 보존했다.
- 완료 후 독립 감사에서 D: 원본 8경로 부재, E: archive 8개 존재,
  manifest SHA-256 8/8 일치, 미완성 `.partial` 0개를 확인했다.
- D: 여유는 작업 전 317.184GiB에서 366.300GiB로 늘었다. 이 증가량에는
  같은 날 먼저 완료한 구 공통사전·파일럿 7항목 정리도 포함된다.
- archive I/O는 종료됐으며, 다음 생산 단계는 별도 후보표 재생성 없이
  `start_2020_mfa_after_review.ps1 -ApprovedBy ari30` 단일 진입점이다.

### 2020 시작 preflight 자기유발 tracked-diff 수정

- archive 완료 뒤 2020 단일 wrapper의 `-PreflightOnly`를 실제 Windows
  PowerShell 5.1에서 실행했다. 계약·승인 1,887건·공통 Jamo r2·phone 109개·
  D: 366.3GiB·전체 312시험은 모두 통과했지만 최종 gate만
  `tracked_code_committed`에서 `NO_GO`였다. MFA는 시작되지 않았다.
- 원인은 wrapper가 먼저 `verify_production_source_contract.ps1`를 기본 출력으로
  호출해 Git 추적 보고서의 `checked_at`을 갱신한 뒤, 이어지는 preflight가
  그 자기유발 diff를 미커밋 코드로 판정한 것이었다. 데이터·계약 실패가 아니다.
- 2020 시작 wrapper가 source contract 검증 결과를 비추적 runtime preflight
  보고서로 명시 출력하도록 수정했다. 코드 청결 gate 자체를 약화하거나
  `outputs/reports` 전체를 예외 처리하지 않았다.
- 회귀 안전검사에 `-Output $sourceContractReport`와 runtime 보고서 경로 토큰을
  고정해 같은 자기차단이 재발하지 않게 했다.
- 수정 후 실제 최종 preflight는 `GO`, 전체 312시험과 PowerShell 5.1 검사가
  통과했다. 이어 장시간 무인 MFA 큐에 process-scoped Windows sleep guard가
  빠진 것을 확인해 추가했다. 큐 시작부터 종료·실패까지 시스템 절전을 막고,
  `finally`에서 정상 전원 정책으로 복원한다. 화면 꺼짐은 허용한다.

### 2020 공통 Jamo r2 전수 MFA 계산 완료·post-MFA gate 보류

- 2026-08-02 18:50–23:05 KST에 `--clean` 2020년 전수 정렬을 수행했고 MFA는
  exit 0으로 계산을 마쳤다. 구 정렬 결과를 재사용한 실행이 아니다.
- 입력 WAV 868,603개 중 pre-MFA에서 빈 기준 발음/미해결 기호로 승인 제외된
  53개를 제외한 active DB 발화는 868,550개다. 이 중 word와 phone interval이
  모두 생성된 것은 868,187개이고, 기본 beam 10과 retry beam 40에서도
  정렬되지 않은 active 발화는 363개다. job별 최종 오류는
  `33 + 54 + 39 + 237 = 363`으로 일치한다.
- 보존 DB `D:\mfa_tmp\2020\2020.db`는 6,348,247,040 bytes이며 SQLite
  checkpoint 검사 뒤 `D:\mfa_eojeol\done\2020.direct_db_ready` marker를
  남겼다. 따라서 후속 판단 뒤에는 전수 MFA를 다시 하지 않고 direct 6-tier
  export부터 재개한다.
- 기존 exporter는 pre-MFA 승인 제외 1,887건을 active LAB 밖의 stale 승인으로
  잘못 해석했다. 안전 gate를 완화하지 않고 원천/active/post-MFA 방정식을
  분리했다. 실 DB 재검증에서 `870,437 = 868,550 + 1,887`, DB 밖 active 0,
  원천 밖 승인 0, 미승인 quarantine 0을 확인했다.
- 남은 363건은 82개 세션에 분포하지만 `SDRW2000000257`에 200/464건이
  집중됐다. 단순 실패로 자동 제외하지 않고, 실패 12개와 같은 세션 정렬 성공
  대조 4개를 묶은 WAV/LAB 파일럿을
  `outputs/reviews/mfa_post_alignment_2020_mfa_r2_prod_2020_20260802`에 만들었다.
- 연구자 판단 전에는 승인 계약 변경, 정본 승격, 2021 진입을 하지 않는다.
  상세 방법론 결정은
  `docs/decisions/DECISION_2020_post_mfa_alignment_missing_gate_20260802.md`에
  기록했다.
- 사용자가 원격에서도 바로 들을 수 있도록 같은 검토 묶음 37파일/1,480,094
  bytes를 `C:\Users\ari30\Dropbox\MFA_2020_POST_ALIGNMENT_REVIEW_20260803`에
  복사했다. 원본과 복사본의 파일별 SHA-256 37/37 일치를 확인한 뒤 `.partial`
  폴더를 최종 이름으로 승격했으며, MFA DB와 로컬 검토 원본은 변경하지 않았다.
- 7월 구방식 실패 3,644건과 이번 실패 363건을 ID로 대사했다. 구방식 실패
  3,332건이 이번에는 회수됐고, 현 363건 중 312건은 지속 실패, 51건은 새
  실패다. 최다 세션은 구방식 205건/이번 200건이며 193 ID가 겹친다. 해당
  세션은 WAV ID 복구 계획 대상이 아니므로 새 remap 회귀 가능성은 낮지만,
  원자료 대응 문제를 배제하기 위한 대표 청취는 유지한다.
- 큐의 실패 분기가 실제 `direct_db_ready` marker를 읽지 않아 상태판에는
  `db_retained=False`로 보이는 관찰성 오류를 발견했다. 향후 큐는 marker의
  `computation_complete`, DB 경로·존재를 검증해 계약 ID와 보존 DB를 상태에
  기록하고 `post_mfa_export_failed_db_preserved`로 구분한다. 읽기 전용
  상태판도 과거 큐 JSON을 marker와 대사해 실제 DB 보존 여부를 표시하도록
  고쳤다. 현 2020 상태판에서 direct checkpoint와 DB 보존이 모두 True,
  D: 여유 343.54GiB, live lock 없음으로 확인됐다.

### 2020 post-MFA 표본 검토 단순화 — 전수 재정렬 없음

- 최초 전달본은 WAV/LAB와 검토 CSV가 분리돼 있고 파일명이 번호순이 아니어서,
  연구자가 발화마다 원자료를 찾아야 했다. 이는 16개 표본의 연결 QC라는 목적에
  비해 절차가 과도하다는 사용자 지적을 반영했다.
- 2020 전수 MFA나 고 beam 재정렬을 다시 수행하지 않았다. 보존 DB와 동결
  search-master를 읽기 전용으로 열어 기존 16개만 한 평면 폴더에 재구성했다.
- 각 번호에 WAV, LAB, search-master의 정확한 1행 CSV, 주요 열을 풀어 쓴
  CONTEXT를 붙였다. DB에 word+phone interval이 있는 13–16번 정렬 성공
  대조군에는 승인된 6-tier TextGrid를 직접 생성했다. 1–12번은 현 DB의 정렬
  실패 표본이므로 없는 TextGrid를 가장하지 않고 `NO_CURRENT_TEXTGRID` 안내를
  붙였다.
- 연구자가 이미 청취한 1번은 `decision=match`로 사전 기록했고 나머지 15행만
  pending으로 남겼다. 이 검토는 실제 음운 실현 판정이 아니라 WAV·전사·CSV·
  정렬 산출물 연결 QC다.
- 로컬 묶음은
  `outputs/reviews/MFA_2020_REVIEW_SIMPLE_20260803`, 사용자 전달본은
  `C:\Users\ari30\Dropbox\MFA_2020_REVIEW_SIMPLE_20260803`이다. 총 83파일,
  검토 16행, TextGrid 4개, 정렬 부재 안내 12개이며 파일별 복사 SHA-256이
  모두 일치했다.
- 생성 전후 `D:\mfa_tmp\2020\2020.db`는 6,348,247,040 bytes와 mtime이
  동일했다. 승인 계약·정본·2021 gate는 변경하지 않았다.
- 사용자 검토 절차에 포함하지 않기로 한 고 beam 진단은 공통사전 정규화만 오래
  수행하고 TextGrid를 만들지 못해 중단했다. 그 미완성 작업 폴더 317,992,561
  bytes와 폐기한 복잡한 검토본 1,266,038 bytes는 정본·원자료가 아님을 확인한
  뒤 프로젝트에서 삭제했다. 복구할 실험 결과는 없으며 단순 검토본, 최초
  16표본 묶음, 보존 DB는 유지했다.

### TextGrid 바깥 경계 전수 감사·검토본 V2·청취 불가 3건 기록

- 연구자는 16표본을 모두 검토해 13건의 WAV·LAB·CSV 연결이 맞다고 확인했고,
  `SDRW2000000257.1.1.231`, `.39`, `.97` 3건은 소리가 들리지 않는다고 기록했다.
  세 파일의 RMS는 각각 -79.307, -70.993, -79.191 dBFS였다. 디지털 0이라고
  과장하지 않고 연구자 청취 기반 `audio_unusable`,
  `alignment_and_analysis`, `approved`로 정확한 3행 부록을 만들었다.
- 검토 중 파일에 따라 TextGrid 좌우 빈 경계가 보이거나 보이지 않는다는 지적을
  받았다. 단순 검토 묶음이 기존 결정에 있던 검토용 좌우 0.05초 패딩을 실제로
  적용하지 않은 구현 누락이었다. 생산 MFA나 원자료 문제가 아니며 전수
  재정렬도 하지 않았다.
- V2는 16개 WAV 모두에 실제 0.05초 zero-amplitude PCM을 좌우로 붙였다.
  정렬 대조 4개의 6-tier는 모든 interval을 같이 0.05초 이동하고 모든 tier에
  0.05초와 `xmax-0.05` 경계를 넣었다. Python PNG와 독립 JSON 감사에서
  4/4 TextGrid × 6/6 tier가 통과했다. 원시간 복원식은 manifest와 검토표에
  `source_time=review_time-0.05`로 기록했다.
- 검토본만 고친 뒤 전수 문제를 놓치지 않기 위해 `D:\mfa_tmp\2020\2020.db`의
  정렬 성공 868,187발화를 읽기 전용으로 전수 집계했다. word와 phone의 유표
  바깥 시작·끝은 868,187/868,187, 100% 일치했다. 자연 무음 분포는 좌우 모두
  650,259, 왼쪽만 75,165, 오른쪽만 128,309, 없음 14,454였다. 파일 간 빈
  구간 차이는 원음 차이이며 한 파일 안의 6-tier 바깥 발화 경계는 exporter
  계약상 일치한다.
- 생산 6-tier 전수 실물은 아직 export 전이다. production은 원음 source time을
  유지하고 검토본만 인공 패딩한다. 형태소 tier를 word 경계에 억지로 나누지
  않으며 검색은 동반 CSV/Parquet를 기준으로 한다.
- 로컬 V2는 `outputs/reviews/MFA_2020_REVIEW_SIMPLE_V2_20260803`, 그림 감사는
  `outputs/reports/MFA_2020_TIER_BOUNDARY_AUDIT_FIXED_20260803`, 전수 보고서는
  `outputs/reports/AUDIT_2020_FULL_DB_TIER_EDGES_20260803.json`이다. 같은 V2와
  그림 폴더를 Dropbox에 각각 84파일과 5파일로 복사해 파일별 SHA-256 일치를
  확인했다. 구 Dropbox 검토본과 연구자 Excel 증거는 덮어쓰지 않았다.
- 이 시점에는 나머지 360개 미정렬 발화를 자동 승인하지 않고 별도 연구자 결정을
  기다렸다. 현 DB와 checkpoint는 변경하지 않았다.

### 2020 post-MFA 363건 확정·보존 DB export 인수인계 정리

- 연구자는 연결 표본 검토 뒤 보존 DB를 유지하고 인프라 구축을 계속하도록
  지시했다. 승인 프로그램은 원 post-MFA 후보 363 ID를
  `D:\mfa_tmp\2020\2020.db`에서 다시 읽은 미정렬 ID와 전수 대조했고 차이 0을
  확인했다.
- 청취 불가 3건을 `audio_unusable`, 나머지 360건을
  `mfa_alignment_missing`으로 기록했다. 기존 pre-MFA 1,887건과 결합한 최종
  승인 계약은 2,250건이다. 자동 승인으로 가장하지 않고 연구자명·시각·승인
  문구·원 후보/검토본/DB fingerprint를 manifest에 고정했다.
- 결합 계약은
  `outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_export_20260803/2020`
  에 새로 만들었으며 기존 1,887건 계약과 pending 363표를 덮어쓰지 않았다.
  `full_year_mfa_rerun_required=false`, `resume_from_retained_db=true`다.
- 현재 진입점을 `resume_2020_export_after_post_mfa_review.ps1` 하나로 줄였다.
  `direct_db_ready`의 DB·입력 계약을 먼저 확인하고, 같은 checkpoint이면 신규 MFA
  계산을 건너뛰어 6-tier·동반표 export와 후속 기계 QC부터 재개한다.
- 연구 검색용 생산 TextGrid 계약을 다시 명시했다. 한글 발화,
  `utterance_orth_r`, `morph_analysis_utt` 레이블은 같은 유표 word span에 놓이며
  세 tier 경계가 같다. 모든 tier는 빈 interval을 포함해 0–xmax를 연속적으로
  덮는다. 형태소 문자열을 음향적 형태소 경계로 분할하지 않는다.
- 로컬 구 검토본
  `outputs/reviews/MFA_2020_REVIEW_SIMPLE_20260803` 83파일/1,328,922 bytes는
  `outputs/reviews/archive/MFA_2020_REVIEW_SIMPLE_V1_20260803`으로 옮겼다.
  수정 전 그림 감사 5파일/211,280 bytes는
  `outputs/reports/archive/MFA_2020_TIER_BOUNDARY_AUDIT_PRE_FIX_20260803`으로
  옮겼다. V2와 수정 후 감사는 활성 근거로 유지했다. Dropbox는 수정하지 않았고
  연구자가 root의 임시 검토 폴더를 직접 삭제하기로 했다.
- 코드·시험·정본 문서를 commit `362fcc0`으로 GitHub에 푸시한 뒤, Windows
  PowerShell 5.1에서 현재 wrapper의 `-PreflightOnly`를 실행했다. 공통사전,
  acoustic/G2P, 109-phone, D: 343.5GB, 입력·승인 계약, 보존 checkpoint, Python
  320시험이 모두 통과해 최종 상태는 `GO`였다. 보고서는
  `outputs/reports/PREFLIGHT_mfa_year_queue_mfa_r2_prod_2020_export_20260803_after_review.json`이며
  이 검사에서는 MFA·export를 시작하지 않았다.

### 2020 첫 export 재개 차단과 post-MFA active 제외 gate 교정

- 12:37 KST 실제 재개는 LAB 계약 확인과 WAV 길이 전수 검사까지 정상 통과했지만,
  기존 `approved_alignment_inputs_inactive` gate가 결합 계약의 post-MFA 363건도
  “승인했으므로 입력에서 없어야 하는 발화”로 해석해 12:52에 안전 중단했다.
  상태는 `post_mfa_export_failed_db_preserved`였고 전수 MFA 재계산·6-tier 생성은
  없었다.
- 실패 보고서 자체에서 870,437 source, 2,250 승인, 868,187 export 대상,
  WAV 길이 868,187/868,187 일치, residual 오류 0을 확인했다. 실패 원인은 자료가
  아니라 pre-MFA와 post-MFA 제외 단계의 의미를 합치지 못한 gate였다.
- 일반 신규 실행에서는 active 승인 제외를 계속 차단한다. 오직 현재
  `direct_db_ready`의 연도·입력 계약·정렬 계약·보존 DB를 확인하고, DB의 실제
  word/phone 미정렬 ID와 계약의 `audio_unusable`·`mfa_alignment_missing` ID가
  exact-match할 때만 해당 active pair를 허용하도록 수정했다.
- 실자료 정책 진단에서 승인 active 363, 관측 active 363, 허용 363, 미허용 0,
  DB exact-match, execution gate 모두 통과했다. Python 321시험과 PowerShell
  안전/Windows 5.1 호환성 검사도 통과했다. 다음 실행은 같은 보존 DB export
  wrapper의 재개이며 full clean은 금지한다.

### 13:07–14:14 KST — 2020 보존 DB export 재개·중간 점검

- 교정된 gate로 같은 큐 `mfa_r2_prod_2020_export_20260803`을 재개했다. 13:23에
  `direct_db_ready` 체크포인트와 `D:\mfa_tmp\2020\2020.db`를 재검증한 뒤 전수
  MFA 재계산 없이 13:30부터 DB→6-tier·동반표 직접 export에 진입했다.
- 13:41:51에는 TextGrid 147,327/868,187(16.970%), 14:14:19에는
  664,665/868,187(76.558%)를 부분 staging에서 직접 계수했다. 두 계측 사이 평균은
  약 265.6개/초이며, 이는 정렬 계산과 TextGrid 직렬화를 분리하고 기존 DB를
  재사용한 효과이다.
- 14:13 기준 queue lock PID 15204와 상위 실행기·export PID 21656이 모두 살아
  있고, D: 여유 공간은 337.74 GiB이다. parent 로그의 마지막 기록이 export 시작
  시각인 것은 자식 exporter가 실행 중이기 때문이며, Traceback 또는 실제 오류는
  관측되지 않았다. `duration failed sessions=`는 값이 빈 정상 통과 문장이라 오류
  신호에서 제외한다.
- 후속 코드를 미리 확인한 결과 독립 연도 감사는 active LAB에서 결합 승인
  `alignment_and_analysis` ID를 빼 868,187개를 기대하고, companion `excluded`
  표는 승인 2,250건 전체와 exact-match해야 한다. DB 표본 재생성 QC도 같은 제외
  ID를 표본에서 제거하므로 현재 결합 계약과 일치한다.
- 14:45:24 계측에서 부분 staging의 6-tier TextGrid가 목표치
  868,187/868,187(100%)에 도달했다. 그러나 exporter PID 21656, queue lock과
  상위 실행기가 계속 살아 있고 최종 manifest·export report가 아직 없으므로 전체
  export 완료로 판정하지 않았다. 14:28부터 네 gzip 동반표의 atomic partial이
  생성되어 현재는 단일 프로세스의 동반표 직렬화 단계이다. D: 여유 공간은
  335.45 GiB이고 실제 오류 문자열은 없다.
- 14:49:55 direct-DB export가 성공 종료되어 부분 폴더가
  `D:\20_AUDIO\08_textgrid_research_v2_staging\2020`으로 원자적 승격됐다.
  export report는 `ready_with_approved_exclusions`, `created=868187`,
  `approved_excluded=363`, `spn_intervals=0`이다. 동반표 manifest도 `success`이며
  utterance 868,187, word 4,973,795, phone 19,101,192, excluded 2,250행을 기록한다.
  큐는 14:49:56 자동으로 `independent_machine_qc`로 전환됐고, PID 14544가 최종
  staging의 TextGrid 전수 구조·phone inventory·동반표 fingerprint/ID 계약을
  4 workers로 독립 감사하기 시작했다. 이 시점은 export 완료이지 Gate B 완료는
  아니다.
- 독립 감사는 1,694.055초 뒤 `success`로 끝났다. 누락·초과·중복·invalid
  TextGrid, `spn`, phone inventory 이탈, 동반표 schema/fingerprint/ID/순서/중복,
  manifest count 불일치 등 하드 실패 항목은 모두 0이다. active LAB 868,550개에서
  승인 정렬 제외 2,250건 중 active 363건을 빼 기대한 TextGrid 868,187개와 실제
  868,187개가 exact-match했다. 동반표의 utterance 868,187, word 4,973,795,
  phone 19,101,192, excluded 2,250행도 독립 재계수와 일치했다.
- DB에서 독립 재생성한 24개 표본은 최종 TextGrid와 semantic 24/24 및 byte
  24/24 exact-match했다. 큐는 15:20에
  `machine_qc_complete_human_review_pending`, 2020은
  `machine_qc_passed_human_review_pending`으로 끝났고 lock과 QC 프로세스는
  정상 해제됐다. D: 여유 공간은 334.33 GiB이다.
- Gate B용 공식 연구자 검토표 24행(24세션·24화자)을 생성했다. 파일 찾기를
  반복하지 않도록 같은 검토 폴더에 번호순 WAV·LAB·TextGrid 72개와 해당
  search-master 원행을 합친 `REVIEW_CONTEXT.csv`, `README_REVIEW.md`를 추가했다.
  payload는 1,650,228 bytes이고 누락 0, 각 복사본 SHA-256 일치, Gate B 입력인
  `03_RESEARCHER_REVIEW.csv` SHA-256도 manifest와 일치해 패키징 전후 불변이다.
  자동 승인은 하지 않았다.
- 사용자 요청으로 검토 폴더를 프로젝트 공식 원본은 보존한 채 Dropbox root의
  `mfa_production_2020_mfa_r2_prod_2020_export_20260803`에 복사했다. 최초 임시
  폴더→최종 폴더 rename 중 Dropbox 동기화가 LAB 한 파일을 잠가 75/76개만
  이동했으므로 성공으로 간주하지 않고 누락 inventory를 다시 계산했다. 남은
  `02_SDRW2000000272.1.1.358.lab`을 원본에서 보완한 뒤 76개, 1,727,574 bytes,
  상대경로·크기·SHA-256 불일치 0을 확인했다. 우리가 만든 빈 `.partial`은 제거했고
  프로젝트 Gate B 입력 원본은 그대로 남겼다. Dropbox에서 편집한 뒤에는 identity
  열을 고정한 채 `decision`·`notes`만 공식 검토표로 반영해야 한다.

### 2020 생산 표본 24개 연구자 승인·파일 가장자리 경계 판정·Gate B 통과

- 연구자는 공식 생산 표본 24개를 모두 확인해 WAV·LAB·TextGrid가 같은 발화이고,
  정렬은 대체로 맞으며, 6개 tier가 정상이고 검색 정보가 이해된다고 승인했다.
  이 검토는 검색·정렬 인프라 QC이며 실제 음운 실현 판정은 수행하지 않았다.
- 공식 검토표와 Dropbox 검토표에서 identity·맥락 열은 그대로 두고 24행의
  `decision`만 `pending`에서 `approved`로 반영했다. 두 최종 CSV의 SHA-256은
  `1d8b0d2e15157348f5e6a07cd4adbea435eaede120050352d63036d306c1ae5c`로
  같고 자동 승인으로 기록하지 않았다.
- 승인 기록은
  `outputs/reviews/mfa_production_2020_mfa_r2_prod_2020_export_20260803/04_RESEARCHER_APPROVAL.json`이다.
  상태는 `approved`, 승인 시각은 `2026-08-03T15:47:05+09:00`, 24행·24세션·
  24화자이며 `allow_next_year_mfa=true`, `realization_judgment_performed=false`다.
- 육안상 경계가 없어 보인 `SDRW2000001747.1.1.224`,
  `SDRW2000001814.1.1.315`, `SDRW2000002000.1.1.37`,
  `SDRW2000001838.1.1.265`의 실제 TextGrid를 확인했다. 모든 6개 tier는 빈
  interval을 포함해 0–xmax를 연속적으로 덮고, 세 검색 tier의 유표 span은
  `words` 유표 span과 정확히 같았다. 발화 구간이 0초나 xmax와 겹칠 때 Praat의
  파일 테두리가 곧 경계이므로 별도 내부선이 보이지 않는 현상이다. 검색 누락이나
  시간정보 손실이 아니며 산출물 수정은 하지 않았다.
- `approve_2020_production_sample_review.ps1` 뒤
  `preflight_2020_gate_b.ps1`을 실행했다. `GATE_B_2020_core.json`의 16개 core
  check가 모두 통과했고 `failed_checks=[]`였다. 최종
  `GATE_B_2020_TO_2021.json`은 `status=passed`,
  `allow_remaining_years=true`다. 이 시점에는 2021을 시작하지 않았다.
