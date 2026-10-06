"""Bounded receipt-chain audit after relocation; never writes DELIVERY_FINAL.

Payload integrity is reused from the independent copy and add-on audits. This
component freshly hashes small receipts only, and lists unfinished acceptance
requirements instead of promoting a selected-partition check to full delivery.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import time
import traceback

STAGE = 'metadata/acceptance_evidence_v1'
MAX_BYTES = 16 * 1024 * 1024
SEM = 'metadata/semantic_links'
HIST = 'metadata/historical_textgrid_links'
GUIDE = 'metadata/guide_targets_v2'
ADDON = 'metadata/addon_integrity_v1'
REOPEN = 'metadata/reopen_queries_v1'


def fields(status, **values):
    return {('status',): status, **{tuple(k.split('.')): v for k, v in values.items()}}


# Expected production counts are explicit, not inferred from the new plan.
PROD = 'current_cloud_20260926'
SPECS = {
    'production': (PROD, 'FINAL.json', fields('complete_with_explicit_reviews',
        smoke=False, runtime_version_verified=False, requests=141991)),
    'modu_morphology': (PROD, 'modu/morphology/FINAL.json', fields('complete_with_explicit_reviews',
        smoke=False, source_files=17156, **{'counts.utterances':5103356,'counts.morphemes':51252187})),
    'modu_textgrid': (PROD, 'modu/TEXTGRID_FINAL.json', fields('passed_with_explicit_alignment_reviews',
        smoke=False, schema='alignment_only.v1', audited_textgrids=4286046, linked_utterances=5103356,
        removed_tier='morph_analysis_utt', source_modified=False,
        **{'counts.derived':4286046,'counts.no_mfa_alignment':817310})),
    'seoul_morphology': (PROD, 'seoul/COMPLETE/MORPHOLOGY_FINAL.json', fields('complete_with_explicit_reviews',
        smoke=False, recordings=240, **{'counts.utterances':59504,'counts.morphemes':400729})),
    'seoul_dictionary': (PROD, 'seoul/DICTIONARY/FINAL.json', fields('complete',
        sources=240, human_verified=False, api_called=False)),
    'modu_discourse': (PROD, 'discourse_json/modu/FINAL.json', fields('complete',
        smoke=False, api_called=False, **{'counts.discourses':17156,'counts.utterances':5157997,'counts.analyzed_utterances':5103356})),
    'seoul_discourse': (PROD, 'discourse_json/seoul/FINAL.json', fields('complete',
        smoke=False, api_called=False, **{'counts.discourses':240,'counts.utterances':128313,'counts.analyzed_utterances':59504})),
    'seoul_interviews': (PROD, 'discourse_json/seoul_interviews/FINAL.json', fields('complete',
        interviews=40, segments=240, utterance_intervals=128313, api_calls=0,
        original_metadata_order_and_local_times_preserved=True)),
    'comparison': ('comparison_current_cloud_20260928','FINAL.json',fields('mechanical_comparison_complete_review_pending',
        sample=False, api_calls=0, source_modified=False, corrections_applied=0,
        **{'counts.utterances':5103356})),
    'saved_review': ('saved_result_review_20260928','FINAL.json',fields('technical_review_complete_with_linguistic_holds',
        api_calls=0, source_modified=False, delivery_complete=False,
        **{'seoul.sample':False,'modu_gap_review.sample':False,'seoul.counts.recordings':240,
           'modu_gap_review.counts.gap_utterances':4323,'modu_gap_review.counts.gap_characters':21611})),
    'context': ('historical_context_export_20260928','FINAL.json',fields('historical_context_export_complete',
        sample=False, sources=17156, **{'counts.utterances':5103356,'counts.morphemes':51280814,'counts.json_alignment':5157997})),
    'supplement': ('historical_supplement_export_20260928','FINAL.json',fields('historical_supplement_export_complete',
        sample=False, api_calls=0, source_modified=False, **{'dependency.sources':17156})),
    'csv': ('delivery_csv_parquet_20260928','FINAL.json',fields('modu_csv_mirror_complete',
        sample=False, api_calls=0, source_modified=False)),
    'tabular': ('delivery_tabular_parquet_20260928','FINAL.json',fields('seoul_alignment_parquet_complete',
        sample=False, tables=35, rows=173195400, api_calls=0, source_modified=False)),
    'discourse_parquet': ('delivery_discourse_parquet_20260928','FINAL.json',fields('native_discourse_parquet_complete',
        sample=False, api_calls=0, source_modified=False)),
    'supplement_parquet': ('delivery_supplement_parquet_20260928','FINAL.json',fields('supplement_parquet_complete',
        sample=False, api_calls=0, source_modified=False)),
}
DYNAMIC = {
    'COPY_FINAL.json':fields('declared_scope_copied_sha_verified',files=15580294,bytes=832706074044,delivery_complete=False),
    SEM+'/FINAL.json':fields('semantic_links_complete_with_explicit_scope_gaps',sample=False,delivery_complete=False,
        **{'counts.modu_documents':17156,'counts.modu_utterances':5157997,'counts.seoul_documents':240,
           'counts.seoul_utterances':128313,'counts.seoul_interviews':40,'counts.seoul_segments':240,
           'counts.modu_derived':4286046,'counts.modu_no_mfa_alignment':817310,'counts.modu_empty_source_not_analyzed':54641}),
    HIST+'/FINAL.json':fields('historical_textgrid_links_complete',sample=False,native_utterances=5157997,
        without_historical_analysis=54641,delivery_complete=False,
        **{'counts.shards':17156,'counts.utterances':5103356,'counts.derived':4286046,'counts.no_mfa_alignment':817310}),
    GUIDE+'/FINAL.json':fields('guide_targets_verified',sample=False,bundle_files_hashed=28,examples=7,
        registered_sources=49,delivery_complete=False),
    ADDON+'/FINAL.json':fields('addon_files_sha_verified',sample=False,delivery_complete=False),
    REOPEN+'/FINAL.json':fields('bounded_reopen_queries_verified',sample=True,files=5,bytes=5929118,rows=251806,
        python_r_equal=True,physical_relocation=True,delivery_complete=False,api_calls=0,source_modified=False),
}
REMAINING = [
    dict(id='audio_scope', requirement='Finish official Modu 2021-2025 audio scope and actual PCM/WAV provenance; resolve or explicitly approve original-audio coverage.'),
    dict(id='final_guide', requirement='Create a new completed-state guide/catalog with actual receipts, version relationships and opening order; frozen v2 is unchanged.'),
    dict(id='final_integrity', requirement='Bind final guide, reopen evidence, acceptance tools and recovery provenance in a final incremental SHA manifest; existing add-on covers four roots only.'),
    dict(id='revision_regeneration', requirement='Implement and validate affected-document CSV/Parquet regeneration for separately recorded confirmed researcher revisions.'),
    dict(id='delivery_final', requirement='Evaluate all delivery requirements and create a separate DELIVERY_FINAL only after coverage and remaining acceptance checks pass.'),
]


def now(): return datetime.now(timezone.utc).isoformat()


def safe(root, relative):
    p = PurePosixPath(relative)
    if not relative or '\\' in relative or ':' in relative or p.is_absolute() or '..' in p.parts or p.as_posix()!=relative:
        raise ValueError('Unsafe relative path: '+relative)
    root=root.resolve(); target=root.joinpath(*p.parts)
    for parent in (root, *[root.joinpath(*p.parts[:i]) for i in range(1,len(p.parts)+1)]):
        if parent.is_symlink() or (parent.exists() and getattr(parent.lstat(),'st_file_attributes',0)&1024):
            raise ValueError('Reparse point')
    if target==root or not target.resolve().is_relative_to(root): raise ValueError('Escaped package')
    return target


def metadata(path, parse=True):
    before=path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_BYTES: raise ValueError('Metadata size/type limit')
    raw=path.read_bytes(); after=path.stat()
    if len(raw)>MAX_BYTES or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('Metadata changed during read')
    return (json.loads(raw.decode('utf-8-sig')) if parse else None,hashlib.sha256(raw).hexdigest())


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n'); f.flush(); os.fsync(f.fileno())
    for retry in range(10):
        try: tmp.replace(path); return
        except PermissionError:
            if retry==9: raise
            time.sleep(.2)


def check(value,expected,label):
    for keys,want in expected.items():
        actual=value
        for key in keys:
            if not isinstance(actual,dict) or key not in actual: raise ValueError(label+': missing '+'.'.join(keys))
            actual=actual[key]
        if type(actual) is not type(want) or actual!=want: raise ValueError(label+': unexpected '+'.'.join(keys))


def digest_format(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid SHA')


def validate_plan(plan):
    if plan['schema']!='delivery_acceptance_evidence.v1' or set(plan['sources'])!=set(SPECS): raise ValueError('Unexpected source plan')
    roles=plan['roles']; seen=set()
    if len(roles)!=25: raise ValueError('Expected 25 frozen copy roots')
    for dest in roles.values():
        safe(Path.cwd(),dest)
        if dest.casefold() in seen: raise ValueError('Duplicate destination')
        seen.add(dest.casefold())
    for name,(role,rel,_) in SPECS.items():
        item=plan['sources'][name]
        if item['path']!=roles[role]+'/'+rel: raise ValueError('Source mapping changed')
        digest_format(item['sha256']); safe(Path.cwd(),item['path'])
    required={'CONTRACT.json','INVENTORY.json',*[d+'/CONTRACT.json' for d in [SEM,HIST,GUIDE,ADDON,REOPEN]],
        'research_tools_v2/BUNDLE_MANIFEST.json',REOPEN+'/QUERY_PLAN.json'}
    if set(plan['frozen_metadata'])!=required: raise ValueError('Frozen metadata plan changed')
    for digest in plan['frozen_metadata'].values(): digest_format(digest)
    digest_format(plan['copy_config_sha256'])


def make_plan(config_path,root):
    config,config_sha=metadata(config_path); roles={r['role']:r['destination'] for r in config['roots']}
    sources={}
    for name,(role,rel,expected) in SPECS.items():
        entry=next(r for r in config['roots'] if r['role']==role)
        value,digest=metadata(safe(Path(entry['source']),rel)); check(value,expected,name)
        sources[name]=dict(path=roles[role]+'/'+rel,sha256=digest)
    frozen={rel:metadata(safe(root,rel))[1] for rel in
        ['CONTRACT.json','INVENTORY.json',*[d+'/CONTRACT.json' for d in [SEM,HIST,GUIDE,ADDON,REOPEN]],
         'research_tools_v2/BUNDLE_MANIFEST.json',REOPEN+'/QUERY_PLAN.json']}
    contract=metadata(root/'CONTRACT.json')[0]
    if contract['config_sha256']!=config_sha or contract['config']!=config: raise ValueError('Copy config changed')
    plan=dict(schema='delivery_acceptance_evidence.v1',created_at=now(),roles=roles,sources=sources,
        frozen_metadata=frozen,copy_config_sha256=config_sha,scope='Bounded metadata evidence, no payload scan')
    validate_plan(plan); return plan


def missing(root,plan):
    validate_plan(plan)
    return [rel for rel in DYNAMIC if not safe(root,rel).exists()]


def audit(root,plan):
    validate_plan(plan); bindings={}; values={}
    def load(rel,expected_sha=None,expected_fields=None,parse=True):
        value,digest=metadata(safe(root,rel),parse)
        if expected_sha is not None and digest!=expected_sha: raise ValueError('Receipt SHA mismatch: '+rel)
        if rel in bindings and bindings[rel]!=digest: raise ValueError('Receipt changed: '+rel)
        bindings[rel]=digest
        if expected_fields: check(value,expected_fields,rel)
        return value
    for rel,digest in plan['frozen_metadata'].items(): load(rel,digest)
    contract=load('CONTRACT.json')
    if contract['config_sha256']!=plan['copy_config_sha256']: raise ValueError('Config SHA binding changed')
    if {r['role']:r['destination'] for r in contract['config']['roots']}!=plan['roles']: raise ValueError('Copy role mapping differs')
    for name,(_,_,expected) in SPECS.items():
        item=plan['sources'][name]; values[name]=load(item['path'],item['sha256'],expected)
    for rel,expected in DYNAMIC.items(): values[rel]=load(rel,expected_fields=expected)
    copy=values['COPY_FINAL.json']; inv=load('INVENTORY.json')
    if copy.get('sample',False) is not False: raise ValueError('Copy cannot be a sample')
    check(inv,fields('source_inventory_complete',files=copy['files'],bytes=copy['bytes']),'inventory')
    if copy['inventory_sha256']!=bindings['INVENTORY.json']: raise ValueError('Inventory SHA binding differs')
    digest_format(copy['ledger_sha256'])  # Already audited by preceding full stages; no 10GB rehash here.
    artifacts=values['production']['artifacts']
    wanted={SPECS[n][1]:plan['sources'][n]['sha256'] for n in
        ['seoul_morphology','seoul_dictionary','modu_morphology','modu_textgrid','seoul_discourse','modu_discourse']}
    if len(artifacts)!=6 or {r['path']:r['sha256'] for r in artifacts}!=wanted: raise ValueError('Production six-artifact binding differs')
    for child,parent in [('supplement','context'),('csv','supplement'),('tabular','csv'),
                         ('discourse_parquet','tabular'),('supplement_parquet','discourse_parquet')]:
        expected=plan['sources'][parent]['sha256']
        actual=values[child]['dependency']['final_sha256'] if child=='supplement' else values[child]['dependency_sha256']
        if actual!=expected: raise ValueError('Source dependency binding differs: '+child)
    interviews=values['seoul_interviews']['receipts']
    if len(interviews)!=40: raise ValueError('Expected 40 interview receipts')
    base=str(PurePosixPath(plan['sources']['seoul_interviews']['path']).parent)
    for key,digest in interviews.items(): load(base+'/'+key+'.receipt.json',digest)
    hdeps=load(HIST+'/DEPENDENCIES.json')
    if hdeps!={'copy_final_sha256':bindings['COPY_FINAL.json'],'semantic_final_sha256':bindings[SEM+'/FINAL.json']}:
        raise ValueError('Historical dependencies differ')
    for stage,required in [(GUIDE,['COPY_FINAL.json',SEM+'/FINAL.json',HIST+'/FINAL.json']),
                           (ADDON,['COPY_FINAL.json',SEM+'/FINAL.json',HIST+'/FINAL.json',GUIDE+'/FINAL.json']),
                           (REOPEN,['COPY_FINAL.json',ADDON+'/FINAL.json'])]:
        if values[stage+'/FINAL.json']['dependencies']!={r:bindings[r] for r in required}:
            raise ValueError('Package dependency binding differs: '+stage)
    guide=values[GUIDE+'/FINAL.json']
    if guide['bundle_manifest_sha256']!=bindings['research_tools_v2/BUNDLE_MANIFEST.json'] or len(guide['references'])!=56:
        raise ValueError('Guide target binding differs')
    addon=values[ADDON+'/FINAL.json']
    if addon['roots']!=[SEM,HIST,GUIDE,'research_tools_v2']: raise ValueError('Unexpected add-on scope')
    for field,rel in [('manifest_sha256','SHA256_MANIFEST.jsonl'),('inventory_sha256','INVENTORY.json')]:
        load(ADDON+'/'+rel,addon[field],parse=field!='manifest_sha256')
    reopen=values[REOPEN+'/FINAL.json']
    if reopen['plan_sha256']!=bindings[REOPEN+'/QUERY_PLAN.json']: raise ValueError('Reopen plan differs')
    if set(reopen['evidence'])!={'PYTHON_QUERY.json','RELOCATED_PYTHON_QUERY.json','R_QUERY.json'}: raise ValueError('Missing query evidence')
    for rel,digest in reopen['evidence'].items(): load(REOPEN+'/'+rel,digest)
    if load(REOPEN+'/DEPENDENCIES.json')!=reopen['dependencies']: raise ValueError('Reopen dependency receipt differs')
    if reopen['contract_sha256']!=bindings[REOPEN+'/CONTRACT.json']: raise ValueError('Reopen contract differs')
    # Repeat only bounded metadata hashes, detect changes across the audit.
    for rel,digest in bindings.items():
        if metadata(safe(root,rel),False)[1]!=digest: raise ValueError('Receipt changed during audit: '+rel)
    return dict(status='receipt_chain_verified_with_remaining_acceptance',completed_at=now(),sample=False,
        receipts_hashed=len(bindings),receipt_sha256=bindings,full_delivery_acceptance=False,delivery_complete=False,
        payload_sha_basis='Reuse completed independent copy/add-on audits; no new payload or large ledger rehash.',
        reopened_scope='Five selected whole partitions, Python/R and physical relocation; not full corpus acceptance.',
        remaining_acceptance=REMAINING,linguistic_holds_remain=True,runtime_version_verified=False,
        api_calls=0,source_modified=False)


def run(args):
    import msvcrt
    root=args.package.resolve(); out=safe(root,STAGE); out.mkdir(parents=True,exist_ok=True)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            plan,plan_sha=metadata(args.plan); validate_plan(plan)
            contract=dict(schema='acceptance_evidence_contract.v1',runner_sha256=metadata(Path(__file__),False)[1],plan_sha256=plan_sha)
            cp=out/'CONTRACT.json'
            if cp.exists() and metadata(cp)[0]!=contract: raise ValueError('Frozen contract changed')
            if not cp.exists(): save(cp,contract)
            while missing(root,plan):
                if (out/'STOP').exists(): raise InterruptedError('STOP')
                for dirname in ['',SEM,HIST,GUIDE,ADDON,REOPEN]:
                    sp=safe(root,dirname+'/STATE.json' if dirname else 'STATE.json')
                    if sp.exists() and metadata(sp)[0]['status'] in ['error','failed','stopped']:
                        raise RuntimeError('Dependency stopped: '+dirname)
                save(out/'STATE.json',dict(status='waiting_for_reopen_queries',pid=os.getpid(),updated_at=now(),pending=missing(root,plan)))
                if not args.wait: return
                time.sleep(300)
            if (out/'STOP').exists(): raise InterruptedError('STOP')
            if metadata(args.plan)[1]!=plan_sha or metadata(Path(__file__),False)[1]!=contract['runner_sha256']:
                raise ValueError('Frozen tools changed while waiting')
            save(out/'STATE.json',dict(status='running',pid=os.getpid(),updated_at=now()))
            result=audit(root,plan); result.update(plan_sha256=plan_sha,contract_sha256=metadata(cp)[1])
            final=out/'FINAL.json'
            if final.exists() and metadata(final)[0]['receipt_sha256']!=result['receipt_sha256']:
                raise ValueError('Dependency changed on resume')
            save(final,result); save(out/'STATE.json',dict(status=result['status'],pid=os.getpid(),updated_at=now()))
        except Exception as exc:
            value=dict(status='stopped' if isinstance(exc,InterruptedError) else 'error',pid=os.getpid(),updated_at=now(),error=str(exc),traceback=traceback.format_exc())
            save(out/'ERROR.json',value); save(out/'STATE.json',value); raise
        finally:
            lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--plan',type=Path,required=True); ap.add_argument('--wait',action='store_true')
    ap.add_argument('--preflight-only',action='store_true')
    a=ap.parse_args()
    if a.preflight_only:
        plan=metadata(a.plan)[0]; validate_plan(plan)
        for rel,digest in plan['frozen_metadata'].items():
            if metadata(safe(a.package,rel))[1]!=digest: raise ValueError('Frozen metadata changed: '+rel)
        print(json.dumps(dict(status='preflight_passed',pending=missing(a.package,plan),delivery_complete=False)))
    else: run(a)
