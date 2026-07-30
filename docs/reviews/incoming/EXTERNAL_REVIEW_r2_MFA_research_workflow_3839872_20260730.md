# 외부 리뷰 보고서 — r2 MFA 연구 자료 흐름 (읽기 전용)

- **검토 branch**: `agent/harden-pre-bulk-pipelines`
- **검토 HEAD commit SHA**: `3839872ee3c9e3a39c022edaf66690b99d9ca357`
- 검토일: 2026-07-30
- 검토 방식: 저장소 전체 읽기 전용. 코드·데이터 수정 없음, PR 없음.
- 검토 범위: 지정 문서 9종 전부, 지정 실행 경로 10종 전부, 보조 실행 모듈
  (`realign_eojeol_build_corpus.py`, `realign_eojeol_merge_output.py`,
  `merge_textgrid_v2.py`, `verify_mfa_db_4tier_sample.py`,
  `build_common_pron_mfa_adoption.py` 게이트부), `tests/` 47개 파일 목록과
  관련 테스트 내용. D:/E: 실물은 저장소에 없으므로 계약·manifest 처리
  코드를 기준으로 검토했고, 실물 검증 필요 항목은 `requires local
  evidence`로 구분했다.
- 참고: 저장소에 pytest가 설치된 인터프리터가 없어(시스템 Python·bareun
  venv·mfa conda env 모두 `No module named pytest`) 테스트는 실행하지 않고
  정독으로 검증했다.

---

## 1. 14개 질문에 대한 증거 기반 답변

### Q1. 동결 pre-MFA 입력과 최종 연구 검색 CSV의 분리 — **충분히 분리됨**

- 개념: `WORKFLOW_r2_MFA_research_data_contract_20260730.md` §3.2가 "MFA
  입력으로 충분하지만 연구용 최종 CSV는 아니다"를 명시. `PROJECT_CURRENT_STATE.md`
  "중요한 미완료 항목"도 동일.
- 경로: 동결 입력 `D:\10_LAYERS\05_search_master_pre_mfa_staging\pre_mfa_v1_20260725`
  vs 기준선 `D:\10_LAYERS\05_search_master` (`config/paths.json:20-21`).
  wrapper는 staging 경계 밖 출력을 차단한다
  (`scripts/run_pre_mfa_bulk_safe.ps1:146-153`).
- 완료 보고: `build_search_master.py`는 미구현 coverage 열을 빈 값이 아니라
  `"미계산"`으로 채우고(`scripts/python/build_search_master.py:201-204`),
  `--coverage` 옵션 자체를 실행 차단한다(`:582-584`). wrapper 요약의
  `next_action`은 "전수 QC 후에만 정본 승격; 자동 승격 금지"
  (`scripts/run_pre_mfa_bulk_safe.ps1:341-347`).
- 러너는 공통사전 vocabulary contract의 `search_master_root`가 현재 lab
  입력 root와 일치하지 않으면 시작 전에 종료한다
  (`scripts/run_eojeol_realign.ps1:444-455`).

### Q2. form / original_form / 규칙 발음 / 우리말샘 / r2 phone / MFA phone / wav2vec2 / 연구자 판정의 혼동·덮어쓰기 경로 — **덮어쓰기 경로 없음 확인**

- `build_search_master.py`의 `BASE_COLS`(`:79-96`)는 `form`, `original_form`,
  `pron_pred_*`, `pron_reference_*`를 전부 별도 열로 유지. reference 열 채택
  조건과 출처(`pron_reference_source/status`)가 행별 기록된다(`:283-306`).
- lab은 `pron_reference_form`만 사용하고 숫자 추측 없이 한글만 남긴다
  (`scripts/python/realign_eojeol_build_corpus.py:64-71`,
  `LAB_INPUT_VERSION="eojeol_v3_pron_reference_form"` `:47`).
- 운영 TextGrid `utterance` tier는 `form`을 사용하고(`export_mfa_db_4tier.py:72-90,
  173-191`), phones tier는 MFA DB 시간·라벨만 담는다 — 규칙/사전 발음이 tier로
  유입되는 경로 없음.
- 우리말샘 발음·wav2vec2·연구자 판정은 아직 코드 산출물이 없다(문서상
  미구현으로 정확히 선언, §10). 기존 산출물 재생성 시 원본은
  `archive_copy` 후 교체된다(`build_search_master.py:534-538`).
- 잔여 위험은 finding CSV-002(동결 CSV per-file SHA 미고정) 참조.

### Q3. 철자 로마자 + index 기반 환경 검색의 재현 가능성 — **현 시점 기준선은 가능, 최종 계약은 미완(문서와 일치)**

- 어절별 철자 로마자 `form_roman`(어절 구분 `" | "`), 형태소 경계·품사 보존
  `tagged_roman`(4단 위계: 음소 공백·음절 `_`·형태소 `+`·어절 `|`)이 기본
  생성된다(`build_search_master.py:310-332`). 어절 수 = `n_eojeol` 전수 검증
  (`:505-524`, `validate_session_csv:404-431`), form–tagged 불일치는
  `align_warn`으로 표시되어 조용한 오정렬을 막는다.
- 정규화 표(`eojeol_tokens`/`morph_tokens`/`morph_boundaries`)는
  `DESIGN_pronunciation_environment_search_2026-07-25.md` §3에 설계만 있고
  구현이 없다 — 문서 스스로 미구현으로 선언하므로 "문서에만 있는 필수
  출력"이지만 §10 미완료 목록에 정확히 들어 있어 허위 완료 주장은 없다.
- 단, `utt_id + eojeol_index` 조인 규칙의 계약 공백은 finding CSV-001.

### Q4. utt_id/session/speaker/participant/eojeol_index 조인 무결성 — **utt_id·session 축은 강함, eojeol 축은 계약 미비**

- `utt_id` 유일성: bareun 읽기 단계(`build_search_master.py:342-348`),
  세션 JSON(`:164-165`), export의 form 로드(`export_mfa_db_4tier.py:86-88`)
  모두 중복 시 즉시 실패.
- WAV basename↔utt_id: lab은 `{utt_id}.wav`가 실재하는 위치에만
  `{utt_id}.lab`으로 생성(`realign_eojeol_build_corpus.py:390-408`).
  연도별 audit이 lab↔TextGrid ID 전수 대조·중복·누락 CSV를 hard gate로
  강제(`audit_mfa_4tier_year.py:451-533`).
- 화자·대화: `dialogue_speaker_ids`/`co_speaker_ids`는 JSON document 단위로
  구성되고, `speaker_id∈participants`, `speaker_id∉co_speakers`, 수 일치의
  4중 검증이 생성·재검증 양쪽에 있다(`build_search_master.py:264-281,
  379-403`). "직접 상대자 아님" 의미 규정도 문서·코드 주석 일치.
- `eojeol_index`: TextGrid `words` tier의 유표 interval 순서는
  `form_to_lab`이 비한글 어절을 **탈락**시키므로 CSV의 어절 번호와 위치가
  1:1이 아니다 → finding CSV-001 (P2).

