"""Join only identified audio gaps to frozen researcher approvals, without promoting scope."""
import argparse, csv, hashlib, json
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(65536),b''): h.update(b)
    return h.hexdigest()

def reconcile(gaps, approved):
    result=[]
    for x in gaps:
        key=(str(x['year']),x['utterance_id'])
        a=approved.get(key)
        result.append(dict(year=key[0],utterance_id=key[1],discourse_id=x['discourse_id'],
            prior_approval_found=a is not None,
            prior_reason=a['reason_code'] if a else None,
            prior_scope=a['exclusion_scope'] if a else None,
            source_json=x['source_json'], source_json_sha256=x['source_json_sha256'],
            audio_available=False, global_source_absence_established=False,
            delivery_audio_exception_approved=False,
            classification='previously_approved_alignment_exception_audio_still_unavailable' if a else 'audio_identity_pending'))
    return result

def run(project, package, output):
    output.mkdir(parents=True,exist_ok=True)
    if (output/'FINAL.json').exists():raise ValueError('Completed output is immutable')
    overlay=package/'metadata/original_pcm_supplement_v1/ORIGINAL_AUDIO_LINKS.jsonl'
    if digest(overlay)!='ca961f4f2046d04a5c1ea985cadf700de7576554c6a9abb98d4673008683b80e':raise ValueError('Overlay differs')
    gaps=[x for x in map(json.loads,overlay.read_text(encoding='utf-8').splitlines()) if x['pcm_supplement'] is None]
    if len(gaps)!=1436 or len({x['utterance_id'] for x in gaps})!=1436:raise ValueError('Gap set differs')
    paths={
      '2020':'outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_2020_20260801/2020',
      '2023':'outputs/reviews/mfa_exclusions_queue_mfa_r2_prod_safe_body_2021_2025_20260803/2023'}
    wanted={(str(x['year']),x['utterance_id']) for x in gaps};approved={};sources=[]
    for year,rel in paths.items():
        folder=project/rel;ap=folder/'04_RESEARCHER_APPROVAL.json';a=json.loads(ap.read_text(encoding='utf-8-sig'))
        if a['status']!='approved' or a['year']!=year or a['approved_by']!='ari30':raise ValueError('Approval identity differs')
        cp=folder/'04_RESEARCHER_APPROVED.csv'
        if cp.stat().st_size>32*1024*1024 or digest(cp)!=a['approved_csv']['sha256']:raise ValueError('Frozen approved CSV differs')
        n=0
        with cp.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                n+=1;k=(row['year'],row['utt_id'])
                if k not in wanted:continue
                if k in approved or row['decision']!='approved' or row['input_contract_id']!=a['input_contract_id']:raise ValueError('Duplicate or invalid approval')
                approved[k]=row
        if n!=a['approved_row_count']:raise ValueError('Approval row count differs')
        sources.extend([dict(path=ap.relative_to(project).as_posix(),sha256=digest(ap)),dict(path=cp.relative_to(project).as_posix(),sha256=digest(cp),rows=n)])
    rows=reconcile(gaps,approved)
    def save(name,obj):(output/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save('EXACT_ID_RECONCILIATION.json',rows)
    final=dict(status='prior_approval_exact_id_reconciled_audio_delivery_scope_not_promoted',completed_at=datetime.now(timezone.utc).isoformat(),
      ids=len(rows),matched=sum(x['prior_approval_found'] for x in rows),
      classifications=dict(Counter(x['classification'] for x in rows)),
      reasons=dict(Counter(str(x['prior_reason']) for x in rows)),sources=sources,
      reconciliation_sha256=digest(output/'EXACT_ID_RECONCILIATION.json'),overlay_sha256=digest(overlay),runner_sha256=digest(Path(__file__)),
      original_audio_modified=False,global_source_absence_established=False,delivery_complete=False,
      limitation='Prior approval covers alignment_and_analysis only; this is not approval to declare full original-audio delivery.',
      next_step='Bind version-specific source absence evidence and distinguish recoverable remaps from documented unavailable audio before final acceptance.')
    save('FINAL.json',final)
    print(json.dumps({k:final[k] for k in ['status','ids','matched','classifications','reasons']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,default=Path.cwd());p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.project,a.package,a.output)
