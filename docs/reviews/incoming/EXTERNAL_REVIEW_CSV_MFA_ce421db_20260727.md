한국어 언어학 연구 파이프라인 관련 요청이므로, 먼저 필수 스킬(`nikl-mfa-batch-safety`)을 로드하고 브랜치를 가져오겠습니다.

로컬에 대상 브랜치가 없으므로 origin에서 가져오겠습니다.

build_search_master.py 정독 완료. 이어서 발음 규칙 엔진과 메타데이터 인덱스를 읽겠습니다.

이제 핵심 러너인 run_eojeol_realign.ps1(1,073행)을 정독합니다.

2021 실행 대장까지 확인했습니다. 모든 검토가 끝났으므로 이제 최종 리뷰 보고서를 작성합니다.

리뷰를 완료했습니다. 코드·GitHub·데이터는 일절 수정하지 않았고(읽기 전용 worktree 사용), 아래가 리뷰 결과 전문입니다. 같은 내용을 `.md` 파일로도 첨부했습니다(§8의 Codex 전달용).

---

# 외부 코드리뷰 결과 — 전체 CSV·MFA 파이프라인 (agent/harden-pre-bulk-pipelines)

```text
repository: ari28526-lab/nikl-dialogue-research
branch: agent/harden-pre-bulk-pipelines
reviewed_commit_sha: ce421dbe8c6b7f5bb50202b69f3ff1785508ba5f
reviewed_at: 2026-07-27
files_actually_inspected:
  # 문서 (전문 정독)
  docs/reviews/HANDOFF_external_review_CSV_MFA_20260727.md
  README.md / docs/PROJECT_SUMMARY.md / docs/자료구축_코드해설.md / scripts/SCRIPTS_INDEX.md
  docs/decisions/DESIGN_safe_pre_bulk_pipeline_2026-07-24.md
  docs/decisions/DESIGN_pronunciation_environment_search_2026-07-25.md
  docs/decisions/DESIGN_common_pronunciation_lexicon_2020_2025_20260727.md
  docs/decisions/RUNBOOK_pre_MFA_bulk_safe_2026-07-25.md
  docs/decisions/AUDIT_pre_bulk_MFA_CSV_2026-07-24.md
  docs/decisions/AUDIT_remaining_MFA_years_and_direct_DB_export_2026-07-26.md
  docs/decisions/MONITOR_2021_pre_mfa_v1_20260727.md
  # CSV 경로 (전문 정독)
  scripts/run_search_master.ps1 / scripts/python/pipeline_common.py
  scripts/python/preflight_search_master.py / scripts/python/build_search_master.py
  scripts/python/predict_pron.py / scripts/python/build_metadata_index.py
  scripts/python/audit_search_master.py / scripts/python/bareun_dialogue_full.py
  scripts/python/paths.py / config/paths.json
  # MFA 경로 (전문 정독; 표시한 2개만 부분)
  scripts/run_pre_mfa_bulk_safe.ps1 / scripts/preflight_eojeol_realign.ps1
  scripts/run_eojeol_realign.ps1 / scripts/python/realign_eojeol_build_corpus.py
  scripts/python/export_mfa_db_4tier.py / scripts/python/realign_eojeol_merge_output.py
  scripts/python/merge_textgrid_v2.py(1–100행) / scripts/python/retrofit_textgrid_2020_2024.py(1–70행)
  scripts/python/patch_mfa_export_queue.py / scripts/python/patch_mfa_skip_export.py
  scripts/python/verify_mfa_install.py / scripts/python/quarantine_bad_wavs.py
  scripts/python/audit_mfa_year_readiness.py / scripts/python/audit_mfa_4tier_year.py
  scripts/python/preflight_next_year_after_qc.py / scripts/python/compare_textgrid_tiers.py
  scripts/python/locate_utt.py / scripts/python/fetch_audio_for_search.py
  scripts/python/stitch_session.py / scripts/python/build_stratified_mfa_review_bundle.py(90–430행+함수 목록)
  # 테스트 (정독)
  tests/test_build_search_master.py / tests/test_pipeline_common.py / tests/test_powershell_safety.ps1
  # 근거 산출물 (수치 추출)
  outputs/reports/COMPARE_mfa_builtin_vs_db_4tier_21962_20260726.json
  outputs/reports/COMPARE_mfa_builtin_vs_db_parallel4_21962_20260726.json
  outputs/reports/AUDIT_mfa_year_readiness_2021-2025_20260726.json
  outputs/reports/AUDIT_mfa_year_readiness_2021_content_20260726.json
tests_or_static_checks_actually_run:
  - git fetch + rev-parse → 전체 SHA 고정 (위)
  - python3 -m py_compile scripts/python/*.py tests/*.py scripts/colab/*.py → 전부 통과 (Python 3.11.15, Linux)
  - python3 -m pytest tests/ → 59 passed (pytest·openpyxl 리뷰 환경에 설치 후)
  - python3 predict_pron.py --selftest → 30/30 통과
  - predict_pron 추가 프로브 실행(실측): 굳히다→구티다, 닫히다→다티다, 묻히다→무티다,
    앉히다→안히다, 넓히다→널히다, 밝히다→박히다, 읽히다→익히다 (전부 표준발음과 불일치)
  - realign_eojeol_build_corpus.form_to_lab 프로브(실측): "3시요"→"시요",
    "무조건 1층으로 된 집"→"무조건 층으로 된 집", "OK 하겠습니다"→"하겠습니다"
  - outputs/reports의 동등성·준비도 JSON 수치를 파싱해 문서 주장과 대조
    (21,962 전수 동일 / 2021 lab 일치 1,335,015·불일치 38,320·누락 186 — 문서와 정확히 일치)
unavailable_data_or_assumptions:
  - 리뷰 환경은 Linux이며 pwsh 없음 → PowerShell 구문·tests/test_powershell_safety.ps1은
    실행하지 못했고 .ps1은 수동 정독으로 검토(구문 오류 주장은 하지 않음)
  - D: 원자료·WAV·TextGrid·MFA 설치본·SQLite DB·pre-MFA staging 접근 불가 →
    실데이터 상태 주장은 전부 리포에 커밋된 보고서·문서 기준
  - MFA 3.4.0 소스 미보유 → 패치 스니펫과 MFA 내부 구조의 대응은 patch 스크립트의
    인용과 커밋된 VERIFY/RESULT 보고서를 근거로 신뢰(직접 재현 아님)
  - direct 경로의 temp DB 파일명 `<연도>.db` 가정(run_eojeol_realign.ps1:898)은 코드 추론
```

## 총평 (요약)

