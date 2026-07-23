# HANDOFF — 검색 마스터 v1 완료 + MFA G2P 검증, 전량 실행 대기 (2026-07-23 13:49)

새 세션(Claude)이 이 문서 하나로 맥락 복원하고 이어가기 위한 문서.
직전 세션에서 **검색 마스터 v1 설계·구현·파일럿 검증 + 사용자 결정 확정 반영**,
**MFA G2P 파일럿 성공**까지 끝냈다. 남은 것은 두 밤샘 배치(아래 3·4)다.

## 0. 시간·자원 상황
- **외장 HDD**: 2026-07-24(금) 13:00에나 연결 가능. **단 HDD는 reference 4종
  회수용 — v1 CSV 생성·MFA 재정렬엔 불필요.** 아래 배치는 HDD 없이 오늘부터 가능.
- **D: 경합**: CSV 생성과 MFA는 둘 다 D:를 크게 읽음 → **동시 금지, 순차 실행.**

## 1. 시작 절차
1. 읽기: `CLAUDE.md`(필수규칙) → 이 문서 → `docs/decisions/DESIGN_search_master_layer.md`
   → `docs/decisions/RUNBOOK_MFA_eojeol_realign.md`(특히 ★G2P 부재 절).
2. 상태 실측: `python scripts\python\preflight_search_master.py` → `logs\preflight_report.txt` 확인.

## 2. 완료·확정 (재논의 불필요)
- **predict_pron.py** (필수 규칙 G2P, 단위테스트 30/30). 확정 결정(2026-07-23):
  - 규칙: 필수 규칙 + **용언 어간+어미 경음화 ON**(신고→신꼬, 앉다→안따, 넓게→널께;
    ㄹ어간 알고→알고 대조 통과). **ㄹ비음화 OFF**(담력·강릉 유지 — 추후 한자어 경계와 함께).
  - 표기 4단 위계: **음소=공백 · 음절=`_` · 형태소=`+` · 어절=`|`**, 초성 대문자·종성 소문자.
    IPA 음절=`_`. 자리표시=`∅`. 철자 종성 디그래프(ㅌ→th·ㄼ→lp·ㅎ→h) 승인. ㄹㄹ=`l _ R`.
  - feeding/bleeding은 docstring에 명시.
- **build_search_master.py** (세션 CSV, 검증 내장, **tagged_roman 기본 on**). 파일럿 2020
  3세션·1,297발화 검증 통과. tagged_roman 예: 것을 `G EO s/NNB + EU l/JKO`(ㄴ삽입 검색용).
- **MFA G2P 파일럿 성공**: g2p korean_mfa 다운로드됨. align.py em-dash 패치 버그 수정 완료
  (export 직전 cp949 crash). 파일럿(2020 SDRW2000000001, 479발화): **phones spn 27.5→0%**,
  것을 phones **[거슬](k ʌ sʰ ɨ ɭ)** 시간정렬 확인. 도구: `measure_spn.py`,
  `build_g2p_pilot_corpus.py`.
- **stitch_session.py**: 발화 클립을 utt_id 순 이어붙여 연속 wav+정렬 TextGrid 재구성
  (원본 연속 녹음 부재 대비 — NIKL은 발화 클립 배포). 9발화 데모 검증(타일링 빈틈·겹침 0).

## 3. 남은 작업 (실행 순서 — D: 경합 때문에 순차)

### ① v1 CSV 전량 생성 — ✅ 완료 (2026-07-23 14:47)
> 5,103,356행 / 6개년 / 세션 17,156 / 어절수 불일치 0 / JSON 결측 0 / 검증 통과.
> 메타 결측 1,090·화자 결측 1,767(0.03%)은 미상 처리. tagged_roman은 align_warn
> 행도 채움(2026-07-23 수정). 출처 `05_search_master\_build_meta.json`.
> **다음은 ③ MFA G2P 전량 재정렬(아래).** ②(parquet)는 선택.

<원래 실행 지침 — 재생성 필요 시>

