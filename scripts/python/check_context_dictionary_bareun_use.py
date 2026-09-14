"""Read one existing Bareun morphology file; verify dictionary input compatibility.

This is a construction usability check, not corpus-wide application or accuracy scoring.
All input rows (including nonlexical and OOV) remain in the output sidecar.
"""
import csv,gzip,json,sqlite3
from pathlib import Path
from collections import Counter,defaultdict
from build_context_evidence import ROOT,OUT,sha,js,LEX
from compile_context_dictionary import candidates
from homonym_morphology import structure_features

def run():
    work=ROOT/'work/context_dictionary_build_20260906'
    p=Path(json.loads((work/'BAREUN_EXISTING_SAMPLE_PATH.json').read_text(encoding='utf-8'))['path'])
    before=sha(p)
    receipt_path=p.parent/'RECEIPT.json';receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt.get('status')!='completed' or receipt.get('with_sense') is not False or receipt['outputs'][p.name]['sha256']!=before:raise ValueError('Bareun source receipt mismatch')
    with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if not rows:raise ValueError('empty Bareun sample')
    if len(rows)!=receipt['counts']['morphemes']:raise ValueError('Bareun receipt row count mismatch')
    lex=sqlite3.connect(f'file:{(OUT/"urimalsaem.sqlite").as_posix()}?mode=ro',uri=True)
    words=defaultdict(list)
    for row in rows:words[(row['utt_id'],int(row['token_index']))].append(row)
    cache={};out=[];co=Counter()
    for (utt,token),wr in words.items():
        wr.sort(key=lambda r:int(r['morph_index']))
        ms=[{'id':int(r['morph_index']),'form':r['morph_surface'],'label':r['pos'],'position':i,'word_id':token} for i,r in enumerate(wr)]
        for row,m in zip(wr,ms):
            co['input_morphemes']+=1
            item={'raw_bareun':row,'source_analysis':'existing_Bareun_morphology_without_new_API','state':'functional_or_other_preserved','selected_group':None}
            if m['label'] in LEX:
                key=(m['form'],m['label'])
                if key not in cache:cache[key]=candidates(lex,*key)
                cs=cache[key];kept=[x for x in cs if x['state']!='incompatible'];groups=sorted({x['group'] for x in kept})
                structure=structure_features(ms,m)
                compatible={x['group'] for x in kept if x['state']=='compatible'}
                uncertain={x['group'] for x in kept if x['state']=='unknown'}-compatible
                item.update(candidate_groups=groups,structure=structure,entry_ids=[x['target'] for x in kept],uncertain_groups=sorted(uncertain))
                if structure['issues']:item['state']='structure_hold'
                elif not groups:item['state']='no_compatible_dictionary_entry_preserved'
                elif uncertain:item['state']='dictionary_metadata_hold'
                elif len(groups)==1:item.update(state='morphology_singleton_machine_link',selected_group=groups[0])
                else:item['state']='context_candidates_retained'
            co[item['state']]+=1;out.append(item)
    lex.close()
    if len(out)!=len(rows) or sha(p)!=before:raise ValueError('preservation_or_source_sha_failed')
    sidecar=work/'BAREUN_EXISTING_INPUT_CHECK.jsonl'
    with sidecar.open('w',encoding='utf-8') as f:
        for r in out:f.write(js(r)+'\n')
    report={'status':'passed','purpose':'existing Bareun morphology compatibility and preservation, not accuracy estimate','source_path':str(p),'source_sha256':before,'existing_receipt_sha256':sha(receipt_path),'existing_receipt_verified':True,'output_sha256':sha(sidecar),'source_utterances':len({r['utt_id'] for r in rows}),'source_files':len({r['source_file'] for r in rows}),'counts':dict(co),'api_called':False,'target_corpus_bulk_application':False,'limitations':['Only this existing source file was checked.','Context candidates are retained; this check does not choose them.','A morphology singleton is a machine linkage, not independent gold.']}
    (ROOT/'outputs/reports/CHECK_context_dictionary_existing_bareun_20260906.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(js({k:v for k,v in report.items() if k not in {'source_path','source_sha256','output_sha256'}}))
if __name__=='__main__':run()
