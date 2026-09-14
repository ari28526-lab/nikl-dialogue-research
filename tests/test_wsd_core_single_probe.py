import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import probe_wsd_core_single as p
from test_wsd_plan_b import fixture

class CoreProbe(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.c=p.base.runtime(Path(self.tmp.name))
        self.c.execute('CREATE TABLE context_variant_reservations(parent_id TEXT PRIMARY KEY,root TEXT,variant_sha TEXT,payload BLOB)')
        self.source,self.rows,self.ts,self.job,self.response=fixture()
    def tearDown(self):self.c.close();self.source.close();self.tmp.cleanup()
    def test_reservation_reused_and_blocks_old_runner(self):
        a={'maximum_credit_units':100}
        p.reserve_parent(self.c,self.job,self.job,a);p.reserve_parent(self.c,self.job,self.job,a)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],1)
        self.assertEqual(self.c.execute('SELECT state FROM attempts').fetchone()[0],'variant_reserved')
        changed=dict(self.job,text='different')
        with self.assertRaisesRegex(ValueError,'binding_changed'):p.reserve_parent(self.c,changed,self.job,a)
    def test_cap_before_reserving(self):
        with self.assertRaisesRegex(ValueError,'budget'):p.reserve_parent(self.c,self.job,self.job,{'maximum_credit_units':0})
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)
    def test_existing_regular_attempt_blocks_variant(self):
        p.base.durable_call(self.c,self.job['id'],'bareun',self.job,2,2,0,lambda _:self.response)
        with self.assertRaisesRegex(ValueError,'already_attempted'):p.reserve_parent(self.c,self.job,self.job,{'maximum_credit_units':100})

if __name__=='__main__':unittest.main()
