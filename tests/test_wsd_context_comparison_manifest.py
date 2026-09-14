import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/python'))
from prepare_wsd_context_comparison_manifest import select, prepare


def window(index, length, speakers=('A',)):
    return dict(source_file='NIKL_DIALOGUE_2020_v1/C.csv', status='planned',
                conversation_id='C', window_index=index, morph_receipt='files/C/RECEIPT.json',
                request_sha256='0' * 64, request_chars=200,
                mappings=[dict(utt_id=f'C.{index}.{i}', role='core', speaker_id=s,
                               begin_utf32=i * 100, end_utf32=i * 100 + length)
                          for i, s in enumerate(speakers)])


class ComparisonManifestTests(unittest.TestCase):
    def test_distinct_windows_and_no_text(self):
        result = select([window(0, 5), window(1, 90), window(2, 30, ('A', 'B'))], ('2020',))
        self.assertEqual(len({p['window_index'] for p in result}), 3)
        self.assertEqual({p['stratum'] for p in result}, {'short_core', 'long_core', 'multi_speaker'})
        self.assertNotIn('form', json.dumps(result))

    def test_hold_and_empty_speakers_do_not_satisfy_strata(self):
        held = window(0, 5)
        held['status'] = 'hold_empty_text'
        with self.assertRaises(ValueError):
            select([held, window(1, 90), window(2, 30, ('', 'A'))], ('2020',))

    def test_tampered_or_failed_audit_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = gzip.compress(b'')
            (root / 'conversation_windows.jsonl.gz').write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            (root / 'REPORT.json').write_text(json.dumps({'output_sha256': digest}))
            for audit in ({'passed': False, 'plan_sha256': digest},
                          {'passed': True, 'plan_sha256': 'wrong'}):
                (root / 'AUDIT.json').write_text(json.dumps(audit))
                with self.assertRaisesRegex(ValueError, 'binding_failed'):
                    prepare(root, root / 'AUDIT.json')


if __name__ == '__main__':
    unittest.main()
