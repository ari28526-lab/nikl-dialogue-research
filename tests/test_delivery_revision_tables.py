import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/python'))
import test_delivery_revision_regeneration as fixtures
import delivery_revision_tables as reader
import regenerate_delivery_revision_tables as gen
import update_delivery_revision as u


class ReaderTests(unittest.TestCase):
    def setUp(self):
        fixtures.RegenerationTests.setUp(self)
        (self.root/'COPY_LEDGER.sqlite').write_bytes(b'synthetic ledger only')
        u.save(self.root/'updates/BASE_BINDING.json', dict(base_final_sha256=u.sha(self.root/'COPY_FINAL.json'), ledger_stat=u.ledger_stat(self.root)))
        out = self.base/'tables'
        gen.build(self.root,self.plan,out)
        changes=u.read(out/'CHANGES.json');entries=[]
        for x in changes['files']:
            physical='updates/revisions/r1_tables/files/'+x['logical_path']
            p=self.root/physical;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(Path(x['source']).read_bytes())
            entries.append(dict(logical_path=x['logical_path'],physical_path=physical,bytes=x['bytes'],sha256=x['sha256']))
        u.save(self.root/'updates/revisions/r1_tables/REVISION.json',dict(status='complete',revision='r1_tables',parent='r1',parent_sha256=u.sha(self.root/'updates/revisions/r1/REVISION.json'),base_final_sha256=u.sha(self.root/'COPY_FINAL.json'),changed_files=entries,affected_documents=['d1']))
        self.receipt='common_parquet/revisions/r1_tables/document-00001/RECEIPT.json'
    def tearDown(self):self.temp.cleanup()
    def load(self,**kwargs):
        args=dict(root=self.root,revision='r1_tables',receipt_logical=self.receipt,logical_source='analysis/d1.json',corpus='modu',year='2020',discourse_id='d1');args.update(kwargs)
        return reader.read_document(**args)
    def test_selected_rows_replace_and_preserve_empty(self):
        with patch.object(Path,'rglob',side_effect=AssertionError('No tree scan')):
            result=self.load()
        self.assertEqual(result['native'],self.doc);self.assertEqual(len(result['records']),2)
        self.assertEqual(result['records'][0]['text'],'');self.assertIsNone(result['records'][0]['speaker_id'])
    def test_identity_mismatch(self):
        with self.assertRaises(ValueError):self.load(discourse_id='wrong')
    def test_table_tamper_rejected(self):
        p=self.root/('updates/revisions/r1_tables/files/'+self.receipt.replace('RECEIPT.json','records.parquet'));p.write_bytes(b'bad')
        with self.assertRaises(ValueError):self.load()
    def test_newer_native_without_tables_rejected(self):
        p=self.root/'updates/revisions/r2/files/analysis/d1.json';u.save(p,dict(self.doc,new_value='changed'))
        u.save(self.root/'updates/revisions/r2/REVISION.json',dict(status='complete',revision='r2',parent='r1_tables',parent_sha256=u.sha(self.root/'updates/revisions/r1_tables/REVISION.json'),base_final_sha256=u.sha(self.root/'COPY_FINAL.json'),changed_files=[dict(logical_path='analysis/d1.json',physical_path='updates/revisions/r2/files/analysis/d1.json',bytes=p.stat().st_size,sha256=u.sha(p))],affected_documents=['d1']))
        with self.assertRaises(ValueError):self.load(revision='r2')
    def test_undeclared_receipt_rejected(self):
        with self.assertRaises(ValueError):self.load(receipt_logical=self.receipt.replace('00001','99999'))
    def test_traversal_rejected(self):
        with self.assertRaises(ValueError):self.load(logical_source='../outside.json')
    def test_whole_query_replaces_base_without_duplicates(self):
        base=[dict(corpus='modu',year='2020',discourse_id='d1',text='obsolete'),
              dict(corpus='modu',year='2020',discourse_id='other',text='unchanged'),
              dict(corpus='modu',year='2020',discourse_id='d1',text='obsolete again')]
        with patch.object(Path,'rglob',side_effect=AssertionError('No package tree scan')):
            rows=list(reader.iter_selected_records(self.root,'r1_tables',iter(base)))
        self.assertEqual(len(rows),3)
        self.assertEqual([r['text'] for r in rows],['','한글','unchanged'])
    def test_whole_query_adds_new_document(self):
        rows=list(reader.iter_selected_records(self.root,'r1_tables',iter([])))
        self.assertEqual(len(rows),2)
    def test_whole_query_rejects_missing_regeneration_before_output(self):
        result=reader.iter_selected_records(self.root,'r1',iter([dict(corpus='modu',year='2020',discourse_id='other')]))
        with self.assertRaisesRegex(ValueError,'lacks matching'):next(result)
    def test_query_interface_filters_selected_text(self):
        import query_delivery_revision_records as query
        with patch.object(query,'files',return_value=[]):
            value=query.query(self.root,self.root,'r1_tables','modu',contains='한글')
        self.assertEqual(len(value['rows']),1)
        self.assertEqual(value['rows'][0]['utterance_id'],'u2')
        self.assertFalse(value['complete_corpus_count'])
    def test_query_interface_rejects_unbounded_output(self):
        import query_delivery_revision_records as query
        with self.assertRaises(ValueError):query.query(self.root,self.root,'r1_tables','modu',limit=0)

if __name__=='__main__':unittest.main()
