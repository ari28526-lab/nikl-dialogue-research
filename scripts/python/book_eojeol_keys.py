"""Candidate-retrieval keys only. Preserve raw text, native senses and numeric values."""
import hashlib, re, unicodedata
from build_sejong_supplement import morphology, norm, js

VERSION = 'book_eojeol_keys.v1'
PUNCT = str.maketrans({'，':',','．':'.','？':'?','！':'!','“':'"','”':'"','‘':"'",'’':"'",'（':'(','）':')'})
DECORATION = set('※★☆●○◆◇■□•·*')

def canonical(s):
    return norm(s).translate(PUNCT)

def edge_kind(form, pos):
    f = canonical(form)
    if pos == 'SF' and f and all(ch in '.?!' for ch in f):
        if '?' in f and '!' in f: return 'mixed_question_exclamation'
        if '?' in f: return 'question'
        if '!' in f: return 'exclamation'
        return 'declarative' if f == '.' else 'ellipsis'
    if pos == 'SE' and f and all(ch in '.…' for ch in f): return 'ellipsis'
    if pos == 'SP' and f and all(ch == ',' for ch in f): return 'comma'
    if pos == 'SS' and f and all(ch in '\"\'' for ch in f): return 'quotation'
    if pos == 'SS' and f and all(ch in '()[]{}〈〉《》「」『』【】' for ch in f): return 'bracket'
    if pos == 'SW' and f and all(ch in DECORATION for ch in f): return 'decoration'
    return None

def digest(value):
    return hashlib.sha256(js(value).encode()).digest()

def keys(surface, analysis):
    mp = morphology(analysis) if isinstance(analysis, str) else analysis
    surface = canonical(surface)
    lo, hi = 0, len(mp)
    while lo < hi and edge_kind(*mp[lo][:2]): lo += 1
    while hi > lo and edge_kind(*mp[hi-1][:2]): hi -= 1
    left, right = ''.join(canonical(x[0]) for x in mp[:lo]), ''.join(canonical(x[0]) for x in mp[hi:])
    aligned = surface.startswith(left) and surface.endswith(right) and len(surface) >= len(left)+len(right)
    if not aligned or lo == hi:
        exact = digest([VERSION,'unmerged',surface,[[norm(l),p] for l,p,n in mp]])
        return {'key':exact,'numeric_key':None,'state':'edge_alignment_hold' if not aligned else 'no_lexical_body','removed':[], 'body_surface':surface,'body':mp,'guard':[],'numeric':False}
    body_surface = surface[len(left):len(surface)-len(right) if right else len(surface)]
    body = mp[lo:hi]
    removed = [(canonical(l),p,edge_kind(l,p)) for l,p,n in mp[:lo]+mp[hi:]]
    # Commas and decorative glyphs form a retrieval family, not a semantic judgment.
    guard = sorted(set(k for f,p,k in removed if k not in {'comma','decoration'}))
    signature = [[norm(l),p] for l,p,n in body]
    exact = digest([VERSION,body_surface,signature,guard])
    numeric = any(p == 'SN' for l,p,n in body)
    numeric_key = None
    if numeric:
        def number(l,p):
            if p != 'SN': return norm(l)
            if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',l): return norm(l)
            return '<DECIMAL>' if '.' in l else '<INTEGER>'
        template = [[number(l,p),p] for l,p,n in body]
        # Surface punctuation, units, internal signs and decimal structure remain.
        numeric_key = digest([VERSION,'numeric_template',re.sub(r'[0-9]+','<DIGITS>',body_surface),template,guard])
    return {'key':exact,'numeric_key':numeric_key,'state':'normalized_candidate_family','removed':removed,'body_surface':body_surface,'body':body,'guard':guard,'numeric':numeric}
