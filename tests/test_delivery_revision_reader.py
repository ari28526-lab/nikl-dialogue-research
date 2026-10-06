from contextlib import closing
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/python'))
import build_delivery_semantic_links as m
import update_delivery_revision as updates
import query_delivery_links as q
from test_delivery_semantic_links import fixture


def revised_fixture(base):
    root, entries = fixture(base)
    links = root/'semantic_links'; links.mkdir()
    pkg = m.Package(root)
    try:
        m.build(pkg, links, entries, sample=True)
    finally:
        pkg.db.close()
    m.save(root/'INVENTORY.json', {'fixture': True})
    m.save(root/'COPY_FINAL.json', dict(status='declared_scope_copied_sha_verified',
        ledger_sha256=m.sha(root/'COPY_LEDGER.sqlite'), inventory_sha256=m.sha(root/'INVENTORY.json')))
    updates.initialize(root)
    old = q.context(root, links, 'modu', 'S.2')
    native_rel = old['source_discourse']['path']
    native = m.read(root/native_rel)
    native['utterances'][0]['analysis']['review_note'] = 'explicit test correction'
    stage = base/'changed'; stage.mkdir()
    m.save(stage/'native.json', native)
    link_doc = next((links/'documents').rglob('*.links.json.gz'))
    link_rel = link_doc.relative_to(root).as_posix()
    link = m.read(link_doc)
    link['source_discourse'].update(sha256=m.sha(stage/'native.json'), bytes=(stage/'native.json').stat().st_size)
    m.save(stage/'links.json.gz', link)
    receipt = m.read(link_doc.with_name(link_doc.name+'.receipt.json'))
    receipt.update(sha256=m.sha(stage/'links.json.gz'), source_sha256=m.sha(stage/'native.json'))
    m.save(stage/'receipt.json', receipt)
    changes = dict(schema='delivery_changes.v1', revision='r1', parent=None, affected_documents=['S'], files=[])
    for logical, file in [(native_rel, 'native.json'), (link_rel, 'links.json.gz'), (link_rel+'.receipt.json', 'receipt.json')]:
        path = stage/file
        changes['files'].append(dict(logical_path=logical, source=str(path), sha256=m.sha(path), bytes=path.stat().st_size))
    updates.apply(root, changes)
    return root, changes


class ReaderTests(unittest.TestCase):
    def test_selected_revision_and_relocation_without_audio_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = revised_fixture(Path(tmp))
            moved = Path(tmp)/'relocated'; shutil.copytree(root, moved)
            real_open = Path.open
            def guarded(path, *args, **kwargs):
                if path.suffix == '.wav': raise AssertionError('Unchanged audio must not be read')
                return real_open(path, *args, **kwargs)
            with patch.object(Path, 'open', guarded):
                result = q.context(moved, moved/'semantic_links', 'modu', 'S.2', revision='r1')
            self.assertEqual(result['utterances'][0]['analysis']['review_note'], 'explicit test correction')
            original = q.context(moved, moved/'semantic_links', 'modu', 'S.2')
            self.assertNotIn('review_note', original['utterances'][0]['analysis'])
            self.assertEqual(len(result['utterances']), 3)

    def test_changed_native_without_matching_link_receipt_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, changes = revised_fixture(Path(tmp))
            changes.update(revision='native_only', files=changes['files'][:1])
            updates.apply(root, changes)
            with self.assertRaisesRegex(ValueError, 'Native discourse SHA mismatch'):
                q.context(root, root/'semantic_links', 'modu', 'S.2', revision='native_only')


if __name__ == '__main__': unittest.main()
