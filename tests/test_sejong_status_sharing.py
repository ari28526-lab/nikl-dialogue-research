import contextlib, io, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from apply_sejong_residual import atomic

class StatusSharing(unittest.TestCase):
    def test_transient_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'STATE.json';original=Path.replace;calls=[]
            def once(src,dst):
                calls.append(1)
                if len(calls)==1:raise PermissionError('sharing')
                return original(src,dst)
            with patch.object(Path,'replace',once),patch('apply_sejong_residual.time.sleep'):
                self.assertTrue(atomic(p,{'complete':1}))
            self.assertEqual(json.loads(p.read_text()),{'complete':1})
    def test_persistent_status_hold_but_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'STATE.json';p.write_text('{"old":true}')
            with patch.object(Path,'replace',side_effect=PermissionError('sharing')),patch('apply_sejong_residual.time.sleep'),contextlib.redirect_stderr(io.StringIO()):
                self.assertFalse(atomic(p,{'new':True}))
                self.assertEqual(json.loads(p.read_text()),{'old':True})
                with self.assertRaises(PermissionError):atomic(Path(tmp)/'FINAL.json',{})
    @unittest.skipUnless(os.name=='nt','Windows sharing contract')
    def test_actual_windows_reader_lock_then_release(self):
        import ctypes
        from ctypes import wintypes
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        k.CreateFileW.restype=wintypes.HANDLE
        k.CloseHandle.argtypes=[wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'STATE.json';p.write_text('{}')
            handle=k.CreateFileW(str(p),0x80000000,3,None,3,0,None)
            self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
            try:
                with patch('apply_sejong_residual.time.sleep'),contextlib.redirect_stderr(io.StringIO()):self.assertFalse(atomic(p,{'n':1}))
            finally:k.CloseHandle(handle)
            self.assertTrue(atomic(p,{'n':2}))
            self.assertEqual(json.loads(p.read_text()),{'n':2})

if __name__=='__main__':unittest.main()
