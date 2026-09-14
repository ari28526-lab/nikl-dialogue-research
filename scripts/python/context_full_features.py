"""Bounded, replayable morphological, relational and discourse observations.

Keys retain target position, boundaries and surface negation/quotation flags.
Native relation features require native relations; no inferred dependency parser.
"""
import hashlib,json
from collections import defaultdict
from homonym_context_core import LEXICAL,NOUNS,PREDS,markers
from build_context_evidence import js

VERSION='context_full_features.v1'
def integer(x):return type(x) is int
def signature(key):return hashlib.blake2b(js(key).encode('utf-8'),digest_size=16).digest()

class Sentence:
    def __init__(self,s,ordinal,lexicon):
        self.raw=s;self.ordinal=ordinal;self.lexicon=lexicon;self.issues=[]
        self.words=s.get('word',[]);self.ids=[];self.w={};self.mp=defaultdict(list);self.targets=[]
        for w in self.words:
            i=w.get('id')
            if not integer(i) or i in self.w:self.issues.append('invalid_or_duplicate_word_id');continue
            self.ids.append(i);self.w[i]=w
        self.at={w:i for i,w in enumerate(self.ids)}
        seen=set()
        for mi,m in enumerate(s.get('MP',s.get('morpheme',[]))):
            if not isinstance(m,dict) or not isinstance(m.get('form'),str) or not isinstance(m.get('label'),str) or not integer(m.get('word_id')) or m['word_id'] not in self.w:
                self.issues.append('invalid_MP_field');continue
            mid=m.get('id',mi)
            if not integer(mid) or mid in seen:self.issues.append('invalid_or_duplicate_morph_id');continue
            seen.add(mid);row=dict(m);row['id']=mid;row['position']=len(self.mp[m['word_id']]);self.mp[m['word_id']].append(row)
            if m['label'] in LEXICAL:self.targets.append(row)
        self.seq={w:[[m['form'],m['label']] for m in self.mp[w]] for w in self.ids}
        self.lex={w:[[m['form'],m['label']] for m in self.mp[w] if m['label'] in LEXICAL] for w in self.ids}
        self.class_cache={};self.flags=markers([m for ms in self.mp.values() for m in ms]);self.guard=[self.flags['negation_form'],self.flags['quote_form']]
        self.pred=[w for w in self.ids if any(m['label'] in PREDS for m in self.mp[w])]
        self.nouns=[w for w in self.ids if any(m['label'] in NOUNS for m in self.mp[w])]
        self.dp={};self.children=defaultdict(list);self.srl=[]
        for d in s.get('DP',[]):
            if not isinstance(d,dict) or not integer(d.get('word_id')) or not integer(d.get('head')) or not isinstance(d.get('label'),str) or d['word_id'] not in self.w or d['head'] not in {*self.ids,0,-1}:
                self.issues.append('invalid_DP');continue
            if d['word_id'] in self.dp:self.issues.append('duplicate_DP');continue
            self.dp[d['word_id']]=d;self.children[d['head']].append(d['word_id'])
        for sr in s.get('SRL',[]):
            if not isinstance(sr,dict):self.issues.append('invalid_SRL');continue
            p=sr.get('predicate',{});pw=p.get('word_id') if isinstance(p,dict) else None
            if not integer(pw) or pw not in self.w:self.issues.append('invalid_SRL_predicate');continue
            args=[]
            for a in sr.get('argument',[])+sr.get('adjunct',[]):
                ww=a.get('word_id',[]) if isinstance(a,dict) else None
                if not isinstance(ww,list) or not ww or any(not integer(w) or w not in self.w for w in ww) or len(ww)!=len(set(ww)) or not isinstance(a.get('label'),str):self.issues.append('invalid_SRL_span');continue
                args.append(a)
            self.srl.append((p,args))

    def labels(self,w):return {m['label'] for m in self.mp[w]}
    def particles(self,w):return [[m['form'],m['label']] for m in self.mp[w] if m['label'].startswith('J')]
    def classes(self,w):
        if w in self.class_cache:return self.class_cache[w]
        result=set()
        for form,pos in self.lex[w]:result.update(self.lexicon.analyze(form,pos)['common_classes'])
        self.class_cache[w]=sorted(result);return self.class_cache[w]
    def nearest(self,items,w,limit=1,distance=12):
        return sorted([i for i in items if i!=w and abs(self.at[i]-self.at[w])<=distance],key=lambda i:(abs(self.at[i]-self.at[w]),self.at[i]))[:limit]

