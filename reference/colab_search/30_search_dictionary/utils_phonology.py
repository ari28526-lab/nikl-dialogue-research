"""
utils_phonology.py — 30번 사전 검색 공통 유틸리티
=================================================

사용법 (Colab 노트북 상단에서):
    %run /content/drive/MyDrive/DATA_2026/30_search_dictionary/utils_phonology.py

사용법 (로컬):
    %run utils_phonology.py
    또는
    exec(open('utils_phonology.py', encoding='utf-8').read())

포함 함수:
    [형태소 파싱]
    - parse_dict_morph(dict_morph) → 형태소 리스트
    - parse_dict_morph_with_boundaries(dict_morph) → (형태소, 경계유형)
    - parse_word_roman_by_morphemes(word_roman, morphemes_kor) → 로마자 형태소 리스트

    [어종 딕셔너리]
    - build_morpheme_origin_dict(df) → {형태소: 어종}
    - classify_compound_type(origin1, origin2) → "N+N" 등
    - get_compound_type_description(compound_type) → 한글 설명

    [로마자 자음/모음 분류]
    - ends_with_consonant_roman(roman_str) → bool
    - starts_with_i_j_roman(roman_str) → bool
    - get_final_sound_type(roman_str) → (char, type)
    - get_initial_sound_type(roman_str) → (char, type)
    - get_consonant_type(roman_char) → type
    - ends_with_consonant_type(roman_str) → (char, type)
    - starts_with_consonant_type(roman_str) → (char, type)
    - is_plain_obstruent(roman_str) → (bool, char)

    [한글 자모]
    - get_hangul_initial(char) → 초성 문자
    - get_hangul_final(char) → 종성 문자 또는 ''

    [ㄴ/ㄹ삽입 (34번)]
    - check_n_l_insertion_env(morphemes_kor, morphemes_roman) → 후보 리스트
    - detect_insertion_from_pron(morph1_roman, morph2_roman, pron_roman) → 감지 결과
    - get_m2_onset_type(morph2_roman) → 'j_glide' / 'i_vowel'
    - get_m1_coda_type(morph1_roman) → 'sonorant_non_ng' / 'ng' / 'obstruent'
    - get_m2_vowel_height(morph2_roman) → 'high' / 'non_high' / ''

    [유음화/비음화 (35번)]
    - check_nl_ln_at_boundary(morphemes_kor, morphemes_roman) → 후보 리스트
    - check_nl_ln_internal(word_roman) → 후보 리스트
    - get_expected_process(env_type) → 이론적 예상
    - detect_assimilation_from_pron(consonant1, consonant2, env_type, word_roman, pron_roman) → 감지

    [합성어경음화 (36번)]
    - check_fortis_environment(morphemes_kor, morphemes_roman) → 후보 리스트
    - detect_fortis_from_pron(morph2_roman, pron_roman) → (감지, 유형)
    - get_m2_initial_place(morph2_roman) → 조음위치
    - has_laryngeal_in_morph(morph_roman) → bool

버전: 2026-03-11 v1
"""

import pandas as pd
import numpy as np
import re


# ============================================================
# 1. 형태소 파싱
# ============================================================

def parse_dict_morph(dict_morph):
    """
    dict_morph 파싱 (하위 호환성 유지)
    예: "솜-이불" → ["솜", "이불"]
    """
    if pd.isna(dict_morph) or not dict_morph:
        return []
    morphemes = re.split(r'[-+]', str(dict_morph))
    return [m.strip() for m in morphemes if m.strip()]


def parse_dict_morph_with_boundaries(dict_morph):
    """
    dict_morph 파싱 + 경계 유형 정보 보존

    경계 유형:
    - '-': 'compound' (합성)
    - '+': 'derivation' (파생)

    Returns:
        (형태소 리스트, 경계 유형 리스트)

    예:
    - "손-가락" → (['손','가락'], ['compound'])
    - "먹+이" → (['먹','이'], ['derivation'])
    - "김+밥-말+이" → (['김','밥','말','이'], ['derivation','compound','derivation'])
    """
    if pd.isna(dict_morph) or not dict_morph:
        return [], []

    morphemes = []
    boundaries = []
    pattern = r'([^-+]+)([-+]?)'

    for match in re.finditer(pattern, str(dict_morph)):
        morph = match.group(1).strip()
        boundary = match.group(2)

        if morph:
            morphemes.append(morph)
            if boundary == '-':
                boundaries.append('compound')
            elif boundary == '+':
                boundaries.append('derivation')

    return morphemes, boundaries


