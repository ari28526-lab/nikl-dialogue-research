"""Resolve the additive original-PCM index without changing frozen base links."""
import hashlib,json
from pathlib import Path

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(65536),b''):h.update(block)
 return h.hexdigest()

def resolve_original_pcm(package_root,utterance_id,verify=False):
 root=Path(package_root);stage=root/'metadata/original_pcm_supplement_v1'
 final=json.loads((stage/'FINAL.json').read_text(encoding='utf-8'))
 if final['status']!='confirmed_original_pcm_supplement_copied_sha_verified':raise ValueError('PCM supplement incomplete')
 index=stage/'ORIGINAL_AUDIO_LINKS.jsonl'
 if sha(index)!=final['evidence_sha256']['ORIGINAL_AUDIO_LINKS.jsonl']:raise ValueError('PCM overlay changed')
 matches=[]
 with index.open(encoding='utf-8') as f:
  for line in f:
   row=json.loads(line)
   if row['utterance_id']==utterance_id:matches.append(row)
 if not matches:return dict(utterance_id=utterance_id,status='not_in_supplement_scope',source_absence_established=False)
 if len(matches)!=1:raise ValueError('Duplicate supplemental identity')
 row=matches[0];record=row['pcm_supplement']
 if record is None:return dict(utterance_id=utterance_id,status='not_found_in_checked_roots',source_absence_established=False,alignment_status=row['alignment_status'])
 rel=Path(record['relative_pcm_path'])
 if rel.is_absolute() or '..' in rel.parts or rel.parts[0]!='audio_originals_supplement_v1':raise ValueError('Unsafe relative PCM path')
 target=root/rel
 if not target.is_file():raise FileNotFoundError('Confirmed PCM is missing from this package root')
 if verify and (sha(target)!=record['destination_sha256'] or target.stat().st_size!=record['bytes']):raise ValueError('PCM payload changed')
 return dict(utterance_id=utterance_id,status='confirmed_original_pcm_supplement',path=str(target),relative_pcm_path=rel.as_posix(),
  bytes=record['bytes'],sha256=record['destination_sha256'],verified_now=verify,
  alignment_status=row['alignment_status'],analysis_status=row['analysis_status'],
  original_text_empty=row['original_text_empty'],source_json=row['source_json'],
  raw_audio_format='original PCM; consult the year-specific official guide',time_coordinates_inferred=False)