### Q5. r2 공통사전의 6개년 강제, inline G2P/구사전 회귀 차단 — **강제됨**

- wrapper: manifest 없는 실행은 기본 차단, `-AllowLegacyInlineG2p`와
  manifest는 상호 배타(`run_pre_mfa_bulk_safe.ps1:71-90`).
- runner: 동일 게이트 반복(`run_eojeol_realign.ps1:33-52`) + r2 manifest의
  schema/status/release_id/`g2p_missing=0`/`g2p_spn_words=0`/
  `phone_outside_acoustic_inventory=0`/adoption v3 `passed`·
  `allow_yearly_mfa`·`legacy_inline_g2p_default=false`를 모두 검사
  (`:371-393`), 사전·G2P·acoustic·base dict·manifest의 SHA256 5중
  fingerprint 대조(`:406-442`).
- 공통사전 모드에서는 `--g2p_model_path`를 mfa align 인자에 넣지 않는다
  (`:1744-1746`, `$useInlineG2p=false` `:459`).
- alignment contract 생성기도 같은 게이트를 독립 반복하고 frozen pin과
  대조(`build_mfa_alignment_contract.py:105-191`). 사전 경로는
  `common_pron_home` 하위로 제한(`run_eojeol_realign.ps1:395-406`).
- adoption 계약 자체는 difference inventory(완료·`allow_yearly_mfa=false`
  상태 요구)·연구자 승인 v2·27건 결정 적용을 SHA로 결합해야만 생성된다
  (`build_common_pron_mfa_adoption.py:817-922`).

### Q6. 2020·2021 전수 재실행 허용 + 구 산출물 오인 방지 — **오인 방지는 fail-closed로 성립하나, 문서가 말하는 "stale archive 격리"와 다르고 첫 실행이 막힐 수 있음**

- 허용: wrapper·runner 모두 `-AllowBaselineCommonPronRerun` 명시 요구
  (`run_pre_mfa_bulk_safe.ps1:101-121`, `run_eojeol_realign.ps1:72-82`).
- temp: 입력·정렬 계약이 다르면 삭제하지 않고 `archive_stale_temp`로 보존
  이동(`run_eojeol_realign.ps1:1640-1662`, `Archive-StaleTemp:1323-1352`).
- done marker: `Read-DoneMarker`가 연도·단계·발음모드·input/alignment
  contract·search root·staging root까지 검사하므로 구 marker가 r2 성공으로
  오인될 경로는 없다(`:1285-1322`). 그러나 불일치 marker는 격리가 아니라
  **exit 1 하드스톱**이다(`:1681-1685`, `:2300-2305`) → finding MFA-002.
- 구 raw 출력만 남은 상태·marker 없는 최종 staging도 각각 실행 차단
  (`:1687-1690`, `:2142-2145`).

### Q7. 4-tier 스키마·0–xmax 연속성·provenance — **스키마·연속성은 이중 강제, provenance는 문서 수준**

- 생성 시: `interval_tier`가 정렬·중첩 검사 후 빈 interval로 0–xmax를
  연속 충전(`merge_textgrid_v2.py:34-65`), `write_4tier`가 임시본을
  `validate_4tier`(순서 `words/phones/morphemes/utterance`, 경계, 핵심 tier
  비어있음)로 검증한 뒤에만 승격(`realign_eojeol_merge_output.py:96-131`).
- 독립 QC: `audit_mfa_4tier_year.py`가 tier 순서(`:35,97-100`),
  좌우 경계·gap/overlap(`:113-146`), WAV header duration 대조(`:176-189`),
  phones의 `spn` interval을 hard failure로 계수(`:147-154, 525`)한다.
- provenance: "phones=의미상 phones_mfa, morphemes=legacy 출처"는 workflow
  §6.2·STANDARD·SCRIPTS_INDEX·stitch 도구(`morphemes_legacy` 명시)에는
  있으나, 연도별 기계가독 산출물(merge marker·direct report)에는 필드가
  없다 → finding MFA-005 (P3). `morpheme_tier()`가 구
  `06_textgrid_merged`의 `words` tier를 복사한다는 사실은 코드에 명시
  (`realign_eojeol_merge_output.py:154-163`).

### Q8. direct DB export의 시간·라벨 보존과 자료 손실 방지 — **보존됨(한정 사항 2건)**

- DB는 read-only URI로만 연다(`export_mfa_db_4tier.py:223-227, 278-282`).
  word/phone interval의 begin/end를 그대로 읽어 `%.6f`로 기록; silence
  라벨(`<eps>/sil/sp/<unk>`)만 빈 라벨로 치환(`:34-35, 140-162`) — 운영
  표준(빈 interval)과 일치.
- 손실 방지: 발화 계정 항등식 `created+validated_existing+alignment_missing+
  form_missing+failed == source_utterances`와 hard failure 0, 99% coverage를
  전부 만족해야 success(`:339-354`). 러너는 여기에 lab 기준 coverage 게이트를
  별도로 겹친다(`run_eojeol_realign.ps1:2160-2177`). 실패 시 DB·partial 보존
  후 중단(`:2156-2159, 2183-2186`). resume 시 기존 파일은 재검증하고 빈
  morphemes를 완비로 오인하지 않도록 재계수한다(`export_mfa_db_4tier.py:119-127`).
- 표본 동등성 도구 `verify_mfa_db_4tier_sample.py`는 결정적 세션 표본을
  DB에서 재생성해 tier·라벨·시간·SHA256을 대조한다(도구 docstring, 2021
  24/24 실적 — SCRIPTS_INDEX:104).
- 한정 1: 표본 검증이 **같은 export 함수**를 재사용하므로 export 함수
  자체의 체계적 변환(예: silence 치환 규칙)은 검출 범위 밖이다. 시간값은
  DB에서 직접 재대조되므로 보존 검증이 성립한다.
- 한정 2: `interval_tier`는 `e=min(e,dur)` 클램프와 1e-6 미만 zero-length
  interval 탈락이 있어(`merge_textgrid_v2.py:39-42`) 이론상 마이크로초
  수준 변형이 가능하나 `validate` 허용오차(0.001s) 안이고 audit이 재검한다.

### Q9. 부분 성공·누락·quarantine·재시도·중단·stale lock·coverage — **거짓 성공 차단 다층 구성 확인**

- lock: PID 생존 검사, 죽은 lock은 archive 이동, bulk↔direct 소유권 상속
  검증, 공통사전 생성과 상호 배제(`run_eojeol_realign.ps1:164-275`).
- 거짓 성공: exit 0인데 TextGrid 0건이면 실패 처리·temp 보존
  (`:2091-2110`, 2021 실사고 반영). 최종 실패에도 temp 보존(`:2122-2131`).
