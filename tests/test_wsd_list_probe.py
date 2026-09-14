import copy,json,sqlite3,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import probe_wsd_list as probe
import run_wsd_plan_b as base
from test_wsd_plan_b import fixture


class ListProbeTests(unittest.TestCase):
    def test_post_supplement_pos_scope_preserves_text(self):
        job={'text':'unchanged dialogue','target_ids':['a','b','c','d','e']}
        targets=[{'id':'a','pos':'NNG'},{'id':'b','pos':'VV'},{'id':'c','pos':'VA'},{'id':'d','pos':'MAG'},{'id':'e','pos':'NNG'}]
        selected,ts=probe.select_remaining(job,targets,{'e'})
        self.assertEqual(selected['text'],job['text']);self.assertEqual(selected['target_ids'],['a','b','c'])
        self.assertEqual(job['target_ids'],['a','b','c','d','e'])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.c=base.runtime(self.root);probe.setup(self.c,{'test':'fixed'})
        self.source,rows,ts,job,response=fixture()
        self.jobs=[];self.hydrated={};self.raw={'sentences':[]};self.calls=0
        for i in range(4):
            j=copy.deepcopy(job);j['id']=f'b:{i}:0';j['sid']=i
            targets=copy.deepcopy(ts)
            for t in targets:t['id']=str(i)+t['id'][1:]
            j['target_ids']=[t['id'] for t in targets]
            self.jobs.append(j);self.hydrated[j['id']]=(rows,targets)
            self.raw['sentences'].append(copy.deepcopy(response['sentences'][0]))
        self.allowance={'wsd_eojeol_per_credit':10,'maximum_credit_units':100}
    def tearDown(self):self.c.close();self.source.close();self.temp.cleanup()
    def call(self,body):self.calls+=1;return self.raw
    def run_batch(self,hook=lambda p:None):
        return probe.process_batch(self.c,'batch',self.jobs,self.allowance,self.call,self.source,self.hydrated,hook)
    def crash(self,phase):
        def hook(p):
            if p==phase:raise KeyboardInterrupt()
        return hook
    def test_maps_all_targets_and_no_repeat(self):
        self.run_batch();self.assertFalse(self.run_batch());self.assertEqual(self.calls,1)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],8)
        self.assertEqual(base.usage(self.c)['reserved_or_consumed_credit_units'],4)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM attempts WHERE state='mapped'").fetchone()[0],4)
        groups=[r[0] for r in self.c.execute('SELECT selected_group FROM decisions ORDER BY target_id')]
        self.assertEqual(groups,['G1','G2']*4)
    def test_intent_crash_never_resends(self):
        with self.assertRaises(KeyboardInterrupt):self.run_batch(self.crash('after_intent'))
        with self.assertRaisesRegex(ValueError,'uncertain'):self.run_batch()
        self.assertEqual(self.calls,0);self.assertEqual(base.usage(self.c)['reserved_or_consumed_credit_units'],4)
    def test_received_before_durable_crash_never_resends(self):
        with self.assertRaises(KeyboardInterrupt):self.run_batch(self.crash('after_response_before_save'))
        with self.assertRaisesRegex(ValueError,'uncertain'):self.run_batch()
        self.assertEqual(self.calls,1)
    def test_raw_durable_resume_after_parent_recovery(self):
        with self.assertRaises(KeyboardInterrupt):self.run_batch(self.crash('after_raw_saved'))
        self.c.close();self.c=base.runtime(self.root);base.recover(self.c)
        self.run_batch();self.assertEqual(self.calls,1)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],8)
    def test_children_resume_without_resend(self):
        with self.assertRaises(KeyboardInterrupt):self.run_batch(self.crash('after_children_saved'))
        self.run_batch();self.assertEqual(self.calls,1)
    def test_wrong_count_preserves_original_raw_and_blocks(self):
        self.raw['sentences'].pop()
        with self.assertRaisesRegex(ValueError,'contract_hold'):self.run_batch()
        self.assertIsNotNone(self.c.execute('SELECT raw FROM list_probe_batches').fetchone()[0])
        with self.assertRaisesRegex(ValueError,'uncertain'):self.run_batch()
        self.assertEqual(self.calls,1);self.assertEqual(self.c.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],0)
    def test_wrong_anchor_fails(self):
        self.raw['sentences'][2]['text']['begin_offset']=6
        with self.assertRaisesRegex(ValueError,'contract_hold'):self.run_batch()
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],0)
    def test_tampered_raw_fails(self):
        with self.assertRaises(KeyboardInterrupt):self.run_batch(self.crash('after_raw_saved'))
        with self.c:self.c.execute('UPDATE list_probe_batches SET raw=?',(base.packed({}),))
        with self.assertRaisesRegex(ValueError,'sha_failed'):self.run_batch()
    def test_parent_attempt_prevents_new_call(self):
        j=self.jobs[0]
        base.durable_call(self.c,j['id'],'bareun',j,2,1,0,lambda _:self.raw)
        with self.assertRaisesRegex(ValueError,'already_attempted'):self.run_batch()
        self.assertEqual(self.calls,0)
    def test_budget_checked_before_intent(self):
        self.allowance['maximum_credit_units']=3
        with self.assertRaisesRegex(ValueError,'credit_cap'):self.run_batch()
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)
    def test_bind_change_rejected(self):
        with self.assertRaisesRegex(ValueError,'binding_changed'):probe.setup(self.c,{'test':'changed'})
    def test_one_bad_target_does_not_select_default(self):
        del self.raw['sentences'][0]['tokens'][0]['morphemes'][0]['sense']
        self.run_batch()
        self.assertEqual(self.c.execute("SELECT status,luna_eligible FROM decisions WHERE target_id='0:0:0'").fetchone()[:],('group_hold',1))


if __name__=='__main__':unittest.main()
