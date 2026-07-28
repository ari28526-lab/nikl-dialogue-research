# EXTERNAL REVIEW — 공통 발음사전·MFA (claude-code, 2026-07-28)

- 대상 저장소: `ari28526-lab/nikl-dialogue-research`
- 대상 브랜치: `agent/harden-pre-bulk-pipelines`
- 검토 기준 commit: `773d2e7a55b572c7098062d3238431c32fb74c6b`
- 검토 방식: 코드 변경 없이 저장소 정독 + 실측(테스트 실행, MFA 3.4.0
  원본 대조, 유니코드 동작 재현). 아래 모든 `파일:행`은 위 commit 기준.
- 실측 환경 고지: 리뷰 환경은 Linux + Python 3.11.15 (생산 환경은
  Windows PS 5.1 + conda MFA). `tests/` Python 전수 **132개 통과, 2.41초**
  실측. `tests/test_powershell_safety.ps1`은 리뷰 환경에 PowerShell이
  없어 미실행(MISSING EVIDENCE — Windows에서만 실행 가능). 5개 `.ps1`
  전부 UTF-8 BOM(EF BB BF) 존재 실측 확인.
- MFA 대조 근거: PyPI `montreal_forced_aligner-3.4.0` wheel의
  `utils.py`·`g2p/generator.py`를 직접 열람(아래 인용).

---

## 1. 최종 판정

**CONDITIONAL GO.** 공통사전 *구축* 파이프라인(prepare→shard G2P→
verify→finalize)의 완전성 gate는 견고하고 테스트로 뒷받침되며(132/132
통과), 동결 묶음 산출물·manifest도 DECISION 문서의 SHA와 일치함을
확인했다. 그러나 저장소의 실행 코드에는 아직 (a) 동결 묶음을 강제하는
핀 고정이 없고, (b) 폐기된 r1의 mismatch=0 동등성 gate가 새 기준 r2를
구조적으로 차단하거나 반대로 구기준 실행을 승인할 수 있는 경로가
남아 있으며, (c) 정렬 산출물 단계의 `spn`/OOV 내용 gate가 없다.
따라서 **구결과 archive와 정상 OOV G2P 계산은 GO, 연도별 MFA 정렬은
MFA-001·002·004 수정 전 NO-GO**이며, 이는 DECISION 문서의 외부 리뷰
checkpoint 방침과도 일치한다.

---

## 2. 발견사항

### MFA-001
- **Severity**: BLOCKER
- **Confidence**: HIGH
- **위치**: `scripts/run_common_pron_mfa_r1.ps1:210-213`,
  `scripts/run_eojeol_realign.ps1:138-144`,
  `scripts/python/package_hf_korean_mfa_bundle.py:293-303`,
  `scripts/python/build_mfa_alignment_contract.py` (expected 비교 부재)
