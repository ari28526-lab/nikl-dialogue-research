"""Bounded synthetic backup tests; no production corpus/network access."""
import csv
import contextlib
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/python'))
import package_existing_textgrids as b


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path('work').resolve())
        self.root = Path(self.temp.name)
        self.modu = self.root / 'modu_release'
        self.seoul = self.root / 'seoul_original'
        self.out = self.root / 'backup'
        self.seoul.mkdir()
        self.rows = []
        self.total = 0
        for i in range(5):
            p = self.modu / f'modu/alignment_textgrids_v1/textgrids/2020/source/{i}.TextGrid'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((f'Synthetic TextGrid {i}\n' * 80).encode())
            self.total += p.stat().st_size
            self.rows.append(dict(textgrid_path=p.relative_to(self.modu).as_posix(), textgrid_sha256=b.sha(p)))
        self.links = self.modu / 'modu/alignment_textgrids_v1/receipts/source.csv.gz'
        self.links.parent.mkdir(parents=True)
        self.write_links(self.rows + [dict(textgrid_path='', textgrid_sha256='')])
        p = self.seoul / 'original.TextGrid'
        p.write_bytes(b'Original synthetic Seoul TextGrid\n')
        self.receipt = self.root / 'seoul_receipt.json'
        b.save(self.receipt, dict(status='verified', files=[dict(relative_path=p.name, sha256=b.sha(p), bytes=p.stat().st_size)]))
        self.config = dict(modu_root=str(self.modu), seoul_root=str(self.seoul), seoul_receipt=str(self.receipt),
                           expected_seoul_files=1, entry_limit=2, piece_bytes=160,
                           source_floor_bytes=0, output_floor_bytes=0)
        self.config_path = self.root / 'config.json'
        b.save(self.config_path, self.config)

    def write_links(self, rows):
        with gzip.open(self.links, 'wt', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['textgrid_path', 'textgrid_sha256'])
            w.writeheader()
            w.writerows(rows)
        index = self.modu / 'modu/alignment_textgrids_v1/LINK_INDEX.csv.gz'
        with gzip.open(index, 'wt', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['source_file', 'links_relative', 'sha256'])
            w.writeheader()
            w.writerow(dict(source_file='synthetic', links_relative=self.links.relative_to(self.modu).as_posix(), sha256=b.sha(self.links)))
        b.save(self.modu / 'modu/TEXTGRID_FINAL.json', dict(status='passed_with_explicit_alignment_reviews', smoke=False,
               link_index_relative=index.relative_to(self.modu).as_posix(), link_index_sha256=b.sha(index),
               counts=dict(derived=5, bytes=self.total, no_mfa_alignment=1)))

    def tearDown(self):
        self.temp.cleanup()

    def run_backup(self, **kwargs):
        return b.run(self.config_path, self.out, **kwargs)

    def test_complete_bounded_chunks_and_accounting(self):
        r = self.run_backup()
        self.assertEqual((r['files'], r['parts']), (6, 3))
        f = b.read(self.out / 'PACKAGE_FINAL.json')
        self.assertEqual(f['corpus_counts'], dict(modu=5, seoul=1))
        self.assertTrue(all(p['bytes'] <= 160 for r in f['archives'] for p in r['pieces']))
        self.assertFalse(f['cloud_complete'])

    def test_resume_reuses_completed_archive_and_receipt(self):
        self.run_backup(max_parts=1)
        p = self.out / 'PART_00001.json'
        before = (b.sha(p), p.stat().st_mtime_ns)
        self.assertEqual(self.run_backup()['files'], 6)
        self.assertEqual(before, (b.sha(p), p.stat().st_mtime_ns))

    def test_changed_source_rejected_without_completion(self):
        p = self.modu / self.rows[0]['textgrid_path']
        p.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'source_sha_mismatch'):
            self.run_backup()
        self.assertFalse((self.out / 'PART_00001.json').exists())

    def test_changed_parent_rejected(self):
        self.run_backup(max_parts=1)
        self.write_links(self.rows + [dict(textgrid_path='', textgrid_sha256='')])
        p = self.modu / 'modu/TEXTGRID_FINAL.json'
        d = b.read(p)
        d['extra'] = 'changed'
        b.save(p, d)
        with self.assertRaisesRegex(ValueError, 'contract_or_code_changed'):
            self.run_backup()

    def test_changed_config_rejected(self):
        self.run_backup(max_parts=1)
        self.config['entry_limit'] = 3
        b.save(self.config_path, self.config)
        with self.assertRaisesRegex(ValueError, 'contract_or_code_changed'):
            self.run_backup()

    def test_changed_inventory_rejected(self):
        self.run_backup(inventory_only=True)
        with (self.out / 'LOCAL_INVENTORY.sqlite').open('ab') as f:
            f.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'inventory_changed'):
            self.run_backup()

    def test_completed_archive_damage_rejected(self):
        self.run_backup(max_parts=1)
        (self.out / 'textgrids_00001.zip').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'completed_archive_changed'):
            self.run_backup()

    def test_duplicate_source_path_rejected_atomically(self):
        self.write_links(self.rows + [self.rows[0]])
        with self.assertRaises(b.sqlite3.IntegrityError):
            self.run_backup()
        with contextlib.closing(b.sqlite3.connect(self.out / 'LOCAL_INVENTORY.sqlite')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM files').fetchone()[0], 0)

    def test_path_escape_rejected(self):
        self.write_links([dict(textgrid_path='../outside.TextGrid', textgrid_sha256='0' * 64)])
        with self.assertRaisesRegex(ValueError, 'path_outside_scope'):
            self.run_backup()

    def test_stop_marker(self):
        self.out.mkdir()
        (self.out / 'STOP').touch()
        with self.assertRaisesRegex(ValueError, 'stopped_by_marker'):
            self.run_backup()
        self.assertFalse((self.out / 'CONTRACT.json').exists())

    def test_resource_floor(self):
        self.config['output_floor_bytes'] = 2**60
        b.save(self.config_path, self.config)
        with self.assertRaisesRegex(ValueError, 'output_space_floor'):
            self.run_backup()

    def test_duplicate_lock(self):
        self.out.mkdir()
        with b.lock(self.out / 'RUN.lock'):
            with self.assertRaises(OSError):
                self.run_backup()

    def test_actual_process_crash_partial_preserved_then_resume(self):
        code = ('import sys,os;sys.path.insert(0,sys.argv[1]);import package_existing_textgrids as b;'
                'b.copy_hash=lambda src,dst:os._exit(42);b.run(sys.argv[2],sys.argv[3])')
        r = subprocess.run([sys.executable, '-c', code, str(Path(b.__file__).parent), str(self.config_path), str(self.out)],
                           capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 42)
        partial = self.out / 'textgrids_00001.zip.partial'
        self.assertTrue(partial.exists())
        self.assertEqual(self.run_backup()['files'], 6)
        self.assertEqual(len(list(self.out.glob('incomplete_*/textgrids_00001.zip.partial'))), 1)

    def test_no_adoption_after_receipt_write_failure(self):
        real_save = b.save
        def fail_receipt(path, value):
            if Path(path).name == 'PART_00001.json':
                raise RuntimeError('receipt_write_failure')
            real_save(path, value)
        with patch.object(b, 'save', fail_receipt):
            with self.assertRaisesRegex(RuntimeError, 'receipt_write_failure'):
                self.run_backup()
        self.assertFalse((self.out / 'PART_00001.json').exists())
        self.assertEqual(self.run_backup()['files'], 6)
        self.assertEqual(len(list(self.out.glob('incomplete_*/textgrids_00001.zip'))), 1)


if __name__ == '__main__':
    unittest.main()
