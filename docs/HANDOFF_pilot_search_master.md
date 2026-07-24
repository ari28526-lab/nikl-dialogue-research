# HANDOFF — 검색 마스터 파일럿 (새 세션 시작용, 2026-07-23 작성)

새 세션(Claude)이 이 문서 하나로 맥락을 복원하고 바로 파일럿 작업에
들어가기 위한 문서. **사용자는 지난 몇 주 반복된 오류·누락으로 지친 상태다.
이번 세션의 최우선 가치는 "한 번에 되게"이며, 그 수단은 아래 규칙과 확정
사항을 재논의 없이 따르는 것이다.**

## 0. 시작 절차 (순서대로)
1. 읽기: `CLAUDE.md`(특히 필수 규칙 8~10) → 이 문서 →
   `docs/decisions/DESIGN_search_master_layer.md`(설계 정본, 전문)
2. 상태 실측: 사용자에게 `python scripts\python\preflight_search_master.py`
   실행 요청 → `logs/preflight_report.txt`를 직접 읽고 ✅ 확인 후 진행
   (2026-07-23 통과 이력 있음. 재실행은 그 사이 변화 감지용)
3. 자산 위치가 궁금하면 `docs/ASSETS_LEDGER.md` (실측 기반 정본) — 폴더를
   뒤지거나 추정하지 말 것

## 1. 확정된 것 (재논의 불필요 — DESIGN 문서가 정본)
- **목적**: 발화 단위 CSV 한 층위에서 사회변수·형태소·철자열·발음열 검색 →
  utt_id·어절 번호로 wav/TextGrid 추적. 기존 레이어 불변, 그 위에 신규 레이어.
- **결정 4** (2026-07-23 사용자): roman_mfa 체계 재사용 / 예측 발음열은 필수
  규칙만 단일 기준열 / 발화 1행+어절 정렬 병기 / 세션별 CSV 정본+연도
  Parquet+전체 단일 Parquet(`search_master_all.parquet`)
- **표기 규약**: 음소=공백, 음절=` - `, 어절=` | `, 초성 대문자·종성 소문자.
  정본 토큰 집합 = `D:\10_LAYERS\03_freq_dictionaries\_roman_mfa_to_ipa.csv`.
  미정의 토큰은 `⟨기호⟩`로 노출. 철자 전용 종성 토큰은 표에 추가 등록.
- **컬럼**: 추적(utt_id 등)+사회변수(file_meta·speakers_normalized의 `_norm`)+
  텍스트(form·tagged·**original_form·start·end·note** ←원본 JSON)+철자열+
  예측발음열(한글·roman·IPA). MFA phones·시간정보는 별도 보조 레이어로
  두고, 현상 실현 여부는 연구자가 음성과 TextGrid를 보고 별도 판정.
- **발음 조회부**: lexicon **v1**(`D:\00_RAW\reference\03_lexicon_1기\01_NIKL_lexicon_full.csv`,
  pron_1/pron_2/pron_g2p·morph_dict, 130만 행) 우선 + 형태소·어절 경계 필수
  규칙. 한글 발음→roman_mfa **직접 변환**(lexicon의 서울식 roman은 참조 전용).
  v2(word_roman_mfa 보유)는 HDD 유일본 — 회수 전까지 v1로 진행(차단 아님).
- **TextGrid**: 어절 4-tier 표준 유지, 예측발음·사회변수는 tier에 넣지 않음.
  운율은 분석 발화만 5번째 tier 온디맨드.

## 2. 이번 세션 작업 목록 (파일럿)
- [ ] `scripts/python/predict_pron.py` 작성 — form+tagged → 철자열·예측
      발음열(한글/roman/IPA). 규칙별 on/off 플래그, lexicon 조회부(용언 '-다'
      어간 매핑 포함), 미정의 토큰 노출, 단위테스트 몇 개 동봉
- [ ] `scripts/python/build_search_master.py` 작성 — 세션별 CSV 생성.
      `--pilot N`(세션 수 제한) 옵션, 연도·세션 체크포인트, paths.json 사용.
      검증 내장: 행수=발화수 전수 일치 / 문자열 컬럼 어절수=n_eojeol /
      same-length 가드(불일치는 `_`+`align_warn`) / 조인 결측은 `미상`
- [ ] 파일럿 실행(사용자 콘솔): 2020 세션 2~3개 → 출력 CSV를 사용자와 함께 검토
- [ ] 사용자 확정 3건 받기: ① 예측발음 규칙 인벤토리·적용 순서(음운론 판단)
      ② 기호 세부(어절 `|`·자리표시 `_`) ③ `tagged_roman` 컬럼 포함 여부
      → DESIGN 문서 "미결" 절 갱신
- [ ] 확정 반영 → 전량 생성 준비(밤샘 배치 안내문 포함) — 실행은 사용자
- [ ] `build_search_parquet.py`(연도+전체 단일 Parquet) — 전량 후

## 3. 이 세션에서 하지 말 것 (별도 트랙 — 건드리면 혼선)
- G2P 파일럿·어절 재정렬 재개 (TODO_A단계 최우선 항목이지만 **독립 트랙**)
- HDD reference 4종 회수 (ASSETS_LEDGER에 명령 준비됨 — HDD 연결 때)
- 1기 enriched CSV 백업 (G: 연결 확인됨 — ASSETS_LEDGER의 robocopy 한 줄)
- 운율 청취 검증·ㄴ삽입 definition 검토 (사용자 몫, 재촉만)

## 4. 사고 예방 수칙 (이번 주 사고에서 나온 것 — 어기지 말 것)
1. 사용자 콘솔에 **한 줄 명령 지시 금지** — 모든 점검·작업은 리포에 커밋한
   스크립트로, 결과는 `logs/` 파일로 남겨 Claude가 직접 읽는다
2. **상태 선언은 실측으로만** — "있다/완료됐다"는 preflight류 보고서 근거 필수
3. 대량 작업 전 파일럿, 원본(00_RAW) 불변, 장시간 배치는 체크포인트
4. `.ps1`은 UTF-8 BOM, Python은 utf-8 + stdout reconfigure
5. D:에서 배치가 도는 동안 D:를 읽는 다른 작업 금지
