import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/python'))
import benchmark_lossless_gzip as bench


class LosslessBenchmarkTests(unittest.TestCase):
    def setUp(self):
        temporary_parent = Path(__file__).resolve().parents[1] / 'work'
        temporary_parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary_parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = json.dumps({'synthetic': ['example'] * 100}).encode()
        self.payload = gzip.compress(self.raw, mtime=0)
        (self.root / 'SAMPLE.json.gz').write_bytes(self.payload)
        self.receipt = self.root / 'RECEIPT.json'
        self.data = dict(status='complete_with_reviews', outputs={'SAMPLE.json.gz': dict(
            bytes=len(self.payload), sha256=hashlib.sha256(self.payload).hexdigest())})
        self.save()

    def save(self):
        self.receipt.write_text(json.dumps(self.data), encoding='utf-8')

    def run_benchmark(self, **kwargs):
        with patch.object(bench, 'available_memory', return_value=2**31):
            return bench.benchmark(self.receipt, **kwargs)

    def test_lossless_content_and_unchanged_inputs(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.run_benchmark()
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(result['samples'][0]['all_roundtrips_byte_identical'])
        self.assertEqual(set(result['totals']), {'1', '3', '6', '9'})
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_changed_payload_is_rejected(self):
        (self.root / 'SAMPLE.json.gz').write_bytes(self.payload + b'changed')
        with self.assertRaisesRegex(ValueError, 'receipt_binding'):
            self.run_benchmark()

    def test_parent_path_in_receipt_is_rejected(self):
        self.data['outputs'] = {'../SAMPLE.json.gz': next(iter(self.data['outputs'].values()))}
        self.save()
        with self.assertRaisesRegex(ValueError, 'basename_required'):
            self.run_benchmark()

    def test_uncompressed_limit_is_enforced(self):
        with self.assertRaisesRegex(ValueError, 'sample_limit'):
            self.run_benchmark(limit_mib=0)

    def test_memory_floor_preserves_active_worker(self):
        with patch.object(bench, 'available_memory', return_value=699 * 2**20):
            with self.assertRaisesRegex(MemoryError, 'active_worker_memory_floor'):
                bench.benchmark(self.receipt)


if __name__ == '__main__':
    unittest.main()
