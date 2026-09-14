"""Read-only supplemental evidence API; historical mapping never implies WSD gold."""
import argparse,collections,json,zlib
from pathlib import Path
from build_sejong_supplement import ROOT,ro,js,morphology,shape,norm,kind

POS={'NNG':'명사','NNP':'명사','NNB':'의존 명사','NP':'대명사','NR':'수사','VV':'동사','VA':'형용사','VX':'보조 동사','MM':'관형사','MAG':'부사','MAJ':'부사','IC':'감탄사','XR':'어근','XPN':'접사','XSN':'접사','XSV':'접사','XSA':'접사'}

class Supplement:
    def __init__(self,root=ROOT):
        self.root=Path(root);self.manifest=json.loads((self.root/'FINAL_MANIFEST.json').read_text(encoding='utf-8'))
        if self.manifest['status']!='complete':raise ValueError('supplement_incomplete')
        self.c=ro(self.root/'SUPPLEMENT.sqlite')
        self.bridge=None
        br=self.root/'DEFINITION_BRIDGE.receipt.json'
        if br.exists():
            if json.loads(br.read_text(encoding='utf-8'))['status']!='complete':raise ValueError('definition_bridge_incomplete')
            self.bridge=ro(self.root/'DEFINITION_BRIDGE.sqlite')
        rp=self.root/'CONTEXT_PATTERNS.receipt.json'
        self.patterns=None
        if rp.exists():
            r=json.loads(rp.read_text(encoding='utf-8'))
            if r['status']!='complete' or r['input_sha256']!=self.manifest['database_sha256']:raise ValueError('pattern_source_mismatch')
            self.patterns=ro(self.root/'CONTEXT_PATTERNS.sqlite')
    def close(self):
        self.c.close()
        if self.patterns is not None:self.patterns.close()
        if self.bridge is not None:self.bridge.close()
    def matched_patterns(self,words,wi,mi):
        from build_sejong_context_patterns import context_keys
        if self.patterns is None:return []
        out=[]
        for h,family,key in context_keys(words,wi,mi):
            rows=self.patterns.execute('SELECT native_code,label_kind,occurrences,source_id,first_segment,last_segment FROM observations WHERE hash=?',(h,)).fetchall()
            if not rows:continue
            counts=collections.Counter();sources=set();segments=[]
            for n,label,count,source,first,last in rows:
                counts[n]+=count;sources.add(source)
                if len(segments)<4:
                    for sid in {first,last}:
                        raw,th=self.c.execute('SELECT raw,text_hash FROM segments WHERE id=?',(sid,)).fetchone();rr=json.loads(zlib.decompress(raw));segments.append({'segment_id':sid,'source_id':source,'text_sha256':th,'rows':rr,'native_code':n})
            out.append({'family':family,'pattern_hash':h.hex(),'condition':json.loads(key),'native_distribution':dict(counts),'source_files':len(sources),'example_segments':segments,'single_regular_native_label':len(counts)==1 and all(kind(n)=='native_number' for n in counts),'selected_group':None,'status':'context_evidence_requires_dictionary_correspondence'})
        return out
    def mapping(self,lemma,pos,native):
        forms=[lemma]+([lemma+'다'] if pos in {'VV','VA','VX'} else [])
        out=[]
        for form in forms:
            if getattr(self,'bridge',None) is not None:
                rows=self.bridge.execute('SELECT native_code,pos,stdict_target,urimal_target,group_id,match_type,score,stdict_definition,current_definition,state FROM bridge WHERE lemma=?',(form,))
            else:rows=self.c.execute('SELECT native_code,pos,stdict_target,urimal_target,group_id,match_type,score,stdict_definition,urimal_definition,state FROM crosswalk WHERE lemma=?',(form,))
            for r in rows:
                if pos in POS and r[1]!=POS[pos] and not(pos=='VX' and r[1]=='보조 형용사'):continue
                out.append(dict(zip(['modern_homonym_code','dictionary_pos','stdict_target','urimal_target','group','match_type','score','stdict_definition','urimal_definition','state'],r))|{'historical_number_matches':bool(native and native==r[0]),'native_code':native,'historical_mapping_verified':False,'modern_target_definition_verified':r[9]=='modern_definition_verified_historical_code_pending'})
        # Keep competing definitions and numbering discrepancies visible.
        return out
    def word(self,surface,lemma,pos,word_morphemes=None):
        desired=shape(word_morphemes) if word_morphemes is not None else None
        entries=[];counts=collections.Counter();native=set()
        for dataset,total,analysis,k,n,percent in self.c.execute('SELECT e.dataset,e.total,v.analysis,v.word_shape,v.frequency,v.percent FROM eojeols e JOIN variants v ON v.eojeol_id=e.id WHERE e.surface=? ORDER BY e.dataset,v.rowid',(surface,)):
            if dataset!='05.txt':continue
            try:mp=morphology(analysis)
            except ValueError:continue
            hits=[(i,nc) for i,(l,p,nc) in enumerate(mp) if norm(l)==norm(lemma) and p==pos]
            if not hits:continue
            compatible=desired is None or k==desired
            for i,nc in hits:
                if compatible:native.add(nc);counts[nc]+=n
            entries.append({'analysis':analysis,'frequency':n,'eojeol_total':total,'positions':hits,'same_morphological_shape':compatible,'source':'05.txt'})
        return {'surface':surface,'lemma':lemma,'pos':pos,'variants':entries,'matching_native_distribution':dict(counts),'native_codes':sorted(native),'single_observed_regular_native_code':len(native)==1 and all(kind(n)=='native_number' for n in native),'completion_status':'evidence_only','selected_group':None,'reason':'An observed frequency or one historical label alone does not complete a target WSD judgment.'}
    def contexts(self,lemma,pos,word_morphemes=None,limit=6):
        sql='SELECT o.segment_id,o.word_index,o.morph_index,o.native_code,o.label_kind,s.raw,src.name,s.text_hash FROM occurrences o JOIN segments s ON s.id=o.segment_id JOIN sources src ON src.id=s.source_id WHERE o.lemma=? AND o.pos=?'
        args=[lemma,pos]
        if word_morphemes is not None:sql+=' AND o.word_shape=?';args.append(shape(word_morphemes))
        sql+=' LIMIT ?';args.append(limit)
        out=[]
        for sid,wi,mi,nc,label,raw,name,th in self.c.execute(sql,args):
            rows=json.loads(zlib.decompress(raw));out.append({'source_member':name,'segment_id':sid,'source_segment_text_sha256':th,'target_word_id':rows[wi][0],'target_word_index':wi,'target_morph_index':mi,'native_code':nc,'label_kind':label,'context':rows[max(0,wi-3):wi+4],'window_start':max(0,wi-3),'segment_word_count':len(rows)})
        return out
    def lookup(self,lemma,pos,surface=None,word_morphemes=None,limit=6):
        ctx=self.contexts(lemma,pos,word_morphemes,limit);word=self.word(surface,lemma,pos,word_morphemes) if surface else None
        native=sorted(set(x['native_code'] for x in ctx)|set(word['native_codes'] if word else []))
        return {'schema':'sejong_supplement_lookup.v1','lemma':lemma,'pos':pos,'eojeol_evidence':word,'annotated_contexts':ctx,'context_return_limit':limit,'context_selection':'first matching source occurrences, not an exhaustive semantic distribution','definition_correspondences':{n:self.mapping(lemma,pos,n) for n in native},'book_lexical_frequency':[dict(zip(['dataset','lemma','pos','native_code','label_kind','frequency'],r)) for r in self.c.execute('SELECT dataset,lemma,pos,native_code,label_kind,frequency FROM lexical_frequency WHERE lemma=? AND pos=?',(lemma,pos))],'selected_group':None,'human_gold':False,'api_called':False}

