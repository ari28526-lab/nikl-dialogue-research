"""Finalize only after explicit human delivery-scope approval; reuse frozen audits honestly."""
import argparse,json,hashlib,os
from pathlib import Path
from datetime import datetime,timezone

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def safe(root,rel):
 p=root/rel
 if Path(rel).is_absolute() or not p.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe relative reference')
 return p
def check_approval(a,review_sha):
 if a.get('schema')!='explicit_delivery_audio_scope_approval.v1' or a.get('decision')!='approved' or a.get('approved_by')!='user':raise ValueError('Explicit human scope approval required')
 if a.get('review_sha256')!=review_sha or a.get('exceptions')!=1436 or a.get('candidate_mapping_applied') is not False:raise ValueError('Approval scope differs')
 if not a.get('user_statement') or not a.get('approved_at'):raise ValueError('Human statement and timestamp required')
def run(root,approval):
 root=root.resolve();out=root/'DELIVERY_FINAL.json'
 if out.exists():raise ValueError('Existing delivery final is immutable')
 review=root/'metadata/audio_scope_decision_v1/FINAL.json';r=read(review);a=read(approval);check_approval(a,sha(review))
 if r['status']!='technical_receipt_recheck_complete_explicit_audio_scope_decision_required':raise ValueError('Technical review incomplete')
 stage=review.parent;manifest=stage/'MANIFEST.json'
 if sha(manifest)!=r['manifest_sha256']:raise ValueError('Review manifest changed')
 files=read(manifest)['files']
 if len(files)!=r['evidence_files']:raise ValueError('Evidence count differs')
 bindings={**r['prior_receipt_sha256'],**r['receipt_sha256']}
 for rel,d in bindings.items():
  if sha(safe(root,rel))!=d:raise ValueError('Pinned completion receipt changed: '+rel)
 for entry in files:
  p=safe(stage,entry['path'])
  if p.stat().st_size!=entry['bytes'] or sha(p)!=entry['sha256']:raise ValueError('Explicit scope evidence changed')
 final=dict(schema='local_research_delivery_final.v1',status='complete_with_explicit_audio_exceptions_and_linguistic_holds',completed_at=datetime.now(timezone.utc).isoformat(),
  delivery_complete=True,full_delivery_acceptance=True,acceptance_scope='explicitly_approved_available_audio_and_complete_transcript_analysis_with_1436_audio_exceptions',
  original_audio_complete=False,global_source_absence_established=False,audio_exception_ids=1436,unapplied_mapping_candidates=400,
  scope_approval_sha256=sha(approval),scope_review_sha256=sha(review),scope_evidence_manifest_sha256=sha(manifest),finalizer_sha256=sha(Path(__file__)),
  requirements=r['requirements'],completed_receipt_sha256=bindings,payload_sha_basis=r['payload_sha_basis'],
  runtime_version_verified=False,linguistic_holds_remain=True,confirmed_corrections=0,source_modified=False,new_api_calls=0,
  note='Acceptance covers the explicitly approved delivery scope. It does not establish complete original-audio availability, candidate correctness, or a new whole-payload rehash.')
 final['requirements']=[dict(x,status='accepted_explicit_exception',basis='Explicit human scope approval and exact-ID exception catalog') if x['id']=='remaining_audio_delivery_scope' else x for x in r['requirements']]
 temp=out.with_suffix('.tmp');temp.write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,out)
 print(json.dumps(dict(status=final['status'],delivery_complete=True,original_audio_complete=False)))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--approval',type=Path,required=True);a=p.parse_args();run(a.package,a.approval)