def extract(view,target,context=()):
    v=view;w=target['word_id'];at=v.at[w];lemma=target['form'];pos=target['label'];offset=target['position'];out={}
    def add(family,body,kind='morphological_observation'):
        key=[VERSION,family,lemma,pos,offset,body,v.guard]
        h=signature(key);out[h]=(family,js(key),kind)
    def span(a,b):return [v.seq[v.ids[i]] for i in range(a,b+1)]
    left=v.ids[at-1] if at>0 else None;right=v.ids[at+1] if at+1<len(v.ids) else None
    add('K01',[v.seq[w]])
    for a,b in ((at-1,at),(at,at+1),(at-1,at+1)):
        if a>=0 and b<len(v.ids):
            add('K02',[at-a,[v.w[v.ids[i]].get('form','') for i in range(a,b+1)]])
            add('K03',[at-a,span(a,b)])
    if left is not None and right is not None:add('K04',[v.lex[left],v.seq[w],v.lex[right]])
    for other in v.nearest(v.pred if pos in NOUNS else v.nouns if pos in PREDS else [],w,2,12):
        a,b=sorted((at,v.at[other]));distance=v.at[other]-at
        path=span(a,b);parts=v.particles(w if pos in NOUNS else other)
        add('K05' if abs(distance)<=3 else 'K09',[distance,parts,v.lex[other],[[x for x in ww if x[1].startswith('E') or x[0] in {'안','못','않'}] for ww in path]])
        if distance<0 or pos in PREDS:add('K18',[distance,parts,v.lex[other]])
        if pos in NOUNS:
            add('K15',[v.lex[other],parts,'fixed_target_and_predicate',distance])
        cls=v.classes(other)
        if cls:add('K24_linear',[distance,parts,cls],'semantic_class_candidate')
    for other in (left,right):
        if other is None:continue
        labels=v.labels(other);distance=v.at[other]-at
        if 'JKG' in labels or 'JKG' in v.labels(w):add('K06',[distance,v.seq[other],v.seq[w]])
        if 'ETM' in labels or 'MM' in labels or 'ETM' in v.labels(w):add('K07',[distance,v.seq[other],v.seq[w]])
        if pos in PREDS and labels & {'MAG','MAJ'}:add('K08',[distance,v.seq[other]])
        if 'JC' in labels or 'JC' in v.labels(w):add('K26',[distance,v.seq[other],v.particles(w)])
        if labels & {'ETN'} or (any(x[0]=='것' for x in v.lex[other]) and 'ETM' in v.labels(w)):add('K28',[distance,v.seq[other],v.seq[w]])
        cls=v.classes(other)
        if cls:add('K24_adjacent',[distance,cls,v.particles(w)],'semantic_class_candidate')
    # Same-word constituent class: target itself is excluded.
    for m in v.mp[w]:
        if m['id']==target['id'] or m['label'] not in LEXICAL:continue
        cls=v.lexicon.analyze(m['form'],m['label'])['common_classes']
        if cls:add('K24_compound',[m['position']-offset,cls,[[f if i!=m['position'] else '<CLASS>',p] for i,(f,p) in enumerate(v.seq[w])]],'semantic_class_candidate')
    if pos in PREDS:
        ns=v.nearest(v.nouns,w,2,5)
        if len(ns)==2:add('K10',[[v.at[n]-at,v.lex[n],v.particles(n)] for n in ns])
        if ns:
            n=ns[0];ni=v.at[n]
            if ni>0 and (v.labels(v.ids[ni-1]) & {'MM','ETM'}):add('K11',[v.at[n]-at,v.seq[v.ids[ni-1]],v.seq[n],v.lex[w]])
    near=v.ids[max(0,at-2):min(len(v.ids),at+3)];near_ms=[m for n in near for m in v.mp[n]]
    if any(m['label']=='VX' for m in near_ms):add('K12',[[v.at[n]-at,v.seq[n]] for n in near])
    if any(m['form'] in {'안','못','않','아니'} for m in near_ms):add('K13',[[v.at[n]-at,v.seq[n]] for n in near])
    if any(m['label']=='NNB' for m in near_ms) and any(m['label']=='ETM' for m in near_ms):add('K14',[[v.at[n]-at,v.seq[n]] for n in near])
    add('K16',[[v.at[n]-at,[[f if n==w or p.startswith(('J','E')) or f in {'안','못','않'} else '<'+p+'>',p] for f,p in v.seq[n]]] for n in v.ids[max(0,at-1):at+2]])
    for other in v.nearest([n for n in v.ids if v.lex[n]],w,2,12):add('K17',[v.at[other]-at,v.lex[other],v.particles(w)])
    if any(m['label'] in {'XSV','XSA'} for m in v.mp[w]):add('K29',['derived',v.seq[w],offset])
    elif lemma=='하' and pos=='VV' and left is not None:add('K29',['independent_predicate',v.seq[left],v.seq[w]])
    if v.guard[1]:add('K27',[v.seq[w],[[m['form'],m['label']] for m in near_ms if m['form'] in {'라고','다고','말하','묻','이야기하'} or m['label'] in {'SS','SSO','SSC'}]])
    # Direct/ancestor DP observations use words, never assume a unique morpheme head.
    node=w;visited={w};path=[]
    for depth in range(1,4):
        if node not in v.dp:break
        d=v.dp[node];head=d['head']
        if head in visited:v.issues.append('DP_cycle');break
        if head not in v.w:break
        visited.add(head);path.append([d['label'],v.at[head]-at,v.lex[head]])
        add('K19' if depth==1 else 'K20',[path.copy()],'native_DP_word_relation');node=head
    for child in v.children.get(w,[]):
        add('K19',['dependent',v.dp[child]['label'],v.at[child]-at,v.lex[child]],'native_DP_word_relation')
    cc=v.children.get(w,[])
    if len(cc)>=2:add('K21',[[v.dp[ch]['label'],v.at[ch]-at,v.lex[ch]] for ch in sorted(cc,key=lambda n:abs(v.at[n]-at))[:2]],'native_DP_shared_head')
    for pred,args in v.srl:
        pw=pred['word_id'];heads=[]
        for a in args:
            aw=a['word_id'];is_pred=w==pw;member=w in aw
            if member or is_pred:
                add('K22',[a['label'],'predicate' if is_pred else 'span_member',v.at[pw]-at,v.lex[pw],[[v.at[n]-at,v.lex[n]] for n in aw]],'native_SRL_span')
                cls=sorted({cl for n in aw for cl in v.classes(n)})
                if cls:add('K24_role',[a['label'],'predicate' if is_pred else 'span_member',v.lex[pw],cls],'native_SRL_with_class_candidate')
            hs=[n for n in aw if n in v.dp and v.dp[n]['head'] not in aw]
            if len(hs)==1:heads.append((a['label'],hs[0]))
        if w==pw and len(heads)>=2:add('K23',[[role,v.lex[h],v.at[h]-at] for role,h in heads[:2]],'native_SRL_with_DP_head')
    # Lexicographic collocation links do not transfer phrase senses to components.
    available={f for n in v.ids[max(0,at-12):at+13] for f,p in v.lex[n]}
    for partner,cid in v.lexicon.pairs.get(lemma,[]):
        if partner in available and partner!=lemma:add('K25',[cid,partner],'dictionary_collocation_form_match')
    prev=[q for q in context if 0<v.ordinal-q.ordinal<=3]
    for q in prev:
        same=q.raw.get('speaker_id') is not None and v.raw.get('speaker_id') is not None and q.raw.get('speaker_id')==v.raw.get('speaker_id')
        if any(m['form']==lemma and m['label']==pos for m in q.targets):add('K30',[v.ordinal-q.ordinal,same],'local_repetition_not_coreference')
    if prev:
        q=prev[-1];switch=q.raw.get('speaker_id') is not None and v.raw.get('speaker_id') is not None and q.raw.get('speaker_id')!=v.raw.get('speaker_id')
        question='?' in q.raw.get('form','') or any(m['form'] in {'뭐','무엇','어디','누구','어떻게'} for m in q.targets)
        if pos=='IC' or (question and len(v.ids)<=5):
            add('K31_response',[switch,question,len(v.ids)<=5,[v.lex[n] for n in v.ids]],'dialogue_response_candidate')
        classes=sorted({cl for n in q.ids for cl in q.classes(n)})
        if classes:add('K24_discourse',[switch,classes],'discourse_class_cooccurrence_candidate')
    if v.guard[0] or v.guard[1]:add('K32',[v.guard,v.seq[w]],'scope_guard_not_sense_rule')
    return out

