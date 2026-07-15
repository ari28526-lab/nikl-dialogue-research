"""
utils_phonology.py 검증 스크립트
================================

실행 방법 (Anaconda Prompt):
  cd "G:\내 드라이브\DATA_2026\30_search_dictionary"
  python test_utils_phonology.py

결과: test_utils_phonology_result.txt 저장
"""

import sys
import os

# utils_phonology.py 로드
exec(open('utils_phonology.py', encoding='utf-8').read())

import pandas as pd

results = []
pass_count = 0
fail_count = 0

def log(msg=""):
    print(msg)
    results.append(msg)

def check(name, actual, expected):
    global pass_count, fail_count
    ok = actual == expected
    if ok:
        pass_count += 1
        log(f"  [PASS] {name}")
    else:
        fail_count += 1
        log(f"  [FAIL] {name}: expected={expected}, got={actual}")


# ============================================================
log("=" * 70)
log("1. 형태소 파싱 테스트")
log("=" * 70)

m, b = parse_dict_morph_with_boundaries('솜-이불')
check('솜-이불 형태소', m, ['솜', '이불'])
check('솜-이불 경계', b, ['compound'])

m, b = parse_dict_morph_with_boundaries('먹+이')
check('먹+이 형태소', m, ['먹', '이'])
check('먹+이 경계', b, ['derivation'])

m, b = parse_dict_morph_with_boundaries('김+밥-말+이')
check('김+밥-말+이 형태소', m, ['김', '밥', '말', '이'])
check('김+밥-말+이 경계', b, ['derivation', 'compound', 'derivation'])

r = parse_word_roman_by_morphemes("SOm-I-BUl", ["솜", "이불"])
check('SOm-I-BUl 재구성', r, ['SOm', 'I-BUl'])

r = parse_word_roman_by_morphemes("GEOt-GA-RU", ["겉", "가루"])
check('GEOt-GA-RU 재구성', r, ['GEOt', 'GA-RU'])

r = parse_word_roman_by_morphemes("NA-MUt-Ip", ["나뭇", "잎"])
check('NA-MUt-Ip 재구성', r, ['NA-MUt', 'Ip'])


# ============================================================
log("\n" + "=" * 70)
log("2. 로마자 자음/모음 분류 테스트")
log("=" * 70)

check('SOm 자음끝', ends_with_consonant_roman('SOm'), True)
check('GA 모음끝', ends_with_consonant_roman('GA'), False)
check('GAng 자음끝', ends_with_consonant_roman('GAng'), True)

check('I 시작 i/j', starts_with_i_j_roman('I'), True)
check('iA 시작 i/j', starts_with_i_j_roman('iA'), True)
check('yA 시작 i/j', starts_with_i_j_roman('yA'), True)
check('wA 시작 NOT i/j', starts_with_i_j_roman('wA'), False)
check('Al 시작 NOT i/j', starts_with_i_j_roman('Al'), False)

check('SIn 끝 종류', ends_with_consonant_type('SIn'), ('n', 'nasal'))
check('KAl 끝 종류', ends_with_consonant_type('KAl'), ('l', 'liquid'))
check('GAng 끝 종류', ends_with_consonant_type('GAng'), ('ng', 'nasal'))
check('DOk 끝 종류', ends_with_consonant_type('DOk'), ('k', 'obstruent'))

check('GA 끝소리', get_final_sound_type('GA'), ('a', 'vowel'))
check('SOm 끝소리', get_final_sound_type('SOm'), ('m', 'nasal'))


# ============================================================
log("\n" + "=" * 70)
log("3. is_plain_obstruent 테스트 (격음 제외 수정 핵심)")
log("=" * 70)

check('GA 평음', is_plain_obstruent('GA'), (True, 'g'))
check('GYO 평음', is_plain_obstruent('GYO'), (True, 'g'))
check('KIl 평음', is_plain_obstruent('KIl'), (True, 'k'))
check('SAl 평음', is_plain_obstruent('SAl'), (True, 's'))
check('JA 평음', is_plain_obstruent('JA'), (True, 'j'))

