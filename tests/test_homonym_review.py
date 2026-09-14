"""Meaningful audit of review identity and append-only human judgment handling."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('review',REPO/'scripts/python/build_homonym_review.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)

class ReviewTests(unittest.TestCase):
    def test_exported_identity_and_references(self):
        d=review.read(review.OUT/'review_data.json')
        self.assertEqual(len(d['starter']),10)
        self.assertEqual(len(d['cases']),1499)
        self.assertEqual(len({c['target_id'] for c in d['cases']}),1499)
        for c in d['cases']:
            s=d['sentences'][c['sentence']]
            self.assertIn(c['mp'],s['mp'])
            self.assertTrue(any(w['id']==c['word_id'] for w in s['words']))
            self.assertEqual({d['entries'][str(e)]['group_code'] for e in c['entry_ids']},set(c['candidate_groups']))
            for e in c['evidence']:
                self.assertIn(e['mp'],d['sentences'][e['sentence']]['mp'])
                doc='/'.join(e['sentence'].split('/')[:2])
                self.assertEqual(d['documents'][doc]['split'],'train')

    def test_human_revision_preserves_quote_and_rejects_invalid_candidate(self):
        with tempfile.TemporaryDirectory(dir=REPO/'work') as td:
            out=Path(td)
            (out/'review_data.json').write_text(json.dumps(dict(cases=[dict(id='H-TEST',target_id='abc',candidate_groups=[123,456])],source_receipt_sha256='test')),encoding='utf-8')
            (out/'judgments.jsonl').write_text('',encoding='utf-8')
            req=out/'request.json'
            with patch.object(review,'OUT',out),patch.object(review,'build') as rebuild:
                req.write_text(json.dumps(dict(case_id='H-TEST',status='chosen',group=123,user_quote='첫 후보로 판단합니다.')),encoding='utf-8')
                review.record(req)
                first=(out/'judgments.jsonl').read_bytes()
                req.write_text(json.dumps(dict(case_id='H-TEST',status='hold',group=None,user_quote='앞 판단을 보류합니다.')),encoding='utf-8')
                review.record(req)
                final=(out/'judgments.jsonl').read_bytes()
                self.assertTrue(final.startswith(first))
                rows=[json.loads(v) for v in final.decode('utf-8').splitlines()]
                self.assertEqual(rows[0]['user_quote'],'첫 후보로 판단합니다.')
                self.assertEqual(rows[1]['status'],'hold')
                self.assertEqual([r['event_id'] for r in rows],[1,2])
                req.write_text(json.dumps(dict(case_id='H-TEST',status='chosen',group=999,user_quote='없는 후보')),encoding='utf-8')
                with self.assertRaises(AssertionError):review.record(req)
                self.assertEqual((out/'judgments.jsonl').read_bytes(),final)
                self.assertEqual(rebuild.call_count,2)

if __name__=='__main__':unittest.main()
