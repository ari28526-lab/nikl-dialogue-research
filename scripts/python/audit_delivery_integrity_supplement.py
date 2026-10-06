"""Resumable explicit small-file integrity supplement, never DELIVERY_FINAL.

Only a frozen explicit list is read. Dependency receipts are bound at start and
rechecked at end. This supplements, and does not replace, corpus payload audits.
"""
import argparse,hashlib,json,os
from pathlib import Path
import update_delivery_revision as u

MAX_FILE=16*1024*1024
MAX_TOTAL=128*1024*1024
def digest(path):
    before=path.stat()
    if before.st_size>MAX_FILE:raise ValueError('Small-file bound exceeded')
    with path.open('rb') as f:raw=f.read(MAX_FILE+1)
    after=path.stat()
    if len(raw)>MAX_FILE or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('Input changed during hash')
    return hashlib.sha256(raw).hexdigest(),len(raw)
def safe(root,rel):
    p=u.safe(root,rel)
    for a in [p,*p.parents]:
        if a==root.parent:break
        if a.exists() and (a.is_symlink() or getattr(a.stat(),'st_file_attributes',0)&1024):
            raise ValueError('Reparse point prohibited')
    return p
def validate(plan):
    if plan.get('schema')!='explicit_integrity_supplement.v1':raise ValueError('Wrong schema')
    files=plan['files'];deps=plan['dependencies']
    if not 1<=len(files)<=500 or not 1<=len(deps)<=20:raise ValueError('List bounds exceeded')
    seen=set();total=0
    for x in files:
        p=x['path'];u.safe(Path.cwd(),p)
        if p.casefold() in seen:raise ValueError('Duplicate file')
        seen.add(p.casefold())
        if type(x['bytes']) is not int or not 0<=x['bytes']<=MAX_FILE:raise ValueError('File byte bound')
        if len(x['sha256'])!=64 or any(c not in '0123456789abcdef' for c in x['sha256']):raise ValueError('Invalid SHA')
        total+=x['bytes']
    if total>MAX_TOTAL:raise ValueError('Aggregate bound exceeded')
    if len({x['path'].casefold() for x in deps})!=len(deps):raise ValueError('Duplicate dependency')
    for x in deps:
        u.safe(Path.cwd(),x['path'])
        if x['path'].split('/')[-1] in {'STATE.json','ERROR.json','DELIVERY_FINAL.json'}:raise ValueError('Stable stage receipt required')
        if not x.get('status'):raise ValueError('Dependency status required')
def bindings(root,plan):
    result=[]
    for x in plan['dependencies']:
        p=safe(root,x['path']);h,size=digest(p)
        if u.read(p).get('status')!=x['status']:raise ValueError('Dependency incomplete')
        result.append(dict(path=x['path'],sha256=h,bytes=size,status=x['status']))
    return result
def audit(root,plan,out):
    root=Path(root).resolve();out=Path(out).resolve();validate(plan)
    # Output must be a new independent metadata stage, never a corpus directory.
    allowed=safe(root,'metadata/integrity_supplement_v2').resolve()
    if out.is_relative_to(root) and out!=allowed:raise ValueError('Output scope prohibited')
    for x in plan['files']:
        if safe(root,x['path']).is_relative_to(out):raise ValueError('Self-audit input prohibited')
    dep=bindings(root,plan);pin=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    out.mkdir(parents=True,exist_ok=True)
    contract=dict(schema='integrity_supplement_binding.v1',plan_sha256=pin,dependencies=dep)
    cp=out/'CONTRACT.json'
    if cp.exists() and u.read(cp)!=contract:raise ValueError('Resume binding differs; preserve output')
    if not cp.exists():u.save(cp,contract)
    progress=out/'PROGRESS.json'
    if progress.exists():
        old=u.read(progress)
        if old['plan_sha256']!=pin:raise ValueError('Progress plan differs')
        # Progress is an interruption receipt, not authority to skip new hashing.
    rows=[]
    for x in plan['files']:
        h,size=digest(safe(root,x['path']))
        if (h,size)!=(x['sha256'],x['bytes']):raise ValueError('Explicit input SHA/size differs: '+x['path'])
        rows.append(dict(path=x['path'],sha256=h,bytes=size))
        u.save(progress,dict(plan_sha256=pin,verified_files=rows))
    if bindings(root,plan)!=dep:raise ValueError('Dependency receipt changed during audit')
    final=dict(schema='integrity_supplement_receipt.v1',status='explicit_small_files_sha_verified',
        plan_sha256=pin,dependencies=dep,files=rows,bytes=sum(x['bytes'] for x in rows),
        full_payload_rehash_performed=False,delivery_complete=False,api_calls=0,
        resume_policy='Preserve binding and progress, rehash only explicit bounded small-file list')
    u.save(out/'FINAL.json',final);return final
def verify_receipt(root,plan,out):
    """Consume a receipt only after independently checking its current inputs."""
    root=Path(root).resolve();out=Path(out).resolve();validate(plan)
    final=u.read(out/'FINAL.json');contract=u.read(out/'CONTRACT.json')
    pin=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if (final.get('schema')!='integrity_supplement_receipt.v1' or
        final.get('status')!='explicit_small_files_sha_verified' or
        final.get('plan_sha256')!=pin or final.get('delivery_complete') is not False or
        final.get('full_payload_rehash_performed') is not False):
        raise ValueError('Receipt contract differs')
    before=bindings(root,plan)
    expected=[dict(path=x['path'],sha256=x['sha256'],bytes=x['bytes']) for x in plan['files']]
    if contract!=dict(schema='integrity_supplement_binding.v1',plan_sha256=pin,dependencies=before):
        raise ValueError('Current dependency binding differs')
    if final['dependencies']!=before or final['files']!=expected or final['bytes']!=sum(x['bytes'] for x in expected):
        raise ValueError('Receipt does not cover the explicit plan')
    for x in expected:
        if digest(safe(root,x['path']))!=(x['sha256'],x['bytes']):
            raise ValueError('Current small input differs; old FINAL is historical only')
    if bindings(root,plan)!=before:raise ValueError('Dependencies changed during consumption')
    return final
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--verify-only',action='store_true')
    a=p.parse_args();operation=verify_receipt if a.verify_only else audit
    print(json.dumps(operation(a.package,u.read(a.plan),a.output)))
