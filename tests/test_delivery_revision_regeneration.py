import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import regenerate_delivery_revision_tables as m
import update_delivery_revision as u

class RegenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.root=self.base/'package';self.root.mkdir()
        u.save(self.root/'COPY_FINAL.json',dict(status='declared_scope_copied_sha_verified'))
        self.doc=dict(discourse_id='d1',metadata={'unknown':None},utterances=[
          dict(utterance_id='u1',turn_order=1,original=dict(form='',speaker_id=None,start=0,end=1),analysis=dict(status='not_analyzed',morphemes=[])),
          dict(utterance_id='u2',turn_order=2,original=dict(form='한글',speaker_id='s1',start=None,end=None),analysis=dict(status='complete',morphemes=[{'lemma':'한국어','sense':None}]))])
        physical='updates/revisions/r1/files/analysis/d1.json';p=self.root/physical;u.save(p,self.doc)
        self.entry=dict(logical_path='analysis/d1.json',physical_path=physical,bytes=p.stat().st_size,sha256=u.sha(p))
        rp=self.root/'updates/revisions/r1/REVISION.json'
        u.save(rp,dict(status='complete',revision='r1',parent=None,parent_sha256=None,base_final_sha256=u.sha(self.root/'COPY_FINAL.json'),changed_files=[self.entry],affected_documents=['d1']))
        self.plan=dict(schema='delivery_regeneration.v1',selected_revision='r1',output_revision='r1_tables',revision_manifest_sha256=u.sha(rp),affected_documents=['d1'],
          documents=[dict(logical_path='analysis/d1.json',corpus='modu',analysis_version='bareun_3.2',year='2020',discourse_id='d1',confirmation=dict(status='confirmed',basis='researcher_recorded',decision_id='synthetic_test_only',evidence='Synthetic test; not a real linguistic judgment'))])
    def tearDown(self):self.temp.cleanup()
    def test_lossless_csv_parquet_and_no_unchanged_scan(self):
        with patch.object(Path,'rglob',side_effect=AssertionError('No full tree scan')):
            result=m.build(self.root,self.plan,self.base/'export')
        self.assertFalse(result['base_modified']);self.assertFalse(result['revision_applied'])
        self.assertEqual(result['documents'][0]['records'],2)
        folder=self.base/'export/document-00001'
        d=m.pq.read_table(folder/'documents.parquet').to_pylist()[0];rows=m.pq.read_table(folder/'records.parquet').to_pylist()
        self.assertEqual(m.reconstruct(d,rows),self.doc);self.assertEqual(rows[0]['text'],'');self.assertIsNone(rows[0]['speaker_id'])
        self.assertEqual(u.sha(self.root/self.entry['physical_path']),self.entry['sha256'])
    def test_unconfirmed_candidate_rejected(self):
        self.plan['documents'][0]['confirmation']['status']='candidate'
        with self.assertRaises(ValueError):m.build(self.root,self.plan,self.base/'export')
        self.assertFalse((self.base/'export').exists())
    def test_source_tamper(self):
        (self.root/self.entry['physical_path']).write_text('{}')
        with self.assertRaises(ValueError):m.check_plan(self.root,self.plan)
    def test_missing_affected_document(self):
        self.plan['documents']=[]
        with self.assertRaises(ValueError):m.check_plan(self.root,self.plan)
    def test_cannot_overwrite_base(self):
        with self.assertRaises(ValueError):m.build(self.root,self.plan,self.root/'common_parquet')
    def test_order_corruption(self):
        self.doc['utterances'][1]['turn_order']=1
        with self.assertRaises(ValueError):m.split(self.doc,self.plan['documents'][0],self.entry)
    def test_duplicate_json_keys(self):
        p=self.base/'bad.json';p.write_text('{"id":1,"id":2}')
        with self.assertRaises(ValueError):m.native(p)
    def test_resume_destination_not_overwritten(self):
        m.build(self.root,self.plan,self.base/'export')
        with self.assertRaises(ValueError):m.build(self.root,self.plan,self.base/'export')
    def test_historical_version_not_automatically_transferred(self):
        self.plan['documents'][0]['analysis_version']='bareun_3.1'
        with self.assertRaises(ValueError):m.check_plan(self.root,self.plan)
    def interrupt_after_document(self):
        out=self.base/'resume_export';save=u.save
        def interrupted(path,value):
            if path.name=='CHANGES.json':raise RuntimeError('Synthetic interruption')
            return save(path,value)
        with patch.object(u,'save',side_effect=interrupted):
            with self.assertRaises(RuntimeError):m.build(self.root,self.plan,out)
        return out
    def test_resume_reuses_completed_tables_without_duplicate_rows(self):
        out=self.interrupt_after_document()
        before=u.sha(out/'document-00001/records.parquet')
        with patch.object(m,'write_table',side_effect=AssertionError('Completed tables must not be rewritten')):
            result=m.build(self.root,self.plan,out,resume=True)
        self.assertEqual(result['generated_files'],5)
        self.assertEqual(result['documents'][0]['records'],2)
        self.assertEqual(before,u.sha(out/'document-00001/records.parquet'))
    def test_resume_rejects_changed_plan(self):
        out=self.interrupt_after_document();self.plan['documents'][0]['confirmation']['evidence']='different decision'
        with self.assertRaisesRegex(ValueError,'plan binding'):m.build(self.root,self.plan,out,resume=True)
    def test_resume_rejects_completed_table_tamper(self):
        out=self.interrupt_after_document();(out/'document-00001/records.csv').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'output hash'):m.build(self.root,self.plan,out,resume=True)
    def test_resume_rebuilds_only_uncommitted_document(self):
        out=self.base/'partial';real=m.write_table
        def interrupted(folder,name,rows,schema):
            if name=='records':raise RuntimeError('Synthetic table interruption')
            return real(folder,name,rows,schema)
        with patch.object(m,'write_table',side_effect=interrupted):
            with self.assertRaises(RuntimeError):m.build(self.root,self.plan,out)
        result=m.build(self.root,self.plan,out,resume=True)
        self.assertEqual(result['documents'][0]['records'],2)
        with self.assertRaisesRegex(ValueError,'Completed destination'):m.build(self.root,self.plan,out,resume=True)

if __name__=='__main__':unittest.main()
