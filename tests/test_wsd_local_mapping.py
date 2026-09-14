import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/python'))
from diagnose_wsd_local_mapping import diagnose
from audit_wsd_local_mapping import verify_candidate


def fixture():
    text = 'abc def ghi'
    mappings = [dict(utt_id=str(i),role='core',begin_utf32=b,end_utf32=b+3)
                for i,b in enumerate([0,4,8])]
    tokens = []
    for m in mappings:
        t = dict(content=text[m['begin_utf32']:m['end_utf32']],begin_offset=m['begin_utf32'],length=3)
        tokens.append(dict(text=copy.deepcopy(t),morphemes=[dict(text=copy.deepcopy(t),tag='NNG')]))
    response = dict(sentences=[dict(text=dict(content=text,begin_offset=0,length=len(text)),tokens=tokens)])
    return response, text, mappings


class LocalMappingTests(unittest.TestCase):
    def statuses(self, result):
        return [r['status'] for r in result['ledger']]

    def test_valid_all_candidates_not_semantic_pass(self):
        result=diagnose(*fixture())
        self.assertEqual(self.statuses(result), ['candidate_mapping_verified']*3)
        self.assertFalse(result['production_ready'])
        self.assertFalse(result['semantic_quality_verified'])

    def test_morph_outside_token_holds_both_affected_utterances(self):
        r,t,m=fixture()
        r['sentences'][0]['tokens'][0]['morphemes'][0]['text']['length']=5
        self.assertEqual(self.statuses(diagnose(r,t,m)),
                         ['hold_mapping','hold_mapping','candidate_mapping_verified'])

    def test_saved_failure_pattern_stays_local_and_unrepaired(self):
        r,t,m=fixture()
        token=r['sentences'][0]['tokens'][1]
        token['text'].update(content='d',length=1)
        token['morphemes'][0]['text'].update(content='de',length=2)
        before=copy.deepcopy(r)
        result=diagnose(r,t,m)
        self.assertEqual(self.statuses(result),
                         ['candidate_mapping_verified','hold_mapping','candidate_mapping_verified'])
        self.assertEqual(r,before)
        self.assertFalse(result['coordinates_repaired'])

    def test_unknown_out_of_input_span_holds_whole_request(self):
        r,t,m=fixture()
        r['sentences'][0]['tokens'][1]['morphemes'][0]['text']['begin_offset']=100
        self.assertEqual(self.statuses(diagnose(r,t,m)), ['hold_mapping']*3)

    def test_missing_token_only_holds_missing_utterance(self):
        r,t,m=fixture()
        r['sentences'][0]['tokens'].pop(1)
        self.assertEqual(self.statuses(diagnose(r,t,m)),
                         ['candidate_mapping_verified','hold_mapping','candidate_mapping_verified'])

    def test_duplicate_token_not_silent(self):
        r,t,m=fixture()
        r['sentences'][0]['tokens'].append(copy.deepcopy(r['sentences'][0]['tokens'][1]))
        result=diagnose(r,t,m)
        self.assertEqual(result['ledger'][1]['status'],'hold_mapping')
        self.assertIn('overlapping_token_coverage',result['ledger'][1]['reasons'])

    def test_cross_utterance_token_holds_both(self):
        r,t,m=fixture()
        token=r['sentences'][0]['tokens'][0]
        token['text'].update(content=t[:7],length=7)
        token['morphemes'][0]['text'].update(content=t[:7],length=7)
        r['sentences'][0]['tokens'].pop(1)
        self.assertEqual(self.statuses(diagnose(r,t,m)),
                         ['hold_mapping','hold_mapping','candidate_mapping_verified'])

    def test_bad_sentence_and_bad_token_anchors_fail_closed(self):
        for level in ['sentence','token']:
            r,t,m=fixture()
            target=r['sentences'][0] if level=='sentence' else r['sentences'][0]['tokens'][1]
            target['text']['content']='wrong'
            self.assertEqual(self.statuses(diagnose(r,t,m)), ['hold_mapping']*3)

    def test_empty_response_and_empty_morphs(self):
        r,t,m=fixture()
        self.assertEqual(self.statuses(diagnose({},t,m)), ['hold_mapping']*3)
        r['sentences'][0]['tokens'][1]['morphemes']=[]
        self.assertEqual(self.statuses(diagnose(r,t,m)),
                         ['candidate_mapping_verified','hold_mapping','candidate_mapping_verified'])

    def test_duplicate_or_overlapping_mapping_rejected(self):
        r,t,m=fixture()
        m[1]['utt_id']=m[0]['utt_id']
        with self.assertRaises(ValueError): diagnose(r,t,m)
        r,t,m=fixture()
        m[1]['begin_utf32']=2
        with self.assertRaises(ValueError): diagnose(r,t,m)

    def test_nonspace_mapping_gap_holds_whole_request(self):
        r,t,m=fixture()
        r['sentences'][0]['tokens'].pop(1)
        m.pop(1)
        self.assertEqual(self.statuses(diagnose(r,t,m)), ['hold_mapping']*2)

    def test_independent_audit_agrees_on_coordinate_mutations(self):
        # Valid candidates must survive an independent geometry implementation.
        # Exercise malformed, empty, crossing, overlapping and out-of-input spans.
        for ti in range(3):
            for begin in range(-1,14):
                for length in range(6):
                    r,t,m=fixture()
                    r['sentences'][0]['tokens'][ti]['morphemes'][0]['text'].update(
                        begin_offset=begin,length=length)
                    result=diagnose(r,t,m)
                    for row,mapping in zip(result['ledger'],m,strict=True):
                        if row['status']=='candidate_mapping_verified':
                            self.assertEqual(verify_candidate(r,t,mapping),row['verified_morphemes'])

    def test_independent_auditor_rejects_bad_candidate(self):
        r,t,m=fixture()
        r['sentences'][0]['tokens'][1]['morphemes'][0]['text']['length']=4
        with self.assertRaises(ValueError): verify_candidate(r,t,m[1])


if __name__=='__main__': unittest.main()