def za_links(views):
    """Validate actual antecedent character spans, keeping #/unknown as holds."""
    byid={v.raw['id']:v for v in views};out=defaultdict(list);issues=CounterLike()
    for v in views:
        for z in v.raw.get('ZA',[]):
            if not isinstance(z,dict):issues['invalid_ZA']+=1;continue
            p=z.get('predicate',{});pw=p.get('word_id');pv=byid.get(p.get('sentence_id'))
            if pv is None or not integer(pw) or pw not in pv.w:issues['invalid_ZA_predicate']+=1;continue
            for ell in z.get('ellipsis',[]):
                for ant in ell.get('antecedent',[]):
                    av=byid.get(ant.get('sentence_id'));b=ant.get('begin');e=ant.get('end')
                    if av is None or not integer(b) or not integer(e) or not 0<=b<e<=len(av.raw.get('form','')):
                        issues['unresolved_or_invalid_ZA_antecedent']+=1;continue
                    if av.raw['form'][b:e].replace(' ','')!=str(ant.get('form','')).replace(' ',''):
                        issues['ZA_text_span_mismatch']+=1;continue
                    aw=[n for n in av.ids if integer(av.w[n].get('begin')) and integer(av.w[n].get('end')) and av.w[n]['begin']<e and av.w[n]['end']>b]
                    if not aw:issues['ZA_no_word_overlap']+=1;continue
                    out[(pv.raw['id'],pw)].append(['predicate',av.ordinal-pv.ordinal,ell.get('restored',{}).get('type'),[av.lex[n] for n in aw]])
                    for n in aw:out[(av.raw['id'],n)].append(['antecedent_span_member',pv.ordinal-av.ordinal,ell.get('restored',{}).get('type'),pv.lex[pw]])
                    issues['resolved_ZA_links']+=1
    return out,issues

class CounterLike(defaultdict):
    def __init__(self):super().__init__(int)
