"""Real R/Python equivalence on synthetic relocated revision data only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import test_delivery_revision_tables as fixture
import regenerate_delivery_revision_tables as tables
import query_delivery_revision_records as query
import update_delivery_revision as updates


class RQueryTests(unittest.TestCase):
    def setUp(self):
        fixture.ReaderTests.setUp(self)
        self.base_tables=self.root/'common_parquet/discourse'
        self.base_tables.mkdir(parents=True)
        doc=dict(self.doc,discourse_id='d2')
        doc['utterances']=[dict(utterance_id='u3',turn_order=1,original=dict(form='unchanged',speaker_id=None,start=None,end=None),analysis=dict(status='not_analyzed'))]
        source=self.root/'analysis/d2.json';updates.save(source,doc)
        _,rows=tables.split(doc,dict(corpus='modu',year='2020',discourse_id='d2'),dict(physical_path='analysis/d2.json',sha256=updates.sha(source)))
        _,old=tables.split(self.doc,dict(corpus='modu',year='2020',discourse_id='d1'),self.entry)
        tables.pq.write_table(tables.pa.Table.from_pylist(old+rows,schema=tables.ROW),self.base_tables/'records.parquet')
        updates.save(self.base_tables/'partition.json',dict(sources=[dict(corpus='modu')],outputs=[dict(table='records',path='records.parquet')]))
        updates.save(self.base_tables/'FINAL.json',dict(receipts=[dict(path='partition.json')]))
        moved=self.base/'relocated_package';shutil.copytree(self.root,moved)
        self.root=moved;self.base_tables=self.root/'common_parquet/discourse'
    def tearDown(self):self.temp.cleanup()
    def run_query(self,contains=''):
        out=self.base/'R-result.json'
        script=Path(__file__).resolve().parents[1]/'scripts/R/query_delivery_revision_records.R'
        cmd=[r'C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe',str(script),sys.executable,str(self.root),str(self.base_tables),'r1_tables','modu','100',contains,str(out)]
        env=os.environ.copy()
        for key in ('LC_ALL','LC_CTYPE','LANG'):env[key]=''
        result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60,env=env)
        self.assertEqual(result.returncode,0,result.stderr)
        actual=json.loads(out.read_text(encoding='utf-8'))
        expected=query.query(self.root,self.base_tables,'r1_tables','modu',contains=contains or None)
        self.assertEqual(actual['rows'],expected['rows'])
        self.assertEqual(actual['R_validation']['status'],'selected_native_values_verified')
        return actual
    def test_relocated_empty_null_overlay_and_unchanged_rows(self):
        value=self.run_query()
        self.assertEqual(len(value['rows']),3)
        self.assertEqual(value['rows'][0]['text'],'')
        self.assertIsNone(value['rows'][0]['speaker_id'])
        self.assertEqual(value['rows'][-1]['discourse_id'],'d2')
    def test_korean_literal_filter(self):
        value=self.run_query('한글')
        self.assertEqual(len(value['rows']),1)
        self.assertEqual(value['rows'][0]['utterance_id'],'u2')


if __name__=='__main__':unittest.main()
