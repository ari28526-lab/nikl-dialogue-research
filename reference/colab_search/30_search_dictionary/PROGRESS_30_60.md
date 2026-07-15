# 30~60번 작업 진행 현황 및 흐름

최종 업데이트: 2026-03-19

---

## 전체 파이프라인

```
30 사전검색 (v7 53만행)
 ├─ 34 ㄴ/ㄹ삽입 → CSV 6,630행
 ├─ 35 유음화/비음화 → CSV 18,878행
 ├─ 36 합성어경음화 → CSV 미저장 (버그 수정 후 저장 예정)
 └─ 37 모음조화/모음충돌회피 → 용언 어간+어미 분석 (신규)
    ↓ (word 리스트)
40 LS빈도 검색 (빈도 CSV 8개, 총 102MB)
 └─ 각 현상별 단어의 실제 사용 빈도 조회
    ↓
50 서울코퍼스 발음 검색 (231,632 pWord)
 └─ 철자 vs 발음 비교, 화자별 변이
    ↓
60 대화코퍼스 맥락 검색 (4,570,823 발화)
 └─ 실제 대화에서의 사용 맥락, 구 경계 ㄴ삽입
    ↓
90 통합 분석
```

---

## Phase 0: utils_phonology.py [완료]

**상태**: 118 PASS / 0 FAIL

### 핵심 변경사항
- 어종 분류: ~~형태소 문자열 매칭 (동음이의어 문제)~~ → **sense_no 기반 정확 매칭**
  - `build_sense_origin_dict(df)` — sense_no → word_type
  - `classify_compound_type_from_row(row, sense_dict)` — word_type 직접 사용 + 혼종어만 seg_links 파싱
- `is_plain_obstruent()` — 격음(Kh/Th/Ph/Ch) 제외 수정
- `detect_fortis_from_pron()` — 36번에서 누락되었던 함수 추가
- `check_n_l_insertion_internal()` — 단어내부 ㄴ삽입 환경 (신규)
- `check_nl_ln_internal()` — 장애음ㄴ/장애음ㅁ 환경 추가
- 34번 조건 변수 함수들: m2_onset_type, m1_coda_type, m2_vowel_height, branching 등

---

## Phase 1: 34번 ㄴ/ㄹ삽입 [✅ 완료]

**파일**: `34_n_insertion_v2.ipynb`
**현재 CSV**: `n_l_insertion_candidates_v2_20260312_070223.csv` (12.7MB, 2026-03-12)

### 수정 사항
1. **인라인 함수 → %run utils_phonology.py** 로 교체
   - cell 9 (build_morpheme_origin_dict) → 삭제, build_sense_origin_dict 사용
   - cell 11 (ends_with_consonant_roman, starts_with_i_j_roman) → 삭제
   - cell 12 (parse_dict_morph 등) → 삭제
   - cell 14 (check_n_l_insertion_env 등) → 삭제
   - cell 15 (classify_compound_type) → 삭제

2. **어종 분류 교체**
   - `build_morpheme_origin_dict(df)` → `build_sense_origin_dict(df)`
   - `classify_compound_type(o1, o2)` → `classify_compound_type_from_row(row, sense_dict)`

3. **조건 변수 컬럼 추가** (세미나 3~4강 기준)
   - `m2_onset_type`: j_glide / i_vowel
   - `m1_coda_type`: sonorant_non_ng / ng / obstruent
   - `m2_vowel_height`: high / non_high
   - `branching`: left / right / flat / binary
   - `m1_syllable_count`, `m2_syllable_count`: 음절수
   - `boundary_type`: compound / derivation (이미 column_order에 있으나 CSV에 누락)

4. **단어내부 ㄴ삽입 추가**
   - `check_n_l_insertion_internal(word_roman)` 사용
   - 한자어 단일어 내부 (금융, 담요 등)

### 구 경계 ㄴ삽입 — 50/60번에서 처리
- 사전(30번)에서는 **형태소 경계 + 단어내부**만 검색 가능
- **구 경계**(솜 이불 → [솜니불], 꽃 위 → [꼰뉘])는 코퍼스에서만 검색 가능
  - 50번 서울코퍼스: pWord_ortho vs pWord_prono 비교
  - 60번 대화코퍼스: form vs pronunciation 비교
- 구 경계 검색 로직: 연속된 두 어절에서 어절1 종성 + 어절2 초성 i/j → ㄴ삽입 환경

