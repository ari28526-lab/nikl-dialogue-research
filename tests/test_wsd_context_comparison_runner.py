import copy
import csv
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/python'))
from run_wsd_context_comparison import (project, execute_jobs, digest, safe_child,
                                        compare, reconstruct, canonical, exclusive, live_client)


def response(text):
    return {'sentences': [{'text': {'content': text, 'begin_offset': 0, 'length': len(text)},
                          'tokens': [{'text': {'content': text, 'begin_offset': 0, 'length': len(text)},
                                      'morphemes': [{'text': {'content': text, 'begin_offset': 0, 'length': len(text)},
                                                     'tag': 'NNG', 'sense': {'sense_no': 1}}]}]}]}


def maps(text):
    return [dict(utt_id='U', role='core', begin_utf32=0, end_utf32=len(text))]


def jobs():
    return [dict(id='00_'+mode, mode=mode, pair=0, text='한😀', text_sha256=digest('한😀'.encode()),
                 target_utt_id='U', mappings=maps('한😀')) for mode in ('standalone', 'context')]


class ProjectionTests(unittest.TestCase):
    def test_utf32_emoji_assignment(self):
        result = project(response('한😀'), '한😀', maps('한😀'))
        self.assertFalse(result['held'])
        self.assertEqual(result['assigned'][0]['end_in_utterance'], 2)

    def test_utf16_offset_is_held(self):
        res = response('한😀')
        res['sentences'][0]['tokens'][0]['text']['length'] = 3
        self.assertTrue(project(res, '한😀', maps('한😀'))['held'])

    def test_cross_boundary_token_is_held(self):
        mapping = [dict(utt_id='U', role='core', begin_utf32=0, end_utf32=1),
                   dict(utt_id='V', role='context', begin_utf32=2, end_utf32=3)]
        result = project(response('a b'), 'a b', mapping)
        self.assertFalse(result['assigned'])
        self.assertTrue(result['held'])

    def test_spacing_rewrite_is_held(self):
        self.assertTrue(project(response('ab'), 'a b', maps('a b'))['held'])

    def test_empty_response_is_held(self):
        self.assertTrue(project({}, 'a', maps('a'))['held'])

    def test_partial_response_is_held(self):
        self.assertTrue(project(response('a'), 'abc', maps('abc'))['held'])

    def test_overlap_is_held(self):
        res = response('a')
        res['sentences'].append(copy.deepcopy(res['sentences'][0]))
        self.assertTrue(project(res, 'a', maps('a'))['held'])

    def test_nonzero_global_sentence_offset(self):
        a = response('a')['sentences'][0]
        b = response('b')['sentences'][0]
        for item in (b['text'], b['tokens'][0]['text'], b['tokens'][0]['morphemes'][0]['text']):
            item['begin_offset'] = 2
        result = project({'sentences': [a, b]}, 'a b', maps('a b'))
        self.assertFalse(result['held'])
        self.assertEqual(len(result['assigned']), 2)


