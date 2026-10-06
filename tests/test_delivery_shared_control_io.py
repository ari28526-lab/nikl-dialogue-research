import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import subprocess
import sys
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('control_io', Path(__file__).resolve().parents[1]/'scripts/python/run_delivery_shared_control_io.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ControlTests(unittest.TestCase):
    def tearDown(self):
        module.uninstall()

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing semantics')
    def test_shared_old_reader_does_not_block_atomic_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)/'STATE.json'; temp = Path(directory)/'STATE.json.tmp'
            state.write_text('{"version":1}', encoding='utf-8')
            module.install([state])
            with state.open('r', encoding='utf-8') as old:
                temp.write_text('{"version":2}', encoding='utf-8'); temp.replace(state)
                self.assertEqual(json.load(old)['version'], 1)
                self.assertEqual(json.loads(state.read_text())['version'], 2)

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing semantics')
    def test_real_legacy_read_lock_then_retry_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)/'STATE.json'; temp = Path(directory)/'STATE.json.tmp'
            state.write_bytes(b'old'); temp.write_bytes(b'new')
            legacy = module.ORIGINAL_OPEN(state, 'rb')
            with self.assertRaises(PermissionError):
                module.ORIGINAL_REPLACE(temp, state)
            module.install([state])
            timer = threading.Timer(.15, legacy.close); timer.start()
            try:
                temp.replace(state)
                self.assertEqual(state.read_bytes(), b'new')
            finally:
                timer.join(); legacy.close()

    def test_persistent_denial_is_finite_and_not_ignored(self):
        calls = []
        def denied():
            calls.append(1); raise PermissionError('permanent')
        with patch.object(module.time, 'sleep'):
            with self.assertRaises(PermissionError): module.retry(denied)
        self.assertEqual(len(calls), module.ATTEMPTS)

    def test_non_permission_errors_are_not_retried(self):
        with patch.object(module.time, 'sleep') as sleep:
            with self.assertRaises(FileNotFoundError):
                module.retry(lambda: (_ for _ in ()).throw(FileNotFoundError()))
            sleep.assert_not_called()

    def test_payload_io_and_writes_use_original_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)/'STATE.json'; payload = Path(directory)/'payload.json'
            module.install([state])
            payload.write_text('한국어', encoding='utf-8'); state.write_text('{}')
            self.assertEqual(payload.read_text(encoding='utf-8'), '한국어')
            self.assertEqual(state.read_bytes(), b'{}')

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing semantics')
    def test_builtin_binary_reader_and_path_reader_both_share_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)/'STATE.json'; temp = Path(directory)/'STATE.json.tmp'
            state.write_bytes(b'old'); module.install([state])
            with open(state, 'rb') as first, state.open('rb') as second:
                temp.write_bytes(b'new'); temp.replace(state)
                self.assertEqual(first.read(), b'old'); self.assertEqual(second.read(), b'old')

    def test_copy_resume_start_state_is_published_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); ledger = root/'COPY_LEDGER.sqlite'; state = root/'STATE.json'
            module.install([state], ledger, state)
            db = module.sqlite3.connect(ledger); db.close()
            start = json.loads(state.read_text()); self.assertEqual(start['phase'], 'resume_capacity_check')
            state.write_text('{"status":"next"}')
            db = module.sqlite3.connect(ledger); db.close()
            self.assertEqual(json.loads(state.read_text())['status'], 'next')

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing semantics')
    def test_oversize_control_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)/'STATE.json'
            state.write_bytes(b'x'*(module.MAX_CONTROL_BYTES+1)); module.install([state])
            with self.assertRaises(ValueError): state.read_bytes()

    def test_frozen_copy_runner_executes_through_wrapper_without_contract_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'source'; source.mkdir(); (source/'a.txt').write_text('한국어',encoding='utf-8')
            package=root/'package'; package.mkdir(); config=root/'config.json'
            config.write_text(json.dumps(dict(schema='portable_delivery_copy.v1',roots=[dict(role='test',source=str(source),destination='source')],free_floor_bytes=0)),encoding='utf-8')
            runner=Path(__file__).resolve().parents[1]/'scripts/python/build_portable_delivery_copy.py'
            policy=root/'policy.json'; policy.write_text(json.dumps(dict(package=str(package),wrapper_sha256=module.digest(spec.origin),
                controls=[str(package/'STATE.json'),str(package/'ERROR.json')],workers=[dict(runner=str(runner),runner_sha256=module.digest(runner))])),encoding='utf-8')
            result=subprocess.run([sys.executable,spec.origin,'--policy',str(policy),'--policy-sha256',module.digest(policy),
                '--runner',str(runner),'--','--config',str(config),'--output',str(package),'--copy'],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads((package/'COPY_FINAL.json').read_text())['files'],1)
            self.assertEqual(json.loads((package/'CONTRACT.json').read_text())['runner_sha256'],module.digest(runner))
            self.assertEqual((package/'source/a.txt').read_bytes(),(source/'a.txt').read_bytes())

if __name__ == '__main__': unittest.main()