### 확인 필요
- [ ] 조건 변수 컬럼이 세미나 자료와 일치하는지 검토
- [ ] boundary_type이 CSV에 정상 저장되는지 확인
- [ ] 단어내부 ㄴ삽입 결과가 합리적인지 (금융, 담요 등 포함 여부)

---

## Phase 2: 35번 유음화/비음화 [✅ 완료]

**파일**: `35_nl_ln_nasalization.ipynb`
**현재 CSV**: `nl_ln_nasalization_candidates_20260312_070559.csv` (9.0MB, 2026-03-12)

### 수정 사항
1. **인라인 함수 → %run utils_phonology.py** 로 교체
2. **어종 분류 교체** (위와 동일)
3. **장애음 비음화 환경 추가** (세미나 9강)
   - `장애음ㄴ`: 국민[궁민], 학년[항년] — 이미 utils에 구현됨
   - `장애음ㅁ`: 작물[장물], 밥맛[밤맛] — 이미 utils에 구현됨
4. **음운 변화 감지 컬럼 추가**
   - `expected_process`: lateralization / nasalization / obstruent_nasalization
   - `detected_process`: lateralized / nasalized / no_change / unknown

### 확인 필요
- [ ] 장애음비음화 결과 행수가 합리적인지
- [ ] 기존 4환경(ㄴㄹ/ㄹㄴ/비음ㄹ/저해음ㄹ) 행수가 변하지 않았는지
- [ ] morph_boundary_type이 CSV에 정상 저장되는지

---

## Phase 3: 36번 합성어경음화 [✅ 완료]

**파일**: `36_fortis_compound.ipynb`
**현재 CSV**: `fortis_compound_candidates_20260312_071626.csv` (43.7MB, 2026-03-12)

### 수정 사항 (버그 수정 핵심)
1. **인라인 함수 → %run utils_phonology.py** 로 교체
2. **detect_fortis_from_pron 누락 해결** — utils에 이미 정의됨
3. **classify_compound_type 충돌 해결** — cell 15(N+N) vs cell 16(A/B/C) → utils의 N+N 사용
4. **is_plain_obstruent 격음 미제외 해결** — utils에서 수정됨
5. **어종 분류 교체** (위와 동일)
6. **추가 컬럼**
   - `m2_initial_place`: velar / alveolar / bilabial
   - `m2_has_laryngeal`: True/False (경음/격음 차단 조건)
   - `word_length`: 전체 음절수
7. **CSV 저장** — column_order 존재하지만 실행 안 되던 문제 → 정상화

### 확인 필요
- [ ] CSV 저장 후 행수 확인 (예상: 수천 건)
- [ ] 손칼(ㅋ), 발톱(ㅌ) 등 격음이 정상 제외되는지
- [ ] compound_type이 N+N, S+S 등으로 정상 분류되는지

---

## Phase 3.5: 37번 모음조화/모음충돌회피 [✅ 완료 — 전 파이프라인 완주]

**파일**: `37_vowel_harmony_collision/37_vowel_harmony_collision.ipynb` (+ LS/Seoul/Dialogue 노트북 3개)

### 목적
v7 용언(동사/형용사)에서 모음조화와 모음충돌회피 환경을 체계적으로 추출

### 접근 방법
1. v7에서 동사(78,792) + 형용사(17,594) 필터
2. `conjugations` 필드에서 -아/어 활용형 파싱 (첫 항목)
3. 어간 마지막 모음 분석 → 양성/음성 분류
4. **모음조화**: 자음어간 → -아/-어 선택이 양/음성과 일치하는지
5. **모음충돌회피**: 모음어간 → 탈락/활음화/활음삽입/축약 분류
6. 결과 CSV 저장 → 50/60번에서 코퍼스 검색

### 세미나 자료 기반
- 2강: 모음조화 — 양성모음(ㅏ,ㅗ)+아, 음성모음+어
- 10강: 모음충돌회피 — 탈락(떼+어→떼), 활음화(보+아→봐), 활음삽입(보+아→보와)
- 변이 요인: 어간모음 종류, 음절수, 발화속도, 빈도 (홍석우 2023, 신우봉 2013)

### 확인 필요
- [ ] conjugations 파싱이 정확한지 (v7 형식 검증)
- [ ] 모음충돌회피 분류 정확도 (활음화 vs 축약 구분)
- [ ] 불규칙 용언(ㅂ불규칙, ㅡ탈락 등) 처리
- [ ] 코퍼스에서의 검색 방법 (어간+어미 결합형을 어떻게 찾을지)

---

