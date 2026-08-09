# 2026년 8월 작업 기록

## 2026-08-07 — r2 발음 입력 배선 공백 전수 감사·신규 실행 차단

### 반복 원인

- 기존 `predict_pron.py`와 검색/참조 CSV에는 표면 음운규칙 예상형이 있었지만,
  `build_common_pron_mfa_lexicon.py`는 이를 소비하지 않았다.
- r2 MFA 사전은 기본 Korean MFA 사전 발음을 무조건 보존하고 OOV에만 Jamo G2P
  1-best를 썼다. 따라서 검색표에서 고친 발음이 `phones_mfa` 입력에는 반영되지
  않는 이중 원천 구조였다.
- 기존 adoption 검사는 SHA·OOV·`spn`·acoustic phone inventory만 확인했고
  규칙 예상형·사전 근거·최종 MFA phone의 언어학적 일치 여부는 검사하지 않았다.
- 2020 Gate B와 연도별 표본 Gate의 주목적도 파일 연결·경계·tier·검색 사용성이라
  모든 phone label의 발음 입력 타당성을 필수 항목으로 두지 않았다.

### 전수 감사

- 2020–2025 관측 표면형 881,237개, 총 27,847,068회 출현을 r2 phone과 기존
  표면 규칙 예상형으로 전수 비교했다.
- 규칙 적용 대상이면서 불일치한 것은 312,756형·4,718,489회다. 이는 자동 오류
  확정 수가 아니라 형태·문맥 검토가 필요한 screening 후보 수다.
- 그중 규칙 예상형과 우리말샘 등재 발음 근거가 함께 일치하고 r2만 다른 보수적
  집합은 5,556형·411,320회다.
- 불일치 비율은 모든 연도에서 약 16.4–17.6%로 나타나 2022 특정 파일 문제가
  아니라 공통 r2 사전 생성 정책의 문제임을 확인했다.
- 감사 정본은
  `D:\mfa_common_pron\audits\common_pron_r2_rule_audit_20260807`이며 Git에는
  작은 요약 `outputs/reports/AUDIT_common_pron_r2_rule_consistency_20260807.json`을
  남겼다.

### 재발 차단과 재사용 원칙

- `config/mfa_pronunciation_release_gate.json`을 fail-closed로 만들고 r2 release를
  명시 차단했다. `validate_mfa_r2_adoption.py`와 실제 연도 runner가 이 Gate를
  통과하지 못하면 새 MFA를 시작할 수 없다.
- 구 r2 builder와 v1 참조층 runner도 같은 Gate에서 조기 중단하도록 했다. 이
  시험에서 전역 `trap`이 아직 정의되지 않은 lock 정리 함수를 불러 실제 오류를
  가리던 PowerShell 결함을 발견해, lock 상태·정리 함수를 스크립트 맨 앞에서
  초기화하도록 수정했다.
- 2020–2022 r2 DB·TextGrid·동반표·검토 결과는 삭제하거나 label만 바꾸지 않고
  읽기 전용 방법론 증거와 r3 회귀 자료로 보존한다.
- 같은 24표본 청취·광범위 파일 검토는 반복하지 않는다. 이미 발견한 2022
  08/09/15/24번과 음운현상별 자동 표본을 r3 표적 회귀에 재사용한다.
- r3는 관측 표면형당 한 행인 canonical 선택표에서 표기 Roman, 규칙 예상형,
  사전 후보·품사/출처, r2 phone, 선택 r3 phone과 결정 근거를 함께 관리한다.
  검색 동반표와 실제 MFA 사전은 같은 선택 projection·contract ID를 써야 한다.
- r3가 채택되면 2020–2025를 같은 acoustic phone inventory와 같은 선택 계약으로
  다시 정렬한다. 구 TextGrid phone 문자열만 교체하는 것은 금지한다.

### 현재 정지점

- r2를 이용한 2023 진입과 추가 v1 참조층 backfill은 중단했다.
- 다음 구현은 r3 canonical 선택표 builder, zero-fallback 검증, MFA 사전
  projection 동등성, 기존 표본 표적 회귀, 단일 adoption Gate 순서다.
- 이 단계에서 연구자가 다시 청취·승인하거나 PowerShell 장시간 명령을 실행할
  일은 없다.

### r3 canonical inventory 첫 전수 실물

- `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  01_canonical_inventory`에 2020–2025 공통 881,237형 전수 inventory를 생성했다.
- 출력은 30,954,798 bytes, SHA-256
  `1a42a0b07daae7a9d9a4b0adc6438e828e17cb5b6b4bef6b1ae6851a03742f05`다.
- r2 phone과 표면 규칙형이 정확히 같은 382,891형·19,765,802회만 provisional
  유지했다. 나머지 498,346형은 phone을 임의로 만들거나 첫 변이를 선택하지 않고
  근거별 후보·보류 상태로 남겼다.
- 규칙 예상형과 사전 근거가 동의하지만 r2가 다른 교체 후보는 7,179형·535,600회,
  사전 지지 예외 후보는 426형·46,197회다. 이들도 backend phone 후보가 Roman
  목표와 정확히 대응하기 전에는 최종 선택하지 않는다.
- 사용자는 최종 수정이 TextGrid에 반영돼야 하고 2020–2025가 동일해야 함을 다시
  확인했다. 이에 r3 계약은 새 r3 DB에서 6-tier를 재생성하고, 모든 연도 TextGrid
  manifest가 동일 r3 contract ID·사전 SHA를 기록해야만 완료로 인정하도록 보강했다.
- 이어서 기존 2020–2022를 모두 처음부터 다시 정렬하는 것은 반복 방지 목적에
  어긋난다는 연구자 지적을 반영했다. 최종 정책은 전수 재계산이 아니라 **증명 기반
  선택 재사용**이다. LAB의 모든 token에 대해 r2/r3 발음 변이 집합이 같은 전체
  화자/세션 적응 단위는 기존 TextGrid를 재사용하고, 하나라도 달라진 단위만 r3로
  재정렬한다. 2023–2025는 아직 최종 정렬 전이므로 r3로 한 번만 정렬한다.
- 재사용은 단순 추정이 아니다. WAV·LAB·acoustic model·feature/alignment 설정,
  기존 QC, token별 변이 집합이 모두 같아야 하며, 동등 세션의 층화 표본을 r3로
  다시 돌려 label·경계 허용치 동등성을 확인한다. 실패하면 해당 적응 단위를
  재정렬 범위로 승격한다.
- 최종 발화 index는 각 TextGrid를 `reused_r2_equivalent` 또는 `realigned_r3`로
  표시하고 equivalence proof SHA·r3 contract ID·사전 SHA를 함께 기록한다. 기존
  r2 phone 문자열을 제자리 치환하는 방식은 계속 금지한다.

### r3 후보 근거 확장과 장시간 G2P 준비

- canonical inventory의 미선택 유형에 기존 phone을 억지로 복사하지 않았다.
  규칙 예상 Roman과 정확히 같은 기존 표면형 phone만 donor 후보로 연결했으며,
  346형·245,597회가 후보가 됐다. 이는 최종 선택이 아니다.
- donor로 해결되지 않은 규칙 민감 source 312,410형·4,472,892회를 규칙 목표
  한글형 310,605개로 중복 제거했다. 동결 Jamo G2P v3.2.0의 grapheme 계약을
  전수 확인하고 25,000개 단위 13 shard를 만들었다.
- target inventory SHA-256은
  `65b51abc7a76ca5a84bf41379422c4d21333d0781ef150dba2be1c5d91408fde`다.
  target manifest는 `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  03_g2p_rule_targets_1best\G2P_TARGETS_MANIFEST.json`에 있다.
- G2P 1-best는 발음 정답이 아니라 backend phone 후보로만 사용한다. 독립적으로
  계산된 규칙 목표 Roman과 정확히 맞는 결과만 다음 선택 단계로 넘긴다. 임의
  fallback, `spn`, acoustic inventory 밖 phone은 허용하지 않는다.
- `run_common_pron_mfa_r3_g2p_candidates.ps1`은 MFA G2P exit 0 뒤 생성한
  입력·출력·모델 SHA 보고서가 있을 때만 shard를 완료로 인정한다. 창이 닫혀
  부분 `.dict`만 남으면 완료로 오인하지 않고 archive한 뒤 해당 shard만 다시
  계산한다. 완료 shard는 재사용한다.
- Windows PowerShell 5.1 안전성·런타임 검사와 실제 `-PreflightOnly`가 통과했다.
  이 준비 과정에서는 최종 사전, adoption, 연도별 MFA, TextGrid를 변경하지 않았다.
- 20:43 KST 사용자가 사용자 홈에서 상대경로 상태판 명령을 실행해 `-File` 경로
  없음 오류가 났다. 읽기 전용 상태 확인 결과 `prepared_not_started`, lock 없음,
  완료 shard 0이어서 계산·자료 영향은 없었다. RUNBOOK과 연속성 문서의 사용자용
  명령을 프로젝트 절대경로로 통일했다.
- 20:44:58 KST 절대경로 본 실행은 정적 preflight 뒤 절전 방지 flag
  `[uint32]0x80000001`의 Windows PowerShell 5.1 음수 `Int32` 해석 때문에 첫
  shard 전에 중단됐다. lock 없음·완료/부분 shard 0을 확인했다. flag를
  `Convert.ToUInt32(..., 16)`으로 고치고 `-PreflightOnly`가 sleep guard 활성화·
  복원까지 실행하도록 보강했다. PS 안전성 50파일, 런타임 63스크립트와 새 실제
  preflight가 통과했으며, unsafe hexadecimal cast 재도입을 정적 회귀에서 막았다.
- 20:51:40 KST 수정본 본 실행이 시작됐다. 첫 shard가 계산 중일 때 완료 보고서가
  아직 없는 활성 `.dict`를 상태판이 `interrupted_unverified_outputs=1`로 표시해
  실제 중단처럼 보이는 표현 문제를 발견했다. 실행·후보 자료는 건드리지 않고,
  live lock이 있으면 `active_unverified_outputs`, lock이 없을 때만
  `interrupted_unverified_outputs`로 나누도록 읽기 전용 상태판을 보정했다.
- 연구자는 G2P 후보 계산 뒤 수정 발음이 최종 TextGrid에 실제 반영되는 단계까지
  누락하지 말 것을 다시 확인했다. 현행 r3 계약은 G2P 완료를 생산 완료로 보지
  않는다. 후보 검증→canonical 선택→MFA 사전 adoption→변경 적응 단위 재정렬→
  6-tier 재생성 또는 증명된 동등본 재사용→모든 발화 final index의 r3 contract
  ID·사전 SHA·`alignment_origin` 검증까지 통과해야만 연도 완료로 인정한다.
  기존 r2 TextGrid의 phone 문자열만 제자리에서 바꾸는 방식은 계속 금지한다.
- 연구자는 위 중간 수정 방법론을 논문 각주에 명시할 것을 다시 확인했다. 각주
  초안은 현재 방법론 방향만 고정하며, 완료 전 재사용·재정렬을 과거형 사실로
  인용하지 않는다. r3 adoption과 6개년 TextGrid materialization 뒤 실제 후보·
  보류·재사용·재정렬·연도별 TextGrid 수 및 contract/사전 SHA를 manifest에서
  채우는 최종 각주 확정 Gate를 방법론 노트에 추가했다.
- 논문 연구방법·각주에 중간 수정 이유와 절차를 그대로 인용할 수 있도록
  `docs/decisions/METHODS_NOTE_common_pron_r3_revision_for_reporting_20260807.md`를
  만들고 r2 문제 발견→전수 감사→r3 후보/선택 분리→증명 기반 재사용 정책과
  commit·manifest 근거를 기록했다.



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

### 2021 진입 전 저장소 정본·archive 정리

- VS Code의 Source Control `185`는 push 실패가 아니라 tracked 변경 0,
  untracked 산출물 185개 표시였다. 145개는 검토 폴더, 19개는 보고서였고 전체
  9.059MiB였다.
- 2020 최종 TextGrid 868,187개, 보존 DB, 결합 제외 계약, 동반표, 독립 감사,
  생산 표본 승인, Gate B는 보호 목록으로 고정하고 이동·수정하지 않았다.
- 현재 생산 전에 끝난 로컬 파일럿 5폴더를
  `outputs/archive/pre_2021_local_20260803`으로 이동했다. 각 폴더의 이동 전후
  파일 수·바이트·결정적 트리 SHA-256이 모두 같았다.
- 구 기기 설정, 반복 검토를 유도하던 단계별 학습노트, 구 Dropbox root 결정문
  3개를 `docs/archive/pre_2021_cleanup_20260803`으로 이동했다. 구 3-tier·잔여 재정렬,
  일회성 이행, 병목 파일럿 코드 13개는
  `scripts/archive/pre_2021_legacy_20260803`으로 이동했다. 현행 Jamo r2,
  6-tier exporter, 연도 큐, 감사 및 Gate B 코드는 유지했다.
- Git에는 Gate B·독립 감사·DB 표본·연구자 결정 등 작은 재현 근거만 남기고,
  WAV·TextGrid·LAB·미리보기·중복 검토 payload와 진행 JSONL은 로컬 보존/무시로
  분리했다. 상세 manifest는
  `docs/archive/ARCHIVE_MANIFEST_pre_2021_20260803.md`다.

### 2021–2025 구 실행 결과·상태 정리

- 새 2021 실행과 과거 산출물이 섞이지 않도록 D:의 구 TextGrid, MFA temp/output,
  marker, log 및 E: archive를 읽기 전용으로 대조했다. 2022–2025의 구 merged
  TextGrid와 2021의 구 TextGrid·MFA DB/temp는 이미 E:에서 검증 완료됐고 대응
  D: 연도 폴더는 0개였다.
- 활성 상태에 남은 구 2021 로그·LAB 완료표시·입력계약 9개, 4,208,271 bytes를
  exact allowlist로 제한해
  `E:\READ_ONLY_ARCHIVE\2026_summer_research\pre_2021_active_state_20260803`에
  압축했다. 7-Zip test가 통과했고 압축본은 458,443 bytes, SHA-256은
  `fb4ccb859a60b9833960d38ba97330a530fbd89be0b820e08e32ebf004edbc39`다.
  검증 뒤 활성 사본 9개를 정리했으며 남은 활성 구 상태는 0개다.
- 구 2021 align/merge marker 2개는 이미 `archive_stale`에 격리된 감사 증거이므로
  유지했다. 기존 2021 `.lab` 약 133만 건은 모델 산출물이 아니라 동결 CSV 기반
  입력이므로 보존했다. 완료표시를 제거했기 때문에 새 실행은 이를 건너뛰지 않고
  전수 재검증하고 불일치 파일만 다시 쓴다.
- 2020 최종 6-tier 868,187개, 보존 DB, Gate B, 원본 WAV/CSV, 공통 Jamo r2,
  `morph_search.v3`는 변경하지 않았다. 사후 보호 경로와 2021 LAB 존재를 다시
  확인했다. 실행·근거 보고서는
  `scripts/archive/pre_2021_cleanup_20260803/archive_pre_2021_active_state_20260803.ps1`과
  `outputs/reports/ARCHIVE_pre_2021_active_state_20260803.json`이다.

### 2021–2025 진입 직전 Gate B 구 queue 기본값 차단

- 2021–2025 목표를 시작하며 Gate B를 다시 실행했을 때
  `preflight_2020_gate_b.ps1`의 기본 `QueueId`가 구
  `mfa_r2_prod_2020_20260801`을 가리키는 것을 발견했다. 실제 2020 완성
  TextGrid·DB·승인 자료는 손상되지 않았지만, 존재하지 않는 구 감사·승인 경로를
  읽어 canonical Gate B 보고서 3개가 일시적으로 `failed`로 갱신됐다. 이 상태에서
  2021 계산은 시작하지 않았다.
- Gate B가 허용하는 queue를 최종 생산 ID
  `mfa_r2_prod_2020_export_20260803` 하나로 동결했다. 남은 연도 후보표 준비기와
  시작 wrapper도 이 ID를 명시 전달해 기본값 의존을 없앴다.
- 구 queue ID를 고의로 전달했을 때 exit 1로 거부되고 세 canonical Gate 보고서의
  SHA-256이 변하지 않는 것을 확인했다. 이어 최종 queue로 다시 실행해 source
  contract, 연구자 24/24 승인, 6-tier 감사, 보존 DB, DB 재수출 24/24,
  companion manifest를 포함한 core 16/16과 최종 `allow_remaining_years=true`를
  복원·재확인했다.
- PowerShell 5.1 안전·런타임 검사를 함께 통과했다. 이 수정은 2020 산출물이나
  phone 기준을 바꾸지 않고, 잘못된 과거 queue로 Gate 근거가 덮이는 재발만
  차단한다.

### 2021–2025 후보표 진입점 PowerShell 5.1 인자 계약 보강

- 남은 연도 후보표 준비기를 처음 실행할 때 Windows PowerShell 5.1의 native
  `-File` 경계에서 `-Years 2021,2022,...`가 문자열 하나로 전달되는 문제를
  잡았다. 이어 선택 인자인 빈 `AudioRecoveryPlan`도 다음 인자의 값을 삼키는
  문제가 확인됐다. 두 경우 모두 2021 읽기 감사 단계에서 중단됐고 후보표,
  승인 계약, MFA 결과는 생성되지 않았다.
- 공용 `mfa_year_selection.ps1`을 추가해 외부 프로세스 경계에서는
  `-YearsCsv '2021,2022,2023,2024,2025'`만 사용하고, 내부에서 허용 연도·빈
  선택·중복을 검증한 배열로 복원한다. 선택 경로 인자는 값이 있을 때만 전달한다.
- 과거 후보표를 다시 만들고 있는지 전수 대조했다. 현행 작업공간과 로컬 review
  archive에는 2020 후보표만 있으며, 과거 full6y preflight도 2021 승인 계약 없음,
  2022–2025 LAB/승인 계약 없음으로 기록돼 있다. 구 2021 LAB 완료표시는 앞선
  archive 단계에서 의도적으로 격리됐고 현행 보고서도 없으므로 승인 근거로
  재사용할 수 없다. 따라서 2020은 반복하지 않고 2021–2025만 각 연도의 실제
  CSV–WAV·LAB 입력에 대해 후보표를 한 번씩 준비한다.
