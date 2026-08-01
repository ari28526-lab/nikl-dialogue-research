# 외부 설계·코드 리뷰 — 2020–2025 전수 TextGrid·CSV 생산 계약

- 일자: 2026-08-01
- 리뷰 대상 체크아웃: branch `agent/harden-pre-bulk-pipelines`, HEAD `967d1dc`
  (`feat: stage research six-tier production contract`). checkout/pull/reset 없음.
- 리뷰 지시: `docs/reviews/PROMPT_external_review_full_production_TextGrid_CSV_20260801.md`
- 방법: 지정 문서 9종 전량 정독, 지정 코드 11종 + `tests/` 전량 추적,
  로컬 회귀 실물 `work/research_6tier_candidate_60_20260801` 읽기 전용 표본 확인,
  단위시험·정적 검사 재실행. 코드·데이터·D:는 수정하지 않음. MFA/KOINA 미실행.
- 증거 재현 실측 (이 리뷰에서 직접 재실행):
  - Python 단위시험: **263건 전부 통과** (`python -m unittest discover -s tests`,
    32.8s) — `RESULT_research_6tier_candidate_60_20260801.md`의 "263건" 주장과 일치
  - PowerShell 정적 안전 검사: **16파일 PASS** (`tests/test_powershell_safety.ps1`)
  - 회귀 실물: 파일 96개·**669,108 bytes**·TextGrid 60·gzip 18·활성 `.partial` 0 —
    보고서 수치와 바이트 단위 일치. `reports/2025.json`의 사전·acoustic·G2P SHA-256이
    `PROJECT_CURRENT_STATE.md`의 r2 동결 SHA와 일치함을 확인
  - `SARW2500000414.1.1.2` 실물 TextGrid·동반표에서 `2사람이 → 두+사람이`
    좌표 분리(`reference_eojeol_idx` 4=두, 5=사람이) 실측 확인

---

## 1. 최종 판정

## **GO AFTER FIXES**

구현 품질·출처 추적·실패 복구 설계는 5.1M 규모 운영 기준으로 상위 수준이며,
60발화 회귀 증거는 전부 재현된다. 그러나 (i) **연도별 독립 QC·다음 연도 gate
체인이 아직 구 4-tier 계약에 묶여 있어 새 6-tier 실행의 연도 완료를 판정할 수
없고**, (ii) **예상되는 미정렬·자료 사용 불가 발화를 분류·승인할 계약이 없어
exporter가 연도 전체 실패로만 처리**한다. 이 두 가지(H-01, H-02)를 해결하기
전에는 2020 전수를 시작해도 연도를 "완료"로 닫을 방법이 계약상 존재하지 않는다.
BLOCKER(자료를 오염시키는 결함)는 발견하지 못했다.

## 2. 논문 방법론 타당성 요약

**타당하다.** 다음이 코드에서 실제로 강제됨을 확인했다.

1. **자동값과 판정값의 분리가 자료 구조에 새겨져 있다.** MFA phone은
   `phones_mfa`, 기계 로마자는 `phoneme_r_auto`로 이름부터 출처를 드러내며
   (`scripts/python/research_textgrid_v2.py:26-33`), 완료 marker에
   tier별 출처(`tier_provenance`)가 기록된다
   (`scripts/run_eojeol_realign.ps1:2335-2342`). `phoneme_r_auto`는
   `phones_mfa`만의 결정적 매핑이며 철자·사전에서 역복원하지 않는다
   (`scripts/python/phoneme_roman.py:240-259`,
   `export_mfa_db_research_6tier.py:857-858`).
2. **형태소 시간경계를 주장하지 않는 설계가 구현과 일치한다.**
   `morph_analysis_utt`는 발화 전체 span 단일 유표 interval이다
   (`research_textgrid_v2.py:311, 326-331`).
3. **방법 계약이 연도마다 SHA로 재고정된다.** acoustic·사전·G2P 파일 SHA와
   adoption 계약을 교차 검증하고(`run_eojeol_realign.ps1:424-460`), 어긋나면
   `alignment_contract_id`가 달라져 기존 temp·marker를 재사용하지 않는다
   (`run_eojeol_realign.ps1:1487-1489, 1546-1555`).
4. **"실현 판정 아님" 경고가 문서·docstring·manifest 세 곳에 반복된다**
   (`export_mfa_db_research_6tier.py:15`, `inspect_mfa_db_checkpoint.py:1-6`,
   PROPOSAL §1–2).

