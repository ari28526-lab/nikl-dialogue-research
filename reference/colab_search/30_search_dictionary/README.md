# 30_search_dictionary

사전 내 검색 (v7 lexicon 52만 행 활용)

---

## 🎯 목적

`10_dictionary_build/output/04_v7_lexicon.csv` (52만 행)에서 특정 조건의 단어 검색

---

## 📁 파일 구조

```
30_search_dictionary/
├── README.md                  ← 이 파일
├── 31_search_phonology.ipynb  ⭐ 음운 조건 검색
├── 32_search_morpheme.ipynb   ⭐ 형태소 조건 검색
├── 33_productivity.ipynb      (형태소 생산성)
└── search_results/            (검색 결과 저장)
```

---

## 🔍 검색 기능

### 31_search_phonology.ipynb
**음운 조건 검색**:
- ㄹ 종성 단어
- ㄴ 종성 단어
- 받침 없는 단어
- 경음화 환경
- 비음화 환경
- 유음화 환경

### 32_search_morpheme.ipynb
**형태소 조건 검색**:
- 접미사 검색 (예: '-이', '-하다')
- 접두사 검색 (예: '새-', '풋-')
- 어근 검색
- 복합어 패턴

### 33_productivity.ipynb
**형태소 생산성 계산**:
- Type frequency
- Token frequency
- Productivity index

---

## 📊 산출물

`search_results/` 폴더에 자동 저장:
- `phonology_ㄹ종성_YYYYMMDD_HHMMSS.csv`
- `morpheme_이접미사_YYYYMMDD_HHMMSS.csv`
- `productivity_index_YYYYMMDD.csv`

---

## 🚀 시작하기

```python
# v7 lexicon 로드
import pandas as pd
df = pd.read_csv('g:/내 드라이브/DATA_2026/10_dictionary_build/output/04_v7_lexicon.csv',
                 encoding='utf-8-sig')

print(f"전체: {len(df):,}개")
```

---

**최종 업데이트**: 2026-02-10
