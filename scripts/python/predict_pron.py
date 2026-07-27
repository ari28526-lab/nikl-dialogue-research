# -*- coding: utf-8 -*-
"""predict_pron.py - 검색 마스터 v1: 철자열·예측 발음열 생성

form(한글 어절) + tagged(형태소 분석) 을 받아 다음을 만든다:
  form_roman        철자 전자(轉字) — roman_mfa, 종성 원자 보존(중화 전)
  pron_pred_hangul  필수(의무) 규칙 적용 후 표면 한글
  pron_pred_roman   위의 roman_mfa (종성 7종 중화)
  pron_pred_ipa     _roman_mfa_to_ipa.csv 변환

표기 규약(사용자 확정 2026-07-23): 음소=공백, 음절='_', 어절='|',
초성 대문자·종성 소문자. 자리표시자는 음절 '_'와 겹치지 않게 '∅'.
정본 토큰 집합=_roman_mfa_to_ipa.csv (빈도사전과 단일화).

규칙(설계 결정 2 = 필수 규칙만). 사용자 확정(2026-07-23):
 - 인벤토리·순서 현행 유지 + '용언 어간+어미 경음화'(신+고→신꼬) 추가.
 - 'ㄹ비음화'(담력→담녁, 강릉→강능)는 v1 미적용(추후 한자어 경계와 함께).
 - 어절 내부에만 적용(어절 간 연음/동화 미적용 — 어절 정렬 보존).
 - 수의적 규칙(ㄴ삽입·합성어경음화·위치동화 등)은 미구현
   (B단계에서 연구자의 수동 실현 판정과 대조).

적용 순서와 feeding/bleeding (사용자 요청 '나누자' 반영):
 1 격음화  2 ㅎ탈락  3 구개음화  4 연음  5 중화  6 겹받침단순화  7 비음/유음  8 경음화
 · feeding: ㅎ탈락→연음(싫어→시러), 겹받침단순화→경음화(넓게→널께),
            중화→경음화(꽃도→꼳또), 중화→비음화(밥는? 없음/닫는→단는).
 · bleeding: 연음 bleeds 중화(옷이: 연음이 먼저라 [오시], 중화 안 됨),
             구개음화 bleeds 연음(굳이: 구개음화 먼저라 [구지], ㄷ 연음 아님),
             격음화 bleeds 중화(좋다: ㅎ+ㄷ→ㅌ, ㅎ 중화 소멸).

실행:  python predict_pron.py --selftest      # 단위테스트
       python predict_pron.py --demo "국물 신라 좋다"   # 즉석 확인
"""
import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 표기 구분자
PHON_SEP = " "
SYL_SEP = " _ "      # 로마자 음절 경계 (음소 공백 유지 위해 좌우 공백)
IPA_SYL_SEP = "_"    # IPA 음절 경계
EOJEOL_SEP = " | "
PLACEHOLDER = "∅"    # 숫자·외국어·비언어 어절 자리표시(음절 '_'와 구분)

# ============================================================
# 1. 자모 테이블 · 로마자 매핑
# ============================================================
CHO = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
JUNG = ['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ',
        'ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ']
JONG = ['','ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ',
        'ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']

ONSET_ROMAN = {'ㄱ':'G','ㄲ':'KK','ㄴ':'N','ㄷ':'D','ㄸ':'TT','ㄹ':'R',
               'ㅁ':'M','ㅂ':'B','ㅃ':'PP','ㅅ':'S','ㅆ':'SS','ㅇ':'',
               'ㅈ':'J','ㅉ':'JJ','ㅊ':'CH','ㅋ':'K','ㅌ':'T','ㅍ':'P','ㅎ':'H'}
VOWEL_ROMAN = {'ㅏ':'A','ㅐ':'AE','ㅑ':'YA','ㅒ':'YAE','ㅓ':'EO','ㅔ':'E',
               'ㅕ':'YEO','ㅖ':'YE','ㅗ':'O','ㅘ':'WA','ㅙ':'WAE','ㅚ':'OE',
               'ㅛ':'YO','ㅜ':'U','ㅝ':'WO','ㅞ':'WE','ㅟ':'WI','ㅠ':'YU',
               'ㅡ':'EU','ㅢ':'UI','ㅣ':'I'}
