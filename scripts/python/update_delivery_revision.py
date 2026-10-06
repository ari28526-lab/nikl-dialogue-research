"""Manifest-driven, additive package updates. Never scans/copies unchanged media.

init verifies the base ledger once. apply accepts an explicit changed-file list,
writes an immutable revision overlay, and leaves base and prior revisions intact.
Readers resolve through the selected revision; this is not a full integrity audit.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import msvcrt


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)


def now():return datetime.now(timezone.utc).isoformat()


def safe(root,relative):
    p=PurePosixPath(relative)
    if not p.parts or p.is_absolute() or '\\' in relative or any(x=='..' or ':' in x for x in p.parts):
        raise ValueError('Unsafe relative path')
    result=root.joinpath(*p.parts)
    if not result.resolve().is_relative_to(root.resolve()):raise ValueError('Path escapes package')
    return result


def revision_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}',value):
        raise ValueError('Unsafe revision ID')
    return value


def ledger_stat(root):
    s=(root/'COPY_LEDGER.sqlite').stat();return dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns)


def initialize(root):
    root=root.resolve();final=read(root/'COPY_FINAL.json')
    if final['status']!='declared_scope_copied_sha_verified':raise ValueError('Completed base copy required')
    binding=root/'updates/BASE_BINDING.json'
    if binding.exists():return verify_binding(root)
    before=ledger_stat(root)
    if sha(root/'COPY_LEDGER.sqlite')!=final['ledger_sha256'] or ledger_stat(root)!=before:
        raise ValueError('Base ledger hash/stat mismatch')
    if sha(root/'INVENTORY.json')!=final['inventory_sha256']:raise ValueError('Base inventory hash mismatch')
    value=dict(schema='delivery_update_base.v1',bound_at=now(),base_final_sha256=sha(root/'COPY_FINAL.json'),
               ledger_sha256=final['ledger_sha256'],ledger_stat=before,
               audit_policy='Later updates use immutable base receipt plus ledger stat and indexed lookups; this is not a new full-media audit.')
    save(binding,value);return value


def verify_binding(root):
    b=read(root/'updates/BASE_BINDING.json')
    if b['base_final_sha256']!=sha(root/'COPY_FINAL.json') or b['ledger_stat']!=ledger_stat(root):
        raise ValueError('Base binding changed; investigate and re-audit, do not silently rebind')
    return b


def chain(root,selected):
    result=[];seen=set()
    while selected is not None:
        selected=revision_id(selected)
        if selected in seen:raise ValueError('Revision cycle')
        seen.add(selected);p=root/'updates/revisions'/selected/'REVISION.json';r=read(p)
        if r['revision']!=selected or r['status']!='complete':raise ValueError('Incomplete revision')
        if r['base_final_sha256']!=sha(root/'COPY_FINAL.json'):raise ValueError('Revision belongs to another base')
        if r['parent']:
            parent=root/'updates/revisions'/revision_id(r['parent'])/'REVISION.json'
            if sha(parent)!=r['parent_sha256']:raise ValueError('Parent revision changed')
        result.append(r);selected=r['parent']
    return result


def lookup(root,db,revisions,logical):
    safe(root,logical)
    for r in revisions:
        for entry in r['changed_files']:
            if entry['logical_path'].casefold()==logical.casefold():
                return dict(path=entry['physical_path'],bytes=entry['bytes'],sha256=entry['sha256'])
    row=db.execute('SELECT relative,bytes,sha256,copied FROM files WHERE relative=?',(logical,)).fetchone()
    if row is None:return None
    if row[3]!=1 or not row[2]:raise ValueError('Unverified base file')
    return dict(path=row[0],bytes=row[1],sha256=row[2])


def plan(root,changes):
    binding=verify_binding(root)
    if changes['schema']!='delivery_changes.v1':raise ValueError('Invalid change manifest')
    revision_id(changes['revision']);parent=changes.get('parent');revisions=chain(root,parent)
    if parent==changes['revision']:raise ValueError('Revision cannot be its own parent')
    work=[];seen=set()
    with closing(sqlite3.connect((root/'COPY_LEDGER.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        for x in changes['files']:
            logical=x['logical_path'];safe(root,logical)
            if logical.split('/')[0].casefold()=='updates':raise ValueError('Reserved logical namespace')
            if logical.casefold() in seen:raise ValueError('Duplicate logical path')
            seen.add(logical.casefold())
            if not re.fullmatch('[0-9a-f]{64}',x['sha256']) or not isinstance(x['bytes'],int) or x['bytes']<0:
                raise ValueError('Invalid expected hash/size')
            prior=lookup(root,db,revisions,logical)
            unchanged=prior is not None and prior['sha256']==x['sha256'] and prior['bytes']==x['bytes']
            work.append(dict(**x,action='reuse' if unchanged else 'write',previous=prior))
    return dict(schema='delivery_revision_plan.v1',revision=changes['revision'],parent=parent,
                parent_sha256=sha(root/'updates/revisions'/parent/'REVISION.json') if parent else None,
                base_final_sha256=binding['base_final_sha256'],files=work,
                copy_files=sum(x['action']=='write' for x in work),
                copy_bytes=sum(x['bytes'] for x in work if x['action']=='write'),
                reused_manifest_entries=sum(x['action']=='reuse' for x in work),
                unchanged_tree_scanned=False,unchanged_media_rehashed=False,
                affected_documents=changes.get('affected_documents',[]),
                input_requirement='Explicit change manifest from upstream transformation; omissions are not discovered by a full-tree scan.')


def apply(root,changes):
    root=root.resolve();directory=root/'updates/revisions'/revision_id(changes['revision']);directory.mkdir(parents=True,exist_ok=True)
    with (directory/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        proposed=plan(root,changes);manifest=directory/'PLAN.json'
        if manifest.exists() and read(manifest)!=proposed:raise ValueError('Revision ID already bound to different inputs')
        if not manifest.exists():save(manifest,proposed)
        done=[]
        for x in proposed['files']:
            if x['action']=='reuse':continue
            if (directory/'STOP').exists():raise InterruptedError('STOP at changed-file boundary')
            source=Path(x['source']);source_before=source.stat()
            if source_before.st_size!=x['bytes']:raise ValueError('Changed source size mismatch')
            rel=f'updates/revisions/{changes["revision"]}/files/{x["logical_path"]}'
            dest=safe(root,rel);dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():
                if os.path.samefile(source,dest) or sha(dest)!=x['sha256'] or sha(source)!=x['sha256']:
                    raise ValueError('Resume file differs from immutable revision')
            else:
                tmp=dest.with_name(dest.name+'.partial');h=hashlib.sha256()
                if tmp.is_symlink():raise ValueError('Unsafe partial file')
                with source.open('rb') as src,tmp.open('wb') as dst:
                    for block in iter(lambda:src.read(4*1024*1024),b''):h.update(block);dst.write(block)
                    dst.flush();os.fsync(dst.fileno())
                if h.hexdigest()!=x['sha256'] or sha(tmp)!=x['sha256']:raise ValueError('Changed file SHA mismatch')
                after=source.stat()
                if (after.st_size,after.st_mtime_ns)!=(source_before.st_size,source_before.st_mtime_ns):raise ValueError('Source changed while copying')
                if dest.exists():raise ValueError('Destination appeared while copying')
                tmp.rename(dest)
            done.append(dict(logical_path=x['logical_path'],physical_path=rel,bytes=x['bytes'],sha256=x['sha256'],previous=x['previous']))
            save(directory/'STATE.json',dict(status='running',completed_files=len(done),total_files=proposed['copy_files'],updated_at=now()))
        final=dict(schema='delivery_revision.v1',status='complete',revision=proposed['revision'],parent=proposed['parent'],parent_sha256=proposed['parent_sha256'],
                   base_final_sha256=proposed['base_final_sha256'],changed_files=done,affected_documents=proposed['affected_documents'],
                   full_delivery_revalidated=False,unchanged_media_rehashed=False,unchanged_tree_scanned=False)
        rp=directory/'REVISION.json'
        if rp.exists() and read(rp)!=final:raise ValueError('Completed revision changed')
        if not rp.exists():save(rp,final)
        save(directory/'STATE.json',dict(status='complete',updated_at=now(),revision_sha256=sha(rp)))
        return final


def resolve(root,selected,logical,verify=False):
    verify_binding(root)
    with closing(sqlite3.connect((root/'COPY_LEDGER.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        result=lookup(root,db,chain(root,selected),logical)
    if result is None:raise ValueError('Unknown logical path')
    p=safe(root,result['path'])
    if not p.is_file() or p.stat().st_size!=result['bytes']:raise ValueError('Resolved file missing/changed')
    if verify and sha(p)!=result['sha256']:raise ValueError('Resolved file SHA mismatch')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['init','plan','apply','resolve']);p.add_argument('--package',type=Path,required=True)
    p.add_argument('--changes',type=Path);p.add_argument('--revision');p.add_argument('--logical-path');p.add_argument('--verify',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.command=='init':value=initialize(a.package)
    elif a.command=='plan':value=plan(a.package,read(a.changes))
    elif a.command=='apply':value=apply(a.package,read(a.changes))
    else:value=resolve(a.package,a.revision,a.logical_path,a.verify)
    if a.output:save(a.output,value)
    else:print(json.dumps(value,ensure_ascii=False,indent=2))