```
python scripts\python\build_search_master.py
```
- 전량(6개년). 연도·세션 체크포인트(기존 CSV skip) — 중단돼도 재실행하면 이어감.
- 출력 `D:\10_LAYERS\05_search_master\{연도}\`. 검증 리포트 `logs\build_search_master_*.txt`.
- **도는 동안 D: 읽는 다른 작업 금지**(MFA 등). 텍스트 연산이라 MFA와 무관·수 시간.

### ② (선택, CSV 후) 검색 인덱스 — build_search_parquet.py **미작성**
- 세션 CSV → 연도 Parquet + `search_master_all.parquet`. DuckDB 정규식 검색용(설계 §5).
- 다음 세션에서 작성 권장(pyarrow/duckdb). CSV만으로도 DuckDB 검색은 가능(느릴 뿐).

### ③ MFA G2P 전량 재정렬 (CSV 끝난 뒤, ~4일)
- 러너에 `--g2p_model_path korean_mfa` 추가됨(2026-07-23). align.py 패치도 수정됨.
- **2020·2021을 g2p로 재작업하려면** 완료 마커 삭제 후 실행:
  ```
  Remove-Item D:\mfa_eojeol\done\*.align_done, D:\mfa_eojeol\done\*.merge_done -Force
  powershell -ExecutionPolicy Bypass -File scripts\run_eojeol_realign.ps1
  ```
  (2022–2025만 새로 하려면 마커 삭제 불필요 — 러너가 미완료분만 처리.)
- 완료 후: `extract_actual_pron.py`(미작성) → `06_textgrid_eojeol` phones → **v2 실발음 레이어**
  (`06_actual_pron`), utt_id로 v1과 조인. 그러면 "예측 vs 실제 발음" 대조 완성.

### ④ 내일 13:00 HDD 연결 (독립 트랙 — CSV/MFA와 무관)
- reference 4종(00_DICTIONARY·MP·LS·다층위) robocopy 회수 — `docs/ASSETS_LEDGER.md` 명령.
- MFA 도는 중이면 잠깐 피해서(D: 경합). 회수 후 preflight 재실행 → ASSETS_LEDGER 갱신.

## 4. 미착수·보류
- coverage 컬럼(has_wav·has_tg_eojeol·quarantined) — build_search_master `--coverage` 배선.
- lexicon 발음 예외층 override(한자어 경음화 등) — 규칙 확정됐으니 착수 가능.
- 맥락 HTML 뷰어(검색 hit → 전후 발화 표 + 이어듣기) — 원하면.

## 5. 스크래치 (검토 끝나면 삭제 가능)
- `C:\mfa_g2p_pilot`(파일럿 코퍼스·G2P 출력 479 TextGrid), `C:\mfa_tmp_pilot`,
  `C:\stitch`(이어붙이기 데모 wav+TextGrid).

## 6. 커밋 상태
- 스크립트·문서 커밋됨(main). 신규: predict_pron·build_search_master·measure_spn·
  build_g2p_pilot_corpus·stitch_session + run_eojeol_realign.ps1(g2p) + 이 문서.
- push는 미실행(사용자 지시 대기). claude.ai 프로젝트 지식 최신화하려면 push 필요.

## 7. TextGrid tier 결정 + 온디맨드 enrichment (2026-07-23 세션3)

**결정 (1)**: 전량 `06_textgrid_eojeol`은 표준 4-tier(words/phones/morphemes/
utterance) 그대로 유지. 어절/형태소 철자 로마자·예측발음 등 파생값은 검색마스터
CSV(05_search_master)에 이미 있고 utt_id로 조인되므로 585만 tier에 상시 넣지
않는다. 이유: (a) 검색·집계는 Parquet/DuckDB에서 하지 Praat에서 안 함, (b) 파생값을
~4일짜리 재정렬 층에 결합하면 규칙 한 번 바뀔 때 전량 재생성, (c) phones tier는 이미
로마자라 발음 로마자는 이미 있음. 형태소 tier 품사태그 상시 포함은 보류(옵션).

**추가 도구**: `scripts/python/enrich_textgrid_ondemand.py` — 분석 대상 발화
(`--session`/`--utt`/`--hitlist`)에만 CSV에서 `pron_pred_hangul,pron_pred_roman,
form_roman,tagged` tier를 phones 아래 얹은 **사본**을 `--out`(기본 C:\enriched_textgrid)에
생성. 원본 불변. words tier 경계 미러 + 어절수 불일치 시 발화 1구간 `[align≠]` 폴백
(조용한 오정렬 금지). paths.py 사용. 운율 5번째 tier와 같은 온디맨드 방식.

**상태**: `--selftest` 통과(합성 4케이스: 정렬/폴백/공백/미분할).
★**검증 대기**: 실제 CSV로 `--session <세션> --dry-run` 1회 돌려 각 컬럼 어절
구분자 가정(roman=`|`, 한글=공백, tagged=미분할) 확정 — **MFA 등 D: 배치 끝난 뒤**.
스크립트는 아직 미커밋(사용자 지시 대기).

## 8. ★결정: CSV 예측발음에 사전(lexicon) 발음 반영 (2026-07-23 사용자 확정)

**경위**: 사용자는 예측발음에 사전 예외 발음이 반영되길 의도했으나 v1
`predict_pron.py`는 **규칙 기반만** 구현됨(실측: import는 argparse/sys뿐,
`lexicon`/`pron_1`/`morph_dict` 참조 0건). 사전 예외 미반영 상태였고, 이번에
**명시적으로 반영하기로 결정**. 놓쳤던 항목이므로 MFA 이후 최우선.

**범위**
- **CSV 예측발음 층만** 사전 반영. **MFA 정렬 쪽 override는 안 함**(사용자 결정).
- 대상 = 규칙이 못 잡는 어휘화 발음(합성어/한자어 경음화, 불규칙 등).
- 사전 = lexicon v1 `P("lexicon_full")`
  (D:\00_RAW\reference\03_lexicon_1기\01_NIKL_lexicon_full.csv,
  pron_1/pron_2/pron_g2p·morph_dict, 130만 행).

**실행 조건**
- 예측발음 열 재생성 = `build_search_master` 재빌드(D: 대배치) →
  **MFA 전량 재정렬 끝난 뒤** 실행(필수규칙 7: D: 경합 금지).
- 사전 포맷 실측(헤더·컬럼)도 D: 여유 때. 코드 골격은 C:에서 선작성 가능.

**구현 전 확정 필요(음운론 판단, 사용자)**
1. 우선순위: 사전 우선 / 규칙 우선+사전은 예외만.
2. 조회 단위: 어절 전체 / 형태소.
3. 단일 기준열에 반영 vs 사전기반 별도 열 병기.
   → 권장: 비파괴로 사전 열 별도 병기(규칙-사전 불일치 자체가 관찰값) 후 검토.

**상태**: 코드 미착수. MFA 종료 후 착수 예정.

## 9. MFA 워치독 G2P 오살 사고 + 재시작 + 자동감시 (2026-07-23 세션3)

**사고**: g2p 추가로 새로 생긴 `Generating pronunciations` 단계는 mfa/python CPU가
거의 안 올라(사전·FST 빌드/헬퍼), 워치독의 "15분간 CPU 증가 <10초 = 교착" 판정에
오판됨 → 4시간+ 진행 중이던 2020을 강제종료하고 temp 비운 뒤 `--clean` 재시작하는
낭비 루프. (2020: 15:12 시작 → 19:27 오살)

**수정**: `run_eojeol_realign.ps1` 워치독 예외에 `Generating pronunciations` 추가
(commit 0416a3f). **근거**: 2021이 워치독 켜진 채 19h(68,463초) 완주한 stderr 확인 —
MFCC/CMVN/graph 컴파일/정렬/export 등 다른 단계는 오살 이력 없음. 문제는 g2p
단계 하나뿐으로 확정, 다른 예외 불필요(과잉 예외는 진짜 교착 놓칠 위험).

**재시작 전 실측**: C: 51GB / D: 347GB 여유(큰 연도는 C:<40GB 시 자동 D: 전환).
모델 g2p·acoustic·dict 모두 존재. done 마커 empty(6개년 g2p 재정렬). 스테일 temp는
`C:\mfa_tmp\2020`뿐(재시작 시 삭제).

**재시작 절차**: MFA 창 Ctrl+C → `Remove-Item C:\mfa_tmp\2020 -Recurse -Force` →
`run_eojeol_realign.ps1` 재실행.

**자동감시**: 스케줄 태스크(2시간 간격)가 새 세션으로 power-cube에 접속해
`D:\mfa_eojeol\logs`(최근 러너 로그·stderr)·`done` 마커·C:/D: 여유를 점검하고,
루프/실패/hang/디스크부족/연도완료/전체완료 시 사용자에게 알림. 데스크톱 앱(브리지)
연결 시에만 동작.
