import importlib.util
import json
from pathlib import Path
import tempfile
import sqlite3
from contextlib import closing
import unittest
import pyarrow as pa
import pyarrow.parquet as pq

spec=importlib.util.spec_from_file_location('reopen',Path(__file__).parents[1]/'scripts/python/audit_delivery_reopen_queries.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class ReopenTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'source';self.dest=Path(self.temp.name)/'different'
        self.root.mkdir();self.file=self.root/'data.parquet'
        pq.write_table(pa.table({'id':['가','나','',None], 'kind':['x',None,'','x'],
            'order':[0,1,2,3], 'payload':['{"한글":null}','{}','',None]}),self.file)
        self.plan=dict(schema='delivery_reopen_queries.v1',cases=[dict(id='fixture',path='data.parquet',
            bytes=self.file.stat().st_size,sha256=m.sha(self.file),rows=4,sample_rows=4,
            columns=['id','kind','order','payload'],category='kind',float_columns=[])])

    def test_physical_relocation_and_resume(self):
        a=m.query(self.root,self.plan);m.relocate(self.root,self.dest,self.plan)
        m.assert_equal(a,m.query(self.dest,self.plan));m.relocate(self.root,self.dest,self.plan)
        self.assertEqual(a['cases'][0]['null_counts']['id'],1)
        self.assertEqual(a['cases'][0]['selected'][2]['id'],'')

    def test_changed_relocated_file_rejected(self):
        m.relocate(self.root,self.dest,self.plan)
        p=self.dest/'data.parquet';b=bytearray(p.read_bytes());b[-1]^=1;p.write_bytes(b)
        with self.assertRaisesRegex(ValueError,'SHA'):m.relocate(self.root,self.dest,self.plan)

    def test_bad_receipt_rows_and_source_hash(self):
        self.plan['cases'][0]['rows']=5
        with self.assertRaisesRegex(ValueError,'row count'):m.query(self.root,self.plan)
        self.plan['cases'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'SHA'):m.query(self.root,self.plan)

    def test_relative_root_and_size_limits(self):
        for path in ['../escape.parquet','/absolute','C:/absolute','a\\b']:
            bad=json.loads(json.dumps(self.plan));bad['cases'][0]['path']=path
            with self.assertRaises(ValueError):m.validate_plan(bad)
        self.plan['cases'][0]['bytes']=m.MAX_BYTES+1
        with self.assertRaises(ValueError):m.validate_plan(self.plan)
        with self.assertRaises(ValueError):m.relocate(self.root,self.root/'nested',self.plan)

    def test_result_null_order_and_value_mismatch(self):
        expected=m.query(self.root,self.plan)
        for mutation in ('null','order','value'):
            bad=json.loads(json.dumps(expected))
            selected=bad['cases'][0]['selected']
            if mutation=='null':selected[3]['id']=''
            elif mutation=='order':selected.reverse()
            else:selected[0]['payload']='changed'
            with self.assertRaisesRegex(ValueError,'differ'):m.assert_equal(expected,bad)

    def test_counts_order_irrelevant_but_counts_not(self):
        a=m.query(self.root,self.plan);b=json.loads(json.dumps(a))
        b['cases'][0]['counts'].reverse();m.assert_equal(a,b)
        b['cases'][0]['counts'][0]['n']+=1
        with self.assertRaises(ValueError):m.assert_equal(a,b)

    def test_dependencies_require_full_stage_and_matching_indexed_row(self):
        m.save(self.root/'COPY_FINAL.json',dict(status='declared_scope_copied_sha_verified',sample=False))
        addon=dict(status='addon_files_sha_verified',sample=False,
                   dependencies={'COPY_FINAL.json':m.sha(self.root/'COPY_FINAL.json')})
        m.save(self.root/m.DEPENDENCY,addon)
        with closing(sqlite3.connect(self.root/'COPY_LEDGER.sqlite')) as db:
            db.execute('CREATE TABLE files(relative TEXT PRIMARY KEY,bytes INTEGER,sha256 TEXT,copied INTEGER)')
            c=self.plan['cases'][0]
            db.execute('INSERT INTO files VALUES(?,?,?,?)',(c['path'],c['bytes'],c['sha256'],1));db.commit()
        self.assertIn(m.DEPENDENCY,m.dependencies(self.root,self.plan))
        addon['sample']=True;m.save(self.root/m.DEPENDENCY,addon)
        with self.assertRaisesRegex(ValueError,'Full'):m.dependencies(self.root,self.plan)
        addon['sample']=False;addon['dependencies']={};m.save(self.root/m.DEPENDENCY,addon)
        with self.assertRaisesRegex(ValueError,'binding'):m.dependencies(self.root,self.plan)
        addon['dependencies']={'COPY_FINAL.json':m.sha(self.root/'COPY_FINAL.json')};m.save(self.root/m.DEPENDENCY,addon)
        with closing(sqlite3.connect(self.root/'COPY_LEDGER.sqlite')) as db:
            db.execute('UPDATE files SET copied=0');db.commit()
        with self.assertRaisesRegex(ValueError,'ledger'):m.dependencies(self.root,self.plan)

    def test_float_coordinates_are_compared_without_decimal_rounding(self):
        import struct
        pq.write_table(pa.table({'id':['x','y','z','w'],'kind':['a']*4,
             'time':[0.12345678901234567,-0.0,None,float('nan')]}),self.file)
        c=self.plan['cases'][0];c.update(bytes=self.file.stat().st_size,sha256=m.sha(self.file),
             columns=['id','kind','time'],float_columns=['time'])
        result=m.query(self.root,self.plan)['cases'][0]
        self.assertEqual(result['null_counts']['time'],1)
        self.assertEqual(result['selected'][0]['time']['ieee754_le_hex'],struct.pack('<d',0.12345678901234567).hex())
        self.assertEqual(result['selected'][1]['time']['ieee754_le_hex'],'0000000000000080')
        self.assertIsNone(result['selected'][2]['time'])
        self.assertIsInstance(result['selected'][3]['time'],dict)


if __name__=='__main__':unittest.main()
