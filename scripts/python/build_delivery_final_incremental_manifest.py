"""Bounded metadata-only independent SHA stage; never certifies full delivery."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from run_delivery_shared_control_io import shared_opener
from datetime import datetime, timezone

STAGE = 'metadata/final_incremental_integrity_v1'
DEPENDENCY = 'metadata/completed_guide_v3/FINAL.json'
RUNTIME = {'STATE.json','ERROR.json','ERROR_RESOLUTION.json','PROCESS.lock','STOP','stdout.log','stderr.log','LAUNCH.json'}
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024

def now(): return datetime.now(timezone.utc).isoformat()
def safe(root, rel):
    p = Path(rel)
    if p.is_absolute() or '..' in p.parts or ':' in rel: raise ValueError('Unsafe relative path')
    target = root / p
    if not target.resolve().is_relative_to(root.resolve()): raise ValueError('Path escapes package')
    for parent in [target, *target.parents]:
        if parent == root.parent: break
        if parent.exists() and (parent.is_symlink() or (getattr(parent.stat(), 'st_file_attributes', 0) & 1024)):
            raise ValueError('Reparse point prohibited')
    return target

def data(path):
    for attempt in range(16):
        try:
            if path.stat().st_size > MAX_FILE: raise ValueError('Metadata exceeds file bound')
            if path.name in {'STATE.json','ERROR.json'} and os.name=='nt':
                with open(path,'rb',opener=shared_opener) as handle: raw=handle.read(1024*1024+1)
                if len(raw)>1024*1024:raise ValueError('Control snapshot exceeds bound')
            else:
                with path.open('rb') as handle: raw = handle.read(MAX_FILE + 1)
            if len(raw) > MAX_FILE: raise ValueError('Metadata exceeds file bound')
            return raw
        except PermissionError:
            if attempt == 15: raise
            time.sleep(min(.05 * (attempt + 1), .5))

def sha(path): return hashlib.sha256(data(path)).hexdigest()
def read(path): return json.loads(data(path))
def save(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for attempt in range(16):
        try: os.replace(tmp, path); return
        except PermissionError:
            if attempt == 15: raise
            time.sleep(min(.05*(attempt+1),.5))

def preflight(root, plan):
    if plan['schema'] != 'final_incremental_plan.v1': raise ValueError('Wrong plan')
    if len(plan['roots']) > 12 or len(set(plan['roots'])) != len(plan['roots']): raise ValueError('Root bounds')
    for rel in plan['roots']:
        if rel not in {'research_tools_v3','metadata/reopen_queries_v1','metadata/acceptance_evidence_v1',
                       'metadata/completed_guide_v3','metadata/control_io_v1',
                       'recovery_20261001_reboot','recovery_20261002_reboot',
                       'recovery_20261002_state_read','recovery_20261002_control_replace'}:
            raise ValueError('Undeclared metadata root')
        safe(root, rel)
    for rel, digest in plan['pins'].items():
        if sha(safe(root, rel)) != digest: raise ValueError('Frozen metadata changed: '+rel)
    helper=plan['pins'].get('metadata/control_io_v1/run_delivery_shared_control_io.py')
    if helper and sha(Path(__file__).with_name('run_delivery_shared_control_io.py'))!=helper:
        raise ValueError('Shared snapshot helper differs')

def inventory(root, plan):
    rows=[]; total=0
    for rel in plan['roots']:
        base=safe(root,rel)
        if not base.is_dir(): raise ValueError('Required metadata root missing: '+rel)
        # Only explicit bounded metadata trees; never traverses corpus roots.
        for current, dirs, files in os.walk(base, followlinks=False):
            for name in dirs: safe(root,(Path(current)/name).relative_to(root).as_posix())
            for name in sorted(files):
                path=Path(current)/name
                if not rel.startswith('recovery_') and path.parent==base and name in RUNTIME: continue
                relative=path.relative_to(root).as_posix(); safe(root,relative)
                if path.suffix.lower() not in {'.json','.jsonl','.md','.py','.r','.ps1','.html','.log','.txt','.toml'}:
                    raise ValueError('Nonmetadata payload prohibited: '+relative)
                size=path.stat().st_size
                if size>MAX_FILE: raise ValueError('Metadata exceeds file bound')
                total+=size
                if len(rows)>=500 or total>MAX_TOTAL: raise ValueError('Metadata inventory bounds exceeded')
                digest=sha(path)
                if path.stat().st_size!=size: raise ValueError('Metadata changed during read')
                rows.append(dict(path=relative,bytes=size,sha256=digest))
    return sorted(rows,key=lambda x:x['path'])

def bindings(root):
    paths={'copy':'COPY_FINAL.json','addon':'metadata/addon_integrity_v1/FINAL.json',
           'reopen':'metadata/reopen_queries_v1/FINAL.json','evidence':'metadata/acceptance_evidence_v1/FINAL.json',
           'guide':DEPENDENCY}
    docs={k:read(safe(root,v)) for k,v in paths.items()}
    expected={'copy':'declared_scope_copied_sha_verified','addon':'addon_files_sha_verified',
              'reopen':'bounded_reopen_queries_verified','evidence':'receipt_chain_verified_with_remaining_acceptance',
              'guide':'completed_state_guide_generated'}
    for k,d in docs.items():
        if d['status']!=expected[k] or d.get('delivery_complete',False) is not False: raise ValueError('Component status differs')
        if d.get('sample',False) is not (k=='reopen'): raise ValueError('Component sample scope differs')
    if (docs['copy']['files'],docs['copy']['bytes'])!=(15580294,832706074044): raise ValueError('Copy scope differs')
    if not docs['reopen']['python_r_equal'] or not docs['reopen']['physical_relocation']: raise ValueError('Reopen evidence missing')
    hashes={k:sha(safe(root,v)) for k,v in paths.items()}
    if docs['guide']['receipt_chain_sha256']!=hashes['evidence']: raise ValueError('Guide evidence binding differs')
    if sha(safe(root,'research_tools_v3/BUNDLE_MANIFEST.json'))!=docs['guide']['manifest_sha256']: raise ValueError('Guide manifest differs')
    for row in read(safe(root,'research_tools_v3/BUNDLE_MANIFEST.json'))['files']:
        if sha(safe(root,'research_tools_v3/'+row['path']))!=row['sha256']: raise ValueError('Guide file differs')
    # Large ledger and existing addon manifests are receipt references, not rehashed here.
    return dict(receipt_sha256=hashes,prior_copy=dict(files=docs['copy']['files'],bytes=docs['copy']['bytes']),
                prior_addon_manifest_sha256=docs['addon']['manifest_sha256'])

def build(root, out, plan):
    preflight(root,plan); bound=bindings(root); rows=inventory(root,plan)
    result=dict(schema='final_incremental_manifest.v1',status='bounded_metadata_sha_verified',
                completed_at=now(),sample=False,files=len(rows),bytes=sum(x['bytes'] for x in rows),
                bindings=bound,roots=plan['roots'],files_sha256=rows,delivery_complete=False,
                full_delivery_acceptance=False,api_calls=0,source_modified=False,
                remaining_acceptance=['audio_scope','revision_regeneration','delivery_final'],
                scope='Explicit metadata additions only; prior corpus audits referenced without full rehash')
    if inventory(root,plan)!=rows or bindings(root)!=bound: raise ValueError('Metadata changed during audit')
    save(out/'MANIFEST.json',result)
    if read(out/'MANIFEST.json')!=result: raise ValueError('Manifest readback differs')
    return {k:v for k,v in result.items() if k!='files_sha256'} | {'manifest_sha256':sha(out/'MANIFEST.json')}

def run(args):
    import msvcrt
    root=args.package.resolve(); plan=read(args.plan); preflight(root,plan)
    out=safe(root,STAGE);out.mkdir(parents=True,exist_ok=True)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            contract=dict(schema='final_incremental_contract.v1',runner_sha256=sha(Path(__file__)),plan_sha256=sha(args.plan))
            cp=out/'CONTRACT.json'
            if cp.exists() and read(cp)!=contract:raise ValueError('Contract changed')
            if not cp.exists():save(cp,contract)
            while not safe(root,DEPENDENCY).exists():
                if (out/'STOP').exists():raise InterruptedError('STOP')
                for rel in plan['dependency_states']:
                    state=safe(root,rel)
                    if state.exists() and read(state).get('status') in {'error','failed','stopped'}:
                        raise RuntimeError('Dependency stopped: '+rel)
                save(out/'STATE.json',dict(status='waiting_for_completed_guide',pid=os.getpid(),updated_at=now()))
                if not args.wait:return
                time.sleep(300)
            if (out/'STOP').exists():raise InterruptedError('STOP')
            if sha(args.plan)!=contract['plan_sha256'] or sha(Path(__file__))!=contract['runner_sha256']:raise ValueError('Frozen runner changed')
            preflight(root,plan)
            if (out/'FINAL.json').exists():
                prior=read(out/'FINAL.json')
                if sha(out/'MANIFEST.json')!=prior['manifest_sha256'] or inventory(root,plan)!=read(out/'MANIFEST.json')['files_sha256'] or bindings(root)!=prior['bindings']:
                    raise ValueError('Completed metadata changed')
                return
            save(out/'STATE.json',dict(status='running',pid=os.getpid(),updated_at=now()))
            final=build(root,out,plan);final.update(contract_sha256=sha(cp),plan_sha256=contract['plan_sha256'])
            save(out/'FINAL.json',final);save(out/'STATE.json',dict(status=final['status'],pid=os.getpid(),updated_at=now()))
        except Exception as exc:
            error=dict(status='error',pid=os.getpid(),updated_at=now(),error=str(exc))
            save(out/'ERROR.json',error);save(out/'STATE.json',error);raise
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--wait',action='store_true');ap.add_argument('--preflight-only',action='store_true')
    args=ap.parse_args()
    if args.preflight_only:preflight(args.package,read(args.plan));print('incremental preflight passed')
    else:run(args)
