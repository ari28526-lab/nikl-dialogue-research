import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('progress',Path(__file__).parents[1]/'scripts/python/summarize_delivery_copy_recovery.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.prior=dict(pid=10,files=1000,bytes=100000,total_files=3000,total_bytes=500000,updated_at='2026-10-01T00:00:00+00:00')

    def test_stale_state_is_not_new_runner_progress(self):
        x=m.summarize(self.prior,20,self.prior)
        self.assertIsNone(x['current_pass']);self.assertIsNone(x['interval'])
        self.assertFalse(x['recorded_checkpoint_is_freshly_revalidated'])

    def test_counter_reset_keeps_recorded_checkpoint_separate(self):
        current=dict(self.prior,pid=20,files=25,bytes=2500)
        x=m.summarize(current,20,self.prior,self.prior)
        self.assertEqual(x['recorded_pre_shutdown_checkpoint']['files'],1000)
        self.assertEqual(x['current_pass']['files'],25)
        self.assertIsNone(x['interval'])
        self.assertFalse(x['recorded_checkpoint_is_freshly_revalidated'])

    def test_prefix_revalidated_still_not_full_delivery(self):
        current=dict(self.prior,pid=20,files=1200,bytes=120000)
        x=m.summarize(current,20,self.prior)
        self.assertTrue(x['recorded_checkpoint_is_freshly_revalidated'])
        self.assertFalse(x['delivery_complete']);self.assertIsNone(x['whole_copy_eta_hours'])

    def test_short_sample_and_changed_scope_rejected(self):
        old=dict(self.prior,pid=20,files=25,bytes=2500)
        new=dict(old,files=50,bytes=5000,updated_at='2026-10-01T00:05:00+00:00')
        self.assertIsNone(m.summarize(new,20,self.prior,old)['interval'])
        new['total_files']=3001
        with self.assertRaises(ValueError):m.summarize(new,20,self.prior)


if __name__=='__main__':unittest.main()
