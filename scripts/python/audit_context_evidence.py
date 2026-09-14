"""Check constructed data, receipts, archive coverage and representative recovery."""
import json,sqlite3,hashlib,zlib,random,zipfile
from pathlib import Path
from collections import Counter
from build_context_evidence import OUT,ROOT,INTAKE,plans,sha,js

def ro(path):return sqlite3.connect(f'file:{path.as_posix()}?mode=ro',uri=True)
def run():
    result={'status':'checking','units':{},'errors':[],'limitations':['Representative restoration checks are samples; full parsing and source SHA are recorded separately.','Source-specific counts do not remove cross-corpus overlap.'],'api_called':False}
    errors=result['errors']
    for name,kind,paths,spec in plans():
        receipt=OUT/(name+'.receipt.json');db=OUT/(name+'.sqlite')
        if not receipt.exists() or not db.exists():errors.append(name+':incomplete');continue
        r=json.loads(receipt.read_text(encoding='utf-8'));co=r['counts'];checks={}
        checks['database_sha']=sha(db)==r['database_sha256']
        checks['source_shas']=all(sha(Path(s['path']))==s['sha256'] and Path(s['path']).stat().st_size==s['bytes'] for s in r['sources'])
        c=ro(db);checks['quick_check']=c.execute('PRAGMA quick_check').fetchall()==[('ok',)]
        if kind=='corpus':
            for table,key in [('documents','documents'),('sentences','sentences'),('occurrences','WSD_occurrences')]:checks[table+'_count']=c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==co[key]
            checks['occurrence_parent']=c.execute('SELECT COUNT(*) FROM occurrences o LEFT JOIN sentences s ON s.id=o.sentence_id WHERE s.id IS NULL').fetchone()[0]==0
            checks['sentence_parent']=c.execute('SELECT COUNT(*) FROM sentences s LEFT JOIN documents d ON d.id=s.document_id WHERE d.id IS NULL').fetchone()[0]==0
            checks['relation_parent']=c.execute('SELECT COUNT(*) FROM relations r LEFT JOIN sentences s ON s.id=r.sentence_id WHERE s.id IS NULL').fetchone()[0]==0
            for rk in ['DP','SRL','ZA']:checks[rk+'_count']=c.execute('SELECT COUNT(*) FROM relations WHERE kind=?',(rk,)).fetchone()[0]==co.get(rk+'_records',0)
            n=co['sentences'];chosen=sorted({1,n,*random.Random(20260906).sample(range(1,n+1),min(n,12))})
            checks['restored_sentences']=True
            for sid in chosen:
                nid,form,raw=c.execute('SELECT native_id,form,raw FROM sentences WHERE id=?',(sid,)).fetchone();s=json.loads(zlib.decompress(raw))
                checks['restored_sentences'] &= s['id']==nid and s.get('form','')==form
                rows=c.execute('SELECT ordinal,raw FROM occurrences WHERE sentence_id=? ORDER BY ordinal',(sid,)).fetchall()
                checks['restored_sentences'] &= [json.loads(zlib.decompress(x[1])) for x in rows]==s.get('WSD',[])
            checks['restoration_sample_size']=len(chosen)
        elif kind=='urimal':
            checks['entry_count']=c.execute('SELECT COUNT(*) FROM entries').fetchone()[0]==co['entries']
            checks['entry_recovery']=all(str(json.loads(zlib.decompress(raw))['target_code'])==tid for tid,raw in c.execute('SELECT target,raw FROM entries ORDER BY target LIMIT 14'))
        elif kind=='sejong':
            checks['member_count']=c.execute('SELECT COUNT(*) FROM members').fetchone()[0]==co['archive_members']
            checks['sense_count']=c.execute('SELECT COUNT(*) FROM collocations').fetchone()[0]==co['collocation_senses']
            checks['xml_errors']=co.get('xml_parse_issues',0)==0
            checks['member_recovery']=all(hashlib.sha256(zlib.decompress(b)).hexdigest()==h for h,b in c.execute('SELECT sha256,raw FROM members ORDER BY id LIMIT 14'))
        elif kind=='frequency':checks['row_count']=c.execute('SELECT COUNT(*) FROM frequencies').fetchone()[0]==co['rows']
        elif kind=='csv':checks['row_count']=c.execute('SELECT COUNT(*) FROM records').fetchone()[0]==sum(co.values())
        c.close()
        for k,v in checks.items():
            if v is False:errors.append(name+':'+k)
        result['units'][name]={'counts':co,'checks':checks,'receipt_sha256':sha(receipt)}
        print(js({'checked':name,'errors':len(errors)}),flush=True)
    result['dictionary_units']={}
    for name,kind,paths,spec in plans():
        if kind!='corpus':continue
        rp=OUT/(name+'.dictionary.receipt.json');p=OUT/(name+'.dictionary.sqlite')
        if not rp.exists() or not p.exists():errors.append(name+':dictionary_incomplete');continue
        r=json.loads(rp.read_text(encoding='utf-8'));c=ro(p)
        ch={'database_sha':sha(p)==r['database_sha256'],'quick_check':c.execute('PRAGMA quick_check').fetchall()==[('ok',)],'binding_coverage':c.execute('SELECT SUM(occurrences) FROM bindings').fetchone()[0]==result['units'].get(name,{}).get('counts',{}).get('WSD_occurrences'),'pattern_count':c.execute('SELECT COUNT(*) FROM patterns').fetchone()[0]==r['counts']['patterns']}
        ch['special_codes_preserved']=c.execute('SELECT COALESCE(SUM(occurrences),0) FROM bindings WHERE state="special_or_invalid_native_code"').fetchone()[0]==result['units'].get(name,{}).get('counts',{}).get('special_or_invalid_native_codes',0)
        ch['special_codes_not_linked']=c.execute('SELECT COUNT(*) FROM bindings WHERE state="special_or_invalid_native_code" AND (groups_json!="[]" OR entry_ids_json!="[]")').fetchone()[0]==0
        ch['binding_key_count']=c.execute('SELECT COUNT(*) FROM bindings').fetchone()[0]==r['counts']['bindings']
        c.close();result['dictionary_units'][name]={'counts':r['counts'],'checks':ch}
        errors.extend(name+':dictionary_'+k for k,v in ch.items() if not v)
    expected=json.loads((INTAKE/'EXPECTED_DROPBOX_HASHES.json').read_text(encoding='utf-8'));intake=[]
    for m in expected:
        p=INTAKE/m['name'];block_hash=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(4194304),b''):block_hash.update(hashlib.sha256(b).digest())
        valid=p.stat().st_size==m['size'] and block_hash.hexdigest()==m['dropbox_content_hash']
        intake.append({**m,'sha256':sha(p),'verified':valid})
        if not valid:errors.append('intake:'+p.name)
    result['dropbox_intake']=intake
    c=ro(OUT/'sejong_collocations.sqlite');coverage=[]
    for p in INTAKE.glob('*.txt'):
        names={x.strip() for x in p.read_bytes().decode('cp949').splitlines() if x.strip()}
        sourceid=next(si for si,path in c.execute('SELECT id,path FROM sources') if ('상세' in path)==('상세' in p.name))
        xmlnames={x[0] for x in c.execute('SELECT DISTINCT orth FROM collocations c JOIN members m ON m.id=c.member_id WHERE m.source_id=?',(sourceid,))}
        coverage.append({'technical_list':p.name,'unique_listed':len(names),'unique_xml_orth':len(xmlnames),'list_only':sorted(names-xmlnames),'xml_only':sorted(xmlnames-names),'interpretation':'coverage discrepancies retained; names are not silently rewritten'})
    c.close();result['sejong_technical_list_coverage']=coverage
    sem=OUT/'semantic_cues.receipt.json'
    if sem.exists():
        r=json.loads(sem.read_text(encoding='utf-8'));result['semantic_layer']=r
        if sha(OUT/'semantic_cues.sqlite')!=r['database_sha256']:errors.append('semantic_sha')
    else:errors.append('semantic_incomplete')
    result['code_sha256']={p.name:sha(p) for p in [Path(__file__),*[ROOT/'scripts/python'/n for n in ['build_context_evidence.py','compile_context_dictionary.py','query_context_dictionary.py','build_context_semantic_layers.py','homonym_context_core.py','homonym_morphology.py','homonym_food_context.py']]]}
    result['status']='passed' if not errors else 'incomplete_or_failed'
    output=ROOT/'outputs/reports/VALIDATION_context_dictionary_build_20260906.json';output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(js({'status':result['status'],'errors':errors,'output':str(output)}),flush=True)
    return result
if __name__=='__main__':run()