# 경음 제외
check('GGA 경음 제외', is_plain_obstruent('GGA'), (False, None))
check('DDO 경음 제외', is_plain_obstruent('DDO'), (False, None))
check('BBA 경음 제외', is_plain_obstruent('BBA'), (False, None))
check('JJA 경음 제외', is_plain_obstruent('JJA'), (False, None))
check('SSA 경음 제외', is_plain_obstruent('SSA'), (False, None))

# 격음 제외 (v1 버그 수정!)
check('Kha 격음(ㅋ) 제외', is_plain_obstruent('Kha'), (False, None))
check('Tha 격음(ㅌ) 제외', is_plain_obstruent('Tha'), (False, None))
check('Pha 격음(ㅍ) 제외', is_plain_obstruent('Pha'), (False, None))
check('Cha 격음(ㅊ) 제외', is_plain_obstruent('Cha'), (False, None))
check('ThOp 격음(ㅌ) 제외', is_plain_obstruent('ThOp'), (False, None))


# ============================================================
log("\n" + "=" * 70)
log("4. ㄴ/ㄹ삽입 환경 테스트")
log("=" * 70)

r = check_n_l_insertion_env(['솜', '이불'], ['SOm', 'I-BUl'])
check('솜이불 ㄴ삽입 환경', len(r), 1)
check('솜이불 삽입유형', r[0][4] if r else '', 'ㄴ삽입')

r = check_n_l_insertion_env(['물', '엿'], ['MUl', 'iEOt'])
check('물엿 ㄹ삽입 환경', len(r), 1)
check('물엿 삽입유형', r[0][4] if r else '', 'ㄹ삽입')

r = check_n_l_insertion_env(['겉', '가루'], ['GEOt', 'GA-RU'])
check('겉가루 비환경 (a 시작)', len(r), 0)

r = check_n_l_insertion_env(['밥', '알'], ['BAp', 'Al'])
check('밥알 비환경 (a 시작)', len(r), 0)

# --- 단어내부 ㄴ/ㄹ삽입 ---
r = check_n_l_insertion_internal('GEUm-iUng')  # 금융
check('금융 내부 ㄴ삽입', len(r), 1)
check('금융 삽입유형', r[0]['insertion_type'] if r else '', 'ㄴ삽입')

r = check_n_l_insertion_internal('DAm-iO')  # 담요
check('담요 내부 ㄴ삽입', len(r), 1)

r = check_n_l_insertion_internal('HAl-iYUl')  # 할률 (ㄹ종성+i)
check('ㄹ+i 내부 ㄹ삽입', len(r), 1)
check('ㄹ+i 삽입유형', r[0]['insertion_type'] if r else '', 'ㄹ삽입')

r = check_n_l_insertion_internal('HAk-GYO')  # 학교 (비환경: j/i아님)
check('학교 내부 비환경', len(r), 0)


# ============================================================
log("\n" + "=" * 70)
log("5. 34번 조건 변수 테스트 (세미나 기준)")
log("=" * 70)

check('이불 m2_onset = i_vowel', get_m2_onset_type('I-BUl'), 'i_vowel')
check('엿 m2_onset = i_vowel→j?', get_m2_onset_type('iEOt'), 'j_glide')
check('요일 m2_onset = j_glide', get_m2_onset_type('iO-Il'), 'j_glide')
check('연필 m2_onset = j_glide', get_m2_onset_type('iEOn-PhIl'), 'j_glide')

check('SOm m1_coda = sonorant_non_ng', get_m1_coda_type('SOm'), 'sonorant_non_ng')
check('MUl m1_coda = sonorant_non_ng', get_m1_coda_type('MUl'), 'sonorant_non_ng')
check('GEOt m1_coda = obstruent', get_m1_coda_type('GEOt'), 'obstruent')
check('GAng m1_coda = ng', get_m1_coda_type('GAng'), 'ng')

check('I-BUl vowel_height = high', get_m2_vowel_height('I-BUl'), 'high')
check('iEOt vowel_height = non_high', get_m2_vowel_height('iEOt'), 'non_high')

check('2형태소 branching', get_branching_structure(['솜', '이불'], ['compound']), 'binary')
check('좌분지 A-B+C', get_branching_structure(['김', '밥', '이'], ['compound', 'derivation']), 'left')
check('우분지 A+B-C', get_branching_structure(['접', '두', '어'], ['derivation', 'compound']), 'right')