# 발음(중화) 종성: 표면에 실제 나올 수 있는 7종만
PRON_CODA_ROMAN = {'':'', 'ㄱ':'k','ㄴ':'n','ㄷ':'t','ㄹ':'l','ㅁ':'m',
                   'ㅂ':'p','ㅇ':'ng'}
# 철자 전자용 종성(원자 보존·겹받침·격음) — form_roman·tagged_roman 전용
SPELL_CODA_ROMAN = {'':'', 'ㄱ':'k','ㄲ':'kk','ㄳ':'ks','ㄴ':'n','ㄵ':'nj',
                    'ㄶ':'nh','ㄷ':'t','ㄹ':'l','ㄺ':'lk','ㄻ':'lm','ㄼ':'lp',
                    'ㄽ':'ls','ㄾ':'lt','ㄿ':'lph','ㅀ':'lh','ㅁ':'m','ㅂ':'p',
                    'ㅄ':'ps','ㅅ':'s','ㅆ':'ss','ㅇ':'ng','ㅈ':'j','ㅊ':'ch',
                    'ㅋ':'kh','ㅌ':'th','ㅍ':'ph','ㅎ':'h'}


# ============================================================
# 2. 한글 분해·결합
# ============================================================
def is_syllable(ch):
    return len(ch) == 1 and 0xAC00 <= ord(ch) <= 0xD7A3