def parse_word_roman_by_morphemes(word_roman, morphemes_kor):
    """
    word_roman을 형태소 단위로 재구성

    예:
      word_roman: "SOm-I-BUl"
      morphemes_kor: ["솜", "이불"]
      → ["SOm", "I-BUl"]
    """
    if pd.isna(word_roman) or not word_roman:
        return []

    syllables = str(word_roman).split('-')
    morpheme_lengths = [len(m) for m in morphemes_kor]

    if sum(morpheme_lengths) != len(syllables):
        return []

    result = []
    idx = 0
    for length in morpheme_lengths:
        morph_syllables = syllables[idx:idx + length]
        result.append('-'.join(morph_syllables))
        idx += length

    return result


# ============================================================
# 2. 어종 딕셔너리
# ============================================================

def _extract_origin_from_word_type(word_type):
    """word_type 문자열에서 어종 추출"""
    if pd.isna(word_type) or not word_type:
        return 'unknown'
    wt = str(word_type).lower()
    if '고유어' in wt:
        return '고유어'
    if '한자어' in wt:
        return '한자어'
    if '외래어' in wt:
        return '외래어'
    if '혼종어' in wt:
        return '혼종어'
    return 'unknown'


def build_sense_origin_dict(df):
    """
    v7_lexicon에서 sense_id → word_type 매핑 딕셔너리 구축

    sense_id (예: '45697:001')는 고유 키이므로 동음이의어 문제가 없다.
    seg_links에서 각 형태소의 sense_id를 파싱하여 이 딕셔너리를 조회한다.

    Returns:
        {sense_id: word_type} 딕셔너리
    """
    sense_dict = {}
    for _, row in df.iterrows():
        sid = row.get('sense_id', '')
        wt = row.get('word_type', '')
        if pd.isna(sid) or not sid:
            continue
        sid = str(sid).strip()
        if pd.notna(wt) and wt:
            sense_dict[sid] = _extract_origin_from_word_type(str(wt))

    print(f"sense_id 어종 딕셔너리: {len(sense_dict):,}개")
    return sense_dict


def get_morpheme_origins_from_seg_links(seg_links, sense_origin_dict):
    """
    seg_links 필드를 파싱하여 각 형태소의 어종을 반환

    seg_links 형식 예시:
      SOm/NNG(537178:001,537178:002)+I-BUl/NNG(1409052:008,742597:001)
      → 형태소1: 537178 → sense_dict에서 word_type 조회
      → 형태소2: 1409052 → sense_dict에서 word_type 조회

    Returns:
        [어종1, 어종2, ...] 리스트 (형태소 순서)
    """
    if pd.isna(seg_links) or not seg_links:
        return []

    seg_str = str(seg_links)
    # '+' 기준으로 형태소 분리 (로마자 안의 '-'는 음절 경계)
    morpheme_parts = seg_str.split('+')

    origins = []
    for part in morpheme_parts:
        # 괄호 안의 sense_no 추출: NNG(537178:001,537178:002)
        m = re.search(r'\(([^)]+)\)', part)
        if not m:
            origins.append('unknown')
            continue

        sense_ids = m.group(1).split(',')
        # 첫 번째 매칭되는 sense_id 사용
        origin = 'unknown'
        for sid in sense_ids:
            sid = sid.strip()
            # sense_id 전체 (예: '537178:001')로 매칭
            if sid in sense_origin_dict:
                origin = sense_origin_dict[sid]
                break
        origins.append(origin)

    return origins


def get_compound_origin_simple(word_type):
    """
    복합어의 word_type으로 간단히 compound_type 추정

    고유어 → N+N, 한자어 → S+S, 외래어 → L+L
    혼종어 → seg_links 파싱 필요 (이 함수로는 판별 불가)

    Returns: "N+N", "S+S", "L+L", "mixed", "unknown"
    """
    origin = _extract_origin_from_word_type(word_type)
    if origin == '고유어':
        return 'N+N'
    elif origin == '한자어':
        return 'S+S'
    elif origin == '외래어':
        return 'L+L'
    elif origin == '혼종어':
        return 'mixed'  # seg_links로 세분화 필요
    return 'unknown'


def classify_compound_type(morph1_origin, morph2_origin):
    """
    합성어 유형 분류 (어종 약어 조합)

    Returns: "N+N", "S+S", "N+S", "S+N", "L+N" 등
    """
    origin_map = {
        '고유어': 'N', '한자어': 'S', '외래어': 'L',
        '혼종어': 'H', 'unknown': 'U'
    }
    a1 = origin_map.get(morph1_origin, 'U')
    a2 = origin_map.get(morph2_origin, 'U')
    return f"{a1}+{a2}"


