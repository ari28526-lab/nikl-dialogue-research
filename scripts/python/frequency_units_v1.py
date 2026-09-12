"""Explicit, reviewable frequency units; no new morphological analysis or WSD."""
import json,re,unicodedata
from collections import defaultdict

PRED={'VV','VA','VX','VCP','VCN'}
NOM={'NNG','NNP','NNB','NP','NR'}
OTHER={'MM','MAG','MAJ','IC','SL','SH','SN'}
PUNCT={'SF','SP','SS','SE','SO','SW','SSO','SSC','SC','SY'}
JAMO=str.maketrans({'ᆫ':'ㄴ','ᆯ':'ㄹ','ᆷ':'ㅁ','ᆸ':'ㅂ','ᆻ':'ㅆ','ᄂ':'ㄴ','ᄅ':'ㄹ','ᄆ':'ㅁ','ᄇ':'ㅂ'})
def norm(s):return unicodedata.normalize('NFC',s).translate(JAMO)
def pos(p):return 'MM' if p in {'MMA','MMD','MMN'} else p
def js(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def group(g):return 'urimal:'+str(g) if g is not None and str(g).isdigit() else '?'

def lexical_words(morphs):
    """Tag-based word draft: within-token nominal chains and derivational affixes only."""
    pending=[];tag=None
    def result(parts,p):
        stem=''.join(norm(m['lemma']) for m in parts)
        form=stem+'다' if p in PRED else stem
        sense=group(parts[0].get('group')) if len(parts)==1 else '?'
        return form,p,sense,('atomic_lexeme' if len(parts)==1 else 'tag_based_lexical_composition'),[[m['lemma'],pos(m['pos'])] for m in parts]
    for m in morphs:
        p=pos(m['pos'])
        if p in NOM:
            if pending and tag not in NOM|{'XPN','XR','WORD_UNRESOLVED'}:
                yield result(pending,tag);pending=[]
            pending.append(m);tag=p if len(pending)==1 else ('NNP' if all(pos(x['pos']) in {'NNP','XPN'} for x in pending) else 'NNG')
        elif p in {'XPN','XR'}:
            if pending:yield result(pending,tag)
            pending=[m];tag='WORD_UNRESOLVED'
        elif p in {'XSN','XSV','XSA'}:
            if pending:
                pending.append(m);tag={'XSN':'NNG','XSV':'VV','XSA':'VA'}[p]
            else:
                yield result([m],'WORD_UNRESOLVED')
        else:
            if pending:yield result(pending,tag);pending=[];tag=None
            if p in PRED or p in OTHER:
                pending=[m];tag=p
    if pending:yield result(pending,tag)

def events(form,tokens):
    """Yield unit, mode, base-key, semantic-key, quality; one contribution per event."""
    for t in tokens:
        for m in t['morphs']:
            key=js([norm(m['lemma']),pos(m['pos'])]);g=group(m.get('group'))
            yield 'morpheme','collapsed',key,'','all_observed'
            yield 'morpheme','split',key,g,'machine_link' if g!='?' else 'unresolved_or_unassessed'
        for word,p,g,quality,structure in lexical_words(t['morphs']):
            key=js([word,p])
            yield 'word','collapsed',key,'',quality
            yield 'word','split',key,g,'machine_link' if g!='?' else 'unresolved_or_unassessed'
    for match in re.finditer(r'\S+',form):
        surface=match.group();start,end=match.span()
        yield 'surface_eojeol','surface',js([surface,None]),'','raw_transcript'
        local=[t for t in tokens if t.get('start') is not None and start<=t['start'] and t['end']<=end]
        local.sort(key=lambda t:t['start']);at=start;verified=bool(local)
        for t in local:
            if t['start']!=at or form[t['start']:t['end']]!=t['surface']:verified=False
            at=t['end']
        verified=verified and at==end
        if verified:
            morphs=[m for t in local for m in t['morphs']]
            analysis=[[norm(m['lemma']),pos(m['pos'])] for m in morphs]
            # Signature is explicit and may be partial. It is never a whole-eojeol sense number.
            signature=[group(m.get('group')) if pos(m['pos']) in NOM|PRED|OTHER|{'XR'} else 'FORMAL_UNASSESSED' for m in morphs]
            quality='partial_or_unresolved' if '?' in signature else 'lexical_groups_available_formal_unassessed'
        else:analysis='ANALYSIS_UNAVAILABLE';signature=['?'];quality='analysis_join_hold'
        key=js([surface,analysis])
        yield 'eojeol','collapsed',key,'','character_joined' if verified else 'analysis_join_hold'
        yield 'eojeol','split',key,js(signature),quality

def aligned_span(surface,begin,end,form,response_base=0):
    choices=set()
    for delta in {0,response_base}:
        a,b=begin-delta,end-delta
        if 0<=a<=b<=len(form) and form[a:b]==surface:choices.add((a,b))
    return next(iter(choices)) if len(choices)==1 else (None,None)
