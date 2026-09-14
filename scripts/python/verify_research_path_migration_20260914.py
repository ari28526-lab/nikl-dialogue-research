"""Read-only dependency equivalence audit before and after relocation."""
import argparse,hashlib,json,sqlite3,sys
from pathlib import Path
import research_paths as rp
ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'outputs/reports/research_path_migration_20260914'
a=argparse.ArgumentParser();a.add_argument('--source',action='store_true');args=a.parse_args()
cfg=rp.catalog()
if args.source:
    for entry in cfg['locations'].values():entry['path']=entry['legacy']
    rp.catalog=lambda:cfg
bindings=rp.verify_bindings()
import run_seoul_koina_clock_v2 as clock
import pilot_seoul_boundaries as boundaries
assert clock.PILOT==rp.data_path('koina_clock') and clock.OLD==rp.data_path('koina_v1')
receipts=json.loads((rp.drive_root()/'40_SEOUL_CORPUS/52_KOINA_FULL_V2_20260911/FINAL.json').read_text(encoding='utf-8-sig'))
def records(obj):
    if isinstance(obj,dict):
        if 'result_directory' in obj and 'artifacts' in obj:yield obj
        else:
            for value in obj.values():yield from records(value)
    elif isinstance(obj,list):
        for value in obj:yield from records(value)
checked=[]
for record in records(receipts):
    path=boundaries.winpath(record['result_directory'])
    f0=next(x for x in record['artifacts'] if x['name']=='f0_frames.csv')
    p=path/'f0_frames.csv'
    with p.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    assert actual==f0['sha256'] and p.stat().st_size==f0['bytes']
    checked.append(record.get('source_file',path.name))
assert len(checked)==240, len(checked)
for sid in clock.SOURCES:clock.verify_result(rp.data_path('koina_clock')/sid)
qc=sum(len(rp.qc_diagnostics(sid)) for sid in cfg['locations']['koina_qc']['diagnostic_files'])
assert qc>0
probe=rp.data_path('wsd_probe')/'RUN.sqlite'
c=sqlite3.connect(probe.as_uri()+'?mode=ro',uri=True)
try:probe_count=c.execute("SELECT count(*) FROM decisions WHERE status='bareun_group_resolved'").fetchone()[0]
finally:c.close()
result=dict(status='passed_read_only_dependency_audit',mode='source' if args.source else 'relocated',locations=bindings,koina_full_f0_verified=len(checked),koina_reused_pilot_recordings=len(clock.SOURCES),qc_diagnostic_files=qc,wsd_reused_decisions=probe_count,api_called=False,production_restarted=False)
(REPORT/('VERIFY_SOURCE.json' if args.source else 'VERIFY_RELOCATED.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='locations'}))
