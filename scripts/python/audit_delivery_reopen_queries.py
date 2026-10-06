"""Bounded physical relocation and independent Python/R Parquet query audit.

This is deliberately a selected-partition test, never full delivery acceptance.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import struct
import subprocess
import time
import traceback

MAX_BYTES = 32 * 1024 * 1024
STAGE = 'metadata/reopen_queries_v1'
DEPENDENCY = 'metadata/addon_integrity_v1/FINAL.json'


def now(): return datetime.now(timezone.utc).isoformat()


def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def read(p):
    if p.stat().st_size > MAX_BYTES: raise ValueError('Metadata too large')
    return json.loads(p.read_text(encoding='utf-8-sig'))


def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for retry in range(10):
        try: tmp.replace(p); return
        except PermissionError:
            if retry == 9: raise
            time.sleep(.2)


def safe(root, rel):
    q = PurePosixPath(rel)
    if not rel or '\\' in rel or ':' in rel or q.is_absolute() or '..' in q.parts:
        raise ValueError('Unsafe relative path')
    root = root.resolve(); p = root.joinpath(*q.parts)
    cursor = root
    for part in q.parts:
        cursor = cursor/part
        if cursor.exists() and (cursor.is_symlink() or getattr(cursor.lstat(), 'st_file_attributes', 0) & 1024):
            raise ValueError('Reparse point')
    if p == root or not p.resolve().is_relative_to(root): raise ValueError('Escaped root')
    return p


def validate_plan(plan):
    cases = plan['cases']
    if plan['schema'] != 'delivery_reopen_queries.v1' or not 1 <= len(cases) <= 16:
        raise ValueError('Unsupported plan')
    if not 0 < sum(c['bytes'] for c in cases) <= MAX_BYTES: raise ValueError('Bounded byte limit')
    ids = set(); paths = set()
    for c in cases:
        safe(Path.cwd(), c['path'])
        if c['id'] in ids or c['path'].casefold() in paths: raise ValueError('Duplicate case')
        ids.add(c['id']); paths.add(c['path'].casefold())
        if c['rows'] <= 0 or c['rows'] > 200000 or not 1 <= c['sample_rows'] <= 50:
            raise ValueError('Bounded row limit')
        if not c['columns'] or len(set(c['columns'])) != len(c['columns']): raise ValueError('Columns')
        if c['category'] not in c['columns']: raise ValueError('Category column')
        if not set(c['float_columns']) <= set(c['columns']): raise ValueError('Float columns')
        if len(c['sha256']) != 64 or any(x not in '0123456789abcdef' for x in c['sha256']):
            raise ValueError('SHA format')


def verified_file(root, c):
    p = safe(root, c['path']); before = p.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size != c['bytes']: raise ValueError('File size/type')
    if sha(p) != c['sha256']: raise ValueError('Selected file SHA mismatch')
    after = p.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Selected file changed during audit')
    return p


def query(root, plan):
    import pyarrow.parquet as pq
    validate_plan(plan); results = []
    for c in plan['cases']:
        p = verified_file(root, c)
        pf = pq.ParquetFile(p)
        if pf.metadata.num_rows != c['rows']: raise ValueError('Receipt row count mismatch')
        table = pf.read(columns=c['columns'])
        values = table.column(c['category']).to_pylist()
        counts = Counter(values)
        selected=table.slice(0,c['sample_rows']).to_pylist()
        for row in selected:
            for col in c['float_columns']:
                if row[col] is not None: row[col]={'ieee754_le_hex':struct.pack('<d',row[col]).hex()}
        results.append(dict(id=c['id'], rows=table.num_rows,
            null_counts={k: table.column(k).null_count for k in c['columns']},
            counts=[dict(value=k, n=v) for k, v in counts.items()],
            selected=selected))
    return dict(cases=results)


def normalized(result):
    value = json.loads(json.dumps(result, ensure_ascii=False))
    for c in value['cases']:
        c['counts'].sort(key=lambda x: (x['value'] is not None, str(x['value'])))
    return value


def assert_equal(a, b):
    if normalized(a) != normalized(b): raise ValueError('Independent query results differ')


def relocate(root, destination, plan):
    validate_plan(plan)
    root = root.resolve(); destination = destination.resolve()
    if destination == root or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError('Relocation requires separate roots')
    destination.mkdir(parents=True, exist_ok=True)
    for c in plan['cases']:
        source = verified_file(root, c); target = safe(destination, c['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists(): verified_file(destination, c)
        else:
            tmp = target.with_suffix(target.suffix+'.partial')
            with source.open('rb') as src, tmp.open('wb') as dst:
                shutil.copyfileobj(src, dst, 1024*1024); dst.flush(); os.fsync(dst.fileno())
            if sha(tmp) != c['sha256']: raise ValueError('Relocation SHA mismatch')
            tmp.replace(target)
            verified_file(destination, c)


def audit(root, destination, plan_path, out, rscript, r_query, r_library):
    plan = read(plan_path); validate_plan(plan)
    original = query(root, plan)
    relocate(root, destination, plan)
    # R receives only relative paths in this copied plan and the NEW root.
    moved_plan = destination/'REOPEN_QUERY_PLAN.json'; save(moved_plan, plan)
    moved = query(destination, read(moved_plan)); assert_equal(original, moved)
    out.mkdir(parents=True, exist_ok=True)
    r_output = out/'R_QUERY.json'
    env = os.environ.copy(); env.update(LC_ALL='', LC_CTYPE='', LANG='')
    completed = subprocess.run([str(rscript), str(r_query), str(destination), str(moved_plan),
        str(r_output), str(r_library)], capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=300, env=env)
    (out/'R_stdout.log').write_text(completed.stdout, encoding='utf-8')
    (out/'R_stderr.log').write_text(completed.stderr, encoding='utf-8')
    if completed.returncode: raise RuntimeError('R query failed; inspect R_stderr.log')
    actual = read(r_output); assert_equal(moved, actual)
    # Detect changes during the independent reads, including a resumable old target.
    for c in plan['cases']: verified_file(root, c); verified_file(destination, c)
    save(out/'PYTHON_QUERY.json', original)
    save(out/'RELOCATED_PYTHON_QUERY.json', moved)
    return dict(status='bounded_reopen_queries_verified', sample=True,
        scope='Deterministic selected whole Parquet partitions, first rows, category and null counts; not full-corpus or full-delivery acceptance',
        completed_at=now(), files=len(plan['cases']), bytes=sum(c['bytes'] for c in plan['cases']),
        rows=sum(c['rows'] for c in plan['cases']), plan_sha256=sha(plan_path),
        evidence={f: sha(out/f) for f in ['PYTHON_QUERY.json','RELOCATED_PYTHON_QUERY.json','R_QUERY.json']},
        python_r_equal=True, physical_relocation=True, delivery_complete=False, api_calls=0,
        source_modified=False)


def dependencies(root, plan):
    final = read(safe(root, DEPENDENCY))
    if final['status'] != 'addon_files_sha_verified' or final.get('sample'):
        raise ValueError('Full add-on dependency required')
    if final['dependencies'].get('COPY_FINAL.json') != sha(root/'COPY_FINAL.json'):
        raise ValueError('Add-on copy dependency binding missing or changed')
    for rel, digest in final['dependencies'].items():
        if sha(safe(root, rel)) != digest: raise ValueError('Dependency receipt changed')
    copied = read(root/'COPY_FINAL.json')
    if copied['status'] != 'declared_scope_copied_sha_verified' or copied.get('sample'):
        raise ValueError('Full copy required')
    # The preceding full-copy audit is authoritative. Indexed lookups only here.
    dbpath = root/'COPY_LEDGER.sqlite'
    with closing(sqlite3.connect(dbpath.as_uri()+'?mode=ro', uri=True)) as db:
        for c in plan['cases']:
            row = db.execute('SELECT bytes,sha256,copied FROM files WHERE relative=?', (c['path'],)).fetchone()
            if row != (c['bytes'], c['sha256'], 1): raise ValueError('Selected copy ledger row mismatch')
    return {DEPENDENCY:sha(root/DEPENDENCY), 'COPY_FINAL.json':sha(root/'COPY_FINAL.json')}


def run(args):
    import msvcrt
    root = args.root.resolve(); out = root/STAGE; out.mkdir(parents=True, exist_ok=True)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            plan = read(args.plan); validate_plan(plan)
            contract = dict(schema='reopen_contract.v1', runner_sha256=sha(Path(__file__)),
                r_query_sha256=sha(args.r_query), plan_sha256=sha(args.plan),
                addon_contract_sha256=sha(root/'metadata/addon_integrity_v1/CONTRACT.json'),
                destination=str(args.destination.resolve()), rscript=str(args.rscript.resolve()),
                r_library=str(args.r_library.resolve()))
            cp = out/'CONTRACT.json'
            if cp.exists() and read(cp) != contract: raise ValueError('Frozen contract changed')
            if not cp.exists(): save(cp, contract)
            while not (root/DEPENDENCY).exists():
                if (out/'STOP').exists(): raise InterruptedError('STOP')
                for rel in ['', 'metadata/semantic_links', 'metadata/historical_textgrid_links',
                            'metadata/guide_targets_v2', 'metadata/addon_integrity_v1']:
                    sp = root/rel/'STATE.json'
                    if sp.exists() and read(sp)['status'] in ('error','failed','stopped'):
                        raise RuntimeError('Dependency stopped: '+rel)
                save(out/'STATE.json', dict(status='waiting_for_addon_integrity',pid=os.getpid(),updated_at=now()))
                if not args.wait: return
                time.sleep(300)
            if (out/'STOP').exists(): raise InterruptedError('STOP')
            if sha(args.plan)!=contract['plan_sha256'] or sha(args.r_query)!=contract['r_query_sha256'] or sha(Path(__file__))!=contract['runner_sha256']:
                raise ValueError('Frozen tools changed while waiting')
            if sha(root/'metadata/addon_integrity_v1/CONTRACT.json')!=contract['addon_contract_sha256']:
                raise ValueError('Add-on contract changed')
            bindings = dependencies(root, plan)
            if (out/'DEPENDENCIES.json').exists() and read(out/'DEPENDENCIES.json') != bindings:
                raise ValueError('Dependency changed on resume')
            save(out/'DEPENDENCIES.json', bindings)
            save(out/'STATE.json', dict(status='running',pid=os.getpid(),updated_at=now()))
            result = audit(root,args.destination,args.plan,out,args.rscript,args.r_query,args.r_library)
            if dependencies(root,plan) != bindings: raise ValueError('Dependency changed during audit')
            result['dependencies']=bindings; result['contract_sha256']=sha(cp)
            save(out/'FINAL.json',result)
            save(out/'STATE.json',dict(status=result['status'],pid=os.getpid(),updated_at=now()))
        except Exception as exc:
            status='stopped' if isinstance(exc,InterruptedError) else 'error'
            save(out/'ERROR.json',dict(status=status,error=str(exc),traceback=traceback.format_exc(),updated_at=now()))
            save(out/'STATE.json',dict(status=status,pid=os.getpid(),updated_at=now()))
            raise
        finally:
            lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    for name in ['root','destination','plan','rscript','r-query','r-library']:ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--wait',action='store_true')
    run(ap.parse_args())