def get_compound_type_description(compound_type):
    """약어 조합 -> 한글 설명"""
    desc_map = {
        'N+N': '고유어+고유어', 'S+S': '한자어+한자어',
        'N+S': '고유어+한자어', 'S+N': '한자어+고유어',
        'L+N': '외래어+고유어', 'N+L': '고유어+외래어',
        'L+L': '외래어+외래어', 'S+L': '한자어+외래어',
        'L+S': '외래어+한자어', 'H+N': '혼종어+고유어',
        'N+H': '고유어+혼종어', 'H+S': '혼종어+한자어',
        'S+H': '한자어+혼종어',
    }
    return desc_map.get(compound_type, compound_type)


def classify_compound_type_from_row(row, sense_origin_dict):
    """
    v7 행에서 compound_type을 결정

    1순위: word_type이 고유어/한자어/외래어면 바로 N+N/S+S/L+L
    2순위: 혼종어이거나 세분화 필요 → seg_links 파싱
    3순위: seg_links 없으면 → unknown

    Returns: (compound_type, morph1_origin, morph2_origin)
    """
    word_type = str(row.get('word_type', ''))
    simple = get_compound_origin_simple(word_type)

    if simple != 'mixed' and simple != 'unknown':
        # 고유어/한자어/외래어: 각 형태소도 동일 어종으로 추정
        origin = _extract_origin_from_word_type(word_type)
        return simple, origin, origin

    # 혼종어 또는 unknown: seg_links 파싱
    seg_links = row.get('seg_links', '')
    origins = get_morpheme_origins_from_seg_links(seg_links, sense_origin_dict)

    if len(origins) >= 2:
        ct = classify_compound_type(origins[0], origins[1])
        return ct, origins[0], origins[1]
    elif len(origins) == 1:
        return classify_compound_type(origins[0], 'unknown'), origins[0], 'unknown'
    else:
        return 'unknown', 'unknown', 'unknown'


# ============================================================
# 3. 로마자 자음/모음 분류
# ============================================================

def ends_with_consonant_roman(roman_str):
    """로마자 표기가 자음으로 끝나는지 (모음: aeiou)"""
    if not roman_str:
        return False
    return roman_str[-1].lower() not in 'aeiou'


def starts_with_i_j_roman(roman_str):
    """
    로마자 표기가 i/j(y)로 시작하는지
    ㄴ/ㄹ 삽입 환경: 자음 + i/j(y)
    w는 제외 (와, 워, 위 등은 ㄴ 삽입 환경 아님)
    """
    if not roman_str:
        return False
    return roman_str[0].lower() in ['i', 'y']


def get_consonant_type(roman_char):
    """
    로마자 자음 분류
    Returns: 'nasal' / 'liquid' / 'obstruent' / 'vowel' / None
    """
    c = roman_char.lower()
    if c in ['m', 'n']:
        return 'nasal'
    if c in ['l', 'r']:
        return 'liquid'
    if c in ['a', 'e', 'i', 'o', 'u', 'y', 'w']:
        return 'vowel'
    if c in ['k', 'g', 't', 'd', 'p', 'b', 's', 'j', 'c', 'h', 'q', 'x', 'z', 'f', 'v']:
        return 'obstruent'
    return None


def ends_with_consonant_type(roman_str):
    """
    로마자 끝 자음 종류 반환
    Returns: ('n', 'nasal'), ('l', 'liquid'), ('ng', 'nasal'), etc. 또는 (None, None)
    """
    if not roman_str:
        return None, None

    # ng 처리
    if len(roman_str) >= 2 and roman_str[-2:].lower() == 'ng':
        return 'ng', 'nasal'

    last_char = roman_str[-1]
    char_type = get_consonant_type(last_char)

    if char_type in ['nasal', 'liquid', 'obstruent']:
        return last_char.lower(), char_type
    return None, None


def starts_with_consonant_type(roman_str):
    """로마자 첫 자음 종류 반환"""
    if not roman_str:
        return None, None

    first_char = roman_str[0]
    char_type = get_consonant_type(first_char)

    if char_type in ['nasal', 'liquid', 'obstruent']:
        return first_char.lower(), char_type
    return None, None


def get_final_sound_type(roman_str):
    """
    로마자 끝소리 분류 (모음 포함)
    Returns: (char, type) — type은 'vowel'/'nasal'/'liquid'/'obstruent'
    """
    if not roman_str:
        return None, None

    # ng 처리
    if len(roman_str) >= 2 and roman_str[-2:].lower() == 'ng':
        return 'ng', 'nasal'

    last_char = roman_str[-1].lower()

    if last_char in 'aeiou':
        return last_char, 'vowel'
    if last_char in ['m', 'n']:
        return last_char, 'nasal'
    if last_char in ['l', 'r']:
        return last_char, 'liquid'
    if last_char in ['k', 'g', 't', 'd', 'p', 'b', 's', 'j', 'c', 'h']:
        return last_char, 'obstruent'
    return None, None


