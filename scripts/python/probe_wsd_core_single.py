"""Four unused core-only requests. Separate responses; shared parent reservations."""
import argparse,json,signal,sqlite3,sys
from pathlib import Path
from research_paths import data_path, drive_root, resolve_legacy_path, qc_diagnostics
import probe_wsd_list as lp
base=lp.base
ROOT=data_path('wsd_probe')

def jobs_for(long_jobs,hydrated):
    out=[]
    for j in long_jobs[4:]:
        rows,ts=hydrated[j['id']]
        short=base.make_job(j['sid'],int(j['id'].split(':')[-1]),rows,ts,
            (j['core_start'],j['core_end'],j['core_start'],j['core_end']))
        out.append(short)
    return out

def reserve_parent(parent,job,original,allowance):
    h=base.digest(base.canonical(job));old=parent.execute('SELECT * FROM context_variant_reservations WHERE parent_id=?',(job['id'],)).fetchone()
    if old:
        if old['variant_sha']!=h or old['root']!=str(ROOT):raise ValueError('variant_binding_changed')
        return
    if parent.execute('SELECT 1 FROM attempts WHERE id=?',(job['id'],)).fetchone():raise ValueError('parent_already_attempted')
    words=len(job['text'].split())
    if base.usage(parent)['reserved_or_consumed_credit_units']+words>allowance['maximum_credit_units']:raise ValueError('budget_exceeded')
    with parent:
        parent.execute('INSERT INTO context_variant_reservations VALUES(?,?,?,?)',(job['id'],str(ROOT),h,base.packed(job)))
        parent.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (job['id'],'bareun',base.digest(base.canonical(original)),'variant_reserved',base.now(),None,None,words,words,0,0,None,None,None,base.packed(original)))
        base.event(parent,'core_variant_reserved',job['id'],'Actual short request and response are stored in the separate bound experiment root; parent payload is the original logical request.')

def main(execute=False):
    ROOT.mkdir(parents=True,exist_ok=True)
    with base.RunLock(base.OUT/'RUN.lock'):
        m,a,source,long_jobs,hydrated,prior=lp.prepare(allowed_variant_root=ROOT)
        jobs=jobs_for(long_jobs,hydrated)
        if sum(len(j['text'].split()) for j in jobs)!=215 or sum(len(j['target_ids']) for j in jobs)!=32:raise ValueError('scope_changed')
        binding={'code_sha':base.sha(__file__),'parent_code_shas':base.code_shas(),'plan_sha':m['plan_sha256'],'supplement_sha':prior['supplement_decision_sha'],'jobs':[base.digest(base.canonical(j)) for j in jobs],'mode':'core_only_single','maximum_credit_units':215}
        contract_path=ROOT/'CONTRACT.json'
        if contract_path.exists() and base.read(contract_path)!=binding:raise ValueError('experiment_contract_changed')
        parent=base.runtime(base.OUT)
        parent.execute('CREATE TABLE IF NOT EXISTS context_variant_reservations(parent_id TEXT PRIMARY KEY,root TEXT,variant_sha TEXT,payload BLOB)');parent.commit()
        for j in jobs:
            row=parent.execute('SELECT state FROM attempts WHERE id=?',(j['id'],)).fetchone()
            own=parent.execute('SELECT variant_sha FROM context_variant_reservations WHERE parent_id=?',(j['id'],)).fetchone()
            if row and not own:raise ValueError('input_already_attempted')
        preview={'status':'preflight_passed','http_calls_max':4,'words':215,'targets':32,'credit_units_reserved_max':215,'additional_purchase_krw':0,'api_called':False,'original_words':242,'original_ids':[j['id'] for j in jobs],'method':'AnalyzeSyntax','policy':'core only; NNG VV VA residual targets; no resend after unknown outcome'}
        base.atomic_json(ROOT/'PREFLIGHT.json',preview);print(json.dumps(preview),flush=True)
        if not execute:source.close();parent.close();return
        if base.stop_requested():raise ValueError('stop_requested')
        base.atomic_json(contract_path,binding);c=base.runtime(ROOT);client=base.bareun_client()
        stop=[False];old_signal=signal.signal(signal.SIGINT,lambda *_:stop.__setitem__(0,True))
        originals=base.connect_ro(base.OUT/'PLAN.sqlite')
        try:
            with base.awake():
                for j in jobs:
                    if stop[0] or (ROOT/'STOP').exists() or base.stop_requested():raise ValueError('safe_stop')
                    checked,why=base.allowance(base.OUT/'ALLOWANCE.json',m)
                    if checked!=a:raise ValueError('allowance_changed')
                    base.space_check(ROOT,50)
                    original=base.unpacked(originals.execute('SELECT payload FROM requests WHERE id=?',(j['id'],)).fetchone()[0])
                    reserve_parent(parent,j,original,a)
                    existing=c.execute('SELECT state FROM attempts WHERE id=?',(j['id'],)).fetchone()
                    if existing and existing[0]=='mapped':
                        with parent:parent.execute("UPDATE attempts SET state='variant_mapped' WHERE id=?",(j['id'],))
                        continue
                    raw=base.durable_call(c,j['id'],'bareun',j,len(j['text'].split()),len(j['text'].split()),0,client)
                    if raw is None:raise ValueError('prior_outcome_unknown_no_resend')
                    with parent:parent.execute("UPDATE attempts SET state='variant_raw_saved' WHERE id=?",(j['id'],))
                    rows,ts=hydrated[j['id']];base.map_commit(c,source,j,rows,ts,raw)
                    with parent:parent.execute("UPDATE attempts SET state='variant_mapped',finished=? WHERE id=?",(base.now(),j['id']))
                    print(json.dumps({'stage':'mapped','id':j['id'],'targets':len(ts)}),flush=True)
            result={'status':'complete','api_called':True,'attempts':[dict(r) for r in c.execute('SELECT id,state,elapsed,words,units,error FROM attempts')],'decisions':dict(c.execute('SELECT status,COUNT(*) FROM decisions GROUP BY status'))}
            base.atomic_json(ROOT/'RESULT.json',result);print(json.dumps(result),flush=True)
        except BaseException as exc:
            for r in c.execute("SELECT id,state,error,elapsed,finished FROM attempts WHERE state IN ('api_error_uncertain','calling','uncertain')"):
                with parent:parent.execute("UPDATE attempts SET state='variant_error_uncertain',error=?,elapsed=?,finished=? WHERE id=?",(r['error'],r['elapsed'],r['finished'],r['id']))
            base.atomic_json(ROOT/'STOPPED.json',{'status':'review_required','error_type':type(exc).__name__,'api_called':c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]>0,'automatic_resend':False})
            raise
        finally:signal.signal(signal.SIGINT,old_signal);originals.close();c.close();parent.close();source.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
    try:main(a.execute)
    except Exception as exc:print(json.dumps({'status':'stopped','error':str(exc) if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__}),flush=True);sys.exit(1)
