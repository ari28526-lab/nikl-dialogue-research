import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('overlay',Path(__file__).parents[1]/'scripts/python/finalize_pcm_supplement_evidence.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class OverlayTests(unittest.TestCase):
 def fixture(self):
  receipts=[dict(utterance_id=str(i),relative_pcm_path='audio_originals_supplement_v1/pcm/2020/'+str(i)+'.pcm',source_sha256='a'*64,destination_sha256='a'*64,independently_reopened_destination=True) for i in range(1559)]
  rows=[dict(utterance_id=str(i),pcm_supplement=receipts[i] if i<1559 else None,global_source_absence_established=False,source_pcm_absence_established=False) for i in range(2995)]
  return rows,receipts
 def test_scope_and_missing_status(self):
  rows,receipts=self.fixture();m.validate_overlay(rows,receipts)
  rows[-1]['global_source_absence_established']=True
  with self.assertRaises(ValueError):m.validate_overlay(rows,receipts)
 def test_path_escape(self):
  rows,receipts=self.fixture();receipts[0]['relative_pcm_path']='audio_originals_supplement_v1/../bad.pcm'
  with self.assertRaises(ValueError):m.validate_overlay(rows,receipts)
if __name__=='__main__':unittest.main()