이 브랜치는 F01–F29 사고 등록부의 교훈이 코드에 실제로 반영된, 보기 드물게 방어적인 파이프라인이다. 원자적 승격(`.partial`→검증→`os.replace`), 구판 archive, 입력계약 SHA256, 거짓 성공 차단(exit 0 + TextGrid 0건), stale temp 보존 격리, 병합 부분실패 exit 1, direct DB 경로의 21,962건 전수 동등성 검증까지 문서 주장과 코드·커밋된 보고서가 서로 일치함을 역추적으로 확인했다. **P0(정본 손상·복구 불가)은 발견하지 못했다.** 아래 발견은 (1) 대량 경로에서 아직 게이트가 없는 연구 타당성 위험 2건(P1), (2) 정확도·재현성·운영상 위험 7건(P2), (3) 유지보수 8건(P3)이다. 현재 진행 중인 2021 실행을 중단할 근거는 없다. 2022 시작 전에 P1 2건과 P2-05를 처리하기를 권고한다.

---

## P1-01 발화 번호가 어긋난 세션(F29형)의 CSV–WAV 대응 검증이 대량 경로에 없음

- 범위: MFA | CSV | recovery
- 위치: `scripts/python/audit_mfa_year_readiness.py:160-166` (크기 44바이트 검사만 존재), `scripts/run_eojeol_realign.ps1:640-644` (quarantine은 0바이트류만), `docs/decisions/AUDIT_pre_bulk_MFA_CSV_2026-07-24.md:84` (F29)
- 확신도: high (게이트 부재는 코드로 확정) / 실제 발생 규모는 low (추가 데이터 필요)
- 확인한 근거: F29 등록부에 따르면 층화 파일럿 v1에서 세션 `SDRW2300000130`은 CSV 428행·WAV 436개이고 428행 중 363행의 길이가 0.02초 이상 불일치했다(발화 번호가 밀린 음성 세션). 층화 파일럿 v2는 세션별 CSV–WAV 대응률(≥98%)·발화 길이 잔차(≤0.025초) 검사를 도입했지만(`build_stratified_mfa_pilot.py`, SCRIPTS_INDEX:86), **대량 경로에는 같은 검사가 없다**: `audit_mfa_year_readiness.py`는 파일 존재와 44바이트 미만만 보고, `run_eojeol_realign.ps1`·`export_mfa_db_4tier.py`·`audit_mfa_4tier_year.py` 어디에도 CSV의 `start/end`(dur)와 WAV header duration의 잔차 대조가 없다. `audit_mfa_4tier_year.py`의 WAV duration 검사는 TextGrid xmax와 **정렬에 쓴 그 WAV**를 비교하므로 이 오류를 원리적으로 잡지 못한다. F29의 "남은 검증"란에도 "문제 세션 전수 범위·재분절 가능성은 대량 작업 전에 별도 감사"가 **미완**으로 남아 있다.
- 재현 방법 또는 실패 시나리오: 2021(또는 이미 완료한 2020)에 F29형 세션이 하나라도 있으면, 그 세션의 각 발화는 **다른 발화의 음성**에 올바른 전사가 강제정렬된다. MFA는 exit 0, TextGrid 수량·coverage 99%↑, tier 구조·0–xmax 연속성·WAV duration 일치까지 전부 통과한다(구조 게이트가 모두 무력). 결과는 "구조적으로 완벽하지만 내용이 전부 틀린" 4-tier이다.
- 연구 결과/자료 무결성 영향: 해당 세션의 phones/words 시간값이 전부 다른 발화의 음성을 가리키므로, 후보 위치 탐색·분절 보조·KOINA 구간 추출·청취 검증 표본이 세션 단위로 오염된다. 세션 단위(=화자 단위) 결측·오염이라 사회변수 분석에 비무작위 편향을 만든다.
- 권장 수정: `audit_mfa_year_readiness.py`에 읽기 전용 검사 추가 — 세션별로 CSV `dur`(=end−start)와 WAV header duration의 잔차(예: >0.025초) 비율을 집계하고, 세션 대응률(<98%)을 hard gate로 둔다(파일럿 v2와 동일 기준). WAV header 읽기는 wave 모듈로 프레임 수만 읽으면 되므로 전수도 수 시간 내 가능하며 D: 읽기 전용이다. 2020·2021 완료본에 대해서도 같은 감사를 소급 실행해 오염 세션 목록을 확정한다.
- 반드시 추가할 시험: 합성 회귀검사 — 같은 세션에서 wav 하나를 옆 발화 길이로 바꾼 fixture가 gate FAIL을 내는지; 정상 세션이 PASS인지.
- 대량 재실행 필요 여부: **감사 결과에 따라 부분 재실행**. 오염 세션이 나오면 해당 세션만 제외 목록(분석 제외표)에 넣거나 재분절 후 그 세션만 재정렬하면 되고, 연도 전체 재실행은 불필요. 오염 0이면 재실행 불요.
- 다른 finding과의 의존성: P2-05(계약 fingerprint)와 함께 2022 이전에 처리 권고.

## P1-02 형태소 tier 결측 처리의 경로 간 불일치 — direct는 20시간 뒤 연도 전체 실패, built-in은 빈 tier를 성공으로 병합

- 범위: MFA | TextGrid | recovery
- 위치: `scripts/python/export_mfa_db_4tier.py:126-128,239-243,267-276` (morpheme_tier_missing이 hard_failures에 포함 → 1건이라도 있으면 연도 status=failed), `scripts/python/realign_eojeol_merge_output.py:110,256-258,288-291` (morphs=None이면 빈 morphemes tier `[(0.0,dur,"")]`로 쓰고 success 판정에 미반영), `scripts/python/audit_mfa_4tier_year.py:148-153` (no_labeled_interval:morphemes → invalid)
- 확신도: high (코드 의미론은 확정) / 실제 결측 발생 수는 medium (데이터 필요)
- 확인한 근거: 두 경로의 형태소 경계 원천은 기존 `06_textgrid_merged`다(`realign_eojeol_merge_output.morpheme_tier`, direct exporter도 같은 함수 재사용). 기존 3-tier의 커버리지는 전 연도 99.94%(SCRIPTS_INDEX:59-61)로 100%가 아니며, 잔여 미회수 중 난정렬 405건 등은 **새 G2P 정렬에서는 성공할 가능성이 높은** 발화들이다. 그런 발화가 1건이라도 정렬되면: ① direct 경로 — `morpheme_tier_missing≥1` → hard_failures>0 → status=failed → 러너 exit 1. 연도 전체가 **정렬·수집이 다 끝난 뒤**(2021 기준 약 18–23시간 후) 실패한다. 이 조건은 MFA 실행 전에 정적으로 계산 가능한데(기존 TextGrid 존재 여부), 사전 게이트가 없다. ② built-in fallback 경로 — 같은 발화를 morphemes tier가 **빈** 4-tier로 만들고 `morph_missing` 카운터만 남긴 채 success·merge_done을 만든다. 이 빈 tier는 이후 `audit_mfa_4tier_year.py`(수동 실행)에서야 invalid로 잡힌다. 즉 같은 입력이 경로에 따라 "연도 실패" 또는 "성공 후 수동 감사 의존"으로 갈라진다. (참고: 2020 실측은 "form·morpheme 누락 0"이었으므로 지금까지는 미발현.)
- 재현 방법 또는 실패 시나리오: 2022에서 과거 난정렬이었다가 G2P로 새로 정렬된 발화 1건 → direct 실행이 마지막 export 단계에서 연도 전체 failed. 또는 어떤 연도를 fallback 경로로 돌리고 독립 감사를 생략하면 빈 morphemes tier가 staging에 merge_done과 함께 남는다.
- 연구 결과/자료 무결성 영향: direct는 fail-closed라 자료 오염은 없지만 밤샘 실행 수십 시간이 조건 1건으로 무효화된다(사용자 피로·재시도 비용). fallback 쪽은 morphemes tier가 비어 있는 발화가 "완료"로 남아 형태소 경계 기반 검색·검토에서 조용히 빠진다(감사를 건너뛰면 발견되지 않음).
- 권장 수정: ① 결측 정책을 하나로 통일한다 — 권장: 결측 발화를 **사전에 열거**해 둘 다 "빈 morphemes tier + 상태 기록"으로 생성하되, 그 목록을 연도 보고서·누락 CSV에 남기고 hard failure에서는 뺀다(연구자가 A2/tagged로 온디맨드 보완 가능, DESIGN_pron_env_search §6의 morph_analysis 방식과 일관). ② 어느 쪽을 택하든 `audit_mfa_year_readiness.py`에 "예상 usable lab 중 기존 형태소 TextGrid 없는 발화 수"를 사전 집계하는 검사를 추가해 MFA 시작 전에 규모를 알게 한다.
- 반드시 추가할 시험: export_mfa_db_4tier에 morpheme 결측 fixture를 넣어 채택한 정책(실패 또는 기록-후-통과)이 재현되는지; merge 경로와 direct 경로가 같은 fixture에서 같은 판정을 내는지 교차 시험.
- 대량 재실행 필요 여부: 불요(기존 산출물은 영향 없음). 정책 변경 후 신규 연도부터 적용.
- 다른 finding과의 의존성: P2-07(연도 간 게이트 자동화)과 함께 처리하면 효과적.