def decompose(ch):
    s = ord(ch) - 0xAC00
    return [CHO[s // 588], JUNG[(s % 588) // 28], JONG[s % 28]]

def compose(cho, jung, jong):
    return chr(0xAC00 + (CHO.index(cho) * 21 + JUNG.index(jung)) * 28
               + JONG.index(jong))

# ============================================================
# 3. 필수 규칙 (음절 트리플[초성,중성,종성] 리스트를 제자리 수정, 어절 단위)
# ============================================================
NEUTRALIZE = {'ㅋ':'ㄱ','ㄲ':'ㄱ','ㅅ':'ㄷ','ㅆ':'ㄷ','ㅈ':'ㄷ','ㅊ':'ㄷ',
              'ㅌ':'ㄷ','ㅎ':'ㄷ','ㅍ':'ㅂ'}
CLUSTER = {'ㄳ':'ㄱ','ㄵ':'ㄴ','ㄶ':'ㄴ','ㄺ':'ㄱ','ㄻ':'ㅁ','ㄼ':'ㄹ',
           'ㄽ':'ㄹ','ㄾ':'ㄹ','ㄿ':'ㅂ','ㅀ':'ㄹ','ㅄ':'ㅂ'}
LINK_CLUSTER = {'ㄳ':('ㄱ','ㅅ'),'ㄵ':('ㄴ','ㅈ'),'ㄺ':('ㄹ','ㄱ'),
                'ㄻ':('ㄹ','ㅁ'),'ㄼ':('ㄹ','ㅂ'),'ㄽ':('ㄹ','ㅅ'),
                'ㄾ':('ㄹ','ㅌ'),'ㄿ':('ㄹ','ㅍ'),'ㅄ':('ㅂ','ㅅ')}
TENSE = {'ㄱ':'ㄲ','ㄷ':'ㄸ','ㅂ':'ㅃ','ㅅ':'ㅆ','ㅈ':'ㅉ'}
# 용언 어간+어미 경음화 (표준발음법 24·25항)
STEM_POS = {'VV', 'VA', 'VX', 'VCP', 'VCN'}
ENDING_POS = {'EC', 'EP', 'EF', 'ETM', 'ETN', 'EG'}
STEM_CODA_TRIGGER = {'ㄴ', 'ㅁ', 'ㄵ', 'ㄻ', 'ㄼ', 'ㄾ'}  # 어간 받침(ㄹ 제외)
FORTABLE_ONSET = {'ㄱ', 'ㄷ', 'ㅅ', 'ㅈ'}                  # 어미 첫 평음


def r_aspiration(syls):
    """격음화(자음축약): ㅎ+평장애음 / 평장애음+ㅎ -> 격음."""
    for i in range(len(syls) - 1):
        c1, c2 = syls[i][2], syls[i + 1][0]
        if c1 in ('ㅎ', 'ㄶ', 'ㅀ') and c2 in ('ㄱ', 'ㄷ', 'ㅈ', 'ㅅ'):
            syls[i + 1][0] = {'ㄱ':'ㅋ','ㄷ':'ㅌ','ㅈ':'ㅊ','ㅅ':'ㅆ'}[c2]
            syls[i][2] = {'ㅎ':'', 'ㄶ':'ㄴ', 'ㅀ':'ㄹ'}[c1]
        elif c2 == 'ㅎ':
            base = NEUTRALIZE.get(c1, c1)
            if base in ('ㄱ', 'ㄷ', 'ㅂ'):
                syls[i + 1][0] = {'ㄱ':'ㅋ','ㄷ':'ㅌ','ㅂ':'ㅍ'}[base]
                syls[i][2] = ''

def r_h_deletion(syls):
    """ㅎ 탈락: 종성 ㅎ계열 + 초성 ㅇ(모음) -> ㅎ 제거(이후 연음)."""
    for i in range(len(syls) - 1):
        c1 = syls[i][2]
        if syls[i + 1][0] == 'ㅇ' and c1 in ('ㅎ', 'ㄶ', 'ㅀ'):
            syls[i][2] = {'ㅎ':'', 'ㄶ':'ㄴ', 'ㅀ':'ㄹ'}[c1]

def r_palatalization(syls):
    """구개음화: 종성 ㄷ/ㅌ + 이/히 -> ㅈ/ㅊ (표면 조건만; 동형 음절 부재)."""
    for i in range(len(syls) - 1):
        c1 = syls[i][2]
        nxt = syls[i + 1]
        if c1 in ('ㄷ', 'ㅌ') and nxt[1] == 'ㅣ' and nxt[0] in ('ㅇ', 'ㅎ'):
            nxt[0] = 'ㅈ' if (c1 == 'ㄷ' and nxt[0] == 'ㅇ') else 'ㅊ'
            syls[i][2] = ''

def r_liaison(syls):
    """연음(재음절화): 종성(비어있지않고 ㅇ 아님) + 초성 ㅇ -> 종성 이동."""
    for i in range(len(syls) - 1):
        c1 = syls[i][2]
        if syls[i + 1][0] != 'ㅇ' or c1 in ('', 'ㅇ'):
            continue
        if c1 in LINK_CLUSTER:
            keep, move = LINK_CLUSTER[c1]
            syls[i][2] = keep
            syls[i + 1][0] = move
        else:
            syls[i + 1][0] = c1
            syls[i][2] = ''

def r_neutralize(syls):
    """음절말 평폐쇄음화(중화): 단일 종성."""
    for s in syls:
        if s[2] in NEUTRALIZE:
            s[2] = NEUTRALIZE[s[2]]

def r_cluster(syls):
    """겹받침 단순화(연음/격음화에서 안 쓰인 것)."""
    for s in syls:
        if s[2] in CLUSTER:
            s[2] = CLUSTER[s[2]]

def r_nasal_assim(syls):
    """비음화·유음화 (중화·단순화 후, 종성 in ㄱㄴㄷㄹㅁㅂㅇ 가정).
    ※ ㄹ비음화(담력→담녁, 강릉→강능)·상호비음화(국립→궁닙)는 사용자 결정
      (2026-07-23)으로 v1 미적용 — 추후 한자어 경계 판별과 함께 재도입."""
    NASALIZE = {'ㄱ':'ㅇ', 'ㄷ':'ㄴ', 'ㅂ':'ㅁ'}
    for i in range(len(syls) - 1):
        c1, c2 = syls[i][2], syls[i + 1][0]
        if c1 == 'ㄴ' and c2 == 'ㄹ':          # 유음화 ㄴㄹ->ㄹㄹ
            syls[i][2] = 'ㄹ'
        elif c1 == 'ㄹ' and c2 == 'ㄴ':        # 유음화 ㄹㄴ->ㄹㄹ
            syls[i + 1][0] = 'ㄹ'
        elif c1 in NASALIZE and c2 in ('ㄴ', 'ㅁ'):   # 장애음 비음화
            syls[i][2] = NASALIZE[c1]

def _parse_morphs(tagged_group):
    """'저/NP+는/JX' -> [('저','NP'), ('는','JX')]."""
    out = []
    for u in tagged_group.split('+'):
        surf, _, tag = u.rpartition('/')
        out.append((surf, tag))
    return out

def stem_fortis_gaps(eojeol, tagged_group):
    """용언 어간(받침 ㄴ/ㅁ/ㄵ/ㄻ/ㄼ/ㄾ)+어미(ㄱㄷㅅㅈ) 경계의 음절 gap 인덱스.
    형태소 표층 음절수 합이 어절 음절수와 다르면(불규칙 활용 등) 보수적으로 빈 집합."""
    syls = [c for c in eojeol if is_syllable(c)]
    morphs = _parse_morphs(tagged_group)
    lens = [len([c for c in s if is_syllable(c)]) for s, _ in morphs]
    if not morphs or sum(lens) != len(syls):
        return frozenset()
    gaps, pos = set(), 0
    for k in range(len(morphs) - 1):
        pos += lens[k]
        if lens[k] == 0 or lens[k + 1] == 0:
            continue
        (surf_a, tag_a), (surf_b, tag_b) = morphs[k], morphs[k + 1]
        if tag_a not in STEM_POS or tag_b not in ENDING_POS:
            continue
        last_a = [c for c in surf_a if is_syllable(c)][-1]
        first_b = [c for c in surf_b if is_syllable(c)][0]
        if decompose(last_a)[2] in STEM_CODA_TRIGGER \
                and decompose(first_b)[0] in FORTABLE_ONSET:
            gaps.add(pos - 1)
    return frozenset(gaps)

def r_fortis(syls, stem_gaps=frozenset()):
    """경음화: (의무) 장애음 뒤 + (용언) 어간 ㄴ/ㅁ/겹받침 어미 경계."""
    for i in range(len(syls) - 1):
        onset = syls[i + 1][0]
        if syls[i][2] in ('ㄱ', 'ㄷ', 'ㅂ') and onset in TENSE:
            syls[i + 1][0] = TENSE[onset]
        elif i in stem_gaps and onset in FORTABLE_ONSET:
            syls[i + 1][0] = TENSE[onset]


RULE_FUNCS = {'aspiration': r_aspiration, 'h_deletion': r_h_deletion,
              'palatalization': r_palatalization, 'liaison': r_liaison,
              'neutralize': r_neutralize, 'cluster': r_cluster,
              'nasal_assim': r_nasal_assim, 'fortis': r_fortis}
RULE_ORDER = ['aspiration', 'h_deletion', 'palatalization', 'liaison',
              'neutralize', 'cluster', 'nasal_assim', 'fortis']
DEFAULT_FLAGS = {k: True for k in RULE_ORDER}
DEFAULT_FLAGS['stem_fortis'] = True   # 용언 어간+어미 경음화 (fortis 내부)

# ============================================================
# 4. 로마자화 · 어절 처리
# ============================================================
def _syl_tokens(triple, coda_map):
    cho, jung, jong = triple
    toks = []
    if ONSET_ROMAN[cho]:
        toks.append(ONSET_ROMAN[cho])
    toks.append(VOWEL_ROMAN[jung])
    if coda_map[jong]:
        toks.append(coda_map[jong])
    return PHON_SEP.join(toks)

def romanize(syls, coda_map):
    return SYL_SEP.join(_syl_tokens(t, coda_map) for t in syls)

PUNCT = set(".,?!~…\"'`()[]{}<>《》「」『』·:;/\\-–—")

def _is_processable(eojeol):
    core = [c for c in eojeol if not c.isspace() and c not in PUNCT]
    return bool(core) and all(is_syllable(c) for c in core)

def process_eojeol(eojeol, flags, tagged_group=None):
    """한 어절 -> (form_roman, pron_hangul, pron_roman) 또는 자리표시자."""
    if not _is_processable(eojeol):
        return PLACEHOLDER, PLACEHOLDER, PLACEHOLDER
    base = [decompose(c) for c in eojeol if is_syllable(c)]
    form_roman = romanize([t[:] for t in base], SPELL_CODA_ROMAN)
    gaps = frozenset()
    if tagged_group and flags.get('stem_fortis', True):
        gaps = stem_fortis_gaps(eojeol, tagged_group)
    pron = [t[:] for t in base]
    for name in RULE_ORDER:
        if not flags.get(name, True):
            continue
        if name == 'fortis':
            r_fortis(pron, gaps)
        else:
            RULE_FUNCS[name](pron)
    pron_hangul = ''.join(compose(*t) for t in pron)
    pron_roman = romanize(pron, PRON_CODA_ROMAN)
    return form_roman, pron_hangul, pron_roman

# ============================================================
# 5. IPA 변환 (_roman_mfa_to_ipa.csv 공유; 없으면 내장 기본값)
# ============================================================
_DEFAULT_IPA = {
    'G':'k','KK':'k*','N':'n','D':'t','TT':'t*','R':'ɾ','M':'m','B':'p',
    'PP':'p*','S':'s','SS':'s*','J':'tɕ','JJ':'tɕ*','CH':'tɕʰ','K':'kʰ',
    'T':'tʰ','P':'pʰ','H':'h','NG':'ŋ','A':'a','AE':'ɛ','YA':'ja',
    'YAE':'jɛ','EO':'ʌ','E':'e','YEO':'jʌ','YE':'je','O':'o','WA':'wa',
    'WAE':'wɛ','OE':'we','YO':'jo','U':'u','WO':'wʌ','WE':'we','WI':'wi',
    'YU':'ju','EU':'ɯ','UI':'ɰi','I':'i','k':'k̚','n':'n','t':'t̚','l':'l',
    'm':'m','p':'p̚','ng':'ŋ','L':'l'}

def load_ipa_map(path=None):
    if path:
        try:
            import csv
            with open(path, encoding='utf-8-sig') as f:
                m = {r['roman_mfa']: r['ipa'] for r in csv.DictReader(f)}
            if m:
                return m
        except Exception as e:
            print(f"  [경고] IPA표 로드 실패({e}) — 내장 기본값 사용", flush=True)
    return dict(_DEFAULT_IPA)

def to_ipa_eojeol(roman_eojeol, ipa_map):
    """어절 roman_mfa -> IPA. 미정의 토큰은 ⟨토큰⟩로 노출(빈도사전과 동일)."""
    if roman_eojeol == PLACEHOLDER:
        return PLACEHOLDER
    syls = []
    for syl in roman_eojeol.split(SYL_SEP):
        parts = [ipa_map.get(tok, f"⟨{tok}⟩") for tok in syl.split() if tok]
        if parts:
            syls.append(''.join(parts))
    return IPA_SYL_SEP.join(syls)

# ============================================================
# 6. 최상위: 발화 하나 -> 컬럼 dict
# ============================================================
def predict_pron(form, tagged=None, flags=None, ipa_map=None):
    """form(+tagged) -> 예측 발음 컬럼 dict.
    tagged 어절수가 form과 같을 때만 형태소 경계(용언 경음화) 활용.
    """
    flags = flags or DEFAULT_FLAGS
    ipa_map = ipa_map or dict(_DEFAULT_IPA)
    eojeols = form.split()
    n_eojeol = len(eojeols)
    tgroups = tagged.split(' ') if tagged else []
    aligned = len(tgroups) == n_eojeol

    form_r, pron_h, pron_r, pron_i = [], [], [], []
    for idx, eoj in enumerate(eojeols):
        tg = tgroups[idx] if aligned else None
        fr, ph, pr = process_eojeol(eoj, flags, tg)
        form_r.append(fr)
        pron_h.append(ph)
        pron_r.append(pr)
        pron_i.append(to_ipa_eojeol(pr, ipa_map))

    align_warn = ''
    if tagged is not None and tagged != '' and not aligned:
        align_warn = f'eojeol_tag_mismatch({n_eojeol}!={len(tgroups)})'

    return {
        'n_eojeol': n_eojeol,
        'form_roman': EOJEOL_SEP.join(form_r),
        'pron_pred_hangul': ' '.join(pron_h),
        'pron_pred_roman': EOJEOL_SEP.join(pron_r),
        'pron_pred_ipa': EOJEOL_SEP.join(pron_i),
        'align_warn': align_warn,
    }


def predict_pron_reference(form, original_form="", tagged=None, flags=None,
                           ipa_map=None):
    """검색·검토용 기준 발음과 그 출처를 만든다.

    정규화 form의 숫자·기호가 ``∅``로 소실될 때만 원본 JSON의
    ``original_form``을 대체 입력으로 시험한다. 원전사 결과가 실제로
    placeholder를 줄일 때만 채택하며, 숫자 읽기를 임의로 추측하지 않는다.

    ``base``는 기존 form 기반 결과, ``reference``는 출처가 기록된 보완
    결과다. 두 값을 함께 반환해 구판 열을 보존할 수 있게 한다.
    """
    base = predict_pron(
        form, tagged=tagged, flags=flags, ipa_map=ipa_map
    )
    original = (original_form or "").strip()
    if original in {"미상", "NA", "N/A"}:
        original = ""

    def unresolved_count(result):
        return sum(
            token.strip() == PLACEHOLDER
            for token in result["pron_pred_hangul"].split()
        )

    base_unresolved = unresolved_count(base)
    reference = base
    reference_form = form
    source = "form_rule_prediction"
    if base_unresolved and original:
        # original_form과 tagged는 어절·형태소 수가 다를 수 있으므로 원전사
        # 폴백에는 정규화 form용 tagged를 억지로 결합하지 않는다.
        candidate = predict_pron(
            original, tagged=None, flags=flags, ipa_map=ipa_map
        )
        if unresolved_count(candidate) < base_unresolved:
            reference = candidate
            reference_form = original
            source = "original_form_placeholder_resolution"

    unresolved = unresolved_count(reference)
    status = "unresolved_symbol" if unresolved else (
        "resolved_original_form"
        if source == "original_form_placeholder_resolution"
        else "resolved_form"
    )
    return {
        "base": base,
        "reference": reference,
        "reference_form": reference_form,
        "reference_source": source,
        "reference_status": status,
        "reference_unresolved_count": unresolved,
    }

# ============================================================
# 7. lexicon(v1) 조회부 — 형태소별 사전 발음(예외) 층 (기본 off, 규칙 확정 후 결합)
# ============================================================
VERB_POS = {'VV', 'VA', 'VX', 'VCP', 'VCN', 'XSV', 'XSA'}

def build_lexicon_index(rows):
    """rows(word,pos_tag,sense_no,pron_1) -> {(word,pos): pron_1}.
    (word,pos) 키, 다의어는 최소 sense_no 채택. 용언/파생접사 '-다' 어간형도 색인.

    DEPRECATED: 진단용 v1 helper만 보존한다. 최소 의미번호 자동 선택은
    동형·다의어의 실제 문맥 의미를 보장하지 않으므로 최종 공통 발음 registry나
    연구용 CSV에 배선하지 않는다.
    """
    best = {}
    def _put(key, sn, pron):
        cur = best.get(key)
        if cur is None or sn < cur[0]:
            best[key] = (sn, pron)
    for r in rows:
        w = (r.get('word') or '').strip()
        pos = (r.get('pos_tag') or '').strip()
        pron = (r.get('pron_1') or '').strip()
        if not w or not pos or not pron:
            continue
        sn_raw = (r.get('sense_no') or '').strip().lstrip('0')
        sn = int(sn_raw) if sn_raw.isdigit() else 999
        _put((w, pos), sn, pron)
        if pos in VERB_POS and w.endswith('다') and len(w) > 1:
            _put((w[:-1], pos), sn, pron)
    return {k: v[1] for k, v in best.items()}

def lexicon_pron(word, pos_tag, lex_index):
    return lex_index.get((word, pos_tag))

# ============================================================
# 8. 단위테스트 (--selftest)
# ============================================================
_CASES_HANGUL = [
    ('저는 여행 다니는 것을', '저는 여행 다니는 거슬'),
    ('국물', '궁물'),        # 장애음 비음화
    ('신라', '실라'),        # 유음화 ㄴㄹ
    ('칼날', '칼랄'),        # 유음화 ㄹㄴ
    ('담력', '담력'),        # ㄹ비음화 미적용(v1) — 담력 유지
    ('강릉', '강릉'),        # ㄹ비음화 미적용(v1)
    ('좋아하는데요', '조아하는데요'),  # ㅎ탈락
    ('많이', '마니'),        # ㄶ ㅎ탈락+연음
    ('싫어', '시러'),        # ㅀ ㅎ탈락+연음
    ('굳이', '구지'),        # 구개음화
    ('같이', '가치'),        # 구개음화 ㅌ
    ('국밥', '국빱'),        # 장애음 경음화
    ('학교', '학꾜'),
    ('밝다', '박따'),        # 겹받침+경음화
    ('값', '갑'), ('닭', '닥'),
    ('읽어', '일거'),        # 겹받침 연음
    ('좋다', '조타'),        # 격음화 ㅎ+ㄷ
    ('축하', '추카'),        # 격음화 ㄱ+ㅎ
    ('꽃', '꼳'), ('앞', '압'),
]
# 용언 어간+어미 경음화 (tagged 필요)
_CASES_TAGGED = [
    ('신고', '신/VV+고/EC', '신꼬'),
    ('안고', '안/VV+고/EC', '안꼬'),
    ('감고', '감/VV+고/EC', '감꼬'),
    ('앉다', '앉/VV+다/EC', '안따'),
    ('넓게', '넓/VA+게/EC', '널께'),
    ('알고', '알/VV+고/EC', '알고'),   # ㄹ 어간 -> 경음화 없음(대조)
]
_CASES_ROMAN = [
    ('것을', 'G EO _ S EU l'),
    ('국물', 'G U ng _ M U l'),
    ('밝다', 'B A k _ TT A'),
]

def _selftest():
    ok, total, fail = 0, 0, []
    for form, exp in _CASES_HANGUL:
        total += 1
        got = predict_pron(form)['pron_pred_hangul']
        if got == exp: ok += 1
        else: fail.append((form, exp, got))
    for form, tagged, exp in _CASES_TAGGED:
        total += 1
        got = predict_pron(form, tagged=tagged)['pron_pred_hangul']
        if got == exp: ok += 1
        else: fail.append((f'{form}[{tagged}]', exp, got))
    for form, exp in _CASES_ROMAN:
        total += 1
        got = predict_pron(form)['pron_pred_roman']
        if got == exp: ok += 1
        else: fail.append((form, exp, got))
    lex = build_lexicon_index([
        {'word':'먹다','pos_tag':'VV','sense_no':'001','pron_1':'먹따'},
        {'word':'값','pos_tag':'NNG','sense_no':'001','pron_1':'갑'}])
    lex_ok = (lexicon_pron('먹','VV',lex) == '먹따'
              and lexicon_pron('먹다','VV',lex) == '먹따'
              and lexicon_pron('값','NNG',lex) == '갑')
    print(f"[predict_pron 단위테스트] 규칙 {ok}/{total} 통과 · "
          f"lexicon 색인 {'OK' if lex_ok else 'FAIL'}")
    for form, exp, got in fail:
        print(f"  FAIL  {form!r}  기대={exp!r}  실제={got!r}")
    return 0 if (ok == total and lex_ok) else 1


# ============================================================
# 9. CLI
# ============================================================
def _demo(text, tagged=None):
    d = predict_pron(text, tagged=tagged)
    print(f"form            : {text}")
    print(f"form_roman      : {d['form_roman']}")
    print(f"pron_pred_hangul: {d['pron_pred_hangul']}")
    print(f"pron_pred_roman : {d['pron_pred_roman']}")
    print(f"pron_pred_ipa   : {d['pron_pred_ipa']}")

def main():
    ap = argparse.ArgumentParser(description='예측 발음열 생성 (검색 마스터 v1)')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--demo', metavar='FORM')
    ap.add_argument('--tagged', metavar='TAGGED', help='--demo와 함께(용언 경음화)')
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    if args.demo:
        _demo(args.demo, args.tagged)
        return 0
    ap.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
