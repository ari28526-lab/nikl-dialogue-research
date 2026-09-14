"""Read-only independent source/derivative audit, except new audit receipts."""
import argparse,csv,hashlib,json,time
from collections import Counter,defaultdict
from pathlib import Path
import textgrid

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(d,indent=2),encoding='utf-8')
    for attempt in range(30):
        try:
            tmp.replace(p)
            break
        except PermissionError:
            if attempt==29:raise
            time.sleep(min(.05*(attempt+1),.5))
def load_tg(p):
    tg=textgrid.TextGrid();tg.read(str(p),round_digits=15);return tg

def run(base,out):
    index=read(out/'INDEX.json')['recordings']
    expected=read(base/'52_KOINA_FULL_V2_20260911/FINAL.json')['sources']
    assert len(index)==240 and {r['source_file'] for r in index}=={r['source_file'] for r in expected}
    word_ids=set();utt_ids=set();counts=Counter();preserved=0;points_checked=0;receipts=[]
    for item in index:
        name=item['source_file'];folder=out/'recordings'/name
        for a in item['artifacts']:
            p=folder/a['name'];assert p.stat().st_size==a['bytes'] and sha(p)==a['sha256']
        doc=read(folder/f'{name}.json');rows=doc['word_end_evaluations'];utts=doc['original_utterances']
        orig=load_tg(base/f'00_SOURCE/00_file/{name}.TextGrid');derived=load_tg(folder/f'{name}_AP_IP_MACHINE.TextGrid')
        assert len(orig.tiers)==7 and len(derived.tiers)==8
        for old,new in zip(orig.tiers,derived.tiers[:7]):
            assert old.name==new.name and len(old.intervals)==len(new.intervals)
            assert abs(old.minTime-new.minTime)<1e-12 and abs(old.maxTime-new.maxTime)<1e-12
            for a,b in zip(old.intervals,new.intervals):
                assert a.mark==b.mark and abs(a.minTime-b.minTime)<1e-12 and abs(a.maxTime-b.maxTime)<1e-12
                preserved+=1
        assert len(rows)==len(orig.tiers[4].intervals)==item['words']
        assert len(utts)==len(orig.tiers[6].intervals)==item['utterances']
        grouped=defaultdict(list)
        for i,(r,w) in enumerate(zip(rows,orig.tiers[4].intervals),1):
            assert r['candidate_id']==f'seoul:{name}:t5:i{i}:end' and r['candidate_id'] not in word_ids
            word_ids.add(r['candidate_id']);counts[r['candidate_type']]+=1
            assert r['word']==w.mark and abs(r['boundary_seconds']-w.maxTime)<1e-12
            assert abs(r['word_start_seconds']-w.minTime)<1e-12
            assert not r['human_verified'] and r['manual_break_index'] is None
            if r['candidate_type'] in ('AP_candidate','IP_candidate'):
                assert not r['hold_reasons'] and len(set(r['parameter_classes']))==1
                assert not set(r['quality_flags']) & {'threshold_sensitive','local_pitch_settings_sensitive'}
            if r['utt_id']:
                u=orig.tiers[6].intervals[int(r['utt_id'].split(':i')[-1])-1]
                assert u.minTime<=w.minTime+1e-12 and w.maxTime<=u.maxTime+1e-12
            grouped[r['boundary_seconds']].append(r)
        for i,(u,source) in enumerate(zip(utts,orig.tiers[6].intervals),1):
            assert u['utt_id']==f'seoul:{name}:t7:i{i}' and u['utt_id'] not in utt_ids
            utt_ids.add(u['utt_id'])
            assert u['text']==source.mark and abs(u['start_seconds']-source.minTime)<1e-12 and abs(u['end_seconds']-source.maxTime)<1e-12
        assert derived.tiers[7].name=='AP_IP_MACHINE_EVALUATION_V01'
        assert len(derived.tiers[7].points)==len(grouped)==item['textgrid_points']
        for p,(t,group) in zip(derived.tiers[7].points,sorted(grouped.items())):
            label=','.join(sorted(set(r['candidate_type'] for r in group)))+'|'+','.join(r['candidate_id'] for r in group)
            assert abs(p.time-t)<1e-12 and p.mark==label
            points_checked+=1
        for filename,records in [('candidates.csv',rows),('utterances.csv',utts)]:
            with (folder/filename).open(encoding='utf-8-sig',newline='') as f:
                csvrows=list(csv.DictReader(f))
            assert len(csvrows)==len(records)
            for c,r in zip(csvrows,records):
                assert set(c)==set(r)
                for k,v in r.items():assert json.loads(c[k])==v if isinstance(v,(dict,list)) else c[k]==('' if v is None else str(v))
        receipts.append(dict(source_file=name,passed=True,words=len(rows),utterances=len(utts)))
        save(out/'AUDIT_PROGRESS.json',dict(status='auditing',recordings=len(receipts),words=len(word_ids),utterances=len(utt_ids),updated_at=time.strftime('%Y-%m-%dT%H:%M:%S')))
    assert len(word_ids)==302288 and len(utt_ids)==128313
    for filename,key,expected_ids in [('candidates.csv','candidate_id',word_ids),('utterances.csv','utt_id',utt_ids)]:
        seen=set()
        # Compare every aggregate row with the corresponding per-record CSV in index order.
        with (out/filename).open(encoding='utf-8-sig',newline='') as agg:
            aggregate=csv.DictReader(agg)
            for item in index:
                with (out/'recordings'/item['source_file']/filename).open(encoding='utf-8-sig',newline='') as local:
                    for row in csv.DictReader(local):
                        other=next(aggregate);assert row==other and row[key] not in seen;seen.add(row[key])
            assert next(aggregate,None) is None
        assert seen==expected_ids
    assert read(out/'PILOT_EQUIVALENCE.json')['passed']
    review=out.parent/'PILOT_V01'
    pilot_audit=read(review/'AUDIT.json')
    for artifact in pilot_audit['artifacts']:
        p=review/artifact['path'];assert p.exists() and p.stat().st_size==artifact['bytes']
    assert (out/'REVIEW.html').exists()
    result=dict(passed=True,status='complete_technical_audit_not_semantic_validation',recordings=len(receipts),
        words=len(word_ids),utterances=len(utt_ids),candidate_counts=dict(counts),
        original_tier_intervals_preserved=preserved,points_checked=points_checked,
        aggregates={n:dict(bytes=(out/n).stat().st_size,sha256=sha(out/n)) for n in ['candidates.csv','utterances.csv','INDEX.json','REVIEW.html']},
        records=receipts,human_accuracy_evaluated=False,pilot_review_reused=True,
        source_wav_hashes_reused=True,original_files_modified=False)
    save(out/'AUDIT.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('records','aggregates')}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(Path(a.base),Path(a.out))