## P2-03 규칙 발음 엔진의 의무 규칙 결손 — ㄷ+히 구개음화가 격음화에 선행 차단되고, 겹받침+ㅎ 격음화 미구현 (실행 확증)

- 범위: pronunciation | CSV
- 위치: `scripts/python/predict_pron.py:105-116` (r_aspiration), `scripts/python/predict_pron.py:125-132` (r_palatalization), `scripts/python/predict_pron.py:219-220` (RULE_ORDER)
- 확신도: high — 리뷰 환경에서 실행해 확인
- 확인한 근거(실측): `굳히다→구티다`(표준 [구치다]), `닫히다→다티다`([다치다]), `묻히다→무티다`([무치다]) — 격음화(1순위)가 ㄷ+ㅎ을 먼저 ㅌ로 축약해 구개음화(3순위)의 적용 환경을 없앤다(r_palatalization은 `nxt[0] in ('ㅇ','ㅎ')`로 '히'를 처리하도록 작성돼 있으나 도달 불가). 또 `앉히다→안히다`([안치다]), `넓히다→널히다`([널피다]), `읽히다→익히다`([일키다]), `밝히다→박히다`([발키다]) — r_aspiration의 역방향 분기가 `NEUTRALIZE.get(c1)`으로 단일 종성만 처리해 ㄵ·ㄼ·ㄺ 등 겹받침+ㅎ 축약(표준발음법 12항, 의무)이 통째로 빠져 있고, 이후 겹받침 단순화가 잘못된 쪽(ㄺ→ㄱ)을 남긴다. `--selftest` 30종에는 이런 사례가 하나도 없다(축하·좋다·같이·굳이만 존재). 이 결손은 '-히-' 피동·사동이라는 고빈도·생산적 부류 전체에 체계적으로 작용한다.
- 재현 방법 또는 실패 시나리오: `python predict_pron.py --demo 닫히다` → `다티다`. 전량 CSV의 `pron_pred_*`·`pron_reference_*` 열에서 해당 부류가 전부 잘못된 기준 발음을 갖는다.
- 연구 결과/자료 무결성 영향: 규칙 발음열은 "후보 검색·비교 기준"층이다(DESIGN_pron_env_search §1). 격음화·구개음화 환경 검색, 규칙발음–실현 대조를 이 열로 하면 '-히-' 부류에서 기준선 자체가 틀려 후보 누락·오분류를 만든다. 실현 판정 자체는 사람이 하므로 정본 오염은 아니지만, 검색층의 체계적 편향이다. (MFA lab은 한글 표기만 쓰므로 정렬 입력에는 영향 없음.)
- 권장 수정: r_aspiration에 겹받침+ㅎ 축약(ㄶ·ㅀ 외에 ㄵ→ㄴㅊ, ㄺ→ㄹㅋ, ㄼ→ㄹㅍ)을 추가하고, ㄷ(ㅌ)+히는 구개음화가 격음화보다 먼저 적용되도록 순서 예외를 두거나 r_aspiration에서 `nxt[1]=='ㅣ' and c1 in (ㄷ,ㅌ)`일 때 양보하게 한다. 변경은 언어학적 판단이므로 규칙 인벤토리·순서 확정은 사용자 승인 후에 적용할 것.
- 반드시 추가할 시험: `_CASES_HANGUL`에 굳히다/닫히다/묻히다/앉히다/넓히다/밝히다/읽히다(+대조로 좋다·많다·싫어) 추가.
- 대량 재실행 필요 여부: **CSV 열 갱신 필요**하나, 어차피 사전 발음 결합을 위한 검색층 재생성이 예정돼 있으므로(RUNBOOK "pre-MFA v1은 최종 연구용 CSV가 아님") 그때 새 rule_version으로 함께 재생성하면 된다. 별도 긴급 재실행 불요. MFA·TextGrid 재실행 불요.
- 다른 finding과의 의존성: 공통 발음 자원(§4.3) 구현 시 rule_version 고정과 함께.

## P2-04 미해결 숫자·기호 발화의 lab이 어절을 통째로 버리지 않고 한글만 남겨, 잘못된 부분 전사로 강제정렬됨 (실행 확증)