- 후보표는 공통발음사전이나 형태소 검색표가 아니라 해당 연도 MFA 입력에서
  제외할 손상·대응 불가 발화를 승인하는 연도별 계약이다. 같은 원인 범주는
  요약 단위로 검토하되, 서로 다른 연도의 행을 한 연도 승인으로 대체하지 않는다.

### 2021 후보표 전수 준비와 원본 음원 불량 fail-closed

- 보강한 진입점으로 2021을 실행했다. LAB 입력 1,373,920행을 전수 확인해 기존
  LAB 내용 일치 1,373,521, 신규 0, 불일치 재작성 0, WAV 누락 0, 빈 입력 399를
  확인했다. 미해결 기호 17,394건은 별도 inventory로 보존했다. 즉 구 LAB를
  결과로 신뢰한 것이 아니라 현행 search master와 내용 동등성을 확인해 재사용했다.
- 입력 감사는 4,143 CSV·1,373,920행과 WAV 1,416,216개를 확인했다. 44 bytes
  미만 파일은 0이었지만 duration 대응 issue 1,005건이 발견돼 후보표 생성기가
  안전 중단됐다. MFA와 2022는 시작하지 않았다.
- 12개 영향 세션의 읽기 전용 duration 계획을 만들었다. 4개 세션은 거의 모든
  원본 PCM/WAV가 0.1초 또는 0초였고, 나머지는 개별 0초·header 불량이었다.
  길이 연속성에 근거한 고신뢰 remap은 0건이므로 임의 재매핑하지 않는다.
- 이 과정에서 구 `wav_duration_recovery_plan.v1`이 한 세션의 일부 WAV가
  불량일 때 정상 same-ID 파일까지 `target_unresolved`로 확대할 수 있음을
  발견했다. v2는 감사에서 문제로 지목되지 않은 same-ID 파일을 우선 보존하고,
  실제 audio issue ID만 remap/unresolved 대상으로 허용한다. 2021 재계산 결과는
  audio issue 1,005, `target_unresolved` 1,005, 정상 발화 오제외 0,
  고신뢰 remap 0이다. 관련 Python 6시험과 Windows PowerShell 5.1 안전·런타임
  검사를 통과했다.
- 현행 2021 후보표는 1,468행이다. 사유별로 음원 대응 불가 1,005,
  빈 발음참조 399, 원전 분절시간상 텍스트 불가능 64이며 자동 승인은 하지 않았다.
  동일 현상이 다음 연도에서 반복돼 장시간 감사 뒤 수동 명령으로 멈추지 않도록,
  연도 준비기는 audio issue가 있을 때 v2 읽기 전용 계획을 자동 생성한다. 이때도
  remap은 적용하지 않으며, issue 미포함 정상 발화가 제외로 확대되거나 issue가
  누락되면 즉시 중단한다.

### 2023 대량 음원 대응 문제의 원자료 층위 원인 확인

- 2023 후보표의 audio pairing issue 66,459건을 단순 파일명 밀림으로 처리하지
  않고, JSON·배포 PCM·배포 WAV·현재 D: WAV를 대표 세션
  `SDRW2300000022`에서 직접 대조했다.
- JSON은 332발화, 배포 PCM/WAV는 각각 333파일이다. JSON 87번 종료와 88번
  시작 사이 공백은 0.051810초이고, `88.pcm`은 정확히 약 0.052초다. 그 뒤
  `89.pcm` 4.920초가 JSON 88번 4.919790초와, `90.pcm` 4.163초가 JSON
  89번 4.163340초와 대응했다. JSON에 없는 짧은 공백 조각이 음원 파일 번호를
  하나 차지해 뒤 ID가 국소적으로 밀린 증거다.
- 87–91번 배포 PCM과 WAV payload 해시는 모두 같고, 현재 D: WAV와 배포 WAV의
  파일 해시도 모두 같다. 따라서 형태소 CSV 생성, 로컬 WAV 변환 또는 복사에서
  새로 생긴 오류가 아니라 배포 JSON 발화 분절과 배포 개별 음원 분절의 ID 계약
  불일치로 판정했다. 다만 2023 전체에는 여러 offset과 실제 결손·짧은 조각 등
  복합 예외가 있어 일괄 `+1` 보정은 금지한다.
- 1/2/5ms 길이 해상도 합의와 세션 내부 양방향 같은-offset anchor를 함께 적용한
  보수적 계획은 remap 48,053, 고신뢰 identity 184, 미해결 18,222다. 전체 구조
  scan에서 659,040개 코퍼스 엔트리와 source WAV 659,040개가 일대일이며 중복
  source 배정은 0이었다. 아직 자동 적용하지 않았고 24행 층화 음성 표본 검토와
  연구자 승인을 기다린다.

### 2021–2025 안전 본체 우선·회수분 후속 정렬 전환

- 음원 대응 후보 때문에 연도 전체를 세우지 않고, 같은 ID WAV가 같은 음성임을
  감사로 확인한 안전 본체를 먼저 MFA하기로 결정했다. 회수 가능한 음원은 원본을
  바꾸지 않은 별도 staging/shard에서 같은 Jamo r2·acoustic model로 추가하고,
  본체 결과를 다시 계산하거나 덮어쓰지 않는다.
- 최초 5개년 pending 후보표의 SHA·입력계약·감사 보고서를 다시 검증해 5행 범주
  요약을 만들었으나, session gate를 크게 실패한 세션 안의 우연한 길이 일치까지
  안전 본체로 남을 수 있음을 추가 확인했다. 특히 2022 대표 PCM은 같은 payload를
  16 kHz로 감싸 14.04초가 됐지만 48 kHz로 해석하면 JSON의 4.681초와 일치했다.
- 실패 세션은 전 행, gate 통과 세션은 실제 issue 행만 격리한 별도 safe-body
  queue를 기존 표를 덮어쓰지 않고 생성했다. 최종 정본 요약은 검색 4,232,919,
  안전 본체 4,120,627, 승인 후보 112,292이며, 사유는 음원 대응 111,425,
  빈 참조 788, 시간 불가능 79다. 요약 생성은 승인이나 MFA 시작을 하지 않는다.
- 같은 처리 원칙을 적용하되 원인이 모두 2023의 ID 밀림이라고 쓰지 않는다.
  2021은 원음 결손, 2022 일부는 약 3배 길이의 표본율/헤더 가능성 등 연도별
  근거가 다르다. 연구자는 세 범주와 연도별 개수를 승인하면 되고, 수만 행을
  개별 반복 검토하지 않는다.

# 2026-08-03 2021–2025 범주 승인 단일 진입점 추가

- `approve_remaining_mfa_exclusion_categories.ps1`를 추가했다. 연구자가
  5개년의 세 제외 범주를 명시 승인한 뒤 같은 작업을 연도마다 수작업하지 않도록
  후보 CSV SHA·범주·행 수를 먼저 전부 검사하고 별도 승인 CSV·승인 기록·제외
  계약만 생성한다.
- pending 후보표, WAV/LAB, MFA, 정본은 이 진입점에서 바뀌지 않는다. 기존
  산출물은 세 파일이 모두 존재하고 승인자·문구·범주·입력 계약이 정확히 같을
  때만 재사용하며 부분 산출물이나 다른 승인은 자동 덮어쓰지 않는다.
- 범주 승인과 2021 실행을 분리했다. 승인 계약을 2021–2025에 미리 기록해도
  `start_remaining_mfa_after_2020_gate.ps1`는 여전히 2021만 시작할 수 있다.

## 2026-08-03 — 2021–2025 연도별 gate와 실행 queue 분리

- 2021 이후에도 2020과 같은 생산 관문을 반복할 수 있도록 표본 준비·승인,
  직전 연도 gate, 다음 한 연도 시작의 공용 wrapper 4개를 추가했다.
- 5개년 제외 승인 root는 공유하지만 실제 MFA queue는 연도별 ID로 분리했다.
  따라서 2022 실행이 2021 `queue_state.json`을 덮어쓰지 않는다.
- 동일 queue 재개 시 기존 state를 history로 복사하고 SHA-256을 재검증한다.
  같은 queue ID에 다른 연도 선택을 넣으면 시작 전에 중단한다.
- 이미 기계 QC까지 통과한 execution queue는 재실행하지 않고 연구자 표본
  검토와 다음 연도 gate로 보내도록 중복 실행도 차단했다.
- 다음 연도 gate는 source contract, align/merge marker, 보존 DB, 6-tier·동반표
  전수 감사, DB 표본 재수출, 최소 5세션 연구자 인프라 승인을 결합한다. 실제
  음운 실현 판정이나 자동 정본 승격은 수행하지 않는다.
- 실측상 2021–2025 `morph_search.v3` 최종 7표는 아직 0/5년이었다. MFA만 먼저
  완료하면 다음 연도 source gate에서 멈추므로, 각 연도 MFA 전에 검색표를
  checkpoint 생성/재개하고 source contract까지 검증하는
  `prepare_production_year_before_mfa.ps1`를 추가했다. 시작 wrapper도 현 연도
  검색 manifest 성공 없이는 MFA를 시작하지 않는다.
- 실행 여부를 추측하지 않도록 shard 진행률, lock/PID, annual manifest,
  source contract와 D: 여유를 한 번에 보여주는 읽기 전용
  `show_production_year_pre_mfa_status.ps1`도 추가했다.

## 2026-08-04 — Codex 리밋·새 대화 연속성 고정

- 사용자가 계정을 또 만들어야 하는지 우려해, 새 계정 생성이 아니라 같은 계정의
  한도 초기화 또는 새 대화 뒤 재개하는 절차를
  `CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md`로 고정했다.
- 로컬 PowerShell은 Codex 대화와 독립적으로 계속되므로, 새 대화는 먼저 Git과
  읽기 전용 상태판을 확인한다. `partial`, DB, shard, lock은 임의 삭제하거나
  상태 확인 전에 재실행하지 않는다.
- 새 대화용 최소 프롬프트를 문서화하고 `PROJECT_START_HERE.md`에서 바로
  연결했다. 채팅 기억보다 manifest·현재 D:·Git commit을 우선한다.

## 2026-08-04 — 2021 pre-MFA 7표·source contract 생산 완료

- `prepare_production_year_before_mfa.ps1 -Year 2021`을 08:24:33 KST에 시작했다.
  42개 shard를 재시작 없이 순차 처리했고 각 완료 shard는 `status=success`,
  7표, SHA-256 manifest를 갖췄다. 09:28:00에 42/42 shard가 완료됐고, 이어서
  연간 7표를 원자적 partial→final 방식으로 병합했다.
- 첫 실행 구간은 09:24:49까지 1시간 16초 이상 집중 모니터링했다. 그 시점은
  39/42 shard, 92.857%였으며 lock/PID, Python CPU, 최신 checkpoint와 D: 여유가
  모두 정상이고 오류·재처리·정체 징후가 없었다. 시작 시 약 335GiB였던 D: 여유는
  완료 시 약 323GiB로 남아 공간 gate에도 문제가 없었다.
- 09:45:45에 연간 manifest `success`, source contract `frozen`, lock 해제를
  확인했다. 연간 master는 1,373,920발화이며 7표 행 수는 eojeol 6,579,411,
  master 1,373,920, morph boundary 10,641,533, morph token 12,015,453,
  morph unit 17,707,418, orth eojeol 6,610,698, symbol reading 537,167이다.
- 실행 wrapper의 성공을 그대로 신뢰하지 않고
  `verify_production_source_contract.ps1 -Year 2021 -RequireMorphYearSuccess`로
  별도 검증했다. source contract check는 모두 통과했고 source meta SHA와
  input/output path identity가 동결 계약과 일치했다. 연간 manifest gate는
  `all_shards_success=true`, 중복 utt_id 0, 비결정적 gzip mtime 0,
  철자·기호 coverage 일치였다.
- 근거 보고서는
  `outputs/reports/SOURCE_CONTRACT_morph_search_v3_20260801_2021.json`과
  `outputs/reports/VERIFY_SOURCE_2021_after_morph_search.json`이다. 이 단계는
  MFA·TextGrid·2020 완성본·원본 WAV/CSV를 변경하지 않았다. 다음 단계는
  연구자가 2021–2025 safe-body 제외 세 범주를 명시 승인한 뒤 2021 한 연도
  MFA만 시작하는 것이다.

## 2026-08-04 — 2021–2025 safe-body 세 범주 연구자 승인

- 10:02 KST에 연구자 `ari30`이 다음 문구로 명시 승인했다.
  “2021–2025의 audio_pairing_unresolved, empty_reference_unresolved_symbol,
  text_duration_impossible 세 범주를 안전 본체 MFA에서 제외하고, 음원 회수
  가능분은 후속 shard로 처리하는 것을 승인한다. 승인자 ari30.”
- 승인 행은 2021 1,488, 2022 1,231, 2023 103,930, 2024 1,610,
  2025 4,033으로 합계 112,292다. 범주 합계는 음원 대응 불가 111,425,
  빈 참조·미해결 기호 788, 원전 시간상 텍스트 불가능 79다.
- 각 연도의 `04_RESEARCHER_APPROVAL.json`과 `approved_exclusions.json`을
  생성하고 승인자, 승인 문구, 후보 CSV SHA-256, 입력 계약 ID, 범주별 수를
  재검증했다. 이는 자료 삭제 승인이 아니며 안전 본체에서만 분리한다. 회수 가능한
  음원은 원본을 바꾸지 않는 후속 shard에서 같은 공통 Jamo r2·음향모델로 정렬한다.
- 승인 작업은 MFA를 시작하지 않았고 WAV, LAB, 2020 완성본을 변경하지 않았다.
  실제 실행 wrapper도 2021 한 연도만 허용한다.

## 2026-08-04 — 2021 MFA 시작 preflight의 생성 보고서 자기오염 수정

- 2020 Gate B, 2021 source contract, 연구자 승인 1,488건, 공통 Jamo r2,
  109-phone inventory, D: 공간과 모델 검사는 모두 통과했다. 그러나 outer
  wrapper가 먼저 갱신한 `outputs/reports`의 `checked_at`을 최종 Git clean gate가
  미커밋 코드로 오인해 `tracked_code_committed` 하나만 실패하고 안전 중단했다.
- `preflight_mfa_year_queue.ps1`의 Git gate가 `outputs/reports/**`만 제외하고
  나머지 모든 추적 코드·설정·문서·승인 증거의 미커밋 변경을 계속 차단하도록
  수정했다. 안전 검사에는 해당 pathspec을 필수 계약으로 추가했다. 따라서 생성
  보고서 때문에 영구적으로 NO_GO가 되는 순환은 없애되 코드 변경 은폐는 허용하지
  않는다.
- 이 진단 시점에도 MFA는 시작되지 않았다. 수정·승인 증거·문서를 커밋한 뒤
  Windows PowerShell 5.1 안전·호환성 검사와 `-PreflightOnly`를 다시 통과해야
  사용자 PowerShell용 장시간 2021 MFA 명령을 제공한다.
- 수정과 승인 증거를 커밋한 뒤 10:11 KST에 같은 `-PreflightOnly`를 재실행해
  최종 `GO`를 확인했다. PowerShell 안전 검사 45개 파일, 5.1 실행 호환성
  52개 스크립트, Python 329개 테스트가 통과했고, 승인 계약·입력·모델·D: 공간
  검사도 모두 통과했다. `PreflightOnly`였으므로 MFA는 여전히 시작하지 않았다.

## 2026-08-04 — 2021 MFA 정렬 전 입력감사 안전 중단과 계약 적용 보강

- 10:23:36 KST에 2021 한 연도 queue를 시작했다. 4,143개 세션,
  1,373,920행을 전수 확인해 기존 LAB 내용 일치 1,373,521, 빈 reference 399,
  신규·불일치 재작성·WAV 누락 0을 확인했다.
- MFA 계산 직전 독립 입력감사가 승인 제외 1,488건 중 활성 WAV+LAB 1,089쌍이
  여전히 입력 폴더에 남은 것을 잡았다. 승인 계약은 검증했지만 LAB builder에
  전달하지 않아 실제 제외를 적용하지 않은 구현 누락이었다. 감사는 이를
  승인되지 않은 active pair로 판정해 10:49:01에 중단했다.
- 같은 감사에서 원본 CSV 분절시간이 `0.0`인 14건도 새로 발견했다. 이는 기존
  1,488행 snapshot에 없으며 2022–2025에는 같은 범주의 추가 건이 0임을 확인했다.
- 중단은 MFA 전에 일어났다. MFA DB·TextGrid는 생성되지 않았고, queue는
  `mfa_failed_checkpoint_preserved`로 남았다. 원본 WAV/CSV와 2020 완성본은
  변경하지 않았다. 근거 보고서는
  `outputs/reports/PREFLIGHT_mfa_input_integrity_2021_eojeol_commonpron_2021_20260804_102356.json`이다.
- 승인된 `alignment_and_analysis` ID는 파생 LAB만 계약별 archive로 옮긴다.
  이동 전후 SHA를 검증하고, 재실행 시 이미 보존된 LAB를 인식하며, active와
  archive 양쪽에 있으면 자동 선택하지 않고 중단한다. WAV/CSV는 이동·삭제하지
  않는다. 적용 inventory와 manifest도 원자적으로 기록한다.
- 승인 제외 계약 SHA를 `alignment_contract_id` 계산에 포함했다. 승인 snapshot이
  바뀌면 과거 alignment temp/DB를 잘못 재사용할 수 없다. runner는 같은 계약을
  LAB builder와 alignment contract builder 모두에 전달한다.
- `csv_duration_invalid`를 `audio_pairing_unresolved / alignment_and_analysis`
  pending 후보로 생성하도록 보강했다. 기존 1,488행 snapshot을 덮어쓰지 않고,
  후속 감사 후보와 병합하는 재현 가능한 merger를 추가했다.
