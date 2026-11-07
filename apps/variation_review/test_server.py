"""Regression tests use disposable fixtures, never the user's review database."""
import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from server import Store, Problem

class ReviewTests(unittest.TestCase):
    def setUp(self):
        test_root=Path(__file__).resolve().parents[2]/'work/variation_review_tests'
        test_root.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=test_root);self.root=Path(self.tmp.name)
        cards=[dict(occurrence_id=str(i),case_id='TEST-'+str(i),question_group_id='q',provisional_pos='NNG',lemma='가상',
            token_surface='가상은',text='가상은 예시다',target_begin=0,target_end=2,content_hash='h'+str(i),source='test',document='d',alternatives={}) for i in range(2)]
        dictionary={'q':{'candidate_groups':[{'group_id':'10','entries':[{'pos':'명사'}]},{'group_id':'20','entries':[{'pos':'동사'}]}]}}
        self.dataset=self.root/'data.json';self.dataset.write_text(json.dumps(dict(cards=cards,dictionary=dictionary,scope='test')),encoding='utf-8')
        self.ledger=self.root/'ledger.jsonl';self.ledger.write_text('',encoding='utf-8')
        self.s=Store(self.dataset,self.root/'state.sqlite',self.ledger)
        self.n=0
    def tearDown(self):
        expected=Path(__file__).resolve().parents[2]/'work/variation_review_tests'
        assert self.root.resolve().parent==expected.resolve()
        self.tmp.cleanup()
    def body(self,ids=None):
        self.n+=1;ids=ids or ['0'];return dict(request_id='request-'+str(self.n),dataset_hash=self.s.dataset_hash,legacy_hash=self.s.legacy()[1],ids=ids,
            revisions={x:self.s.states().get(x,{}).get('revision',0) for x in ids},content_hashes={x:'h'+x for x in ids},
            decision=dict(status='confirmed',group_id='10',pos='NNG',morphology_confirmed=True,note='검토'),scope_note='같은 조건')
    def test_persistence_and_legacy_untouched(self):
        self.s.mutate(self.body());reopened=Store(self.dataset,self.root/'state.sqlite',self.ledger)
        self.assertEqual(reopened.states()['0']['decision']['group_id'],'10');self.assertEqual(self.ledger.read_text(),'')
    def test_idempotency(self):
        b=self.body();a=self.s.mutate(b);r=self.s.mutate(b)
        self.assertEqual(a['event_id'],r['event_id']);self.assertEqual(len(self.s.export()['events']),1)
    def test_reused_request_rejected(self):
        b=self.body();self.s.mutate(b);b['decision']['note']='different'
        with self.assertRaises(Problem):self.s.mutate(b)
    def test_revision_conflict_atomic(self):
        stale=self.body(['0','1']);self.s.mutate(self.body())
        with self.assertRaises(Problem):self.s.mutate(stale)
        self.assertNotIn('1',self.s.states())
    def test_unknown_candidate(self):
        b=self.body();b['decision']['group_id']='999'
        with self.assertRaises(Problem):self.s.mutate(b)
    def test_pos_mismatch(self):
        b=self.body();b['decision']['group_id']='20'
        with self.assertRaises(Problem):self.s.mutate(b)
    def test_morph_gate(self):
        b=self.body();b['decision']['morphology_confirmed']=False
        with self.assertRaises(Problem):self.s.mutate(b)
    def test_legacy_change_blocks(self):
        b=self.body();self.ledger.write_text('\n',encoding='utf-8')
        with self.assertRaises(Problem):self.s.mutate(b)
    def test_scoped_vs_direct(self):
        self.s.mutate(self.body(['0','1']));self.assertEqual(self.s.states()['0']['decision']['authority'],'scoped_application')
    def test_scope_required(self):
        b=self.body(['0','1']);b['scope_note']=''
        with self.assertRaises(Problem):self.s.mutate(b)
    def test_hold_keeps_no_selected_meaning(self):
        b=self.body();b['decision']['status']='held';self.s.mutate(b)
        self.assertIsNone(self.s.states()['0']['decision']['group_id'])
    def test_undo_and_history(self):
        e=self.s.mutate(self.body());b=self.body();b.update(kind='undo',event_id=e['event_id']);self.s.mutate(b)
        self.assertIsNone(self.s.states()['0']['decision']);self.assertEqual(len(self.s.export()['events']),2)
    def test_stale_undo_rejected(self):
        e=self.s.mutate(self.body());self.s.mutate(self.body());b=self.body();b.update(kind='undo',event_id=e['event_id'])
        with self.assertRaises(Problem):self.s.mutate(b)
    def test_concurrent_writers(self):
        a=self.body();b=self.body()
        def run(x):
            try:self.s.mutate(x);return 'ok'
            except Problem:return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(run,[a,b]))
        self.assertCountEqual(r,['ok','conflict'])
    def test_snapshot_content_guard(self):
        b=self.body();b['content_hashes']['0']='changed'
        with self.assertRaises(Problem):self.s.mutate(b)

    def proposal_body(self, group='10'):
        detail=self.s.detail('0')
        raw=json.dumps(dict(action='select_group',group_id=group,evidence='검토 근거',
                            requires_audio=False,requires_context=False))
        return dict(request_id='proposal-001',occurrence_id='0',dataset_hash=self.s.dataset_hash,
                    annotation_request_sha256=detail['annotation_request_sha256'],raw_output=raw)

    def test_proposal_persistence_without_judgment(self):
        body=self.proposal_body()
        result=self.s.save_proposal(body)
        self.assertEqual(result['proposal']['parse_status'],'valid')
        self.assertEqual(result['proposal']['annotation_request']['semantic_unit'],'urimalsaem_group_id')
        self.assertEqual(self.s.states(),{})
        reopened=Store(self.dataset,self.root/'state.sqlite',self.ledger)
        self.assertEqual(len(reopened.export()['model_proposals']),1)
        self.assertTrue(reopened.save_proposal(body)['replayed'])

    def test_bad_proposal_preserves_raw_output(self):
        body=self.proposal_body('not-a-candidate')
        result=self.s.save_proposal(body)
        self.assertEqual(result['proposal']['parse_status'],'invalid')
        self.assertEqual(result['proposal']['raw_output'],body['raw_output'])
        self.assertEqual(self.s.states(),{})

    def test_proposal_rejects_changed_input(self):
        body=self.proposal_body()
        body['annotation_request_sha256']='changed'
        with self.assertRaises(Problem):self.s.save_proposal(body)
        self.assertEqual(self.s.export()['model_proposals'],[])

if __name__=='__main__':unittest.main(verbosity=2)
