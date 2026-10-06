"""Pinned sequential small-file audit gate; does not scan corpus payloads."""
import argparse,hashlib,importlib.util,json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');t.replace(p)
def main(a):
 c=json.loads(a.contract.read_text(encoding='utf-8-sig'))
 if sha(a.contract)!=a.contract_sha256:raise ValueError('Gate contract changed')
 for p,h in c['pins'].items():
  if sha(Path(p))!=h:raise ValueError('Pinned code/plan changed')
 root=Path(c['package']);plan=json.loads(Path(c['plan']).read_text(encoding='utf-8-sig'))
 sys.path.insert(0,str(Path(c['runner']).parent))
 spec=importlib.util.spec_from_file_location('pinned_supplement_gate',c['runner']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.validate(plan)
 out=Path(c['output']);control=a.contract.parent
 def pending():return [x['path'] for x in plan['dependencies'] if not (root/x['path']).exists()]
 if a.preflight:return dict(status='gate_preflight_passed',pending=pending(),files=len(plan['files']))
 import msvcrt
 with (control/'PROCESS.lock').open('a+b') as lock:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  try:
   while pending():
    dep=root/'metadata/final_incremental_integrity_v1/STATE.json'
    if dep.exists() and json.loads(dep.read_text()).get('status') in {'error','stopped','failed'}:raise ValueError('Final incremental dependency stopped; diagnose')
    save(control/'STATE.json',dict(status='waiting_for_final_incremental',pid=os.getpid(),updated_at=datetime.now(timezone.utc).isoformat(),pending=pending()))
    time.sleep(60)
   for p,h in c['pins'].items():
    if sha(Path(p))!=h:raise ValueError('Pinned input changed during wait')
   save(control/'STATE.json',dict(status='running',pid=os.getpid(),phase='explicit_small_file_sha'))
   result=m.audit(root,plan,out);m.verify_receipt(root,plan,out)
   save(control/'FINAL.json',dict(status='explicit_supplement_and_consumer_verified',receipt_sha256=sha(out/'FINAL.json'),files=len(result['files']),delivery_complete=False))
   save(control/'STATE.json',dict(status='explicit_supplement_and_consumer_verified',pid=os.getpid(),delivery_complete=False))
  except BaseException as e:
   save(control/'ERROR.json',dict(status='error',pid=os.getpid(),error=str(e)));save(control/'STATE.json',dict(status='error',pid=os.getpid(),error=str(e)));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--contract',type=Path,required=True);p.add_argument('--contract-sha256',required=True);p.add_argument('--preflight',action='store_true');print(json.dumps(main(p.parse_args())))
