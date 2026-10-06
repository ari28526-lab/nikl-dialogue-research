import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('audit',Path(__file__).parents[1]/'scripts/python/reconcile_delivery_audio_prior_approvals.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class TestScope(unittest.TestCase):
 def test_scope_not_promoted(self):
  g=dict(year='2020',utterance_id='u',discourse_id='d',source_json='x',source_json_sha256='h')
  row=m.reconcile([g],{('2020','u'):dict(reason_code='audio_pairing_unresolved',exclusion_scope='alignment_and_analysis')})[0]
  self.assertTrue(row['prior_approval_found']);self.assertFalse(row['delivery_audio_exception_approved']);self.assertFalse(row['global_source_absence_established'])
 def test_year_exact_and_unmatched_preserved(self):
  g=dict(year='2023',utterance_id='u',discourse_id='d',source_json='x',source_json_sha256='h')
  self.assertFalse(m.reconcile([g],{('2020','u'): {}})[0]['prior_approval_found'])
if __name__=='__main__':unittest.main()