- **증거**: 두 러너 모두 모델을 가변 설치 경로
  `%USERPROFILE%\Documents\MFA\pretrained_models\{acoustic,dictionary,g2p}\korean_mfa.*`
  에서 읽는다. 이 경로는 DECISION §채택 과정 2("내장 downloader의 거짓
  갱신")에서 `--force`로도 구버전이 남아 있음이 실측된 바로 그 위치다.
  `package_hf_korean_mfa_bundle.py`는 commit·SHA를 *기록*만 하고 기대값
  (commit `0091ffa1…`, SHA 3종)과 *비교*하지 않으며, 기대 commit/SHA를
  받는 인자 자체가 없다. `build_mfa_alignment_contract.py`도 현재 파일의
  fingerprint를 계약 ID에 넣을 뿐 기대값 대조가 없다. 즉 DECISION의
  hard gate 1–3(공식 commit·SHA 일치, inventory 동일, Jamo udecomp)이
  실행 코드 어디에서도 강제되지 않는다.
- **재현법**: 설치 경로에 구 음절형 모델이 남은 상태(현재 상태로 추정)
  에서 `run_common_pron_mfa_r1.ps1 -PrepareOnly` 실행 → prepare가 구
  모델 fingerprint로 정상 성공하고 manifest도 유효하게 생성됨(차단 없음).
- **연구 영향**: 일관성·재현성 — 구 모델로 만든 산출물이 유효한
  manifest·마커를 갖게 되어, "2020–2025 동일 기준" 방법론 주장의 근거가
  실행 시점 운에 좌우된다.
- **제안 수정**: 저장소에 이미 커밋된
  `outputs/reports/korean_mfa_latest_jamo_bundle_20260728.json`(실측:
  DECISION 표의 SHA 3종·phone 107·commit과 일치 확인)을 **기대 계약
  정본**으로 삼아, r2 러너·prepare·alignment contract가 시작 시 모델
  파일 SHA256을 이 파일과 hard 비교 후 불일치면 즉시 중단하게 한다.
  모델 경로도 동결 묶음 디렉터리
  (`D:\mfa_common_pron\models\frozen_…_0091ffa1`)를 명시 인자로 받는다.
- **수정 후 검증**: (1) 설치 경로에 구 모델을 둔 채 실행 → SHA 불일치로
  즉시 중단. (2) 동결 묶음 경로로 실행 → 통과. (3) manifest의
  `inputs.*.sha256` == 기대 계약 JSON의 SHA 3종 자동 대조 테스트 추가.

### MFA-002
- **Severity**: BLOCKER
- **Confidence**: HIGH
- **위치**: `scripts/run_common_pron_mfa_r1.ps1:411-478`,
  `scripts/run_eojeol_realign.ps1:195-213`,
  `scripts/python/audit_common_pron_mfa_equivalence.py:593-651,700`,
  `scripts/python/build_common_pron_mfa_lexicon.py:814-818`,
  `scripts/show_common_pron_mfa_status.ps1:255-270`
- **증거**: 구 r1의 채택 gate(2020·2021 mismatch=0)가 네 지점에 살아
  있다. ① r1 러너는 동등성 `status!='passed'`면 throw. ② 어절 재정렬
  러너는 공통사전을 쓰려면 동등성 `passed` + `allow_common_dictionary_for_2022`
  를 요구. ③ 동등성 감사는 mismatch>0이면 exit 2. ④ finalize manifest는
  `required_before_mfa.baseline_*_equivalence=pending`을 하드코딩. 그런데
  MONITOR 14:30 실측대로 2021 DB의 10개 어절이 `pronunciation=spn`이고
  2020 구 TextGrid의 해당 어절 phone열도 `spn`이므로, spn 결함을 고친
  **어떤** 사전(r1 수정본이든 r2든)도 `audit_2020`(`phone_sequence_changed`,
  `audit_common_pron_mfa_equivalence.py:199-204`)과 `audit_2021`
  (`pronunciation_set_changed`, 같은 파일 474-480행)에서 mismatch가
  반드시 발생한다. 즉 이 gate는 **수학적으로 통과 불가**하며, 통과했던
  유일한 상태는 결함(spn) 재생산뿐이다. 반대로 설치 경로의 구 모델로
  r1 러너를 그대로 완주시키면 구기준 사전이 `allow_common_dictionary_for_2022=true`
  로 승인된다(①+MFA-001 결합). 상태판도 같은 gate를 `complete`로
  표출한다.
- **재현법**: spn이 실 phone으로 바뀐 사전으로
  `audit_common_pron_mfa_equivalence.py` 실행 → 항상 exit 2 → 러너 throw.
- **연구 영향**: 일관성 — 새 기준 r2가 영구 차단되거나, 구기준 산출이
  "2022 사용 허용"으로 오승인되는 양방향 위험.
- **제안 수정**: MONITOR §2020·2021 재실행 판단의 결정대로 감사를
  "채택 gate"에서 "전수 차이 inventory"로 개편한다: (a) 새 모드
  (`--mode difference-inventory`)는 mismatch가 있어도 exit 0 +
  `status=differences_inventoried`로 CSV를 산출하고, 차이를
  `spn_defect_fixed / base_dictionary_changed / g2p_changed` 등으로 분류.
  (b) r2 채택 gate는 동등성이 아니라 「사전 gate(missing=0·spn=0·이탈 0,
  기구현) + 모델 핀(MFA-001) + 차이 inventory 분류 완료 + 연구자 승인
  기록」으로 재정의. (c) `required_before_mfa`·`allow_common_dictionary_for_2022`
  필드를 r2 계약에 맞게 교체, 상태판 gates 표기도 함께 갱신.
- **수정 후 검증**: 구기준 baseline 대비 r2 사전으로 difference-inventory
  실행 → exit 0, spn 10개 어절이 전부 `spn_defect_fixed`로 분류되고
  건수가 구 grapheme 감사(5,176 OOV·654 음절)와 정합. 구 gate 경로로는
  어떤 r2 실행도 시작되지 않음을 회귀 테스트로 고정.

### MFA-003
- **Severity**: HIGH
- **Confidence**: HIGH
- **위치**: `scripts/run_eojeol_realign.ps1:161-164` (기본 모드),
  `scripts/run_pre_mfa_bulk_safe.ps1:21-22,204-210` (기본값 '')
- **증거**: `-CommonPronManifest` 없이 실행하면 `$useInlineG2p=$true`
  로 설치 경로 사전+inline G2P의 **구방식** 정렬이 어떤 연도든 그대로
  수행되고, done 마커·병합·staging까지 정상 생성된다. bulk wrapper의
  기본값도 빈 문자열이라 습관적 호출이 곧 구기준 실행이다. 마커에
  `g2p_model='korean_mfa'`가 기록돼 사후 판별은 가능하지만 실행 자체는
  차단되지 않는다. DECISION의 "2020–2025 최종 MFA는 동일 묶음" 원칙과
  정면 충돌.
- **재현법**: `run_eojeol_realign.ps1 -Year 2022` (공통사전 인자 생략)
  → 게이트 없이 구방식 정렬 시작.
- **연구 영향**: 일관성 — 연도 간 상이한 사전·G2P 산출물이 정상 완료로
  기록됨.
- **제안 수정**: r2 계약 확정 후 inline G2P 경로를 명시적 opt-in 플래그
  (예: `-AllowLegacyInlineG2p`) 뒤로 옮기고, 기본 실행은
  공통사전 manifest 필수로 전환.
- **수정 후 검증**: 인자 생략 실행이 즉시 중단되는지, opt-in 시에만
  구방식이 동작하며 마커에 legacy 표식이 남는지 테스트.

### MFA-004
- **Severity**: HIGH
- **Confidence**: HIGH
- **위치**: `scripts/python/audit_mfa_4tier_year.py`,
  `scripts/python/export_mfa_db_4tier.py` (두 파일 모두 `spn` 문자열
  0회 — grep 실측)
- **증거**: 연도별 QC는 tier 구조·0–xmax 연속성·lab↔TextGrid coverage·
  WAV duration을 검사하지만, 정렬 **산출물 내용**의 `spn`/OOV gate가
  없다. 2021의 숨은 spn도 QC가 아니라 수동 DB 조회로 발견됐다(MONITOR
  14:30). r2에서 사전이 관측 어휘를 전수 포함하므로 정렬 시 spn은
  "입력 계약 위반"의 신호인데, 이를 자동 검출하는 장치가 없다.
- **재현법**: spn interval이 있는 TextGrid/DB를 현행
  `audit_mfa_4tier_year.py`에 통과시키면 valid로 집계된다(검사 항목에
  라벨 내용 gate 없음).
- **연구 영향**: 정합성 — G2P 부재/어휘 불일치가 재발해도 "정렬 성공"
  으로 남는 r1 사고 유형의 재발 경로.
- **제안 수정**: 연도 QC에 두 검사를 추가한다. (a) DB gate:
  `SELECT COUNT(*) FROM word w JOIN pronunciation p ON p.word_id=w.id
  WHERE w.word_type IN ('speech','oov') AND p.pronunciation='spn'` = 0,
  (b) TextGrid phones tier의 `spn` 라벨 수 = 0 (기존 tier 순회에 카운터
  1개 추가라 비용 미미). 위반 시 해당 연도 marker 생성 금지.
- **수정 후 검증**: spn 1건 주입 fixture로 QC가 FAIL하는 단위 테스트;
  r2 첫 연도 실측 보고서에 `spn_intervals=0` 필드 존재.

### MFA-005
- **Severity**: MEDIUM
- **Confidence**: HIGH (코드 동작), MEDIUM (운영 시나리오)
- **위치**: `scripts/archive_pre_jamo_outputs_to_external.ps1:203-217,234-242`,
  `scripts/run_common_pron_mfa_r1.ps1:383-406`
- **증거**: ① archive 내용 검증은 `Join-Path $source '2021.db'`, 즉
  **원본 루트 직하의 `2021.db`만** SHA256 대조하고, 그 외 파일은
  robocopy zero-diff(크기+시각)와 파일 수·총 byte만 본다.
  `archive_stale_temp\20260725_141701\C\2020\2020.db`(2020 유일본 부분
  DB — r1 러너 주석대로 2020 발음 후보의 유일한 DB 증거)는 중첩 경로라
  hash 검증 없이 `-PruneAfterVerify`에서 D: 원본이 삭제된다. ② prune
  대상(`07_staging\2020·2021`, `mfa_tmp\2021`, `archive_stale_temp`)은
  r1 러너가 하드코딩한 동등성 baseline 경로와 정확히 겹친다. prune 후
  차이 inventory(MFA-002 개편본)가 읽을 D: 입력이 사라지는데, E:는
  "실행 root 아님" 정책이라 감사 입력의 소재 규정이 없다.
- **재현법**: `-PruneAfterVerify` 실행 후
  `run_common_pron_mfa_r1.ps1` 재실행 → `전수 동등성 baseline/evidence
  없음` throw.
- **연구 영향**: 재현성 — baseline 유일본의 무결성 증거 부족 +
  차이 감사의 입력 상실 순서 사고 가능.
- **제안 수정**: (a) 검증을 "트리 내 모든 `*.db` SHA256 대조"로 확장
  (대상 5종에 db는 소수라 비용 미미). (b) prune은 차이 inventory 완료
  ·보고서 커밋 **후**에만 허용하거나, 감사 스크립트가 E: archive를
  읽기 전용 입력으로 명시 지원(정책 문서에 "E: 읽기는 허용, 실행
  root 금지" 예외를 명문화).
- **수정 후 검증**: archive manifest에 db별 SHA 기록 필드 존재; prune
  전제조건(차이 보고서 fingerprint) 검사 테스트.

### MFA-006
- **Severity**: MEDIUM
- **Confidence**: HIGH
- **위치**: `scripts/run_eojeol_realign.ps1` (lock 부재; 파일 전체에
  lock 취득 코드 없음), `scripts/run_common_pron_mfa_r1.ps1:177-180`,
  `scripts/run_pre_mfa_bulk_safe.ps1:98-135`
- **증거**: 상호 배제는 「bulk wrapper가 만든
  `D:\mfa_eojeol\locks\pre_mfa_bulk.lock` ↔ r1 러너의 하드코딩 검사」
  한 방향뿐이다. `run_eojeol_realign.ps1`을 헤더 주석(8행)대로 **직접**
  실행하면 어떤 lock도 만들지 않으므로, 공통 G2P shard 계산과 연도
  정렬이 같은 D:에서 동시에 돌 수 있다(CLAUDE.md 규칙 7 위반 경로).
  역방향(재정렬 러너가 공통 G2P lock을 확인)도 없다.
- **재현법**: 터미널 1에서 `run_eojeol_realign.ps1 -Year 2020` 직접
  실행, 터미널 2에서 r1 러너 실행 → 둘 다 진행.
- **연구 영향**: 효율성·안정성 — USB SSD 경합으로 두 배치 모두 지연
  ·타임아웃성 실패 위험.
- **제안 수정**: 재정렬 러너가 직접 실행 시에도 `pre_mfa_bulk.lock`을
  스스로 취득(+해제)하고, 공통 G2P lock(`D:\mfa_common_pron\locks\*.lock`
  의 live PID)을 시작 gate에서 확인. 경로는 하드코딩 대신
  `config/paths.json` 파생으로 통일.
- **수정 후 검증**: 직접 실행 중 lock 파일 존재 실측; 교차 실행 시도가
  차단되는 dry test.

### MFA-007
- **Severity**: MEDIUM
- **Confidence**: HIGH
- **위치**: `scripts/run_eojeol_realign.ps1:295-330` (`Get-WorkPaths`),
  `scripts/run_pre_mfa_bulk_safe.ps1:149-153`
- **증거**: `-PreferD` 미지정 기본 동작은 신규 연도에 대해 C: 여유가
  문턱(45/55GB) 이상이면 **C:\mfa_tmp·C:\mfa_eojeol_out을 선택**한다.
  DECISION 불변 원칙("`D:\`는 유일한 메인 작업·실행·최종 산출물
  드라이브")과 충돌하며, 과거 C: 실행 잔재가 실제로
  `archive_stale_temp\…\C\2020` 형태로 남아 있다. bulk wrapper도
  기본값이 "자동 선택"이다.
- **재현법**: C: 여유 ≥45GB 상태에서 `-Year 2022`를 -PreferD 없이 실행
  → temp가 C:에 생성.
- **연구 영향**: 일관성·운영 — 산출물 소재 분산, resume 드라이브 전환
  분기 재유발.
- **제안 수정**: r2부터 기본을 D: 고정(-PreferD 기본 on 또는 C: 후보
  제거)하고, 기존 temp-우선 resume 규칙만 유지.
- **수정 후 검증**: 인자 없는 실행의 temp·out 경로가 D:임을 로그로
  확인하는 테스트/실측.

### MFA-008
- **Severity**: LOW
- **Confidence**: HIGH
- **위치**: `scripts/show_common_pron_mfa_status.ps1:166-189`
- **증거**: 처리율·ETA가 「현재 lock의 `acquired_at` 이후 경과시간 ÷
  누적 생성 단어수」로 계산된다. 중단 후 재개하면 이전 실행에서 검증된
  shard들의 단어수가 분자에 그대로 들어가 재개 직후 처리율이 크게
  과대평가되고 ETA가 비현실적으로 짧아진다. 데이터 손상은 없다
  (읽기 전용 확인).
- **재현법**: shard 다수 완료 상태에서 러너 재시작 직후 상태판 실행.
- **연구 영향**: 효율성 — 무인 배치 babysitting 판단(개입 시점)을
  오도할 수 있음.
- **제안 수정**: 분자를 「현재 lock 취득 이후 새로 검증된 shard 단어수」
  로 한정하거나, shard report의 `recorded_at`으로 실측 rate를 계산.
- **수정 후 검증**: 재개 시나리오 fixture에서 ETA가 최근 실측 rate
  기준으로 산출되는지 확인.

### 확인했으나 문제 없음(오탐 방지 기록)
- 사전 확률열 파서는 MFA 3.4.0 원본과 **동일**: 정규식
  `\b(\d+\.\d+|1)\b`·최대 4열 pop·단어 NFKC까지 일치
  (`build_common_pron_mfa_lexicon.py:46,60-78` ↔ wheel
  `montreal_forced_aligner/utils.py:186-210` 실측 대조,
  `tests/test_build_common_pron_mfa_lexicon.py:143` 통과).
- `clean()`의 NFKC가 어휘를 변형할 위험: 없음 — lab 토큰은
  `form_to_lab`이 `[가-힣]`만 남기므로(`realign_eojeol_build_corpus.py:46,64-71`)
  NFKC 불변이고, MFA도 사전 단어를 NFKC 정규화하므로 오히려 정합.
- shard 완전성: 입력↔출력 집합 동일·단어당 1발음·shard 간 중복·spn·
  inventory 이탈이 shard 검증과 finalize 양쪽에서 이중 차단
  (`build_common_pron_mfa_lexicon.py:602-668,684-741`), r1 실측(14:21
  34건 누락 차단)으로 라이브 검증됨.
- archive allowlist의 CRLF clone(`official_…_20260728`)과 동결 원천
  LF clone(`official_…_20260728_lf`)은 별개 경로 — bundle manifest
  `hf_root` 실측으로 prune이 원천을 지우지 않음을 확인.
- 거짓 성공 가드: align exit 0 + TextGrid 0건 → temp 보존 중단
  (`run_eojeol_realign.ps1:1916-1930`), 존재-기반 성공 판정을 상태판이
  하지 않음(`show_common_pron_mfa_status.ps1:5-8,104-132`).

---

## 3. `ᆳ` 처리 판정

**수정 후 채택(완전분해 방안 유지 + 필수 보강 3건).**

근거 실측: MFA G2P는 출력 word 키를 `clean_up_word`에서 NFKD→필터→
**NFKC 재조합**으로 만든다(wheel `g2p/generator.py:445-456`). 재작성
입력 `외골(ᆯᆺ)을`은 NFKC로 `외곬을`에 복원되지 **않고** `외골ᆺ을`
(U+11BA 고립 종성)로 남는다(Python 재현 실측). 따라서 재작성 문자열을
그대로 shard에 넣으면 사전 word 키가 코퍼스 표층형과 달라져,
`verify_g2p_shard`/`finalize`의 coverage gate가 (올바르게) 실패한다.
또 `--strict_graphemes`는 미지원 grapheme 어절을 exit 0인 채 조용히
누락시키므로(generator.py:614,659 — r1 14:21 사고와 동일 기제) 재작성
없이 v3.2.0에 그대로 넣는 선택지는 없다.

보강 조건:
1. **재작성은 FST 입력에만** 적용하고, 산출 사전 행의 word 키는 원
   표층형(`외곬수적인·외곬을·외곬의·천구백칤비육`) 그대로 기록한다
   (전용 미니 shard + 「원형→재작성형→출력 phone」 3열 매핑을 release
   manifest에 SHA와 함께 동결). 기존 coverage gate가 키 복원 누락을
   자동 차단하므로 gate는 그대로 둔다.
2. `ᆳ→ᆯ+ᆺ` 이외의 미지원 grapheme 발견 시 중단하는 현행 결정
   (`audit-graphemes` gate)을 r2 러너의 실행 전 필수 단계로 배선한다
   (현재는 보고서만 존재: `common_pron_mfa_r2_latest_jamo_grapheme_coverage_20260728.json`,
   4어절·ᆳ 1종 실측).
3. 산출 4건의 phone열은 연구자 언어학 승인을 기록으로 남긴다
   (겹받침 ㄽ의 모음 조사 앞 [ㄹ+ㅆ] 실현 등은 모델이 학습 분포 밖
   이중 종성열에서 보장하지 못함 — 4건이라 육안 검증 비용 0에 가깝다).

phone inventory를 바꾸지 않는 대안(동일 Jamo 유지, 우선순위 순):
- **대안 A(더 단순·권장 후보)**: 4어절을 G2P 경로에서 빼고, 같은
  107-inventory phone만 쓰는 **동결 수동 4행 override 표**
  (`pron_source=manual_jamo_ls_decomposition_v1`)로 finalize에 주입.
  재현성은 SHA 고정 표가 담보하고, rewriter의 분포 밖 입력 문제가
  원천 소거된다. 채택 시 g2p_cache의 `pron_source` 구분과 manifest
  카운트(`manual_override_rows=4`)만 추가하면 된다.
- 대안 B: 위 보강 1–3을 적용한 완전분해 자동화(결정문 방안). 자동화
  일관성은 높으나 매핑·검증 코드가 늘어난다.
- 금지 확인: `spn` 잔류 최종안 없음(두 안 모두 실 phone), 타 모델
  혼용 없음, inventory 변경 없음.

---

## 4. 전 연도 재실행 계약 체크리스트

DECISION §앞으로의 hard gate 12항 기준.

| # | 항목 | 판정 | 필요 증거(한 줄) |
|---|---|---|---|
| 1 | 공식 commit·동결 3파일 SHA 일치 | **FAIL** | 러너 시작 시 기대 계약 JSON과의 hard 비교 코드 + 불일치 중단 로그 (MFA-001) |
| 2 | acoustic–G2P phone inventory 동일 | **PASS** | `package_hf_korean_mfa_bundle.py:215-220` 강제 + bundle manifest 107/107 실측 |
| 3 | Jamo `unicode_decomposition=true` | **PASS** | 같은 파일 221-224행 gate + manifest `unicode_decomposition:true` 실측 |
| 4 | OpenFST symbol CR=0 | **PASS** | 같은 파일 225-229행 + `test_rejects_windows_crlf_symbol_files` 통과 |
| 5 | OOV grapheme coverage 100% (허용 확장 U+11B3 한정) | **MISSING EVIDENCE** | 감사 보고서는 실측 존재(4어절·ᆳ 1종)하나 ᆳ 처리 구현·재감사 0건 보고서 미존재 (§3 보강 후 재실행) |
| 6 | shard 입·출력 단어 집합 동일 | **PASS** | `verify_g2p_shard:608-624`+`finalize:705-712`+테스트, r1 14:21 라이브 차단 실측 |
| 7 | 1-best·spn=0·inventory 이탈=0 | **PASS** | `read_generated_dictionary:100-110`·`finalize:724-741`+`test_finalize_rejects_spn` 등 통과 |
| 8 | 기본행 보존 + OOV 전수 포함 | **PASS**(주석) | `finalize:744-770`+`test_finalize_preserves_base_rows…`; 단 "byte 보존"은 빈 행 제거·개행 LF 통일 범위에서만 성립 — 계약 문구를 "행 텍스트·순서 보존"으로 정정 권고 |
| 9 | 2020–2025 동일 final dictionary·acoustic SHA | **FAIL** | 연도 간 alignment contract SHA 동일성 최종 감사 스크립트·보고서 부재 (신규 필요) |
| 10 | 연도별 TextGrid 수·tier·누락·DB integrity 독립 QC | **FAIL**(부분) | 구조 QC는 존재하나 산출물 spn/OOV 내용 gate 부재 (MFA-004) — spn=0 필드가 있는 연도 QC 보고서 필요 |
| 11 | 구·새 결과 경로·manifest 혼용 금지 | **MISSING EVIDENCE** | staging 충돌은 차단됨(`run_eojeol_realign.ps1:1962-1965`)이나, 구 staging archive→비우기→r2 기록의 순서 절차 문서·스크립트 미확정 (MFA-005와 연동) |
| 12 | 존재·exit 0 성공 판정 금지 | **PASS**(주석) | 사전 파이프라인·align 거짓 성공 가드·상태판 모두 준수 실측; 잔여 구멍은 #10의 내용 gate로 마감 |

---

## 5. 실행 전 필수 수정 순서 (BLOCKER/HIGH만, 의존 순)

1. **MFA-001** 동결 묶음 SHA 핀 고정(기대 계약 JSON 대조)을 r2 러너·
   prepare·alignment contract에 삽입 — 이후 모든 gate가 이 위에 선다.
2. **MFA-002** 동등성 감사를 difference-inventory 모드로 개편하고 r2
   채택 gate(사전 gate+핀+차이 분류+연구자 승인)를 새로 정의 —
   1의 핀 값을 계약 필드로 사용하므로 1 이후.
3. **MFA-004** 연도 QC에 spn/OOV 내용 gate 추가 — 2에서 정의한 r2
   계약의 연도별 검증 항목으로 편입.
4. **MFA-003** inline G2P(구방식) 경로를 opt-in 플래그 뒤로 격리 —
   2의 새 gate가 있어야 "기본=공통사전" 전환이 가능.
5. (순서 제약 주의, MEDIUM) **MFA-005**: `-PruneAfterVerify`는 2의
   차이 inventory 완료·보존 전까지 실행 금지 + `*.db` 전수 SHA 검증
   확장. — 위 1–4와 병행 가능하나 prune 실행만은 2 완료 후.

---

## 6. 성능 개선

결과를 바꾸지 않는 것:
- **G2P shard 계산의 타 기기 병행**: shard 입력 txt+동결 모델 zip만
  있으면 되므로 i5-1240P 기기에서 동일 SHA 모델·동일 MFA 3.4.0으로
  분담 가능. r1 실측(shard1 ≈ 39분/25k 단어) 기준 N200 단독 전량은
  약 22–23시간 추정 — 분담 시 절반 이하 기대이나 **계측 필요**
  (동일 shard를 양 기기에서 계산해 출력 SHA 동일성 확인 후 채택).
- **차이 감사 baseline 추출 캐시**: 2020 TextGrid 866,196개 walk는
  회당 수 시간(USB) — 「word→phone열 집합」 추출을 1회 수행해 CSV로
  동결(fingerprint 포함)하고 이후 감사·연구는 캐시를 읽게 하면 재실행
  비용이 파일 1개 읽기로 줄어든다. 추출 결과는 동일 입력의 순수 함수라
  결과 불변.
- **direct-DB 4-tier export 기본화**(`-UseDirectDbExport`): raw
  TextGrid 수백만 개 쓰고-다시-읽는 이중 I/O 제거 — 이미 구현·검증된
  경로(`run_eojeol_realign.ps1:1952-2067`, 관련 테스트 통과). r2
  기본값으로 승격 권고.
- 상태판 재개 후 rate 산정 교정(MFA-008) — 관측 정확도 개선.
- `audit_2020` ThreadPool workers(현 NumJobs=4)를 USB 랜덤리드 특성에
  맞춰 6–8로 상향 — 효과는 **계측 필요**(I/O 병목이면 이득, CPU
  병목이면 무익).

결과를 바꿀 수 있는 것(전부 비권고):
- MFA 버전 업그레이드·beam/boost 파라미터 변경·비엄격 G2P — 정렬
  결과·phone 기준이 바뀌므로 r2 계약 동결 후에는 금지가 맞다.
- shard_size 확대는 사전 결과는 불변이나 실패 시 재계산 단위가 커진다
  — 현행 25k 유지 권고(변경 이득 근거 없음: 계측 필요).

---

### 리뷰에서 실행하지 못한 것 (MISSING EVIDENCE 명세)
- `tests/test_powershell_safety.ps1` 및 PS1 구문 검사: 리뷰 환경에
  PowerShell 부재 — Windows에서 실행·로그 보존 필요.
- 실제 D:/E: 드라이브 상태·설치 모델의 현재 SHA·동결 묶음 실물:
  저장소 밖 자산이라 미검증 — MFA-001 수정 후 러너의 핀 검사 로그로
  대체 확인.
- ᆳ 4어절의 실제 G2P 출력 phone열: 미구현 단계라 미실측 — §3 보강
  구현 후 4행 산출물로 확인.
