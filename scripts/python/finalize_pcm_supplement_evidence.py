"""Wait for immutable PCM supplement receipt, then archive explicit small evidence.

No H access, bulk ledger scan, full package rehash or claim of delivery completion.
"""
import argparse, hashlib, json, os, shutil, time
from pathlib import Path
from datetime import datetime, timezone

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):h.update(b)
    return h.hexdigest()

def save(p,v):
    p=Path(p);t=p.with_suffix('.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(t,p)

def now():return datetime.now(timezone.utc).isoformat()

def validate_overlay(rows, receipts):
    if len(rows)!=2995 or len(receipts)!=1559 or len({r['utterance_id'] for r in rows})!=2995:
        raise ValueError('Unexpected scope/duplicate identity')
    by_id={r['utterance_id']:r for r in receipts}
    if len(by_id)!=1559:raise ValueError('Duplicate copy receipt')
    matched=0
    for row in rows:
        record=row['pcm_supplement']
        if row['global_source_absence_established'] or row['source_pcm_absence_established']:
            raise ValueError('Unjustified source absence assertion')
        if record is None:
            if row['utterance_id'] in by_id:raise ValueError('Missing supplement link')
            continue
        if record!=by_id.get(row['utterance_id']):raise ValueError('Receipt/link mismatch')
        path=Path(record['relative_pcm_path'])
        if path.is_absolute() or '..' in path.parts or path.parts[0]!='audio_originals_supplement_v1':
            raise ValueError('Unsafe relative audio link')
        if record['source_sha256']!=record['destination_sha256'] or not record['independently_reopened_destination']:
            raise ValueError('Independent destination verification missing')
        matched+=1
    if matched!=1559:raise ValueError('Supplement link count mismatch')

def run(plan_path):
    p=Path(plan_path);plan=json.loads(p.read_text(encoding='utf-8-sig'));out=Path(plan['output']);out.mkdir(parents=True,exist_ok=True)
    import msvcrt
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        if sha(__file__)!=plan['runner_sha256']:raise ValueError('Runner hash mismatch')
        for item in plan['files']:
            if sha(item['source'])!=item['sha256']:raise ValueError('Pinned evidence changed: '+item['source'])
        if (out/'FINAL.json').exists():return
        dep=Path(plan['dependency'])
        save(out/'STATE.json',dict(status='waiting',updated_at=now(),pid=os.getpid(),dependency=str(dep)))
        while not (dep/'FINAL.json').exists():
            if (dep/'ERROR.json').exists():raise ValueError('PCM copier failed; preserve evidence')
            time.sleep(15)
        try:
            final=json.loads((dep/'FINAL.json').read_text(encoding='utf-8'))
            if final['status']!='confirmed_original_pcm_supplement_copied_sha_verified' or final['files']!=1559 or final['bytes']!=104185216:
                raise ValueError('Incomplete original PCM supplement')
            for name in ['CONTRACT.json','PROGRESS.json','ORIGINAL_AUDIO_LINKS.jsonl','GUIDE.md']:
                if sha(dep/name)!=final['evidence_sha256'][name]:raise ValueError('Changed PCM evidence '+name)
            rows=[json.loads(x) for x in (dep/'ORIGINAL_AUDIO_LINKS.jsonl').read_text(encoding='utf-8').splitlines()]
            receipts=json.loads((dep/'PROGRESS.json').read_text(encoding='utf-8'))
            validate_overlay(rows,receipts)
            save(out/'STATE.json',dict(status='running',phase='explicit_small_evidence_copy',updated_at=now(),pid=os.getpid()))
            items=list(plan['files'])+[
                dict(source=str(p),relative='PLAN.json',sha256=sha(p)),
                dict(source=__file__,relative='finalize_pcm_supplement_evidence.py',sha256=sha(__file__))]
            for name in ['CONTRACT.json','PROGRESS.json','ORIGINAL_AUDIO_LINKS.jsonl','GUIDE.md','FINAL.json']:
                items.append(dict(source=str(dep/name),relative='pcm_copy_completed/'+name,sha256=sha(dep/name)))
            if len(items)>200 or sum(Path(x['source']).stat().st_size for x in items)>64*1024*1024:raise ValueError('Small evidence bound')
            manifest=[]
            for item in items:
                rel=Path(item['relative'])
                if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe evidence path')
                target=out/'evidence'/rel;target.parent.mkdir(parents=True,exist_ok=True)
                if sha(item['source'])!=item['sha256']:raise ValueError('Changed evidence')
                if not target.exists():
                    with Path(item['source']).open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,65536)
                if sha(target)!=item['sha256']:raise ValueError('Evidence destination SHA mismatch')
                manifest.append(dict(relative_path=target.relative_to(out).as_posix(),sha256=item['sha256'],bytes=target.stat().st_size))
            save(out/'MANIFEST.json',manifest)
            save(out/'FINAL.json',dict(status='original_pcm_supplement_links_and_explicit_provenance_verified',completed_at=now(),
                 pcm_files=1559,pcm_bytes=104185216,unresolved_in_checked_roots=1436,
                 metadata_files=len(manifest),metadata_bytes=sum(x['bytes'] for x in manifest),
                 manifest_sha256=sha(out/'MANIFEST.json'),copy_final_sha256=sha(dep/'FINAL.json'),
                 no_source_absence_inference=True,full_audio_coverage_verified=False,delivery_complete=False,
                 next_step='Review official year-specific PCM scope and remaining missing identities before final acceptance'))
            save(out/'STATE.json',dict(status='completed',updated_at=now(),pid=os.getpid()))
        except Exception as exc:
            save(out/'ERROR.json',dict(error=str(exc),at=now(),retry_automatically=False));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);a=parser.parse_args();run(a.plan)
