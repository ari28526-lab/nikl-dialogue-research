import csv
import gzip
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import test_delivery_revision_regeneration as fixture
import regenerate_delivery_morphology_shard as m
import update_delivery_revision as updates
import delivery_morphology_revision as selection


class MorphologyTests(unittest.TestCase):
    def setUp(self):
        fixture.RegenerationTests.setUp(self)
        self.fields=['utt_id','token_index','morph_index','lemma','pos','start_utf32','end_utf32','human_verified']
        def row(uid,lemma,index=0):return dict(utt_id=uid,token_index=0,morph_index=index,lemma=lemma,pos='NNG',start_utf32=0,end_utf32=2,human_verified=False)
        self.doc['utterances'][1]['analysis']['morphemes']=[row('u2','수정'),row('u2','분절',1)]
        p=self.root/self.entry['physical_path'];updates.save(p,self.doc)
        self.entry.update(bytes=p.stat().st_size,sha256=updates.sha(p))
        rp=self.root/'updates/revisions/r1/REVISION.json';r=updates.read(rp);r['changed_files']=[self.entry];updates.save(rp,r)
        self.plan['revision_manifest_sha256']=updates.sha(rp)
        self.source=self.root/'morphology/shard/morphemes.csv.gz';self.source.parent.mkdir(parents=True)
        self.old=[row('u2','old'),row('other','unchanged')]
        with gzip.open(self.source,'wt',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,self.fields);w.writeheader();w.writerows(self.old)
        self.mplan=dict(regeneration=self.plan,source_csv='morphology/shard/morphemes.csv.gz',source_csv_sha256=updates.sha(self.source),
            corpus='modu',year='2020',shard_id='shard1',document_utterance_ids={'d1':['u1','u2']})
    def tearDown(self):self.temp.cleanup()
    def test_changed_segmentation_and_unchanged_cells_preserved(self):
        result=m.build(self.root,self.mplan,self.base/'export')
        self.assertEqual(result['rows'],3);self.assertEqual(result['unchanged_rows_preserved'],1)
        self.assertEqual(result['empty_affected_utterances'],['u1'])
        rows=m.pq.ParquetFile(self.base/'export/morphemes.parquet').read().to_pylist()
        self.assertEqual([r['lemma'] for r in rows],['수정','분절','unchanged'])
        self.assertEqual(rows[-1]['human_verified'],'False')
        self.assertEqual([r['_source_row_index'] for r in rows],[0,1,2])
        self.assertEqual(updates.sha(self.source),self.mplan['source_csv_sha256'])
    def test_candidate_not_promoted(self):
        self.plan['documents'][0]['confirmation']['status']='candidate'
        with self.assertRaises(ValueError):m.build(self.root,self.mplan,self.base/'export')
        self.assertFalse((self.base/'export').exists())
    def test_wrong_utterance_coverage_rejected(self):
        self.mplan['document_utterance_ids']['d1']=['u2']
        with self.assertRaises(ValueError):m.build(self.root,self.mplan,self.base/'export')
    def test_native_coordinate_not_inferred(self):
        del self.doc['utterances'][1]['analysis']['morphemes'][0]['start_utf32']
        p=self.root/self.entry['physical_path'];updates.save(p,self.doc)
        self.entry.update(bytes=p.stat().st_size,sha256=updates.sha(p))
        rp=self.root/'updates/revisions/r1/REVISION.json';r=updates.read(rp);r['changed_files']=[self.entry];updates.save(rp,r)
        self.plan['revision_manifest_sha256']=updates.sha(rp)
        with self.assertRaisesRegex(ValueError,'original fields'):m.build(self.root,self.mplan,self.base/'export')
    def test_original_csv_tamper_rejected(self):
        self.source.write_bytes(b'bad')
        with self.assertRaises(ValueError):m.build(self.root,self.mplan,self.base/'export')
    def test_no_overwrite_or_package_write(self):
        with self.assertRaises(ValueError):m.build(self.root,self.mplan,self.root/'new')
        m.build(self.root,self.mplan,self.base/'export')
        with self.assertRaises(ValueError):m.build(self.root,self.mplan,self.base/'export')
    def applied(self):
        out=self.base/'export';m.build(self.root,self.mplan,out)
        (self.root/'COPY_LEDGER.sqlite').write_bytes(b'synthetic ledger only')
        updates.save(self.root/'updates/BASE_BINDING.json',dict(base_final_sha256=updates.sha(self.root/'COPY_FINAL.json'),ledger_stat=updates.ledger_stat(self.root)))
        changes=updates.read(out/'CHANGES.json');entries=[]
        for f in changes['files']:
            physical='updates/revisions/r1_tables/files/'+f['logical_path'];p=self.root/physical
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(Path(f['source']).read_bytes())
            entries.append(dict(logical_path=f['logical_path'],physical_path=physical,bytes=p.stat().st_size,sha256=updates.sha(p)))
        updates.save(self.root/'updates/revisions/r1_tables/REVISION.json',dict(status='complete',revision='r1_tables',parent='r1',parent_sha256=updates.sha(self.root/'updates/revisions/r1/REVISION.json'),base_final_sha256=updates.sha(self.root/'COPY_FINAL.json'),changed_files=entries,affected_documents=['d1']))
    def test_selected_mirror_replaces_shard_once(self):
        self.applied()
        base=[dict(_corpus='modu',_year='2020',_source_csv=self.mplan['source_csv'],lemma='old'),dict(_corpus='modu',_year='2020',_source_csv='other.csv',lemma='other'),dict(_corpus='modu',_year='2020',_source_csv=self.mplan['source_csv'],lemma='duplicate old')]
        rows=list(selection.selected_rows(self.root,'r1_tables',iter(base)))
        self.assertEqual([r['lemma'] for r in rows],['수정','분절','unchanged','other'])
    def test_native_changed_without_morphology_tables_rejected(self):
        self.applied()
        with self.assertRaisesRegex(ValueError,'lacks current'):list(selection.selected_rows(self.root,'r1',iter([])))
    def test_selected_receipt_tamper_rejected(self):
        self.applied();p=self.root/'updates/revisions/r1_tables/files/common_parquet/morphology_revisions/r1_tables/shard1/morphemes.parquet';p.write_bytes(b'bad')
        with self.assertRaises(ValueError):list(selection.selected_rows(self.root,'r1_tables',iter([])))
    def test_actual_morphology_query_counts_selected_rows(self):
        import query_delivery_parquet as query
        self.applied()
        mirror=self.base/'base_mirror';folder=mirror/'version=bareun_3.2/corpus=modu/year=2020/table=morphemes/group-0001';folder.mkdir(parents=True)
        rows=m.pq.ParquetFile(self.base/'export/morphemes.parquet').read().to_pylist()
        # The frozen base intentionally has only one old row. The selected
        # replacement must contribute all three current rows, not four.
        old=m.pa.Table.from_pylist([rows[0]])
        m.pq.write_table(old,folder/'part-0001.parquet')
        result=query.query(mirror,'bareun_3.2',package=self.root,revision='r1_tables')
        self.assertEqual(result['rows'],3);self.assertEqual(result['counts'],{'NNG':3})
        with self.assertRaises(ValueError):query.query(mirror,'bareun_3.2',max_files=1,package=self.root,revision='r1_tables')


if __name__=='__main__':unittest.main()