- watchdog: MFA 진행 카운터+단계 인지 기반 교착 감지, "Done!" 후 오살 방지
  (`:1782-2045`), heartbeat JSONL에 CPU 트리·interval CSV 증분·메모리 압력
  기록.
- quarantine: 0바이트 wav 사전 격리(`quarantine_bad_wavs.py` 호출 `:1713-1715`),
  F29형 입력 무결성 게이트(analysis/execution profile,
  `audit_mfa_year_readiness.py` 호출 `:1576-1631`).
- 누락 inventory: audit이 `lab_without_textgrid` 전수 CSV를 남기고
  (`audit_mfa_4tier_year.py:451-486`), 미해결 숫자·기호 발화도 계약별 CSV로
  고정된다(`realign_eojeol_build_corpus.py:157-247, 510-514`).
- 다음 연도 게이트: audit·align/merge marker·direct 보고서·temp 계약·보존
  DB를 동일 input contract로 결합 검증(`preflight_next_year_after_qc.py:110-557`).
  단 이 게이트는 r2 marker를 통과시키지 못한다 → finding MFA-001 (P1).

### Q10. 연도별 QC → D: 정리·archive → 다음 연도 저장 정책과 코드의 일치 — **일치**

- wrapper가 `-Years` 1개만 허용(`run_pre_mfa_bulk_safe.ps1:35-42`), 연도
  실패 시 다음 연도 미진행(`:300-302`), pause 요청 파일은 run_id에 묶인다
  (`run_eojeol_realign.ps1:98-130`).
- `-CleanupDirectDbAfterMerge`는 기본 off이고 direct 모드 기본값은 "QC 전
  DB 보존"(`:2232-2246`); §11 첫 실행 명령에도 cleanup이 없다.
- E: archive·검증·삭제는 별도 스크립트로 존재하며(`archive_pre_jamo_outputs_
  compressed.ps1`, `prune_pre_jamo_outputs_after_compressed_archive.ps1`,
  `tests/test_powershell_safety.ps1` 목록) CRC·DB SHA 검증 실적이
  PROJECT_CURRENT_STATE에 기록되어 있다.
- 사소한 불일치: preflight 메시지 "러너는 C:를 우선"은 현행 D:-우선
  코드와 반대(finding CSV-003).

### Q11. 후보 bundle·KOINA·stitch·wav2vec2·연구자 판정의 층 분리 — **설계·기존 도구는 분리 원칙 준수, 대부분 미구현(문서와 일치)**

- `stitch_session.py`는 온디맨드 클립 전용으로 `phones_mfa/morphemes_legacy`
  를 명시하고 원 clip↔연결 시간 환산 manifest를 만들며 padded 점검본
  입력을 차단한다(SCRIPTS_INDEX:137). canonical 산출물을 수정하는 경로는
  발견하지 못했다.
- KOINA·wav2vec2·`human_judgment` 표는 코드가 없고, workflow §7·§10과
  CURRENT_STATE가 "선택 후보에만 별도 산출물"·"아직 시작하지 않음"으로
  정확히 선언한다.

### Q12. 6개년 동일 기준의 논문용 증거 충분성 — **계약·SHA 증거는 충분, "phone inventory 전수 감사" 주장만 코드와 불일치**

- 남는 증거: 연도별 alignment contract(모델 3종 SHA·MFA/Pynini/Python
  판본·frozen pin·manifest/adoption fingerprint,
  `build_mfa_alignment_contract.py:194-263`), done marker에 contract ID·모델
  SHA 내장(`run_eojeol_realign.ps1:1375-1397`), r2 release manifest·adoption
  v3·연구자 승인 v2·difference inventory의 SHA 사슬
  (`build_common_pron_mfa_adoption.py:877-958`), 실행 transcript·heartbeat.
- `audit_mfa_cross_year_contracts.py`는 6개 계약의 runtime·모델 3종
  SHA·frozen commit·manifest/adoption SHA 동일성을 검사하고 감사 시점에
  실물을 재해시한다(`:34-96`). 그러나 **phone inventory 자체(연도별 DB나
  QC 산출물의 phone 집합)는 어디에서도 비교하지 않는다** — workflow §8
  마지막 단락("phone inventory와 모든 방법 계약 SHA가 동일한지 전수
  감사")과 불일치 → finding MFA-003 (P2).

### Q13. 품질을 낮추지 않는 실제 병목 — **direct export가 이미 최대 항목을 제거, 추가 권고는 소폭**

- 지배 요인은 MFA 자체(코퍼스 로딩 최대 5.5h/연도·정렬 수 시간)와 USB
  SSD I/O이며 SAT 비활성화 등 품질 변화 옵션은 권하지 않는다.
- 이미 반영된 개선: raw 2-tier 이중 I/O 제거(direct DB export), lab 전수
  스캔의 marker 기반 생략(`realign_eojeol_build_corpus.py:286-343`), 세션당
  scandir 1회(`:74-79`), temp-우선 드라이브 유지로 재계산 방지.
- 남은 소폭 후보(품질 무영향): ① `audit_mfa_4tier_year`의 WAV duration
  전수 대조는 연도당 수십만~백만 파일의 USB 왕복이 크다 — `--workers`
  상향은 N200에서 실익이 제한적이므로, audit을 MFA가 끝난 뒤 D: 유휴
  시간에 단독 실행(경합 금지 정책과 일치)하는 운영이 최선. ② 러너의
  lab 수 계수(EnumerateFiles)가 align 게이트와 direct 게이트에서 두 번
  일어난다 — 캐시 가능하나 이득 수 분 수준. 구조적 병목 finding 없음.

### Q14. 문서의 "구현됨 vs 필수-미구현" 구분 정확성 — **대체로 정확, 2건 예외**

- workflow §10·CURRENT_STATE "중요한 미완료"·DESIGN §8.0의 "CSV 전량 생성
  완료 ≠ 연구용 최종 CSV 완료" 구분은 코드 실물과 일치한다(coverage 열
  `미계산`, `--coverage` 차단, post-MFA 레이어 부재).
- 예외 1: workflow §5 "구 marker…stale archive로 격리"는 marker에 대해
  구현되어 있지 않다(하드스톱만 존재) — MFA-002.
- 예외 2: workflow §8 "cross-year 감사가 phone inventory를 전수 감사"는
  현 코드 능력을 넘는 서술 — MFA-003.
- 문구 수준: CURRENT_STATE "확정된 r2 방법 기준"의 "…다시 정렬함"은 결정
  선언이지만 완료 서술로 오독될 수 있다(같은 문서 "아직 시작하지 않음"과
  병존). P3 권고만 남긴다.

---

## 2. Findings

### MFA-001 — r2 발음모드 문자열을 QC·게이트 도구들이 거부함 (자동 재개·연도 전환 게이트 전면 불통)