# ============================================================
log("\n" + "=" * 70)
log("6. 유음화/비음화 환경 테스트 (장애음 비음화 포함)")
log("=" * 70)

r = check_nl_ln_at_boundary(['신', '라'], ['SIn', 'RA'])
check('신라 ㄴㄹ', r[0]['env_type'] if r else '', 'ㄴㄹ')

r = check_nl_ln_at_boundary(['칼', '날'], ['KAl', 'NAl'])
check('칼날 ㄹㄴ', r[0]['env_type'] if r else '', 'ㄹㄴ')

r = check_nl_ln_at_boundary(['심', '리'], ['SIm', 'RI'])
check('심리 비음ㄹ', r[0]['env_type'] if r else '', '비음ㄹ')

r = check_nl_ln_at_boundary(['독', '립'], ['DOk', 'RIp'])
check('독립 저해음ㄹ', r[0]['env_type'] if r else '', '저해음ㄹ')

# 장애음 비음화 (신규)
r = check_nl_ln_at_boundary(['국', '민'], ['GUk', 'MIn'])
check('국민 장애음ㅁ', r[0]['env_type'] if r else '', '장애음ㅁ')

r = check_nl_ln_at_boundary(['학', '년'], ['HAk', 'NiEOn'])
check('학년 장애음ㄴ', r[0]['env_type'] if r else '', '장애음ㄴ')

r = check_nl_ln_at_boundary(['십', '년'], ['SIp', 'NiEOn'])
check('십년 장애음ㄴ', r[0]['env_type'] if r else '', '장애음ㄴ')

# 이론적 예상
check('ㄴㄹ 예상 유음화', get_expected_process('ㄴㄹ'), 'lateralization')
check('저해음ㄹ 예상 비음화', get_expected_process('저해음ㄹ'), 'nasalization')
check('장애음ㄴ 예상 비음화', get_expected_process('장애음ㄴ'), 'obstruent_nasalization')


# ============================================================
log("\n" + "=" * 70)
log("7. 합성어경음화 환경 테스트")
log("=" * 70)

r = check_fortis_environment(['손', '가락'], ['SOn', 'GA-RAk'])
check('손가락 경음화 환경', len(r), 1)
if r:
    check('손가락 m1_final_type', r[0]['morph1_final_type'], 'nasal')
    check('손가락 m2_initial', r[0]['morph2_initial'], 'g')

r = check_fortis_environment(['학', '교'], ['HAk', 'GYO'])
check('학교 경음화 환경', len(r), 1)
if r:
    check('학교 m1_final_type', r[0]['morph1_final_type'], 'obstruent')

# 격음은 제외되어야 함
r = check_fortis_environment(['손', '칼'], ['SOn', 'KhAl'])
check('손칼 격음(ㅋ) 제외', len(r), 0)

r = check_fortis_environment(['발', '톱'], ['BAl', 'ThOp'])
check('발톱 격음(ㅌ) 제외', len(r), 0)

# 경음도 제외
r = check_fortis_environment(['밤', '꽃'], ['BAm', 'GGOt'])
check('밤꽃 경음(ㄲ) 제외', len(r), 0)

# detect_fortis_from_pron
d, ft = detect_fortis_from_pron('GA-RAk', 'SOn-GGA-RAk')
check('손가락 경음화 감지', d, 'yes')

d, ft = detect_fortis_from_pron('GYO', 'HAk-GGiO')
check('학교 경음화 감지', d, 'yes')

# 조음위치
check('GA 조음위치 velar', get_m2_initial_place('GA-RAk'), 'velar')
check('DA 조음위치 alveolar', get_m2_initial_place('DA-RI'), 'alveolar')
check('BA 조음위치 bilabial', get_m2_initial_place('BAl'), 'bilabial')

# 후두자질 차단
check('GGOt 경음 있음', has_laryngeal_in_morph('GGOt'), True)
check('KhAl 격음 있음', has_laryngeal_in_morph('KhAl'), True)
check('GA-RAk 없음', has_laryngeal_in_morph('GA-RAk'), False)


# ============================================================
log("\n" + "=" * 70)
log("8. 한글 자모 테스트")
log("=" * 70)