- 범위: MFA | pronunciation
- 위치: `scripts/python/realign_eojeol_build_corpus.py:54-61` (form_to_lab), `scripts/python/realign_eojeol_build_corpus.py:292-307` (unresolved는 카운터만; lab은 그대로 생성)
- 확신도: high (동작은 실측) / 영향 규모는 medium (2021 기준 unresolved 수치는 CSV에 있으나 리뷰 환경에서 미확인)
- 확인한 근거(실측): `form_to_lab("3시요") == "시요"`, `form_to_lab("무조건 1층으로 된 집") == "무조건 층으로 된 집"`. 즉 원전사로 회복되지 못한(`unresolved_symbol`) 발화는 화자가 발음한 수사([세]/[일])가 전사에서 빠진 채 정렬된다. "추측 금지" 정책 자체는 문서화돼 있으나(RUNBOOK), 그 결과물인 lab이 "부분적으로 틀린 전사"라는 사실은 발화 단위로 하류(4-tier·검색층)에 전파되지 않는다 — lab 보고서·CSV에 집계·상태열은 있지만 TextGrid 자체나 누락 inventory에는 표시가 없다.
- 재현 방법 또는 실패 시나리오: 숫자 포함 발화(예: "3시요")의 phones tier에서 [세]에 해당하는 음성 구간이 인접 어절 음소나 무음으로 흡수돼 경계가 왜곡된다. 이 발화가 경음화·비음화 후보로 검색되면 왜곡된 시간값으로 청취 구간을 안내한다.
- 연구 결과/자료 무결성 영향: 후보 수집·KOINA 구간 추출 시 해당 발화의 시간 좌표 신뢰도가 낮다. CSV의 `pron_reference_status=unresolved_symbol`로 필터 가능하므로 연구자가 걸러낼 수는 있으나, 그 규약이 문서 한 곳(RUNBOOK)에만 있다.
- 권장 수정: ① 분석 제외/주의 표: 연도별 unresolved 발화 ID 목록을 lab 보고서 옆에 CSV로 고정(이미 카운터는 있으므로 ID만 추가). ② 후보 검색·bundle 도구가 기본으로 `unresolved_symbol` 발화에 경고 표지를 붙이게 한다. ③ (언어학적 결정 필요) 어절 내 숫자·라틴이 섞인 어절은 한글만 남기는 대신 어절 전체를 lab에서 빼는 방안과의 정렬 품질 A/B를 소표본으로 비교 — 현행은 "없는 소리를 붙이는" 대신 "있는 소리를 숨기는" 선택이므로 어느 쪽이 분절 보조에 덜 해로운지 실측 근거를 남길 것.
- 반드시 추가할 시험: form_to_lab의 혼합 어절 케이스(숫자+한글, 라틴+한글)를 test_realign_eojeol_build_corpus에 고정하고, 채택 정책이 바뀌면 시험도 갱신.
- 대량 재실행 필요 여부: 현행 정책 유지 시 불요. 정책 변경(어절 제외) 채택 시 공통 발음 자원 재정렬(§4.3의 2020·2021 재실행 정책)에 편승.
- 다른 finding과의 의존성: P2-05·공통 발음 자원 설계와 함께 결정.

## P2-05 정렬 입력계약에 사전·G2P·음향모델·MFA 판본 fingerprint가 없음

- 범위: MFA | recovery | pronunciation
- 위치: `scripts/python/realign_eojeol_build_corpus.py:104-123` (input_contract 구성 필드), `scripts/run_eojeol_realign.ps1:471-483` (marker에 `g2p_model='korean_mfa'` 이름만 기록), `scripts/preflight_eojeol_realign.ps1:92-100` (모델은 존재만 확인)
- 확신도: high (코드로 확정; 문서 스스로도 인지 — DESIGN_common_pron §1, MONITOR_2021 11:23 절)
- 확인한 근거: input_contract_id는 search master meta SHA256·세션 수·정책 문자열의 해시다. `korean_mfa.dict`/G2P zip/acoustic zip의 SHA256은 계약·marker·보고서 어디에도 없다. verify_mfa_install.py는 **MFA 소스 패치**의 fingerprint만 기록한다. 따라서 연도 사이(예: 2021과 2022 사이)에 모델 파일이 교체·갱신되어도 temp resume 계약과 완료 marker는 이를 구분하지 못한다.
- 재현 방법 또는 실패 시나리오: 2022 전에 누군가 MFA 모델을 재다운로드(버전 갱신) → 2022는 2020·2021과 다른 발음 집합으로 정렬되지만 모든 계약·marker는 "같은 입력"이라고 기록 → 6개년 비교가능성이 조용히 깨진다. 같은 연도 내에서도 clean 재시작 전후 모델이 바뀌면 한 연도 안에 두 기준이 섞일 수 있다.
- 연구 결과/자료 무결성 영향: 연도 간 phones 층의 방법론적 동일성(이 연구의 핵심 전제)이 파일 이름 신뢰와 수동 규율에만 의존한다.
- 권장 수정: 공통 발음 자원 release(§4.3 설계의 계약 필드 9종)를 기다리지 말고, 지금 바로 최소 3개 — `acoustic_model_sha256`·`base_dictionary_sha256`·`g2p_model_sha256` — 를 input_contract payload와 done marker details에 추가한다(sha256_file 재사용, 수 초 비용). 기존 2020·2021 marker는 소급 수정하지 말고, 현재 설치본의 hash를 별도 기록 파일로 남겨 baseline과 연결한다.
- 반드시 추가할 시험: 모델 파일 hash가 바뀐 fixture에서 기존 temp가 stale로 격리되고 기존 marker가 재사용되지 않는 회귀검사.
- 대량 재실행 필요 여부: 불요(기록 강화). 단 2020·2021 당시 모델 hash를 지금 설치본 기준으로 즉시 실측·기록해 두지 않으면 소급 증명이 불가능해짐 — 빠를수록 좋음.
- 다른 finding과의 의존성: DESIGN_common_pronunciation_lexicon 구현의 선행 최소분.

## P2-06 동결 CSV 밖 발화의 고아 lab이 built-in 병합 경로에서는 차단되지 않음

- 범위: MFA | CSV | TextGrid
- 위치: `scripts/python/realign_eojeol_merge_output.py:212-214` (form을 **동결 pre-MFA CSV가 아니라 01_bareun_raw에서** 로드), `scripts/python/realign_eojeol_build_corpus.py:264-307` (CSV에 존재하는 행만 순회 — CSV에 없는 발화의 기존 lab은 재작성·archive 대상이 아님), `scripts/python/audit_mfa_year_readiness.py:277-294` (lab_not_expected_with_wav를 잡는 유일한 검사이나 수동 실행), `scripts/python/audit_mfa_year_readiness.py:356-357` (gate 실패여도 exit 0)
- 확신도: medium (경로는 코드로 확정; 현실 트리거 확률은 낮음 — 2021 실측 lab_not_expected_with_wav=0 확인)
- 확인한 근거: lab은 wav 옆 제자리 파일이라 입력계약 스코프 밖에 있다. 어떤 발화가 이전 계약에서는 usable이었다가 새 pre-MFA CSV에서 빠지면(입력 정책 변화·행 제외) 그 발화의 lab은 아무도 지우지 않는다. MFA는 그 lab을 정렬하고, ① direct 경로는 `forms.get(name) is None → form_missing → 연도 failed`로 차단하지만(export_mfa_db_4tier.py:122-124 — 올바른 fail-closed), ② built-in 병합은 bareun 전체(모든 발화의 초집합)에서 form을 찾으므로 그대로 4-tier를 만들어 성공 처리한다. 사후 `audit_mfa_4tier_year.py`도 TextGrid↔**lab** 집합만 대조하므로(lab이 남아 있는 한) 통과한다. 즉 fallback 경로에서는 "TextGrid ⊆ 동결 CSV" 계약을 어떤 자동 게이트도 보증하지 않는다.
- 재현 방법 또는 실패 시나리오: RunId v2에서 특정 발화가 CSV에서 제외되도록 입력 정책이 바뀌었는데 v1 시절 lab이 남은 상태에서 fallback 경로 실행 → staging에 동결 CSV에 없는 발화의 4-tier가 생기고 merge_done이 찍힘.
- 연구 결과/자료 무결성 영향: 검색층(CSV)과 시간층(TextGrid)의 집합 불일치 — "CSV에서 검색→TextGrid 수집" 흐름에서는 실해가 없지만, TextGrid 쪽에서 출발하는 전수 통계·coverage 계산이 오염되고 provenance 계약이 깨진다.
- 권장 수정: ① realign_eojeol_build_corpus가 세션 폴더를 스캔해 "현재 CSV에 없는 utt의 lab"을 stale과 동일하게 `archive_stale_labs/<계약>`로 이동(이미 있는 archive 경로·함수 재사용). ② realign_eojeol_merge_output의 form 로더를 동결 CSV 우선으로 바꾸거나 최소한 동결 CSV 부재 발화를 failed로 계상. ③ audit_mfa_year_readiness의 main이 gates 실패 시 exit 1을 반환하게 한다.
- 반드시 추가할 시험: CSV에 없는 utt의 lab+wav fixture → build_corpus가 archive하는지, merge가 실패로 잡는지.
- 대량 재실행 필요 여부: 불요 — 2021 실측 0건 확인. 향후 계약 전환 시 위험이므로 예방 수정.
- 다른 finding과의 의존성: P1-02(경로 간 정책 통일)와 같은 파일들.

