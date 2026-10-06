import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('f',Path(__file__).parents[1]/'scripts/python/finalize_delivery_with_explicit_scope.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Gate(unittest.TestCase):
 def valid(self):return dict(schema='explicit_delivery_audio_scope_approval.v1',decision='approved',approved_by='user',review_sha256='h',exceptions=1436,candidate_mapping_applied=False,user_statement='accepted',approved_at='time')
 def test_requires_human_approval(self):
  with self.assertRaises(ValueError):m.check_approval({},'h')
 def test_rejects_candidate_promotion_and_changed_scope(self):
  a=self.valid();a['candidate_mapping_applied']=True
  with self.assertRaises(ValueError):m.check_approval(a,'h')
  with self.assertRaises(ValueError):m.check_approval(self.valid(),'changed')
 def test_exact_scope(self):m.check_approval(self.valid(),'h')
if __name__=='__main__':unittest.main()