def supplemented_dictionary(root=ROOT):
    """Explicit opt-in extension; the frozen production Dictionary is unmodified."""
    from context_full_use import Dictionary
    class SupplementedDictionary(Dictionary):
        def __init__(self):super().__init__();self.sejong=Supplement(root)
        def close(self):self.sejong.close();super().close()
        def lookup(self,lemma,pos,limit=5):
            result=super().lookup(lemma,pos,limit);result['sejong_sense_supplement']=self.sejong.lookup(lemma,pos,limit=limit);return result
        def decide(self,v,m,previous=()):
            result=super().decide(v,m,previous)
            if result.get('selected_group') is None:
                mp=[(x['form'],x['label'],'') for x in v.mp[m['word_id']]]
                extra=self.sejong.lookup(m['form'],m['label'],v.w[m['word_id']].get('form'),mp,limit=3)
                words=[[(x['form'],x['label'],'') for x in v.mp[wid]] for wid in v.ids]
                mi=next(i for i,x in enumerate(v.mp[m['word_id']]) if x['id']==m['id'])
                extra['matching_adjacent_contexts']=self.sejong.matched_patterns(words,v.at[m['word_id']],mi)
                result['sejong_supplement']=extra
                result['supplement_status']='annotated_context_and_definition_candidates_available'
            return result
    return SupplementedDictionary()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lemma',required=True);ap.add_argument('--pos',required=True);ap.add_argument('--surface');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=Supplement()
    try:r=s.lookup(a.lemma,a.pos,a.surface);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(js({'status':'written','contexts':len(r['annotated_contexts']),'variants':len(r['eojeol_evidence']['variants']) if r['eojeol_evidence'] else 0,'selected_group':None,'api_called':False}))
    finally:s.close()
if __name__=='__main__':main()