## P2-07 다년 연쇄 실행 시 연도 사이에 독립 QC 게이트가 강제되지 않음

- 범위: MFA | recovery | docs
- 위치: `scripts/run_pre_mfa_bulk_safe.ps1:167-207` (연도 loop — 이전 연도 exit 0 + marker만 확인), `scripts/python/preflight_next_year_after_qc.py` (강력한 결합 게이트이나 어떤 러너도 호출하지 않음 — 수동), `scripts/python/audit_mfa_4tier_year.py` (동일 — 수동)
- 확신도: high
- 확인한 근거: 커밋 e632d2a("gate 2022 on verified 2021 QC artifacts")의 구현은 별도 스크립트로만 존재한다. `-Years 2021,2022` 또는 기본값(6개년 전부)으로 wrapper를 부르면, 2021 merge_done 직후 2022가 **독립 4-tier 감사·표본 청취 없이** 시작된다. 현재 안전은 "정식 명령은 한 연도만"이라는 RUNBOOK 규율에 의존한다. (PauseAfterYear·emergency pause가 있으나 기본 동작이 아님.)
- 재현 방법 또는 실패 시나리오: 사용자가 피로한 상태에서 6개년 명령을 실행 — 2021 산출에 문제가 있어도(예: P1-01형 오염) 2022~2025가 같은 조건으로 이어져 수일의 연산이 미검증 상태 위에 쌓인다.
- 연구 결과/자료 무결성 영향: 산출물 자체보다 "검증 전 확산" 위험. 사고 등록부의 재발 방지 원칙("부분 성공을 성공으로 승격하지 않음")의 연도 간 버전이 빠져 있다.
- 권장 수정: run_eojeol_realign.ps1 시작부(또는 wrapper의 연도 loop)에서, 직전 연도의 done marker가 존재하면 `preflight_next_year_after_qc.py` 통과 보고서를 요구하고, 없으면 exit — 명시적 `-SkipInterYearQc` 스위치로만 우회 가능하게. 기본 `-Years`도 전체 6개년 대신 단일 연도 필수로 바꾸는 편이 현재 운영 방침과 일치.
- 반드시 추가할 시험: test_powershell_safety.ps1의 필수 문자열 목록에 게이트 호출 존재를 추가.
- 대량 재실행 필요 여부: 불요.
- 다른 finding과의 의존성: P1-01·P1-02 게이트를 이 지점에 함께 편입 가능.

## P2-08 file_meta 정규화 열이 없으면 전량 CSV가 '메타 결측 0'으로 통과할 수 있음 (게이트 비대칭)

- 범위: CSV
- 위치: `scripts/python/build_search_master.py:207-214` (`m.get(c, MISSING)` — 세션이 메타에 있으면 열 부재 시 '미상'을 채우되 stats 미증가), `scripts/python/build_search_master.py:367` (validate는 값=='미상'을 세고, 신규 build는 세션 부재만 셈), `scripts/python/preflight_search_master.py:211-212` (`category_norm`·`discourse_mode` 헤더 검사의 반환값을 ok_all에 반영하지 않고 버림)
- 확신도: medium (조건부 — 현재 file_meta.csv는 정규화 열을 포함하므로 미발현; 구판 복원·롤백 시나리오에서 발현)
- 확인한 근거: F27 롤백 절차(DESIGN_safe_pre_bulk §6)나 구판 file_meta로 되돌린 상태에서 전량을 빌드하면: preflight는 경고만 내고 통과 → build_row는 모든 행의 `category_norm` 등에 '미상'을 채우면서 stats["meta_missing"]는 0 유지 → `meta_ok=True`로 검증 통과·success 기록. 반대로 같은 산출물을 재실행(resume)하면 validate_session_csv가 '미상' 값을 세어 meta_missing이 폭증 → 같은 데이터가 fresh는 통과, resume은 실패하는 비대칭.
- 재현 방법 또는 실패 시나리오: 위 그대로. 테스트로도 재현 가능(메타 dict에서 category_norm 키 제거).
- 연구 결과/자료 무결성 영향: 사용역·담화양식 변수가 전량 '미상'인 CSV가 success manifest를 달고 나올 수 있음 — F27이 잡으려 했던 "비무작위 결측" 부류의 재발 경로.
- 권장 수정: ① preflight의 해당 check 반환값을 `ok_all &=`로 반영. ② build_row에서 키 부재로 '미상'을 채울 때 별도 카운터(`meta_column_missing`)를 증가시키고 verdict에 포함. ③ fresh/resume의 meta_missing 정의를 통일(값 기준으로).
- 반드시 추가할 시험: category_norm 키 없는 meta로 build_session → 실패(또는 전용 카운터>0)임을 고정하는 단위시험.
- 대량 재실행 필요 여부: 불요(현재 데이터는 정상 열 보유; 감사 보고서로 확인됨).
- 다른 finding과의 의존성: 없음.

## P2-09 locate_utt의 격리(quarantine) 조회 경로가 실제 격리 구조와 불일치 — 격리 발화를 '격리 아님'으로 보고