- 새 2021 v2 pending 표는 1,502행이다. 기존 1,488, 후속 감사 1,438 중 중복
  1,424, 새 14이며 범주별로 audio 1,039, empty reference 399, time impossible
  64다. 자동 승인은 0건이다. 연구자 보충 승인과 새 preflight 전에는 재실행하지
  않는다.
- 11:21 KST에 연구자 `ari30`이 다음을 명시 승인했다. “2021의 CSV 분절시간
  0.0인 14건을 audio_pairing_unresolved 보충 후보로 안전 본체 MFA에서 제외하고
  후속 shard로 넘기는 것을 승인한다. 승인자 ari30.” 기존 1,488건의 선행 승인과
  이 보충 승인을 결합해 1,502행 새 계약을 만들었다. 승인 계약 SHA-256은
  `ca60cbd3111a4c6d120229d7822e536ea41fe8d6bad0b08f8126cfb429d1f356`이며,
  승인 계보는 새 review root의 `05_APPROVAL_LINEAGE.md`에 고정했다.
- 수정·승인 증거를 커밋 `05078a3`으로 원격에 푸시한 뒤, 새 approval/execution
  queue ID `mfa_r2_prod_safe_body_2021_v2_20260804`로 `-PreflightOnly`를
  실행했다. 11:27 KST에 2020 Gate B, 2021 source contract, 승인 1,502행,
  공통 Jamo r2·109-phone, D: 322.9GiB, Python 335개와 PowerShell 안전·호환성
  검사가 모두 통과해 최종 `GO`였다. 이 단계는 LAB를 옮기거나 MFA를 시작하지
  않았다.

## 2026-08-04 — 2021 v2 승인 적용·MFA 진입과 첫 1시간 집중 점검

- 새 단일 연도 queue `mfa_r2_prod_safe_body_2021_v2_20260804`는 11:42:13
  KST에 시작됐다. 승인 제외 1,502건을 실제 입력에 적용하면서 파생 LAB
  1,103개를 계약별 가역 보관소로 SHA 검증 이동했고, 나머지 399건은 활성 LAB가
  원래 없음을 확인했다. 두 수의 합은 승인 계약 1,502건과 정확히 일치한다.
  원본 WAV/CSV와 2020 완성본은 변경하지 않았다.
- LAB builder는 4,143세션·1,373,920행을 11:54:38까지 전수 확인했다. 신규 생성,
  내용 불일치 재작성, WAV 누락은 모두 0이었다. 입력 계약은
  `1bda84ba0ce02fed685991f1da0dff3b75577fffa07b05b971293f8c189fe0f8`,
  정렬 계약은
  `5ff1865744c85d982fc43708d7666f9af061cad833aa7fde04a09bef3238d5dd`다.
- 승인 적용 뒤의 독립 입력감사는 12:06:49에 통과했다. 검색 1,373,920행 중
  안전 본체 LAB는 1,372,418개, 승인 제외는 1,502개였고, 승인됐으나 여전히
  활성인 WAV+LAB 쌍 0, duration 잔여 불일치 0이었다. analysis/execution gate가
  모두 참이었다.
- 실제 MFA `--clean` 전수 정렬은 12:07:23에 공통 Jamo r2, 동결 음향모델,
  `num_jobs=4`, D: temp로 시작됐다. 11:42부터 12:42까지 첫 실행 구간을 집중
  점검했다. MFA 하트비트는 매분 갱신됐고 CPU 누적값은 55.83초에서
  2,935.25초로 증가했다. watchdog 중단 예정·정렬 오류 신호·traceback은 없었다.
- setup 초기에 사용 가능 물리 메모리가 일시적으로 284.3MB, 시스템 commit이
  최대 65.8%, MFA tree private memory가 최대 5,481.7MB가 됐으나, 개입 없이
  경고가 해소되고 commit은 90% 미만을 유지했다. 12:42 D: 여유는 322.06GiB였다.
  따라서 재시작하거나 job 수를 실행 중 변경하지 않고 계속 진행한다고 판정했다.
- 구조화된 근거는
  `outputs/reports/MONITOR_2021_mfa_first_hour_20260804.json`에 기록했다. 2021
  MFA·6-tier·동반표·독립 감사·DB 표본·연구자 표본 승인이 끝나기 전에는
  2022를 시작하지 않는다.

## 2026-08-04 — 2021 MFA 코퍼스 로딩·MFCC 장시간 감시

- MFA는 4,143개 세션을 서로 다른 speaker로 인식했다. `Found ... across
  1,416,216 files`의 파일 수는 입력감사의 실제 WAV 수 1,416,216과 일치했다.
  과거의 평면 코퍼스·한 화자 오인 재발은 아니다.
- 검색표 1,373,920행 밖의 WAV는 42,296개였다. `lab_not_expected=0`이고
  `lab_not_expected_with_wav=0`이므로 이들은 활성 LAB가 없는 WAV-only 잔여분이다.
  MFA가 초기 로딩 때 목록은 읽지만 안전 본체 1,372,418건의 정렬 입력에는
  들어가지 않는다. 결과 정합성 문제는 아니고 setup I/O 비용 문제다.
- 현재 2021 실행을 멈추거나 입력 경로를 바꾸지 않는다. 2022 시작 전에 파생
  safe-body corpus view가 42,296개 불필요 WAV scan을 줄이는지 검토하되, 원천
  identity·승인 제외·utt_id 집합·모델·phone 계약의 exact 동등성이 증명될 때만
  최적화로 채택한다. 이 검토는 새 연구자 gate나 새 파일럿을 만드는 이유가 아니다.
- `Generating MFCCs` 구간을 12:54:37–13:56:42 KST에 연속 감시했다. MFCC
  하트비트 62개 동안 CPU는 3,575.97초에서 12,338.36초로 증가했고, 13:56:42의
  `Calculating CMVN` 전환 시 12,416.88초였다. 최대 commit은 64.6%, 최소 사용
  가능 물리 메모리는 469.7MB, D: 여유는 321.02→316.56GiB였다. 오류·watchdog
  중단 신호 없이 단계가 전환돼 실행을 유지했다.
- 구조화된 근거는
  `outputs/reports/MONITOR_2021_mfa_mfcc_to_cmvn_20260804.json`에 남겼다.

## 2026-08-04 — 2021 feature 생성 경고 43,822건의 완전 분해

- MFA가 final features 생성 뒤 43,822개 발화를 무시했다고 경고했다. 입력 계약과
  실행 중 MFA DB를 읽기 전용으로 대조해 `검색표 밖 WAV-only 42,296 + 승인 LAB
  분리 1,502 + LAB·전사가 있으나 feature 생성에 실패한 초단시간 발화 24 =
  43,822`임을 확인했다. 따라서 원인을 알 수 없는 대량 누락이 아니다.
- 마지막 24건은 0.01–0.099875초 WAV이며 DB에서 `ignored=1`,
  `num_frames=NULL`, `features=NULL`이다. 이들을 자동 승인하거나 현재 MFA를
  재시작하지 않았다. 현재 실행은 완료 DB를 보존하도록 계속 진행한다.
- MFA 완료 뒤 export exact-ID reconciliation에서 동일 집합을 다시 확인하고,
  `mfa_feature_generation_failed` 연구자 승인 후보표를 만든다. 승인 뒤 제외 계약을
  결합해 export부터 재개하므로, 이 사유만으로 2021 MFA 전체를 다시 돌리지 않는다.
- 구조화된 목록은
  `outputs/reports/OBSERVATION_2021_mfa_feature_generation_20260804.json`, 현행 결정은
  `docs/decisions/DECISION_2021_feature_generation_ignored_pending_20260804.md`에
  기록했다.

## 2026-08-04 — 2021 training graph 완료와 실제 alignment 진입

- training graph 단계는 14:11:49–14:49:52 KST에 진행됐다. 4개 job이 각각
  약 4.67–4.71GB의 FST를 완성했고 합계는 18,760,162,775바이트(17.472GiB)다.
  4개 graph log도 모두 완료되었으며 합계 158,218,463바이트다.
- graph heartbeat 38개 동안 tree CPU는 13,607.02초에서 18,821.92초로
  5,214.91초 증가했다. 최대 system commit은 84.6%, 최소 사용 가능 물리
  메모리는 267.6MB였고 watchdog 중단 예정과 오류·traceback은 없었다.
- 14:50:11 heartbeat에서 phase가 `align`, stderr가 `Generating alignments`로
  전환됐다. 이때 commit은 72.0%, 사용 가능 메모리는 1,256.5MB로 회복됐고
  4개 alignment log가 생성됐다. 따라서 재시작하거나 job 수를 바꾸지 않고
  계속 실행한다.
- 구조화된 근거는
  `outputs/reports/MONITOR_2021_mfa_graph_to_align_20260804.json`에 남겼다.

## 2026-08-04 — 2021 alignment 초기 구간과 heartbeat 잠금 충돌

- alignment 진입 뒤 14:50:11–15:15:24 KST 25분 동안 279,715건(안전 본체의
  20.381%)을 처리했다. 평균은 초당 184.93건, 마지막 10분은 초당
  202.45건이었다. 재시도는 4,048건(1.447%), alignment 오류 신호는 0건,
  최대 system commit은 72.5%였다.
- 15:15:24 상태 감시가 활성 heartbeat JSONL을 `Get-Content`로 읽는 순간 기존
  `Add-Content` append와 파일 잠금이 한 차례 충돌해 IOException이 화면에
  출력됐다. 이는 MFA 정렬 오류가 아니었고 처리량은 291,846→299,609로 계속
  증가했다. 15:17:26 heartbeat도 재개됐으며, 별도 15초 측정에서 MFA Python
  CPU가 46.891초 증가했다.
- 원인은 연구 계산이 아니라 너무 잦고 write sharing을 허용하지 않은 감시
  읽기였다. 즉시 `Get-Content` polling을 중단하고 이후 관측은 `FileStream`의
  `FileShare.ReadWrite`로만 수행한다. 15:22:28에는 342,747건, 오류 0건으로
  정상 진행을 재확인했다.
- 다음 실행부터 `Write-JsonLine`은 공유 append를 사용하고, IOException을
  100ms 간격으로 10회 재시도한다. 모두 실패해도 보조 heartbeat 한 행만
  경고와 함께 건너뛰며 MFA 본체를 종료하지 않는다. 잠금 충돌 회귀 검사를
  추가했고 Windows PowerShell 5.1 안전성 45파일·호환성 52스크립트 검사를
  모두 통과했다. 현재 실행에는 이미 로드된 함수가 적용되므로 감시 읽기
  방식을 바꾸는 것으로 재발을 막고, 실행을 재시작하지 않는다.
- 반복 점검도 같은 규칙을 따르도록 `show_active_mfa_progress.ps1`을 추가했다.
  상태판은 활성 JSONL을 `FileShare.ReadWrite/Delete`로만 읽고 phase·처리량·오류·
  watchdog·자원·최신 연도 queue를 표시하며 어떠한 상태도 변경하지 않는다.
  백분율 분모는 같은 run의 동결 입력감사 `expected_usable_lab`만 사용하므로
  수동 추정이나 전체 WAV 수 혼용을 피한다.
- 구조화된 근거는
  `outputs/reports/MONITOR_2021_mfa_alignment_initial_20260804.json`에 남겼다.

- 15:54:39 KST의 공유 읽기 중간점검에서 674,926/1,372,418건(49.178%)이
  처리됐고 재시도 10,235건, alignment 오류 신호 0, watchdog 중단 예정 false였다.
  system commit 71.1%, D: 여유 297.15GB로 계속 실행 판정을 유지했다. 근거는
  `outputs/reports/MONITOR_2021_mfa_alignment_midpoint_20260804.json`이다.

## 2026-08-04 — 2021–2025 post-MFA exact-ID 공통 재개 경로

- 2021 feature 실패 24건을 MFA 종료 전에 승인하지 않고, direct exporter의 실제
  `unknown_active_lab_without_alignment` 집합과 보존 DB에서 다시 확정하도록
  공통 절차를 구현했다. `ignored=1`·usable frame 없음은
  `mfa_feature_generation_failed`, interval 없음은 `mfa_alignment_missing`으로
  분리하고, 연구자 표본에도 각 사유가 빠지지 않도록 층화한다.
- 생성 당시 `02_RESEARCHER_DECISIONS.csv`는 immutable pending 근거로 남기고,
  연구자는 별도 `04_RESEARCHER_APPROVAL.csv`만 편집한다. 후보 identity SHA와
  명시 token, 실패 보고서 SHA, DB fingerprint, pre-MFA 승인 계약, DB의 현재
  분류가 모두 맞고 전 행이 `approved`일 때만 새 결합 제외 계약을 만든다.
- `prepare_post_mfa_exact_reconciliation_review.ps1`과
  `resume_year_export_after_post_mfa_review.ps1`을 추가했다. 후자는 같은
  `direct_db_ready` input/alignment contract와 DB를 재검증하고 새 queue에서 MFA
  계산을 건너뛰어 6-tier export만 재개한다. 기존 계약·2020 완성본·원본
  WAV/CSV를 덮어쓰지 않으며 자동 승인과 full-clean 재실행을 하지 않는다.
- 관련 Python 회귀 30개, Windows PowerShell 5.1 안전성 45파일·호환성 54스크립트가
  통과했다. 현재 2021 MFA는 실행 중이므로 후보 수·실제 승인·export 성공은 아직
  주장하지 않는다.

## 2026-08-04 — 2021 MFA 정상 종료·DB checkpoint·post-MFA 후보 확정

- MFA는 20:53:45 KST에 exit 0으로 종료됐다. 최종 heartbeat는
  `watchdog_killed=false`, alignment error signal 0, processed 1,372,394,
  interval 재시도 19,956을 기록했다. alignment 계산을 다시 실행할
  근거는 없다.
- 12.7GB `D:\mfa_tmp\2021\2021.db`를 읽기 전용으로 재검증했다.
  source 1,372,394, word interval 10,572,619, phone interval 39,296,691,
  word·phone이 모두 있는 발화 1,371,883, `spn` 0이었다.
  21:08:22에 `D:\mfa_eojeol\done\2021.direct_db_ready`를 생성했다.
- direct exporter는 파일을 쓰기 전 source 1,373,920, active LAB 1,372,418,
  DB 1,372,394, aligned DB 1,371,883을 exact-ID로 대조했다. 승인 없는
  quarantine, DB-only, source-only, source 밖 LAB, 계약 밖 제외, 잘못된
  analysis-only는 모두 0이었다.
- active LAB에는 있지만 정렬 interval이 없는 535건은 숨기지 않고
  `blocked_exact_id_reconciliation`으로 fail-closed했다. queue는
  `post_mfa_export_failed_db_preserved`로 종료됐고 DB·partial·checkpoint는 보존했다.
- 보존 DB에서 535건을 `mfa_alignment_missing` 511건과
  `mfa_feature_generation_failed` 24건으로 재분류했다. feature 실패 24건은
  전부 0.01–0.10초였고, alignment missing은 0.11–10.44초였다.
- 검토 root는
  `outputs/reviews/mfa_post_exact_2021_mfa_r2_prod_safe_body_2021_v2_20260804`다.
  immutable 후보표, 편집용 승인표, 20건 후보+4건 정상 대조군
  WAV/LAB 표본, `SUMMARY.json`을 생성했다. 표본의 WAV·LAB는 24/24
  실물이 존재하며 자동 승인은 0건이다.
- 현재 재개 조건은 연구자가 두 사유와 535건 제외를 명시 승인하는
  것이다. 승인 후에만 기존 1,502건과 결합한 새 계약을 만들고,
  같은 `direct_db_ready` DB에서 6-tier·동반표 export만 재개한다.
  2021 독립 감사·DB 표본·연구자 표본 gate 전에는 2022를 시작하지 않는다.

## 2026-08-04 — 2021 post-MFA 535건 기술적 제외 승인·preflight

- 21:35 KST에 연구자 `ari30`이 `mfa_alignment_missing` 511건과
  `mfa_feature_generation_failed` 24건, 합계 535건을 안전 본체에서
  기술적으로 제외하고 후속 회수 대상으로 보존하는 것을 명시 승인했다.
  이는 음운 실현·원자료 오류 판정이 아니다.
- 연구자가 현재 청취 시간이 없음을 반영해, 24개 WAV/LAB 표본 청취는
  2021 최종 Gate 전으로 유예했다. 이 검토가 끝나기 전에는 2022를 시작하지
  않는다.
- `04_RESEARCHER_APPROVAL.csv`의 535행을 모두 `approved`로 반영했고,
  immutable 원본과 비교해 year, input contract, utt_id, reason, scope, evidence
  변경 0을 확인했다. 작업본 SHA-256은
  `89bdd81279d90a737d2cc2a72a1bc91c699210fd4e2dd87b2e161260322d28b6`다.
- Windows PowerShell 5.1 안전성 45파일·호환성 55스크립트가 통과했다.
  재개 wrapper `-PreflightOnly`는 기존 1,502건+post-MFA 535건=2,037건,
  후보 identity SHA, DB, 실패 보고서, 입력·정렬 계약을 모두 재검증해
  `validated_preflight`을 반환했다. preflight는 계약·MFA·export를 생성하지 않았다.

## 2026-08-04 — 첫 export 재개 안전 중단·정렬/export 계약 분리

- 결합 2,037건 계약을 생성한 뒤 첫 재개 queue를 시작했으나, 6-tier 파일이나
  MFA를 시작하기 전에 `direct_db_ready` alignment identity 불일치로 중단됐다.
  marker의 실제 계산 계약은 `5ff1865744c85d...`, 단일 결합 계약으로 재작성된
  값은 `11e9f6d3078ac...`였다.
- 원인은 post-MFA 제외가 이미 끝난 정렬의 provenance까지 소급 변경한 변수
  설계였다. DB·원자료·2020 완성본 문제는 아니며, fail-closed gate가 전수
  재정렬을 막았다. 실패 queue와 결합 계약은 시행착오 증거로 보존한다.
