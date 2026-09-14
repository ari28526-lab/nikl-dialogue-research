"""Independent result accounting and source-backed sample replay. No API calls."""
import argparse,collections,csv,gzip,json,sqlite3
from pathlib import Path
from apply_seoul_dictionary import OUT,INPUT,read,sha,digest,morph_key,save
from context_full_lexicon import FULL,BASE

def audit():
    db=sqlite3.connect(f'file:{(OUT/"EVIDENCE.sqlite").as_posix()}?mode=ro',uri=True)
    lex=sqlite3.connect(f'file:{(BASE/"urimalsaem.sqlite").as_posix()}?mode=ro',uri=True)
    counts=collections.Counter();checked_patterns=0;connections={};receipts=list((OUT/'receipts').glob('*.json'))
    try:
        for rp in sorted(receipts):
            p=OUT/'json'/(rp.stem+'.json.gz');receipt=read(rp)
            assert sha(p)==receipt['output_sha256'] and sha(INPUT/'json'/(rp.stem+'.json'))==receipt['input_sha256']
            with gzip.open(p,'rt',encoding='utf-8') as f:d=json.load(f)
            original=read(INPUT/'json'/(rp.stem+'.json'));by={morph_key(r):r for r in original['morphology']};seen=set()
            for result in d['results']:
                r=result['bareun'];key=morph_key(r);assert key not in seen and by[key]==r;seen.add(key)
                a=result['dictionary'];c=result['comparison'];selected=a.get('selected_group')
                if selected is not None:assert selected in a['candidate_groups'] and not result['source_gap_in_utterance']
                if c.get('bareun_group'):
                    group=lex.execute('SELECT group_id FROM entries WHERE target=?',(str(r['urimal_target_id']),)).fetchone()
                    assert group and group[0]==c['bareun_group']
                if c['status']=='same_homonym_group':assert selected is not None and c['bareun_group']==selected
                if c['status']=='group_conflict':assert selected is not None and c['bareun_group']!=selected
                assert c['final_selected_group'] is None and not c['human_verified']
                for eid in result['evidence_refs']:
                    ev=db.execute('SELECT kind,payload FROM evidence WHERE id=?',(eid,)).fetchone();assert ev
                    value=json.loads(ev[1]);assert digest([ev[0],value])==eid
                # Replay a bounded sample of native base-pattern evidence against source DBs.
                for e in a.get('evidence',[]):
                    if checked_patterns>=30 or 'pattern_hash' not in e:continue
                    name=e['source']
                    if name not in connections:connections[name]=sqlite3.connect(f'file:{(FULL/(name+".sqlite")).as_posix()}?mode=ro',uri=True)
                    rows=connections[name].execute('SELECT occurrences FROM patterns WHERE hash=? AND group_id=? AND label_kind=?',
                        (bytes.fromhex(e['pattern_hash']),e['group'],'native_snapshot_candidate')).fetchall()
                    assert sum(r[0] for r in rows)==e['occurrences'];checked_patterns+=1
                counts['morphemes']+=1;counts['comparison:'+c['status']]+=1
            assert len(seen)==len(by);counts['sources']+=1
        if (OUT/'FINAL.json').exists():
            final=read(OUT/'FINAL.json');assert counts['sources']==240 and counts['morphemes']==396193
            for artifact in final['artifacts']:assert sha(Path(artifact['path']))==artifact['sha256']
            with (OUT/'dictionary_comparison.csv').open(encoding='utf-8-sig',newline='') as f:
                csv_counts=collections.Counter(r['comparison_status'] for r in csv.DictReader(f))
            assert csv_counts==final['comparison']
        report=dict(status='passed',scope='all_completed_source_receipts',counts=dict(counts),native_pattern_samples_replayed=checked_patterns,
            source_rows_exactly_preserved=True,final_research_judgments_created=False,api_called=False,semantic_accuracy_evaluated=False)
        save(OUT/('AUDIT.json' if (OUT/'FINAL.json').exists() else 'PILOT_AUDIT.json'),report)
        print(json.dumps(report,ensure_ascii=True))
    finally:
        db.close();lex.close()
        for c in connections.values():c.close()
if __name__=='__main__':audit()
