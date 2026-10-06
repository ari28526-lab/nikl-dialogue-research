from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from test_delivery_semantic_links import fixture
import build_delivery_semantic_links as links
import audit_delivery_clip_gaps as audit


class GapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root,entries=fixture(self.base);stage=self.root/'metadata/semantic_links';stage.mkdir(parents=True)
        package=links.Package(self.root)
        try:links.build(package,stage,entries,sample=True)
        finally:package.db.close()
        self.stage=stage;self.out=self.base/'gap_audit'
    def tearDown(self):self.tmp.cleanup()
    def test_missing_empty_and_unaligned_separately_accounted(self):
        with patch.object(Path,'rglob',side_effect=AssertionError('No audio directory scan')):
            value=audit.run(self.root,self.out)
        self.assertEqual(value['missing_clips'],2);self.assertEqual(value['missing_empty_text'],1)
        self.assertEqual(value['documents'],1);self.assertEqual(value['utterances'],3)
        self.assertFalse(value['source_pcm_presence_verified'])
        again=audit.run(self.root,self.out)
        self.assertEqual(again['listing_sha256'],value['listing_sha256'])
    def test_link_receipt_tamper_rejected(self):
        final=links.read(self.stage/'FINAL.json');p=self.stage/final['receipts'][0]['path'];p.write_bytes(b'bad')
        with self.assertRaises(ValueError):audit.run(self.root,self.out)
    def test_native_source_tamper_rejected(self):
        final=links.read(self.stage/'FINAL.json');rp=self.stage/final['receipts'][0]['path']
        doc=links.read(rp.with_name(rp.name.removesuffix('.receipt.json')))
        (self.root/doc['source_discourse']['path']).write_text('{}')
        with self.assertRaises(ValueError):audit.run(self.root,self.out)


if __name__=='__main__':unittest.main()