## Phase 4: 40번 LS빈도 [✅ 완료]

**파일**: `40_search_LS_corpus/41_ls_frequency_search.ipynb` (20KB, 2026-03-13)
**결과**: search_results/ CSV 6개 (34/35/36/37 전체에 LS 빈도 붙임)

### 목적
30번 검색 결과(word 리스트)의 실제 사용 빈도를 LS 코퍼스에서 조회

### 입력 데이터
- 30번 결과 CSV: `search_results/*.csv` (word 컬럼)
- LS 빈도: `00_raw_data/02_nikl_ls/07_ALL_word_freq.csv` (102MB)
  - 컬럼: word_surface, morpheme_analysis, sense_analysis, corpus_type, corpus_name, freq, word_roman

### 처리 로직
1. 30번 CSV에서 word 리스트 추출
2. LS 빈도 CSV 로드
3. word_surface 기준 매칭 → 빈도 조회
4. 코퍼스 유형별(messenger/written/spoken) 빈도 분리
5. 결과 CSV 저장

### 주의사항
- 30번 CSV에 이미 freq_LS_total 등이 있음 (v7에서 가져온 것)
- 40번에서는 LS 원본 데이터에서 **더 상세한 빈도** 조회 가능
  - 예: corpus_name별 빈도, morpheme_analysis 활용
- 사전에 없는 단어도 LS에는 있을 수 있음 → 매칭 실패 건 추적

### 확인 필요
- [ ] v7의 freq_LS_total과 LS 원본의 freq 차이 확인
- [ ] 매칭률 (30번 word 중 몇 %가 LS에 존재?)

---

## Phase 5: 50번 서울코퍼스 [🔄 부분 완료]

**파일**: `50_search_seoul_corpus/51_seoul_pronunciation.ipynb` (24KB, 2026-03-13)
**결과**: `seoul_all_phenomena_...csv` (5.3MB) + `seoul_phrase_n_insertion_...csv` (638KB)

### 목적
30번 검색 결과의 단어가 서울 코퍼스에서 실제로 어떻게 발음되는지 확인

### 입력 데이터
- 30번 결과 CSV
- 서울 enriched: `00_raw_data/03_seoul_corpus/02_csv/04_seoul_pword_enriched.csv` (242MB)
  - 컬럼: pWord_ortho, pWord_prono, pWord_ortho_roman, pWord_prono_roman, morphs, morphs_roman, morphs_v7_ids, morphs_v7_origins, spk_gender, spk_age 등

### 처리 로직
1. 30번 CSV에서 word 리스트 추출
2. 서울 pWord CSV 로드
3. pWord_ortho 기준 매칭
4. ortho vs prono 비교 → 실제 발음 변이 확인
5. 화자 변수(성별/연령) 별 발음 변이 통계
6. **구 경계 ㄴ삽입 검색** (핵심)
   - 연속 pWord에서: 어절1 종성(자음) + 어절2 초성(i/j) → ㄴ삽입 환경
   - pWord_prono에서 실제 ㄴ삽입 여부 확인

### 주의사항
- 사전에 없는 단어(은어, 줄임말 등)도 코퍼스에는 있을 수 있음
- morphs_v7_ids로 v7과 직접 연결 가능
- 서울 코퍼스는 읽기 발화(낭독체) 중심 → 자연 발화와 다를 수 있음

### 확인 필요
- [ ] pWord_ortho와 30번 word의 매칭률
- [ ] 구 경계 ㄴ삽입 후보 건수
- [ ] 화자 변수별 발음 변이 패턴

---

## Phase 6: 60번 대화코퍼스 [🔄 시작]

**파일**: `60_search_dialogue_corpus/61_dialogue_context.ipynb` (15KB, 2026-03-13)
**완료**: file_index.csv (1.2GB, D: 경로 인덱스) + 샘플 테스트 (84KB CSV)

### 목적
30번 검색 결과의 단어가 실제 대화에서 어떤 맥락으로 사용되는지 확인

### 입력 데이터
- 30번 결과 CSV
- 대화 enriched: `00_raw_data/04_nikl_dialogue/02_csv/01_nikl_dialogue_enriched.csv` (4.7GB)
  - 컬럼: form, pronunciation, form_roman, morphs, morphs_roman, morphs_v7_ids, morphs_v7_origins, speaker_age, speaker_sex, speaker_birthplace 등
- **샘플** (테스트용): `01_nikl_dialogue_enriched_sample3k.csv` (3.1MB)

