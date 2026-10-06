import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import build_delivery_addon_manifest as m

class AddonTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'package';self.out=self.root/'audit'
        for r in m.ROOTS:(self.root/r).mkdir(parents=True)
        sem=self.root/m.ROOTS[0];hist=self.root/m.ROOTS[1];guide=self.root/m.ROOTS[2];bundle=self.root/m.ROOTS[3]
        self.payload=sem/'documents/sample.json.gz';self.payload.parent.mkdir();self.payload.write_bytes(b'example')
        receipt=self.payload.with_name(self.payload.name+'.receipt.json');m.save(receipt,dict(sha256=m.sha(self.payload)))
        (sem/'UTTERANCE_INDEX.sqlite').write_bytes(b'index');m.save(sem/'DATASET_CATALOG.json',{})
        m.save(sem/'FINAL.json',dict(status=m.FINALS[m.ROOTS[0]+'/FINAL.json'],sample=False,index_sha256=m.sha(sem/'UTTERANCE_INDEX.sqlite'),catalog_sha256=m.sha(sem/'DATASET_CATALOG.json'),receipts=[dict(path=receipt.relative_to(sem).as_posix(),sha256=m.sha(receipt))]))
        (hist/'HISTORICAL_TEXTGRID_INDEX.sqlite').write_bytes(b'history')
        m.save(hist/'FINAL.json',dict(status=m.FINALS[m.ROOTS[1]+'/FINAL.json'],sample=False,index_sha256=m.sha(hist/'HISTORICAL_TEXTGRID_INDEX.sqlite'),receipts=[]))
        m.save(self.root/'COPY_FINAL.json',dict(status=m.FINALS['COPY_FINAL.json']))
        m.save(hist/'DEPENDENCIES.json',dict(copy_final_sha256=m.sha(self.root/'COPY_FINAL.json'),semantic_final_sha256=m.sha(sem/'FINAL.json')))
        (bundle/'GUIDE.md').write_text('fixture',encoding='utf-8')
        m.save(bundle/'BUNDLE_MANIFEST.json',dict(files=[dict(path='GUIDE.md',bytes=7,sha256=m.sha(bundle/'GUIDE.md'))]))
        bindings={k:m.sha(self.root/k) for k in m.FINALS if k!=m.ROOTS[2]+'/FINAL.json'}
        m.save(guide/'FINAL.json',dict(status='guide_targets_verified',sample=False,dependencies=bindings,bundle_manifest_sha256=m.sha(bundle/'BUNDLE_MANIFEST.json')))

    def tearDown(self):self.temp.cleanup()
    def build(self):
        bindings,expected=m.dependencies(self.root)
        return m.build(self.root,self.out,m.ROOTS,expected,bindings)

    def test_resume_relocation_and_manifest(self):
        first=self.build();second=self.build()
        self.assertEqual(first['manifest_sha256'],second['manifest_sha256'])
        dest=Path(self.temp.name)/'relocated';shutil.copytree(self.root,dest)
        bindings,expected=m.dependencies(dest);other=m.build(dest,dest/'audit',m.ROOTS,expected,bindings)
        self.assertEqual(first['manifest_sha256'],other['manifest_sha256'])
        self.assertFalse(other['delivery_complete'])
        lines=[json.loads(x) for x in (dest/'audit/SHA256_MANIFEST.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(lines),other['files'])
        for x in lines:self.assertEqual(m.sha(dest/x['path']),x['sha256'])

    def test_same_size_payload_tamper(self):
        self.build();s=self.payload.stat();self.payload.write_bytes(b'EXAMPLE');os.utime(self.payload,ns=(s.st_atime_ns,s.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'Stage payload SHA'):self.build()

    def test_unbound_resume_tamper(self):
        p=self.root/m.ROOTS[0]/'notes.txt';p.write_bytes(b'old');self.build();s=p.stat();p.write_bytes(b'NEW');os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'Resume payload'):self.build()

    def test_added_removed_and_partial_files(self):
        self.build();p=self.root/m.ROOTS[1]/'new.txt';p.write_text('new')
        with self.assertRaisesRegex(ValueError,'inventory changed'):self.build()
        p.unlink();self.payload.unlink()
        with self.assertRaisesRegex(ValueError,'Expected stage file absent'):self.build()
        self.payload.write_bytes(b'example');q=self.root/m.ROOTS[0]/'open.sqlite-wal';q.write_bytes(b'wal')
        with self.assertRaisesRegex(ValueError,'Unfinished file'):self.build()

    def test_dependency_sample_binding_and_traversal(self):
        with self.assertRaises(ValueError):m.safe(self.root,'../outside')
        with self.assertRaises(ValueError):m.safe(self.root,'C:/outside')
        p=self.root/m.ROOTS[2]/'FINAL.json';v=m.read(p);v['sample']=True;m.save(p,v)
        with self.assertRaisesRegex(ValueError,'Full completed'):self.build()
        v['sample']=False;v['dependencies']['COPY_FINAL.json']='0'*64;m.save(p,v)
        with self.assertRaisesRegex(ValueError,'dependency SHA'):self.build()

    def test_stop_then_resume_and_control_scope(self):
        self.out.mkdir();(self.out/'STOP').write_text('stop')
        with self.assertRaises(InterruptedError):self.build()
        (self.out/'STOP').unlink()
        (self.root/m.ROOTS[0]/'STATE.json').write_text('mutable')
        result=self.build();manifest=(self.out/'SHA256_MANIFEST.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('STATE.json',manifest)
        (self.root/m.ROOTS[0]/'STATE.json').write_text('changed control')
        self.assertEqual(result['manifest_sha256'],self.build()['manifest_sha256'])

    def test_mutation_during_hash(self):
        bindings,expected=m.dependencies(self.root);original=m.sha
        def changed(p):
            digest=original(p)
            if p==self.payload:p.write_bytes(b'changed size')
            return digest
        with patch.object(m,'sha',changed):
            with self.assertRaisesRegex(ValueError,'changed during hashing'):m.build(self.root,self.out,m.ROOTS,expected,bindings)

if __name__=='__main__':unittest.main()
