import copy
import json
import tempfile
import unittest
from pathlib import Path
from server import Store, Problem, ROOT
from portable import make_packet, import_responses, ordered_events, render

class PortableTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work/portable_review_tests';parent.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.tmp.name)
        self.dataset=self.root/'dataset.json';self.ledger=self.root/'ledger.jsonl'
        self.ledger.write_text('',encoding='utf-8')
        cards=[dict(occurrence_id=str(i),case_id='TEST-'+str(i),question_group_id='q',provisional_pos='NNG',lemma='시험',token_surface='시험은',target_surface='시험',text='시험은 가상이다',target_begin=0,target_end=2,content_hash='hash'+str(i),source='fixture',document='fiction',uid='u',context_parts=[dict(uid='u',text='시험은 가상이다')],alternatives={'before':[],'after':[]}) for i in range(3)]
        dictionary={'q':dict(candidate_groups=[dict(group_id='10',entries=[dict(pos='명사',word='시험',definition='가상 검사용')]),dict(group_id='11',entries=[dict(pos='명사',word='시험',definition='또 다른 가상 후보')])])}
        self.dataset.write_text(json.dumps(dict(cards=cards,dictionary=dictionary,scope='가상 시험',issues=[])),encoding='utf-8')
        self.store=Store(self.dataset,self.root/'reviews.sqlite',self.ledger)
        self.packet=make_packet(self.store)
        self.serial=0
    def tearDown(self):self.tmp.cleanup()
    def event(self,ids=None,parent='base',revision=0,group='10'):
        self.serial+=1;ids=ids or ['0'];eid='test-event-'+str(self.serial)
        req=dict(request_id=eid,kind='review',dataset_hash=self.packet['dataset_hash'],legacy_hash=self.packet['legacy_hash'],ids=ids,
            revisions={oid:revision for oid in ids},content_hashes={oid:'hash'+oid for oid in ids},scope_note='표시한 가상 사례만',decision=dict(status='confirmed',group_id=group,pos='NNG',morphology_confirmed=True))
        return dict(id=eid,at='2026-11-01T00:00:00Z',parents={oid:parent for oid in ids},request=req)
    def bundle(self,*events):return dict(schema='variation_portable_responses.v1',packet_id=self.packet['packet_id'],events=list(events))
    def imp(self,*events):return import_responses(self.store,self.packet,self.bundle(*events))
    def test_roundtrip_and_duplicate(self):
        e=self.event();self.assertEqual(self.imp(e)['accepted'],1);self.assertEqual(self.imp(e)['duplicates'],1)
        self.assertEqual(self.store.states()['0']['decision']['group_id'],'10');self.assertEqual(self.ledger.read_text(),'')
    def test_edit_order_and_undo(self):
        a=self.event();b=self.event(parent=a['id'],revision=1,group='11')
        u=self.event(parent=b['id'],revision=2);u['request'].update(kind='undo',event_id=b['id'])
        self.imp(u,b,a)
        self.assertEqual(self.store.states()['0']['decision']['group_id'],'10')
        self.assertEqual(self.store.states()['0']['revision'],3)
    def test_fork_rolls_back_entire_bundle(self):
        a=self.event();b=self.event(group='11');other=self.event(['1'])
        with self.assertRaises(ValueError):self.imp(a,other,b)
        self.assertEqual(self.store.states(),{});self.assertEqual(len(self.store.export()['events']),0)
    def test_local_edit_conflict(self):
        a=self.event();self.store.mutate(self.event(group='11')['request'])
        with self.assertRaises(ValueError):self.imp(a)
        self.assertEqual(self.store.states()['0']['decision']['group_id'],'11')
    def test_missing_parent(self):
        with self.assertRaises(ValueError):self.imp(self.event(parent='missing-event'))
    def test_uuid_collision_rejected(self):
        e=self.event();self.imp(e);bad=copy.deepcopy(e);bad['request']['decision']['note']='changed'
        with self.assertRaises(ValueError):self.imp(bad)
    def test_invalid_candidate_atomic(self):
        with self.assertRaises(Problem):self.imp(self.event(['0','1'],group='bad'))
        self.assertFalse(self.store.states())
    def test_morph_not_confirmed(self):
        e=self.event();e['request']['decision']['morphology_confirmed']=False
        with self.assertRaises(Problem):self.imp(e)
    def test_scoped_authority(self):
        self.imp(self.event(['0','1']));self.assertEqual(self.store.states()['1']['decision']['authority'],'scoped_application')
    def test_changed_legacy(self):
        self.ledger.write_text('\n')
        with self.assertRaises(ValueError):self.imp(self.event())
    def test_tampered_packet(self):
        self.packet['base_states']['0']['revision']=77
        with self.assertRaises(ValueError):self.imp(self.event())
    def test_independent_pc_union(self):
        a=self.event(['0']);b=self.event(['1']);self.imp(a);self.imp(a,b)
        self.assertEqual(len(self.store.states()),2)
    def test_reimport_after_local_edit_does_not_revert(self):
        a=self.event();self.imp(a);b=self.event(revision=1,group='11');self.store.mutate(b['request'])
        self.assertEqual(self.imp(a)['duplicates'],1);self.assertEqual(self.store.states()['0']['decision']['group_id'],'11')
    def test_stale_undo_rejected(self):
        a=self.event();b=self.event(parent=a['id'],revision=1,group='11');u=self.event(parent=b['id'],revision=2)
        u['request'].update(kind='undo',event_id=a['id'])
        with self.assertRaises(ValueError):self.imp(a,b,u)
        self.assertFalse(self.store.states())
    def test_html_escapes_corpus_script(self):
        self.packet['details']['0']['card']['text']='</script><script>alert(1)</script>'
        h=render(self.packet);self.assertNotIn('</script><script>alert(1)',h)
        self.assertIn('connect-src',h);self.assertNotIn('src="/app.js"',h)

if __name__=='__main__':unittest.main(verbosity=2)