- 범위: recovery | CSV
- 위치: `scripts/python/locate_utt.py:59` (`D:\mfa_eojeol\quarantine\{year}\{utt}.wav` — 평면 + 드라이브 하드코딩), `scripts/python/quarantine_bad_wavs.py:87-89` (격리는 **세션 상대경로 보존**: `quarantine/{year}/{session}/{utt}.wav`)
- 확신도: high (두 코드의 경로 규약 불일치는 확정; 실기 재현은 미실행)
- 확인한 근거: 세션 하위폴더 구조(현재 6개년 표준)에서 격리된 wav는 `quarantine/{year}/{session}/…`에 놓이는데 locate_utt는 `{year}/…` 평면만 본다. 따라서 `fetch_audio_for_search.py:65-67`의 "격리됨" note도 세션 구조 연도에서는 절대 붙지 않는다.
- 재현 방법 또는 실패 시나리오: 격리된 발화 ID로 locate/fetch 실행 → wav [X], 격리 표시 없음 → 연구자는 "원본 손실"로 오인하거나 원인 추적에 시간을 낭비.
- 연구 결과/자료 무결성 영향: 자료 오염은 없음. 결측 사유 추적(분석 제외표 작성)의 정확성 저하.
- 권장 수정: locate_utt에서 `P("mfa_state")/"quarantine"/year/session/f"{utt}.wav"` 우선 + 평면 폴백; 하드코딩 제거.
- 반드시 추가할 시험: 세션 구조 fixture에서 격리 후 locate가 quarantine 키를 반환하는지.
- 대량 재실행 필요 여부: 불요.
- 다른 finding과의 의존성: 없음.

## P3-10 감사 스크립트 2종이 판정 실패에도 exit 0을 반환

- 범위: recovery | docs
- 위치: `scripts/python/audit_search_master.py:684`, `scripts/python/audit_mfa_year_readiness.py:356-357`
- 확신도: high
- 확인한 근거: 두 스크립트 모두 verdicts/gates 실패와 무관하게 return 0. 대조적으로 audit_mfa_4tier_year·preflight_next_year_after_qc·export_mfa_db_4tier는 status를 exit code로 반환한다. 러너·자동화에 배선되는 순간 무의미한 게이트가 된다.
- 재현 방법 또는 실패 시나리오: P2-07 권고대로 러너에 배선 시 거짓 통과.
- 연구 결과/자료 무결성 영향: 현재는 사람 판독이라 실해 없음; 자동화 시 거짓 통과.
- 권장 수정: `--strict`(기본 on) 시 verdicts/gates 실패 → exit 1.
- 반드시 추가할 시험: 실패 fixture에서 exit code 검증.
- 대량 재실행 필요 여부: 불요.
- 다른 finding과의 의존성: P2-07 선행 조건.

## P3-11 MFA가 'Done!' 문구를 낸 뒤 정리 국면에서는 heartbeat JSONL 기록이 중단됨

- 범위: performance | recovery
- 위치: `scripts/run_eojeol_realign.ps1:787` (`continue`)이 `scripts/run_eojeol_realign.ps1:807`의 Write-JsonLine보다 앞
- 확신도: high (코드 흐름 확정; 지속 시간은 데이터 의존)
- 확인한 근거: 완주 직후 오살 방지 가드가 kill 판정뿐 아니라 heartbeat 기록까지 건너뛴다. 대규모 연도의 마지막 flush·DB 종료가 길어지면 모니터링 규약("생존 판정은 heartbeat mtime")과 충돌 — 운영자가 정지로 오인해 수동 개입할 유인이 생긴다(이 프로젝트의 반복 사고 유형).
- 재현 방법 또는 실패 시나리오: Done! 이후 heartbeat mtime이 수십 분 동결 → MONITOR 절차상 "이상"으로 보임.
- 연구 결과/자료 무결성 영향: 자료 무결성 영향 없음. 운영 오판 위험.
- 권장 수정: continue 대신 kill 판정만 억제(`$kill=$false`)하고 heartbeat는 계속 기록(`phase='finalizing'` 표시).
- 반드시 추가할 시험: test_powershell_safety의 필수 문자열에 finalizing 기록 추가.
- 대량 재실행 필요 여부: 불요.
- 다른 finding과의 의존성: 없음.

## P3-12 direct 모드의 marker 직전 crash 창에서 preflight가 잘못된 복구 지시를 냄

- 범위: recovery
- 위치: `scripts/run_eojeol_realign.ps1:942-968` (partial→final 이동 후 align/merge marker 순차 기록), `scripts/preflight_eojeol_realign.ps1:299` (`align_done인데 원출력 없음 → "마커 삭제 후 재정렬 필요"` FAIL)
- 확신도: medium (창은 수 ms~수 초로 작음)
- 확인한 근거: direct 모드는 MFA 원출력(mfa_eojeol_out)을 만들지 않으므로, final 이동·align marker 기록 후 merge marker 기록 전에 crash하면 preflight [7]의 규칙이 "재정렬 필요"라는 built-in 전제를 그대로 적용한다. 지시를 따르면 이미 완성된 final staging이 있는 연도를 불필요하게 재정렬하게 된다(러너 자체는 `scripts/run_eojeol_realign.ps1:903` 가드로 fail-closed).
- 재현 방법 또는 실패 시나리오: 위 crash 창 → preflight FAIL 메시지의 지시대로 marker 삭제·재정렬.
- 연구 결과/자료 무결성 영향: 오염 없음, 시간 낭비·혼란.
- 권장 수정: preflight [7]에서 align marker의 `export_mode=direct_db_4tier`이면 원출력 부재를 FAIL 사유에서 제외하고 "final staging·merge marker 상태 확인" 안내로 대체. 러너도 direct 구간의 두 marker 기록을 단일 원자 기록으로 합치면 창이 사라짐.
- 반드시 추가할 시험: direct marker fixture로 preflight 분기 검증.
- 대량 재실행 필요 여부: 불요.
- 다른 finding과의 의존성: 없음.

## P3-13 direct exporter가 개별 실패(failed)의 원인·예시를 보고서에 남기지 않음

- 범위: MFA | recovery
- 위치: `scripts/python/export_mfa_db_4tier.py:138-140` (bare `except Exception: counts["failed"] += 1; continue`)
- 확신도: high
- 확인한 근거: alignment_missing은 예시 20건을 남기지만 failed는 수만 남는다. 연도 전체가 failed=1로 실패했을 때 어느 발화·무슨 예외인지 보고서로는 알 수 없다(built-in merge는 failed_files 목록을 남김 — 비대칭).
- 재현 방법 또는 실패 시나리오: write_4tier에서 예외 1건 → 연도 failed인데 원인 발화 불명.
- 연구 결과/자료 무결성 영향: fail-closed라 오염 없음; 디버깅 비용 증가.
- 권장 수정: failed_examples(utt_id + 예외 1줄) 최대 N건 수집.
- 반드시 추가할 시험: write_4tier 강제 예외 fixture에서 예시 포함 확인.
- 대량 재실행 필요 여부: 불요.
- 다른 finding과의 의존성: P1-02와 같은 파일.

## P3-14 최소 의미번호 자동 선택 lexicon 헬퍼가 여전히 존재하며 셀프테스트가 그 동작을 고정함

