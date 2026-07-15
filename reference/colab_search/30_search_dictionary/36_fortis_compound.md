# 합성어 경음화 환경 검색

**작성일**: 2026-02-10
**노트북**: `36_fortis_compound.ipynb`

---

## 🎯 목적

**합성어 경음화 환경**을 사전에서 검색

- 형태소 경계에서 평음 → 경음 변화 환경
- 형태론적 조건별 분류 (어종 조합)
- 사전 발음 기반 실제 경음화 여부 자동 감지

---

## 🔍 검색 조건

### 1. 음운론적 조건

**형태소 경계**에서:
- **morph1 끝**: 모음, 비음(ㅁ/ㄴ/ㅇ), 유음(ㄹ), 저해음(ㄱ/ㄷ/ㅂ/ㅅ 등)
- **morph2 시작**: **평음** 저해음 (ㄱ/ㄷ/ㅂ/ㅈ/ㅅ)
  - 로마자: k/t/p/j/s (경음 GG/DD/BB/JJ/SS 제외)

### 2. 형태론적 조건 (3가지 유형)

| 유형 | morph1 어종 | morph2 어종 | 예시 |
|------|-------------|-------------|------|
| **Type A** | 고유어 | 고유어 | 손-가락, 밤-길 |
| **Type B** | 한자어/외래어 | 고유어 | 학-교, 아파트-단지 |
| **Type C** | 고유어/한자어/외래어 | 한자어 | 등교-길, 물-질, 학-생 |

---

## ⚠️ 유의사항

### 1. 받침 ㅅ 처리
```
등굣길 [등교낄]:
  - dict_morph: "등교-길" (ㅅ는 사잇소리 표기)
  - 실제 형태소: 등교(한자어) + 길(고유어)
  - 경음화: 길 → [낄]
```

### 2. 한자어 접미사
```
물-질, 공-간, 시-간:
  - 한자어가 원래 경음으로 저장되어 있을 수도 있음
  - vs 사잇소리 현상으로 경음화된 것
  → 사전 발음과 비교하여 확인
```

---

## 📊 출력 컬럼

### 기본 정보
- word, sense_id, definition

### 환경 정보
- **morph1_final_type**: vowel / nasal / liquid / obstruent
- **morph2_initial**: k / t / p / j / s (평음)
- **detected_fortis**: yes / no / unknown (자동 감지)
- **fortis_type**: k→GG, t→DD, p→BB, j→JJ, s→SS

### 형태론 정보
- **morph1_origin**: 고유어 / 한자어 / 외래어
- **morph2_origin**: 고유어 / 한자어 / 외래어
- **compound_type**: A / B / C

### 형태소 분석
- dict_morph, word_roman
- morph1, morph2, morph1_roman, morph2_roman
- seg_morph, anal_morph

### 발음 정보
- pron, pron_roman

### 빈도 정보
- freq_LS_total, freq_MP_total
- freq_06b, freq_13a (Freq_2009)

---

## 🔧 주요 함수

### 1. `build_morpheme_origin_dict(df)` ⭐
v7_lexicon에서 단일 형태소의 어종 딕셔너리 구축
- 단일 형태소 (dict_morph가 없거나 경계가 없는 것) 추출
- {형태소: 어종} 딕셔너리 생성
- 약 18만개 형태소의 어종 매핑

### 2. `get_final_sound_type(roman_str)`
형태소 끝소리 분류
- 'vowel': 모음 (a/e/i/o/u)
- 'nasal': 비음 (m/n/ng)
- 'liquid': 유음 (l/r)
- 'obstruent': 저해음 (k/t/p/s 등)

### 3. `is_plain_obstruent(roman_char)`
평음 저해음인지 확인
- True: k, t, p, j, s
- False: GG, DD, BB, JJ, SS (경음)

### 4. `detect_fortis_from_pron(morph2_roman, pron_roman)`
발음 로마자에서 경음화 자동 감지
- k → GG, t → DD, p → BB, j → JJ, s → SS

### 5. `classify_compound_type(morph1_origin, morph2_origin)`
합성어 유형 분류
- Type A: 고유어 + 고유어
- Type B: (한자어/외래어) + 고유어
- Type C: (any) + 한자어

---

## 🚀 사용 방법

1. **Colab 실행**
   ```
   36_fortis_compound.ipynb
   → Runtime → Run all
   ```

2. **결과 확인**
   ```
   fortis_compound_candidates_YYYYMMDD_HHMMSS.csv
   ```

3. **필터링**
   - compound_type = 'A' → 고유어+고유어만
   - detected_fortis = 'yes' → 실제 경음화 확인된 것만

---

## 📝 검토 가이드

### Type A (고유어 + 고유어)
```
손가락 [손까락]: 고유어+고유어, 경음화 O
밤길 [밤낄]: 고유어+고유어, 경음화 O
```

### Type B (한자어/외래어 + 고유어)
```
학교 [학꾜]: 한자어+고유어, 경음화 O
아파트단지 [아파트딴지]: 외래어+고유어, 경음화 O
```

### Type C (any + 한자어)
```
등교길 [등교낄]: 한자어+고유어? or 한자어+한자어?
물질 [물찔]: 고유어+한자어, 경음화 O
공간 [공깐]: 한자어+한자어, 원래 경음? or 경음화?
```

---

## 🎯 연구 질문

1. **Type C에서 한자어 접미사의 경음화**:
   - 사잇소리 현상인가?
   - 아니면 한자어 자체가 경음으로 저장되어 있는가?

2. **어종 조합별 경음화 비율**:
   - Type A vs Type B vs Type C
   - 각 유형에서 실제 경음화 비율은?

3. **음운론적 조건의 영향**:
   - morph1 끝소리 유형별 경음화 비율
   - 모음 > 비음 > 유음 > 저해음 순인가?

---

## 🔗 관련 노트북

- **34_n_insertion_v2.ipynb**: ㄴ/ㄹ 삽입
- **35_nl_ln_nasalization.ipynb**: 유음화/비음화
- **36_fortis_compound.ipynb**: 합성어 경음화 (현재)

---

**이제 Colab에서 실행하세요!** 🚀
