"""Construction audit: full accounting, source immutability, condition replay."""
import argparse,json,time
from collections import Counter
from pathlib import Path
from context_full_lexicon import FULL,BASE,ROOT,SOURCES,ro,Lexicon,unpack
from context_full_features import Sentence,extract,za_links,signature,VERSION
from build_context_evidence import sha,js

def audit(name):
    rp=FULL/(name+'.receipt.json');r=json.loads(rp.read_text(encoding='utf-8'));db=FULL/(name+'.sqlite');old=json.loads((BASE/(name+'.receipt.json')).read_text(encoding='utf-8'));co=r['counts'];checks={}
    print(js({'audit_started':name,'stage':'SHA_and_source_identity'}),flush=True)
    checks['database_sha']=sha(db)==r['database_sha256'];checks['inputs_unchanged']=all(sha(Path(p))==h for p,h in r['input_shas'].items())
    c=ro(db);source=ro(BASE/(name+'.sqlite'));lex=Lexicon()
    # The known publisher ran quick_check before SHA/rename. A matching SHA
    # establishes the identical checked bytes; avoid re-running that same scan.
    known_publisher=r.get('code_shas',{}).get('context_full_lexicon.py')==sha(Path(__file__).with_name('context_full_lexicon.py'))
    if known_publisher and checks['database_sha'] and r['status']=='complete':
        checks['published_quick_check_and_matching_sha']=True;integrity_method='known_publish_function_quick_check_then_independent_SHA_match'
    else:
        checks['sqlite_quick_check']=c.execute('PRAGMA quick_check').fetchall()==[('ok',)];integrity_method='audit_reran_quick_check'
    print(js({'audit_progress':name,'stage':'full_counts_and_conditions'}),flush=True)
    for new,original in [('documents','documents'),('sentences','sentences'),('morphemes_accounted','morphemes_preserved'),('native_WSD_annotations','WSD_occurrences')]:checks['source_count_'+new]=co[new]==old['counts'][original]
    checks['target_count']=c.execute('SELECT COUNT(*) FROM targets').fetchone()[0]==co['lexical_targets']
    checks['annotation_count']=c.execute('SELECT COUNT(*) FROM annotations').fetchone()[0]==co['native_WSD_annotations']
    checks['searchable_sentences']=c.execute('SELECT COUNT(*) FROM utterance_search').fetchone()[0]==co['sentences']
    checks['target_routing']=sum(co.get(k,0) for k in ['context_indexed_targets','context_not_needed_morphology_singleton','no_dictionary_context_retained_in_source'])==co['lexical_targets']
    checks['source_pointer_ranges']=c.execute('SELECT COUNT(*) FROM targets WHERE sentence_id<1 OR sentence_id>? OR document_id<1 OR document_id>?',(co['sentences'],co['documents'])).fetchone()[0]==0
    # One sequential scan avoids family-index random reads of the large key table.
    families=Counter();pattern_count=0;bad_bounds=0
    for fam,n,nd,first,last in c.execute('SELECT family,occurrences,documents,first_target,last_target FROM patterns NOT INDEXED'):
        pattern_count+=1;families[fam]+=n
        if n<nd or nd<1 or first>last or first<1 or last>co['lexical_targets']:bad_bounds+=1
    checks['pattern_count']=pattern_count==co['patterns'];checks['distribution_bounds']=bad_bounds==0
    checks['family_accounting']=families==r['families'];checks['observation_count']=sum(families.values())==co['feature_observations']
    checked=[];views_cache={}
    for family in sorted(families):
        h,key,first=c.execute('SELECT hash,key_json,first_target FROM patterns WHERE family=? LIMIT 1',(family,)).fetchone()
        sid,did,mid=c.execute('SELECT sentence_id,document_id,morph_id FROM targets WHERE id=?',(first,)).fetchone()
        if did not in views_cache:
            rr=source.execute('SELECT id,ordinal,raw FROM sentences WHERE document_id=? ORDER BY ordinal',(did,)).fetchall()
            vv=[Sentence(unpack(raw),ordinal,lex) for sid,ordinal,raw in rr];zz,zi=za_links(vv);views_cache[did]=({sid:i for i,(sid,ordinal,raw) in enumerate(rr)},vv,zz)
        where,vv,zz=views_cache[did];at=where[sid];v=vv[at];m=next(m for m in v.targets if m['id']==mid)
        feats=extract(v,m,vv[max(0,at-3):at])
        for link in zz.get((v.raw['id'],m['word_id']),[]):
            k=[VERSION,'K31_ZA',m['form'],m['label'],m['position'],link,v.guard];feats[signature(k)]=('K31_ZA',js(k),'native_ZA_validated_span')
        ok=signature(json.loads(key))==h and h in feats and feats[h][1]==key
        checked.append({'family':family,'target_id':first,'reproduced':ok})
    checks['condition_replay']=all(x['reproduced'] for x in checked)
    # Existing machine labels and mapping holds remain distinct from native support.
    labels={k:n for k,n in c.execute('SELECT label_kind,COUNT(*) FROM targets GROUP BY label_kind')}
    checks['label_accounting']=all(co.get('label_'+k)==n for k,n in labels.items())
    checks['hold_labels_not_grouped']=c.execute('SELECT COUNT(*) FROM targets WHERE label_kind IN ("native_mapping_hold","annotation_conflict","unannotated") AND group_id!=""').fetchone()[0]==0
    c.close();source.close();lex.close()
    result={'source':name,'status':'passed' if all(checks.values()) else 'failed','checks':checks,'errors':[k for k,v in checks.items() if not v],'counts':co,'families':families,'replayed_conditions':checked,'database_sha256':r['database_sha256'],'receipt_sha256':sha(rp),'audit_code_sha256':sha(Path(__file__)),'sqlite_integrity_method':integrity_method,'api_called':False}
    output=ROOT/'work/context_dictionary_full_20260906'/('AUDIT_'+name+'.json');output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(js({'audited':name,'status':result['status'],'errors':result['errors']}),flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--unit',action='append');a=p.parse_args()
    for name in a.unit or SOURCES:
        if name not in SOURCES:raise ValueError('unknown source')
        audit(name)
