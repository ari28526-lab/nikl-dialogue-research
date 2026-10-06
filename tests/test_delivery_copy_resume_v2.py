import importlib.util,tempfile,unittest,time,hashlib,json,sqlite3,argparse
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('resume',BASE/'scripts/python/build_portable_delivery_copy_resume_v2.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
old=m.load_legacy(BASE/'scripts/python/build_portable_delivery_copy.py')
class ResumeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name)
  self.s=self.r/'source';self.d=self.r/'dest';self.s.write_bytes(b'original');self.d.write_bytes(b'original')
  self.size,self.mt=old.stat_key(self.s);self.h=m.sha(self.s);self.cutoff=time.time_ns()
 def tearDown(self):self.tmp.cleanup()
 def reuse(self):return m.reuse(old,self.s,self.d,self.size,self.mt,self.h,self.cutoff)
 def test_committed_receipt_reused_without_payload_hash(self):
  with patch.object(m,'sha',side_effect=AssertionError('Unexpected payload read')):self.assertTrue(self.reuse())
 def test_source_metadata_change_rejected(self):
  self.s.write_bytes(b'changed size')
  with self.assertRaises(ValueError):self.reuse()
 def test_missing_copy_requires_fresh_validation(self):
  self.d.unlink();self.assertFalse(self.reuse())
 def test_changed_destination_rehash_detects_tamper(self):
  self.d.write_bytes(b'modified');self.cutoff=0
  with self.assertRaises(ValueError):self.reuse()
 def test_same_file_rejected(self):
  self.d=self.s
  with self.assertRaises(ValueError):self.reuse()
 def test_missing_hash_rejected(self):
  self.h=None
  with self.assertRaises(ValueError):self.reuse()
 def test_mismatched_destination_preserved(self):
  self.d.write_bytes(b'wrong size')
  with self.assertRaises(ValueError):self.reuse()
  self.assertEqual(self.d.read_bytes(),b'wrong size')
 def test_partial_preserved_and_new_copy_sha(self):
  self.d.unlink();partial=self.d.with_name(self.d.name+'.delivery-partial-v2');partial.write_bytes(b'old interrupted')
  got=m.copy_stream(old,self.s,self.d,self.size,self.mt,self.h)
  self.assertEqual(got,self.h);self.assertEqual(m.sha(self.d),self.h);self.assertEqual(partial.read_bytes(),b'old interrupted')
 def test_existing_uncommitted_copy_hash_checked(self):
  self.d.write_bytes(b'modified')
  with self.assertRaises(ValueError):m.copy_stream(old,self.s,self.d,self.size,self.mt,self.h)
 def test_full_migration_and_second_resume(self):
  source=self.r/'inputs';source.mkdir();a=source/'a';b=source/'b';a.write_bytes(b'a');b.write_bytes(b'b')
  root=self.r/'package';root.mkdir();(root/'payload').mkdir();(root/'payload/a').write_bytes(b'a')
  cfg={'schema':'portable_delivery_copy.v1','roots':[{'role':'test','source':str(source),'destination':'payload'}],'free_floor_bytes':0}
  m.save(root/'CONTRACT.json',{'config':cfg});m.save(root/'INVENTORY.json',{'files':2,'bytes':2})
  with sqlite3.connect(root/'COPY_LEDGER.sqlite') as db:
   db.execute('CREATE TABLE files(id INTEGER PRIMARY KEY,source TEXT,relative TEXT,bytes INTEGER,mtime_ns INTEGER,sha256 TEXT,copied INTEGER)')
   for i,p in enumerate([a,b],1):db.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?)',(i,str(p),'payload/'+p.name,1,p.stat().st_mtime_ns,m.sha(p) if i==1 else None,1 if i==1 else 0))
  db.close()
  policy={'package':str(root),'legacy_runner':str(BASE/'scripts/python/build_portable_delivery_copy.py'),'shared_helper':str(BASE/'scripts/python/run_delivery_shared_control_io.py'),'bindings':{p:m.sha(root/p) for p in ['CONTRACT.json','INVENTORY.json']},'archive_bindings':[],'baseline_cutoff_ns':time.time_ns()}
  policy['legacy_runner_sha256']=m.sha(policy['legacy_runner']);policy['shared_helper_sha256']=m.sha(policy['shared_helper'])
  plan=self.r/'policy.json';m.save(plan,policy);args=argparse.Namespace(output=root,policy=plan,policy_sha256=m.sha(plan))
  try:
   m.run(args);first=m.read(root/'COPY_REUSE_FINAL.json');self.assertEqual((first['reused_sha_records'],first['fresh_sha_files']),(1,1))
   original=m.sha
   def bounded(p):
    if Path(p) in [a,b,root/'payload/a',root/'payload/b']:raise AssertionError('Rehashed completed payload')
    return original(p)
   with patch.object(m,'sha',side_effect=bounded):m.run(args)
   final=m.read(root/'COPY_REUSE_FINAL.json');self.assertEqual((final['reused_sha_records'],final['fresh_sha_files']),(2,0))
  finally:m.load_legacy(Path(policy['shared_helper'])).uninstall()
if __name__=='__main__':unittest.main()
