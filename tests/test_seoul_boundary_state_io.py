import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import run_seoul_boundary_full as runner

class StateIO(unittest.TestCase):
    def test_transient_replace_lock_preserves_new_state(self):
        original=Path.replace;calls=[]
        def transient(path,target):
            calls.append(1)
            if len(calls)<3:raise PermissionError('simulated shared reader')
            return original(path,target)
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'state.json';dest.write_text('{"old": true}')
            with patch.object(Path,'replace',transient),patch.object(runner.time,'sleep'):
                runner.save(dest,{'completed':45})
            self.assertEqual(json.loads(dest.read_text()),{'completed':45})
            self.assertEqual(len(calls),3)

    def test_persistent_lock_keeps_old_state_and_pending_file(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'state.json';dest.write_text('{"old": true}')
            with patch.object(Path,'replace',side_effect=PermissionError('persistent')),patch.object(runner.time,'sleep'):
                with self.assertRaises(PermissionError):runner.save(dest,{'completed':45})
            self.assertEqual(json.loads(dest.read_text()),{'old':True})
            self.assertEqual(json.loads(dest.with_name('state.json.tmp').read_text()),{'completed':45})

if __name__=='__main__':unittest.main()