- **Severity**: P1
- **Evidence**:
  - 기록측: `scripts/run_eojeol_realign.ps1:456` (`$pronunciationMode =
    'common_pron_mfa_r2_latest_jamo'`) → `:1390` (`g2p_model =
    $script:pronunciationMode`로 done marker 기록)
  - 거부측 1: `scripts/preflight_eojeol_realign.ps1:253`
    (`$markerData.g2p_model -eq 'korean_mfa'`만 통과)
  - 거부측 2: `scripts/python/preflight_next_year_after_qc.py:214,223`
    (`_nested(align|merge, "g2p_model") == "korean_mfa"` 하드코딩)
  - 테스트도 legacy 값만 사용: `tests/test_preflight_next_year_after_qc.py:46,59`
  - 저장소 전수 grep 결과 `common_pron_mfa_r2_latest_jamo` 문자열은
    기록자(run_eojeol_realign.ps1)와 과거 리뷰 문서에만 존재 — 어떤
    검증기·테스트도 이 값을 승인하지 않음.
- **Violated contract**: workflow §5(연도 상태 기계: QC 통과 후 다음 연도),
  §8(다음 연도 게이트) — r2 실행이 만든 정당한 marker를 게이트가 판독할 수
  있어야 한다는 암묵 전제.
- **Research impact**: ① 2020 r2가 부분 완료된 상태(align_done 존재)에서
  재개하면 러너 내장 preflight `[7]`이 "완료 마커 내용 불일치" FAIL → exit 1
  → **정당한 재개가 불가능**. ② 2020 QC 후 `preflight_next_year_after_qc.py`
  가 `align_marker_identity`/`merge_marker_identity`에서 항상 fail → 2021
  진입 게이트가 영구 실패. 거짓 성공은 아니지만, 수 시간짜리 무인 배치의
  재개 경로가 막히면 사용자가 marker를 수동 편집하는 우회(가장 위험한
  형태의 계약 훼손)를 유발할 수 있다.
- **Minimal fix**: 세 곳에서 허용 발음모드를 상수 집합
  `{'korean_mfa', 'common_pron_mfa_r2_latest_jamo'}` 또는 "현재 실행의
  alignment contract에 기록된 `pronunciation_mode`와 일치"로 교체.
  `preflight_next_year_after_qc.py`는 r2 marker의 기대값을 인자
  (`--expected-pronunciation-mode`)로 받아 하드코딩을 제거하는 쪽이 최소·안전.
- **Rerun scope**: 코드만. 데이터 재실행 불필요.
- **Required test**: `tests/test_preflight_next_year_after_qc.py`에
  `g2p_model='common_pron_mfa_r2_latest_jamo'` marker fixture로 passed가
  되는 케이스 + legacy·미지 문자열 fail 케이스.
  `test_powershell_safety.ps1` 필수 문자열 목록에 r2 모드 승인 로직 추가.

### MFA-002 — 구(legacy) done marker가 남아 있으면 첫 2020 r2 실행이 시작 불가; 문서의 "stale archive 격리"와 코드(하드스톱) 불일치

- **Severity**: P2 (requires local evidence: `D:\mfa_eojeol\done`에 2020/2021
  legacy marker 잔존 여부)
- **Evidence**: `scripts/run_eojeol_realign.ps1:1681-1685` (align marker
  불일치 시 `exit 1`), `:2300-2305` (merge 동일). temp는
  `Archive-StaleTemp`(`:1323-1352`)로 자동 격리되지만 marker에는 대응
  격리 경로가 없음. 문서측:
  `docs/decisions/WORKFLOW_r2_MFA_research_data_contract_20260730.md:131-133`
  ("구 marker나 temp를 성공으로 인정하지 않고 stale archive로 격리한다").
  삭제 보고서(`outputs/reports/PRUNE_pre_jamo_after_compressed_archive_
  20260730.json`, CURRENT_STATE 인용)의 5개 정리 경로에 done marker
  디렉터리는 포함되지 않음.
- **Violated contract**: workflow §5의 stale marker 격리 계약; §11 "외부
  리뷰 GO 후 즉시 2020 시작" 운영 전제.
- **Research impact**: 거짓 성공 없음(fail-closed). 그러나 legacy
  2020.align_done/merge_done이 남아 있으면 §11 명령이 lab 단계 직후
  중단된다. 수동 삭제를 유도하면 "실측 없이 상태 선언 금지" 원칙과 충돌.
