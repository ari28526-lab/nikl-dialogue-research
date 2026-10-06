import hashlib
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import audit_delivery_guide_targets as m


class GuideTargetsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'package';self.root.mkdir()
        self.bundle=self.root/'research_tools';s=self.bundle/'supplement_reader'
        m.save(self.root/'CONTRACT.json',dict(config=dict(roots=[dict(source='F:/original',destination='historical')])) )
        (self.root/'historical').mkdir();(self.root/'historical/source.bin').write_bytes(b'evidence')
        (self.root/'historical/analysis.sqlite').write_bytes(b'fixture database placeholder')
        with closing(sqlite3.connect(self.root/'COPY_LEDGER.sqlite')) as db, db:
            db.execute('CREATE TABLE files(relative TEXT UNIQUE COLLATE NOCASE,bytes INTEGER,sha256 TEXT,copied INTEGER)')
            for name in ['source.bin','analysis.sqlite']:
                p=self.root/'historical'/name
                db.execute('INSERT INTO files VALUES(?,?,?,1)',('historical/'+name,p.stat().st_size,m.sha(p)))
        old=dict(created_at='original time',examples=[dict(id='E01',source_database='F:/original/analysis.sqlite',source_table='morphemes',source_key=dict(ordinal=1),payload=dict(selected_group=None,status='hold'))])
        inv=[dict(destination='F:/original/source.bin',sha256=m.sha(self.root/'historical/source.bin'),bytes=8)]
        m.save(s/'original_examples.json',old);m.save(s/'original_source_inventory.json',inv)
        m.save(s/'examples.json',dict(created_at=old['created_at'],original_examples_sha256=m.sha(s/'original_examples.json'),examples=[dict(old['examples'][0],package_database_path='historical/analysis.sqlite')]))
        m.save(s/'source_inventory.json',dict(original_inventory_sha256=m.sha(s/'original_source_inventory.json'),sources=[dict(inv[0],package_path='historical/source.bin')]))
        self.freeze()

    def freeze(self):
        files=[]
        for p in sorted((self.bundle/'supplement_reader').iterdir()):
            files.append(dict(path=p.relative_to(self.bundle).as_posix(),bytes=p.stat().st_size,sha256=m.sha(p)))
        m.save(self.bundle/'BUNDLE_MANIFEST.json',dict(files=files))
        self.expected=m.sha(self.bundle/'BUNDLE_MANIFEST.json')

    def tearDown(self):self.temp.cleanup()

    def audit(self):return m.audit(self.root,self.bundle,self.expected,(1,1))

    def test_relatively_relocated_targets_and_preserved_records(self):
        a=self.audit();self.assertEqual(len(a['references']),2)
        moved=Path(self.temp.name)/'moved';shutil.copytree(self.root,moved)
        b=m.audit(moved,moved/'research_tools',self.expected,(1,1))
        self.assertEqual(a,b);self.assertFalse(a['delivery_complete'])

    def test_missing_target_and_registered_hash_mismatch(self):
        p=self.root/'historical/source.bin';p.rename(p.with_suffix('.preserved'))
        with self.assertRaises(FileNotFoundError):self.audit()
        p.with_suffix('.preserved').rename(p)
        with closing(sqlite3.connect(self.root/'COPY_LEDGER.sqlite')) as db, db:db.execute("UPDATE files SET sha256='wrong' WHERE relative='historical/source.bin'")
        with self.assertRaisesRegex(ValueError,'Registered source SHA'):self.audit()

    def test_bundle_tamper_and_semantic_example_tamper(self):
        p=self.bundle/'supplement_reader/examples.json';v=m.read(p);v['examples'][0]['payload']['selected_group']='changed';m.save(p,v)
        with self.assertRaisesRegex(ValueError,'bundle file changed'):self.audit()
        self.freeze()
        with self.assertRaisesRegex(ValueError,'Stored example changed'):self.audit()

    def test_paths_and_incomplete_copy_rejected(self):
        for bad in ['../escape','C:/outside','/outside','history\\file']:
            with self.assertRaises(ValueError):m.safe(self.root,bad)
        with closing(sqlite3.connect(self.root/'COPY_LEDGER.sqlite')) as db, db:db.execute('UPDATE files SET copied=0')
        with self.assertRaisesRegex(ValueError,'not copied'):self.audit()

    def test_sample_dependency_does_not_pass_production_gate(self):
        h=self.root/'metadata/historical_textgrid_links';s=self.root/'metadata/semantic_links'
        m.save(self.root/'COPY_FINAL.json',dict(status='declared_scope_copied_sha_verified'))
        m.save(s/'FINAL.json',dict(status='semantic_links_complete_with_explicit_scope_gaps',sample=True))
        m.save(h/'FINAL.json',dict(status='historical_textgrid_links_complete',sample=False))
        out=self.root/'metadata/guide_targets'
        with self.assertRaisesRegex(ValueError,'Full dependency receipt required'):m.run(self.root,self.bundle,out,False)
        self.assertFalse((out/'FINAL.json').exists());self.assertEqual(m.read(out/'STATE.json')['status'],'error')


if __name__=='__main__':unittest.main()