따라서 §7의 방법론 서술 골격("자동 강제정렬 보조값 … 실제 실현은 연구자가
별도 판정")은 현재 코드 동작을 정확히 기술하며 과장이 아니다. 남은 방법론
리스크는 §3(provenance)·§8(서술 수정안)에 적었다.

## 3. 자료·tier·표별 provenance 누락/혼동

전반적으로 우수하다. PROPOSAL §2의 출처 표가 코드와 일치함을 확인했다
(frozen search master 열 → 동반표 복사: `export_mfa_db_research_6tier.py:683-739`;
버전 열 `textgrid_schema_version/phoneme_schema_version/roman_system_version`
:736-738; manifest의 좌표 계약 문장 :816-819). 발견한 누락·혼동 위험:

1. **Bareun 엔진 버전 미고정** — `build_search_master.py:60`이 스스로
   `"engine_version": "미고정 — 논문용 버전 문자열 확인 요망"`으로 기록.
   논문 방법론에 형태소 분석기 버전을 쓸 수 없는 상태. (문서가 이미 TODO로
   인정; 전수 전 확정 필요 — 체크리스트 §5-6)
2. **`n_spn`·`align_status`가 실측이 아니라 상수** —
   `export_mfa_db_research_6tier.py:732`(`"n_spn": 0`), `:734`
   (`"align_status": "aligned"`). 현재는 DB 전역 `spn=0` gate(:862-869)와
   미정렬 전체-실패 정책 때문에 참이지만, "측정된 0"이 아니라 "정책상 0"이다.
   H-02의 승인 제외 계약이 들어오는 순간 이 두 열은 실측값이 되어야 한다.
3. **`utterance_orth_r`의 혼합 어절 `∅` 대체** — 실물
   `work/.../2025/SARW2500000414/SARW2500000414.1.1.2.TextGrid:750`에서
   `2사람이` 어절 전체가 `∅`로 표시된다. `form_roman`의 자리표시 규약
   (`build_search_master.py:53`, `predict_pron.py:242` `_is_processable`)에
   따른 것으로, 숫자를 추측하지 않는 원칙과 일치하나 **이 tier에서 표기 로마자
   검색을 하면 혼합 어절의 한글 부분이 통째로 누락**된다. 형태소 표
   (`tagged_roman_v2`)는 `⟨2⟩`+`사람` 로마자를 보존하므로 정본 검색은 CSV라는
   계약과 일치하지만, 이 비대칭을 tier 사용 안내·논문 각주에 명시해야 한다.
4. **회귀 증거가 gitignore 대상** — `.gitignore:54`가 `work/`를 제외하므로
   외부 리뷰의 실물 근거(60발화 출력·reports·checkpoints)가 커밋되지 않은
   휘발성 상태다. 최소한 `reports/`·`checkpoints/` JSON 12개는 커밋하거나
   E: 아카이브로 고정할 것.
5. 동반표의 발화 수준 열 중 `pron_pred_*`/`pron_reference_*`는 출처 열
   (`pron_reference_source/status`)이 함께 복사되어(:707-708) 혼동 없음. 어절
   표 쪽 출처 열(`eojeol_form_source/eojeol_roman_source`,
   `morph_schema.py:499-501`)도 적절.

## 4. 심각도별 발견 사항

BLOCKER 없음. HIGH 2건, MEDIUM 10건, LOW 6건.

### HIGH

**H-01: 연도 QC·다음 연도 gate 체인이 새 6-tier 계약과 배선되지 않음**
- 증거:
  - `scripts/python/preflight_next_year_after_qc.py:8, 239, 249, 620` —
    `direct_db_4tier` export mode **전용**이라고 스스로 선언·검사. 새 러너는
    marker에 `export_mode='direct_db_research_6tier_v1'`을 기록하므로
    (`run_eojeol_realign.ps1:2319`) 이 gate는 새 실행을 통과시킬 수 없다.
  - `scripts/python/audit_mfa_4tier_year.py:35` —
    `EXPECTED_TIERS = ["words", "phones", "morphemes", "utterance"]`
    (파일럿 v1의 legacy 4-tier). 새 6-tier 연도 산출물 감사가 불가능.
  - `scripts/python/verify_mfa_db_4tier_sample.py:22` — 재수출 동등성 기준이
    `export_mfa_db_4tier`(구 코드)에서 import된다.
  - `WORKFLOW_r2_MFA_research_data_contract_20260730.md` §8이 이 세 스크립트를
    연도 gate의 필수 순서로 규정.
- 영향: 2020을 새 계약으로 완주해도 **연도 승인·2021 진입을 판정할 공식 gate가
  없다**. 임시로 사람이 눈으로 넘기면 규칙 9(실측 기반 상태 선언) 위반.
- 재현: `preflight_next_year_after_qc.py`를 새 marker에 대해 실행하면
  `supported_export_mode` 불일치로 실패한다(:239, :249).
- 수정안: (a) `audit_mfa_research_6tier_year.py` 신설 — 6-tier 이름·순서·
  `0–xmax` 연속·`phones_mfa`/`phoneme_r_auto` 경계 동일·발화 3-tier 경계 동일
  (검증 로직은 `research_textgrid_v2.py:336-383` 재사용) + 동반표 3종
  count/SHA/manifest 대조; (b) `verify_mfa_db_research_6tier_sample.py` —
  보존 DB에서 세션 5개 재수출·바이트/의미 동등성(기준 코드를
  `export_mfa_db_research_6tier`로 교체); (c) `preflight_next_year_after_qc.py`에
  `direct_db_research_6tier_v1` 지원 추가 + companion `TABLES_MANIFEST.json`·
  DB checkpoint의 `alignment_contract_id` 동일성 요구.

**H-02: 예상 미정렬·자료 사용 불가 발화의 분류·승인 계약 부재
(exporter는 전체 실패, 승격 gate는 무명 1% 손실 허용)**
- 증거:
  - `export_mfa_db_research_6tier.py:946-954` — `alignment_missing`,
    `search_row_missing`, `failed`, `word_span_fallback`이 하나라도 있으면
    연도 전체 `hard_failure`. 분류·승인 경로 없음.
  - `export_mfa_db_research_6tier.py:1010-1011` — 미정렬 inventory를
    `[:1000]`으로 절단해 보고. 연 85만 발화 규모에서 전수 근거로 불충분.
  - `run_eojeol_realign.ps1:2299-2308` — 승격 gate가 `TextGrid ≥ 99% of lab`
    휴리스틱. lab은 있으나 DB에 아예 들어가지 못한 발화(격리 wav 등)는
    exporter 성공에 잡히지 않고, **1% 미만이면 어떤 utt_id가 빠졌는지 대사
    없이 통과**한다.
  - 반면 입력 쪽에는 이미 분류 인프라가 있다:
    `audit_mfa_year_readiness.py:579-596`
    (`exclude_source_audio_unusable`/`manual_review_unclassified` 분류),
    `quarantine_bad_wavs.py`(러너 :1750-1752에서 호출).
- 영향: 실전 연도에는 격리 wav·물리 불일치 발화가 반드시 존재한다(입력 감사가
  그 존재를 전제). 현 계약대로면 **정당한 제외 1건 때문에 연도가 영구
  차단**되거나, 반대로 99% gate 아래에서 **무명 손실이 조용히 통과**한다.
  둘 다 "누락 전수 inventory"(WORKFLOW §8-2) 원칙과 충돌.
- 재현: 60발화 회귀에는 미정렬이 0이라 이 경로가 한 번도 실행되지 않았다
  (`reports/2025.json`의 `alignment_missing_inventory: []`).
- 수정안(구체): 리뷰 질문 12에 대한 답 — §9 Q12 참조. 요지:
  (a) 연구자가 승인한 제외 utt_id 목록 파일(사유 코드 포함)을 연도 입력
  계약에 동결; (b) exporter에 `--approved-exclusions`를 추가해 목록 내
  발화만 계약된 스킵으로 처리하고 4번째 산출물
  `excluded_utterances.csv.gz`(상한 없는 전수)로 기록, 목록 밖 결측은 지금처럼
  hard failure; (c) 승격 gate를 99% 휴리스틱에서
  `set(lab) == set(정렬성공) ⊎ set(승인 제외) ⊎ set(격리)` 정확 대사로 교체,
  차집합 0 요구; (d) `n_spn`/`align_status`를 실측값으로 전환(M-01과 연동).

### MEDIUM

**M-01: `n_spn=0`·`align_status="aligned"` 상수 기록** —
`export_mfa_db_research_6tier.py:732, 734`. 현재는 전역 gate(:862-869) 덕에
참이지만 측정값이 아니다. spn 정책이 "차단"에서 "격리"로 바뀌는 순간 침묵
오기록이 된다. per-utterance 실측 count로 교체하고, H-02 채택 시
`align_status`에 `aligned/excluded_approved` 등 실제 상태를 기록할 것.

**M-02: 동반표 `textgrid_relative_path`가 Windows 백슬래시** —
`export_mfa_db_research_6tier.py:714-716`(`str(Path(...))`), 시험이 백슬래시를
고정함(`tests/test_export_mfa_db_research_6tier.py:206`). KOINA를 Colab/Linux로
보내는 계획(PROPOSAL_Seoul §9.4)과 DuckDB 경로 조인에서 이식성 결함.
`Path.as_posix()`로 통일하고 시험도 갱신할 것.

**M-03: gzip CSV의 dtype·인코딩 계약 미동결** — gzip 내부가 `utf-8-sig`
(`export_mfa_db_research_6tier.py:414`), 부울이 Python `True/False` 문자열,
결측이 빈 문자열(예: 무음 word의 `mfa_word_idx=""` :547). 현행 도구(pandas·
DuckDB)는 소화하지만, **Parquet 미러 재생성 계약**(PROPOSAL §4)에 열별 dtype·
부울 표현·결측 규약·BOM 처리를 명시적으로 동결하지 않으면 미러마다 스키마가
흔들린다. 열 목록은 이미 코드에 고정되어 있으므로(:78-166) 이를 기계가독
schema 파일(JSON)로 내려 Parquet 빌더와 공유할 것.

**M-04: `direct_db_ready` 재사용 경로가 DB를 재검증하지 않음** —
재사용 시 `Test-Path`만 확인(`run_eojeol_realign.ps1:2181-2185`), marker는
파일 내용 fingerprint를 검증하지 않고, checkpoint 자체도 coverage 100%를
요구하지 않는다(`inspect_mfa_db_checkpoint.py:95-100` — quick_check·행수>0만).
marker 생성이 MFA exit 0 이후로 제한되므로(:2144-2148 → :2189 순서) 실위험은
"marker 생성 후 DB가 외부 요인으로 변한 경우"에 한정되나, 재사용 시
`inspect_mfa_db_checkpoint.py`를 다시 실행해(1분 미만) marker의 counts
(:2214-2221에 저장됨)와 대조하는 한 줄 gate로 닫을 수 있다.

**M-05: lab 완료 marker 재사용이 세션 CSV 내용을 재검증하지 않음** —
`realign_eojeol_build_corpus.py:111-165`의 input contract는 `_build_meta.json`
SHA와 세션 **수**만 포함하고 세션 CSV별 내용 SHA가 없다. marker가 같으면 전수
재검사를 건너뛴다(:317-375). frozen root 불변이 전제이므로 실제 위험은 낮지만,
전수 실행 직전 1회는 `--force-verify`(:621-624)로 전수 내용 검증을 도는 것을
운영 절차에 명시할 것.

**M-06: 동반표 생성이 연도 단일 패스·재개 불가** —
`export_mfa_db_research_6tier.py:504-770`이 세션 수천 개를 단일 연결로 직렬
처리하며 중간 체크포인트가 없다. 마지막 세션에서 실패해도 3표 전체를 처음부터
다시 쓴다(.partial 보존·아카이브는 됨 :423-443). TextGrid 패스는
`validated_existing`(:362-377)으로 재개 가능하지만 동반표는 아니다. 또한 세션
CSV를 TextGrid 패스(:326)와 동반표 패스(:507)에서 **두 번** 읽는다. N200+USB
환경에서 연도 wall-clock을 Q14 벤치마크로 실측하고, 필요시 세션 단위 재개
checkpoint를 추가할 것(수용 가능하면 실측치만 문서화해도 됨).

**M-07: `_materialize_intervals`의 침묵 클램프** —
`research_textgrid_v2.py:102-104`가 DB interval을 `[0, duration]`으로 자르고
길이 ≤1e-9는 버린다. DB 시간이 duration을 넘는 손상 자료가 오면 TextGrid는
잘린 값, 동반표는 원값(:592-594는 DB begin/end 그대로)을 기록해 **TG–CSV 시간
불일치가 조용히 생길 수 있다**. overlap은 차단하면서(:106-109) 범위 초과는
허용하는 비대칭. `end > duration + ε` 시 예외로 승격 권장.

**M-08: `utterance_orth_r` 혼합 어절 `∅` 검색 누락** — §3-3 참조. 코드 수정이
아니라 계약 문서·검토 안내·논문 각주 항목. (형태소 표가 정본이라는 §6 계약과
일치하므로 MEDIUM-문서)

**M-09: silence 집합의 이중 기준** — `research_textgrid_v2.py:35`의 `SILENCE`는
`spn`을 포함해 `phoneme_r_auto`에서 spn을 빈칸 처리하지만, exporter의
`SILENCE_PHONES`(`export_mfa_db_research_6tier.py:64`)는 spn을 포함하지 않는다.
현재는 전역 spn gate로 도달 불가능한 경로지만, spn 정책 변경 시
`phones_mfa`에는 spn이 남고 `phoneme_r_auto`만 침묵으로 표시되는 불일치가
잠복해 있다. 한 모듈의 단일 상수로 통일하고 "spn은 매핑 대상이 아니라 차단
대상"임을 주석으로 고정할 것.

**M-10: gzip 산출물의 바이트 재현성 없음** — `gzip.open(..., "wt")`(:413-415)는
헤더에 현재 시각 mtime을 기록하므로 같은 입력을 재수출해도 SHA-256이 달라진다.
manifest의 SHA(:826-828)로 "그때 그 파일"은 증명되지만 "재생성 동일성"은 증명할
수 없다. `gzip.GzipFile(..., mtime=0)`로 결정적 출력으로 바꾸면 연도 재수출
동등성 검증(H-01의 sample verify)이 SHA 비교로 단순해진다.

### LOW

**L-01: 회귀 증거 휘발성** — §3-4와 동일. `work/`가 `.gitignore:54`로 제외.
**L-02: gzip partial에 fsync 없음** — `_atomic_gzip_writer`(:410-420)는
`staged_text_writer`(`pipeline_common.py:70-71`)와 달리 fsync 없이 승격.
OS 크래시 시 승격된 파일이 불완전할 이론적 여지. fsync 추가 권장.
**L-03: `phoneme_r_auto` 대소문자 의미 구분** — 미파열 종성 소문자
(`phoneme_roman.py:160-167`: `k/p/t` vs 격음 `K/P/T`), 탄설음 `R` vs 설측
`l`(:203). Praat 검색은 대소문자 구분 설정이 필요함을 검토 안내에 명시할 것.
**L-04: label 제어문자 방어 없음** — `_escape`(`research_textgrid_v2.py:41-42`)는
따옴표만 이스케이프. 개행이 섞인 label은 검증 단계에서 실패하므로 안전하게
죽지만(파서 `retrofit_textgrid_2020_2024.py:40-52` round-trip), 명시적 사전
가드가 오류 메시지를 명확하게 만든다.
**L-05: preflight [7]이 "final staging 존재 + marker 전무" 미분류** —
`preflight_eojeol_realign.ps1:315-339`는 align marker가 있는 경우만 direct
시나리오를 분류. 승격(Move-Item :2309-2310)과 marker 기록(:2315) 사이 크래시는
러너의 :2240-2242에서 명시적으로 중단되므로 데이터는 안전하나, preflight가
미리 알려주면 복구가 빠르다.
**L-06: `build_morph_position_tables.py`의 전량 메모리 유일성 검사** —
`seen_ids` set(:160, :179-189)이 입력 전 발화를 메모리에 유지. 연도 단위(85만)
는 8GB에서 안전하지만 5.1M 일괄 실행은 금지 계약을 명시할 것(현 사용처는
파일럿 한정이라 LOW).

## 5. 전수 실행 전 필수 수정 체크리스트

전부 완료 후에만 2020 명령을 작성한다 (권장 순서):

1. [ ] **H-02** 승인 제외 계약: 제외 목록 파일 형식 확정 → exporter
   `--approved-exclusions` + `excluded_utterances.csv.gz`(상한 없음) → 승격
   gate를 정확 집합 대사로 교체 → 실패 fixture 단위시험 추가
2. [ ] **H-01** 연도 QC 3종을 6-tier 계약으로 배선(audit/verify-sample/
   preflight_next_year) + `alignment_contract_id`·`TABLES_MANIFEST` 동일성 요구
3. [ ] **M-01** `n_spn`·`align_status` 실측화 (H-02와 같은 패치로)
4. [ ] **M-02** `textgrid_relative_path` POSIX화 + 시험 갱신
5. [ ] **M-03** 동반표 스키마(JSON) 동결 + Parquet 미러 빌더가 이를 입력으로
   사용하는 계약 문서화
6. [ ] Bareun `engine_version` 확정 기록 (§3-1; 논문 방법론 전제)
7. [ ] **M-04** `direct_db_ready` 재사용 시 checkpoint 재실행·counts 대조
8. [ ] **M-10** gzip 결정적 출력(mtime=0) — H-01의 재수출 동등성 검증을 SHA
   비교로 만들기 위한 선행
9. [ ] **Q14 벤치마크** (§9 Q14): 합성 대량 DB exporter 벤치 + 저장량 실측 +
   Parquet 왕복 시험. 새 MFA 파일럿은 불필요
10. [ ] 60발화 `reports/`·`checkpoints/` 증거 고정(커밋 또는 E: 아카이브, L-01)

M-05·M-06·M-07·M-09·L-02는 권장 수정이며, 반영하지 못하면 운영 절차 문서에
해당 제약(전수 직전 `--force-verify` 1회, 동반표 재개 불가, 클램프 정책)을
명시하는 것으로 대체 가능하다.

## 6. 실행 후 연도별 gate 체크리스트

연도 1개 완료 → 다음 연도 시작 전에 (H-01 수정본 기준):

1. [ ] MFA exit·watchdog 기록 확인 (`mfa_<year>_stderr.log`, heartbeat JSONL)
2. [ ] `inspect_mfa_db_checkpoint` `status=success` + `missing_alignment_examples`
   전수 분류 (승인 제외 목록과 대조)
3. [ ] exporter report `status=success` + `analysis_ready_status=ready` +
   `coverage_pct` + `excluded_utterances.csv.gz` 사유별 집계
4. [ ] 정확 집합 대사: lab ⊎ 격리 ⊎ 승인 제외 = TextGrid+제외 기록 (차집합 0)
5. [ ] 6-tier 연도 감사(신규 audit): tier 이름·순서·`0–xmax`·경계 동기화·
   phone inventory ⊂ 허용 inventory·실측 `spn=0`
6. [ ] 보존 DB 표본 재수출 동등성(세션 ≥5, 신규 verify) —
   `alignment_contract_id` 동일 확인
7. [ ] 동반표 3종 count 삼각대조: TextGrid 수 = utterance 행 수,
   word/phone 행 수 = DB interval 수, `TABLES_MANIFEST.json` SHA 재검증
8. [ ] 연구자 표본 검토(화자 ≥5, WAV/TextGrid/CSV 연결·경계 가독성만) →
   `validate_mfa_r2_review_workbook` 계열 승인 보고서
9. [ ] `preflight_next_year_after_qc`(6-tier판): 위 보고서들 + 같은
   input/alignment contract 결합 확인 후에만 다음 연도
10. [ ] D: 여유 공간·연도 산출물 크기 기록, E: 아카이브 여부 결정
11. [ ] `PROJECT_CURRENT_STATE.md`·WORK_HISTORY 갱신 (규칙 4·9)

## 7. 연구자 결정 vs 코드 결정

**연구자에게만 받아야 하는 결정** (자동화 금지):

1. 승인 제외 목록의 각 utt_id 사유 승인 (H-02의 (a); 특히
   `manual_review_unclassified` 항목)
2. 6-tier 전수 물리 저장 vs 후보 시 파생 — §9 Q3의 실측치를 근거로 한 최종
   선택 (스토리지·백업 부담의 수용 여부는 연구 운영 판단)
3. 우리말샘/표준국어대사전 1:N 후보 표의 sense 연결 정책과 동형어 처리
   (§9 Q8) — 어휘부 판단
4. `utterance_orth_r`의 `∅` 규약을 유지할지, 혼합 어절의 한글 부분만 로마자화
   하는 v2 규약을 만들지 (검색 요구 대 규약 안정성의 트레이드오프)
5. 연도별 연구자 표본 검토 승인 (WORKFLOW §8-4·8-5)
6. KOINA 후보 선정 쿼리와 `prosody_manual` 판정 일체

**코드로 결정 가능** (연구자 승인 불필요, 시험으로 고정):

1. H-01 QC 스크립트의 6-tier 배선 (기존 검증 로직 재사용)
2. M-02 POSIX 경로, M-03 dtype 스키마 동결, M-10 결정적 gzip
3. M-04 checkpoint 재실행 gate, M-05 `--force-verify` 운영 절차
4. 정확 집합 대사 구현 (승인 목록 자체는 연구자, 대사 계산은 코드)
5. Q14 벤치마크 스크립트와 수치 수집

## 8. 논문 방법 서술 수정안과 미완료 주장

**PROPOSAL §7 골격은 사용 가능**하며, 다음 수정·보강을 권한다.

수정안 (보강 문장):

> 2020–2025 자료에 동일한 Korean MFA acoustic model(v3.3.0, SHA-256 94bd…),
> Jamo G2P(v3.2.0, SHA-256 4df7…), 공통 발음사전(common_pron_mfa_r2, SHA-256
> 24c4…)을 적용하였다. **어절 표기(`form`/`tagged`)와 MFA 입력 표기
> (`pron_reference_form`)의 어절 좌표를 별도 색인으로 유지하여, 숫자 읽기
> 복원 등으로 두 표기의 어절 수가 다른 발화(예: '2사람이'→'두 사람이')에서
> 형태소–phone 연결이 어긋나지 않도록 하였다.** 원 전사·형태소 분석, MFA 입력
> 표기, 사전/G2P phone, MFA 정렬 phone, 자동 Roman 매핑을 별도 출처로
> 보존하였고, **자동 Roman 음소층(`phoneme_r_auto`)은 MFA 정렬 phone만을
> 입력으로 하는 결정적 광전사이며 철자·규칙 발음에서 역복원하지 않았다.**
> MFA phone은 청취 위치를 찾기 위한 자동 강제정렬 보조값으로만 사용했으며,
> 음운 현상의 실제 실현 여부는 선별 발화의 음성과 TextGrid를 연구자가 직접
> 검토하여 별도로 판정하였다. **정렬 불가·원음 사용 불가로 제외된 발화는
> 사유별 전수 목록으로 보고한다.**

**아직 쓰면 안 되는 주장** (현 시점 증거 없음):

1. "2020–2025 전수를 동일 기준으로 정렬 완료" — 전수 MFA 미시작
   (`PROJECT_CURRENT_STATE.md:100`). 60발화 회귀는 재출력 검증일 뿐이다.
2. "형태소 분석기 버전 X" — engine_version 미고정 (§3-1).
3. "누락·제외 발화 전수 목록 보고" — H-02 수정 전에는 거짓 (inventory 1000개
   절단, 99% 휴리스틱).
4. "spn 0%" 를 연도 결과로 일반화 — 각 연도 실측 후에만. 60발화 `spn=0`은
   파일럿 DB의 사실이다.
5. 서울 코퍼스 발음형 tier와의 동등성 — PROPOSAL_Seoul §2·§7이 이미 금지한
   대로, `phoneme_r_auto`를 "발음형 전사"로 부르지 말 것.
6. KOINA·wav2vec2·연결 발화 관련 일체 (미실행).

## 9. 리뷰 질문 14개에 대한 답

**Q1. 출처 계층이 schema·값·provenance에서 드러나는가?** — **예.**
tier 이름(`research_textgrid_v2.py:26-33`), marker `tier_provenance`
(`run_eojeol_realign.ps1:2335-2342, 2367-2374`), 동반표 버전·계약 열
(`export_mfa_db_research_6tier.py:120-125, 736-738`), manifest 좌표 계약
(:816-819), 어절 표 출처 열(`morph_schema.py:499-501`), 미해결 기호 inventory
(`realign_eojeol_build_corpus.py:189-260`). 예외 3건은 §3(engine_version,
상수 `n_spn/align_status`, `∅` 비대칭).

**Q2. 논문 방법론에서 올바르게 설명 가능한가?** — **예, §8의 보강 후.**
거짓 정밀성의 잠재 원천은 (i) `morph_analysis_utt`를 시간 분할로 오독 —
설계가 차단(전체 span, PROPOSAL_Seoul §5-4); (ii) `phoneme_r_auto`를 실현
전사로 오독 — 이름·문서·매핑 구조가 차단(`phoneme_roman.py:1-13`);
(iii) "전수 완료" 조기 주장 — §8 금지 목록.

**Q3. 6-tier가 Praat 검토·간단 검색과 5.1M 운영 사이에서 타당한가?** —
**타당하다. 전수 물리 저장을 지지하되 실측 후 확정을 권한다.** 실측: 60발화
TextGrid 평균 9,089 bytes → 5.1M 환산 약 **43 GiB**(비압축 추정; NTFS 4KB
클러스터 오버헤드와 5.1M개 파일 생성·백업 비용은 별도, 표본이 60발화라
편차 있음). 발화 수준 3-tier는 파일당 수백 bytes~2KB 수준으로 한계 비용이
작고, 제거해도 파일 수는 그대로라 운영 부담의 본질(파일 수)이 줄지 않는다.
따라서 "일부 tier만 파생"의 실익은 낮다. 근거 코드: 발화 3-tier는
`build_base_tier_data_from_intervals`(`research_textgrid_v2.py:278-333`)가
frozen CSV 행에서 결정적으로 만들므로, 만약 저장량 실측(Q14)이 예상을 크게
넘으면 **동일 함수로 후보 추출 시 재생성하는 경로가 이미 존재**한다 —
즉 지금 결정을 미뤄도 코드 재작업이 없다. 결정 주체는 연구자(§7-2).

**Q4. 형태소 시간경계 없이 발화 전체 span `tagged` — 목적과 일치하는가?** —
**예.** 연구 목적이 "검색→청취 판정"이므로 실측 없는 경계를 주장하지 않는 것이
방법론적으로 옳다. 구현: `_relabel_utterance_tier`(`research_textgrid_v2.py:
219-229`)가 유표 word span 하나에만 label을 둔다. legacy `morphemes` tier의
오독 위험(WORKFLOW §6.2)을 정확히 제거했다. 정밀 위치 검색은
`morph_tokens/units/boundaries`(`morph_schema.py:433-730`)가 담당 — 어절 내/
어절 간 경계 구분(`boundary_scope` :663-667), 좌우 edge 자모(:678-679)까지
갖춰 형태소 경계 환경 검색이 CSV에서 가능함을 확인.

**Q5. 좌표계 분리가 `2사람이 → 두 사람이` 오연결을 막는가?** — **예, 실측
검증됨.** 대응표 생성(`realign_eojeol_build_corpus.py:65-88` — 비한글 어절은
`mfa_word_index=None`으로 삭제 사실 보존), exporter 재생성(`export_mfa_db_
research_6tier.py:452-473`), 세 좌표 열(`WORD_FIELDS`/`PHONE_FIELDS` :127-166),
label 순서 전수 대조 gate(:681, :753-763, :790-799 — 불일치 시 연도 실패).
실물 확인: word 표에서 `reference_eojeol_idx` 4·5가 각각 '두'·'사람이',
`n_source_eojeol=12 ≠ n_reference_eojeol=13`이 값으로 보존됨. 주의 1건:
`form_to_lab_mapping`은 한 어절 안의 분리된 한글 run을 연결한다(`3박4일`→
`박일`; `HANGUL.findall` join :76-77). 이는 동결된 lab 정책
(`unresolved_policy: do_not_guess` :147)이며 `unresolved_symbol` 상태로 추적
되므로 오연결은 아니지만, 그런 발화의 `pron_mfa`가 병합어임을 검색 문서에
명시할 것.

**Q6. 연도별 gzip 세 표가 logical sidecar로 타당한가? 필수 수정은?** —
**타당하다.** 5.1M 개별 CSV 회피 논거(PROPOSAL §4)와 구현(`utt_id`+interval
idx 1:1, manifest의 `logical_sidecar_policy` :821-824)이 일치. 필수 수정:
(i) row key 문서화 — utterance=`utt_id`, word=`utt_id+word_interval_idx`,
phone=`utt_id+phone_interval_idx` (코드상 이미 유일; 계약서에 명기);
(ii) dtype·부울·결측·BOM 동결(M-03); (iii) POSIX 경로(M-02); (iv) schema
evolution — 표 스키마 버전은 manifest(:806-812)에만 있으므로 Parquet 미러가
manifest를 필수 입력으로 받게 할 것; (v) 대량 스트리밍 — 단일 gz는 병렬
스캔이 안 되므로 검색은 Parquet 미러로 한다는 역할 분담(gz=감사·장기보존)을
계약에 명시. 연 phone 표 추정 수십M 행·수백MB gz는 DuckDB `read_csv` 1-thread
로도 처리 가능하나 반복 검색용은 아니다. (vi) 결정적 gzip(M-10).

**Q7. `utt_id` 중심 조인이 추후 안전한가?** — **예.** `utt_id` 유일성 gate가
모든 입구에 있다(search master: `build_search_master.py:346-348`; 세션 로드:
`export_mfa_db_research_6tier.py:220-222`; morph 표: `build_morph_position_
tables.py:179-189`; JSON 파싱: `build_search_master.py:164-165`). 동반표에
speaker/dialogue/co_speaker(:688-691), WAV/LAB 경로(:712-713), TextGrid 상대
경로(:714-716)가 함께 있어 형태소 표·어절 표·TextGrid·WAV·MFA word/phone·
대화/화자를 모두 `utt_id`(+interval idx)로 연결 가능. 사전 후보·KOINA·manual
judgment 표는 **아직 미구현**이며 계약만 있다(PROPOSAL §9-4·5) — 스키마 확정
필요(§7-1). 60발화 조합검색 실증은 `COMBINED_SEARCH_DEMO`(PROJECT_CURRENT_
STATE:158-160)로 존재.

**Q8. 우리말샘/표준국어대사전 1:N 보조표 계약 제안** — 필요한 키·계약:
- 후보 표 기본키: `(lemma, pos, sense_no, pron_variant_idx)`; 열:
  `lemma, homograph_no, pos, sense_no, pron_hangul, pron_roman, pron_ipa,
  source(urimalsaem|std_dict|lexicon_1gi), variant_type(표제어발음|활용발음),
  entry_id(원사전 ID)`.
- 형태소 쪽 연결: Bareun `morph_surface`는 표층형이므로 직접 조인하지 않고,
  **기저형 lemma 매핑 표**를 중간에 둔다: `(morph_surface, pos) → (lemma,
  homograph_no?) + match_status(exact|lemma_only|ambiguous|unmatched)`.
  다의어·동형어는 1:N **그대로 유지**하고 단일값 축약을 금지(PROPOSAL §2 표의
  금지 조항과 일치). 의미 판별을 자동으로 하지 않으며, 코퍼스 의미번호(76.4%
  층)는 `sense_source=corpus_auto`로만 표시(뜻별 빈도는 LS 참조값 사용 원칙).
- 조인 결과는 발화 표가 아니라 **형태소 표 ×사전 후보 표의 별도 뷰**로 두어
  행 폭발이 정본을 오염하지 않게 한다.
- **전제조건(UNVERIFIED)**: 1기 어휘 실물 `lexicon_full`
  (`config/paths.json:26`)과 사전 v2는 reference 4종에 속해 **HDD 유일본 —
  SSD 미회수**(CLAUDE.md·PROJECT_CURRENT_STATE:209). 회수·검증 전에는 이 표를
  만들 수 없다.

**Q9. r2 강제·legacy 미회귀가 보장되는가?** — **예.** (i) manifest 없는 실행
자체가 차단, legacy는 명시 플래그 필요·상호배타(`run_eojeol_realign.ps1:34-53`,
wrapper `run_pre_mfa_bulk_safe.ps1:81-100`); (ii) r2 gate가 release schema·
adoption v3·`allow_yearly_mfa`·`legacy_inline_g2p_default=false`·SHA 5종
교차·vocabulary root 일치를 전수 검사(:388-472); (iii) r2 모드에서 MFA에
`--g2p_model_path`를 넘기지 않음(:1792-1794 — inline G2P 물리적 배제), 잔여
OOV는 exporter `spn=0` gate(:862-869)가 차단; (iv) marker가
`g2p_model=pronunciationMode`를 요구해 legacy marker 재사용 불가
(`Read-DoneMarker` :1312-1313); (v) r2에서 4-tier 폴백 경로 진입 시 즉시 중단
(:2444-2451); (vi) 매 연도 모델 파일 SHA 재검증(`verify_frozen_mfa_bundle`
호출 :344-353)과 alignment contract 재생성(:1490-1545). 2020/2021 재실행은
양층 모두 `-AllowBaselineCommonPronRerun` 요구(:73-83, wrapper :111-131).
정적 검사가 이 안전장치 문자열들을 회귀 고정한다
(`tests/test_powershell_safety.ps1:64-158`).

**Q10. `direct_db_ready`가 재실행 방지와 승인 분리를 지키는가?** — **예.**
의미 선언이 세 곳에서 일관된다: checkpoint `meaning`/`analysis_ready_status`
(`inspect_mfa_db_checkpoint.py:104-109, 125-128` — 실물 60발화 checkpoint에서
확인), marker `computation_complete=true, analysis_ready=false`
(`run_eojeol_realign.ps1:2212-2213`), 문서(PROPOSAL §6). 재사용 시 MFA만
건너뛰고(:1766-1772) export·gate는 다시 강제되며, 계약 불일치 marker는 자동
재정렬 대신 중단한다(:1703-1713). 남은 개선 1건 = M-04(재사용 시 checkpoint
재실행). checkpoint가 coverage 100%를 요구하지 않는 것은 의도(부분 DB도
"재계산 불필요"일 수 있음)와 부합하나, 그 판단 근거가 marker counts에 남으므로
재사용 시 대조만 추가하면 된다.

**Q11. partial·marker·staging·DB 보존 순서가 실패에서도 안전한가?** — **예,
검증됨.** 순서: 동반표 `.partial`→모든 gate→`os.replace` 승격
(`export_mfa_db_research_6tier.py:801-804`; 실패 시 완성본 없음을 시험이 고정
`tests/test_export_mfa_db_research_6tier.py:280-325`), TextGrid는 staged 쓰기+
검증+실패 시 unlink(`research_textgrid_v2.py:469-479`), 연도 폴더는 partial
root에서 잔류 `.partial` 검사(:2290-2296)·coverage 후 원자 이동(:2309-2310),
**marker는 승격 이후에만**(:2315). 창 종료/오류: MFA exit≠0·watchdog kill 시
temp 보존(:2170-2178), exit 0+출력 0 거짓 성공 차단(:2144-2158). 디스크 부족:
시작 전 가드(:1729-1736)+heartbeat 여유 기록(:1946-1952). 파일 lock:
`promote_staged`가 PermissionError 10회 지수 재시도(`pipeline_common.py:84-93`
— V3 백신 환경 대응). 승격–marker 사이 crash는 다음 실행이 명시 중단
(:2240-2242) — 데이터 무손실, 수동 복구(개선 L-05). 이미 끝난 정렬 손실 방지:
stale temp는 삭제 아닌 보존 이동(`Archive-StaleTemp` :1343-1372), lab도 동일
(`archive_stale_lab`, `realign_eojeol_build_corpus.py:282-305`).

**Q12. 예상 미정렬·자료 불가 — 전체 실패 vs 분류 계약, 구체안** — **분류
계약으로 전환해야 한다(H-02).** 구체안:
1. **승인 제외 목록**: `audit_mfa_year_readiness.py`의 분류(:579-596)와
   `quarantine_bad_wavs` 결과에서 연도별
   `approved_exclusions_<year>_<input_contract_id>.csv`
   (`utt_id, reason_code{audio_unusable|quarantined_wav|text_duration_impossible|
   researcher_excluded}, evidence_path, approved_by, approved_at`)를 생성하고
   연구자가 승인·서명. input contract ID에 묶어 재사용 오염 방지.
2. **exporter**: `--approved-exclusions` 인자 추가.
   `alignment_missing`/`search_row_missing` 발화가 목록에 있으면
   `excluded_utterances.csv.gz`(4번째 동반표, **상한 없음**)에 전수 기록하고
   계속, 목록 밖이면 현행대로 hard failure(:946-954 유지). `word_span_fallback`
   은 승인 대상이 아니라 항상 failure 유지(정렬 자체가 무의미한 산출).
3. **승격 gate**: `run_eojeol_realign.ps1:2299-2308`의 99% 휴리스틱을
   `set(lab utt_id) == set(TextGrid) ⊎ set(excluded 기록)` 정확 대사로 교체.
   집계는 코드, 목록 승인은 연구자.
4. **manifest·논문**: 연도 report에 사유별 제외 수를 싣고, §8 서술의 "사유별
   전수 목록" 문장을 이 실물로 뒷받침.

**Q13. 연도 1개 → 다음 연도 gate가 충분한가?** — **현재는 불충분(H-01).**
러너 내부 gate(수량·경계·checkpoint)는 충분하나, **독립** QC 3종이 구 계약
전용이다: `preflight_next_year_after_qc.py:620`(`supported_export_mode:
direct_db_4tier`), `audit_mfa_4tier_year.py:35`, `verify_mfa_db_4tier_sample.
py:22`. §6의 연도 gate 체크리스트가 H-01 수정 후의 충분 조건이다. 연구자 표본
검토·workbook 검증(`validate_mfa_r2_review_workbook.py`)은 재사용 가능.

**Q14. 60발화가 증명하지 못한 것과, 새 MFA 파일럿 없이 확인할 최소 항목** —
60발화 회귀가 증명한 것: 출력 정확성·계약 gate·좌표 분리·승격 순서(전부 재현
확인). **증명하지 못한 것**: (i) 연도 규모(85만 발화·수천 세션)의 exporter
wall-clock·메모리 — 동반표 단일 패스(M-06)와 세션 CSV 이중 읽기 포함;
(ii) 예상 미정렬 경로 — 60발화에는 미정렬 0건이라 H-02 경로가 미실행;
(iii) 5.1M 파일 생성의 스토리지·백업 특성; (iv) Parquet 미러 왕복 동등성;
(v) `validated_existing` 대량 재개 시나리오; (vi) 승격 원자 이동이 대형
디렉터리(수십만 파일)에서 갖는 소요 시간. **새 MFA 파일럿 없이 확인하는 최소
항목**: (1) **합성 대량 fixture 벤치** — 보존 60발화 DB의 utterance/interval
행을 프로그램으로 10⁴–10⁵배 복제한 SQLite로 exporter를 돌려 시간·메모리·재개·
집합 대사를 측정(MFA 불필요, 시험 fixture 패턴 재사용
`tests/test_export_mfa_db_research_6tier.py:37-91`); (2) **스토리지 벤치** —
평균 9,089B(실측)에 연도 발화 수를 곱한 추정치와, D:에 10만 개 소파일 쓰기
속도 실측(NTFS·USB SSD 특성); (3) **정적 fixture로 H-02 경로 단위시험** —
승인 목록 유/무·목록 외 결측·`excluded` 표 전수성; (4) **Parquet 미러 왕복** —
60발화 gzip→Parquet→재 CSV 동등성; (5) 보존 pre-Jamo 2021 완성 DB
(E: 압축 archive)의 읽기 전용 복원으로 실연도 규모 exporter를 1회 시험하는
것은 선택 사항(압축 해제 55GB 공간이 필요하므로 (1)로 충분하면 생략).

## 10. UNVERIFIED 목록

이 리뷰에서 실물로 검증하지 못했고, 추정으로 채우지 않은 항목:

1. **D: 실물 일체** — 파일럿 DB(`D:\mfa_eojeol\pilots\...`), r2 release,
   E: archive. 리포 내 보고서·manifest의 SHA 기록으로만 교차 확인했다
   (수치·SHA는 문서 간 일치). 외부 드라이브 직접 검사는 수행하지 않음.
2. **`audit_mfa_year_readiness.py`의 분류 정확도** — gate 구조(:817-830)와
   분류 상수만 확인. 실연도 데이터에 대한 분류 품질은 미검증.
3. **연도 규모 exporter 성능** — Q14 벤치마크 전까지 미지수 (M-06).
4. **우리말샘/사전 1기 실물** — HDD 유일본, 미회수 (Q8 전제조건).
5. **`work/` 회귀 실물의 재현 가능성** — 실물은 검증했으나 gitignore 상태라
   (L-01) 제3자가 같은 증거를 다시 볼 수 있다는 보장은 없음.
6. **Windows `sess_cache`/scandir 최적화의 5.1M 규모 실측치** —
   설계 주석(`realign_eojeol_build_corpus.py:101-104`)의 성능 주장 자체는
   2026-07-17 실측 기록을 신뢰하되 이번에 재측정하지 않음.

---

*이 보고서는 읽기 전용 리뷰이며, 코드·데이터·D:/E:/H:/Dropbox·원 corpus를
수정하지 않았다. 새로 생성한 파일은 이 문서 하나다.*