- 범위: pronunciation | docs
- 위치: `scripts/python/predict_pron.py:396-417` (build_lexicon_index — 다의어 최소 sense_no 채택), `scripts/python/predict_pron.py:478-483` (selftest가 이 동작을 검증)
- 확신도: high
- 확인한 근거: DESIGN_pron_env_search §4.2는 "가장 작은 sense_no 자동 선택 방식은 최종 인프라에 사용하지 않는다"고 확정했고, 현재 builder는 이 헬퍼를 배선하지 않음(audit_search_master.audit_lexicon_wiring로 확인 — 의도된 False). 그러나 import 가능한 공개 헬퍼로 남아 있고 셀프테스트가 통과 도장을 찍어 주므로, 향후 결합 작업에서 실수로 재사용될 유인이 있다.
- 재현 방법 또는 실패 시나리오: 향후 사전 결합 구현자가 기존 헬퍼를 그대로 배선 → 다의어 발음이 임의(최소 의미번호)로 선택되는 P류 위험 재발.
- 연구 결과/자료 무결성 영향: 현재 없음(휴면 확인); 장래 위험.
- 권장 수정: docstring에 폐기 예정·사용 금지 사유 명시, `_deprecated` 개명 또는 사용 시 경고. 새 색인(§4.3 registry) 구현 시 제거.
- 반드시 추가할 시험: 불요(정책 표시가 목적).
- 대량 재실행 필요 여부: 불요.
- 다른 finding과의 의존성: 공통 발음 자원 구현.

## P3-15 export queue 패치의 blocking get은 producer 조기 사망 시 무한 대기로 바뀜 (watchdog 의존)

- 범위: MFA | performance
- 위치: `scripts/python/patch_mfa_export_queue.py:42-51` (NEW_WORKER — timeout 없는 `get()`; sentinel만이 종료 신호)
- 확신도: medium (MFA 내부 예외 경로는 소스 미보유로 추론)
- 확인한 근거: 종전 1초 timeout+finished_adding 경쟁(15시간 57분 직렬화 사고)의 올바른 수정이지만, producer가 sentinel을 넣기 전에 예외로 죽으면 worker가 영구 대기한다. 이때 회수 수단은 러너 watchdog(정렬 국면 카운터 30분 정지)뿐이다. 실측 3,330·21,965건 검증 통과가 커밋된 보고서로 존재하므로 정상 경로는 입증됨.
- 재현 방법 또는 실패 시나리오: export batch 수집 중 producer 예외 → worker hang → 30분 뒤 watchdog kill → clean 재시도 루프.
- 연구 결과/자료 무결성 영향: 오염 없음; 시간 손실 한정.
- 권장 수정: (선택) 긴 timeout(예: 300초) get + finished_adding 재확인 조합 — 단 MFA 설치 패치 변경이므로 검증 비용과 비교해 결정. 현행 유지 시 문서에 "이 hang은 watchdog이 회수" 명시로 충분.
- 반드시 추가할 시험: 기존 test_mfa_export_queue_race 유지.
- 대량 재실행 필요 여부: 불요.
- 다른 finding과의 의존성: 없음.

## P3-16 preflight_next_year_after_qc가 direct 모드 전용임이 문서화되지 않음

- 범위: docs | recovery
- 위치: `scripts/python/preflight_next_year_after_qc.py:172-189` (align·merge marker의 `export_mode == "direct_db_4tier"`를 필수로 요구)
- 확신도: high
- 확인한 근거: 2020처럼 built-in 경로로 완료한 연도는 이 게이트를 원리적으로 통과할 수 없다(별도 검증 절차 필요). PLAN_2022·SCRIPTS_INDEX에는 이 제약이 명시돼 있지 않다.
- 재현 방법 또는 실패 시나리오: built-in 연도를 prior로 게이트 실행 → marker identity에서 항상 failed → 원인 혼동.
- 연구 결과/자료 무결성 영향: 없음(fail-closed); 혼란만.
- 권장 수정: docstring·PLAN 문서에 "direct 연도 전용, built-in 연도는 audit_mfa_4tier_year + merge 보고서로 대체 검증" 명시. (P2-07 구현 시 분기 필요.)
- 반드시 추가할 시험: built-in marker fixture의 명시적 실패 사유 메시지.
- 대량 재실행 필요 여부: 불요.
- 다른 finding과의 의존성: P2-07.

## P3-17 소소한 표기·경로·기록 비일관 묶음

- 범위: docs | CSV | performance
- 위치·내용:
  1. `scripts/python/build_search_master.py:189-256` — JSON에 없는 발화의 `original_form` 등은 '미상'으로 채우나 `start/end`는 빈 문자열로 남음(결측 표기 비일관).
  2. `scripts/python/build_search_master.py:51-76` — BUILD_PROVENANCE의 바른 engine_version이 "미고정"인 채 전량 manifest에 복사됨(METHODS TODO와 동일; 논문 인용 전 확정 필요).
  3. `scripts/python/audit_mfa_year_readiness.py:308-317` — wav-root·source-pcm 기본값이 paths.json을 거치지 않는 하드코딩(F24 원칙과 불일치; CLI 인자로 우회 가능).
  4. `scripts/python/bareun_dialogue_full.py:251-258` — `_write_speakers`가 비원자 덮어쓰기(레거시·실행 완료 스크립트; 재실행 시에만 위험).
  5. `scripts/python/audit_search_master.py:571-613` — `missing_json_sessions`가 어떤 verdict에도 반영되지 않음(집계는 존재).
  6. `scripts/python/stitch_session.py:60-83` — parse_tg_tiers가 라벨의 `""` unescape를 생략한 채 esc()로 재이스케이프(따옴표 포함 라벨의 이중 이스케이프 가능; 실코퍼스에서는 드묾).
  7. `scripts/run_pre_mfa_bulk_safe.ps1:79-101` — PID lock 생존 판정이 프로세스 이름을 확인하지 않아 PID 재사용 시 오탐 가능(드묾; 오탐 방향은 안전한 쪽).
- 확신도: high(각 항목 코드 확인) / 권장 수정: 각 1–3줄 수준 / 대량 재실행: 불요 / 의존성: 없음.

---

## §4.1/§4.2/§4.3 검토 질문에 대한 답 (finding 외 확인 사항)

**§4.1 CSV — ID·순서 보존**: `validate_session_csv`가 utt_id 순서·개수·중복을 바른 원본과 강제 일치시키고(build_search_master.py:347-438), audit_search_master가 JSON↔바른↔마스터를 행 병렬로 전수 대조한다(zip_longest). 세션 좌표는 파일 stem 정본 + 내부 doc/utt ID 접두 검증(build_metadata_index.py:150-166)으로 F27이 코드에 반영됨을 확인. form 빈 54,641행 제외 정책은 입력단(iter_utterances)과 감사(json_missing_in_source의 form_empty 분해)가 일관.

**§4.1 lexicon 조인 위험(Q3)**: 현재 v1 CSV에는 사전 발음 조인이 **없다**(빌더에 lexicon 배선 없음 — audit_lexicon_wiring이 이를 명시적으로 False로 보고). 따라서 행 폭증·첫 의미 임의 선택은 현재 산출물에는 존재하지 않으며, 위험은 P3-14의 휴면 헬퍼와 향후 결합 단계에 있다. 설계 문서(§4.2 조회 우선순위·dedup 색인)는 이 위험을 정확히 겨냥하고 있고 타당하다.

