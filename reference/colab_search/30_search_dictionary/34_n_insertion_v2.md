# ㄴ/ㄹ 삽입 환경 검색 v2

**작성일**: 2026-02-10
**노트북**: `34_n_insertion_v2.ipynb`
**검토 가이드**: `REVIEW_GUIDE_V2.md`

---

## 🎯 v1 → v2 개선 사항

| 항목 | v1 | v2 |
|------|-----|-----|
| 형태소 출처 | seg_morph (자동 분석) | **dict_morph** (우리말샘 원본) ⭐ |
| 자음/모음 판별 | 한글 유니코드 | **word_roman** (로마자) ⭐ |
| ㄹ 삽입 | 없음 | **포함** (물엿[물렫]) ⭐ |
| 비교 정보 | seg_morph만 | **anal_morph 추가** ⭐ |
| 결과 | "경+우", "필+요" 포함 | 사전 복합명사만 |

---

## ✅ 포함된 정보 (모두 포함!)

### 기본 정보
- word, word_stem, sense_id
- definition (뜻풀이)

### 발음 정보
- **pron** (사전 발음)
- **pron_roman** (발음 로마자)
- **n_in_pron** / **l_in_pron** (사전 발음에 ㄴ/ㄹ 표기 여부)
- **insertion_type** (ㄴ삽입 / ㄹ삽입)

### 형태소 분석 (비교용)
- **dict_morph** (우리말샘 원본) ← 메인
- **word_roman** (로마자 표기)
- **seg_morph** (v7 정제 분석) ← 참조
- **anal_morph** (재분석) ← 참조
- seg_status, seg_links (품사 정보)
- morph1, morph2 (파싱된 형태소)
- morph1_roman, morph2_roman

### 빈도 정보
- **LS 빈도**: messenger, written, spoken, total
- **MP 빈도**: written, spoken, total
- **Freq_2009**: freq_06b (형태소), freq_13a (단어) - 강범모·김흥규 2009
- **형태소 빈도**: freq_morph1_LS, freq_morph2_LS

### 검토용 컬럼
- review_status
- morph_ok
- **n_insertion** ← 수동으로 채워야 함!
- decision
- notes

---

## ⚠️ 중요: 이 검색의 목적

**"ㄴ/ㄹ 삽입 환경"을 찾는 것**

- 조건: 자음 종성 + i/j(y) 초성
- 로마자: 자음 ending + i/y 시작
- **실제 삽입 여부는 수동으로 판단!**

### 포함되는 케이스:

#### ✅ 삽입이 일어나는 경우
```
솜-이불 → [솜니불]  (ㄴ 삽입 O)
물-엿 → [물렫]      (ㄹ 삽입 O)
```

#### ✅ 삽입이 안 일어나는 경우 (환경만 맞음)
```
밥-알 → [바발]      (ㅂ 약화 우선, ㄴ 삽입 X)
겉-옷 → [거돗]      (ㅅ 탈락 우선, ㄴ 삽입 X)
```

#### ✅ 방언 차이
```
밤-일 → [밤닐] (서울)  vs  [바밀] (경상)
```

**→ 모두 중요한 데이터!** `n_insertion` 컬럼에 yes/no/dialect 등을 채워야 함

---

## 📊 출력 컬럼 (총 35개)

| 그룹 | 컬럼 수 | 주요 컬럼 |
|------|---------|-----------|
| 기본 정보 | 3 | word, sense_id |
| 발음 정보 | 5 | pron, pron_roman, insertion_type, n_in_pron, l_in_pron |
| 형태소 분석 | 10 | dict_morph, word_roman, morph1/2, anal_morph, seg_morph |
| 빈도 정보 | 11 | freq_LS_total, freq_MP_total, freq_06b, freq_13a, freq_morph1_LS |
| 뜻풀이 | 1 | definition |
| 검토용 | 5 | n_insertion, decision, notes |

---

## 🚀 사용 방법

### 1️⃣ Colab 실행
```
34_n_insertion_v2.ipynb
→ Runtime → Run all
→ 결과: n_l_insertion_candidates_v2_YYYYMMDD_HHMMSS.csv
```

### 2️⃣ Google Sheets 열기
```
CSV → Google Sheets로 열기
```

### 3️⃣ 드롭다운 설정 (필수!)
```
morph_ok: yes, no, uncertain
n_insertion: yes, no, maybe, dialect, other
decision: keep, discard, uncertain
```

### 4️⃣ 수동 검토
**REVIEW_GUIDE_V2.md** 참고하여:
- **n_insertion** 컬럼 채우기
  - yes: 실제로 ㄴ/ㄹ 삽입됨
  - no: 환경만 맞고 삽입 안 됨
  - dialect: 방언 차이
  - maybe: 확인 필요
- **decision** 컬럼 채우기
  - keep: 최종 코퍼스 포함
  - discard: 제외

### 5️⃣ 저장
```
n_l_insertion_candidates_v2_YYYYMMDD_HHMMSS_reviewed.csv
```

---

## 📝 검토 예시

### 예시 1: ㄴ 삽입 O
```
단어: 솜이불
dict_morph: 솜-이불
pron: 솜니불
n_in_pron: yes

→ n_insertion: yes
→ decision: keep
→ notes: "사전 발음 확인"
```

### 예시 2: ㄴ 삽입 X (약화 우선)
```
단어: 밥알
dict_morph: 밥-알
pron: 바발
n_in_pron: no

→ n_insertion: no
→ decision: discard
→ notes: "ㅂ 약화 [바발], ㄴ 삽입 안 됨"
```

### 예시 3: 방언 차이
```
단어: 밤일
dict_morph: 밤-일
pron: 밤닐

→ n_insertion: dialect
→ decision: keep
→ notes: "서울: [밤닐], 경상: [바밀]"
```

---

## 🎯 다음 단계

1. **수동 검토 완료** → `decision = "keep"` 필터링
2. **형태소 통계** → 33_morpheme_stats.ipynb 실행
3. **Seoul Corpus** → 실제 발음 확인 (50_search_seoul/)
4. **통합 분석** → 90_integrated_analysis/

---

## 📚 관련 문서

- **REVIEW_GUIDE_V2.md**: 수동 검토 가이드 (자세함) ⭐
- **FREQUENCY_GUIDE.md**: 빈도 정보 해석
- **MORPH_FIELDS_GUIDE.md**: 형태소 필드 비교
- **CORPUS_PIPELINE.md**: 전체 파이프라인

---

## ⚡ Quick Start

```bash
# 1. Colab에서 34_n_insertion_v2.ipynb 실행
# 2. CSV 다운로드
# 3. Google Sheets에서 열기
# 4. REVIEW_GUIDE_V2.md 보면서 n_insertion 컬럼 채우기
# 5. decision = "keep"인 것만 추출
```

---

**핵심**: 환경은 맞지만 삽입이 안 되는 경우도 중요한 데이터입니다!
