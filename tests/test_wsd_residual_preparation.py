import json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts/python'));sys.path.insert(0,str(ROOT/'tests'))
import prepare_wsd_residual as prep
import apply_context_dictionary_full as app
from test_context_dictionary_application import fixture,FakeDictionary

CFG={'core_characters':10,'core_utterances':2,'targets_per_request':2,'context_before':1,'context_after':1}

class WithCandidates(FakeDictionary):
    def decide(self,v,m,previous):return {'status':'context_hold','selected_group':None,'candidate_groups':['1','2']}

class Tests(unittest.TestCase):
    def setUp(self):
        p=ROOT/'work/wsd_residual_20260909/tests';p.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=p);self.root=Path(self.tmp.name)
        assert self.root.resolve().is_relative_to(p.resolve())
    def tearDown(self):self.tmp.cleanup()
    def contexts(self):
        return [{'ordinal':i,'document_id':'a' if i<4 else 'b','utt_id':str(i),'raw':{'form':'문맥' if i!=2 else '', 'speaker_id':'s'}} for i in range(7)]
    def test_windows_preserve_targets_and_boundaries(self):
        targets=[{'utterance_ordinal':i,'row_ordinal':0,'json_ordinal':i} for i in (0,3,4,6)]
        contexts=self.contexts();requests,_=prep.plan_requests(contexts,targets,CFG)
        self.assertEqual(sum(len(r['target_keys']) for r in requests),4)
        for r in requests:
            self.assertTrue(all(u['document_id']==r['document_id'] for u in contexts[r['context_start']:r['context_end']]))
            self.assertLessEqual(len(r['target_keys']),2)
    def test_single_long_utterance_splits_targets_without_truncating_context(self):
        contexts=self.contexts();contexts[0]['raw']['form']='말'*1000
        targets=[{'utterance_ordinal':0,'row_ordinal':i,'json_ordinal':0} for i in range(5)]
        requests,_=prep.plan_requests(contexts,targets,CFG)
        self.assertEqual([len(r['target_keys']) for r in requests],[2,2,1])
        self.assertTrue(all(r['context_characters']>=1000 for r in requests))
    def test_no_target_no_request_but_context_not_mutated(self):
        contexts=self.contexts();before=json.dumps(contexts);r,n=prep.plan_requests(contexts,[],CFG)
        self.assertEqual(r,[]);self.assertGreater(n,0);self.assertEqual(json.dumps(contexts),before)
    def source_fixture(self):
        src,ref,jp=fixture(self.root)
        # Match original speaker metadata to existing morphology.
        raw=app.read(jp)
        for d in raw['document']:
            for u in d['utterance']:u['speaker_id']='p'
        app.atomic_json(jp,raw);ref['json_binding']['json_sha256']=app.sha(jp)
        dest=self.root/'application/files/year/source';app.apply_one(src,dest,ref,'source_contract',WithCandidates(),json_path=jp)
        ref['relative']='files/year/source/RECEIPT.json'
        cfg={**CFG,'application_root':str(self.root/'application'),'json_root':str(self.root)}
        contract={'application_contract_sha256':'source_contract'}
        return dest,ref,cfg,contract
    def lookup(self,lemma,pos):return [{'group':'1','definition':'첫째'},{'group':'2','definition':'둘째'}]
    def test_source_audit_build_render_and_rollback(self):
        dest,ref,cfg,contract=self.source_fixture();c=prep.open_output(self.root/'prepared.sqlite',contract)
        def crash(stage,*_):
            if stage=='target':raise RuntimeError('simulated interruption')
        try:
            with self.assertRaisesRegex(RuntimeError,'interruption'):prep.prepare_source(c,0,ref,app.sha(dest/'RECEIPT.json'),cfg,contract,self.lookup,hook=crash)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM sources').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM targets').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM contexts').fetchone()[0],0)
            result=prep.prepare_source(c,0,ref,app.sha(dest/'RECEIPT.json'),cfg,contract,self.lookup)
            self.assertEqual(result['json_utterances'],8);self.assertEqual(result['wsd_targets'],6)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM contexts WHERE analysis_ordinal IS NULL').fetchone()[0],1)
        finally:c.close()
        rendered=prep.render_request(self.root/'prepared.sqlite',0,0)
        self.assertGreater(len(rendered['context']),0);self.assertEqual(rendered['targets'][0]['candidate_groups'],['1','2'])
        self.assertFalse(rendered['api_called'])
    def test_source_sha_corruption_rejected(self):
        dest,ref,cfg,contract=self.source_fixture()
        with (dest/'APPLICATION.sqlite').open('ab') as f:f.write(b'bad')
        c=prep.open_output(self.root/'prepared.sqlite',contract)
        try:
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):prep.prepare_source(c,0,ref,app.sha(dest/'RECEIPT.json'),cfg,contract,self.lookup)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM sources').fetchone()[0],0)
        finally:c.close()
    def test_changed_dictionary_groups_rejected(self):
        dest,ref,cfg,contract=self.source_fixture();c=prep.open_output(self.root/'prepared.sqlite',contract)
        try:
            with self.assertRaisesRegex(ValueError,'candidate set differs'):prep.prepare_source(c,0,ref,app.sha(dest/'RECEIPT.json'),cfg,contract,lambda *_:[{'group':'1'}])
        finally:c.close()
    def test_resume_contract_guard(self):
        db=self.root/'prepared.sqlite';prep.open_output(db,{'v':1}).close()
        with self.assertRaisesRegex(ValueError,'contract changed'):prep.open_output(db,{'v':2})

if __name__=='__main__':unittest.main()
