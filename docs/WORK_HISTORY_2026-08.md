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
