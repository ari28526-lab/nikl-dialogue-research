import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('resolver',Path(__file__).parents[1]/'scripts/python/resolve_delivery_pcm_supplement.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ResolverTests(unittest.TestCase):
 def setup_root(self,root,path='audio_originals_supplement_v1/pcm/2020/clip.pcm'):
  stage=root/'metadata/original_pcm_supplement_v1';stage.mkdir(parents=True)
  row=dict(utterance_id='known',alignment_status='no_mfa_alignment',analysis_status='response_saved',original_text_empty=False,source_json='source.json',pcm_supplement=dict(relative_pcm_path=path,bytes=4,destination_sha256=hashlib.sha256(b'clip').hexdigest()))
  missing=dict(row,utterance_id='missing',pcm_supplement=None)
  index=stage/'ORIGINAL_AUDIO_LINKS.jsonl';index.write_text('\n'.join(json.dumps(x) for x in [row,missing])+'\n',encoding='utf-8')
  (stage/'FINAL.json').write_text(json.dumps(dict(status='confirmed_original_pcm_supplement_copied_sha_verified',evidence_sha256={'ORIGINAL_AUDIO_LINKS.jsonl':m.sha(index)})),encoding='utf-8')
 def test_relocated_root_and_tamper(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.setup_root(root);audio=root/'audio_originals_supplement_v1/pcm/2020/clip.pcm';audio.parent.mkdir(parents=True);audio.write_bytes(b'clip')
   result=m.resolve_original_pcm(root,'known',True);self.assertEqual(result['path'],str(audio));self.assertFalse(result['time_coordinates_inferred'])
   audio.write_bytes(b'bad!')
   with self.assertRaises(ValueError):m.resolve_original_pcm(root,'known',True)
 def test_missing_not_global_absence(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.setup_root(root)
   self.assertFalse(m.resolve_original_pcm(root,'missing')['source_absence_established'])
   self.assertEqual(m.resolve_original_pcm(root,'other')['status'],'not_in_supplement_scope')
 def test_path_escape(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.setup_root(root,'audio_originals_supplement_v1/../bad.pcm')
   with self.assertRaises(ValueError):m.resolve_original_pcm(root,'known')
if __name__=='__main__':unittest.main()
