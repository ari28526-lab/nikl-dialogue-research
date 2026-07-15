# 40_search_seoul_corpus

Seoul Corpus 검색 (최우선)

---

## 🎯 목적

Seoul Corpus의 철자형 vs. 발음형을 활용하여 **실제 발음 변이** 검색

---

## ⭐ Seoul Corpus 특징

- **음성 파일**: TextGrid + WAV 240쌍
- **철자-발음 구분**: `pWord_ortho` vs. `pWord_prono`
- **형태소 분석**: Bareun AI
- **화자 정보**: 성별, 나이

**데이터 위치**:
- 원본: `03_Seoul_Corpus/00_file/` (TextGrid + WAV)
- CSV: `03_Seoul_Corpus/02_csv/02_seoul_corpus_enriched.csv`

---

## 📁 파일 구조

```
40_search_seoul_corpus/
├── README.md                      ← 이 파일
├── 41_seoul_exploration.ipynb     (데이터 탐색)
├── 42_seoul_pronunciation.ipynb   ⭐ 철자-발음 검색
├── 43_seoul_audio_extract.ipynb   (음성 추출)
└── search_results/
    ├── pronunciation_patterns_*.csv
    └── audio_segments/*.wav
```

---

## 🔍 검색 기능

### 41_seoul_exploration.ipynb
**데이터 탐색**:
- 전체 통계
- 철자=발음 vs. 철자≠발음 비율
- 화자별 변이율

### 42_seoul_pronunciation.ipynb
**철자-발음 검색**:
- 특정 단어의 발음 변이
- 음운 규칙별 검색:
  - 경음화: `학교 → 학꾜`
  - 비음화: `국물 → 궁물`
  - 유음화: `신라 → 실라`
  - 축약: `하지 않아 → 안 해`

### 43_seoul_audio_extract.ipynb
**음성 추출**:
- 특정 단어의 음성 세그먼트 추출
- 시간 정보 활용 (word_xmin, word_xmax)
- WAV 파일로 저장

---

## 📊 산출물

- `pronunciation_patterns_YYYYMMDD.csv`: 철자-발음 변이 목록
- `audio_segments/`: 추출된 음성 파일

---

## 🚀 시작하기

```python
# Seoul Corpus 로드
import pandas as pd
df = pd.read_csv('g:/내 드라이브/DATA_2026/03_Seoul_Corpus/02_csv/02_seoul_corpus_enriched.csv',
                 encoding='utf-8-sig')

# 철자 ≠ 발음
df_var = df[df['pWord_ortho'] != df['pWord_prono']]
print(f"변이 발생: {len(df_var)} / {len(df)}")
```

---

**최종 업데이트**: 2026-02-10