### 처리 로직 — 2단계
**Stage A (Colab, G:)**: CSV 기반 검색
1. 샘플 CSV 로드 (개발/테스트)
2. 30번 word 기준 form 매칭
3. 발화 맥락(utt context) 추출
4. form vs pronunciation 비교 → 음운 변이 확인
5. 화자 변수별 분석
6. **구 경계 ㄴ삽입**: 연속 발화에서 어절 경계 분석

**Stage B (Local, D:)**: TextGrid 기반 음성 분석
- TextGrid (40GB): `D:\04_00_NIKL_DIALOGUE_MFA\06_textgrid_merged\`
- WAV (431GB): `D:\04_00_NIKL_DIALOGUE_MFA\03_wav\`
- 음향 분석이 필요한 경우에만 사용

### 주의사항
- 4.7GB CSV는 Colab에서 메모리 문제 가능 → 청크 처리 또는 필터링 필요
- 샘플(3K)로 먼저 파이프라인 검증 → 전체 데이터 실행
- D: 데이터는 로컬 Jupyter에서만 접근 가능

### 확인 필요
- [ ] 4.7GB CSV의 Colab 메모리 한계 (무료: ~12GB RAM)
- [ ] 샘플 3K에서 30번 word 매칭률
- [ ] Stage B가 실제로 필요한지 (음향 분석 범위)

---

## 구 경계 ㄴ삽입 — 설계 메모

### 왜 50/60번에서 해야 하는가
- 사전(30번): 단어 내부 형태소 경계만 있음 (솜-이불 = 1 단어)
- 코퍼스(50/60번): 어절 경계가 있음 (솜 이불 = 2 어절)
- 구 경계 ㄴ삽입: "솜 이불" → [솜니불]은 두 어절 사이에서 발생

### 검색 로직 (50/60번 공통)
```python
# 연속 어절에서 ㄴ삽입 환경 탐색
for i in range(len(words) - 1):
    word1_roman = words[i].pWord_ortho_roman  # or form_roman
    word2_roman = words[i+1].pWord_ortho_roman

    # word1 끝 자음 + word2 시작 i/j → ㄴ삽입 환경
    if ends_with_consonant_roman(word1_roman.split('-')[-1]):
        if starts_with_i_j_roman(word2_roman.split('-')[0]):
            # ㄴ삽입 후보!
            # pronunciation에서 실제 ㄴ삽입 확인
```

### 유음화/비음화 구 경계도 동일 패턴
- "신 라면" → [실라면] (유음화 at phrase boundary)
- 동일한 검색 로직 적용 가능

---

## 데이터 흐름 요약

| 단계 | 입력 | 처리 | 출력 |
|------|------|------|------|
| 30 사전검색 | v7 lexicon (53만행) | 음운 환경 필터링 | 후보 CSV (수천~만행) |
| 40 LS빈도 | 30 결과 + LS CSV | 빈도 조회 | 빈도 보강 CSV |
| 50 서울발음 | 30 결과 + 서울 pWord | 발음 비교 + 구 경계 | 발음 변이 CSV |
| 60 대화맥락 | 30 결과 + 대화 CSV | 맥락 추출 + 구 경계 | 맥락 CSV |
| 90 통합 | 40+50+60 결과 | 교차 분석 | 최종 분석 |

---

## 막혀 있는 부분 / 결정 필요 (2026-03-19 갱신)

1. ~~**40번**: v7에 이미 freq_LS_total이 있는데~~ → **해결됨** (LS 빈도 CSV 6개 생성 완료)

2. ~~**50번 서울코퍼스**: 242MB pWord CSV를 Colab에서~~ → **해결됨** (통합검색 1회 실행 완료)
   - **남은 문제**: 개별 환경별 세분화 + 화자 변수 분석이 필요한지?

3. **60번 대화코퍼스**: 4.7GB CSV → Colab 메모리 한계 **여전히 미해결**
   - 샘플(3K)은 성공, 전체 실행 전략 미결정
   - 옵션 A: 30번 word 리스트로 미리 필터링 → 작은 CSV 생성
   - 옵션 B: 청크 단위 처리
   - 옵션 C: 로컬 Jupyter에서 처리
   - D: file_index.csv (1.2GB) 이미 구축되어 TextGrid/WAV 경로 참조 가능

4. ~~**구 경계 ㄴ삽입**~~ → **부분 해결** (50번에서 `seoul_phrase_n_insertion` 638KB 생성)
   - 60번 대화코퍼스에서도 동일 검색 필요 (전체 실행 시)
