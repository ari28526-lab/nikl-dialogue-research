"""Read-only morphology-first dictionary lookup with recoverable donor context."""
import argparse,json,sqlite3,zlib
from pathlib import Path
from build_context_evidence import OUT,js
from compile_context_dictionary import candidates
from homonym_context_core import markers, POS, NOUNS

def connect(name):return sqlite3.connect(f'file:{(OUT/(name+".sqlite")).as_posix()}?mode=ro',uri=True)
def unpack(b):return json.loads(zlib.decompress(b))

def contextual_cues(s,semantic,did,ordinal,target_sid,target_wid,target_lemma):
    cues=[]
    for sid,native,offset,raw in s.execute('SELECT id,native_id,ordinal,raw FROM sentences WHERE document_id=? AND ordinal BETWEEN ? AND ? ORDER BY ordinal',(did,ordinal-3,ordinal+3)):
        sent=unpack(raw);mp=sent.get('MP',sent.get('morpheme',[]))
        for m in mp:
            if sid==target_sid and m.get('word_id')==target_wid and m.get('form')==target_lemma:continue
            if m.get('form')=='먹' and m.get('label')=='VV':
                cues.append({'kind':'eat_form_not_disambiguated','sentence_id':native,'offset':offset-ordinal,'word_id':m.get('word_id'),'relation':'context_cooccurrence','markers':markers(mp)})
            if m.get('label') not in NOUNS:continue
            for tid,gid,ep in semantic.execute('SELECT target,group_id,pos FROM food_cues WHERE lemma=?',(m.get('form'),)):
                if ep and ep not in POS.get(m.get('label'),[]):continue
                cues.append({'kind':'food_definition_keyword_candidate','sentence_id':native,'offset':offset-ordinal,'word_id':m.get('word_id'),'lemma':m.get('form'),'entry_id':tid,'group_id':gid,'relation':'same_word' if sid==target_sid and m.get('word_id')==target_wid else 'context_cooccurrence','markers':markers(mp)})
        if sid==target_sid:
            for sr in sent.get('SRL',[]):
                if sr.get('predicate',{}).get('lemma') in {'먹','먹다'}:
                    for a in sr.get('argument',[]):
                        if target_wid in a.get('word_id',[]):cues.append({'kind':'native_eat_argument','relation':'native_SRL_argument','label':a.get('label'),'predicate':sr['predicate'],'argument':a,'eat_sense_verified':False})
    return cues

def query(lemma,pos,limit=3):
    lex=connect('urimalsaem');cs=candidates(lex,lemma,pos);lex.close()
    kept=[x for x in cs if x['state']!='incompatible']
    forms={lemma,*[x['word'].replace('-','').replace('^','') for x in kept]}
    result={'lemma':lemma,'pos':pos,'morphology_first':{'candidate_groups':sorted({x['group'] for x in kept}),'entries':cs,'decision':'candidate lookup; actual Bareun occurrence and structure required for assignment'},'sejong':[],'sources':{},'automatic_adoption':False,'api_called':False}
    if (OUT/'MP_background.sqlite').exists():
        freq=connect('MP_background')
        result['MP_background']=[{'source_id':si,'genre':{1:'written',2:'spoken'}.get(si),'frequency':n} for si,n in freq.execute('SELECT source_id,frequency FROM frequencies WHERE form=? AND pos=?',(lemma,pos))];freq.close()
    if (OUT/'lexicon_and_crosswalk.sqlite').exists():
        cross=connect('lexicon_and_crosswalk')
        result['existing_lexicon_records']=[{'source_id':si,'record':unpack(raw),'state':'existing_analysis_not_promoted_to_gold'} for form in sorted(forms) for si,raw in cross.execute('SELECT source_id,raw FROM records WHERE lemma=? LIMIT 20',(form,))];cross.close()
    sej=connect('sejong_collocations')
    for form in sorted(forms):
        for cid,orth,b,co,fields,mid in sej.execute('SELECT id,orth,base,collocate,fields_json,member_id FROM collocations WHERE base=? OR collocate=? LIMIT ?',(form,form,limit)):
            result['sejong'].append({'record_id':cid,'orth':orth,'base':b,'collocate':co,'fields':json.loads(fields),'source_member_id':mid,'link_state':'surface_form_match_not_group_or_affix_link'})
    sej.close()
    semantic=connect('semantic_cues') if (OUT/'semantic_cues.sqlite').exists() else None
    for path in sorted(OUT.glob('*.dictionary.sqlite')):
        name=path.name.removesuffix('.dictionary.sqlite');d=connect(name+'.dictionary');s=connect(name)
        b=[{'native_code':code,'state':state,'candidate_groups':json.loads(groups),'occurrences':n} for code,state,groups,n in d.execute('SELECT native_code,state,groups_json,occurrences FROM bindings WHERE lemma=? AND pos=? ORDER BY occurrences DESC',(lemma,pos))]
        patterns=[]
        for native,fam,wp,anchor,n,nd,oid in d.execute('SELECT native_code,family,word_pattern,anchor,occurrences,documents,evidence_occurrence_id FROM patterns WHERE lemma=? AND pos=? ORDER BY occurrences DESC LIMIT ?',(lemma,pos,limit)):
            sid,raw=s.execute('SELECT sentence_id,raw FROM occurrences WHERE id=?',(oid,)).fetchone()
            did,ordinal=s.execute('SELECT document_id,ordinal FROM sentences WHERE id=?',(sid,)).fetchone()
            context=[{'sentence_id':sn,'ordinal':o,'form':form,'speaker':speaker} for sn,o,form,speaker in s.execute('SELECT native_id,ordinal,form,speaker FROM sentences WHERE document_id=? AND ordinal BETWEEN ? AND ? ORDER BY ordinal',(did,ordinal-3,ordinal+3))]
            relations=[{'kind':k,'native_annotation':unpack(r)} for k,r in s.execute('SELECT kind,raw FROM relations WHERE sentence_id=? AND kind IN ("SRL","ZA")',(sid,))]
            target=unpack(raw)
            competing=[{'native_code':other,'occurrences':on,'documents':od} for other,on,od in d.execute('SELECT native_code,occurrences,documents FROM patterns WHERE lemma=? AND pos=? AND family=? AND word_pattern=? AND anchor=? AND native_code IS NOT ?',(lemma,pos,fam,wp,anchor,native))]
            patterns.append({'native_code':native,'family':fam,'target_word_morphemes':json.loads(wp),'neighbor_lexical_morphemes':json.loads(anchor),'occurrences':n,'documents':nd,'same_pattern_competing_senses':competing,'evidence_occurrence_id':oid,'target_native_WSD':target,'context':context,'native_relations':relations,'food_and_eat_cues':contextual_cues(s,semantic,did,ordinal,sid,target.get('word_id'),lemma) if semantic else []})
        result['sources'][name]={'native_code_bindings':b,'observed_patterns':patterns}
        d.close();s.close()
    if semantic:semantic.close()
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--lemma',required=True);p.add_argument('--pos',required=True);p.add_argument('--limit',type=int,default=3);p.add_argument('--output');a=p.parse_args()
    if not 1<=a.limit<=20:raise ValueError('limit must be 1..20')
    r=query(a.lemma,a.pos,a.limit)
    if a.output:Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    else:print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