check('가 초성', get_hangul_initial('가'), 'ㄱ')
check('솜 초성', get_hangul_initial('솜'), 'ㅅ')
check('힘 초성', get_hangul_initial('힘'), 'ㅎ')

check('솜 종성', get_hangul_final('솜'), 'ㅁ')
check('가 종성(없음)', get_hangul_final('가'), '')
check('닭 종성', get_hangul_final('닭'), 'ㄺ')
check('밤 종성', get_hangul_final('밤'), 'ㅁ')


# ============================================================
log("\n" + "=" * 70)
log("9. 어종 딕셔너리 테스트 (v7 로드)")
log("=" * 70)

V7_PATH = '../10_dictionary_build/output/04_v7_lexicon.csv'
if os.path.exists(V7_PATH):
    log("v7 lexicon 로딩...")
    df_v7 = pd.read_csv(V7_PATH, encoding='utf-8-sig', low_memory=False)
    log(f"v7: {len(df_v7):,}행")

    # --- sense_no 기반 어종 딕셔너리 구축 ---
    sense_origin_dict = build_sense_origin_dict(df_v7)

    # --- 복합어 word_type 직접 사용 테스트 ---
    log("\n복합어 word_type 직접 사용:")
    compound_tests = {
        '솜이불': ('고유어', 'N+N'),
        '색연필': ('한자어', 'S+S'),
        '물엿': ('고유어', 'N+N'),
        '꽃잎': ('고유어', 'N+N'),
        '금요일': ('한자어', 'S+S'),
        '손가락': ('고유어', 'N+N'),
        '학교': ('한자어', 'S+S'),
        '독립': ('한자어', 'S+S'),
    }
    for word, (exp_wt, exp_ct) in compound_tests.items():
        matches = df_v7[df_v7['word'] == word]
        if len(matches) > 0:
            row = matches.iloc[0]
            wt = str(row.get('word_type', ''))
            simple_ct = get_compound_origin_simple(wt)
            check(f'{word} word_type={exp_wt}', _extract_origin_from_word_type(wt), exp_wt)
            check(f'{word} compound_type={exp_ct}', simple_ct, exp_ct)
        else:
            log(f"  [WARN] {word} v7에 없음")

    # --- seg_links 파싱 테스트 (혼종어 세분화) ---
    log("\nseg_links 파싱 테스트:")
    # 솜이불: seg_links에서 각 형태소 sense_no 조회
    matches = df_v7[df_v7['word'] == '솜이불']
    if len(matches) > 0:
        row = matches.iloc[0]
        ct, o1, o2 = classify_compound_type_from_row(row, sense_origin_dict)
        check(f'솜이불 seg_links -> {o1}+{o2}', ct, 'N+N')

    matches = df_v7[df_v7['word'] == '색연필']
    if len(matches) > 0:
        row = matches.iloc[0]
        ct, o1, o2 = classify_compound_type_from_row(row, sense_origin_dict)
        check(f'색연필 seg_links -> {o1}+{o2}', ct, 'S+S')

    # 혼종어 테스트 — 혼종어는 seg_links로 세분화
    log("\n혼종어 세분화 테스트:")
    df_mixed = df_v7[df_v7['word_type'] == '혼종어'].head(5)
    for _, row in df_mixed.iterrows():
        word = row.get('word', '')
        ct, o1, o2 = classify_compound_type_from_row(row, sense_origin_dict)
        log(f"  {word}: {ct} ({o1}+{o2})")

    # --- classify_compound_type 기본 테스트 ---
    log("\nclassify_compound_type 기본:")
    check('N+N', classify_compound_type('고유어', '고유어'), 'N+N')
    check('S+S', classify_compound_type('한자어', '한자어'), 'S+S')
    check('N+S', classify_compound_type('고유어', '한자어'), 'N+S')
    check('S+N', classify_compound_type('한자어', '고유어'), 'S+N')

else:
    log(f"[WARN] v7 lexicon 없음: {V7_PATH}")
    log("   어종 딕셔너리 테스트 스킵")


# ============================================================
log("\n" + "=" * 70)
log(f"결과: {pass_count} PASS / {fail_count} FAIL")
log("=" * 70)

# 결과는 > 리다이렉트로 저장 (스크립트 내부 저장 제거 — 파일 충돌 방지)
