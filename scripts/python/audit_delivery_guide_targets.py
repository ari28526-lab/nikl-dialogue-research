"""After sequential indexing, verify portable guide files and declared targets.

Only the small reader bundle is freshly hashed. Corpus SHA values are checked
against the completed copy ledger; this is not a new corpus-wide payload audit.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import msvcrt
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import sqlite3
import time
import traceback


def now(): return datetime.now(timezone.utc).isoformat()


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    if path.stat().st_size > 16 * 1024 * 1024: raise ValueError('Unexpectedly large metadata')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for attempt in range(10):
        try: temp.replace(path); return
        except PermissionError:
            if attempt == 9: raise
            time.sleep(.2)


def safe(root, relative):
    if not relative or '\\' in relative or ':' in relative: raise ValueError('Unsafe relative path')
    p = PurePosixPath(relative)
    if p.is_absolute() or '..' in p.parts: raise ValueError('Path traversal')
    target = (root/p).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve(): raise ValueError('Path escaped root')
    return target


def mapped_source(source, roots):
    source = PureWindowsPath(source)
    if not source.is_absolute() or '..' in source.parts: raise ValueError('Unsafe original source path')
    for item in sorted(roots, key=lambda x: len(x['source']), reverse=True):
        try: tail = source.relative_to(PureWindowsPath(item['source']))
        except ValueError: continue
        return str(PurePosixPath(item['destination']) / PurePosixPath(tail.as_posix()))
    raise ValueError('Unmapped original source')


def audit(root, bundle, expected_manifest_sha, expected_counts=(7,49)):
    manifest_path = bundle/'BUNDLE_MANIFEST.json'
    if sha(manifest_path) != expected_manifest_sha: raise ValueError('Frozen bundle manifest changed')
    manifest = read(manifest_path); seen = set()
    for item in manifest['files']:
        rel = item['path']
        if rel.casefold() in seen: raise ValueError('Duplicate manifest path')
        seen.add(rel.casefold()); path = safe(bundle, rel)
        if path.stat().st_size != item['bytes'] or path.stat().st_size > 8*1024*1024 or sha(path) != item['sha256']:
            raise ValueError('Reader bundle file changed: '+rel)
    required = ['supplement_reader/'+name for name in ['examples.json','source_inventory.json',
        'original_examples.json','original_source_inventory.json']]
    if not all(x.casefold() in seen for x in required): raise ValueError('Required guide metadata not in manifest')
    examples = read(bundle/required[0]); sources = read(bundle/required[1])
    old_examples = read(bundle/required[2]); old_sources = read(bundle/required[3])
    if examples['original_examples_sha256'] != sha(bundle/required[2]) or sources['original_inventory_sha256'] != sha(bundle/required[3]):
        raise ValueError('Original guide SHA binding changed')
    if (len(examples['examples']), len(sources['sources'])) != expected_counts:
        raise ValueError('Unexpected guide record counts')
    if len(old_examples['examples']) != len(examples['examples']) or len(old_sources) != len(sources['sources']):
        raise ValueError('Original guide record count differs')
    if examples['created_at'] != old_examples['created_at']: raise ValueError('Original sample date changed')
    roots = read(root/'CONTRACT.json')['config']['roots']
    refs = []
    with closing(sqlite3.connect((root/'COPY_LEDGER.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        def target(relative, expected_sha=None, expected_bytes=None):
            path = safe(root, relative)
            row = db.execute('SELECT bytes,sha256,copied FROM files WHERE relative=?',(relative,)).fetchone()
            if not row or row[2] != 1: raise ValueError('Guide target absent or not copied: '+relative)
            if path.stat().st_size != row[0]: raise ValueError('Guide target size changed: '+relative)
            if expected_sha is not None and expected_sha != row[1]: raise ValueError('Registered source SHA differs from copied source: '+relative)
            if expected_bytes is not None and expected_bytes != row[0]: raise ValueError('Registered source size differs')
            return dict(path=relative, bytes=row[0], sha256=row[1], payload_sha_basis='Completed independent copy audit; no fresh target rehash')
        for item, old in zip(examples['examples'], old_examples['examples']):
            if {k:v for k,v in item.items() if k != 'package_database_path'} != old: raise ValueError('Stored example changed')
            rel = item['package_database_path']
            if rel != mapped_source(old['source_database'], roots): raise ValueError('Example path mapping mismatch')
            refs.append(dict(kind='stored_example_database',id=item['id'],reference=target(rel),
                             source_table=item['source_table'],source_key=item['source_key']))
        for number, (item, old) in enumerate(zip(sources['sources'],old_sources)):
            if {k:v for k,v in item.items() if k != 'package_path'} != old: raise ValueError('Registered source record changed')
            rel = item['package_path']
            if rel != mapped_source(old['destination'], roots): raise ValueError('Source path mapping mismatch')
            refs.append(dict(kind='registered_used_source',ordinal=number,reference=target(rel,old['sha256'],old['bytes'])))
    return dict(status='guide_targets_verified',bundle_manifest_sha256=expected_manifest_sha,
        bundle_files_hashed=len(manifest['files']),examples=expected_counts[0],registered_sources=expected_counts[1],
        references=refs,delivery_complete=False,
        limits='Fresh hashes cover only the reader bundle. Targets checked by indexed ledger SHA/size and current file size. No new DB row, linguistic, full payload or relocated-root validation.')


def run(root, bundle, out, wait):
    root=root.resolve();bundle=bundle.resolve();out=out.resolve()
    if not out.is_relative_to(root/'metadata') or out == root/'metadata': raise ValueError('Output must be a metadata subdirectory')
    if not bundle.is_relative_to(root) or bundle == root: raise ValueError('Bundle must be inside package')
    out.mkdir(parents=True,exist_ok=True)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            contract=dict(schema='guide_target_audit.v1',runner_sha256=sha(Path(__file__)),
                copy_contract_sha256=sha(root/'CONTRACT.json'),bundle=bundle.relative_to(root).as_posix(),
                bundle_manifest_sha256=sha(bundle/'BUNDLE_MANIFEST.json'))
            if (out/'CONTRACT.json').exists():
                if read(out/'CONTRACT.json') != contract: raise ValueError('Frozen guide audit contract changed')
            else: save(out/'CONTRACT.json',contract)
            history=root/'metadata/historical_textgrid_links';semantic=root/'metadata/semantic_links'
            while not (history/'FINAL.json').exists():
                if (out/'STOP').exists(): raise InterruptedError('STOP while waiting')
                for dependency in [root,semantic,history]:
                    if read(dependency/'STATE.json')['status'] in ['error','stopped']: raise RuntimeError('Dependency stopped: '+str(dependency))
                if not wait: raise RuntimeError('Historical index FINAL required')
                save(out/'STATE.json',dict(status='waiting_for_historical_textgrid_links',pid=os.getpid(),updated_at=now()))
                time.sleep(300)
            if sha(Path(__file__)) != contract['runner_sha256'] or sha(root/'CONTRACT.json') != contract['copy_contract_sha256']:
                raise ValueError('Runner or copy contract changed during wait')
            expected=[(root/'COPY_FINAL.json','declared_scope_copied_sha_verified'),
                (semantic/'FINAL.json','semantic_links_complete_with_explicit_scope_gaps'),
                (history/'FINAL.json','historical_textgrid_links_complete')]
            dependencies={}
            for path,status in expected:
                value=read(path)
                if value['status'] != status or value.get('sample'): raise ValueError('Full dependency receipt required')
                dependencies[path.relative_to(root).as_posix()]=sha(path)
            hdeps=read(history/'DEPENDENCIES.json')
            if hdeps['copy_final_sha256'] != dependencies['COPY_FINAL.json'] or hdeps['semantic_final_sha256'] != dependencies['metadata/semantic_links/FINAL.json']:
                raise ValueError('Historical dependency binding changed')
            save(out/'STATE.json',dict(status='running',phase='guide_targets',pid=os.getpid(),updated_at=now()))
            result=audit(root,bundle,contract['bundle_manifest_sha256'])
            result.update(completed_at=now(),dependencies=dependencies,sample=False)
            save(out/'FINAL.json',result);save(out/'STATE.json',result)
        except BaseException as exc:
            error=dict(status='stopped' if isinstance(exc,InterruptedError) else 'error',pid=os.getpid(),updated_at=now(),error=str(exc),traceback=traceback.format_exc())
            save(out/'ERROR.json',error);save(out/'STATE.json',error);raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--wait',action='store_true')
    a=p.parse_args();run(a.package,a.bundle,a.output,a.wait)
