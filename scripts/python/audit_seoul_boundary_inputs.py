"""New tier/syllable topology audit, with prior KOINA receipts reused."""
import argparse,json,time
from collections import Counter
from pathlib import Path
from prepare_seoul_corpus import parse
from seoul_boundary_core import map_syllables,lexical

def run(base,out,params):
    if out.exists():
        raise RuntimeError('Existing audit must be reused, not overwritten')
    final=json.loads((base/'52_KOINA_FULL_V2_20260911/FINAL.json').read_text())
    records=[]; overall=Counter(); labels=Counter(); errors=[]
    for i,receipt in enumerate(final['sources']):
        name=receipt['source_file']; tiers,_=parse(base/f'00_SOURCE/00_file/{name}.TextGrid')
        pairs=[]
        for a,b in [(1,2),(1,4),(4,5),(3,6)]:
            x,y=tiers[a]['intervals'],tiers[b]['intervals']
            ok=len(x)==len(y) and all(abs(u['start']-v['start'])<1e-7 and abs(u['end']-v['end'])<1e-7 for u,v in zip(x,y))
            pairs.append(dict(tiers=[a+1,b+1],matched=ok))
        counts=Counter(); phones=tiers[0]['intervals']; ends=[p['end'] for p in phones]
        labels.update(p['text'] for p in phones)
        if all(p['matched'] for p in pairs):
            for w,p,r in zip(tiers[4]['intervals'],tiers[1]['intervals'],tiers[2]['intervals']):
                _,reason=map_syllables(w,p,r,phones,ends,set(params['vowel_codes_hypothesis']))
                counts[reason]+=1
        else:
            errors.append(name)
            counts['tier_pair_mismatch']=len(tiers[4]['intervals'])
        overall.update(counts)
        records.append(dict(source_file=name,tier_counts=[len(t['intervals']) for t in tiers],
                            pairs=pairs,mapping_counts=dict(counts),source_sha_from_completed_receipt=receipt['source']['textgrid_sha256'],
                            source_hash_recomputed=False))
        if (i+1)%60==0: print(json.dumps({'topology_recordings':i+1}),flush=True)
    assert len(records)==240
    assert sum(r['tier_counts'][6] for r in records)==128313
    payload=dict(status='completed_with_holds' if errors else 'completed',recordings=len(records),
                 original_t7_intervals=sum(r['tier_counts'][6] for r in records),
                 original_t5_intervals=sum(r['tier_counts'][4] for r in records),
                 tier_mismatch_recordings=errors,mapping_counts=dict(overall),phone_labels=dict(labels),sources=records,
                 semantic_accuracy_evaluated=False,source_files_modified=False)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k not in ('phone_labels','sources')},ensure_ascii=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--out',required=True);p.add_argument('--parameters',required=True)
    a=p.parse_args();run(Path(a.base),Path(a.out),json.loads(Path(a.parameters).read_text()))
