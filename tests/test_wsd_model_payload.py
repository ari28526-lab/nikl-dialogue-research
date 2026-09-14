import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from wsd_model_payload import compact

class Tests(unittest.TestCase):
    def setUp(self):
        entry={'target':'e','group':'g','sense_no':'1','word':'말','pos':'명사','definition':'뜻풀이','state':'compatible'}
        t={'target_id':'0:0:0','existing_bareun':{'utt_id':'u','morph_surface':'말','pos':'NNG','token_begin_utf32':'0','token_length_utf32':'1','token_surface':'말','token_index':'0','morph_index':'0'},'dictionary_entries':[entry],'candidate_groups':['g','h']}
        self.r={'request_id':'0:0','context':[{'utt_id':'u','speaker_id':'s','form':'말'}],'targets':[t,copy.deepcopy(t)]};self.r['targets'][1]['target_id']='0:0:1'
    def test_definitions_deduplicated_and_targets_retained(self):
        p=compact(self.r,{'u':'말'});self.assertEqual(len(p['dictionary_sets']),1);self.assertEqual(len(p['targets']),2);self.assertEqual(p['dictionary_sets']['D0']['entries'][0]['definition'],'뜻풀이')
    def test_outside_anchor_rejected(self):
        self.r['targets'][0]['existing_bareun']['token_begin_utf32']='2'
        with self.assertRaises(ValueError):compact(self.r,{'u':'말'})
    def test_surface_difference_is_explicit(self):
        p=compact(self.r,{'u':'발'});self.assertFalse(p['targets'][0]['token_surface_matches_span']);self.assertEqual(p['targets'][0]['observed_span_text'],'발')

if __name__=='__main__':unittest.main()
