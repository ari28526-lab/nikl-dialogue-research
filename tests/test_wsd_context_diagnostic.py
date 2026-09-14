import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/python'))
from diagnose_wsd_context_request import run_one, safe_error
from connectrpc.code import Code
from connectrpc.errors import ConnectError


class DiagnosticTests(unittest.TestCase):
    def test_error_code_without_secret_or_payload(self):
        value = safe_error(ConnectError(Code.UNAVAILABLE, '504 Gateway Timeout SECRET_KEY private_corpus'))
        self.assertEqual(value['error_code'], 'UNAVAILABLE')
        self.assertTrue(value['gateway_timeout_hint'])
        self.assertNotIn('SECRET_KEY', json.dumps(value))
        self.assertNotIn('private_corpus', json.dumps(value))

    @patch('diagnose_wsd_context_request.storage')
    def test_failure_is_not_automatically_repeated(self, _):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def call(text):
                calls.append(text)
                raise ConnectError(Code.DEADLINE_EXCEEDED, 'secret')
            root = Path(directory)
            run_one(root, {}, 'synthetic', call)
            run_one(root, {}, 'synthetic', call)
            self.assertEqual(len(calls), 1)
            self.assertNotIn('secret', (root/'STATE.json').read_text())

    @patch('diagnose_wsd_context_request.storage')
    def test_saved_result_reused_and_contract_change_rejected(self, _):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []
            def call(text):
                calls.append(text)
                return {'sentences': []}
            run_one(root, {'v': 1}, 'synthetic', call)
            run_one(root, {'v': 1}, 'synthetic', call)
            self.assertEqual(len(calls), 1)
            with self.assertRaises(ValueError):
                run_one(root, {'v': 2}, 'synthetic', call)


if __name__ == '__main__':
    unittest.main()
