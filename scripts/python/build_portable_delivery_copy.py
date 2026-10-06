"""Resumable independent copies of explicit source trees; never declares DELIVERY_FINAL."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import time
import traceback
import msvcrt
from contextlib import closing

def stamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def save(path, obj):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)

def sha(path):
    h=hashlib.sha256()
    with io_path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def io_path(path):
    """Use Windows extended paths for IO without changing manifest references."""
    path=Path(path)
    if os.name!='nt':return path
    value=os.path.abspath(path)
    if value.startswith('\\\\?\\'):return Path(value)
    if value.startswith('\\\\'):return Path('\\\\?\\UNC\\'+value[2:])
    return Path('\\\\?\\'+value)

def safe_target(root, relative):
    rel=PurePosixPath(relative)
    assert rel.parts and not rel.is_absolute() and all(p not in ('..','') and ':' not in p for p in rel.parts), 'Unsafe relative path'
    target=root.joinpath(*rel.parts)
    assert target.resolve().is_relative_to(root.resolve()), 'Destination escapes package'
    return target

def validate_config(config, out):
    sources=[];destinations=[];roles=set()
    assert config['schema']=='portable_delivery_copy.v1' and config['roots']
    for entry in config['roots']:
        assert entry['role'] not in roles;roles.add(entry['role'])
        source=Path(entry['source']).resolve()
        assert source.is_dir() and not source.is_junction() and not source.is_symlink()
        assert not out.resolve().is_relative_to(source) and not source.is_relative_to(out.resolve()), 'Source/output overlap'
        target=safe_target(out,entry['destination']).resolve()
        for prior in sources:assert not source.is_relative_to(prior) and not prior.is_relative_to(source),'Duplicate source scope'
        for prior in destinations:assert not target.is_relative_to(prior) and not prior.is_relative_to(target),'Overlapping destinations'
        sources.append(source);destinations.append(target)

def files(root, exclude_names=(), exclude_prefixes=(), exclude_suffixes=()):
    # Do not follow reparse points into unrelated source trees.
    for current,dirs,names in os.walk(root,followlinks=False):
        dirs[:]=sorted(n for n in dirs if n not in exclude_names and not any(n.startswith(x) for x in exclude_prefixes))
        names=sorted(n for n in names if n not in exclude_names and not any(n.startswith(x) for x in exclude_prefixes) and not any(n.endswith(x) for x in exclude_suffixes))
        for name in dirs:
            p=Path(current)/name
            assert not p.is_symlink() and not p.is_junction(),'Source directory is a reparse point'
        for name in names:
            p=Path(current)/name
            assert not p.is_symlink() and p.is_file(),'Unexpected source file type'
            yield p

def stat_key(path):
    s=path.stat();return (s.st_size,s.st_mtime_ns)

def copy_one(source, dest, size, mtime, expected=None):
    source=io_path(source);dest=io_path(dest)
    assert stat_key(source)==(size,mtime),'Source changed since inventory'
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        assert not dest.is_symlink() and stat_key(dest)[0]==size,'Existing destination differs'
        assert not os.path.samefile(source,dest),'Destination is not an independent copy'
        value=sha(source)
        assert sha(dest)==value and (expected is None or value==expected),'Existing destination SHA mismatch'
    else:
        partial=dest.with_name(dest.name+'.delivery-partial')
        assert not partial.is_symlink()
        digest=hashlib.sha256()
        with source.open('rb') as src,partial.open('wb') as dst:
            for block in iter(lambda:src.read(4*1024*1024),b''):
                digest.update(block);dst.write(block)
            dst.flush();os.fsync(dst.fileno())
        value=digest.hexdigest()
        assert stat_key(source)==(size,mtime) and partial.stat().st_size==size
        assert sha(partial)==value,'Independent destination SHA mismatch'
        assert expected is None or value==expected
        assert not dest.exists(),'Destination appeared while copying'
        partial.rename(dest)
    assert stat_key(source)==(size,mtime),'Source changed during verification'
    return value

def inventory(config,out,db):
    db.execute('CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, role TEXT, source TEXT UNIQUE, relative TEXT UNIQUE COLLATE NOCASE, bytes INTEGER, mtime_ns INTEGER, sha256 TEXT, copied INTEGER DEFAULT 0)')
    counts={}
    for entry in config['roots']:
        source=Path(entry['source']);count=0;size=0
        for path in files(source,config.get('exclude_names',[]),config.get('exclude_prefixes',[]),config.get('exclude_suffixes',[])):
            if (out/'STOP').exists():raise InterruptedError('STOP during inventory')
            rel=(PurePosixPath(entry['destination'])/path.relative_to(source).as_posix()).as_posix()
            safe_target(out,rel);key=stat_key(path);count+=1;size+=key[0]
            prior=db.execute('SELECT relative,bytes,mtime_ns FROM files WHERE source=?',(str(path),)).fetchone()
            if prior:assert prior==(rel,*key),'Source changed on inventory resume'
            else:db.execute('INSERT INTO files(role,source,relative,bytes,mtime_ns) VALUES(?,?,?,?,?)',(entry['role'],str(path),rel,*key))
            if count%10000==0:
                db.commit();save(out/'STATE.json',dict(status='running',phase='source_inventory',pid=os.getpid(),updated_at=stamp(),role=entry['role'],files=count,bytes=size))
        db.commit();counts[entry['role']]=dict(files=count,bytes=size)
        actual=db.execute('SELECT count(*),coalesce(sum(bytes),0) FROM files WHERE role=?',(entry['role'],)).fetchone()
        assert actual==(count,size),'Source inventory lost files'
    value=dict(status='source_inventory_complete',created_at=stamp(),counts=counts,
        files=sum(x['files'] for x in counts.values()),bytes=sum(x['bytes'] for x in counts.values()),
        scope_gaps=config.get('scope_gaps',[]),delivery_complete=False)
    save(out/'INVENTORY.json',value);return value

def run(config_path,out,do_copy=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            config=read(config_path)
            contract=dict(config=config,config_sha256=sha(config_path),runner_sha256=sha(Path(__file__)))
            if (out/'CONTRACT.json').exists():assert read(out/'CONTRACT.json')==contract
            else:save(out/'CONTRACT.json',contract)
            dep=config.get('wait_for')
            while dep and not (Path(dep)/'FINAL.json').exists():
                if (out/'STOP').exists():raise InterruptedError('STOP while waiting')
                state=read(Path(dep)/'STATE.json')
                assert state['status'] not in ('error','stopped'),'Dependency failed'
                save(out/'STATE.json',dict(status='waiting_for_supplement_parquet',pid=os.getpid(),updated_at=stamp(),dependency_status=state['status']))
                time.sleep(300)
            if dep:
                final=read(Path(dep)/'FINAL.json')
                assert final['status']=='supplement_parquet_complete' and final['sample'] is False
                for rec in final['receipts']:assert sha(Path(dep)/rec['path'])==rec['sha256']
            validate_config(config,out)
            with closing(sqlite3.connect(out/'COPY_LEDGER.sqlite')) as db:
                inv=inventory(config,out,db) if not (out/'INVENTORY.json').exists() else read(out/'INVENTORY.json')
                if not do_copy:return inv
                remaining=db.execute('SELECT coalesce(sum(bytes),0),count(*) FROM files WHERE copied=0').fetchone()
                floor=config.get('free_floor_bytes',100*2**30)
                # Reserve cluster allocation for millions of tiny files plus a safety floor.
                required=remaining[0]+remaining[1]*4096+floor
                free=shutil.disk_usage(out).free
                save(out/'CAPACITY.json',dict(at=stamp(),free=free,required=required,payload_remaining=remaining[0],floor=floor,passed=free>=required))
                assert free>=required,'Insufficient free space for independent copies and reserve'
                done=0;copied_bytes=0
                # Revalidate completed copies on resume; never trust ledger flags alone.
                for ident,source,relative,size,mtime,expected,copied in db.execute('SELECT id,source,relative,bytes,mtime_ns,sha256,copied FROM files ORDER BY id'):
                    if (out/'STOP').exists():raise InterruptedError('STOP at file boundary')
                    if done%256==0:assert shutil.disk_usage(out).free>=floor,'Free-space floor reached'
                    value=copy_one(Path(source),safe_target(out,relative),size,mtime,expected)
                    db.execute('UPDATE files SET copied=1,sha256=? WHERE id=?',(value,ident))
                    done+=1;copied_bytes+=size
                    if done%256==0:
                        db.commit();save(out/'STATE.json',dict(status='running',phase='copy_and_independent_sha',pid=os.getpid(),updated_at=stamp(),files=done,total_files=inv['files'],bytes=copied_bytes,total_bytes=inv['bytes']))
                db.commit()
                assert done==inv['files'] and copied_bytes==inv['bytes']
            final=dict(status='declared_scope_copied_sha_verified',completed_at=stamp(),files=done,bytes=copied_bytes,
                ledger_sha256=sha(out/'COPY_LEDGER.sqlite'),inventory_sha256=sha(out/'INVENTORY.json'),
                scope_gaps=config.get('scope_gaps',[]),delivery_complete=False,
                remaining='Semantic relative links, full scope acceptance, guides, Python/R full-data query and relocated package verification')
            save(out/'COPY_FINAL.json',final);save(out/'STATE.json',final);return final
        except BaseException as exc:
            error=dict(status='stopped' if isinstance(exc,InterruptedError) else 'error',pid=os.getpid(),updated_at=stamp(),error=str(exc),traceback=traceback.format_exc())
            save(out/'ERROR.json',error);save(out/'STATE.json',error);raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--copy',action='store_true')
    a=p.parse_args();run(a.config,a.output,a.copy)
