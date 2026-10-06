"""Pinned recovery adapter: one bounded buffer, Windows memory telemetry.

Loads the unchanged v2 runner; changes buffer allocation only. Not a throughput
optimization or proof of the historical MemoryError cause. Single-thread only.
"""
import argparse,ctypes,hashlib,importlib.util,json,os,time
from pathlib import Path

class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in
      ['total_physical','free_physical','total_pagefile','free_pagefile','total_virtual','free_virtual','extended_virtual']]
def memory():
    m=Memory();m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise ctypes.WinError()
    return dict(physical_free=m.free_physical,commit_free=m.free_pagefile,virtual_free=m.free_virtual,load_percent=m.load)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(path):
    s=importlib.util.spec_from_file_location('frozen_v2_memory_guard',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def install(module,telemetry,sample=memory):
    arena=bytearray(module.BLOCK);last=[0]
    def provider(size):
        if size!=len(arena):raise ValueError('Unexpected allocation size')
        t=time.monotonic()
        if t-last[0]>=5:
            status=dict(pid=os.getpid(),at=module.stamp(),buffer_bytes=len(arena),memory=sample(),runtime_adapter=True)
            tmp=telemetry.with_suffix('.tmp');tmp.write_text(json.dumps(status)+'\n',encoding='utf-8');tmp.replace(telemetry)
            last[0]=t
        return arena
    module.bytearray=provider
    return arena
def main(args):
    policy=json.loads(args.guard_policy.read_text(encoding='utf-8-sig'))
    if sha(args.guard_policy)!=args.guard_policy_sha256:raise ValueError('Guard policy differs')
    for path,h in policy['pins'].items():
        if sha(path)!=h:raise ValueError('Frozen recovery pin differs')
    if str(args.output.resolve())!=str(Path(policy['package']).resolve()):raise ValueError('Package differs')
    status=memory()
    if status['commit_free']<512*1024*1024 or status['physical_free']<128*1024*1024:
        raise MemoryError('Insufficient start memory; do not retry automatically')
    if args.preflight:return dict(status='memory_guard_preflight_passed',memory=status)
    m=load(Path(policy['v2_runner']));telemetry=args.guard_policy.parent/'MEMORY_STATE.json'
    install(m,telemetry)
    m.run(argparse.Namespace(output=args.output,policy=Path(policy['v2_policy']),policy_sha256=policy['v2_policy_sha256']))
    return dict(status='underlying_v2_completed',runtime_adapter=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--guard-policy',type=Path,required=True);p.add_argument('--guard-policy-sha256',required=True);p.add_argument('--preflight',action='store_true')
    print(json.dumps(main(p.parse_args())))
