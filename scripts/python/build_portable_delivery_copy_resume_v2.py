"""Reuse committed independent-SHA receipts; metadata audit is not a fresh full hash."""
import argparse, hashlib, importlib.util, json, os, re, sqlite3, time, traceback
from pathlib import Path
from contextlib import closing
import msvcrt

BLOCK=256*1024
def stamp():
    from datetime import datetime,timezone
    return datetime.now(timezone.utc).isoformat()
def sha(p):
    h=hashlib.sha256();buf=bytearray(BLOCK)
    with Path(p).open('rb') as f:
        while (n:=f.readinto(buf)):h.update(memoryview(buf)[:n])
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):
    p=Path(p);tmp=p.with_suffix(p.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    tmp.replace(p)
def load_legacy(p):
    spec=importlib.util.spec_from_file_location('frozen_delivery_copy_v1',p)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
def checked_stat(p):
    s=p.stat()
    if p.is_symlink() or (getattr(s,'st_file_attributes',0)&0x400):raise ValueError('Reparse payload')
    return s
def copy_stream(old,src,dest,size,mtime,expected):
    src=old.io_path(src);dest=old.io_path(dest)
    if old.stat_key(src)!=(size,mtime):raise ValueError('Source changed since frozen inventory')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        if checked_stat(dest).st_size!=size or os.path.samefile(src,dest):raise ValueError('Existing destination differs or aliases source')
        value=sha(src)
        if sha(dest)!=value or (expected and value!=expected):raise ValueError('Existing SHA differs')
    else:
        partial=dest.with_name(dest.name+'.delivery-partial-v2')
        # Preserve earlier interrupted bytes, even those created by this version.
        if partial.exists():
            partial=dest.with_name(dest.name+'.delivery-partial-v2-'+str(time.time_ns()))
        h=hashlib.sha256();buf=bytearray(BLOCK)
        with src.open('rb') as f,partial.open('xb') as g:
            while (n:=f.readinto(buf)):
                block=memoryview(buf)[:n];h.update(block);g.write(block)
            g.flush();os.fsync(g.fileno())
        value=h.hexdigest()
        if old.stat_key(src)!=(size,mtime) or partial.stat().st_size!=size or sha(partial)!=value or (expected and value!=expected):raise ValueError('Independent SHA validation failed')
        if dest.exists():raise ValueError('Destination appeared')
        partial.rename(dest)
    if old.stat_key(src)!=(size,mtime):raise ValueError('Source changed during copy')
    return value
def reuse(old,src,dest,size,mtime,expected,cutoff_ns,known_dest_mtime=None):
    if not expected or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Completed receipt lacks SHA')
    src=old.io_path(src);dest=old.io_path(dest)
    a=checked_stat(src)
    if (a.st_size,a.st_mtime_ns)!=(size,mtime):raise ValueError('Source metadata changed')
    if not dest.exists():return False
    b=checked_stat(dest)
    if b.st_size!=size or os.path.samefile(src,dest):raise ValueError('Completed destination differs/aliases; preserve for diagnosis')
    changed=(b.st_mtime_ns!=known_dest_mtime) if known_dest_mtime is not None else b.st_mtime_ns>cutoff_ns
    if changed:
        if sha(src)!=expected or sha(dest)!=expected:raise ValueError('Changed destination SHA differs')
    return True
def run(args):
    root=args.output.resolve();policy=read(args.policy)
    if sha(args.policy)!=args.policy_sha256:raise ValueError('Policy SHA changed')
    old=load_legacy(Path(policy['legacy_runner']))
    if sha(policy['legacy_runner'])!=policy['legacy_runner_sha256']:raise ValueError('Legacy code changed')
    wrapper=load_legacy(Path(policy['shared_helper']))
    if sha(policy['shared_helper'])!=policy['shared_helper_sha256']:raise ValueError('Control helper changed')
    wrapper.install([root/'STATE.json',root/'ERROR.json'])
    if str(root)!=str(Path(policy['package']).resolve()):raise ValueError('Package differs')
    with (root/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            for name,h in policy['bindings'].items():
                if sha(root/name)!=h:raise ValueError('Frozen binding changed: '+name)
            for rec in policy['archive_bindings']:
                if sha(root/rec['path'])!=rec['sha256']:raise ValueError('Preserved provenance changed')
            cp=root/'COPY_RESUME_V2_CONTRACT.json'
            contract=dict(schema='portable_copy_resume.v2',policy_sha256=args.policy_sha256,runner_sha256=sha(Path(__file__)))
            if cp.exists() and read(cp)!=contract:raise ValueError('Resume contract changed')
            if not cp.exists():save(cp,contract)
            config=read(root/'CONTRACT.json')['config'];old.validate_config(config,root)
            inv=read(root/'INVENTORY.json')
            save(root/'STATE.json',dict(status='running',phase='resume_ledger_validation',pid=os.getpid(),updated_at=stamp(),progress_scope='reuse_committed_sha_with_metadata_audit'))
            with closing(sqlite3.connect(root/'COPY_LEDGER.sqlite')) as db:
                db.execute('PRAGMA cache_size=-2048')
                if db.execute('PRAGMA quick_check').fetchone()!=('ok',):raise ValueError('Ledger quick_check failed')
                db.execute('CREATE TABLE IF NOT EXISTS resume_v2_dest_stats (id INTEGER PRIMARY KEY,mtime_ns INTEGER NOT NULL)')
                total=db.execute('SELECT count(*),coalesce(sum(bytes),0),sum(CASE WHEN copied=1 THEN 1 ELSE 0 END),coalesce(sum(CASE WHEN copied=1 THEN bytes ELSE 0 END),0) FROM files').fetchone()
                if total[:2]!=(inv['files'],inv['bytes']):raise ValueError('Inventory/ledger totals differ')
                if db.execute('SELECT 1 FROM files WHERE copied NOT IN (0,1) OR bytes<0 LIMIT 1').fetchone():raise ValueError('Malformed ledger status')
                floor=config.get('free_floor_bytes',100*2**30)
                required=total[1]-total[3]+(total[0]-total[2])*4096+floor
                if __import__('shutil').disk_usage(root).free<required:raise ValueError('Capacity insufficient')
                done=0;amount=0;reused=0;fresh=0;last_state=0
                rows=db.execute('SELECT f.id,source,relative,bytes,f.mtime_ns,sha256,copied,s.mtime_ns FROM files f LEFT JOIN resume_v2_dest_stats s ON f.id=s.id ORDER BY f.id')
                for ident,source,relative,size,mtime,expected,copied,known_dest_mtime in rows:
                    if (root/'STOP').exists():raise InterruptedError('STOP at file boundary')
                    dest=old.safe_target(root,relative)
                    if copied and reuse(old,Path(source),dest,size,mtime,expected,policy['baseline_cutoff_ns'],known_dest_mtime):reused+=1
                    else:
                        if __import__('shutil').disk_usage(root).free<floor:raise ValueError('Capacity floor reached')
                        value=copy_stream(old,Path(source),dest,size,mtime,expected)
                        db.execute('UPDATE files SET copied=1,sha256=? WHERE id=?',(value,ident));fresh+=1
                        db.execute('INSERT OR REPLACE INTO resume_v2_dest_stats VALUES(?,?)',(ident,dest.stat().st_mtime_ns))
                    done+=1;amount+=size
                    if done%256==0:db.commit()
                    if time.monotonic()-last_state>=10:
                        save(root/'STATE.json',dict(status='running',phase='reuse_metadata_and_copy_pending',pid=os.getpid(),updated_at=stamp(),files=done,bytes=amount,total_files=total[0],total_bytes=total[1],retained_verified_files=total[2],retained_verified_bytes=total[3],reused_sha_records=reused,fresh_sha_files=fresh,fresh_full_rehash=False,progress_scope='metadata_audit_plus_pending_copy'))
                        last_state=time.monotonic()
                db.commit()
                if (done,amount)!=total[:2]:raise ValueError('Final count mismatch')
            evidence=dict(status='committed_sha_reuse_and_pending_copy_complete',at=stamp(),reused_sha_records=reused,fresh_sha_files=fresh,full_payload_rehash_performed=False,assumption='Previously verified committed files are retained unchanged; metadata checks cannot detect pre-baseline same-size modifications or silent corruption. New/changed-after-baseline/missing files receive independent SHA.',policy_sha256=args.policy_sha256,resume_contract_sha256=sha(cp),legacy_contract_sha256=sha(root/'CONTRACT.json'),delivery_complete=False)
            save(root/'COPY_REUSE_FINAL.json',evidence)
            final=dict(status='declared_scope_copied_sha_verified',completed_at=stamp(),files=done,bytes=amount,ledger_sha256=sha(root/'COPY_LEDGER.sqlite'),inventory_sha256=sha(root/'INVENTORY.json'),scope_gaps=config.get('scope_gaps',[]),delivery_complete=False,reuse_evidence_sha256=sha(root/'COPY_REUSE_FINAL.json'),full_payload_rehash_performed=False,remaining='Semantic links, guides, re-open queries and full delivery acceptance')
            save(root/'COPY_FINAL.json',final);save(root/'STATE.json',final)
        except BaseException as exc:
            save(root/'ERROR.json',dict(status='stopped' if isinstance(exc,InterruptedError) else 'error',pid=os.getpid(),updated_at=stamp(),error=str(exc),traceback=traceback.format_exc()))
            save(root/'STATE.json',read(root/'ERROR.json'));raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--policy',type=Path,required=True);p.add_argument('--policy-sha256',required=True);run(p.parse_args())
