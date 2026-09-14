from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/python'))
from diagnose_wsd_short_context import crop, run_batch, select_jobs
from run_wsd_context_comparison import digest
from connectrpc.code import Code
from connectrpc.errors import ConnectError


def fixture():
    texts = ['a'*100, 'b'*81, 'c'*100, 'd'*200, 'e'*400]
    mappings, offset = [], 0
    for i, text in enumerate(texts):
        mappings.append(dict(utt_id=str(i), begin_utf32=offset, end_utf32=offset+len(text)))
        offset += len(text)+1
    context = dict(id='00_context', text=' '.join(texts), mappings=mappings, target_utt_id='1')
    solo = dict(id='00_standalone', text=texts[1], text_sha256=digest(texts[1].encode()),
                target_utt_id='1', mappings=[dict(utt_id='1', begin_utf32=0, end_utf32=81)])
    return [solo, context]


class ShortContextTests(unittest.TestCase):
    def test_whole_utterances_and_offsets(self):
        job = fixture()[1]
        for cap in (300, 600):
            out = crop(job, cap)
            self.assertLessEqual(len(out['text']), cap)
            for mapping in out['mappings']:
                expected = next(m for m in job['mappings'] if m['utt_id'] == mapping['utt_id'])
                self.assertEqual(out['text'][mapping['begin_utf32']:mapping['end_utf32']],
                                 job['text'][expected['begin_utf32']:expected['end_utf32']])
        self.assertEqual(len(select_jobs(fixture())), 3)

    def test_unicode_target_not_truncated(self):
        job = dict(text='앞 😀뒤 끝', target_utt_id='t', mappings=[
            dict(utt_id='a', begin_utf32=0, end_utf32=1),
            dict(utt_id='t', begin_utf32=2, end_utf32=4),
            dict(utt_id='b', begin_utf32=5, end_utf32=6)])
        self.assertEqual(crop(job, 2)['text'], '😀뒤')
        with self.assertRaises(ValueError):
            crop(job, 1)

    @patch('diagnose_wsd_context_request.storage')
    def test_control_failure_stops_and_repeat_makes_no_calls(self, _):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def call(text):
                calls.append(text)
                raise ConnectError(Code.UNAVAILABLE, 'secret')
            root = Path(directory)
            run_batch(root, {}, select_jobs(fixture()), call)
            run_batch(root, {}, select_jobs(fixture()), call)
            self.assertEqual(len(calls), 1)
            self.assertNotIn('secret', (root/'STATE.json').read_text())

    @patch('diagnose_wsd_context_request.storage')
    def test_at_most_three_and_no_retry_of_failed_context(self, _):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def call(text):
                calls.append(text)
                if len(calls) == 2:
                    raise ConnectError(Code.UNAVAILABLE, 'private')
                return {'sentences': []}
            root = Path(directory)
            run_batch(root, {}, select_jobs(fixture()), call)
            run_batch(root, {}, select_jobs(fixture()), call)
            self.assertEqual(len(calls), 3)
            self.assertEqual(len(set(calls)), 3)
            with self.assertRaises(ValueError):
                run_batch(root, {'changed': True}, select_jobs(fixture()), call)


if __name__ == '__main__':
    unittest.main()