- **Minimal fix**: 둘 중 하나. (a) 러너가 불일치 marker를
  `done\archive_stale\<stamp>\`로 보존 이동 후 진행(temp와 동일 패턴), 또는
  (b) 문서를 "marker 불일치는 하드스톱; 시작 전 점검 스크립트로 legacy
  marker를 보존 격리"로 고치고, 리포에 커밋된 점검 스크립트(규칙 10:
  한 줄 명령 지시 금지)를 추가.
- **Rerun scope**: 코드(또는 문서+보조 스크립트)만.
- **Required test**: legacy marker fixture가 있는 상태에서 r2 계약으로
  실행 시 marker가 보존 이동되고 실행이 진행(또는 명시적 안내로 중단)됨을
  검증하는 회귀 테스트.

### MFA-003 — cross-year 감사가 "phone inventory 전수 감사"를 수행하지 않음 (문서 과잉 주장)

- **Severity**: P2
- **Evidence**: `scripts/python/audit_mfa_cross_year_contracts.py:34-54`
  (`_method_key`는 runtime·모델 SHA·frozen commit·manifest/adoption SHA만
  비교), `:83-96`(실물 재해시도 모델 파일 3종뿐). 연도별 DB/QC 산출물의
  phone 집합을 추출·비교하는 코드는 저장소에 없음(`audit_mfa_4tier_year.py`
  는 `spn`만 계수, `:147-154`). 문서측: workflow §8 마지막 단락
  (`…20260730.md:241-243`), DECISION_r2 문서 "phone inventory를 독립 QC"
  (`DECISION_r2_realign_all_six_years_20260729.md:40-42`).
- **Violated contract**: §8 6개년 완료 후 감사 계약; METHODS 문서의
  "110개 inventory 동일 해시" 주장을 산출물 수준에서 입증할 증거 사슬.
- **Research impact**: 방법론적으로 phone 기준은 acoustic model+사전
  SHA로 간접 보증되지만, 논문 주장("동일 phone inventory")을 산출물
  실측으로 뒷받침하는 마지막 고리가 빠진다. 심사자가 "정렬 결과에 실제로
  등장한 phone 집합이 6개년 동일한가"를 물으면 현 산출물로는 답할 수 없다.
- **Minimal fix**: 연도별 QC 시 보존 DB(또는 phone_intervals.csv)에서
  `SELECT DISTINCT phone`을 뽑아 연도별 phone inventory JSON(정렬 목록
  SHA 포함)을 남기고, cross-year 감사에서 6개 집합의 동일성(+acoustic
  inventory 포함 관계)을 비교하는 검사 추가. 또는 문서 §8을 "방법 계약
  SHA 동일성"으로 축소 서술.
- **Rerun scope**: 코드만(각 연도 QC 시점에 자동 축적되므로 재정렬 불필요).
- **Required test**: 합성 DB 2개(동일/상이 phone 집합)로 pass/fail 검증.

### MFA-004 — 다음 연도 게이트에 DB↔4-tier 표본 동등성·연구자 표본 검토 증거가 결합되지 않음

- **Severity**: P2
- **Evidence**: `scripts/python/preflight_next_year_after_qc.py:110-557`의
  검사 목록에 `verify_mfa_db_4tier_sample.py` 보고서와 연구자 표본 검토
  (workflow §8 항목 5·7) 확인이 없음. 도구 자체는 존재·검증됨
  (SCRIPTS_INDEX:104).
- **Violated contract**: workflow §8 "다음 연도로 넘어가기 전에 최소한
  다음을 확인한다" 항목 5(표본 동등성)·7(최소 5명 화자 표본 검토).
- **Research impact**: 게이트가 통과해도 §8의 두 항목은 수동 규율에만
  의존 — 무인·야간 운영에서 누락되기 쉬운 바로 그 유형. direct export
  버그가 있는 경우 표본 동등성 없이 다음 연도로 진행할 수 있다.
- **Minimal fix**: 게이트에 `--sample-equivalence-report`(status=success,
  같은 DB path·같은 input contract)와
  `--researcher-review-report`(승인 플래그) 인자를 추가해 결합 검증.
- **Rerun scope**: 코드만.
- **Required test**: 표본 보고서 부재/실패/다른 DB 경로 fixture에서 게이트
  fail 회귀 테스트.

### CSV-001 — `utt_id + eojeol_index` 조인 계약이 비한글 어절 탈락을 규정하지 않음 (post-MFA 레이어 구현 시 오조인 위험)

- **Severity**: P2 (현재는 미구현 레이어라 잠재적; 구현 착수 전 계약 확정 필요)
- **Evidence**: `docs/decisions/WORKFLOW_r2_MFA_research_data_contract_
  20260730.md:196-198` ("`pron_mfa`는 `words` 경계로 phone을 어절별로 묶어
  …`utt_id + eojeol_index`를 통해 …연결"). 그러나 lab 생성기는 비한글
  전용 어절을 통째로 탈락시키고 혼합 어절에서 비한글 문자를 제거한다
  (`scripts/python/realign_eojeol_build_corpus.py:64-71` `form_to_lab`).
  따라서 `words` tier의 k번째 유표 interval은 CSV의 k번째 어절이 아니라
  "k번째 한글 보유 어절"이다. 설계 문서는 위험을 인지하고 있으나
  (`DESIGN_pronunciation_environment_search_2026-07-25.md` §3.2 "공백
  interval의 물리 인덱스를 어절 번호로 사용하지 않는다") 탈락 어절의
  매핑 규칙 자체는 어느 계약 문서에도 없다.
- **Violated contract**: §6.3 연구 검색 마스터의 MFA 보조 레이어 조인 계약
  (재현 가능한 어절 대응).
- **Research impact**: 구현자가 "유표 words interval 순서 = `n_eojeol`
  순서"로 단순 구현하면 숫자·기호·외국어 어절을 포함한 발화 전체에서
  `pron_mfa`가 한 칸씩 밀린다. 음운 환경 검색(선행 어절 종성 등)이
  체계적으로 오염되는 유형이라 발견이 늦다.
- **Minimal fix**: workflow §6.3에 매핑 규칙을 명문화 — "CSV 어절 i ↔
  words 유표 interval j의 대응은 `form_to_lab(pron_reference_form)` 재계산으로
  얻은 한글 보유 어절 순번으로 정의하고, 비한글 어절의 `pron_mfa` 칸은
  자리표시자로 보존; 생성기는 `유표 interval 수 == 한글 보유 어절 수`를
  발화별 hard gate로 검사". (audit에 이 수 일치 검사를 추가하면 더 강함.)
- **Rerun scope**: 문서+향후 코드. MFA 재실행 불필요. 잘못 구현된 뒤
  발견되면 CSV 보조 레이어 전량 재생성.
- **Required test**: 숫자 어절 포함 발화("1 다음에 뭐야" 류) fixture로
  어절 index 대응 검증.

### CSV-002 — 동결 pre-MFA 입력의 무결성이 per-session CSV 내용 해시로 고정되지 않음

- **Severity**: P3
- **Evidence**: `scripts/python/realign_eojeol_build_corpus.py:84-133`
  (`input_contract`는 `_build_meta.json` SHA + 세션 **수**만 포함; 세션
  CSV 내용 SHA 없음). 러너의 공통사전 검사도 vocabulary contract의
  root **경로** 일치만 확인(`run_eojeol_realign.ps1:444-455`).
- **Violated contract**: workflow §3.2 "전수 일치해야 한다" 목록(LAB 내용과
  `pron_reference_form`의 전수 동등성 자체는 lab 단계가 매 실행 검증하지만,
  CSV가 조용히 바뀌면 lab이 그에 **맞춰** 재작성됨).
- **Research impact**: 동결 CSV가 실수로 편집되면 `rewritten_mismatch`
  급증으로 관측은 되지만(게이트는 아님), 어휘가 공통사전 vocabulary 밖으로
  나가면 OOV→spn으로만 하류에서 검출된다. 침묵 손상 대부분은 spn·audit
  게이트에 걸리므로 실害는 제한적.
- **Minimal fix**: pre-MFA build 시 세션별 SHA 목록(`_session_hashes.json`)
  을 만들고 `input_contract`에 그 목록 파일의 SHA를 포함; 또는 최소한
  러너가 `rewritten_mismatch>0`이면 경고가 아니라 중단하도록.
- **Rerun scope**: 코드만(다음 lab 검증 실행에서 자동 적용).
- **Required test**: 세션 CSV 1행 변조 fixture에서 계약 ID 변화(또는 중단)
  확인.

### CSV-003 — preflight 안내문이 현행 드라이브 정책과 반대

- **Severity**: P3
- **Evidence**: `scripts/preflight_eojeol_realign.ps1:302` ("temp가 C·D
  양쪽에 있음 — 러너는 C:를 우선") vs 러너 `Get-WorkPaths`는 D:(secondary)
  를 먼저 검사(`run_eojeol_realign.ps1:484-488`).
- **Violated contract**: 규칙 9(상태 선언은 실측으로만)의 정신 — 운영자가
  잘못된 안내로 반대 드라이브를 정리할 수 있음.
- **Research impact**: 잘못된 수동 정리 유도 가능성(온전한 resume temp
  삭제 → 수 시간 재계산). 데이터 정확성 영향 없음.
- **Minimal fix**: 메시지를 "러너는 D:를 우선"으로 수정.
- **Rerun scope**: 코드만. / **Required test**: 정적 안전성 테스트의 필수
  문자열 목록 갱신.

### CSV-004 — 상태 정본의 완료형 문장이 미완 작업을 완료로 오독시킬 수 있음

- **Severity**: P3
- **Evidence**: `docs/environment/PROJECT_CURRENT_STATE.md:43` ("2020–2025
  전부를 같은 r2·acoustic·G2P·adoption으로 다시 정렬함") — 같은 문서
  `:97`("아직 시작하지 않음")과 병존.
- **Violated contract**: 규칙 9(실측 기반 상태 선언), METHODS 문서의
  "gate 통과 전 완료 사실로 쓰지 않는다" 원칙.
- **Research impact**: context compaction 후 새 세션이 §43만 읽으면 완료로
  오인할 수 있는 유형(이 프로젝트가 명시적으로 방어하려는 사고 유형).
- **Minimal fix**: "다시 정렬한다(계획)"로 시제 수정.
- **Rerun scope**: 문서만. / **Required test**: 해당 없음.

### MFA-005 — phones/morphemes tier의 provenance가 기계가독 산출물에 없음

- **Severity**: P3
- **Evidence**: direct/merge done marker 세부(`run_eojeol_realign.ps1:
  2187-2231, 2324-2340`)와 direct report(`export_mfa_db_4tier.py:356-391`)
  에 `phones=phones_mfa`, `morph_tier_source=morphemes_legacy` 상당 필드
  부재. 설계 약속: `DESIGN_pronunciation_environment_search_2026-07-25.md`
  §6.1("기존 phones는 manifest에 phones_mfa 의미라고 명시하고 …
  `morph_tier_source=morphemes_legacy`로 기록").
- **Violated contract**: workflow §6.2 provenance 유지 계약(현재는 문서
  레벨에서만 유지).
- **Research impact**: TextGrid만 반출된 downstream(협업자·후속 세션)에서
  `morphemes`를 현행 Bareun 1:1 분절로 오인할 여지 — 과거 실제로 발생한
  오인 유형(설계 문서 §2.5).
- **Minimal fix**: direct report와 merge marker `details`에
  `tier_provenance={"phones":"phones_mfa","morphemes":"morphemes_legacy_
  copy_of_06_textgrid_merged_words"}` 고정 필드 추가.
- **Rerun scope**: 코드만(이미 만든 파일 재작성 불필요; 보고서 필드부터).
- **Required test**: direct report 스키마 검증에 필드 존재 확인 추가.

### MFA-006 — lab 생성기의 기본 search-master root가 동결본이 아닌 기준선 마스터

- **Severity**: P3
- **Evidence**: `scripts/python/realign_eojeol_build_corpus.py:39`
  (`SEARCH_MASTER = P("search_master")` = `D:/10_LAYERS/05_search_master`),
  `:583-586`(`--search-master-root` 기본값). 러너 경유 실행은 항상 동결
  root를 넘기지만, 수동 단독 실행 시 기본값이 기준선 마스터가 되어 wav
  옆의 **공유 lab**을 그 내용으로 재작성할 수 있음(`:449-468`).
- **Violated contract**: §3.2 동결 입력 계약(lab은 동결본과 전수 동등해야).
- **Research impact**: 다음 계약 검증 실행에서 자동 복원되므로(불일치
  재작성) 영구 손상은 아니나, 대량 lab 재작성 낭비와 혼란. MFA 실행
  중이었다면 경합 규칙 위반 상황도 가능.
- **Minimal fix**: `--search-master-root`를 필수 인자로 변경(기본값 제거).
- **Rerun scope**: 코드만. / **Required test**: 인자 생략 시 종료 확인.

### MFA-007 — 층화 파일럿 인프라가 r2 계약 이전 방식으로 고정됨 (리허설 도구로 쓰려면 갱신 필요)

- **Severity**: P2 (6개년 샘플 파일럿을 리허설 단계로 채택하는 경우; 파일럿을
  쓰지 않으면 P3)
- **Evidence**:
  - inline G2P 하드코딩: `scripts/run_stratified_mfa_pilot.ps1:267,299`
    (`'--g2p_model_path', 'korean_mfa'`) — r2가 금지한 연도별 inline G2P 경로
  - 기본 사전 직접 참조: `:163-164`
    (`Documents\MFA\pretrained_models\dictionary\korean_mfa.dict`) — r2
    release 사전(`common_pron_mfa_r2.dict`) 아님
  - lab 원천이 `form`: `scripts/python/build_stratified_mfa_pilot.py:248`
    (`form_to_lab(row.get("form", ""))`) — 생산 lab 계약
    `eojeol_v3_pron_reference_form`(pron_reference_form 우선)과 입력층부터
    다름
  - marker 모드 문자열도 legacy 고정: `run_stratified_mfa_pilot.ps1:83,96`
    (`g2p_model = 'korean_mfa'`) — MFA-001과 같은 계열
  - 격리 자체는 건전: 파일럿은 wav를 run 폴더로 복사하고 lab을 그 안에
    새로 쓰므로 운영 코퍼스 lab을 건드리지 않음
    (`build_stratified_mfa_pilot.py:562-570`)
- **Violated contract**: workflow §3.3(6개년 생산 실행에서 inline G2P
  불허)·§3.2(lab은 `pron_reference_form` 기준) — 파일럿을 "전수와 같은
  코드·같은 방식"의 리허설로 쓰는 순간 이 계약들과 어긋난 방법을 검증하게
  됨.
- **Research impact**: 파일럿이 green이어도 그것은 구 방법(inline G2P +
  기본 사전 + form 기반 lab)의 green이라, r2 전수 실행의 위험(사전 로딩,
  OOV=0 기대, direct export, r2 marker 판독)을 하나도 미리 밟아 보지
  못한다. 최악의 경우 "파일럿 통과"가 거짓 안심을 만든다.
- **Minimal fix**: 파일럿 러너를 r2로 갱신 — ① 사전·adoption 게이트를
  전수 러너와 동일하게 manifest에서 읽기, ② `--g2p_model_path` 제거,
  ③ lab 원천을 `pron_reference_form`으로 교체, ④ marker 모드 문자열을
  r2 값으로(MFA-001 수정과 같은 묶음), ⑤ 파일럿도 direct DB export 경로
  사용(그래야 export→audit→next-year gate 사슬 리허설이 성립).
- **Rerun scope**: 코드만(파일럿 도구). 기존 60발화 파일럿 산출물은 구
  방법의 시행착오 기록으로 보존.
- **Required test**: 파일럿 러너 정적 검사에 inline G2P 인자 부재·manifest
  게이트 존재 확인 추가(`test_powershell_safety.ps1` 계열).

---

## 3. finding 없이 확인한 경로·불변식

- r2 사전·adoption·approval·difference inventory의 SHA 사슬(§Q5): 게이트
  값 하나라도 어긋나면 wrapper/runner/contract 빌더 3중에서 각각 실패함을
  코드로 확인. inline G2P가 공통사전 모드에 섞일 수 있는 분기 없음.
- lock 수명주기(취득·상속·stale 격리·해제)와 공통사전 작업 상호 배제.
- temp 재사용은 input+alignment contract 동일성 증명 시에만; 불일치 temp는
  삭제가 아닌 보존 이동.
- 거짓 성공 차단(exit 0 + TextGrid 0건), watchdog 오살 방지 3중 예외
  (Done!·G2P 프리루드·카운터 기반), heartbeat의 CPU 누적 역행 보정.
- direct export의 발화 계정 항등식과 이중 coverage 게이트(DB 분모 99% +
  lab 분모 99%), 실패 시 DB/partial 보존.
- 4-tier 스키마·0–xmax 연속성의 생성 시 검증 + 독립 audit 이중화, `spn`
  interval hard failure.
- D: 볼륨 라벨 가드, 평면 wav 구조 가드, 0바이트 wav 격리.
- 검색 마스터의 발화 수·어절 수·화자/대화 참여자 정합성 전수 검증과
  fresh/resume 대칭 검증.

## 4. requires local evidence (저장소만으로 판정 불가)

1. `D:\mfa_eojeol\done`의 2020/2021 legacy `*.align_done`/`*.merge_done`
   / `*.lab_input_done.json` 잔존 여부 (MFA-002의 실제 발현 여부 결정).
2. `pre_mfa_v1_20260725` 실물의 `_build_meta.json` status와 연도별 세션 수.
3. r2 release 실물 4파일의 SHA가 문서 기록값과 일치하는지
   (`release_manifest.json`·`adoption_contract.json`·dict·G2P).
4. `verify_mfa_install.py`가 요구하는 MFA 패치(skip-export·export queue
   등)가 현재 기기 site-packages에 적용되어 있는지 (preflight [1]이 실행
   시 검증하므로 시작 전 preflight 1회로 충분).
5. D: 여유 공간(2020 시작 문턱 45GB) — 7/30 기록상 323GiB로 충분 추정.

## 5. 최종 판정

**GO AFTER FIXES**

P0 없음. 위 P1 1건(MFA-001)과 P2 중 시작 전 필수분(MFA-002 확인)을 반영한
뒤 2020 r2 전수 MFA를 시작할 수 있다. MFA-003·004·CSV-001은 2020 실행과
병행 수정 가능하나, **2021 진입 게이트 실행 전**(MFA-001·004)과 **post-MFA
레이어 구현 착수 전**(CSV-001)이 마감 시한이다.

### 2020 시작 전 필수 체크리스트

- [ ] MFA-001 수정: `preflight_eojeol_realign.ps1`·
  `preflight_next_year_after_qc.py`가 r2 발음모드 marker를 승인하도록 변경
  + 회귀 테스트 추가 (코드만)
- [ ] MFA-002 확인: `D:\mfa_eojeol\done`의 legacy marker 실측 → 잔존 시
  보존 격리(자동화 스크립트 or 러너 수정), ASSETS_LEDGER/작업 이력 기록
- [ ] MFA-007 수정 후 **6개년 층화 샘플 r2 파일럿**을 QC 사슬 끝까지 완주
  → 발견 수정 반영 → 파일럿 재실행 green → 코드 동결(커밋 SHA 기록)
  (§6.1 3번 참조)
- [ ] preflight 1회 실행으로 4번 항목(MFA 패치)·D: 라벨·공간·wav 구조·
  pre-MFA 계약 실측 (`logs/preflight_*.log` 근거 확보)
- [ ] 2020 QC 절차 명문화: `audit_mfa_4tier_year` → `verify_mfa_db_4tier_
  sample` → 연구자 표본 검토 → `preflight_next_year_after_qc`(수정판)의
  실행 순서·인자·보고서 경로를 workflow §8에 1:1로 기입
- [ ] (권장) MFA-003: 연도 QC에 phone inventory 추출 추가 — 2020부터
  축적해야 6개년 감사가 가능하므로 시작 전 반영이 값이 가장 쌈
- [ ] §11 명령 그대로 실행 (cleanup 없음, `-SkipSearchMasterBuild`,
  `-AllowBaselineCommonPronRerun` 포함 확인)

### 가장 위험한 세 가지

1. **게이트 불통에서 출발하는 수동 우회** (MFA-001/002): 재개·연도 전환이
   막힌 상태에서 marker 수동 편집·삭제가 습관화되면 이 프로젝트의 계약
   체계 전체가 무력화된다. 예상 재실행 비용: 지금 고치면 0; 방치 후 marker
   오편집 사고 시 해당 연도 전체 재정렬(연도당 수 시간~하루).
2. **phone inventory 증거 공백** (MFA-003): 6개년 완료 후에 발견하면 보존
   DB가 이미 archive·정리된 연도의 inventory를 복원하기 위해 E: archive
   해제·재검사가 필요. 지금 반영하면 연도당 SELECT 1회.
3. **`pron_mfa` 어절 index 오조인** (CSV-001): post-MFA 레이어를 naive하게
   구현하면 숫자·기호 포함 발화 전반에서 환경 검색이 오염되고, 발견 시
   CSV 보조 레이어 전량 재생성(MFA 재실행은 불필요하나 수 시간~하룻밤 +
   그 위에 이미 수행한 검색·후보 추출 재작업).

### 예상 재실행 비용 요약

| 시나리오 | 범위 |
|---|---|
| 본 보고서 P1·P2 전부 수정 | 코드/문서만 — MFA·CSV 재실행 0 |
| CSV-001을 구현 후 발견 | post-MFA 보조 레이어 전량 재생성 (MFA 무관) |
| MFA-003을 6개년 완료 후 보완 | E: archive 부분 해제 + 연도별 DB 재검사 |
| marker 수동 편집 사고 발생 시 | 해당 연도 r2 재정렬 |

---

## 6. 전체 진행 제안과 조언

아래는 finding을 넘어, 이 저장소의 규칙(파일럿 우선·실측 기반 상태
선언·한 번에 되는 작업 단위)과 저사양 무인 배치 환경을 전제로 한 진행
순서 제안이다.

### 6.1 권장 진행 순서 (2020 시작까지)

연도별 방법 일관성의 가장 큰 실제 위협은 "연도 사이의 코드 수정"이다
(2020 QC에서 버그를 고치면 2021~2025가 2020과 다른 코드로 돌게 됨).
따라서 전수 시작 전에 **6개년 층화 샘플을 같은 코드로 끝까지 한 번
돌리는 단계**(사용자 제안, 3번)를 넣어 수정을 앞당기고, 전수 6개년이
단일 코드 커밋으로 완주할 확률을 높인다. done marker가 `git_commit`을
기록하므로 사후 입증도 가능하다.

1. **코드 수정 1묶음 (반나절 이하, 데이터 무관)**: MFA-001(모드 문자열
   승인) + MFA-007(파일럿 러너 r2 갱신) + CSV-003(안내문) +
   MFA-006(`--search-master-root` 필수화)을 한 커밋 묶음으로.
   이 묶음이 끝나야 "중단돼도 그냥 다시 실행하면 이어진다"는 무인 배치의
   기본 가정이 성립하고, 파일럿이 전수와 같은 방법을 검증하게 된다.
2. **상태 실측 1회 (스크립트, 콘솔 한 줄 실행)**: legacy done marker·
   lab_input marker·temp·staging 잔존물을 읽기 전용으로 훑어 JSON 보고서를
   `logs/`에 남기는 점검 스크립트를 커밋하고 실행(MFA-002 실측 +
   requires-local-evidence 4건 해소). 결과에 따라 marker 보존 격리까지
   같은 스크립트의 `--apply` 단계로 처리 — 수동 삭제 지시 금지 원칙 유지.
3. **★ 6개년 층화 샘플 r2 파일럿 (QC 사슬 끝까지)**: r2로 갱신된 파일럿
   도구(MFA-007 수정판)로 연도당 세션 5~10개(화자=세션이므로 세션 단위
   표집)를 격리 run 폴더에 wav/lab **사본**으로 구성해, 전수와 같은
   경로로 align → direct DB export → `audit_mfa_4tier_year` →
   `verify_mfa_db_4tier_sample` → `preflight_next_year_after_qc`(수정판)
   까지 완주한다. 표본에 문제 유형을 의도적으로 포함: `unresolved_symbol`
   발화, 형태소 원천 결측, 평면 연도(2020·2021·2025)와 세션 연도(2023),
   `발화겹침` note, 숫자·기호 어절. 여기서 나온 수정을 반영한 뒤
   **파일럿을 한 번 더 green으로** 재확인하고 코드를 동결(커밋 SHA 기록).
   한계도 명시해 둔다: 소표본 정렬로 품질·임계값을 판단하지 않으며(MFA는
   코퍼스 단위 통계 추정), 규모 의존 버그(export 전멸·디스크 고갈·수 시간
   hang)는 이 단계가 잡지 못한다 — 그것은 4번(2020 전수)의 몫이다.
   실행 중 D: 경합 금지(규칙 7)는 파일럿에도 동일 적용.
4. **phone inventory 추출기 선반영 (MFA-003)**: 연도 QC에 DB
   `SELECT DISTINCT phone` 1회를 끼워 넣는 작은 스크립트. 2020부터
   축적해야 6개년 감사가 공짜가 된다. (3번 파일럿에서 함께 리허설 가능.)
5. **§11 명령으로 2020 전수 시작 (규모 프로브)**. 시작 직후 첫 heartbeat와
   `PREFLIGHT_mfa_input_integrity_*` 보고서만 확인하고 개입하지 않는다.
   이후 2021~2025는 **코드 무변경 원칙**으로 한 연도씩; 불가피한 변경이
   생기면 그 시점에 "이전 연도 소급 재실행 여부"를 명시적 결정으로
   문서화한다.

### 6.2 2020 완료 후 (게이트 통과까지가 "완료")

- QC 순서를 고정: `audit_mfa_4tier_year` → `verify_mfa_db_4tier_sample`
  → 연구자 표본 검토(≥5화자) → phone inventory 추출 →
  `preflight_next_year_after_qc`. 이 5단계의 명령·인자·보고서 경로를
  workflow §8에 1:1로 기입하고, 가능하면 5단계를 순서대로 부르는 QC
  wrapper `.ps1` 하나로 묶는다(각 단계 보고서가 이미 fail-closed이므로
  wrapper는 순서와 기록만 담당). MFA-004는 이 wrapper로 자연 해소된다.
- 2020은 병목 계측 연도로 쓴다: heartbeat JSONL에서 단계별 소요·words/sec·
  세션 outlier를 뽑아 2021 이후의 예상 시간표를 만든 뒤에 2021을 시작한다
  (§8 항목 8의 실측화).
- E: archive·D: 정리는 **게이트 통과 보고서가 나온 뒤에만**. 정리 전
  phone inventory 추출을 끝냈는지 체크리스트로 강제.
- 6개년 완료 후 cross-year 감사에 **6개 done marker의 `git_commit` 동일성
  검사**를 추가할 것을 권장 — 현재 감사는 모델·계약 SHA만 보므로, "같은
  코드로 6개년을 돌렸다"는 주장의 마지막 고리를 실측으로 닫는다.

### 6.3 병행 트랙 (MFA와 독립, D: 경합 없는 시간대에)

- **CSV-001 계약 확정을 post-MFA 레이어 구현보다 먼저**: 어절 매핑 규칙
  (한글 보유 어절 순번 대응 + 자리표시자 보존 + 발화별 수 일치 gate)을
  workflow §6.3에 명문화하고, 숫자 어절 포함 fixture 테스트를 먼저 커밋한
  뒤 구현한다. 이 순서면 오조인 위험이 설계 단계에서 소멸한다.
- 최종 연구 검색 CSV(형태소별 로마자·우리말샘 보조 발음·coverage 열)는
  6개년 MFA와 독립적인 텍스트 연산이므로, MFA가 도는 동안 **코드와
  파일럿만** 준비하고 전량 생성은 D:가 한가할 때 밤샘 배치로 돌린다
  (경합 금지 규칙 7 준수).
- 문서 정비(MFA-005 provenance 필드, CSV-004 시제, §8 문구)는 각 수정
  커밋에 함께 싣는다 — 문서만 따로 미루면 다시 어긋난다.

### 6.4 일반 조언

- **게이트를 고치는 일에는 항상 "승인 fixture"를 함께 넣을 것**: 이번
  MFA-001은 거부 케이스 테스트는 충실했지만 새 정상 케이스(r2 marker)를
  승인하는 테스트가 없어서 생겼다. 게이트류 코드의 회귀 테스트는
  fail-closed 확인만큼 pass-through 확인이 필요하다.
- **모드·스키마 문자열은 한 곳에서만 정의**: `'korean_mfa'`,
  `'common_pron_mfa_r2_latest_jamo'`, marker stage명 같은 리터럴이 러너·
  preflight·게이트·테스트에 흩어져 있다. 작은 공유 상수 모듈(파이썬)과
  러너 상단 상수로 모으면 이런 계열 결함이 구조적으로 줄어든다.
- **연도당 "완료"의 정의를 보고서 파일로 고정**: "2020 완료"는 콘솔
  문구가 아니라 (audit success + 표본 동등성 success + 연구자 승인 +
  next-year gate passed) 4개 JSON의 존재로 정의하고, 그 4개 경로를
  WORK_HISTORY에 남긴다 — 규칙 9(실측 기반 상태 선언)의 연도판.
- **한 번에 하나의 위험만**: 2020 실행 중에는 post-MFA 레이어 구현이나
  대규모 문서 개편을 시작하지 않는다. 이 저장소의 사고 이력(7/17, 7/20,
  7/23)은 모두 "큰 배치 + 동시 변경" 조합에서 나왔다.

---

*본 보고서는 읽기 전용 검토 결과이며, 수정 여부와 실행 결정은 사용자가
Codex에 전달해 판단한다.*
