import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('pcmcopy', Path(__file__).parents[1] / 'scripts/python/copy_confirmed_pcm_supplement.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CopyTests(unittest.TestCase):
    def fixture(self, root):
        source = root / 'SDRW2000000027.1.1.339.pcm'
        raw = b'\x00\x10' * 50000
        source.write_bytes(raw)
        return dict(utterance_id=source.stem, year='2020', source_pcm_path=str(source), read_evidence=dict(bytes=len(raw), prefix_bytes=65536, prefix_sha256=hashlib.sha256(raw[:65536]).hexdigest()))

    def test_full_copy_and_existing_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = self.fixture(root)
            target = root / 'out' / 'clip.pcm'
            receipt = m.copy_one(item, target)
            self.assertTrue(receipt['independently_reopened_destination'])
            self.assertEqual(target.read_bytes(), Path(item['source_pcm_path']).read_bytes())
            self.assertTrue(m.copy_one(item, target)['existing_destination_verified'])
            target.write_bytes(b'x' * item['read_evidence']['bytes'])
            with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
                m.copy_one(item, target)

    def test_changed_source_and_partial_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = self.fixture(root)
            target = root / 'out.pcm'
            Path(item['source_pcm_path']).write_bytes(b'x' * item['read_evidence']['bytes'])
            with self.assertRaisesRegex(ValueError, 'prefix changed'):
                m.copy_one(item, target)
            self.assertFalse(target.exists())
            partial = target.with_suffix('.pcm.partial')
            partial.write_bytes(b'preserve')
            with self.assertRaisesRegex(ValueError, 'interrupted partial'):
                m.copy_one(item, target)
            self.assertEqual(partial.read_bytes(), b'preserve')

    def test_identity_guard(self):
        with self.assertRaises(ValueError):
            m.relative(dict(utterance_id='../bad', year='2020', source_pcm_path='bad.pcm'))

    def test_isolated_unicode_source_path(self):
        with tempfile.TemporaryDirectory(prefix='원음성_') as tmp:
            root = Path(tmp)
            item = self.fixture(root)
            result = m.isolated(item, root / '복사본' / 'clip.pcm')
            self.assertEqual(result['bytes'], item['read_evidence']['bytes'])


if __name__ == '__main__':
    unittest.main()
