"""Hash frozen post-copy indexes and tools; never declares full delivery complete."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import msvcrt
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import time
import traceback

ROOTS = ('metadata/semantic_links', 'metadata/historical_textgrid_links',
         'metadata/guide_targets_v2', 'research_tools_v2')
CONTROLS = {'STATE.json', 'ERROR.json', 'ERROR_RESOLUTION.json', 'PROCESS.lock',
            'STOP', 'stdout.log', 'stderr.log'}
FINALS = {'COPY_FINAL.json': 'declared_scope_copied_sha_verified',
          ROOTS[0]+'/FINAL.json': 'semantic_links_complete_with_explicit_scope_gaps',
          ROOTS[1]+'/FINAL.json': 'historical_textgrid_links_complete',
          ROOTS[2]+'/FINAL.json': 'guide_targets_verified'}

def now(): return datetime.now(timezone.utc).isoformat()

def safe(root, rel):
    p = PurePosixPath(rel)
    if not rel or '\\' in rel or ':' in rel or p.is_absolute() or '..' in p.parts:
        raise ValueError('Unsafe relative path: '+rel)
    root = root.resolve(); target = root.joinpath(*p.parts)
    cursor = root
    for part in p.parts:
        cursor = cursor/part
        if cursor.exists() and cursor.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Reparse point: '+rel)
    if target == root or not target.resolve().is_relative_to(root): raise ValueError('Escaped root')
    return target

def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def read(path):
    if path.stat().st_size > 128*1024*1024: raise ValueError('Metadata size limit')
    return json.loads(path.read_text(encoding='utf-8-sig'))

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for retry in range(10):
        try: temp.replace(path); return
        except PermissionError:
            if retry == 9: raise
            time.sleep(.2)

def inventory(root, roots):
    rows=[]; seen=set()
    for rel in roots:
        base=safe(root,rel)
        if not base.is_dir(): raise ValueError('Required add-on directory absent: '+rel)
        for directory, dirs, files in os.walk(base, followlinks=False):
            for name in dirs:
                safe(root,(Path(directory)/name).relative_to(root).as_posix())
            for name in files:
                path=Path(directory)/name; key=path.relative_to(root).as_posix()
                path=safe(root,key)
                # Only top-level runtime files are excluded, never data subtrees.
                if path.parent==base and name in CONTROLS: continue
                if name.endswith(('.tmp','.partial','-wal','-shm','-journal')):
                    raise ValueError('Unfinished file in frozen add-on: '+key)
                if key.casefold() in seen: raise ValueError('Duplicate add-on path')
                seen.add(key.casefold()); s=path.stat()
                if not stat.S_ISREG(s.st_mode): raise ValueError('Nonregular file')
                rows.append(dict(path=key,bytes=s.st_size,mtime_ns=s.st_mtime_ns))
    return sorted(rows,key=lambda x:x['path'])

def dependencies(root):
    values={}; bindings={}
    for rel,status in FINALS.items():
        p=safe(root,rel); v=read(p)
        if v['status']!=status or v.get('sample'): raise ValueError('Full completed dependency required: '+rel)
        values[rel]=v; bindings[rel]=sha(p)
    guide=values[ROOTS[2]+'/FINAL.json']
    if guide['dependencies']!={k:v for k,v in bindings.items() if k!=ROOTS[2]+'/FINAL.json'}:
        raise ValueError('Guide dependency SHA mismatch')
    hist=read(safe(root,ROOTS[1]+'/DEPENDENCIES.json'))
    if hist['copy_final_sha256']!=bindings['COPY_FINAL.json'] or hist['semantic_final_sha256']!=bindings[ROOTS[0]+'/FINAL.json']:
        raise ValueError('Historical dependency SHA mismatch')
    expected={k:v for k,v in bindings.items() if k!='COPY_FINAL.json'}
    for dirname,indexname in [(ROOTS[0],'UTTERANCE_INDEX.sqlite'),(ROOTS[1],'HISTORICAL_TEXTGRID_INDEX.sqlite')]:
        final=values[dirname+'/FINAL.json'];expected[dirname+'/'+indexname]=final['index_sha256']
        for r in final['receipts']:
            key=dirname+'/'+r['path'];rp=safe(root,key)
            if sha(rp)!=r['sha256']: raise ValueError('Stage receipt changed')
            expected[key]=r['sha256']
            if dirname==ROOTS[0]:
                if not key.endswith('.receipt.json'): raise ValueError('Unexpected semantic receipt name')
                expected[key[:-len('.receipt.json')]]=read(rp)['sha256']
    expected[ROOTS[0]+'/DATASET_CATALOG.json']=values[ROOTS[0]+'/FINAL.json']['catalog_sha256']
    bundle=ROOTS[3];bm=safe(root,bundle+'/BUNDLE_MANIFEST.json')
    if sha(bm)!=guide['bundle_manifest_sha256']: raise ValueError('Bundle binding changed')
    expected[bundle+'/BUNDLE_MANIFEST.json']=sha(bm)
    for r in read(bm)['files']:expected[bundle+'/'+r['path']]=r['sha256']
    return bindings,expected

def build(root,out,roots,expected,bindings):
    root=root.resolve();out.mkdir(parents=True,exist_ok=True)
    rows=inventory(root,roots); bypath={x['path']:x for x in rows}
    if not set(expected)<=set(bypath): raise ValueError('Expected stage file absent from inventory')
    inv=out/'INVENTORY.json'; content=dict(roots=list(roots),files=rows)
    if inv.exists() and read(inv)!=content: raise ValueError('Frozen add-on inventory changed')
    if not inv.exists():save(inv,content)
    dep=out/'DEPENDENCIES.json'
    if dep.exists() and read(dep)!=bindings: raise ValueError('Dependency changed on resume')
    if not dep.exists():save(dep,bindings)
    total=0; dbpath=out/'HASH_LEDGER.sqlite'
    with closing(sqlite3.connect(dbpath)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,bytes INTEGER,mtime_ns INTEGER,sha256 TEXT)')
        for ordinal,item in enumerate(rows,1):
            if (out/'STOP').exists(): raise InterruptedError('STOP at file boundary')
            p=safe(root,item['path']);before=p.stat(); digest=sha(p);after=p.stat()
            if (before.st_size,before.st_mtime_ns)!=(item['bytes'],item['mtime_ns']) or (after.st_size,after.st_mtime_ns)!=(before.st_size,before.st_mtime_ns):
                raise ValueError('Add-on changed during hashing')
            if item['path'] in expected and digest!=expected[item['path']]:raise ValueError('Stage payload SHA mismatch: '+item['path'])
            prior=db.execute('SELECT bytes,mtime_ns,sha256 FROM files WHERE path=?',(item['path'],)).fetchone()
            value=(item['bytes'],item['mtime_ns'],digest)
            if prior is not None and prior!=value:raise ValueError('Resume payload changed')
            if prior is None:db.execute('INSERT INTO files VALUES(?,?,?,?)',(item['path'],*value))
            total+=item['bytes']
            if ordinal%128==0 or ordinal==len(rows):
                db.commit();save(out/'STATE.json',dict(status='running',phase='addon_sha',pid=os.getpid(),updated_at=now(),files=ordinal,total_files=len(rows),bytes=total,total_bytes=sum(x['bytes'] for x in rows)))
        if db.execute('SELECT count(*) FROM files').fetchone()[0]!=len(rows):raise ValueError('Unexpected ledger rows')
        manifest=out/'SHA256_MANIFEST.jsonl';temp=manifest.with_suffix('.jsonl.tmp')
        with temp.open('w',encoding='utf-8',newline='\n') as f:
            for path,size,digest in db.execute('SELECT path,bytes,sha256 FROM files ORDER BY path'):
                f.write(json.dumps(dict(path=path,bytes=size,sha256=digest),ensure_ascii=False)+'\n')
            f.flush();os.fsync(f.fileno())
        temp.replace(manifest)
    if inventory(root,roots)!=rows:raise ValueError('Add-on inventory changed during audit')
    count=0;size=0;last=''
    with manifest.open(encoding='utf-8') as f:
        for line in f:
            item=json.loads(line)
            if item['path']<=last or bypath[item['path']]['bytes']!=item['bytes']:raise ValueError('Manifest readback mismatch')
            last=item['path'];count+=1;size+=item['bytes']
    if (count,size)!=(len(rows),total):raise ValueError('Manifest totals mismatch')
    result=dict(status='addon_files_sha_verified',completed_at=now(),sample=False,files=count,bytes=size,
        roots=list(roots),manifest_sha256=sha(manifest),inventory_sha256=sha(inv),ledger_sha256=sha(dbpath),
        dependencies=bindings,stage_bound_files=len(expected),delivery_complete=False,
        exclusions=sorted(CONTROLS),limits='Only declared post-copy add-on roots. Existing corpus payload copy audit is reused, not repeated. Audio scope, full-package relocation and final acceptance remain separate.')
    return result

def run(root,out,wait):
    root=root.resolve();out=out.resolve()
    if out!=root/'metadata/addon_integrity_v1':raise ValueError('Unexpected output directory')
    out.mkdir(parents=True,exist_ok=True)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            frozen=['CONTRACT.json',*(x+'/CONTRACT.json' for x in ROOTS[:3]),ROOTS[3]+'/BUNDLE_MANIFEST.json']
            contract=dict(schema='delivery_addon_manifest.v1',roots=list(ROOTS),runner_sha256=sha(Path(__file__)),frozen={p:sha(safe(root,p)) for p in frozen})
            cp=out/'CONTRACT.json'
            if cp.exists() and read(cp)!=contract:raise ValueError('Frozen contract changed')
            if not cp.exists():save(cp,contract)
            while not (root/ROOTS[2]/'FINAL.json').exists():
                if (out/'STOP').exists():raise InterruptedError('STOP while waiting')
                for d in ['',*ROOTS[:3]]:
                    if read(root/d/'STATE.json')['status'] in ('error','failed','stopped'):raise RuntimeError('Dependency stopped: '+d)
                if not wait:raise RuntimeError('Guide FINAL required')
                save(out/'STATE.json',dict(status='waiting_for_guide_targets',pid=os.getpid(),updated_at=now()));time.sleep(300)
            if sha(Path(__file__))!=contract['runner_sha256'] or any(sha(safe(root,p))!=v for p,v in contract['frozen'].items()):raise ValueError('Frozen inputs changed during wait')
            bindings,expected=dependencies(root)
            result=build(root,out,ROOTS,expected,bindings)
            if dependencies(root)[0]!=bindings:raise ValueError('Dependency changed during audit')
            save(out/'FINAL.json',result);save(out/'STATE.json',result)
        except BaseException as exc:
            error=dict(status='stopped' if isinstance(exc,InterruptedError) else 'error',pid=os.getpid(),updated_at=now(),error=str(exc),traceback=traceback.format_exc())
            save(out/'ERROR.json',error);save(out/'STATE.json',error);raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--wait',action='store_true')
    a=p.parse_args();run(a.package,a.output,a.wait)
