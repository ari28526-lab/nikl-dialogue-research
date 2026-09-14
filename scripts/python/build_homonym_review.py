"""Build a local, offline conversation review; completed pilot inputs stay read-only."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from research_paths import data_path, drive_root, resolve_legacy_path, qc_diagnostics
import os

REPO = Path(__file__).resolve().parents[2]
ROOT = data_path('homonym_review_source')
OUT = REPO / 'outputs/reviews/HOMONYM_CONTEXT_REVIEW_20260906'
TEMPLATE = REPO / 'scripts/templates/homonym_review.html'
REASONS = {'selected':'문맥으로 기계 선택', 'unseen':'활용 가능한 구축 용례 없음',
           'unmatched':'단어 용례는 있지만 결합 불일치', 'conflict':'문맥 근거 충돌'}

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp')
    temp.write_text(value, encoding='utf-8')
    os.replace(temp,p)
def js(value): return json.dumps(value,ensure_ascii=False).replace('<','\\u003c')

def build():
    receipt=read(ROOT/'FINAL_RECEIPT.json')
    assert receipt['audit']['passed'] and receipt['status']=='completed_pilot_pending_research_review'
    names=[n for n in receipt['files'] if (n.startswith(('documents/','applications/')) and not n.endswith('.receipt.json')) or n in ('LEXICON.json','CONTEXT_DICTIONARY.json')]
    for n in names:
        assert sha(ROOT/n)==receipt['files'][n], 'changed input: '+n
    docs=[read(ROOT/n) for n in sorted(names) if n.startswith('documents/')]
    pats={p['id']:p for p in read(ROOT/'CONTEXT_DICTIONARY.json')['patterns']}
    known={(p['key'][1],p['key'][2]) for p in pats.values()}
    lexical={e['target_code']:e for e in read(ROOT/'LEXICON.json')['entries']}
    morphs={m['id']:(b,m) for b in docs for m in b['morphemes']}
    sentences={}; documents={}; train=defaultdict(list)
    for b in docs:
        dk=b['source']+'/'+b['document_id']
        documents[dk]=dict(source=b['source'],id=b['document_id'],split=b['split'],metadata=b['raw_document'].get('metadata'),sentence_ids=[])
        for s in b['raw_document']['sentence']:
            sk=dk+'/'+s['id']; documents[dk]['sentence_ids'].append(sk)
            sentences[sk]=dict(id=s['id'],form=s['form'],original_form=s.get('original_form'),speaker=s.get('speaker_id'),
                words=s['word'],mp=s.get('MP',s.get('morpheme',[])),optional_layers={k:s[k] for k in ('DP','SRL','ZA') if k in s})
        if b['split']=='train':
            for m in b['morphemes']:
                train[(m['raw']['form'],m['raw']['label'])].append(m['id'])
    def sentence_key(b,m):return b['source']+'/'+b['document_id']+'/'+m['sentence_id']
    def example(eid):
        b,m=morphs[eid]
        return dict(target=eid,sentence=sentence_key(b,m),word_id=m['raw']['word_id'],mp=m['raw'])
    cases=[];used_entries=set();family_counts=Counter()
    for n in sorted(names):
        if not n.startswith('applications/'):continue
        for d in read(ROOT/n)['decisions']:
            if len(d.get('candidate_groups',[]))<2:continue
            b,m=morphs[d['target_id']]; key=(m['raw']['form'],m['raw']['label'])
            reason=('selected' if d['selected_group'] is not None else 'conflict' if d['state']=='context_conflict' else 'unseen' if key not in known else 'unmatched')
            support=[];eids=set();docids=set();fams=set()
            for pid in d['supporting_pattern_ids']+d.get('conflicting_pattern_ids',[]):
                p=pats[pid];fams.add(p['family'])
                for g in p['groups'].values():eids.update(g['evidence_ids'])
                support.append(p)
            for eid in eids:
                eb,em=morphs[eid];docids.add(eb['source']+'/'+eb['document_id'])
            family_counts.update(fams)
            used_entries.update(m['candidate_entry_ids'])
            cases.append(dict(id='H-'+m['id'][:10].upper(),target_id=m['id'],lemma=key[0],pos=key[1],reason=reason,
                document=b['source']+'/'+b['document_id'],sentence=sentence_key(b,m),word_id=m['raw']['word_id'],mp=m['raw'],
                candidate_groups=d['candidate_groups'],entry_ids=m['candidate_entry_ids'],machine_group=d['selected_group'],
                native_annotations=[a for a in b['native_annotations'] if a.get('target_id')==m['id']],
                patterns=m['patterns'],support=support,evidence=[example(eid) for eid in sorted(eids)],
                evidence_documents=len(docids),families=sorted(fams),
                training_occurrences=len(train[key]),training_examples=[example(eid) for eid in train[key][:6]],
                training_examples_total=len(train[key])))
    # Curated strata; order fixed by source identity, favour fuller sentences for readability.
    specs=[('눈','NNG','selected'),('올리','VV','selected'),('수','NNB','selected'),
           ('맛','NNG','unmatched'),('먹','VV','unmatched'),('들어가','VV','unmatched'),
           ('하','XSV','unseen'),('들','XSN','unseen'),('새우','NNG','unseen'),('네','IC','unseen')]
    starter=[]
    for lemma,pos,reason in specs:
        pool=[c for c in cases if (c['lemma'],c['pos'],c['reason'])==(lemma,pos,reason)]
        assert pool, (lemma,pos,reason)
        pool.sort(key=lambda c:(not 15<=len(sentences[c['sentence']]['form'])<=140,-len(c['families']),c['sentence'],c['target_id']))
        starter.append(pool[0]['id'])
    assert len(cases)==1499 and len({c['id'] for c in cases})==len(cases)
    counts=Counter(c['reason'] for c in cases)
    assert counts=={'selected':184,'unseen':1047,'unmatched':268}
    buckets=Counter((c['lemma'],c['pos'],c['reason']) for c in cases)
    for c in cases:c['similar_count']=buckets[(c['lemma'],c['pos'],c['reason'])]
    # Keep the original 1,499 cases and candidate numbers stable across revisions.
    comparison_root=REPO/'outputs/pilots/homonym_morphology_20260906'
    morphology_summary=None
    if (comparison_root/'SUMMARY.json').exists():
        morphology_summary=read(comparison_root/'SUMMARY.json')
        assert morphology_summary['source_receipt_sha256']==sha(ROOT/'FINAL_RECEIPT.json')
        assert sha(comparison_root/'COMPARISON.json')==morphology_summary['files']['COMPARISON.json']
        for filename,expected in morphology_summary['code_sha256'].items():
            assert sha(REPO/'scripts/python'/filename)==expected, 'stale morphology comparison: '+filename
        current={r['target_id']:r for r in read(comparison_root/'COMPARISON.json')['rows']}
        for c in cases:
            c['current_analysis']=current[c['target_id']]
        morphology_summary={k:morphology_summary[k] for k in (
            'version','original_multiple_count','original_multiple_selected_before','original_multiple_selected_after',
            'original_multiple_methods','accuracy_established')}
    ledger=OUT/'judgments.jsonl'
    events=[json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines() if line.strip()] if ledger.exists() else []
    ids={c['id'] for c in cases}
    assert all(e['case_id'] in ids for e in events)
    data=dict(schema='homonym_conversation_review.v1',source_receipt_sha256=sha(ROOT/'FINAL_RECEIPT.json'),
        generated_at=datetime.now(timezone.utc).isoformat(),starter=starter,cases=cases,
        sentences=sentences,documents=documents,entries={str(e):lexical[e] for e in sorted(used_entries)},
        reasons=REASONS,events=events,counts=dict(counts),family_counts=dict(family_counts),
        morphology_summary=morphology_summary,
        shortlist_policy='Purposive contrasting examples, not representative accuracy sample; no automatic propagation.')
    write(OUT/'review_data.json',js(data)+'\n')
    write(OUT/'judgments_view.json',js(dict(schema=data['schema'],source_receipt_sha256=data['source_receipt_sha256'],events=events))+'\n')
    write(OUT/'index.html',TEMPLATE.read_text(encoding='utf-8').replace('__REVIEW_DATA__',js(data)))
    if not ledger.exists():ledger.write_text('',encoding='utf-8')
    manifest=dict(schema='homonym_review_manifest.v1',pilot_receipt_sha256=sha(ROOT/'FINAL_RECEIPT.json'),
        input_sha256={n:receipt['files'][n] for n in names},cases=len(cases),starter=starter,counts=dict(counts),
        files={n:sha(OUT/n) for n in ('index.html','review_data.json','judgments.jsonl','judgments_view.json')},
        generator_sha256=sha(Path(__file__)),template_sha256=sha(TEMPLATE),internal_research_only=True)
    if morphology_summary:
        manifest['comparison_summary_sha256']=sha(comparison_root/'SUMMARY.json')
    write(OUT/'MANIFEST.json',js(manifest)+'\n')
    print(json.dumps(dict(output=str(OUT/'index.html'),cases=len(cases),starter=starter,counts=dict(counts),events=len(events)),ensure_ascii=True))

def record(p):
    """Record a user's explicit conversation judgment, never a machine inference."""
    data=read(OUT/'review_data.json'); req=read(p)
    c=next(c for c in data['cases'] if c['id']==req['case_id'])
    assert req['status'] in ('chosen','hold','context_needed','segmentation_review','reopened','noted')
    assert isinstance(req['user_quote'],str) and req['user_quote'].strip()
    assert isinstance(req.get('note',''),str)
    group=req.get('group')
    assert (type(group) is int and group in c['candidate_groups']) if req['status']=='chosen' else group is None
    ledger=OUT/'judgments.jsonl'
    # Windows exclusive writer lock; replay retains all revisions and original wording.
    import msvcrt
    with (OUT/'JUDGMENTS.guard').open('a+b') as guard:
        if guard.tell()==0:guard.write(b'0');guard.flush()
        guard.seek(0);msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
        try:
            rows=[json.loads(v) for v in ledger.read_text(encoding='utf-8').splitlines() if v.strip()]
            event=dict(schema='homonym_user_judgment.v1',case_id=c['id'],target_id=c['target_id'],
                event_id=len(rows)+1,recorded_at=datetime.now(timezone.utc).isoformat(),
                status=req['status'],group=group,user_quote=req['user_quote'],note=req.get('note',''),
                scope='this_occurrence_only',actor='user_via_conversation',
                source_receipt_sha256=data['source_receipt_sha256'])
            with ledger.open('a',encoding='utf-8',newline='\n') as f:
                f.write(json.dumps(event,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        finally:
            guard.seek(0);msvcrt.locking(guard.fileno(),msvcrt.LK_UNLCK,1)
    build()

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--record',type=Path,help='UTF-8 JSON containing an explicit user judgment')
    args=ap.parse_args()
    record(args.record) if args.record else build()
