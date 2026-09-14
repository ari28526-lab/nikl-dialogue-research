from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/python'))
from run_wsd_short_context_pilot import acquire, attempt_inventory, verify_result
from run_wsd_context_comparison import atomic, digest
from connectrpc.code import Code
from connectrpc.errors import ConnectError


def job():
    return dict(id='00_standalone', text='synthetic', text_sha256=digest(b'synthetic'))


class PilotTests(unittest.TestCase):
    @patch('run_wsd_short_context_pilot.storage')
    def test_retry_once_then_reuse_without_calls(self, _):
        with tempfile.TemporaryDirectory() as directory:
            root, calls = Path(directory), []
            def call(text):
                calls.append(text)
                if len(calls) == 1:
                    raise ConnectError(Code.UNAVAILABLE, 'secret')
                return {'sentences': []}
            result, error = acquire(root, job(), {}, call, sleep=lambda _:None)
            self.assertIsNone(error)
            self.assertEqual(result['origin'], 'new_api_call')
            acquire(root, job(), {}, call)
            self.assertEqual(len(calls), 2)
            self.assertEqual(attempt_inventory(root), (2, 18))
            self.assertNotIn('secret', (root/job()['id']/'attempt_1.error.json').read_text())

    @patch('run_wsd_short_context_pilot.storage')
    def test_two_failures_never_become_three(self, _):
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            def call(text):
                calls.append(text)
                raise ConnectError(Code.UNAVAILABLE, 'private')
            for _ in range(2):
                result,error=acquire(Path(directory),job(),{},call,sleep=lambda _:None)
                self.assertIsNone(result)
            self.assertEqual(len(calls),2)

    @patch('run_wsd_short_context_pilot.storage')
    def test_auth_failure_is_not_retried(self, _):
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            def call(text):
                calls.append(text)
                raise ConnectError(Code.UNAUTHENTICATED, 'private')
            acquire(Path(directory),job(),{},call)
            self.assertEqual(len(calls),1)

    def test_uncertain_intent_blocks_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            folder=root/job()['id']
            folder.mkdir()
            atomic(folder/'attempt_1.intent.json',dict(binding={},chars=9))
            def forbidden(_): self.fail('must not call')
            result,error=acquire(root,job(),{},forbidden)
            self.assertIsNone(result)
            self.assertEqual(error['status'],'paused_uncertain_attempt')

    @patch('run_wsd_short_context_pilot.MAX_CALLS',0)
    def test_budget_blocks_before_call(self):
        with tempfile.TemporaryDirectory() as directory:
            result,error=acquire(Path(directory),job(),{},lambda _:self.fail('must not call'))
            self.assertEqual(error['status'],'paused_call_budget')

    def test_invalid_result_rejected(self):
        with self.assertRaises(ValueError):
            verify_result(dict(binding={},response={},response_sha256='bad'),{})


if __name__ == '__main__':
    unittest.main()
