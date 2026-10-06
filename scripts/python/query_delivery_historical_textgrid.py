"""Read one exact old TextGrid reference, keeping missing history distinct from no alignment."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from query_delivery_links import safe


def query(package, uid, verify_sha=False, index_relative='metadata/historical_textgrid_links/HISTORICAL_TEXTGRID_INDEX.sqlite'):
    index=safe(package,index_relative)
    with closing(sqlite3.connect(index.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        row=db.execute('SELECT l.utterance_id,l.source_file,l.ordinal,l.discourse_id,l.status,l.reference_json,s.source_sha256,s.inventory_sha256 FROM links l JOIN shards s USING(source_file) WHERE utterance_id=?',(uid,)).fetchone()
    if not row:
        with closing(sqlite3.connect((package/'metadata/semantic_links/UTTERANCE_INDEX.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
            known=db.execute("SELECT 1 FROM utterances WHERE corpus='modu' AND utterance_id=?",(uid,)).fetchone()
        if not known: raise ValueError('Unknown Modu utterance ID')
        return dict(utterance_id=uid,status='no_historical_analysis_record',textgrid=None,
                    meaning='Not present in old analyzed-utterance inventory; not a no-MFA alignment judgment')
    result=dict(zip(['utterance_id','source_file','historical_inventory_ordinal_zero_based','discourse_id','status','textgrid','source_receipt_sha256','source_inventory_sha256'],row))
    result['textgrid']=json.loads(result['textgrid'])
    if result['textgrid']:
        ref=result['textgrid'];p=safe(package,ref['path'])
        if p.stat().st_size!=ref['bytes']: raise ValueError('Historical TextGrid missing or size changed')
        if verify_sha:
            with p.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
            if actual!=ref['sha256']: raise ValueError('Historical TextGrid SHA mismatch')
    result.update(version='historical_20260829',references_base='package_root',
        morphology='Old whole-utterance layer; not the current analysis or meaning supplement',payload_sha_verified_now=verify_sha and bool(result['textgrid']))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--utterance-id',required=True);p.add_argument('--verify-sha',action='store_true');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=query(a.package,a.utterance_id,a.verify_sha)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