- 실행 경로에 기본값 호환 방식의 계약 분리를 추가했다. 정렬 당시 pre-MFA
  계약은 alignment contract 생성에만 고정하고, post-MFA 결합 계약은 LAB
  재정돈·입력감사·direct export·독립 QC에 전달한다.
- Windows PowerShell 5.1 안전성 46파일·호환성 55스크립트, Python 전체
  340시험이 통과했다. 실제 재개는 코드 커밋·새 queue `PreflightOnly`가
  통과한 뒤에만 수행한다.
- 교정 커밋 `5331e53`을 원격 브랜치에 푸시한 뒤 새 execution queue
  `mfa_r2_prod_safe_body_2021_v2_20260804_postmfa_v2`의 `PreflightOnly`를
  실행했다. export/QC 결합 계약 2,037건과 정렬 provenance 계약 1,502건이
  각각 같은 input contract에 결속됐고 최종 상태는 `GO`였다.
- 정렬 당시 1,502건 계약으로 alignment contract를 별도 임시 재구성한 값은
  `5ff1865744c85d982fc43708d7666f9af061cad833aa7fde04a09bef3238d5dd`로,
  `2021.direct_db_ready` marker와 exact match였다. 이 검사는 MFA·DB를
  수정하지 않았으며 결합 2,037건 계약이 정렬 identity에 들어가지 않음을
  실제 파일 fingerprint로 확인했다.

## 2026-08-04 — 2021 보존 DB 재개 입력 게이트 역조건 교정

- v2 queue는 LAB 4,143세션·1,371,883건 전수 내용 일치, 신규 0, 불일치 재작성 0을
  확인하고 정렬 계약을 `5ff186…`로 정확히 복원했다.
- 이후 읽기 전용 실행 감사는 4,143 CSV·1,373,920행, duration 대상 1,371,883건을
  검사해 duration mismatch 0, tiny WAV 0, 위험한 예상 밖 LAB 0을 확인했다.
- 단 하나의 실패는 `approved_alignment_active_pairs_authorized`였다. DB interval 누락과
  exact-match된 승인 ID 511건의 LAB가 이미 제거돼 활성 쌍이 0인데도, 감사 코드가
  활성 승인 쌍 수와 승인 ID 수의 완전 일치를 요구한 구현 오류였다.
- 판정을 `미승인 활성 쌍 0`이고 `활성 승인 쌍이 승인 집합의 부분집합`인 조건으로
  교정했다. DB 누락 ID exact-match는 그대로 유지한다. 따라서 안전 기준과 연구 계약은
  낮아지지 않는다.
- 관련 회귀 테스트를 추가했고 Python 전체 340개, PowerShell 안전 46파일,
  Windows PowerShell 5.1 호환성 55스크립트가 모두 통과했다.
- 실패 queue와 보고서는 시행착오 증거로 보존한다. 2021 DB checkpoint와 원자료,
  2020 완성본은 변경하지 않았으며 새 queue에서 direct export만 재개한다.

## 2026-08-04 — 2021 direct exporter 비활성 승인 DB ID 오판 교정

- v3 queue의 실행 감사가 4,143 CSV·1,373,920행, 활성 LAB 1,371,883건을 검사해
  통과했고, 12.7GB DB 체크포인트도 정렬 계약 `5ff1865744c8…`과 다시 일치했다.
- 23:48:17부터 재정렬 없이 direct export에 진입했으나 23:52:41에 exporter가
  `db_ids_without_active_lab=511`로 fail-closed했다. 이 511건은 보존 DB의 interval
  미생성 ID와 exact-match하는 승인 post-MFA 제외이며 LAB가 이미 비활성화된 상태다.
- `export_mfa_db_research_6tier.py`에서 미승인 DB-only 집합만 차단하도록 교정하고,
  승인된 비활성 DB ID를 실제와 같은 fixture로 재현하는 회귀 테스트를 추가했다.
  승인되지 않은 활성/DB-only/source-only ID를 차단하는 기존 검사는 유지된다.
- exporter 테스트 10개, Python 전체 342개, PowerShell 안전 46파일, Windows
  PowerShell 5.1 호환 55스크립트가 모두 통과했다.
- 실패 당시 partial 파일은 0건이며 DB·원본 WAV/CSV·2020 완성본은 변경되지 않았다.
  근거는 `outputs/reports/FAIL_2021_direct_export_inactive_approved_db_ids_20260804.json`에
  기록했다. 새 queue에서는 MFA 계산을 건너뛰고 같은 DB에서 export를 재개한다.

## 2026-08-05 — 2021 v4 첫 1시간 집중 모니터링과 direct export 진입

- v4 queue는 00:03:30 KST에 시작됐다. LAB 4,143세션·1,371,883건은 신규 생성·재작성
  없이 전수 일치했고 입력·정렬 계약은 각각 `1bda84…`, `5ff186…`으로 유지됐다.
- 실행 감사는 4,143 CSV·1,373,920행과 WAV duration 1,371,883건을 전수 검사했다.
  duration mismatch, 예상 밖 LAB, 미승인 active/DB-only ID는 0건이고 승인 비활성 DB
  ID 511건은 보존 DB의 interval 누락 집합과 exact-match했다.
- WAV 1,416,216개를 추가 스캔해 `<44B` 불량 0건을 확인했다. 12.7GB DB 체크포인트는
  다시 통과했고 로그에 `재정렬 없이 출력 단계만 재개`가 명시됐다.
- 01:11:24부터 direct export가 시작됐고 수정된 exact-ID gate가 실제 전수 데이터에서
  통과했다. 01:27 관측 시 500/4,139세션·170,326개 6-tier TextGrid를 생성했으며 오류
  신호는 0건이다.
- 00:03부터 01:27까지 1시간 이상 집중 모니터링했다. D: 디렉터리 I/O 지연 구간이
  있었으나 같은 프로세스가 재시작 없이 전진했다. 상세 근거는
  `outputs/reports/MONITOR_2021_v4_first_hour_to_export_500_20260805.json`에 기록했다.

## 2026-08-05 — 2021 v4 전수 순회 후 float32 종단 경계 교정

- 02:56 KST에 4,139세션 순회가 끝났으나 1,371,883개 중 6개가 WAV xmax보다
  1.2207–6.7139µs 큰 마지막 word·phone end로 안전 차단됐다. exporter는
  1,371,877개 부분 TextGrid와 12.7GB DB를 보존하고 동반표·2022 진입을 막았다.
- 6개 WAV를 프레임 단위로 대조했다. 모두 16kHz이며 차이는 0.0195–0.1074샘플,
  DB interval end는 같은 WAV duration의 float32 표현과 정확히 일치했다. 정렬이나
  음향모델·phone 문제가 아니라 수치 표현 차이다.
- 파일별 float32 표현으로 설명되는 0/xmax 차이만 정규화하도록
  `research_textgrid_v2.py`를 고쳤다. 고정 광역 tolerance는 도입하지 않았고 실제
  범위 초과·overlap·gap 차단은 유지했다.
- direct exporter는 TextGrid와 동반표에 같은 정규화 경계를 쓰고 발화 수·경계 수·
  최대 조정량·예시를 최종 JSON에 기록하도록 보완했다. 관련 단위·통합 테스트 18개,
  Python 전체 345개, PowerShell 안전 46파일·5.1 호환 55스크립트와 실제 6건 진단이
  통과했다. 첫 v5 `PreflightOnly`는 데이터·계약·모델·공간·테스트가 모두 통과한 뒤
  미커밋 코드만 `tracked_code_committed=false`로 차단했다. 수정·NO_GO 근거를 먼저
  커밋하고 같은 preflight가 GO일 때만 보존 DB에서 export를 재개한다.
- 수정·결정·실측 보고서와 NO_GO 증거를 `f205d32`로 커밋·푸시했다. 03:10 KST에
  같은 v5 `PreflightOnly`를 재실행해 모델·공통사전·승인 계약·입력·DB 재개 상태·
  저장공간·커밋·전체 345개 테스트가 모두 GO임을 확인했다. `PreflightOnly`이므로
  이 시점에는 실제 queue나 MFA/export가 시작되지 않았다.

## 2026-08-05 — 2021 v5 전수 끝검사 19건 안전 중단과 표적 복구 설계

- v5는 보존 DB와 partial을 재사용해 4,139세션을 끝까지 검사했다. v4에서
  누락됐던 6개는 정확히 생성됐고, 기존 1,371,858개는 통과했으나 19개 기존
  TextGrid가 신규 예상 interval과 달라 동반표 전 안전 중단됐다. 2022는 시작되지
  않았다.
- 19개를 현재 DB·검색표·음향모델로 재구성한 결과 19/19가 `f205d32` 이전
  writer로 정확히 재현됐고 라벨 차이는 0건이었다. 차이는 12세션에서 발화 끝
  0.656–6.714µs를 빈 interval로 남긴 구 직렬화 규칙뿐이다. 근거는
  `outputs/reports/DIAG_2021_v5_textgrid_mismatches_20260805.json`이다.
- 19개를 archive+SHA 검증 뒤 원자적으로 교체하고, v5 전수 통과 증거와 repair
  manifest를 결합해 동반표부터 재개하는 복구 경로를 추가했다. 실패 목록이
  완전하지 않거나 DB·모델·계약·경로·파일 fingerprint가 하나라도 다르면
  fail-closed한다. 독립 연도 전수 감사와 DB 표본 재수출은 그대로 수행한다.
- 실제 mutation 전 repair preflight는 19건·12세션·최대 6.713867µs로 `READY`다.
  Python 347개, PowerShell 안전 46파일, Windows PowerShell 5.1 호환 55스크립트가
  통과했다.
- 세부 결정은
  `docs/decisions/DECISION_MFA_2021_targeted_terminal_repair_checkpoint_resume_20260805.md`에
  기록했다.

## 2026-08-05 — 2021 TextGrid 19건 표적 복구 적용 완료

- mutation 전 preflight가 확정한 19건만 적용했다. 구 파생 TextGrid는
  `D:\mfa_eojeol\repair_archive\2021_float32_terminal_roundoff_20260805`에
  상대경로와 SHA-256을 보존한 뒤, 현재 DB·검색표로 재구성한 6-tier 파일로
  원자 교체했다.
- repair manifest는 `success`, 복구 19/19다. 적용 뒤 보관본과 교체본의
  SHA-256을 실제 파일에서 다시 계산해 각각 19/19 일치, 문제 0건을 확인했다.
- 변경 범위는 direct-export 부분 산출물 19개다. 2021 MFA DB·원본 WAV/CSV·
  검색표·2020 완성본은 변경하지 않았다.
- 다음 queue는 전수 MFA나 전수 TextGrid export를 반복하지 않는다. v5 전수
  검증 결과와 표적 복구 manifest를 fail-closed로 결합해 동반표부터 재개하고,
  승격 후 독립 전수 감사와 DB 표본 24개 재수출은 생략하지 않는다.
- 적용 증거:
  `outputs/reports/REPAIR_2021_float32_terminal_roundoff_20260805.json`

## 2026-08-05 — 2021 v6 의미 동일 정렬 계약의 파일 SHA 오판 교정

- v6는 LAB 4,143세션·1,371,883건 전수 일치, CSV 4,143개·1,373,920행
  실행 감사, WAV 1,416,216개 손상 0건, 12.7GB DB `quick_check=ok`,
  word 10,572,619·phone 39,296,691·spn 0을 확인했다. MFA는 재계산하지 않았다.
- 동반표 직전 재개 gate가 `alignment_contract_file` 하나로 안전 중단됐다.
  같은 4,050바이트 계약의 `recorded_at`만 새 실행 시각으로 바뀌어 파일 SHA가
  달라졌지만, 저장 정렬 ID와 builder 생성식 재계산 ID는 모두 `5ff186…`였다.
- 계약 생성기는 같은 의미 ID의 기존 파일을 보존하도록 바꿨다. 재개기는 파일
  전체 SHA 대신 builder canonical identity를 독립 재계산한다. 모델·런타임·
  입력·공통사전·승인 제외 SHA는 모두 ID에 포함하고 `recorded_at`만 제외한다.
- 관련 8개, Python 전체 348개, PowerShell 안전 46파일·5.1 호환 55스크립트가
  통과했다. 실제 2021 계약도 `semantic_match=true`였다.
- 실패 근거:
  `outputs/reports/FAIL_2021_v6_alignment_contract_recorded_at_identity_20260805.json`.
  DB·partial·원본·2020 완성본은 보존됐으며 다음 실행은 동반표부터 재개한다.

## 2026-08-05 — 2021 checkpoint 후처리 실행과 비재계산 승격 경로

- 06:28 KST부터 보존 DB·v5 전수 보고서·19건 표적 repair·현재 의미 정렬 계약을
  다시 결속한 후처리기를 실행했다. MFA, LAB 생성, 6-tier TextGrid 전수 생성은
  재실행하지 않으며 네 gzip 동반표와 최종 성공 보고서만 만드는 실행이다.
- 실행 중 프로세스·CPU·메모리·D: 여유 공간을 확인했고, `_tables` 아래 네
  `.partial`이 원자적 writer 정책대로 생성된 뒤 단일 후처리가 계속 진행 중임을
  확인했다. `Get-PSDrive`가 제한 셸에서 0을 반환한 관측은 `DriveInfo`로 재검증해
  실제 여유 264GiB임을 확인했으며 용량 부족으로 판정하지 않았다.
- 성공 뒤 기존 runner의 LAB·입력·DB 전수 검사를 다시 반복하지 않도록
  `promote_mfa_direct_export_checkpoint.py`를 추가했다. 성공 report, 현재 builder
  canonical alignment ID, `direct_db_ready`, 입력 감사, 동결 search root,
  exact-ID full-year gate, 4개 동반표 크기·SHA와 잔류 partial을 모두 확인한 뒤
  같은 D: 안에서 연도 staging 폴더만 원자적으로 옮긴다.
- 승격은 정본 채택이 아니며 독립 연도 전수 감사와 DB 표본 24건 검증을 생략하지
  않는다. 정상·중단 후 재개·동반표 변조·정렬 의미 변조 회귀시험이 통과했다.

## 2026-08-05 — 동반표 최종 계약에서 발견한 후행 무음 중복 어절 19건

- 06:28 KST 후처리는 MFA·LAB·TextGrid 전수 생성을 반복하지 않고 4,139세션의
  동반표 4종을 끝까지 썼다. 약 3,814초 뒤 최종 계약에서 19발화가 각각
  `lab_word_count_mismatch`와 `word_label_sequence_mismatch`를 내 안전 중단했다.
  최종 gzip과 성공 보고서는 생성되지 않았고 닫힌 네 `.partial`과 12.7GB DB,
  1,371,883개 TextGrid는 보존됐다. 2022는 시작되지 않았다.
- 19건 모두 LAB N개 대 MFA N+1개였고, 끝의 추가 word 표지는 바로 앞 마지막
  어절과 같았다. DB를 interval–phone 연결로 전수 대조하니 추가 interval은 실제
  마지막 어절 끝부터 WAV xmax까지이고 연결 phone은 19/19 모두 `sil`이었다.
  실제 추가 어절이나 phone 오류가 아니라 MFA DB가 후행 무음 word interval에
  마지막 lexical `word_id`를 남긴 경우다.
- exporter와 동반표에 공통 규칙을 추가했다. 연결 phone이 하나 이상이고 모두
  무음인 word interval의 표지만 빈칸으로 만들며 시간과 phone은 바꾸지 않는다.
  `utterance`·철자 Roman·형태소 텍스트도 유지하고 유표 span만 실제 lexical 끝에
  맞춘다. 회귀시험은 동반표 count·sequence와 6-tier 결과를 함께 고정한다.
- 실자료 읽기 전용 preflight는 정확히 19건을 찾았고 phone tier 변경 0건,
  words 변경 19건, 세 검색 tier span 변경 각 19건을 확인했다. 이어 구 파생
  TextGrid를 SHA 보관한 뒤 19/19를 원자 교체했다. 적용 manifest는
  `outputs/reports/REPAIR_2021_phone_only_silence_word_20260805.json`이며 상태는
  `success`다.
- 앞선 float32 종단 repair와 새 repair가 겹치는 파일도 기존 기록을 변조하지 않고
  SHA 사슬로 검증하도록 재개기를 확장했다. 다음 실행은 MFA나 TextGrid 전수를
  반복하지 않고 네 동반표만 다시 쓴다. 그 뒤 연도 staging 승격·독립 전수 감사·
  DB 표본 24건 재수출·연구자 표본 Gate를 거치며, 그 전에는 2022로 가지 않는다.

## 2026-08-05 — 2021 동반표 국소 재개 성공

- 08:00:36–09:02:06 KST에 보존 DB와 두 repair manifest의 SHA 사슬을 재검증하고
  동반표 4종만 다시 썼다. 총 3,690.6초, exit 0이며 MFA·LAB·TextGrid 전수 생성은
  재실행하지 않았다.
- 4,139/4,139세션, 분석 TextGrid·utterance 표 1,371,883행, word 10,572,619행,
  phone 39,296,691행, 승인 제외 2,037행이다. coverage 100%, failed 0, spn 0,
  LAB word count mismatch 0, word label sequence mismatch 0이다.
- 새 규칙이 정규화한 phone-only silence word interval은 정확히 19건이다. 이전
  실패 partial 네 개는 별도 실패 이력으로 보존됐고 새 네 gzip과
  `TABLES_MANIFEST.json`만 최종 이름으로 원자 승격됐다.
- 성공 보고서:
  `D:\mfa_eojeol\logs\direct_db_export_2021_eojeol_commonpron_2021_20260805_phone_sil_fix.json`.
  다음 단계는 이 성공 계약의 비재계산 staging 승격 preflight, 독립 연도 전수
  감사와 DB 표본 24건 재수출이다. 연구자 표본 Gate 전에는 2022를 시작하지 않는다.
## 2026-08-05 — 2021 체크포인트 독립 감사 LAB 루트 계약 교정

