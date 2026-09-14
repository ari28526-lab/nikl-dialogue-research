"""Reviewed continuation: serial deletion with bounded ledger and status batches.

The original runner and first archive remain immutable. An explicit migration records
the changed execution contract; source scope and first-shard membership are unchanged.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import sys
import time
import run_legacy_mfa_cleanup as m

WORKERS = 1
BATCH = 128
BASE_PREFLIGHT = m.preflight
BASE_ARCHIVE = m.archive_shard
OVERRIDE_NAME = 'serial_batched_delete_v2'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def fingerprint(path):
    s=path.stat()
    return [s.st_size,s.st_mtime_ns,s.st_dev,s.st_ino]


def delete_one(item):
    ident,rel,size,mtime=item;p=m.safe_relative(m.INPUT,rel)
    try:
        s=p.lstat()
        if not m.regular(s) or (s.st_size,s.st_mtime_ns)!=(size,mtime):return ident,rel,'held','changed'
        p.unlink();return ident,rel,'deleted',None
    except FileNotFoundError:return ident,rel,'absent',None
    except OSError as exc:return ident,rel,'held',str(exc)


def delete_shard(job,shard):
    db=job.db;row=db.execute('SELECT receipt,deleted FROM shards WHERE id=?',(shard,)).fetchone()
    if not row or json.loads(row[0])['status']!='verified':raise ValueError('unverified shard cannot be deleted')
    if row[1]:return
    total=json.loads(row[0])['inventory']['shard_files']
    before=db.execute('SELECT COUNT(*) FROM files WHERE shard=? AND result IS NOT NULL',(shard,)).fetchone()[0]
    parents=set();done=0;last_id=0;started=time.monotonic()
    while True:
        job.check()
        items=db.execute('SELECT id,rel,size,mtime FROM files WHERE shard=? AND result IS NULL AND id>? ORDER BY id LIMIT ?',
                         (shard,last_id,BATCH)).fetchall()
        if not items:break
        for _,rel,_,_ in items:
            parent=m.safe_relative(m.INPUT,rel).parent
            if parent not in parents:m.plain(parent);parents.add(parent)
        # Serial filesystem operations; commit and check status once per bounded batch.
        for ident,rel,result,error in map(delete_one,items):
            db.execute('UPDATE files SET result=? WHERE id=?',(result,ident))
            if error:job.issue('input',rel,error)
        db.commit();last_id=items[-1][0];done+=len(items)
        speed=done/max(time.monotonic()-started,.001)
        job.update(phase='input_verified_shard_cleanup',current_shard=shard,processed=before+done,total=total,
                   files_per_second=round(speed,2),eta_seconds=round((total-before-done)/max(speed,.001)),delete_workers=WORKERS)
    stats=dict(db.execute('SELECT result,COUNT(*) FROM files WHERE shard=? GROUP BY result',(shard,)).fetchall())
    db.execute('UPDATE shards SET deleted=1,stats=? WHERE id=?',(json.dumps(stats),shard));db.commit()


def preflight():
    plan=BASE_PREFLIGHT()
    plan['contract']['code_shas'][Path(__file__).name]=m.common.sha(Path(__file__))
    plan['contract']['execution_override']={'name':OVERRIDE_NAME,'delete_workers':WORKERS,'batch':BATCH}
    return plan


def archive(job,shard):
    if shard!=0:return BASE_ARCHIVE(job,shard)
    final=m.ARCHIVES/'legacy_mfa_000_of_064.tar.zst';path=final.with_suffix('.zst.receipt.json')
    if not path.exists():return BASE_ARCHIVE(job,shard)
    receipt=m.common.read(path)
    permitted={digest(job.state['contract']), *[v['from_contract_sha256'] for v in job.state.get('execution_migrations',[])]}
    if receipt['shard']!=0 or receipt['status']!='verified' or receipt['contract_sha256'] not in permitted:
        raise ValueError('first receipt is outside the reviewed migration')
    if m.common.sha(final)!=receipt['archive_sha256']:raise ValueError('first archive changed')
    db=job.db
    existing=db.execute('SELECT receipt FROM shards WHERE id=0').fetchone()
    if not existing or json.loads(existing[0])!=receipt:raise ValueError('stored first receipt differs from E receipt')
    return receipt


def migrate(plan):
    with m.common.exclusive_lock(m.WORK/'RUN.lock'):
        state=m.common.read(m.STATE)
        if state['contract']==plan['contract']:return
        if state['status'] not in ('paused','failed_preserved') or state.get('pid'):
            raise ValueError('migration requires a stopped runner')
        original=BASE_PREFLIGHT()['contract']
        if state['contract']!=original:raise ValueError('original contract no longer matches')
        db=m.connect()
        try:
            if db.execute('SELECT COUNT(*) FROM files WHERE shard>0').fetchone()[0] or db.execute("SELECT 1 FROM meta WHERE key='full_snapshot'").fetchone():
                raise ValueError('cannot change remaining partition after it has started')
            if db.execute('SELECT COUNT(*) FROM shards WHERE id<>0').fetchone()[0]:raise ValueError('later archive already exists')
            receipt=json.loads(db.execute('SELECT receipt FROM shards WHERE id=0').fetchone()[0])
            if receipt['contract_sha256']!=digest(original):raise ValueError('old first-shard receipt contract differs')
        finally:db.close()
        previous=m.WORK/'STATE_before_v2_20260910.json'
        if not previous.exists():m.common.save(previous,state)
        change={'from_contract_sha256':digest(original),'to_contract_sha256':digest(plan['contract']),
                'at':m.common.now(),'reason':'user approved brief review and applying measured cleanup improvement; first archive and original code preserved'}
        state.setdefault('execution_migrations',[]).append(change);state['contract']=plan['contract']
        m.common.save(m.STATE,state)


def main():
    if '--execute' in sys.argv:
        migrate(preflight())
    m.preflight=preflight;m.delete_input_shard=delete_shard;m.archive_shard=archive
    m.main()


if __name__=='__main__':main()
