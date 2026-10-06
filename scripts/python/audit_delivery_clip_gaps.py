"""Resumeable missing-clip accounting from existing link/native JSON receipts.

Does not query the source drive, scan audio trees, or rehash audio/large ledgers.
"""
import argparse
from collections import Counter
from contextlib import closing
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import update_delivery_revision as io


def bounded(path,limit=32*1024*1024):
    with path.open('rb') as f:raw=f.read(limit+1)
    if len(raw)>limit:raise ValueError('Document size bound exceeded')
    return raw


def run(package,out):
    import msvcrt
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:return work(package,out)
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def work(package,out):
    package=Path(package).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    source=package/'metadata/semantic_links/FINAL.json';raw=bounded(source)
    final=json.loads(raw);binding=hashlib.sha256(raw).hexdigest()
    contract=dict(schema='clip_gap_accounting.v1',runner_sha256=io.sha(Path(__file__)),semantic_final_sha256=binding,
                  expected_missing=final['counts']['modu_clip_not_in_declared_copy_scope'])
    cp=out/'CONTRACT.json'
    if cp.exists() and io.read(cp)!=contract:raise ValueError('Frozen gap accounting contract changed')
    io.save(cp,contract)
    with closing(sqlite3.connect(out/'ACCOUNTING.sqlite')) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Gap accounting ledger damaged')
        db.execute('CREATE TABLE IF NOT EXISTS documents(path TEXT PRIMARY KEY, utterances INTEGER)')
        db.execute('CREATE TABLE IF NOT EXISTS gaps(uid TEXT PRIMARY KEY, payload TEXT)')
        done={x[0] for x in db.execute('SELECT path FROM documents')}
        items=[x for x in final['receipts'] if x['path'].startswith('documents/modu/')]
        for i,item in enumerate(items,1):
            rel=item['path']
            if rel in done:continue
            rp=io.safe(package/'metadata/semantic_links',rel);rr=bounded(rp)
            if hashlib.sha256(rr).hexdigest()!=item['sha256']:raise ValueError('Link receipt changed')
            receipt=json.loads(rr);p=rp.with_name(rp.name.removesuffix('.receipt.json'));compressed=bounded(p)
            if hashlib.sha256(compressed).hexdigest()!=receipt['sha256']:raise ValueError('Stored link document changed')
            # Decompression size is bounded independently of the compressed file.
            import io as stream_io
            with gzip.GzipFile(fileobj=stream_io.BytesIO(compressed)) as f:raw_doc=f.read(32*1024*1024+1)
            if len(raw_doc)>32*1024*1024:raise ValueError('Expanded link document size bound exceeded')
            doc=json.loads(raw_doc);missing=[x for x in doc['utterances'] if x['clip_status']=='not_in_declared_copy_scope']
            if missing:
                ref=doc['source_discourse'];native_raw=bounded(io.safe(package,ref['path']))
                if hashlib.sha256(native_raw).hexdigest()!=ref['sha256']:raise ValueError('Native source changed')
                native=json.loads(native_raw);byid={u['utterance_id']:u for u in native['utterances']}
                if len(byid)!=len(native['utterances']):raise ValueError('Duplicate native utterance')
                for row in missing:
                    u=byid[row['utterance_id']]
                    if u['turn_order']!=row['turn_order'] or row.get('clip') is not None:raise ValueError('Missing clip identity differs')
                    value=dict(utterance_id=row['utterance_id'],year=Path(rel).parts[2],discourse_id=doc['discourse_id'],
                        source_file=doc['source_file'],source_json=ref['path'],source_json_sha256=ref['sha256'],
                        turn_order=row['turn_order'],alignment_status=row['alignment_status'],
                        analysis_status=u['analysis']['status'],original_text_empty=not (u['original'].get('form') or '').strip(),
                        clip_status=row['clip_status'],source_pcm_presence='not_checked',
                        explanation='Absent from frozen declared WAV copy/link scope; not proof source PCM absent')
                    encoded=json.dumps(value,ensure_ascii=False,separators=(',',':'))
                    previous=db.execute('SELECT payload FROM gaps WHERE uid=?',(value['utterance_id'],)).fetchone()
                    if previous and previous[0]!=encoded:raise ValueError('Conflicting missing clip evidence')
                    db.execute('INSERT OR IGNORE INTO gaps VALUES(?,?)',(value['utterance_id'],encoded))
            db.execute('INSERT INTO documents VALUES(?,?)',(rel,len(doc['utterances'])))
            if i%64==0:
                db.commit();io.save(out/'STATE.json',dict(status='running',pid=os.getpid(),updated_at=io.now(),documents=i,total_documents=len(items),phase='stored_link_gap_accounting'))
        db.commit();counts=Counter();empty=0
        for payload, in db.execute('SELECT payload FROM gaps ORDER BY uid'):
            x=json.loads(payload);counts[x['year']+'|'+x['analysis_status']+'|'+x['alignment_status']]+=1;empty+=x['original_text_empty']
        total=db.execute('SELECT count(*) FROM gaps').fetchone()[0]
        documents,utterances=db.execute('SELECT count(*),sum(utterances) FROM documents').fetchone()
        if total!=contract['expected_missing'] or documents!=final['counts']['modu_documents'] or utterances!=final['counts']['modu_utterances']:raise ValueError('Gap/full document accounting differs')
        listing=out/'MISSING_CLIPS.jsonl'
        with listing.open('w',encoding='utf-8') as f:
            for payload, in db.execute('SELECT payload FROM gaps ORDER BY uid'):f.write(payload+'\n')
    if io.sha(source)!=binding:raise ValueError('Semantic completion receipt changed during accounting')
    result=dict(status='declared_clip_gap_accounting_complete_source_presence_unverified',documents=documents,utterances=utterances,
        missing_clips=total,missing_empty_text=empty,counts=dict(counts),semantic_final_sha256=binding,
        listing_sha256=io.sha(listing),source_pcm_presence_verified=False,source_drive_accessed=False,
        audio_rehashed=False,api_calls=0,source_modified=False,delivery_complete=False)
    io.save(out/'FINAL.json',result);io.save(out/'STATE.json',dict(status=result['status'],updated_at=io.now(),pid=os.getpid(),missing_clips=total));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:print(json.dumps(run(a.package,a.output),ensure_ascii=True))
    except Exception as e:
        io.save(a.output/'ERROR.json',dict(status='error',pid=os.getpid(),updated_at=io.now(),error=str(e)));raise
