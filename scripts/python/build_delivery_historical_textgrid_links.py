"""Index frozen old TextGrid receipts after semantic links; no audio or API work."""
import argparse
from collections import Counter
from contextlib import closing
import csv
import gzip
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import sqlite3
import time
import traceback
import build_delivery_semantic_links as common

STORAGE = {'external_d': 'old_textgrids_primary', 'local_c': 'old_textgrids_spill'}


def digest_rows(rows):
    h=hashlib.sha256()
    for row in rows:
        h.update((json.dumps(list(row),ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'))
    return h.hexdigest()


def verified_rows(pkg, semantic, receipt, inventory):
    seen=set()
    for ordinal,row in enumerate(inventory):
        uid=row['utt_id']
        if not uid or uid in seen: raise ValueError('Duplicate or empty historical utterance ID')
        seen.add(uid)
        native=semantic.execute("SELECT discourse_id FROM utterances WHERE corpus='modu' AND utterance_id=?",(uid,)).fetchone()
        if not native: raise ValueError('Historical utterance missing from native index: '+uid)
        status=row['status']; ref=None
        if status=='derived':
            if row['storage_id'] not in STORAGE: raise ValueError('Unknown historical storage')
            ref=pkg.ref(STORAGE[row['storage_id']],row['derived_relative'],row['sha256'])
            if int(row['bytes'])!=ref['bytes']: raise ValueError('Historical TextGrid size mismatch')
        elif status!='no_mfa_alignment': raise ValueError('Unknown historical alignment status')
        yield (uid,receipt['source_file'],ordinal,native[0],status,json.dumps(ref,ensure_ascii=False,separators=(',',':')))


def build(pkg, out, semantic_path, sample_limit=0):
    out.mkdir(parents=True,exist_ok=True)
    index_ref=pkg.ref('old_textgrids_primary','SHARD_RECEIPT_INVENTORY.tsv')
    index_path=pkg.path(index_ref['path'])
    if common.sha(index_path)!=index_ref['sha256']: raise ValueError('Historical shard index changed')
    totals=Counter(); receipts=[]; source_keys=set()
    with closing(sqlite3.connect(semantic_path.resolve().as_uri()+'?mode=ro',uri=True)) as semantic, closing(sqlite3.connect(out/'HISTORICAL_TEXTGRID_INDEX.sqlite')) as db:
        db.execute('CREATE TABLE IF NOT EXISTS links(utterance_id TEXT PRIMARY KEY,source_file TEXT,ordinal INTEGER,discourse_id TEXT,status TEXT,reference_json TEXT) WITHOUT ROWID')
        db.execute('CREATE INDEX IF NOT EXISTS source_rows ON links(source_file,ordinal)')
        db.execute('CREATE TABLE IF NOT EXISTS shards(source_file TEXT PRIMARY KEY,source_sha256 TEXT,inventory_sha256 TEXT,row_digest TEXT,rows INTEGER) WITHOUT ROWID')
        with index_path.open(encoding='utf-8-sig',newline='') as stream:
            for number,fields in enumerate(csv.reader(stream,delimiter='\t'),1):
                if sample_limit and number>sample_limit: break
                if (out/'STOP').exists(): raise InterruptedError('STOP at shard boundary')
                if len(fields)!=5: raise ValueError('Malformed historical shard index')
                key,old_sha,storage,relative,expected=fields
                if storage not in STORAGE: raise ValueError('Unknown shard storage')
                # Consolidated shard receipts/inventories are in primary; storage selects only TG payload.
                ref=pkg.ref('old_textgrids_primary',relative,expected); receipt=pkg.load(ref)
                if receipt['bareun_receipt_relative']!=key or receipt['bareun_receipt_sha256']!=old_sha or receipt['status']!='completed':
                    raise ValueError('Historical source receipt mismatch')
                source=receipt['source_file']
                if source in source_keys: raise ValueError('Duplicate source shard')
                source_keys.add(source)
                invref=pkg.ref('old_textgrids_primary',receipt['output_inventory_relative'],receipt['output_inventory_sha256'])
                invpath=pkg.path(invref['path'])
                if common.sha(invpath)!=invref['sha256']: raise ValueError('Historical output inventory changed')
                prior=db.execute('SELECT source_sha256,inventory_sha256,row_digest,rows FROM shards WHERE source_file=?',(source,)).fetchone()
                if prior:
                    stored=list(db.execute('SELECT * FROM links WHERE source_file=? ORDER BY ordinal',(source,)))
                    if prior!=(expected,invref['sha256'],digest_rows(stored),len(stored)):
                        raise ValueError('Historical resume binding or index changed')
                    counts=Counter(x[4] for x in stored)
                else:
                    with gzip.open(invpath,'rt',encoding='utf-8-sig',newline='') as f:
                        rows=list(verified_rows(pkg,semantic,receipt,csv.DictReader(f)))
                    counts=Counter(x[4] for x in rows)
                    if len(rows)!=receipt['counts']['utterances'] or any(counts[k]!=receipt['counts'][k] for k in ['derived','no_mfa_alignment']):
                        raise ValueError('Historical receipt counts mismatch')
                    with db:
                        db.executemany('INSERT INTO links VALUES(?,?,?,?,?,?)',rows)
                        db.execute('INSERT INTO shards VALUES(?,?,?,?,?)',(source,expected,invref['sha256'],digest_rows(rows),len(rows)))
                    stored=list(db.execute('SELECT * FROM links WHERE source_file=? ORDER BY ordinal',(source,)))
                    if digest_rows(stored)!=digest_rows(rows): raise ValueError('Index readback mismatch')
                totals.update(counts);totals['utterances']+=len(stored);totals['shards']+=1
                rp=out/'receipts'/common.relative(key)
                common.save(rp,dict(status='historical_textgrid_links_verified',source_file=source,
                    original_completed_at=receipt.get('completed_at'),source_receipt=ref,output_inventory=invref,
                    rows=len(stored),row_digest=digest_rows(stored),counts=dict(counts),
                    version='historical_20260829',morphology='Historical whole-utterance morph_analysis_utt; not current 3.2 or semantic supplement'))
                receipts.append(dict(path=rp.relative_to(out).as_posix(),sha256=common.sha(rp)))
                common.save(out/'STATE.json',dict(status='running',phase='historical_textgrid_links',pid=os.getpid(),updated_at=common.now(),counts=dict(totals)))
        if db.execute('SELECT count(*) FROM links').fetchone()[0]!=totals['utterances'] or db.execute('SELECT count(*) FROM shards').fetchone()[0]!=totals['shards']:
            raise ValueError('Unexpected retained index rows')
        native_count=semantic.execute("SELECT count(*) FROM utterances WHERE corpus='modu'").fetchone()[0]
        if not sample_limit and (totals['shards'],totals['utterances'],totals['derived'],totals['no_mfa_alignment'],native_count)!=(17156,5103356,4286046,817310,5157997):
            raise ValueError('Historical full-scope counts mismatch')
    final=dict(status='historical_textgrid_links_complete',sample=bool(sample_limit),completed_at=common.now(),
        counts=dict(totals),native_utterances=native_count,without_historical_analysis=native_count-totals['utterances'],
        receipts=receipts,index_sha256=common.sha(out/'HISTORICAL_TEXTGRID_INDEX.sqlite'),
        source_index=index_ref,references_base='package_root',delivery_complete=False,
        verification='Old receipt SHA and copied ledger binding; payload SHA reuse from independent copy audit, not a new payload rehash')
    common.save(out/'FINAL.json',final);common.save(out/'STATE.json',final)
    return final


def run(root,out,wait):
    root=root.resolve();out=out.resolve()
    if not out.is_relative_to(root/'metadata') or out==root/'metadata': raise ValueError('Output must be a new metadata subdirectory')
    out.mkdir(parents=True,exist_ok=True)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            dependency=root/'metadata/semantic_links'
            contract=dict(schema='historical_textgrid_links.v1',runner_sha256=common.sha(Path(__file__)),
                helper_sha256=common.sha(Path(common.__file__)),copy_contract_sha256=common.sha(root/'CONTRACT.json'),
                semantic_contract_sha256=common.sha(dependency/'CONTRACT.json'))
            if (out/'CONTRACT.json').exists():
                if common.read(out/'CONTRACT.json')!=contract: raise ValueError('Frozen contract changed')
            else: common.save(out/'CONTRACT.json',contract)
            while not (dependency/'FINAL.json').exists():
                for dep in [root,dependency]:
                    state=common.read(dep/'STATE.json')
                    if state['status'] in ['error','stopped']: raise RuntimeError('Dependency stopped: '+str(dep))
                if not wait: raise RuntimeError('Semantic FINAL required')
                if (out/'STOP').exists(): raise InterruptedError('STOP while waiting')
                common.save(out/'STATE.json',dict(status='waiting_for_semantic_links',pid=os.getpid(),updated_at=common.now()))
                time.sleep(300)
            semantic_final=common.read(dependency/'FINAL.json');copy_final=common.read(root/'COPY_FINAL.json')
            if semantic_final.get('sample') or semantic_final['status']!='semantic_links_complete_with_explicit_scope_gaps': raise ValueError('Full semantic completion required')
            if copy_final['status']!='declared_scope_copied_sha_verified': raise ValueError('Copy completion required')
            if common.sha(root/'COPY_LEDGER.sqlite')!=copy_final['ledger_sha256'] or common.sha(dependency/'UTTERANCE_INDEX.sqlite')!=semantic_final['index_sha256']:
                raise ValueError('Dependency index hash mismatch')
            common.save(out/'DEPENDENCIES.json',dict(copy_final_sha256=common.sha(root/'COPY_FINAL.json'),semantic_final_sha256=common.sha(dependency/'FINAL.json')))
            pkg=common.Package(root)
            try: build(pkg,out,dependency/'UTTERANCE_INDEX.sqlite')
            finally: pkg.db.close()
        except BaseException as exc:
            error=dict(status='stopped' if isinstance(exc,InterruptedError) else 'error',pid=os.getpid(),updated_at=common.now(),error=str(exc),traceback=traceback.format_exc())
            common.save(out/'ERROR.json',error);common.save(out/'STATE.json',error);raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--wait',action='store_true')
    a=p.parse_args();run(a.package,a.output,a.wait)