def get_initial_sound_type(roman_str):
    """
    로마자 첫소리 분류 (모음 포함)
    Returns: (char, type)
    """
    if not roman_str:
        return None, None

    first_char = roman_str[0].lower()

    if first_char in 'aeiou':
        return first_char, 'vowel'
    if first_char in ['m', 'n']:
        return first_char, 'nasal'
    if first_char in ['l', 'r']:
        return first_char, 'liquid'
    if first_char in ['k', 'g', 't', 'd', 'p', 'b', 's', 'j', 'c', 'h', 'y', 'w']:
        return first_char, 'obstruent'
    return None, None


def is_plain_obstruent(roman_str):
    """
    평음 저해음으로 시작하는지 확인

    평음: K, T, P, J, S, G, D, B (단독 대문자 또는 소문자)
    경음: GG, DD, BB, JJ, SS, KK (같은 대문자 2개)
    격음: Kh(ㅋ), Th(ㅌ), Ph(ㅍ), Ch(ㅊ)  ← v1에서 누락, 이제 제외

    Returns: (bool, char) — char는 소문자 평음 문자
    """
    if not roman_str or len(roman_str) < 1:
        return False, None

    first_char = roman_str[0]

    # 대문자로 시작하는 경우
    if first_char in ['K', 'T', 'P', 'J', 'S', 'G', 'D', 'B']:
        if len(roman_str) >= 2:
            second_char = roman_str[1]
            # 경음: 같은 대문자 반복 (GG, DD, BB, JJ, SS, KK, TT, PP)
            if first_char == second_char:
                return False, None
            # 격음: h가 뒤따름 (Kh=ㅋ, Th=ㅌ, Ph=ㅍ, Ch=ㅊ)
            if second_char == 'h':
                return False, None
        return True, first_char.lower()

    # 소문자로 시작하는 경우
    if first_char in ['k', 't', 'p', 'j', 's', 'g', 'd', 'b']:
        if len(roman_str) >= 2:
            second_char = roman_str[1]
            # 경음: 소문자+대문자 동일 (kK, tT 등)
            if first_char.upper() == second_char:
                return False, None
        return True, first_char

    return False, None


# ============================================================
# 4. 한글 자모 추출
# ============================================================

_INITIALS = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ',
             'ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
_FINALS = ['','ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ',
           'ㄽ','ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ',
           'ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']