**§4.1 Parquet(Q6)**: `build_search_parquet.py`는 미작성(SCRIPTS_INDEX:107)이라 검토 대상이 없다. provenance 열(출처·status·rule_version)을 스키마에 1:1로 옮기고 스키마 버전을 명시하라는 설계 원칙만 재확인한다.

**§4.2 거짓 성공 경로(Q2)**: 러너의 exit 0+TextGrid 0건 차단(run_eojeol_realign.ps1:852-871), 99% 수량 게이트(:984-1005), 병합 부분실패 exit 1(realign_eojeol_merge_output.py:301-314), marker의 연도·단계·계약·경로 검증(Read-DoneMarker)까지 — 문서(F08·F21·F22)와 코드가 일치한다. 남은 구멍은 P1-01(구조가 아닌 **내용**의 거짓 성공)과 P2-06뿐이다.

**§4.2 direct 동등성(Q5)**: `compare_textgrid_tiers.py`는 파일 집합+전체 tier 라벨·시간(6자리 반올림)을 전수 비교하며, 커밋된 보고서 실측값(21,962/21,962 identical, 결측 0)이 AUDIT 문서 주장과 정확히 일치함을 확인했다. 주의: 동등성 표본은 morpheme 결측 0인 세션들이었으므로 P1-02의 결측 케이스 동작 차이는 이 검증이 커버하지 않는다.

**§4.2 성능(Q7)**: 병목 재설계(blocking queue+sentinel, direct 4-tier)는 실측 근거가 커밋돼 있다(73.983초/21,962). 남은 관찰: ① 4-tier 개별 파일마다 staged write+fsync(pipeline_common.py:69-70) — USB SSD에서 fsync가 파일당 지배 비용이나, 실측 처리율(~300/s)이면 2021 규모 약 77분으로 수용 범위. 안전성을 낮추는 배칭은 권하지 않음. ② exporter의 세션별 스레드 4개+세션별 CSV 로드는 구조상 무난. ③ watchdog은 카운터·단계 인지 기반으로 재설계돼 과거 오살 사고 유형을 회피(P3-11의 기록 공백만 남음).

**§4.3 공통 발음 자원 설계 비판 검토**: 설계 자체는 이 리뷰의 요구(출처 보존 long format, `pron_g2p`를 사전 등재로 오인 금지, 다의·품사 crosswalk 분리, 대표 발음 덮어쓰기 금지, .dict 파생물 분리, A/B 게이트, 재정렬 시 새 run_id)를 정확히 담고 있고, `lexicon_enriched` 664,596 무발음행의 `urimal_id` 일의 대응 실측(미대응·복수 대응 0)도 문서에 근거로 남아 있다. 비판적으로 보완할 점: ① fingerprint 계약(§5)이 "구현 후"로 미뤄져 있는데 최소 3종은 지금 필요(P2-05). ② 정책 B의 복수 발음 상한·충돌 계측은 "필요하면"이 아니라 **필수 산출물**로 못 박을 것 — MFA word 키 사전에서 후보 폭증은 정렬 경계 이동으로 직결되며, A/B 비교의 "word/phone 경계 이동 분포" 항목이 그 계측 지점이므로 서로 연결해 문서화하면 된다. ③ "진행 중인 G2P는 반환 전까지 DB에 commit되지 않는다"(MONITOR_2021 11:23)는 MFA 내부 동작 주장으로, 리뷰 환경에서 검증 불가 — 소스 확인 기록(파일·행)을 문서에 남겨 두기를 권함. ④ 2021 baseline v0 DB에서 word–pronunciation을 추출해 seed로 쓰는 계획은 P2-05의 모델 hash 실측 기록이 선행돼야 "어떤 G2P의 출력인지"를 증명할 수 있다.

**문서 주장 역추적 결과**: 표본 추출한 정량 주장 — 21,962 전수 동등(불일치 0), 2021 lab 일치 1,335,015/불일치 38,320/누락 186/reference 변경 38,529, 2025 stale lab 9, 연도별 세션·행 수 — 모두 커밋된 outputs/reports JSON과 일치했다. 문서가 코드보다 앞서가는 서술(과장)은 발견하지 못했고, 오히려 미구현·미고정 항목(--coverage 차단, engine_version 미고정, fingerprint 부재)을 문서가 스스로 명시하는 패턴이었다.

---

## 마지막 요약표

| 항목 | 내용 |
|---|---|
| 실제 검토한 파일 | 위 헤더 files_actually_inspected 목록(문서 12·코드 30·테스트 3 정독 + 보고서 JSON 4 수치 대조; build_stratified_mfa_review_bundle·merge_textgrid_v2·retrofit는 부분 정독) |
| 실행한 검사 | py_compile 전체 통과 · pytest 59/59 통과 · predict_pron --selftest 30/30 · predict_pron -히- 프로브 7건(전부 표준발음과 불일치 실측) · form_to_lab 프로브 3건 · 동등성/준비도 보고서 JSON 수치 대조(문서와 일치) · pwsh 부재로 PowerShell 시험은 미실행(정독 대체) |
| P0/P1/P2/P3 수 | P0 0 / P1 2 / P2 7 / P3 8 |
| 먼저 고칠 5개 (의존순서) | ① P1-01 CSV–WAV duration 잔차 감사(2020·2021 소급 + 2022 사전 게이트) ② P2-05 모델 3종 SHA256을 입력계약·marker에 추가(+현 설치본 hash 즉시 실측 기록) ③ P1-02 형태소 결측 사전 집계 + 경로 간 정책 통일 ④ P2-07 연도 간 QC 게이트를 러너에 강제(P3-10 exit code 수정 포함) ⑤ P2-03 규칙 엔진 -히- 계열 수정+selftest(다음 검색층 재생성에 편승) |
| 추가 데이터가 있어야 판단할 항목 | ① F29형 세션의 전수 규모: 연도별 CSV dur↔WAV header duration 잔차 통계(읽기 전용) ② 연도별 "정렬 예상 발화 중 기존 형태소 TextGrid 없는 수"(P1-02 규모 확정) ③ 연도별 unresolved_symbol 발화 수·분포(P2-04 영향 규모) ④ 현재 설치 korean_mfa 모델 3종의 SHA256(P2-05 baseline 증빙) |
| 현재 대량 실행을 막아야 하는가 | **진행 중인 2021은 막지 않음**(no) — direct 경로는 fail-closed이고 2021 lab 위생은 실측 0건으로 확인됨. **단 2022 이후 신규 연도 시작은 P1-01·P1-02·P2-05 처리(또는 최소한 읽기 전용 감사 2종 실행) 전까지 보류 권고**(conditional yes) — 근거: 세 항목 모두 실행 전 저비용으로 확인 가능하며, 미확인 시 20시간급 실행이 내용 오염(P1-01) 또는 말단 실패(P1-02)로 끝날 수 있음 |
