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
