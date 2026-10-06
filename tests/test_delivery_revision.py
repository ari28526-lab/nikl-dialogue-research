from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import update_delivery_revision as m


def fixture(base):
    root=base/'package';root.mkdir();(root/'audio').mkdir();(root/'analysis').mkdir()
    (root/'audio/a.wav').write_bytes(b'immutable original audio')
    (root/'analysis/a.json').write_bytes(b'{"version":1}')
    with closing(sqlite3.connect(root/'COPY_LEDGER.sqlite')) as db:
        db.execute('CREATE TABLE files(relative TEXT UNIQUE COLLATE NOCASE,bytes INTEGER,sha256 TEXT,copied INTEGER)')
        for rel in ['audio/a.wav','analysis/a.json']:
            p=root/rel;db.execute('INSERT INTO files VALUES(?,?,?,1)',(rel,p.stat().st_size,m.sha(p)))
        db.commit()
    m.save(root/'INVENTORY.json',dict(files=2))
    m.save(root/'COPY_FINAL.json',dict(status='declared_scope_copied_sha_verified',ledger_sha256=m.sha(root/'COPY_LEDGER.sqlite'),inventory_sha256=m.sha(root/'INVENTORY.json')))
    m.initialize(root)
    source=base/'new.json';source.write_bytes(b'{"version":2}')
    change=dict(schema='delivery_changes.v1',revision='r1',parent=None,affected_documents=['a'],files=[dict(logical_path='analysis/a.json',source=str(source),bytes=source.stat().st_size,sha256=m.sha(source))])
    return root,change


class RevisionTests(unittest.TestCase):
    def test_only_changed_files_are_read_copied_and_resolved_after_relocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,change=fixture(Path(tmp));original_sha=m.sha(root/'audio/a.wav');real_sha=m.sha
            def guarded_sha(path):
                self.assertNotEqual(Path(path).name,'a.wav','Unchanged audio must not be rehashed')
                self.assertNotEqual(Path(path).name,'COPY_LEDGER.sqlite','Bound base ledger must not be rehashed per update')
                return real_sha(path)
            with patch.object(m,'sha',guarded_sha),patch.object(Path,'rglob',side_effect=AssertionError('No tree scan')):
                plan=m.plan(root,change);self.assertEqual(plan['copy_files'],1)
                result=m.apply(root,change);m.apply(root,change)
                self.assertEqual(len(result['changed_files']),1)
            self.assertEqual(m.sha(root/'audio/a.wav'),original_sha)
            self.assertEqual((root/'analysis/a.json').read_bytes(),b'{"version":1}')
            relocated=Path(tmp)/'elsewhere';shutil.copytree(root,relocated)
            self.assertEqual(m.resolve(relocated,'r1','analysis/a.json',True)['path'],'updates/revisions/r1/files/analysis/a.json')
            self.assertEqual(m.resolve(relocated,'r1','audio/a.wav',True)['path'],'audio/a.wav')
            (relocated/'updates/revisions/r1/files/analysis/a.json').write_bytes(b'{"version":3}')
            with self.assertRaisesRegex(ValueError,'SHA'):m.resolve(relocated,'r1','analysis/a.json',True)

    def test_noop_and_parent_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,change=fixture(Path(tmp));m.apply(root,change)
            change['revision']='r2';change['parent']='r1'
            plan=m.plan(root,change);self.assertEqual(plan['copy_files'],0)
            # A same-hash manifest entry reuses the already verified revision.
            Path(change['files'][0]['source']).unlink()
            result=m.apply(root,change);self.assertEqual(result['changed_files'],[])
            self.assertIn('/r1/',m.resolve(root,'r2','analysis/a.json',True)['path'])

    def test_wrong_source_hash_never_publishes_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,change=fixture(Path(tmp));change['files'][0]['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'SHA'):m.apply(root,change)
            self.assertFalse((root/'updates/revisions/r1/REVISION.json').exists())
            self.assertEqual((root/'analysis/a.json').read_bytes(),b'{"version":1}')

    def test_path_and_immutable_contract_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,change=fixture(Path(tmp));m.apply(root,change)
            change['files'][0]['logical_path']='analysis/other.json'
            with self.assertRaisesRegex(ValueError,'different inputs'):m.apply(root,change)
            for value in ['../outside','F:/absolute','/absolute','a\\b']:
                with self.assertRaises(ValueError):m.safe(root,value)


if __name__=='__main__':unittest.main()
