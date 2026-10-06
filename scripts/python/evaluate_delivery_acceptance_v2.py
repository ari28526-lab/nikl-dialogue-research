"""Automatic receipt acceptance after gap accounting; never hides audio holds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import audit_delivery_acceptance_evidence as prior
import update_delivery_revision as io


def evaluate(root,plan):
    root=Path(root).resolve()
    old_path=io.safe(root,plan['prior_plan'])
    if io.sha(old_path)!=plan['prior_plan_sha256']:raise ValueError('Previous acceptance plan changed')
    old=prior.audit(root,io.read(old_path))
    bindings={};values={}
    for rel,digest in plan['pinned_receipts'].items():
        value,current=prior.metadata(prior.safe(root,rel))
        if current!=digest:raise ValueError('Pinned completion receipt changed: '+rel)
        bindings[rel]=current;values[rel]=value
    for rel in plan['tool_manifests']:
        manifest,current=prior.metadata(prior.safe(root,rel));bindings[rel]=current
        for f in manifest['files']:
            logical=(Path(rel).parent/f['path']).as_posix();path=prior.safe(root,logical)
            _,sha=prior.metadata(path,False)
            if path.stat().st_size!=f['bytes'] or sha!=f['sha256']:raise ValueError('Registered tool/guide changed')
            bindings[logical]=sha
    for rel,digest in plan['explicit_provenance'].items():
        _,sha=prior.metadata(prior.safe(root,rel),False)
        if sha!=digest:raise ValueError('Fixed recovery/new provenance changed')
        bindings[rel]=sha
    gap_path=plan['gap_receipt'];gap,sha=prior.metadata(prior.safe(root,gap_path));bindings[gap_path]=sha
    if gap['status']!='declared_clip_gap_accounting_complete_source_presence_unverified' or gap['missing_clips']!=2995 or gap['documents']!=17156 or gap['utterances']!=5157997:
        raise ValueError('Full missing-clip accounting differs')
    listing=(Path(gap_path).parent/'MISSING_CLIPS.jsonl').as_posix()
    _,sha=prior.metadata(prior.safe(root,listing),False)
    if sha!=gap['listing_sha256']:raise ValueError('Missing clip listing changed')
    bindings[listing]=sha
    # Current evidence is partial: no workflow state may silently override it.
    requirements=[dict(id='production_history_tables_links',status='verified',basis=old['status']),
        dict(id='guides_and_revision_tools',status='verified',basis='Explicit bundle manifests and relocated synthetic query evidence'),
        dict(id='missing_clip_accounting',status='verified',basis=gap['status']),
        dict(id='new_runtime_provenance',status='verified',basis='Direct small-file SHA bindings; previous component payload audits reused'),
        dict(id='official_audio_scope_2021_2025',status='unresolved',basis='2021 source directory timed out; later directories not retried'),
        dict(id='source_PCM_coverage_and_missing_clip_explanation',status='unresolved',basis='Stored gaps classified; source-drive presence not established')]
    for rel,digest in bindings.items():
        if prior.metadata(prior.safe(root,rel),False)[1]!=digest:raise ValueError('Acceptance input changed during evaluation')
    return dict(schema='delivery_acceptance_evaluation.v2',status='technical_evidence_evaluated_audio_scope_pending',
        completed_at=io.now(),requirements=requirements,gap_counts=gap['counts'],missing_empty_text=gap['missing_empty_text'],
        receipt_sha256=bindings,prior_receipt_sha256=old['receipt_sha256'],
        full_delivery_acceptance=False,delivery_complete=False,DELIVERY_FINAL_created=False,
        payload_integrity_basis='Reuse completed independent copy/SHA and committed SHA reuse receipts; no full payload rehash',
        reopened_scope='Existing selected-partition relocation and synthetic revision tests; no new full physical copy',
        runtime_version_verified=False,linguistic_holds_remain=True,api_calls=0,source_modified=False,
        next_step='Resolve source audio scope/presence evidence or obtain an explicit documented scope decision before DELIVERY_FINAL')


def run(root,plan_path,out,wait=False):
    import msvcrt
    root=Path(root).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    plan=io.read(plan_path);plan_sha=io.sha(plan_path)
    contract=dict(schema='delivery_acceptance_evaluation_contract.v2',runner_sha256=io.sha(Path(__file__)),plan_sha256=plan_sha)
    cp=out/'CONTRACT.json'
    if cp.exists() and io.read(cp)!=contract:raise ValueError('Acceptance evaluation contract changed')
    io.save(cp,contract)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            gap=io.safe(root,plan['gap_receipt'])
            while not gap.exists():
                if (gap.parent/'ERROR.json').exists():raise RuntimeError('Gap accounting failed; investigate, do not restart')
                io.save(out/'STATE.json',dict(status='waiting_for_clip_accounting',pid=os.getpid(),updated_at=io.now(),delivery_complete=False))
                if not wait:return
                time.sleep(30)
            if io.sha(plan_path)!=plan_sha or io.sha(Path(__file__))!=contract['runner_sha256']:raise ValueError('Frozen evaluation inputs changed while waiting')
            result=evaluate(root,plan);io.save(out/'FINAL.json',result)
            io.save(out/'STATE.json',dict(status=result['status'],pid=os.getpid(),updated_at=io.now(),delivery_complete=False))
        except Exception as e:
            io.save(out/'ERROR.json',dict(status='error',pid=os.getpid(),updated_at=io.now(),error=str(e)));raise
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--wait',action='store_true');a=p.parse_args();run(a.package,a.plan,a.output,a.wait)