class ResumeTests(unittest.TestCase):
    def test_concurrent_guard_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with exclusive(Path(directory)):
                with self.assertRaises(OSError):
                    with exclusive(Path(directory)):
                        self.fail('second lock acquired')

    def test_completed_responses_never_recalled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []
            def call(text):
                calls.append(text)
                return response(text)
            execute_jobs(root, jobs(), {'v': 1}, call)
            execute_jobs(root, jobs(), {'v': 1}, call)
            self.assertEqual(len(calls), 2)
            self.assertEqual(json.loads((root/'STATE.json').read_text())['completed_calls'], 2)

    def test_crash_intent_refuses_automatic_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def failure(_):
                raise RuntimeError('DO_NOT_PERSIST_SECRET')
            with self.assertRaises(RuntimeError):
                execute_jobs(root, jobs(), {}, failure)
            self.assertNotIn('DO_NOT_PERSIST_SECRET', (root/'STATE.json').read_text())
            calls = []
            with self.assertRaisesRegex(ValueError, 'uncertain_prior_call'):
                execute_jobs(root, jobs(), {}, lambda text: calls.append(text))
            self.assertFalse(calls)

    def test_tampered_response_and_changed_contract_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            execute_jobs(root, jobs(), {'v': 1}, response)
            with self.assertRaisesRegex(ValueError, 'contract_changed'):
                execute_jobs(root, jobs(), {'v': 2}, response)
            path = root/'00_context.result.json'
            result = json.loads(path.read_text())
            result['response'] = {}
            path.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, 'integrity_failed'):
                execute_jobs(root, jobs(), {'v': 1}, response)

    def test_time_budget_before_call(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            execute_jobs(Path(directory), jobs(), {}, lambda text: calls.append(text), seconds=0)
            self.assertFalse(calls)

    def test_budget_rejects_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'new'
            with self.assertRaisesRegex(ValueError, 'budget_exceeded'):
                execute_jobs(root, jobs()*19, {}, response)
            self.assertFalse(root.exists())

    def test_morph_change_not_compared_as_sense_change(self):
        items = [dict(pair=0, mode=m, target_utt_id='U', projection=project(response('a'), 'a', maps('a')))
                 for m in ('standalone', 'context')]
        items[1]['projection']['assigned'][0]['pos'] = 'VV'
        self.assertEqual(compare(items)['pairs'][0]['status'], 'hold_mapping_or_segmentation')

    def test_sense_change_is_not_improvement(self):
        items = [dict(pair=0, mode=m, target_utt_id='U', projection=project(response('a'), 'a', maps('a')))
                 for m in ('standalone', 'context')]
        items[1]['projection']['assigned'][0]['sense']['sense_no'] = 2
        result = compare(items)
        self.assertEqual(result['pairs'][0]['changed_senses'], 1)
        self.assertFalse(result['semantic_improvement_established'])

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                safe_child(Path(directory), '../outside')


class ReconstructionTests(unittest.TestCase):
    def test_reconstruct_and_detect_changed_offsets_or_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root/'files/C'
            folder.mkdir(parents=True)
            buf = io.StringIO(newline='')
            writer = csv.DictWriter(buf, fieldnames=['utt_id', 'speaker_id', 'source_row_index', 'form'])
            writer.writeheader()
            writer.writerows([dict(utt_id='C.1', speaker_id='A', source_row_index=1, form='한😀'),
                              dict(utt_id='C.2', speaker_id='B', source_row_index=2, form='가\n나')])
            data = gzip.compress(buf.getvalue().encode())
            (folder/'utterances.csv.gz').write_bytes(data)
            receipt = canonical({'outputs': {'utterances.csv.gz': {'sha256': digest(data)}}})
            (folder/'RECEIPT.json').write_bytes(receipt)
            refname = 'files/C/RECEIPT.json'
            refs = {refname: dict(morph_receipt_sha256=digest(receipt), utterances_sha256=digest(data))}
            text = '한😀 가 나'
            pair = dict(morph_receipt=refname, request_sha256=digest(text.encode()), context_request_chars=len(text),
                        target_utt_id='C.2', target_begin_utf32=3, target_end_utf32=6, standalone_request_chars=3)
            window = dict(morph_receipt=refname, request_sha256=pair['request_sha256'], context_start=0, context_end=2,
                          mappings=[dict(utt_id='C.1', speaker_id='A', source_row_index=1, role='context', begin_utf32=0, end_utf32=2),
                                    dict(utt_id='C.2', speaker_id='B', source_row_index=2, role='core', begin_utf32=3, end_utf32=6)])
            self.assertEqual(reconstruct(pair, window, refs, root), (text, '가 나'))
            bad = copy.deepcopy(pair)
            bad['target_begin_utf32'] = 2
            with self.assertRaisesRegex(ValueError, 'offset_changed'):
                reconstruct(bad, window, refs, root)
            (folder/'utterances.csv.gz').write_bytes(gzip.compress(b'tampered'))
            with self.assertRaisesRegex(ValueError, 'sha_changed'):
                reconstruct(pair, window, refs, root)

    def test_live_adapter_uses_exact_options_and_deadline_without_network(self):
        from bareunpy.bareun.language_service_pb2 import AnalyzeSyntaxResponse
        from bareunpy.bareun.lang_common_pb2 import EncodingType
        recorded = []
        class Spy:
            def __init__(self, *args, **kwargs):
                pass
            def analyze_syntax(self, request, **kwargs):
                recorded.append((request, kwargs))
                return AnalyzeSyntaxResponse()
        with patch('run_wsd_context_comparison.load_api_key', return_value=('synthetic_key', 'test')), \
             patch('bareunpy.bareun.language_service_connect.LanguageServiceClientSync', Spy):
            _, call = live_client({'secret': {}})
            call('한😀')
        self.assertEqual(len(recorded), 1)
        request, kwargs = recorded[0]
        self.assertEqual(request.encoding_type, EncodingType.UTF32)
        self.assertEqual(request.document.content, '한😀')
        self.assertTrue(request.with_sense)
        self.assertFalse(request.auto_split_sentence)
        self.assertEqual(kwargs['timeout_ms'], 60000)


if __name__ == '__main__':
    unittest.main()
