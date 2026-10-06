import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import evaluate_delivery_acceptance_v2 as m


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        m.io.save(self.root/'old_plan.json',{'synthetic':True})
        m.io.save(self.root/'tool/BUNDLE_MANIFEST.json',{'files':[]})
        m.io.save(self.root/'pinned.json',{'status':'synthetic_complete'})
        listing=self.root/'gap/MISSING_CLIPS.jsonl';listing.parent.mkdir();listing.write_text('synthetic only\n')
        m.io.save(self.root/'gap/FINAL.json',dict(status='declared_clip_gap_accounting_complete_source_presence_unverified',missing_clips=2995,documents=17156,utterances=5157997,listing_sha256=m.io.sha(listing),counts={'synthetic':2995},missing_empty_text=2995))
        self.plan=dict(prior_plan='old_plan.json',prior_plan_sha256=m.io.sha(self.root/'old_plan.json'),pinned_receipts={'pinned.json':m.io.sha(self.root/'pinned.json')},tool_manifests=['tool/BUNDLE_MANIFEST.json'],explicit_provenance={},gap_receipt='gap/FINAL.json')
    def tearDown(self):self.tmp.cleanup()
    def test_complete_technical_receipts_do_not_hide_audio_holds(self):
        with patch.object(m.prior,'audit',return_value={'status':'receipt_chain_verified_with_remaining_acceptance','receipt_sha256':{}}):
            result=m.evaluate(self.root,self.plan)
        self.assertFalse(result['delivery_complete']);self.assertFalse(result['DELIVERY_FINAL_created'])
        self.assertEqual(sum(x['status']=='unresolved' for x in result['requirements']),2)
        self.assertFalse((self.root/'DELIVERY_FINAL.json').exists())
    def test_pinned_receipt_change_rejected(self):
        (self.root/'pinned.json').write_text('{}')
        with patch.object(m.prior,'audit',return_value={'status':'ok','receipt_sha256':{}}):
            with self.assertRaises(ValueError):m.evaluate(self.root,self.plan)
    def test_wrong_gap_count_rejected(self):
        p=self.root/'gap/FINAL.json';x=m.io.read(p);x['missing_clips']=1;m.io.save(p,x)
        with patch.object(m.prior,'audit',return_value={'status':'ok','receipt_sha256':{}}):
            with self.assertRaises(ValueError):m.evaluate(self.root,self.plan)


if __name__=='__main__':unittest.main()