- 체크포인트 승격 뒤 독립 감사에서 active LAB 0건, TextGrid 1,371,883건
  전부 `wav_missing`으로 오인되어 안전 중단되었다. 원인은 재개
  스크립트가 `D:\20_AUDIO\03_wav\individual\2021`을 넘긴 상태에서
  감사기가 연도 `2021`을 다시 결합한 호출부 오류였다.
- 2020 Gate B 본 생산 경로는 올바른 상위 `$wavRoot`를 넘기므로 같은
  문제가 없었다. 수정은 동적 `$Year`를 쓰는 공통 재개 경로에 적용되어
  2021–2025 모두를 보호한다.
- 2021 MFA·6-tier·동반표는 재생성하지 않았다. 완료 checkpoint와
  1,371,883개 TextGrid, 네 동반표는 보존했다. 원본 WAV/CSV와 2020
  완성본도 변경하지 않았다.
- 감사 전 실제 LAB probe, 감사기 `lab_year_empty` 빠른 실패, 요약형
  콘솔 출력, PowerShell 경로 회귀 검사를 추가했다. Python 표적 18개,
  PowerShell 안전성 47개 파일, Windows PowerShell 5.1 호환성 56개
  스크립트가 통과했다.
- 수정 후 preflight는 active LAB 1,371,883건과 TextGrid 1,371,883건,
  동반표 SHA를 모두 일치시켰다. 다음 실행은 정렬이 아니라 독립 감사와
  DB 표본 24건만 재개한다.
## 2026-08-05 — 2021 독립 전수 감사·DB 표본 Gate 통과

- 공통 LAB root 계약 수정 커밋 `3eb8caf`로 체크포인트 감사만 재개했다.
  MFA 정렬, 6-tier TextGrid 전수 생성, 동반표 생성은 반복하지 않았다.
- 독립 전수 감사는 2,771.775초에 완료되었다. active LAB, expected
  TextGrid, 실제 TextGrid, utterance 표가 모두 1,371,883건이고 coverage는
  100%이다. word 10,572,619행, phone 39,296,691행, 승인 제외 2,037행이
  manifest와 일치했다.
- 누락·초과·중복·invalid TextGrid·tier 오류·`spn`·phone inventory 밖
  기호·동반표 중복/정렬/행 수 오류는 전부 0건이다.
- 보존 DB에서 24개 서로 다른 세션을 다시 export한 결과 semantic 24/24,
  byte 24/24가 현재 staging TextGrid와 동일했다.
- 연구자 검토표는 24개 세션·24개 화자로 구성했다. WAV/LAB/6-tier 각
  24개와 권위 CSV의 바이트 동일 사본을
  `C:\Users\ari30\Dropbox\MFA_2021_FINAL_REVIEW_20260805` 한 폴더에
  전달했다. 이 Gate는 실제 음운 실현 판정이 아니라 연결·tier·검색 사용
  가능성 점검이다.
- 첫 잘못된 감사의 139MiB 원시 출력은 SHA 요약을 보존한 뒤
  `D:\mfa_eojeol\audit_failure_archive\2021_checkpoint_lab_root_failure_20260805.7z`
  로 압축했고 7-Zip 무결성 검사를 통과했다. 작업 폴더의 원시 대용량
  실패 파일은 제거했다.
## 2026-08-05 — 2022 시작 전 직전 연도 queue 계약 일반화

- 2021 연구자 Gate 대기 중 2022를 읽기 전용 점검했다. 2022의 기존 승인
  제외 계약은 input contract `3043de75...`에 대해 1,231건이 승인되어
  있고, 같은 input ID의 `2022.lab_input_done.json`도 존재한다. 2022 MFA
  DB·정렬 계약·완료 marker는 아직 없으므로 생산 정렬은 시작되지 않았다.
- `start_next_mfa_year_after_gate.ps1`이 직전 연도 queue를 과거 기본 이름으로
  고정해 현재 2021 checkpoint QC queue를 참조하지 못할 수 있음을
  발견했다. `PriorExecutionQueueId`를 명시적으로 받도록 2022–2025 공통
  wrapper를 일반화했다. 2021 연구자 승인 전에는 2022를 실행하지 않는다.
## 2026-08-05 — 2022–2025 잔여 연도 준비 상태 동등성 확인

- 2021 연구자 Gate 대기 중 생산 실행 없이 2022–2025 승인 제외 계약과
  LAB marker를 대조했다. 네 연도 모두 승인 계약 input ID와 LAB marker
  input ID가 일치했다.
- 승인 제외 수는 2022 1,231건, 2023 103,930건, 2024 1,610건, 2025
  4,033건이다. 2023의 큰 제외 집합은 이미 연구자가 승인한 safe-body
  계약을 그대로 보존하며, 이 준비 inventory가 그 판단을 재개정하거나
  우회하지 않는다.
- 네 연도 모두 alignment contract, MFA DB, 정렬 완료 marker가 없으므로
  아직 생산 정렬은 시작되지 않았다. 각 연도는 반드시 직전 연도 연구자
  Gate와 당해 연도 source preflight를 순차 통과한 뒤에만 시작한다.
- 근거: `outputs/reports/PREFLIGHT_2022_2025_readiness_inventory_20260805.json`.

## 2026-08-05 — 2021 표본에서 MFA 입력 phone 의미 재확인·사전 발음 배선 감사

- 연구자가 2021 최종 표본 중 20개 파일은 WAV·LAB·TextGrid가 정상적으로
  열리고 분절도 대체로 적절하다고 확인했다. 첫 표본 `어디든 갈 수 있잖아`에서
  `있잖아`의 `phones_mfa`가 `iː s͈ tɕʰ ɐ n ɐ`로 표시되어, 이를 규칙 발음으로
  오해할 위험을 발견했다.
- 공통사전 실물을 대조한 결과 위 열은 동결 Jamo G2P v3.2.0 1-best와 정확히
  같았다. 이는 음성에서 실제 발음을 판정한 값이 아니라, 주어진 phone 순서를
  음향모델이 시간에 강제정렬한 결과다.
- 2020·2021 search master, `morph_search.v3` 7표, post-MFA 동반표 4종의 실제
  header를 확인했다. `pron_reference_*` 규칙 예상형과 `pron_mfa_*`는 있으나,
  우리말샘 `pron_1/2`·예외·복수 발음 후보 ID는 아직 배선되지 않았다.
- 사전 발음은 type-level long registry와 occurrence link로 분리하고, 연구용
  `eojeol_pronunciation_compare` view에서 규칙 예상형·사전 후보·MFA phone을
  함께 보도록 결정했다. TextGrid에는 음소별 가짜 시간을 만들지 않는 발화
  수준 `pron_reference_utt`를 7번째 파생 tier로 추가한다.
- 기존 2020·2021 MFA·DB·6-tier 정본은 변경하지 않는다. 공통발음열 감사를
  먼저 수행하고, 7번째 tier와 사전 조인표는 MFA 재실행 없이 backfill한다.
  실제 경계 문제가 확인된 occurrence만 별도 국소 재정렬 후보로 분리한다.
- 현행 결정문:
  `docs/decisions/DECISION_dictionary_pronunciation_registry_and_reference_tier_20260805.md`.

## 2026-08-05 — 사전 발음 registry 생성기와 실자료 preflight

- 현재 생산 CSV에 없던 우리말샘 `pron_1/pron_2`와 예외·복수 발음 후보를
  반복 문자열 없이 재사용하기 위해 type-level long registry 생성기를 추가했다.
  enriched 판본에 두 등재 발음이 모두 없을 때만 같은 `urimal_id`의 legacy
  `pron_g2p`를 연결하고, 이를 `is_machine_generated=true`,
  `is_dictionary_attested=false`로 강제 표기한다.
- `pron_1`·`pron_2`의 기존 한글·Roman·Roman-MFA 값을 각각 보존한다. 후보 ID는
  source row 번호가 아니라 표제어·품사·의미 ID·발음·출처의 canonical hash라서
  원천 행 순서가 달라져도 같은 후보를 안정적으로 조인할 수 있다.
- 기존 7월 28일 원천 전수 감사의 SHA-256을 신뢰 앵커로 삼아 실제 enriched
  386,602,735바이트와 legacy 280,816,832바이트의 경로·크기·수정시각을 다시
  대조했다. 두 원천 모두 감사 당시와 일치했고 실자료 preflight가 통과했다.
- Python 표적·기존 공통발음 회귀 13개, PowerShell 안전성 47파일, Windows
  PowerShell 5.1 호환성 57스크립트가 통과했다. preflight 동안 D: 출력은 만들지
  않았다. 실제 registry는 사용자 장시간 PowerShell에서 최초 release로 생성한다.
- 기존 공통 MFA 사전·2020/2021 DB·6-tier·phone 기준은 변경하지 않는다.

## 2026-08-05 — 사전 발음 registry v1 완전성 검증과 Roman 계약 교정

- 사용자 PowerShell 실행은 114.687초에 성공했다. v1은 1,192,729후보,
  `pron_1` 491,178, `pron_2` 37,864, legacy 기계 fallback 663,687행이며,
  의미·출처 동일 중복 10,768개를 제거했다. 출력은 83,743,330바이트다.
- 독립적으로 gzip을 끝까지 다시 읽고 1,192,729행, 필수 열 누락 0,
  사전/fallback flag 모순 0, partial 0, SHA-256 재계산 일치를 확인했다.
- 표본 확인 중 enriched의 기존 Roman-MFA와 legacy `pron_g2p_roman` 구형
  convention이 v1의 한 `pron_roman_mfa` 열에 공존함을 발견했다. 후보 한글·품사·
  의미·출처는 정확하지만 검색 표기 일관성 계약에는 부적합하므로 v1을 채택하지
  않는다.
- v2는 source Roman 두 열을 그대로 보존하고, `pron_hangul`에서 현재
  `roman_mfa.v1` 검색열을 별도로 동일 생성한다. v1을 덮어쓰거나 삭제하지 않으며
  v2만 이후 occurrence 조인과 공통발음열 감사에 사용한다.
- 검증 근거:
  `outputs/reports/VERIFY_dictionary_pronunciation_registry_v1_20260805.json`.

## 2026-08-05 — 사전 발음 registry v2 참조용 채택

- 교정된 v2는 121.231초에 별도 release로 생성됐다. 후보 구성과 semantic ID는
  v1과 같고, Roman 열만 source/source-MFA/current-search로 분리했다.
- 87,968,966바이트 gzip을 독립적으로 끝까지 다시 읽어 1,192,729행, 필수 열
  누락 0, 사전/fallback flag 오류 0, 현대 한글 검색 Roman 누락·버전 오류 0,
  partial 0을 확인했다. 출력 SHA-256도 manifest와 일치했다.
- `수가`는 의미번호별 사전 후보와 fallback이 분리되고 검색열은 모두
  `S U _ G A`, `읽다→익따`는 `I k _ TT A`, legacy `있잖아→읻짜나`는
  `I t _ JJ A _ N A`로 현재 `roman_mfa.v1`에서 동일 검색된다. legacy 값은
  여전히 사전 등재 발음으로 승격하지 않는다.
- v2를 사전 참조·검색 registry로 채택했다. MFA 입력사전·2020/2021 DB·TextGrid는
  변경하지 않았다. 다음 단계는 품사·의미를 보존한 occurrence link와 발음 비교
  감사표 구현이다.
- 검증 근거:
  `outputs/reports/VERIFY_dictionary_pronunciation_registry_v2_20260805.json`.

## 2026-08-05 — 사전 발음 형태소·품사 match index와 2020 소규모 연결

- 119만 사전 후보를 occurrence마다 복제하지 않도록 type group/member 구조로
  정규화했다. 용언은 사전 `word_stem + 정확 품사`, 기타 품사는
  `headword + 정확 품사`를 사용한다. 코퍼스에 의미번호가 없으므로 여러 의미나
  발음 중 하나를 자동으로 선택하지 않는다.
- 202.792초에 564,385 group·804,324 member를 생성했다. 사전 품사가 없는
  388,405후보는 registry에 보존하되 자동 조인을 금지했다. 등재 후보가 있는
  group에서 legacy fallback 23,192개는 삭제하지 않고 `retained_fallback`으로
  분리했다.
- 두 gzip을 독립적으로 끝까지 읽고 SHA 일치, group ID/표면형+품사 중복 0,
  고아 member 0, candidate 중복 0, 우선순위 오류 0, partial 0을 확인했다.
- 2020 실제 `morph_tokens` 첫 5,000행 pilot은 출력 5,000행과 정확히 일치했다.
  정확 표면형+품사 3,866, 표면형은 있으나 품사 불일치 746, 미등재 표면형 61,
  비표준 표면형 112, 문장부호 215건으로 분리됐다. `여행/NNG`·`수가/NNG`의
  복수 발음은 unresolved, `읽/VV→읽다/VV`의 여러 의미 동일 발음은 같은 그룹으로
  유지된다.
- 기존 MFA 입력사전·DB·TextGrid는 변경하지 않았다. 다음은 2020·2021 전수
  occurrence 1:1 연결과 post-MFA 어절 비교 감사표다.
- 검증 근거:
  `outputs/reports/VERIFY_dictionary_pronunciation_match_index_v1_20260805.json`.

## 2026-08-05 — 2020·2021 occurrence 전수 연결과 연도 공통 참조층 계약

- 2020 생산 표본에서 사전 발음층을 확인하지 못한 원인을 연구자 검토 누락으로
  보지 않았다. 당시 Gate B의 범위는 MFA 계산·동일 발화·6-tier 경계·검색 정보·
  제외 회계였고, 우리말샘 `pron_1/2`를 형태소 품사·의미에 연결하는 occurrence
  계약이 아직 없었다. 2021 `있잖아` 표본이 `phones_mfa`·규칙 예상형·사전 후보를
  구분해 보여줄 필요를 드러냈다.
- 2020 5,767,506행과 2021 12,015,453행의 형태소 occurrence 연결표를 생성했다.
  독립 전수 동시 스캔에서 입력 identity, match state, manifest count/bytes/SHA,
  partial 오류가 두 연도 모두 0이었다.
- 564,385 group을 occurrence 비교에서 반복 해석하지 않도록 compact summary를
  생성했다. group 564,385, member 804,324, preferred 후보 781,132,
  fallback 보존 23,192이며 출력 SHA는 manifest에 동결했다.
- 2020–2025 공통 계약을
  `config/pronunciation_reference_layer_v1.json`에 동결했다. 연도별 예외 코드가
  아니라 같은 registry·좌표·schema·tier 순서·재개 규칙을 사용한다. 기존 MFA
  DB·phone inventory·6-tier·WAV·LAB·원 CSV는 변경하지 않는다.

## 2026-08-05 — 어절 비교 좌표 v1 시행착오와 v2 채택

- 첫 비교 파일럿은 형태소 분석 어절을 행 중심으로 사용했다. `그래가지고`처럼
  원 표기 1어절과 형태소 분석 2어절이 대응하면 규칙 예상형·MFA 어절 연결이
  비어 버릴 수 있음을 실자료에서 발견했다. 파일럿은 비채택 근거로 보존했다.
- v2는 `orth_eojeol_tokens`의 원 표기 어절을 정본 좌표로 사용한다. 규칙/MFA
  비교는 계속 보존하고, 형태소 사전 후보는 명시적 `linked_morph_eojeol_idx`가
  있을 때만 붙인다. 어절 수가 다르면 추측 결합하지 않고
  `morph_coordinate_not_linked`를 기록한다.
- 2020 전수 비교표는 원 표기 어절 3,042,451행이다. 독립 전수 감사에서
  identity·coordinate·structured JSON·규칙/MFA 재계산·manifest SHA·partial
  오류가 0이었다. 차이·경고 수는 후속 연구 후보의 기술 통계이며 오류율이나
  실제 실현 판정률이 아니다.
- 발화 수준 `pron_reference_utterance.csv.gz` 870,437행을 만들었다. 1:N 후보의
  실제 상세는 정규화 CSV에 남기고 TextGrid에는 읽을 수 있는 요약 label만 둔다.

## 2026-08-05 — 7번째 tier 파일럿·중단 재개·정렬 순서 교정

- 기존 6-tier를 읽기 전용으로 두고 `pron_reference_utt`만 추가하는 세션
  checkpoint형 backfill과 독립 감사기를 구현했다. 새 tier는 `utterance`와 같은
  interval 경계를 사용하며 가짜 phone 시간은 만들지 않는다.
- 첫 실자료 실행은 TextGrid를 쓰기 전에 `utt_id` 순서 차이로 안전 중단됐다.
  6-tier alignment 표는 문자열 순서(`1,10,100,...,11`)이고 발화 index는 수치
  순서(`1,2,...,10,11`)이며 index에는 MFA 제외 발화도 포함됐다. 이를 연도 전체
  정렬 재생성으로 해결하지 않고, 세션 단위 dictionary join으로 바꿔 발화 내부
  순서 가정을 제거했다.
- 재시작 시험에서 `--max-sessions 1`이 완료 세션을 건너뛴 뒤 다음 1세션을 더
  만드는 의미였음을 발견했다. 원본 손상은 없고 파일럿 파생본만 2세션으로
  늘었다. 옵션을 “연도 첫 N세션”의 안정된 범위로 교정해 재실행 때 파일럿이
  확장되지 않게 했다.
- 실제 2020 2세션 914개를 독립 전수 감사했다. 기존 6-tier semantic 변경 0,
  7번째 tier 순서·연속성·`utterance` 경계·label 오류 0, partial 0이다. 같은
  실행을 다시 하면 2세션 914개를 checkpoint로 건너뛰고 새 파일을 만들지 않는다.
- 단일 실행기 `scripts/run_pronunciation_reference_year.ps1`은 `Tables/Pilot/Full`
  모드, 연도별 lock, 성공 산출물 재사용, 원 표기 좌표 비교, 세션 재개, 독립
  검증을 결합한다. Windows PowerShell 5.1 safety 48파일과 runtime compatibility
  60스크립트가 통과했다.
- 문서:
  `docs/RUNBOOK_pronunciation_reference_layer_2020_2025.md`,
  `docs/DATA_DICTIONARY_pronunciation_reference_layer.md`.
