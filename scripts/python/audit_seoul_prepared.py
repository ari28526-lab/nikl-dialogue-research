"""Read-only verification of Seoul CSV/JSON/request exports; no API."""
import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
import argparse

def audit(root):
    m=json.loads((root/'FINAL_MANIFEST.json').read_text('utf-8'))
    artifacts={a['path']:a for a in m['artifacts']}
    for rel,a in artifacts.items():
        p=root/rel
        with p.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        assert p.stat().st_size==a['bytes'] and digest==a['sha256'], ('artifact_changed',rel)
    utterances={};words={};phones={};intervals=0
    for rel in artifacts:
        if not rel.replace('\\','/').startswith('json/'):continue
        d=json.loads((root/rel).read_text('utf-8'));sid=d['source_file']
        assert d['analysis_status']=='not_run' and not d['morphology'] and not d['wsd']
        assert len(d['tiers'])==7
        intervals+=sum(len(t['intervals']) for t in d['tiers'])
        for u in d['tiers'][6]['intervals']:
            key=f"seoul:{sid}:t7:i{u['interval_index']}";assert key not in utterances
            utterances[key]=u
        for w in d['tiers'][4]['intervals']:
            words[f"seoul:{sid}:t5:i{w['interval_index']}"]=w
        phones[sid]=len(d['tiers'][0]['intervals'])
    assert intervals==m['counts']['all_tier_intervals']
    seen=set(); ready={};statuses=Counter()
    with (root/'utterances.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            key=row['utt_id'];assert key not in seen;seen.add(key);u=utterances[key]
            assert row['text']==u['text'] and float(row['start'])==u['start'] and float(row['end'])==u['end']
            assert row['morph_status']==row['wsd_status']=='not_run'
            statuses[row['input_status']]+=1
            if row['input_status']=='ready':ready[key]=row['text']
    assert seen==set(utterances) and statuses==m['input_statuses']
    request_seen=set();eojeol=0
    with (root/'BAREUN_REQUESTS.jsonl').open(encoding='utf-8') as f:
        for line in f:
            q=json.loads(line);key=q['utt_id'];assert key not in request_seen;request_seen.add(key)
            assert q['text']==ready[key] and hashlib.sha256(q['text'].encode('utf-8')).hexdigest()==q['text_sha256']
            assert q['char_start']==0 and q['char_end']==len(q['text'])
            assert q['options']['with_sense'] is True
            eojeol+=len(q['text'].split())
    assert request_seen==set(ready) and eojeol==m['counts']['transmitted_eojeol']
    seen=set();links=Counter()
    with (root/'words.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            key=row['word_id'];assert key not in seen;seen.add(key);w=words[key]
            assert row['orthography']==w['text'] and float(row['start'])==w['start'] and float(row['end'])==w['end']
            links[row['link_status']]+=1
            if row['link_status']=='contained':
                u=utterances[row['utt_id']]
                assert u['start']<=w['start']+1e-7 and w['end']<=u['end']+1e-7
            else:assert not row['utt_id']
    assert seen==set(words) and links==m['word_utterance_links']
    actual=Counter()
    with gzip.open(root/'phonemes.csv.gz','rt',encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):actual[row['source_file']]+=1
    assert actual==phones
    result=dict(status='passed',api_called=False,wsd_completed=False,artifacts_sha_checked=len(artifacts),
        utterances=len(utterances),words=len(words),phonemes=sum(phones.values()),requests=len(ready),eojeol=eojeol,
        scope='Export integrity and input accounting; not morphological or semantic accuracy')
    (root/'AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();audit(a.root)
