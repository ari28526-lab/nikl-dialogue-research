import json
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from build_portable_delivery_copy import run,safe_target,sha,validate_config,copy_one,io_path

class CopyTests(unittest.TestCase):
    def test_extended_path_copy_resume_and_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);source=p/'source.bin';source.write_bytes(b'long path fixture'*250)
            dest=p/('directory_'+'a'*70)/('directory_'+'b'*70)/('directory_'+'c'*70)/('filename_'+'d'*60+'.bin')
            self.assertGreater(len(str(dest)),300)
            st=source.stat();digest=copy_one(source,dest,st.st_size,st.st_mtime_ns)
            self.assertEqual(digest,sha(source));self.assertEqual(sha(dest),digest)
            self.assertEqual(copy_one(source,dest,st.st_size,st.st_mtime_ns,digest),digest)
            io_path(dest).write_bytes(b'changed')
            with self.assertRaises(AssertionError):copy_one(source,dest,st.st_size,st.st_mtime_ns,digest)
            # Windows tempfile cleanup itself does not add the long-path prefix.
            self.assertTrue(dest.is_relative_to(p))
            io_path(dest).unlink()
            parent=dest.parent
            while parent!=p:
                io_path(parent).rmdir();parent=parent.parent
    def test_copy_resume_relocation_and_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);src=p/'source';src.mkdir();(src/'한글.json').write_text('{"id":"001","null":null}',encoding='utf-8');(src/'empty').write_bytes(b'')
            cfg=dict(schema='portable_delivery_copy.v1',roots=[dict(role='fixture',source=str(src),destination='latest_release/test/source')],free_floor_bytes=0)
            cp=p/'config.json';cp.write_text(json.dumps(cfg),encoding='utf-8');out=p/'out'
            result=run(cp,out,True);self.assertEqual(result['files'],2);self.assertFalse(result['delivery_complete'])
            self.assertEqual(run(cp,out,True)['bytes'],result['bytes'])
            import shutil
            moved=p/'other';shutil.copytree(out,moved)
            for source in src.iterdir():self.assertEqual(sha(source),sha(moved/'latest_release/test/source'/source.name))
            (out/'latest_release/test/source/한글.json').write_bytes(b'bad')
            with self.assertRaises(AssertionError):run(cp,out,True)
    def test_escape_and_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            for rel in ['../outside','C:/outside','/absolute']:
                with self.assertRaises(AssertionError):safe_target(p,rel)
            src=p/'src';src.mkdir()
            with self.assertRaises(AssertionError):validate_config(dict(schema='portable_delivery_copy.v1',roots=[dict(role='x',source=str(src),destination='x')]),src/'out')
    def test_changed_source_fails_on_resume(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);src=p/'src';src.mkdir();(src/'x').write_bytes(b'first')
            cfg=dict(schema='portable_delivery_copy.v1',roots=[dict(role='x',source=str(src),destination='x')],free_floor_bytes=0)
            cp=p/'config.json';cp.write_text(json.dumps(cfg));out=p/'out';run(cp,out,False)
            (src/'x').write_bytes(b'changed')
            with self.assertRaises(AssertionError):run(cp,out,True)

if __name__=='__main__':unittest.main()
