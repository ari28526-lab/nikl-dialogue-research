"""
어종 딕셔너리 버그 진단 스크립트
- 왜 compound_type이 전부 'Other'/'unknown'인지 원인 파악
- 결과를 .txt 파일로 저장

실행: Anaconda Prompt에서
  cd "G:\내 드라이브\DATA_2026\30_search_dictionary"
  python test_origin_diagnosis.py
"""

import pandas as pd
import re
from pathlib import Path

# ============================================================
# 1. 데이터 로드
# ============================================================
V7_PATH = '../10_dictionary_build/output/04_v7_lexicon.csv'
OUTPUT_PATH = 'test_origin_diagnosis_result.txt'

print("v7 lexicon 로딩 중...")
df = pd.read_csv(V7_PATH, encoding='utf-8-sig', low_memory=False)
print(f"로드 완료: {len(df):,}행")

results = []
def log(msg=""):
    print(msg)
    results.append(msg)

log("=" * 70)
log("어종 딕셔너리 버그 진단")
log("=" * 70)

# ============================================================
# 2. 전체 pos 분포
# ============================================================
log("\n【1. 전체 pos 분포 (상위 20)】")
for pos, cnt in df['pos'].value_counts().head(20).items():
    log(f"  {pos}: {cnt:,}")

# ============================================================
# 3. 전체 word_type 분포
# ============================================================
log("\n【2. 전체 word_type 분포】")
for wt, cnt in df['word_type'].value_counts().head(20).items():
    log(f"  {wt}: {cnt:,}")
log(f"  (null): {df['word_type'].isna().sum():,}")

# ============================================================
# 4. 핵심 형태소 검색 — 왜 딕셔너리에서 못 찾는지
# ============================================================
target_morphemes = [
    '솜', '이불', '물', '엿', '금', '색', '학', '교',
    '손', '가락', '밤', '길', '신', '라', '칼', '날',
    '심', '리', '독', '립', '력', '료', '꽃', '잎',
    '공', '간', '질', '연', '필', '요', '일',
]

log("\n【3. 핵심 형태소별 v7 매칭 결과】")
log(f"{'형태소':<6} {'pos':<10} {'word_type':<12} {'origin_lang':<15} {'dict_morph':<20}")
log("-" * 70)

for morph in target_morphemes:
    matches = df[df['word'] == morph]
    if len(matches) == 0:
        log(f"{morph:<6} NOT_FOUND")
    else:
        # 명사인 것과 아닌 것 구분
        for _, row in matches.head(5).iterrows():
            pos = str(row.get('pos', ''))
            wt = str(row.get('word_type', ''))
            ol = str(row.get('origin_lang', ''))
            dm = str(row.get('dict_morph', ''))
            is_noun = '✓' if pos == '명사' else ' '
            is_single = '✓' if (pd.isna(row['dict_morph']) or not re.search(r'[-+]', str(row['dict_morph']))) else ' '
            log(f"{morph:<6} {pos:<10} {wt:<12} {ol:<15} {dm:<20} 명사={is_noun} 단일={is_single}")

# ============================================================
# 5. 현재 코드 시뮬레이션: 명사 + 단일형태소만
# ============================================================
log("\n【4. 현재 코드 시뮬레이션 (명사 + 단일형태소만)】")

df_noun = df[df['pos'] == '명사'].copy()
df_single_noun = df_noun[
    (df_noun['dict_morph'].isna()) |
    (~df_noun['dict_morph'].str.contains(r'[-+]', na=False))
].copy()
log(f"전체: {len(df):,}")
log(f"명사만: {len(df_noun):,}")
log(f"명사 + 단일형태소: {len(df_single_noun):,}")

# 이 중 word_type이 있는 것
has_wt = df_single_noun['word_type'].notna().sum()
log(f"word_type 있음: {has_wt:,}")
log(f"word_type 없음: {len(df_single_noun) - has_wt:,}")

# 핵심 형태소가 이 필터에 포함되는지
log("\n핵심 형태소 포함 여부 (명사+단일):")
for morph in target_morphemes:
    found = df_single_noun[df_single_noun['word'] == morph]
    if len(found) > 0:
        wt = found.iloc[0].get('word_type', '')
        log(f"  {morph}: ✓ 포함 (word_type={wt})")
    else:
        # 왜 빠졌는지 진단
        in_noun = df_noun[df_noun['word'] == morph]
        in_all = df[df['word'] == morph]
        if len(in_noun) == 0 and len(in_all) > 0:
            pos_list = in_all['pos'].unique().tolist()
            log(f"  {morph}: ✗ 명사 아님 (pos={pos_list})")
        elif len(in_noun) > 0:
            dm_list = in_noun['dict_morph'].dropna().unique().tolist()[:3]
            log(f"  {morph}: ✗ 복합어 (dict_morph={dm_list})")
        else:
            log(f"  {morph}: ✗ v7에 없음")

# ============================================================
# 6. 개선안 시뮬레이션: 전 품사 + 단일형태소
# ============================================================
log("\n【5. 개선안: 전 품사 + 단일형태소】")

df_single_all = df[
    (df['dict_morph'].isna()) |
    (~df['dict_morph'].str.contains(r'[-+]', na=False))
].copy()
log(f"전 품사 + 단일형태소: {len(df_single_all):,}")

has_wt_all = df_single_all['word_type'].notna().sum()
log(f"word_type 있음: {has_wt_all:,}")

log("\n핵심 형태소 포함 여부 (전품사+단일):")
for morph in target_morphemes:
    found = df_single_all[df_single_all['word'] == morph]
    if len(found) > 0:
        wt_vals = found['word_type'].dropna().unique().tolist()
        pos_vals = found['pos'].unique().tolist()
        log(f"  {morph}: ✓ 포함 (pos={pos_vals}, word_type={wt_vals})")
    else:
        log(f"  {morph}: ✗ 없음")

# ============================================================
# 7. seg_links 활용 가능성
# ============================================================
log("\n【6. seg_links 필드 샘플 (복합어)】")
sample_compounds = ['솜이불', '꽃잎', '물엿', '색연필', '금요일', '손가락', '학교', '독립']
for w in sample_compounds:
    matches = df[df['word'] == w]
    if len(matches) > 0:
        row = matches.iloc[0]
        dm = row.get('dict_morph', '')
        sl = row.get('seg_links', '')
        wt = row.get('word_type', '')
        log(f"  {w}: dict_morph={dm}, word_type={wt}, seg_links={str(sl)[:80]}")

# ============================================================
# 8. word_type으로 직접 어종 판별 가능한 복합어
# ============================================================
log("\n【7. 복합어의 word_type 분포】")
df_compound = df[
    (df['dict_morph'].notna()) &
    (df['dict_morph'].str.contains(r'[-+]', na=False))
]
log(f"복합어 총: {len(df_compound):,}")
for wt, cnt in df_compound['word_type'].value_counts().head(10).items():
    log(f"  {wt}: {cnt:,}")
log(f"  (null): {df_compound['word_type'].isna().sum():,}")

# ============================================================
# 저장
# ============================================================
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))

print(f"\n결과 저장: {OUTPUT_PATH}")
