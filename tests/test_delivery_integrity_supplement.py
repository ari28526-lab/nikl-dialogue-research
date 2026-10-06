import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import audit_delivery_integrity_supplement as m
class Tests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name)/'pkg';self.root.mkdir();self.out=Path(self.t.name)/'audit'
  m.u.save(self.root/'COPY_REUSE_FINAL.json',dict(status='done'))
  (self.root/'guide.md').write_text('synthetic',encoding='utf-8');h,size=m.digest(self.root/'guide.md')
  self.plan=dict(schema='explicit_integrity_supplement.v1',files=[dict(path='guide.md',sha256=h,bytes=size)],dependencies=[dict(path='COPY_REUSE_FINAL.json',status='done')])
 def tearDown(self):self.t.cleanup()
 def test_complete_and_reopen_without_tree_scan(self):
  with patch.object(Path,'rglob',side_effect=AssertionError('No scan')):
   a=m.audit(self.root,self.plan,self.out);b=m.audit(self.root,self.plan,self.out)
  self.assertEqual(a,b);self.assertFalse(a['delivery_complete']);self.assertEqual(len(a['files']),1)
 def test_tamper_during_resume_rejected(self):
  m.audit(self.root,self.plan,self.out);(self.root/'guide.md').write_text('corrupt')
  with self.assertRaises(ValueError):m.audit(self.root,self.plan,self.out)
 def test_incomplete_dependency(self):
  self.plan['dependencies'][0]['status']='not_done'
  with self.assertRaises(ValueError):m.audit(self.root,self.plan,self.out)
  self.assertFalse(self.out.exists())
 def test_dependency_changed_after_checkpoint(self):
  m.audit(self.root,self.plan,self.out);m.u.save(self.root/'COPY_REUSE_FINAL.json',dict(status='done',new_value=1))
  with self.assertRaises(ValueError):m.audit(self.root,self.plan,self.out)
 def test_partial_progress_resumes(self):
  real=m.u.save
  def stop(path,value):
   if path.name=='FINAL.json':raise InterruptedError('Synthetic interruption')
   return real(path,value)
  with patch.object(m.u,'save',side_effect=stop):
   with self.assertRaises(InterruptedError):m.audit(self.root,self.plan,self.out)
  self.assertTrue((self.out/'PROGRESS.json').exists());self.assertFalse((self.out/'FINAL.json').exists())
  self.assertEqual(m.audit(self.root,self.plan,self.out)['status'],'explicit_small_files_sha_verified')
 def test_traversal(self):
  self.plan['files'][0]['path']='../outside'
  with self.assertRaises(ValueError):m.audit(self.root,self.plan,self.out)
 def test_duplicate(self):
  self.plan['files']*=2
  with self.assertRaises(ValueError):m.audit(self.root,self.plan,self.out)
 def test_size_bound(self):
  self.plan['files'][0]['bytes']=m.MAX_FILE+1
  with self.assertRaises(ValueError):m.audit(self.root,self.plan,self.out)
 def test_no_corpus_output(self):
  with self.assertRaises(ValueError):m.audit(self.root,self.plan,self.root/'corpus')
 def test_consumer_rechecks_current_inputs(self):
  a=m.audit(self.root,self.plan,self.out)
  self.assertEqual(m.verify_receipt(self.root,self.plan,self.out),a)
  (self.root/'guide.md').write_text('corrupt')
  with self.assertRaises(ValueError):m.audit(self.root,self.plan,self.out)
  self.assertTrue((self.out/'FINAL.json').exists())
  with self.assertRaises(ValueError):m.verify_receipt(self.root,self.plan,self.out)
 def test_consumer_rejects_missing_coverage(self):
  m.audit(self.root,self.plan,self.out);p=self.out/'FINAL.json';v=m.u.read(p);v['files']=[];m.u.save(p,v)
  with self.assertRaises(ValueError):m.verify_receipt(self.root,self.plan,self.out)
 def test_consumer_rejects_new_dependency(self):
  m.audit(self.root,self.plan,self.out);m.u.save(self.root/'COPY_REUSE_FINAL.json',dict(status='done',changed=True))
  with self.assertRaises(ValueError):m.verify_receipt(self.root,self.plan,self.out)
 def test_consumer_rejects_delivery_promotion(self):
  m.audit(self.root,self.plan,self.out);p=self.out/'FINAL.json';v=m.u.read(p);v['delivery_complete']=True;m.u.save(p,v)
  with self.assertRaises(ValueError):m.verify_receipt(self.root,self.plan,self.out)
if __name__=='__main__':unittest.main()