- 검증 근거:
  `outputs/reports/VERIFY_pron_reference_textgrid_backfill_2020_20260805.json`.

## 2026-08-05 — 2021 발음 참조표 전수 완료와 다음 단계 전 정리

- 단일 연도 실행기의 `Tables` 모드로 기존 2021 occurrence checkpoint를
  재사용하고, 원 표기 어절 비교표 v2 6,610,698행과 발화 index 1,373,920행을
  생성했다. 비교표 741,493,171바이트의 SHA-256은
  `6232142f1caf53f705891e6aecb4e116dde837e230fa5d07103b1fc44c710f1e`,
  index 96,551,706바이트의 SHA-256은
  `6b14ae02840f38c306f3c1ed634b002ee5e096543a80f0eff250eade989a52f3`다.
- 독립 전수 검증은 6,610,698행을 입력 원 표기 좌표와 함께 다시 읽어 identity,
  structured morphology, 규칙/MFA 비교 재계산, manifest SHA, partial을 검사했다.
  오류와 partial은 0이었다. `audit_status`와 `issue_codes` 수는 실제 발음 오류율이
  아니라 후속 필터·연구자 검토를 위한 기술적 표지다.
- 채택되지 않은 registry v1과 좌표 설계 중 폐기된 1,000발화 비교 파일럿 2종,
  총 6파일·84,513,545바이트를 E: 읽기 전용 archive로 압축했다. SHA 목록과
  7-Zip 검사를 통과한 뒤 정확한 세 구경로만 D:에서 제거했다. 채택 v2,
  2020·2021 전수표, 기존 MFA·6-tier는 변경하지 않았다.
- 같은 코드·계약의 2020 7-tier 구현 파일럿이 통과했으므로 2021에서 또 파일럿을
  반복하지 않는다. 다음 허용 단계는 2021 세션 checkpoint형 전수 backfill과
  독립 검증이며, 그 뒤 연구자 Gate 전에는 2022 MFA로 넘어가지 않는다.
- archive 근거:
  `outputs/reports/ARCHIVE_pronunciation_reference_pre_adoption_20260805.json`.

## 2026-08-05~06 — 2021 7-tier 전수 완료·시작 오류 재현·문서 refresh

- 사용자 PowerShell의 첫 `-Mode Full` 시도는 lock·출력·partial을 하나도 만들지
  않고 시작 전에 종료됐다. 화면 오류를 복사하기 어려워 같은 동결 입력으로 첫
  세션 416개를 프로젝트 임시 root에서 직접 재현했다. 기존 6-tier 변경 0,
  7번째 tier 경계·label 오류 0으로 416/416 통과했다.
- 로그를 남기는 숨김 PowerShell로 16:52 KST에 전수를 시작했다. 세션
  checkpoint는 4,139개까지 증가했고 19:54 KST에 backfill이 끝났다. 이어진 독립
  감사는 2026-08-05 21:20 KST에 1,371,883/1,371,883 TextGrid와 동반표를
  검증해 `passed`, 오류 0으로 끝났다. MFA DB·WAV·LAB·원 CSV·기존 6-tier는
  변경하지 않았다.
- 정본 근거는
  `outputs/reports/VERIFY_pron_reference_textgrid_backfill_2021_20260805.json`이다.
  재현용 416개 TextGrid를 포함한 임시 419파일·3,598,599바이트는 정본 완료 뒤
  제거했고, 작은 독립 감사 보고서만 개발 archive에 보존했다.
- 실물은 완료됐으나 452행 현재 상태 문서와 383행 생산 RUNBOOK이 2021 export
  전 상태를 현재처럼 계속 포함하고 있었다. 두 원문을
  `docs/archive/pre_2022_refresh_20260806`에 보존하고, 2020 동결·2021 완료·
  2021 공식 Gate 기록 대기·2022 미시작만 담은 짧은 정본으로 교체했다.
- 공식 2021 연구자 검토 CSV 24행은 여전히 모두 `pending`이다. 대화에서는
  20개가 정상이라고 확인했지만 행 identity가 기록되지 않았으므로 자동 승인하지
  않는다. 다음 단계는 기존 확인 증거를 대조하고 실제 남은 행만 확인하는 것이다.

## 2026-08-06 — 2021 24/24 명시 승인·수동 CSV 절차 제거·2022 Gate 통과

- 연구자가 기존에 확인한 표본은 번호 1–20번이라고 명시했다. 이어 21번의
  `아`를 포함해 21–24번도 WAV·LAB·TextGrid 연결, 6-tier, 정렬, 검색 정보가
  대체로 적절하다고 확인했다. 총 24/24를 승인했으며 실제 음운 실현 판정은
  수행하지 않았다.
- 기존 공식 CSV는 24행 모두 `pending`이고 Dropbox 사본에도 별도 결정 파일이
  없었다. 스프레드시트 전용 runtime도 경로 오류로 두 번 시작하지 못했다. 이를
  또 다른 수동 편집 지시로 우회하지 않고 연도별 승인 절차 자체를 수정했다.
- 새 `approve-explicit` 경로는 승인자·명시 승인 문장·정확 행 수를 필수로 받고,
  manifest의 identity/path와 원 CSV SHA를 확인한다. 원 pending CSV를 바이트
  동일 보존한 뒤 승인 CSV·명시 결정 JSON·승인 JSON을 원자적으로 생성한다.
  기계는 승인 여부를 추론하지 않으며
  `automatic_approval_performed=false`를 유지한다.
- 2021 적용 결과는 24행·24세션·24화자 승인이다. 같은 명령을 한 번 더 실행해
  승인 CSV와 원 pending archive SHA가 모두 그대로임을 확인했다.
- 첫 `2021 → 2022` Gate는 16개 핵심 검사 중 다른 14개는 통과했으나,
  `direct_db_research_6tier_v1_checkpoint_resume`를 구 단일 mode만 허용한 검사와
  옛 input contract의 export-pending status만 본 검사에서 실패했다. 이는 2021
  산출물 오류가 아니라 완료 증거 판독 코드의 시대 불일치였다.
- Gate가 표준 6-tier mode와 checkpoint-resume mode를 호환 실행 방식으로
  인정하고, 같은 input/alignment 계약·보존 DB를 가리키는
  `2021.direct_db_ready`의 `computation_complete=true`를 완료 근거로 읽도록
  수정했다. 원 marker는 사후 수정하지 않았다.
- Python 전체 387시험(명시 승인·재실행·checkpoint Gate 포함)과 Windows PowerShell 5.1
  안전성 48파일·런타임 호환성 60스크립트가 통과했다. 재실행한
  `GATE_2021_TO_2022.json`은 `passed`, 실패 검사 0,
  `allow_next_year=true`다.
- 다음 단계는 2021 재실행이 아니라 2022 `morph_search.v3`·source contract
  생성과 당해 연도 preflight다.

## 2026-08-06 — 2022 전수 MFA 계산 완료·438건 exact-ID 검토 Gate

- 2022 source search 866,359건에서 사전 승인 제외 1,231건을 뺀 활성 LAB
  865,128건으로 동결 계약 MFA를 수행했다. MFA checkpoint는 `success`이며
  864,690발화에 word/phone 정렬 구간이 생성됐다. phone interval은
  26,372,701개, word interval은 7,039,920개, `spn`은 0개다.
- `D:\mfa_tmp\2022\2022.db` 약 8.49GB와 `2022.direct_db_ready`를 보존했다.
  full-year MFA 재실행은 필요하지 않다. direct export는 활성 LAB 중 정렬 구간이
  없는 438건을 발견해 `blocked_exact_id_reconciliation`로 fail-closed 됐다.
  source/LAB/DB/사전 승인 집합의 다른 차이 범주는 모두 0이다.
- Windows PowerShell 5.1 safety 48파일, runtime compatibility 60스크립트와
  사후 검토 wrapper의 읽기 전용 preflight를 통과시킨 뒤 보존 DB에서 후보를
  생성했다. 438건 모두 `mfa_alignment_missing`이며
  `mfa_feature_generation_failed`는 0건이다. 후보는 231세션에 분포하고,
  최다 세션은 `SDRW2200002739`와 `SDRW2200002740` 각 35건이다.
- 검토 root는
  `outputs/reviews/mfa_post_exact_2022_mfa_r2_prod_safe_body_2022_20260806`이다.
  immutable pending 원본·별도 승인 작업본은 각각 438행, 고유 ID도 438개이며
  모든 결정은 `pending`이다. 자동 승인 0, DB 수정 0이다.
- 연구자 표본은 미정렬 후보 16건과 최다 세션 정상 정렬 대조군 4건이다.
  WAV/LAB 각각 20개가 모두 존재하고 빈 LAB은 0이다. 검토 안내를 함께 만들고
  Dropbox root `MFA_2022_POST_EXACT_REVIEW_438_20260806`에 46파일을 복사한 뒤
  원본과 SHA-256을 전수 대조했다.
- 추가 읽기 전용 프로파일에서 후보율은 활성 입력의 0.050628%였다. 438건 모두
  35–497 frame과 비어 있지 않은 정규화 text를 가지며 `ignored=false`,
  word/phone interval은 0이었다. 네 MFA job 모두에 77–168건이 분포했고,
  231세션 중 172세션에는 1건씩만 있었다. 따라서 단일 job 손상·0 frame·빈 text가
  아니라 세션 군집과 산발적 최종 정렬 실패가 함께 있는 집합이다. 근거는 검토
  root의 `05_TECHNICAL_PROFILE.md`와 동일 Dropbox 사본에 보존했다.
- 다음 허용 단계는 20건의 WAV–LAB 대응만 연구자가 확인하는 것이다. 실제 음운
  실현·정렬 품질 판정은 요구하지 않는다. 명시 승인 전에는 438건을 제외 계약에
  결합하거나 export를 재개하지 않는다. 승인 후에도 MFA를 다시 돌리지 않고
  보존 DB에서 direct export·6-tier·동반 CSV·독립 감사를 재개한다.

## 2026-08-07 — 2020–2025 대화 음원 품질 Gate 공통화

- 2022 post-MFA 표본에서 연구자가 관찰한 발화 겹침, 경계 잘림 의심, 심한
  주변소음을 2022만의 예외로 처리하지 않고 2020–2025 공통 품질층으로
  확장했다. 원 WAV·JSON·CSV·MFA DB·TextGrid는 변경하지 않았다.
- 전체 JSON 구조 감사 결과 원자료 겹침 근거는 2021 235,476건, 2022
  128,034건, 2024 13,068건, 2025 16,235건이었다. 2020·2023의 0건은 연도별
  annotation 차이로 해석하며 실제 겹침 부재로 해석하지 않는다.
- 세션별 8개 WAV 층화 표본과 2022 문제 세션 전수 등 총 160,215개 WAV를
  측정했다. 읽기 실패 표본은 2021 3건, 2023 3건이며 나머지 연도는 0건이었다.
  noise proxy 상위 5%는 검토 예산일 뿐 자동 소음 판정이 아니다.
- 2022 `mfa_alignment_missing` 438건과 aligned control 4건의 exact WAV를 모두
  읽었다. 103건에 원자료 겹침 근거, 104건에 경계+활성 edge 검토 신호,
  111건에 상위 noise proxy/연구자 보고 소음 신호가 있었다. 신호들은 중복되며
  자동 승인하지 않았다.
- 정렬 가능한 품질 문제는 데이터 구축을 위해 TextGrid를 남기고 승인 후
  `analysis_only`, 정렬 불가능한 기술 문제만 `alignment_and_analysis`로
  분리하는 원칙을 채택했다. 2020–2022는 재정렬 없이 후향 플래그를 붙이고,
  2023–2025는 정렬 전 감사와 정렬 후 동반표 Gate에 같은 기준을 적용한다.
- 재현 스크립트 4개와 단위시험 11개를 추가했으며, 관련 시험이 통과했다.
  실제 exclusion reason code와 승인 계약은 정확한 후보표 제시 뒤 별도로
  연구자 승인을 받는다.
- `<=44B` 전수 읽기 전용 스캔은 2021 68개, 2023 75개의 정확히 44바이트인
  header-only WAV를 찾았고 다른 연도는 0개였다. 2023의 75개는 모두 기존
  `audio_pairing_unresolved / alignment_and_analysis` 승인에 포함된다. 2021은
  53개가 같은 사전 승인에 포함되고, 나머지 15개는 현재 search master와 LAB에
  없으며 보존 DB에서도 `ignored=true`·interval 0이다. 재정렬·재승인은 하지
  않고 15개는 디스크 inventory로 보존한다.
- 구 불량 WAV 경계가 `<44B`라 정확히 44B를 quarantine 단계에서 놓치던 오류를
  `<=44B`로 교정했다. 더 중요한 안전 교정으로 생산 러너의 원 WAV `--apply`
  이동을 제거했다. 읽기 전용 inventory 중 현재 LAB와 짝을 이루는 ID만 기존
  승인 계약과 대조하고, 불일치 시 원자료 무변경 중단한다. LAB 없는 디스크
  잔존물은 수량을 보존하되 MFA를 과잉 차단하지 않는다.
- 공통 inventory 구분을 exclusion validator, direct DB export, pending 검토표,
  생산 PowerShell에 함께 반영했다. 신규 회귀시험을 포함한 Python 전수 402개,
  PowerShell 안전성 48개 파일, Windows PowerShell 5.1 호환성 60개 스크립트가
  모두 통과했다. `run_eojeol_realign.ps1` UTF-8 BOM도 확인했다.

### 2022 post-MFA 438건 명시 승인과 재개 preflight

- 연구자는 “2022년 post-MFA 미정렬 438건을 `alignment_and_analysis` 범위로
  안전 본체에서 제외하고, 원 WAV·LAB·MFA DB는 후속 회수 대상으로 보존”하는
  것을 승인했다. 승인자는 `ari30`이다.
- 전용 승인기는 `02_RESEARCHER_DECISIONS.csv`와 `SUMMARY.json`의 candidate
  identity·행 수·scope·token을 검증했다. 원 pending 작업본은
  `archive/04_RESEARCHER_APPROVAL.pending_original.csv`에 byte-exact SHA-256
  `da0504e1...`로 보존하고, 작업본 438행의 `decision`만 `approved`로 바꿨다.
- 명시 승인 manifest는 `materialized_from_explicit_researcher_statement=true`,
  `automatic_approval_performed=false`, 원 음원·DB 수정 0, full-year rerun 불필요를
  기록한다.
- `resume_year_export_after_post_mfa_review.ps1 -PreflightOnly`는 기존 pre-MFA
  1,231건 + post-MFA 438건 = 결합 1,669건, candidate SHA
  `36912d5d3802...`를 exact-ID로 확인했다. DB 수정·출력 생성은 0건이다.
- PowerShell 안전성 48개 파일과 Windows PowerShell 5.1 호환성 60개 스크립트도
  다시 통과했다. 다음 단계는 같은 보존 DB에서 direct export를 실제 재개하는
  장시간 PowerShell 한 번이다.
- 긴 승인 문장과 token의 재입력 오류를 막기 위해
  `resume_2022_export_after_exact_approval.ps1`을 추가했다. 기록된 manifest와
  승인 CSV SHA를 검증하며 기본은 preflight, `-Start`를 명시해야 실제 재개한다.
  wrapper 자체 preflight도 결합 1,669건으로 통과했고, PowerShell 안전성 48개와
  Windows PowerShell 5.1 호환성 61개 스크립트가 통과했다. 파일은 UTF-8 BOM이다.

### 2022 보존 DB direct export·독립 전수 감사 완료

- `mfa_r2_prod_safe_body_2022_20260806_postmfa` queue는 2026-08-07 15:22 KST에
  시작했다. 입력·정렬 계약과 8.49GB 보존 DB checkpoint를 재검증한 뒤 MFA를
  다시 계산하지 않고 15:45부터 direct export를 수행했다.
- 17:28 KST에 연구용 6-tier 864,690개와 gzip 동반표 4종을 최종 staging으로
  승격했다. TextGrid coverage 100%, 정확 ID 대사 `passed`, `spn` 0이다. 동반표는
  발화 864,690행, 어절 7,039,920행, phone 26,372,701행, 승인 제외 1,669행이다.
- 독립 전수 감사는 18:00 KST에 끝났다. 중복·누락·추가 TextGrid, invalid tier,
  phone inventory 밖 기호, 동반표 ID·key·manifest 불일치 등 hard failure 20범주가
  모두 0이었다. DB 재수출 24세션 표본은 최종 TextGrid와 semantic·byte 24/24
  일치했다. queue는 `machine_qc_complete_human_review_pending`으로 정상 종료했고
  blocked year는 0이다.
- 공식 연구자 인프라 표본은 24세션·24화자·24발화다. 권위 검토표는
  `outputs/reviews/mfa_production_2022_mfa_r2_prod_safe_body_2022_20260806_postmfa`에
  만들었고, WAV/LAB/TextGrid 72개를 한 평면 SHA 검증 묶음으로 구성했다. Dropbox
  root의 `REVIEW_2022_FINAL_GATE_20260807`에도 76파일·2.3MiB로 복사했다.
- 검토 bundle 안내문의 연도가 2021로 고정되고 `phoneme_auto` 구표기가 남아 있던
  재사용 오류를 manifest 연도와 `phoneme_r_auto`로 교정하고 회귀시험을 추가했다.
  생산 DB·WAV·LAB·TextGrid는 변경하지 않았다. 남은 단계는 자동 승인이 아닌
  연구자 24개 직접 확인과 명시 승인, 이어지는 읽기 전용 완료 Gate다.

## 2026-08-07~08 — 공통발음 r3 Jamo G2P 후보 13 shard 완료

- r2 입력 배선 불일치의 규칙 민감 source 312,410형·4,472,892회를 규칙 목표
  한글형 310,605개로 중복 제거하고 25,000개 이하 13 shard로 계산했다.