def get_hangul_initial(char):
    """한글 글자의 초성 반환"""
    if not char or len(char) != 1:
        return ''
    code = ord(char)
    if 0xAC00 <= code <= 0xD7A3:
        return _INITIALS[(code - 0xAC00) // 588]
    return ''

def get_hangul_final(char):
    """한글 글자의 종성 반환 (없으면 '')"""
    if not char or len(char) != 1:
        return ''
    code = ord(char)
    if 0xAC00 <= code <= 0xD7A3:
        return _FINALS[(code - 0xAC00) % 28]
    return ''


# ============================================================
# 5. ㄴ/ㄹ삽입 (34번) 함수
# ============================================================

def check_n_l_insertion_env(morphemes_kor, morphemes_roman):
    """
    로마자 기반 ㄴ/ㄹ 삽입 환경 확인

    ㄴ 삽입: morph1 끝 자음(ㄹ 제외) + morph2 시작 i/j(y)
    ㄹ 삽입: morph1 끝 l(ㄹ) + morph2 시작 i/j(y)

    Returns: [(m1_kor, m2_kor, m1_roman, m2_roman, insertion_type, position), ...]
    """
    if len(morphemes_kor) < 2 or len(morphemes_roman) < 2:
        return []
    if len(morphemes_kor) != len(morphemes_roman):
        return []

    candidates = []
    for i in range(len(morphemes_kor) - 1):
        m1_roman = morphemes_roman[i]
        m2_roman = morphemes_roman[i + 1]
        if not m1_roman or not m2_roman:
            continue

        m1_last = m1_roman.split('-')[-1]
        m2_first = m2_roman.split('-')[0]

        if not ends_with_consonant_roman(m1_last):
            continue
        if not starts_with_i_j_roman(m2_first):
            continue

        ins_type = 'ㄹ삽입' if m1_last[-1].lower() == 'l' else 'ㄴ삽입'

        candidates.append((
            morphemes_kor[i], morphemes_kor[i + 1],
            m1_roman, m2_roman, ins_type, i
        ))
    return candidates


def detect_insertion_from_pron(morph1_roman, morph2_roman, pron_roman_full, boundary_type='morpheme'):
    """
    pron_roman에서 실제 ㄴ/ㄹ 삽입 여부 자동 감지

    Returns:
        'n_inserted' / 'l_inserted' / 'no' / 'unknown'
        'no_pron_same_as_spelling' — pron 비어있음 = 철자=발음 = 삽입 없음
        'internal_unknown' — 단어 내부 후보 (형태소 경계 없어 판단 불가)
    """
    if not pron_roman_full or pd.isna(pron_roman_full) or str(pron_roman_full).strip() in ('', 'nan'):
        if boundary_type == 'internal':
            return 'internal_unknown'
        else:
            return 'no_pron_same_as_spelling'

    pron_clean = str(pron_roman_full).replace('ː', '')
    pron_syllables = pron_clean.split('-')

    m2_syllables = morph2_roman.split('-') if morph2_roman else []
    if not m2_syllables or not m2_syllables[0]:
        return 'no'
    m2_first = m2_syllables[0].upper()
    if not m2_first:
        return 'no'

    if len(m2_first) == 0:
        return 'no'
    m2_initial = m2_first[0]  # 첫 글자 미리 추출

    for pron_syl in pron_syllables:
        if not pron_syl:
            continue
        pu = pron_syl.upper()

        # ㄴ 삽입: I → NI
        if pu.startswith('N') and m2_initial in ('I', 'Y'):
            if len(pu) > 1 and pu[1] == m2_initial:
                return 'n_inserted'

        # ㄹ 삽입: iEOt → RiEOt
        if pu.startswith('R') and m2_initial in ('I', 'Y'):
            if len(pu) > 1 and pu[1] == m2_initial:
                return 'l_inserted'

        # 경음화
        if len(pu) >= 2 and pu[0:2] == m2_initial * 2:
            return 'no'

    # pron_roman이 있는데 삽입 패턴이 안 보임 → 삽입 없음
    return 'no'


def check_n_l_insertion_internal(word_roman):
    """
    단어 내부(형태소 경계 없음)에서 ㄴ/ㄹ삽입 환경 확인

    한자어 단일어로 등록된 단어에서도 실제 음절 경계에서
    자음 종성 + i/j 시작 → ㄴ삽입 환경이 존재할 수 있음
    예: 금융[금늉], 담요[담뇨] 등

    Returns: [{syllable1, syllable2, consonant1, onset_type, insertion_type, position}, ...]
    """
    if pd.isna(word_roman) or not word_roman:
        return []

    syllables = str(word_roman).split('-')
    if len(syllables) < 2:
        return []

    candidates = []
    for i in range(len(syllables) - 1):
        syl1 = syllables[i]
        syl2 = syllables[i + 1]
        if not syl1 or not syl2:
            continue

        if not ends_with_consonant_roman(syl1):
            continue
        if not starts_with_i_j_roman(syl2):
            continue

        c1, _ = ends_with_consonant_type(syl1)
        ins_type = 'ㄹ삽입' if (c1 and c1.lower() == 'l') else 'ㄴ삽입'

        # left/right_roman: 경계 기준 왼쪽/오른쪽 음절들을 묶어서 반환
        left_roman = '-'.join(syllables[:i+1])
        right_roman = '-'.join(syllables[i+1:])

        candidates.append({
            'syllable1': syl1,
            'syllable2': syl2,
            'left': ''.join(syllables[:i+1]),  # 한글 근사 (로마자임)
            'right': ''.join(syllables[i+1:]),
            'left_roman': left_roman,
            'right_roman': right_roman,
            'consonant1': c1 or '',
            'onset_type': 'i_or_j',
            'insertion_type': ins_type,
            'position': i,
        })

    return candidates


# --- 34번 조건 변수 함수 (세미나 3강-4강 기준) ---

def get_m2_onset_type(morph2_roman):
    """
    M2 초성이 /j/ 계열인지 /i/인지

    Returns: 'j_glide' / 'i_vowel' / ''

    - y로 시작 → j_glide (야, 여, 요, 유)
    - i + 모음 → j_glide (iA=야, iEO=여 등)
    - i 단독 또는 i + 자음 → i_vowel (이, 잎 등)
    """
    if not morph2_roman:
        return ''
    first_syl = morph2_roman.split('-')[0]
    if not first_syl:
        return ''

    fc = first_syl[0].lower()

    if fc == 'y':
        return 'j_glide'

    if fc == 'i':
        # i 뒤에 모음이 오면 활음 (iA, iEO, iO, iU)
        if len(first_syl) > 1 and first_syl[1].lower() in 'aeou':
            return 'j_glide'
        # 대문자 i 뒤에 대문자 → 다른 음절이므로 i_vowel
        return 'i_vowel'

    return ''


def get_m1_coda_type(morph1_roman):
    """
    M1 종성 자연부류 (세미나 3강: 공명음 > 장애음; 비ŋ공명음 > ŋ)

    Returns: 'sonorant_non_ng' / 'ng' / 'obstruent' / ''
    """
    if not morph1_roman:
        return ''
    last_syl = morph1_roman.split('-')[-1]
    c, ctype = ends_with_consonant_type(last_syl)
    if not c:
        return ''
    if c == 'ng':
        return 'ng'
    if ctype == 'nasal' or ctype == 'liquid':
        return 'sonorant_non_ng'
    if ctype == 'obstruent':
        return 'obstruent'
    return ''


def get_m2_vowel_height(morph2_roman):
    """
    M2의 /jV/에서 V가 고모음인지 (세미나 3강: 고모음 > 비고모음)

    고모음: i, u (이, 우)
    비고모음: a, e, o (아, 어, 오)

    Returns: 'high' / 'non_high' / ''
    """
    if not morph2_roman:
        return ''
    first_syl = morph2_roman.split('-')[0].lower()
    if not first_syl:
        return ''

    # y + 모음 패턴
    if first_syl[0] == 'y' and len(first_syl) > 1:
        vowel_after = first_syl[1]
        if vowel_after in ['i', 'u']:
            return 'high'
        return 'non_high'

    # i + 모음 패턴 (활음)
    if first_syl[0] == 'i' and len(first_syl) > 1 and first_syl[1] in 'aeou':
        vowel_after = first_syl[1]
        if vowel_after in 'u':  # iu(유)
            return 'high'
        return 'non_high'  # ia(야), ieo(여), io(요)

    # 단독 i → 고모음
    if first_syl[0] == 'i':
        return 'high'

    return ''


def get_branching_structure(morphemes_kor, boundaries):
    """
    분지 구조 판단 (3형태소 이상)

    Returns: 'binary' / 'left' / 'right' / 'flat' / ''

    2형태소 → 'binary'
    3형태소+: 경계 유형 조합으로 추론
      A-B+C → left (AB가 먼저 합성, C가 파생)
      A+B-C → right (A가 파생, BC가 합성)
      A-B-C → flat (판별 불가, 수동 태깅 필요)
    """
    n = len(morphemes_kor)
    if n < 2:
        return ''
    if n == 2:
        return 'binary'
    if n >= 3 and len(boundaries) >= 2:
        # 간단한 휴리스틱: 경계 유형 변화 지점
        if boundaries[0] == 'compound' and boundaries[1] == 'derivation':
            return 'left'
        if boundaries[0] == 'derivation' and boundaries[1] == 'compound':
            return 'right'
        return 'flat'
    return 'flat'


# ============================================================
# 6. 유음화/비음화 (35번) 함수
# ============================================================

def check_nl_ln_at_boundary(morphemes_kor, morphemes_roman):
    """
    형태소 경계에서 공명성 동화 환경 확인

    환경 유형:
    - ㄴㄹ: n + l/r (유음화)
    - ㄹㄴ: l + n (유음화)
    - 비음ㄹ: m/ng + l/r (유음화/비음화 경쟁)
    - 저해음ㄹ: k/t/p/s 등 + l/r (비음화)
    - 장애음ㄴ: k/t/p/s 등 + n (장애음 비음화) ← 신규
    - 장애음ㅁ: k/t/p/s 등 + m (장애음 비음화) ← 신규

    Returns: list of dict
    """
    if len(morphemes_kor) < 2 or len(morphemes_roman) < 2:
        return []
    if len(morphemes_kor) != len(morphemes_roman):
        return []

    candidates = []
    for i in range(len(morphemes_kor) - 1):
        m1_roman = morphemes_roman[i]
        m2_roman = morphemes_roman[i + 1]
        if not m1_roman or not m2_roman:
            continue

        m1_last = m1_roman.split('-')[-1]
        m2_first = m2_roman.split('-')[0]
        if not m1_last or not m2_first:
            continue

        c1, c1_type = ends_with_consonant_type(m1_last)
        c2, c2_type = starts_with_consonant_type(m2_first)
        if not c1 or not c2:
            continue

        env_type = None

        # ㄴ+ㄹ
        if c1 == 'n' and c2 in ['l', 'r']:
            env_type = 'ㄴㄹ'
        # ㄹ+ㄴ
        elif c1 == 'l' and c2 == 'n':
            env_type = 'ㄹㄴ'
        # 비음+ㄹ (ㄴ+ㄹ 제외)
        elif c1_type == 'nasal' and c2 in ['l', 'r']:
            env_type = '비음ㄹ'
        # 저해음+ㄹ
        elif c1_type == 'obstruent' and c2 in ['l', 'r']:
            env_type = '저해음ㄹ'
        # 장애음+ㄴ (신규: 장애음 비음화)
        elif c1_type == 'obstruent' and c2 == 'n':
            env_type = '장애음ㄴ'
        # 장애음+ㅁ (신규: 장애음 비음화)
        elif c1_type == 'obstruent' and c2 == 'm':
            env_type = '장애음ㅁ'

        if env_type:
            candidates.append({
                'morph1': morphemes_kor[i],
                'morph2': morphemes_kor[i + 1],
                'morph1_roman': m1_roman,
                'morph2_roman': m2_roman,
                'consonant1': c1,
                'consonant2': c2,
                'env_type': env_type,
                'position': i,
            })

    return candidates


def check_nl_ln_internal(word_roman):
    """
    단어 내부(형태소 경계 없음)에서 공명성 동화 환경 확인

    장애음+비음도 포함 (신규)
    """
    if pd.isna(word_roman) or not word_roman:
        return []

    syllables = str(word_roman).split('-')
    if len(syllables) < 2:
        return []

    candidates = []
    for i in range(len(syllables) - 1):
        syl1 = syllables[i]
        syl2 = syllables[i + 1]
        if not syl1 or not syl2:
            continue

        c1, c1_type = ends_with_consonant_type(syl1)
        c2, c2_type = starts_with_consonant_type(syl2)
        if not c1 or not c2:
            continue

        env_type = None

        if c1 == 'n' and c2 in ['l', 'r']:
            env_type = 'ㄴㄹ'
        elif c1 == 'l' and c2 == 'n':
            env_type = 'ㄹㄴ'
        elif c1_type == 'nasal' and c2 in ['l', 'r']:
            env_type = '비음ㄹ'
        elif c1_type == 'obstruent' and c2 in ['l', 'r']:
            env_type = '저해음ㄹ'
        elif c1_type == 'obstruent' and c2 == 'n':
            env_type = '장애음ㄴ'
        elif c1_type == 'obstruent' and c2 == 'm':
            env_type = '장애음ㅁ'

        if env_type:
            candidates.append({
                'syllable1': syl1,
                'syllable2': syl2,
                'consonant1': c1,
                'consonant2': c2,
                'env_type': env_type,
                'position': i,
            })

    return candidates


def get_expected_process(env_type):
    """
    환경 유형에 따른 이론적 예상 음운 변화

    Returns: 'lateralization' / 'nasalization' / 'obstruent_nasalization' / ''
    """
    mapping = {
        'ㄴㄹ': 'lateralization',      # 유음화 예상
        'ㄹㄴ': 'lateralization',      # 유음화 예상
        '비음ㄹ': 'lateralization',     # 유음화 예상 (경쟁)
        '저해음ㄹ': 'nasalization',     # 비음화 예상
        '장애음ㄴ': 'obstruent_nasalization',
        '장애음ㅁ': 'obstruent_nasalization',
    }
    return mapping.get(env_type, '')


def detect_assimilation_from_pron(consonant1, consonant2, env_type, word_roman, pron_roman):
    """
    pron_roman 기반 실제 동화 과정 감지

    Returns: 'lateralized' / 'nasalized' / 'no_change' / 'unknown'
    """
    if not pron_roman or pd.isna(pron_roman):
        return 'unknown'

    pron_clean = str(pron_roman).replace('ː', '').upper()
    word_clean = str(word_roman).upper()

    # 간단한 휴리스틱: pron에 ㄹㄹ 패턴이 있으면 유음화
    if 'LL' in pron_clean or 'RR' in pron_clean:
        if env_type in ['ㄴㄹ', 'ㄹㄴ', '비음ㄹ']:
            return 'lateralized'

    # pron에서 ㄴ이 유지/추가되면 비음화
    if env_type in ['저해음ㄹ', '비음ㄹ']:
        # 원래 l/r이었는데 pron에서 n으로 바뀜
        if consonant2 in ['l', 'r']:
            # word에 R/L이 있는데 pron에서 N으로 바뀐 패턴
            word_syls = word_clean.split('-')
            pron_syls = pron_clean.split('-')
            for ws, ps in zip(word_syls, pron_syls):
                if ws.startswith('R') and ps.startswith('N'):
                    return 'nasalized'
                if ws.startswith('L') and ps.startswith('N'):
                    return 'nasalized'

    return 'unknown'


# ============================================================
# 7. 합성어경음화 (36번) 함수
# ============================================================

def check_fortis_environment(morphemes_kor, morphemes_roman):
    """
    형태소 경계에서 합성어 경음화 환경 확인

    조건: morph2가 평음 저해음(k/t/p/j/s)으로 시작
    (격음 Kh/Th/Ph/Ch, 경음 GG/DD/BB/JJ/SS는 제외)
    """
    if len(morphemes_kor) < 2 or len(morphemes_roman) < 2:
        return []
    if len(morphemes_kor) != len(morphemes_roman):
        return []

    candidates = []
    for i in range(len(morphemes_kor) - 1):
        m1_roman = morphemes_roman[i]
        m2_roman = morphemes_roman[i + 1]
        if not m1_roman or not m2_roman:
            continue

        m1_last = m1_roman.split('-')[-1]
        m2_first = m2_roman.split('-')[0]
        if not m1_last or not m2_first:
            continue

        final_char, final_type = get_final_sound_type(m1_last)
        if not final_type:
            continue

        is_plain, initial_char = is_plain_obstruent(m2_first)
        if not is_plain:
            continue

        candidates.append({
            'morph1': morphemes_kor[i],
            'morph2': morphemes_kor[i + 1],
            'morph1_roman': m1_roman,
            'morph2_roman': m2_roman,
            'morph1_final_char': final_char,
            'morph1_final_type': final_type,
            'morph2_initial': initial_char,
            'position': i,
        })

    return candidates


def detect_fortis_from_pron(morph2_roman, pron_roman):
    """
    pron_roman에서 경음화 여부 감지

    원리: morph2 시작이 G(ㄱ)인데 pron에서 GG(ㄲ)이면 경음화
    대응: G→GG, D→DD, B→BB, J→JJ, S→SS

    Returns: (detected, fortis_type)
        detected: 'yes' / 'no' / 'unknown'
        fortis_type: 'G→GG' 등 또는 ''
    """
    if not pron_roman or pd.isna(pron_roman):
        return 'unknown', ''

    pron_clean = str(pron_roman).replace('ː', '')
    pron_syls = pron_clean.split('-')

    m2_first = morph2_roman.split('-')[0] if morph2_roman else ''
    if not m2_first:
        return 'unknown', ''

    # 평음 → 경음 대응
    plain_to_fortis = {
        'G': 'GG', 'D': 'DD', 'B': 'BB', 'J': 'JJ', 'S': 'SS',
        'K': 'GG', 'T': 'DD', 'P': 'BB',
    }

    first_char = m2_first[0]
    expected_fortis = plain_to_fortis.get(first_char, '')

    if not expected_fortis:
        return 'unknown', ''

    # pron에서 해당 경음 패턴 찾기
    for ps in pron_syls:
        if ps.upper().startswith(expected_fortis):
            return 'yes', f'{first_char}→{expected_fortis}'

    # 경음이 아닌 경우
    for ps in pron_syls:
        pu = ps.upper()
        if pu.startswith(first_char) and not pu.startswith(expected_fortis):
            return 'no', ''

    return 'unknown', ''


def get_m2_initial_place(morph2_roman):
    """
    N2 초성 조음위치 (세미나 5강: 연구개 > 치경 > 양순)

    Returns: 'velar' / 'alveolar' / 'bilabial' / 'palatal' / 'sibilant' / ''
    """
    if not morph2_roman:
        return ''
    first = morph2_roman.split('-')[0]
    if not first:
        return ''
    fc = first[0].lower()

    if fc in ['k', 'g']:
        return 'velar'
    if fc in ['t', 'd', 's']:
        return 'alveolar'
    if fc in ['p', 'b']:
        return 'bilabial'
    if fc in ['j', 'c']:
        return 'palatal'
    return ''


def has_laryngeal_in_morph(morph_roman):
    """
    형태소 내에 경음/격음이 있는지 (세미나 7강: 차단 조건)

    경음: GG, DD, BB, JJ, SS
    격음: Kh, Th, Ph, Ch

    Returns: bool
    """
    if not morph_roman:
        return False
    mr = str(morph_roman)

    # 경음 패턴
    fortis_patterns = ['GG', 'DD', 'BB', 'JJ', 'SS', 'KK', 'TT', 'PP']
    for pat in fortis_patterns:
        if pat in mr:
            return True

    # 격음 패턴
    aspirate_patterns = ['Kh', 'Th', 'Ph', 'Ch']
    for pat in aspirate_patterns:
        if pat in mr:
            return True

    return False


# ============================================================
# 완료 메시지
# ============================================================
print("[OK] utils_phonology.py 로드 완료")
print(f"   함수 {len([x for x in dir() if not x.startswith('_') and callable(eval(x))])}개")
