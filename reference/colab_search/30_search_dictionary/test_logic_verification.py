#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
34_n_insertion_v2.ipynb 로직 검증 테스트
"""

import re

# 함수 정의 (노트북과 동일)
def ends_with_consonant_roman(roman_str):
    """자음으로 끝나는지 확인"""
    if not roman_str:
        return False
    last_char = roman_str[-1].lower()
    vowels = 'aeiou'
    return last_char not in vowels

def starts_with_i_j_roman(roman_str):
    """i, j(y)로 시작하는지 - w 제외!"""
    if not roman_str:
        return False
    first_char = roman_str[0].lower()
    return first_char in ['i', 'y']

def parse_dict_morph(dict_morph):
    """dict_morph 파싱"""
    if not dict_morph:
        return []
    morphemes = re.split(r'[-+]', dict_morph)
    return [m.strip() for m in morphemes if m.strip()]

def parse_word_roman_by_morphemes(word_roman, morphemes_kor):
    """word_roman을 형태소 단위로 재구성"""
    if not word_roman:
        return []

    syllables = word_roman.split('-')
    morpheme_lengths = [len(m) for m in morphemes_kor]

    if sum(morpheme_lengths) != len(syllables):
        return []

    result = []
    syllable_index = 0

    for length in morpheme_lengths:
        morph_syllables = syllables[syllable_index:syllable_index + length]
        result.append('-'.join(morph_syllables))
        syllable_index += length

    return result

def check_n_l_insertion_env(morphemes_kor, morphemes_roman):
    """ㄴ/ㄹ 삽입 환경 확인"""
    if len(morphemes_kor) < 2 or len(morphemes_roman) < 2:
        return []

    if len(morphemes_kor) != len(morphemes_roman):
        return []

    candidates = []

    for i in range(len(morphemes_kor) - 1):
        m1_kor = morphemes_kor[i]
        m2_kor = morphemes_kor[i + 1]
        m1_roman = morphemes_roman[i]
        m2_roman = morphemes_roman[i + 1]

        if not m1_roman or not m2_roman:
            continue

        m1_syllables = m1_roman.split('-')
        m1_last = m1_syllables[-1] if m1_syllables else ''

        m2_syllables = m2_roman.split('-')
        m2_first = m2_syllables[0] if m2_syllables else ''

        if not m1_last or not m2_first:
            continue

        # 선행: 자음 종성
        if not ends_with_consonant_roman(m1_last):
            continue

        # 후행: i/j(y) 시작
        if not starts_with_i_j_roman(m2_first):
            continue

        insertion_type = 'ㄹ삽입' if m1_last[-1].lower() == 'l' else 'ㄴ삽입'
        candidates.append((m1_kor, m2_kor, m1_roman, m2_roman, insertion_type, i))

    return candidates

# 테스트 케이스
print("=" * 70)
print("34_n_insertion_v2.ipynb 로직 검증 테스트")
print("=" * 70)

test_cases = [
    # (단어, dict_morph, word_roman, 예상결과)
    ("솜이불", "솜-이불", "SOm-I-BUl", True, "ㄴ삽입"),
    ("물엿", "물-엿", "MUl-iEOt", True, "ㄹ삽입"),
    ("밤일", "밤-일", "BAm-Il", True, "ㄴ삽입"),
    ("겉가루", "겉-가루", "GEOt-GA-RU", False, None),  # 자음 ㄱ
    ("밥알", "밥-알", "BAb-Al", False, None),  # 'a'로 시작
    ("꽃오징어", "꽃-오징어", "GGOt-O-JiNG-EO", False, None),  # 'o'로 시작
    ("빗어귀", "빗-어귀", "BIt-EO-GWI", False, None),  # 'e'로 시작
    ("나뭇잎", "나뭇-잎", "NA-MUt-Ip", True, "ㄴ삽입"),  # 음절 3개, 형태소 2개
    ("강아지", "강-아지", "GAng-A-Ji", False, None),  # 'a'로 시작
]

print("\n테스트 케이스 검증:\n")

all_pass = True
for word, dict_morph, word_roman, should_match, expected_type in test_cases:
    # 1. 형태소 파싱
    morphemes_kor = parse_dict_morph(dict_morph)

    # 2. word_roman 재구성
    morphemes_roman = parse_word_roman_by_morphemes(word_roman, morphemes_kor)

    # 3. 환경 체크
    env_list = check_n_l_insertion_env(morphemes_kor, morphemes_roman)

    # 4. 결과 검증
    matched = len(env_list) > 0

    if matched and should_match:
        insertion_type = env_list[0][4]
        if insertion_type == expected_type:
            status = "✅ PASS"
        else:
            status = f"❌ FAIL (예상: {expected_type}, 실제: {insertion_type})"
            all_pass = False
    elif not matched and not should_match:
        status = "✅ PASS"
    elif matched and not should_match:
        status = f"❌ FAIL (예상: 제외, 실제: 포함됨)"
        all_pass = False
    else:
        status = f"❌ FAIL (예상: 포함, 실제: 제외됨)"
        all_pass = False

    print(f"{status} | {word:8s} | {dict_morph:12s} | morphs_kor: {morphemes_kor} | morphs_roman: {morphemes_roman}")

print("\n" + "=" * 70)

if all_pass:
    print("🎉 모든 테스트 통과! 노트북 로직이 정확합니다.")
else:
    print("⚠️  일부 테스트 실패! 코드를 다시 확인해야 합니다.")

print("=" * 70)

# 추가 검증: 함수별 단위 테스트
print("\n함수별 단위 테스트:\n")

print("1. ends_with_consonant_roman():")
print(f"   SOm (ㅁ): {ends_with_consonant_roman('SOm')} (예상: True)")
print(f"   GA (ㅏ): {ends_with_consonant_roman('GA')} (예상: False)")
print(f"   MUl (ㄹ): {ends_with_consonant_roman('MUl')} (예상: True)")

print("\n2. starts_with_i_j_roman():")
print(f"   I (이): {starts_with_i_j_roman('I')} (예상: True)")
print(f"   iA (야): {starts_with_i_j_roman('iA')} (예상: True)")
print(f"   yA (야): {starts_with_i_j_roman('yA')} (예상: True)")
print(f"   wA (와): {starts_with_i_j_roman('wA')} (예상: False)")
print(f"   Al (알): {starts_with_i_j_roman('Al')} (예상: False)")
print(f"   O (오): {starts_with_i_j_roman('O')} (예상: False)")

print("\n3. parse_word_roman_by_morphemes():")
test_parse = parse_word_roman_by_morphemes("SOm-I-BUl", ["솜", "이불"])
print(f"   'SOm-I-BUl' + ['솜', '이불']: {test_parse}")
print(f"   예상: ['SOm', 'I-BUl'] | 일치: {test_parse == ['SOm', 'I-BUl']}")

print("\n" + "=" * 70)
print("검증 완료!")