- 20:51:40 KST에 시작해 02:42:10 KST에 정상 종료했다. 1시간 간격 점검에서
  2/13, 4/13, 7/13, 9/13, 11/13을 순서대로 확인했고, 오류나 미검증 중단
  산출물 없이 13/13에 도달했다.
- 입력 310,605개와 후보 출력 310,605개가 전수 대응했다. no-path, `spn`, 입력
  밖 key, shard 내부·전체 shard 간 중복, acoustic inventory 밖 phone은 모두
  0이다. 후보 manifest status는 `success_candidates_not_selected`다.
- 완료 뒤 13개 SHA 보고서를 다시 검증했다. 기존 `finalize`는 검증과 동시에
  D: 보고서를 다시 쓰는 경로여서 샌드박스가 차단했고 D: 변경은 없었다. 이를
  계기로 `audit-phase` 읽기 전용 감사를 추가해 원본 무변경으로 phase manifest
  SHA·전역 key coverage·phone inventory를 재검증했다.
- 독립 감사 결과는
  `outputs/reports/AUDIT_common_pron_mfa_r3_g2p_candidates_20260808.json`이며
  `passed_read_only`다. 이 단계에서는 후보를 자동 채택하지 않았고 canonical
  selection·adoption·연도별 MFA·TextGrid materialization으로 넘어가지 않았다.
- 다음 단계는 후보 broad Roman과 독립 규칙 목표 Roman의 exact agreement
  Gate이다. 최종 채택 뒤에는 r3 사전 SHA와 contract ID가 실제 6-tier TextGrid
  및 동반 index까지 전달되어야 하며 r2 phone label의 제자리 치환은 금지한다.

## 2026-08-08 — r3 G2P–규칙 발음 전수 agreement Gate 완료

- 후보 생성 성공과 발음 타당성을 분리하기 위해 310,605개 target의 G2P phone을
  동결 acoustic-model broad-Roman으로 변환하고 독립 규칙 목표 Roman과 단위 순서·
  길이까지 exact 비교했다. 새 산출물은
  `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  04_g2p_rule_agreement_gate`에 원자적으로 생성했다.
- target exact는 96,284개(30.999%), mismatch는 214,321개(69.001%)였다.
  source 312,410형·4,472,892회 기준 exact 출현은 1,676,283회(37.476%),
  mismatch 출현은 2,796,609회(62.524%)였다.
- exact source를 다시 사전 근거로 나눠 사전 일치 3,078형·184,103회, 사전 충돌
  14형·57회, 독립 사전 일치 근거 없음 94,134형·1,492,123회로 보존했다.
  mismatch 215,184형은 자동 선택 불가로 분리했다. exact도 최종 선택하지 않았다.
- 연도별 exact 출현 비율은 2020 37.023%, 2021 38.281%, 2022 37.952%,
  2023 37.166%, 2024 37.684%, 2025 36.347%다. 모든 연도에 같은 target,
  model, Roman mapping, exact 함수와 evidence routing을 적용했다.
- 기존 문제 예시 `놨던`, `어쨌든`, `없는`, `있는`, `있지`를 회귀 표본으로
  고정했다. 앞 세 예시는 exact, `있는`·`있지`는 mismatch로 분류됐다.
- 별도 감사기는 310,605 target과 312,410 source의 변환·편집거리·연도 합계·
  target/source 연결·SHA를 전수 재계산해 `passed_read_only`로 통과했다. 보고서는
  `outputs/reports/AUDIT_common_pron_r3_g2p_agreement_gate_20260808.json`이다.
- 75행 `EVIDENCE_SAMPLE.csv`는 결과 범주 설명용이지 승인표가 아니다. 이 단계에서
  canonical selection, adoption, 연도별 MFA, TextGrid 변경, 실제 실현 판정을
  수행하지 않았다.

## 2026-08-08 — r3 G2P mismatch 전수 진단·반복 패턴 축약 완료

- agreement mismatch target 214,321개와 source 215,184형을 모두 읽어 후보
  broad Roman–규칙 Roman의 unit-cost 순서 보존 편집을 만들고, acoustic-model
  phone 표상·사전·형태소·연도 근거를 결합했다.
- 초기 구현은 장음 표지만 표상 차이로 인식해 `RULE_ONLY:Y/W`를 실질 차이로
  과대분류했다. 실제 phone 분포를 전수 조사해 `/ʲ/`, `/ʷ/` 및 고유 구개
  phone이 인접 활음 단위를 포함할 수 있음을 확인했다. 초기 출력은 삭제하지 않고
  `archive_intermediate\05_g2p_mismatch_diagnostics_initial_20260808_1053`에
  보존한 뒤 분류 계약과 회귀검사를 보강해 최종 출력을 다시 만들었다.
- target 기준 표상 동등성 후보 124,564, 표상 추가 검토 30, model 내부 대조
  5,988, 실질 차이 후보 83,739개다. source 출현 2,796,609회 기준 각각
  1,686,625회(60.310%), 106회(0.004%), 34,667회(1.240%),
  1,075,211회(38.447%)다. 표상 후보도 자동 승인하지 않았다.
- 연도별 표상 후보 비율은 59.397–60.618%, 실질 차이 후보 비율은
  38.059–39.325%로 여섯 연도에 같은 진단 계약을 적용했다.
- 기존 예시 중 `있는`은 `RULE_ONLY:N` 장음/중복 단위 표상 후보,
  `있지`는 `SUB:JJ>D` 실질 차이 후보로 남았다. `놨던`, `어쨌든`, `없는`은
  agreement exact라 mismatch 입력에 들어오지 않음을 회귀검사로 확인했다.
- 2,625개 편집 패턴을 출현 상위·각 class 대표·표상 추가 검토·회귀 사례의
  56행 결정표로 축약했다. 이 표는 불일치 출현 2,590,212회(92.620%)를
  포괄하지만 adoption 승인표가 아니며 모든 행의 자동 승인은 `false`다.
- 첫 독립 감사는 agreement target과 진단 CSV의 행 순서가 같다고 가정해 즉시
  안전 중단됐다. 산출물은 변경되지 않았다. 감사기를 target ID exact join으로
  고친 뒤 편집경로·거리·분류·source link·연도·2,625패턴을 독립 재계산해
  `passed_read_only`로 통과했다.
- 최종 manifest는
  `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  05_g2p_mismatch_diagnostics\G2P_MISMATCH_DIAGNOSTICS_MANIFEST.json`,
  감사 보고서는
  `outputs/reports/AUDIT_common_pron_r3_g2p_mismatch_diagnostics_20260808.json`,
  결과 문서는
  `docs/decisions/RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md`다.
- 이 단계에서 canonical 선택·adoption·MFA·TextGrid·기존 DB 변경은 하지 않았다.
  다음 단계는 model 표상 동등성 및 규칙·사전 projection 정책을 코드 계약으로
  고정하고 자동 해소할 수 없는 소수만 연구자 판단으로 넘기는 것이다.

## 2026-08-08 — r3 model 표상·exact 문맥 projection 후보 완료

- `config/common_pron_r3_model_projection_v1.json`에 후보 생성 전용 계약을
  고정했다. 장음과 `Y/W` 흡수만 좁은 model 단위화 관계로 인정하며 발음
  동등성·실현을 주장하지 않는다.
- 실질 차이는 agreement exact·rewrite 없음 target만 donor로 사용했다. 문맥은
  ±2/±1/해당 단위와 음절·어절 경계를 보존하고, 최소 2 target type 및 phone
  완전 일치를 요구했다. mode·첫 변이·수기 phone·기본사전 fallback은 금지했다.
- 원자적 출력은 `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  06_model_projection_candidates`다. target 후보 가능 264,906개(85.287%)·
  3,744,243회(83.710%), 보류 45,699개·728,649회다.
- source에서 projection과 독립 사전 근거가 함께 일치한 것은 5,948형·349,689회다.
  사전 일치는 근거 routing일 뿐 최종 선택으로 사용하지 않았다.
- `있는`은 장음 단위화 후보로 유지됐고 `있지`는 전수 exact donor가 최소 지지를
  충족하지 않아 보류됐다. 합성 단위시험 결과를 실제 전수 evidence로 오인하지
  않았다.
- 독립 감사기는 target/source 원 입력 불변성, 9,347/810/44 query context,
  exact donor 96,284 target·1,000,388 unit, 798 evidence, phone inventory,
  source 사전 경로와 회귀 예시를 다시 계산해 `passed_read_only`로 통과했다.
- 잔여 1,799패턴은 95.136% 출현과 각 범주 대표를 포괄하는 56행 handoff로
  축약했다. 사용자에게 1,799패턴이나 56행 전체 청취를 요구하지 않는다.
- canonical selection, adoption, 연도별 MFA, 기존 DB·TextGrid 변경은 모두
  수행하지 않았다. 다음 단계는 canonical 선택 우선순위·zero-fallback·사전
  projection·표적 회귀·단일 adoption Gate다.

## 2026-08-08 — r3 881,237형 selection-readiness·국소 복구 완료

- canonical·surface donor·사전·06 projection·r2 phone을 881,237행에서 연결했다.
  candidate 준비 749,779형(85.083%)·25,978,186회(93.289%), 복수 변이 정책
  24형·126회, zero-fallback 보류 131,434형·1,868,756회다.
- candidate 구성은 r2 exact 382,891, no-rule model 단위화 99,660, 의무 규칙
  projection·사전 비충돌 260,508, projection·사전 일치 5,948, surface donor
  346, 사전 지지 r2 예외 426형이다.
- 첫 실행은 projection 열 이름 `original_selection_status`를 잘못 연결해 첫
  행에서 안전 중단됐다. 1KB partial은 `archive_intermediate\
  07_selection_readiness_failed_schema_link_20260808_1207`에 보존했다.
- 수정 실행은 881,237행 gzip을 완성했으나 닫힌 iterator를 다시 읽는 종료검사
  오류로 manifest 직전에 멈췄다. 완성 partial을 버리지 않고 gzip EOF, donor
  원행, 312,410 projection link, JSON 수, phone inventory, 집계를 전수 검증해
  원자 승격했다. manifest에 `recovery.performed=true`와
  `full_recomputation_avoided=true`를 기록하고 종료검사를 수정했다.
- 별도 감사가 model 관계·사전 변이·planning route·회귀 예시를 재계산해
  `passed_read_only`로 통과했다.
- no-rule 보류 85,504형 중 83,922형은 이미 동일 Jamo G2P 1-best 출처다. 같은
  모델을 다시 돌리지 않고 canonical exact-rule 382,891형을 전역 donor로
  확장한 projection v2를 다음 후보 단계로 정했다.
- canonical selection·adoption·MFA·TextGrid 변경은 수행하지 않았다.

## 2026-08-08 — r3 전역 exact donor projection·09 readiness 완료

- 제한 donor 96,284형의 우연한 unanimity를 피하기 위해 canonical exact-rule
  382,891형·382,994 phone 변이를 donor로 사용했다. 기존 310,605 G2P target을
  재사용했고 같은 G2P는 실행하지 않았다.
- 기존 projection과 완전히 같은 target은 286,556형·4,000,557회였다. 전역
  근거에서 후보 13,172형·345,783회를 새로 얻었고, 변이가 드러난 기존 후보
  10,799형·126,339회는 fail-closed 보류로 되돌렸다. 후보 phone 변경은
  78형·213회다.
- `있지`는 전역 exact donor에서 `[iː t̚ tɕ͈ i]` 후보로 회수됐다. `있는`은
  model 단위화, `없는`·`놨던`·`어쨌든`은 기존 exact 근거 경로를 유지했다.
- 첫 실행은 제한 환경의 D: 폴더 쓰기 권한에서 출력 전 안전 중단됐다. 다음
  실행은 Python dictionary 삽입 순서를 CSV 고정 열 순서로 오인한 과도한
  검사에서 첫 행에 중단됐다. 343B·192B partial은
  `archive_intermediate\08_global_projection_failed_field_order_20260808_1301`에
  보존하고, field 집합 검사로 고친 뒤 단위 테스트와 전수 재실행을 수행했다.
- 독립 감사기는 382,891 donor, 310,605 target, 312,410 source, evidence 931행과
  후보 획득·상실·변경을 다시 계산해 `passed_read_only`로 통과했다.
- 감사된 전역 결과를 canonical 881,237형에 다시 연결한 09 readiness는
  candidate 준비 752,270형·26,197,593회, 복수 변이 정책 35형·163회,
  zero-fallback 보류 128,932형·1,649,312회다. 별도 readiness 감사도 통과했다.
- 다음 범위는 기존 target projection 미해결 43,428형과 별도로, 아직 target이
  아닌 no-rule 실질 불일치 85,504형의 candidate-only 계약 설계다. 사전 예외·
  기호·숫자·외래어와 분리하기 전에는 자동 선택하지 않는다.
- canonical selection·adoption·MFA·TextGrid 변경은 수행하지 않았다.

## 2026-08-08 — r3 no-rule 85,504형 전수 특성화·독립 감사 완료

- 09 readiness에서 아직 projection target이 아니었던 no-rule 실질 불일치
  85,504형·1,140,107회를 문자 구성, 사전 근거, r2 발음 출처, 편집 signature로
  전수 분류했다. 출력은
  `D:\mfa_common_pron\staging\common_pron_mfa_r3_20260807\
  10_no_rule_hold_characterization`에 원자적으로 생성했다.
- 85,504형은 모두 완성형 한글 음절로만 이루어졌다. 숫자·기호·라틴 문자·낱자
  자모 문제는 이 집합에 없으므로 별도 정책으로 유지한다.
- 사전 후보 보유는 6,144형, r2 Jamo G2P 출처는 83,922형, Korean MFA 기본사전
  보존 출처는 1,582형이었다. 진단 층위는 실질 차이 75,692형, acoustic-model
  내부 대립 검토 9,828형, 단위화 표상 검토 22형이다.
- 비배타적 family 표지는 비음 조음 위치·경계 54,073형, 분절 수·탈락
  35,703형, 활음·모음 단위화 22,168형, 후두 대립·phone 매핑 13,550형이었다.
  이는 규칙 정답이 아니라 coverage 감사 우선순위다.
- `한번`, `친구가`, `공부를`에서 비음 동화 미표현 가능성, `왜`, `돼`에서
  활음·모음 단위화, `어차피`에서 후두 대립 phone 매핑을 확인했다. 따라서 전체를
  표기 규칙이나 r2 G2P로 일괄 투사하지 않기로 했다.
- 독립 감사기는 전수 행·출현·근거·편집 분류를 다시 계산해 `passed_read_only`로
  통과했다. 요약 보고서와 방법론 결과 문서를 만들었고 후보 생성, canonical
  selection, adoption, MFA, TextGrid 변경은 수행하지 않았다.
- 신규 특성화·요약 단위시험을 포함한 공통발음·발음 참조 회귀시험 168개가
  모두 통과했다.
- 다음 단계는 고빈도 signature부터 표준 발음·우리말샘·형태소 경계·Korean MFA
  acoustic inventory를 대조하는 읽기 전용 규칙/phone 매핑 coverage 감사다.

## 2026-08-08 — r3 의무 규칙·수의 변이·MFA phone coverage 감사

- stage 10의 비음 관련 휴리스틱을 표준발음 규칙 누락으로 오인하지 않도록,
  no-rule 85,504형·85,741변이를 frozen Korean MFA 기본사전·107 acoustic phone과
  읽기 전용으로 전수 대조했다.
- 국립국어원 표준발음법·FAQ 근거에 따라 `친구→칭구`, `한번→함번` 유형의
  위치동화를 수의적 정렬 변이로 분리하고 의무 규칙 엔진에는 추가하지 않았다.
- 주분류 결과는 모든 변이 수의 위치동화 36,568형·525,747회, 일부 변이만 해당
  82형·16,271회, 비중복 frozen 기본사전 정확 일치 811형·229,177회, 미해결
  48,043형·368,912회다.
- frozen 기본사전의 동일 길이 위치 대조에서 107 phone 중 33개가 둘 이상의
  규칙키와 반복 공존했다. `pʲ`가 B 132형·P 137형 등으로 나타나므로 phone에서
  확정 음소를 일대일 복원하지 않는다.
- 첫 실행은 비일대일 phone이 하나라도 든 47,851형을 주분류 해결 범주로 잘못
  사용했다. 결과를
  `archive_intermediate\11_rule_phone_coverage_audit_v1_overbroad_noninjective_20260808`
  로 보존하고, 비일대일성을 경고 표지로만 고쳐 stage 11을 다시 생성했다.
- 수정 stage 11 manifest는 `success_audited_not_candidate`, 별도 감사기는
  `passed_read_only`다. 후보 채택, canonical selection, adoption, MFA, TextGrid,
  원자료 변경은 모두 수행하지 않았다.
- 다음 단계는 검증된 37,379형만 정렬용 candidate-only로 09 readiness에
  추가하는 것이다. 의무 규칙 Roman과 정렬용 phone 역할을 별도 열로 유지한다.

## 2026-08-08 — r3 selection-readiness v2 candidate-only 병합

- stage 09 readiness 881,237형과 stage 11 coverage를 token·variant 순서로
  연결했다. 모든 변이가 수의적 위치동화로만 다른 36,568형과 비중복 frozen
  기본사전 정확 일치 811형, 합계 37,379형·754,924회만 새 계획 후보로 추가했다.
- `한번`의 의무 규칙 참조 `H A n _ B EO n`과 정렬용 phone 후보
  `h ɐ m b ʌ n`을 별도 열로 유지했다. `중에서`의 분절 누락형과 `한국`의 일부
  변이만 위치동화인 경우는 계속 hold로 남겼다.
- candidate 준비 범위는 789,649형·26,952,517회, zero-fallback hold는
  91,553형·894,388회가 됐다. 정책 결정 35형·163회는 그대로다.
- 독립 감사기는 881,237행을 v1과 전수 대조해 새 후보 37,379행의 허용된 planning
  필드 외 변화 0, 비대상·hold 기존 필드 변화 0, 의무 규칙 참조 변화 0을 확인해
  `passed_read_only`로 통과했다.
- candidate-only이며 canonical selection, adoption, MFA, TextGrid, 원자료 변경,
  실제 실현 판정은 수행하지 않았다.
- 다음 단계는 target projection 미해결 43,428형과 no-rule 잔여 48,125형을
  분리한 읽기 전용 반복 패턴 감사다. 같은 G2P를 다시 실행하지 않는다.

## 2026-08-08 — readiness v2 잔여 hold 반복 패턴 우선순위 확정

- zero-fallback 91,553형·894,388회를 target projection 43,428형·509,205회와
  no-rule 잔여 48,125형·385,183회로 분리해 읽기 전용 요약했다.
- target projection 중 42,839형·506,404회는 exact-context donor 불합의,
  589형·2,801회는 deletion 정책 보류다. fortis, liaison, neutralize+fortis,
  aspiration 조합이 출현 대부분을 차지한다.
- no-rule 잔여 상위는 `pʲ/tʲ`의 이차조음·후두 대립, 활음 단위화, ㅢ,
  `중에서`류 분절 누락이다. `B→P`, `D→T` 전역 치환은 비일대일 phone 때문에
  금지한다.
- 다음 단계는 frozen 기본사전의 단어·음절·이차조음 문맥 donor inventory와
  기존 donor 합의·충돌 감사다. 같은 G2P 재실행, 후보 자동 채택, MFA, TextGrid
  변경은 수행하지 않는다.

## 2026-08-08 — r3 문맥 보존 frozen 사전 donor 전수 감사

- `config/common_pron_r3_contextual_dictionary_donor_audit_v1.json`에 단어·음절·
  국소 window·이차조음 문맥 보존, 전역 phone→음소 매핑 금지, 빈도 다수결 금지,
  후보·selection·adoption 금지 계약을 고정했다.
- 동결 Korean MFA 기본사전 17,946표제어·20,978변이를 inventory로 만들었다.
  문맥 mapping이 완전한 18,109변이만 donor index에 사용했고, 분절 누락·삽입 등
  미지원 mapping 2,869변이는 증거표에는 보존하되 donor에서 제외했다.
- readiness v2 zero-fallback 91,553형·894,388회의 91,677변이·172,565 issue를
  기존 canonical exact donor와 대조했다. 결과는 단일 근거 10,594형·162,574회,
  복수 근거 22,171형·225,511회, 출처 충돌 48,780형·377,518회, 근거 없음
  10,008형·128,785회다.
- `최근에`의 `CH W ↔ tɕʷ`, `편하게`의 `P Y ↔ pʲ`는 frozen 사전의 같은
  음절 문맥에서 단일하게 지지됐다. `친구들이`의 `n ↔ ŋ`은 canonical/frozen
  충돌, `중에서`의 빠진 `ng`는 단일 donor가 있어도 phone 삽입 필요, `학교`는
  복수·근거 없음으로 보류했다.
- 장시간 실행 호출의 120초 관찰 제한이 먼저 끝났지만 Python PID가 CPU를 계속
  사용하고 있음을 확인해 중복 재시작하지 않았다. 원자적 partial 폴더가 최종
  `13_contextual_dictionary_donor_audit`로 승격된 뒤에만 완료로 인정했다.
- 독립 감사기는 frozen 사전 variant identity, 91,553형 coverage, 172,565 issue의
  분류와 모든 비채택 flag를 다시 계산해 `passed_read_only`로 통과했다.
- canonical selection, adoption, MFA, TextGrid, r2/2020–2022 보존 자산은 변경하지
  않았다.

## 2026-08-08 — r3 selection-readiness v3 phone 불변 후보 병합

- 단일 근거 10,594형 중 기존 r2 phone·Roman을 바이트 그대로 유지하고, 모든
  issue가 frozen 사전의 onset+glide 이차조음 문맥으로 지지되는 6,141형·90,544회만
  정렬용 candidate-only로 추가하는 정책을 고정했다.
- 첫 Stage 14 실행은 issue가 0개인 특수 hold가 분류표에는 있고 issue 상세표에는
  없는 합법적 구조를 token 집합 불일치로 잡아 출력 전 안전 중단됐다. 이 행을 빈
  근거·계속 hold로 명시하도록 reader를 고치고 회귀 테스트를 추가했다. 기존
  Stage 13·readiness v2·MFA·TextGrid 변경은 없었다.
- 재실행 결과 candidate 준비는 795,790형·27,043,061회, zero-fallback hold는
  85,412형·803,844회가 됐다. planning status는
  `candidate_r2_contextual_secondary_articulation_equivalent`다.
- 독립 감사기는 881,237행을 v2와 전수 비교해 6,141행의
  `r2_pron_phones_json/r2_pron_roman_json`과 새 planning 후보 JSON이 바이트
  동일하고, 나머지 행의 v2 필드 변화가 0임을 확인했다.
- 남은 단일 근거 4,453형·72,030회는 `중에서`류 분절 삽입, `걔`류 glide,
  `저희·너희`류 ㅢ, 후두 대립·종성 교체가 섞여 계속 보류한다. 다음은 이 집합을
  규칙별로 좁게 감사하는 단계이며 사용자 전수 청취나 장시간 MFA 단계가 아니다.

## 2026-08-08 — r3 단일 문맥 근거·phone 변경 필요형 Stage 15 전수 감사

- 사용자에게 다음 작업을 설명한 뒤 턴을 끝내 실제 작업이 이어지지 않았던 문제를
  인정하고, 추가 사용자 명령이나 PowerShell 없이 Stage 15 구현·실행·감사·문서화를
  연속 수행하도록 작업을 재개했다.
- readiness v3에서 `unanimous_contextual_support`, candidate 미적격,
  zero-fallback hold인 4,453형·72,030회를 다시 추출했다. Stage 13 issue 중 현재
  r2 phone이 donor에 지지되지 않는 4,900행을 전수 연결했다.
- issue 편집은 분절 삽입 2,826개, 직접 치환 2,047개, 이차조음 결합 치환
  27개였다. 형별 주 경로는 ㅢ `EU_G` 삽입 964형, `Y/W` 활음 삽입 589형,
  `ng` 삽입 536형, 종성·공명음 삽입 212형, 초성 후두 대립·조음 방법 치환
  919형, 비음·종성 치환 455형, 모음 질·길이 치환 144형, 이차조음 치환 16형,
  혼합 편집 333형과 기타 경로로 분리했다.
- 단일 donor는 기존 phone열 편집의 자동 승인 근거가 아니므로 자동 후보는 0형,
  4,453형 모두 기존 hold로 보존했다. 빈도는 다음 감사 우선순위일 뿐 표준발음·
  실제 실현의 진실값으로 사용하지 않았다.
- 독립 감사기는 readiness v3 목표 집합, Stage 13 미지지 issue, Stage 15 issue·
  token·요약표를 전수 대조하고 분류·회계·비채택 flag를 재계산해
  `passed_read_only`로 통과했다. canonical selection, adoption, MFA, TextGrid,
  r2/2020–2022 보존 산출물 변경은 없었다.
- 표준 pipeline Python으로 `test_*common_pron*.py` 180개를 실행해 모두 통과했다.
  제한 셸에서 AppData Python이 보이지 않은 결과는 설치 부재로 해석하지 않고,
  프로젝트 계약에 따라 MFA 환경 Python의 `unittest`로 동일 범위를 검증했다.

## 2026-08-08 — r3 Stage 16 형태소·문맥 근거 연결

- Stage 15 보류 4,453형·72,030회를 2020–2025 동결 검색 master 17,156개 CSV,
  5,103,356개 발화와 exact 표면 어절 기준으로 전수 연결했다.
- 첫 호출은 장시간 작업에 비해 관찰 timeout을 너무 짧게 주어 산출물 없이
  종료됐다. 두 번째 호출은 Bareun `tagged` group과 `form` 어절이 항상 1:1이라는
  가정을 `그래가지고` 사례에서 잡고 출력 전에 안전 중단됐다. 기존 Stage 13–15,
  MFA, TextGrid, 원자료 변경은 없었다.
- 표면 어절 연결과 형태소 위치 연결을 분리했다. 표면 exact 출현은 68,285회,
  Bareun group 수가 `form` 및 `n_eojeol`과 같아 위치를 안전하게 연결한 출현은
  60,292회다. 비1:1 분석은 억지로 맞추지 않고 형태소 미연결로 보존했다.
- 표면 출현은 3,661형 전부 연결, 306형 일부 연결, 486형 미연결이었다. 형태소는
  2,502형 전부 연결, 839형 일부 연결, 1,112형 미연결이었다. 3,025형은 단일
  signature, 316형은 복수 signature였고 총 signature 행은 3,792개다.
- 사전 참조가 있는 형은 179개, 표면 규칙 참조가 있는 형은 742개였으나 이 정보는
  후보 자동 승인 근거로 사용하지 않았다. 자동 후보 0형, 4,453형 zero-fallback
  hold, canonical selection/adoption/MFA/TextGrid 미변경을 유지했다.
- 독립 감사기는 검색 master 5,103,356행을 다시 순회해 surface와 morphology
  연결을 재계산하고 모든 출력·회계·비채택 flag를 대조해 통과했다. 새 회귀 테스트
  3개도 통과했다.
- 사전·규칙 Roman exact형도 기존 phone의 한 분절만 바꾸면 주변 변이음이 남을 수
  있음을 확인했다. 다음은 이 좁은 집합의 전체 phone열을 문맥 donor로 완전하고
  단일하게 재구성할 수 있는지 감사하는 단계이며, 부분 교정 자동 채택은 금지한다.

## 2026-08-08 — r3 Stage 17 사전 등재 발음 전체 phone열 projection

- Stage 15 보류 4,453형에서 dictionary Roman과 rule Roman이 같은 141형을
  추출했다. 이 중 76형은 우리말샘 등재가 아닌 legacy 기계 `pron_g2p`만 가진
  경우라 사전 근거에서 제외했다. 어휘목록 v2 `pron_1/2` exact는 65형이었다.
- 기존 phone의 문제 분절만 바꾸지 않고 65형의 모든 rule unit을 canonical exact
  donor 382,891형과 동결 MFA 사전 문맥에서 다시 projection했다. 14형·200회는
  모든 unit이 단일하고 출처 간 호환되는 phone을 가졌고, 51형·2,851회는 복수
  phone 또는 출처 충돌로 보류했다.
- 14형은 정렬용 candidate-only 계획이며 canonical 선택·adoption·표준발음·실현
  판정이 아니다. 51형은 연구자 청취 문제가 아니라 model allophone 선택 문제라
  사용자 검토표로 넘기지 않았다.
- 첫 호출은 관찰 timeout으로 manifest 전에 종료됐고, 다음 호출은 CSV 생성 뒤
  `runtime_snapshot`의 프로젝트 root 인수 누락으로 final 승격 전에 안전 중단됐다.
  인수를 명시하고 회귀 테스트를 추가한 뒤 성공·독립 감사를 통과했다. 두 실패
  partial은 `archive_intermediate`에 보존했다.

## 2026-08-08 — r3 selection-readiness v4 병합

- 독립 감사된 Stage 17의 14형·200회만 v3 hold에서 candidate-only로 옮겼다.
  candidate 준비는 795,804형·27,043,261회, zero-fallback hold는
  85,398형·803,644회가 됐다.
- 첫 실행은 기존 별도 정책결정 35형·163회를 candidate/hold 합에 포함하지 않고
  전체 출현 기대치를 적은 회계 오류를 잡아 final 전 안전 중단됐다. Stage 14 정본
  총계 27,847,068을 다시 묶고 회귀 테스트를 추가했다.
- 재실행 뒤 독립 감사기는 v3/v4 881,237행을 전수 비교해 대상 14형의 허용 planning
  필드만 바뀌고 비대상 881,223행 변화 0임을 확인했다. canonical selection,
  adoption, MFA, TextGrid, 2020–2022 완성본은 변경하지 않았다.
- 표준 pipeline Python으로 `test_*common_pron*.py` 190개를 실행해 모두 통과했다.

## 2026-08-08 — r3 Stage 19 pre-adoption 발화 라우팅

- 동결 pre-MFA `pron_reference_form`을 실제 LAB tokenizer로 17,156 CSV,
  5,103,356발화, 27,847,068 LAB 어절 전수 다시 읽었다. 모든 어절이 candidate인
  safe body는 4,384,992발화, hold·policy·빈 LAB가 포함된 follow-up은
  718,364발화였다. unknown은 0이고 부분 어절 삭제·대체는 하지 않았다.
- 연구 검색용 구 `05_search_master/form`을 입력으로 쓴 첫 시도는 어절 총계
  불일치로 final 전에 중단됐다. 두 번째 시도는 `pron_reference_n_eojeol`과 실제
  tokenizer 결과가 같다는 과도한 가정 때문에 기호 제거 사례에서 중단됐다.
  올바른 pre-MFA root와 실제 LAB 어절 수를 계약으로 고친 뒤 성공했다.
- 두 실패 partial은 삭제하지 않고 r3 `archive_intermediate`에 원인별 이름으로
  옮겼다. 독립 감사기는 원 CSV부터 전수 재스캔해 blocked identity, 연도 회계,
  follow-up token 연도별 출현과 safe 누출 0을 확인했다.

## 2026-08-08 — r3 Stage 20 safe-body 후보 사전

- readiness candidate 795,804형·27,043,261회를 796,061변이의 MFA 후보 사전으로
  물질화했다. Korean MFA v3.3.0의 raw acoustic phone 107개를 기준으로 inventory
  밖 phone, lexical `sil`/`spn`, non-candidate 누출이 모두 0임을 독립 감사했다.
- 첫 preflight는 acoustic 특수 심볼 `sil`/`spn`을 어휘 inventory에 더한 109개와
  raw 동결 pin 107개를 비교해 안전 중단됐다. 출력 생성 전에 raw 107-phone
  계약으로 교정했다. 후보는 `NOT_ADOPTED`이며 생산 MFA를 시작하지 않았다.

## 2026-08-08 — r3 Stage 21 표적 회귀와 adoption 정지점

- 기존 2022 문제 표본 08 `있지`, 09 `놨던`, 15 `슬프겠지만`, 24 `없는`만
  별도 corpus에서 정렬했다. candidate phone exact, interval 연속성,
  word–phone 외곽 경계가 4/4 통과했고 `spn`은 0이었다. 기존 r2 TextGrid와 원
  WAV/LAB는 변경하지 않았다.
- 4개 정렬은 약 15분 38초였으며 병목은 79만형 후보 사전 graph compile이었다.
  이후 소수 파일마다 compile을 반복하지 않고 연도·shard로 묶는 근거로 기록했다.
- 연구자 최소 검토용 WAV/LAB/r2/r3 TextGrid를 Dropbox 한 폴더에 모았다.
  자동 adoption 감사는 production MFA·TextGrid 생성을 차단한 채, 네 경계 검토와
  full-coverage/단계적 safe-body 선택만 실제 연구자 결정으로 남겼다.

## 2026-08-09 — 단계적 safe-body 승인과 6개년 신규 r3 정렬 workflow 확정

- 연구자는 Stage 21의 네 표적 회귀 TextGrid 경계를 모두 승인했다. 동시에
  2020–2025 pronunciation-safe 4,384,992발화를 r3 대상 pool로 삼고 정렬 가능
  발화를 동일 r3 기준으로 새로 정렬하며, follow-up 718,364발화를 exact-ID 별도
  shard로 보존하는 방안을 승인했다. 음원·CSV 기술 제외는 별도 축으로 회계한다.
- 최종 r3에 기존 r2 interval·TextGrid를 섞는 선택 재사용 정책을 폐기했다.
  2020–2022 r2 DB·TextGrid는 삭제·수정하지 않고 비교·회귀·시행착오의 읽기 전용
  근거로 보존한다.
- Stage 01–18 canonical/readiness, Stage 19 라우팅, Stage 20 후보 사전,
  Stage 21 표적 회귀와 기존 광범위 사람 검토는 입력 계약이 바뀌지 않는 한 다시
  하지 않는 전역 checkpoint로 고정했다.
- 연도별 작업을 입력 계약, corpus, preflight, MFA DB, exact-ID 회계, 6-tier,
  동반표, 독립 감사, completion manifest로 분리했다. 따라서 TextGrid 경계·tier
  오류는 export만, CSV 열·조인 오류는 동반표만, 일부 미정렬은 exact-ID
  follow-up만 처리하며 연도 전체 자동 clean 재시작을 금지한다.
- 연구자 승인 계약과 정책 일관성 독립 감사기를 추가했다. 감사 결과 정책 모순은
  0건이고, r2 전용 코드 세 곳과 아직 없는 r3 연도 runner를 의도적 구현 gap으로
  기록했다. release Gate는 외부 workflow 리뷰와 구현이 끝날 때까지 닫아 뒀다.
- 이 단계에서는 생산 MFA, D: 원자료, 기존 r2 DB·TextGrid를 변경하지 않았다.

## 2026-08-09 — 외부 리뷰 체크리스트 1: v3.1 staged-adoption 계약

- 외부 리뷰 C2에 따라 전체 881,237형 채택과 795,804 candidate-ready형의 첫
  staged release를 분리했다. 85,398 hold형과 35 policy형은 selected coverage
  분모에서 제외하고 718,364 follow-up 발화에 그대로 보존한다.
- Stage 20 `NOT_ADOPTED` 실물은 후보 증거로 유지하며, 체크리스트 2에서 새
  release의 byte-identical projection과 독립 감사를 통과할 때만 candidate를
  staged selected로 승격하도록 v3.1 계약에 명시했다.
- 외부 리뷰 M3에 따라 기존 `RESEARCHER_APPROVAL.json`의 SHA-256
  `9e5e1a082798...2cb38a90`을 고정했다. 실제 실행 전후 SHA가 동일함을 확인했고,
  입력 내용 SHA 이력은 별도 `RESEARCHER_APPROVAL.provenance.v2.json`에만
  append한다. 동일 입력 재실행에서는 sidecar 바이트도 바뀌지 않았다.
- production Gate, Stage 01–21, D: 원자료와 r2 산출물은 변경하지 않았다.
